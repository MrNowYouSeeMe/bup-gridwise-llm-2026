
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.llm_interpreter import (
    LLMInterpreterError,
    interpret_operator_notes,
)
from app.optimizer import (
    OptimizationError,
    solve_schedule,
)
from app.replay import (
    ReplayValidationError,
    recalculate_metrics,
    validate_schedule,
)


def _summary(interpretations: list[dict[str, Any]]) -> str:
    applied = sum(
        1
        for entry in interpretations
        if entry["applies"]
    )
    ignored = len(interpretations) - applied

    if applied == 0:
        return (
            "No scheduling directive applied; returned the "
            "minimum-cost valid 24-hour energy plan."
        )

    if ignored:
        return (
            f"Applied {applied} scheduling directive(s), ignored "
            f"{ignored} no-op note(s), and returned the "
            "minimum-cost valid 24-hour energy plan."
        )

    return (
        f"Applied {applied} scheduling directive(s) and returned "
        "the minimum-cost valid 24-hour energy plan."
    )


def run_pipeline(
    payload,
    *,
    interpreter: Callable[..., list[dict[str, Any]]] = (
        interpret_operator_notes
    ),
):
    interpretations = interpreter(
        scenario_id=payload.scenario_id,
        notes=list(payload.operator_notes),
        battery_capacity_kwh=float(
            payload.battery.capacity_kwh
        ),
        battery_minimum_energy_kwh=float(
            payload.battery.minimum_energy_kwh
        ),
    )

    plan = solve_schedule(
        payload,
        interpretations,
    )

    validate_schedule(
        payload,
        interpretations,
        plan,
    )

    metrics = recalculate_metrics(
        payload,
        plan,
    )

    return {
        "scenario_id": payload.scenario_id,
        "directive_interpretation": interpretations,
        "hourly_plan": plan,
        "total_grid_kwh": metrics["total_grid_kwh"],
        "total_cost_bdt": metrics["total_cost_bdt"],
        "peak_grid_kwh": metrics["peak_grid_kwh"],
        "plan_summary": _summary(interpretations),
    }


__all__ = [
    "LLMInterpreterError",
    "OptimizationError",
    "ReplayValidationError",
    "run_pipeline",
]
