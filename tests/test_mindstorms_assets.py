import json

import pytest

from Mindstorms import assets
from Mindstorms.protocol import AssetRef


@pytest.fixture()
def isolated_assets_root(tmp_path, monkeypatch):
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(assets, "ASSETS_ROOT", assets_root)
    return assets_root


def test_write_asset_json_resolves_asset_ref_under_assets_root(isolated_assets_root):
    ref = AssetRef(
        asset_id="candidate_model:home_price_GR1:cm1",
        type="candidate_model",
        uri="asset://candidate_model/home_price_GR1/cm1.json",
    )

    path = assets.write_asset_json(ref, {"asset_id": ref.asset_id})

    assert path == isolated_assets_root / "candidate_model" / "home_price_GR1" / "cm1.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "asset_id": "candidate_model:home_price_GR1:cm1"
    }


def test_asset_index_upsert_replaces_existing_entries_by_asset_id(isolated_assets_root):
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

    assets.upsert_asset_index_entries([first])
    assets.upsert_asset_index_entries([second])

    assert assets.read_asset_index()["assets"] == [second]


def test_read_asset_resolves_payload_through_index(isolated_assets_root):
    ref = AssetRef(
        asset_id="evaluation_result:home_price_GR1:search_001",
        type="evaluation_result",
        uri="asset://evaluation_result/home_price_GR1/search_001.json",
    )
    index_entry = {
        "asset_id": ref.asset_id,
        "type": ref.type,
        "uri": ref.uri,
        "created_at": "2026-06-30T14:23:00Z",
        "created_by_run_id": "search_001",
        "target": "home_price_GR1",
    }
    payload = {
        "protocol_version": "0.1",
        "asset_id": ref.asset_id,
        "type": ref.type,
    }
    assets.write_asset_json(ref, payload)
    assets.upsert_asset_index_entries([index_entry])

    result = assets.read_asset(ref.asset_id)

    assert result["asset"] == payload
    assert result["asset_ref"] == index_entry
    assert result["asset_path"] == str(
        isolated_assets_root / "evaluation_result" / "home_price_GR1" / "search_001.json"
    )


def test_list_assets_filters_and_limits_index_entries(isolated_assets_root):
    entries = [
        {
            "asset_id": "candidate_model:home_price_GR1:cm1",
            "type": "candidate_model",
            "uri": "asset://candidate_model/home_price_GR1/cm1.json",
            "created_at": "2026-06-30T14:23:00Z",
            "created_by_run_id": "search_001",
            "target": "home_price_GR1",
        },
        {
            "asset_id": "candidate_model:other_target:cm1",
            "type": "candidate_model",
            "uri": "asset://candidate_model/other_target/cm1.json",
            "created_at": "2026-06-30T14:24:00Z",
            "created_by_run_id": "search_002",
            "target": "other_target",
        },
        {
            "asset_id": "evaluation_result:home_price_GR1:search_001",
            "type": "evaluation_result",
            "uri": "asset://evaluation_result/home_price_GR1/search_001.json",
            "created_at": "2026-06-30T14:25:00Z",
            "created_by_run_id": "search_001",
            "target": "home_price_GR1",
        },
    ]

    assets.upsert_asset_index_entries(entries)

    assert assets.list_assets(asset_type="candidate_model", target="home_price_GR1") == [entries[0]]
    assert assets.list_assets(target="home_price_GR1", limit=1) == [entries[0]]
