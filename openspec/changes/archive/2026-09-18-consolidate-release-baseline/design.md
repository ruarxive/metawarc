## Context

The repository has two materially different product states. Rewriting either
branch would obscure history, while developing new work on `master` would
duplicate fixes and interfaces already present on `testing`.

## Goals / Non-Goals

- Goals:
  - preserve existing commit history while producing one reviewable baseline;
  - make package metadata, documentation, CI, and tags agree;
  - keep the core WARC CLI install smaller than optional server installs;
  - document how existing indexes are handled during consolidation.
- Non-Goals:
  - redesign the DuckDB/Parquet schema in this change;
  - implement the security and scalability roadmap changes;
  - delete user-created workspace files or generated archive data.

## Decisions

### Decision: Integrate through a reviewed branch change

Use the `testing` history as the candidate implementation base and reconcile it
with `master` through a normal reviewable integration branch. Do not squash away
the feature history or force-update published tags.

### Decision: Use PEP 517 project metadata as the source of truth

`pyproject.toml` owns the version source, supported Python range, dependencies,
entry point, package data, and optional extras. Compatibility shims such as a
minimal `setup.py` may remain only when a documented consumer requires them.

### Decision: Split dependency groups by interface

The default install contains indexing, querying, extraction, and CLI packages.
FastAPI/Uvicorn belong to an `api` extra, FastMCP belongs to an `mcp` extra, and
an `all` extra composes both.

## Risks / Trade-offs

- Existing consumers may depend on legacy setup commands. Mitigation: build and
  install wheel/sdist artifacts in clean environments before removing shims.
- Index schema ambiguity can surprise users after upgrade. Mitigation: publish a
  compatibility table and make unsupported schemas fail with an actionable
  migrate/rebuild message.
- Integrating a large branch can hide regressions. Mitigation: require the
  quality-gate fixture suite before changing the default branch.

## Migration Plan

1. Create an integration branch from the newer candidate history.
2. Reconcile package metadata and dependency groups without publishing.
3. Run clean installation and critical CLI/API tests.
4. Document index versions supported, migrated, rebuilt, or rejected.
5. Review the complete default-branch delta.
6. Promote the reviewed commit, then create the changelog entry and release tag.

Rollback retains the previous default-branch reference and published artifacts;
no existing tag is moved.

## Open Questions

- Which Python versions will be declared supported for the stabilization release?
- Does any downstream automation still require direct `setup.py` commands?
- Should the first consolidated release retain version 1.3.x or increment to the
  next minor version because the branch baseline changes materially?

