from __future__ import annotations

import os
from typing import Any, Dict
import pandas as pd

from .config import load_yaml, deep_copy, ConfigBundle
from .governance import ensure_dir, write_json, input_fingerprint, dict_sha256, utc_now_iso
from .step1_spec import build_decision_spec
from .step2_demand import compute_demand_hours
from .step3_capacity import compute_capacity_hours, compute_utilization_and_gaps
from .step4_scenarios import load_scenarios, build_scenario_config



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

def run_scenarios(config_path: str, artifacts_dir: str = "artifacts") -> Dict[str, str]:
    raw = load_yaml(config_path)
    resolved = resolve_config(raw)

    scenarios = load_scenarios(resolved)

    # Run baseline first using existing run_model
    baseline_result = run_model(config_path=config_path, artifacts_dir=artifacts_dir)
    baseline_dir = baseline_result["artifacts_dir"]

    import pandas as pd
    baseline_totals = pd.read_csv(os.path.join(baseline_dir, "totals.csv"))

    if not scenarios:
        return {"baseline_run_id": baseline_result["run_id"], "baseline_dir": baseline_dir}

    # Create a scenarios folder under the baseline directory for clean lineage
    scenarios_out = os.path.join(baseline_dir, "scenarios")
    ensure_dir(scenarios_out)

    summary_rows = []

    for s in scenarios:
        if s.name == "baseline":
            continue

        # Build patched config, write it, then run from that config object by temporarily saving a file
        scenario_cfg = build_scenario_config(resolved, s)

        scenario_cfg_path = os.path.join(scenarios_out, f"{s.name}.resolved_config.json")
        write_json(scenario_cfg_path, scenario_cfg)

        # Run scenario by temporarily writing a YAML alongside (simple approach)
        # Better approach later: accept dict configs directly.
        import yaml
        scenario_yaml_path = os.path.join(scenarios_out, f"{s.name}.yaml")
        with open(scenario_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(scenario_cfg, f, sort_keys=False)

        scenario_result = run_model(config_path=scenario_yaml_path, artifacts_dir=scenarios_out)
        scenario_dir = scenario_result["artifacts_dir"]

        scenario_totals = pd.read_csv(os.path.join(scenario_dir, "totals.csv"))

        # Compute delta summary (aggregate)
        # Align by row order (same horizon)
        d_util = (scenario_totals["utilization_total"] - baseline_totals["utilization_total"]).mean()
        d_gap = (scenario_totals["gap_total_hours"] - baseline_totals["gap_total_hours"]).sum()

        # Worst-week improvements
        worst_base = baseline_totals["utilization_total"].max()
        worst_scn = scenario_totals["utilization_total"].max()
        worst_delta = worst_scn - worst_base

        summary_rows.append(
            {
                "scenario": s.name,
                "description": s.description,
                "scenario_run_id": scenario_result["run_id"],
                "scenario_dir": scenario_dir,
                "mean_utilization_delta": d_util,
                "total_gap_hours_delta_sum": d_gap,
                "worst_week_utilization_baseline": worst_base,
                "worst_week_utilization_scenario": worst_scn,
                "worst_week_utilization_delta": worst_delta,
            }
        )

    pd.DataFrame(summary_rows).to_csv(os.path.join(scenarios_out, "scenario_summary.csv"), index=False)

    return {
        "baseline_run_id": baseline_result["run_id"],
        "baseline_dir": baseline_dir,
        "scenarios_dir": scenarios_out,
        "scenario_summary": os.path.join(scenarios_out, "scenario_summary.csv"),
    }