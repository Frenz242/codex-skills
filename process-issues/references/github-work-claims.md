# GitHub work-claim convention

Use this convention to make active implementation scope visible to humans, Codex instances, and other AI coding agents through GitHub alone. Claims are advisory coordination records, not locks or permission grants. Repository contribution rules, assignments, required approvals, and merge protections take precedence.

## Discover active work first

Before claiming scope, inspect applicable `AGENTS.md` and contribution guidance, `CODEOWNERS`, issue and pull-request templates, assigned or in-progress issues, open pull requests, referenced branches, recent issue comments, and existing `parallel-work-claim:v1` comments. An open pull request or active branch is relevant even when nobody posted a claim.

## Active claim

Post the claim on the primary work issue after creating the branch or worktree and before editing repository files. Link every grouped issue under **Work items**.

```markdown
<!-- parallel-work-claim:v1 -->
### Active work claim

- **Status:** Active
- **Work items:** #123
- **Participant:** @github-user, human, AI agent, or mixed pairing
- **Branch:** `feat/example`
- **Base commit:** `<full-default-branch-commit>`
- **Expected scope:** `src/cli/**`, command registration, related parser tests
- **Shared contracts/artifacts:** CLI command registry and help snapshot
- **Known overlaps:** None found; checked active issues and PRs at `<GitHub timestamp>`
- **Coordination notes:** Stop and coordinate before changing shared manifests or another claim's scope.
```

Use repository-relative paths, components, symbols, contracts, tests, fixtures, schemas, or generated artifacts. Do not publish machine names, worktree paths, prompts, secrets, customer data, or private agent state.

Immediately after GitHub accepts the comment, re-read relevant issues, claims, branches, and pull requests. Classify material overlap with the repository's `SAFE`, `LOW`, `MODERATE`, `HIGH`, or `NOT PARALLEL-SAFE` convention:

- `SAFE` or `LOW`: proceed when scopes are genuinely independent.
- `MODERATE`: proceed only after the affected issues record a concrete boundary, sequence, or integration mitigation.
- `HIGH` or `NOT PARALLEL-SAFE`: the later claimant stops before editing until work is combined, sequenced, or the conflicting change reaches the required integration point.

When claims appear concurrently and participants have not agreed otherwise, the earlier GitHub-created claim wins. A later claimant records that it is backing off. The convention does not make Git merge checks optional.

## Scope update

Before expanding into an undeclared file, component, shared contract, fixture, manifest, schema, or generated artifact, append this scope-update comment. Re-run active-work discovery and proceed only when the expanded scope remains safe or a recorded mitigation resolves the overlap.

```markdown
<!-- parallel-work-claim:v1 -->
### Work claim scope update

- **Status:** Active
- **Work items:** #123
- **Branch:** `feat/example`
- **Added scope:** `src/shared/manifest.yaml`
- **Updated shared contracts/artifacts:** shared manifest and generated index
- **Overlap check:** `MODERATE`; coordinated sequence recorded in #123 and #124 at `<GitHub timestamp>`
- **Coordination notes:** Do not edit the manifest until #124 reaches the recorded integration point.
```

Append history; do not edit the original active claim. If the expanded scope is `HIGH` or `NOT PARALLEL-SAFE`, use the release/update rules below instead of leaving **Status** as `Active`.

## Release or handoff

When active work stops, append a status update instead of editing away history:

```markdown
<!-- parallel-work-claim:v1 -->
### Work claim update

- **Status:** Released | Waiting on PR #456 | Handed off
- **Work items:** #123
- **Branch:** `feat/example`
- **Final scope:** `src/cli/**`, parser tests
- **Next action:** Review/merge PR #456, or claim is available for reassignment
```

Use `Waiting on PR #456` only when this claim's implementation is complete and its associated PR is the integration dependency. Use `Handed off` only for an explicit ownership transfer. Use `Released` when active implementation stops for any other reason, including an unresolved overlap; keep the issue `agent:blocked` and name the external issue or PR in **Next action** when unfinished work cannot continue.

Keep the issue's workflow state aligned with evidence: active implementation is `agent:in-progress`; reviewable work needing human action is `agent:needs-review`; completed reviewed work awaiting default-branch integration is `agent:waiting-on-merge`; unresolved overlap is `agent:blocked`; released actionable work with no active participant is `agent:ready`. Repositories using another workflow keep their established assignments or status fields. When the repository uses the standard `agent:*` workflow but a required label is missing, create only the missing label through the standard label setup before applying it.

## Reactivation after feedback

When review or issue feedback reopens implementation after a claim was released, handed off, or set to `Waiting on PR`, return the pull request to draft and append a reactivation record before editing:

```markdown
<!-- parallel-work-claim:v1 -->
### Work claim reactivation

- **Status:** Active
- **Work items:** #123
- **Branch:** `feat/example`
- **Resumed scope:** parser correction and related regression test
- **Reason:** Address confirmed finding `<GitHub comment or review-thread URL>`
- **Known overlaps:** None found; checked active issues and PRs at `<GitHub timestamp>`
- **Coordination notes:** Corrections remain within the prior final scope.
```

Immediately re-read relevant issues, claims, branches, and pull requests. Apply `agent:in-progress` and resume edits only after the reactivation comment is accepted and the overlap check permits work. If the resumed scope expands, also use the canonical scope-update record before crossing that boundary.

## Apparently stale claims

Do not use automatic leases or reclaim scope solely because time elapsed. Inspect the issue, branch, pull request, commits, checks, and recent comments. Mention the participant or request maintainer disposition when practical. Release or supersede the claim only when GitHub evidence shows integration, abandonment, or explicit transfer.

## Forward evaluation scenarios

### Claim parsing and mixed collaborators

Given an active v1 claim, a human, Codex instance, and non-Codex AI agent can identify the same work items, participant, branch, base commit, expected scope, shared contracts, overlap status, and coordination notes from the GitHub comment. Expected disposition: all reconstruct the same active scope without a local ledger or mandatory parser.

### Disjoint scopes

Two claims cover separate source components and separate tests with no shared contract. Expected disposition: `SAFE` or `LOW`; both may proceed with the published scopes.

### Shared parser and tests

Two branches claim the same CLI parser and parser tests. Expected disposition: `HIGH`; the later claimant stops before editing and records the required sequence or integration point.

### Concurrent claims

Two claims are accepted close together and materially overlap. Expected disposition: the earlier GitHub-created claim wins unless participants record another agreement; the later claim backs off.

### Scope expansion

An initially disjoint change discovers it must edit a shared manifest. Expected disposition: amend the claim, re-run discovery, and stop if the new overlap is `HIGH` or `NOT PARALLEL-SAFE`.

### Release and handoff

Implementation stops because a PR is ready, work is abandoned, or ownership transfers. Expected disposition: append a v1 update with `Waiting on PR`, `Released`, or `Handed off`, final scope, and next action; align workflow state without erasing history.

### Feedback reopens implementation

A review finding arrives after the claim is `Waiting on PR`. Expected disposition: return the PR to draft, append an `Active` reactivation record linked to the finding, re-run active-work discovery, and only then apply `agent:in-progress` and edit.

### Apparently stale claim

An old claim has no recent comment. Expected disposition: inspect GitHub branch, PR, commit, check, and participant evidence; never reclaim solely by age.

### Existing repository governance

A repository requires feature approval in `CONTRIBUTING.md`. Expected disposition: follow that requirement; planning does not edit the file merely to introduce claims.

### Missing repository guidance

No contribution document explains coordination. Expected disposition: planning reports the gap and, only when GitHub issue creation is authorized, creates or updates a human-gated documentation issue containing a proposed snippet. It does not edit tracked guidance directly.

### Unregistered open pull request

No claim exists, but an open pull request changes shared scope. Expected disposition: treat the pull request as active-work evidence and warn or sequence the work instead of reporting a false `SAFE` result.
