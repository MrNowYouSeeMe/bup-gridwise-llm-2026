import json
import pytest
from pathlib import Path

from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app

client = TestClient(app, raise_server_exceptions=False)



def _phase3_stub_result(payload):
    return {
        "scenario_id": payload.scenario_id,
        "directive_interpretation": [],
        "hourly_plan": [],
        "total_grid_kwh": 0.0,
        "total_cost_bdt": 0.0,
        "peak_grid_kwh": 0.0,
        "plan_summary": "offline regression stub",
    }


@pytest.fixture(autouse=True)
def _phase3_stub_pipeline(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "run_pipeline",
        _phase3_stub_result,
    )


def make_payload():
    return {
        "scenario_id": "GRID-PHASE1",
        "operator_notes": ["Do not charge the battery from 2 PM to 4 PM."],
        "hours": [
            {
                "hour": hour,
                "demand_kwh": 100.0,
                "solar_kwh": 20.0,
                "tariff_bdt_per_kwh": 8.0,
            }
            for hour in range(24)
        ],
        "battery": {
            "capacity_kwh": 500.0,
            "initial_energy_kwh": 200.0,
            "minimum_energy_kwh": 50.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0,
        },
    }


def assert_phase1_valid(response):
    assert response.status_code == 200

    body = response.json()

    assert set(body) == {
        "scenario_id",
        "directive_interpretation",
        "hourly_plan",
        "total_grid_kwh",
        "total_cost_bdt",
        "peak_grid_kwh",
        "plan_summary",
    }

    assert "traceback" not in str(body).lower()


def test_health_exact():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_request_id_header_exists():
    assert "X-Request-ID" in client.get("/health").headers


def test_valid_request_reaches_phase1_boundary():
    assert_phase1_valid(client.post("/optimize-energy", json=make_payload()))


def test_one_two_three_notes_are_valid():
    for count in (1, 2, 3):
        p = make_payload()
        p["operator_notes"] = [f"note {i}" for i in range(count)]
        assert_phase1_valid(client.post("/optimize-energy", json=p))


def test_zero_notes_rejected():
    p = make_payload(); p["operator_notes"] = []
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_four_notes_rejected():
    p = make_payload(); p["operator_notes"] = ["a", "b", "c", "d"]
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_blank_note_rejected():
    p = make_payload(); p["operator_notes"] = ["   "]
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_blank_scenario_id_rejected():
    p = make_payload(); p["scenario_id"] = "   "
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_23_hours_rejected():
    p = make_payload(); p["hours"] = p["hours"][:-1]
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_25_hours_rejected():
    p = make_payload(); p["hours"].append(dict(p["hours"][-1]))
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_duplicate_hour_rejected():
    p = make_payload(); p["hours"][23]["hour"] = 22
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_out_of_range_hour_rejected():
    p = make_payload(); p["hours"][23]["hour"] = 24
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_shuffled_hours_are_accepted():
    p = make_payload(); p["hours"] = list(reversed(p["hours"]))
    assert_phase1_valid(client.post("/optimize-energy", json=p))


def test_boolean_hour_rejected():
    p = make_payload(); p["hours"][0]["hour"] = True
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_string_number_rejected():
    p = make_payload(); p["hours"][0]["demand_kwh"] = "100"
    assert client.post("/optimize-energy", json=p).status_code == 400


def test_nan_rejected():
    p = make_payload(); p["hours"][0]["demand_kwh"] = float("nan")
    raw = json.dumps(p, allow_nan=True)
    r = client.post("/optimize-energy", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_infinity_rejected():
    p = make_payload(); p["hours"][0]["solar_kwh"] = float("inf")
    raw = json.dumps(p, allow_nan=True)
    r = client.post("/optimize-energy", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_malformed_json_rejected():
    r = client.post("/optimize-energy", content='{"scenario_id":', headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_negative_battery_values_rejected():
    fields = [
        "capacity_kwh",
        "initial_energy_kwh",
        "minimum_energy_kwh",
        "max_charge_kwh_per_hour",
        "max_discharge_kwh_per_hour",
    ]
    for field in fields:
        p = make_payload(); p["battery"][field] = -1
        assert client.post("/optimize-energy", json=p).status_code == 422


def test_initial_above_capacity_rejected():
    p = make_payload(); p["battery"]["initial_energy_kwh"] = 501
    assert client.post("/optimize-energy", json=p).status_code == 422


def test_minimum_above_capacity_rejected():
    p = make_payload(); p["battery"]["minimum_energy_kwh"] = 501
    assert client.post("/optimize-energy", json=p).status_code == 422


def test_zero_battery_rates_allowed():
    p = make_payload()
    p["battery"]["max_charge_kwh_per_hour"] = 0
    p["battery"]["max_discharge_kwh_per_hour"] = 0
    assert_phase1_valid(client.post("/optimize-energy", json=p))


def test_unknown_input_fields_are_ignored():
    p = make_payload()
    p["extra"] = "ignored"
    p["hours"][0]["extra"] = 123
    p["battery"]["extra"] = True
    assert_phase1_valid(client.post("/optimize-energy", json=p))


def test_logging_file_exists():
    client.get("/health")
    assert Path("logs/gridwise.log").exists()