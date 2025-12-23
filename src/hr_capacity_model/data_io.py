from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def load_workforce_forecast(path: str) -> Dict[str, Any]:
    df = _read_csv(path)
    if "employees" not in df.columns:
        raise ValueError("workforce_forecast.csv must contain column 'employees'")
    return {
        "unit": "employees",
        "by_period": [float(x) for x in df["employees"].tolist()],
    }


def load_capacity_schedule(path: str) -> Dict[str, Any]:
    df = _read_csv(path)
    required = {"period", "role", "fte", "availability_factor", "buffer_rate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"capacity_schedule.csv missing columns: {sorted(missing)}")

    roles: Dict[str, Any] = {}
    for role, g in df.groupby("role", sort=False):
        # Assumes one row per period per role
        fte = [float(x) for x in g["fte"].tolist()]
        availability = float(g["availability_factor"].iloc[0])
        buffer_rate = float(g["buffer_rate"].iloc[0])
        roles[str(role)] = {
            "fte_by_period": fte,
            "availability_factor": availability,
            "buffer_rate": buffer_rate,
        }

    return roles


def load_routing_matrix(path: str) -> Dict[str, Dict[str, float]]:
    df = _read_csv(path)
    required = {"event_type", "role", "route_share"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"routing_matrix.csv missing columns: {sorted(missing)}")

    routing: Dict[str, Dict[str, float]] = {}
    for event_type, g in df.groupby("event_type", sort=False):
        routing[str(event_type)] = {str(r): float(s) for r, s in zip(g["role"], g["route_share"])}
    return routing


def load_fixed_event_counts(path: str) -> Dict[str, List[float]]:
    df = _read_csv(path)
    if "period" not in df.columns:
        raise ValueError("fixed_event_counts.csv must contain 'period' column")
    # All other columns are event types
    out: Dict[str, List[float]] = {}
    for c in df.columns:
        if c == "period":
            continue
        out[str(c)] = [float(x) for x in df[c].tolist()]
    return out


def load_events_config(
    events_config_path: str,
    routing_matrix_path: str,
    fixed_counts_path: str,
) -> List[Dict[str, Any]]:
    events_df = _read_csv(events_config_path)
    required = {
        "event_type",
        "count_model_type",
        "rate_per_employee_per_period",
        "counts_file",
        "effort_hours_base",
        "locked_effort",
    }
    missing = required - set(events_df.columns)
    if missing:
        raise ValueError(f"events_config.csv missing columns: {sorted(missing)}")

    routing = load_routing_matrix(routing_matrix_path)
    fixed_counts = load_fixed_event_counts(fixed_counts_path)

    events: List[Dict[str, Any]] = []
    for _, row in events_df.iterrows():
        event_type = str(row["event_type"])
        cm_type = str(row["count_model_type"]).strip()

        event_obj: Dict[str, Any] = {
            "event_type": event_type,
            "effort_hours": {"base": float(row["effort_hours_base"])},
            "routing": routing.get(event_type, {}),
            "locked_effort": bool(row["locked_effort"]),
        }

        if cm_type == "rate_per_employee":
            rate = float(row["rate_per_employee_per_period"])
            event_obj["count_model"] = {
                "type": "rate_per_employee",
                "rate_per_employee_per_period": rate,
            }

        elif cm_type == "fixed":
            # counts_file is informational, we actually read from fixed_counts_path
            if event_type not in fixed_counts:
                raise ValueError(
                    f"fixed_event_counts.csv does not have a column for fixed event '{event_type}'"
                )
            event_obj["count_model"] = {
                "type": "fixed",
                "counts_by_period": fixed_counts[event_type],
            }
        else:
            raise ValueError(f"Unsupported count_model_type '{cm_type}' for event '{event_type}'")

        # Optional: remove locked_effort key if false to keep config clean
        if not event_obj["locked_effort"]:
            event_obj.pop("locked_effort", None)

        events.append(event_obj)

    return events
