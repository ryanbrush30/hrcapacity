from __future__ import annotations

import argparse
from datetime import datetime, timezone

from hr_capacity_model.core.settings import load_settings, load_yaml
from hr_capacity_model.orchestration.pipeline import run_pipeline


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hr_capacity_model", description="HR Capacity Model CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run v0.1 pipeline and write governance artifacts")
    run.add_argument("--config", default="configs/base.yaml", help="Path to yaml config (relative to repo root)")
    run.add_argument("--run-id", default=None, help="Optional run id (defaults to UTC timestamp)")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = load_settings()

    if args.cmd == "run":
        run_id = args.run_id or make_run_id()
        cfg_path = settings.repo_root / args.config
        resolved_config = load_yaml(cfg_path)

        # v0.1 fingerprint placeholder. Replace with data hashes later.
        input_fingerprints = {
            "note": "v0.1 no external inputs",
        }

        outputs = run_pipeline(
            settings=settings,
            run_id=run_id,
            command=f"run --config {args.config} --run-id {run_id}",
            resolved_config=resolved_config,
            input_fingerprints=input_fingerprints,
        )

        print(f"run_dir: {outputs.run_dir}")
        print(f"manifest: {outputs.manifest_path}")
        print(f"pressure_index: {outputs.pressure_index:.4f}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
