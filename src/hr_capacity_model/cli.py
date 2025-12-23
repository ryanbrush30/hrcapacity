from __future__ import annotations

import argparse
from .run import run_model


def main() -> None:
    p = argparse.ArgumentParser(prog="hrcm", description="Run HR Capacity Model (Steps 1-3).")
    p.add_argument("--config", required=True, help="Path to YAML config.")
    p.add_argument("--artifacts", default="artifacts", help="Artifacts output directory.")
    args = p.parse_args()

    result = run_model(config_path=args.config, artifacts_dir=args.artifacts)
    print(f"Run complete: {result['run_id']}")
    print(f"Artifacts: {result['artifacts_dir']}")
    print(f"Manifest: {result['manifest']}")
    print(f"Totals: {result['totals']}")


if __name__ == "__main__":
    main()