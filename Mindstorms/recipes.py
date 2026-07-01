"""Build and persist deterministic recipe proposal and approval assets.

This module owns recipe lifecycle asset payloads. It deliberately does not
materialize features; feature building lives in ``Mindstorms.features``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .assets import asset_path_segment, read_asset, upsert_asset_index_entries, write_asset_json
from .protocol import PROTOCOL_VERSION, AssetRef


FEATURE_RECIPE_PROPOSAL_STATUS = "proposed"
FEATURE_RECIPE_APPROVED_STATUS = "approved"
FEATURE_RECIPE_PROPOSAL_WORKFLOW_ID = "propose_feature_recipes"
FEATURE_RECIPE_APPROVAL_WORKFLOW_ID = "approve_feature_recipe"


def recipe_proposal_slug(value: str) -> str:
    return asset_path_segment(value).lower()


def feature_recipe_proposal_asset_id(slug: str) -> str:
    return f"feature_recipe_proposal:{recipe_proposal_slug(slug)}"


def feature_recipe_proposal_asset_ref(slug: str) -> AssetRef:
    normalized_slug = recipe_proposal_slug(slug)
    return AssetRef(
        asset_id=feature_recipe_proposal_asset_id(normalized_slug),
        type="feature_recipe_proposal",
        role="feature_recipe_proposal",
        uri=f"asset://feature_recipe_proposal/{normalized_slug}.json",
    )


def feature_recipe_asset_id(slug: str) -> str:
    return f"feature_recipe:{recipe_proposal_slug(slug)}"


def feature_recipe_asset_ref(slug: str) -> AssetRef:
    normalized_slug = recipe_proposal_slug(slug)
    return AssetRef(
        asset_id=feature_recipe_asset_id(normalized_slug),
        type="feature_recipe",
        role="approved_feature_recipe",
        uri=f"asset://feature_recipe/{normalized_slug}.json",
    )


def _utc_timestamp() -> str:
    value = datetime.now(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def _normalize_recipe_outputs(outputs: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(outputs)
    normalized.setdefault("assets", [])
    normalized.setdefault("summary", {})
    normalized.setdefault("diagnostics", {})
    return normalized


def build_proposed_recipe(
    *,
    name: str,
    expression: str,
    source_columns: List[str],
    category: str,
    rationale: Optional[str] = None,
    recipe_kind: str = "arithmetic",
    expression_language: str = "lego_formula_v0",
) -> Dict[str, Any]:
    """Return the stable recipe definition stored inside proposal assets."""
    return {
        "name": name,
        "recipe_kind": recipe_kind,
        "expression": expression,
        "expression_language": expression_language,
        "source_columns": list(source_columns),
        "category": category,
        "rationale": rationale,
    }


def write_feature_recipe_proposal_asset(
    manifest: Dict[str, Any],
    outputs: Dict[str, Any],
    *,
    request: str,
    scope: str,
    available_columns: List[str],
    proposed_recipes: List[Dict[str, Any]],
    slug: str,
) -> Dict[str, Any]:
    """Persist a proposal asset and return normalized run outputs.

    The proposal is durable protocol state and is indexed for later CLI
    inspection. Approval is a separate asset; this function never creates or
    mutates approved recipes.
    """
    normalized = _normalize_recipe_outputs(outputs)
    created_at = manifest.get("completed_at") or _utc_timestamp()
    run_id = manifest["run_id"]
    asset_ref = feature_recipe_proposal_asset_ref(slug)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "asset_id": asset_ref.asset_id,
        "type": "feature_recipe_proposal",
        "created_at": created_at,
        "created_by_run_id": run_id,
        "source_asset_ids": [],
        "artifact_refs": [],
        "source_run_id": run_id,
        "status": FEATURE_RECIPE_PROPOSAL_STATUS,
        "scope": scope,
        "request": request,
        "available_columns": list(available_columns),
        "proposed_recipes": list(proposed_recipes),
    }

    write_asset_json(asset_ref, payload)
    asset_ref_payload = asset_ref.to_dict()
    assets = list(normalized.get("assets") or [])
    if asset_ref_payload not in assets:
        assets.append(asset_ref_payload)
    normalized["assets"] = assets
    summary = dict(normalized.get("summary") or {})
    summary.update(
        {
            "status": FEATURE_RECIPE_PROPOSAL_STATUS,
            "scope": scope,
            "proposal_asset_id": asset_ref.asset_id,
            "proposed_recipe_count": len(proposed_recipes),
        }
    )
    normalized["summary"] = summary
    upsert_asset_index_entries(
        [
            {
                "asset_id": asset_ref.asset_id,
                "type": "feature_recipe_proposal",
                "uri": asset_ref.uri,
                "created_at": created_at,
                "created_by_run_id": run_id,
                "source_run_id": run_id,
                "scope": scope,
                "status": FEATURE_RECIPE_PROPOSAL_STATUS,
            }
        ]
    )
    return normalized


def write_approved_feature_recipe_asset(
    manifest: Dict[str, Any],
    outputs: Dict[str, Any],
    *,
    proposal_id: str,
    approved_by: Optional[str] = None,
    approval_rationale: Optional[str] = None,
    slug: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist an approved FeatureRecipe asset without mutating its proposal."""
    proposal = read_asset(proposal_id)["asset"]
    if proposal.get("type") != "feature_recipe_proposal":
        raise ValueError(f"Asset '{proposal_id}' is not a feature_recipe_proposal.")

    normalized = _normalize_recipe_outputs(outputs)
    created_at = manifest.get("completed_at") or _utc_timestamp()
    run_id = manifest["run_id"]
    recipe_slug = slug or proposal_id.split(":", 1)[-1]
    asset_ref = feature_recipe_asset_ref(recipe_slug)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "asset_id": asset_ref.asset_id,
        "type": "feature_recipe",
        "created_at": created_at,
        "created_by_run_id": run_id,
        "source_asset_ids": [proposal_id],
        "artifact_refs": [],
        "source_run_id": run_id,
        "status": FEATURE_RECIPE_APPROVED_STATUS,
        "scope": proposal.get("scope"),
        "request": proposal.get("request"),
        "recipes": list(proposal.get("proposed_recipes") or []),
    }
    if approved_by:
        payload["approved_by"] = {"name": approved_by}
    if approval_rationale:
        payload["approval_rationale"] = approval_rationale

    write_asset_json(asset_ref, payload)
    asset_ref_payload = asset_ref.to_dict()
    assets = list(normalized.get("assets") or [])
    if asset_ref_payload not in assets:
        assets.append(asset_ref_payload)
    normalized["assets"] = assets
    summary = dict(normalized.get("summary") or {})
    summary.update(
        {
            "status": FEATURE_RECIPE_APPROVED_STATUS,
            "scope": proposal.get("scope"),
            "recipe_asset_id": asset_ref.asset_id,
            "recipe_count": len(payload["recipes"]),
        }
    )
    normalized["summary"] = summary
    upsert_asset_index_entries(
        [
            {
                "asset_id": asset_ref.asset_id,
                "type": "feature_recipe",
                "uri": asset_ref.uri,
                "created_at": created_at,
                "created_by_run_id": run_id,
                "source_run_id": run_id,
                "scope": proposal.get("scope"),
                "status": FEATURE_RECIPE_APPROVED_STATUS,
            }
        ]
    )
    return normalized
