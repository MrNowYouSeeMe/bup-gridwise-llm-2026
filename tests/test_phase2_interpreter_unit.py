import pytest

import app.llm_interpreter as module
from app.llm_interpreter import (
    LLMInterpreterError,
    interpret_operator_notes,
)


def valid_item():
    return {
        "note_index": 0,
        "applies": True,
        "directive_type": "no_charge_window",
        "hours": [14, 15],
        "solar_quantity_mode": "none",
        "solar_quantity_value": 0,
        "reserve_quantity_mode": "none",
        "reserve_quantity_value": 0,
        "max_grid_kwh": 0,
        "explanation": "Charging unavailable.",
    }


def call_interpreter():
    return interpret_operator_notes(
        scenario_id="UNIT",
        notes=[
            "Do not charge from 2 PM to 4 PM."
        ],
        battery_capacity_kwh=500,
        battery_minimum_energy_kwh=50,
    )


def test_valid_model_output_uses_one_call(
    monkeypatch,
):
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return {
            "items": [
                valid_item()
            ]
        }

    monkeypatch.setattr(
        module,
        "_call_model",
        fake_call,
    )

    result = call_interpreter()

    assert len(calls) == 1
    assert result[0]["directive_type"] == (
        "no_charge_window"
    )


def test_guardrail_failure_gets_exactly_one_repair(
    monkeypatch,
):
    calls = []

    bad = valid_item()
    bad["hours"] = [27]

    outputs = [
        {"items": [bad]},
        {"items": [valid_item()]},
    ]

    def fake_call(**kwargs):
        calls.append(kwargs)
        return outputs[len(calls) - 1]

    monkeypatch.setattr(
        module,
        "_call_model",
        fake_call,
    )

    result = call_interpreter()

    assert len(calls) == 2
    assert calls[0]["repair_feedback"] is None
    assert calls[1]["repair_feedback"]
    assert result[0]["structured_adjustment"] == {
        "hours": [14, 15],
    }


def test_second_guardrail_failure_stops(
    monkeypatch,
):
    calls = []

    bad = valid_item()
    bad["hours"] = [27]

    def fake_call(**kwargs):
        calls.append(kwargs)
        return {"items": [bad]}

    monkeypatch.setattr(
        module,
        "_call_model",
        fake_call,
    )

    with pytest.raises(LLMInterpreterError):
        call_interpreter()

    assert len(calls) == 2


def test_provider_error_is_not_blindly_retried(
    monkeypatch,
):
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        raise LLMInterpreterError(
            "OpenAI request timed out"
        )

    monkeypatch.setattr(
        module,
        "_call_model",
        fake_call,
    )

    with pytest.raises(LLMInterpreterError):
        call_interpreter()

    assert len(calls) == 1


@pytest.mark.parametrize(
    "notes",
    [
        [],
        ["a", "b", "c", "d"],
        [""],
        ["   "],
        [123],
    ],
)
def test_invalid_notes_never_call_provider(
    monkeypatch,
    notes,
):
    called = False

    def fake_call(**kwargs):
        nonlocal called
        called = True
        return {"items": []}

    monkeypatch.setattr(
        module,
        "_call_model",
        fake_call,
    )

    with pytest.raises(LLMInterpreterError):
        interpret_operator_notes(
            scenario_id="BAD",
            notes=notes,
            battery_capacity_kwh=500,
            battery_minimum_energy_kwh=50,
        )

    assert called is False