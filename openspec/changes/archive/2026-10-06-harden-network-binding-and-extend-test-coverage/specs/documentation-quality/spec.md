## ADDED Requirements

### Requirement: OpenSpec Purpose paragraphs
Every OpenSpec specification file under `openspec/specs/*/spec.md` SHALL
carry a non-placeholder Purpose paragraph that names the capability,
the surface it governs, and the user-visible behavior it covers.

#### Scenario: A spec carries the archived placeholder
- **WHEN** a reviewer inspects `openspec/specs/<capability>/spec.md`
- **THEN** the first paragraph after the `# <capability> Specification`
  header is a non-empty Purpose paragraph and does not start with the
  literal string `TBD`

### Requirement: Governance documentation
The repository SHALL provide a code of conduct, security policy,
contributor guide, and support document at the repository root or in
the docs site.

#### Scenario: A new contributor looks for project governance
- **WHEN** a contributor reviews the repository root or the docs site
  landing page
- **THEN** the code of conduct, security policy, contributor guide, and
  support document are all reachable from a single entry point