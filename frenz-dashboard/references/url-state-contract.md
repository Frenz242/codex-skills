# Dashboard URL contract and regression coverage

Read this before implementing navigation or table state. Document the concrete contract in each generated site's developer documentation: supported sections, filters and values, sortable columns, defaults, page-size choices, entry-ID format, history rules and examples. Explain sharing and any excluded private selections in the site's own help.

## Query parameters

Use query parameters for validated presentation state. Each view must have a shareable URL; the current URL includes the effective state so a recipient's preferences cannot change the shared view.

| Parameter | Meaning and validation |
| --- | --- |
| `section` | Allowlisted view identifier; unknown or duplicate values use the default section. |
| `filter.<key>` | Allowlisted filter name and value for the selected section. Omit inactive filters. The helper supports single-value categorical filters; explicitly extend and test the schema for dates, search or multiple values. |
| `sort` | Allowlisted sortable column for the selected section; otherwise use that section's default. |
| `direction` | `asc` or `desc`; otherwise use that section's default. |
| `page` | One-based positive safe integer; otherwise 1. After filtering, clamp to the available page count (empty results use page 1) and replace the current URL. |
| `pageSize` | An allowed positive page size. Explicit valid URL wins over remembered preference, which wins over the site default. An invalid explicit value uses the site default. |
| `entry` | Optional stable, non-sensitive ID for open details. The helper permits 1–128 ASCII letters, digits, underscores and hyphens. Validate authorization and existence separately after data loads. |

Example using synthetic identifiers:

```text
/dashboard?section=entries&filter.status=open&sort=updated&direction=desc&page=2&pageSize=25&entry=entry_42
```

Reject duplicate scalar parameters, invalid values and unsupported section-specific filters; do not interpolate query input into HTML or database queries. Canonicalize deterministically using URL encoding. The helper owns the dashboard query and drops unknown parameters; integrate explicitly with any host/router parameters that must survive. Never copy arbitrary query values into output.

Only include safe presentation values. Exclude credentials, raw records and sensitive search/filter text. Use access-controlled opaque references for private saved views when available; possession of a URL must not grant access. When private state cannot safely be shared, keep the safe view link usable and explain the omitted selections.

## History, details and preferences

- Read the query on initial/direct load, reload and every Back/Forward event; validate before rendering. Prefer router-native APIs when present, with the same semantics. Avoid push/restore feedback loops.
- Push deliberate section/filter/sort/page/detail changes. Reset the page to 1 when filters, sort or page size change. Coalesce search typing into one meaningful history step. Replace canonicalization, bounds corrections, and detail closing.
- Close details by removing only `entry` from the current validated presentation state using replace navigation. Never call Back to close: a directly opened link may have an unrelated previous page or no previous dashboard view.
- After an authorized lookup finishes, a missing, deleted or unavailable entry shows a dismissible plain-English notice. Preserve section, filters, sort, page and page size; remove the invalid entry parameter with replace navigation so reload does not repeat it. Do not reveal whether an unauthorized entry exists. Announce the notice politely, provide a labeled dismiss button and keep keyboard focus useful. Ignore stale lookup results for entries that are no longer selected.
- A valid open entry remains inspectable even when outside the current table page or filters; label this context rather than silently changing the shared scope.
- Remember explicit rows-per-page choices using site-scoped local storage (a versioned key such as `dashboard.rowsPerPage.v1`). Reuse the preference across the site's tables. Loading a shared URL must not overwrite the remembered choice. Handle unavailable storage without breaking pagination.
- Include the effective page size in generated links. Keep menu collapse and theme as personal UI preferences outside the shareable query. Toggling Menu must not change the query or remount/reset the dashboard state.
- When several independently controlled tables share a view, document and test namespaced table state; do not let their sort or pagination controls overwrite each other. The bundled helper handles one active table per section.

## Reusable implementation

[view-state.mjs](../assets/view-state.mjs) supplies a framework-neutral query codec and navigation controller. Reuse or adapt it to the project's stack instead of creating conflicting state logic in each view. Its schema is trusted application configuration; allowed filter values must already be safe to share. Data lookup, authorization, table sorting/filtering, bounds clamping, rendering, focus and storage adapters remain the site's responsibility.

```js
const schema = {
  defaultSection: 'entries',
  pageSizes: [10, 25, 50, 100],
  defaultPageSize: 25,
  sections: {
    entries: {
      sorts: ['name', 'updated'],
      defaultSort: 'updated',
      defaultDirection: 'desc',
      filters: { status: ['open', 'closed'] },
    },
  },
};
```

Wire `createNavigation(window, schema, options)` to rendering via `onChange({state, notice})`; callbacks `readPageSize` and `savePageSize` access the site-scoped preference. Call `navigate` with a complete filters object and page 1 for filter/sort changes; clear incompatible entry/filter state explicitly on section changes. Use `setPageSize`, `closeEntry`, `entryUnavailable(id)` after a completed lookup, and `dismissNotice` for those actions. For page clamping call `navigate({page}, {replace: true})`. Dispose the controller when its owner unmounts. The callback must render without performing record writes or recursively initiating navigation.

Keep state ownership above the collapsible menu and reusable view components. Share Menu, sortable table headers, pagination/page-size controls, detail panels and explanatory callouts where their behavior matches. Do not force unrelated views into an overly generic component.

## Five executable regression tests

Run from the skill repository root with Node.js 18 or newer (no packages required):

```sh
node --test frenz-dashboard/tests/view-state.test.mjs
```

The five tests cover:

1. A complete shared query restores section, filters, sort, page, page size and entry independently of local preferences.
2. Malformed, duplicate, unknown and section-incompatible query values fall back safely and canonicalize.
3. Back/Forward and controller re-creation for reload restore presentation state without changing saved records.
4. Explicit page-size selection persists and resets pagination; shared URLs win without overwriting preferences, and blocked storage remains usable.
5. Closing directly opened details preserves the current view; missing IDs produce a dismissible notice, stale lookups are ignored and the entry parameter is removed.

These use a deterministic history adapter, not a rendered browser. When generating a dashboard, add five corresponding regression tests in its existing test framework and exercise its actual UI. Include Menu collapse/expand without state loss, released sidebar space, keyboard/focus and ARIA behavior, mobile wrapping with no internal menu scrollbar, sorting before pagination across every table list, page-bound clamping, remembered page size, and accessible notice dismissal in the relevant scenarios. Inspect light/dark desktop and narrow mobile renderings. Never report helper tests as proof of browser layout, accessibility or authorization.
