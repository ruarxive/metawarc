"""Subprocess driver for cross-process JobRunner integration tests."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from metawarc.jobs import Job, JobContext, JobKind, JobRunner, JobStatus, JobStore


class _Settings:
    db_path = "unused.db"
    job_max_concurrent = 2
    job_timeout_seconds = 30


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--invocations", type=Path, required=True)
    parser.add_argument("--started", type=Path, required=True)
    parser.add_argument("--hold-seconds", type=float, default=0.1)
    parser.add_argument("--stage-partial", action="store_true")
    args = parser.parse_args()
    store = JobStore(args.data_dir)

    async def handler(job: Job, context: JobContext) -> dict:
        descriptor = os.open(
            args.invocations,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()} {job.id}\n")
        args.started.write_text(str(os.getpid()), encoding="utf-8")
        if args.stage_partial:
            staged = store.job_directory(job.id) / ".result-crash.json.tmp"
            staged.write_text("incomplete", encoding="utf-8")
        await asyncio.sleep(args.hold_seconds)
        return {"rows": 1}

    async def exercise() -> None:
        runner = JobRunner(store, settings=_Settings())
        runner.register(JobKind.EXPORT_RECORDS, handler)
        await runner.start_background()
        try:
            for _ in range(300):
                current = store.load(args.job_id)
                if current is not None and current.status in {
                    JobStatus.SUCCEEDED.value,
                    JobStatus.FAILED.value,
                    JobStatus.CANCELLED.value,
                }:
                    return
                await asyncio.sleep(0.05)
            raise TimeoutError(f"job {args.job_id} did not reach a terminal state")
        finally:
            await runner.stop_background()

    asyncio.run(exercise())


if __name__ == "__main__":
    main()
