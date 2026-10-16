# Optional Symphony execution boundary

[Symphony-Setup](https://github.com/Frenz242/Symphony-Setup) owns external workflows,
runner-only helpers and local deployment/activation. This repository owns its
reusable skills, safety rules, scope rules and validation. It contains no generated
workflow or automatically discovered runner-only landing skill. Cloning, pulling
or installing these reusable skills does not authorize Symphony.

In an explicitly authorized Symphony session, work only on its assigned issue
using the selected external workflow. The reviewed Setup route for this project
uses Linear; this does not move ordinary development or this repository's GitHub
backlog into Linear. Do not duplicate an issue between trackers or run
`process-issues` or another orchestrator concurrently for the same work. Tracker
assignment and repository-policy conflicts require human reconciliation.

Application-owned reusable skills remain available in either execution mode. Read
the relevant skill before using or editing it. Participating skills follow the
current [observation protocol](../improve-skills/references/observation-protocol.md):
one best-effort call with explicit `record-run`, privacy-preserving metadata, and
JSON `ok: true` before claiming persistence. Failure to record is non-blocking.
Do not duplicate an event as both a skill and an agent observation.

The external runner landing helper is an orchestration capability outside the
installed reusable-skill tree. It explicitly opts out of skill-run recording;
that does not opt application skills out. A Symphony task does not authorize
transcript collection, automatic skill improvement, global instruction changes,
installation changes or feedback-store setup.

## Transfer and rollout

The old `WORKFLOW.md` and `.codex/skills/land` are removed only after their sources
and behavior are preserved in Setup. Setup PR7 also carries the pending landing
feedback fixes and pure fixture tests from [PR20](https://github.com/Frenz242/codex-skills/pull/20)
at `7dc577377798c039f9eb4c711777dd2c896646c9`, with only runner-root path adaptation
and an explicit observation opt-out. Coordinate PR20's retirement after review;
do not merge it after this cleanup and recreate the removed installation.

Merge the canonical Setup transfer before this cleanup. Review actual runtime
build evidence and this boundary on the selected runner, stop legacy runners,
then explicitly deploy, inspect, record local prerequisite resolutions, enable,
and separately authorize a single-project smoke test. This change supplies no
local approval and starts no process. Disabling and stopping remain separate.

Do not synchronize generated workflow commits back into this repository. Installed
user skills and historical `~/bin` launchers require separate operator decisions;
this repository change neither edits nor removes them.
