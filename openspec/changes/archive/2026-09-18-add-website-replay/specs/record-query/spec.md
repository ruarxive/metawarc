## ADDED Requirements

### Requirement: Timestamp-aware record lookup
The typed query service SHALL support selecting a single response record by
exact URL combined with a closest or exact timestamp policy.

#### Scenario: Closest capture query
- **WHEN** `QueryService` is asked for an exact URL with timestamp policy
  `closest` and a target datetime
- **THEN** it returns at most one matching response row ordered by minimum
  absolute distance of `rec_date` to the target

#### Scenario: Deterministic tie-break
- **WHEN** two captures share the same absolute distance to the target timestamp
- **THEN** the service applies a documented deterministic tie-break
  (prefer earlier `rec_date`, then lower `archive_id`, then lower `offset`)
