#!/usr/bin/env python3
"""Submit a job to the pilot coordinator and poll for the result."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from urllib import request


def http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, data=data, headers=headers)
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a prompt to the compute-share pilot.")
    parser.add_argument("prompt", help="Prompt or job payload to send")
    parser.add_argument(
        "--coordinator",
        default="http://127.0.0.1:8000",
        help="Coordinator base URL",
    )
    parser.add_argument(
        "--preferred-model",
        default=None,
        help="Optional worker model tag to target",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="How long to wait before giving up",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="How often to poll job status",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coordinator = args.coordinator.rstrip("/")
    payload = {"prompt": args.prompt}
    if args.preferred_model:
        payload["preferred_model"] = args.preferred_model

    job = http_json("POST", f"{coordinator}/jobs", payload)
    job_id = job["job_id"]
    print(f"Submitted job {job_id}")

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        status = http_json("GET", f"{coordinator}/jobs/{job_id}")
        if status["status"] in {"completed", "failed"}:
            print(json.dumps(status, indent=2))
            return
        time.sleep(args.poll_seconds)

    raise SystemExit(f"Timed out waiting for job {job_id}")


if __name__ == "__main__":
    main()
