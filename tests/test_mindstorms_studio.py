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
    assert snapshot["runs_timeline"][0] == {
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


def test_studio_snapshot_builds_fit_search_asset_details(isolated_protocol_roots):
    runs_root, assets_root = isolated_protocol_roots
    run_dir = runs_root / "search_001"
    run_dir.mkdir(parents=True)
    candidate_id = "candidate_model:home_price_GR1:search_001:cm1"
    evaluation_id = "evaluation_result:home_price_GR1:search_001"
    candidate_uri = "asset://candidate_model/home_price_GR1/search_001/cm1.json"
    evaluation_uri = "asset://evaluation_result/home_price_GR1/search_001.json"
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "run_id": "search_001",
                "workflow_id": "demo_housing_search_smoke",
                "created_at": "2026-07-01T14:00:00Z",
                "completed_at": "2026-07-01T14:01:00Z",
                "status": "succeeded",
                "segment_id": "home_price_GR1",
                "target": "home_price_GR1",
                "inputs": {},
                "outputs": {
                    "summary": {
                        "summary_type": "search_summary",
                        "target": "home_price_GR1",
                        "segment_id": "home_price_GR1",
                        "selected_count": 1,
                        "candidate_count": 1,
                        "best_model_id": "cm1",
                        "best_candidate_model_id": candidate_id,
                        "pilot_smoke": True,
                        "zero_selected_is_valid": True,
                    },
                    "assets": [
                        {
                            "asset_id": candidate_id,
                            "type": "candidate_model",
                            "role": "selected_model",
                            "uri": candidate_uri,
                        },
                        {
                            "asset_id": evaluation_id,
                            "type": "evaluation_result",
                            "role": "search_evaluation",
                            "uri": evaluation_uri,
                        },
                    ],
                },
                "warnings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    assets.upsert_asset_index_entries(
        [
            {
                "asset_id": candidate_id,
                "type": "candidate_model",
                "uri": candidate_uri,
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "target": "home_price_GR1",
            },
            {
                "asset_id": evaluation_id,
                "type": "evaluation_result",
                "uri": evaluation_uri,
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "target": "home_price_GR1",
            },
        ]
    )
    candidate_path = assets_root / "candidate_model" / "home_price_GR1" / "search_001" / "cm1.json"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "asset_id": candidate_id,
                "type": "candidate_model",
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_asset_ids": [],
                "artifact_refs": [
                    {
                        "uri": "technic://Segment/home_price_GR1/cms/search_001/cm1",
                        "role": "technic_candidate_model",
                    }
                ],
                "source_run_id": "search_001",
                "target": "home_price_GR1",
                "segment_id": "home_price_GR1",
                "model_id": "cm1",
                "formula": "home_price_GR1 ~ USMORT30Y",
                "specs": ["USMORT30Y"],
                "metrics": {
                    "rsquared": 0.82,
                    "rsquared_adj": 0.8,
                    "aic": 120.1,
                    "bic": 125.5,
                    "rmse": 0.04,
                },
            }
        ),
        encoding="utf-8",
    )
    evaluation_path = assets_root / "evaluation_result" / "home_price_GR1" / "search_001.json"
    evaluation_path.parent.mkdir(parents=True)
    evaluation_path.write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "asset_id": evaluation_id,
                "type": "evaluation_result",
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_asset_ids": [candidate_id],
                "artifact_refs": [],
                "source_run_id": "search_001",
                "target": "home_price_GR1",
                "segment_id": "home_price_GR1",
                "candidate_count": 1,
                "selected_count": 1,
                "candidate_model_ids": [candidate_id],
                "best_candidate_model_id": candidate_id,
                "summary": {
                    "status": "needs_review",
                    "selected_count": 1,
                    "zero_selected_is_valid": True,
                    "warning_count": 1,
                },
                "warnings": [
                    {
                        "code": "LOW_SAMPLE",
                        "severity": "info",
                        "message": "Small sample.",
                    }
                ],
                "diagnostics": {"notes": ["kept structured"]},
            }
        ),
        encoding="utf-8",
    )

    snapshot = studio.build_studio_snapshot()

    timeline = snapshot["runs_timeline"][0]
    assert timeline["summary_type"] == "search_summary"
    assert timeline["candidate_count"] == 1
    assert timeline["best_model_id"] == "cm1"
    assert timeline["best_candidate_model_id"] == candidate_id
    assert timeline["pilot_smoke"] is True
    details_by_id = {detail["asset_id"]: detail for detail in snapshot["asset_details"]}
    candidate_detail = details_by_id[candidate_id]
    assert candidate_detail["render_kind"] == "candidate_model_card"
    assert candidate_detail["source_run_id"] == "search_001"
    assert candidate_detail["workflow_id"] == "demo_housing_search_smoke"
    assert candidate_detail["formula"] == "home_price_GR1 ~ USMORT30Y"
    assert candidate_detail["metric_highlights"] == {
        "rsquared": 0.82,
        "rsquared_adj": 0.8,
        "aic": 120.1,
        "bic": 125.5,
    }
    assert candidate_detail["raw_available"] is True
    evaluation_detail = details_by_id[evaluation_id]
    assert evaluation_detail["render_kind"] == "evaluation_result_card"
    assert evaluation_detail["status"] == "needs_review"
    assert evaluation_detail["candidate_count"] == 1
    assert evaluation_detail["selected_count"] == 1
    assert evaluation_detail["zero_selected_is_valid"] is True
    assert evaluation_detail["best_candidate_model_id"] == candidate_id
    assert evaluation_detail["warning_count"] == 1
    assert evaluation_detail["diagnostics_summary"] == [{"key": "notes", "size": 19}]
    output_path = assets_root.parent / "studio.html"
    studio.export_studio_html(snapshot, output_path)
    html = output_path.read_text(encoding="utf-8")
    assert "Raw Details" in html
    assert "Selected Model" in html
    assert "Model Options" in html
    assert "Search Summary" in html
    assert "home_price_GR1 ~ USMORT30Y" in html
    assert "<summary>Raw JSON</summary>" in html


def test_search_review_view_prioritizes_selected_model(isolated_protocol_roots):
    runs_root, assets_root = isolated_protocol_roots
    run_dir = runs_root / "search_001"
    run_dir.mkdir(parents=True)
    candidate_id = "candidate_model:home_price_GR1:search_001:cm1"
    candidate_uri = "asset://candidate_model/home_price_GR1/search_001/cm1.json"
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "run_id": "search_001",
                "workflow_id": "demo_housing_search_smoke",
                "created_at": "2026-07-01T14:00:00Z",
                "completed_at": "2026-07-01T14:01:00Z",
                "status": "succeeded",
                "segment_id": "home_price_GR1",
                "target": "home_price_GR1",
                "inputs": {},
                "outputs": {
                    "summary": {
                        "summary_type": "search_summary",
                        "target": "home_price_GR1",
                        "segment_id": "home_price_GR1",
                        "selected_count": 1,
                        "candidate_count": 1,
                        "best_candidate_model_id": candidate_id,
                        "pilot_smoke": True,
                        "zero_selected_is_valid": True,
                    },
                    "assets": [
                        {
                            "asset_id": candidate_id,
                            "type": "candidate_model",
                            "role": "selected_model",
                            "uri": candidate_uri,
                        }
                    ],
                },
                "warnings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    assets.upsert_asset_index_entries(
        [
            {
                "asset_id": candidate_id,
                "type": "candidate_model",
                "uri": candidate_uri,
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "target": "home_price_GR1",
            }
        ]
    )
    candidate_path = assets_root / "candidate_model" / "home_price_GR1" / "search_001" / "cm1.json"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "asset_id": candidate_id,
                "type": "candidate_model",
                "created_at": "2026-07-01T14:01:00Z",
                "created_by_run_id": "search_001",
                "source_run_id": "search_001",
                "source_asset_ids": [],
                "artifact_refs": [],
                "target": "home_price_GR1",
                "segment_id": "home_price_GR1",
                "model_id": "cm1",
                "formula": "home_price_GR1 ~ USMORT30Y",
                "specs": ["USMORT30Y"],
                "metrics": {
                    "rsquared": 0.82,
                    "rsquared_adj": 0.8,
                    "aic": 120.1,
                    "bic": 125.5,
                },
            }
        ),
        encoding="utf-8",
    )

    snapshot = studio.build_studio_snapshot()
    review = studio.build_search_review_view(snapshot)

    assert review["title"] == "Search Review"
    assert review["review_run_id"] == "search_001"
    assert review["target"] == "home_price_GR1"
    assert review["segment_id"] == "home_price_GR1"
    assert review["search_summary"]["candidate_count"] == 1
    assert review["search_summary"]["selected_count"] == 1
    assert review["selected_model"]["asset_id"] == candidate_id
    assert review["selected_model"]["formula"] == "home_price_GR1 ~ USMORT30Y"
    assert review["selected_model"]["drivers"] == ["USMORT30Y"]
    assert review["selected_model"]["metric_highlights"]["rsquared"] == 0.82
    assert [option["asset_id"] for option in review["model_options"]] == [candidate_id]


def test_search_review_view_handles_valid_zero_selected_search(isolated_protocol_roots):
    runs_root, _assets_root = isolated_protocol_roots
    run_dir = runs_root / "search_001"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "protocol_version": "0.1",
                "run_id": "search_001",
                "workflow_id": "demo_housing_search_smoke",
                "created_at": "2026-07-01T14:00:00Z",
                "completed_at": "2026-07-01T14:01:00Z",
                "status": "succeeded",
                "segment_id": "home_price_GR1",
                "target": "home_price_GR1",
                "inputs": {},
                "outputs": {
                    "summary": {
                        "summary_type": "search_summary",
                        "target": "home_price_GR1",
                        "segment_id": "home_price_GR1",
                        "selected_count": 0,
                        "candidate_count": 0,
                        "zero_selected_is_valid": True,
                        "no_candidate_reason": "No candidates passed filters.",
                    },
                    "assets": [],
                },
                "warnings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    review = studio.build_search_review_view(studio.build_studio_snapshot())

    assert review["selected_model"] is None
    assert review["selected_model_empty_state"] == {
        "title": "No model selected",
        "message": "This search completed with zero selected models, and zero-selected is valid.",
        "reason": "No candidates passed filters.",
    }


def test_studio_snapshot_flags_missing_expected_fit_and_search_assets(isolated_protocol_roots):
    runs_root, _assets_root = isolated_protocol_roots
    fit_manifest = runs.base_manifest(
        run_id="fit_001",
        workflow="demo_housing_fit_single",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={"specs": ["USMORT30Y"], "sample": "in"},
    )
    fit_manifest["status"] = "succeeded"
    fit_manifest["completed_at"] = "2026-07-01T14:00:00Z"
    fit_manifest["outputs"] = {
        "summary": {
            "summary_type": "fit_summary",
            "selected_count": 1,
        },
        "assets": [],
    }
    runs.write_manifest(fit_manifest)

    search_manifest = runs.base_manifest(
        run_id="search_001",
        workflow="demo_housing_search",
        segment_id="home_price_GR1",
        target="home_price_GR1",
        inputs={},
    )
    search_manifest["status"] = "succeeded"
    search_manifest["completed_at"] = "2026-07-01T14:05:00Z"
    search_manifest["outputs"] = {
        "summary": {
            "summary_type": "search_summary",
            "selected_count": 0,
            "zero_selected_is_valid": True,
        },
        "assets": [],
    }
    runs.write_manifest(search_manifest)

    snapshot = studio.build_studio_snapshot()

    finding_codes = {finding["code"] for finding in snapshot["health"]["findings"]}
    assert finding_codes >= {
        "EXPECTED_CANDIDATE_MODEL_ASSET_MISSING",
        "EXPECTED_EVALUATION_RESULT_ASSET_MISSING",
    }


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
    assert "Search Review" in html
    assert "Selected Model" in html
    assert "Model Options" in html
    assert "Search Summary" in html
    assert "Diagnostics" in html
    assert "Run History" in html
    assert "Raw Details" in html
    assert "Protocol Health" not in html
    assert "Asset Details" not in html
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
