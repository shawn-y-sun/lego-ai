import json

import pytest

from Mindstorms import assets, cli, runs, studio


@pytest.fixture()
def isolated_protocol_roots(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(assets, "ASSETS_ROOT", assets_root)
    return runs_root, assets_root


def test_studio_snapshot_handles_empty_protocol_state(isolated_protocol_roots):
    snapshot = studio.build_studio_snapshot()

    assert snapshot["protocol_version"] == "0.1"
    assert snapshot["health"]["run_count"] == 0
    assert snapshot["health"]["asset_count"] == 0
    assert snapshot["health"]["latest_run_id"] is None
    assert snapshot["runs_timeline"] == []
    assert snapshot["asset_inventory"] == []
    assert snapshot["lineage"] == []
    assert [finding["code"] for finding in snapshot["health"]["findings"]] == [
        "NO_RUNS_FOUND",
        "ASSET_INDEX_MISSING",
    ]


def test_studio_snapshot_summarizes_runs_lineage_and_health(isolated_protocol_roots):
    runs_root, assets_root = isolated_protocol_roots
    run_dir = runs_root / "legacy_search_001"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "legacy_search_001",
                "workflow": "demo_housing_search",
                "created_at": "2026-06-30T14:23:00Z",
                "completed_at": "2026-06-30T14:24:00Z",
                "status": "succeeded",
                "target": "home_price_GR1",
                "inputs": {},
                "outputs": {
                    "selected_count": 0,
                    "zero_selected_is_valid": True,
                    "assets": [
                        {
                            "asset_id": "evaluation_result:home_price_GR1:legacy_search_001",
                            "type": "evaluation_result",
                            "uri": "asset://evaluation_result/home_price_GR1/legacy_search_001.json",
                        },
                        {
                            "asset_id": "candidate_model:home_price_GR1:missing",
                            "type": "candidate_model",
                            "uri": "asset://candidate_model/home_price_GR1/missing.json",
                        },
                    ],
                    "diagnostics": {"captured_stdout": "x" * 2500},
                },
                "warnings": [
                    {
                        "code": "SCENARIO_INTERNAL_DATA_FALLBACK",
                        "severity": "info",
                        "fatal": False,
                        "message": "Fallback.",
                    }
                ],
                "errors": [],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    runs.LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    runs.LATEST_FILE.write_text("legacy_search_001", encoding="utf-8")
    assets.upsert_asset_index_entries(
        [
            {
                "asset_id": "evaluation_result:home_price_GR1:legacy_search_001",
                "type": "evaluation_result",
                "uri": "asset://evaluation_result/home_price_GR1/legacy_search_001.json",
                "created_at": "2026-06-30T14:24:00Z",
                "created_by_run_id": "legacy_search_001",
                "source_run_id": "legacy_search_001",
                "target": "home_price_GR1",
            }
        ]
    )
    asset_path = assets_root / "evaluation_result" / "home_price_GR1" / "legacy_search_001.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text(
        json.dumps({"asset_id": "evaluation_result:home_price_GR1:legacy_search_001"}),
        encoding="utf-8",
    )

    snapshot = studio.build_studio_snapshot()

    assert snapshot["health"]["run_count"] == 1
    assert snapshot["health"]["asset_count"] == 1
    assert snapshot["health"]["latest_run_id"] == "legacy_search_001"
    assert snapshot["runs_timeline"] == [
        {
            "run_id": "legacy_search_001",
            "workflow_id": "demo_housing_search",
            "status": "succeeded",
            "created_at": "2026-06-30T14:23:00Z",
            "completed_at": "2026-06-30T14:24:00Z",
            "target": "home_price_GR1",
            "segment_id": None,
            "warning_count": 1,
            "error_count": 0,
            "output_asset_count": 2,
            "selected_count": 0,
            "zero_selected_is_valid": True,
        }
    ]
    assert snapshot["asset_inventory"][0]["asset_id"] == (
        "evaluation_result:home_price_GR1:legacy_search_001"
    )
    assert snapshot["asset_inventory"][0]["resolved"] is True
    assert [entry["status"] for entry in snapshot["lineage"]] == [
        "resolved",
        "missing_from_index",
    ]
    assert {finding["code"] for finding in snapshot["health"]["findings"]} >= {
        "LEGACY_WORKFLOW_FIELD_NORMALIZED",
        "RUN_DIAGNOSTICS_HEAVY",
        "RUN_OUTPUT_ASSET_MISSING_FROM_INDEX",
    }
    assert snapshot["diagnostics"][0]["size"] == 2500
    assert snapshot["warnings_summary"] == [
        {
            "code": "SCENARIO_INTERNAL_DATA_FALLBACK",
            "count": 1,
            "severity": "info",
            "fatal": False,
            "runs": ["legacy_search_001"],
            "message": "Fallback.",
        }
    ]


def test_studio_snapshot_records_unparseable_manifests(isolated_protocol_roots):
    runs_root, _assets_root = isolated_protocol_roots
    bad_dir = runs_root / "bad_001"
    bad_dir.mkdir(parents=True)
    (bad_dir / "manifest.json").write_text("{not-json", encoding="utf-8")

    snapshot = studio.build_studio_snapshot()

    assert snapshot["health"]["run_count"] == 0
    assert snapshot["diagnostics"][0]["code"] == "UNPARSEABLE_MANIFEST"
    assert snapshot["diagnostics"][0]["run_id"] == "bad_001"
    assert snapshot["health"]["findings"][0]["code"] == "UNPARSEABLE_MANIFEST"


def test_studio_export_writes_static_html(isolated_protocol_roots, tmp_path):
    snapshot = studio.build_studio_snapshot()
    output_path = tmp_path / "studio" / "index.html"

    result = studio.export_studio_html(snapshot, output_path)

    assert result == output_path
    html = output_path.read_text(encoding="utf-8")
    assert "Runs Timeline" in html
    assert "Protocol Health" in html
    assert "Asset Inventory" in html
    assert "Run Detail" in html
    assert "studio-snapshot" in html


def test_cli_studio_snapshot_and_export_emit_json(isolated_protocol_roots, tmp_path, capsys):
    manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    manifest["status"] = "succeeded"
    runs.write_manifest(manifest)

    assert cli.main(["studio", "snapshot", "--json"]) == 0
    snapshot_payload = json.loads(capsys.readouterr().out)
    assert snapshot_payload["ok"] is True
    assert snapshot_payload["snapshot"]["health"]["run_count"] == 1

    output_path = tmp_path / "studio.html"
    assert cli.main(["studio", "export", "--html", str(output_path)]) == 0
    export_payload = json.loads(capsys.readouterr().out)
    assert export_payload["ok"] is True
    assert export_payload["html_path"] == str(output_path)
    assert output_path.exists()


def test_cli_help_json_includes_studio_commands(capsys):
    assert cli.main(["help", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    commands = {item["name"]: item for item in payload["commands"]}

    assert commands["studio snapshot"]["safe_for_pilot"] is True
    assert commands["studio export"]["safe_for_pilot"] is True
