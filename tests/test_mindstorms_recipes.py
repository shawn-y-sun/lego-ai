import pytest

from Mindstorms import assets
from Mindstorms import recipes
from Mindstorms import runs


@pytest.fixture()
def isolated_protocol_roots(tmp_path, monkeypatch):
    runs_root = tmp_path / ".lego" / "runs"
    assets_root = tmp_path / ".lego" / "assets"
    monkeypatch.setattr(runs, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(runs, "LATEST_FILE", runs_root / "latest")
    monkeypatch.setattr(assets, "ASSETS_ROOT", assets_root)
    return runs_root, assets_root


def test_write_feature_recipe_proposal_asset_persists_and_indexes_asset(isolated_protocol_roots):
    manifest = runs.base_manifest(
        run_id="recipe_proposal_001",
        workflow="propose_feature_recipes",
        segment_id="feature_recipes",
        target="feature_recipes",
        inputs={},
    )
    manifest["completed_at"] = "2026-06-30T14:23:00Z"
    proposed_recipe = recipes.build_proposed_recipe(
        name="USYC10_2",
        expression="USGOV10Y - USGOV2Y",
        source_columns=["USGOV10Y", "USGOV2Y"],
        category="yield_slope",
        rationale="Classic 10Y-2Y slope.",
    )

    updated = recipes.write_feature_recipe_proposal_asset(
        manifest,
        {"assets": []},
        request="Create variables that capture yield curve steepness.",
        scope="project",
        available_columns=["USGOV10Y", "USGOV2Y"],
        proposed_recipes=[proposed_recipe],
        slug=recipes.recipe_proposal_slug("Yield Curve Steepness"),
    )

    asset_id = "feature_recipe_proposal:yield_curve_steepness"
    assert updated["assets"] == [
        {
            "asset_id": asset_id,
            "type": "feature_recipe_proposal",
            "role": "feature_recipe_proposal",
            "uri": "asset://feature_recipe_proposal/yield_curve_steepness.json",
        }
    ]
    payload = assets.read_asset(asset_id)["asset"]
    assert payload == {
        "protocol_version": "0.1",
        "asset_id": asset_id,
        "type": "feature_recipe_proposal",
        "created_at": "2026-06-30T14:23:00Z",
        "created_by_run_id": "recipe_proposal_001",
        "source_asset_ids": [],
        "artifact_refs": [],
        "source_run_id": "recipe_proposal_001",
        "status": "proposed",
        "scope": "project",
        "request": "Create variables that capture yield curve steepness.",
        "available_columns": ["USGOV10Y", "USGOV2Y"],
        "proposed_recipes": [proposed_recipe],
    }
    assert assets.list_assets(asset_type="feature_recipe_proposal") == [
        {
            "asset_id": asset_id,
            "type": "feature_recipe_proposal",
            "uri": "asset://feature_recipe_proposal/yield_curve_steepness.json",
            "created_at": "2026-06-30T14:23:00Z",
            "created_by_run_id": "recipe_proposal_001",
            "source_run_id": "recipe_proposal_001",
            "scope": "project",
            "status": "proposed",
        }
    ]
