# Assignee And Inventor Alias Strategy

## Goal

Expand entity names carefully without silently broadening the final search.

## Source levels

- `official_help_doc`: Google Patents supports autocomplete and prefix matching for `inventor:` and `assignee:`.
- `internal_design_rule`: alias candidates are gathered first, then confirmed by the user.
- `internal_design_rule`: related companies remain candidate-only unless the user confirms them.

## Candidate sources

1. Original user input
2. User-supplied alias candidates
3. Heuristic normalization
4. Public name lookup from Wikidata and Wikipedia

## Confirmation policy

- Expanded aliases never enter final query generation automatically.
- The skill returns `needs_user_confirmation=true` when public or heuristic expansion adds candidates beyond the original input.
- Final query generation only uses:
  - the original input when no expansion exists
  - or the explicitly confirmed alias list

## Privacy rule

- Only entity names are used for public alias lookup.
- Full technical descriptions and disclosure excerpts must not be sent to public services for alias or translation enrichment.
