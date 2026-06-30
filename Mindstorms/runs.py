from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .protocol import ASSETS_ROOT, PROTOCOL_VERSION, AssetRef, asset_ref_to_path


RUNS_ROOT = Path(".lego") / "runs"
LATEST_FILE = RUNS_ROOT / "latest"
_SAFE_ASSET_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def utc_timestamp() -> str:
    value = datetime.now(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"


def _run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def _manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / "manifest.json"


def _asset_index_path() -> Path:
    return ASSETS_ROOT / "index.json"


def write_manifest(manifest: Dict[str, Any]) -> Path:
    run_id = manifest["run_id"]
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(run_id)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    LATEST_FILE.write_text(run_id, encoding="utf-8")
    return path


def read_manifest(run_id: str) -> Dict[str, Any]:
    if run_id == "latest":
        run_id = latest_run_id()
    path = _manifest_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"No run manifest found for '{run_id}'.")
    return json.loads(path.read_text(encoding="utf-8"))


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


def read_asset_index() -> Dict[str, Any]:
    path = _asset_index_path()
    if not path.exists():
        return {"protocol_version": PROTOCOL_VERSION, "assets": []}
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_asset_index_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    index = read_asset_index()
    by_id = {
        entry["asset_id"]: entry
        for entry in index.get("assets", [])
        if "asset_id" in entry
    }
    for entry in entries:
        by_id[entry["asset_id"]] = entry

    index = {
        "protocol_version": PROTOCOL_VERSION,
        "assets": sorted(
            by_id.values(),
            key=lambda item: (
                item.get("type", ""),
                item.get("asset_id", ""),
                item.get("created_at", ""),
            ),
        ),
    }
    path = _asset_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


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


def _asset_path_segment(value: Any) -> str:
    segment = _SAFE_ASSET_SEGMENT_RE.sub("_", str(value).strip()).strip("._")
    if not segment:
        raise ValueError("Asset path segment cannot be empty.")
    return segment


def write_candidate_model_assets(
    manifest: Dict[str, Any],
    outputs: Dict[str, Any],
) -> Dict[str, Any]:
    selected_models = outputs.get("selected_models") or []
    if not selected_models:
        return outputs

    normalized = normalize_outputs_for_protocol(outputs)
    target = normalized.get("target") or manifest.get("target") or "unknown_target"
    target_segment = _asset_path_segment(target)
    created_at = manifest.get("completed_at") or utc_timestamp()
    existing_refs = list(normalized.get("assets") or [])
    index_entries: List[Dict[str, Any]] = []

    for index, candidate in enumerate(selected_models, start=1):
        model_id = candidate.get("model_id") or f"candidate_{index:03d}"
        model_segment = _asset_path_segment(model_id)
        asset_id = f"candidate_model:{target}:{model_id}"
        asset_ref = AssetRef(
            asset_id=asset_id,
            type="candidate_model",
            role="selected_model",
            uri=f"asset://candidate_model/{target_segment}/{model_segment}.json",
        )
        asset_payload = {
            "protocol_version": PROTOCOL_VERSION,
            "asset_id": asset_id,
            "type": "candidate_model",
            "created_at": created_at,
            "created_by_run_id": manifest["run_id"],
            "source_asset_ids": [],
            "artifact_refs": [],
            "source_run_id": manifest["run_id"],
            "target": target,
            "model_id": model_id,
            "formula": candidate.get("formula"),
            "specs": candidate.get("specs", []),
            "metrics": candidate.get("metrics", {}),
        }
        asset_path = asset_ref_to_path(asset_ref, assets_root=ASSETS_ROOT)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_text(
            json.dumps(asset_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
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
