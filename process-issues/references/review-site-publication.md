# Private review Site: setup, capture and publication

Read this when a project opts in to hosted PR evidence. The supplied publisher,
D1/R2 service and mobile gallery implement one private Site with repository
views and PR deep links. They do not capture a screen or decide whether an
acceptance criterion passed. The invoking agent owns capture, visual/semantic
inspection and the existing process-issues readiness gates.

## Supported runtime and proof boundary

The integration has been exercised from Codex desktop on native Windows with
Node 24, Python 3, GitHub CLI, ffmpeg/ffprobe and the installed Sites plugin.
Use Node 24+ for the publisher and its SQLite tests. Other operating systems,
WSL, standalone CLI and unattended runs are not yet validated. No schedule,
daemon or continuous GitHub monitor is installed.

A private deployed Site has passed authenticated binary upload/read-back,
matching hashes, idempotent retry, viewer/write separation, private caching,
HEAD/range handling and signed-out direct media rejection from that runtime.
Automated tests separately cover storage failure, concurrent writes and lost
responses. These are not visual or physical-phone verification. Record the
actual real-PR pilot and phone result separately; never infer them from this
template, its build, synthetic fixtures or a successful upload.

## Configure an existing project

1. Verify repository identity through gh and Git under the normal workflow.
2. Opt in with an ignored `.codex/review-site.local.json`, starting from
   `assets/review-site.config.example.json`. The agent may resolve
   `CODEX_REVIEW_SITE_CONFIG` and pass that path explicitly. The helper does
   not silently search environment paths. Missing/disabled config means no
   Site calls or writes. Unknown versions fail.
3. Append local config/evidence exclusions to `.git/info/exclude`, or use
   established project ignore policy; preserve existing entries. Never commit
   local configuration, credentials, real media or raw operational logs.
4. Set the verified canonical GitHub host and numeric repository ID. Names
   may change; identity is host plus ID. Reuse the retained Site ID and native
   canonical HTTPS *.chatgpt.site origin. Custom domains are not supported.
5. Keep evidence under the configured ignored repository-relative directory,
   in normal-user-accessible, non-synced storage. Verify junction/symlink and
   sync policy. The inspector checks containment, whole-directory exclusion,
   actual handoff paths and untracked status,
   but cannot establish intended-user access or every synchronization policy.
6. Set `required` according to the project's existing acceptance requirements.
   Do not silently make optional delivery a readiness gate or waive required
   media. Configure 8–15 seconds as the demonstration target.

The example is disabled and contains synthetic values. Credential fields are
environment-variable names, never secret values.

## One-time Site setup

Use the installed Sites skill and its current source, storage, identity and
deployment references. Reuse `.openai/hosting.json` when present; never create
a duplicate Site to retry setup. Verify the Site is owner-private through
native metadata, not by whether a URL opens. Do not broaden its audience.

Start from the supported Vinext starter in a separate local, non-synced source
project. Follow the user's Git initialization, first-publication and feature
branch rules. Overlay `assets/review-site/` onto the starter, and copy
`scripts/review-bundle.mjs` and `scripts/review-service.mjs` into its root
`lib/` directory. Preserve existing files and schema exports; add
`export * from './review-schema';` to `db/schema.ts`. The hosting manifest
needs D1 binding `DB` and R2 binding `BUCKET`. Generate and inspect the
additive migration with the starter's documented `npm run db:generate`.
Keep migration history; never replace an applied migration.

Set a random application secret `REVIEW_PUBLISHER_KEY` using Sites runtime
environment-variable tools, marked secret. Separately obtain the existing
Site service bearer credential from native metadata. Do not create or rotate
the platform token merely because publishing failed. The service token grants
platform access but no visitor identity; the application secret authorizes
writes. Keep both out of source, arguments, logs, browser code and receipts.

Build/package through the supported Sites workflow, push source, then deploy
the exact pushed commit privately using the returned archive. Confirm the
deployment succeeded. Keep account-specific hosting/source metadata in that
private local source project, outside the reusable skill.

Before relying on a new deployment, prove authenticated binary upload and
hash read-back, viewer-only write rejection, signed-out GET/HEAD/range denial,
private cache headers, exact media types and range responses. Preserve a
sanitized proof record locally. A successful capability response alone does
not prove media delivery.

## Capture the real behavior

Select the capture surface by the project being demonstrated:

| Project | Evidence capture |
| --- | --- |
| Web or browser-based | Use Codex's built-in browser for screenshots and video of the actual running application. Do not substitute external-browser or computer-use captures. |
| PowerShell, CLI or other terminal project | Use Codex's built-in terminal where possible. If unavailable, record why and use an already authorized terminal; meaningful command output may be better than video. |
| Other projects, including native applications | Use computer use under permissions already granted to this session. Request only missing access required for the specific capture/action; do not ask again for existing authorization. |
| Nonvisual change | Use real semantic/output evidence. A video may be not applicable with a concrete reason. |

Discover the available built-in browser/terminal and capture interfaces in the
current runtime. Opening a Codex panel is not proof of capture capability.
Do not invent tool calls or use a computer-use/browser-use fallback for web
evidence when built-in browser capture is unavailable. Record that gap as
`not verified`, retain finalized evidence and identify the missing capability.
Only ask for additional access when it is actually needed. Existing session
permissions do not waive platform approval checks.

Run the representative changed behavior from the exact committed PR revision.
Verify the launched build's identity, not merely checkout HEAD. Preserve
unrelated dirty work; do not capture it as proof of the intended revision.
Record a baseline when useful. Capture concise before/after screenshots and
an approximately ten-second interaction with an observable result. Do not
substitute generated imagery, slides, or a clip of passing test text for UI
behavior. Avoid sensitive data before capture; inspect all finalized assets.

Use ffmpeg/ffprobe only to encode, trim, decode or validate actual captures.
They are not the capture source. A sequence assembled from genuine built-in
browser frames must retain the actual interaction order; record frame-capture
and assembly details rather than implying native video recording. Never
invent intermediate behavior. Rehash after redaction or encoding.

Record `demonstration.surface` (web, terminal, other, nonvisual) and
`capture_source` (codex-browser, codex-terminal, authorized-computer-use,
other-terminal, none). The schema rejects incompatible combinations and
requires provenance for media. A terminal fallback requires a limitation.
Describe the actual tool/session/export, scenario and outcome in `tool`;
keep private session IDs and unnecessary paths in local provenance sidecars.
These declarations are assertions to verify, not proof supplied by a validator.

## Finalize the bundle

`scripts/review-bundle.mjs` defines version 1. The synthetic manifest example
is not real evidence. Required fields include exact head/base repository and
ref identity, tested/full build SHAs, clean-source assertion, UTC capture time,
actual verification evidence, limitations and SHA-256 asset hashes.

Stable identity is host:repository-ID, then PR number, then full tested SHA.
The publication key adds the SHA-256 digest of canonical stable evidence:
schema_version, repository, pull_request, revision, summary, acceptance,
demonstration and assets. Sort assets by logical ID and object keys by
JavaScript code-unit order; retain other array order; serialize UTF-8 JSON
without whitespace or Unicode normalization. Observation/CAS/preparation
times, receipts and credentials are excluded. Capture timestamps are included.
Changed evidence creates a new key; retry/status refresh preserves it.

Use criterion states verified, not applicable and not verified. Failed,
skipped or not-run evidence cannot support a verified criterion. Missing UI
tools are not a reason for not applicable. Verified UI evidence requires
screenshots, video and matching build SHA plus actual behavior review.

Allowed assets are PNG, fast-start H.264/yuv420p MP4, UTF-8 text and JSON. Keep
assets alone in their directory; manifest and receipts belong outside it.
Local contract limits are 256 KiB manifest, 8 assets, 16 MiB/file and 32 MiB
total. The service advertises smaller limits: 8 MiB/file, 20 MiB assets and
21 MiB multipart request. The publisher applies configured and service bounds.
These are enforced ceilings, not a claim that every hosting/network layer
accepts the maximum. Oversized evidence must be reduced locally and rehashed.

Run helpers by installed absolute path when outside this repository:

```text
node process-issues/scripts/review-bundle-cli.mjs config CONFIG REPO_ROOT
node process-issues/scripts/review-bundle-cli.mjs key MANIFEST
node process-issues/scripts/review-bundle-cli.mjs validate MANIFEST ASSET_DIR
```

Put the computed key in publication.key before validation. The full validator
counts decoded frames, checks dimensions/codec/duration and decodes the whole
visual stream using bounded ffprobe/ffmpeg subprocesses. Missing/failed tools
fail media validation. Integrity-only mode is a diagnostic explicitly marked
not verified. Neither decoding nor hashes establish semantic/visual correctness.

## Publish and retain a receipt

Refresh native Sites metadata immediately before invocation (maximum age
120 seconds). Verify ID, canonical origin, owner role and owner-only audience.
Do not print metadata containing the service credential. Pass it via hidden
stdin as one JSON line with keys `native_site` and `metadata_read_at`.
The native service token may instead be injected under the configured
service_token_env name after the same metadata verification.

Inject the publisher secret under publisher_key_env, or through hidden stdin
as publisher_key. On Windows the supplied vault helper stores it per user in
Windows Credential Manager without printing it:

```text
python process-issues/scripts/review-publisher-vault.py store SITE_ID
python process-issues/scripts/review-publisher-vault.py run CONFIG REPO_ROOT MANIFEST ASSET_DIR
```

Store accepts hidden JSON containing publisher_key. It refuses to overwrite a
different existing key. Run accepts only native metadata, retrieves the key,
and passes it to the child process environment. Use the same normal Windows
user as the intended operator. No key is written to configuration or a file.

On other systems use an existing secure environment injection mechanism:

```text
node --use-system-ca process-issues/scripts/review-publish-cli.mjs CONFIG REPO_ROOT MANIFEST ASSET_DIR
```

The tested Windows runtime needed --use-system-ca to use the OS trust store.
Never disable certificate checks. Disabled configuration returns before reading
credentials or making network calls.

The CLI validates local media, verifies the repository/PR head/base identities
with gh, discovers live limits, and looks up the publication key before writing.
It uploads bounded multipart to the fixed verified origin with redirects
disabled. It never fetches URLs supplied in a manifest or receipt. It verifies
stored asset bytes, rechecks GitHub, applies a guarded observation update and
writes a durable ignored receipt containing canonical project/review URLs and
the exact tested SHA. Report only links returned by this verified operation.

Reads require platform visitor identity or the publisher credential. Writes
additionally require the application key and reject browser Origin/Cookie
requests. Viewer access alone never grants write access. The gallery escapes
text and uses only validated GitHub links and same-origin media routes.

## Recovery, concurrency and freshness

R2 objects are immutable by publication key/asset ID/hash. D1 batches record
the immutable publication and compare-and-swap the per-PR current pointer.
A failed asset/database step cannot replace the previous successful review.
Unreferenced objects may remain after failure; broad cleanup is out of scope.

An identical retry returns the same publication. After an ambiguous upload,
unreadable response body or
server error the client looks up the key once before considering another run;
it never blindly resubmits. A later run can publish the same finalized bundle
without rerunning implementation or capture. CAS conflict requires a fresh
GitHub/state assessment; do not blindly replace a version. Different PRs and
repositories have separate current pointers. Older observations cannot
overwrite newer ones; stale evidence remains historical when current evidence
exists. Older captures of the same commit remain historical even after a
retry refreshes the storage version. Capture time does not order different
commits. SHAs are identities, not chronological ordering.

The final GitHub read establishes freshness only as of its timestamp. A changed
head is stale; an unavailable head or failed observation refresh is unknown.
A failed final delivery/read-back retains server state and local evidence but
does not return a verified-delivery success; retry reconciles by key. No
automatic polling silently refreshes the gallery.

Optional publication occurs after the existing clean 60-second ready window.
Required evidence is captured/published/verified while draft, before entering
that transition. Refresh head/status after the window; replace or explicitly
invalidate stale evidence. Capture/publication never resets the two correction
passes, three ready windows, ownership limits or explicit merge authorization.

Missing optional media does not erase independently verified code evidence.
Missing required media/delivery stays not verified and follows existing draft/
blocked rules. Use Refs while material acceptance remains outstanding. A
physical-phone-only step may be an explicit human handoff when permitted; do
not claim device verification from emulation.

## Review and add another project

Open the returned PR deep link as the intended signed-in viewer. Confirm the
summary, tested SHA, actual results, provenance and stale/unknown labeling.
Check screenshots full-size, video play/pause/seek and GitHub navigation.
Reload and check persisted history; repeat after a deploy to establish
durability. On the intended physical phone also inspect narrow-screen layout,
text/media sizing and controls. Record each check and exact remaining action.

For another repository, opt in with its verified host/numeric ID, the same
retained Site identity and safe local configuration/storage. Reuse authorized
credential storage; do not create another Site or share project secrets.
The first successful publication creates its project view automatically.

## Focused verification

```text
node --test process-issues/tests/review-bundle.test.mjs process-issues/tests/review-service.test.mjs process-issues/tests/review-publish.test.mjs
```

Run the skill validator and git diff --check as applicable. Build the overlay
with the current Sites starter's documented workflow. Evaluate
`tests/review-site-workflow-scenarios.md` separately from executable tests.
Capture, browser appearance, intended-user login and phone playback require
runtime evidence; unit tests cannot establish them.
