
import random

from app.optimizer import solve_schedule
from app.replay import validate_schedule
from app.schemas import ScenarioRequest


def make_interpretation(
    index,
    directive_type,
    adjustment,
):
    return {
        "note_index": index,
        "applies": directive_type != "no_op",
        "directive_type": directive_type,
        "structured_adjustment": (
            None
            if directive_type == "no_op"
            else adjustment
        ),
        "explanation": "randomized test",
    }


def test_seeded_randomized_hidden_like_regression():
    rng = random.Random(20260918)

    for case_no in range(120):
        capacity = rng.uniform(80, 500)
        minimum = rng.uniform(0, capacity * 0.35)
        initial = rng.uniform(
            max(minimum, capacity * 0.35),
            capacity * 0.8,
        )
        charge = rng.uniform(10, capacity * 0.25)
        discharge = rng.uniform(10, capacity * 0.25)

        hours = []

        for hour in range(24):
            demand = rng.uniform(40, 250)
            solar = (
                rng.uniform(0, 180)
                if 6 <= hour <= 17
                else 0.0
            )
            tariff = rng.uniform(3, 35)

            hours.append(
                {
                    "hour": hour,
                    "demand_kwh": demand,
                    "solar_kwh": solar,
                    "tariff_bdt_per_kwh": tariff,
                }
            )

        payload = ScenarioRequest.model_validate(
            {
                "scenario_id": f"FUZZ-{case_no}",
                "operator_notes": ["synthetic"],
                "hours": hours,
                "battery": {
                    "capacity_kwh": capacity,
                    "initial_energy_kwh": initial,
                    "minimum_energy_kwh": minimum,
                    "max_charge_kwh_per_hour": charge,
                    "max_discharge_kwh_per_hour": discharge,
                },
            }
        )

        choice = case_no % 6

        if choice == 0:
            interpretations = [
                make_interpretation(
                    0,
                    "no_op",
                    None,
                )
            ]

        elif choice == 1:
            start = rng.randint(0, 20)
            interpretations = [
                make_interpretation(
                    0,
                    "no_charge_window",
                    {
                        "hours": list(
                            range(start, start + 3)
                        )
                    },
                )
            ]

        elif choice == 2:
            start = rng.randint(0, 20)
            interpretations = [
                make_interpretation(
                    0,
                    "no_discharge_window",
                    {
                        "hours": list(
                            range(start, start + 3)
                        )
                    },
                )
            ]

        elif choice == 3:
            start = rng.randint(7, 15)
            factor = rng.uniform(0.05, 0.95)

            interpretations = [
                make_interpretation(
                    0,
                    "solar_reduction",
                    {
                        "hours": list(
                            range(start, start + 2)
                        ),
                        "factor": factor,
                    },
                )
            ]

        elif choice == 4:
            start = rng.randint(0, 20)
            reserve = rng.uniform(
                minimum,
                initial,
            )

            interpretations = [
                make_interpretation(
                    0,
                    "minimum_battery_reserve",
                    {
                        "hours": list(
                            range(start, start + 3)
                        ),
                        "minimum_energy_kwh": reserve,
                    },
                )
            ]

        else:
            # Safe cap: demand itself is always reachable with
            # solar curtailment and idle battery.
            start = rng.randint(0, 20)

            interpretations = [
                make_interpretation(
                    0,
                    "max_grid_window",
                    {
                        "hours": list(
                            range(start, start + 3)
                        ),
                        "max_grid_kwh": max(
                            hours[h]["demand_kwh"]
                            for h in range(
                                start,
                                start + 3,
                            )
                        ),
                    },
                )
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
