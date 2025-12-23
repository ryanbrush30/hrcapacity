from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PressureResult:
    projected_load_hours: float
    sustainable_capacity_hours: float
    pressure_index: float


def compute_pressure_index(projected_load_hours: float, sustainable_capacity_hours: float) -> PressureResult:
    if sustainable_capacity_hours <= 0:
        raise ValueError("sustainable_capacity_hours must be > 0")

    pressure = projected_load_hours / sustainable_capacity_hours
    return PressureResult(
        projected_load_hours=projected_load_hours,
        sustainable_capacity_hours=sustainable_capacity_hours,
        pressure_index=pressure,
    )
