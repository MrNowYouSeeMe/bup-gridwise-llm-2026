
from copy import deepcopy

import pytest

from app.optimizer import solve_schedule
from app.replay import (
    ReplayValidationError,
    validate_schedule,
)
from app.schemas import ScenarioRequest


def payload():
    return ScenarioRequest.model_validate(
        {
            "scenario_id": "REPLAY",
            "operator_notes": ["No scheduling change."],
            "hours": [
                {
                    "hour": h,
                    "demand_kwh": 100.0,
                    "solar_kwh": 20.0,
                    "tariff_bdt_per_kwh": 10.0,
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
    )


def no_op():
    return [
        {
            "note_index": 0,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "none",
        }
    ]


def valid():
    p = payload()
    d = no_op()
    return p, d, solve_schedule(p, d)


def test_replay_rejects_missing_hour():
    p, d, plan = valid()

    with pytest.raises(ReplayValidationError):
        validate_schedule(
            p,
            d,
            plan[:-1],
        )


def test_replay_rejects_duplicate_hour():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[23]["hour"] = 22

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_negative_grid():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[0]["grid_kwh"] = -5

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_solar_overuse():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[0]["solar_used_kwh"] = 25

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_energy_balance_error():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[0]["grid_kwh"] += 1

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_bad_battery_transition():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[0]["battery_energy_after_kwh"] += 1

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_idle_with_nonzero_battery():
    p, d, plan = valid()
    bad = deepcopy(plan)

    bad[0]["battery_action"] = "idle"
    bad[0]["battery_kwh"] = 1

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_charge_rate_violation():
    p, d, plan = valid()
    bad = deepcopy(plan)

    bad[0]["battery_action"] = "charge"
    bad[0]["battery_kwh"] = 60
    bad[0]["battery_energy_after_kwh"] = 160
    bad[0]["grid_kwh"] = 140

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_discharge_rate_violation():
    p, d, plan = valid()
    bad = deepcopy(plan)

    bad[0]["battery_action"] = "discharge"
    bad[0]["battery_kwh"] = 60
    bad[0]["battery_energy_after_kwh"] = 40
    bad[0]["grid_kwh"] = 20

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_no_charge_violation():
    p = payload()
    d = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {
                "hours": [0],
            },
            "explanation": "test",
        }
    ]

    plan = solve_schedule(p, d)
    bad = deepcopy(plan)

    bad[0] = {
        "hour": 0,
        "grid_kwh": 90.0,
        "solar_used_kwh": 20.0,
        "battery_action": "charge",
        "battery_kwh": 10.0,
        "battery_energy_after_kwh": 110.0,
    }

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_no_discharge_violation():
    p = payload()
    d = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {
                "hours": [0],
            },
            "explanation": "test",
        }
    ]

    plan = solve_schedule(p, d)
    bad = deepcopy(plan)

    bad[0] = {
        "hour": 0,
        "grid_kwh": 70.0,
        "solar_used_kwh": 20.0,
        "battery_action": "discharge",
        "battery_kwh": 10.0,
        "battery_energy_after_kwh": 90.0,
    }

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_reserve_violation():
    p = payload()
    d = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {
                "hours": [0],
                "minimum_energy_kwh": 95.0,
            },
            "explanation": "test",
        }
    ]

    plan = solve_schedule(p, d)
    bad = deepcopy(plan)

    bad[0] = {
        "hour": 0,
        "grid_kwh": 70.0,
        "solar_used_kwh": 20.0,
        "battery_action": "discharge",
        "battery_kwh": 10.0,
        "battery_energy_after_kwh": 90.0,
    }

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_grid_cap_violation():
    p = payload()
    d = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {
                "hours": [0],
                "max_grid_kwh": 75.0,
            },
            "explanation": "test",
        }
    ]

    plan = solve_schedule(p, d)
    bad = deepcopy(plan)
    bad[0]["grid_kwh"] = 80.0

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_final_neutrality_break():
    p, d, plan = valid()
    bad = deepcopy(plan)

    bad[-1]["battery_energy_after_kwh"] += 1

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)


def test_replay_rejects_nan():
    p, d, plan = valid()
    bad = deepcopy(plan)
    bad[0]["grid_kwh"] = float("nan")

    with pytest.raises(ReplayValidationError):
        validate_schedule(p, d, bad)
