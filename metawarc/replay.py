"""Website replay over the workspace catalog with optional CDXJ export."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

from lxml import etree
from lxml import html as lxml_html

from .cmds.dump import iter_payload
from .errors import MetawarcError, QueryValidationError
from .query import QueryService, RecordQuery, _coerce_timestamp
from .workspace import Workspace, canonical_path

ReplayMode = Literal["", "id_", "mp_"]

STAMP_RE = re.compile(r"^(?P<ts>\d{14})(?P<mod>id_|mp_)?$")
CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.IGNORECASE)
META_CHARSET_RE = re.compile(
    rb"""<meta\b[^>]*?\bcharset\s*=\s*['"]?\s*([a-zA-Z0-9._-]+)""",
    re.IGNORECASE,
)
META_CONTENT_TYPE_RE = re.compile(
    rb"""<meta\b[^>]*?\bcontent\s*=\s*['"][^'"]*?\bcharset\s*=\s*([a-zA-Z0-9._-]+)""",
    re.IGNORECASE,
)
CONTENT_TYPE_CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?\s*([a-zA-Z0-9._-]+)", re.I)
HTML_ATTRS = ("href", "src", "action", "poster", "data", "cite", "formaction")
DEFAULT_REDIRECT_HOPS = 5
DEFAULT_SITE_LIMIT = 500
CHARSET_ALIASES = {
    "utf8": "utf-8",
    "utf-8": "utf-8",
    "cp1251": "cp1251",
    "windows-1251": "cp1251",
    "win-1251": "cp1251",
    "win1251": "cp1251",
    "koi8-r": "koi8-r",
    "koi8r": "koi8-r",
    "latin1": "latin-1",
    "iso-8859-1": "latin-1",
    "ascii": "ascii",
}
BANNER_HTML = (
    '<div id="metawarc-replay-banner" style="all:initial;display:block;'
    "position:sticky;top:0;z-index:2147483647;background:#111;color:#f5f5f5;"
    "font:14px/1.4 ui-sans-serif,system-ui,sans-serif;padding:8px 12px;"
    'border-bottom:1px solid #333;">'
    '<a href="/" style="all:unset;color:#9cf;text-decoration:underline;cursor:pointer;'
    'font-weight:700;margin-right:12px;">metawarc</a>'
    "<strong style='all:unset;font-weight:700;color:#f5f5f5;'>replay</strong>"
    " — archived page; scripts are not rewritten and may be hostile. "
    '<a id="metawarc-replay-banner-url" href="{original}" '
    'style="all:unset;color:#9cf;text-decoration:underline;cursor:pointer;">{original}</a>'
    "</div>"
)


class ReplayError(MetawarcError):
    """Raised when replay cannot resolve or serve a capture."""


@dataclass(frozen=True)
class ReplayStamp:
    timestamp: datetime
    mode: ReplayMode
    raw: str

    @property
    def wayback(self) -> str:
        return self.timestamp.astimezone(UTC).strftime("%Y%m%d%H%M%S")

    @property
    def token(self) -> str:
        return f"{self.wayback}{self.mode}"


def parse_replay_stamp(value: str) -> ReplayStamp:
    """Parse a Wayback-style timestamp token with optional id_/mp_ modifier."""
    match = STAMP_RE.fullmatch(value.strip())
    if not match:
        raise QueryValidationError(
            "replay stamp must be YYYYMMDDHHMMSS with optional id_ or mp_ suffix"
        )
    mode = match.group("mod") or ""
    return ReplayStamp(timestamp=_coerce_timestamp(match.group("ts")), mode=mode, raw=value)


def format_memento_datetime(value: datetime | str) -> str:
    stamp = value if isinstance(value, datetime) else _coerce_timestamp(value)
    return stamp.astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


def wayback_timestamp(value: datetime | str) -> str:
    stamp = value if isinstance(value, datetime) else _coerce_timestamp(value)
    return stamp.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def surt_key(url: str) -> str:
    """Return a minimal SURT-like URL key for CDXJ export."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    labels = ",".join(reversed([label for label in host.split(".") if label]))
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"{labels}){path}{query}"


def replay_url(stamp: str | ReplayStamp, url: str, *, mode: ReplayMode | None = None) -> str:
    """Build a local replay path for an absolute target URL."""
    if isinstance(stamp, ReplayStamp):
        token = stamp.token if mode is None else f"{stamp.wayback}{mode}"
    elif mode is None:
        token = stamp
    else:
        parsed = parse_replay_stamp(stamp)
        token = f"{parsed.wayback}{mode}"
    return f"/replay/{token}/{url}"


def header_value(headers: Sequence[dict[str, Any]], name: str) -> str | None:
    wanted = name.lower()
    for item in headers:
        if str(item.get("key", "")).lower() == wanted:
            value = item.get("value")
            return None if value is None else str(value)
    return None


def is_html_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.split(";", 1)[0].strip().lower() in {"text/html", "application/xhtml+xml"}


def is_css_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.split(";", 1)[0].strip().lower() == "text/css"


def normalize_charset(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().strip("\"'").lower()
    if not key:
        return None
    return CHARSET_ALIASES.get(key, key)


def charset_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    match = CONTENT_TYPE_CHARSET_RE.search(content_type)
    return normalize_charset(match.group(1) if match else None)


def charset_from_meta(payload: bytes) -> str | None:
    head = payload[:8192]
    for pattern in (META_CHARSET_RE, META_CONTENT_TYPE_RE):
        match = pattern.search(head)
        if match:
            return normalize_charset(match.group(1).decode("ascii", errors="ignore"))
    return None


def detect_text_charset(payload: bytes, content_type: str | None = None) -> str:
    """Detect a decode charset for HTML/CSS payloads.

    Prefer Content-Type, then HTML meta, then UTF-8. Fall back to cp1251 when
    UTF-8 is invalid (common for older Russian sites).
    """
    for candidate in (
        charset_from_content_type(content_type),
        charset_from_meta(payload),
        "utf-8",
    ):
        if not candidate:
            continue
        try:
            payload.decode(candidate)
            return candidate
        except (LookupError, UnicodeDecodeError):
            continue
    for candidate in ("cp1251", "koi8-r", "latin-1"):
        try:
            payload.decode(candidate)
            return candidate
        except (LookupError, UnicodeDecodeError):
            continue
    return "utf-8"


def decode_text_payload(payload: bytes, content_type: str | None = None) -> tuple[str, str]:
    charset = detect_text_charset(payload, content_type)
    try:
        return payload.decode(charset), charset
    except UnicodeDecodeError:
        return payload.decode(charset, errors="replace"), charset


def ensure_html_utf8_meta(document: Any) -> None:
    """Force a UTF-8 charset declaration after we re-serialize as UTF-8."""
    head = document.find("head")
    if head is None:
        head = etree.Element("head")
        document.insert(0, head)
    for meta in list(head.findall("meta")):
        http_equiv = (meta.get("http-equiv") or "").lower()
        content = meta.get("content") or ""
        if meta.get("charset") is not None:
            meta.set("charset", "utf-8")
            continue
        if http_equiv == "content-type" and "charset=" in content.lower():
            meta.set("content", "text/html; charset=utf-8")
    if head.find("meta[@charset]") is None:
        meta = etree.Element("meta")
        meta.set("charset", "utf-8")
        head.insert(0, meta)


def should_rewrite(mode: ReplayMode, content_type: str | None) -> bool:
    if mode == "id_":
        return False
    return is_html_type(content_type) or is_css_type(content_type)


def _rewrite_absolute(page_url: str, value: str, stamp_token: str) -> str | None:
    raw = value.strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "data:", "javascript:", "blob:")):
        return None
    absolute = urljoin(page_url, raw)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None
    return replay_url(stamp_token, absolute)


def rewrite_css(text: str, page_url: str, stamp_token: str) -> str:
    def replace(match: re.Match[str]) -> str:
        quote, target = match.group(1), match.group(2)
        rewritten = _rewrite_absolute(page_url, target, stamp_token)
        if rewritten is None:
            return match.group(0)
        return f"url({quote}{rewritten}{quote})"

    return CSS_URL_RE.sub(replace, text)


def rewrite_html(
    payload: bytes,
    page_url: str,
    stamp_token: str,
    *,
    banner: bool = True,
    content_type: str | None = None,
) -> bytes:
    text, _charset = decode_text_payload(payload, content_type)
    try:
        document = lxml_html.document_fromstring(text)
    except Exception:
        return rewrite_css(text, page_url, stamp_token).encode("utf-8")

    for element in document.iter():
        tag = (element.tag or "").lower() if isinstance(element.tag, str) else ""
        if tag == "script":
            continue
        for attr in HTML_ATTRS:
            value = element.get(attr)
            if value is None:
                continue
            rewritten = _rewrite_absolute(page_url, value, stamp_token)
            if rewritten is not None:
                element.set(attr, rewritten)
        srcset = element.get("srcset")
        if srcset:
            parts = []
            for item in srcset.split(","):
                chunk = item.strip()
                if not chunk:
                    continue
                pieces = chunk.split(None, 1)
                rewritten = _rewrite_absolute(page_url, pieces[0], stamp_token)
                if rewritten is None:
                    parts.append(chunk)
                elif len(pieces) == 1:
                    parts.append(rewritten)
                else:
                    parts.append(f"{rewritten} {pieces[1]}")
            element.set("srcset", ", ".join(parts))
        style = element.get("style")
        if style:
            element.set("style", rewrite_css(style, page_url, stamp_token))
        if tag == "style" and element.text:
            element.text = rewrite_css(element.text, page_url, stamp_token)
        if tag in {"link", "script", "iframe"} and element.get("integrity"):
            del element.attrib["integrity"]

    ensure_html_utf8_meta(document)
    body = document.find("body")
    if banner and body is not None:
        banner_node = lxml_html.fragment_fromstring(
            BANNER_HTML.format(original=escape(page_url, quote=True)),
            create_parent=False,
        )
        body.insert(0, banner_node)

    return lxml_html.tostring(document, method="html", encoding="utf-8", doctype="<!DOCTYPE html>")


def read_payload(record: dict[str, Any], *, max_bytes: int | None = None) -> bytes:
    return b"".join(iter_payload(record, max_bytes=max_bytes))


def render_home_page(
    sites: Sequence[dict[str, Any]],
    *,
    revision: int | None = None,
) -> bytes:
    """Render a simple HTML index of archived hosts with replay links."""
    rows: list[str] = []
    for site in sites:
        stamp = wayback_timestamp(site["last_date"])
        href = escape(replay_url(f"{stamp}mp_", site["entry_url"]), quote=True)
        host = escape(str(site["host"]))
        entry = escape(str(site["entry_url"]))
        first = escape(wayback_timestamp(site["first_date"]))
        last = escape(stamp)
        count = int(site["captures"])
        rows.append(
            "<tr>"
            f'<td><a href="{href}">{host}</a></td>'
            f"<td><code>{entry}</code></td>"
            f"<td>{count}</td>"
            f"<td><time>{first}</time> – <time>{last}</time></td>"
            f'<td><a href="{href}">Open</a></td>'
            "</tr>"
        )
    body_rows = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="5">No archived websites found in this workspace.</td></tr>'
    )
    revision_line = (
        f"<p class='meta'>Catalog revision {int(revision)}</p>" if revision is not None else ""
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>metawarc replay</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      margin: 0;
      font: 16px/1.5 "IBM Plex Sans", "Segoe UI", sans-serif;
      color: #1a1a1a;
      background:
        radial-gradient(circle at top left, #e8f1ff 0, transparent 40%),
        linear-gradient(180deg, #f7f7f4 0%, #eceae4 100%);
      min-height: 100vh;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      padding: 48px 24px 64px;
    }}
    h1 {{
      font: 700 2.4rem/1.1 "IBM Plex Serif", Georgia, serif;
      margin: 0 0 8px;
      letter-spacing: -0.02em;
    }}
    .lede {{ margin: 0 0 28px; color: #444; max-width: 42rem; }}
    .meta {{ color: #666; font-size: 0.9rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: rgba(255,255,255,0.72);
      backdrop-filter: blur(6px);
    }}
    th, td {{
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid #d8d5ce;
      vertical-align: top;
    }}
    th {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #555;
    }}
    a {{ color: #0b57d0; }}
    code {{ font: 0.85rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
</head>
<body>
  <main>
    <h1>metawarc</h1>
    <p class="lede">Browse archived websites in this workspace. Each link opens the
    latest capture for a preferred entry URL (site root when available).</p>
    {revision_line}
    <table>
      <thead>
        <tr>
          <th>Host</th>
          <th>Entry URL</th>
          <th>Captures</th>
          <th>Date range</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""
    return html.encode("utf-8")


class ReplayService:
    """Resolve captures and prepare replay HTTP responses."""

    def __init__(
        self,
        workspace: Workspace,
        *,
        max_payload_bytes: int = 128 * 1024 * 1024,
        redirect_hops: int = DEFAULT_REDIRECT_HOPS,
    ) -> None:
        self.workspace = workspace
        self.query = QueryService(workspace)
        self.max_payload_bytes = max_payload_bytes
        self.redirect_hops = redirect_hops

    def list_sites(
        self,
        *,
        limit: int = DEFAULT_SITE_LIMIT,
        archive_ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List archived hosts with a preferred entry URL and capture stats."""
        if limit < 1 or limit > 10_000:
            raise QueryValidationError("site limit must be between 1 and 10000")
        paths = self.query._paths(archive_ids)
        if not paths:
            return []
        cursor = self.workspace.con.execute(
            """
            WITH records AS (
              SELECT host, url, c_type, status_code, rec_date
              FROM read_parquet(?)
              WHERE host IS NOT NULL AND host != ''
            ),
            ranked AS (
              SELECT
                host,
                url,
                rec_date,
                COUNT(*) OVER (PARTITION BY host) AS captures,
                MIN(rec_date) OVER (PARTITION BY host) AS first_date,
                MAX(rec_date) OVER (PARTITION BY host) AS last_date,
                ROW_NUMBER() OVER (
                  PARTITION BY host
                  ORDER BY
                    CASE
                      WHEN status_code BETWEEN 200 AND 299
                        AND url IN (
                          'https://' || host || '/',
                          'https://' || host
                        ) THEN 0
                      WHEN status_code BETWEEN 200 AND 299
                        AND url IN (
                          'http://' || host || '/',
                          'http://' || host
                        ) THEN 1
                      WHEN status_code BETWEEN 200 AND 299
                        AND (
                          url LIKE 'https://' || host || '/index.html'
                          OR url LIKE 'http://' || host || '/index.html'
                          OR url LIKE 'https://' || host || '/index.htm'
                          OR url LIKE 'http://' || host || '/index.htm'
                        ) THEN 2
                      WHEN status_code BETWEEN 200 AND 299 AND c_type = 'text/html' THEN 3
                      WHEN status_code BETWEEN 200 AND 299 THEN 4
                      ELSE 5
                    END,
                    length(url),
                    url,
                    rec_date DESC
                ) AS entry_rank
              FROM records
            )
            SELECT host, url AS entry_url, rec_date AS entry_date,
                   captures, first_date, last_date
            FROM ranked
            WHERE entry_rank = 1
            ORDER BY host ASC
            LIMIT ?
            """,
            [paths, limit],
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def home_page(self, *, limit: int = DEFAULT_SITE_LIMIT) -> bytes:
        sites = self.list_sites(limit=limit)
        return render_home_page(sites, revision=self.workspace.revision())

    def find_capture(
        self,
        url: str,
        timestamp: datetime | str,
        *,
        policy: str = "closest",
    ) -> dict[str, Any]:
        record = self.query.find_capture(url, timestamp, policy=policy)
        if record is None:
            raise ReplayError(f"No capture found for {url}")
        return record

    def location_for(self, record: dict[str, Any]) -> str | None:
        headers = self.query.get_headers(record["archive_id"], record["warc_id"])
        location = header_value(headers, "Location")
        if not location:
            return None
        return urljoin(record["url"], location.strip())

    def follow_redirects(
        self,
        record: dict[str, Any],
        timestamp: datetime | str,
        *,
        policy: str = "closest",
        max_hops: int | None = None,
    ) -> dict[str, Any]:
        hops = self.redirect_hops if max_hops is None else max_hops
        current = record
        seen: set[tuple[str, str]] = set()
        for _ in range(hops + 1):
            status = int(current.get("status_code") or 0)
            if status < 300 or status >= 400:
                return current
            key = (current["archive_id"], current["warc_id"])
            if key in seen:
                raise ReplayError("Redirect loop detected while resolving capture")
            seen.add(key)
            location = self.location_for(current)
            if not location:
                return current
            current = self.find_capture(location, timestamp, policy=policy)
        raise ReplayError(f"Redirect hop limit of {hops} exceeded")

    def prepare(
        self,
        url: str,
        stamp: str | ReplayStamp,
        *,
        policy: str = "closest",
    ) -> dict[str, Any]:
        parsed = stamp if isinstance(stamp, ReplayStamp) else parse_replay_stamp(stamp)
        record = self.find_capture(url, parsed.timestamp, policy=policy)
        status = int(record.get("status_code") or 200)
        headers: dict[str, str] = {
            "Memento-Datetime": format_memento_datetime(record["rec_date"]),
            "Link": (
                f'<{record["url"]}>; rel="original", '
                f'<{replay_url(parsed, record["url"], mode="id_")}>; rel="identity"'
            ),
            "X-Archive-Src": str(Path(record["source"]).name),
            "X-Archive-Offset": str(record["offset"]),
        }
        content_type = record.get("content_type") or "application/octet-stream"
        location = None
        body: bytes | None = None

        if 300 <= status < 400:
            target = self.location_for(record)
            if target:
                location = replay_url(parsed, target, mode=parsed.mode or "mp_")
                headers["Location"] = location
                body = b""
        elif should_rewrite(parsed.mode, content_type):
            payload = read_payload(record, max_bytes=self.max_payload_bytes)
            stamp_token = f"{parsed.wayback}{parsed.mode or 'mp_'}"
            if is_css_type(content_type):
                text, _charset = decode_text_payload(payload, content_type)
                body = rewrite_css(text, record["url"], stamp_token).encode("utf-8")
                content_type = "text/css; charset=utf-8"
            else:
                body = rewrite_html(
                    payload,
                    record["url"],
                    stamp_token,
                    banner=True,
                    content_type=content_type,
                )
                content_type = "text/html; charset=utf-8"
        else:
            body = None

        return {
            "record": record,
            "status_code": status if status > 0 else 200,
            "content_type": content_type,
            "headers": headers,
            "location": location,
            "body": body,
            "stream": body is None,
            "stamp": parsed,
        }

    def iter_body(self, prepared: dict[str, Any]) -> Iterator[bytes]:
        if prepared["body"] is not None:
            yield prepared["body"]
            return
        yield from iter_payload(prepared["record"], max_bytes=self.max_payload_bytes)


def export_cdxj(
    workspace: Workspace,
    output: Path | str,
    *,
    path_index: Path | str | None = None,
    archive_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Export CDXJ (and optional path index) from active record sidecars."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    query = QueryService(workspace)
    count = 0
    sources: dict[str, str] = {}
    page = RecordQuery.from_values(archive_ids=archive_ids, limit=1)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in query.iter_records(page, export_limit=10**9):
            source = canonical_path(record["source"])
            filename = source.name
            sources[filename] = str(source)
            fields = {
                "url": record["url"],
                "mime": record.get("c_type") or "",
                "status": str(record.get("status_code") or ""),
                "digest": record.get("payload_digest") or "",
                "length": str(record.get("length") or ""),
                "offset": str(record.get("offset") or ""),
                "filename": filename,
            }
            timestamp = wayback_timestamp(record["rec_date"])
            handle.write(
                f"{surt_key(record['url'])} {timestamp} "
                f"{json.dumps(fields, separators=(',', ':'))}\n"
            )
            count += 1

    path_index_written = None
    if path_index is not None:
        path_index_path = Path(path_index)
        path_index_path.parent.mkdir(parents=True, exist_ok=True)
        with path_index_path.open("w", encoding="utf-8") as handle:
            for filename, source in sorted(sources.items()):
                handle.write(f"{filename}\t{source}\n")
        path_index_written = str(path_index_path)

    return {
        "records": count,
        "cdxj": str(output_path),
        "path_index": path_index_written,
        "sources": len(sources),
        "revision": workspace.revision(),
    }


__all__ = [
    "DEFAULT_REDIRECT_HOPS",
    "DEFAULT_SITE_LIMIT",
    "ReplayError",
    "ReplayMode",
    "ReplayService",
    "ReplayStamp",
    "decode_text_payload",
    "detect_text_charset",
    "export_cdxj",
    "format_memento_datetime",
    "parse_replay_stamp",
    "render_home_page",
    "replay_url",
    "rewrite_css",
    "rewrite_html",
    "surt_key",
    "wayback_timestamp",
]
