## MODIFIED Requirements

### Requirement: Batch jobs share remote safety defaults
When batch jobs are exposed over REST, they SHALL mount on the existing
`metawarc serve` application, bind to loopback by default, require
authentication or explicit insecure acknowledgement for non-loopback
binds, and enforce the same concurrency, time, and payload-byte limits
as other remote payload operations. Job state, persistence, and
supported job kinds SHALL be defined by the `remote-batch-job`
capability spec.

#### Scenario: Batch job route requires authentication on a non-loopback bind
- **WHEN** the server is started with `--token` and a client calls
  `POST /jobs` without an `Authorization` header
- **THEN** the route returns 401 with the documented error envelope

#### Scenario: Batch job route inherits the request timeout
- **WHEN** a job handler runs longer than
  `ServerSettings.request_timeout_seconds`
- **THEN** the runner marks the job `failed`, the route returns
  the documented timeout code, and the worker is released