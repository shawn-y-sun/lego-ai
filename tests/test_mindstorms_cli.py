import json

import pandas as pd
import pytest

from Mindstorms import __version__
from Mindstorms import assets
from Mindstorms import cli, runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(assets, "ASSETS_ROOT", assets_root)
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
    assert commands["recipe propose"]["safe_for_pilot"] is True
    assert "feature recipe proposal" in commands["recipe propose"]["purpose"]
    assert commands["features build"]["safe_for_pilot"] is True
    assert "deterministic feature outputs" in commands["features build"]["purpose"]


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
    assets.upsert_asset_index_entries([asset_ref])
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


def test_cli_recipe_propose_writes_manifest_asset_and_index(isolated_runs_root, capsys):
    assert (
        cli.main(
            [
                "recipe",
                "propose",
                "--request",
                "Create variables that capture yield curve steepness.",
                "--name",
                "USYC10_2",
                "--expression",
                "USGOV10Y - USGOV2Y",
                "--source-columns",
                "USGOV10Y",
                "USGOV2Y",
                "--available-columns",
                "USGOV10Y",
                "USGOV2Y",
                "USGOV3M",
                "--category",
                "yield_slope",
                "--scope",
                "project",
                "--rationale",
                "Classic 10Y-2Y slope.",
                "--slug",
                "yield_curve_steepness",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    proposal_id = "feature_recipe_proposal:yield_curve_steepness"
    assert payload["ok"] is True
    assert payload["run"]["workflow"] == "propose_feature_recipes"
    assert payload["run"]["workflow_id"] == "propose_feature_recipes"
    assert payload["run"]["inputs"]["request"] == "Create variables that capture yield curve steepness."
    assert payload["run"]["inputs"]["scope"] == "project"
    assert payload["run"]["inputs"]["available_columns"] == ["USGOV10Y", "USGOV2Y", "USGOV3M"]
    assert payload["run"]["outputs"]["assets"] == [
        {
            "asset_id": proposal_id,
            "type": "feature_recipe_proposal",
            "role": "feature_recipe_proposal",
            "uri": "asset://feature_recipe_proposal/yield_curve_steepness.json",
        }
    ]
    assert payload["run"]["outputs"]["summary"] == {
        "status": "proposed",
        "scope": "project",
        "proposal_asset_id": proposal_id,
        "proposed_recipe_count": 1,
    }

    assert cli.main(["asset", "inspect", proposal_id, "--json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    asset_payload = inspect_payload["asset"]
    assert inspect_payload["ok"] is True
    assert asset_payload["asset_id"] == proposal_id
    assert asset_payload["type"] == "feature_recipe_proposal"
    assert asset_payload["source_run_id"] == payload["run"]["run_id"]
    assert asset_payload["status"] == "proposed"
    assert asset_payload["scope"] == "project"
    assert asset_payload["request"] == "Create variables that capture yield curve steepness."
    assert asset_payload["available_columns"] == ["USGOV10Y", "USGOV2Y", "USGOV3M"]
    assert asset_payload["proposed_recipes"] == [
        {
            "name": "USYC10_2",
            "recipe_kind": "arithmetic",
            "expression": "USGOV10Y - USGOV2Y",
            "expression_language": "lego_formula_v0",
            "source_columns": ["USGOV10Y", "USGOV2Y"],
            "category": "yield_slope",
            "rationale": "Classic 10Y-2Y slope.",
        }
    ]

    assert cli.main(["assets", "list", "--type", "feature_recipe_proposal", "--json"]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert list_payload["assets"] == [
        {
            "asset_id": proposal_id,
            "type": "feature_recipe_proposal",
            "uri": "asset://feature_recipe_proposal/yield_curve_steepness.json",
            "created_at": payload["run"]["completed_at"],
            "created_by_run_id": payload["run"]["run_id"],
            "source_run_id": payload["run"]["run_id"],
            "scope": "project",
            "status": "proposed",
        }
    ]


def test_cli_features_build_writes_artifact_assets_and_index(isolated_runs_root, tmp_path, capsys):
    assert (
        cli.main(
            [
                "recipe",
                "propose",
                "--request",
                "Create variables that capture yield curve steepness.",
                "--name",
                "USYC10_2",
                "--expression",
                "USGOV10Y - USGOV2Y",
                "--source-columns",
                "USGOV10Y",
                "USGOV2Y",
                "--category",
                "yield_slope",
                "--slug",
                "yield_curve_steepness",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    source_csv = tmp_path / "macro_monthly.csv"
    pd.DataFrame(
        {
            "observation_date": ["2026-01-31", "2026-02-28", "2026-03-31"],
            "USGOV10Y": [5.0, 4.5, 4.0],
            "USGOV2Y": [3.0, 3.5, 3.25],
        }
    ).to_csv(source_csv, index=False)

    assert (
        cli.main(
            [
                "features",
                "build",
                "--proposal-id",
                "feature_recipe_proposal:yield_curve_steepness",
                "--source-csv",
                str(source_csv),
                "--date-column",
                "observation_date",
                "--output-name",
                "macro_monthly_enriched",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    run_id = payload["run"]["run_id"]
    derived_id = f"derived_dataset_snapshot:macro_monthly_enriched:{run_id}"
    feature_set_id = f"feature_set:macro_monthly_enriched:{run_id}"
    assert payload["ok"] is True
    assert payload["run"]["workflow_id"] == "build_features"
    assert payload["run"]["outputs"]["summary"] == {
        "status": "built",
        "output_name": "macro_monthly_enriched",
        "added_columns": ["USYC10_2"],
        "row_count": 3,
        "derived_dataset_asset_id": derived_id,
        "feature_set_asset_id": feature_set_id,
    }
    assert payload["run"]["outputs"]["assets"] == [
        {
            "asset_id": derived_id,
            "type": "derived_dataset_snapshot",
            "role": "derived_dataset",
            "uri": f"asset://derived_dataset_snapshot/macro_monthly_enriched/{run_id}.json",
        },
        {
            "asset_id": feature_set_id,
            "type": "feature_set",
            "role": "feature_set",
            "uri": f"asset://feature_set/macro_monthly_enriched/{run_id}.json",
        },
    ]

    artifact_path = isolated_runs_root / run_id / "artifacts" / "macro_monthly_enriched.csv"
    artifact = pd.read_csv(artifact_path)
    assert artifact["USYC10_2"].tolist() == [2.0, 1.0, 0.75]

    assert cli.main(["asset", "inspect", derived_id, "--json"]) == 0
    derived_payload = json.loads(capsys.readouterr().out)
    assert derived_payload["asset"]["row_count"] == 3
    assert derived_payload["asset"]["column_count"] == 4
    assert derived_payload["asset"]["added_columns"] == ["USYC10_2"]
    assert derived_payload["asset"]["artifact_refs"] == [
        {
            "uri": "run://artifacts/macro_monthly_enriched.csv",
            "role": "derived_dataset_csv",
            "media_type": "text/csv",
        }
    ]

    assert cli.main(["asset", "inspect", feature_set_id, "--json"]) == 0
    feature_set_payload = json.loads(capsys.readouterr().out)
    assert feature_set_payload["asset"]["features"] == [
        {
            "name": "USYC10_2",
            "recipe_kind": "arithmetic",
            "expression": "USGOV10Y - USGOV2Y",
            "expression_language": "lego_formula_v0",
            "source_columns": ["USGOV10Y", "USGOV2Y"],
            "category": "yield_slope",
            "allowed_for_search": True,
        }
    ]

    assert cli.main(["assets", "list", "--type", "feature_set", "--json"]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert list_payload["assets"] == [
        {
            "asset_id": feature_set_id,
            "type": "feature_set",
            "uri": f"asset://feature_set/macro_monthly_enriched/{run_id}.json",
            "created_at": payload["run"]["completed_at"],
            "created_by_run_id": run_id,
            "source_run_id": run_id,
            "name": "macro_monthly_enriched",
        }
    ]


def test_cli_features_build_fails_cleanly_for_unsupported_expression(isolated_runs_root, tmp_path, capsys):
    assert (
        cli.main(
            [
                "recipe",
                "propose",
                "--request",
                "Create a multi-term spread.",
                "--name",
                "BAD_EXPR",
                "--expression",
                "USGOV10Y - USGOV2Y + USGOV3M",
                "--source-columns",
                "USGOV10Y",
                "USGOV2Y",
                "USGOV3M",
                "--category",
                "yield_slope",
                "--slug",
                "bad_expression",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    source_csv = tmp_path / "macro_monthly.csv"
    pd.DataFrame(
        {
            "observation_date": ["2026-01-31"],
            "USGOV10Y": [5.0],
            "USGOV2Y": [3.0],
            "USGOV3M": [2.0],
        }
    ).to_csv(source_csv, index=False)

    assert (
        cli.main(
            [
                "features",
                "build",
                "--proposal-id",
                "feature_recipe_proposal:bad_expression",
                "--source-csv",
                str(source_csv),
                "--date-column",
                "observation_date",
                "--output-name",
                "bad_output",
                "--json",
            ]
        )
        == 1
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["run"]["status"] == "failed"
    assert payload["run"]["workflow_id"] == "build_features"
    assert payload["run"]["errors"][0]["code"] == "WORKFLOW_FAILED"
    assert "Unsupported expression" in payload["run"]["errors"][0]["message"]
