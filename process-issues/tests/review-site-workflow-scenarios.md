# Review evidence workflow scenarios

Decision evaluations are separate from executed Node tests. Do not mutate live
GitHub/Sites state merely to exercise these descriptions.

| Scenario | Evaluation and evidence boundary |
| --- | --- |
| Config absent/disabled | Existing workflow continues without Site calls; executable disabled-path test. |
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
