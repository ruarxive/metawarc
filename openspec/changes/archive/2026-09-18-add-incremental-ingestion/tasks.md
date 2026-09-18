## 1. Planning and State
- [x] 1.1 Define run manifest, action, revision, and checkpoint models
- [x] 1.2 Implement source-to-catalog comparison and conflict classification
- [x] 1.3 Add human and JSON dry-run plans
- [x] 1.4 Add single-writer workspace locking

## 2. Incremental Processing
- [x] 2.1 Add new sources while skipping unchanged registered sources
- [x] 2.2 Update changed sources under their stable archive IDs
- [x] 2.3 Report missing sources without deleting their catalog history
- [x] 2.4 Add explicit verified source-path rebind for moved archives
- [x] 2.5 Advance catalog revision only after atomic archive action commit

## 3. Resume and Cleanup
- [x] 3.1 Persist checkpoints at configured batch intervals
- [x] 3.2 Validate source fingerprint, reader version, and temporary sidecars
- [x] 3.3 Resume from the last verified safe point without duplicate rows
- [x] 3.4 Fall back safely when a checkpoint cannot be trusted
- [x] 3.5 Mark superseded sidecars retired and implement retention cleanup

## 4. Verification
- [x] 4.1 Test add/update/unchanged/missing/moved/conflict plans
- [x] 4.2 Test repeated incremental runs for idempotency
- [x] 4.3 Test interruption before batch, after batch, and during catalog commit
- [x] 4.4 Test source changes after checkpoint creation
- [x] 4.5 Test concurrent reader and rejected second-writer behavior
- [x] 4.6 Test cleanup never removes the last committed complete sidecar

