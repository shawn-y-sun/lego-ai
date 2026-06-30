from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


RUNS_ROOT = Path(".lego") / "runs"
LATEST_FILE = RUNS_ROOT / "latest"


def utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"


def _run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def _manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / "manifest.json"


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


def base_manifest(
    *,
    run_id: str,
    workflow: str,
    segment_id: str,
    target: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": utc_timestamp(),
        "workflow": workflow,
        "segment_id": segment_id,
        "target": target,
        "status": "running",
        "inputs": inputs,
        "outputs": {},
    }


def fail_manifest(manifest: Dict[str, Any], exc: BaseException) -> Dict[str, Any]:
    manifest["status"] = "failed"
    manifest["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    manifest["completed_at"] = utc_timestamp()
    return manifest
