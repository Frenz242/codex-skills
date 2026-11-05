# Review evidence workflow scenarios

These are decision evaluations, separate from the executed Node tests. Use
synthetic descriptions; do not mutate live GitHub/Sites state to exercise them.
The current implementation is a local foundation. Hosted outcomes remain
unverified until the transport, gallery and integrated pilot exist.

| Scenario | Required decision | Current evidence / boundary |
| --- | --- | --- |
| Config absent or disabled | Preserve existing run; no Site call | Executed config tests return disabled and zero mutations. |
| Config enabled, transport not yet proven | Validate locally; disclose hosted gate | Reference explicitly forbids claiming automatic publication. |
| Nonvisual code change | Meaningful semantic evidence; video may be not applicable | Synthetic nonvisual manifest and public CLI pass; no live PR claim. |
| UI tool missing | Capture not verified; never relabel as not applicable | Executed manifest test rejects the false exemption. |
| Checkout matches but running build is old | Capture cannot be verified | Executed build-SHA mismatch rejection; matching metadata still needs runtime provenance inspection. |
| Same evidence, fresh status/CAS token | Keep publication identity | Executed key-stability checks; no server retry claim. |
| Late publisher races newer PR evidence | Preserve newer entry; refresh head and CAS | Documented gate only; server concurrency remains not implemented. |
| Important issue comment during ready window | Draft/correct under existing budgets; invalidate changed-head evidence | Original 60-second/two-pass/three-window text unchanged; no new loop added. |
| Optional publication fails after tests pass | Preserve code result; report delivery failure separately | Reference preserves this distinction; live failure recovery not verified. |
| Required hosted evidence missing | Keep criterion not verified and PR draft/blocked | This feature's own partial PR remains draft and uses Refs. |
| Viewer has read access | Read does not authorize writes | Local Site probe rejects viewer POST and unauthenticated GET/HEAD/range; hosted enforcement not verified. |
| Ownership unknown or another active lane | Read/report only; no publication on its behalf | Scope and ownership rules unchanged; reference requires scope check. |
| Physical phone unavailable | Explicit phone handoff, not emulation success | Real phone criterion remains not verified. |

When resuming, evaluate actual immutable storage, D1 failures, ambiguous commits,
concurrent publishers, signed-out hosted media, redeployment persistence,
mobile rendering and physical playback. Do not convert these pending scenarios
into passing automated results.
