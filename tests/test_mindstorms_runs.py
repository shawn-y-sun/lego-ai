import json

import pytest

from Mindstorms import assets
from Mindstorms import runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(assets, "ASSETS_ROOT", assets_root)
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


def test_read_manifest_normalizes_legacy_manifest_without_rewriting_file(isolated_runs_root):
    run_dir = isolated_runs_root / "legacy_001"
    run_dir.mkdir(parents=True)
    path = run_dir / "manifest.json"
    legacy = {
        "run_id": "legacy_001",
        "workflow": "demo_housing_fit_single",
        "created_at": "2026-06-30T14:23:00Z",
        "status": "succeeded",
        "inputs": {"specs": ["USMORT30Y"]},
        "outputs": {
            "selected_count": 1,
            "selected_models": [{"model_id": "cm1"}],
        },
    }
    path.write_text(json.dumps(legacy, indent=2, sort_keys=True), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    manifest = runs.read_manifest("legacy_001")

    assert manifest["protocol_version"] == "0.1"
    assert manifest["workflow"] == "demo_housing_fit_single"
    assert manifest["workflow_id"] == "demo_housing_fit_single"
    assert manifest["warnings"] == []
    assert manifest["errors"] == []
    assert manifest["outputs"]["selected_count"] == 1
    assert manifest["outputs"]["selected_models"] == [{"model_id": "cm1"}]
    assert manifest["outputs"]["summary"]["selected_count"] == 1
    assert manifest["outputs"]["assets"] == []
    assert manifest["outputs"]["diagnostics"] == {}
    assert "search_config" not in manifest["inputs"]
    assert path.read_text(encoding="utf-8") == before


def test_read_manifest_adds_search_config_for_legacy_search_manifest(isolated_runs_root):
    run_dir = isolated_runs_root / "legacy_search_001"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "legacy_search_001",
                "workflow": "demo_housing_search",
                "created_at": "2026-06-30T14:23:00Z",
                "status": "succeeded",
                "inputs": {
                    "desired_pool": ["USMORT30Y", "USPRIME"],
                    "forced_in": [],
                    "top_n": 7,
                    "max_var_num": 2,
                    "max_lag": 3,
                    "periods": [1, 3],
                },
                "outputs": {
                    "target": "home_price_GR1",
                    "captured_stdout": "stdout text",
                    "captured_stderr": "stderr text",
                    "selected_count": 0,
                    "selected_models": [],
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    manifest = runs.read_manifest("legacy_search_001")

    assert manifest["inputs"]["search_config"] == {
        "engine": {
            "name": "technic_model_search",
            "version": "legacy_adapter",
        },
        "driver_pool": ["USMORT30Y", "USPRIME"],
        "forced_in": [],
        "constraints": {
            "top_n": 7,
            "max_var_num": 2,
            "max_lag": 3,
            "periods": [1, 3],
        },
        "filter_profile": None,
        "runtime_budget": {
            "max_candidates": None,
            "max_seconds": None,
        },
        "pilot_smoke": False,
    }
    assert manifest["outputs"]["summary"]["target"] == "home_price_GR1"
    assert manifest["outputs"]["summary"]["selected_count"] == 0
    assert manifest["outputs"]["diagnostics"] == {
        "captured_stdout": "stdout text",
        "captured_stderr": "stderr text",
    }
    assert all(asset["type"] != "search_pool" for asset in manifest["outputs"]["assets"])
    assert not (isolated_runs_root.parent / "assets").exists()


def test_normalize_manifest_for_protocol_is_idempotent_for_v0_1_manifest():
    manifest = {
        "protocol_version": "0.1",
        "run_id": "search_001",
        "workflow": "demo_housing_search",
        "workflow_id": "demo_housing_search",
        "created_at": "2026-06-30T14:23:00Z",
        "status": "succeeded",
        "inputs": {
            "desired_pool": ["USMORT30Y"],
            "search_config": {
                "engine": {"name": "custom", "version": "v1"},
                "driver_pool": ["CUSTOM"],
            },
        },
        "outputs": {
            "summary": {"selected_count": 1},
            "assets": [{"asset_id": "candidate_model:target:cm1", "type": "candidate_model"}],
            "diagnostics": {"captured_stdout": "already normalized"},
            "selected_count": 1,
        },
        "warnings": [{"code": "W", "severity": "info", "fatal": False, "message": "m"}],
        "errors": [],
    }

    normalized = runs.normalize_manifest_for_protocol(manifest)

    assert normalized["inputs"]["search_config"] == manifest["inputs"]["search_config"]
    assert normalized["outputs"]["summary"] == {"selected_count": 1}
    assert normalized["outputs"]["assets"] == [
        {"asset_id": "candidate_model:target:cm1", "type": "candidate_model"}
    ]
    assert normalized["outputs"]["diagnostics"] == {"captured_stdout": "already normalized"}
    assert normalized["warnings"] == manifest["warnings"]
    assert normalized["errors"] == []


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
            "asset_id": "candidate_model:home_price_GR1:search_001:cm1",
            "type": "candidate_model",
            "role": "selected_model",
            "uri": "asset://candidate_model/home_price_GR1/search_001/cm1.json",
        }
    ]

    asset_path = isolated_runs_root.parent / "assets" / "candidate_model" / "home_price_GR1" / "search_001" / "cm1.json"
    payload = json.loads(asset_path.read_text(encoding="utf-8"))
    assert payload["protocol_version"] == "0.1"
    assert payload["asset_id"] == "candidate_model:home_price_GR1:search_001:cm1"
    assert payload["type"] == "candidate_model"
    assert payload["created_at"] == "2026-06-30T14:23:00Z"
    assert payload["created_by_run_id"] == "search_001"
    assert payload["source_run_id"] == "search_001"
    assert payload["target"] == "home_price_GR1"
    assert payload["segment_id"] == "home_price_GR1"
    assert payload["formula"] == "home_price_GR1 ~ USMORT30Y"
    assert payload["specs"] == ["USMORT30Y"]
    assert payload["metrics"] == {"rsquared": 0.82}

    index_path = isolated_runs_root.parent / "assets" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index == {
        "protocol_version": "0.1",
        "assets": [
            {
                "asset_id": "candidate_model:home_price_GR1:search_001:cm1",
                "type": "candidate_model",
                "uri": "asset://candidate_model/home_price_GR1/search_001/cm1.json",
                "created_at": "2026-06-30T14:23:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "target": "home_price_GR1",
            }
        ],
    }


def test_candidate_model_assets_include_stable_search_artifact_refs(isolated_runs_root):
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
            "segment_id": "home_price_GR1",
            "target": "home_price_GR1",
            "search_id": "search_001",
            "artifacts_dir": "C:\\Users\\shawn\\Project\\LEGO_AI\\Segment\\home_price_GR1\\cms\\search_001",
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

    runs.write_candidate_model_assets(manifest, outputs)

    payload = assets.read_asset("candidate_model:home_price_GR1:search_001:cm1")["asset"]
    assert payload["artifact_refs"] == [
        {
            "uri": "technic://Segment/home_price_GR1/cms/search_001",
            "role": "technic_search_directory",
            "media_type": "application/vnd.lego.technic-search",
        },
        {
            "uri": "technic://Segment/home_price_GR1/cms/search_001/cm1",
            "role": "technic_candidate_model",
            "media_type": "application/vnd.lego.technic-candidate",
        },
    ]
    assert all("C:" not in ref["uri"] for ref in payload["artifact_refs"])
    assert all("\\" not in ref["uri"] for ref in payload["artifact_refs"])


def test_candidate_model_asset_ids_are_run_scoped(isolated_runs_root):
    first_manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    second_manifest = runs.base_manifest(
        run_id="search_001",
        workflow="demo_housing_search",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    outputs = runs.normalize_outputs_for_protocol(
        {
            "target": "home_price_GR1",
            "selected_models": [{"model_id": "cm1"}],
        }
    )

    first_outputs = runs.write_candidate_model_assets(first_manifest, outputs)
    second_outputs = runs.write_candidate_model_assets(second_manifest, outputs)

    fit_asset_id = "candidate_model:home_price_GR1:fit_001:cm1"
    search_asset_id = "candidate_model:home_price_GR1:search_001:cm1"
    assert first_outputs["assets"][0]["asset_id"] == fit_asset_id
    assert second_outputs["assets"][0]["asset_id"] == search_asset_id
    assert assets.read_asset(fit_asset_id)["asset"]["source_run_id"] == "fit_001"
    assert assets.read_asset(search_asset_id)["asset"]["source_run_id"] == "search_001"


def test_evaluation_result_asset_is_written_for_search_outputs(isolated_runs_root):
    manifest = runs.base_manifest(
        run_id="search_001",
        workflow="demo_housing_search",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    manifest["completed_at"] = "2026-06-30T14:23:00Z"
    manifest["warnings"] = []
    outputs = runs.write_candidate_model_assets(
        manifest,
        runs.normalize_outputs_for_protocol(
            {
                "target": "home_price_GR1",
                "selected_models": [{"model_id": "cm1"}],
                "selected_count": 1,
                "zero_selected_is_valid": True,
            }
        ),
    )

    updated = runs.write_evaluation_result_asset(manifest, outputs)

    assert updated["assets"][-1] == {
        "asset_id": "evaluation_result:home_price_GR1:search_001",
        "type": "evaluation_result",
        "role": "search_evaluation",
        "uri": "asset://evaluation_result/home_price_GR1/search_001.json",
    }
    payload = assets.read_asset("evaluation_result:home_price_GR1:search_001")["asset"]
    assert payload == {
        "protocol_version": "0.1",
        "asset_id": "evaluation_result:home_price_GR1:search_001",
        "type": "evaluation_result",
        "created_at": "2026-06-30T14:23:00Z",
        "created_by_run_id": "search_001",
        "source_asset_ids": ["candidate_model:home_price_GR1:search_001:cm1"],
        "artifact_refs": [],
        "source_run_id": "search_001",
        "target": "home_price_GR1",
        "segment_id": "home_price_GR1",
        "candidate_count": 1,
        "selected_count": 1,
        "candidate_model_ids": ["candidate_model:home_price_GR1:search_001:cm1"],
        "best_candidate_model_id": "candidate_model:home_price_GR1:search_001:cm1",
        "summary": {
            "status": "needs_review",
            "selected_count": 1,
            "zero_selected_is_valid": True,
            "warning_count": 0,
        },
        "warnings": [],
        "diagnostics": {},
        "weaknesses": [],
        "recommended_next_actions": [],
    }
    assert [asset["type"] for asset in assets.read_asset_index()["assets"]] == [
        "candidate_model",
        "evaluation_result",
    ]


def test_evaluation_result_asset_represents_zero_selected_search(isolated_runs_root):
    manifest = runs.base_manifest(
        run_id="search_002",
        workflow="demo_housing_search",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    manifest["completed_at"] = "2026-06-30T15:00:00Z"
    manifest["warnings"] = [{"code": "W", "message": "review this"}]
    outputs = runs.normalize_outputs_for_protocol(
        {
            "target": "home_price_GR1",
            "selected_models": [],
            "selected_count": 0,
            "zero_selected_is_valid": True,
        }
    )

    updated = runs.write_evaluation_result_asset(manifest, outputs)

    assert updated["assets"] == [
        {
            "asset_id": "evaluation_result:home_price_GR1:search_002",
            "type": "evaluation_result",
            "role": "search_evaluation",
            "uri": "asset://evaluation_result/home_price_GR1/search_002.json",
        }
    ]
    payload = assets.read_asset("evaluation_result:home_price_GR1:search_002")["asset"]
    assert payload["candidate_model_ids"] == []
    assert payload["candidate_count"] == 0
    assert payload["selected_count"] == 0
    assert payload["segment_id"] == "home_price_GR1"
    assert "best_candidate_model_id" not in payload
    assert payload["summary"] == {
        "status": "no_candidates_selected",
        "selected_count": 0,
        "zero_selected_is_valid": True,
        "warning_count": 1,
    }


def test_evaluation_result_asset_is_not_written_for_fit_single(isolated_runs_root):
    manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    outputs = runs.normalize_outputs_for_protocol(
        {
            "target": "home_price_GR1",
            "selected_models": [{"model_id": "cm1"}],
            "selected_count": 1,
        }
    )

    assert runs.write_evaluation_result_asset(manifest, outputs) == outputs
    assert not (isolated_runs_root.parent / "assets").exists()
