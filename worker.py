#!/usr/bin/env python3
"""Polling worker for the trusted compute-sharing pilot.

The worker keeps an outbound connection pattern: register, poll, work, report.
That is friendlier to home networks than exposing a public inference port.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib import error, request

COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://127.0.0.1:8000").rstrip("/")
WORKER_ID = os.getenv("WORKER_ID", "worker-demo")
WORKER_SECRET = os.getenv("WORKER_SECRET", "change-me")
WORKER_REGION = os.getenv("WORKER_REGION", "home-lab")
ADVERTISED_MODEL = os.getenv("ADVERTISED_MODEL") or os.getenv("OLLAMA_MODEL", "mock-llm")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "2"))
MOCK_DELAY_SECONDS = float(os.getenv("MOCK_DELAY_SECONDS", "1.2"))
BENCHMARK_TPS = float(os.getenv("BENCHMARK_TPS", "8"))
MAX_CONTEXT = int(os.getenv("MAX_CONTEXT", "4096"))
REGISTER_INTERVAL_SECONDS = float(os.getenv("REGISTER_INTERVAL_SECONDS", "20"))


def http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, data=data, headers=headers)
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def register_worker() -> None:
    payload = {
        "worker_id": WORKER_ID,
        "secret": WORKER_SECRET,
        "region": WORKER_REGION,
        "model": ADVERTISED_MODEL,
        "benchmark_tps": BENCHMARK_TPS,
        "max_context": MAX_CONTEXT,
        "supports_ollama": bool(OLLAMA_MODEL),
    }
    http_json("POST", f"{COORDINATOR_URL}/register", payload)


def poll_job() -> dict[str, Any] | None:
    payload = {"worker_id": WORKER_ID, "secret": WORKER_SECRET}
    response = http_json("POST", f"{COORDINATOR_URL}/workers/poll", payload)
    return response.get("job")


def submit_result(job_id: str, output: str | None, error_message: str | None) -> None:
    payload = {
        "worker_id": WORKER_ID,
        "secret": WORKER_SECRET,
        "job_id": job_id,
        "output": output,
        "error": error_message,
    }
    http_json("POST", f"{COORDINATOR_URL}/workers/result", payload)


def mock_generate(prompt: str) -> str:
    time.sleep(MOCK_DELAY_SECONDS)
    short_prompt = prompt.strip().replace("\n", " ")
    if len(short_prompt) > 120:
        short_prompt = short_prompt[:117] + "..."
    return (
        f"[mock-response from {WORKER_ID} in {WORKER_REGION}]\n"
        f"model={ADVERTISED_MODEL}\n"
        f"prompt={short_prompt}\n"
        "This is where a local model result would be returned."
    )


def ollama_generate(prompt: str) -> str:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    response = http_json("POST", f"{OLLAMA_URL}/api/generate", payload)
    return str(response.get("response", "")).strip()


def generate(prompt: str) -> str:
    if OLLAMA_MODEL:
        return ollama_generate(prompt)
    return mock_generate(prompt)


def main() -> None:
    print(f"Worker {WORKER_ID} connecting to {COORDINATOR_URL} as model {ADVERTISED_MODEL}")
    last_register = 0.0

    while True:
        try:
            if time.time() - last_register >= REGISTER_INTERVAL_SECONDS:
                register_worker()
                last_register = time.time()

            job = poll_job()
            if not job:
                time.sleep(POLL_SECONDS)
                continue

            job_id = str(job["job_id"])
            print(f"Picked up job {job_id}")
            try:
                output = generate(str(job["prompt"]))
                submit_result(job_id, output=output, error_message=None)
                print(f"Completed job {job_id}")
            except Exception as exc:  # noqa: BLE001
                submit_result(job_id, output=None, error_message=str(exc))
                print(f"Failed job {job_id}: {exc}")
        except error.HTTPError as exc:
            print(f"HTTP error: {exc.code} {exc.reason}")
            time.sleep(POLL_SECONDS)
        except error.URLError as exc:
            print(f"Network error: {exc.reason}")
            time.sleep(POLL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            print(f"Unexpected error: {exc}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
