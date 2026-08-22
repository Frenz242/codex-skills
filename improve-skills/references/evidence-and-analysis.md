# Evidence and analysis

## Preserve facts; derive priorities

Store raw evidence type, category, run, version, severity, reuse judgment, and positive/negative nature separately from later ranking. Do not rewrite historical facts when the weighting model changes and do not assign fake probabilistic precision.

Use this explainable evidence order:

1. explicit user correction or explicit negative feedback;
2. objective failed test, violated acceptance criterion, or invalid artifact;
3. repeated independently observed workaround or failure;
4. recurrence across distinct privacy-preserving contexts;
5. repeatable external activation false positive/negative;
6. repeated self-observation without external confirmation;
7. isolated self-observation;
8. speculative idea.

Then consider independent run count, distinct context count, severity/safety, current versus obsolete content hashes, recency, and positive counter-evidence. Several observations in one run remain one occurrence. Fewer reports after a change are correlation/monitoring evidence, not proof of causation.

## Reuse guard

Before treating evidence as improvement-oriented, ask:

- Would it matter in another invocation of the same skill?
- Could it plausibly matter in another repository/context?
- Does it expose a reusable rule, method, invariant, capability, or guardrail?
- Is recurrence plausible?
- Is it actually a temporary project fact?

Classify reuse as `high`, `medium`, `low`, or `task-specific`. Never promote a low-confidence one-off solely because it exists.

## Target and problem clustering

The database groups observations by an analyst-assigned stable `problem_key`. Candidate names are aliases; the problem solved is canonical. Before opening a new-skill issue, search:

1. installed skills and adjacent ownership;
2. existing candidate clusters and aliases;
3. open and closed GitHub issues;
4. open and merged pull requests.

Use reasoning for semantic clustering and record the result. Deterministic normalization only catches obvious aliases; it does not pretend to solve semantic similarity.

Classify the cluster as `existing-skill`, `repository-rule`, `shared-infrastructure`, `new-skill`, `insufficient-evidence`, or `no-action`. Prefer an existing owner. Move a rule to repository `AGENTS.md` only with evidence it is truly global, not merely repeated twice.

## Candidate lifecycle

Lifecycle is explicit and historical:

`observed → candidate → validating → validated → promotable → implemented → monitoring → confirmed`

Alternate states include `deferred`, `invalid`, `duplicate`, `superseded`, `regressed`, `reverted`, and `declined`. Transitions add immutable history; they do not delete or renumber records. A previously addressed observation remains queryable and linkable to an issue, PR, merge, or outcome.

## Targeted review path

The recorder is paired with explicit consumption commands:

- `health` validates infrastructure first.
- `query` filters by skill, lifecycle state, category, suggestion kind, and time.
- `clusters` shows grouped candidates and distinct-run/context counts.
- `history` shows state changes.
- `mark` transitions state with a reason.
- `cluster` creates/reuses one canonical problem and records aliases/relationships.
- `link` associates sanitized public references or outcome slugs.

Review a narrow slice first, then expand only if root-cause analysis requires it. Include guardrail successes as regression protection. Explicitly record `no-action` when working behavior should be preserved.

## New-skill qualification

A new-skill cluster normally needs three independent runs, or two independent runs with high/critical cost, risk, or value. It also needs a recognizable recurring goal, stable inputs/outputs, reusable workflow, realistic triggers and non-triggers, practical validation, no natural current owner, and benefit exceeding routing/context cost. Repeated commands alone are not a skill.
