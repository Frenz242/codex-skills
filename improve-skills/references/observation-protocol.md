# Observation protocol

## Purpose and reliability boundary

Ordinary skills do their real work first. After substantive work, a participating skill makes one best-effort recorder call. This instruction is lightweight and probabilistic: Codex currently has general lifecycle hooks, but no supported hook that identifies completion of a specific skill invocation. A successful invocation can record execution evidence; it cannot prove that missed implicit activations did not occur.

Use external routing benchmarks, explicit user reports, or durable task evidence for activation false negatives. Keep activation and execution observations in separate categories.

## Shared footer contract

Participating `SKILL.md` files use this small footer:

> After substantive work completes, make one non-blocking `record-run` call through the shared portable launcher: `improve-skills/scripts/run_feedback_store.ps1` on Windows or `improve-skills/scripts/run_feedback_store.sh` on POSIX. Pass `record-run` explicitly before `--skill-path`; the launcher does not add it. Follow the shared [recorder invocation](#recorder-invocation) examples and confirm JSON `ok: true` before claiming persistence. Record minimal run metadata always; include generalized detailed observations only for material evidence. Recording failure must not fail the primary task, and an observation must never trigger skill modification.

Resolve the helper and skill directory from the installed skill locations; do not hard-code a user or project path. If observation is inappropriate for a skill—for example, a read-only skill whose policy forbids any local persistence—state the opt-out with its reason in that skill’s footer instead of silently omitting participation.

## Recorder invocation

Use the shared platform launcher rather than invoking `feedback_store.py` directly:

The launcher forwards the full CLI; it does **not** supply a default
subcommand. Always include the literal `record-run` token before run options.
Resolve the launcher and participating skill from their installed locations,
then use absolute paths so the call works from any project directory.

Replace the placeholder paths below with those discovered absolute paths. Use
the actual invocation mode and outcome; do not copy `explicit` or `success`
when they do not describe the run.

Windows PowerShell 5.1 or 7:

```powershell
$launcher = '<absolute-installed-improve-skills-directory>\scripts\run_feedback_store.ps1'
$skillPath = '<absolute-participating-skill-directory>'
& $launcher record-run --skill-path "$skillPath" --invocation-mode explicit --outcome success --context-path "$PWD" --non-blocking
```

When starting a new process, use `powershell -NoProfile -File "$launcher"`
or `pwsh -NoProfile -File "$launcher"`, followed by the same arguments.

POSIX `sh`:

```sh
launcher='<absolute-installed-improve-skills-directory>/scripts/run_feedback_store.sh'
skill_path='<absolute-participating-skill-directory>'
sh "$launcher" record-run --skill-path "$skill_path" --invocation-mode explicit --outcome success --context-path "$PWD" --non-blocking
```

Global options precede the subcommand: `--db "<stable-database-path>" record-run`.
Run options follow it. To include details, append
`--observation-file "<absolute-sanitized-json-file>"` to the run options.
Prefer this file form to inline JSON across shell boundaries.

Inspect the returned JSON: only `"ok": true` confirms recording. Explicit
`--non-blocking` also handles argument-parse failures (including a missing
`record-run`) with exit 0 and `"ok": false, "nonBlocking": true`, without
opening or modifying the database. Without that opt-in, parse errors retain
their nonzero exit. The flag must be an option before any `--` separator.
Help remains a successful usage request. Missing Python remains a distinct
launcher failure (exit 127); treat it as best-effort and never claim recording
succeeded merely because the primary task did.

The launcher tries `CODEX_SKILL_PYTHON`, the bundled Codex runtime, and standard Python commands, accepting only Python 3.10 or newer. It forwards every argument and preserves the recorder's exit code. The database defaults to the stable user-level location:

- Windows: `%USERPROFILE%\.agents\skill-feedback\skill-feedback.db`
- POSIX: `~/.agents/skill-feedback/skill-feedback.db`

`CODEX_SKILL_FEEDBACK_DB` may override it. The helper rejects Git-controlled, temporary, and recognized plugin-cache paths. Use a stable user-level path; writability alone does not imply durability.

Use the launchers for routine recording. The direct Python CLI below documents the equivalent forwarded arguments for debugging; a minimal successful run is:

```text
python <skills-repository>/improve-skills/scripts/feedback_store.py record-run \
  --skill-path <participating-skill-directory> \
  --invocation-mode explicit \
  --outcome success \
  --context-path <current-repository> \
  --non-blocking
```

### Source and target are independent

The default footer above is skill-sourced. Omitting `--source-kind` remains backward compatible when `--skill-path` is present. `--source-kind skill` requires a skill path and discovered version; `--source-kind agent` rejects a skill path and creates no skill identity or version.

Optional global agent guidance may use this contract only when a material reusable problem occurs and no participating skill run owns the observation:

```text
python <skills-repository>/improve-skills/scripts/feedback_store.py record-run \
  --source-kind agent \
  --outcome partial \
  --context-path <current-repository> \
  --observation-file <sanitized-json> \
  --non-blocking
```

- Do not record routine success or broad task telemetry.
- Do not duplicate one event as both skill-sourced and agent-sourced.
- Prefer a participating skill source when the evidence arose during that skill run, even when its target is repository or infrastructure.
- Never crawl session history, persist transcripts, invoke `$improve-skills`, or automatically inject or rewrite user-level `AGENTS.md`.
- Generalize and apply every existing privacy-at-write restriction before recording.

The observation target remains `skill`, `repository`, `infrastructure`, or `new-skill`, regardless of source. An infrastructure target may include a stable lowercase `target_component` slug such as `mcp-runtime`; the slug is only a clustering hint and must not contain paths, URLs, accounts, customers, or project identifiers. An agent-sourced skill target must provide `target_skill_path`. Agent-sourced `activation-false-negative` evidence additionally requires explicit user feedback, an external routing benchmark, or an objective check; isolated self-reflection is rejected.

Use the actual invocation mode only when determinable; otherwise use `unknown`. Use ISO-8601 `--started-at` and `--completed-at` when available. The helper emits JSON. A non-blocking failure returns success to the caller with `"ok": false`; do not claim the observation was written.

For a material observation, supply sanitized JSON with `--observation-file` or `--observation-json`. Prefer a file/structured argument mechanism that does not expose sensitive shell history. Allowed fields are deliberately closed; unknown fields such as `raw_prompt` are rejected.

```json
{
  "target_kind": "skill",
  "target_skill_path": "<skill-directory>",
  "category": "guardrail-success",
  "evidence_type": "positive-guardrail",
  "summary": "Dirty-worktree validation prevented unrelated edits from being overwritten.",
  "severity": "medium",
  "reusability": "high",
  "confidence_tier": "objective-failure",
  "suggestion_kind": "no-action",
  "positive": true
}
```

Primary target is normalized and must exist when recording. Use `related_skill_paths` for secondary skills; never hide secondary relevance in a free-text target. Use `target_kind` of `repository`, `infrastructure`, or `new-skill` when no existing skill is the primary target. New-skill observations require a conservative working `candidate_name`.

## When detailed evidence is warranted

Record detail for explicit correction, objective/validation failure, near-violation of a constraint, missing or ambiguous reusable instruction, meaningful reusable workaround, wrong approach reversal, externally evidenced activation problem, skill overlap, repeated missing setup, unexpected repeatable environment, positive guardrail protection, or a plausibly recurring unowned workflow.

Do not detail ordinary success. Low-severity task-specific self-observations are omitted by the helper, while the run denominator remains. Positive evidence is reserved for material protection, not balance-padding.

## Write-time confidentiality

Generalize before invoking the recorder. Never submit raw prompts, transcripts, secrets, tokens, keys, credentials, full emails, customer identifiers or datasets, tenant IDs, private URLs, large logs, or unnecessary absolute paths. The helper rejects common secret-like forms, email addresses, URLs, and personal absolute paths, but this is a safety net—not a complete redactor.

Repository/context identity is stored only as a local HMAC using a random database salt. Skill paths are also HMACed. Skill name, repository commit when available, `SKILL.md` SHA-256, bundle hash, and dirty flag identify versions without storing the full skill.

## Storage behavior

SQLite uses UUID identifiers, foreign keys, WAL mode, a busy timeout, bounded retry, explicit transactions, and deterministic versioned migrations. Every observation receives an initial lifecycle state and history row in the same transaction. Identifiers are never recycled; addressed, duplicate, invalid, and superseded evidence remains queryable.

Run `health` for integrity, schema, journal, path classification, and counts. For dry runs, put the global `--read-only` option before `health`, `query`, `clusters`, or `history`; this opens only an existing database and never initializes or migrates one. Persistent failure matters during an `improve-skills` review; a transient post-run failure never blocks the user’s task.

## Optional one-time backfill

The `backfill` command accepts only sanitized structured observations from durable Git/GitHub artifacts. It marks evidence as `historical-backfill` and records a unique source key so the same batch is not intentionally mined twice. Never ingest old transcripts, assume a session-history path, or crawl unrelated files.

## Example outcomes

- No notable evidence: one run row, zero observation rows.
- Useful evidence: one run plus one generalized observation and initial state history.
- Several observations from one run: several facts, but one independent occurrence.
- Recorder unavailable: JSON reports failure; primary skill result remains successful.
