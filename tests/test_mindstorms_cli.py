import json

import pytest

from Mindstorms import __version__
from Mindstorms import cli, runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(runs, "ASSETS_ROOT", assets_root)
    return runs_root


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    assert exc_info.value.code == 0
    assert f"Mindstorms {__version__}" in capsys.readouterr().out


def test_cli_runs_list_emits_json(isolated_runs_root, capsys):
    manifest = runs.base_manifest(
        run_id="init_001",
        workflow="demo_housing_init",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    runs.write_manifest(manifest)

    assert cli.main(["runs", "list", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["runs"][0]["run_id"] == "init_001"


def test_cli_help_json_catalog_highlights_pilot_path(capsys):
    assert cli.main(["help", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    commands = {item["name"]: item for item in payload["commands"]}

    assert payload["ok"] is True
    assert commands["demo init"]["safe_for_pilot"] is True
    assert commands["demo fit-single"]["safe_for_pilot"] is True
    assert commands["demo search-smoke"]["safe_for_pilot"] is True
    assert commands["demo search"]["safe_for_pilot"] is False


def test_cli_demo_search_smoke_parser_path(monkeypatch, isolated_runs_root, capsys):
    def fake_run_search_smoke(*, search_id):
        return {
            "segment_id": "home_price_GR1",
            "target": "home_price_GR1",
            "search_id": search_id,
            "artifacts_dir": "C:\\Users\\shawn\\Project\\LEGO_AI\\Segment\\home_price_GR1\\cms\\fake_search",
            "selected_models": [{"model_id": "cm1"}],
            "selected_count": 1,
            "zero_selected_is_valid": True,
            "pilot_smoke": True,
        }

    monkeypatch.setattr(cli._demo_housing(), "run_search_smoke", fake_run_search_smoke)

    assert cli.main(["demo", "search-smoke", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["run"]["workflow"] == "demo_housing_search_smoke"
    assert payload["run"]["workflow_id"] == "demo_housing_search_smoke"
    assert payload["run"]["inputs"]["filter_profile"] == "relaxed_demo_smoke"
    assert payload["run"]["inputs"]["search_config"] == {
        "engine": {
            "name": "technic_model_search",
            "version": "legacy_adapter",
        },
        "driver_pool": ["USMORT30Y"],
        "forced_in": [],
        "constraints": {
            "top_n": 1,
            "max_var_num": 1,
            "max_lag": 0,
            "periods": [1],
        },
        "filter_profile": "relaxed_demo_smoke",
        "runtime_budget": {
            "max_candidates": None,
            "max_seconds": None,
        },
        "pilot_smoke": True,
    }
    assert payload["run"]["outputs"]["selected_count"] == 1
    assert payload["run"]["outputs"]["summary"]["selected_count"] == 1
    assert payload["run"]["outputs"]["assets"] == [
        {
            "asset_id": "candidate_model:home_price_GR1:cm1",
            "type": "candidate_model",
            "role": "selected_model",
            "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        },
        {
            "asset_id": f"evaluation_result:home_price_GR1:{payload['run']['run_id']}",
            "type": "evaluation_result",
            "role": "search_evaluation",
            "uri": f"asset://evaluation_result/home_price_GR1/{payload['run']['run_id']}.json",
        }
    ]
    assert payload["run"]["outputs"]["diagnostics"] == {}
    assert all(asset["type"] != "search_pool" for asset in payload["run"]["outputs"]["assets"])

    asset_id = "candidate_model:home_price_GR1:cm1"
    assert cli.main(["asset", "inspect", asset_id, "--json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["ok"] is True
    assert inspect_payload["asset"]["artifact_refs"] == [
        {
            "uri": f"technic://Segment/home_price_GR1/cms/{payload['run']['outputs']['search_id']}",
            "role": "technic_search_directory",
            "media_type": "application/vnd.lego.technic-search",
        },
        {
            "uri": f"technic://Segment/home_price_GR1/cms/{payload['run']['outputs']['search_id']}/cm1",
            "role": "technic_candidate_model",
            "media_type": "application/vnd.lego.technic-candidate",
        },
    ]
    assert all("C:" not in ref["uri"] for ref in inspect_payload["asset"]["artifact_refs"])
    assert all("\\" not in ref["uri"] for ref in inspect_payload["asset"]["artifact_refs"])

    eval_asset_id = f"evaluation_result:home_price_GR1:{payload['run']['run_id']}"
    assert cli.main(["asset", "inspect", eval_asset_id, "--json"]) == 0
    eval_payload = json.loads(capsys.readouterr().out)
    assert eval_payload["ok"] is True
    assert eval_payload["asset"]["candidate_model_ids"] == [asset_id]
    assert eval_payload["asset"]["best_candidate_model_id"] == asset_id
    assert eval_payload["asset"]["summary"] == {
        "status": "needs_review",
        "selected_count": 1,
        "zero_selected_is_valid": True,
        "warning_count": 0,
    }

    assert cli.main(["assets", "list", "--json"]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert [asset["type"] for asset in list_payload["assets"]] == [
        "candidate_model",
        "evaluation_result",
    ]


def test_cli_demo_search_parser_maps_legacy_inputs_to_search_config(monkeypatch, isolated_runs_root, capsys):
    def fake_run_search(**kwargs):
        return {
            "segment_id": "home_price_GR1",
            "target": "home_price_GR1",
            "search_id": kwargs["search_id"],
            "selected_models": [],
            "selected_count": 0,
            "zero_selected_is_valid": True,
        }

    monkeypatch.setattr(cli._demo_housing(), "run_search", fake_run_search)

    assert (
        cli.main(
            [
                "demo",
                "search",
                "--json",
                "--pool",
                "USMORT30Y",
                "USPRIME",
                "--top-n",
                "7",
                "--max-var-num",
                "2",
                "--max-lag",
                "3",
                "--periods",
                "1",
                "3",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["run"]["inputs"]["desired_pool"] == ["USMORT30Y", "USPRIME"]
    assert payload["run"]["inputs"]["top_n"] == 7
    assert payload["run"]["inputs"]["search_config"] == {
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
    assert payload["run"]["outputs"]["assets"] == [
        {
            "asset_id": f"evaluation_result:home_price_GR1:{payload['run']['run_id']}",
            "type": "evaluation_result",
            "role": "search_evaluation",
            "uri": f"asset://evaluation_result/home_price_GR1/{payload['run']['run_id']}.json",
        }
    ]

    eval_asset_id = f"evaluation_result:home_price_GR1:{payload['run']['run_id']}"
    assert cli.main(["asset", "inspect", eval_asset_id, "--json"]) == 0
    eval_payload = json.loads(capsys.readouterr().out)
    assert eval_payload["ok"] is True
    assert eval_payload["asset"]["candidate_model_ids"] == []
    assert "best_candidate_model_id" not in eval_payload["asset"]
    assert eval_payload["asset"]["summary"] == {
        "status": "no_candidates_selected",
        "selected_count": 0,
        "zero_selected_is_valid": True,
        "warning_count": 0,
    }


def test_cli_demo_fit_single_does_not_emit_search_config(monkeypatch, isolated_runs_root, capsys):
    def fake_run_fit_single(*, specs, sample):
        return {
            "segment_id": "home_price_GR1",
            "target": "home_price_GR1",
            "selected_models": [{"model_id": "cm1"}],
        }

    monkeypatch.setattr(cli._demo_housing(), "run_fit_single", fake_run_fit_single)

    assert cli.main(["demo", "fit-single", "--vars", "USMORT30Y", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert "search_config" not in payload["run"]["inputs"]
    assert all(asset["type"] != "evaluation_result" for asset in payload["run"]["outputs"]["assets"])


def test_cli_run_inspect_latest_emits_json(isolated_runs_root, capsys):
    manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={"specs": ["USMORT30Y"]},
    )
    runs.write_manifest(manifest)

    assert cli.main(["run", "inspect", "latest", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["run"]["run_id"] == "fit_001"


def test_cli_assets_list_and_asset_inspect_emit_json(isolated_runs_root, capsys):
    asset_ref = {
        "asset_id": "candidate_model:home_price_GR1:cm1",
        "type": "candidate_model",
        "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        "created_at": "2026-06-30T14:23:00Z",
        "created_by_run_id": "search_001",
        "source_run_id": "search_001",
        "target": "home_price_GR1",
    }
    runs.upsert_asset_index_entries([asset_ref])
    asset_path = isolated_runs_root.parent / "assets" / "candidate_model" / "home_price_GR1" / "cm1.json"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "asset_id": "candidate_model:home_price_GR1:cm1",
                "type": "candidate_model",
                "created_at": "2026-06-30T14:23:00Z",
                "created_by_run_id": "search_001",
                "source_asset_ids": [],
                "artifact_refs": [],
                "model_id": "cm1",
            }
        ),
        encoding="utf-8",
    )

    assert cli.main(["assets", "list", "--json"]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert list_payload["ok"] is True
    assert list_payload["assets"] == [asset_ref]

    assert cli.main(["asset", "inspect", "candidate_model:home_price_GR1:cm1", "--json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["ok"] is True
    assert inspect_payload["asset"]["asset_id"] == "candidate_model:home_price_GR1:cm1"
    assert inspect_payload["asset_ref"] == asset_ref
