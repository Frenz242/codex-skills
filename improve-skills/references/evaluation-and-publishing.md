# Evaluation and publishing

## Preferred backend

Prefer OpenAI `plugin-eval` for structural analysis, policy-aware token analysis, benchmark scaffolding, isolated live Codex runs, observed usage, verifier results, and before/after comparison. Detect it with the helper. It may be available as a `plugin-eval` command or through `PLUGIN_EVAL_ROOT` pointing to the plugin directory or an `openai/plugins` checkout.

Before use, inspect the installed version’s README and `--help`; do not assume current syntax. The reference release inspected for this skill exposes concepts/commands including `analyze`, `measurement-plan`, `init-benchmark`, `benchmark`, and `compare`, but the live installation is authoritative.

Do not silently clone/vendor the OpenAI repository, install global dependencies, or make observation capture depend on Node. If unavailable, use safe local deterministic checks only and label the result `degraded`. Degraded evaluation may produce a recommendation but is never equivalent to isolated live Codex benchmarking and never makes a change draft-PR eligible.

On Windows, verify whether the installed benchmark verifier supports the literal shell required by the test. The inspected implementation invokes verifier commands with `/bin/zsh`; do not claim a Windows verifier passed by running a different equivalent command in a mutated shell. Run representative deterministic checks separately, record the limitation, and require suitable live evaluation before promotion.

## Frozen experiment

1. Select one cluster and target; record the exact before commit, content hash, bundle hash, and dirty flag.
2. Write concrete criteria and holdouts before editing. Calibrate deterministic checks with positive and negative fixtures, assert thresholds, identify what each metric counts, and verify negative cases fail for the intended reason.
3. Use `evaluation-begin` to hash/freeze those artifacts and record the chosen backend.
4. Run and record baseline results.
5. Make one focused change. Do not edit the evaluator to make the change pass.
6. Run the same evaluation and record the experiment result.
7. Run regression/holdout checks. Preserve positive guardrails.
8. Compare correctness, activation boundaries, regressions, subjective rubric results, and instruction/token cost.
9. Keep only a measured net improvement. A factual evaluator defect is a separate candidate: repair/calibrate it, rerun baseline, and do not count that repair as skill improvement.

Use deterministic assertions for observable actions, prohibited actions, Git state, issue/PR state, artifacts, files, validation, and guardrails. Label clarity/usefulness/judgment rubrics as subjective model grading.

Default stop rules: one target, at most three experiments, stop after two consecutive non-improvements, after material failures resolve, when evidence is insufficient, when isolation is unsafe, when another skill owns the fix, or when human product/design input is needed.

## Activation versus execution

Activation evaluation needs positive, negative, and adjacent-skill boundary prompts. Include explicit invocation and realistic implicit prompts when the skill allows implicit activation. A running skill’s own log cannot detect times it never activated. Use plugin-eval/live routing evidence or explicit durable reports.

Execution evaluation begins only after selection: confirm the workflow, applicable `AGENTS.md`, Git safeguards, required state/artifacts, documented failure protections, and avoidance of needless complexity.

For `improve-skills`, include these positive routing cases:

- `$improve-skills`
- `$improve-skills review recent skill performance`
- `$improve-skills improve process-issues`
- `$improve-skills find new skill opportunities`

Include boundaries owned elsewhere: processing ready issues/backlog, planning parallel Codex lanes, syncing after a merge, explaining another skill, and ordinary project coding. `agents/openai.yaml` disables implicit invocation as a structural backstop.

## Existing-skill publication

Only a `plugin-eval`-backed passing experiment with passing regression/holdout protection may be marked `keep`/promotable. Then:

1. preserve unrelated work and use repository feature-branch/worktree conventions;
2. change only required files;
3. rerun final empirical and deterministic evaluation;
4. inspect status, unstaged diff, and staged diff;
5. commit intentionally and push according to standing workflow;
6. open a **draft** PR; never merge.

The PR summarizes sanitized evidence and affected versions, baseline, focused change/root cause, before/after and holdouts, instruction-size impact, and limitations. Link the evaluation and cluster to the PR without publishing the private database.

## New-skill feature request

After deduplication and qualification, create/update a feature request titled `Feature request: add <proposed-skill-name> skill`. Include:

- Problem / repeated workflow
- Evidence: independent runs, versions, contexts, strength, corrections/objective failures
- Proposed skill: name, purpose, inputs, outputs/actions
- Trigger examples and adjacent non-trigger examples
- Why separate from existing skills
- Owned and excluded scope
- Concrete acceptance criteria
- Activation/execution/edge/holdout evaluation plan
- Related skills, dependencies, issues, and PRs
- Risks and unresolved decisions
- Workflow state

Keep all evidence generalized. Use current labels while preserving human approval; normally `type:enhancement`, `agent:blocked`, `needs:decision`. Do not set `agent:ready`, create the skill, or open an implementation PR. Create no more than three strong feature requests in one run.

## Monitoring and retention

Link the intervention to before/after hashes, issue/PR, merge commit, and monitoring state. After merge, compare recurrence, correction frequency, activation problems, new regression categories, and positive guardrail evidence across versions. Do not mark confirmed immediately after merge.

Plugin-eval artifacts are temporary evaluation state, not the evidence database. Keep the active baseline/after comparison, current holdout material, and most recent failing run needed for diagnosis. Before removing older artifacts, resolve and inventory the exact `.plugin-eval` target, honor repository retention/instructions, and retain links/hashes in SQLite. Never recursively clean a broad or computed path.
