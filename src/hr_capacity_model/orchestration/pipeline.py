from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hr_capacity_model.core.settings import Settings
from hr_capacity_model.decision.pressure_index import compute_pressure_index
from hr_capacity_model.reporting.manifest import RunManifest, try_get_git_sha, utc_now_iso, write_manifest


@dataclass(frozen=True)
class PipelineOutputs:
    run_dir: Path
    manifest_path: Path
    pressure_index: float


def run_pipeline(
    *,
    settings: Settings,
    run_id: str,
    command: str,
    resolved_config: dict[str, Any],
    input_fingerprints: dict[str, Any],
) -> PipelineOutputs:
    run_dir = settings.artifacts_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Placeholder v0.1 logic:
    projected_load_hours = float(resolved_config["model"]["projected_load_hours"])
    sustainable_capacity_hours = float(resolved_config["model"]["sustainable_capacity_hours"])
    result = compute_pressure_index(projected_load_hours, sustainable_capacity_hours)

    outputs = {
        "pressure_index": str(result.pressure_index),
    }

    manifest = RunManifest(
        run_id=run_id,
        created_utc=utc_now_iso(),
        git_sha=try_get_git_sha(settings.repo_root),
        command=command,
        resolved_config=resolved_config,
        input_fingerprints=input_fingerprints,
        outputs=outputs,
    )
    manifest_path = write_manifest(run_dir, manifest)

    return PipelineOutputs(run_dir=run_dir, manifest_path=manifest_path, pressure_index=result.pressure_index)
