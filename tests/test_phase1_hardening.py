from concurrent.futures import ThreadPoolExecutor
import pytest

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app



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


def client():
    return TestClient(
        app,
        raise_server_exceptions=False,
    )


def make_payload():
    return {
        "scenario_id": "HARDENING-01",
        "operator_notes": [
            "Do not charge the battery from 2 PM to 4 PM."
        ],
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


def assert_invalid_400(response):
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_request"
    assert "request_id" in body
    assert "traceback" not in str(body).lower()


def assert_phase1_boundary(response):
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


def test_empty_body_is_controlled_400():
    response = client().post("/optimize-energy")
    assert_invalid_400(response)


def test_json_null_is_controlled_400():
    response = client().post(
        "/optimize-energy",
        content="null",
        headers={"Content-Type": "application/json"},
    )
    assert_invalid_400(response)


def test_root_array_is_rejected():
    response = client().post(
        "/optimize-energy",
        json=[],
    )
    assert_invalid_400(response)


def test_missing_scenario_id_is_rejected():
    payload = make_payload()
    del payload["scenario_id"]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_missing_operator_notes_is_rejected():
    payload = make_payload()
    del payload["operator_notes"]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_missing_hours_is_rejected():
    payload = make_payload()
    del payload["hours"]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_missing_battery_is_rejected():
    payload = make_payload()
    del payload["battery"]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_numeric_scenario_id_is_rejected():
    payload = make_payload()
    payload["scenario_id"] = 123

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_operator_notes_string_instead_of_array_is_rejected():
    payload = make_payload()
    payload["operator_notes"] = "Do not charge."

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_non_string_note_is_rejected():
    payload = make_payload()
    payload["operator_notes"] = [123]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_hours_object_instead_of_array_is_rejected():
    payload = make_payload()
    payload["hours"] = {"hour": 0}

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_missing_hour_field_is_rejected():
    payload = make_payload()
    del payload["hours"][7]["solar_kwh"]

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_float_hour_is_rejected():
    payload = make_payload()
    payload["hours"][5]["hour"] = 5.0

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_negative_hour_is_rejected():
    payload = make_payload()
    payload["hours"][0]["hour"] = -1

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_battery_null_is_rejected():
    payload = make_payload()
    payload["battery"] = None

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_battery_string_number_is_rejected():
    payload = make_payload()
    payload["battery"]["capacity_kwh"] = "500"

    response = client().post(
        "/optimize-energy",
        json=payload,
    )
    assert_invalid_400(response)


def test_custom_request_id_round_trip():
    request_id = "gridwise-hardening-request-id"

    response = client().get(
        "/health",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_400_response_does_not_leak_traceback():
    payload = make_payload()
    payload["hours"] = []

    response = client().post(
        "/optimize-energy",
        json=payload,
    )

    assert response.status_code == 400
    assert "traceback" not in str(response.json()).lower()


def test_422_response_does_not_leak_traceback():
    payload = make_payload()
    payload["battery"]["capacity_kwh"] = -1

    response = client().post(
        "/optimize-energy",
        json=payload,
    )

    assert response.status_code == 422
    assert "traceback" not in str(response.json()).lower()


def test_negative_tariff_is_not_arbitrarily_rejected():
    payload = make_payload()
    payload["hours"][0]["tariff_bdt_per_kwh"] = -1.0

    response = client().post(
        "/optimize-energy",
        json=payload,
    )

    # Phase 1 has no optimizer yet, so reaching the
    # pipeline boundary proves request validation accepted it.
    assert_phase1_boundary(response)


def test_repeated_valid_requests_do_not_leak_state():
    c = client()

    for index in range(30):
        payload = make_payload()
        payload["scenario_id"] = f"REPEAT-{index}"

        response = c.post(
            "/optimize-energy",
            json=payload,
        )

        assert_phase1_boundary(response)


def test_repeated_invalid_requests_remain_controlled():
    c = client()

    for _ in range(30):
        payload = make_payload()
        payload["operator_notes"] = []

        response = c.post(
            "/optimize-energy",
            json=payload,
        )

        assert_invalid_400(response)


def _health_once(_):
    response = client().get("/health")
    return (
        response.status_code,
        response.json(),
        "X-Request-ID" in response.headers,
    )


def test_concurrent_health_requests_are_stable():
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                _health_once,
                range(32),
            )
        )

    assert len(results) == 32

    for status, body, has_request_id in results:
        assert status == 200
        assert body == {"status": "ok"}
        assert has_request_id is True


def test_unknown_route_is_controlled_404():
    response = client().get("/definitely-not-a-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(
        "application/json"
    )


def test_wrong_method_is_controlled_405():
    response = client().post("/health")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith(
        "application/json"
    )