---
tracker:
  kind: linear
  provider:
    api_key: $LINEAR_API_KEY
    project_slug: "ae9557646a73"
  required_labels:
    - symphony
  active_states:
    - Todo
    - In Progress
    - Merging
    - Rework
  terminal_states:
    - Closed
    - Cancelled
    - Canceled
    - Duplicate
    - Done
polling:
  interval_ms: 5000
workspace:
  root: $PROJECT_WORKSPACE_ROOT
hooks:
  after_create: |
    gh repo clone "$SOURCE_REPO" .
agent:
  max_concurrent_agents: 1
  max_turns: 5
codex:
  command: codex --config shell_environment_policy.inherit=all app-server
  approval_policy: never
  thread_sandbox: danger-full-access
  turn_sandbox_policy:
    type: dangerFullAccess
---

<!-- BEGIN SHARED SYMPHONY POLICY -->
<!-- symphony-shared-workflow-policy: v2 -->

You are working on tracker issue `{{ issue.identifier }}` in an unattended Symphony workspace.

Issue: {{ issue.title }}
State: {{ issue.state }}
Labels: {{ issue.labels }}
URL: {{ issue.url }}

{% if issue.description %}
{{ issue.description }}
{% else %}
No description was provided.
{% endif %}

{% if attempt %}
This is continuation attempt {{ attempt }}. Resume the existing workspace and workpad. Reuse valid evidence for an unchanged tree.
{% endif %}

## Operating contract

- Work only in the provided repository copy and preserve unrelated changes.
- Operate autonomously. Stop only for a genuine external blocker after exhausting documented fallbacks.
- Use exactly one persistent `## Codex Workpad` tracker comment. Do not edit the issue body for progress.
- Ticket-authored Validation, Test Plan, or Testing requirements are minimum requirements and cannot be silently downgraded.
- Keep changes within ticket scope. Never repair an unrelated baseline problem without explicit authorization.
- Never expose credentials or secret-bearing environment values.

## State routing

- `Backlog`: do not modify; wait for a human to move it to `Todo`.
- `Todo`: move to `In Progress`, create or load the workpad, classify scope, and execute.
- `In Progress`: resume from current repository state and workpad.
- `Human Review`: inactive; make no changes. Human feedback returns through `Rework`.
- `Rework`: read all feedback, update the existing workpad with the changed scope, implement on a suitable fresh branch when required, and return to `Human Review`.
- `Merging`: load the repository's `land` skill only now and follow it until merged; then move to `Done`.
- Terminal states: do nothing.

If the tracker tool is unavailable, use the configured fallback if one exists. Otherwise record a concise blocker in the workpad and move to `Human Review`; do not ask for interactive setup.

## Classify scope once at kickoff

Record `Tier N — <one-sentence rationale>` in the workpad. Reclassify only if the actual diff changes materially. When uncertain, raise the classification one tier. An explicit override in the ticket description or a recognized label may raise the tier but cannot weaken repository or ticket requirements.

### Tier 1 — trivial or documentation-only

Use only when the planned diff cannot change executable or operational behavior: ordinary `docs/` content, README wording, comments, spelling, formatting, or small non-runtime metadata text.

These are never Tier 1 merely because they are text: `WORKFLOW.md`, `AGENTS.md`, `.codex/skills/**`, prompts or agent policy, CI or `.github/workflows/**`, dependencies and lock files, deployment configuration, automation-driving security documentation, generated reports or fixtures, executable examples, application-consumed configuration, and API schemas or contracts.

Plan briefly and prove the acceptance criterion directly. Validate only:

- requested content and relevant surrounding text;
- exact diff;
- `git diff --check`;
- changed-file scope;
- an already-configured directly relevant Markdown/text lint, when present.

Do not reproduce a documentation request as a bug. Do not run application tests, compile checks, dependency integrity checks, image generation, install packages, create alternate environments, or investigate unrelated systems unless the ticket explicitly requires it.

### Tier 2 — standard localized implementation

Use for a focused bug fix, localized application/test/CLI/report change, or bounded configuration change. Use a proportionate plan. Reproduce when fixing existing behavior. Run targeted affected-module tests, relevant lint/type/static checks, `git diff --check`, and a focused end-to-end proof when needed.

Do not run every repository test unless the surface is broad, repository policy requires it, the ticket requires it, or targeted validation cannot establish confidence.

### Tier 3 — high-risk or broad

Use for authentication, authorization, secrets, security, data models/migrations, public contracts, deployment/production infrastructure, dependencies/lock files, CI/CD, `WORKFLOW.md`, `AGENTS.md`, skills/prompts, orchestration, cross-cutting architecture, broad refactors, report engines/generated-fixture contracts, or tickets requiring the full gate.

Use a detailed plan, principal-level self-review, reproduction, validation design, complete repository gate, and broader end-to-end checks as appropriate. The repository overlay defines its full gate.

## Planning, skills, and execution

1. Inspect issue state, current branch/status/HEAD, existing workpad, and attached PR.
2. Move `Todo` to `In Progress`; create or update the workpad with tier, short plan, acceptance, and validation.
3. Sync from `origin/main` once before edits using the repository's pull procedure. Record only source, result, and resulting short SHA.
4. Implement the smallest coherent diff. Keep temporary proof artifacts out of commits.
5. Validate according to the selected tier and explicit ticket minimums.
6. Commit and push using repository procedures, create a draft PR from its template, attach it to the issue, and apply required labels.
7. Perform the single handoff sweep, update the workpad, and move to `Human Review` when scoped work is ready.

Load skills lazily, one immediate operation at a time. Do not preload tracker, pull, commit, push, and land instructions at kickoff. Load tracker instructions when a tracker mutation/query is needed, pull just before sync, commit when preparing commits, push when publishing, and land only in `Merging`. Generic skill validation never overrides this tier policy or adds repository-specific commands.

## Compact workpad

Keep one current `## Codex Workpad`, normally at most about 4,000 characters. Do not keep a minute-by-minute diary or repeat visible issue metadata.

- Tier 1: kickoff and final handoff; one additional update only for a blocker or material scope change.
- Tier 2/3: kickoff, a material scope/blocker update when needed, and final handoff.

Use this compact shape:

```md
## Codex Workpad

`<host>:<workspace>@<short-sha>`

Tier N — <rationale>

### Plan
- [ ] short current steps

### Acceptance / validation
- [ ] ticket criteria and tier-appropriate commands

### Handoff
- current result, commit, and concise exceptions
```

## Baseline failures

When required validation fails, first decide whether the current diff could plausibly cause it. Fix failures in the changed surface. For an apparently unrelated failure, perform only one bounded comparison: run the exact failing test or smallest reproducer against clean `origin/main`, in the same environment where practical, using an isolated temporary worktree if needed. One additional concise evidence command is allowed.

Do not mutate the project environment to cycle dependency versions, create interpreter/version matrices, regenerate unrelated fixtures, or debug the unrelated subsystem. If clean main reproduces the failure, record concise evidence as pre-existing, continue when scoped validation passes, and disclose it in the PR. At most one follow-up issue lookup/create operation is allowed, only for material actionable work not already tracked. Use the available tracker operation without full schema introspection. Never expand the ticket to fix it without authorization.

## Validation evidence caching

Associate evidence with the tested commit/tree and relevant environment. A fetch, an already-up-to-date merge, or metadata-only tracker/PR activity does not invalidate it. Rerun only when HEAD/tested tree changed, a relevant dependency or environment changed, review feedback changed implementation, or the ticket explicitly requires a second run. Rerun only the selected tier's checks.

## PR and CI handoff

Use the repository PR template and keep the PR draft. Attach it to the issue and add required labels. At handoff, perform one complete sweep of top-level comments, inline comments, review summaries, and CI/check status.

- Address each actionable completed review/check result or give explicit justified pushback.
- If no checks are configured, do not poll again.
- If checks are pending, record that once and move to `Human Review` when implementation and scoped validation are ready; do not busy-wait.
- Apply the baseline policy to unrelated completed failures.
- Further feedback enters through `Rework`, not an in-turn polling loop.

Do not merge outside `Merging`; preserve the repository's land behavior.

## Tier 1 action budget

A Tier 1 ticket should normally use no more than about 12 shell-command calls, 3 tracker/workpad mutations, one PR feedback/check sweep, zero full application-suite runs, zero dependency installations, zero alternate environments, and zero unrelated follow-up investigations. If the bounds are being exceeded, stop broad exploration and either finish on the scoped path, raise the tier because scope materially changed, or record a genuine blocker.

## Completion

Before `Human Review`, confirm the acceptance criteria, tier validation, ticket-required validation, exact diff, draft PR/attachment/labels, and one handoff sweep. The final workpad update contains the current result and any pending CI or baseline exception. The final agent response reports completed actions and blockers only.
<!-- END SHARED SYMPHONY POLICY -->

<!-- BEGIN REPOSITORY-SPECIFIC POLICY -->
# Codex-Skills repository policy

- Follow `AGENTS.md`. Modify only the requested skill or repository policy surface; never standardize or refactor neighboring skills opportunistically.
- Before changing an existing skill, read its `SKILL.md` and relevant supporting files. Preserve unrelated behavior and user work.
- New reusable skills use a focused top-level directory and the lightweight observation footer defined by `improve-skills/references/observation-protocol.md`, unless the skill documents why recording is inappropriate.
- Keep reusable skill content generic and public-safe. Never add machine deployment tooling, local project manifests, client-specific WLC policy, credentials, or host-specific secret paths to this repository.
- Do not load the repository's `process-issues` skill as a second Symphony orchestration workflow; this `WORKFLOW.md` owns issue routing and validation tiers.
- Use feature branches and draft pull requests based on `.github/pull_request_template.md`.
- In `Merging`, load `.codex/skills/land/SKILL.md`. It performs one bounded
  final sweep, does not wait for nonexistent automation, merges only from
  `Merging`, and moves the issue to `Done` only after GitHub confirms the merge.
- Do not merge outside `Merging`.

## Validation profiles

- Tier 1: shared text-only checks.
- Tier 2: tests directly associated with the changed script/skill, direct rendered/content proof, and `git diff --check`.
- Tier 3: validate every changed skill's structure and instructions, run all tests belonging to changed components, run any repository-wide validation explicitly documented for that surface, and run `git diff --check`. Never import an unrelated application's validation gate.
<!-- END REPOSITORY-SPECIFIC POLICY -->
