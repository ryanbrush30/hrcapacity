from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def input_fingerprint(files: List[str]) -> Dict[str, str]:
    fp: Dict[str, str] = {}
    for p in files:
        fp[p] = sha256_file(p)
    return fp


def dict_sha256(obj: Dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)
