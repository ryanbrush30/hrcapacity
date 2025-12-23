from hr_capacity_model.core.settings import load_settings
from hr_capacity_model.orchestration.pipeline import run_pipeline


def test_pipeline_smoke(tmp_path, monkeypatch):
    settings = load_settings()

    # Redirect artifacts to tmp so the test is clean
    monkeypatch.setattr(settings, "artifacts_dir", tmp_path, raising=False)

    resolved_config = {"model": {"projected_load_hours": 120.0, "sustainable_capacity_hours": 100.0}}
    outputs = run_pipeline(
        settings=settings,
        run_id="test_run",
        command="run --config configs/base.yaml --run-id test_run",
        resolved_config=resolved_config,
        input_fingerprints={"note": "test"},
    )

    assert outputs.manifest_path.exists()
