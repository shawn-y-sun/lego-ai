"""Agent-friendly CLI commands for Mindstorms protocol workflows."""

from __future__ import annotations

import argparse
import json
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from . import __version__
from .assets import list_assets, read_asset
from .features import build_features_from_proposal
from .recipes import (
    build_proposed_recipe,
    recipe_proposal_slug,
    write_approved_feature_recipe_asset,
    write_feature_recipe_proposal_asset,
)
from .runs import (
    base_manifest,
    fail_manifest,
    list_runs,
    new_run_id,
    normalize_outputs_for_protocol,
    read_manifest,
    run_artifacts_dir,
    search_config_from_inputs,
    write_candidate_model_assets,
    write_evaluation_result_asset,
    write_manifest,
)
from .warnings import summarize_warning_text


DEMO_SEGMENT_ID = "home_price_GR1"
DEMO_TARGET = "home_price_GR1"


def _demo_housing():
    from . import demo_housing

    return demo_housing


def emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _run_quietly(func: Callable[[], Dict[str, Any]], *, verbose: bool) -> Dict[str, Any]:
    if verbose:
        return func()
    captured_out = StringIO()
    captured_err = StringIO()
    with redirect_stdout(captured_out), redirect_stderr(captured_err):
        result = func()
    logs = captured_out.getvalue().strip()
    errors = captured_err.getvalue().strip()
    if logs:
        result["captured_stdout"] = logs[-4000:]
    if errors:
        result["captured_stderr"] = errors[-4000:]
    warnings = summarize_warning_text("\n".join(part for part in (logs, errors) if part))
    if warnings:
        result["warnings"] = warnings
    return result


def _complete_manifest(manifest: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
    manifest["status"] = "succeeded"
    manifest["warnings"] = outputs.get("warnings", [])
    manifest["errors"] = []
    from .runs import utc_timestamp

    manifest["completed_at"] = utc_timestamp()
    normalized_outputs = normalize_outputs_for_protocol(outputs)
    manifest["outputs"] = write_evaluation_result_asset(
        manifest,
        write_candidate_model_assets(manifest, normalized_outputs),
    )
    return manifest


def command_catalog() -> Dict[str, Any]:
    return {
        "commands": [
            {
                "name": "demo init",
                "purpose": "Build the demo housing segment and write a run manifest.",
                "example": "lego demo init --json",
                "safe_for_pilot": True,
            },
            {
                "name": "demo fit-single",
                "purpose": "Fit one known-good demo candidate model.",
                "example": "lego demo fit-single --vars USMORT30Y --json",
                "safe_for_pilot": True,
            },
            {
                "name": "demo search-smoke",
                "purpose": "Run a small relaxed-filter demo search that exercises search plumbing and should select at least one model.",
                "example": "lego demo search-smoke --json",
                "safe_for_pilot": True,
            },
            {
                "name": "demo search",
                "purpose": "Run an honest small demo model search; zero selected models can be a valid modeling outcome.",
                "example": "lego demo search --top-n 5 --max-var-num 2 --max-lag 1 --json",
                "safe_for_pilot": False,
            },
            {
                "name": "runs list",
                "purpose": "List recent Mindstorms run manifests.",
                "example": "lego runs list --json",
                "safe_for_pilot": True,
            },
            {
                "name": "run inspect",
                "purpose": "Inspect one run manifest by run ID or latest.",
                "example": "lego run inspect latest --json",
                "safe_for_pilot": True,
            },
            {
                "name": "assets list",
                "purpose": "List indexed protocol assets.",
                "example": "lego assets list --json",
                "safe_for_pilot": True,
            },
            {
                "name": "asset inspect",
                "purpose": "Inspect one protocol asset by asset ID.",
                "example": "lego asset inspect candidate_model:home_price_GR1:cm1 --json",
                "safe_for_pilot": True,
            },
            {
                "name": "recipe propose",
                "purpose": "Create a deterministic feature recipe proposal asset from explicit inputs.",
                "example": 'lego recipe propose --request "Create yield slope" --name USYC10_2 --expression "USGOV10Y - USGOV2Y" --source-columns USGOV10Y USGOV2Y --json',
                "safe_for_pilot": True,
            },
            {
                "name": "recipe approve",
                "purpose": "Create an approved feature recipe asset from a proposal asset.",
                "example": "lego recipe approve --proposal-id feature_recipe_proposal:yield_curve_steepness --approved-by model_owner --json",
                "safe_for_pilot": True,
            },
            {
                "name": "features build",
                "purpose": "Build deterministic feature outputs from a feature recipe proposal asset.",
                "example": "lego features build --recipe-id feature_recipe:yield_curve_steepness --source-csv \"Demo Data/macro_monthly.csv\" --date-column observation_date --output-name macro_monthly_enriched --json",
                "safe_for_pilot": True,
            },
        ]
    }


def cmd_demo_init(args: argparse.Namespace) -> int:
    demo_housing = _demo_housing()
    run_id = new_run_id("init")
    inputs: Dict[str, Any] = {}
    manifest = base_manifest(
        run_id=run_id,
        workflow="demo_housing_init",
        segment_id=DEMO_SEGMENT_ID,
        target=DEMO_TARGET,
        inputs=inputs,
    )
    try:
        def action() -> Dict[str, Any]:
            seg = demo_housing.build_demo_segment()
            return {
                "segment_id": seg.segment_id,
                "target": seg.target,
                "model_type": getattr(seg.model_type, "__name__", str(seg.model_type)),
                "model_cls": getattr(seg.model_cls, "__name__", str(seg.model_cls)),
                "default_driver_pool": demo_housing.DEFAULT_DRIVER_POOL,
            }

        outputs = _run_quietly(action, verbose=args.verbose)
        manifest = _complete_manifest(manifest, outputs)
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_demo_fit_single(args: argparse.Namespace) -> int:
    demo_housing = _demo_housing()
    specs = args.vars or ["USMORT30Y"]
    run_id = new_run_id("fit")
    inputs = {"specs": specs, "sample": args.sample}
    manifest = base_manifest(
        run_id=run_id,
        workflow="demo_housing_fit_single",
        segment_id=DEMO_SEGMENT_ID,
        target=DEMO_TARGET,
        inputs=inputs,
    )
    try:
        outputs = _run_quietly(
            lambda: demo_housing.run_fit_single(specs=specs, sample=args.sample),
            verbose=args.verbose,
        )
        manifest = _complete_manifest(manifest, outputs)
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if args.debug:
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_demo_search(args: argparse.Namespace) -> int:
    demo_housing = _demo_housing()
    desired_pool = args.pool or demo_housing.DEFAULT_DRIVER_POOL
    forced_in = demo_housing.default_forced_in(args.seasonality)
    run_id = new_run_id("search")
    search_suffix = run_id[len("search_") :] if run_id.startswith("search_") else run_id
    search_id = f"search_{DEMO_SEGMENT_ID}_{search_suffix}"
    inputs = {
        "desired_pool": desired_pool,
        "forced_in": demo_housing.serialize_specs(forced_in),
        "top_n": args.top_n,
        "max_var_num": args.max_var_num,
        "max_lag": args.max_lag,
        "periods": args.periods,
    }
    inputs["search_config"] = search_config_from_inputs(inputs)
    manifest = base_manifest(
        run_id=run_id,
        workflow="demo_housing_search",
        segment_id=DEMO_SEGMENT_ID,
        target=DEMO_TARGET,
        inputs=inputs,
    )
    try:
        outputs = _run_quietly(
            lambda: demo_housing.run_search(
                desired_pool=desired_pool,
                forced_in=forced_in,
                top_n=args.top_n,
                max_var_num=args.max_var_num,
                max_lag=args.max_lag,
                periods=args.periods,
                search_id=search_id,
            ),
            verbose=args.verbose,
        )
        manifest = _complete_manifest(manifest, outputs)
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if args.debug:
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_demo_search_smoke(args: argparse.Namespace) -> int:
    demo_housing = _demo_housing()
    run_id = new_run_id("search_smoke")
    search_suffix = run_id[len("search_smoke_") :] if run_id.startswith("search_smoke_") else run_id
    search_id = f"search_{DEMO_SEGMENT_ID}_smoke_{search_suffix}"
    inputs = {
        "desired_pool": ["USMORT30Y"],
        "forced_in": [],
        "top_n": 1,
        "max_var_num": 1,
        "max_lag": 0,
        "periods": [1],
        "pilot_smoke": True,
        "filter_profile": "relaxed_demo_smoke",
    }
    inputs["search_config"] = search_config_from_inputs(inputs)
    manifest = base_manifest(
        run_id=run_id,
        workflow="demo_housing_search_smoke",
        segment_id=DEMO_SEGMENT_ID,
        target=DEMO_TARGET,
        inputs=inputs,
    )
    try:
        outputs = _run_quietly(
            lambda: demo_housing.run_search_smoke(search_id=search_id),
            verbose=args.verbose,
        )
        manifest = _complete_manifest(manifest, outputs)
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if args.debug:
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_help_json(args: argparse.Namespace) -> int:
    emit_json({"ok": True, **command_catalog()})
    return 0


def cmd_runs_list(args: argparse.Namespace) -> int:
    emit_json({"ok": True, "runs": list_runs(limit=args.limit)})
    return 0


def cmd_run_inspect(args: argparse.Namespace) -> int:
    try:
        emit_json({"ok": True, "run": read_manifest(args.run_id)})
        return 0
    except Exception as exc:
        emit_json({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})
        return 1


def cmd_assets_list(args: argparse.Namespace) -> int:
    emit_json(
        {
            "ok": True,
            "assets": list_assets(
                asset_type=args.type,
                target=args.target,
                limit=args.limit,
            ),
        }
    )
    return 0


def cmd_asset_inspect(args: argparse.Namespace) -> int:
    try:
        payload = read_asset(args.asset_id)
        emit_json({"ok": True, **payload})
        return 0
    except Exception as exc:
        emit_json({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})
        return 1


def cmd_recipe_propose(args: argparse.Namespace) -> int:
    """Create a deterministic FeatureRecipeProposal run and asset."""
    run_id = new_run_id("recipe_proposal")
    available_columns = list(args.available_columns or args.source_columns)
    proposed_recipe = build_proposed_recipe(
        name=args.name,
        expression=args.expression,
        source_columns=list(args.source_columns),
        category=args.category,
        rationale=args.rationale,
        recipe_kind=args.recipe_kind,
        expression_language=args.expression_language,
    )
    slug = args.slug or recipe_proposal_slug(args.name)
    inputs = {
        "request": args.request,
        "scope": args.scope,
        "available_columns": available_columns,
        "proposed_recipes": [proposed_recipe],
    }
    manifest = base_manifest(
        run_id=run_id,
        workflow="propose_feature_recipes",
        segment_id="feature_recipes",
        target="feature_recipes",
        inputs=inputs,
    )
    try:
        from .runs import utc_timestamp

        manifest["status"] = "succeeded"
        manifest["warnings"] = []
        manifest["errors"] = []
        manifest["completed_at"] = utc_timestamp()
        manifest["outputs"] = write_feature_recipe_proposal_asset(
            manifest,
            {"assets": []},
            request=args.request,
            scope=args.scope,
            available_columns=available_columns,
            proposed_recipes=[proposed_recipe],
            slug=slug,
        )
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if getattr(args, "debug", False):
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_recipe_approve(args: argparse.Namespace) -> int:
    """Create an approved FeatureRecipe asset without mutating its proposal."""
    run_id = new_run_id("approve_feature_recipe")
    inputs = {
        "proposal_id": args.proposal_id,
        "approved_by": args.approved_by,
        "approval_rationale": args.rationale,
        "slug": args.slug,
    }
    manifest = base_manifest(
        run_id=run_id,
        workflow="approve_feature_recipe",
        segment_id="feature_recipes",
        target="feature_recipes",
        inputs=inputs,
    )
    try:
        from .runs import utc_timestamp

        manifest["status"] = "succeeded"
        manifest["warnings"] = []
        manifest["errors"] = []
        manifest["completed_at"] = utc_timestamp()
        manifest["outputs"] = write_approved_feature_recipe_asset(
            manifest,
            {"assets": []},
            proposal_id=args.proposal_id,
            approved_by=args.approved_by,
            approval_rationale=args.rationale,
            slug=args.slug,
        )
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if getattr(args, "debug", False):
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def cmd_features_build(args: argparse.Namespace) -> int:
    """Build deterministic feature artifacts from a proposal or approved recipe."""
    run_id = new_run_id("build_features")
    source_asset_id = args.recipe_id or args.proposal_id
    inputs = {
        "proposal_id": args.proposal_id,
        "recipe_id": args.recipe_id,
        "source_csv": str(args.source_csv),
        "date_column": args.date_column,
        "output_name": args.output_name,
    }
    manifest = base_manifest(
        run_id=run_id,
        workflow="build_features",
        segment_id=args.output_name,
        target=args.output_name,
        inputs=inputs,
    )
    try:
        from .runs import utc_timestamp

        manifest["status"] = "succeeded"
        manifest["warnings"] = []
        manifest["errors"] = []
        manifest["completed_at"] = utc_timestamp()
        manifest["outputs"] = build_features_from_proposal(
            manifest=manifest,
            proposal_id=source_asset_id,
            source_csv=Path(args.source_csv),
            date_column=args.date_column,
            output_name=args.output_name,
            artifacts_dir=run_artifacts_dir(run_id),
        )
        path = write_manifest(manifest)
        emit_json({"ok": True, "manifest_path": str(path), "run": manifest})
        return 0
    except Exception as exc:
        manifest = fail_manifest(manifest, exc)
        if getattr(args, "debug", False):
            manifest["traceback"] = traceback.format_exc()
        path = write_manifest(manifest)
        emit_json({"ok": False, "manifest_path": str(path), "run": manifest})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m Mindstorms.cli")
    parser.add_argument("--version", action="version", version=f"Mindstorms {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    help_cmd = sub.add_parser("help", help="Emit a machine-readable command catalog.")
    help_cmd.add_argument("--json", action="store_true", help="Emit the command catalog as JSON.")
    help_cmd.set_defaults(func=cmd_help_json)

    demo = sub.add_parser("demo", help="Run demo housing workflows.")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)

    init = demo_sub.add_parser("init", help="Build the demo housing segment.")
    init.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    init.add_argument("--verbose", action="store_true")
    init.set_defaults(func=cmd_demo_init)

    fit = demo_sub.add_parser("fit-single", help="Fit one demo candidate model.")
    fit.add_argument("--vars", nargs="+", help="Feature specs to fit.")
    fit.add_argument("--sample", choices=["in", "full", "both"], default="in")
    fit.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    fit.add_argument("--verbose", action="store_true")
    fit.add_argument("--debug", action="store_true")
    fit.set_defaults(func=cmd_demo_fit_single)

    search = demo_sub.add_parser("search", help="Run a small demo model search.")
    search.add_argument("--pool", nargs="+", help="Driver pool. Defaults to a small demo pool.")
    search.add_argument("--top-n", type=int, default=5)
    search.add_argument("--max-var-num", type=int, default=2)
    search.add_argument("--max-lag", type=int, default=1)
    search.add_argument("--periods", nargs="+", type=int)
    search.add_argument("--seasonality", action="store_true", help="Force monthly seasonal dummies.")
    search.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    search.add_argument("--verbose", action="store_true")
    search.add_argument("--debug", action="store_true")
    search.set_defaults(func=cmd_demo_search)

    search_smoke = demo_sub.add_parser("search-smoke", help="Run a reliable demo search smoke test.")
    search_smoke.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    search_smoke.add_argument("--verbose", action="store_true")
    search_smoke.add_argument("--debug", action="store_true")
    search_smoke.set_defaults(func=cmd_demo_search_smoke)

    runs = sub.add_parser("runs", help="Inspect Mindstorms runs.")
    runs_sub = runs.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_sub.add_parser("list", help="List recent runs.")
    runs_list.add_argument("--limit", type=int)
    runs_list.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    runs_list.set_defaults(func=cmd_runs_list)

    run = sub.add_parser("run", help="Inspect one Mindstorms run.")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    inspect = run_sub.add_parser("inspect", help="Inspect a run manifest.")
    inspect.add_argument("run_id", help="Run ID or 'latest'.")
    inspect.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    inspect.set_defaults(func=cmd_run_inspect)

    assets = sub.add_parser("assets", help="Inspect protocol assets.")
    assets_sub = assets.add_subparsers(dest="assets_command", required=True)
    assets_list = assets_sub.add_parser("list", help="List indexed assets.")
    assets_list.add_argument("--type", help="Filter by asset type.")
    assets_list.add_argument("--target", help="Filter by target.")
    assets_list.add_argument("--limit", type=int)
    assets_list.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    assets_list.set_defaults(func=cmd_assets_list)

    asset = sub.add_parser("asset", help="Inspect one protocol asset.")
    asset_sub = asset.add_subparsers(dest="asset_command", required=True)
    asset_inspect = asset_sub.add_parser("inspect", help="Inspect an asset by asset ID.")
    asset_inspect.add_argument("asset_id")
    asset_inspect.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    asset_inspect.set_defaults(func=cmd_asset_inspect)

    recipe = sub.add_parser("recipe", help="Create and inspect feature recipe protocol assets.")
    recipe_sub = recipe.add_subparsers(dest="recipe_command", required=True)
    propose = recipe_sub.add_parser("propose", help="Create a deterministic feature recipe proposal.")
    propose.add_argument("--request", required=True)
    propose.add_argument("--name", required=True)
    propose.add_argument("--expression", required=True)
    propose.add_argument("--source-columns", nargs="+", required=True)
    propose.add_argument("--available-columns", nargs="+")
    propose.add_argument("--category", required=True)
    propose.add_argument("--scope", choices=["project", "domain", "global"], default="project")
    propose.add_argument("--recipe-kind", default="arithmetic")
    propose.add_argument("--expression-language", default="lego_formula_v0")
    propose.add_argument("--rationale")
    propose.add_argument("--slug")
    propose.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    propose.add_argument("--debug", action="store_true")
    propose.set_defaults(func=cmd_recipe_propose)

    approve = recipe_sub.add_parser("approve", help="Create an approved feature recipe from a proposal.")
    approve.add_argument("--proposal-id", required=True)
    approve.add_argument("--approved-by")
    approve.add_argument("--rationale")
    approve.add_argument("--slug")
    approve.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    approve.add_argument("--debug", action="store_true")
    approve.set_defaults(func=cmd_recipe_approve)

    features = sub.add_parser("features", help="Build deterministic feature artifacts.")
    features_sub = features.add_subparsers(dest="features_command", required=True)
    build = features_sub.add_parser("build", help="Build features from a proposal asset.")
    source_group = build.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--proposal-id")
    source_group.add_argument("--recipe-id")
    build.add_argument("--source-csv", required=True)
    build.add_argument("--date-column")
    build.add_argument("--output-name", required=True)
    build.add_argument("--json", action="store_true", help="Accepted for agent-friendly command symmetry.")
    build.add_argument("--debug", action="store_true")
    build.set_defaults(func=cmd_features_build)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
