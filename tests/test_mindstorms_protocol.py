import json
from pathlib import Path

import pytest

from Mindstorms.protocol import (
    Asset,
    AssetRef,
    ArtifactRef,
    ErrorRecord,
    Run,
    WarningRecord,
    asset_ref_to_path,
    asset_uri_to_path,
)


def test_asset_uri_to_path_maps_under_assets_root():
    path = asset_uri_to_path(
        "asset://candidate_model/home_price_GR1/cm17.json",
        assets_root=Path(".lego") / "assets",
    )

    assert path == Path(".lego") / "assets" / "candidate_model" / "home_price_GR1" / "cm17.json"


@pytest.mark.parametrize(
    "uri",
    [
        "repo://candidate_model/home_price_GR1/cm17.json",
        "asset:///candidate_model/home_price_GR1/cm17.json",
        "asset://candidate_model/home_price_GR1/cm17",
        "asset://candidate_model/../cm17.json",
        "asset://candidate_model/C:/cm17.json",
        "asset://candidate_model/home_price_GR1/cm17.json?download=1",
        "asset://candidate_model/home_price_GR1/cm17.json#frag",
    ],
)
def test_asset_uri_to_path_rejects_invalid_or_machine_local_uris(uri):
    with pytest.raises(ValueError):
        asset_uri_to_path(uri)


def test_asset_ref_to_path_uses_asset_ref_uri():
    ref = AssetRef(
        asset_id="candidate_model:home_price_GR1:cm17",
        type="candidate_model",
        uri="asset://candidate_model/home_price_GR1/cm17.json",
    )

    assert asset_ref_to_path(ref) == (
        Path(".lego") / "assets" / "candidate_model" / "home_price_GR1" / "cm17.json"
    )


def test_base_asset_envelope_serializes_to_stable_json_shape():
    asset = Asset(
        asset_id="candidate_model:home_price_GR1:cm17",
        type="candidate_model",
        created_at="2026-06-30T10:24:12Z",
        created_by_run_id="search_20260630_102300",
        source_asset_ids=[
            "modeling_frame:home_price_GR1:v1",
            "search_pool:home_price_GR1:iter_003",
        ],
        artifact_refs=[
            ArtifactRef(
                uri="technic://Segment/home_price_GR1/cms/search_20260630_102300/cm17",
                media_type="application/vnd.lego.technic-candidate",
            )
        ],
    )

    payload = asset.to_dict()
    assert json.loads(json.dumps(payload)) == {
        "protocol_version": "0.1",
        "asset_id": "candidate_model:home_price_GR1:cm17",
        "type": "candidate_model",
        "created_at": "2026-06-30T10:24:12Z",
        "created_by_run_id": "search_20260630_102300",
        "source_asset_ids": [
            "modeling_frame:home_price_GR1:v1",
            "search_pool:home_price_GR1:iter_003",
        ],
        "artifact_refs": [
            {
                "uri": "technic://Segment/home_price_GR1/cms/search_20260630_102300/cm17",
                "media_type": "application/vnd.lego.technic-candidate",
            }
        ],
    }


def test_warning_error_and_run_records_serialize_to_protocol_shape():
    run = Run(
        run_id="search_20260630_102300",
        workflow_id="search_candidate_models",
        status="failed",
        created_at="2026-06-30T10:23:00Z",
        inputs={"search_pool_id": "search_pool:home_price_GR1:iter_003"},
        outputs={"summary": {}, "assets": [], "diagnostics": {}},
        warnings=[
            WarningRecord(
                code="SCENARIO_INTERNAL_DATA_FALLBACK",
                count=2,
                severity="info",
                fatal=False,
                message="No scenario internal data was available.",
                details={"scenarios": ["Base", "Sev"]},
            )
        ],
        errors=[
            ErrorRecord(
                code="ARTIFACT_WRITE_FAILED",
                severity="error",
                fatal=False,
                message="The model chart could not be written.",
            )
        ],
    )

    payload = run.to_dict()
    assert payload["protocol_version"] == "0.1"
    assert payload["workflow_id"] == "search_candidate_models"
    assert payload["warnings"] == [
        {
            "code": "SCENARIO_INTERNAL_DATA_FALLBACK",
            "count": 2,
            "severity": "info",
            "fatal": False,
            "message": "No scenario internal data was available.",
            "scenarios": ["Base", "Sev"],
        }
    ]
    assert payload["errors"] == [
        {
            "code": "ARTIFACT_WRITE_FAILED",
            "severity": "error",
            "fatal": False,
            "message": "The model chart could not be written.",
        }
    ]
