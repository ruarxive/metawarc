## ADDED Requirements

### Requirement: Phrase search
The record-query service SHALL expose a phrase-search method over
the `texts` sidecar through the existing `record-query` capability,
gated by the same allowlist and pagination discipline as the other
query paths.

#### Scenario: Phrase search hits the index
- **WHEN** a user runs `metawarc search <phrase>` with at least one
  matching record
- **THEN** the CLI prints each match's URL, archive, and a text
  snippet that includes the matched phrase

#### Scenario: Phrase search respects the page limit
- **WHEN** the user sets `--limit N`
- **THEN** at most `N` records are returned, never more; the limit
  is capped at the configured `ServerSettings.max_page`

#### Scenario: Empty phrase is rejected
- **WHEN** a user submits an empty phrase
- **THEN** the CLI exits with a usage error and no database query is
  executed