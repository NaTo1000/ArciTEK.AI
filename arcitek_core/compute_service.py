#!/usr/bin/env python3
"""HTTP service for the ArciTEK compute dashboard."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .robotics_plan import ExpertPlanOrchestrator, ProjectRepository, formats, simulation
from .robotics_plan.storage import SQLiteStore
from .robotics_plan.validation import ValidationError


WEB_ROOT = Path(__file__).resolve().parent.parent / "arcitek_ui" / "web"
MAX_BODY_SIZE = 16_384
MAX_ROBOTICS_BODY_SIZE = 262_144
MAX_RETAINED_JOBS = 100
_ID_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9_\-.]{0,79}"


class ComputeQueue:
    """Bounded in-process queue for safe, predefined compute workloads."""

    WORKLOAD_LIMITS = {
        "prime-scan": (1_000, 2_000_000),
        "hash-benchmark": (1_000, 1_000_000),
        "fibonacci": (100, 100_000),
    }

    def __init__(self, workers: int = 2) -> None:
        self.started_at = time.time()
        self.workers = max(1, min(workers, 16))
        self.capacity = self.workers * 8
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=self.workers,
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
            active = sum(
                item["status"] in {"queued", "running"} for item in self._jobs.values()
            )
            if active >= self.capacity:
                raise ValueError("Compute queue is at capacity")
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
            "workers": self.workers,
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
            sieve = bytearray(b"\x01") * (size + 1)
            sieve[:2] = b"\x00\x00"
            for candidate in range(2, math.isqrt(size) + 1):
                if sieve[candidate]:
                    start = candidate * candidate
                    sieve[start::candidate] = b"\x00" * (
                        ((size - start) // candidate) + 1
                    )
            return {"primesFound": sum(sieve), "range": size}
        if workload == "hash-benchmark":
            digest = b"arcitek"
            for _ in range(size):
                digest = hashlib.sha256(digest).digest()
            return {"iterations": size, "digest": digest.hex()[:16]}

        previous, current = 0, 1
        for _ in range(size):
            previous, current = current, previous + current
        digits = (
            1
            if size < 2
            else math.floor(
                size * math.log10((1 + math.sqrt(5)) / 2)
                - math.log10(math.sqrt(5))
            )
            + 1
        )
        return {
            "index": size,
            "digits": digits,
            "tail": f"{previous % 10**16:016d}",
        }

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


class RoboticsPlanAPI:
    """Regex-routed REST surface over the robotics engineering-plan domain.

    Every handler validates its own inputs (delegating to the domain
    modules, which enforce bounded/strict validation) and returns a plain
    ``(HTTPStatus, dict)`` tuple. No handler executes external code, shells
    out, or calls any external AI service -- everything here is local,
    structured data produced by :mod:`arcitek_core.robotics_plan`.
    """

    def __init__(self, workers: int = 4, database: str | Path = ":memory:") -> None:
        self.store = SQLiteStore(database)
        self.repo = ProjectRepository(store=self.store)
        self.orchestrator = ExpertPlanOrchestrator(workers=workers, store=self.store)
        self._routes: list[tuple[str, re.Pattern, Any]] = [
            ("GET", re.compile(r"^/api/dashboard$"), self._get_dashboard),
            ("GET", re.compile(r"^/api/projects$"), self._list_projects),
            ("POST", re.compile(r"^/api/projects$"), self._create_project),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})$"),
                self._get_project,
            ),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/revisions$"),
                self._list_revisions,
            ),
            (
                "POST",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/revisions$"),
                self._create_revision,
            ),
            (
                "GET",
                re.compile(
                    rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/revisions/(?P<revision>\d+)$"
                ),
                self._get_revision,
            ),
            (
                "POST",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/rollback$"),
                self._rollback,
            ),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/approvals$"),
                self._list_approvals,
            ),
            (
                "POST",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/approvals$"),
                self._approve_revision,
            ),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/findings$"),
                self._get_findings,
            ),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/events$"),
                self._get_events,
            ),
            (
                "GET",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/plans$"),
                self._list_plans,
            ),
            (
                "POST",
                re.compile(rf"^/api/projects/(?P<project_id>{_ID_SEGMENT})/plans$"),
                self._create_plan,
            ),
            (
                "GET",
                re.compile(rf"^/api/plans/(?P<plan_id>{_ID_SEGMENT})$"),
                self._get_plan,
            ),
            (
                "POST",
                re.compile(rf"^/api/plans/(?P<plan_id>{_ID_SEGMENT})/approve$"),
                self._approve_plan,
            ),
            (
                "GET",
                re.compile(rf"^/api/plans/(?P<plan_id>{_ID_SEGMENT})/activity$"),
                self._get_plan_activity,
            ),
            ("GET", re.compile(r"^/api/formats$"), self._list_formats),
            (
                "POST",
                re.compile(rf"^/api/formats/(?P<format_id>{_ID_SEGMENT})/validate-import$"),
                self._validate_import,
            ),
            (
                "POST",
                re.compile(rf"^/api/formats/(?P<format_id>{_ID_SEGMENT})/export-manifest$"),
                self._export_manifest,
            ),
            ("GET", re.compile(r"^/api/simulations$"), self._list_simulations),
            (
                "POST",
                re.compile(rf"^/api/simulations/(?P<tool_id>{_ID_SEGMENT})/dry-run$"),
                self._simulation_dry_run,
            ),
        ]

    def dispatch(self, method: str, path: str, query: dict[str, list[str]], body: dict[str, Any] | None):
        for route_method, pattern, handler in self._routes:
            if route_method != method:
                continue
            match = pattern.match(path)
            if match:
                try:
                    return handler(match.groupdict(), query, body or {})
                except KeyError as exc:
                    return HTTPStatus.NOT_FOUND, {"error": str(exc) or "Not found"}
                except (ValidationError, ValueError, TypeError) as exc:
                    return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        return None

    def is_known_prefix(self, path: str) -> bool:
        return any(pattern.match(path) for _, pattern, _ in self._routes)

    # -- projects ----------------------------------------------------------
    def _list_projects(self, params, query, body):
        return HTTPStatus.OK, {"projects": self.repo.list_projects()}

    def _create_project(self, params, query, body):
        project = self.repo.create_project(
            name=body.get("name"),
            description=body.get("description", ""),
            author=body.get("author", "anonymous"),
            requirements=body.get("requirements"),
            parts=body.get("parts"),
            wiring=body.get("wiring"),
            hydraulics=body.get("hydraulics"),
            pcb=body.get("pcb"),
        )
        return HTTPStatus.CREATED, {"project": project}

    def _get_project(self, params, query, body):
        return HTTPStatus.OK, {"project": self.repo.get_project(params["project_id"])}

    # -- revisions -----------------------------------------------------
    def _list_revisions(self, params, query, body):
        revisions = self.repo.list_revisions(params["project_id"])
        return HTTPStatus.OK, {"revisions": revisions}

    def _create_revision(self, params, query, body):
        revision = self.repo.create_revision(
            params["project_id"],
            author=body.get("author", "anonymous"),
            message=body.get("message", ""),
            requirements=body.get("requirements"),
            parts=body.get("parts"),
            wiring=body.get("wiring"),
            hydraulics=body.get("hydraulics"),
            pcb=body.get("pcb"),
            base_revision=body.get("base_revision"),
        )
        return HTTPStatus.CREATED, {"revision": revision}

    def _get_revision(self, params, query, body):
        revision = self.repo.get_revision(params["project_id"], int(params["revision"]))
        return HTTPStatus.OK, {"revision": revision}

    def _rollback(self, params, query, body):
        revision = self.repo.rollback(
            params["project_id"],
            int(body.get("target_revision", 0)),
            author=body.get("author", "anonymous"),
            message=body.get("message", ""),
        )
        return HTTPStatus.CREATED, {"revision": revision}

    # -- approvals ---------------------------------------------------------
    def _list_approvals(self, params, query, body):
        revision = query.get("revision", [None])[0]
        approvals = self.repo.list_approvals(
            params["project_id"], int(revision) if revision else None
        )
        return HTTPStatus.OK, {"approvals": approvals}

    def _approve_revision(self, params, query, body):
        revision = self.repo.approve_revision(
            params["project_id"],
            int(body.get("revision", 0)),
            approver=body.get("approver", "anonymous"),
            decision=body.get("decision", ""),
            comment=body.get("comment", ""),
        )
        return HTTPStatus.OK, {"revision": revision}

    def _get_findings(self, params, query, body):
        revision = query.get("revision", [None])[0]
        findings = self.repo.get_findings(
            params["project_id"], int(revision) if revision else None
        )
        return HTTPStatus.OK, {"findings": findings}

    def _get_events(self, params, query, body):
        limit = int(query.get("limit", ["200"])[0])
        events = self.repo.list_events(params["project_id"], limit=limit)
        return HTTPStatus.OK, {"events": events}

    # -- plans / orchestration ----------------------------------------------
    def _list_plans(self, params, query, body):
        return HTTPStatus.OK, {"plans": self.orchestrator.list_plans(params["project_id"])}

    def _create_plan(self, params, query, body):
        revision_number = body.get("revision")
        if revision_number:
            snapshot = self.repo.get_revision(params["project_id"], int(revision_number))
        else:
            current = self.repo.get_project(params["project_id"])["current_revision"]
            snapshot = self.repo.get_revision(params["project_id"], current)
        plan = self.orchestrator.create_plan(
            project_id=params["project_id"],
            revision=snapshot["number"],
            requested_by=body.get("requested_by", "anonymous"),
            snapshot=snapshot,
        )
        return HTTPStatus.CREATED, {"plan": plan}

    def _get_plan(self, params, query, body):
        return HTTPStatus.OK, {"plan": self.orchestrator.get_plan(params["plan_id"])}

    def _approve_plan(self, params, query, body):
        plan = self.orchestrator.approve_plan(
            params["plan_id"],
            approver=body.get("approver", "anonymous"),
            decision=body.get("decision", ""),
            comment=body.get("comment", ""),
        )
        return HTTPStatus.OK, {"plan": plan}

    def _get_plan_activity(self, params, query, body):
        limit = int(query.get("limit", ["200"])[0])
        activity = self.orchestrator.list_activity(params["plan_id"], limit=limit)
        return HTTPStatus.OK, {"activity": activity}

    # -- formats -------------------------------------------------------
    def _list_formats(self, params, query, body):
        return HTTPStatus.OK, {"formats": formats.list_formats()}

    def _validate_import(self, params, query, body):
        manifest = formats.validate_import(
            params["format_id"], body.get("filename", ""), body.get("metadata")
        )
        return HTTPStatus.OK, {"manifest": manifest}

    def _export_manifest(self, params, query, body):
        manifest = formats.build_export_manifest(params["format_id"], body.get("payload"))
        return HTTPStatus.OK, {"manifest": manifest}

    # -- simulation adapters -------------------------------------------------
    def _list_simulations(self, params, query, body):
        return HTTPStatus.OK, {"tools": simulation.list_tools()}

    def _simulation_dry_run(self, params, query, body):
        project_id = body.get("project_id")
        revision_number = body.get("revision")
        if project_id:
            if revision_number:
                snapshot = self.repo.get_revision(project_id, int(revision_number))
            else:
                current = self.repo.get_project(project_id)["current_revision"]
                snapshot = self.repo.get_revision(project_id, current)
        else:
            snapshot = body.get("snapshot") or {}
        result = simulation.dry_run(params["tool_id"], snapshot)
        return HTTPStatus.OK, {"result": result}

    # -- dashboard ----------------------------------------------------------
    def _get_dashboard(self, params, query, body):
        projects = self.repo.list_projects()
        plans = self.orchestrator.list_plans()
        severity_totals: dict[str, int] = {}
        for project in projects:
            for severity, count in project["findings_summary"].items():
                if severity == "total":
                    continue
                severity_totals[severity] = severity_totals.get(severity, 0) + count
        return HTTPStatus.OK, {
            "project_count": len(projects),
            "plan_count": len(plans),
            "plans_awaiting_approval": sum(1 for p in plans if p["status"] == "completed"),
            "plans_released": sum(1 for p in plans if p["status"] == "released"),
            "severity_totals": severity_totals,
            "simulation_tools": simulation.list_tools(),
            "recent_projects": projects[:10],
            "recent_plans": plans[:10],
        }


class ComputeRequestHandler(SimpleHTTPRequestHandler):
    """Serve the dashboard and its JSON API from one origin."""

    queue: ComputeQueue
    robotics: RoboticsPlanAPI

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {"status": "operational", "service": "ArciTEK Compute", "version": "1.0.0"},
            )
        elif path == "/api/metrics":
            self._json(HTTPStatus.OK, self.queue.metrics())
        elif path == "/api/jobs":
            self._json(HTTPStatus.OK, {"jobs": self.queue.list_jobs()})
        elif path.startswith("/api/"):
            result = self.robotics.dispatch("GET", path, query, None)
            if result is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
                return
            self._json(*result)
        else:
            if path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/jobs":
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
            return

        if not path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_ROBOTICS_BODY_SIZE:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(content_length))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        result = self.robotics.dispatch("POST", path, {}, body)
        if result is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return
        self._json(*result)

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


class ArciTEKHTTPServer(ThreadingHTTPServer):
    """HTTP server that closes the shared persistence store on shutdown."""

    store: SQLiteStore

    def server_close(self) -> None:
        super().server_close()
        self.store.close()


def create_server(
    host: str,
    port: int,
    workers: int,
    database: str | Path = ":memory:",
) -> ThreadingHTTPServer:
    queue = ComputeQueue(workers)
    robotics = RoboticsPlanAPI(workers=workers, database=database)
    handler = type(
        "ArciTEKHandler", (ComputeRequestHandler,), {"queue": queue, "robotics": robotics}
    )
    server = ArciTEKHTTPServer((host, port), handler)
    server.store = robotics.store
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ArciTEK compute service")
    parser.add_argument("--host", default=os.getenv("ARCITEK_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("ARCITEK_PORT", "8000"))
    )
    parser.add_argument(
        "--workers", type=int, default=int(os.getenv("ARCITEK_WORKERS", "2"))
    )
    parser.add_argument(
        "--database",
        default=os.getenv("ARCITEK_DATABASE", "data/arcitek.db"),
        help="SQLite database path (default: data/arcitek.db)",
    )
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.workers, args.database)
    print(f"ArciTEK Compute listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
