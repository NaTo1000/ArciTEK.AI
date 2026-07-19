#!/usr/bin/env python3
"""HTTP service for the ArciTEK compute dashboard."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WEB_ROOT = Path(__file__).resolve().parent.parent / "arcitek_ui" / "web"
MAX_BODY_SIZE = 16_384
MAX_RETAINED_JOBS = 100


class ComputeQueue:
    """Bounded in-process queue for safe, predefined compute workloads."""

    WORKLOAD_LIMITS = {
        "prime-scan": (1_000, 2_000_000),
        "hash-benchmark": (1_000, 1_000_000),
        "fibonacci": (100, 100_000),
    }

    def __init__(self, workers: int = 2) -> None:
        self.started_at = time.time()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(workers, 16)),
            thread_name_prefix="arcitek-compute",
        )

    def submit(self, workload: str, size: int) -> dict[str, Any]:
        if workload not in self.WORKLOAD_LIMITS:
            raise ValueError("Unsupported workload")
        minimum, maximum = self.WORKLOAD_LIMITS[workload]
        if not minimum <= size <= maximum:
            raise ValueError(f"Size must be between {minimum:,} and {maximum:,}")

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "workload": workload,
            "size": size,
            "status": "queued",
            "createdAt": int(time.time()),
            "startedAt": None,
            "completedAt": None,
            "durationMs": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._trim_jobs()
        self._executor.submit(self._run, job_id)
        return dict(job)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = [dict(job) for job in self._jobs.values()]
        return sorted(jobs, key=lambda job: job["createdAt"], reverse=True)

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            jobs = list(self._jobs.values())
        running = sum(job["status"] == "running" for job in jobs)
        queued = sum(job["status"] == "queued" for job in jobs)
        completed = sum(job["status"] == "completed" for job in jobs)
        return {
            "cpuLoad": self._cpu_load(),
            "memoryPercent": self._memory_percent(),
            "runningJobs": running,
            "queuedJobs": queued,
            "completedJobs": completed,
            "uptimeSeconds": int(time.time() - self.started_at),
            "workers": self._executor._max_workers,
        }

    def _run(self, job_id: str) -> None:
        started = time.time()
        self._update(job_id, status="running", startedAt=int(started))
        try:
            with self._lock:
                job = dict(self._jobs[job_id])
            result = self._execute(job["workload"], job["size"])
            self._update(
                job_id,
                status="completed",
                result=result,
                completedAt=int(time.time()),
                durationMs=round((time.time() - started) * 1000),
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                error=str(exc),
                completedAt=int(time.time()),
                durationMs=round((time.time() - started) * 1000),
            )

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)

    def _trim_jobs(self) -> None:
        if len(self._jobs) <= MAX_RETAINED_JOBS:
            return
        finished = [
            job
            for job in self._jobs.values()
            if job["status"] in {"completed", "failed"}
        ]
        for job in sorted(finished, key=lambda item: item["createdAt"])[
            : len(self._jobs) - MAX_RETAINED_JOBS
        ]:
            self._jobs.pop(job["id"], None)

    @staticmethod
    def _execute(workload: str, size: int) -> dict[str, Any]:
        if workload == "prime-scan":
            count = 0
            for candidate in range(2, size + 1):
                if all(candidate % divisor for divisor in range(2, math.isqrt(candidate) + 1)):
                    count += 1
            return {"primesFound": count, "range": size}
        if workload == "hash-benchmark":
            digest = b"arcitek"
            for _ in range(size):
                digest = hashlib.sha256(digest).digest()
            return {"iterations": size, "digest": digest.hex()[:16]}

        previous, current = 0, 1
        for _ in range(size):
            previous, current = current, previous + current
        return {"index": size, "digits": len(str(previous)), "tail": str(previous)[-16:]}

    @staticmethod
    def _cpu_load() -> float:
        try:
            return round(min(os.getloadavg()[0] / (os.cpu_count() or 1) * 100, 100), 1)
        except (AttributeError, OSError):
            return 0.0

    @staticmethod
    def _memory_percent() -> float:
        try:
            values: dict[str, int] = {}
            with open("/proc/meminfo", encoding="utf-8") as meminfo:
                for line in meminfo:
                    key, value = line.split(":", 1)
                    values[key] = int(value.strip().split()[0])
            return round((1 - values["MemAvailable"] / values["MemTotal"]) * 100, 1)
        except (OSError, KeyError, ValueError):
            return 0.0


class ComputeRequestHandler(SimpleHTTPRequestHandler):
    """Serve the dashboard and its JSON API from one origin."""

    queue: ComputeQueue

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {"status": "operational", "service": "ArciTEK Compute", "version": "1.0.0"},
            )
        elif path == "/api/metrics":
            self._json(HTTPStatus.OK, self.queue.metrics())
        elif path == "/api/jobs":
            self._json(HTTPStatus.OK, {"jobs": self.queue.list_jobs()})
        else:
            if path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/jobs":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_BODY_SIZE:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(content_length))
            workload = str(payload.get("workload", ""))
            size = int(payload.get("size", 0))
            job = self.queue.submit(workload, size)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._json(HTTPStatus.ACCEPTED, {"job": job})

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'",
        )
        super().end_headers()

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str, port: int, workers: int) -> ThreadingHTTPServer:
    queue = ComputeQueue(workers)
    handler = type("ArciTEKHandler", (ComputeRequestHandler,), {"queue": queue})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ArciTEK compute service")
    parser.add_argument("--host", default=os.getenv("ARCITEK_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("ARCITEK_PORT", "8000"))
    )
    parser.add_argument(
        "--workers", type=int, default=int(os.getenv("ARCITEK_WORKERS", "2"))
    )
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.workers)
    print(f"ArciTEK Compute listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
