# Codex Skills

Reusable skills for OpenAI Codex.

This repository contains reusable Codex skills that provide repeatable workflows, procedures, and specialized instructions for common development and repository-management tasks.

> **Independent project:** This is a community-maintained project for use with OpenAI Codex. It is not an official OpenAI project and is not affiliated with or endorsed by OpenAI.

## Installation

Codex user-level skills are stored under the `.agents/skills` directory in your user profile:

**Windows**

```text
%USERPROFILE%\.agents\skills
```

**macOS / Linux**

```text
~/.agents/skills
```

If that directory does not already contain skills you need to preserve, you can clone this repository directly into it.

**PowerShell**

```powershell
git clone https://github.com/Frenz242/codex-skills.git "$env:USERPROFILE\.agents\skills"
```

**macOS / Linux**

```bash
git clone https://github.com/Frenz242/codex-skills.git ~/.agents/skills
```

If you already keep other skills in that directory, clone this repository somewhere else and copy or link only the skill directories you want to install. Keep each skill's `SKILL.md` and supporting files together.

### Prerequisites

- OpenAI Codex with skills support.
- Git for cloning and updating the repository.
- GitHub CLI (`gh`) and GitHub authentication for skills that operate on GitHub issues, branches, or pull requests.
- Python 3 for the local `improve-skills` evidence-store helper.

## Usage

Run Codex in the repository you want to work on and invoke a skill by name when you want its workflow. For example:

```text
$process-issues
$plan-parallel-work
$sync-after-merge
$improve-skills review recent skill performance
```

Some skills deliberately require explicit invocation, while others also document natural-language requests that should activate them. Read the relevant `SKILL.md` for its trigger behavior, prerequisites, safeguards, and output expectations.

## Available Skills

### `process-issues`

Reviews a GitHub repository for actionable work, including GitHub issues and TODO-style items in the codebase, and assists with processing that work.

See [`process-issues/SKILL.md`](process-issues/SKILL.md) for the complete skill instructions.

### `plan-parallel-work`

Decomposes large requests and planning material into dependency-aware GitHub issues, safe parallel work lanes, and ready-to-paste Codex prompts without implementing the planned work.

See [`plan-parallel-work/SKILL.md`](plan-parallel-work/SKILL.md) for the complete skill instructions.

### `sync-after-merge`

Safely synchronizes local Git state after merges and reevaluates GitHub issue dependencies and agent workflow states.

See [`sync-after-merge/SKILL.md`](sync-after-merge/SKILL.md) for the complete skill instructions.

### `improve-skills`

Explicitly reviews generalized evidence from real skill runs, evaluates focused existing-skill improvements, and proposes deduplicated new-skill feature requests without self-modifying or auto-merging.

Its local SQLite feedback store defaults to `%USERPROFILE%\.agents\skill-feedback\skill-feedback.db` on Windows or `~/.agents/skill-feedback/skill-feedback.db` on macOS/Linux. The database is outside this Git repository. Observations are generalized at write time and are not Git-tracked. `CODEX_SKILL_FEEDBACK_DB` may select another stable user-level location.

Participating skills contain a small non-blocking post-run footer and share the recorder/protocol under `improve-skills/`. The observer records evidence only; it never rewrites a skill.

OpenAI `plugin-eval` is the preferred optional backend for live Codex evaluation and before/after comparison. Observation capture remains Python-standard-library-only when `plugin-eval` is absent; existing-skill evaluation then operates in an explicitly degraded, recommendation-only mode. Configure a locally installed backend through the `plugin-eval` command or `PLUGIN_EVAL_ROOT`.

See the [improve-skills README](improve-skills/README.md) for the architecture, evidence lifecycle, evaluation gates, and safety model. The [runtime instructions](improve-skills/SKILL.md) remain compact, and the [observation protocol](improve-skills/references/observation-protocol.md) defines participation details.

## Repository Structure

Each skill lives in its own directory at the repository root.

```text
codex-skills/
├── README.md
├── LICENSE
├── AGENTS.md
│
├── process-issues/
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── assets/
│
└── another-skill/
    └── SKILL.md
```

A skill directory should contain:

- `SKILL.md` — required skill definition and instructions.
- `scripts/` — optional scripts used by the skill.
- `references/` — optional supporting documentation or reference material.
- `assets/` — optional templates or other static resources.
- Other files only when they are directly required by that skill.

Keep everything needed by a skill inside that skill's directory whenever practical.

## Adding a Skill

Create a new directory at the repository root:

```text
new-skill/
```

At minimum, add:

```text
new-skill/SKILL.md
```

Keep the skill self-contained. Supporting scripts, references, or assets should normally remain under the same directory.

Example:

```text
new-skill/
├── SKILL.md
├── scripts/
│   └── helper.ps1
└── references/
    └── examples.md
```

Do not modify existing skills merely to make their formatting or structure match a newly added skill.

Every new reusable skill should include the repository's concise post-run observation footer described in `improve-skills/references/observation-protocol.md`. If persistence is inappropriate for that skill, document the opt-out and reason in its `SKILL.md`.

## Updating a Skill

When changing an existing skill:

1. Limit changes to the requested skill unless another file must change for the requested functionality.
2. Preserve existing behavior that is unrelated to the requested change.
3. Do not perform opportunistic refactoring or formatting of other skills.
4. Update supporting files only when the skill change requires it.
5. Review the Git diff before committing.

Repository-specific instructions for Codex are defined in [`AGENTS.md`](./AGENTS.md).

## Naming

Use short, descriptive, lowercase directory names separated by hyphens.

Examples:

```text
process-issues
review-security-alerts
prepare-release
audit-powershell
```

Prefer names that describe what the skill **does** rather than the technology it happens to use.

## Version Control

Changes should be small and focused.

Examples:

```text
feat(process-issues): add TODO discovery
fix(process-issues): ignore generated files
docs(process-issues): clarify issue selection
feat(repo): add new review-pr skill
docs(repo): update skills index
```

Avoid combining unrelated changes to multiple skills in one commit.

Before committing, review:

```powershell
git status
git diff
```

and verify that only intended files are included.

## Security

Do not commit:

- API keys
- passwords
- authentication tokens
- private certificates
- customer credentials
- environment-specific secrets
- sensitive customer data

Use placeholders or environment variables when a skill requires credentials or environment-specific configuration.

The root `.gitignore` excludes common local secret/configuration files such as `.env`, private key files, virtual environments, logs, and temporary files. Treat that as a safety net, not a substitute for reviewing changes before they are committed.

## License

This repository is licensed under the [MIT License](LICENSE).
