# Reusable dashboard UX

## Provenance and adaptation

Derived from the merged WorkTrace dashboard revision: [PR #7](https://github.com/Frenz242/WorkTrace/pull/7), merge commit `7f4c680`, especially `sites/worktrace-dashboard/THEME.md`, `app/theme.css`, `app/dashboard.css`, `lib/projects.ts` and the navigation/detail components.

The principles are captured here so normal use does not require access to WorkTrace. Do not copy its records, operational configuration, time-estimation logic or private data. Its Slate & Indigo palette, six-month Chicago reporting default, chart library and particular chart lineup describe that dashboard; the Frenz defaults generalize them as follows.

## Layout and visual hierarchy

- Lead with the dashboard purpose, current scope and actual freshness. A live indicator requires evidence of a live source; a static snapshot should show its update time.
- Put the global period and filters before the views they affect. Follow with a small set of meaningful KPIs, the primary analytical view, supporting views and relevant records.
- Use understated borders, comfortable whitespace, gently rounded cards and a readable sans-serif font. Highlight one leading metric only when its importance warrants it.
- The source used an approximately 230px desktop sidebar, a 1620px maximum main region, 10-12px card corners and an approximately 1.65:1 primary/supporting chart split. These are optional starting proportions, not fixed requirements. A simple dashboard may need no sidebar.
- On mobile, stack content in priority order, keep controls reachable and wrap long labels. Constrain horizontal scrolling to a deliberate chart/table region, not the whole page. Do not simply shrink desktop charts until labels become unreadable.

## Theme and color identity

- Use shared tokens for background, surface, text, muted text, border, accent, focus and semantic states. Theme the logo/favicon, controls, tooltips and charts consistently when those assets are in scope.
- Persist the user's System/Light/Dark preference; System follows changes in OS appearance. Validate both theme renderings.
- Favor solid vivid colors for common categories. Assign by canonical identity, never by an index in the currently filtered or sorted list. The same category should retain its style in charts, legends, tables, themes, navigation and reload.
- The source allocated 20 bright light/dark color pairs to the largest identities in the full snapshot, then added diagonal/dot/crosshatch cues for overflow. Its rankings could change with a new snapshot. Reuse this policy only when useful: choose a visible series count the chart can support, and never rerank colors just because a filter or period changes.
- When cross-refresh identity matters, persist assignments or otherwise define a stable assignment policy. If a deliberate refresh can reassign styles, make that behavior clear. Verified aliases can share identity; do not infer renames from similar labels alone.
- Use contrasting outlines or other cues when bright marks disappear against light surfaces. Patterns, labels, isolation and exact values supplement colors; do not promise unlimited visually distinguishable categories.
- Keep Other visually neutral and inspectable. Use sequential color for intensity and labeled warning/error states rather than treating every color as a category.

## Shared scope and inspection

- Apply the reporting range consistently to relevant KPIs, charts, axes and records. Display any intentionally different scope next to that view. Reset restores the agreed starting view and makes its effect clear.
- Offer date presets appropriate to the task and custom dates when useful. Calendar arithmetic must handle month ends and leap years in the chosen timezone.
- Where a wide chronological chart must scroll on mobile, initially expose recent data when that matches the task. Preserve manual scroll position on ordinary rerenders; do not repeatedly snap the user back.
- Provide named legends and a way to isolate or inspect categories. All contributors and exact values must remain accessible when a dense chart summarizes them.
- Clicking/tapping chart data opens detail that stays open after release. Hover may supplement desktop inspection but cannot be the only path. Preserve page scrolling and pinch zoom on touch layouts.
- Detail panels wrap long names, fit the current viewport including landscape, and scroll their content while keeping essential controls reachable. Provide an explicit close action, Escape, focus management and focus return. Outside click/tap may dismiss where appropriate.

## Navigation is view state

- Back/Forward restore meaningful sections, dates, filters, sorting, pagination and inspected records. Reload restores the current view where persistence is appropriate.
- Coalesce consecutive search typing into one meaningful history step, including the first keystroke if it resets pagination. Replace automatic corrections to invalid pages so Back cannot loop through an impossible page.
- Keep navigation state separate from durable saved data. Going Back must not undo a recorded decision, re-import a snapshot or repeat a write.
- Choose URL, session or local persistence according to sharing and privacy requirements. The source kept view state tab-local and names out of URLs. Shareable links are optional; never place sensitive filter values in URLs merely to support Back/Forward.

## Useful optional capabilities

Suggest comparison periods, filtered exports, saved views or editable workflows only when they serve the user's decision. Exports should state scope, units and period. Editing needs explicit save/error feedback and appropriate authorization. A static or planning-only deliverable should not pretend to have working live controls.
