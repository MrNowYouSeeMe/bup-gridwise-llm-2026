
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.llm_interpreter import LLMInterpreterError
from app.main import app
from app.optimizer import OptimizationError
from app.pipeline import run_pipeline
from app.replay import (
    ReplayValidationError,
    validate_schedule,
)
from app.schemas import ScenarioRequest


client = TestClient(
    app,
    raise_server_exceptions=False,
)


TOP_LEVEL_KEYS = {
    "scenario_id",
    "directive_interpretation",
    "hourly_plan",
    "total_grid_kwh",
    "total_cost_bdt",
    "peak_grid_kwh",
    "plan_summary",
}


def make_payload():
    return {
        "scenario_id": "API-OFFLINE",
        "operator_notes": [
            "Do not charge from 2 PM to 4 PM."
        ],
        "hours": [
            {
                "hour": h,
                "demand_kwh": 100.0,
                "solar_kwh": 20.0,
                "tariff_bdt_per_kwh": (
                    5.0
                    if h < 8
                    else 15.0
                ),
            }
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 20.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        },
    }


def fake_interpreter(**kwargs):
    return [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {
                "hours": [14, 15],
            },
            "explanation": "Charging unavailable.",
        }
    ]


def run_real_offline(payload_dict=None):
    if payload_dict is None:
        payload_dict = make_payload()

    payload = ScenarioRequest.model_validate(
        payload_dict
    )

    return payload, run_pipeline(
        payload,
        interpreter=fake_interpreter,
    )


def test_pipeline_exact_top_level_contract():
    payload, response = run_real_offline()

    assert set(response) == TOP_LEVEL_KEYS
    assert response["scenario_id"] == (
        payload.scenario_id
    )
    assert len(response["hourly_plan"]) == 24
    assert len(
        response["directive_interpretation"]
    ) == 1
    assert response["plan_summary"].strip()

    validate_schedule(
        payload,
        response["directive_interpretation"],
        response["hourly_plan"],
    )


def test_hourly_plan_exact_fields():
    _, response = run_real_offline()

    expected = {
        "hour",
        "grid_kwh",
        "solar_used_kwh",
        "battery_action",
        "battery_kwh",
        "battery_energy_after_kwh",
    }

    for row in response["hourly_plan"]:
        assert set(row) == expected


def test_metrics_match_hourly_plan():
    payload, response = run_real_offline()

    total_grid = sum(
        row["grid_kwh"]
        for row in response["hourly_plan"]
    )
    peak = max(
        row["grid_kwh"]
        for row in response["hourly_plan"]
    )
    tariff = {
        item.hour: float(
            item.tariff_bdt_per_kwh
        )
        for item in payload.hours
    }
    cost = sum(
        row["grid_kwh"] * tariff[row["hour"]]
        for row in response["hourly_plan"]
    )

    assert response["total_grid_kwh"] == pytest.approx(
        total_grid,
        abs=1e-6,
    )
    assert response["peak_grid_kwh"] == pytest.approx(
        peak,
        abs=1e-6,
    )
    assert response["total_cost_bdt"] == pytest.approx(
        cost,
        abs=1e-6,
    )


def test_health_contract_unchanged():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_main_success_mapping(monkeypatch):
    _, expected = run_real_offline()

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        lambda payload: expected,
    )

    response = client.post(
        "/optimize-energy",
        json=make_payload(),
    )

    assert response.status_code == 200
    assert set(response.json()) == TOP_LEVEL_KEYS


def test_llm_failure_is_controlled_503(
    monkeypatch,
):
    def fail(_payload):
        raise LLMInterpreterError("secret details")

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail,
    )

    response = client.post(
        "/optimize-energy",
        json=make_payload(),
    )

    assert response.status_code == 503

    body = response.json()

    assert body["error"] == (
        "llm_interpretation_error"
    )
    assert "request_id" in body
    assert "secret details" not in str(body)
    assert "traceback" not in str(body).lower()


def test_optimizer_failure_is_controlled_422(
    monkeypatch,
):
    def fail(_payload):
        raise OptimizationError("solver detail")

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail,
    )

    response = client.post(
        "/optimize-energy",
        json=make_payload(),
    )

    assert response.status_code == 422

    body = response.json()

    assert body["error"] == "optimization_error"
    assert "solver detail" not in str(body)


def test_replay_failure_is_controlled_500(
    monkeypatch,
):
    def fail(_payload):
        raise ReplayValidationError(
            ["internal replay detail"]
        )

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail,
    )

    response = client.post(
        "/optimize-energy",
        json=make_payload(),
    )

    assert response.status_code == 500

    body = response.json()

    assert body["error"] == (
        "schedule_validation_error"
    )
    assert "internal replay detail" not in str(body)


def test_malformed_request_never_calls_pipeline(
    monkeypatch,
):
    called = False

    def fail_if_called(_payload):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail_if_called,
    )

    response = client.post(
        "/optimize-energy",
        content='{"scenario_id":',
        headers={
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 400
    assert called is False


def test_semantic_invalid_battery_never_calls_pipeline(
    monkeypatch,
):
    called = False

    def fail_if_called(_payload):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        fail_if_called,
    )

    payload = make_payload()
    payload["battery"]["initial_energy_kwh"] = 999

    response = client.post(
        "/optimize-energy",
        json=payload,
    )

    assert response.status_code == 422
    assert called is False


def test_repeated_offline_pipeline_is_stateless():
    for index in range(30):
        payload = make_payload()
        payload["scenario_id"] = (
            f"REPEAT-{index}"
        )

        validated = ScenarioRequest.model_validate(
            payload
        )

        response = run_pipeline(
            validated,
            interpreter=fake_interpreter,
        )

        assert response["scenario_id"] == (
            f"REPEAT-{index}"
        )
        assert len(response["hourly_plan"]) == 24


def _offline_once(index):
    payload = make_payload()
    payload["scenario_id"] = f"CONCURRENT-{index}"

    validated = ScenarioRequest.model_validate(
        payload
    )

    result = run_pipeline(
        validated,
        interpreter=fake_interpreter,
    )

    return (
        result["scenario_id"],
        result["total_cost_bdt"],
        len(result["hourly_plan"]),
    )


def test_concurrent_offline_pipeline_is_stable():
    with ThreadPoolExecutor(
        max_workers=8
    ) as pool:
        results = list(
            pool.map(
                _offline_once,
                range(32),
            )
        )

    assert len(results) == 32

    for index, result in enumerate(results):
        scenario_id, _, count = result
        assert scenario_id == (
            f"CONCURRENT-{index}"
        )
        assert count == 24
