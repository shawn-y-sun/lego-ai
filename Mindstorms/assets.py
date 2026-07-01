from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .protocol import ASSETS_ROOT as DEFAULT_ASSETS_ROOT
from .protocol import PROTOCOL_VERSION, AssetRef, asset_ref_to_path, asset_uri_to_path


ASSETS_ROOT = DEFAULT_ASSETS_ROOT
_SAFE_ASSET_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def asset_index_path() -> Path:
    return ASSETS_ROOT / "index.json"


def asset_path_segment(value: Any) -> str:
    segment = _SAFE_ASSET_SEGMENT_RE.sub("_", str(value).strip()).strip("._")
    if not segment:
        raise ValueError("Asset path segment cannot be empty.")
    return segment


def write_asset_json(asset_ref: AssetRef, payload: Dict[str, Any]) -> Path:
    path = asset_ref_to_path(asset_ref, assets_root=ASSETS_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_asset_index() -> Dict[str, Any]:
    path = asset_index_path()
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
    path = asset_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def list_assets(
    *,
    asset_type: Optional[str] = None,
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    asset_entries = list(read_asset_index().get("assets", []))
    if asset_type is not None:
        asset_entries = [asset for asset in asset_entries if asset.get("type") == asset_type]
    if target is not None:
        asset_entries = [asset for asset in asset_entries if asset.get("target") == target]
    if limit is not None:
        asset_entries = asset_entries[:limit]
    return asset_entries


def read_asset(asset_id: str) -> Dict[str, Any]:
    for asset_ref in read_asset_index().get("assets", []):
        if asset_ref.get("asset_id") != asset_id:
            continue
        asset_path = asset_uri_to_path(asset_ref["uri"], assets_root=ASSETS_ROOT)
        if not asset_path.exists():
            raise FileNotFoundError(f"Asset file is missing for '{asset_id}'.")
        return {
            "asset": json.loads(asset_path.read_text(encoding="utf-8")),
            "asset_ref": asset_ref,
            "asset_path": str(asset_path),
        }
    raise FileNotFoundError(f"No asset found for '{asset_id}'.")
