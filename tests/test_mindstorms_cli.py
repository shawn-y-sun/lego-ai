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
    assert payload["run"]["outputs"]["selected_count"] == 1
    assert payload["run"]["outputs"]["summary"]["selected_count"] == 1
    assert payload["run"]["outputs"]["assets"] == [
        {
            "asset_id": "candidate_model:home_price_GR1:cm1",
            "type": "candidate_model",
            "role": "selected_model",
            "uri": "asset://candidate_model/home_price_GR1/cm1.json",
        }
    ]
    assert payload["run"]["outputs"]["diagnostics"] == {}


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
