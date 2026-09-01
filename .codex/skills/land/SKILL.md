---
name: land
description:
  Perform a bounded, head-bound final review/check sweep and synchronously merge
  an already-ready pull request only while its tracker issue is in Merging.
---

# Land

Load this skill only after the tracker issue enters `Merging`. The Human Review
handoff owns the earlier draft-to-review transition. Landing never changes draft
state.

## Fail-closed contract

- Confirm the tracker issue is still in `Merging` before any merge command.
- Require an open PR with `isDraft == false`. If it is draft, return it to
  Human Review and stop; readiness and merging never occur in the same landing
  pass.
- Wait only for actual pending checks or an actual Codex review-summary row that
  is not complete. Every such wait is bounded to ten minutes.
- Retry `UNKNOWN` mergeability for at most one minute.
- After all waits and the merge-queue check, take a completely fresh
  authoritative snapshot and fetch every page of inline feedback.
- Abort on a changed head, new feedback, pending/failed checks or review,
  non-clean mergeability, or a state change. Do not retry against a new head.
- Direct merge is permitted only when no active merge-queue rule applies. An
  inconclusive rules check for an organization-owned repository is an external
  blocker. Do not create an asynchronous merge, enable auto-merge, or bypass
  branch rules.
- Bind the merge to the inspected head with `--match-head-commit`. Move the
  tracker issue to `Done` only after GitHub reports `MERGED`.

## Reference procedure

Use temporary files so every evaluated value comes from one named snapshot:

```bash
set -euo pipefail

preliminary_snapshot=$(mktemp)
preliminary_inline=$(mktemp)
preliminary_comments=$(mktemp)
preliminary_check_runs=$(mktemp)
preliminary_status_history=$(mktemp)
preliminary_statuses=$(mktemp)
review_poll=$(mktemp)
final_snapshot=$(mktemp)
final_inline=$(mktemp)
final_comments=$(mktemp)
final_reviews=$(mktemp)
final_check_runs=$(mktemp)
final_status_history=$(mktemp)
final_statuses=$(mktemp)
rules_file=$(mktemp)
rules_error=$(mktemp)
trap 'rm -f "$preliminary_snapshot" "$preliminary_inline" "$preliminary_comments" "$preliminary_check_runs" "$preliminary_status_history" "$preliminary_statuses" "$review_poll" "$final_snapshot" "$final_inline" "$final_comments" "$final_reviews" "$final_check_runs" "$final_status_history" "$final_statuses" "$rules_file" "$rules_error"' EXIT

status_reducer=.codex/skills/land/scripts/latest-statuses.jq
[[ -r $status_reducer ]] || {
  printf 'Missing commit-status reducer: %s\n' "$status_reducer" >&2
  exit 1
}

snapshot_fields=number,title,body,state,isDraft,headRefOid,baseRefName,mergeable,comments,reviews,statusCheckRollup
gh pr view --json "$snapshot_fields" > "$preliminary_snapshot"
pr_number=$(jq -r .number "$preliminary_snapshot")
initial_head=$(jq -r .headRefOid "$preliminary_snapshot")
base_ref=$(jq -r .baseRefName "$preliminary_snapshot")
repo_nwo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
owner_type=$(gh api "repos/$repo_nwo" --jq .owner.type)

[[ $(jq -r .state "$preliminary_snapshot") == OPEN ]] || {
  printf 'PR is not open; stop landing.\n' >&2
  exit 1
}
if [[ $(jq -r .isDraft "$preliminary_snapshot") != false ]]; then
  printf 'PR is still draft; return to the Human Review handoff and stop.\n' >&2
  exit 1
fi

# Fetch and combine all inline-comment pages; inspect this with top-level
# comments and reviews before any wait.
gh api --paginate --slurp \
  "repos/$repo_nwo/pulls/$pr_number/comments?per_page=100" \
  | jq 'flatten' > "$preliminary_inline"
gh api --paginate --slurp \
  "repos/$repo_nwo/issues/$pr_number/comments?per_page=100" \
  | jq 'flatten' > "$preliminary_comments"
gh api --paginate --slurp \
  "repos/$repo_nwo/commits/$initial_head/check-runs?per_page=100" \
  | jq '[.[].check_runs[]]' > "$preliminary_check_runs"
gh api --paginate --slurp \
  "repos/$repo_nwo/commits/$initial_head/statuses?per_page=100" \
  | jq 'flatten' > "$preliminary_status_history"
# The statuses endpoint is newest-first and includes historical updates. Keep
# only the newest record for each context before evaluating the gate.
jq -f "$status_reducer" "$preliminary_status_history" > "$preliminary_statuses"

codex_review_pending() {
  jq '[.[].body
    | select(contains("codex-pull-request-review-summary"))
    | split("\n")[]
    | select(test("Code Review"; "i"))
    | select((test("Completed|Failed|Cancelled"; "i")) | not)
  ] | length' "$1"
}
codex_review_failed() {
  jq '[.[].body
    | select(contains("codex-pull-request-review-summary"))
    | split("\n")[]
    | select(test("Code Review"; "i"))
    | select(test("Failed|Cancelled"; "i"))
  ] | length' "$1"
}
export -f codex_review_pending codex_review_failed

(( $(codex_review_failed "$preliminary_comments") == 0 )) || {
  printf 'Codex review failed or was cancelled; return to Human Review.\n' >&2
  exit 1
}

review_pending=$(codex_review_pending "$preliminary_comments")
if (( review_pending > 0 )); then
  timeout 10m bash -c '
    for attempt in {1..60}; do
      gh api --paginate --slurp \
        "repos/$2/issues/$3/comments?per_page=100" | jq flatten > "$1"
      [[ $(codex_review_pending "$1") == 0 ]] && exit 0
      sleep 10
    done
    exit 124
  ' _ "$review_poll" "$repo_nwo" "$pr_number" || exit 1
fi

pending_checks=$((
  $(jq '[.[] | select(.status != "completed")] | length' "$preliminary_check_runs") +
  $(jq '[.[] | select(.state == "pending")] | length' "$preliminary_statuses")
))
if (( pending_checks > 0 )); then
  timeout 10m gh pr checks --watch || exit 1
fi

# The only mergeability retry is finite: six attempts, ten seconds apart.
for attempt in 1 2 3 4 5 6; do
  [[ $(gh pr view --json mergeable --jq .mergeable) != UNKNOWN ]] && break
  sleep 10
done

# Detect applicable branch rules before the final snapshot. Personal-account
# repositories cannot require merge queues; only the explicit feature-
# unavailable response is accepted when their rules endpoint is unavailable.
if gh api --paginate --slurp \
  "repos/$repo_nwo/rules/branches/$base_ref?per_page=100" \
  > "$rules_file" 2> "$rules_error"; then
  merge_queue_rules=$(jq '[flatten[] | select(.type == "merge_queue")] | length' "$rules_file")
  (( merge_queue_rules == 0 )) || {
    printf 'Active merge queue: direct synchronous landing is unsupported.\n' >&2
    exit 1
  }
elif [[ $owner_type == User ]] && grep -Fqi 'Upgrade to GitHub Pro or make this repository public to enable this feature' "$rules_error"; then
  : # The current personal-account repository cannot require a merge queue.
else
  printf 'Merge-queue rules check is inconclusive; fail closed.\n' >&2
  exit 1
fi

# Fresh authoritative snapshot after every bounded wait and immediately before
# merge. Re-fetch and combine every inline-comment page at this same point.
gh pr view --json "$snapshot_fields" > "$final_snapshot"
gh api --paginate --slurp \
  "repos/$repo_nwo/pulls/$pr_number/comments?per_page=100" \
  | jq 'flatten' > "$final_inline"

head_oid=$(jq -r .headRefOid "$final_snapshot")
final_base=$(jq -r .baseRefName "$final_snapshot")
[[ $head_oid == "$initial_head" ]] || {
  printf 'PR head changed after validation; return to Rework.\n' >&2
  exit 1
}
[[ $final_base == "$base_ref" ]] || {
  printf 'PR base changed after the merge-queue check; return to Rework.\n' >&2
  exit 1
}
gh api --paginate --slurp \
  "repos/$repo_nwo/issues/$pr_number/comments?per_page=100" \
  | jq 'flatten' > "$final_comments"
gh api --paginate --slurp \
  "repos/$repo_nwo/pulls/$pr_number/reviews?per_page=100" \
  | jq 'flatten' > "$final_reviews"
gh api --paginate --slurp \
  "repos/$repo_nwo/commits/$head_oid/check-runs?per_page=100" \
  | jq '[.[].check_runs[]]' > "$final_check_runs"
gh api --paginate --slurp \
  "repos/$repo_nwo/commits/$head_oid/statuses?per_page=100" \
  | jq 'flatten' > "$final_status_history"
jq -f "$status_reducer" "$final_status_history" > "$final_statuses"
[[ $(jq -r .state "$final_snapshot") == OPEN ]] || {
  printf 'PR is no longer open; stop landing.\n' >&2
  exit 1
}
[[ $(jq -r .isDraft "$final_snapshot") == false ]] || {
  printf 'PR returned to draft; return to Human Review.\n' >&2
  exit 1
}
[[ $(jq -r .mergeable "$final_snapshot") == MERGEABLE ]] || {
  printf 'PR is no longer cleanly mergeable; return to Rework.\n' >&2
  exit 1
}
(( $(codex_review_pending "$final_comments") == 0 )) || {
  printf 'Codex review is pending; return to Human Review.\n' >&2
  exit 1
}
(( $(codex_review_failed "$final_comments") == 0 )) || {
  printf 'Codex review failed or was cancelled; return to Human Review.\n' >&2
  exit 1
}

pending_checks=$((
  $(jq '[.[] | select(.status != "completed")] | length' "$final_check_runs") +
  $(jq '[.[] | select(.state == "pending")] | length' "$final_statuses")
))
failed_checks=$((
  $(jq '[.[] | select(.status == "completed" and
    (.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped"))
  ] | length' "$final_check_runs") +
  $(jq '[.[] | select(.state != "success" and .state != "pending")] | length' "$final_statuses")
))
(( pending_checks == 0 && failed_checks == 0 )) || {
  printf 'A check is pending or failed; stop landing.\n' >&2
  exit 1
}

# Evaluate final_snapshot, final_inline, final_comments, and final_reviews for
# any new actionable feedback.
# Reconfirm the tracker state is Merging using the targeted tracker operation.
pr_title=$(jq -r .title "$final_snapshot")
pr_body=$(jq -r .body "$final_snapshot")
gh pr merge "$pr_number" --squash --match-head-commit "$head_oid" \
  --subject "$pr_title" --body "$pr_body"
[[ $(gh pr view "$pr_number" --json state --jq .state) == MERGED ]] || {
  printf 'GitHub did not confirm the merge; do not move the tracker issue.\n' >&2
  exit 1
}
# Only now move the tracker issue to Done.
```

If any final assertion or semantic feedback review fails, route to `Rework` or
`Human Review` as appropriate and stop. Never continue to the merge command
using stale evidence.
