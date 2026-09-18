## MODIFIED Requirements

### Requirement: Stored metadata analysis
The system SHALL analyze current registered metadata sidecars for PDF, image,
OOXML, OLE, video, audio, and font records without reading source WARC payloads.

#### Scenario: User analyzes one metadata type
- **WHEN** the user requests stored metadata analysis for one supported type
- **THEN** the report reads only current registered sidecars for that type
  within the selected archive scope

### Requirement: Stored metadata type selection
The metadata analysis command SHALL accept repeatable selections from `pdfs`,
`images`, `ooxmldocs`, `oledocs`, `videos`, `audio`, and `fonts`, and SHALL
support `all` as an exclusive shorthand for every supported stored metadata
type.

#### Scenario: User selects all types
- **WHEN** the user selects `all`
- **THEN** the system analyzes every supported current metadata sidecar type in
  deterministic order

#### Scenario: User combines all with a specific type
- **WHEN** the user combines `all` with an explicit metadata type
- **THEN** the command rejects the ambiguous selection with an actionable error
