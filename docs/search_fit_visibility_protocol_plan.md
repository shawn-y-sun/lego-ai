# Search/Fit Visibility Protocol Plan

Status: planning draft

## Purpose

This plan defines a narrow Asset/Run Protocol slice for making the current demo
fit and search workflows visible without scraping raw stdout or stderr.

The slice covers:

- `lego demo fit-single --json`
- `lego demo search --json`
- `lego demo search-smoke --json`
- `.lego/runs/<run_id>/manifest.json`
- `outputs.summary`
- `outputs.assets`
- durable `candidate_model` and `evaluation_result` assets
- `.lego/assets/index.json`
- `lego assets list --json`
- `lego asset inspect <asset_id> --json`
- `lego studio snapshot --json`
- `lego studio export --html ...`

The design keeps `Technic` behind the Mindstorms adapter. Studio Zero and
agents should depend on protocol summaries and assets, not on captured
diagnostic text or `Technic` object internals.

## Scope

This is a protocol-content tightening slice, not a Studio UI expansion. The
goal is to make existing modeling state easier to inspect through the current
read-only Studio Zero surfaces.

In scope:

- Stable summary fields for fit and search runs.
- Minimal durable assets for selected candidate models.
- Minimal evaluation assets for search outcomes, including valid zero-selected
  searches.
- Health expectations that identify missing protocol content.
- Tests around run manifests, asset writing, asset inspection, and Studio
  snapshot visibility.

Out of scope:

- Interactive Studio.
- `lego studio serve`.
- New notebook workflows.
- General `ModelingFrame`, `SearchPool`, or `ModelingIteration` implementation.
- Search-pool curation rationale.
- A database or migration command for legacy manifests.
- Major `Technic` refactors.
- Full model documentation or model package export.

## Current Findings

Studio Zero showed the important weakness in the current protocol surface:
useful modeling facts were visible, but too many of them could still be
understood only by opening raw run details or diagnostics.

The current code is already partway through the target slice:

- `outputs.summary` is normalized from legacy top-level output fields.
- Search inputs include a stable `inputs.search_config` view.
- Selected models can be persisted as `candidate_model` assets.
- Search workflows can persist an `evaluation_result` asset.
- Studio Zero reads run timelines, asset inventory, lineage, diagnostics, and
  health findings.

The remaining tightening is to document the minimum stable fields, fill summary
gaps for `fit-single`, make search summaries explicit enough for Studio, and
make the durable asset invariant obvious to implementers and tests.

## SearchSummary

Search workflows must expose a stable summary under `outputs.summary`.

Applies to:

- `workflow_id = demo_housing_search`
- `workflow_id = demo_housing_search_smoke`

Required stable fields:

```json
{
  "summary_type": "search_summary",
  "target": "home_price_GR1",
  "segment_id": "home_price_GR1",
  "search_id": "search_home_price_GR1_...",
  "selected_count": 1,
  "zero_selected_is_valid": true,
  "pilot_smoke": true,
  "candidate_count": 1,
  "best_model_id": "cm1",
  "best_candidate_model_id": "candidate_model:home_price_GR1:search_smoke_...:cm1"
}
```

Field meanings:

- `summary_type`: Discriminator for Studio and agents. Must be
  `search_summary`.
- `target`: Modeled target variable.
- `segment_id`: Adapter segment identifier. This is a stable protocol field for
  the current demo slice, not a license for Studio to inspect `Technic Segment`
  objects.
- `search_id`: Stable search execution identifier used to derive
  `technic://` artifact refs.
- `selected_count`: Number of selected candidate models emitted by the search.
- `zero_selected_is_valid`: Whether zero selected models represents a valid
  modeling outcome rather than workflow failure.
- `pilot_smoke`: Whether the run used the relaxed smoke-test path.
- `candidate_count`: Number of candidate model payloads available in
  `selected_models`; for this slice it should match `selected_count`.
- `best_model_id`: Adapter model id for the first or best selected model, when
  one exists.
- `best_candidate_model_id`: Durable asset id for the best selected candidate,
  when one exists.

Optional stable fields for this slice:

- `no_candidate_reason`: Required only when `selected_count` is zero and the
  adapter can identify a reason without parsing diagnostics. Initial allowed
  value: `no_models_passed_filters`.
- `active_filter_count`: Number of enabled model-test filters, when available
  as structured data.
- `built_spec_count`: Number of specs attempted, when available as structured
  data.
- `passed_spec_count`: Number of specs passing filters, when available as
  structured data.
- `failed_spec_count`: Number of specs failing filters, when available as
  structured data.
- `error_spec_count`: Number of specs that errored during evaluation, when
  available as structured data.
- `target_pretest_passed`: Boolean pretest outcome, when available as
  structured data.
- `feature_pretest_exclusion_count`: Number of features excluded by pretest,
  when available as structured data.

Not in `outputs.summary`:

- Full `search_config`. It belongs in `inputs.search_config` because it records
  how the run was requested, not what it produced.
- Full selected model payloads. These remain transitional in
  `outputs.selected_models` and should be persisted as durable
  `candidate_model` assets.
- Raw stdout, stderr, stack traces, or backend dumps.

## FitSummary

`fit-single` must expose a stable summary under `outputs.summary`.

Applies to:

- `workflow_id = demo_housing_fit_single`

Required stable fields:

```json
{
  "summary_type": "fit_summary",
  "target": "home_price_GR1",
  "segment_id": "home_price_GR1",
  "selected_count": 1,
  "model_count": 1,
  "best_model_id": "cm1",
  "best_candidate_model_id": "candidate_model:home_price_GR1:fit_...:cm1",
  "best_formula": "home_price_GR1 ~ USMORT30Y",
  "sample": "in",
  "specs": ["USMORT30Y"],
  "metric_highlights": {
    "rsquared": 0.82
  }
}
```

Field meanings:

- `summary_type`: Discriminator for Studio and agents. Must be `fit_summary`.
- `target`: Modeled target variable.
- `segment_id`: Adapter segment identifier for the current demo slice.
- `selected_count`: Number of selected candidate models from the fit. For
  `fit-single`, this should normally be `1` on success.
- `model_count`: Number of model payloads in the fit output.
- `best_model_id`: Adapter model id for the fitted model.
- `best_candidate_model_id`: Durable asset id for the fitted model, when asset
  writing succeeds.
- `best_formula`: Human-readable model formula suitable for Studio tables and
  asset cards.
- `sample`: Fit sample requested by the user.
- `specs`: Requested model specs after CLI parsing.
- `metric_highlights`: Small map of headline metrics for timeline and cards.
  It should not try to preserve the full backend result.

Optional stable fields for this slice:

- `warning_count`: Number of structured warnings attached to the run.
- `metrics_available`: Names of metrics present on the selected model.

## Durable Asset Invariant

For this slice, the protocol invariant is:

> If a successful fit or search workflow exposes selected candidate models, each
> selected model must have a durable `candidate_model` asset, and the run
> manifest must reference those assets through `outputs.assets`.

Additional rules:

- `fit-single` should always write one `candidate_model` asset on successful
  fit.
- `search` and `search-smoke` should write one `candidate_model` asset for each
  selected candidate.
- `search` and `search-smoke` should always write one `evaluation_result`
  asset on success, even when `selected_count` is zero.
- `fit-single` does not need an `evaluation_result` asset in this slice unless
  a future reviewer decides that on-demand fits need evaluation semantics.
- `.lego/assets/index.json` should exist after any successful run that writes
  assets.
- `outputs.assets` is the stable run-to-asset connection. It contains AssetRefs,
  not full asset payloads.
- Durable asset JSON files are the source of truth for reusable modeling state.
  `.lego/assets/index.json` is a lookup index, not the only source of truth.

For failed runs:

- The run manifest should contain structured `errors`.
- Asset writing is not required.
- Captured diagnostics may help debugging but must not be required for normal
  Studio display.

For successful zero-selected searches:

- No `candidate_model` asset is required.
- One `evaluation_result` asset is required.
- `outputs.summary.selected_count` must be `0`.
- `outputs.summary.zero_selected_is_valid` must be `true`.
- `outputs.summary.no_candidate_reason` should be present when a structured
  reason is available.

## CandidateModel Required Fields

For this slice, a durable `candidate_model` asset must include:

```json
{
  "protocol_version": "0.1",
  "asset_id": "candidate_model:home_price_GR1:fit_...:cm1",
  "type": "candidate_model",
  "created_at": "2026-07-01T14:23:00Z",
  "created_by_run_id": "fit_...",
  "source_asset_ids": [],
  "artifact_refs": [],
  "source_run_id": "fit_...",
  "target": "home_price_GR1",
  "segment_id": "home_price_GR1",
  "model_id": "cm1",
  "formula": "home_price_GR1 ~ USMORT30Y",
  "specs": ["USMORT30Y"],
  "metrics": {
    "rsquared": 0.82
  }
}
```

Required fields:

- Base envelope: `protocol_version`, `asset_id`, `type`, `created_at`,
  `created_by_run_id`, `source_asset_ids`, `artifact_refs`.
- Lineage aliases used by current code and tests: `source_run_id`.
- Model identity: `target`, `segment_id`, `model_id`.
- Model description: `formula`, `specs`.
- Model quality: `metrics`.

CandidateModel asset ids should be scoped by source run for current demo
workflows, for example `candidate_model:<target>:<run_id>:<model_id>`. The
legacy adapter can reuse model ids such as `cm1` across many fits and searches;
without the run id, later runs overwrite earlier durable assets and corrupt
lineage.

Optional fields for this slice:

- `model_family`, defaulting to `ols` when known.
- `sample`, copied from `fit-single` when known.
- `search_id`, copied from search runs when known.
- `metric_highlights`, if the asset writer wants to preserve the same reduced
  map used in `FitSummary`.

Artifact refs:

- Search-origin candidates should include stable `technic://` refs when
  `segment_id`, `search_id`, and `model_id` are available.
- Machine-local absolute paths must not be copied into stable artifact URIs.
- Fit-origin candidates may have an empty `artifact_refs` list until there is a
  stable fit artifact location.

## EvaluationResult Required Fields

For this slice, a durable `evaluation_result` asset must include:

```json
{
  "protocol_version": "0.1",
  "asset_id": "evaluation_result:home_price_GR1:search_...",
  "type": "evaluation_result",
  "created_at": "2026-07-01T14:23:00Z",
  "created_by_run_id": "search_...",
  "source_asset_ids": ["candidate_model:home_price_GR1:search_smoke_...:cm1"],
  "artifact_refs": [],
  "source_run_id": "search_...",
  "target": "home_price_GR1",
  "segment_id": "home_price_GR1",
  "candidate_count": 1,
  "selected_count": 1,
  "candidate_model_ids": ["candidate_model:home_price_GR1:search_smoke_...:cm1"],
  "best_candidate_model_id": "candidate_model:home_price_GR1:search_smoke_...:cm1",
  "summary": {
    "status": "needs_review",
    "selected_count": 1,
    "zero_selected_is_valid": true,
    "warning_count": 0
  },
  "warnings": [],
  "diagnostics": {}
}
```

Required fields:

- Base envelope: `protocol_version`, `asset_id`, `type`, `created_at`,
  `created_by_run_id`, `source_asset_ids`, `artifact_refs`.
- Lineage aliases used by current code and tests: `source_run_id`.
- Evaluation identity: `target`, `segment_id`.
- Candidate references: `candidate_count`, `selected_count`,
  `candidate_model_ids`.
- Summary: `summary.status`, `summary.selected_count`,
  `summary.zero_selected_is_valid`, `summary.warning_count`.

Required when available:

- `best_candidate_model_id`, when at least one candidate model exists.

Optional for this slice:

- `search_summary`, as a copy of the stable run `outputs.summary` if consumers
  need evaluation assets to stand alone.
- `warnings`, copied from the structured run warnings.
- `diagnostics`, limited to small structured diagnostic facts. Do not copy raw
  captured stdout or stderr.
- `weaknesses` and `recommended_next_actions`, currently empty placeholders.

Status values for this slice:

- `needs_review`: At least one candidate was selected.
- `no_candidates_selected`: The search succeeded, selected zero candidates, and
  `zero_selected_is_valid` is true.
- `incomplete`: Reserved for future partial-result workflows.

## Studio Zero Expectations

After this slice, Studio Zero should be able to show useful fit/search state
without opening raw run details.

Expected snapshot behavior:

- `health.asset_count` is greater than zero after a successful `fit-single` or
  selected-candidate search.
- `health.asset_counts_by_type.candidate_model` increments after successful
  selected-candidate fit/search runs.
- `health.asset_counts_by_type.evaluation_result` increments after successful
  search/search-smoke runs, including zero-selected searches.
- `runs_timeline[]` includes `target`, `segment_id`, `selected_count`,
  `zero_selected_is_valid`, `output_asset_count`, and summary-derived headline
  values.
- `asset_inventory[]` resolves indexed `candidate_model` and
  `evaluation_result` entries.
- `lineage[]` connects run output AssetRefs to indexed asset files.
- `health.findings[]` warns when a successful fit/search run has missing
  expected assets.
- `diagnostics[]` can still report large captured diagnostics, but normal
  timeline and inventory display should not depend on them.

HTML expectations:

- The current HTML can remain minimal.
- It should be able to render asset counts and run summary values from the
  snapshot.
- Rich candidate cards or evaluation detail panels can wait until protocol
  fields are reliable.

## Raw Diagnostics Policy

Raw captured output is diagnostic-only.

Rules:

- `captured_stdout` and `captured_stderr` may be stored under
  `outputs.diagnostics`.
- They are not stable protocol fields.
- Studio may flag heavy diagnostics as a health signal.
- Studio must not parse raw diagnostics to derive selected counts, formulas,
  metrics, search ids, candidate ids, warnings, or asset references.
- Any modeling fact needed for normal display should graduate to
  `outputs.summary`, structured `warnings`/`errors`, or a durable asset.

## Implementation Slices

### Slice 1: Summary Tightening

Goal:

Ensure fit/search workflows emit the required summary fields.

Likely files:

- `Mindstorms/demo_housing.py`
- `Mindstorms/runs.py`
- `Mindstorms/cli.py`
- `tests/test_mindstorms_runs.py`
- `tests/test_mindstorms_cli.py`
- `tests/test_mindstorms_studio.py`

Expected work:

- Add `summary_type` to normalized fit/search summaries.
- Add `model_count`, `best_model_id`, `best_formula`, `sample`, `specs`, and
  `metric_highlights` for `fit-single`.
- Add `candidate_count`, `best_model_id`, `best_candidate_model_id`, and
  optional `no_candidate_reason` for search summaries.
- Keep `inputs.search_config` as the stable search configuration location.
- Preserve legacy top-level output fields during transition.

Validation:

```bash
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego run inspect latest --json
lego studio snapshot --json
```

Acceptance checks:

- `fit-single` summary is useful without opening `selected_models`.
- `search-smoke` summary is useful without opening diagnostics.
- Existing legacy manifest normalization remains idempotent.
- Studio timeline reads summary values from `outputs.summary`.

### Slice 2: Asset Contract Tightening

Goal:

Ensure durable assets carry the minimal required fields and Studio health can
identify missing expected assets.

Likely files:

- `Mindstorms/runs.py`
- `Mindstorms/assets.py`
- `Mindstorms/studio.py`
- `tests/test_mindstorms_runs.py`
- `tests/test_mindstorms_cli.py`
- `tests/test_mindstorms_studio.py`

Expected work:

- Add `segment_id` to `candidate_model` assets.
- Add `segment_id`, `candidate_count`, `selected_count`, and structured
  warning summary to `evaluation_result` assets.
- Add `best_candidate_model_id` to run summaries after assets are written.
- Ensure successful zero-selected search runs always write an
  `evaluation_result` asset.
- Add Studio health findings for successful fit/search runs that lack expected
  assets.
- Keep `.lego/assets/index.json` creation tied to asset-writing workflows.

Validation:

```bash
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego assets list --json
lego asset inspect <candidate_model_asset_id> --json
lego studio snapshot --json
```

Acceptance checks:

- `assets list` shows `candidate_model` after fit/search with selected models.
- `assets list` shows `evaluation_result` after search/search-smoke.
- `asset inspect` exposes formula, specs, metrics, selected count, and lineage.
- Studio health finds broken asset refs or missing required assets.

## Open Questions

1. Should `fit-single` write an `evaluation_result` asset later, or is a
   `candidate_model` asset enough for on-demand fits?
2. Should `metric_highlights` be a separate stable reduced map, or should Studio
   read directly from `CandidateModel.metrics` for this slice?
3. Should `no_candidate_reason` have a small enum immediately, or start as a
   best-effort string with tests only for presence in known zero-selected
   cases?
4. Should `SearchSummary` be copied into `EvaluationResult.search_summary`, or
   is the run manifest the only stable home for that summary in v0.1?
5. Should the current transitional `outputs.selected_models` field stay visible
   indefinitely, or be hidden once Studio and agents rely on durable assets?
