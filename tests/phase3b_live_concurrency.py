
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data" / "public_sample_cases.json"

pack = json.loads(DATA.read_text(encoding="utf-8"))
cases = pack["cases"][:4]


def run_case(case):
    started = time.perf_counter()

    with TestClient(app) as client:
        response = client.post(
            "/optimize-energy",
            json=case["input"],
        )

    elapsed = time.perf_counter() - started

    if response.status_code != 200:
        return {
            "ok": False,
            "case": case["id"],
            "elapsed": elapsed,
            "message": (
                f"status={response.status_code} "
                f"body={response.text[:500]}"
            ),
        }

    body = response.json()
    expected_cost = float(
        case["expected_output"]["total_cost_bdt"]
    )
    actual_cost = float(body["total_cost_bdt"])

    if abs(actual_cost - expected_cost) > 0.01:
        return {
            "ok": False,
            "case": case["id"],
            "elapsed": elapsed,
            "message": (
                "optimal cost mismatch "
                f"expected={expected_cost} actual={actual_cost}"
            ),
        }

    return {
        "ok": True,
        "case": case["id"],
        "elapsed": elapsed,
        "message": "ok",
    }


started_all = time.perf_counter()

with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [
        pool.submit(run_case, case)
        for case in cases
    ]

    results = [
        future.result()
        for future in as_completed(futures)
    ]

wall = time.perf_counter() - started_all

for result in sorted(results, key=lambda item: item["case"]):
    print(
        "[CONCURRENCY] "
        f"case={result['case']} "
        f"ok={result['ok']} "
        f"seconds={result['elapsed']:.3f} "
        f"message={result['message']}"
    )

if not all(result["ok"] for result in results):
    print("[FAIL] One or more concurrent requests failed.")
    sys.exit(1)

if any(result["elapsed"] > 30.0 for result in results):
    print("[FAIL] A concurrent request exceeded 30 seconds.")
    sys.exit(2)

print(
    f"[CONCURRENCY] workers=4 wall_seconds={wall:.3f}"
)
print("[PASS] 4 concurrent real E2E requests completed correctly.")