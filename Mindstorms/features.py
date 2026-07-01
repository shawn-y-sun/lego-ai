"""Deterministic feature-building helpers for v0.1 protocol assets.

The expression evaluator is intentionally tiny: it supports only one binary
arithmetic operation between two source columns. That keeps this prototype safe
and inspectable while the protocol surface is still taking shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .assets import asset_path_segment, read_asset, upsert_asset_index_entries, write_asset_json
from .protocol import PROTOCOL_VERSION, ArtifactRef, AssetRef


_BINARY_EXPRESSION_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*([+\-*/])\s*([A-Za-z_][A-Za-z0-9_.]*)\s*$"
)


def parse_binary_expression(expression: str) -> tuple[str, str, str]:
    """Parse the only formula shape supported by the deterministic prototype."""
    match = _BINARY_EXPRESSION_RE.match(expression)
    if match is None:
        raise ValueError(
            "Unsupported expression. Expected '<column> - <column>', '<column> + <column>', "
            "'<column> * <column>', or '<column> / <column>'."
        )
    return match.group(1), match.group(2), match.group(3)


def apply_proposed_recipe(df: pd.DataFrame, recipe: Dict[str, Any]) -> pd.DataFrame:
    """Apply one recipe definition to a DataFrame without using Python eval."""
    left, operator, right = parse_binary_expression(str(recipe.get("expression", "")))
    missing = [column for column in (left, right) if column not in df.columns]
    if missing:
        raise ValueError(f"Recipe references missing source columns: {', '.join(missing)}")

    output = df.copy()
    name = recipe.get("name")
    if not name:
        raise ValueError("Recipe must include a name.")

    if operator == "-":
        output[name] = output[left] - output[right]
    elif operator == "+":
        output[name] = output[left] + output[right]
    elif operator == "*":
        output[name] = output[left] * output[right]
    elif operator == "/":
        output[name] = output[left] / output[right]
    else:
        raise ValueError(f"Unsupported expression operator: {operator}")
    return output


def _source_ref(source_csv: Path, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Return a stable repo URI only when the source path is repo-relative."""
    root = (repo_root or Path.cwd()).resolve()
    resolved = source_csv.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return {}
    return {"uri": "repo://" + relative.as_posix()}


def _feature_metadata(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a recipe definition into FeatureSet feature metadata."""
    return {
        "name": recipe.get("name"),
        "recipe_kind": recipe.get("recipe_kind"),
        "expression": recipe.get("expression"),
        "expression_language": recipe.get("expression_language"),
        "source_columns": list(recipe.get("source_columns") or []),
        "category": recipe.get("category"),
        # In this prototype, a successfully materialized recipe is search-ready.
        "allowed_for_search": True,
    }


def _recipes_from_asset(asset_id: str) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    asset = read_asset(asset_id)["asset"]
    asset_type = asset.get("type")
    if asset_type == "feature_recipe_proposal":
        return asset, list(asset.get("proposed_recipes") or [])
    if asset_type == "feature_recipe":
        return asset, list(asset.get("recipes") or [])
    raise ValueError(
        f"Asset '{asset_id}' must be a feature_recipe_proposal or feature_recipe."
    )


def build_features_from_proposal(
    *,
    manifest: Dict[str, Any],
    proposal_id: str,
    source_csv: Path,
    date_column: Optional[str],
    output_name: str,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """Build a derived CSV plus DerivedDatasetSnapshot and FeatureSet assets.

    ``proposal_id`` is kept for backward compatibility with the first
    BuildFeatures slice. It may now point to either a proposal asset or an
    approved feature_recipe asset; lineage follows the asset actually used.
    """
    source_asset, recipes = _recipes_from_asset(proposal_id)

    df = pd.read_csv(source_csv)
    if date_column and date_column not in df.columns:
        raise ValueError(f"Date column '{date_column}' was not found in source CSV.")

    if not recipes:
        raise ValueError("Feature recipe asset does not contain recipes.")

    output = df
    added_columns: List[str] = []
    for recipe in recipes:
        output = apply_proposed_recipe(output, recipe)
        added_columns.append(recipe["name"])

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{asset_path_segment(output_name)}.csv"
    output.to_csv(artifact_path, index=False)

    run_id = manifest["run_id"]
    created_at = manifest["completed_at"]
    output_segment = asset_path_segment(output_name)
    run_segment = asset_path_segment(run_id)
    derived_asset_ref = AssetRef(
        asset_id=f"derived_dataset_snapshot:{output_name}:{run_id}",
        type="derived_dataset_snapshot",
        role="derived_dataset",
        uri=f"asset://derived_dataset_snapshot/{output_segment}/{run_segment}.json",
    )
    feature_set_ref = AssetRef(
        asset_id=f"feature_set:{output_name}:{run_id}",
        type="feature_set",
        role="feature_set",
        uri=f"asset://feature_set/{output_segment}/{run_segment}.json",
    )

    artifact_ref = ArtifactRef(
        uri=f"run://artifacts/{asset_path_segment(output_name)}.csv",
        role="derived_dataset_csv",
        media_type="text/csv",
    ).to_dict()
    source_ref = _source_ref(source_csv)
    derived_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "asset_id": derived_asset_ref.asset_id,
        "type": "derived_dataset_snapshot",
        "created_at": created_at,
        "created_by_run_id": run_id,
        "source_asset_ids": [source_asset["asset_id"]],
        "artifact_refs": [artifact_ref],
        "source_run_id": run_id,
        "name": output_name,
        "time_index": date_column,
        "added_columns": added_columns,
        "row_count": int(output.shape[0]),
        "column_count": int(output.shape[1]),
    }
    if source_ref:
        derived_payload["source_ref"] = source_ref

    feature_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "asset_id": feature_set_ref.asset_id,
        "type": "feature_set",
        "created_at": created_at,
        "created_by_run_id": run_id,
        "source_asset_ids": [source_asset["asset_id"], derived_asset_ref.asset_id],
        "artifact_refs": [],
        "source_run_id": run_id,
        "name": output_name,
        "features": [_feature_metadata(recipe) for recipe in recipes],
    }

    write_asset_json(derived_asset_ref, derived_payload)
    write_asset_json(feature_set_ref, feature_payload)
    upsert_asset_index_entries(
        [
            {
                "asset_id": derived_asset_ref.asset_id,
                "type": "derived_dataset_snapshot",
                "uri": derived_asset_ref.uri,
                "created_at": created_at,
                "created_by_run_id": run_id,
                "source_run_id": run_id,
                "name": output_name,
            },
            {
                "asset_id": feature_set_ref.asset_id,
                "type": "feature_set",
                "uri": feature_set_ref.uri,
                "created_at": created_at,
                "created_by_run_id": run_id,
                "source_run_id": run_id,
                "name": output_name,
            },
        ]
    )

    return {
        "summary": {
            "status": "built",
            "output_name": output_name,
            "added_columns": added_columns,
            "row_count": int(output.shape[0]),
            "derived_dataset_asset_id": derived_asset_ref.asset_id,
            "feature_set_asset_id": feature_set_ref.asset_id,
        },
        "assets": [derived_asset_ref.to_dict(), feature_set_ref.to_dict()],
        "diagnostics": {},
    }
