import math
from typing import Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

StrictNumber = Union[StrictInt, StrictFloat]


def ensure_finite(value):
    if not math.isfinite(float(value)):
        raise ValueError("numeric value must be finite")
    return value


class HourInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hour: StrictInt
    demand_kwh: StrictNumber
    solar_kwh: StrictNumber
    tariff_bdt_per_kwh: StrictNumber

    @field_validator("demand_kwh", "solar_kwh", "tariff_bdt_per_kwh")
    @classmethod
    def numeric_values_must_be_finite(cls, value):
        return ensure_finite(value)


class BatteryInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    capacity_kwh: StrictNumber
    initial_energy_kwh: StrictNumber
    minimum_energy_kwh: StrictNumber
    max_charge_kwh_per_hour: StrictNumber
    max_discharge_kwh_per_hour: StrictNumber

    @field_validator(
        "capacity_kwh",
        "initial_energy_kwh",
        "minimum_energy_kwh",
        "max_charge_kwh_per_hour",
        "max_discharge_kwh_per_hour",
    )
    @classmethod
    def numeric_values_must_be_finite(cls, value):
        return ensure_finite(value)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scenario_id: StrictStr
    operator_notes: list[StrictStr] = Field(min_length=1, max_length=3)
    hours: list[HourInput] = Field(min_length=24, max_length=24)
    battery: BatteryInput

    @field_validator("scenario_id")
    @classmethod
    def scenario_id_must_not_be_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("scenario_id must not be blank")
        return value

    @field_validator("operator_notes")
    @classmethod
    def notes_must_not_be_blank(cls, notes):
        cleaned = []
        for note in notes:
            note = note.strip()
            if not note:
                raise ValueError(
                    "operator_notes must contain only non-empty strings"
                )
            cleaned.append(note)
        return cleaned

    @model_validator(mode="after")
    def validate_hour_indices(self):
        indices = [item.hour for item in self.hours]
        if len(set(indices)) != 24:
            raise ValueError("hours must contain 24 unique hour values")
        if set(indices) != set(range(24)):
            raise ValueError("hours must contain every integer from 0 through 23")
        return self