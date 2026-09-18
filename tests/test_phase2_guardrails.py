import pytest

from app.directives import (
    DirectiveGuardrailError,
    canonicalize_interpretations,
)


CAPACITY = 500.0


def item(
    *,
    note_index=0,
    applies=True,
    directive_type="no_charge_window",
    hours=None,
    solar_mode="none",
    solar_value=0,
    reserve_mode="none",
    reserve_value=0,
    max_grid=0,
    explanation="ok",
):
    if hours is None:
        hours = [14, 15]

    return {
        "note_index": note_index,
        "applies": applies,
        "directive_type": directive_type,
        "hours": hours,
        "solar_quantity_mode": solar_mode,
        "solar_quantity_value": solar_value,
        "reserve_quantity_mode": reserve_mode,
        "reserve_quantity_value": reserve_value,
        "max_grid_kwh": max_grid,
        "explanation": explanation,
    }


def canon(raw, note_count=1, capacity=CAPACITY):
    return canonicalize_interpretations(
        raw,
        note_count=note_count,
        battery_capacity_kwh=capacity,
    )


def test_no_charge_exact_shape():
    result = canon(
        {"items": [item()]}
    )[0]

    assert result["directive_type"] == (
        "no_charge_window"
    )
    assert result["structured_adjustment"] == {
        "hours": [14, 15],
    }


def test_no_discharge_exact_shape():
    result = canon(
        {
            "items": [
                item(
                    directive_type=(
                        "no_discharge_window"
                    )
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"] == {
        "hours": [14, 15],
    }


def test_solar_to_20_percent_becomes_point_2():
    result = canon(
        {
            "items": [
                item(
                    directive_type="solar_reduction",
                    hours=[13, 14],
                    solar_mode=(
                        "remaining_fraction"
                    ),
                    solar_value=0.2,
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"] == {
        "hours": [13, 14],
        "factor": 0.2,
    }


def test_solar_reduced_by_20_percent_becomes_point_8():
    result = canon(
        {
            "items": [
                item(
                    directive_type="solar_reduction",
                    hours=[13, 14],
                    solar_mode=(
                        "reduction_fraction"
                    ),
                    solar_value=0.2,
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"]["factor"] == 0.8


def test_eighty_percent_reduction_becomes_point_2():
    result = canon(
        {
            "items": [
                item(
                    directive_type="solar_reduction",
                    solar_mode=(
                        "reduction_fraction"
                    ),
                    solar_value=0.8,
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"]["factor"] == (
        0.2
    )


def test_absolute_reserve():
    result = canon(
        {
            "items": [
                item(
                    directive_type=(
                        "minimum_battery_reserve"
                    ),
                    hours=[18, 19, 20],
                    reserve_mode="absolute_kwh",
                    reserve_value=120,
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"] == {
        "hours": [18, 19, 20],
        "minimum_energy_kwh": 120.0,
    }


def test_capacity_fraction_reserve_is_deterministic():
    result = canon(
        {
            "items": [
                item(
                    directive_type=(
                        "minimum_battery_reserve"
                    ),
                    reserve_mode=(
                        "capacity_fraction"
                    ),
                    reserve_value=0.5,
                )
            ]
        },
        capacity=480,
    )[0]

    assert result["structured_adjustment"][
        "minimum_energy_kwh"
    ] == 240.0


def test_max_grid_exact_shape():
    result = canon(
        {
            "items": [
                item(
                    directive_type="max_grid_window",
                    hours=[19, 20],
                    max_grid=60,
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"] == {
        "hours": [19, 20],
        "max_grid_kwh": 60.0,
    }


def test_no_op_exact_semantics():
    result = canon(
        {
            "items": [
                item(
                    applies=False,
                    directive_type="no_op",
                    hours=[],
                )
            ]
        }
    )[0]

    assert result == {
        "note_index": 0,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "ok",
    }


def test_hours_sort_and_dedupe_is_harmless_normalization():
    result = canon(
        {
            "items": [
                item(
                    hours=[15, 14, 14],
                )
            ]
        }
    )[0]

    assert result["structured_adjustment"]["hours"] == [
        14,
        15,
    ]


@pytest.mark.parametrize(
    "bad_hour",
    [-1, 24, 100],
)
def test_hour_out_of_range_rejected(bad_hour):
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        hours=[bad_hour],
                    )
                ]
            }
        )


@pytest.mark.parametrize(
    "bad_hour",
    [True, 1.5, "14"],
)
def test_non_integer_hours_rejected(bad_hour):
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        hours=[bad_hour],
                    )
                ]
            }
        )


def test_empty_hours_rejected_for_real_directive():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(hours=[])
                ]
            }
        )


def test_no_op_with_hours_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        applies=False,
                        directive_type="no_op",
                        hours=[1],
                    )
                ]
            }
        )


def test_non_no_op_with_applies_false_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        applies=False,
                    )
                ]
            }
        )


def test_no_op_with_applies_true_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        applies=True,
                        directive_type="no_op",
                        hours=[],
                    )
                ]
            }
        )


def test_unsupported_directive_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type="freeze_account",
                    )
                ]
            }
        )


def test_missing_note_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(note_index=0),
                ]
            },
            note_count=2,
        )


def test_duplicate_note_index_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(note_index=0),
                    item(note_index=0),
                ]
            },
            note_count=2,
        )


def test_note_indices_are_returned_in_order():
    result = canon(
        {
            "items": [
                item(
                    note_index=1,
                    directive_type=(
                        "no_discharge_window"
                    ),
                    hours=[18],
                ),
                item(
                    note_index=0,
                    hours=[14],
                ),
            ]
        },
        note_count=2,
    )

    assert [
        entry["note_index"]
        for entry in result
    ] == [0, 1]


@pytest.mark.parametrize(
    "mode,value",
    [
        ("remaining_fraction", -0.01),
        ("remaining_fraction", 1.01),
        ("reduction_fraction", -0.01),
        ("reduction_fraction", 1.01),
    ],
)
def test_invalid_solar_fraction_rejected(
    mode,
    value,
):
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "solar_reduction"
                        ),
                        solar_mode=mode,
                        solar_value=value,
                    )
                ]
            }
        )


def test_reserve_above_capacity_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "minimum_battery_reserve"
                        ),
                        reserve_mode="absolute_kwh",
                        reserve_value=501,
                    )
                ]
            }
        )


def test_negative_absolute_reserve_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "minimum_battery_reserve"
                        ),
                        reserve_mode="absolute_kwh",
                        reserve_value=-1,
                    )
                ]
            }
        )


def test_capacity_fraction_above_one_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "minimum_battery_reserve"
                        ),
                        reserve_mode=(
                            "capacity_fraction"
                        ),
                        reserve_value=1.1,
                    )
                ]
            }
        )


def test_negative_grid_cap_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "max_grid_window"
                        ),
                        max_grid=-1,
                    )
                ]
            }
        )


def test_nan_grid_cap_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "max_grid_window"
                        ),
                        max_grid=float("nan"),
                    )
                ]
            }
        )


def test_wrong_unused_field_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        directive_type=(
                            "no_charge_window"
                        ),
                        solar_value=0.2,
                    )
                ]
            }
        )


def test_blank_explanation_rejected():
    with pytest.raises(DirectiveGuardrailError):
        canon(
            {
                "items": [
                    item(
                        explanation="   ",
                    )
                ]
            }
        )