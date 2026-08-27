# Runtime acceptance validation

Use this reference after implementation when mapping an issue's material acceptance criteria to evidence. Automated tests remain necessary where the repository requires them, but they are only one evidence layer.

## Evidence model

Keep a compact ledger for each issue or coherent group:

```text
Criterion: <material acceptance criterion>
State: verified | not applicable | not verified
Automated evidence: <test/build/static command and result, or none>
Runtime evidence: <real changed path, representative input, and observed result, or reason>
Output review: <artifact/behavior inspected and semantic or visual finding, or reason>
Limitation: <remaining blocker or human action, if any>
```

Use `verified` only when the cited evidence proves the criterion. Use `not applicable` only when that evidence layer genuinely does not apply, not when it was inconvenient to run. Use `not verified` for a missing prerequisite, unavailable environment, failed command, unreviewed artifact, or other evidence gap.

If one material criterion is `not verified`, do not use `Fixes` or move the issue to `agent:waiting-on-merge`. Prefer `agent:blocked` while an unresolved prerequisite prevents agent work. If repository or user policy permits handing the remaining validation to a human, use `Refs` and `agent:needs-review` only when implementation and all agent-verifiable work are complete and the specific human validation action is identified.

## Selecting runtime evidence

Choose the closest safe path to what a user or downstream system exercises:

- CLI or application: run the public command or application flow and inspect exit behavior, stdout/stderr, produced files, and state changes relevant to the issue.
- Generator, report, or export: run it on representative input, parse or render the artifact, check the changed semantic fields or visual regions, and inspect relevant unaffected content.
- API or service: use a local or test integration path to verify the material status, response, schema, and side effects.
- Library: invoke the public API through an existing example or realistic harness rather than only an internal helper.
- UI: build or run the affected view and inspect the relevant state. Use existing browser, screenshot, or local UI tooling when practical; do not invent brittle automation solely to satisfy this contract.
- Documentation or metadata: mark runtime validation `not applicable` with a reason. Still run applicable link, schema, render, or packaging checks.

Use existing sanitized fixtures or synthetic data first. Local real-world inputs remain subject to repository privacy rules and must not be copied into commits, issue comments, pull requests, or reports.

## Output review

Match inspection to the artifact and issue:

- JSON, CSV, XML, configuration, or other structured text: parse it and assert material values, shapes, fallbacks, and formatting used by downstream consumers.
- HTML or SVG: inspect structure and content; render when the issue concerns appearance or interaction.
- Image, PDF, or other user-visible layout: visually review the rendered result when suitable tooling is available.
- State-changing behavior: inspect the resulting safe local or test state, not only the request or process exit.

For output-sensitive changes, compare with a default-branch baseline when it helps distinguish the intended change from accidental drift. Record the changed region and at least one relevant unaffected region when the issue calls for preserving adjacent output.

## Skill regression scenarios

Use these fixtures for forward evaluation of the workflow. The expected disposition is part of the fixture; an evaluator should vary filenames and domain details so success does not depend on memorized wording.

### CLI behavior change

- Setup: a unit test for a command helper passes, but invoking the public CLI still prints the old value.
- Required evidence: run the public command with representative arguments and inspect its exit status and output.
- Expected result: the criterion remains `not verified` until the real command emits the expected value. A passing helper test alone cannot complete the issue.

### Generated artifact change

- Setup: a report-generation unit test passes and the generator exits successfully, but the final artifact contains the wrong changed field.
- Required evidence: run the generator, parse or render the artifact, verify the expected changed field, and inspect a relevant unaffected field or region.
- Expected result: the workflow fails the quality gate until semantic or visual output review passes. File existence and exit code are insufficient.

### Runtime prerequisite failure

- Setup: automated tests pass, but the public application path fails because a documented local configuration or fixture is missing.
- Required evidence: attempt the documented setup or bootstrap path, record the missing prerequisite precisely, and identify which criteria remain unverified without exposing sensitive values.
- Expected result: do not claim full verification or use `Fixes`. Use `agent:blocked` if the prerequisite prevents further agent work, or `agent:needs-review` if implementation is complete and a specific human-only validation is the remaining step.

### Non-runnable documentation change

- Setup: the issue only corrects prose and has no executable behavior.
- Required evidence: run applicable documentation, link, render, schema, or packaging checks; record runtime validation as `not applicable` with the reason.
- Expected result: the issue may be fully verified without fabricating a runtime command when every material documentation criterion has appropriate evidence.
