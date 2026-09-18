
from __future__ import annotations

import math
from typing import Any


HOURS = 24
ATOL = 1e-5


class ReplayValidationError(RuntimeError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _profiles(payload, interpretations):
    hours = sorted(payload.hours, key=lambda item: item.hour)

    original_solar = [
        float(item.solar_kwh)
        for item in hours
    ]
    effective_solar = list(original_solar)

    base_min = float(
        payload.battery.minimum_energy_kwh
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
            factor = float(adj["factor"])
            for hour in listed:
                effective_solar[hour] = min(
                    effective_solar[hour],
                    original_solar[hour] * factor,
                )

        elif kind == "minimum_battery_reserve":
            minimum = float(
                adj["minimum_energy_kwh"]
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
            cap = float(adj["max_grid_kwh"])
            for hour in listed:
                if grid_cap[hour] is None:
                    grid_cap[hour] = cap
                else:
                    grid_cap[hour] = min(
                        grid_cap[hour],
                        cap,
                    )

        elif kind == "no_op":
            pass

        else:
            raise ReplayValidationError(
                [f"unsupported directive: {kind}"]
            )

    return (
        hours,
        effective_solar,
        active_min,
        no_charge,
        no_discharge,
        grid_cap,
    )


def validate_schedule(
    payload,
    interpretations,
    hourly_plan,
    *,
    atol: float = ATOL,
):
    issues: list[str] = []

    if not isinstance(hourly_plan, list):
        raise ReplayValidationError(
            ["hourly_plan must be an array"]
        )

    if len(hourly_plan) != HOURS:
        issues.append(
            "hourly_plan must contain exactly 24 entries"
        )

    if issues:
        raise ReplayValidationError(issues)

    try:
        (
            hours,
            effective_solar,
            active_min,
            no_charge,
            no_discharge,
            grid_cap,
        ) = _profiles(payload, interpretations)
    except Exception as exc:
        if isinstance(exc, ReplayValidationError):
            raise
        raise ReplayValidationError(
            ["could not compile directive constraints"]
        ) from exc

    seen: set[int] = set()
    by_hour: dict[int, dict[str, Any]] = {}

    for position, row in enumerate(hourly_plan):
        if not isinstance(row, dict):
            issues.append(
                f"plan position {position}: entry must be an object"
            )
            continue

        hour = row.get("hour")

        if (
            not isinstance(hour, int)
            or isinstance(hour, bool)
            or hour < 0
            or hour > 23
        ):
            issues.append(
                f"plan position {position}: invalid hour"
            )
            continue

        if hour in seen:
            issues.append(f"duplicate plan hour: {hour}")
            continue

        seen.add(hour)
        by_hour[hour] = row

    if seen != set(range(HOURS)):
        missing = sorted(set(range(HOURS)) - seen)
        if missing:
            issues.append(
                f"missing plan hours: {missing}"
            )

    if issues:
        raise ReplayValidationError(issues)

    capacity = float(payload.battery.capacity_kwh)
    initial = float(
        payload.battery.initial_energy_kwh
    )
    max_charge = float(
        payload.battery.max_charge_kwh_per_hour
    )
    max_discharge = float(
        payload.battery.max_discharge_kwh_per_hour
    )

    previous_energy = initial

    for hour in range(HOURS):
        source = hours[hour]
        row = by_hour[hour]

        numeric_fields = (
            "grid_kwh",
            "solar_used_kwh",
            "battery_kwh",
            "battery_energy_after_kwh",
        )

        values: dict[str, float] = {}

        for field in numeric_fields:
            value = row.get(field)

            if not _finite(value):
                issues.append(
                    f"hour {hour}: {field} must be finite numeric"
                )
                continue

            values[field] = float(value)

        if len(values) != len(numeric_fields):
            continue

        grid = values["grid_kwh"]
        solar = values["solar_used_kwh"]
        battery_kwh = values["battery_kwh"]
        energy_after = values[
            "battery_energy_after_kwh"
        ]

        action = row.get("battery_action")

        if action not in {
            "charge",
            "discharge",
            "idle",
        }:
            issues.append(
                f"hour {hour}: invalid battery_action"
            )
            continue

        if grid < -atol:
            issues.append(
                f"hour {hour}: grid_kwh is negative"
            )

        if solar < -atol:
            issues.append(
                f"hour {hour}: solar_used_kwh is negative"
            )

        if battery_kwh < -atol:
            issues.append(
                f"hour {hour}: battery_kwh is negative"
            )

        if solar > effective_solar[hour] + atol:
            issues.append(
                f"hour {hour}: solar exceeds effective availability"
            )

        if action == "idle":
            if abs(battery_kwh) > atol:
                issues.append(
                    f"hour {hour}: idle requires battery_kwh=0"
                )
            signed_delta = 0.0

        elif action == "charge":
            signed_delta = battery_kwh

            if battery_kwh > max_charge + atol:
                issues.append(
                    f"hour {hour}: charge rate exceeded"
                )

            if no_charge[hour] and battery_kwh > atol:
                issues.append(
                    f"hour {hour}: charging forbidden by directive"
                )

        else:
            signed_delta = -battery_kwh

            if battery_kwh > max_discharge + atol:
                issues.append(
                    f"hour {hour}: discharge rate exceeded"
                )

            if (
                no_discharge[hour]
                and battery_kwh > atol
            ):
                issues.append(
                    f"hour {hour}: discharging forbidden by directive"
                )

        expected_energy = (
            previous_energy + signed_delta
        )

        if abs(
            energy_after - expected_energy
        ) > atol:
            issues.append(
                f"hour {hour}: battery transition mismatch"
            )

        if energy_after < active_min[hour] - atol:
            issues.append(
                f"hour {hour}: active minimum reserve violated"
            )

        if energy_after > capacity + atol:
            issues.append(
                f"hour {hour}: battery capacity exceeded"
            )

        if (
            grid_cap[hour] is not None
            and grid > grid_cap[hour] + atol
        ):
            issues.append(
                f"hour {hour}: grid cap violated"
            )

        demand = float(source.demand_kwh)

        if action == "charge":
            lhs = grid + solar
            rhs = demand + battery_kwh
        elif action == "discharge":
            lhs = grid + solar + battery_kwh
            rhs = demand
        else:
            lhs = grid + solar
            rhs = demand

        if abs(lhs - rhs) > atol:
            issues.append(
                f"hour {hour}: energy balance mismatch"
            )

        previous_energy = energy_after

    if abs(previous_energy - initial) > atol:
        issues.append(
            "final battery energy does not equal initial energy"
        )

    if issues:
        raise ReplayValidationError(issues)


def recalculate_metrics(payload, hourly_plan):
    hours = sorted(payload.hours, key=lambda item: item.hour)
    tariff = {
        item.hour: float(item.tariff_bdt_per_kwh)
        for item in hours
    }

    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for row in hourly_plan:
        hour = int(row["hour"])
        grid = float(row["grid_kwh"])

        total_grid += grid
        total_cost += grid * tariff[hour]
        peak_grid = max(peak_grid, grid)

    def clean(value: float) -> float:
        if abs(value) < 1e-9:
            return 0.0
        rounded = round(value, 10)
        if abs(rounded - round(rounded)) < 1e-9:
            return float(round(rounded))
        return float(rounded)

    return {
        "total_grid_kwh": clean(total_grid),
        "total_cost_bdt": clean(total_cost),
        "peak_grid_kwh": clean(peak_grid),
    }
