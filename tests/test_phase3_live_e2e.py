
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.replay import (
    recalculate_metrics,
    validate_schedule,
)
from app.schemas import ScenarioRequest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PHASE3_LIVE_E2E") != "1",
    reason="Phase-3 live E2E disabled",
)


client = TestClient(
    app,
    raise_server_exceptions=False,
)

DATA_PATH = (
    Path(__file__).parent
    / "data"
    / "public_sample_cases.json"
)


def public_cases():
    return json.loads(
        DATA_PATH.read_text(encoding="utf-8")
    )["cases"]


def assert_interpretation_semantics(
    actual,
    expected,
):
    assert len(actual) == len(expected)

    for index, (got, want) in enumerate(
        zip(actual, expected)
    ):
        assert got["note_index"] == index
        assert got["note_index"] == want["note_index"]
        assert got["applies"] is want["applies"]
        assert got["directive_type"] == (
            want["directive_type"]
        )

        ga = got["structured_adjustment"]
        wa = want["structured_adjustment"]

        if wa is None:
            assert ga is None
            continue

        assert ga is not None
        assert ga["hours"] == wa["hours"]

        for numeric in (
            "factor",
            "minimum_energy_kwh",
            "max_grid_kwh",
        ):
            if numeric in wa:
                assert ga[numeric] == pytest.approx(
                    wa[numeric],
                    abs=0.01,
                )


@pytest.mark.parametrize(
    "case",
    public_cases(),
    ids=lambda case: case["id"],
)
def test_all_official_public_samples_live_e2e(
    case,
):
    started = time.perf_counter()

    response = client.post(
        "/optimize-energy",
        json=case["input"],
    )

    elapsed = time.perf_counter() - started

    print(
        f"[PUBLIC-E2E] {case['id']} "
        f"status={response.status_code} "
        f"seconds={elapsed:.3f}"
    )

    assert response.status_code == 200, (
        response.text
    )

    body = response.json()
    expected = case["expected_output"]

    assert body["scenario_id"] == case["id"]

    assert_interpretation_semantics(
        body["directive_interpretation"],
        expected["directive_interpretation"],
    )

    payload = ScenarioRequest.model_validate(
        case["input"]
    )

    # Replay using organizer ground-truth directives,
    # not merely the model's returned interpretation.
    validate_schedule(
        payload,
        expected["directive_interpretation"],
        body["hourly_plan"],
        atol=0.01,
    )

    metrics = recalculate_metrics(
        payload,
        body["hourly_plan"],
    )

    assert body["total_grid_kwh"] == pytest.approx(
        metrics["total_grid_kwh"],
        abs=0.01,
    )
    assert body["total_cost_bdt"] == pytest.approx(
        metrics["total_cost_bdt"],
        abs=0.01,
    )
    assert body["peak_grid_kwh"] == pytest.approx(
        metrics["peak_grid_kwh"],
        abs=0.01,
    )

    assert body["total_cost_bdt"] == pytest.approx(
        expected["total_cost_bdt"],
        abs=0.01,
    )


def synthetic_input(note):
    hours = []

    for hour in range(24):
        solar = 0.0

        if 8 <= hour <= 16:
            solar = 60.0

        hours.append(
            {
                "hour": hour,
                "demand_kwh": 100.0,
                "solar_kwh": solar,
                "tariff_bdt_per_kwh": (
                    6.0
                    if hour < 8
                    else 12.0
                    if hour < 17
                    else 25.0
                    if hour < 21
                    else 10.0
                ),
            }
        )

    return {
        "scenario_id": "MULTILINGUAL-E2E",
        "operator_notes": [note],
        "hours": hours,
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 20.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        },
    }


MULTILINGUAL_CASES = [
    (
        "bn_solar",
        "দুপুর ১টা থেকে ৩টা পর্যন্ত সোলার স্বাভাবিকের ২০% থাকবে।",
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {
                "hours": [13, 14],
                "factor": 0.2,
            },
            "explanation": "expected",
        },
    ),
    (
        "banglish_no_charge",
        "2 PM theke 4 PM battery charge kora jabe na",
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {
                "hours": [14, 15],
            },
            "explanation": "expected",
        },
    ),
    (
        "bn_no_discharge",
        "সন্ধ্যা ৬টা থেকে রাত ৯টা পর্যন্ত ব্যাটারি ডিসচার্জ করা যাবে না।",
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {
                "hours": [18, 19, 20],
            },
            "explanation": "expected",
        },
    ),
    (
        "banglish_reserve",
        "6 PM theke 9 PM battery te at least half capacity reserve rakho",
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {
                "hours": [18, 19, 20],
                "minimum_energy_kwh": 100.0,
            },
            "explanation": "expected",
        },
    ),
    (
        "mixed_grid_cap",
        "7 PM theke 10 PM grid import 70 kWh er beshi nibe na",
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {
                "hours": [19, 20, 21],
                "max_grid_kwh": 70.0,
            },
            "explanation": "expected",
        },
    ),
    (
        "bn_no_op",
        "আগামীকাল ক্যাফেটেরিয়ার মেনু পরিবর্তন হবে।",
        {
            "note_index": 0,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "expected",
        },
    ),
]


@pytest.mark.parametrize(
    "case_id,note,expected",
    MULTILINGUAL_CASES,
    ids=[
        case[0]
        for case in MULTILINGUAL_CASES
    ],
)
def test_multilingual_full_pipeline(
    case_id,
    note,
    expected,
):
    payload_dict = synthetic_input(note)
    payload_dict["scenario_id"] = case_id

    started = time.perf_counter()

    response = client.post(
        "/optimize-energy",
        json=payload_dict,
    )

    elapsed = time.perf_counter() - started

    print(
        f"[MULTI-E2E] {case_id} "
        f"status={response.status_code} "
        f"seconds={elapsed:.3f}"
    )

    assert response.status_code == 200, (
        response.text
    )

    body = response.json()

    assert_interpretation_semantics(
        body["directive_interpretation"],
        [expected],
    )

    payload = ScenarioRequest.model_validate(
        payload_dict
    )

    validate_schedule(
        payload,
        [expected],
        body["hourly_plan"],
        atol=0.01,
    )
