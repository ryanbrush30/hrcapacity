# src/hr_capacity_model/validate.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import math


def _near(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def _is_number(x: Any) -> bool:
    try:
        float(x)
        return True
    except Exception:
        return False


def validate_resolved_config(cfg: Dict[str, Any]) -> None:
    """
    Fail-fast validation for decision-grade runs.

    Validates:
    - Period length alignment across all period-based inputs
    - Routing shares sum to 1.0 per event (tolerance)
    - Routing roles exist in capacity roles
    - Fixed-count events have counts_by_period with correct length
    - Scenario patches reference valid roles/events and valid indices
    """
    errors: List[str] = []

    # Horizon
    try:
        horizon = cfg["step1_decision_spec"]["horizon"]
        periods = int(horizon["periods"])
    except Exception:
        raise ValueError("Missing/invalid step1_decision_spec.horizon.periods")

    # Workforce forecast
    wf = cfg.get("inputs", {}).get("workforce_forecast", {}).get("by_period")
    if wf is None:
        errors.append("Missing inputs.workforce_forecast.by_period")
    else:
        if not isinstance(wf, list):
            errors.append("inputs.workforce_forecast.by_period must be a list")
        elif len(wf) != periods:
            errors.append(
                f"workforce_forecast length mismatch: got {len(wf)}, expected {periods}"
            )
        elif any(not _is_number(x) for x in wf):
            errors.append("workforce_forecast contains non-numeric values")

    # Capacity roles
    roles = cfg.get("step3_capacity", {}).get("roles")
    if not isinstance(roles, dict) or not roles:
        errors.append("Missing/invalid step3_capacity.roles (must be a non-empty mapping)")
        role_names: List[str] = []
    else:
        role_names = sorted(list(roles.keys()))
        for rname, r in roles.items():
            if "fte_by_period" not in r:
                errors.append(f"Role '{rname}' missing fte_by_period")
                continue
            fte = r["fte_by_period"]
            if not isinstance(fte, list):
                errors.append(f"Role '{rname}' fte_by_period must be a list")
                continue
            if len(fte) != periods:
                errors.append(
                    f"Role '{rname}' fte_by_period length mismatch: got {len(fte)}, expected {periods}"
                )
            if any(not _is_number(x) for x in fte):
                errors.append(f"Role '{rname}' fte_by_period has non-numeric values")

            for k in ("availability_factor", "buffer_rate"):
                if k not in r or not _is_number(r[k]):
                    errors.append(f"Role '{rname}' missing/invalid '{k}'")
                else:
                    val = float(r[k])
                    if k == "availability_factor" and not (0.0 < val <= 1.0):
                        errors.append(f"Role '{rname}' availability_factor must be in (0,1]")
                    if k == "buffer_rate" and not (0.0 <= val < 1.0):
                        errors.append(f"Role '{rname}' buffer_rate must be in [0,1)")

    # Demand events + routing
    events = cfg.get("step2_demand", {}).get("events")
    if not isinstance(events, list) or not events:
        errors.append("Missing/invalid step2_demand.events (must be a non-empty list)")
        event_types: List[str] = []
    else:
        event_types = []
        seen = set()
        for e in events:
            et = e.get("event_type")
            if not et:
                errors.append("An event is missing event_type")
                continue
            et = str(et)
            if et in seen:
                errors.append(f"Duplicate event_type '{et}' in step2_demand.events")
            seen.add(et)
            event_types.append(et)

            # Count model validations
            cm = e.get("count_model")
            if not isinstance(cm, dict) or "type" not in cm:
                errors.append(f"Event '{et}' missing/invalid count_model")
            else:
                cm_type = cm.get("type")
                if cm_type == "rate_per_employee":
                    if "rate_per_employee_per_period" not in cm or not _is_number(cm["rate_per_employee_per_period"]):
                        errors.append(f"Event '{et}' rate_per_employee missing/invalid rate_per_employee_per_period")
                    # multiplier fields are optional; if present validate
                    if "multiplier" in cm and not _is_number(cm["multiplier"]):
                        errors.append(f"Event '{et}' multiplier must be numeric if provided")
                    if "multiplier_start_period_index" in cm:
                        try:
                            s = int(cm["multiplier_start_period_index"])
                            if s < 0 or s >= periods:
                                errors.append(f"Event '{et}' multiplier_start_period_index out of range")
                        except Exception:
                            errors.append(f"Event '{et}' multiplier_start_period_index must be int")
                elif cm_type == "fixed":
                    counts = cm.get("counts_by_period")
                    if not isinstance(counts, list):
                        errors.append(f"Event '{et}' fixed count_model requires counts_by_period list")
                    else:
                        if len(counts) != periods:
                            errors.append(
                                f"Event '{et}' counts_by_period length mismatch: got {len(counts)}, expected {periods}"
                            )
                        if any(not _is_number(x) for x in counts):
                            errors.append(f"Event '{et}' counts_by_period has non-numeric values")
                else:
                    errors.append(f"Event '{et}' has unsupported count_model.type '{cm_type}'")

            # Effort hours validations
            effort = e.get("effort_hours", {})
            if not isinstance(effort, dict) or "base" not in effort or not _is_number(effort["base"]):
                errors.append(f"Event '{et}' missing/invalid effort_hours.base")
            else:
                if float(effort["base"]) <= 0:
                    errors.append(f"Event '{et}' effort_hours.base must be > 0")

            # Routing validations
            routing = e.get("routing", {})
            if not isinstance(routing, dict) or not routing:
                errors.append(f"Event '{et}' missing/invalid routing (must be mapping with at least 1 role)")
            else:
                s = 0.0
                for role, share in routing.items():
                    if role not in roles:
                        errors.append(f"Event '{et}' routes to unknown role '{role}' (not in step3_capacity.roles)")
                    if not _is_number(share):
                        errors.append(f"Event '{et}' routing share for '{role}' is not numeric")
                        continue
                    fshare = float(share)
                    if fshare < 0:
                        errors.append(f"Event '{et}' routing share for '{role}' must be >= 0")
                    s += fshare
                if not _near(s, 1.0, tol=1e-6):
                    errors.append(f"Event '{et}' routing shares sum to {s:.6f}, expected 1.0")

    # Scenario patch validations (optional)
    s4 = cfg.get("step4_scenarios", {})
    if s4 and s4.get("enabled", False):
        scenarios = s4.get("scenarios", [])
        if not isinstance(scenarios, list):
            errors.append("step4_scenarios.scenarios must be a list")
        else:
            for sc in scenarios:
                sname = sc.get("name", "<unnamed>")
                patches = sc.get("patches", [])
                if not isinstance(patches, list):
                    errors.append(f"Scenario '{sname}' patches must be a list")
                    continue
                for p in patches:
                    op = p.get("op")
                    if not op:
                        errors.append(f"Scenario '{sname}' has a patch with missing op")
                        continue

                    if op == "set_fte_from_period":
                        path = p.get("path", "")
                        spi = p.get("start_period_index")
                        add = p.get("add")
                        if not path or not isinstance(path, str):
                            errors.append(f"Scenario '{sname}' set_fte_from_period missing/invalid path")
                        try:
                            spi_i = int(spi)
                            if spi_i < 0 or spi_i >= periods:
                                errors.append(f"Scenario '{sname}' set_fte_from_period start_period_index out of range")
                        except Exception:
                            errors.append(f"Scenario '{sname}' set_fte_from_period start_period_index must be int")
                        if add is None or not _is_number(add):
                            errors.append(f"Scenario '{sname}' set_fte_from_period add must be numeric")

                    elif op == "add_scheduled_hours_window":
                        role = p.get("role")
                        spi = p.get("start_period_index")
                        epi = p.get("end_period_index")
                        addh = p.get("add_hours_per_period")
                        if not role or role not in roles:
                            errors.append(f"Scenario '{sname}' add_scheduled_hours_window role invalid/unknown '{role}'")
                        try:
                            spi_i = int(spi)
                            epi_i = int(epi)
                            if spi_i < 0 or epi_i < 0 or spi_i >= periods or epi_i >= periods or spi_i > epi_i:
                                errors.append(f"Scenario '{sname}' add_scheduled_hours_window invalid start/end indices")
                        except Exception:
                            errors.append(f"Scenario '{sname}' add_scheduled_hours_window start/end must be int")
                        if addh is None or not _is_number(addh):
                            errors.append(f"Scenario '{sname}' add_scheduled_hours_window add_hours_per_period must be numeric")

                    elif op == "scale_event_effort":
                        et = p.get("event_type")
                        factor = p.get("factor")
                        if not et or et not in event_types:
                            errors.append(f"Scenario '{sname}' scale_event_effort unknown event_type '{et}'")
                        if factor is None or not _is_number(factor) or float(factor) <= 0:
                            errors.append(f"Scenario '{sname}' scale_event_effort factor must be numeric > 0")

                    elif op == "scale_event_counts_from_period":
                        et = p.get("event_type")
                        factor = p.get("factor")
                        spi = p.get("start_period_index")
                        if not et or et not in event_types:
                            errors.append(f"Scenario '{sname}' scale_event_counts_from_period unknown event_type '{et}'")
                        if factor is None or not _is_number(factor) or float(factor) <= 0:
                            errors.append(f"Scenario '{sname}' scale_event_counts_from_period factor must be numeric > 0")
                        try:
                            spi_i = int(spi)
                            if spi_i < 0 or spi_i >= periods:
                                errors.append(f"Scenario '{sname}' scale_event_counts_from_period start_period_index out of range")
                        except Exception:
                            errors.append(f"Scenario '{sname}' scale_event_counts_from_period start_period_index must be int")

                    else:
                        errors.append(f"Scenario '{sname}' uses unsupported patch op '{op}'")

    if errors:
        msg = "Config validation failed:\n" + "\n".join(f"- {e}" for e in errors)
        raise ValueError(msg)
