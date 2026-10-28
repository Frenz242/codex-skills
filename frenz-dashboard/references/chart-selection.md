# Choose charts for the question

Use this as a decision aid, not a menu the dashboard must include. Explain each major chart recommendation in one sentence tied to the user's decision.

| Question / data shape | Good starting view | Guardrail or alternative |
| --- | --- | --- |
| What is the current result? | KPI value with unit, period and useful context | Add a sparkline only when a time sequence exists. Show a delta only against a defined comparable baseline. |
| How does a measure change over time? | Line chart for a trend; columns for discrete period totals | Preserve real temporal spacing; do not interpolate missing observations as known values. Avoid smoothing that invents extrema. |
| Which categories are largest? | Sorted horizontal bars | Especially useful with long names or many categories. Start quantitative bar axes at zero. Provide filtering or an exact-value table for large sets. |
| What makes up a whole? | Sorted bars; optionally a donut for a few nonnegative parts | A donut requires a meaningful, complete whole. Avoid it for many similar values, negative values, or unrelated measures. Make any Other breakdown inspectable. |
| How do additive contributions change over time? | Stacked columns or stacked area | Use real opaque stacked bands and preserve totals. For comparing individual trends, prefer small multiples or selectable lines. |
| How does proportional mix change? | 100% stacked bars/area | Label normalization and expose absolute totals; percentages can hide a shrinking denominator. |
| How are values distributed? | Histogram, box plot or dot plot | Inspect sample size, bins, outliers and skew. Do not replace a distribution with its average alone. |
| Are two numeric measures related? | Scatterplot | Label units and expose point detail; correlation does not establish causation. Use size only for a meaningful additional measure. |
| How does performance compare with a target? | Bullet chart, dot plot or bars with a target reference | Explain the target and direction of improvement. A gauge is an optional compact status view, not the default comparison tool. |
| What is the gap between actual and baseline? | Diverging bars or variance plot | Use a meaningful zero/midpoint, consistent units and comparable periods. Show the baseline. |
| When does activity recur? | Calendar heatmap or weekday/hour matrix | Use only with meaningful time coverage and cadence. Distinguish missing evidence from known zero and expose exact cell values. |
| Where does a measure vary? | Map when location itself matters | Use normalized rates when raw totals mainly reflect population/exposure; otherwise a ranked bar chart is often easier to compare. |
| Which records need action? | Searchable, sortable table with status and detail | A table may be the primary view. Do not force a decorative chart onto a record-review task. |

## Shared decisions

- Identify the data grain, measure type, units, denominators and aggregation before choosing the encoding. Weighted rates require their weights; snapshots across dates generally cannot be summed.
- For dense series, use selection, small multiples, ranked bars or a table before relying on dozens of colors. A large available palette does not justify a crowded chart.
- Keep category assignments consistent across every view and filtered subset. Preserve exact names and values as an alternative to interpreting color or area.
- If using Top N + Other, disclose the rule and retain the full total and inspectable remainder. Do not silently drop small contributors.
- Distinguish incomplete coverage, missing values and actual zero. Where coverage is complete, empty event buckets may legitimately mean zero; otherwise label the uncertainty.
- Choose time buckets suited to the cadence and visible span. Show the requested domain, not only dates with observations. Handle timezone, calendar boundaries and partial periods explicitly.
- Comparisons must use compatible definitions and periods. Clearly mark partial current periods; do not imply a full-period decline by comparing them with complete prior periods.
- Avoid 3D decoration, unexplained dual axes and unnecessary motion. Respect reduced motion. Let the user override a recommendation while explaining any material interpretation tradeoff.
