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
preliminary_snapshot=$(mktemp)
preliminary_inline=$(mktemp)
review_poll=$(mktemp)
final_snapshot=$(mktemp)
final_inline=$(mktemp)
rules_file=$(mktemp)
rules_error=$(mktemp)
trap 'rm -f "$preliminary_snapshot" "$preliminary_inline" "$review_poll" "$final_snapshot" "$final_inline" "$rules_file" "$rules_error"' EXIT

snapshot_fields=number,title,body,state,isDraft,headRefOid,baseRefName,mergeable,comments,reviews,statusCheckRollup
gh pr view --json "$snapshot_fields" > "$preliminary_snapshot"
pr_number=$(jq -r .number "$preliminary_snapshot")
initial_head=$(jq -r .headRefOid "$preliminary_snapshot")
base_ref=$(jq -r .baseRefName "$preliminary_snapshot")
repo_nwo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
owner_type=$(gh api "repos/$repo_nwo" --jq .owner.type)

[[ $(jq -r .state "$preliminary_snapshot") == OPEN ]]
if [[ $(jq -r .isDraft "$preliminary_snapshot") != false ]]; then
  printf 'PR is still draft; return to the Human Review handoff and stop.\n' >&2
  exit 1
fi

# Fetch and combine all inline-comment pages; inspect this with top-level
# comments and reviews before any wait.
gh api --paginate --slurp \
  "repos/$repo_nwo/pulls/$pr_number/comments?per_page=100" \
  | jq 'flatten' > "$preliminary_inline"

codex_review_pending() {
  jq '[.comments[].body
    | select(contains("codex-pull-request-review-summary"))
    | split("\n")[]
    | select(test("Code Review"; "i"))
    | select((test("Completed|Failed|Cancelled"; "i")) | not)
  ] | length' "$1"
}
export -f codex_review_pending

review_pending=$(codex_review_pending "$preliminary_snapshot")
if (( review_pending > 0 )); then
  timeout 10m bash -c '
    for attempt in {1..60}; do
      gh pr view --json comments > "$1"
      [[ $(codex_review_pending "$1") == 0 ]] && exit 0
      sleep 10
    done
    exit 124
  ' _ "$review_poll" || exit 1
fi

pending_checks=$(jq '[.statusCheckRollup[] | select(
  (.__typename == "CheckRun" and .status != "COMPLETED") or
  (.__typename == "StatusContext" and (.state == "PENDING" or .state == "EXPECTED"))
)] | length' "$preliminary_snapshot")
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
[[ $head_oid == "$initial_head" ]] || {
  printf 'PR head changed after validation; return to Rework.\n' >&2
  exit 1
}
[[ $(jq -r .state "$final_snapshot") == OPEN ]]
[[ $(jq -r .isDraft "$final_snapshot") == false ]]
[[ $(jq -r .mergeable "$final_snapshot") == MERGEABLE ]]
(( $(codex_review_pending "$final_snapshot") == 0 ))

pending_checks=$(jq '[.statusCheckRollup[] | select(
  (.__typename == "CheckRun" and .status != "COMPLETED") or
  (.__typename == "StatusContext" and (.state == "PENDING" or .state == "EXPECTED"))
)] | length' "$final_snapshot")
failed_checks=$(jq '[.statusCheckRollup[] | select(
  (.__typename == "CheckRun" and .status == "COMPLETED" and
    (.conclusion != "SUCCESS" and .conclusion != "NEUTRAL" and .conclusion != "SKIPPED")) or
  (.__typename == "StatusContext" and
    (.state != "SUCCESS" and .state != "PENDING" and .state != "EXPECTED"))
)] | length' "$final_snapshot")
(( pending_checks == 0 && failed_checks == 0 ))

# Evaluate final_snapshot and final_inline for any new actionable feedback.
# Reconfirm the tracker state is Merging using the targeted tracker operation.
pr_title=$(jq -r .title "$final_snapshot")
pr_body=$(jq -r .body "$final_snapshot")
gh pr merge "$pr_number" --squash --match-head-commit "$head_oid" \
  --subject "$pr_title" --body "$pr_body"
[[ $(gh pr view "$pr_number" --json state --jq .state) == MERGED ]]
# Only now move the tracker issue to Done.
```

If any final assertion or semantic feedback review fails, route to `Rework` or
`Human Review` as appropriate and stop. Never continue to the merge command
using stale evidence.
