from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Guardrails:
    min_reporting_group_size: int = 25
    allow_individual_outputs: bool = False


def validate_governance(reporting_group_size: int, guardrails: Guardrails) -> None:
    if not guardrails.allow_individual_outputs and reporting_group_size < guardrails.min_reporting_group_size:
        raise ValueError(
            f"Reporting group size {reporting_group_size} is below minimum {guardrails.min_reporting_group_size}."
        )
