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
METRIC_HIGHLIGHT_KEYS = ("rsquared", "rsquared_adj", "aic", "bic")


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
    item = {
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
    for key in (
        "summary_type",
        "candidate_count",
        "model_count",
        "best_model_id",
        "best_candidate_model_id",
        "best_formula",
        "metric_highlights",
        "pilot_smoke",
        "no_candidate_reason",
    ):
        if key in summary:
            item[key] = summary[key]
    return item


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


def _expected_asset_health(
    manifests: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> None:
    for manifest in manifests:
        if manifest.get("status") != "succeeded":
            continue

        run_id = manifest.get("run_id")
        workflow_id = manifest.get("workflow_id") or manifest.get("workflow")
        outputs = dict(manifest.get("outputs") or {})
        summary = dict(outputs.get("summary") or {})
        output_assets = outputs.get("assets") if isinstance(outputs.get("assets"), list) else []
        asset_types = {asset.get("type") for asset in output_assets if isinstance(asset, dict)}
        selected_count = summary.get("selected_count", outputs.get("selected_count"))
        selected_count = int(selected_count or 0)

        if workflow_id == "demo_housing_fit_single" and selected_count > 0:
            if "candidate_model" not in asset_types:
                findings.append(
                    _finding(
                        "EXPECTED_CANDIDATE_MODEL_ASSET_MISSING",
                        "warning",
                        "A successful fit run selected a model but did not reference a candidate_model asset.",
                        run_id=run_id,
                        workflow_id=workflow_id,
                        selected_count=selected_count,
                    )
                )

        if workflow_id in {"demo_housing_search", "demo_housing_search_smoke"}:
            if selected_count > 0 and "candidate_model" not in asset_types:
                findings.append(
                    _finding(
                        "EXPECTED_CANDIDATE_MODEL_ASSET_MISSING",
                        "warning",
                        "A successful search run selected models but did not reference candidate_model assets.",
                        run_id=run_id,
                        workflow_id=workflow_id,
                        selected_count=selected_count,
                    )
                )
            if "evaluation_result" not in asset_types:
                findings.append(
                    _finding(
                        "EXPECTED_EVALUATION_RESULT_ASSET_MISSING",
                        "warning",
                        "A successful search run did not reference an evaluation_result asset.",
                        run_id=run_id,
                        workflow_id=workflow_id,
                        selected_count=selected_count,
                    )
                )


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


def _json_size(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    return len(json.dumps(value, sort_keys=True))


def _metric_highlights(metrics: Any) -> Dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    return {key: metrics[key] for key in METRIC_HIGHLIGHT_KEYS if key in metrics}


def _run_lookup(manifests: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(manifest.get("run_id")): manifest for manifest in manifests if manifest.get("run_id")}


def _asset_detail_base(
    asset: Dict[str, Any],
    inventory_item: Dict[str, Any],
    runs_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    source_run_id = asset.get("source_run_id") or asset.get("created_by_run_id")
    source_run = runs_by_id.get(str(source_run_id)) if source_run_id is not None else None
    return {
        "asset_id": asset.get("asset_id") or inventory_item.get("asset_id"),
        "type": asset.get("type") or inventory_item.get("type"),
        "created_at": asset.get("created_at") or inventory_item.get("created_at"),
        "created_by_run_id": asset.get("created_by_run_id") or inventory_item.get("created_by_run_id"),
        "source_run_id": source_run_id,
        "workflow_id": (source_run or {}).get("workflow_id") or (source_run or {}).get("workflow"),
        "target": asset.get("target") or inventory_item.get("target"),
        "segment_id": asset.get("segment_id"),
        "artifact_refs": asset.get("artifact_refs") if isinstance(asset.get("artifact_refs"), list) else [],
        "raw_available": True,
        "raw": asset,
    }


def _candidate_model_detail(
    asset: Dict[str, Any],
    inventory_item: Dict[str, Any],
    runs_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    detail = _asset_detail_base(asset, inventory_item, runs_by_id)
    detail.update(
        {
            "render_kind": "candidate_model_card",
            "model_id": asset.get("model_id"),
            "formula": asset.get("formula"),
            "specs": asset.get("specs") if isinstance(asset.get("specs"), list) else [],
            "metric_highlights": _metric_highlights(asset.get("metrics")),
        }
    )
    return detail


def _diagnostics_summary(diagnostics: Any) -> List[Dict[str, Any]]:
    if not isinstance(diagnostics, dict):
        return []
    return [
        {"key": str(key), "size": _json_size(value)}
        for key, value in sorted(diagnostics.items(), key=lambda item: str(item[0]))
    ]


def _evaluation_result_detail(
    asset: Dict[str, Any],
    inventory_item: Dict[str, Any],
    runs_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    detail = _asset_detail_base(asset, inventory_item, runs_by_id)
    summary = asset.get("summary") if isinstance(asset.get("summary"), dict) else {}
    warnings = asset.get("warnings") if isinstance(asset.get("warnings"), list) else []
    detail.update(
        {
            "render_kind": "evaluation_result_card",
            "candidate_count": asset.get("candidate_count"),
            "selected_count": asset.get("selected_count", summary.get("selected_count")),
            "zero_selected_is_valid": summary.get("zero_selected_is_valid"),
            "status": summary.get("status"),
            "best_candidate_model_id": asset.get("best_candidate_model_id"),
            "candidate_model_ids": (
                asset.get("candidate_model_ids") if isinstance(asset.get("candidate_model_ids"), list) else []
            ),
            "no_candidate_reason": summary.get("no_candidate_reason"),
            "warning_count": summary.get("warning_count", len(warnings)),
            "warnings": warnings,
            "diagnostics_summary": _diagnostics_summary(asset.get("diagnostics")),
        }
    )
    return detail


def _raw_asset_detail(
    asset: Dict[str, Any],
    inventory_item: Dict[str, Any],
    runs_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    detail = _asset_detail_base(asset, inventory_item, runs_by_id)
    detail["render_kind"] = "raw_asset_detail"
    return detail


def _asset_details(
    inventory: List[Dict[str, Any]],
    manifests: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    runs_by_id = _run_lookup(manifests)
    details: List[Dict[str, Any]] = []
    for item in inventory:
        if not item.get("resolved") or not item.get("path"):
            continue
        path = Path(str(item["path"]))
        try:
            asset = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                _finding(
                    "ASSET_DETAIL_UNREADABLE",
                    "warning",
                    "A resolved asset file could not be loaded for Studio detail rendering.",
                    asset_id=item.get("asset_id"),
                    path=str(path),
                    message_detail=str(exc),
                )
            )
            continue

        asset_type = asset.get("type") or item.get("type")
        if asset_type == "candidate_model":
            details.append(_candidate_model_detail(asset, item, runs_by_id))
        elif asset_type == "evaluation_result":
            details.append(_evaluation_result_detail(asset, item, runs_by_id))
        else:
            details.append(_raw_asset_detail(asset, item, runs_by_id))

    return sorted(
        details,
        key=lambda detail: (
            str(detail.get("created_at") or ""),
            str(detail.get("asset_id") or ""),
        ),
        reverse=True,
    )


def _finding_counts(findings: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    counts = Counter(str(finding.get(field) or "unknown") for finding in findings)
    return dict(sorted(counts.items()))


def _not_reported(value: Any) -> Any:
    return value if value is not None else "not reported"


def _reviewable_run(runs_timeline: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for run in runs_timeline:
        if run.get("summary_type") == "search_summary":
            return run
    for run in runs_timeline:
        if run.get("summary_type") == "fit_summary":
            return run
    return None


def _details_for_run(snapshot: Dict[str, Any], run_id: Optional[str]) -> List[Dict[str, Any]]:
    if not run_id:
        return []
    return [
        detail
        for detail in snapshot.get("asset_details", [])
        if detail.get("source_run_id") == run_id or detail.get("created_by_run_id") == run_id
    ]


def _model_option(detail: Dict[str, Any], selected_asset_id: Optional[str]) -> Dict[str, Any]:
    metrics = detail.get("metric_highlights") if isinstance(detail.get("metric_highlights"), dict) else {}
    drivers = detail.get("specs") if isinstance(detail.get("specs"), list) else []
    asset_id = detail.get("asset_id")
    return {
        "asset_id": asset_id,
        "model_id": detail.get("model_id") or asset_id,
        "formula": detail.get("formula"),
        "drivers": drivers,
        "driver_count": len(drivers),
        "metric_highlights": metrics,
        "source_run_id": detail.get("source_run_id"),
        "target": detail.get("target"),
        "segment_id": detail.get("segment_id"),
        "selected": bool(asset_id and selected_asset_id and asset_id == selected_asset_id),
        "raw": detail.get("raw"),
    }


def _search_summary_from_run(run: Dict[str, Any]) -> Dict[str, Any]:
    fields = (
        "candidate_count",
        "model_count",
        "selected_count",
        "zero_selected_is_valid",
        "no_candidate_reason",
        "pilot_smoke",
    )
    return {field: _not_reported(run.get(field)) for field in fields}


def _selected_model_empty_state(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    selected_count = run.get("selected_count")
    zero_selected_is_valid = run.get("zero_selected_is_valid")
    if selected_count not in (0, "0") and zero_selected_is_valid is not True:
        return None
    if zero_selected_is_valid is True:
        return {
            "title": "No model selected",
            "message": "This search completed with zero selected models, and zero-selected is valid.",
            "reason": run.get("no_candidate_reason"),
        }
    return {
        "title": "No model selected",
        "message": "This run did not report a selected model.",
        "reason": run.get("no_candidate_reason"),
    }


def _review_diagnostics(snapshot: Dict[str, Any], review_run_id: Optional[str]) -> Dict[str, Any]:
    findings = snapshot.get("health", {}).get("findings", [])
    run_findings = [
        finding
        for finding in findings
        if not review_run_id or finding.get("run_id") in (None, review_run_id)
    ]
    return {
        "finding_count": len(findings),
        "findings": run_findings,
        "warnings_summary": snapshot.get("warnings_summary", []),
        "errors_summary": snapshot.get("errors_summary", []),
        "asset_inventory": snapshot.get("asset_inventory", []),
    }


def build_search_review_view(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Derive a modeler-facing Search Review view model from a StudioSnapshot."""
    runs_timeline = snapshot.get("runs_timeline", [])
    review_run = _reviewable_run(runs_timeline)
    if review_run is None:
        return {
            "title": "Search Review",
            "generated_at": snapshot.get("generated_at"),
            "empty": True,
            "empty_message": "No reviewable search results were found.",
            "selected_model": None,
            "selected_model_empty_state": None,
            "model_options": [],
            "search_summary": {},
            "diagnostics": _review_diagnostics(snapshot, None),
            "run_history": runs_timeline,
            "raw_detail_refs": [],
        }

    review_run_id = review_run.get("run_id")
    details = _details_for_run(snapshot, review_run_id)
    selected_asset_id = review_run.get("best_candidate_model_id")
    if selected_asset_id is None:
        for detail in details:
            if detail.get("render_kind") == "evaluation_result_card" and detail.get("best_candidate_model_id"):
                selected_asset_id = detail.get("best_candidate_model_id")
                break

    candidate_details = [
        detail for detail in details if detail.get("render_kind") == "candidate_model_card"
    ]
    options = [_model_option(detail, selected_asset_id) for detail in candidate_details]
    selected_model = next((option for option in options if option["selected"]), None)
    if selected_model is None and selected_asset_id:
        selected_model = next((option for option in options if option["asset_id"] == selected_asset_id), None)
    if selected_model is None and len(options) == 1 and review_run.get("selected_count") == 1:
        selected_model = dict(options[0])
        selected_model["selected"] = True
        options[0]["selected"] = True

    raw_detail_refs = [
        {
            "asset_id": detail.get("asset_id"),
            "type": detail.get("type"),
            "render_kind": detail.get("render_kind"),
        }
        for detail in details
    ]

    return {
        "title": "Search Review",
        "empty": False,
        "generated_at": snapshot.get("generated_at"),
        "review_run_id": review_run_id,
        "workflow_id": review_run.get("workflow_id"),
        "status": review_run.get("status"),
        "target": review_run.get("target"),
        "segment_id": review_run.get("segment_id"),
        "selected_model": selected_model,
        "selected_model_empty_state": None if selected_model else _selected_model_empty_state(review_run),
        "model_options": options,
        "search_summary": _search_summary_from_run(review_run),
        "diagnostics": _review_diagnostics(snapshot, review_run_id),
        "run_history": runs_timeline,
        "raw_detail_refs": raw_detail_refs,
    }


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
    _expected_asset_health(manifests, findings)
    details = _asset_details(inventory, manifests, findings)

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
            "finding_counts_by_severity": _finding_counts(findings, "severity"),
            "finding_counts_by_code": _finding_counts(findings, "code"),
            "findings": findings,
        },
        "runs_timeline": [_run_timeline_item(manifest) for manifest in manifests],
        "asset_inventory": inventory,
        "asset_details": details,
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
    severity_counts = snapshot.get("health", {}).get("finding_counts_by_severity", {})
    summary = ""
    if severity_counts:
        chips = [
            f"<span class=\"chip\">{escape(str(key))}: {escape(str(value))}</span>"
            for key, value in severity_counts.items()
        ]
        summary = "<div class=\"chips\">" + "".join(chips) + "</div>"
    if not findings:
        return summary + "<p class=\"empty\">No protocol health findings.</p>"
    rows = []
    for finding in sorted(
        findings,
        key=lambda item: (str(item.get("severity") or ""), str(item.get("code") or "")),
    ):
        rows.append(
            "<tr>"
            f"<td>{escape(str(finding.get('severity', '')))}</td>"
            f"<td>{escape(str(finding.get('code', '')))}</td>"
            f"<td>{escape(str(finding.get('message', '')))}</td>"
            "</tr>"
        )
    return summary + "<table><thead><tr><th>Severity</th><th>Code</th><th>Finding</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_runs(snapshot: Dict[str, Any]) -> str:
    rows = []
    for run in snapshot.get("runs_timeline", []):
        summary_bits = []
        if run.get("summary_type") == "fit_summary":
            if run.get("best_formula"):
                summary_bits.append(str(run.get("best_formula")))
            metrics = run.get("metric_highlights") if isinstance(run.get("metric_highlights"), dict) else {}
            if metrics:
                first_key = next(iter(metrics))
                summary_bits.append(f"{first_key}: {metrics[first_key]}")
        elif run.get("summary_type") == "search_summary":
            if run.get("candidate_count") is not None:
                summary_bits.append(f"{run.get('selected_count')}/{run.get('candidate_count')} selected")
            if run.get("pilot_smoke"):
                summary_bits.append("pilot smoke")
            if run.get("no_candidate_reason"):
                summary_bits.append(str(run.get("no_candidate_reason")))
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
            f"<td>{escape(' | '.join(summary_bits))}</td>"
            "</tr>"
        )
    if not rows:
        return "<p class=\"empty\">No runs were found yet. Studio can still render the protocol shell for review.</p>"
    return "<table><thead><tr><th>Run</th><th>Workflow</th><th>Status</th><th>Created</th><th>Target</th><th>Selected</th><th>Warnings</th><th>Assets</th><th>Summary</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_value(value: Any) -> str:
    if value is None or value == "":
        return "not reported"
    return str(value)


def _render_search_review_header(review: Dict[str, Any]) -> str:
    if review.get("empty"):
        return f"<p class=\"empty\">{escape(str(review.get('empty_message') or 'No reviewable search results were found.'))}</p>"
    return (
        "<dl class=\"meta hero-meta\">"
        f"<div><dt>Target</dt><dd>{escape(_render_value(review.get('target')))}</dd></div>"
        f"<div><dt>Segment</dt><dd>{escape(_render_value(review.get('segment_id')))}</dd></div>"
        f"<div><dt>Source Run</dt><dd>{escape(_render_value(review.get('review_run_id')))}</dd></div>"
        f"<div><dt>Status</dt><dd>{escape(_render_value(review.get('status')))}</dd></div>"
        f"<div><dt>Workflow</dt><dd>{escape(_render_value(review.get('workflow_id')))}</dd></div>"
        f"<div><dt>Generated</dt><dd>{escape(_render_value(review.get('generated_at')))}</dd></div>"
        "</dl>"
    )


def _render_selected_model(review: Dict[str, Any]) -> str:
    selected = review.get("selected_model")
    if not selected:
        empty_state = review.get("selected_model_empty_state") or {}
        reason = empty_state.get("reason")
        reason_html = f"<p class=\"muted\">Reason: {escape(str(reason))}</p>" if reason else ""
        return (
            f"<h3>{escape(str(empty_state.get('title') or 'No model selected'))}</h3>"
            f"<p class=\"empty\">{escape(str(empty_state.get('message') or 'No selected model was reported.'))}</p>"
            f"{reason_html}"
        )

    return (
        "<article class=\"selected-model\">"
        f"<h3>{escape(_render_value(selected.get('model_id')))}</h3>"
        f"<div class=\"formula\">{escape(_render_value(selected.get('formula')))}</div>"
        "<h4>Drivers</h4>"
        f"{_render_chips(selected.get('drivers') or [])}"
        "<h4>Key Metrics</h4>"
        f"{_render_metric_highlights(selected.get('metric_highlights') or {})}"
        "<dl class=\"meta\">"
        f"<div><dt>Source Run</dt><dd>{escape(_render_value(selected.get('source_run_id')))}</dd></div>"
        f"<div><dt>Target</dt><dd>{escape(_render_value(selected.get('target')))}</dd></div>"
        f"<div><dt>Segment</dt><dd>{escape(_render_value(selected.get('segment_id')))}</dd></div>"
        f"<div><dt>Asset</dt><dd>{escape(_render_value(selected.get('asset_id')))}</dd></div>"
        "</dl>"
        "</article>"
    )


def _render_model_options(review: Dict[str, Any]) -> str:
    options = review.get("model_options", [])
    if not options:
        return "<p class=\"empty\">No model options were reported for this run.</p>"
    rows = []
    for option in options:
        metrics = option.get("metric_highlights") if isinstance(option.get("metric_highlights"), dict) else {}
        rows.append(
            "<tr>"
            f"<td>{escape('selected' if option.get('selected') else '')}</td>"
            f"<td>{escape(_render_value(option.get('model_id')))}</td>"
            f"<td>{escape(_render_value(option.get('formula')))}</td>"
            f"<td>{escape(', '.join(str(value) for value in option.get('drivers') or []) or str(option.get('driver_count') or 0))}</td>"
            f"<td>{escape(_render_value(metrics.get('rsquared')))}</td>"
            f"<td>{escape(_render_value(metrics.get('rsquared_adj')))}</td>"
            f"<td>{escape(_render_value(metrics.get('aic')))}</td>"
            f"<td>{escape(_render_value(metrics.get('bic')))}</td>"
            f"<td>{escape(_render_value(option.get('asset_id')))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th></th><th>Model</th><th>Formula</th><th>Drivers</th>"
        "<th>R2</th><th>Adj R2</th><th>AIC</th><th>BIC</th><th>Asset</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_search_summary(review: Dict[str, Any]) -> str:
    summary = review.get("search_summary", {})
    fields = (
        ("Candidate Models", "candidate_count"),
        ("Model Count", "model_count"),
        ("Selected Models", "selected_count"),
        ("Zero Selected Valid", "zero_selected_is_valid"),
        ("No Candidate Reason", "no_candidate_reason"),
        ("Pilot Smoke", "pilot_smoke"),
    )
    stats = [
        f"<div class=\"stat\"><div class=\"label\">{escape(label)}</div><div class=\"value small-value\">{escape(_render_value(summary.get(key)))}</div></div>"
        for label, key in fields
    ]
    return "<div class=\"stats\">" + "".join(stats) + "</div>"


def _render_diagnostics_section(snapshot: Dict[str, Any], review: Dict[str, Any]) -> str:
    diagnostics = review.get("diagnostics", {})
    findings = diagnostics.get("findings", [])
    if findings:
        finding_rows = []
        for finding in findings:
            finding_rows.append(
                "<tr>"
                f"<td>{escape(str(finding.get('severity') or ''))}</td>"
                f"<td>{escape(str(finding.get('code') or ''))}</td>"
                f"<td>{escape(str(finding.get('message') or ''))}</td>"
                "</tr>"
            )
        findings_html = (
            "<table><thead><tr><th>Severity</th><th>Code</th><th>Finding</th></tr></thead><tbody>"
            + "".join(finding_rows)
            + "</tbody></table>"
        )
    else:
        findings_html = "<p class=\"empty\">No diagnostics for the reviewed run.</p>"
    return (
        "<details><summary>System Checks</summary>"
        f"{_render_health(snapshot)}"
        "</details>"
        "<details><summary>Reviewed Run Findings</summary>"
        f"{findings_html}"
        "</details>"
        "<details><summary>Asset Inventory</summary>"
        f"{_render_assets(snapshot)}"
        "</details>"
    )


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


def _render_raw_json(value: Any) -> str:
    body = escape(json.dumps(value, indent=2, sort_keys=True))
    return f"<details class=\"raw-json\"><summary>Raw JSON</summary><pre>{body}</pre></details>"


def _render_chips(values: Iterable[Any]) -> str:
    chips = [f"<span class=\"chip\">{escape(str(value))}</span>" for value in values]
    return "<div class=\"chips\">" + "".join(chips) + "</div>" if chips else "<span class=\"muted\">none</span>"


def _render_metric_highlights(metrics: Dict[str, Any]) -> str:
    if not metrics:
        return "<p class=\"empty\">No headline metrics.</p>"
    rows = [
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
        for key, value in metrics.items()
    ]
    return "<table class=\"compact\"><tbody>" + "".join(rows) + "</tbody></table>"


def _render_warning_summary(warnings: List[Dict[str, Any]]) -> str:
    if not warnings:
        return "<p class=\"empty\">No warnings.</p>"
    rows = []
    for warning in warnings:
        rows.append(
            "<tr>"
            f"<td>{escape(str(warning.get('severity') or ''))}</td>"
            f"<td>{escape(str(warning.get('code') or ''))}</td>"
            f"<td>{escape(str(warning.get('message') or ''))}</td>"
            "</tr>"
        )
    return "<table class=\"compact\"><thead><tr><th>Severity</th><th>Code</th><th>Message</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_diagnostics_summary(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return "<p class=\"empty\">No structured diagnostics.</p>"
    rows = [
        f"<tr><td>{escape(str(entry.get('key') or ''))}</td><td>{escape(str(entry.get('size') or 0))}</td></tr>"
        for entry in entries
    ]
    return "<table class=\"compact\"><thead><tr><th>Key</th><th>Size</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_candidate_detail(detail: Dict[str, Any]) -> str:
    title = detail.get("model_id") or detail.get("asset_id")
    return (
        "<article class=\"asset-card\">"
        f"<h3>CandidateModel <span>{escape(str(title or ''))}</span></h3>"
        "<dl class=\"meta\">"
        f"<div><dt>Run</dt><dd>{escape(str(detail.get('source_run_id') or ''))}</dd></div>"
        f"<div><dt>Workflow</dt><dd>{escape(str(detail.get('workflow_id') or ''))}</dd></div>"
        f"<div><dt>Target</dt><dd>{escape(str(detail.get('target') or ''))}</dd></div>"
        f"<div><dt>Segment</dt><dd>{escape(str(detail.get('segment_id') or ''))}</dd></div>"
        "</dl>"
        f"<div class=\"formula\">{escape(str(detail.get('formula') or ''))}</div>"
        "<h4>Specs</h4>"
        f"{_render_chips(detail.get('specs') or [])}"
        "<h4>Metric Highlights</h4>"
        f"{_render_metric_highlights(detail.get('metric_highlights') or {})}"
        "<h4>Artifact Refs</h4>"
        f"{_render_chips([ref.get('uri') for ref in detail.get('artifact_refs') or [] if isinstance(ref, dict)])}"
        f"{_render_raw_json(detail.get('raw', {}))}"
        "</article>"
    )


def _render_evaluation_detail(detail: Dict[str, Any]) -> str:
    return (
        "<article class=\"asset-card\">"
        f"<h3>EvaluationResult <span>{escape(str(detail.get('asset_id') or ''))}</span></h3>"
        "<dl class=\"meta\">"
        f"<div><dt>Status</dt><dd>{escape(str(detail.get('status') or ''))}</dd></div>"
        f"<div><dt>Selected</dt><dd>{escape(str(detail.get('selected_count') or 0))}</dd></div>"
        f"<div><dt>Candidates</dt><dd>{escape(str(detail.get('candidate_count') or 0))}</dd></div>"
        f"<div><dt>Zero valid</dt><dd>{escape(str(detail.get('zero_selected_is_valid')))}</dd></div>"
        f"<div><dt>Run</dt><dd>{escape(str(detail.get('source_run_id') or ''))}</dd></div>"
        f"<div><dt>Workflow</dt><dd>{escape(str(detail.get('workflow_id') or ''))}</dd></div>"
        f"<div><dt>Target</dt><dd>{escape(str(detail.get('target') or ''))}</dd></div>"
        f"<div><dt>Segment</dt><dd>{escape(str(detail.get('segment_id') or ''))}</dd></div>"
        "</dl>"
        f"<p><strong>Best candidate:</strong> {escape(str(detail.get('best_candidate_model_id') or 'none'))}</p>"
        "<h4>Candidate Models</h4>"
        f"{_render_chips(detail.get('candidate_model_ids') or [])}"
        "<h4>Warnings</h4>"
        f"{_render_warning_summary(detail.get('warnings') or [])}"
        "<h4>Diagnostics Summary</h4>"
        f"{_render_diagnostics_summary(detail.get('diagnostics_summary') or [])}"
        f"{_render_raw_json(detail.get('raw', {}))}"
        "</article>"
    )


def _render_asset_details(snapshot: Dict[str, Any]) -> str:
    detail_items = snapshot.get("asset_details", [])
    if not detail_items:
        return "<p class=\"empty\">No resolved asset details are available yet.</p>"
    rendered = []
    for detail in detail_items:
        if detail.get("render_kind") == "candidate_model_card":
            rendered.append(_render_candidate_detail(detail))
        elif detail.get("render_kind") == "evaluation_result_card":
            rendered.append(_render_evaluation_detail(detail))
        else:
            rendered.append(
                "<article class=\"asset-card\">"
                f"<h3>Raw Asset <span>{escape(str(detail.get('asset_id') or ''))}</span></h3>"
                f"{_render_raw_json(detail.get('raw', {}))}"
                "</article>"
            )
    return "<div class=\"asset-grid\">" + "".join(rendered) + "</div>"


def _html_document(snapshot: Dict[str, Any]) -> str:
    review = build_search_review_view(snapshot)
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
  <title>LEGO AI Search Review</title>
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
    .small-value {{ font-size: 15px; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e8ef; padding: 9px 8px; text-align: left; vertical-align: top; }}
    th {{ color: #475467; font-weight: 650; background: #f2f4f7; }}
    .empty {{ color: #667085; margin: 0; }}
    .muted {{ color: #667085; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; }}
    .chip {{ border: 1px solid #d9dee7; border-radius: 999px; padding: 3px 8px; font-size: 12px; background: #f8fafc; }}
    .asset-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }}
    .asset-card {{ border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; background: #ffffff; }}
    .asset-card h3 {{ font-size: 16px; margin: 0 0 12px; }}
    .asset-card h3 span {{ color: #475467; font-weight: 500; overflow-wrap: anywhere; }}
    .asset-card h4 {{ font-size: 13px; margin: 14px 0 6px; color: #475467; }}
    .selected-model {{ border: 1px solid #b9c7dc; border-radius: 8px; padding: 16px; background: #fbfcff; }}
    .selected-model h3 {{ margin: 0 0 12px; font-size: 18px; }}
    .selected-model h4 {{ font-size: 13px; margin: 14px 0 6px; color: #475467; }}
    .hero-meta {{ margin-top: 14px; }}
    .formula {{ border-left: 3px solid #2563eb; background: #f8fafc; padding: 8px 10px; font-family: Consolas, monospace; overflow-wrap: anywhere; }}
    .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px 12px; margin: 0 0 12px; }}
    .meta div {{ min-width: 0; }}
    .meta dt {{ color: #667085; font-size: 12px; }}
    .meta dd {{ margin: 2px 0 0; overflow-wrap: anywhere; }}
    .compact th, .compact td {{ padding: 6px 7px; }}
    .raw-json {{ margin-top: 12px; }}
    pre {{ overflow: auto; background: #111827; color: #e5e7eb; border-radius: 8px; padding: 12px; font-size: 12px; }}
    summary {{ cursor: pointer; font-weight: 650; padding: 8px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>Search Review</h1>
    <div class="label">Generated {escape(str(snapshot.get("generated_at")))}</div>
    <div class="stats">
      <div class="stat"><div class="label">Runs</div><div class="value">{run_count}</div></div>
      <div class="stat"><div class="label">Assets</div><div class="value">{asset_count}</div></div>
      <div class="stat"><div class="label">Findings</div><div class="value">{finding_count}</div></div>
    </div>
  </header>
  <main>
    <section><h2>Search Review</h2>{_render_search_review_header(review)}</section>
    <section><h2>Selected Model</h2>{_render_selected_model(review)}</section>
    <section><h2>Model Options</h2>{_render_model_options(review)}</section>
    <section><h2>Search Summary</h2>{_render_search_summary(review)}</section>
    <section><h2>Diagnostics</h2>{_render_diagnostics_section(snapshot, review)}</section>
    <section><h2>Run History</h2>{_render_runs(snapshot)}</section>
    <section><h2>Raw Details</h2>{_render_asset_details(snapshot)}</section>
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
