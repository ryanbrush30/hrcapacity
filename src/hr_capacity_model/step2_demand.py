from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import pandas as pd


@dataclass(frozen=True)
class EventSpec:
    event_type: str
    count_model: Dict[str, Any]
    effort_hours_base: float
    routing: Dict[str, float]


def _validate_routing(routing: Dict[str, float], event_type: str) -> None:
    s = sum(float(v) for v in routing.values())
    if s <= 0:
        raise ValueError(f"Routing shares must sum to > 0 for event '{event_type}'.")
    # We do not force sum == 1.0; multi-team routing can exceed 1 if you want explicit parallel work.
    # If you want strict shares, enforce it in config discipline.


def _event_counts_by_period(
    count_model: Dict[str, Any],
    workforce_by_period: List[float],
    periods: int,
) -> List[float]:
    t = count_model.get("type")
    if t == "fixed":
        counts = count_model.get("counts_by_period")
        if not isinstance(counts, list) or len(counts) != periods:
            raise ValueError("fixed count_model requires counts_by_period with length == periods.")
        return [float(x) for x in counts]

    if t == "rate_per_employee":
        r = float(count_model.get("rate_per_employee_per_period", 0.0))
        if len(workforce_by_period) != periods:
            raise ValueError("workforce_forecast.by_period length must equal periods.")
        mult = float(count_model.get("multiplier", 1.0))
        mult_start = int(count_model.get("multiplier_start_period_index", 0))
        out = []
        for i, w in enumerate(workforce_by_period):
            m = mult if i >= mult_start else 1.0
            out.append(float(w) * r * m)
        return out

    raise ValueError(f"Unsupported count_model.type: {t}")


def build_event_specs(cfg: Dict[str, Any]) -> List[EventSpec]:
    s2 = cfg["step2_demand"]
    events = s2.get("events", [])
    specs: List[EventSpec] = []
    for e in events:
        event_type = str(e["event_type"])
        count_model = dict(e["count_model"])
        effort_base = float(e["effort_hours"]["base"])
        routing = {str(k): float(v) for k, v in dict(e["routing"]).items()}
        _validate_routing(routing, event_type)
        specs.append(EventSpec(event_type, count_model, effort_base, routing))
    return specs


def compute_demand_hours(
    cfg: Dict[str, Any],
    period_index: pd.DatetimeIndex,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      demand_by_role_period: index=period, columns=roles, values=service hours demanded
      demand_event_detail: long table with per-event counts and hours by role
    """
    periods = len(period_index)
    workforce_by_period = cfg["inputs"]["workforce_forecast"]["by_period"]
    event_specs = build_event_specs(cfg)

    rows_detail: List[Dict[str, Any]] = []
    demand_accum: Dict[str, List[float]] = {}

    for ev in event_specs:
        counts = _event_counts_by_period(ev.count_model, workforce_by_period, periods)
        for role in ev.routing.keys():
            demand_accum.setdefault(role, [0.0] * periods)

        for i, dt in enumerate(period_index):
            c = float(counts[i])
            base_hours = ev.effort_hours_base
            for role, share in ev.routing.items():
                hrs = c * base_hours * float(share)
                demand_accum[role][i] += hrs
                rows_detail.append(
                    {
                        "period": dt,
                        "event_type": ev.event_type,
                        "role": role,
                        "count": c,
                        "effort_hours_base": base_hours,
                        "route_share": float(share),
                        "demand_hours": hrs,
                    }
                )

    demand_by_role_period = pd.DataFrame({role: vals for role, vals in demand_accum.items()}, index=period_index)
    demand_by_role_period.index.name = "period"
    demand_event_detail = pd.DataFrame(rows_detail).sort_values(["period", "event_type", "role"])
    return demand_by_role_period, demand_event_detail
