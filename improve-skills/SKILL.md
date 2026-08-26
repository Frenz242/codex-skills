---
name: improve-skills
description: Use when explicitly asked to run $improve-skills, review recent skill performance, improve a named reusable skill from evidence, find evidence-backed new-skill opportunities, or dry-run. Do not use for ordinary coding, explaining another skill, processing a backlog, planning parallel work, or synchronizing merged pull requests.
---

# Improve Skills

Improve reusable skills from generalized evidence. “No change needed” is success.

## Guardrails

- Run only for an explicit request. A successful invocation cannot reveal missed activations.
- Before persistence, reject raw prompts/transcripts, secrets, private identifiers/URLs, customer data, and unnecessary paths.
- A running skill observes only; it cannot modify itself, the evaluator, repository guidance, or another skill.
- Existing-skill changes need frozen criteria/baseline, identical re-evaluation, and regression/holdouts. Degraded evaluation may recommend, never validate.
- Do not implement a proposed new skill; create a human-gated feature request. Validated changes end in draft PRs. Never merge automatically.
- `improve-skills` cannot weaken its own evidence, privacy, evaluation, draft-PR, or human-approval gates.

## Review

1. Read applicable `AGENTS.md`, `README.md`, this skill, and needed references.
2. Inspect Git status/branches/worktrees/remotes/identity and authoritative GitHub state. Synchronize per policy before mutation; preserve unrelated work.
3. Inventory installed skills/versions and search skills, issues, and PRs before declaring missing capability.
4. Run helper `health` and targeted queries. Detect `plugin-eval`; inspect its installed version before assuming syntax.
5. Keep run source (`skill` or `agent`) separate from evidence target. Group by problem, target, content hash, and distinct run. Consider tier, context, recency, old versions, and counter-evidence; cluster aliases.
6. Classify as existing-skill, repository-rule, shared-infrastructure, new-skill, insufficient-evidence, or no-action.

Always read [evidence-and-analysis.md](references/evidence-and-analysis.md). Before mutation, read [evaluation-and-publishing.md](references/evaluation-and-publishing.md). Read [observation-protocol.md](references/observation-protocol.md) for feedback work and [design-provenance.md](references/design-provenance.md) for methodology work.

## Act

For one existing target: freeze criteria/holdouts and baseline; make one focused change; rerun the same evaluation and protections. Keep only a measured net improvement. Follow the reference stopping rules.

For a new skill: require three independent occurrences, or two unusually costly/risky ones; deduplicate by problem across skills/clusters/issues/PRs; verify distinct ownership and validation. Create/update at most three strong human-gated feature requests. Do not create the skill or implementation PR.

Dry run: use global helper option `--read-only`; if no database exists, report no history without initializing it. Do not write telemetry, skills, Git, issues, or PRs.

Report evidence/counts/versions, classification, backend, action or no-action, validation, limitations, and draft links without private observations.

## Post-run observation

After substantive work, make one non-blocking `record-run` call through the shared portable launcher: `scripts/run_feedback_store.ps1` on Windows or `scripts/run_feedback_store.sh` on POSIX. Record minimal metadata always; include generalized detail only for material evidence. Recording failure must not fail the primary task or trigger self-modification.

This footer records a skill-sourced run. Separately, optional global agent guidance may record material reusable evidence with `--source-kind agent` when no participating skill invocation owns the event. Never record routine success, duplicate one event under both sources, or inject this contract into global guidance automatically.
