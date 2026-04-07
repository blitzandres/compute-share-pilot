#!/usr/bin/env python3
"""Minimal coordinator for a trusted compute-sharing pilot.

This service keeps an in-memory registry of workers and jobs.
Workers poll for work, so they can sit behind NAT without opening
inbound ports on home networks.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000
WORKER_TTL_SECONDS = 45.0


def now_ts() -> float:
    return time.time()


class Registry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[str, dict[str, Any]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._job_order: list[str] = []

    def register_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        worker_id = str(payload["worker_id"])
        with self._lock:
            existing = self._workers.get(worker_id, {})
            worker = {
                "worker_id": worker_id,
                "secret": str(payload["secret"]),
                "region": str(payload.get("region", "unknown")),
                "model": str(payload.get("model", "mock-llm")),
                "benchmark_tps": float(payload.get("benchmark_tps", 0.0)),
                "max_context": int(payload.get("max_context", 0)),
                "supports_ollama": bool(payload.get("supports_ollama", False)),
                "status": "idle",
                "last_seen": now_ts(),
                "current_job_id": existing.get("current_job_id"),
            }
            self._workers[worker_id] = worker
            return self._public_worker(worker)

    def list_workers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._public_worker(worker) for worker in self._workers.values()]

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        prompt = str(payload["prompt"])
        preferred_model = payload.get("preferred_model")
        job = {
            "job_id": job_id,
            "prompt": prompt,
            "preferred_model": str(preferred_model) if preferred_model else None,
            "status": "queued",
            "created_at": now_ts(),
            "assigned_at": None,
            "completed_at": None,
            "worker_id": None,
            "output": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._job_order.append(job_id)
            return dict(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def authenticate_worker(self, worker_id: str, secret: str) -> bool:
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return False
            return worker["secret"] == secret

    def poll_for_job(self, worker_id: str, secret: str) -> dict[str, Any] | None:
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker or worker["secret"] != secret:
                return None

            worker["last_seen"] = now_ts()
            worker["status"] = "idle"
            worker["current_job_id"] = None

            for job_id in self._job_order:
                job = self._jobs[job_id]
                if job["status"] != "queued":
                    continue

                preferred_model = job.get("preferred_model")
                if preferred_model and preferred_model != worker["model"]:
                    continue

                job["status"] = "assigned"
                job["assigned_at"] = now_ts()
                job["worker_id"] = worker_id
                worker["status"] = "busy"
                worker["current_job_id"] = job_id
                return dict(job)
            return None

    def submit_result(
        self,
        worker_id: str,
        secret: str,
        job_id: str,
        output: str | None,
        error: str | None,
    ) -> dict[str, Any] | None:
        with self._lock:
            worker = self._workers.get(worker_id)
            job = self._jobs.get(job_id)
            if not worker or not job or worker["secret"] != secret:
                return None

            worker["last_seen"] = now_ts()
            worker["status"] = "idle"
            worker["current_job_id"] = None
            job["completed_at"] = now_ts()
            job["output"] = output
            job["error"] = error
            job["status"] = "failed" if error else "completed"
            return dict(job)

    def health(self) -> dict[str, Any]:
        with self._lock:
            live_workers = 0
            cutoff = now_ts() - WORKER_TTL_SECONDS
            for worker in self._workers.values():
                if worker["last_seen"] >= cutoff:
                    live_workers += 1
            queued_jobs = sum(1 for job in self._jobs.values() if job["status"] == "queued")
            return {
                "status": "ok",
                "live_workers": live_workers,
                "total_workers": len(self._workers),
                "queued_jobs": queued_jobs,
                "total_jobs": len(self._jobs),
            }

    @staticmethod
    def _public_worker(worker: dict[str, Any]) -> dict[str, Any]:
        public_worker = dict(worker)
        public_worker.pop("secret", None)
        public_worker["is_live"] = worker["last_seen"] >= now_ts() - WORKER_TTL_SECONDS
        return public_worker


REGISTRY = Registry()


class Handler(BaseHTTPRequestHandler):
    server_version = "ComputeSharePilot/0.1"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, REGISTRY.health())
            return

        if path == "/workers":
            self._send_json(HTTPStatus.OK, {"workers": REGISTRY.list_workers()})
            return

        if path.startswith("/jobs/"):
            job_id = path.removeprefix("/jobs/")
            job = REGISTRY.get_job(job_id)
            if not job:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                return
            self._send_json(HTTPStatus.OK, job)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()
        if isinstance(payload, tuple):
            status, message = payload
            self._send_json(status, {"error": message})
            return

        if path == "/register":
            missing = [field for field in ("worker_id", "secret") if field not in payload]
            if missing:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"missing required fields: {', '.join(missing)}"},
                )
                return
            worker = REGISTRY.register_worker(payload)
            self._send_json(HTTPStatus.OK, worker)
            return

        if path == "/jobs":
            if "prompt" not in payload:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing required field: prompt"})
                return
            job = REGISTRY.create_job(payload)
            self._send_json(HTTPStatus.CREATED, job)
            return

        if path == "/workers/poll":
            missing = [field for field in ("worker_id", "secret") if field not in payload]
            if missing:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"missing required fields: {', '.join(missing)}"},
                )
                return
            job = REGISTRY.poll_for_job(str(payload["worker_id"]), str(payload["secret"]))
            if job is None and not REGISTRY.authenticate_worker(
                str(payload["worker_id"]), str(payload["secret"])
            ):
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid worker credentials"})
                return
            self._send_json(HTTPStatus.OK, {"job": job})
            return

        if path == "/workers/result":
            missing = [field for field in ("worker_id", "secret", "job_id") if field not in payload]
            if missing:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"missing required fields: {', '.join(missing)}"},
                )
                return

            job = REGISTRY.submit_result(
                worker_id=str(payload["worker_id"]),
                secret=str(payload["secret"]),
                job_id=str(payload["job_id"]),
                output=payload.get("output"),
                error=payload.get("error"),
            )
            if not job:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid worker or job state"})
                return
            self._send_json(HTTPStatus.OK, job)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

    def _read_json(self) -> dict[str, Any] | tuple[HTTPStatus, str]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            raw_body = self.rfile.read(length)
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return HTTPStatus.BAD_REQUEST, "invalid JSON body"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Coordinator listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
