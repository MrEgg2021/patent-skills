# Google Patents Official Search Guide

This file freezes the official search facts used by the `patent-search` skill.

## Sources

- `official_help_doc`: https://support.google.com/faqs/answer/7049475
- `official_help_doc`: https://support.google.com/faqs/answer/7049588
- `official_help_doc`: https://support.google.com/faqs/answer/7049724

## Confirmed official behavior

### Query language

Source level: `official_help_doc`

- Supports free-text queries.
- Supports quoted phrases.
- Supports Boolean operators such as `AND`, `OR`, and `NOT`.
- Supports field-constrained terms such as `TI=`, `AB=`, and `CL=`.
- Supports date operators such as `before:` and `after:`.
- Supports metadata filters including `inventor:`, `assignee:`, `country:`, `status:`, and `language:`.
- Supports wildcard matching with `*`.
- Supports proximity ranking with `AROUND(n)`.

### Input surfaces

Source level: `official_help_doc`

- The home search box accepts raw query syntax.
- Prior Art Finder can accept larger text passages and extract keywords.
- Similar Documents uses text similarity against the current patent document.

### Entity search

Source level: `official_help_doc`

- `inventor:` and `assignee:` use autocomplete in the Google Patents UI.
- Prefix matching is supported for longer entity names.

### Result ranking

Source level: `official_help_doc`

- The results page defaults to `Relevance`.
- The user can switch the sort mode to filing-date views such as newest or oldest.

## Internal design rules derived from official facts

Source level: `internal_design_rule`

- Keep the first query short and relevance-friendly.
- Use field restrictions in the second or third query set before adding complex Boolean nesting.
- Treat `AROUND(n)` and wildcard matching as optional refinement tools, not default first-pass operators.
- Never send full technical disclosures to external search or translation services.
