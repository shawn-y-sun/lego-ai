import json

import pytest

from Mindstorms import __version__
from Mindstorms import cli, runs


@pytest.fixture()
def isolated_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
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
