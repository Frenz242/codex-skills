# Design provenance and upstream failure audit

No upstream implementation or prose is vendored. This skill adapts methodology and records provenance so runtime operation is independent of upstream availability.

Attribution: *One Skill to Rule Them All* by `rebelytics`, version `v2.0.0` at commit `281f13466cd3a73e9ebc9d210907748e1941a3dd`, [source repository](https://github.com/rebelytics/one-skill-to-rule-them-all), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Concepts were adapted; text and code were not copied.

## Sources inspected on 2026-08-21

| Source | Version inspected | License/attribution | Adopted | Changed or rejected |
|---|---|---|---|---|
| `rebelytics/one-skill-to-rule-them-all` | tagged `v2.0.0` and current `main`, commit `281f13466cd3a73e9ebc9d210907748e1941a3dd`; latest release `v2.0.0`; open/closed issues and `release/v3.0.0` fixes through this date | CC BY 4.0; methodology credited here, no copied implementation/text | observation from real work, explicit corrections/workarounds/guardrails/overlap, periodic review, progressive disclosure, simplification, observer self-evidence | Replaced Markdown logs/manual numbering with transactional SQLite UUIDs; separated observer from evaluator; removed Claude-specific paths/tools/config; added empirical Codex evaluation, privacy-at-write, stable external storage, explicit consumption, approval and draft-PR gates |
| `openai/plugins`, `plugins/plugin-eval` | current `main` `11c74d6ba24d3a6d48f54a194cd00ef3beea18f9`; plugin manifest `0.1.2`, package `0.1.0` | repository root had no license file in the inspected tree; plugin manifest declares MIT | preferred structural/token analysis, benchmark scaffolding, isolated Codex execution, usage capture, verifier reporting, and comparison | Optional detection rather than vendoring/installing; observation remains Python-only; degraded mode is honest; no copied machine-specific example paths; current Windows `/bin/zsh` verifier limitation is surfaced |
| Official Codex skill and hook documentation | current pages inspected 2026-08-21 | OpenAI documentation; concepts only | explicit-only policy metadata, progressive disclosure, supported lifecycle-hook inventory | No skill-completion hook was claimed; used a minimal instructional footer because Stop/session hooks cannot reliably attribute a particular skill invocation |

Secondary implementations were not needed for code or structure; avoiding them reduced complexity and licensing surface.

### Evaluator calibration notes

The installed `plugin-eval` implementation was itself inspected and calibrated rather than trusted by score. At the inspected commit, its Python function regex misses annotated/multiline definitions, so it falls back to whole-file keyword counts and reports an implausible complexity of 300 for the helper. Its test-file regex uses `/` separators against Windows paths, so `tests/test_feedback_store.py` is reported as missing even though the suite runs. Its inventory includes its own `.plugin-eval` artifacts as deferred skill content. Its observed-usage drift check compares full Codex session input—including system/developer context—with the skill-only estimate, while the budget baseline reports zero skill samples.

Live calibration found that the benchmark runner has no per-scenario timeout, changes `HOME` and `CODEX_HOME` but not Windows `USERPROFILE`, and provisions a skill under isolated `CODEX_HOME/skills` rather than the current user-skill discovery location. A bare exact scenario therefore ran unbounded until manually stopped; routing-only scenarios completed but could classify prompts without the target actually installed. Synthetic feedback was redirected to a rejected temporary database path. These are evaluator limitations, not accepted product failures. The actionable finding—`SKILL.md` invocation cost—was reduced through progressive disclosure, and a supplemental `codex exec` against the real installation confirmed explicit activation. Live negative-boundary classifications and the independent deterministic suite remain the acceptance evidence.

## Upstream issue / failure class matrix

Issue numbers refer to the current open issue set in `rebelytics/one-skill-to-rule-them-all` inspected above.

| Upstream issue / class | Codex-specific mitigation | Deterministic evidence |
|---|---|---|
| #58 activation self-check cannot observe absence; #22 probabilistic activation; #20 simple requests missed | Separate activation categories from execution runs; never derive false-negative rates from successful invocations; external routing suite; explicit-only `improve-skills` policy | routing contract tests check positive/boundary cases and `allow_implicit_invocation: false`; protocol assertion forbids self-proof |
| #34 capture/consume asymmetry; #42 acted records stay open | Explicit `health`, targeted `query`, `clusters`, `history`, `mark`, evaluation, and link workflow; state transitions retain history | query/lifecycle/link tests; addressed records remain queryable |
| #30 logging-time privacy | Closed JSON fields, generalized summaries, write-time rejection of common secrets/emails/URLs/absolute paths, local HMAC context/path identity | privacy tests and raw-prompt rejection |
| #55 concurrent number allocation; #54 archive reuse; #53 statusless records | Database-generated UUIDs, permanent namespace, mandatory state plus initial history in the observation transaction | concurrent uniqueness, state, lifecycle, and no-reuse tests |
| #39 invalid/free-text targets | Existing skill target must resolve at recording; secondary skills use normalized relation table | missing-target and related-target tests |
| #44 candidate-name proliferation | Analyst-assigned canonical problem key plus normalized aliases; count distinct runs, not names | alias/dedup and distinct-problem tests |
| #33 contextual over-learning | Explicit high/medium/low/task-specific reuse judgment; omit low-severity task-specific self-observation while retaining run | task-specific omission test and protocol contract |
| #31 verifier trust; #28 literal artifact/threshold/negative tests; #26 wrong aggregate metric; #43 clean-shell/expected failure | Freeze/calibrate evaluator; assert behavior; hash actual result artifacts; use plugin-eval structured results; count distinct run UUIDs; document literal Windows verifier limitation | evaluation ordering/immutability tests, independent-run count test, positive/negative checker fixtures |
| #32 writable volatile cache; #41 unstable workspace; #18 stable global location; #52 wrong path | Default stable user-level database; durability classifier rejects Git, temp, and recognized plugin caches; override is explicit | path-classification and default-path tests |
| #36 version-control mutation of feedback | Database lives outside project Git/worktrees; only hashes/HMACs are stored | database-outside-Git test and schema privacy assertions |
| #47 costly no-observation mutations | Local SQLite run rows are cheap and intentionally retained for denominators; no remote mutation | no-observation run test |
| #40 unbounded backups/artifacts | No recorder backups; evaluation reference defines bounded artifact retention and exact-target safety | contract test checks retention rule; helper creates no backup files |
| #23 environment-specific read-only claims | Dry run uses SQLite URI read-only mode without initialization/migration and forbids feedback, Git, and GitHub mutation; static evaluation is reported separately from any live run that would write artifacts | read-only non-creation/mutation tests, dry-run contract, and explicit artifact accounting |
| #25/#16 platform-specific shell; #24 unsafe grep input; #17 Claude tools | Python standard-library helper and argument parsing; no GNU/Claude runtime dependency | CLI tests run through Python; static contract checks exclude copied shell assumptions |
| #29 one-time backfill | Explicit sanitized `backfill`, source-key registry, historical evidence type; no transcript/session crawling | repeat-backfill test |
| #38 read before disposition; #46 bound investigation; #45 retry denied writes | Health/targeted query precede decisions; one target/three iterations/two non-improvements; bounded SQLite retry and non-blocking recorder failure | evaluation stopping/ordering and busy-database tests |
| #19 skill-discovery workspace; #21 load before planning | Resolve actual installed skill paths, read applicable instructions/references before action, never derive global storage from checkout | routing/contract checks and durability test |
| #48 dismissed approval is not approval; #50 routing preflight/dedupe/HEAD; #56 independent flush; #57 explicit deferral criterion | Human approval remains an unresolved issue state; dedupe/search current GitHub state; explicit invocation consumes evidence independent of ordinary-task todo state; deferral requires a recorded reason | new-skill/evaluation contract tests and lifecycle reason validation |

The matrix treats issues as evidence of failure modes, not as mandates to copy upstream proposed fixes.
