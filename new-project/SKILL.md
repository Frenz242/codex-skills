---
name: new-project
description: "Set up a new project or bootstrap an existing project's repository with adaptable structure, local storage, documentation, and optional GitHub workflows. Use for requests to start or scaffold a project, create its repository, or explicitly invoke $new-project. Do not use for routine edits in an established project, a standalone document or image, or merely organizing chats in Codex."
---

# New Project

Make project setup consistent while choosing the architecture, tools, languages, layout, and specialized skills that fit the user's actual goal. These instructions specify outcomes and constraints, not a fixed technology stack or an exhaustive list of allowed capabilities. Follow current applicable instructions and tool documentation. Do not add infrastructure merely because this skill mentions it.

## Establish the project

- Use the conversation and existing files to identify the intended outcome, project location, existing work, and whether Git or GitHub is needed. Do not create a repository for every task. Ask only for missing decisions that materially affect the work, such as repository ownership or visibility; do not infer permission to publish private material.
- Read applicable user and repository `AGENTS.md` files. Inspect existing layout, setup documentation, and any overlapping project setup skill before creating files. Preserve existing work and conventions.
- Select and read specialized skills relevant to the actual deliverable. Use them for implementation and verification; this skill coordinates setup and does not replace their expertise. Honor the user's requested scope, including continuing to build the project when setup is only its first step.
- Resolve routine implementation choices with judgment. Explain any real blocker, continue independent authorized work, and reuse authorization already given rather than asking again.

## Keep working files local

Use a local, non-synced project folder suitable for Git. Prefer the user's configured project root; discover it from their instructions instead of hard-coding an account or machine path.

Before creating working files, inspect the destination and its parent chain for symbolic links, junctions, aliases, and sync roots. A local-looking path is not sufficient evidence. If it resolves into OneDrive or another synced location, explain the Git/file synchronization concern and propose a local project path. Existing files in a synced folder do not authorize adding working files there.

Keep repositories, source, scripts, dependencies, virtual environments, caches, previews, logs, diagnostics, processing files, intermediate exports, and operational sidecars local. Only completed deliverables and a brief project-location note may go to OneDrive. An outputs-only junction from the local project to OneDrive is acceptable; never expose local tooling or source through links beneath the synced output folder. Apply any explicit storage exception only within its stated scope and applicable policy.

## Establish Git safely when needed

- If Git metadata already exists, inspect `git status`, configured remote names/URLs, branches, and applicable instructions before changes. Git metadata alone does not establish that `origin` or any remote branch exists. Verify which configured remote is the intended authoritative repository; preserve a different remote name rather than assuming or renaming it to `origin`. If no suitable remote is configured, defer fetching and remote-branch comparison until the remote setup below; continue independent setup without treating a normal new-repository state as an authentication failure.
- Fetch the verified existing remote once. After a successful fetch, determine whether its actual default-branch ref and the corresponding local branch exist before comparing or fast-forwarding them. An empty remote or an unborn local branch has nothing to synchronize yet: defer those operations until the required refs exist. A failed fetch is an error to diagnose, not evidence of an empty remote. Do not discard, stash, or hide user work to synchronize. Before continuing a feature branch, assess whether the verified remote default needs incorporating.
- Once the remote default branch exists, use feature branches for implementation. When `origin/main` exists, preserve it as authoritative for main; otherwise use the verified authoritative remote and actual default branch. Do not invent missing refs or create independent commits on local main during normal development. A brand-new empty repository must first follow the explicitly authorized, one-time bootstrap procedure below.
- On Windows, follow [Initialize Git on Windows](#initialize-git-on-windows) below. When applicable policy permits it, an authorized project setup includes agent-run local initialization; explicit approval for the initial commit and push remains a separate later step. Preserve applicable restrictions on cloning.
- For dubious ownership errors, report the ownership mismatch and have the user repair it from their normal/elevated account as appropriate. Do not add a `safe.directory` exception or change Git metadata ownership yourself.
- Launch PowerShell with `-NoProfile`. Before reporting GitHub authentication unavailable, run both `gh auth status` and `gh api user --jq ".login"`. Distinguish sandbox/network failures from authentication and repository permissions; request the specific required execution permission where supported. Report failed GitHub commands with their exit codes and relevant sanitized errors.

### Initialize Git on Windows

1. Resolve the intended project directory and its parent chain under the local-storage rules. Check for `.git` as either a directory or file and for an enclosing repository/worktree before creating metadata. Preserve existing files; do not accidentally nest or reinitialize repositories. An access error is not proof of absence.
2. Inspect applicable initialization policy. If it permits agent initialization, use the authorized project request without an extra conversational confirmation. Verify the actual process identity matches the intended normal user. If running under a dedicated sandbox account, request the specific approved unsandboxed execution through the platform, and verify the identity again inside that context before mutation. Do not assume escalation changes accounts, and never create user-project Git metadata as a sandbox account.
3. With the destination, absence of metadata, and normal-user identity verified, run `git init -b main` in that directory, or use the explicitly selected initial branch. Launch PowerShell with `-NoProfile`. Verify the resulting Git root, initial branch, and metadata ownership from the normal-user context. Stop on an ownership mismatch; do not automatically change ownership or add `safe.directory` exceptions.
4. Continue preparing the exact seed files, ignore rules, and secret checks. Initialization does not authorize a commit or push. Obtain the concrete bootstrap approval below after the seed is reviewable; reuse approval already given for that scope. Keep `process-issues` setup choices separate from this local initialization.
5. If applicable policy explicitly forbids agent initialization, or a verified normal-user execution context cannot be obtained, report that exact limitation and use manual initialization as the fallback. Do not send the user to a terminal merely because the platform requires an execution approval. This initialization permission does not imply permission to clone or bypass other Git metadata restrictions.

## Choose workflows for GitHub projects

Use `process-issues` by default for projects backed by GitHub. First inspect existing setup and the user's current instructions.

1. If the user explicitly says not to use `process-issues`, honor that instruction and continue implementation without its setup, issue-state gates, or approval requirement. Do not keep asking or block merely because it is absent. Preserve the scope of the opt-out: a task-specific choice is not a permanent repository policy. Do not uninstall existing infrastructure or change unrelated rules unless requested.
2. Otherwise, if the repository already uses it, read the currently available `process-issues` skill and follow its current workflow. Do not duplicate its labels, lifecycle, or synchronization mechanics here.
3. If setup is missing, explain the proposed minimum setup and ask whether to add `process-issues` (the default) or proceed without it. Wait for an answer before dependent implementation or infrastructure changes; continue independent planning. Prior explicit setup approval satisfies this question. An explicit decline is the opt-out in step 1, not a blocker.
4. Inspect other relevant installed codex-skills for actual project prerequisites. Briefly recommend applicable workflows and ask which missing setup to add, grouping related decisions when useful. Do not install every available workflow or interpret declining an optional workflow as a reason to stop. Report a genuinely necessary missing prerequisite specifically.

For approved setup, use the current participating skill and repository conventions. Keep GitHub Issues as the permanent backlog and TODO inboxes as temporary capture unless the user explicitly selects another tracking policy. Opting out of `process-issues` alone does not authorize Linear synchronization. Do not duplicate issues or trigger unrelated backlog processing during setup.

## Configure the target GitHub repository

After ownership, visibility, and creation/setup authorization are established, create or configure only the intended remote repository. Never use a remote setup command that implicitly clones into an uninitialized Windows working directory.

If synchronization was deferred, verify the intended remote URL and its local remote name after configuration, then perform the guarded fetch and branch checks above. For a newly created empty remote, use the bootstrap procedure below and perform branch comparison only after the relevant remote and local refs exist. Do not repeatedly fetch a remote already checked unless there is evidence it changed.

### Bootstrap the initial default branch once

A newly created empty remote has no commit to use as a feature-branch or pull-request base. Establish that base before normal implementation. When resuming an already authorized bootstrap, verify its existing seed and remote state, then continue only the unfinished steps; the emptiness check below governs starting a new bootstrap, not recreating a completed seed.

1. Verify that this is the intended new repository, the remote has no existing history, and the local repository is initialized but has no commits. Failed inspection is not evidence of emptiness. Preserve any existing local commits or user changes; if history already exists on either side, reconcile it under the applicable workflow instead of creating a new root or using this empty-repository exception.
2. Confirm the intended default-branch name and prepare a minimal, reviewed seed, such as a README and ignore rules. Show the exact seed files, target repository, and branch before committing or publishing. Exclude application implementation, secrets, unrelated files, and existing staged user work.
3. After local initialization and seed preparation, obtain explicit authorization for this one-time initial commit and direct push to the intended default branch. Reuse existing explicit approval for that seed and destination. Where standing policy already permits an approved initial bootstrap, this single approval satisfies it; do not ask for a second no-main-commit exception. If a more specific policy still prohibits bootstrap, explain the conflict and obtain an explicit exception for this seed only. While authorization is pending, continue independent preparation without committing or pushing the seed.
4. Once safe local initialization (agent-run or manual fallback) and bootstrap authorization are verified, create the single seed commit on the intended default branch. Stage only the reviewed seed files; do not include unrelated staged content. If the initial commit already exists, inspect and reconcile that state rather than creating another bootstrap commit or replacing history.
5. Immediately before the first push, recheck remote emptiness to detect concurrent initialization. If any history has appeared, stop using this exception and reconcile it; never force-push. Publish the seed with an explicit destination, such as `git push -u REMOTE HEAD:refs/heads/DEFAULT_BRANCH`, substituting the verified remote and branch names. Do not push a feature branch first, since it could become the remote default.
6. Read back the remote branch tip and GitHub default-branch setting. Confirm the tip matches the seed commit and the default branch is the intended one; set it explicitly within the approved bootstrap scope if necessary and verify again. If a check fails, report the exact remaining step and resume from the existing seed rather than making a second root commit. An ambiguous push result requires reading remote state before retrying.
7. Fetch the established default-branch ref, synchronize safely, and create the implementation feature branch from that verified base. The bootstrap exception ends here: all later work follows the normal feature-branch, issue, validation, and pull-request workflow. It authorizes no merge, force-push, protection bypass, or later direct commits to the default branch.

### Delete branches after merge

Enable automatic deletion of head branches after merge for the target repository, then read the setting back. With a supported GitHub CLI, use:

```text
gh repo edit OWNER/REPO --delete-branch-on-merge
gh api repos/OWNER/REPO --jq .delete_branch_on_merge
```

Replace `OWNER/REPO` with the verified repository. Require a returned `true` before reporting success. This setting does not authorize merging pull requests or manually deleting existing branches.

### Keep issue synchronization with Linear disabled by default

Unless the user explicitly requests it, ensure the target repository is excluded from GitHub-to-Linear issue synchronization, including bidirectional synchronization. Inspect the relevant Linear integration's repository/team mappings and any applicable GitHub App, webhook, or automation configuration using current supported tools and access.

Do not assume that absence of a webhook, a local `WORKFLOW.md`, or visible Linear issues proves synchronization is disabled. Do not invent a GitHub repository Boolean for this setting. Disable or exclude only the target repository's issue-sync mapping when supported and authorized; verify the resulting configuration. Preserve unrelated repositories, PR linking, and other integrations. If only a shared workspace-wide switch is available, explain its broader effect and ask before changing it.

If the integration cannot be inspected or changed with available permissions, report issue synchronization as **not verified**, name the exact remaining check/action, and continue independent setup. Do not claim full setup completion while a required setting remains unverified. A user-requested exception should be recorded in the project's setup documentation without secrets.

## Document the actual repository

For a GitHub project, write a concise organization guide in the README or a linked document matching existing conventions. Describe the actual useful directories, what belongs in each, entry points, applicable setup/validation commands, and where final outputs go. Distinguish local or ignored directories from tracked content. Choose a structure suited to the project; do not create empty folders just to fill a template.

Include a visible storage warning in both the human-facing README/guide and repository `AGENTS.md`, merging it into existing instructions without rewriting unrelated policy. Adapt this wording while retaining its meaning:

> Keep this repository outside OneDrive and other synchronized folders. File synchronization can interfere with Git and active processing. Keep source code, scripts, tools, dependencies, environments, caches, previews, logs, and intermediate files in the local project folder. Completed outputs may be copied to OneDrive; processing and tooling must remain local. Check junctions and symbolic links so they do not expose working files to synchronization.

Document the chosen issue workflow and any explicitly scoped opt-out. Do not copy private user configuration into a public repository. Add appropriate ignore rules and sanitized configuration examples without committing secrets, customer data, or generated operational files.

## Verify and hand off

- Inspect the resulting structure and documentation for consistency with the actual project. Run documented checks appropriate to the changed surface and specialized skills; do not invent unrelated validation commands.
- Verify remote settings by reading them back. Keep an acceptance record distinguishing completed, not applicable, and unverified requirements, with the evidence or exact limitation for each.
- Review the diff for unintended files, secrets, unrelated changes, and generated noise. Publish commits and a pull request only when requested or required by applicable standing workflow. Use the explicitly authorized bootstrap procedure for the initial default-branch publication and feature branches thereafter. Never merge without explicit authorization.
- Summarize the project location, organization guide, chosen workflows, verified GitHub settings, validation, and any remaining user action. Do not describe a proposed or inaccessible setting as applied.

## Post-run observation

After substantive work completes, make one non-blocking `record-run` call through the shared portable launcher: `../improve-skills/scripts/run_feedback_store.ps1` on Windows or `../improve-skills/scripts/run_feedback_store.sh` on POSIX. Resolve the helper and participating skill from their installed locations and use absolute paths. Pass `record-run` explicitly before `--skill-path`; the launcher does not add it. Follow the shared [recorder invocation](../improve-skills/references/observation-protocol.md#recorder-invocation) examples and confirm JSON `ok: true` before claiming persistence. Record minimal run metadata always; include generalized detailed observations only for material evidence. Recording failure must not fail the primary task, and an observation must never trigger skill modification.
