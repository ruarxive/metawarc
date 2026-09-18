## ADDED Requirements

### Requirement: Tested command documentation
Documented CLI invocations SHALL be executed as documentation tests or covered
by equivalent command-contract tests.

#### Scenario: Option name changes
- **WHEN** a CLI option is renamed without updating an example
- **THEN** documentation verification fails

### Requirement: Accurate feature status
Documentation SHALL distinguish features on the canonical release branch from
proposed, experimental, optional, or branch-only features.

#### Scenario: API extra is not installed
- **WHEN** a core-only user reads server documentation
- **THEN** the documentation clearly identifies the required extra and secure
  startup defaults

### Requirement: Index format documentation
The project SHALL document workspace layout, catalog schema version, path
portability, compatibility, migration, rebuild, and repair behavior.

#### Scenario: User upgrades an old index
- **WHEN** a release changes the supported schema set
- **THEN** release notes link to exact migrate, rebuild, and rollback guidance

### Requirement: Contributor and security guidance
The repository SHALL provide contribution, security-reporting, threat-model, and
release-checklist documentation.

#### Scenario: Vulnerability is discovered
- **WHEN** a reporter looks for a private security contact and disclosure process
- **THEN** `SECURITY.md` provides current instructions without requiring a public
  issue
