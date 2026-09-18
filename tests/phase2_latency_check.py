import statistics
import time

from app.llm_interpreter import (
    interpret_operator_notes,
)


cases = [
    [
        "Solar output will drop to 20% from 1 PM to 3 PM."
    ],
    [
        "2 PM theke 4 PM battery charge kora jabe na"
    ],
    [
        "সন্ধ্যা ৭টা থেকে রাত ১০টা পর্যন্ত প্রতি ঘণ্টায় গ্রিড থেকে ৬০ kWh-এর বেশি নেওয়া যাবে না।"
    ],
    [
        "Keep 50% of battery capacity from 6 PM to 9 PM.",
        "Do not discharge from 7 PM to 8 PM.",
        "The cafeteria menu changes tomorrow.",
    ],
]

times = []

for round_no in range(2):
    for index, notes in enumerate(cases):
        started = time.perf_counter()

        interpret_operator_notes(
            scenario_id=f"LAT-{round_no}-{index}",
            notes=notes,
            battery_capacity_kwh=500,
            battery_minimum_energy_kwh=50,
        )

        elapsed = (
            time.perf_counter() - started
        )

        times.append(elapsed)

        print(
            f"[LATENCY] call={len(times)} "
            f"seconds={elapsed:.3f}"
        )

ordered = sorted(times)
p95_index = max(
    0,
    min(
        len(ordered) - 1,
        int(0.95 * len(ordered) + 0.999999) - 1,
    ),
)

p95 = ordered[p95_index]

print(
    f"[LATENCY] count={len(times)} "
    f"avg={statistics.mean(times):.3f}s "
    f"p95={p95:.3f}s "
    f"max={max(times):.3f}s"
)

if p95 <= 5:
    print("[PASS] Phase-2 LLM p95 <= 5s in this local sample.")
elif p95 <= 15:
    print("[WARN] Phase-2 LLM p95 is >5s and <=15s.")
else:
    print("[WARN] Phase-2 LLM p95 is >15s.")