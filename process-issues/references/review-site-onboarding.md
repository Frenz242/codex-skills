# Review-hub decision preflight

Run this at the start of `process-issues` in every repository and during
`new-project` setup when that workflow is selected. It enrolls a repository only
when the user chooses to opt in; it does not change the publisher's privacy,
identity, capture or review-readiness requirements.

## Resolve the decision before setup

1. Read applicable repository policy and current session instructions. Reuse an
   explicit opt-in or opt-out already given for this repository. A scoped opt-out
   from `process-issues` skips this preflight for that scope. Do not persist a
   task-only refusal as a permanent repository choice.
2. In the verified repository, read the shared local Git setting:

   ```text
   git config --local --get-all codex.reviewHubDecision
   ```

   Exactly one value, `opt-in` or `opt-out`, is a saved decision. Exit code 1
   with no value means undecided. Other failures, invalid values or multiple
   values require reconciliation; they are not absence. Use `--local`, not
   global or per-worktree config: linked worktrees share the repository choice.
3. If no saved answer exists, inspect only known configuration locations:
   an explicitly supplied config / `CODEX_REVIEW_SITE_CONFIG`, the active
   worktree's `.codex/review-site.local.json`, and the original checkout's same
   file. Locate the original checkout with `git worktree list --porcelain` and
   Git's common-directory information; do not assume it is a parent folder.
   Do not scan unrelated repositories or print config contents/credentials.
   A previously approved, enabled config whose repository identity matches the
   verified repository is existing opt-in evidence. A disabled example, missing
   config, existing hub, local media bundle or successful branch preview is not
   evidence of a decision. Reuse documented explicit refusals. A saved opt-out
   wins over an enabled config left on disk unless the user changes the choice.
4. When still undecided, ask one concise, self-contained question, for example:

   > Should this repository publish PR review entries and short demonstration
   > videos to your private PR hub? Opt in sets up delivery when applicable;
   > opt out keeps the normal GitHub workflow without hub uploads. I will
   > remember your choice for this repository.

   Offer **Opt in** and **Opt out**. Explain video can be not applicable for
   nonvisual work. Name a verified existing hub if known; never invent one or
   infer permission to create a new service. No response, an interrupted run,
   or an unavailable question channel leaves the choice undecided. Continue
   independent work, leave the question pending and report it at handoff;
   do not treat elapsed time as an answer or repeatedly ask within the run.
5. Immediately before persisting an explicit repository-wide answer, re-read
   the setting to avoid overwriting another session's decision. Reconcile any
   unexpected change. Write just the selected value, then read it back:

   ```text
   git config --local codex.reviewHubDecision opt-in
   git config --local --get-all codex.reviewHubDecision
   ```

   Substitute `opt-out` for a refusal. The same command can change a single
   saved value when the user explicitly changes their preference. Do not clear
   or replace conflicting multi-value records without resolving their origin.
   Record no credentials, URLs or capture data in this setting. If persistence
   fails, honor the answer for this session and report that it was not saved.
   A clone on another machine has separate local config; use explicit shared
   repository policy when present, otherwise ask there instead of guessing.

No project-wide rollout should pre-fill opt-in or opt-out for undecided repos.
Installing this shared skill makes the next applicable run perform the check;
there is no need to modify every repository or prompt for all projects at once.

## Act on the answer

- **Opt out:** continue the normal issue/PR workflow without hub setup, capture
  for hub delivery, publication or automatic hub cleanup. Do not ask again on
  later runs unless the user changes the preference. Preserve existing config
  and evidence; opting out does not authorize deletion.
- **Opt in:** resolve the configuration and use [review Site publication](review-site-publication.md).
  Reuse the authorized hub and existing private access. Persisting opt-in is
  not proof of completed setup or successful delivery. Missing config retains
  the opt-in: prepare the needed setup, report a genuine missing prerequisite,
  and never repeat the enrollment question merely because setup is incomplete.
  A disabled config may be an explicit pause; resolve that before enabling it.
- **Undecided:** no hub writes or setup. Report the pending choice separately
  from code progress. Do not manufacture an opt-out to avoid another future
  prompt or mark unknown delivery as complete.

An explicit config override selects the candidate; validate it against the
verified repository. Without an override, reuse the existing valid config from
the active/original checkout. If their destinations or settings disagree,
resolve the conflict rather than silently selecting one. Access/parse errors
are errors, not missing files. Pass the resolved path explicitly to existing
helpers; keep it ignored and untracked. Validate output paths and ignore rules
against the actual issue worktree; a config in another checkout does not waive
these checks. No default template is an approved production destination.

For opted-in visual changes, plan supported capture during runtime validation.
Report screenshot, video, hub-entry and verified-delivery outcomes separately.
Unsupported capture or upload failure is a named limitation; a branch preview
is not a substitute. Nonvisual work can use semantic evidence with a justified
video exemption. Apply the existing required/optional evidence gates. Enrollment
alone does not make optional evidence required, authorize private-data uploads,
create a hub, change access, or opt into merged-evidence cleanup.
