from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


PROTOCOL_VERSION = "0.1"
ASSETS_ROOT = Path(".lego") / "assets"


def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


@dataclass
class ArtifactRef:
    uri: str
    media_type: Optional[str] = None
    role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "uri": self.uri,
                "media_type": self.media_type,
                "role": self.role,
            }
        )


@dataclass
class AssetRef:
    asset_id: str
    type: str
    uri: str
    role: Optional[str] = None
    label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "asset_id": self.asset_id,
                "type": self.type,
                "role": self.role,
                "label": self.label,
                "uri": self.uri,
            }
        )


@dataclass
class Asset:
    asset_id: str
    type: str
    created_at: str
    created_by_run_id: str
    source_asset_ids: List[str] = field(default_factory=list)
    artifact_refs: List[ArtifactRef] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION
    project_context_id: Optional[str] = None
    modeling_frame_id: Optional[str] = None
    modeling_iteration_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "protocol_version": self.protocol_version,
                "asset_id": self.asset_id,
                "type": self.type,
                "created_at": self.created_at,
                "created_by_run_id": self.created_by_run_id,
                "source_asset_ids": list(self.source_asset_ids),
                "artifact_refs": [ref.to_dict() for ref in self.artifact_refs],
                "project_context_id": self.project_context_id,
                "modeling_frame_id": self.modeling_frame_id,
                "modeling_iteration_id": self.modeling_iteration_id,
                "name": self.name,
                "description": self.description,
                "tags": list(self.tags) if self.tags else None,
            }
        )


@dataclass
class WarningRecord:
    code: str
    severity: str
    fatal: bool
    message: str
    count: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = _drop_none(
            {
                "code": self.code,
                "count": self.count,
                "severity": self.severity,
                "fatal": self.fatal,
                "message": self.message,
            }
        )
        payload.update(self.details)
        return payload


@dataclass
class ErrorRecord:
    code: str
    severity: str
    fatal: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "code": self.code,
            "severity": self.severity,
            "fatal": self.fatal,
            "message": self.message,
        }
        payload.update(self.details)
        return payload


@dataclass
class Run:
    run_id: str
    workflow_id: str
    status: str
    created_at: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    warnings: List[WarningRecord] = field(default_factory=list)
    errors: List[ErrorRecord] = field(default_factory=list)
    protocol_version: str = PROTOCOL_VERSION
    workflow_version: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    initiator: Optional[Dict[str, Any]] = None
    project_context_id: Optional[str] = None
    modeling_frame_id: Optional[str] = None
    modeling_iteration_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _drop_none(
            {
                "protocol_version": self.protocol_version,
                "run_id": self.run_id,
                "workflow_id": self.workflow_id,
                "workflow_version": self.workflow_version,
                "status": self.status,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "initiator": self.initiator,
                "project_context_id": self.project_context_id,
                "modeling_frame_id": self.modeling_frame_id,
                "modeling_iteration_id": self.modeling_iteration_id,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "warnings": [warning.to_dict() for warning in self.warnings],
                "errors": [error.to_dict() for error in self.errors],
            }
        )


def asset_uri_to_path(uri: str, assets_root: Path = ASSETS_ROOT) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "asset":
        raise ValueError("AssetRef URI must use the asset:// scheme.")
    if not parsed.netloc:
        raise ValueError("AssetRef URI must include an asset type path segment.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("AssetRef URI must not include params, query, or fragment.")

    raw_parts = [parsed.netloc] + [part for part in parsed.path.split("/") if part]
    if raw_parts[-1].lower().endswith(".json") is False:
        raise ValueError("AssetRef URI path must end in .json.")

    for part in raw_parts:
        if part in (".", ".."):
            raise ValueError("AssetRef URI path must not contain relative segments.")
        if "\\" in part or ":" in part:
            raise ValueError("AssetRef URI path must not contain local path syntax.")

    return assets_root.joinpath(*raw_parts)


def asset_ref_to_path(asset_ref: AssetRef, assets_root: Path = ASSETS_ROOT) -> Path:
    return asset_uri_to_path(asset_ref.uri, assets_root=assets_root)
