## 1. Capture resolution
- [x] 1.1 Add typed URL + timestamp capture selection to `QueryService` (closest, exact)
- [x] 1.2 Return archive path, offset, length, status, content type, and date for the chosen capture
- [x] 1.3 Add redirect target resolution from headers with a bounded hop limit
- [x] 1.4 Cover compressed and uncompressed WARC fixtures with closest-timestamp tests

## 2. Replay service and HTTP surface
- [x] 2.1 Implement `ReplayService` over query + `iter_payload` (no payload duplication)
- [x] 2.2 Mount `/replay/...` routes on the existing `metawarc serve` FastAPI app
- [x] 2.3 Serve `/replay/<timestamp>/…` and `/replay/<timestamp>id_/…` with inline Content-Type
- [x] 2.4 Reuse serve bind/auth/byte/time/concurrency limits (no separate server process)
- [x] 2.5 Emit Memento-style `Link` / `Memento-Datetime` headers where applicable
- [x] 2.6 Decide whether CLI exposes `metawarc replay` as a serve alias or docs-only routes

## 3. HTML/CSS rewriting (P1)
- [x] 3.1 Implement HTML attribute and CSS `url(...)` rewriting into the replay prefix
- [x] 3.2 Add optional minimal banner chrome for rewritten HTML only
- [x] 3.3 Leave script bodies unmodified; document JS fidelity limits
- [x] 3.4 Test multi-asset pages (HTML + CSS + image) load through rewritten URLs

## 4. CDXJ interop (P2; in first milestone)
- [x] 4.1 Export CDXJ from active record sidecars and catalog archive paths
- [x] 4.2 Optionally emit a path index mapping WARC filenames to absolute sources
- [x] 4.3 Document how to point external pywb at the export + original WARCs
- [x] 4.4 Defer `metawarc[replay-pywb]` bridge to a later change (CDXJ is the contract)
- [x] 4.5 Decide CLI-only CDXJ export vs also exposing a REST export endpoint

## 5. Packaging, docs, and gates
- [x] 5.1 Add `metawarc[replay]` optional extra without changing core dependencies
- [x] 5.2 Document replay CLI, URL scheme, security warnings, and pywb escape hatch
- [x] 5.3 Add integration tests for resolution, redirects, rewrite, and export
- [x] 5.4 Update roadmap to list `add-website-replay` and keep F4.10 separate
