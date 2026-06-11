# Search Phrase Templates

These templates are internal helper patterns for `patent-search`.

## Design rule

Source level: `internal_design_rule`

- The knowledge base can be broad.
- Generated queries must stay lightweight.
- Prefer 2-4 core concepts over exhaustive term dumps.

## Query-mode template

```
("core concept") AND ("key mechanism") AND assignee:"confirmed name"
```

## Technical-description template

```
core_strict:
  "primary object" AND "key mechanism"

balanced:
  ("primary object" OR TI="primary object") AND ("key mechanism" OR AB="key mechanism")

recall_fallback:
  ("primary object" OR "technical effect" OR "scenario term") AND classification
```

## Chinese input rule

Source level: `internal_design_rule`

- Keep Chinese terms local.
- Use English core phrases only when they can be derived locally from embedded English terms, a local glossary, or user-supplied must-include terms.
- If English confidence is low, let the mixed query set carry more weight.
