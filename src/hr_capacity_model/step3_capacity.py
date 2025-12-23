from __future__ import annotations

from typing import Any, Dict, Tuple
import pandas as pd


def compute_capacity_hours(
    cfg: Dict[str, Any],
    period_index: pd.DatetimeIndex,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      capacity_by_role_period: index=period, columns=roles, values=available service hours
      capacity_detail: long detail table with scheduled, availability, buffer, available
    """
    s3 = cfg["step3_capacity"]
    hours_per_fte = float(s3["hours_per_fte_per_period"])
    roles_cfg = s3["roles"]

    periods = len(period_index)
    cap_accum = {}
    rows_detail = []

    for role, rcfg in roles_cfg.items():
        fte = rcfg["fte_by_period"]
        if len(fte) != periods:
            raise ValueError(f"fte_by_period length mismatch for role '{role}'. Expected {periods}.")
        availability = float(rcfg["availability_factor"])
        buffer_rate = float(rcfg["buffer_rate"])

        cap_vals = []
        for i, dt in enumerate(period_index):
            scheduled = float(fte[i]) * hours_per_fte
            avail_hours = scheduled * availability
            buffer_hours = scheduled * buffer_rate
            available_service = max(0.0, avail_hours - buffer_hours)

            cap_vals.append(available_service)
            rows_detail.append(
                {
                    "period": dt,
                    "role": role,
                    "fte": float(fte[i]),
                    "scheduled_hours": scheduled,
                    "availability_factor": availability,
                    "buffer_rate": buffer_rate,
                    "available_hours_pre_buffer": avail_hours,
                    "buffer_hours": buffer_hours,
                    "available_service_hours": available_service,
                }
            )

        cap_accum[role] = cap_vals

    capacity_by_role_period = pd.DataFrame(cap_accum, index=period_index)
    capacity_by_role_period.index.name = "period"
    capacity_detail = pd.DataFrame(rows_detail).sort_values(["period", "role"])
    return capacity_by_role_period, capacity_detail


def compute_utilization_and_gaps(
    demand_by_role_period: pd.DataFrame,
    capacity_by_role_period: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    aligned_demand = demand_by_role_period.reindex_like(capacity_by_role_period).fillna(0.0)
    aligned_capacity = capacity_by_role_period.copy()

    gap = aligned_capacity - aligned_demand
    util = aligned_demand.divide(aligned_capacity.replace(0.0, pd.NA))

    gap.columns = [f"{c}_gap_hours" for c in gap.columns]
    util.columns = [f"{c}_utilization" for c in util.columns]

    return util, gap
