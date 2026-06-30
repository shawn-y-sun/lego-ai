import json

import pytest

from Mindstorms import runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(runs, "ASSETS_ROOT", assets_root)
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


def test_candidate_model_assets_are_written_and_referenced(isolated_runs_root):
    manifest = runs.base_manifest(
        run_id="search_001",
        workflow="demo_housing_search",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    manifest["completed_at"] = "2026-06-30T14:23:00Z"
    outputs = runs.normalize_outputs_for_protocol(
        {
            "target": "home_price_GR1",
            "selected_models": [
                {
                    "model_id": "cm1",
                    "formula": "home_price_GR1 ~ USMORT30Y",
                    "specs": ["USMORT30Y"],
                    "metrics": {"rsquared": 0.82},
                }
            ],
        }
    )

    updated = runs.write_candidate_model_assets(manifest, outputs)

    assert updated["selected_models"][0]["model_id"] == "cm1"
    assert updated["assets"] == [
        {
            "asset_id": "candidate_model:home_price_GR1:cm1",
            "type": "candidate_model",
            "role": "selected_model",
            "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        }
    ]

    asset_path = isolated_runs_root.parent / "assets" / "candidate_model" / "home_price_GR1" / "cm1.json"
    payload = json.loads(asset_path.read_text(encoding="utf-8"))
    assert payload["protocol_version"] == "0.1"
    assert payload["asset_id"] == "candidate_model:home_price_GR1:cm1"
    assert payload["type"] == "candidate_model"
    assert payload["created_at"] == "2026-06-30T14:23:00Z"
    assert payload["created_by_run_id"] == "search_001"
    assert payload["source_run_id"] == "search_001"
    assert payload["target"] == "home_price_GR1"
    assert payload["formula"] == "home_price_GR1 ~ USMORT30Y"
    assert payload["specs"] == ["USMORT30Y"]
    assert payload["metrics"] == {"rsquared": 0.82}

    index_path = isolated_runs_root.parent / "assets" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index == {
        "protocol_version": "0.1",
        "assets": [
            {
                "asset_id": "candidate_model:home_price_GR1:cm1",
                "type": "candidate_model",
                "uri": "asset://candidate_model/home_price_GR1/cm1.json",
                "created_at": "2026-06-30T14:23:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "target": "home_price_GR1",
            }
        ],
    }


def test_asset_index_upserts_existing_asset_entries(isolated_runs_root):
    first = {
        "asset_id": "candidate_model:home_price_GR1:cm1",
        "type": "candidate_model",
        "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        "created_at": "2026-06-30T14:23:00Z",
        "created_by_run_id": "search_001",
    }
    second = {
        "asset_id": "candidate_model:home_price_GR1:cm1",
        "type": "candidate_model",
        "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        "created_at": "2026-06-30T15:00:00Z",
        "created_by_run_id": "search_002",
    }

    runs.upsert_asset_index_entries([first])
    runs.upsert_asset_index_entries([second])

    assert runs.read_asset_index()["assets"] == [second]
