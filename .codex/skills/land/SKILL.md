---
name: land
description:
  Perform a bounded final review/check sweep and merge an approved pull request
  only while its tracker issue is in Merging.
---

# Land

Load this skill only when the tracker issue is in `Merging`. Confirm that state
before any merge command and again immediately before merging.

1. Locate the open pull request and confirm its head branch and commit.
2. Capture top-level comments, inline review comments, review summaries,
   `statusCheckRollup`, and mergeability once. List configured GitHub Actions
   workflows only to learn which mechanisms exist.
3. Do not wait for a review comment or check that is not configured and has not
   produced a run. Existing actionable feedback returns the issue to `Rework`.
4. If actual checks are pending, wait for those checks only, for at most ten
   minutes. A timeout or related failure returns the issue to `Rework` or
   `Human Review`; never busy-wait. Apply the repository baseline-failure policy
   to an unrelated completed failure.
5. If mergeability is `UNKNOWN`, retry it for at most one minute. A conflict
   returns through the repository pull/push procedure.
6. Reconfirm `Merging`, resolved feedback, successful existing checks, and clean
   mergeability. Squash-merge without auto-merge.
7. Confirm GitHub reports `MERGED`, then use the available targeted tracker
   operation to move the issue to `Done`.

Reference outline:

```bash
snapshot=$(mktemp)
trap 'rm -f "$snapshot"' EXIT
gh pr view --json number,title,body,mergeable,comments,reviews,statusCheckRollup > "$snapshot"
gh workflow list --json name,path,state
pr_number=$(jq -r .number "$snapshot")
gh api "repos/{owner}/{repo}/pulls/${pr_number}/comments"

check_count=$(jq '.statusCheckRollup | length' "$snapshot")
pending_count=$(jq '[.statusCheckRollup[] | select(
  (.__typename == "CheckRun" and .status != "COMPLETED") or
  (.__typename == "StatusContext" and (.state == "PENDING" or .state == "EXPECTED"))
)] | length' "$snapshot")
failed_count=$(jq '[.statusCheckRollup[] | select(
  (.__typename == "CheckRun" and .status == "COMPLETED" and
    (.conclusion != "SUCCESS" and .conclusion != "NEUTRAL" and .conclusion != "SKIPPED")) or
  (.__typename == "StatusContext" and
    (.state != "SUCCESS" and .state != "PENDING" and .state != "EXPECTED"))
)] | length' "$snapshot")
(( failed_count == 0 )) || exit 1
if (( check_count > 0 && pending_count > 0 )); then
  timeout 10m gh pr checks --watch || exit 1
fi

mergeable=$(jq -r .mergeable "$snapshot")
for _ in 1 2 3 4 5 6; do
  [[ $mergeable != UNKNOWN ]] && break
  sleep 10
  mergeable=$(gh pr view --json mergeable --jq .mergeable)
done
[[ $mergeable == MERGEABLE ]]

# Reconfirm the tracker state is Merging here.
gh pr merge --squash
[[ $(gh pr view --json state --jq .state) == MERGED ]]
# Move the tracker issue to Done with the existing targeted operation.
```

The presence of a possible automation workflow never implies that a review
comment must arrive. Every wait is tied to an existing check run and bounded.
