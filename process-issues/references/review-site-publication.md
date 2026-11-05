# Private review Site: evidence foundation and rollout

Read this when a project opts in to hosted PR evidence. This implementation is
**partial**: local configuration inspection, deterministic bundle validation and
media decoding are available. Automatic publication, the persisted gallery and
the real-PR/physical-phone pilot are not yet implemented or verified. Do not
report a local bundle or registered Site as a completed hosted review.

## Current runtime preflight

The initial investigation used Codex desktop on native Windows, Node 24 and the
installed Sites plugin. Native Site registration and owner-private metadata reads
worked. The supported Vinext starter built, and a local D1/R2 transport probe
passed upload/hash/read-back, repeat upload, viewer/write separation, signed-out
media GET/HEAD/range rejection, private caching, and byte-range tests. This is
local synthetic evidence, not a hosted transport or phone playback result.

The Site source bootstrap awaits the user's explicit initial commit/push
approval under their Git policy. Retain its ID in that local Site's
`.openai/hosting.json`; never register another Site to retry. The registered
identity, source checkout, seed inventory and credentials do not belong in this
public skill. Standalone CLI, WSL, macOS/Linux and future unattended execution
have not been exercised. There is no schedule or background publisher.

## Opt-in configuration

Start with `assets/review-site.config.example.json`. Keep the actual config in
an ignored `.codex/review-site.local.json`, or select another path explicitly
using the CLI's CONFIG argument. An invoking agent may resolve
`CODEX_REVIEW_SITE_CONFIG` before passing that argument. The helper itself does
not implicitly read environment paths. Ignore the local config and evidence
directory in the target repository's local `.git/info/exclude` or established
project ignore policy, without replacing existing exclusions. Missing config
or `enabled: false` produces no Site calls or writes. Unknown versions fail.

The configured repository host and numeric ID must match the verified `gh`
context. Display names and repository renames do not define project identity.
Live Site ID/origin must come from native Sites metadata. V1 accepts canonical
HTTPS `*.chatgpt.site` origins only; custom domains are not yet supported.
Credentials are environment-variable **names**, never values. The future
transport uses the documented Site service credential plus a separate
application publisher secret; ordinary viewers must remain read-only even if
the audience changes. Missing credentials are a publishing blocker, not an
instruction to create/rotate a Site bypass token.

Use a durable, ignored, repository-relative evidence directory outside managed
installed-skill bundles and synced working folders. The config inspector checks
Git ignore/tracking and resolved path containment without creating directories.
The project agent must also check parent sync/junction policy and intended-user
access, as required by runtime acceptance validation. Local artifacts are not
user-delivered merely because the agent can read them.

## Bundle v1 contract

`assets/review-manifest.example.json` is a synthetic nonvisual record, not real
test evidence. `scripts/review-bundle.mjs` is the executable contract. It rejects
missing/unknown fields, unsupported versions, unsafe filenames, invalid URLs,
oversized bundles, incomplete verified criteria and inconsistent revision data.
All timestamps are UTC ISO-8601 ending in `Z` (seconds or milliseconds). Numbers
are safe integers; durations use milliseconds. Allowed files are PNG, fast-start
H.264 MP4, UTF-8 text and JSON. Limits: 256 KiB manifest, 8 assets, 16 MiB per file,
32 MiB total asset bytes. These are local design bounds, **not proven hosted
payload limits**. A future uploader must enforce the smaller configured limits
and the live service's advertised limits.

Identity:

- `project_key = canonical host : numeric repository ID`
- `pr_key = project_key : PR number`
- `revision_key = pr_key : full tested head SHA`
- `publication_key = revision_key : SHA-256(canonical stable evidence)`

Canonical stable evidence includes only `schema_version`, `repository`,
`pull_request`, `revision`, `summary`, `acceptance`, `demonstration`, and `assets`.
Sort assets by logical ID using code-unit order; recursively sort object keys
using JavaScript's default code-unit order; preserve all other array order.
Serialize strings using JSON.stringify, integers in decimal and booleans/null
as JSON, without whitespace; hash UTF-8 bytes. No Unicode normalization occurs.
Capture/test timestamps remain part of the evidence. The publication key,
expected-current/CAS version, preparation/retry times and `observed_github` are
excluded. Receipts, URLs returned by the service, secrets and local paths have
no manifest fields and must remain separate local sidecars. A retry or status
refresh preserves the key; genuinely changed evidence creates another key.

An observed matching head means only "matches the head as of this observation."
A different observed SHA is stale; a null observed SHA is unknown. SHAs never
imply chronological order. Repository renames preserve project/PR identity,
while updated display metadata may produce a new evidence payload digest.

Use the existing criterion states `verified`, `not applicable`, `not verified`.
Individual evidence items retain `passed`, `failed`, `skipped`, `not-run` and
`not applicable` plus reasons. The validator will not accept failed/skipped/
not-run evidence inside a verified criterion. A UI demonstration cannot be
`not applicable` just because capture tools are missing. A verified UI record
needs screenshots, a video, and an asserted matching build SHA. These assertions
still require agent verification of the actual running build and visible behavior.

## Local commands and checks

Node 22+ is required. Run helpers by their installed absolute path when outside
this repository. These commands never create a Site, publish, mutate Git or
modify evidence. The `key` command computes a proposed key; place it in the
manifest's `publication.key`, then validate the final manifest and exact asset
directory. Keep assets separate from the manifest and receipts; extra files in
the asset directory are rejected.

```text
node process-issues/scripts/review-bundle-cli.mjs config CONFIG REPO_ROOT
node process-issues/scripts/review-bundle-cli.mjs key MANIFEST
node process-issues/scripts/review-bundle-cli.mjs validate MANIFEST ASSET_DIR
node --test process-issues/tests/review-bundle.test.mjs
```

Full local validation invokes installed `ffprobe` and `ffmpeg` without shell
interpolation, with bounded time/output. It checks decoded dimensions, H.264/
yuv420p, duration, and a complete visual-stream decode. A missing/failed tool
fails validation. `--integrity-only` explicitly skips decoding and returns
`media_decode: not verified`; it is a diagnostic, not a capture acceptance gate.
Container/hash validation alone does not prove a decodable or meaningful clip.
The helper always reports source provenance and behavior review as unverified
by the helper; the agent must supply those distinct evidence layers.

## Capture and workflow integration

Keep GitHub operations in `gh`/Git. Supported application capture and Sites
operations may use their own native tools. Never replace GitHub ownership,
feedback or review-state handling with browser automation.

1. Verify authorized repository/PR scope and current head/base identities.
   Preserve unrelated work. Capture from the final committed source and verify
   the running application's build provenance, not just checkout cleanliness.
2. Demonstrate one actual changed behavior with sanitized inputs. Prefer real
   before/after screenshots; otherwise explain an after-only capture. Capture
   roughly 8–15 seconds of the user interaction and observable result, readable
   on a phone. Generated imagery, staged slides or passing test text do not
   demonstrate a changed UI. Nonvisual changes use semantic output evidence.
3. Decode and inspect finalized screenshots/video. Rehash after redaction or
   encoding; retain local provenance. A successful decoder does not verify the
   scenario. Do not put real media or raw logs in this public repository.
4. Extend the existing acceptance ledger with source/build, capture, decode,
   semantic/visual review, and intended-user delivery evidence. Missing UI
   tooling is `not verified`, not `not applicable`.
5. Optional delivery occurs only after the existing clean ready window. If
   hosted evidence is required acceptance, publish and verify it while draft,
   then enter the existing ready transition. Refresh head/status after the full
   60-second window. Evidence must be replaced or explicitly stale/unknown when
   the head changes. Neither publication nor capture resets the two correction
   passes/three windows, scope, ownership, or explicit merge authorization.
6. Report the actual PR state separately from delivery. Optional upload failure
   preserves the verified code state and local evidence. Required missing
   hosted evidence remains unverified and follows existing blocking rules.
   Use `Refs` while any material criterion is outstanding. A physical-phone
   check can be a specific human-only handoff; emulation never proves it.

## Next rollout gates (not yet implemented)

Prove an authenticated synthetic upload/read-back from the actual runtime to
the registered private Site before building the gallery. Verify canonical
origin, owner-private audience, service credential, and separate server-side
publisher boundary. Do not forward credentials through redirects or copy them
to source, shell arguments, logs or browser code. A capability/read check and
binary roundtrip must include signed-out direct media GET/HEAD/ranges.

Then implement one proven transport: bounded multipart upload, immutable R2
assets, atomic D1 metadata promotion with per-PR CAS, publication-key lookup for
ambiguous timeouts, historical revisions, guarded observation refresh, durable
receipts, and publish-only retries. Do not blindly replace a CAS version after
a conflict: refresh GitHub and check promotion eligibility. Recheck the head
after upload; update stale/unknown status without demoting newer evidence.

Build the mobile gallery against persisted records with project/PR deep links,
screenshots, controlled inline video, actual results and explicit freshness.
Protected media must survive reload/redeploy and support private HEAD/range
responses. Validate a real PR from this manually invoked workflow, then hand
off the exact phone URL and play/pause/seek/screenshot/GitHub-link checks.

Current native Sites guidance is installed with its skill; read its storage,
identity/service-access and source/deployment references before resuming.
Platform documentation: [data and files](https://learn.chatgpt.com/docs/sites/data-and-connections),
[publishing and sharing](https://learn.chatgpt.com/docs/sites/publishing-and-sharing).
These document platform building blocks, not proof that this integration works.
