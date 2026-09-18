
import json
from pathlib import Path

import pytest

from app.optimizer import solve_schedule
from app.replay import (
    recalculate_metrics,
    validate_schedule,
)
from app.schemas import ScenarioRequest


DATA_PATH = (
    Path(__file__).parent
    / "data"
    / "public_sample_cases.json"
)


def load_cases():
    data = json.loads(
        DATA_PATH.read_text(encoding="utf-8")
    )
    assert data["_meta"]["case_count"] == 10
    return data["cases"]


@pytest.mark.parametrize(
    "case",
    load_cases(),
    ids=lambda case: case["id"],
)
def test_official_reference_schedule_replays(case):
    payload = ScenarioRequest.model_validate(
        case["input"]
    )
    expected = case["expected_output"]

    validate_schedule(
        payload,
        expected["directive_interpretation"],
        expected["hourly_plan"],
        atol=0.01,
    )

    metrics = recalculate_metrics(
        payload,
        expected["hourly_plan"],
    )

    assert metrics["total_grid_kwh"] == pytest.approx(
        expected["total_grid_kwh"],
        abs=0.01,
    )
    assert metrics["total_cost_bdt"] == pytest.approx(
        expected["total_cost_bdt"],
        abs=0.01,
    )
    assert metrics["peak_grid_kwh"] == pytest.approx(
        expected["peak_grid_kwh"],
        abs=0.01,
    )


@pytest.mark.parametrize(
    "case",
    load_cases(),
    ids=lambda case: case["id"],
)
def test_optimizer_matches_official_optimal_cost(case):
    payload = ScenarioRequest.model_validate(
        case["input"]
    )
    expected = case["expected_output"]
    interpretations = expected[
        "directive_interpretation"
    ]

    plan = solve_schedule(
        payload,
        interpretations,
    )

    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    metrics = recalculate_metrics(
        payload,
        plan,
    )

    assert metrics["total_cost_bdt"] == pytest.approx(
        expected["total_cost_bdt"],
        abs=0.01,
    )

    # Total grid is also deterministic across the public
    # references even though the exact hourly optimal schedule
    # may differ.
    assert metrics["total_grid_kwh"] == pytest.approx(
        expected["total_grid_kwh"],
        abs=0.01,
    )
