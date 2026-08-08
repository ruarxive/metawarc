from __future__ import annotations

import csv
import io
import json
import time
import wave
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont
from pdfminer.pdfparser import PDFSyntaxError

from metawarc.analysis import (
    STORED_METADATA_TYPES,
    AnalysisService,
    normalize_url,
    resolve_stored_metadata_types,
    write_report,
)
from metawarc.cmds.extractor import (
    ExtractionLimitError,
    ExtractionLimits,
    ExtractorRegistry,
    FontExtractor,
    OoxmlExtractor,
    PdfExtractor,
    SvgExtractor,
    WebpExtractor,
    decode_pdf_metadata_text,
    extract_record,
    extraction_deadline,
    managed_payload_path,
    read_payload_limited,
)
from metawarc.workspace import Workspace


def ooxml_payload(xml: bytes | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr(
            "docProps/core.xml",
            xml
            or b'<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc"><dc:title>Example</dc:title></cp:coreProperties>',
        )
        archive.writestr("word/document.xml", b"<document/>")
    return output.getvalue()


def font_payload(flavor: str | None = None) -> bytes:
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder([".notdef"])
    builder.setupCharacterMap({})
    builder.setupGlyf({".notdef": TTGlyphPen(None).glyph()})
    builder.setupHorizontalMetrics({".notdef": (500, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable(
        {
            "familyName": "Example Sans",
            "styleName": "Regular",
            "fullName": "Example Sans Regular",
            "psName": "ExampleSans-Regular",
            "version": "Version 1.0",
            "uniqueFontIdentifier": "Example Sans Regular",
        }
    )
    builder.setupOS2()
    builder.setupPost()
    builder.setupMaxp()
    builder.font.flavor = flavor
    output = io.BytesIO()
    builder.save(output)
    return output.getvalue()


def eot_payload() -> bytes:
    header = bytearray(82)
    header[0:4] = (256).to_bytes(4, "little")
    header[4:8] = (128).to_bytes(4, "little")
    header[8:12] = (0x00020001).to_bytes(4, "little")
    header[28:32] = (400).to_bytes(4, "little")
    header[34:36] = b"LP"
    names = ("Example EOT", "Regular", "Version 1.0", "Example EOT Regular", "")
    for name in names:
        encoded = name.encode("utf-16le")
        header.extend(len(encoded).to_bytes(2, "little"))
        header.extend(encoded)
    return bytes(header)


def test_registry_uses_mime_extension_and_signature():
    registry = ExtractorRegistry()
    extractor, warnings = registry.select(
        mime="APPLICATION/PDF; charset=binary", filename="wrong.bin", prefix=b"%PDF-1.7"
    )
    assert extractor and extractor.detected_type == "pdfs"
    extractor, warnings = registry.select(
        mime="application/octet-stream", filename="report.pdf", prefix=b"%PDF-1.7"
    )
    assert extractor and extractor.detected_type == "pdfs"
    assert warnings
    extractor, warnings = registry.select(
        mime=None, filename="unknown", prefix=b"\x89PNG\r\n\x1a\n"
    )
    assert extractor and extractor.detected_type == "images"
    extractor, warnings = registry.select(
        mime="application/pdf", filename="conflict.docx", prefix=b"%PDF-1.7"
    )
    assert extractor and extractor.detected_type == "pdfs"
    assert "conflicts" in warnings[0]


def test_expanded_format_registry_and_extractors():
    registry = ExtractorRegistry()
    cases = (
        ("application/octet-stream", "slides.ppsx", b"PK\x03\x04", "ooxmldocs"),
        ("image/gif", "image.gif", b"GIF89a", "images"),
        ("image/svg+xml", "image.svg", b"<svg/>", "images"),
        ("audio/x-mp3", "audio.mp3", b"ID3\x04\x00", "audio"),
        ("video/mp4", "video.mp4", b"\x00\x00\x00\x18ftypisom", "videos"),
        ("font/woff2", "font.woff2", b"wOF2", "fonts"),
    )
    for mime, filename, prefix, expected in cases:
        extractor, _warnings = registry.select(mime=mime, filename=filename, prefix=prefix)
        assert extractor and extractor.detected_type == expected

    rejected, warnings = registry.select(
        mime="text/html",
        filename="image.gif",
        prefix=b"<html><title>Not an image</title></html>",
        expected_type="images",
    )
    assert rejected is None
    assert "refusing binary" in warnings[0]

    metadata = OoxmlExtractor().extract(ooxml_payload(), ExtractionLimits())
    assert metadata and metadata["title"] == "Example"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as invalid:
        invalid.writestr("docProps/core.xml", b"<core/>")
    with pytest.raises(ValueError, match="not an OOXML"):
        OoxmlExtractor().extract(archive.getvalue(), ExtractionLimits())

    svg = SvgExtractor().extract(
        (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="16" '
            b'viewBox="0 0 24 16"><title>Map</title><desc>Example</desc>'
            b'<use href="https://example.test/symbol"/></svg>'
        ),
        ExtractionLimits(),
    )
    assert svg and svg["Title"] == "Map"
    assert svg["Image width"] == "24"
    assert svg["External reference count"] == 1

    gif = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )
    gif_extractor, _warnings = registry.select(
        mime="image/gif", filename="image.gif", prefix=gif, expected_type="images"
    )
    assert (
        gif_extractor
        and gif_extractor.extract(gif, ExtractionLimits())["Image width"] == "1 pixels"
    )

    webp = (
        b"RIFF"
        + (22).to_bytes(4, "little")
        + b"WEBPVP8X"
        + (10).to_bytes(4, "little")
        + b"\0\0\0\0"
        + (639).to_bytes(3, "little")
        + (479).to_bytes(3, "little")
    )
    assert WebpExtractor().extract(webp, ExtractionLimits()) == {
        "MIME type": "image/webp",
        "Chunk type": "VP8X",
        "Image width": 640,
        "Image height": 480,
    }

    with wave.open(output := io.BytesIO(), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 800)
    wav = output.getvalue()
    audio_extractor, _warnings = registry.select(
        mime="audio/wav", filename="sample.wav", prefix=wav[:4096], expected_type="audio"
    )
    assert audio_extractor and audio_extractor.extract(wav, ExtractionLimits())

    assert FontExtractor().extract(font_payload(), ExtractionLimits())["Family"] == "Example Sans"
    assert FontExtractor().extract(font_payload("woff2"), ExtractionLimits())["Full name"] == (
        "Example Sans Regular"
    )
    collection = TTCollection()
    collection.fonts = [TTFont(io.BytesIO(font_payload()), lazy=True)]
    collection_output = io.BytesIO()
    collection.save(collection_output)
    collection.close()
    assert (
        FontExtractor().extract(collection_output.getvalue(), ExtractionLimits())[
            "Collection faces"
        ]
        == 1
    )
    assert FontExtractor().extract(eot_payload(), ExtractionLimits())["Family"] == "Example EOT"


def test_pdf_metadata_text_uses_pdf_encoding_rules(monkeypatch):
    cyrillic = "Привет, мир"
    utf16be = b"\xfe\xff" + cyrillic.encode("utf-16be")
    assert decode_pdf_metadata_text(utf16be) == cyrillic
    assert decode_pdf_metadata_text(b"R\xe9sum\xe9") == "Résumé"
    assert "\ufffd" not in decode_pdf_metadata_text(utf16be)

    class Document:
        info = [{"Title": utf16be, "Author": b"R\xe9sum\xe9"}]

    class Record:
        payload_length = 8

        def content_stream(self):
            return io.BytesIO(b"%PDF-1.4")

    monkeypatch.setattr("metawarc.cmds.extractor.PDFDocument", lambda parser: Document())
    envelope = extract_record(
        Record(),
        archive_id="archive",
        warc_id="record",
        url="https://example.test/document.pdf",
        filename="document.pdf",
        source="source.warc",
        mime="application/pdf",
    )
    assert envelope.metadata == {"Title": cyrillic, "Author": "Résumé"}
    assert envelope.normalized == {"title": cyrillic, "creator": "Résumé"}
    assert envelope.extractor_version == "2"


def test_ooxml_limits_and_external_entities():
    extractor = OoxmlExtractor()
    with pytest.raises(ExtractionLimitError):
        extractor.extract(ooxml_payload(), ExtractionLimits(max_zip_members=1))
    entity_xml = (
        b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]><core><title>&ext;</title></core>'
    )
    with pytest.raises(ExtractionLimitError):
        extractor.extract(ooxml_payload(entity_xml), ExtractionLimits())


def test_payload_timeout_corrupt_parser_and_temporary_cleanup():
    class OversizedRecord:
        payload_length = 100

        def content_stream(self):
            return io.BytesIO(b"x" * 100)

    with pytest.raises(ExtractionLimitError):
        read_payload_limited(OversizedRecord(), ExtractionLimits(max_payload_bytes=10))
    with pytest.raises(PDFSyntaxError):
        PdfExtractor().extract(b"%PDF-corrupt", ExtractionLimits())
    parent = None
    with (
        pytest.raises(RuntimeError),
        managed_payload_path(b"payload", "bin", ExtractionLimits()) as path,
    ):
        parent = path.parent
        raise RuntimeError("parser failed")
    assert parent is not None and not parent.exists()
    with pytest.raises(ExtractionLimitError), extraction_deadline(0.001):
        time.sleep(0.01)


def test_content_index_expanded_metadata_groups(warc_factory, tmp_path: Path):
    from metawarc.cmds.extractor import ContentIndexer
    from metawarc.cmds.indexer import Indexer

    with wave.open(output := io.BytesIO(), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 800)
    source = warc_factory(
        "expanded-formats.warc",
        [
            {
                "id": "<urn:uuid:slides>",
                "url": "https://example.test/slides.ppsx",
                "mime": "application/octet-stream",
                "payload": ooxml_payload(),
            },
            {
                "id": "<urn:uuid:svg>",
                "url": "https://example.test/icon.svg",
                "mime": "image/svg+xml",
                "payload": b'<svg xmlns="http://www.w3.org/2000/svg"><title>Icon</title></svg>',
            },
            {
                "id": "<urn:uuid:audio>",
                "url": "https://example.test/audio.wav",
                "mime": "audio/wav",
                "payload": output.getvalue(),
            },
            {
                "id": "<urn:uuid:font>",
                "url": "https://example.test/font.woff2",
                "mime": "font/woff2",
                "payload": font_payload("woff2"),
            },
        ],
    )
    database = tmp_path / "expanded.db"
    Indexer(batch_size=1).index_records([source], str(database), silent=True)
    indexer = ContentIndexer(batch_size=1)
    for metadata_type in ("ooxmldocs", "images", "audio", "fonts", "videos"):
        result = indexer.index_by_table_type(None, str(database), metadata_type, silent=True)
        assert result["processed"] == 1

    with Workspace(database, read_only=True, create=False) as workspace:
        assert workspace.active_sidecar_paths("ooxmldocs")
        assert workspace.active_sidecar_paths("images")
        assert workspace.active_sidecar_paths("audio")
        assert workspace.active_sidecar_paths("fonts")
        report = AnalysisService(workspace).stored_metadata(
            metadata_types=("audio", "fonts", "videos")
        )
    assert [(row["metadata_type"], row["rows"]) for row in report.data] == [
        ("audio", 1),
        ("fonts", 1),
        ("videos", 0),
    ]


def test_content_index_links_and_analysis_reports(indexed_workspace, tmp_path: Path):
    from metawarc.cmds.extractor import ContentIndexer

    database, _ = indexed_workspace
    result = ContentIndexer(batch_size=1).index_by_table_type(
        None, str(database), "links", rescan=True, silent=True
    )
    assert result["processed"] == 1
    with Workspace(database, create=False) as workspace:
        hashes = AnalysisService(workspace).hash_payloads(batch_size=1)
        assert not hashes.failures
        duplicate_report = AnalysisService(workspace).duplicates()
        assert duplicate_report.data == []
        link_report = AnalysisService(workspace).link_graph()
        summary = AnalysisService(workspace).summary(top=5)
        integrity = AnalysisService(workspace).integrity(deep=True, max_records=10)
        assert summary.catalog_revision == integrity.catalog_revision
        assert workspace.revision() == integrity.catalog_revision + 1
        assert summary.analysis_version
        assert link_report.data["hosts"][0]["sample_normalized"] == "https://example.test/about"
        assert not integrity.failures

    for output_format in ("json", "csv", "parquet"):
        output = tmp_path / f"summary.{output_format}"
        write_report(summary, output, output_format)
        assert output.stat().st_size > 0


def test_stored_metadata_analysis_types_rollups_filters_and_exports(warc_factory, tmp_path: Path):
    from metawarc.cmds.extractor import ContentIndexer
    from metawarc.cmds.indexer import Indexer

    def document(title: str, creator: str) -> bytes:
        return ooxml_payload(
            (
                '<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc">'
                f"<dc:title>{title}</dc:title><dc:creator>{creator}</dc:creator>"
                "</cp:coreProperties>"
            ).encode()
        )

    primary = warc_factory(
        "metadata-primary.warc",
        [
            {
                "id": "<urn:uuid:doc-one>",
                "url": "https://example.test/one.docx",
                "mime": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "payload": document("One", "Alice"),
            },
            {
                "id": "<urn:uuid:doc-two>",
                "url": "https://example.test/two.docx",
                "mime": "application/octet-stream",
                "payload": document("Two", "Alice"),
            },
            {
                "id": "<urn:uuid:bad-pdf>",
                "url": "https://example.test/bad.pdf",
                "mime": "application/pdf",
                "payload": b"%PDF-corrupt",
            },
        ],
    )
    secondary = warc_factory(
        "metadata-secondary.warc",
        [
            {
                "id": "<urn:uuid:doc-three>",
                "url": "https://example.test/three.docx",
                "mime": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "payload": document("Three", "Bob"),
            }
        ],
    )
    database = tmp_path / "metadata.db"
    Indexer(batch_size=1).index_records([primary, secondary], str(database), silent=True)
    indexer = ContentIndexer(batch_size=1)
    indexer.index_by_table_type(None, str(database), "ooxmldocs", silent=True)
    indexer.index_by_table_type(None, str(database), "pdfs", silent=True)

    with Workspace(database, read_only=True, create=False) as workspace:
        primary_id = workspace.find_archive_by_source(primary)["id"]
        report = AnalysisService(workspace).stored_metadata(
            metadata_types=("all",), archive_ids=[primary_id], top=1
        )
        ooxml_path = Path(workspace.active_sidecar_paths("ooxmldocs", [primary_id])[0])

    assert report.filters == {
        "archive_ids": [primary_id],
        "metadata_types": list(STORED_METADATA_TYPES),
    }
    assert [row["metadata_type"] for row in report.data] == list(STORED_METADATA_TYPES)
    by_type = {row["metadata_type"]: row for row in report.data}
    ooxml = by_type["ooxmldocs"]
    assert ooxml["status"] == "complete"
    assert ooxml["rows"] == ooxml["successes"] == 2
    assert ooxml["errors"] == 0
    assert ooxml["warning_rows"] == ooxml["warning_occurrences"] == 1
    assert ooxml["raw_metadata_rows"] == ooxml["normalized_metadata_rows"] == 2
    assert ooxml["bytes_inspected"] > 0
    assert ooxml["duration_ms"] >= 0
    assert ooxml["field_coverage"]["creator"] == {"rows": 2, "percent": 100.0}
    assert ooxml["top_values"]["creator"] == [{"value": "Alice", "count": 2}]
    assert by_type["pdfs"]["rows"] == by_type["pdfs"]["errors"] == 1
    assert by_type["images"]["status"] == by_type["oledocs"]["status"] == "not-indexed"
    assert not report.failures

    json_output = tmp_path / "metadata.json"
    csv_output = tmp_path / "metadata.csv"
    parquet_output = tmp_path / "metadata.parquet"
    write_report(report, json_output, "json")
    write_report(report, csv_output, "csv")
    write_report(report, parquet_output, "parquet")
    json_rows = json.loads(json_output.read_text())["data"]
    with csv_output.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    parquet_rows = pq.read_table(parquet_output).to_pylist()
    assert (
        [row["metadata_type"] for row in json_rows]
        == [row["metadata_type"] for row in csv_rows]
        == [row["metadata_type"] for row in parquet_rows]
    )
    ooxml_index = list(STORED_METADATA_TYPES).index("ooxmldocs")
    assert (
        json.loads(csv_rows[ooxml_index]["field_coverage"])["creator"]
        == json_rows[ooxml_index]["field_coverage"]["creator"]
    )
    assert (
        json.loads(parquet_rows[ooxml_index]["top_values"])["creator"]
        == json_rows[ooxml_index]["top_values"]["creator"]
    )

    table = pq.read_table(ooxml_path)
    normalized = table.column("normalized_json").to_pylist()
    normalized[0] = "{malformed"
    table = table.set_column(
        table.schema.get_field_index("normalized_json"),
        "normalized_json",
        pa.array(normalized, type=pa.string()),
    )
    pq.write_table(table, ooxml_path)
    with Workspace(database, read_only=True, create=False) as workspace:
        malformed_report = AnalysisService(workspace).stored_metadata(
            metadata_types=("ooxmldocs",), archive_ids=[primary_id], top=1
        )
    malformed = malformed_report.data[0]
    assert malformed["status"] == "partial"
    assert malformed["rows"] == 2
    assert malformed["normalized_metadata_rows"] == 1
    assert malformed["malformed_json_rows"] == 1
    assert malformed_report.to_dict()["failure_count"] == 1
    assert malformed_report.failures[0]["fields"] == ["normalized_json"]


def test_resolve_stored_metadata_types():
    assert resolve_stored_metadata_types() == STORED_METADATA_TYPES
    assert resolve_stored_metadata_types(("all", "all")) == STORED_METADATA_TYPES
    assert resolve_stored_metadata_types(("pdfs", "images", "pdfs")) == (
        "pdfs",
        "images",
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        resolve_stored_metadata_types(("all", "pdfs"))
    with pytest.raises(ValueError, match="must be one of"):
        resolve_stored_metadata_types(("links",))


@pytest.mark.parametrize(
    "base,target,expected",
    [
        ("HTTPS://Example.Test/a", "/b#frag", "https://example.test/b"),
        ("http://example.test:80/a", "b", "http://example.test/b"),
        ("https://example.test:8443/a", "?q=1", "https://example.test:8443/a?q=1"),
        ("https://münich.example/a", "/b", "https://xn--mnich-kva.example/b"),
    ],
)
def test_url_normalization(base: str, target: str, expected: str):
    assert normalize_url(base, target) == expected


def test_record_update_retires_hash_sidecar(indexed_workspace):
    database, source = indexed_workspace
    with Workspace(database, create=False) as workspace:
        AnalysisService(workspace).hash_payloads(batch_size=1)
        assert workspace.active_sidecars("hashes")
    from conftest import build_warc

    from metawarc.cmds.indexer import Indexer

    build_warc(source, [{"id": "<urn:uuid:new>", "payload": b"new"}])
    Indexer().index_records([source], str(database), mode="force", silent=True)
    with Workspace(database, read_only=True, create=False) as workspace:
        assert workspace.active_sidecars("hashes") == []


def test_link_graph_honors_base_tag(warc_factory, tmp_path: Path):
    from metawarc.cmds.extractor import ContentIndexer
    from metawarc.cmds.indexer import Indexer

    source = warc_factory(
        "base.warc",
        [
            {
                "id": "<urn:uuid:base>",
                "url": "https://example.test/original/page.html",
                "mime": "text/html",
                "payload": b'<html><base href="/assets/"><a href="manual#top">M</a></html>',
            }
        ],
    )
    database = tmp_path / "base.db"
    Indexer().index_records([source], str(database), silent=True)
    ContentIndexer().index_by_table_type(None, str(database), "links", silent=True)
    with Workspace(database, read_only=True, create=False) as workspace:
        report = AnalysisService(workspace).link_graph()
    edge = report.data["records"][0]
    assert edge["original_target"] == "manual#top"
    assert edge["normalized_target"] == "https://example.test/assets/manual"


def test_deep_integrity_resume_and_digest_observation(monkeypatch, warc_factory, tmp_path: Path):
    from metawarc.cmds.indexer import Indexer

    source = warc_factory(
        "digest.warc",
        [
            {
                "id": "<urn:uuid:digest>",
                "payload": b"digest payload",
                "warc_headers": {
                    "WARC-Payload-Digest": "sha1:0000000000000000000000000000000000000000"
                },
            },
            {"id": "<urn:uuid:after>", "payload": b"after"},
        ],
    )
    database = tmp_path / "digest.db"
    Indexer(batch_size=1).index_records([source], str(database), silent=True)
    with Workspace(database, read_only=True, create=False) as workspace:
        records_path = Path(workspace.active_sidecar_paths("records")[0])
    table = pq.read_table(records_path)
    digests = table.column("payload_digest").to_pylist()
    digests[0] = "sha1:0000000000000000000000000000000000000000"
    table = table.set_column(
        table.schema.get_field_index("payload_digest"),
        "payload_digest",
        pa.array(digests, type=pa.string()),
    )
    pq.write_table(table, records_path)
    original = Workspace.save_checkpoint
    calls = 0

    def interrupt_once(self, **kwargs):
        nonlocal calls
        original(self, **kwargs)
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(Workspace, "save_checkpoint", interrupt_once)
    with Workspace(database, create=False) as workspace, pytest.raises(KeyboardInterrupt):
        AnalysisService(workspace).integrity(deep=True, batch_size=1)
    monkeypatch.setattr(Workspace, "save_checkpoint", original)
    with Workspace(database, create=False) as workspace:
        report = AnalysisService(workspace).integrity(deep=True, batch_size=1, resume=True)
    assert len(report.data["records"]) == 2
    mismatch = next(item for item in report.data["records"] if item["warc_id"] == "urn:uuid:digest")
    assert mismatch["digest_status"] == "failed"
    assert mismatch["digest_expected"]
    assert mismatch["digest_observed"]
