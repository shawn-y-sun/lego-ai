import pandas as pd
import pytest

from Mindstorms import assets
from Mindstorms import features
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


def _write_proposal_asset():
    proposal_manifest = runs.base_manifest(
        run_id="recipe_proposal_001",
        workflow="propose_feature_recipes",
        segment_id="feature_recipes",
        target="feature_recipes",
        inputs={},
    )
    proposal_manifest["completed_at"] = "2026-07-01T14:00:00Z"
    proposed_recipe = recipes.build_proposed_recipe(
        name="USYC10_2",
        expression="USGOV10Y - USGOV2Y",
        source_columns=["USGOV10Y", "USGOV2Y"],
        category="yield_slope",
        rationale="Classic 10Y-2Y slope.",
    )
    recipes.write_feature_recipe_proposal_asset(
        proposal_manifest,
        {"assets": []},
        request="Create variables that capture yield curve steepness.",
        scope="project",
        available_columns=["USGOV10Y", "USGOV2Y"],
        proposed_recipes=[proposed_recipe],
        slug="yield_curve_steepness",
    )
    return "feature_recipe_proposal:yield_curve_steepness"


def test_build_features_from_proposal_writes_artifact_and_assets(isolated_protocol_roots, tmp_path):
    runs_root, _assets_root = isolated_protocol_roots
    proposal_id = _write_proposal_asset()
    source_csv = tmp_path / "macro_monthly.csv"
    pd.DataFrame(
        {
            "observation_date": ["2026-01-31", "2026-02-28", "2026-03-31"],
            "USGOV10Y": [5.0, 4.5, 4.0],
            "USGOV2Y": [3.0, 3.5, 3.25],
        }
    ).to_csv(source_csv, index=False)
    manifest = runs.base_manifest(
        run_id="build_features_001",
        workflow="build_features",
        segment_id="macro_monthly_enriched",
        target="macro_monthly_enriched",
        inputs={},
    )
    manifest["completed_at"] = "2026-07-01T14:23:00Z"

    outputs = features.build_features_from_proposal(
        manifest=manifest,
        proposal_id=proposal_id,
        source_csv=source_csv,
        date_column="observation_date",
        output_name="macro_monthly_enriched",
        artifacts_dir=runs.run_artifacts_dir("build_features_001"),
    )

    artifact_path = runs_root / "build_features_001" / "artifacts" / "macro_monthly_enriched.csv"
    artifact = pd.read_csv(artifact_path)
    assert artifact["USYC10_2"].tolist() == [2.0, 1.0, 0.75]
    assert outputs["summary"] == {
        "status": "built",
        "output_name": "macro_monthly_enriched",
        "added_columns": ["USYC10_2"],
        "row_count": 3,
        "derived_dataset_asset_id": "derived_dataset_snapshot:macro_monthly_enriched:build_features_001",
        "feature_set_asset_id": "feature_set:macro_monthly_enriched:build_features_001",
    }
    assert [asset["type"] for asset in outputs["assets"]] == [
        "derived_dataset_snapshot",
        "feature_set",
    ]

    derived = assets.read_asset("derived_dataset_snapshot:macro_monthly_enriched:build_features_001")["asset"]
    assert derived["artifact_refs"] == [
        {
            "uri": "run://artifacts/macro_monthly_enriched.csv",
            "role": "derived_dataset_csv",
            "media_type": "text/csv",
        }
    ]
    assert derived["source_asset_ids"] == [proposal_id]
    assert derived["time_index"] == "observation_date"
    assert derived["added_columns"] == ["USYC10_2"]
    assert derived["row_count"] == 3
    assert derived["column_count"] == 4
    assert "source_ref" not in derived

    feature_set = assets.read_asset("feature_set:macro_monthly_enriched:build_features_001")["asset"]
    assert feature_set["source_asset_ids"] == [
        proposal_id,
        "derived_dataset_snapshot:macro_monthly_enriched:build_features_001",
    ]
    assert feature_set["features"] == [
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


def test_parse_binary_expression_rejects_unsupported_formula():
    with pytest.raises(ValueError, match="Unsupported expression"):
        features.parse_binary_expression("USGOV10Y - USGOV2Y + USGOV3M")
