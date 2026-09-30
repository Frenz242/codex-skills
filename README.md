# Codex Skills

Reusable skills for OpenAI Codex.

This repository contains reusable Codex skills that provide repeatable workflows, procedures, and specialized instructions for common development and repository-management tasks.

> **Independent project:** This is a community-maintained project for use with OpenAI Codex. It is not an official OpenAI project and is not affiliated with or endorsed by OpenAI.

## Installation

Use Git to download and update the installer, then use its menu to install or update selected skills from the current GitHub `main`. The installer supports Windows, macOS, Linux, and WSL. It downloads managed skill snapshots separately from your clone.

### New machine

1. Install Git, Codex, and Python 3.10 or newer (the installer also detects Codex's bundled Python runtime when available).
2. Open a terminal in the parent folder where you want to keep the `codex-skills` clone, such as your projects folder. Keep the clone outside your `.agents/skills` directory. On Windows, perform the initial clone from your normal user account, not a Codex sandbox account.
3. Clone `main`, enter the repository folder, and run the appropriate launcher:

**Windows PowerShell**

```powershell
git clone --branch main https://github.com/Frenz242/codex-skills.git
cd codex-skills
powershell -NoProfile -File .\install.ps1
```

**macOS / Linux / inside WSL**

```sh
git clone --branch main https://github.com/Frenz242/codex-skills.git
cd codex-skills
sh ./install.sh
```

If you already have a clone, open a terminal in it and follow the update instructions below.

Windows first offers native Windows and registered WSL distributions. Selecting a distribution runs the installer as its default Linux user, using that user's Python and home directory; Windows Python is not required for this route. The Windows clone must be accessible through `wslpath`. You can instead clone the repository and run `install.sh` inside WSL. Installing into both Windows and WSL requires one run for each target.

The installer reports the OS, Codex executable when on PATH, Codex home (`CODEX_HOME` or `~/.codex`), and common desktop installation evidence. A fresh machine without detectable Codex can still prepare its user skills. Detection is evidence, not proof that every installed Codex edition is running or configured; shell-only PATH changes and custom homes must be supplied in the environment used to launch the installer.

### Select skills and update

The menu shows `not installed`, `current`, `update available`, `unmanaged`, or `conflict`. Enter numbers or names separated by commas, `a` for all, `u` for available managed updates, or `q` to quit. Invalid selections are rejected. Rerun the same launcher to check GitHub `main` again and update selected skills.

To update the installer itself as well, open a terminal inside your `codex-skills` clone on `main`, pull the latest version, then run it:

**Windows PowerShell**

```powershell
git pull --ff-only
powershell -NoProfile -File .\install.ps1
```

**macOS / Linux / inside WSL**

```sh
git pull --ff-only
sh ./install.sh
```

The pull updates your local installer checkout. The menu then lets you choose which managed skills to install or update.

Selecting a workflow skill also includes `improve-skills`, its shared observation helper. The menu explains this dependency before installation. Other unselected skills retain their existing versions. Supporting sibling resources stay with each installed version.

### Locations and overrides

The default destination is `$HOME/.agents/skills` (`%USERPROFILE%\.agents\skills` on Windows), the documented [Codex user skill location](https://learn.chatgpt.com/docs/build-skills). It is independent of where the Codex executable is installed. `CODEX_HOME` changes Codex home detection, not this standard skill destination. An existing `$CODEX_HOME/skills` directory is reported; target it explicitly only if your Codex installation uses that location. The installer does not create duplicate links in both locations automatically.

Managed bundles and state live under `~/.agents/codex-skills-installer`. Windows uses directory junctions, which normally do not require administrator rights or Developer Mode; macOS/Linux/WSL use directory symlinks. Each selected skill points at its own versioned bundle, preserving sibling resources. Do not edit or delete active bundles. Old bundles and previous installations are retained for recovery; automatic garbage collection is intentionally excluded.

```powershell
# Read-only check (downloads main but does not change installed skills).
powershell -NoProfile -File .\install.ps1 -Target windows --list
# Noninteractive skill selection; custom paths may contain spaces.
powershell -NoProfile -File .\install.ps1 -Target windows --skills process-issues sync-after-merge
# All paths forwarded to WSL must be Linux paths.
powershell -NoProfile -File .\install.ps1 -Target Ubuntu --dest /home/me/.agents/skills --list
```

```sh
sh ./install.sh --list
sh ./install.sh --skills process-issues sync-after-merge
sh ./install.sh --dest "$HOME/custom-skills" --store "$HOME/custom-skill-store"
```

Set `CODEX_SKILL_PYTHON` to an explicit Python executable if runtime discovery fails. The store must stay outside the skill discovery directory. Use the same `--store` on later runs to retain installation ownership records. Each destination has separate state. Network failures stop the check without replacing installed skills; GitHub's unauthenticated API rate limit may require retrying later.

### Existing installations and recovery

Existing copies, junctions, and symlinks are compared to upstream but treated as unmanaged until explicitly adopted. The interactive menu asks before backing up and replacing an intact unmanaged installation. Noninteractive runs require `--adopt`:

```sh
sh ./install.sh --skills process-issues --adopt
```

Backups go into `.codex-skills-backups` beside the destination's parent skill directory, outside Codex discovery (for the default destination: `~/.agents/.codex-skills-backups/<id>/<skill>`). Renaming an existing link preserves its original target and checkout. Existing ordinary directories are preserved in full. Ordinary directories inside a Git checkout cannot be adopted; use a separate destination so tracked files stay intact. Managed files with local edits, broken links, and unexpected file conflicts are refused even with `--adopt`; preserve or relocate those manually before retrying. Files generated inside a managed bundle also count as modifications. On POSIX, owner/group/other executable-bit changes also count as modifications; they are reported as conflicts rather than silently overwritten. Other permission bits are not part of this check. Windows fingerprints continue to compare names and contents only.

Installations created before executable-bit tracking used unversioned, content-only fingerprints. On POSIX, the updated installer verifies their content first and lists intact legacy installations as `update available` for a one-time refresh. Selecting an update installs current upstream files and permissions, preserves the old bundle/link as a backup, and records the new fingerprint version. It does not accept existing local modes as a trusted baseline. Content edits still block migration. A read-only `--list` does not change state, and legacy Windows installations need no refresh solely for this change. Run `git pull --ff-only` in your installer clone on `main` to get this behavior.

If a normal installation error occurs after replacement begins, the installer restores the previous link/directory. A forced process kill or power loss can leave `install.lock`, temporary links, or a backup requiring manual recovery. After confirming no installer is running, inspect the printed destination/store and backups before removing a stale lock. To roll back manually, remove only the new skill link and move the saved backup back to its original name; never recursively delete a junction target. Reinstall/adopt afterward to reconcile state. Restart Codex if skills do not appear.

### Prerequisites for skill use

- Codex with skills support and Python 3.10+ for installation and the evidence-store helper.
- Git for cloning/updating the installer and for repository workflow skills; authenticated GitHub CLI (`gh`) for skills that interact with GitHub.
- Internet access to `github.com` for Git cloning/pulling, and to `api.github.com` and `codeload.github.com` for installation/update checks.
- Native Windows installation uses Windows PowerShell 5.1 or newer. WSL needs Python 3.10+ inside the selected distribution.

### Installer validation

```sh
python -m unittest discover -s tests -p test_installer.py -v
sh install.sh --source . --list
```

```powershell
powershell -NoProfile -File tests/test_installer_launcher.ps1
powershell -NoProfile -File install.ps1 -Target windows --source . --list
```

`--source` is an explicit offline/development override and does not check GitHub `main`. Tests use disposable destinations and synthetic content; CI runs the Python behavior suite on Windows, macOS, and Linux. WSL launcher tests simulate enumeration and dispatch, so a live WSL install remains a separate platform smoke check.

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
