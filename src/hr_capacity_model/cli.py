from __future__ import annotations

import argparse
from .run import run_model, run_scenarios


def main() -> None:
    p = argparse.ArgumentParser(prog="hrcm", description="Run HR Capacity Model (Steps 1-4).")
    p.add_argument("--config", required=True, help="Path to YAML config.")
    p.add_argument("--artifacts", default="artifacts", help="Artifacts output directory.")
    p.add_argument("--with-scenarios", action="store_true", help="Run Step 4 scenarios if enabled in config.")
    args = p.parse_args()

    if args.with_scenarios:
        result = run_scenarios(config_path=args.config, artifacts_dir=args.artifacts)
        print(f"Baseline run: {result.get('baseline_run_id')}")
        print(f"Baseline dir: {result.get('baseline_dir')}")
        if "scenario_summary" in result:
            print(f"Scenario summary: {result['scenario_summary']}")
            print(f"Scenarios dir: {result['scenarios_dir']}")
    else:
        result = run_model(config_path=args.config, artifacts_dir=args.artifacts)
        print(f"Run complete: {result['run_id']}")
        print(f"Artifacts: {result['artifacts_dir']}")
        print(f"Manifest: {result['manifest']}")
        print(f"Totals: {result['totals']}")


if __name__ == "__main__":
    main()
