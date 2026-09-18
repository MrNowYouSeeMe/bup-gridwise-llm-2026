
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data" / "public_sample_cases.json"


def percentile_95(values: list[float]) -> float:
    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    index = 0.95 * (len(ordered) - 1)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower

    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


pack = json.loads(DATA.read_text(encoding="utf-8"))
cases = pack["cases"][:10]

times: list[float] = []

with TestClient(app) as client:
    for case in cases:
        started = time.perf_counter()

        response = client.post(
            "/optimize-energy",
            json=case["input"],
        )

        elapsed = time.perf_counter() - started

        if response.status_code != 200:
            print(
                "[FAIL] "
                f"{case['id']} status={response.status_code} "
                f"body={response.text[:500]}"
            )
            sys.exit(1)

        body = response.json()

        expected_cost = float(
            case["expected_output"]["total_cost_bdt"]
        )
        actual_cost = float(body["total_cost_bdt"])

        if abs(actual_cost - expected_cost) > 0.01:
            print(
                "[FAIL] "
                f"{case['id']} optimal cost mismatch "
                f"expected={expected_cost} actual={actual_cost}"
            )
            sys.exit(1)

        times.append(elapsed)

        print(
            f"[LATENCY] case={case['id']} "
            f"seconds={elapsed:.3f}"
        )

p95 = percentile_95(times)
avg = statistics.mean(times)
maximum = max(times)

print(
    "[LATENCY] "
    f"count={len(times)} "
    f"avg={avg:.3f}s "
    f"p95={p95:.3f}s "
    f"max={maximum:.3f}s"
)

if maximum > 30.0:
    print("[FAIL] A valid request exceeded the 30s hard timeout target.")
    sys.exit(2)

if p95 > 5.0:
    print("[FAIL] Full E2E p95 is above the <=5s full-score target.")
    sys.exit(3)

print("[PASS] Full E2E p95 <= 5s and all 10 costs remained optimal.")