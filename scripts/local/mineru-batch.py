#!/usr/bin/env python3
"""Batch orchestration for MinerU API conversions.

This script intentionally lives outside the upstream `mineru/` package. It
submits one document per API task so retries, stop-on-failure, and manifests are
tracked at document granularity.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import signal
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from mineru.cli import api_client


SUPPORTED_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".docx",
    ".pptx",
    ".xlsx",
}
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
}
DEFAULT_API_URL = "http://127.0.0.1:7861"


@dataclass(frozen=True)
class BatchPaths:
    output_root: Path
    batch_dir: Path
    documents_dir: Path
    logs_dir: Path
    manifest_json: Path
    manifest_jsonl: Path
    failed_json: Path


@dataclass
class JobRecord:
    source_path: Path
    relative_path: Path
    output_dir: Path
    result_dir: Path
    status_path: Path
    status: str = "pending"
    attempts: int = 0
    task_ids: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "relative_path": self.relative_path.as_posix(),
            "output_dir": str(self.output_dir),
            "result_dir": str(self.result_dir),
            "status": self.status,
            "attempts": self.attempts,
            "task_ids": self.task_ids,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "backend": args.backend,
            "method": args.method,
            "lang": args.lang,
            "api_url": args.api_url,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def stable_suffix(text: str, length: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def sanitize_component(component: str) -> str:
    sanitized = "".join(
        char if char.isalnum() or char in " ._-+=" else "_"
        for char in component
    ).strip()
    return sanitized or "_"


def safe_relative_output_path(relative_path: Path) -> Path:
    parts = [sanitize_component(part) for part in relative_path.parts]
    if not parts:
        return Path("_")
    parts[-1] = f"{parts[-1]}__{stable_suffix(relative_path.as_posix())}"
    return Path(*parts)


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def build_batch_paths(output_root: Path, batch_name: str | None) -> BatchPaths:
    resolved_batch_name = batch_name or f"batch-{local_timestamp()}"
    batch_dir = output_root / resolved_batch_name
    return BatchPaths(
        output_root=output_root,
        batch_dir=batch_dir,
        documents_dir=batch_dir / "documents",
        logs_dir=batch_dir / "logs",
        manifest_json=batch_dir / "manifest.json",
        manifest_jsonl=batch_dir / "manifest.jsonl",
        failed_json=batch_dir / "failed.json",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root.addHandler(stderr_handler)
    root.addHandler(file_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def discover_documents(input_path: Path, output_root: Path) -> list[Path]:
    input_path = input_path.resolve()
    output_root = output_root.resolve()
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return []
        return [input_path]

    documents: list[Path] = []
    for root_text, dirnames, filenames in os.walk(input_path):
        root = Path(root_text)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_DIR_NAMES
            and not dirname.startswith(".")
            and not path_is_relative_to(root / dirname, output_root)
        ]
        for filename in filenames:
            path = root / filename
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                documents.append(path)
    return sorted(documents, key=lambda item: item.relative_to(input_path).as_posix())


def build_jobs(input_path: Path, batch_paths: BatchPaths) -> list[JobRecord]:
    documents = discover_documents(input_path, batch_paths.output_root)
    jobs: list[JobRecord] = []
    input_root = input_path.resolve() if input_path.is_dir() else input_path.resolve().parent

    for document in documents:
        relative_path = document.resolve().relative_to(input_root)
        job_dir = batch_paths.documents_dir / safe_relative_output_path(relative_path)
        jobs.append(
            JobRecord(
                source_path=document,
                relative_path=relative_path,
                output_dir=job_dir,
                result_dir=job_dir / "result",
                status_path=job_dir / "status.json",
            )
        )
    return jobs


def build_form_data(args: argparse.Namespace) -> dict[str, str | list[str]]:
    return api_client.build_parse_request_form_data(
        lang_list=[args.lang],
        backend=args.backend,
        parse_method=args.method,
        formula_enable=args.formula,
        table_enable=args.table,
        image_analysis=args.image_analysis,
        server_url=args.server_url,
        start_page_id=args.start,
        end_page_id=args.end,
        return_md=True,
        return_middle_json=True,
        return_model_output=True,
        return_content_list=True,
        return_images=True,
        response_format_zip=True,
        return_original_file=True,
    )


def retry_delay(args: argparse.Namespace, failed_attempt_index: int) -> float:
    if not args.retry_delays:
        return 0.0
    index = min(failed_attempt_index - 1, len(args.retry_delays) - 1)
    return args.retry_delays[index]


def should_skip_completed(job: JobRecord, args: argparse.Namespace) -> bool:
    if not args.resume or not job.status_path.exists():
        return False
    try:
        payload = json.loads(job.status_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return payload.get("status") == "succeeded"


def copy_source_if_requested(job: JobRecord, args: argparse.Namespace) -> None:
    if not args.copy_source:
        return
    target = job.output_dir / "source" / job.source_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(job.source_path, target)


async def run_one_attempt(
    client: httpx.AsyncClient,
    job: JobRecord,
    args: argparse.Namespace,
    form_data: dict[str, str | list[str]],
) -> None:
    submit_response = await api_client.submit_parse_task(
        base_url=args.api_url,
        upload_assets=[
            api_client.UploadAsset(
                path=job.source_path,
                upload_name=job.source_path.name,
            )
        ],
        form_data=form_data,
    )
    job.task_ids.append(submit_response.task_id)
    write_json(job.status_path, job.to_payload(args))
    logging.info(
        "submitted %s attempt=%s task_id=%s",
        job.relative_path.as_posix(),
        job.attempts,
        submit_response.task_id,
    )
    await api_client.wait_for_task_result(
        client=client,
        submit_response=submit_response,
        task_label=job.relative_path.as_posix(),
    )
    zip_path = await api_client.download_result_zip(
        client=client,
        submit_response=submit_response,
        task_label=job.relative_path.as_posix(),
    )
    try:
        if job.result_dir.exists() and not args.keep_attempt_output:
            shutil.rmtree(job.result_dir)
        api_client.safe_extract_zip(zip_path, job.result_dir)
    finally:
        zip_path.unlink(missing_ok=True)


async def run_job(
    client: httpx.AsyncClient,
    job: JobRecord,
    args: argparse.Namespace,
    paths: BatchPaths,
    form_data: dict[str, str | list[str]],
) -> JobRecord:
    if should_skip_completed(job, args):
        job.status = "skipped"
        job.error = None
        job.completed_at = utc_now()
        write_json(job.status_path, job.to_payload(args))
        append_jsonl(paths.manifest_jsonl, job.to_payload(args))
        logging.info("skipped already completed %s", job.relative_path.as_posix())
        return job

    job.output_dir.mkdir(parents=True, exist_ok=True)
    job.status = "running"
    job.started_at = utc_now()
    job.error = None
    write_json(job.status_path, job.to_payload(args))

    for attempt in range(1, args.max_attempts + 1):
        job.attempts = attempt
        write_json(job.status_path, job.to_payload(args))
        try:
            await run_one_attempt(client, job, args, form_data)
            copy_source_if_requested(job, args)
            job.status = "succeeded"
            job.error = None
            job.completed_at = utc_now()
            write_json(job.status_path, job.to_payload(args))
            append_jsonl(paths.manifest_jsonl, job.to_payload(args))
            logging.info("succeeded %s attempts=%s", job.relative_path.as_posix(), attempt)
            return job
        except Exception as exc:
            job.error = str(exc)
            logging.warning(
                "failed %s attempt=%s/%s error=%s",
                job.relative_path.as_posix(),
                attempt,
                args.max_attempts,
                job.error,
            )
            write_json(job.status_path, job.to_payload(args))
            if attempt >= args.max_attempts:
                break
            delay = retry_delay(args, attempt)
            if delay > 0:
                await asyncio.sleep(delay)

    job.status = "failed"
    job.completed_at = utc_now()
    write_json(job.status_path, job.to_payload(args))
    append_jsonl(paths.manifest_jsonl, job.to_payload(args))
    logging.error("failed permanently %s attempts=%s", job.relative_path.as_posix(), job.attempts)
    return job


async def run_batch(args: argparse.Namespace, paths: BatchPaths, jobs: list[JobRecord]) -> list[JobRecord]:
    timeout = api_client.build_http_timeout()
    form_data = build_form_data(args)
    completed: list[JobRecord] = []
    stop_requested = asyncio.Event()
    queue: asyncio.Queue[JobRecord] = asyncio.Queue()
    for job in jobs:
        await queue.put(job)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        health = await api_client.fetch_server_health(client, api_client.normalize_base_url(args.api_url))
        args.api_url = health.base_url
        effective_concurrency = max(1, min(args.concurrency, health.max_concurrent_requests, len(jobs)))
        logging.info(
            "connected api=%s backend=%s jobs=%s concurrency=%s",
            health.base_url,
            args.backend,
            len(jobs),
            effective_concurrency,
        )

        async def worker() -> None:
            while True:
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    if stop_requested.is_set():
                        job.status = "skipped"
                        job.error = "Skipped because a previous job failed permanently."
                        job.completed_at = utc_now()
                        write_json(job.status_path, job.to_payload(args))
                        append_jsonl(paths.manifest_jsonl, job.to_payload(args))
                        completed.append(job)
                        continue
                    result = await run_job(client, job, args, paths, form_data)
                    completed.append(result)
                    if result.status == "failed" and args.on_fail == "stop":
                        stop_requested.set()
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(effective_concurrency)]
        await queue.join()
        await asyncio.gather(*workers, return_exceptions=False)

    return sorted(completed, key=lambda item: item.relative_path.as_posix())


def build_summary(args: argparse.Namespace, jobs: Iterable[JobRecord]) -> dict[str, Any]:
    records = [job.to_payload(args) for job in jobs]
    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "created_at": utc_now(),
        "input": str(args.input),
        "output": str(args.output),
        "batch_name": args.batch_name,
        "counts": counts,
        "jobs": records,
    }


def mark_interrupted_jobs(
    args: argparse.Namespace,
    paths: BatchPaths,
    jobs: Iterable[JobRecord],
) -> None:
    for job in jobs:
        if job.status == "running":
            job.status = "interrupted"
            job.error = "Batch process was interrupted before this job reached a terminal state."
            job.completed_at = utc_now()
            write_json(job.status_path, job.to_payload(args))
    summary = build_summary(args, jobs)
    write_json(paths.manifest_json, summary)
    failed = [job.to_payload(args) for job in jobs if job.status == "failed"]
    write_json(paths.failed_json, failed)


def raise_keyboard_interrupt(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


def parse_retry_delays(value: str) -> list[float]:
    if not value.strip():
        return []
    delays: list[float] = []
    for item in value.split(","):
        try:
            delay = float(item.strip())
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid retry delay {item!r}; expected comma-separated seconds."
            ) from exc
        if delay < 0:
            raise argparse.ArgumentTypeError("Retry delays must be >= 0.")
        delays.append(delay)
    return delays


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch convert documents through an existing MinerU FastAPI service."
    )
    parser.add_argument("--input", "-i", type=Path, required=True, help="Input file or directory.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output root directory.")
    parser.add_argument("--batch-name", default=None, help="Batch directory name. Defaults to batch-YYYYMMDD-HHMMSS.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"MinerU API base URL. Default: {DEFAULT_API_URL}")
    parser.add_argument(
        "--backend",
        default="vlm-auto-engine",
        choices=[
            "pipeline",
            "vlm-http-client",
            "hybrid-http-client",
            "vlm-auto-engine",
            "hybrid-auto-engine",
        ],
    )
    parser.add_argument("--method", default="auto", choices=["auto", "txt", "ocr"])
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--server-url", default=None, help="Required for *-http-client backends.")
    parser.add_argument("--start", type=int, default=0, help="PDF start page id, beginning from 0.")
    parser.add_argument("--end", type=int, default=None, help="PDF end page id, beginning from 0.")
    parser.add_argument("--formula", dest="formula", action="store_true", default=True)
    parser.add_argument("--no-formula", dest="formula", action="store_false")
    parser.add_argument("--table", dest="table", action="store_true", default=True)
    parser.add_argument("--no-table", dest="table", action="store_false")
    parser.add_argument("--image-analysis", dest="image_analysis", action="store_true", default=True)
    parser.add_argument("--no-image-analysis", dest="image_analysis", action="store_false")
    parser.add_argument("--max-attempts", "--max-retries", dest="max_attempts", type=int, default=3)
    parser.add_argument("--retry-delays", type=parse_retry_delays, default=parse_retry_delays("5,15,45"))
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--on-fail", choices=["stop", "continue"], default="stop")
    parser.add_argument("--resume", action="store_true", help="Skip jobs with existing succeeded status.json.")
    parser.add_argument("--copy-source", action="store_true", help="Copy source documents into each job directory.")
    parser.add_argument(
        "--keep-attempt-output",
        action="store_true",
        help="Do not clear a job result directory before writing a later successful attempt.",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input does not exist: {args.input}")
    if args.max_attempts < 1:
        parser.error("--max-attempts must be >= 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    if args.start < 0:
        parser.error("--start must be >= 0")
    if args.end is not None and args.end < 0:
        parser.error("--end must be >= 0")
    args.api_url = api_client.normalize_base_url(args.api_url)
    return args


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, raise_keyboard_interrupt)
    args = parse_args(argv or sys.argv[1:])
    paths = build_batch_paths(args.output, args.batch_name)
    args.batch_name = paths.batch_dir.name
    paths.batch_dir.mkdir(parents=True, exist_ok=True)
    paths.documents_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(paths.logs_dir / "batch.log")
    if not args.resume:
        paths.manifest_jsonl.unlink(missing_ok=True)

    jobs = build_jobs(args.input, paths)
    if not jobs:
        logging.error("no supported documents found under %s", args.input)
        return 2

    logging.info("batch_dir=%s", paths.batch_dir)
    logging.info("discovered %s supported document(s)", len(jobs))

    try:
        completed = asyncio.run(run_batch(args, paths, jobs))
    except KeyboardInterrupt:
        mark_interrupted_jobs(args, paths, jobs)
        logging.error("interrupted")
        return 130
    except Exception as exc:
        logging.exception("batch crashed: %s", exc)
        summary = build_summary(args, jobs)
        write_json(paths.manifest_json, summary)
        failed = [job.to_payload(args) for job in jobs if job.status == "failed"]
        write_json(paths.failed_json, failed)
        return 1

    summary = build_summary(args, completed)
    write_json(paths.manifest_json, summary)
    failed = [job.to_payload(args) for job in completed if job.status == "failed"]
    write_json(paths.failed_json, failed)
    logging.info("summary=%s", json.dumps(summary["counts"], ensure_ascii=False))
    logging.info("manifest=%s", paths.manifest_json)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
