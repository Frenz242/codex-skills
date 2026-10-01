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
Delivery evidence: <for a local artifact, durable destination, intended-user access check, and integrity result, or reason>
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

## Local artifact delivery and user access

Treat delivery as a separate acceptance step from generating or reviewing a local artifact. Agent access, file existence, a successful render, and a clickable absolute link do not prove that the interactive user can open the result.

- Keep private scratch directories private. Publish the final artifact to an approved, persistent, ignored handoff location instead of presenting a protected temporary path as the result.
- Prefer creating the destination normally in a location already intended for user handoff. When repairing an existing handoff is necessary, grant access only to the verified intended user and only on the narrow path required.
- Preserve the source artifact and compare a cryptographic hash before and after copying. Keep customer or other private content out of tracked files, GitHub evidence, and observation records.
- Verify every parent directory can be traversed and the final file can be read by the intended user. When a reliable check cannot run in that user's context, record delivery access as `not verified`; ACL or mode inspection alone does not prove the user opened the artifact.
- On Windows, distinguish the sandbox account from the interactive user. Inspect protected ACLs, disabled inheritance, and explicit deny entries as well as apparent allow entries. Do not grant `Everyone` or `Users`, recursively change a workspace ACL, take ownership of Git metadata, or add a Git `safe.directory` exception as an access workaround.
- On POSIX, verify execute permission on each parent directory and read permission on the final file for the intended user or group. Do not relax a private scratch directory merely to make its final artifact deliverable; copy the result to the approved destination with appropriately scoped ownership and modes.

Only present the final local link as a completed handoff after the destination, access, and integrity checks pass. Report what was verified without claiming the user opened the file unless the user actually confirms that action.

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

### Windows protected temporary-directory handoff

- Setup: a synthetic artifact is generated in a sandbox-owned Windows temporary directory with inheritance disabled. The agent account can render and read it, but the intended interactive user lacks parent-directory traversal or final-file read access.
- Required evidence: distinguish the two accounts, inspect the complete parent and file ACL chain including protected inheritance and deny entries, and attempt an intended-user access check when the environment supports it.
- Expected result: the temporary path is not presented as a completed handoff. Generation and agent-side review may remain verified, but delivery access is `not verified` or failed until a safe destination is used.

### Accessible Windows artifact delivery

- Setup: copy the same synthetic artifact into an approved persistent, ignored handoff directory created with normal user-accessible inheritance.
- Required evidence: verify intended-user parent traversal and final-file read access, compare source and destination hashes, and inspect the delivered artifact through the appropriate viewer or parser. If account impersonation is unavailable, state that limitation instead of treating ACL inspection as proof of access.
- Expected result: the final link may be handed off only when the available access check passes and the hashes match. Preserve the private source and do not claim the user opened the artifact without user confirmation.

### POSIX private scratch and final delivery

- Setup: a synthetic artifact is generated beneath a private scratch directory such as one with mode `0700`, while the final handoff must be readable by a different intended user or appropriately scoped group.
- Required evidence: keep the scratch permissions unchanged, copy the final artifact to an approved persistent destination, verify execute permission on every parent and read permission on the file in the intended access context, and compare source and destination hashes.
- Expected result: the private scratch path is never used as the final handoff. If scoped destination access cannot be established without broad grants or ownership changes, delivery remains `not verified` and the workflow reports the blocker.
