## Context

Metawarc already stores response records with exact URL, `rec_date`, status,
content type, headers, and WARC byte offsets, and can stream payloads via
`QueryService` + `iter_payload`. It does not provide closest-timestamp
selection, CDX/CDXJ, URL rewriting, or a browser replay surface. The REST
payload endpoint forces `Content-Disposition: attachment`.

Two realistic approaches exist:

1. **Adopt pywb** as the replay UI/engine and point it at metawarc WARCs.
2. **Implement replay in metawarc** on the DuckDB workspace.
3. **Hybrid**: native replay for common local use; pywb interoperability for
   full-fidelity JS rewriting.

This change selects the hybrid path.

## Goals / Non-Goals

- Goals:
  - let a user open `metawarc replay` against a workspace and browse archived
    pages locally;
  - keep the workspace catalog as the authoritative capture index;
  - support Memento-style URL + timestamp resolution;
  - rewrite HTML/CSS resource URLs enough for typical static and lightly
    linked pages to load from the same collection;
  - export CDXJ so pywb (or other CDX consumers) can replay the same WARCs;
  - preserve existing security defaults (loopback, auth, byte/time/concurrency
    limits);
  - keep core install free of replay/pywb dependencies.
- Non-Goals:
  - replace pywb as a general-purpose Wayback product;
  - ship full Wombat/JS rewriting in v1;
  - build the F4.10 read-only exploration dashboard;
  - live web proxying, recording, or mutation of archives;
  - OutbackCDX as a required runtime;
  - multi-tenant hosted replay.

## Decisions

### Decision: Hybrid architecture — native replay core + pywb interop

**Primary path:** implement a thin native replay stack on `QueryService` and
payload streaming.

**Secondary path:** export CDXJ (and optional path index) from the workspace,
plus an optional `metawarc[replay-pywb]` bridge that either:

- generates a pywb collection from exported CDXJ + WARC paths, or
- registers a custom pywb `BaseIndexSource` that queries DuckDB and fetches
  via metawarc's offset seek.

**Why not embed pywb as the only engine:**
- Metawarc's truth is DuckDB + Parquet, not directory CDX; forcing CDX as the
  live index duplicates identity, fingerprint, and revision semantics.
- pywb pulls a large stack (gevent/Wombat/config YAML) that conflicts with the
  "core CLI without API deps" and FastAPI adapter model.
- Security controls already live in metawarc's remote adapters; wrapping pywb
  as the public surface would fork bind/auth/limit policy.
- Most local research workflows need "open this URL near this date" more than
  full interactive JS fidelity.

**Why not pure from-scratch full fidelity:**
- Correct JS rewriting, service workers, and fuzzy matching are years of
  Webrecorder work. Reimplementing Wombat inside metawarc is out of scope.
- CDXJ export + optional pywb reuse that investment without abandoning the
  workspace catalog.

### Decision: Phased delivery

| Phase | Delivers | Fidelity |
|---|---|---|
| P0 | Resolve URL+time, serve inline payload, redirect hop, Memento headers | Raw capture body |
| P1 | HTML/CSS URL rewriter, replay URL scheme, optional banner chrome | Static / link-driven pages |
| P2 | CDXJ (+ path index) export; documented pywb consumption | Interop |
| P3 | Optional pywb bridge extra for JS/Wombat when needed | Full interactive |

**First shipped milestone (approved):** P0 + P1 + P2 together — exact-URL
closest-timestamp replay with HTML/CSS rewriting and CDXJ export. P3 remains
out of scope for this change.

Ship as `metawarc[replay]` on top of `metawarc[api]` (FastAPI/uvicorn already
covered, plus any rewriter-only deps). P3 may remain documentation-first if a
pywb pin is unstable.

### Decision: Replay resolves through QueryService, not a parallel index

Add typed capture-selection APIs for this change:

- exact URL + closest timestamp (default);
- exact timestamp match when present.

SURT / URL-key / prefix matching is explicitly deferred; exact-URL
closest-timestamp is enough for the first milestone.

Do not maintain a live CDX file as the operational index. CDXJ is an export
artifact derived from active record sidecars and catalog archive paths.
Revisit records remain out of scope until indexed; v1 uses response records
only (current indexer behavior).

### Decision: Mount replay under `metawarc serve`

Replay HTTP routes mount on the existing FastAPI app created by
`metawarc serve` / `create_app`, not a separate long-running process.
Share the same workspace handle, auth, bind host, and limit settings.
CLI may still expose `metawarc replay` as a thin alias that starts `serve`
with replay routes enabled, but there is one server implementation.

### Decision: Replay URL scheme and content serving

Use a Wayback-like local path under the serve app:

- `/replay/<timestamp>/<url>` — closest capture at or near timestamp
- `/replay/<timestamp>id_/<url>` — identity/raw mode (no HTML rewrite)
- `/replay/<timestamp>mp_/<url>` — rewritten mode (default for HTML)

Serve with the indexed `Content-Type`, not as an attachment. Apply
`max_payload_bytes` and request timeouts. Inject a minimal banner only in
rewritten HTML mode. Honor archived `Location` for 3xx by rewriting the
redirect target into the replay URL space (bounded hop count).

### Decision: Rewriter scope for v1

Rewrite in HTML and CSS only:

- `href`, `src`, `action`, `poster`, `srcset`, CSS `url(...)`
- absolute http(s) and protocol-relative URLs into the replay prefix
- leave `<script>` bodies untouched in v1 (document limitation)
- strip or neutralize `Integrity` / Service Worker registration attributes
  that break rewritten assets when safe to do so

Do not rewrite binary formats. Optional later: adopt Webrecorder's rewriter
packages if license/packaging fit; otherwise keep a small lxml/css-based
rewriter owned by metawarc.

### Decision: Security posture matches remote interfaces

Replay is read-only, local-first, and hostile-content aware:

- default bind `127.0.0.1`;
- non-loopback requires token or explicit insecure ack;
- no client-supplied filesystem paths;
- sandbox banner warning that archived JS may be malicious;
- Content-Security-Policy for banner chrome only; do not pretend CSP fully
  contains archived scripts in raw/id mode;
- same page/byte/time/concurrency limits as the API.

### Decision: Packaging

- `metawarc[replay]` depends on `metawarc[api]` plus any rewriter-only deps.
- Core `get`/`dump`/`query` remain available without replay.
- `metawarc[replay-pywb]` is optional and may pin a documented pywb version;
  if the pin is unstable, ship CDXJ export only and document external pywb.

## Architecture sketch

```text
Browser
  │
  ▼
Replay HTTP adapter (FastAPI routes or dedicated app)
  │  auth / limits / loopback
  ▼
ReplayService
  ├─ CaptureResolver  → QueryService (URL + timestamp policy)
  ├─ RedirectFollower → headers sidecar (Location, hop limit)
  ├─ PayloadSource    → dump.iter_payload (offset seek)
  └─ ContentRewriter  → HTML/CSS rewrite (mp_ mode)
  │
  ▼
Workspace catalog (DuckDB) + WARC sources

Side path:
ReplayService / CLI export → CDXJ (+ path index)
  └─ optional pywb collection or custom IndexSource
```

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| pywb-only | Mature rewriter, Wombat, calendar UI | Duplicate index model; heavy deps; auth/bind fork | Reject as primary |
| From-scratch full Wayback | Full control | JS rewrite cost; years of edge cases | Reject for v1 fidelity |
| CDXJ-only + external pywb | Minimal code | No first-class `metawarc replay`; poor UX | Accept as P2 interop only |
| Hybrid (chosen) | Fits workspace; useful local UX; escape hatch to pywb | Two surfaces to document; rewriter limited at first | Accept |

## Risks / Trade-offs

- Limited rewriter fidelity → many modern JS sites break. Mitigation: clear
  docs, `id_` raw mode, CDXJ/pywb path for hard cases.
- Closest-timestamp without SURT/URL canonicalization → misses near-duplicate
  URLs. Mitigation: start with exact URL; add SURT/keying in a follow-up.
- Serving archived HTML executes hostile scripts in the browser. Mitigation:
  loopback default, warning banner, prefer rewritten mode, document risk.
- pywb optional extra may be hard to pin. Mitigation: treat CDXJ export as the
  stable contract; bridge code can lag.
- Replay vs exploration UI confusion. Mitigation: keep F4.10 as a separate
  change; replay is page-centric, not a catalog dashboard.

## Migration Plan

1. Extend typed query with capture selection (no schema break).
2. Add `ReplayService` and CLI `replay` (loopback server).
3. Add rewrite modes and banner.
4. Add `export-cdxj` (or `replay export-cdxj`) from active sidecars.
5. Document external pywb usage; optionally add `replay-pywb` extra.
6. No workspace schema version bump required unless a dedicated URL-key
   sidecar is introduced later.

## Resolved decisions (2026-08-08)

- First shipped milestone includes P1 rewriting and CDXJ export (P0+P1+P2).
- Replay mounts under existing `metawarc serve` (shared app, auth, limits).
- Exact-URL closest-timestamp is sufficient; SURT/URL-key deferred.
- `metawarc replay` is a documented alias of `serve`.
- CDXJ export is CLI-only in this change (`export-cdxj`); no REST export endpoint.
- `metawarc[replay-pywb]` bridge remains deferred; CDXJ is the stable contract.

## Open Questions

- None for this milestone.
