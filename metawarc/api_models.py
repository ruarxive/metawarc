"""Pydantic response contracts for the optional REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


__all__ = [
    "ArchiveResponse",
    "ErrorResponse",
    "HeaderResponse",
    "HealthResponse",
    "MessageResponse",
    "RecordPage",
    "RecordResponse",
]
