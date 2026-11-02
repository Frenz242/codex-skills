# Agreed defaults

These are starting preferences, not mandatory styling for every project. Explicit choices in the current request take precedence. They were established through the Frenz-Dashboard defaults interview.

| Area | Default |
| --- | --- |
| Interview | Short, recommendation-led; cover purpose, data, audience and changed preferences. Reuse answers already provided. |
| Palette | Suggest a palette for each dashboard. Favor bright, vivid colors that pop. Avoid muddy or muted accent/data colors unless requested. Reusing a successful palette is welcome; uniqueness is not a goal. |
| Surfaces | Readable neutral light/dark surfaces and text support the vivid accents. The bright-color preference does not mean saturating every background or using low-contrast text. |
| Theme | Follow the system initially, with visible System/Light/Dark choices and a persistent preference. |
| Density | Comfortable spacing that adapts to mobile. Compact density is an option when the task calls for it. |
| Layout | Summary to detail: useful KPIs, primary chart, supporting views, searchable records when relevant. Sidebar or other navigation only when useful. |
| Navigation | Standard hamburger icon and accessible Menu toggle; collapse releases sidebar space without state loss. Mobile items and labels wrap; no internal menu scrollbar. |
| Self-documentation | Nearby plain-English info boxes or callouts explain tags, warnings and unique terms, including implications and relevant next steps. |
| URLs | Shareable query state for section, filters, sort, page, page size and open entry; restore on direct load, reload and Back/Forward. |
| Tables | Sortable columns, pagination on every table list and a remembered rows-per-page selector. Explicit shared URL values take precedence over local preferences. |
| Reuse | Share components and state logic where practical while preserving meaningful differences between views. |
| Period | Recommend from data cadence and purpose; one shared date control across applicable views. Six months is an option for activity analysis, not a universal default. |
| Interaction | Useful filters, persistent click/tap details, keyboard access, and Back/Forward plus reload restoring the view. |
| Extras | Suggest exports and comparisons when helpful. Add editing only for an authorized need. |
| Charts | Choose from the analytical question, data shape and valid aggregation; no required chart lineup. |

## Palette suggestions for the interview

Offer two or three relevant directions, rather than an exhaustive catalog. These are seeds to adapt and validate, not fully tested theme palettes:

- **Indigo + cyan:** primary `#4F46E5`, cyan `#06B6D4`; familiar analytical feel. Indigo is also suitable for single-measure trends and sequential intensity scales.
- **Cobalt + orange:** primary `#2563EB`, orange `#F97316`; clear distinction between a main accent and a contrasting highlight.
- **Violet + teal:** primary `#7C3AED`, teal `#14B8A6`; vivid without requiring every category to use a different hue family.

Select separate light/dark foreground, surface, border and mark variants; do not assume these seed hex values are readable on every background. Reserve labeled amber/red for warnings/errors in the interface. A data category may use those hues, but its legend must make its categorical meaning clear. Good/bad colors depend on the metric, not on whether a number increased.

Use a sequential scale for magnitude, a diverging scale for values around a meaningful midpoint, and categorical colors for identities. A brand accent is not a substitute for all three.
