from __future__ import annotations

import math
from typing import Any


SUPPORTED_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


class DirectiveGuardrailError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def _is_real_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _clean_hours(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise DirectiveGuardrailError(
            ["hours must be an array"]
        )

    cleaned: list[int] = []

    for hour in value:
        if (
            not isinstance(hour, int)
            or isinstance(hour, bool)
        ):
            raise DirectiveGuardrailError(
                ["hours must contain only integers"]
            )

        if hour < 0 or hour > 23:
            raise DirectiveGuardrailError(
                [f"hour out of range: {hour}"]
            )

        cleaned.append(hour)

    # Harmless normalization allowed by our design:
    # deduplicate and sort valid hour integers.
    return sorted(set(cleaned))


def _expect_zero(value: Any, field: str) -> None:
    if not _is_real_number(value):
        raise DirectiveGuardrailError(
            [f"{field} must be a finite number"]
        )

    if abs(float(value)) > 1e-12:
        raise DirectiveGuardrailError(
            [f"{field} must be 0 when unused"]
        )


def canonicalize_interpretations(
    raw: Any,
    *,
    note_count: int,
    battery_capacity_kwh: float,
) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        raise DirectiveGuardrailError(
            ["model output must be an object"]
        )

    items = raw.get("items")

    if not isinstance(items, list):
        raise DirectiveGuardrailError(
            ["model output must contain items array"]
        )

    if len(items) != note_count:
        raise DirectiveGuardrailError(
            [
                "model output must contain exactly one item "
                "per operator note"
            ]
        )

    if (
        not _is_real_number(battery_capacity_kwh)
        or float(battery_capacity_kwh) < 0
    ):
        raise DirectiveGuardrailError(
            ["battery capacity context is invalid"]
        )

    capacity = float(battery_capacity_kwh)
    by_index: dict[int, dict[str, Any]] = {}
    issues: list[str] = []

    for position, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise DirectiveGuardrailError(
                    ["interpretation item must be an object"]
                )

            index = item.get("note_index")

            if (
                not isinstance(index, int)
                or isinstance(index, bool)
            ):
                raise DirectiveGuardrailError(
                    ["note_index must be an integer"]
                )

            if index < 0 or index >= note_count:
                raise DirectiveGuardrailError(
                    [f"note_index out of range: {index}"]
                )

            if index in by_index:
                raise DirectiveGuardrailError(
                    [f"duplicate note_index: {index}"]
                )

            applies = item.get("applies")

            if not isinstance(applies, bool):
                raise DirectiveGuardrailError(
                    ["applies must be boolean"]
                )

            directive_type = item.get("directive_type")

            if directive_type not in SUPPORTED_DIRECTIVES:
                raise DirectiveGuardrailError(
                    [
                        "unsupported directive_type: "
                        f"{directive_type!r}"
                    ]
                )

            hours = _clean_hours(item.get("hours"))

            solar_mode = item.get(
                "solar_quantity_mode"
            )
            solar_value = item.get(
                "solar_quantity_value"
            )
            reserve_mode = item.get(
                "reserve_quantity_mode"
            )
            reserve_value = item.get(
                "reserve_quantity_value"
            )
            max_grid = item.get("max_grid_kwh")

            explanation = item.get("explanation")

            if not isinstance(explanation, str):
                raise DirectiveGuardrailError(
                    ["explanation must be a string"]
                )

            explanation = explanation.strip()

            if not explanation:
                raise DirectiveGuardrailError(
                    ["explanation must not be blank"]
                )

            if directive_type == "no_op":
                if applies is not False:
                    raise DirectiveGuardrailError(
                        ["no_op must use applies=false"]
                    )

                if hours:
                    raise DirectiveGuardrailError(
                        ["no_op must not contain hours"]
                    )

                if solar_mode != "none":
                    raise DirectiveGuardrailError(
                        [
                            "no_op must not contain "
                            "solar semantics"
                        ]
                    )

                if reserve_mode != "none":
                    raise DirectiveGuardrailError(
                        [
                            "no_op must not contain "
                            "reserve semantics"
                        ]
                    )

                _expect_zero(
                    solar_value,
                    "solar_quantity_value",
                )
                _expect_zero(
                    reserve_value,
                    "reserve_quantity_value",
                )
                _expect_zero(
                    max_grid,
                    "max_grid_kwh",
                )

                canonical = {
                    "note_index": index,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": explanation,
                }

            else:
                if applies is not True:
                    raise DirectiveGuardrailError(
                        [
                            f"{directive_type} must use "
                            "applies=true"
                        ]
                    )

                if not hours:
                    raise DirectiveGuardrailError(
                        [
                            f"{directive_type} requires "
                            "at least one hour"
                        ]
                    )

                if directive_type == "solar_reduction":
                    if solar_mode not in {
                        "remaining_fraction",
                        "reduction_fraction",
                    }:
                        raise DirectiveGuardrailError(
                            [
                                "solar_reduction requires "
                                "remaining_fraction or "
                                "reduction_fraction"
                            ]
                        )

                    if not _is_real_number(solar_value):
                        raise DirectiveGuardrailError(
                            [
                                "solar quantity must be "
                                "a finite number"
                            ]
                        )

                    quantity = float(solar_value)

                    if quantity < 0 or quantity > 1:
                        raise DirectiveGuardrailError(
                            [
                                "solar fraction must be "
                                "between 0 and 1"
                            ]
                        )

                    if solar_mode == "remaining_fraction":
                        factor = quantity
                    else:
                        factor = 1.0 - quantity

                    factor = round(factor, 12)

                    _expect_zero(
                        reserve_value,
                        "reserve_quantity_value",
                    )
                    _expect_zero(
                        max_grid,
                        "max_grid_kwh",
                    )

                    if reserve_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                "solar_reduction must not "
                                "contain reserve semantics"
                            ]
                        )

                    canonical = {
                        "note_index": index,
                        "applies": True,
                        "directive_type": directive_type,
                        "structured_adjustment": {
                            "hours": hours,
                            "factor": factor,
                        },
                        "explanation": explanation,
                    }

                elif directive_type == (
                    "minimum_battery_reserve"
                ):
                    if reserve_mode not in {
                        "absolute_kwh",
                        "capacity_fraction",
                    }:
                        raise DirectiveGuardrailError(
                            [
                                "minimum_battery_reserve "
                                "requires absolute_kwh or "
                                "capacity_fraction"
                            ]
                        )

                    if not _is_real_number(
                        reserve_value
                    ):
                        raise DirectiveGuardrailError(
                            [
                                "reserve quantity must be "
                                "a finite number"
                            ]
                        )

                    quantity = float(reserve_value)

                    if reserve_mode == "absolute_kwh":
                        minimum_kwh = quantity
                    else:
                        if quantity < 0 or quantity > 1:
                            raise DirectiveGuardrailError(
                                [
                                    "capacity fraction must "
                                    "be between 0 and 1"
                                ]
                            )

                        minimum_kwh = (
                            capacity * quantity
                        )

                    if (
                        minimum_kwh < 0
                        or minimum_kwh > capacity
                    ):
                        raise DirectiveGuardrailError(
                            [
                                "battery reserve must be "
                                "between 0 and capacity"
                            ]
                        )

                    _expect_zero(
                        solar_value,
                        "solar_quantity_value",
                    )
                    _expect_zero(
                        max_grid,
                        "max_grid_kwh",
                    )

                    if solar_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                "reserve directive must not "
                                "contain solar semantics"
                            ]
                        )

                    canonical = {
                        "note_index": index,
                        "applies": True,
                        "directive_type": directive_type,
                        "structured_adjustment": {
                            "hours": hours,
                            "minimum_energy_kwh": round(
                                minimum_kwh,
                                12,
                            ),
                        },
                        "explanation": explanation,
                    }

                elif directive_type in {
                    "no_charge_window",
                    "no_discharge_window",
                }:
                    if solar_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                f"{directive_type} must not "
                                "contain solar semantics"
                            ]
                        )

                    if reserve_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                f"{directive_type} must not "
                                "contain reserve semantics"
                            ]
                        )

                    _expect_zero(
                        solar_value,
                        "solar_quantity_value",
                    )
                    _expect_zero(
                        reserve_value,
                        "reserve_quantity_value",
                    )
                    _expect_zero(
                        max_grid,
                        "max_grid_kwh",
                    )

                    canonical = {
                        "note_index": index,
                        "applies": True,
                        "directive_type": directive_type,
                        "structured_adjustment": {
                            "hours": hours,
                        },
                        "explanation": explanation,
                    }

                elif directive_type == "max_grid_window":
                    if not _is_real_number(max_grid):
                        raise DirectiveGuardrailError(
                            [
                                "max_grid_kwh must be "
                                "a finite number"
                            ]
                        )

                    max_grid_value = float(max_grid)

                    if max_grid_value < 0:
                        raise DirectiveGuardrailError(
                            [
                                "max_grid_kwh must be "
                                "non-negative"
                            ]
                        )

                    if solar_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                "max_grid_window must not "
                                "contain solar semantics"
                            ]
                        )

                    if reserve_mode != "none":
                        raise DirectiveGuardrailError(
                            [
                                "max_grid_window must not "
                                "contain reserve semantics"
                            ]
                        )

                    _expect_zero(
                        solar_value,
                        "solar_quantity_value",
                    )
                    _expect_zero(
                        reserve_value,
                        "reserve_quantity_value",
                    )

                    canonical = {
                        "note_index": index,
                        "applies": True,
                        "directive_type": directive_type,
                        "structured_adjustment": {
                            "hours": hours,
                            "max_grid_kwh": max_grid_value,
                        },
                        "explanation": explanation,
                    }

                else:
                    raise DirectiveGuardrailError(
                        [
                            "unreachable unsupported "
                            f"directive: {directive_type}"
                        ]
                    )

            by_index[index] = canonical

        except DirectiveGuardrailError as exc:
            prefix = (
                f"item position {position}: "
            )

            issues.extend(
                prefix + issue
                for issue in exc.issues
            )

    expected = set(range(note_count))
    actual = set(by_index)

    if actual != expected:
        missing = sorted(expected - actual)

        if missing:
            issues.append(
                f"missing note_index values: {missing}"
            )

    if issues:
        raise DirectiveGuardrailError(issues)

    return [
        by_index[index]
        for index in range(note_count)
    ]