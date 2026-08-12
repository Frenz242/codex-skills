\# Codex Skills Repository Instructions



This repository contains reusable Codex skills.



Treat each top-level skill directory as an independent component. Changes should be narrowly scoped, intentional, and easy to review.



\## Primary Rule



\*\*Only modify files required to satisfy the user's current request.\*\*



Do not make unrelated changes, cleanup, refactoring, reformatting, renaming, restructuring, or documentation updates unless the user requested them or they are necessary for the requested functionality.



A nearby improvement is not automatically part of the task.



\## Repository Layout



Each skill normally resides in its own top-level directory:



```text

<skill-name>/

├── SKILL.md

├── scripts/

├── references/

└── assets/

```



`SKILL.md` is the primary definition of a skill.



Optional directories should only be created when the skill actually needs them.



Repository-level files such as this `AGENTS.md` and `README.md` apply to the repository as a whole and should not be changed during ordinary skill work unless necessary.



\## Scope Isolation



Treat each skill as independently maintained.



When asked to modify one skill:



\* Work only inside that skill's directory by default.

\* Do not modify other skills.

\* Do not standardize other skills to match the one being edited.

\* Do not rename other files or directories.

\* Do not reorganize the repository.

\* Do not perform repository-wide formatting.

\* Do not update unrelated dependencies.

\* Do not alter unrelated scripts because they could be written "better."

\* Do not delete apparently unused files outside the requested skill.



If completing the request genuinely requires changing another skill or a repository-level file, make the smallest necessary change and explain why.



\## Adding a New Skill



When asked to create a new skill:



1\. Create a new top-level directory using a descriptive lowercase hyphenated name.

2\. Create its required `SKILL.md`.

3\. Add only supporting files that the skill actually needs.

4\. Keep scripts, references, templates, and assets inside that skill's directory whenever practical.

5\. Do not modify existing skills merely to accommodate the new one.

6\. Do not copy large amounts of boilerplate from another skill unless it is relevant.

7\. Check for an existing skill with overlapping purpose before creating a duplicate.



A new skill should generally look like:



```text

new-skill/

├── SKILL.md

├── scripts/

│   └── optional-helper.ps1

├── references/

│   └── optional-reference.md

└── assets/

&#x20;   └── optional-template.txt

```



Do not create empty optional directories.



\## Updating an Existing Skill



Before editing an existing skill:



1\. Read its current `SKILL.md`.

2\. Inspect supporting files relevant to the requested change.

3\. Understand the existing behavior before replacing it.

4\. Preserve behavior unrelated to the request.



Prefer extending or correcting the existing implementation over rewriting the entire skill.



Do not replace working content solely because you prefer another style.



\## Skill Design



Skills should be:



\* focused on a recognizable task or workflow;

\* reusable across appropriate repositories;

\* explicit about important constraints;

\* conservative about destructive operations;

\* concise enough that instructions remain usable;

\* self-contained when practical.



Prefer instructions that tell Codex \*\*what outcome and constraints matter\*\* rather than unnecessarily prescribing every implementation detail.



When scripts provide deterministic or repeatable behavior better than prose instructions, prefer a small supporting script.



\## Repository-Specific vs Project-Specific Logic



This repository contains reusable skills.



Do not hard-code assumptions that apply only to one unrelated project unless the skill is intentionally project-specific.



For example, avoid embedding:



```text

C:\\Users\\Example\\GitHub\\ExampleOrg\\SomeProject

```



when the skill should operate against whichever repository Codex is currently working in.



Prefer repository-relative paths and discovered project context.



\## Existing User Work



Never discard, overwrite, revert, reset, clean, or otherwise remove existing user changes merely to make the working tree clean.



If unrelated modified or untracked files already exist:



\* leave them untouched;

\* exclude them from the current change;

\* continue working when doing so is safe.



Do not use destructive commands such as:



```text

git reset --hard

git clean -fd

git checkout -- <file>

git restore <file>

```



against user work unless the user explicitly requests the destructive operation and its scope is clear.



\## Git Branches



Respect the repository's existing branch and workflow instructions.



Do not switch branches, create branches, merge, rebase, pull, push, or otherwise alter Git history merely because it is common practice.



Perform those operations only when requested or when standing instructions explicitly require them.



When changing branches, do not disturb unrelated uncommitted work.



\## Before Completing a Change



Review the final diff.



At minimum, verify:



```powershell

git status --short

git diff

```



When staged changes exist, also inspect:



```powershell

git diff --staged

```



Confirm that:



\* every changed file relates to the requested task;

\* no unrelated skill changed;

\* no secrets or local-only data were introduced;

\* generated or temporary files were not accidentally added;

\* existing unrelated user changes remain untouched.



Fix unintended changes before considering the task complete.



\## Commit Conventions



Each commit should represent one logical change.



Prefer this format:



```text

<type>(<scope>): <summary>

```



\### Types



Use:



\* `feat` — new skill or meaningful new skill capability

\* `fix` — correction to existing skill behavior

\* `docs` — documentation-only change

\* `refactor` — structural change that should not alter behavior

\* `test` — tests or validation-only changes

\* `chore` — repository maintenance with no skill behavior change



\### Scope



For changes to a specific skill, use the skill directory name:



```text

feat(process-issues): add TODO discovery

fix(process-issues): ignore generated directories

docs(process-issues): clarify issue prioritization

```



For repository-wide maintenance, use `repo`:



```text

docs(repo): document skill installation

chore(repo): update gitignore

```



For a newly added skill, either the new skill name or `repo` is acceptable, but prefer the skill name:



```text

feat(review-pr): add pull request review skill

```



\### Commit Summary



The summary should:



\* use imperative language;

\* describe the actual change;

\* be concise;

\* avoid vague text such as `updates`, `changes`, or `misc fixes`.



Prefer:



```text

fix(process-issues): exclude closed GitHub issues

```



over:



```text

update process issues

```



\### Commit Scope



Do not include unrelated changes in the same commit.



If work involves independently meaningful changes to multiple skills, keep them in separate commits when practical.



Do not automatically stage everything with:



```text

git add .

```



when unrelated modifications or untracked files exist.



Instead, stage only the files belonging to the intended change.



Examples:



```powershell

git add process-issues/SKILL.md

```



or:



```powershell

git add process-issues/

```



after verifying that everything under that directory belongs to the requested change.



Before committing, inspect:



```powershell

git diff --staged

```



\## Commit Messages and Existing Instructions



If the user or environment provides more specific commit-message instructions, follow those instructions.



These conventions define repository defaults and should not override explicit user instructions.



\## Pushes and Pull Requests



A commit does not automatically imply a push.



A completed local change does not automatically imply a pull request.



Push or create a pull request only when:



\* the user explicitly asks for it; or

\* standing instructions for the current environment explicitly require it.



Do not combine unrelated local work into a push or pull request.



\## README Maintenance



Do not update `README.md` for every small skill modification.



Update the repository README when:



\* adding or removing a skill;

\* materially changing the repository's organization;

\* changing installation or usage instructions;

\* the user specifically asks for documentation updates.



Small implementation changes within an existing skill ordinarily do not require a README change.



\## Final Response



When reporting completed work, summarize:



\* what changed;

\* which skill was affected;

\* validation performed;

\* any important limitation or follow-up.



Mention unrelated pre-existing working-tree changes only when they materially affect the task.



Do not present unrelated existing changes as work performed during the current task.



