\# Codex Skills



Reusable skills for OpenAI Codex.



This repository contains personal and shared Codex skills that provide repeatable workflows, procedures, and specialized instructions for common development and repository-management tasks.



\## Repository Structure



Each skill lives in its own directory at the repository root.



```text

codex-skills/

├── README.md

├── AGENTS.md

│

├── process-issues/

│   ├── SKILL.md

│   ├── scripts/

│   ├── references/

│   └── assets/

│

└── another-skill/

&#x20;   └── SKILL.md

```



A skill directory should contain:



\* `SKILL.md` — required skill definition and instructions.

\* `scripts/` — optional scripts used by the skill.

\* `references/` — optional supporting documentation or reference material.

\* `assets/` — optional templates or other static resources.

\* Other files only when they are directly required by that skill.



Keep everything needed by a skill inside that skill's directory whenever practical.



\## Installed Location



This repository is stored directly in the user-level Codex skills directory:



```text

%USERPROFILE%\\.agents\\skills

```



Equivalent path:



```text

\~\\.agents\\skills

```



Because the Git repository itself is the Codex skills directory, skills added to this repository are available to Codex without maintaining a second synchronized copy.



\## Available Skills



\### `process-issues`



Reviews a GitHub repository for actionable work, including GitHub issues and TODO-style items in the codebase, and assists with processing that work.



See:



```text

process-issues/SKILL.md

```



for the complete skill instructions.



\### `plan-parallel-work`



Decomposes large requests and planning material into dependency-aware GitHub issues, safe parallel work lanes, and ready-to-paste Codex prompts without implementing the planned work.



See `plan-parallel-work/SKILL.md` for the complete skill instructions.



\### `sync-after-merge`



Safely synchronizes local Git state after merges and reevaluates GitHub issue dependencies and agent workflow states.



See `sync-after-merge/SKILL.md` for the complete skill instructions.



\### `improve-skills`



Explicitly reviews generalized evidence from real skill runs, evaluates focused existing-skill improvements, and proposes deduplicated new-skill feature requests without self-modifying or auto-merging.



Its local SQLite feedback store defaults to `%USERPROFILE%\.agents\skill-feedback\skill-feedback.db` (or `~/.agents/skill-feedback/skill-feedback.db`) and is outside this Git repository. Observations are generalized at write time and are not Git-tracked. `CODEX_SKILL_FEEDBACK_DB` may select another stable user-level location.



Participating skills contain a small non-blocking post-run footer and share the recorder/protocol under `improve-skills/`; future skills follow the same convention unless they document why observation is inappropriate. The observer records evidence only. It never rewrites a skill.



OpenAI `plugin-eval` is the preferred optional backend for live Codex evaluation and before/after comparison. Observation capture remains Python-standard-library-only when `plugin-eval` is absent; existing-skill evaluation then operates in an explicitly degraded, recommendation-only mode. Configure a locally installed backend through the `plugin-eval` command or `PLUGIN_EVAL_ROOT`.



See the [improve-skills README](improve-skills/README.md) for a complete
explanation of the architecture, evidence lifecycle, evaluation gates, and
safety model. The [runtime instructions](improve-skills/SKILL.md) remain compact,
and the [observation protocol](improve-skills/references/observation-protocol.md)
defines participation details.



\## Adding a Skill



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

&#x20;   └── examples.md

```



Do not modify existing skills merely to make their formatting or structure match a newly added skill.



Every new reusable skill should include the repository's concise post-run observation footer described in `improve-skills/references/observation-protocol.md`. If persistence is inappropriate for that skill, document the opt-out and reason in its `SKILL.md`.



\## Updating a Skill



When changing an existing skill:



1\. Limit changes to the requested skill unless another file must change for the requested functionality.

2\. Preserve existing behavior that is unrelated to the requested change.

3\. Do not perform opportunistic refactoring or formatting of other skills.

4\. Update supporting files only when the skill change requires it.

5\. Review the Git diff before committing.



Repository-specific instructions for Codex are defined in \[`AGENTS.md`](./AGENTS.md).



\## Naming



Use short, descriptive, lowercase directory names separated by hyphens.



Examples:



```text

process-issues

review-security-alerts

prepare-release

audit-powershell

```



Prefer names that describe what the skill \*\*does\*\* rather than the technology it happens to use.



\## Version Control



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



\## Security



Do not commit:



\* API keys

\* passwords

\* authentication tokens

\* private certificates

\* customer credentials

\* environment-specific secrets

\* sensitive customer data



Use placeholders or environment variables when a skill requires credentials or environment-specific configuration.



