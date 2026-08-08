"""Presentation-neutral progress events and Rich terminal rendering."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import IO, Literal

from rich.console import Console, RenderableType
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

ProgressScope = Literal["overall", "current"]
ProgressStatus = Literal["running", "complete", "skipped", "failed"]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """One monotonic update for a bounded progress task."""

    operation: str
    phase: str
    task_id: str
    label: str
    unit: str
    completed: int = 0
    total: int | None = None
    scope: ProgressScope = "current"
    status: ProgressStatus = "running"
    context: Mapping[str, str | int] = field(default_factory=dict)
    counters: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.completed < 0:
            raise ValueError("progress completed value cannot be negative")
        if self.total is not None and self.total < 0:
            raise ValueError("progress total cannot be negative")


ProgressCallback = Callable[[ProgressEvent], None]


def ignore_progress(_event: ProgressEvent) -> None:
    """Default callback for callers that do not need presentation."""


NO_PROGRESS: ProgressCallback = ignore_progress


def emit_progress(callback: ProgressCallback | None, event: ProgressEvent) -> None:
    """Emit an event only when a caller supplied a callback."""
    if callback is not None:
        callback(event)


def resolve_progress(
    requested: bool | None,
    *,
    silent: bool = False,
    machine_readable: bool = False,
    stream: IO[str] | None = None,
) -> bool:
    """Resolve explicit and automatic CLI progress behavior."""
    if silent or machine_readable:
        return False
    if requested is not None:
        return requested
    output = stream if stream is not None else sys.stderr
    return bool(getattr(output, "isatty", lambda: False)())


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    rounded = max(0, int(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class WorkColumn(ProgressColumn):
    """Render completed work honestly for determinate and open-ended tasks."""

    def render(self, task: Task) -> RenderableType:
        unit = str(task.fields.get("unit", "item"))
        completed = int(task.completed)
        if task.total is None:
            return Text(f"{completed:,} {unit}")
        return Text(f"{completed:,}/{int(task.total):,} {unit}")


class RateColumn(ProgressColumn):
    """Render a rate only after Rich has enough samples to calculate one."""

    def render(self, task: Task) -> RenderableType:
        if task.speed is None:
            return Text("")
        unit = str(task.fields.get("unit", "item"))
        return Text(f"{task.speed:,.1f} {unit}/s")


class ConditionalEtaColumn(ProgressColumn):
    """Avoid displaying a placeholder ETA for tasks without a known total."""

    def render(self, task: Task) -> RenderableType:
        if task.total is None or task.time_remaining is None or task.finished:
            return Text("")
        return Text(f"eta {_duration(task.time_remaining)}")


class RichProgressRenderer:
    """Render at most one overall and one current progress task to stderr."""

    def __init__(
        self,
        *,
        enabled: bool,
        console: Console | None = None,
        refresh_per_second: float = 10.0,
    ) -> None:
        self.enabled = enabled
        self.active = False
        self._console = console or Console(stderr=True, force_terminal=True)
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}", markup=False),
            BarColumn(bar_width=None),
            WorkColumn(),
            RateColumn(),
            TimeElapsedColumn(),
            ConditionalEtaColumn(),
            console=self._console,
            refresh_per_second=refresh_per_second,
        )
        self._tasks: dict[ProgressScope, tuple[str, TaskID]] = {}

    @property
    def callback(self) -> ProgressCallback | None:
        """Return a callback only when rendering is enabled."""
        return self if self.enabled else None

    def __enter__(self) -> RichProgressRenderer:
        if self.enabled:
            self._progress.start()
            self.active = True
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        if self.active:
            self._progress.stop()
            self.active = False
        self._tasks.clear()

    def __call__(self, event: ProgressEvent) -> None:
        if not self.enabled:
            return
        if not self.active:
            raise RuntimeError("progress renderer must be used as a context manager")

        key = f"{event.operation}:{event.phase}:{event.task_id}"
        current = self._tasks.get(event.scope)
        if current is None or current[0] != key:
            if current is not None:
                self._progress.remove_task(current[1])
            task = self._progress.add_task(
                self._description(event),
                total=event.total,
                completed=event.completed,
                unit=event.unit,
            )
            self._tasks[event.scope] = (key, task)
        else:
            task = current[1]
            self._progress.update(
                task,
                description=self._description(event),
                total=event.total,
                completed=event.completed,
                unit=event.unit,
            )
        if event.status != "running":
            self._progress.refresh()

    @staticmethod
    def _description(event: ProgressEvent) -> str:
        pieces = [event.label]
        if event.counters:
            values = ", ".join(
                f"{value:,} {name}" for name, value in event.counters.items() if value
            )
            if values:
                pieces.append(f"({values})")
        if event.status != "running":
            pieces.append(f"[{event.status}]")
        return " ".join(pieces)


__all__ = [
    "NO_PROGRESS",
    "ProgressCallback",
    "ProgressEvent",
    "RichProgressRenderer",
    "emit_progress",
    "ignore_progress",
    "resolve_progress",
]
