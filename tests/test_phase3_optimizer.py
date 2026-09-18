
import pytest

from app.optimizer import (
    OptimizationError,
    solve_schedule,
)
from app.replay import validate_schedule
from app.schemas import ScenarioRequest


def make_payload(
    *,
    demand=100.0,
    solar=20.0,
    tariff=10.0,
    capacity=200.0,
    initial=100.0,
    minimum=20.0,
    charge_rate=50.0,
    discharge_rate=50.0,
):
    return ScenarioRequest.model_validate(
        {
            "scenario_id": "EDGE",
            "operator_notes": ["No scheduling change."],
            "hours": [
                {
                    "hour": h,
                    "demand_kwh": demand,
                    "solar_kwh": solar,
                    "tariff_bdt_per_kwh": tariff,
                }
                for h in range(24)
            ],
            "battery": {
                "capacity_kwh": capacity,
                "initial_energy_kwh": initial,
                "minimum_energy_kwh": minimum,
                "max_charge_kwh_per_hour": charge_rate,
                "max_discharge_kwh_per_hour": discharge_rate,
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
            "explanation": "No scheduling effect.",
        }
    ]


def directive(kind, adjustment):
    return [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": kind,
            "structured_adjustment": adjustment,
            "explanation": "test",
        }
    ]


def test_no_op_produces_valid_neutral_schedule():
    payload = make_payload()
    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)

    assert len(plan) == 24
    assert plan[-1]["battery_energy_after_kwh"] == pytest.approx(
        100.0,
        abs=1e-6,
    )


def test_zero_charge_and_discharge_rates():
    payload = make_payload(
        charge_rate=0.0,
        discharge_rate=0.0,
    )
    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)

    assert all(
        row["battery_action"] == "idle"
        for row in plan
    )


def test_initial_at_capacity():
    payload = make_payload(
        capacity=200,
        initial=200,
        minimum=20,
    )
    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)


def test_initial_at_minimum():
    payload = make_payload(
        capacity=200,
        initial=20,
        minimum=20,
    )
    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)


def test_solar_surplus_can_be_curtailed():
    payload = make_payload(
        demand=20,
        solar=200,
        capacity=100,
        initial=50,
        minimum=10,
    )
    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)

    assert all(
        row["solar_used_kwh"] <= 200 + 1e-6
        for row in plan
    )


def test_solar_factor_zero():
    payload = make_payload()
    interpretations = directive(
        "solar_reduction",
        {
            "hours": [12],
            "factor": 0.0,
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[12]["solar_used_kwh"] == pytest.approx(
        0.0,
        abs=1e-7,
    )


def test_solar_factor_one():
    payload = make_payload()
    interpretations = directive(
        "solar_reduction",
        {
            "hours": [12],
            "factor": 1.0,
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )


def test_no_charge_window_is_respected():
    payload = make_payload()
    interpretations = directive(
        "no_charge_window",
        {
            "hours": [2, 3, 4],
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    for hour in (2, 3, 4):
        assert not (
            plan[hour]["battery_action"] == "charge"
            and plan[hour]["battery_kwh"] > 1e-7
        )


def test_no_discharge_window_is_respected():
    payload = make_payload()
    interpretations = directive(
        "no_discharge_window",
        {
            "hours": [18, 19],
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    for hour in (18, 19):
        assert not (
            plan[hour]["battery_action"] == "discharge"
            and plan[hour]["battery_kwh"] > 1e-7
        )


def test_reserve_directive_is_respected():
    payload = make_payload()
    interpretations = directive(
        "minimum_battery_reserve",
        {
            "hours": [18, 19, 20],
            "minimum_energy_kwh": 120.0,
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    for hour in (18, 19, 20):
        assert (
            plan[hour]["battery_energy_after_kwh"]
            >= 120 - 1e-6
        )


def test_grid_cap_is_respected():
    payload = make_payload(
        demand=100,
        solar=20,
        capacity=200,
        initial=100,
    )

    interpretations = directive(
        "max_grid_window",
        {
            "hours": [18],
            "max_grid_kwh": 70.0,
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[18]["grid_kwh"] <= 70 + 1e-6


def test_grid_cap_can_force_precharge():
    payload = make_payload(
        demand=10,
        solar=0,
        tariff=10,
        capacity=100,
        initial=0,
        minimum=0,
        charge_rate=50,
        discharge_rate=50,
    )

    payload.hours[18].demand_kwh = 50

    interpretations = directive(
        "max_grid_window",
        {
            "hours": [18],
            "max_grid_kwh": 0.0,
        },
    )

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[18]["grid_kwh"] == pytest.approx(
        0.0,
        abs=1e-6,
    )
    assert plan[18]["battery_action"] == "discharge"
    assert plan[18]["battery_kwh"] == pytest.approx(
        50.0,
        abs=1e-6,
    )

    assert any(
        row["battery_action"] == "charge"
        and row["hour"] < 18
        for row in plan
    )


def test_overlapping_reserves_use_strictest_minimum():
    payload = make_payload()
    interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {
                "hours": [18, 19],
                "minimum_energy_kwh": 90,
            },
            "explanation": "a",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {
                "hours": [19, 20],
                "minimum_energy_kwh": 130,
            },
            "explanation": "b",
        },
    ]

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert (
        plan[19]["battery_energy_after_kwh"]
        >= 130 - 1e-6
    )


def test_overlapping_grid_caps_use_strictest_cap():
    payload = make_payload()
    interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {
                "hours": [18],
                "max_grid_kwh": 90,
            },
            "explanation": "a",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {
                "hours": [18],
                "max_grid_kwh": 75,
            },
            "explanation": "b",
        },
    ]

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[18]["grid_kwh"] <= 75 + 1e-6


def test_overlapping_solar_caps_use_strictest_fraction():
    payload = make_payload(
        demand=100,
        solar=100,
        capacity=100,
        initial=50,
        minimum=10,
        charge_rate=0,
        discharge_rate=0,
    )

    interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {
                "hours": [12],
                "factor": 0.8,
            },
            "explanation": "a",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {
                "hours": [12],
                "factor": 0.3,
            },
            "explanation": "b",
        },
    ]

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[12]["solar_used_kwh"] <= 30 + 1e-6


def test_no_charge_and_no_discharge_same_hour_forces_idle():
    payload = make_payload()
    interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {
                "hours": [10],
            },
            "explanation": "a",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {
                "hours": [10],
            },
            "explanation": "b",
        },
    ]

    plan = solve_schedule(payload, interpretations)
    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    assert plan[10]["battery_action"] == "idle"
    assert plan[10]["battery_kwh"] == pytest.approx(
        0.0,
        abs=1e-7,
    )


def test_infeasible_grid_cap_fails_cleanly():
    payload = make_payload(
        demand=100,
        solar=0,
        capacity=0,
        initial=0,
        minimum=0,
        charge_rate=0,
        discharge_rate=0,
    )

    interpretations = directive(
        "max_grid_window",
        {
            "hours": [5],
            "max_grid_kwh": 50,
        },
    )

    with pytest.raises(OptimizationError):
        solve_schedule(
            payload,
            interpretations,
        )


def test_negative_tariff_remains_bounded():
    payload = make_payload(
        demand=100,
        solar=20,
        capacity=100,
        initial=50,
        minimum=0,
    )
    payload.hours[0].tariff_bdt_per_kwh = -5

    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)


def test_large_but_finite_values():
    payload = make_payload(
        demand=1_000_000,
        solar=300_000,
        tariff=1000,
        capacity=500_000,
        initial=250_000,
        minimum=100_000,
        charge_rate=100_000,
        discharge_rate=100_000,
    )

    plan = solve_schedule(payload, no_op())
    validate_schedule(payload, no_op(), plan)
