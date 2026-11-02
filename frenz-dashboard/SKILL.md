---
name: frenz-dashboard
description: "Create or redesign interactive dashboards with Frenz's preferred UX: a short recommendation-led interview, vivid palettes, system light/dark themes, summary-to-detail exploration, and charts chosen for the data. Use when the user requests Frenz-Dashboard, a dashboard in Frenz's style, or reuse of the WorkTrace dashboard UX. Not for unrelated websites or a standalone static chart."
---

# Frenz-Dashboard

Build a dashboard that answers the user's questions and makes its underlying values easy to inspect. Preserve the interaction principles below while adapting the layout and visualizations to the actual data. Do not require every site to look unique.

## Start with a short interview

Read [defaults.md](references/defaults.md) for the agreed preferences. Use facts already supplied or safely available in the current project; do not ask the user to repeat them. Inspect available schemas or representative data before recommending charts when possible.

Ask a small batch of high-value questions, normally no more than three at once. Present a concrete recommendation beside each question, with a brief reason and one or two meaningful alternatives. Cover only missing essentials:

- Purpose and audience: what decision should the dashboard support, and who will use it?
- Data: source, grain, important measures, refresh cadence, and meaningful time range. Establish definitions, units, aggregation and timezone where they affect correctness.
- Preferences: suggest a vivid palette and relevant layout/interaction options; ask which saved defaults to change. Show color names and hex values or swatches, not only vague mood labels.

For example: "For weekly activity, I suggest cobalt and cyan accents on neutral surfaces, with distinct category colors. Keep that, reuse indigo, or choose another direction?" Derive the suggestion from the actual task rather than always using this example.

After the answers, briefly state the chosen defaults, layout and chart rationale. Continue building when the scope is clear; do not introduce a second approval gate. Wait for answers to material choices the user asked to make, while continuing independent work. If the user explicitly delegates choices, apply the saved defaults and state assumptions. Never treat silence as approval.

Use project-specific choices for the current dashboard. Update this skill's reusable defaults only when the user asks to save or change them globally.

## Choose the data views

Read [chart-selection.md](references/chart-selection.md) before choosing charts. For each proposed view, connect the analytical question to the measure, grain and chart type. Prefer a smaller set of useful views over filling a fixed template.

Check missingness, category cardinality, date coverage, duplicates and the meaning of totals before designing the views. Keep unknown, missing and zero distinct. Do not sum percentages, rates, snapshots or overlapping estimates as though they were additive observations. Explain uncertain definitions instead of inventing data.

Recommend the initial period from the data cadence and decision. Use one visible date control for all applicable KPIs, charts and records; show effective dates and timezone when relevant. Explicitly label exceptions such as lifetime benchmarks. Do not add a date control when time has no analytical meaning.

## Apply the UX

Read [ux-patterns.md](references/ux-patterns.md) for the reusable design decisions and their source. Apply relevant patterns rather than copying the source dashboard's domain or full implementation:

- Summary-to-detail hierarchy, comfortable cards and readable typography; navigation only where the sections warrant it.
- Collapsible navigation on desktop and mobile using a standard three-line hamburger icon and an accessible Menu toggle. Collapse must release sidebar space without resetting dashboard state. On mobile, wrap menu items and long labels onto the next line; use normal page scrolling instead of an internal menu scrollbar.
- Self-documenting views with nearby plain-English info boxes or callouts explaining tags, warnings and unique terms, their implications and relevant next steps.
- Sortable tables and pagination for every table list, with a rows-per-page selector that remembers the user's last explicit choice across the site.
- System/Light/Dark modes with a visible selector and persisted preference.
- Vivid semantic tokens for accents and data, readable neutral surfaces, named categories and exact values. Keep category identity consistent across views.
- Shared scope, useful filters and discoverable reset behavior.
- Click/tap detail that stays open, works with keyboard access and fits small screens.
- Shareable query parameters restoring section, filters, sort, page, page size and open entry on direct load, reload and Back/Forward, without reverting saved records or replaying mutations.
- Dismissible notices for missing entry IDs; closing details removes the entry parameter while preserving a directly opened view.

Read [url-state-contract.md](references/url-state-contract.md) before implementing navigation or tables. Document the site's concrete URL contract and add the five regression tests described there. Reuse its state helper or equivalent project-native logic, along with shared Menu, table, pagination, detail and callout components where practical.

Suggest comparisons, exports or additional exploration controls only when they help the task. Editable records require a real user need and authorization; they are not a default dashboard feature.

## Build and deliver

Use the existing project's stack and conventions when present. For a new dashboard, choose the simplest suitable delivery format within the user's request. Use available dashboard/data, website, or visualization workflows when their capabilities fit; inspect their instructions when applying them. Do not assume a particular plugin, chart library or hosting service is installed. The source dashboard's library and hosting choices are not requirements.

Keep data processing, previews and working files in local non-synced project storage. Use synthetic fixtures for committed examples and tests. Do not embed customer data, credentials, operational exports or source-dashboard records in the reusable skill or generated repository. Creating this design does not authorize public hosting, external sharing, source-data edits or sending messages.

Before handoff, validate the implemented behaviors that matter:

- Reconcile KPI/chart/table totals under the same filters and period; verify aggregation and date boundaries. Verify missing-data behavior, empty and single-value cases, long labels, and dense categories relevant to the dataset.
- Inspect light and dark renderings at desktop and narrow mobile widths. Check readable text and marks, keyboard focus, reduced-motion preferences, touch scrolling and persistent details. Aim for at least 4.5:1 normal text contrast and 3:1 meaningful non-text controls/marks; color alone must not convey meaning.
- Exercise filtering, reset, detail dismissal, Back/Forward and reload. If mutations exist, verify that navigation neither undoes nor replays them.
- Verify hamburger Menu collapse releases sidebar space and preserves all view state; check keyboard/focus behavior and mobile wrapping without an internal menu scrollbar.
- Verify every table list sorts before pagination, has page-size controls, remembers explicit choices, honors shared URL values and clamps invalid pages after filtering. Check contextual explanations and accessible notice dismissal.
- Test copied URLs in a fresh tab, malformed query values, direct-entry closing, missing IDs and history restoration. Run all five navigation regression scenarios from the URL contract against the site's implementation.
- Run applicable documented validation commands. Visually inspect actual rendered output when building a dashboard, not just source code. Report unavailable checks and limitations accurately; viewport emulation is not a physical-device test.

Deliver the dashboard and summarize the selected palette, charts and material validation results. When the current request is only a design or plan, deliver that artifact without silently expanding into implementation or deployment.

## Post-run observation

After substantive work completes, make one non-blocking `record-run` call through the shared portable launcher: `../improve-skills/scripts/run_feedback_store.ps1` on Windows or `../improve-skills/scripts/run_feedback_store.sh` on POSIX. Pass `record-run` explicitly before `--skill-path`; the launcher does not add it. Follow the shared [recorder invocation](../improve-skills/references/observation-protocol.md#recorder-invocation) examples and confirm JSON `ok: true` before claiming persistence. Resolve paths from installed skill locations. Record minimal run metadata always; include generalized detailed observations only for material evidence. Never record raw prompts, customer data, credentials or private URLs. If the helper is absent or recording fails, continue the primary task. An observation must never trigger skill modification.
