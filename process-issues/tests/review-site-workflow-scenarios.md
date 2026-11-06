# Review evidence workflow scenarios

Decision evaluations are separate from executed Node tests. Do not mutate live
GitHub/Sites state merely to exercise these descriptions.

| Scenario | Evaluation and evidence boundary |
| --- | --- |
| No decision, no config (existing or new repository) | Ask opt-in/out once; continue independent work; no hub setup/capture/publication until answered. No answer leaves the decision absent. |
| Recorded opt-out, enabled config left behind | Do not ask again or publish. Preserve config and existing evidence; opting out does not authorize deletion. |
| Recorded opt-in, missing/disabled config | Retain opt-in; report setup or pause conflict and resolve it without repeating the enrollment question or publishing prematurely. |
| Disabled example, no decision | Not evidence of a user refusal; ask opt-in/out. Existing publisher disabled-path test still prevents writes. |
| Existing explicit decision in conversation or repository policy | Reuse and persist it without another confirmation. A task-only opt-out does not become a permanent repository refusal. |
| Existing enabled and validated configuration | Treat verified prior opt-in as decided; preserve the destination. Do not infer opt-in from an unvalidated example or merely the existence of a hub. |
| Linked worktree, root config only | Read the shared local Git choice; discover the original checkout config via worktree inventory, not guessed parent paths. Validate repository identity and output paths in the active worktree. |
| Conflicting config sources or inaccessible config | Report the exact ambiguity/access error. Never treat it as missing/opt-out or silently switch hub destinations. |
| Invalid/multiple saved decision values | Resolve the conflicting record; never silently rewrite or enroll the repository. |
| No Git metadata during new-project planning | Ask during setup and retain the explicit answer in the session; persist only after authorized Git initialization. No hidden initialization just to save a preference. |
| Repeat run or explicit later change | Respect the saved answer; change it only when the user explicitly changes the repository preference. Recheck before writing to avoid stale overwrites. |
| Unattended run with no answer channel | Leave undecided and report the pending question; no hub writes. Independent work may continue. |
| First setup/repeat run | Retain one native Site ID and local source; never create a Site in publisher code. Repeated bundle produces one PR entry. |
| Web project | Built-in Codex browser captures actual screenshots/video; incompatible capture provenance is rejected. Opening a panel alone is not capture proof. |
| Terminal project | Prefer built-in terminal; record reason for another authorized terminal. Real semantic output may make video unnecessary. |
| Native/other project | Computer use follows existing session grants. Request only additional permissions actually needed. |
| Nonvisual work | Meaningful semantic evidence; justified video exemption. Synthetic fixture is not live proof. |
| UI capture unavailable | Not verified; no generated replacement or false not-applicable claim. Current pilot still needs real browser screenshots/video. |
| Wrong running build | UI verified state requires matching build SHA; actual launch provenance still needs runtime inspection. |
| Dirty unrelated work | Preserve it; isolate implementation and capture without reset/stash/accidental commit. |
| Same evidence/new observation | Key unchanged; server returns existing publication; status refresh is guarded. |
| Lost response after commit | Client looks up key; executable test confirms one POST. |
| R2 success/DB failure | Prior current evidence remains; failed publication is not visible until retry completes. |
| Concurrent same PR | Overlapping requests produce one current winner and conflict/history for the other; CAS cannot silently replace it. |
| Concurrent different PRs/repositories | Independent pointers retain both records; equal PR numbers across repositories remain distinct. |
| New head/Update branch | Final observation marks older media stale; null head is unknown. Never claim SHA order. |
| Comment during ready window | Original full 60-second check, two correction passes and three-window bound remain. Important findings return PR to draft. Capture cannot restart budget. |
| Optional upload/media failure | Preserve independently verified code state; report delivery separately and retry finalized evidence only. |
| Required media missing | Criterion stays not verified and draft/blocked rules apply; current implementation PR uses Refs. |
| Owner/viewer identity | Native owner-private metadata required; separate server publisher key; browser Origin/Cookie writes rejected. Hosted service credential alone failed write authorization in preflight. |
| Signed-out media | No bytes on GET/HEAD/range; hosted preflight and server tests. |
| Invalid/oversized/unsafe data | Strict schema/path/hash/media/body limits; no arbitrary fetch target. React renders descriptions as text, without raw HTML. Visual browser safety remains an inspection layer. |
| Another author's PR/active lane | Existing read/report-only ownership and scope apply; no publication on its behalf without authority. |
| Phone-only check remains | Exact URL and play/pause/seek/full-size/GitHub checks handed off; no emulation claim. |
| Persistence after redeploy/new session | D1/R2 are durable storage; verify actual retained record/media after deployment. Physical device access remains a separate check. |

Run bundle, service and publisher tests together. Their SQLite/R2 fixtures and
synthetic decoder clips do not establish browser rendering, real capture origin
or phone playback. Keep the actual pilot ledger in ignored evidence and the PR.
