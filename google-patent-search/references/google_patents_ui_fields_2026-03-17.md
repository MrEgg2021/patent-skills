# Google Patents Live UI Notes (2026-03-17)

This file records the live Google Patents UI state observed on 2026-03-17.

## Sources

- `live_ui_observation_2026-03-17`: https://patents.google.com/advanced
- `live_ui_observation_2026-03-17`: https://patents.google.com/?q=machine+learning

## Advanced Search UI fields

Source level: `live_ui_observation_2026-03-17`

- `Search terms`
- `Date`
- `Inventor`
- `Assignee`
- `Patent Office`
- `Language`
- `Status`
- `Type`
- `Litigation`

## Results-page controls

Source level: `live_ui_observation_2026-03-17`

- `Sort by · Relevance`
- `Group by · None`
- `Deduplicate by · Family`
- `Results / page · 10`

## Internal design rules

Source level: `internal_design_rule`

- `Litigation` remains out of scope for v1 search planning.
- `Patent Office`, `Language`, `Status`, and `Type` should be carried in `advanced_fields` even when a deterministic query-string mapping is incomplete.
- The skill should preserve `Relevance` as the default browser-driven search view unless the user explicitly asks for a time-ranked perspective.
