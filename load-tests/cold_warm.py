"""Measure cold-start versus warm latency of deployed functions.

Usage (against a running OpenFaaS gateway with scale-to-zero support)::

    export OPENFAAS_URL=http://127.0.0.1:8080 OPENFAAS_USER=admin OPENFAAS_PASSWORD=...
    python load-tests/cold_warm.py --function quality-check --image synthetic/output/... \
        --tenant uni-a --api-key "$KEY" --rounds 5 --warm 20

Each round scales the function to zero through the gateway API, waits
until no replica is ready, times the first (cold) request, then times
``--warm`` further requests. The quality-check precheck is a good subject
because it is synchronous and does real work; intake works the same way.
Results go to ``results/cold_warm.json`` as raw timings plus p50/p95.
"""

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

import httpx


def percentile(values: list[float], q: float) -> float:
    """The ``q``-quantile (0-1) by nearest rank."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * len(ordered)) - 1))]


def scale_to_zero(client: httpx.Client, function: str, timeout: float = 180.0) -> None:
    """Ask the gateway for zero replicas and wait until none is available."""
    client.post(f"/system/scale-function/{function}", json={"serviceName": function, "replicas": 0})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(f"/system/function/{function}").json()
        if status.get("availableReplicas", 0) == 0:
            return
        time.sleep(2)
    raise TimeoutError(f"{function} did not scale to zero within {timeout}s")


def timed_request(
    client: httpx.Client, function: str, body: bytes, headers: dict[str, str]
) -> float:
    """Seconds taken by one invocation; non-2xx responses raise."""
    started = time.perf_counter()
    response = client.post(f"/function/{function}", content=body, headers=headers, timeout=300)
    response.raise_for_status()
    return time.perf_counter() - started


def main(argv: list[str] | None = None) -> None:
    """Run the measurement rounds and write the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", default="quality-check")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--tenant", default="uni-a")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--warm", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path("results/cold_warm.json"))
    args = parser.parse_args(argv)

    auth = (os.environ.get("OPENFAAS_USER", "admin"), os.environ.get("OPENFAAS_PASSWORD", ""))
    base = os.environ.get("OPENFAAS_URL", "http://127.0.0.1:8080")
    headers = {"Content-Type": "image/png", "X-Tenant-Id": args.tenant, "X-Api-Key": args.api_key}
    body = args.image.read_bytes()
    cold: list[float] = []
    warm: list[float] = []
    with httpx.Client(base_url=base, auth=auth, timeout=30) as client:
        for _ in range(args.rounds):
            scale_to_zero(client, args.function)
            cold.append(timed_request(client, args.function, body, headers))
            warm.extend(
                timed_request(client, args.function, body, headers) for _ in range(args.warm)
            )

    def summary(values: list[float]) -> dict[str, Any]:
        return {
            "n": len(values),
            "p50": round(statistics.median(values), 3),
            "p95": round(percentile(values, 0.95), 3),
            "raw": [round(v, 3) for v in values],
        }

    report = {"function": args.function, "cold": summary(cold), "warm": summary(warm)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
