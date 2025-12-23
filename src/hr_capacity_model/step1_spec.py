from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import pandas as pd


@dataclass(frozen=True)
class DecisionSpec:
    decision_statement: str
    start_date: str
    periods: int
    frequency: str
    in_scope: List[str]
    out_of_scope: List[str]
    governance: Dict[str, Any]

    def period_index(self) -> pd.DatetimeIndex:
        return pd.date_range(start=self.start_date, periods=self.periods, freq=self.frequency)


def build_decision_spec(cfg: Dict[str, Any]) -> DecisionSpec:
    s1 = cfg["step1_decision_spec"]
    horizon = s1["horizon"]
    scope = s1["scope"]
    return DecisionSpec(
        decision_statement=s1["decision_statement"],
        start_date=horizon["start_date"],
        periods=int(horizon["periods"]),
        frequency=horizon["frequency"],
        in_scope=list(scope.get("in_scope", [])),
        out_of_scope=list(scope.get("out_of_scope", [])),
        governance=dict(s1.get("governance", {})),
    )
