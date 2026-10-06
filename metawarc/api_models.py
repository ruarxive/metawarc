"""Pydantic response contracts for the optional REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .jobs import EXPORT_FORMATS, EXPORT_HARD_LIMIT


class ErrorResponse(BaseModel):
    detail: str
    trace_id: str | None = None


class ArchiveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    source_uri: str
    source_path: str
    filename: str
    size: int
    status: str
    num_records: int


class RecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    archive_id: str
    warc_id: str
    url: str
    source: str
    offset: int
    length: int


class RecordPage(BaseModel):
    total: int
    offset: int
    limit: int
    revision: int
    items: list[RecordResponse]


class HeaderResponse(BaseModel):
    key: str
    value: str


class HealthResponse(BaseModel):
    status: str
    schema_version: int
    revision: int


class MessageResponse(BaseModel):
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    archive_id: str
    warc_id: str
    source: str
    url: str
    snippet: str


class SearchResponse(BaseModel):
    phrase: str
    limit: int
    total: int
    hits: list[SearchHit]


class JobRequest(BaseModel):
    """Submit a new job. Only ``export-records`` is registered for the MVP."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Job kind name (`export-records`).")
    format: str | None = Field(default=None, description="Export format.")
    limit: int | None = Field(default=None, ge=1, le=EXPORT_HARD_LIMIT)
    filters: dict[str, Any] = Field(default_factory=dict)

    def job_input(self) -> dict[str, Any]:
        if self.kind == "export-records":
            if self.format is not None and self.format not in EXPORT_FORMATS:
                raise ValueError(
                    f"Unsupported export format {self.format!r}; "
                    f"choose from {', '.join(EXPORT_FORMATS)}"
                )
            return {
                "format": self.format or "json",
                "limit": self.limit,
                "filters": self.filters,
            }
        raise ValueError(f"Unsupported job kind {self.kind!r}")


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None


class JobListResponse(BaseModel):
    total: int
    items: list[JobResponse]


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    path: str
    format: str
    rows: int
    size: int


__all__ = [
    "ArchiveResponse",
    "ErrorResponse",
    "HeaderResponse",
    "HealthResponse",
    "JobListResponse",
    "JobRequest",
    "JobResponse",
    "JobResultResponse",
    "MessageResponse",
    "RecordPage",
    "RecordResponse",
    "SearchHit",
    "SearchResponse",
]
