from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import copy


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    patches: List[Dict[str, Any]]


def _get_by_path(cfg: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    cur: Any = cfg
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            raise KeyError(f"Path not found: {path}")
        cur = cur[p]
    return cur


def _set_by_path(cfg: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = cfg
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            raise KeyError(f"Path not found: {path}")
        cur = cur[p]
    cur[parts[-1]] = value


def _find_event(cfg: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    events = cfg["step2_demand"]["events"]
    for e in events:
        if e.get("event_type") == event_type:
            return e
    raise KeyError(f"event_type not found: {event_type}")


def apply_patch(cfg: Dict[str, Any], patch: Dict[str, Any]) -> None:
    op = patch.get("op")

    # 1) Add FTE from a period index onward
    if op == "set_fte_from_period":
        path = patch["path"]
        start = int(patch["start_period_index"])
        add = float(patch.get("add", 0.0))

        arr = _get_by_path(cfg, path)
        if not isinstance(arr, list):
            raise TypeError(f"{path} must be a list")
        if start < 0 or start >= len(arr):
            raise IndexError("start_period_index out of range")

        new_arr = [float(x) for x in arr]
        for i in range(start, len(new_arr)):
            new_arr[i] = float(new_arr[i]) + add
        _set_by_path(cfg, path, new_arr)
        return

    # 2) Add scheduled hours to a role for a window, by converting to equivalent FTE increment
    # Uses hours_per_fte_per_period to translate extra scheduled hours into fte delta.
    if op == "add_scheduled_hours_window":
        role = patch["role"]
        start = int(patch["start_period_index"])
        end = int(patch["end_period_index"])
        add_hours = float(patch["add_hours_per_period"])

        hours_per_fte = float(cfg["step3_capacity"]["hours_per_fte_per_period"])
        if hours_per_fte <= 0:
            raise ValueError("hours_per_fte_per_period must be > 0")

        fte_delta = add_hours / hours_per_fte

        fte_list = cfg["step3_capacity"]["roles"][role]["fte_by_period"]
        if start < 0 or end >= len(fte_list) or start > end:
            raise IndexError("Invalid start/end period indices")

        new_list = [float(x) for x in fte_list]
        for i in range(start, end + 1):
            new_list[i] = float(new_list[i]) + fte_delta
        cfg["step3_capacity"]["roles"][role]["fte_by_period"] = new_list
        return

    # 3) Scale a specific event's effort hours
    if op == "scale_event_effort":
            event_type = patch["event_type"]
            factor = float(patch["factor"])
            if factor <= 0:
                raise ValueError("factor must be > 0")

            # Enforce scenario-level constraint: no effort reductions for certain events
            constraints = cfg.get("step4_scenarios", {}).get("constraints", {})
            no_reduce = set(constraints.get("no_effort_reduction_events", []) or [])

            # Find event and check event-level lock
            e = _find_event(cfg, event_type)

            locked_effort = bool(e.get("locked_effort", False))

            # Block reductions (factor < 1.0) if constrained or locked
            if factor < 1.0 and (event_type in no_reduce or locked_effort):
                raise ValueError(
                    f"Effort reduction is not permitted for event_type '{event_type}'. "
                    f"Remove this patch or choose a different lever."
                )

            base = float(e["effort_hours"]["base"])
            e["effort_hours"]["base"] = base * factor
            return

    # 4) Scale event counts from a period index onward
    # Works for fixed counts. For rate_per_employee it applies an optional multiplier stored in config.
    if op == "scale_event_counts_from_period":
        event_type = patch["event_type"]
        start = int(patch["start_period_index"])
        factor = float(patch["factor"])
        if factor <= 0:
            raise ValueError("factor must be > 0")

        e = _find_event(cfg, event_type)
        cm = e["count_model"]
        cm_type = cm.get("type")

        if cm_type == "fixed":
            counts = cm.get("counts_by_period")
            if not isinstance(counts, list):
                raise TypeError("counts_by_period must be a list")
            if start < 0 or start >= len(counts):
                raise IndexError("start_period_index out of range")

            new_counts = [float(x) for x in counts]
            for i in range(start, len(new_counts)):
                new_counts[i] = float(new_counts[i]) * factor
            cm["counts_by_period"] = new_counts
            return

        if cm_type == "rate_per_employee":
            # Add a multiplier field and use it in step2 later.
            mult = float(cm.get("multiplier", 1.0))
            cm["multiplier"] = mult * factor
            cm["multiplier_start_period_index"] = start
            return

        raise ValueError(f"Unsupported count_model.type for scaling: {cm_type}")

    raise ValueError(f"Unsupported patch op: {op}")


def load_scenarios(cfg: Dict[str, Any]) -> List[Scenario]:
    s4 = cfg.get("step4_scenarios", {})
    if not s4 or not s4.get("enabled", False):
        return []
    scenarios = []
    for s in s4.get("scenarios", []):
        scenarios.append(
            Scenario(
                name=str(s["name"]),
                description=str(s.get("description", "")),
                patches=list(s.get("patches", [])),
            )
        )
    return scenarios


def build_scenario_config(base_resolved_cfg: Dict[str, Any], scenario: Scenario) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_resolved_cfg)
    for p in scenario.patches:
        apply_patch(cfg, p)
    return cfg
