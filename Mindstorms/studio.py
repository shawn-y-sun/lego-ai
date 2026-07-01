"""Read-only Studio snapshot and static HTML export for protocol runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Tuple

from . import assets, runs
from .protocol import PROTOCOL_VERSION, asset_uri_to_path


HEAVY_DIAGNOSTIC_CHARS = 2000


def _utc_timestamp() -> str:
    value = datetime.now(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def _project_root() -> str:
    return str(Path.cwd())


def _finding(code: str, severity: str, message: str, **details: Any) -> Dict[str, Any]:
    payload = {"code": code, "severity": severity, "message": message}
    payload.update({key: value for key, value in details.items() if value is not None})
    return payload


def _manifest_paths() -> List[Path]:
    return sorted(
        runs.RUNS_ROOT.glob("*/manifest.json"),
        key=lambda path: (path.stat().st_mtime_ns, path.parent.name),
        reverse=True,
    )


def _latest_run_id() -> Optional[str]:
    try:
        return runs.latest_run_id()
    except FileNotFoundError:
        return None


def _read_normalized_manifests() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    manifests: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []

    for path in _manifest_paths():
        run_id = path.parent.name
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(
                {
                    "code": "UNPARSEABLE_MANIFEST",
                    "run_id": run_id,
                    "path": str(path),
                    "message": str(exc),
                }
            )
            findings.append(
                _finding(
                    "UNPARSEABLE_MANIFEST",
                    "error",
                    "A run manifest could not be parsed as JSON.",
                    run_id=run_id,
                    path=str(path),
                )
            )
            continue

        if "workflow_id" not in raw and raw.get("workflow") is not None:
            findings.append(
                _finding(
                    "LEGACY_WORKFLOW_FIELD_NORMALIZED",
                    "info",
                    "A legacy manifest used workflow; Studio normalized workflow_id in memory.",
                    run_id=raw.get("run_id", run_id),
                    workflow=raw.get("workflow"),
                )
            )

        normalized = runs.normalize_manifest_for_protocol(raw)
        normalized["_manifest_path"] = str(path)
        manifests.append(normalized)

    return manifests, diagnostics, findings


def _warning_key(record: Dict[str, Any]) -> str:
    return str(record.get("code") or record.get("message") or "UNSPECIFIED_WARNING")


def _summarize_records(
    manifests: Iterable[Dict[str, Any]],
    field: str,
) -> List[Dict[str, Any]]:
    grouped: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "code": "",
            "count": 0,
            "severity": None,
            "fatal": None,
            "runs": [],
            "message": None,
        }
    )
    for manifest in manifests:
        run_id = manifest.get("run_id")
        for record in manifest.get(field, []) or []:
            if not isinstance(record, dict):
                continue
            code = _warning_key(record)
            item = grouped[code]
            item["code"] = code
            item["count"] += int(record.get("count") or 1)
            item["severity"] = item["severity"] or record.get("severity")
            item["fatal"] = item["fatal"] if item["fatal"] is not None else record.get("fatal")
            item["message"] = item["message"] or record.get("message")
            if run_id and run_id not in item["runs"]:
                item["runs"].append(run_id)

    return sorted(grouped.values(), key=lambda item: (-item["count"], item["code"]))


def _run_timeline_item(manifest: Dict[str, Any]) -> Dict[str, Any]:
    outputs = dict(manifest.get("outputs") or {})
    summary = dict(outputs.get("summary") or {})
    assets_out = outputs.get("assets") if isinstance(outputs.get("assets"), list) else []
    return {
        "run_id": manifest.get("run_id"),
        "workflow_id": manifest.get("workflow_id") or manifest.get("workflow"),
        "status": manifest.get("status"),
        "created_at": manifest.get("created_at"),
        "completed_at": manifest.get("completed_at"),
        "target": manifest.get("target") or summary.get("target"),
        "segment_id": manifest.get("segment_id") or summary.get("segment_id"),
        "warning_count": len(manifest.get("warnings") or []),
        "error_count": len(manifest.get("errors") or []),
        "output_asset_count": len(assets_out),
        "selected_count": summary.get("selected_count", outputs.get("selected_count")),
        "zero_selected_is_valid": summary.get(
            "zero_selected_is_valid",
            outputs.get("zero_selected_is_valid"),
        ),
    }


def _read_asset_index(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    path = assets.asset_index_path()
    if not path.exists():
        findings.append(
            _finding(
                "ASSET_INDEX_MISSING",
                "warning",
                ".lego/assets/index.json is missing; run outputs may still reference assets.",
                path=str(path),
            )
        )
        return []

    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(
            _finding(
                "ASSET_INDEX_UNPARSEABLE",
                "error",
                ".lego/assets/index.json could not be parsed as JSON.",
                path=str(path),
                message_detail=str(exc),
            )
        )
        return []

    entries = index.get("assets") if isinstance(index.get("assets"), list) else []
    if not entries:
        findings.append(
            _finding(
                "ASSET_INDEX_EMPTY",
                "info",
                ".lego/assets/index.json exists but contains no assets.",
                path=str(path),
            )
        )
    return list(entries)


def _asset_inventory(
    asset_entries: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    inventory: List[Dict[str, Any]] = []
    for entry in asset_entries:
        asset_id = entry.get("asset_id")
        path: Optional[Path] = None
        uri_error: Optional[str] = None
        try:
            path = asset_uri_to_path(entry.get("uri", ""), assets_root=assets.ASSETS_ROOT)
        except Exception as exc:
            uri_error = str(exc)

        resolved = bool(path and path.exists())
        item = {
            "asset_id": asset_id,
            "type": entry.get("type"),
            "role": entry.get("role"),
            "target": entry.get("target"),
            "created_at": entry.get("created_at"),
            "created_by_run_id": entry.get("created_by_run_id"),
            "source_run_id": entry.get("source_run_id"),
            "uri": entry.get("uri"),
            "path": str(path) if path is not None else None,
            "resolved": resolved,
        }
        if uri_error:
            item["uri_error"] = uri_error
            findings.append(
                _finding(
                    "INDEXED_ASSET_INVALID_URI",
                    "error",
                    "An indexed asset has an invalid asset URI.",
                    asset_id=asset_id,
                    uri=entry.get("uri"),
                )
            )
        elif not resolved:
            findings.append(
                _finding(
                    "INDEXED_ASSET_FILE_MISSING",
                    "warning",
                    "An indexed asset points to a missing file.",
                    asset_id=asset_id,
                    path=str(path),
                )
            )
        inventory.append(item)

    return sorted(inventory, key=lambda item: (str(item.get("type")), str(item.get("asset_id"))))


def _lineage(
    manifests: List[Dict[str, Any]],
    asset_entries: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    indexed = {entry.get("asset_id"): entry for entry in asset_entries if entry.get("asset_id")}
    entries: List[Dict[str, Any]] = []

    for manifest in manifests:
        run_id = manifest.get("run_id")
        outputs = dict(manifest.get("outputs") or {})
        for ref in outputs.get("assets") or []:
            if not isinstance(ref, dict):
                continue
            asset_id = ref.get("asset_id")
            indexed_ref = indexed.get(asset_id)
            status = "resolved"
            path: Optional[Path] = None
            if indexed_ref is None:
                status = "missing_from_index"
                findings.append(
                    _finding(
                        "RUN_OUTPUT_ASSET_MISSING_FROM_INDEX",
                        "warning",
                        "A run output references an asset id absent from the asset index.",
                        run_id=run_id,
                        asset_id=asset_id,
                    )
                )
            else:
                try:
                    path = asset_uri_to_path(indexed_ref.get("uri", ""), assets_root=assets.ASSETS_ROOT)
                    if not path.exists():
                        status = "missing_file"
                except Exception:
                    status = "invalid_uri"

            entries.append(
                {
                    "run_id": run_id,
                    "asset_id": asset_id,
                    "type": ref.get("type") or (indexed_ref or {}).get("type"),
                    "role": ref.get("role") or (indexed_ref or {}).get("role"),
                    "uri": ref.get("uri") or (indexed_ref or {}).get("uri"),
                    "status": status,
                    "path": str(path) if path is not None else None,
                }
            )

    return entries


def _diagnostics(
    manifests: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for manifest in manifests:
        run_id = manifest.get("run_id")
        diagnostics = dict((manifest.get("outputs") or {}).get("diagnostics") or {})
        for key, value in diagnostics.items():
            size = len(value) if isinstance(value, str) else len(json.dumps(value, sort_keys=True))
            entry = {"code": "RUN_DIAGNOSTIC", "run_id": run_id, "key": key, "size": size}
            entries.append(entry)
            if size >= HEAVY_DIAGNOSTIC_CHARS:
                findings.append(
                    _finding(
                        "RUN_DIAGNOSTICS_HEAVY",
                        "info",
                        "A run carries large captured diagnostics that may deserve stable summary fields.",
                        run_id=run_id,
                        key=key,
                        size=size,
                    )
                )
    return entries


def _asset_counts_by_type(asset_entries: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(str(entry.get("type") or "unknown") for entry in asset_entries)
    return dict(sorted(counts.items()))


def build_studio_snapshot() -> Dict[str, Any]:
    """Build the read-only StudioSnapshot JSON interface from local protocol files."""
    manifests, diagnostics, findings = _read_normalized_manifests()
    if not manifests and not diagnostics:
        findings.append(
            _finding(
                "NO_RUNS_FOUND",
                "info",
                "No Mindstorms run manifests were found under .lego/runs.",
                path=str(runs.RUNS_ROOT),
            )
        )

    asset_entries = _read_asset_index(findings)
    diagnostics.extend(_diagnostics(manifests, findings))
    inventory = _asset_inventory(asset_entries, findings)
    lineage = _lineage(manifests, asset_entries, findings)

    return {
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": _utc_timestamp(),
        "project_root": _project_root(),
        "health": {
            "run_count": len(manifests),
            "asset_count": len(asset_entries),
            "latest_run_id": _latest_run_id(),
            "asset_counts_by_type": _asset_counts_by_type(asset_entries),
            "finding_count": len(findings),
            "findings": findings,
        },
        "runs_timeline": [_run_timeline_item(manifest) for manifest in manifests],
        "asset_inventory": inventory,
        "lineage": lineage,
        "diagnostics": diagnostics,
        "warnings_summary": _summarize_records(manifests, "warnings"),
        "errors_summary": _summarize_records(manifests, "errors"),
        "raw_runs": [
            {
                "run_id": manifest.get("run_id"),
                "manifest_path": manifest.get("_manifest_path"),
                "manifest": {key: value for key, value in manifest.items() if not key.startswith("_")},
            }
            for manifest in manifests
        ],
    }


def _render_health(snapshot: Dict[str, Any]) -> str:
    findings = snapshot.get("health", {}).get("findings", [])
    if not findings:
        return "<p class=\"empty\">No protocol health findings.</p>"
    rows = []
    for finding in findings:
        rows.append(
            "<tr>"
            f"<td>{escape(str(finding.get('severity', '')))}</td>"
            f"<td>{escape(str(finding.get('code', '')))}</td>"
            f"<td>{escape(str(finding.get('message', '')))}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Severity</th><th>Code</th><th>Finding</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_runs(snapshot: Dict[str, Any]) -> str:
    rows = []
    for run in snapshot.get("runs_timeline", []):
        rows.append(
            "<tr>"
            f"<td>{escape(str(run.get('run_id') or ''))}</td>"
            f"<td>{escape(str(run.get('workflow_id') or ''))}</td>"
            f"<td>{escape(str(run.get('status') or ''))}</td>"
            f"<td>{escape(str(run.get('created_at') or ''))}</td>"
            f"<td>{escape(str(run.get('target') or ''))}</td>"
            f"<td>{escape(str(run.get('selected_count') if run.get('selected_count') is not None else ''))}</td>"
            f"<td>{escape(str(run.get('warning_count') or 0))}</td>"
            f"<td>{escape(str(run.get('output_asset_count') or 0))}</td>"
            "</tr>"
        )
    if not rows:
        return "<p class=\"empty\">No runs were found yet. Studio can still render the protocol shell for review.</p>"
    return "<table><thead><tr><th>Run</th><th>Workflow</th><th>Status</th><th>Created</th><th>Target</th><th>Selected</th><th>Warnings</th><th>Assets</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_assets(snapshot: Dict[str, Any]) -> str:
    assets_list = snapshot.get("asset_inventory", [])
    if not assets_list:
        run_count = snapshot.get("health", {}).get("run_count", 0)
        if run_count:
            return "<p class=\"empty\">No indexed assets were found, although runs exist. This is useful protocol feedback: runs may need durable asset refs or the asset index may be transitional.</p>"
        return "<p class=\"empty\">No indexed assets were found.</p>"
    rows = []
    for asset in assets_list:
        rows.append(
            "<tr>"
            f"<td>{escape(str(asset.get('type') or ''))}</td>"
            f"<td>{escape(str(asset.get('asset_id') or ''))}</td>"
            f"<td>{escape(str(asset.get('target') or ''))}</td>"
            f"<td>{escape('yes' if asset.get('resolved') else 'no')}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Type</th><th>Asset</th><th>Target</th><th>File</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_run_detail(snapshot: Dict[str, Any]) -> str:
    raw_runs = snapshot.get("raw_runs", [])
    if not raw_runs:
        return "<p class=\"empty\">No raw run manifests available.</p>"
    blocks = []
    for run in raw_runs[:5]:
        body = escape(json.dumps(run.get("manifest", {}), indent=2, sort_keys=True))
        blocks.append(f"<details><summary>{escape(str(run.get('run_id')))}</summary><pre>{body}</pre></details>")
    return "".join(blocks)


def _html_document(snapshot: Dict[str, Any]) -> str:
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)
    embedded_json = escape(snapshot_json)
    run_count = snapshot.get("health", {}).get("run_count", 0)
    asset_count = snapshot.get("health", {}).get("asset_count", 0)
    finding_count = snapshot.get("health", {}).get("finding_count", 0)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LEGO AI Studio Zero</title>
  <style>
    :root {{ color-scheme: light; font-family: "Segoe UI", Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #20242a; }}
    header {{ background: #ffffff; border-bottom: 1px solid #d9dee7; padding: 24px 32px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; }}
    section {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; margin-bottom: 18px; padding: 18px; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }}
    .stat {{ border: 1px solid #d9dee7; border-radius: 8px; padding: 10px 12px; min-width: 120px; }}
    .label {{ color: #667085; font-size: 12px; }}
    .value {{ font-size: 22px; font-weight: 650; margin-top: 2px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e8ef; padding: 9px 8px; text-align: left; vertical-align: top; }}
    th {{ color: #475467; font-weight: 650; background: #f2f4f7; }}
    .empty {{ color: #667085; margin: 0; }}
    pre {{ overflow: auto; background: #111827; color: #e5e7eb; border-radius: 8px; padding: 12px; font-size: 12px; }}
    summary {{ cursor: pointer; font-weight: 650; padding: 8px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>LEGO AI Studio Zero</h1>
    <div class="label">Generated {escape(str(snapshot.get("generated_at")))}</div>
    <div class="stats">
      <div class="stat"><div class="label">Runs</div><div class="value">{run_count}</div></div>
      <div class="stat"><div class="label">Assets</div><div class="value">{asset_count}</div></div>
      <div class="stat"><div class="label">Findings</div><div class="value">{finding_count}</div></div>
    </div>
  </header>
  <main>
    <section><h2>Runs Timeline</h2>{_render_runs(snapshot)}</section>
    <section><h2>Protocol Health</h2>{_render_health(snapshot)}</section>
    <section><h2>Asset Inventory</h2>{_render_assets(snapshot)}</section>
    <section><h2>Lineage</h2><pre>{escape(json.dumps(snapshot.get("lineage", []), indent=2, sort_keys=True))}</pre></section>
    <section><h2>Run Detail</h2>{_render_run_detail(snapshot)}</section>
  </main>
  <script id="studio-snapshot" type="application/json">{embedded_json}</script>
</body>
</html>
"""


def export_studio_html(snapshot: Dict[str, Any], output_path: Path) -> Path:
    """Write a dependency-light static HTML protocol explorer."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_html_document(snapshot), encoding="utf-8")
    return output_path
