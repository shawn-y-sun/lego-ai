"""Run manifest lifecycle and current protocol asset writer orchestration."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .assets import (
    asset_path_segment,
    upsert_asset_index_entries,
    write_asset_json,
)
from .protocol import PROTOCOL_VERSION, ArtifactRef, AssetRef


RUNS_ROOT = Path(".lego") / "runs"
LATEST_FILE = RUNS_ROOT / "latest"
_LAST_MANIFEST_MTIME_NS = 0
SEARCH_WORKFLOW_IDS = {"demo_housing_search", "demo_housing_search_smoke"}
FIT_WORKFLOW_IDS = {"demo_housing_fit_single"}


def utc_timestamp() -> str:
    value = datetime.now(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"


def _run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def _manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / "manifest.json"


def run_artifacts_dir(run_id: str) -> Path:
    return _run_dir(run_id) / "artifacts"


def write_manifest(manifest: Dict[str, Any]) -> Path:
    global _LAST_MANIFEST_MTIME_NS

    run_id = manifest["run_id"]
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(run_id)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    mtime_ns = max(time.time_ns(), _LAST_MANIFEST_MTIME_NS + 1)
    _LAST_MANIFEST_MTIME_NS = mtime_ns
    os.utime(path, ns=(mtime_ns, mtime_ns))
    LATEST_FILE.write_text(run_id, encoding="utf-8")
    return path


def read_manifest(run_id: str) -> Dict[str, Any]:
    """Read a run manifest and normalize legacy manifests to the v0.1 shape."""
    if run_id == "latest":
        run_id = latest_run_id()
    path = _manifest_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"No run manifest found for '{run_id}'.")
    return normalize_manifest_for_protocol(json.loads(path.read_text(encoding="utf-8")))


def latest_run_id() -> str:
    if LATEST_FILE.exists():
        value = LATEST_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value

    manifests = sorted(
        RUNS_ROOT.glob("*/manifest.json"),
        key=lambda p: (p.stat().st_mtime_ns, p.parent.name),
    )
    if not manifests:
        raise FileNotFoundError("No Mindstorms runs found.")
    return manifests[-1].parent.name


def list_runs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    manifests = sorted(
        RUNS_ROOT.glob("*/manifest.json"),
        key=lambda p: (p.stat().st_mtime_ns, p.parent.name),
        reverse=True,
    )
    if limit is not None:
        manifests = manifests[:limit]

    runs: List[Dict[str, Any]] = []
    for path in manifests:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        runs.append(
            {
                "run_id": data.get("run_id", path.parent.name),
                "created_at": data.get("created_at"),
                "workflow": data.get("workflow"),
                "status": data.get("status"),
                "manifest_path": str(path),
            }
        )
    return runs


def search_config_from_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Map legacy search CLI inputs into the stable SearchConfig run input."""
    return {
        "engine": {
            "name": "technic_model_search",
            "version": "legacy_adapter",
        },
        "driver_pool": list(inputs.get("desired_pool") or []),
        "forced_in": list(inputs.get("forced_in") or []),
        "constraints": {
            "top_n": inputs.get("top_n"),
            "max_var_num": inputs.get("max_var_num"),
            "max_lag": inputs.get("max_lag"),
            "periods": inputs.get("periods"),
        },
        "filter_profile": inputs.get("filter_profile"),
        "runtime_budget": {
            "max_candidates": inputs.get("max_candidates"),
            "max_seconds": inputs.get("max_seconds"),
        },
        "pilot_smoke": bool(inputs.get("pilot_smoke", False)),
    }


def normalize_manifest_for_protocol(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return an in-memory v0.1-compatible view without rewriting old files."""
    normalized = dict(manifest)
    workflow = normalized.get("workflow")

    normalized.setdefault("protocol_version", PROTOCOL_VERSION)
    if "workflow_id" not in normalized and workflow is not None:
        normalized["workflow_id"] = workflow

    inputs = dict(normalized.get("inputs") or {})
    workflow_id = normalized.get("workflow_id") or workflow
    if (
        workflow_id in ("demo_housing_search", "demo_housing_search_smoke")
        and "search_config" not in inputs
    ):
        inputs["search_config"] = search_config_from_inputs(inputs)
    normalized["inputs"] = inputs

    outputs = dict(normalized.get("outputs") or {})
    diagnostics = dict(outputs.get("diagnostics") or {})
    for key in ("captured_stdout", "captured_stderr"):
        if key in normalized and key not in diagnostics:
            diagnostics[key] = normalized[key]
    if diagnostics:
        outputs["diagnostics"] = diagnostics
    normalized["outputs"] = normalize_outputs_for_protocol(outputs)

    warnings = normalized.get("warnings")
    normalized["warnings"] = warnings if isinstance(warnings, list) else []
    errors = normalized.get("errors")
    normalized["errors"] = errors if isinstance(errors, list) else []

    return normalized


def normalize_outputs_for_protocol(outputs: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(outputs)

    summary = dict(normalized.get("summary") or {})
    for key in (
        "segment_id",
        "target",
        "search_id",
        "selected_count",
        "zero_selected_is_valid",
        "pilot_smoke",
    ):
        if key in normalized and key not in summary:
            summary[key] = normalized[key]

    diagnostics = dict(normalized.get("diagnostics") or {})
    for key in ("captured_stdout", "captured_stderr"):
        if key in normalized and key not in diagnostics:
            diagnostics[key] = normalized[key]

    assets = normalized.get("assets")
    if assets is None:
        assets = []

    normalized["summary"] = summary
    normalized["assets"] = assets
    normalized["diagnostics"] = diagnostics
    return normalized


def _candidate_assets_by_model_id(outputs: Dict[str, Any]) -> Dict[str, str]:
    by_model_id: Dict[str, str] = {}
    for asset in outputs.get("assets") or []:
        if asset.get("type") != "candidate_model":
            continue
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str):
            continue
        model_id = asset_id.rsplit(":", 1)[-1]
        if model_id:
            by_model_id[model_id] = asset_id
    return by_model_id


def _metric_highlights(candidate: Dict[str, Any]) -> Dict[str, Any]:
    metrics = candidate.get("metrics")
    if not isinstance(metrics, dict):
        return {}
    return {
        name: value
        for name, value in metrics.items()
        if isinstance(value, (int, float)) and value is not None
    }


def enrich_summary_for_protocol(manifest: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Populate stable summary fields once assets and run inputs are known."""
    normalized = normalize_outputs_for_protocol(outputs)
    workflow_id = manifest.get("workflow_id") or manifest.get("workflow")
    summary = dict(normalized.get("summary") or {})
    selected_models = list(normalized.get("selected_models") or [])
    first_model = selected_models[0] if selected_models else {}
    best_model_id = first_model.get("model_id") if isinstance(first_model, dict) else None
    assets_by_model_id = _candidate_assets_by_model_id(normalized)
    best_candidate_model_id = assets_by_model_id.get(best_model_id) if best_model_id else None

    if workflow_id in SEARCH_WORKFLOW_IDS:
        selected_count = normalized.get("selected_count", len(selected_models))
        summary.update(
            {
                "summary_type": "search_summary",
                "target": normalized.get("target") or manifest.get("target"),
                "segment_id": normalized.get("segment_id") or manifest.get("segment_id"),
                "search_id": normalized.get("search_id"),
                "selected_count": selected_count,
                "zero_selected_is_valid": bool(normalized.get("zero_selected_is_valid", False)),
                "pilot_smoke": bool(
                    normalized.get(
                        "pilot_smoke",
                        (manifest.get("inputs") or {}).get("pilot_smoke", False),
                    )
                ),
                "candidate_count": len(selected_models),
            }
        )
        if best_model_id:
            summary["best_model_id"] = best_model_id
        if best_candidate_model_id:
            summary["best_candidate_model_id"] = best_candidate_model_id
        if int(selected_count or 0) == 0 and "no_candidate_reason" not in summary:
            summary["no_candidate_reason"] = "no_models_passed_filters"

    if workflow_id in FIT_WORKFLOW_IDS:
        inputs = manifest.get("inputs") or {}
        summary.update(
            {
                "summary_type": "fit_summary",
                "target": normalized.get("target") or manifest.get("target"),
                "segment_id": normalized.get("segment_id") or manifest.get("segment_id"),
                "selected_count": normalized.get("selected_count", len(selected_models)),
                "model_count": len(selected_models),
                "sample": inputs.get("sample"),
                "specs": list(inputs.get("specs") or []),
            }
        )
        if best_model_id:
            summary["best_model_id"] = best_model_id
        if best_candidate_model_id:
            summary["best_candidate_model_id"] = best_candidate_model_id
        if isinstance(first_model, dict):
            if first_model.get("formula") is not None:
                summary["best_formula"] = first_model.get("formula")
            highlights = _metric_highlights(first_model)
            if highlights:
                summary["metric_highlights"] = highlights

    normalized["summary"] = {key: value for key, value in summary.items() if value is not None}
    return normalized


def candidate_model_artifact_refs(
    outputs: Dict[str, Any],
    model_id: str,
) -> List[Dict[str, Any]]:
    segment_id = outputs.get("segment_id")
    search_id = outputs.get("search_id")
    if not segment_id or not search_id:
        return []

    segment = asset_path_segment(segment_id)
    search = asset_path_segment(search_id)
    model = asset_path_segment(model_id)
    return [
        ArtifactRef(
            uri=f"technic://Segment/{segment}/cms/{search}",
            role="technic_search_directory",
            media_type="application/vnd.lego.technic-search",
        ).to_dict(),
        ArtifactRef(
            uri=f"technic://Segment/{segment}/cms/{search}/{model}",
            role="technic_candidate_model",
            media_type="application/vnd.lego.technic-candidate",
        ).to_dict(),
    ]


def write_candidate_model_assets(
    manifest: Dict[str, Any],
    outputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist CandidateModel assets for selected models and update run outputs."""
    selected_models = outputs.get("selected_models") or []
    if not selected_models:
        return outputs

    normalized = normalize_outputs_for_protocol(outputs)
    target = normalized.get("target") or manifest.get("target") or "unknown_target"
    segment_id = normalized.get("segment_id") or manifest.get("segment_id")
    target_segment = asset_path_segment(target)
    run_segment = asset_path_segment(manifest["run_id"])
    created_at = manifest.get("completed_at") or utc_timestamp()
    existing_refs = list(normalized.get("assets") or [])
    index_entries: List[Dict[str, Any]] = []

    for index, candidate in enumerate(selected_models, start=1):
        model_id = candidate.get("model_id") or f"candidate_{index:03d}"
        model_segment = asset_path_segment(model_id)
        asset_id = f"candidate_model:{target}:{manifest['run_id']}:{model_id}"
        asset_ref = AssetRef(
            asset_id=asset_id,
            type="candidate_model",
            role="selected_model",
            uri=f"asset://candidate_model/{target_segment}/{run_segment}/{model_segment}.json",
        )
        asset_payload = {
            "protocol_version": PROTOCOL_VERSION,
            "asset_id": asset_id,
            "type": "candidate_model",
            "created_at": created_at,
            "created_by_run_id": manifest["run_id"],
            "source_asset_ids": [],
            "artifact_refs": candidate_model_artifact_refs(normalized, model_id),
            "source_run_id": manifest["run_id"],
            "target": target,
            "segment_id": segment_id,
            "model_id": model_id,
            "formula": candidate.get("formula"),
            "specs": candidate.get("specs", []),
            "metrics": candidate.get("metrics", {}),
        }
        write_asset_json(asset_ref, asset_payload)
        asset_ref_payload = asset_ref.to_dict()
        if asset_ref_payload not in existing_refs:
            existing_refs.append(asset_ref_payload)
        index_entries.append(
            {
                "asset_id": asset_id,
                "type": "candidate_model",
                "uri": asset_ref.uri,
                "created_at": created_at,
                "created_by_run_id": manifest["run_id"],
                "source_run_id": manifest["run_id"],
                "target": target,
            }
        )

    normalized["assets"] = existing_refs
    upsert_asset_index_entries(index_entries)
    return normalized


def _evaluation_status(selected_count: int, zero_selected_is_valid: bool) -> str:
    if selected_count == 0 and zero_selected_is_valid:
        return "no_candidates_selected"
    return "needs_review"


def write_evaluation_result_asset(
    manifest: Dict[str, Any],
    outputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist a minimal EvaluationResult asset for successful search workflows."""
    workflow_id = manifest.get("workflow_id") or manifest.get("workflow")
    if workflow_id not in SEARCH_WORKFLOW_IDS:
        return outputs

    normalized = normalize_outputs_for_protocol(outputs)
    target = normalized.get("target") or manifest.get("target") or "unknown_target"
    segment_id = normalized.get("segment_id") or manifest.get("segment_id")
    target_segment = asset_path_segment(target)
    run_id = manifest["run_id"]
    run_segment = asset_path_segment(run_id)
    created_at = manifest.get("completed_at") or utc_timestamp()
    asset_id = f"evaluation_result:{target}:{run_id}"
    asset_ref = AssetRef(
        asset_id=asset_id,
        type="evaluation_result",
        role="search_evaluation",
        uri=f"asset://evaluation_result/{target_segment}/{run_segment}.json",
    )

    candidate_model_ids = [
        asset["asset_id"]
        for asset in normalized.get("assets", [])
        if asset.get("type") == "candidate_model" and "asset_id" in asset
    ]
    selected_count = normalized.get("selected_count")
    if selected_count is None:
        selected_count = len(candidate_model_ids)
    candidate_count = len(candidate_model_ids)
    zero_selected_is_valid = bool(normalized.get("zero_selected_is_valid", False))
    warnings = manifest.get("warnings") if isinstance(manifest.get("warnings"), list) else []
    summary = {
        "status": _evaluation_status(int(selected_count), zero_selected_is_valid),
        "selected_count": int(selected_count),
        "zero_selected_is_valid": zero_selected_is_valid,
        "warning_count": len(warnings),
    }

    asset_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "asset_id": asset_id,
        "type": "evaluation_result",
        "created_at": created_at,
        "created_by_run_id": run_id,
        "source_asset_ids": candidate_model_ids,
        "artifact_refs": [],
        "source_run_id": run_id,
        "target": target,
        "segment_id": segment_id,
        "candidate_count": candidate_count,
        "selected_count": int(selected_count),
        "candidate_model_ids": candidate_model_ids,
        "summary": summary,
        "warnings": warnings,
        "diagnostics": {},
        "weaknesses": [],
        "recommended_next_actions": [],
    }
    if candidate_model_ids:
        asset_payload["best_candidate_model_id"] = candidate_model_ids[0]

    write_asset_json(asset_ref, asset_payload)

    existing_refs = list(normalized.get("assets") or [])
    asset_ref_payload = asset_ref.to_dict()
    if asset_ref_payload not in existing_refs:
        existing_refs.append(asset_ref_payload)
    normalized["assets"] = existing_refs
    upsert_asset_index_entries(
        [
            {
                "asset_id": asset_id,
                "type": "evaluation_result",
                "uri": asset_ref.uri,
                "created_at": created_at,
                "created_by_run_id": run_id,
                "source_run_id": run_id,
                "target": target,
            }
        ]
    )
    return normalized


def base_manifest(
    *,
    run_id: str,
    workflow: str,
    segment_id: str,
    target: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": utc_timestamp(),
        "workflow": workflow,
        "workflow_id": workflow,
        "segment_id": segment_id,
        "target": target,
        "status": "running",
        "inputs": inputs,
        "outputs": {},
        "warnings": [],
        "errors": [],
    }


def fail_manifest(manifest: Dict[str, Any], exc: BaseException) -> Dict[str, Any]:
    manifest["status"] = "failed"
    manifest["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    manifest["errors"] = [
        {
            "code": "WORKFLOW_FAILED",
            "severity": "error",
            "fatal": True,
            "message": str(exc),
            "exception_type": type(exc).__name__,
        }
    ]
    manifest["completed_at"] = utc_timestamp()
    return manifest
