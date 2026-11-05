# Merged PR evidence cleanup

Cleanup is scripted maintenance during manual `process-issues` and
`sync-after-merge` runs. It does not install a scheduler or inspect images with a
model. Preserve ordinary implementation/review gates and never infer merge
authorization from cleanup configuration.

## Explicit opt-in and ownership

After the user authorizes this retention policy, add to the ignored review
configuration:

```json
"cleanup": {"merged_prs": true, "orphan_grace_hours": 24}
```

Missing/false opt-in makes cleanup a no-op. Keep open, closed-unmerged and unknown
PRs. The CLI checks the checkout's numeric repository identity and reads each
candidate PR from GitHub immediately before deletion. If GitHub cannot confirm
merge, stop that run; do not infer merge from a deleted branch or a Site label.

Keep all disposable capture runs, encodings and bundle sidecars in dedicated
folders strictly beneath the configured ignored evidence directory. Pass the
canonical `host:repository-ID:PR-number` as `prKey` to `createCapture`; its ownership
marker propagates through the encoder. For a manually prepared bundle or an
existing known PR-only folder, explicitly register it once:

```text
node PATH/TO/process-issues/scripts/review-cleanup-cli.mjs register CONFIG REPO_ROOT PR_NUMBER EVIDENCE_DIRECTORY
```

Registration asserts that the whole folder is disposable evidence for that PR.
Inspect legacy folders before registering them. Never register the output root,
a mixed-PR folder, source code, credentials/configuration, or a folder holding
unrelated user work. Publication with cleanup enabled requires a matching
ownership marker on the bundle directory. Local cleanup refuses links/junctions,
foreign nested ownership, tracked output and paths outside configured storage.
Unregistered legacy folders and external exports are preserved and need explicit
registration or a separately scoped cleanup; do not discover them by guessing
from filenames. Shared publisher receipts are removed by their exact PR identity.

## Run once during each authorized workflow

After repository synchronization/state reconciliation and before choosing new
implementation work, run the cleanup helper if configured. Reuse the existing
verified Site identity and private audience; get fresh native Site metadata.
Use the same secure input protocol as publication.

Windows Credential Manager:

```text
python -B PATH/TO/process-issues/scripts/review-publisher-vault.py cleanup CONFIG REPO_ROOT --apply
```

Other platforms with secure environment injection:

```text
node PATH/TO/process-issues/scripts/review-cleanup-cli.mjs run CONFIG REPO_ROOT --apply
```

Omit `--apply` for a non-mutating preview. An opted-in authorized workflow uses
`--apply` without asking again for the same retention policy; platform approvals
still apply. Pass fresh native metadata through hidden stdin exactly as for the
publisher. The helper verifies owner-private destination and publisher authority.
No token or private Site URL belongs in GitHub comments or logs.

## Deletion and recovery

1. Confirm the exact PR is merged using GitHub, then create a small server-side
   cleanup record. This record blocks subsequent publications for the same PR.
2. Remove all revisions' file prefixes and publication metadata in bounded
   batches, then remove the review entry. The project index updates naturally.
3. Only after hosted cleanup completes, remove its registered local evidence
   trees and matching publication receipts. Keep a small cleanup receipt with
   PR identity, completion time and pending relative paths only while needed.
4. Retry an interrupted run using the same command. Completed work is idempotent;
   failed deletion remains pending. Never claim completion from a timeout.
   Active uploads can defer cleanup until their bounded lease expires or they
   finish. Preserve pending state for the next manual run; do not busy-poll.
5. Sweep repository-scoped unreferenced uploads only after the configured grace
   period (minimum 24 hours). Committed prefixes and live upload leases are
   protected. Expired publishers cannot commit a prefix claimed for deletion.
   Late bytes from an already-fenced failed request are caught by a later sweep.
   Persist pagination cursors when a sweep reaches its per-run bound.

The backend adds `cleanup_receipts`, `upload_jobs` and a nullable publication
storage-prefix column through an additive migration. Legacy committed media
continues to use its original paths. Never roll back to a server version that
does not honor cleanup records or the new storage prefixes.

Only per-PR cleanup receipts remain; GitHub retains the code/review history.
Do not delete open-PR history, Site source/deployments, repository configuration,
or credentials. No physical phone verification is inferred from cleanup.

## Validation

```text
node --test process-issues/tests/review-cleanup.test.mjs process-issues/tests/review-bundle.test.mjs process-issues/tests/review-service.test.mjs process-issues/tests/review-publish.test.mjs process-issues/tests/review-capture.test.mjs
```

Exercise deletion and races with isolated synthetic storage. A live deployment
check can preview maintenance and prove that an actual open PR is preserved;
do not invent merged PRs or mutate GitHub to manufacture deletion evidence.
