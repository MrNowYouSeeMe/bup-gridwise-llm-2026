
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import linprog


HOURS = 24
G0 = 0
S0 = 24
X0 = 48
E0 = 72
VAR_COUNT = 96


class OptimizationError(RuntimeError):
    pass


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise OptimizationError(f"{label} must be numeric")
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise OptimizationError(f"{label} must be numeric") from exc
    if not math.isfinite(out):
        raise OptimizationError(f"{label} must be finite")
    return out


def _profiles(payload, interpretations):
    hours = sorted(payload.hours, key=lambda item: item.hour)
    if len(hours) != HOURS:
        raise OptimizationError("exactly 24 hours are required")

    original_solar = [
        _finite(item.solar_kwh, f"hour {item.hour} solar")
        for item in hours
    ]
    effective_solar = list(original_solar)

    base_min = _finite(
        payload.battery.minimum_energy_kwh,
        "battery minimum",
    )
    active_min = [base_min] * HOURS

    no_charge = [False] * HOURS
    no_discharge = [False] * HOURS
    grid_cap: list[float | None] = [None] * HOURS

    for entry in interpretations:
        if not entry["applies"]:
            continue

        kind = entry["directive_type"]
        adj = entry["structured_adjustment"]
        listed = adj["hours"]

        if kind == "solar_reduction":
            factor = _finite(adj["factor"], "solar factor")
            for hour in listed:
                # If multiple hard solar caps overlap, satisfying all of
                # them means using the most restrictive allowed fraction.
                candidate = original_solar[hour] * factor
                effective_solar[hour] = min(
                    effective_solar[hour],
                    candidate,
                )

        elif kind == "minimum_battery_reserve":
            minimum = _finite(
                adj["minimum_energy_kwh"],
                "directive minimum battery reserve",
            )
            for hour in listed:
                active_min[hour] = max(
                    active_min[hour],
                    minimum,
                )

        elif kind == "no_charge_window":
            for hour in listed:
                no_charge[hour] = True

        elif kind == "no_discharge_window":
            for hour in listed:
                no_discharge[hour] = True

        elif kind == "max_grid_window":
            cap = _finite(
                adj["max_grid_kwh"],
                "directive max grid",
            )
            for hour in listed:
                if grid_cap[hour] is None:
                    grid_cap[hour] = cap
                else:
                    grid_cap[hour] = min(
                        grid_cap[hour],
                        cap,
                    )

        elif kind == "no_op":
            continue

        else:
            raise OptimizationError(
                f"unsupported directive: {kind}"
            )

    return (
        hours,
        effective_solar,
        active_min,
        no_charge,
        no_discharge,
        grid_cap,
    )


def _normalize(value: float) -> float:
    value = float(value)
    if abs(value) < 1e-8:
        return 0.0
    return value


def solve_schedule(payload, interpretations):
    (
        hours,
        effective_solar,
        active_min,
        no_charge,
        no_discharge,
        grid_cap,
    ) = _profiles(payload, interpretations)

    demand = [
        _finite(item.demand_kwh, f"hour {item.hour} demand")
        for item in hours
    ]
    tariff = [
        _finite(
            item.tariff_bdt_per_kwh,
            f"hour {item.hour} tariff",
        )
        for item in hours
    ]

    capacity = _finite(
        payload.battery.capacity_kwh,
        "battery capacity",
    )
    initial = _finite(
        payload.battery.initial_energy_kwh,
        "battery initial energy",
    )
    max_charge = _finite(
        payload.battery.max_charge_kwh_per_hour,
        "battery charge rate",
    )
    max_discharge = _finite(
        payload.battery.max_discharge_kwh_per_hour,
        "battery discharge rate",
    )

    objective = np.zeros(VAR_COUNT, dtype=float)
    objective[G0:G0 + HOURS] = tariff

    bounds: list[tuple[float | None, float | None]] = []

    for hour in range(HOURS):
        bounds.append((0.0, grid_cap[hour]))

    for hour in range(HOURS):
        bounds.append((0.0, effective_solar[hour]))

    for hour in range(HOURS):
        lower = 0.0 if no_discharge[hour] else -max_discharge
        upper = 0.0 if no_charge[hour] else max_charge
        bounds.append((lower, upper))

    for hour in range(HOURS):
        bounds.append((active_min[hour], capacity))

    a_eq: list[np.ndarray] = []
    b_eq: list[float] = []

    # Energy balance:
    # grid + solar = demand + signed_battery_change
    # x > 0 charge, x < 0 discharge.
    for hour in range(HOURS):
        row = np.zeros(VAR_COUNT, dtype=float)
        row[G0 + hour] = 1.0
        row[S0 + hour] = 1.0
        row[X0 + hour] = -1.0
        a_eq.append(row)
        b_eq.append(demand[hour])

    # Battery transition.
    for hour in range(HOURS):
        row = np.zeros(VAR_COUNT, dtype=float)
        row[E0 + hour] = 1.0
        row[X0 + hour] = -1.0

        if hour == 0:
            b_value = initial
        else:
            row[E0 + hour - 1] = -1.0
            b_value = 0.0

        a_eq.append(row)
        b_eq.append(b_value)

    # End-of-day neutrality.
    final_row = np.zeros(VAR_COUNT, dtype=float)
    final_row[E0 + HOURS - 1] = 1.0
    a_eq.append(final_row)
    b_eq.append(initial)

    result = linprog(
        objective,
        A_eq=np.asarray(a_eq),
        b_eq=np.asarray(b_eq),
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        message = result.message or "optimization failed"
        raise OptimizationError(
            f"no valid optimal schedule found: {message}"
        )

    g = result.x[G0:G0 + HOURS]
    s = result.x[S0:S0 + HOURS]
    x = result.x[X0:X0 + HOURS]

    plan = []
    energy = initial

    for hour in range(HOURS):
        battery_delta = _normalize(x[hour])
        solar_used = _normalize(s[hour])

        # Reconstruct grid and battery state from the physical
        # equations instead of independently rounding solver vars.
        grid = _normalize(
            demand[hour] + battery_delta - solar_used
        )
        energy = _normalize(energy + battery_delta)

        if grid < 0.0 and abs(grid) < 1e-7:
            grid = 0.0

        if battery_delta > 1e-8:
            action = "charge"
            battery_kwh = battery_delta
        elif battery_delta < -1e-8:
            action = "discharge"
            battery_kwh = -battery_delta
        else:
            action = "idle"
            battery_kwh = 0.0
            battery_delta = 0.0

        plan.append(
            {
                "hour": hour,
                "grid_kwh": float(grid),
                "solar_used_kwh": float(solar_used),
                "battery_action": action,
                "battery_kwh": float(battery_kwh),
                "battery_energy_after_kwh": float(energy),
            }
        )

    return plan
