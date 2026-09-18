from app.schemas import ScenarioRequest


def semantic_validation_errors(payload: ScenarioRequest) -> list[str]:
    errors: list[str] = []
    b = payload.battery

    capacity = float(b.capacity_kwh)
    initial = float(b.initial_energy_kwh)
    minimum = float(b.minimum_energy_kwh)
    max_charge = float(b.max_charge_kwh_per_hour)
    max_discharge = float(b.max_discharge_kwh_per_hour)

    if capacity < 0:
        errors.append("battery.capacity_kwh must be non-negative")
    if initial < 0:
        errors.append("battery.initial_energy_kwh must be non-negative")
    if minimum < 0:
        errors.append("battery.minimum_energy_kwh must be non-negative")
    if max_charge < 0:
        errors.append("battery.max_charge_kwh_per_hour must be non-negative")
    if max_discharge < 0:
        errors.append("battery.max_discharge_kwh_per_hour must be non-negative")

    if capacity >= 0:
        if initial > capacity:
            errors.append("battery.initial_energy_kwh cannot exceed capacity_kwh")
        if minimum > capacity:
            errors.append("battery.minimum_energy_kwh cannot exceed capacity_kwh")

    return errors