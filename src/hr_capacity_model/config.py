from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import yaml


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Top-level YAML must be a mapping.")
    return data


def deep_copy(obj: Any) -> Any:
    # Safe deep copy for dict/list primitives from YAML
    if isinstance(obj, dict):
        return {k: deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_copy(v) for v in obj]
    return obj


@dataclass(frozen=True)
class ConfigBundle:
    raw: Dict[str, Any]
    resolved: Dict[str, Any]
