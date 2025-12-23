from __future__ import annotations

import os
from typing import Any, Dict
import pandas as pd

from .config import load_yaml, deep_copy, ConfigBundle
from .governance import ensure_dir, write_json, input_fingerprint, dict_sha256, utc_now_iso
from .step1_spec import build_decision_spec
from .step2_demand import compute_demand_hours
from .step3_capacity import compute_capacity_hours, compute_utilization_and_gaps


def resolve_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder for future resolution logic (defaults, env overrides, schema checks).
    return deep_copy(raw)


def run_model(config_path: str, artifacts_dir: str = "artifacts") -> Dict[str, str]:
    raw = load_yaml(config_path)
    resolved = resolve_config(raw)
    bundle = ConfigBundle(raw=raw, resolved=resolved)

    spec = build_decision_spec(bundle.resolved)
    periods = spec.period_index()

    demand_by_role, demand_detail = compute_demand_hours(bundle.resolved, periods)
    capacity_by_role, capacity_detail = compute_capacity_hours(bundle.resolved, periods)
    util, gap = compute_utilization_and_gaps(demand_by_role, capacity_by_role)

    # Totals (optional but useful)
    totals = pd.DataFrame(
        {
            "demand_total_hours": demand_by_role.sum(axis=1),
            "capacity_total_hours": capacity_by_role.sum(axis=1),
        },
        index=periods,
    )
    totals["gap_total_hours"] = totals["capacity_total_hours"] - totals["demand_total_hours"]
    totals["utilization_total"] = totals["demand_total_hours"] / totals["capacity_total_hours"].replace(0.0, pd.NA)

    run_id = f"run_{spec.start_date}_{utc_now_iso().replace(':','').replace('.','')}"
    out_dir = os.path.join(artifacts_dir, run_id)
    ensure_dir(out_dir)

    # Governance artifacts
    fp = input_fingerprint([config_path])
    resolved_hash = dict_sha256(bundle.resolved)

    manifest = {
        "run_id": run_id,
        "created_utc": utc_now_iso(),
        "model": bundle.resolved.get("model", {}),
        "decision_statement": spec.decision_statement,
        "horizon": {
            "start_date": spec.start_date,
            "periods": spec.periods,
            "frequency": spec.frequency,
        },
        "input_fingerprint": fp,
        "resolved_config_sha256": resolved_hash,
        "prohibited_use": bundle.resolved["step1_decision_spec"]["governance"].get("prohibited_use", []),
    }

    write_json(os.path.join(out_dir, "manifest.json"), manifest)
    write_json(os.path.join(out_dir, "resolved_config.json"), bundle.resolved)

    # Outputs
    demand_by_role.to_csv(os.path.join(out_dir, "demand_by_role_period.csv"))
    demand_detail.to_csv(os.path.join(out_dir, "demand_event_detail.csv"), index=False)

    capacity_by_role.to_csv(os.path.join(out_dir, "capacity_by_role_period.csv"))
    capacity_detail.to_csv(os.path.join(out_dir, "capacity_detail.csv"), index=False)

    util.to_csv(os.path.join(out_dir, "utilization_by_role_period.csv"))
    gap.to_csv(os.path.join(out_dir, "capacity_gap_by_role_period.csv"))

    totals.to_csv(os.path.join(out_dir, "totals.csv"))

    return {
        "run_id": run_id,
        "artifacts_dir": out_dir,
        "manifest": os.path.join(out_dir, "manifest.json"),
        "totals": os.path.join(out_dir, "totals.csv"),
    }
