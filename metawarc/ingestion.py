"""Incremental collection planning and orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .cmds.indexer import Indexer, IndexSummary
from .progress import ProgressCallback
from .workspace import SourceFingerprint, Workspace, canonical_path, utc_now


@dataclass
class IngestionAction:
    source: str
    action: str
    archive_id: str | None = None
    reason: str | None = None
    moved_from: str | None = None


@dataclass
class IngestionPlan:
    database: str
    created_at: str = field(default_factory=utc_now)
    revision: int = 0
    actions: list[IngestionAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "created_at": self.created_at,
            "revision": self.revision,
            "actions": [asdict(item) for item in self.actions],
        }


class IncrementalIngestor:
    """Plan changes before delegating safe updates to the streaming indexer."""

    def __init__(self, *, batch_size: int = 10_000) -> None:
        self.batch_size = batch_size

    def plan(
        self,
        sources: Sequence[str | Path],
        *,
        dbfile: str = "warcindex.db",
        data_dir: str | None = None,
        digest_fingerprint: bool = False,
    ) -> IngestionPlan:
        db_path = canonical_path(dbfile)
        requested = [canonical_path(item) for item in sources]
        if not db_path.exists():
            plan = IngestionPlan(database=str(db_path))
            for source in requested:
                plan.actions.append(
                    IngestionAction(
                        source=str(source),
                        action="add" if source.exists() else "conflict",
                        reason=None if source.exists() else "source not found",
                    )
                )
            return plan

        with Workspace(db_path, data_dir=data_dir, read_only=True, create=False) as workspace:
            archives = workspace.list_archives()
            plan = IngestionPlan(database=str(db_path), revision=workspace.revision())
            by_uri = {item["source_uri"]: item for item in archives}
            missing = [item for item in archives if not Path(item["source_path"]).exists()]
            missing_by_fingerprint: dict[str, list[dict[str, Any]]] = {}
            for item in missing:
                missing_by_fingerprint.setdefault(item["fingerprint"], []).append(item)

            seen: set[str] = set()
            for source in requested:
                uri = source.as_uri()
                seen.add(uri)
                existing = by_uri.get(uri)
                if not source.exists():
                    plan.actions.append(
                        IngestionAction(
                            source=str(source),
                            action="missing" if existing else "conflict",
                            archive_id=existing["id"] if existing else None,
                            reason="source not found",
                        )
                    )
                    continue
                fingerprint = SourceFingerprint.from_path(source, digest=digest_fingerprint)
                if existing:
                    action = (
                        "unchanged"
                        if existing["fingerprint"] == fingerprint.to_json()
                        else "update"
                    )
                    plan.actions.append(
                        IngestionAction(
                            source=str(source), action=action, archive_id=existing["id"]
                        )
                    )
                    continue
                candidates = missing_by_fingerprint.get(fingerprint.to_json(), [])
                if len(candidates) == 1:
                    candidate = candidates[0]
                    plan.actions.append(
                        IngestionAction(
                            source=str(source),
                            action="moved-candidate",
                            archive_id=candidate["id"],
                            moved_from=candidate["source_path"],
                            reason="explicit rebind required",
                        )
                    )
                elif len(candidates) > 1:
                    plan.actions.append(
                        IngestionAction(
                            source=str(source),
                            action="conflict",
                            reason="multiple missing archives have the same fingerprint",
                        )
                    )
                else:
                    plan.actions.append(IngestionAction(source=str(source), action="add"))

            for archive in archives:
                if archive["source_uri"] not in seen and not Path(archive["source_path"]).exists():
                    plan.actions.append(
                        IngestionAction(
                            source=archive["source_path"],
                            action="missing",
                            archive_id=archive["id"],
                            reason="registered source is unavailable",
                        )
                    )
            return plan

    def ingest(
        self,
        sources: Sequence[str | Path],
        *,
        dbfile: str = "warcindex.db",
        data_dir: str | None = None,
        dry_run: bool = False,
        resume: bool = True,
        force: bool = False,
        silent: bool = False,
        digest_fingerprint: bool = False,
        progress: ProgressCallback | None = None,
    ) -> tuple[IngestionPlan, IndexSummary | None]:
        plan = self.plan(
            sources,
            dbfile=dbfile,
            data_dir=data_dir,
            digest_fingerprint=digest_fingerprint,
        )
        if dry_run:
            return plan, None
        process = [
            item.source
            for item in plan.actions
            if item.action in {"add", "update", "unchanged"}
            and (force or item.action != "unchanged")
        ]
        if not process:
            with (
                Workspace(dbfile, data_dir=data_dir) as workspace,
                workspace.writer_lock("ingest"),
            ):
                run_id = workspace.start_run("ingest", plan.to_dict())
                workspace.finish_run(
                    run_id,
                    status=(
                        "partial"
                        if any(item.action == "conflict" for item in plan.actions)
                        else "complete"
                    ),
                    summary={"plan": plan.to_dict(), "result": None},
                )
            return plan, None
        summary = Indexer(batch_size=self.batch_size).index_records(
            process,
            dbfile,
            data_dir=data_dir,
            mode="force" if force else "update",
            resume=resume,
            silent=silent,
            digest_fingerprint=digest_fingerprint,
            progress=progress,
        )
        with (
            Workspace(dbfile, data_dir=data_dir, create=False) as workspace,
            workspace.writer_lock("ingest-manifest"),
        ):
            workspace.annotate_run(
                summary.run_id,
                operation="ingest",
                request={"plan": plan.to_dict(), "resume": resume, "force": force},
                summary={"plan": plan.to_dict(), "result": summary.to_dict()},
            )
        return plan, summary


__all__ = ["IncrementalIngestor", "IngestionAction", "IngestionPlan"]
