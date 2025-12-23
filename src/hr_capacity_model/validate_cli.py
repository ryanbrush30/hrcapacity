from __future__ import annotations

import argparse
from .config import load_yaml, deep_copy
from .run import resolve_config
from .validate import validate_resolved_config


def main() -> None:
    p = argparse.ArgumentParser(prog="hrcm-validate", description="Validate HR Capacity Model inputs.")
    p.add_argument("--config", required=True, help="Path to YAML config.")
    args = p.parse_args()

    raw = load_yaml(args.config)
    resolved = resolve_config(deep_copy(raw))
    validate_resolved_config(resolved)
    print("OK: validation passed")


if __name__ == "__main__":
    main()
