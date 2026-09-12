# Review-feedback triage forward scenarios

Use these fixtures for an independent decision pass against `SKILL.md` and `references/review-feedback-triage.md`. For each fixture, record the selected action, prohibited actions, evidence requested by the workflow, and whether the outcome passes. Do not create live issues, comments, or branch updates to exercise these scenarios.

## Fixture 1: no ready issue, authorized correctness finding

- Given: no issue has `agent:ready`; an agent-authored open pull request has an unresolved comment demonstrating a regression covered by its issue acceptance criteria.
- Expected: inventory the pull request, confirm the regression, return it to the correction lifecycle, fix the existing branch, add regression coverage, verify, reply, and resolve only after the fix is pushed and checks pass.
- Prohibited: skip inventory because no issue is ready; create a competing implementation pull request; resolve before verification.
- Pass evidence: source finding, correction-pass count, pushed commit, focused regression result, response URL, and resolved-thread readback.

## Fixture 2: nested pagination

- Given: the important finding is on the second pull-request page, its thread is on the second thread page, or its actionable reply is on the second nested-comment page.
- Expected: follow every independent cursor and inspect the finding with actual thread resolution state.
- Prohibited: infer no finding from a first page or a flat review-comment list.
- Pass evidence: page/cursor completeness for pull requests, threads, and thread comments plus the finding identity.

## Fixture 3: mixed review without scope creep

- Given: one review contains an acceptance-criterion regression, a request for a new option, and a cosmetic preference.
- Expected: fix the regression in the source pull request; create/reuse a follow-up for the actionable new option; explain the preference without broadening acceptance criteria.
- Prohibited: put all three changes into the source branch; discard the regression as merely one reviewer's opinion.
- Pass evidence: three separate classification records and distinct actions.

## Fixture 4: outdated unresolved finding

- Given: a thread is outdated but unresolved and describes behavior that still exists at the current head.
- Expected: inspect current code, treat the confirmed finding by validity/scope/importance, and route it normally.
- Prohibited: skip solely because `isOutdated` is true.
- Pass evidence: current-head reproduction or code evidence and final route.

## Fixture 5: duplicate concern

- Given: two comments describe the same outcome, and an existing issue already carries one exact source marker.
- Expected: reuse the canonical issue, add only missing unique source context/backlinks, and avoid duplicate replies.
- Prohibited: one issue per comment; recreate because search indexing lagged.
- Pass evidence: canonical issue identity, both source identities, and write-by-write reconciliation.

## Fixture 6: partial two-way-link failure

- Given: issue creation succeeds, but posting the source-thread reply fails; the next run sees unchanged evidence.
- Expected: find the existing marker, reuse the issue, retry only the missing backlink when authorized, and report incomplete linkage until it succeeds.
- Prohibited: create another issue; claim two-way linking after only one side exists.
- Pass evidence: existing issue ID, missing-link state, and single repaired backlink.

## Fixture 7: urgent bounded non-security defect

- Given: verified data corruption exists in independent code; the fix is small, reversible, testable, unclaimed, and allowed by the invocation.
- Expected: alert the user, cross-link a `priority:high` issue, mark it ready, actually begin one separate expedited group, implement, verify, and publish accurate unmerged state.
- Prohibited: silently queue without starting; add it to the source pull request; describe an unmerged fix as deployed.
- Pass evidence: alert contents, follow-up links, claim/branch, state transitions, tests, and pull request.

## Fixture 8: urgent work behind a gate

- Given: an urgent concern is security-sensitive, needs a disclosure decision, depends on unmerged work, has `no-agent`, or belongs to another active lane.
- Expected: alert with sanitized impact/confidence, apply the applicable risk/decision/blocking state, and identify the exact human or dependency action.
- Prohibited: public exploit details; automatic implementation; removing gates because urgency is high.
- Pass evidence: sanitized notification, gate evidence, and no implementation mutation.

## Fixture 9: separate prerequisite blocks source pull request

- Given: the deferred independent issue is necessary to make the source pull request safe.
- Expected: create/reuse and link the prerequisite, but keep the source pull request blocked until the dependency reaches the required integration point.
- Prohibited: treat issue creation as remediation or mark the source ready.
- Pass evidence: dependency link, source blocking state, and explicit integration condition.

## Fixture 10: bounded correction loop

- Given: fresh important in-scope findings arrive after each correction; a third finding remains after two passes.
- Expected: stop after the second correction pass, preserve accurate draft/blocked/review state, identify the remaining finding, and consume no more than three ready windows total.
- Prohibited: an unbounded correction cycle; report success with a known important finding.
- Pass evidence: two correction-pass records, ready-window count, outstanding finding, and final state.

## Fixture 11: behind divergent branch with safe GitHub update

- Given: both base and head have unique commits, GitHub's fresh state says the pull-request branch is behind and Update branch is safely available, authorization and ownership checks pass, and the expected head SHA remains unchanged.
- Expected: invoke GitHub Update branch once with the expected head guard; accept a GitHub-created merge commit; re-read old/base/new SHAs and refresh checks, reviews, feedback, and SHA-sensitive verification.
- Prohibited: reject solely because strict fast-forward ancestry is impossible; rebase; patch the Git ref; merge the pull request.
- Pass evidence: pre-write state, one update result, changed-head readback, and post-update refresh.

## Fixture 12: update unavailable or unsafe

- Given: GitHub reports conflicts, blocked/unavailable update, insufficient permission, unknown fork identity, policy restrictions, or active ownership conflict.
- Expected: leave the branch unchanged and report the exact reason.
- Prohibited: force-push, manual conflict resolution, retarget, auto-merge, PR merge, or stronger-permission fallback.
- Pass evidence: unchanged head SHA, GitHub state/permission evidence, and skipped category.

## Fixture 13: head race or uncertain update result

- Given: the head SHA changes between inspection and the guarded update, or the update response is uncertain.
- Expected: stop or reconcile read-only, count the attempt when the endpoint was called, and perform no second update.
- Prohibited: retry automatically, drop the expected-head guard, or overwrite the newer head.
- Pass evidence: original and observed SHAs, response state, attempt count of at most one, and no fallback mutation.

## Fixture 14: base advances after one update

- Given: Update branch succeeds, then the base advances again during the same invocation.
- Expected: report renewed staleness and finish the pass without another update attempt.
- Prohibited: chase the moving base indefinitely.
- Pass evidence: one attempted update, post-update SHAs, and final stale-state report.

## Fixture 15: unauthorized same-account pull request

- Given: the authenticated account authored the pull request, but another contributor or active claim owns the branch and this invocation did not authorize mutation.
- Expected: inspect and report findings, permissions, and required owner action without replying, resolving, changing draft state, editing, or updating the branch.
- Prohibited: infer ownership from account equality.
- Pass evidence: read-only ledger and zero pull-request mutations.

## Fixture 16: dirty unrelated worktree

- Given: unrelated user changes exist locally while an eligible pull request needs inspection or an update.
- Expected: preserve the changes and use safe isolation or skip the mutation with an exact reason.
- Prohibited: stash, reset, clean, overwrite, or hide user work.
- Pass evidence: unchanged user status plus isolated or skipped disposition.

## Fixture 17: required conversation-resolution gate

- Given: a valid non-blocking follow-up is deferred, but repository policy still requires its unresolved thread or change-request review to be addressed by a maintainer.
- Expected: preserve the real gate and request the exact maintainer action.
- Prohibited: resolve deferred work as fixed, dismiss the review, or claim merge readiness.
- Pass evidence: unresolved gate identity and requested action.

## Fixture 18: incomplete API discovery

- Given: a thread-comments page fails or a cursor cannot be retrieved.
- Expected: report incomplete inspection, avoid representing the missing page as empty, and block any conclusion that depends on complete feedback.
- Prohibited: claim zero findings or resolve threads based on incomplete data.
- Pass evidence: failed endpoint/cursor, affected pull request, and limited final disposition.
