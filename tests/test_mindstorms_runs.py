import json

import pytest

from Mindstorms import runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    return runs_root


def test_write_read_list_and_latest_manifest(isolated_runs_root):
    manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={"specs": ["USMORT30Y"]},
    )
    manifest["status"] = "succeeded"

    path = runs.write_manifest(manifest)

    assert path == isolated_runs_root / "fit_001" / "manifest.json"
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "fit_001"
    assert runs.latest_run_id() == "fit_001"
    assert runs.read_manifest("latest")["inputs"] == {"specs": ["USMORT30Y"]}
    stored = runs.read_manifest("latest")
    assert stored["protocol_version"] == "0.1"
    assert stored["workflow_id"] == "demo_housing_fit_single"
    assert stored["warnings"] == []
    assert stored["errors"] == []

    listed = runs.list_runs()
    assert listed == [
        {
            "run_id": "fit_001",
            "created_at": manifest["created_at"],
            "workflow": "demo_housing_fit_single",
            "status": "succeeded",
            "manifest_path": str(path),
        }
    ]


def test_latest_run_id_falls_back_to_newest_manifest(isolated_runs_root):
    first = runs.base_manifest(
        run_id="init_001",
        workflow="demo_housing_init",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    second = runs.base_manifest(
        run_id="fit_002",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={"specs": ["USMORT30Y"]},
    )

    runs.write_manifest(first)
    runs.write_manifest(second)
    runs.LATEST_FILE.unlink()

    assert runs.latest_run_id() == "fit_002"


def test_outputs_are_normalized_for_v0_1_without_removing_legacy_fields():
    outputs = runs.normalize_outputs_for_protocol(
        {
            "segment_id": "home_price_GR1",
            "target": "home_price_GR1",
            "search_id": "search_001",
            "selected_count": 1,
            "selected_models": [{"model_id": "cm1"}],
            "captured_stdout": "hello",
            "captured_stderr": "warn",
        }
    )

    assert outputs["selected_count"] == 1
    assert outputs["selected_models"] == [{"model_id": "cm1"}]
    assert outputs["summary"] == {
        "segment_id": "home_price_GR1",
        "target": "home_price_GR1",
        "search_id": "search_001",
        "selected_count": 1,
    }
    assert outputs["assets"] == []
    assert outputs["diagnostics"] == {
        "captured_stdout": "hello",
        "captured_stderr": "warn",
    }
