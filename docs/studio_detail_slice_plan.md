# Studio Detail Slice Plan

Status: planning draft

## Purpose

This plan defines the next narrow Studio Zero slice after Search/Fit Visibility:
make durable `candidate_model` and `evaluation_result` assets visually useful in
the static Studio HTML export.

The slice should close the loop between the tightened protocol payload and
human review:

```text
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego studio snapshot --json
lego studio export --html .lego/studio/index.html
```

After opening the HTML, a reviewer should be able to answer whether the selected
model, formula, metrics, evaluation outcome, lineage, warnings, and health
findings are understandable without reading raw JSON or captured stdout.

## Non-Goals

- Do not build an interactive dashboard or `lego studio serve`.
- Do not introduce React, Vue, Svelte, or a browser app framework.
- Do not run modeling workflows from Studio.
- Do not add asset editing, approval, or human sign-off workflows.
- Do not operate the notebook workflow for agent runs.
- Do not add `ModelingFrame`, `SearchPool`, or `ModelingIteration` in this
  slice.
- Do not refactor `Technic`.
- Do not make raw stdout or stderr part of the normal Studio display path.
- Do not add a database or migrate legacy `.lego` run artifacts.

## Human Feedback Questions

The slice is successful if the HTML gives enough visual feedback to answer:

- Which model was selected?
- Which run produced the model?
- What target, segment, formula, specs, and metrics describe it?
- How many candidates were evaluated and selected?
- Was zero-selected search a valid outcome, when applicable?
- Are warnings and protocol health findings useful, or too noisy?
- Is raw JSON still reachable when a custom renderer is missing?

## Data Sources And Protocol Fields

Studio Zero should keep `build_studio_snapshot()` as the durable interface. The
HTML export should render from the snapshot, not read `.lego` files directly.
This keeps the module deep: file discovery, manifest normalization, asset index
resolution, lineage, diagnostics, and health policy stay behind one snapshot
interface.

Existing snapshot sources:

- `.lego/runs/<run_id>/manifest.json`
- `.lego/assets/index.json`
- Durable asset JSON files resolved through `asset://...` URIs

Stable run fields to use:

- `run_id`
- `workflow_id`
- `status`
- `created_at`
- `completed_at`
- `target`
- `segment_id`
- `warnings`
- `errors`
- `outputs.summary`
- `outputs.assets`

Stable asset fields to use:

- Base envelope: `asset_id`, `type`, `created_at`, `created_by_run_id`,
  `source_asset_ids`, `artifact_refs`
- Common lineage alias: `source_run_id`
- `CandidateModel`: `target`, `segment_id`, `model_id`, `formula`, `specs`,
  `metrics`
- `EvaluationResult`: `target`, `segment_id`, `candidate_count`,
  `selected_count`, `candidate_model_ids`, `best_candidate_model_id`,
  `summary`, `warnings`, `diagnostics`

## CandidateModel Detail Design

Add a snapshot-level `asset_details` list for resolved custom-rendered assets.
Each detail item should include:

```json
{
  "asset_id": "candidate_model:home_price_GR1:fit_...:cm1",
  "type": "candidate_model",
  "render_kind": "candidate_model_card",
  "source_run_id": "fit_...",
  "workflow_id": "demo_housing_fit_single",
  "segment_id": "home_price_GR1",
  "target": "home_price_GR1",
  "model_id": "cm1",
  "formula": "home_price_GR1 ~ USMORT30Y",
  "specs": ["USMORT30Y"],
  "metric_highlights": {
    "rsquared": 0.82,
    "rsquared_adj": 0.81,
    "aic": 123.4,
    "bic": 130.2
  },
  "artifact_refs": [],
  "raw_available": true
}
```

Minimum HTML card:

- Title: model id or asset id suffix.
- Lineage row: source run id, workflow id, target, segment id.
- Formula block.
- Specs as compact chips or a short comma-separated list.
- Metric highlights table with `rsquared`, `rsquared_adj`, `aic`, and `bic`
  when present.
- Artifact refs count and URI list only when non-empty.
- Collapsed raw JSON fallback.

First-version scope:

- Render all resolved `candidate_model` assets from the asset index.
- Sort newest first by `created_at`, then `asset_id`.
- Do not try to infer "approved" or "best overall" across runs.
- Emphasize selected or best only when the source run summary points to
  `best_candidate_model_id`.

## EvaluationResult Detail Design

Use the same `asset_details` list with `render_kind =
evaluation_result_card`.

Each detail item should include:

```json
{
  "asset_id": "evaluation_result:home_price_GR1:search_...",
  "type": "evaluation_result",
  "render_kind": "evaluation_result_card",
  "source_run_id": "search_...",
  "workflow_id": "demo_housing_search_smoke",
  "segment_id": "home_price_GR1",
  "target": "home_price_GR1",
  "candidate_count": 1,
  "selected_count": 1,
  "zero_selected_is_valid": true,
  "status": "needs_review",
  "best_candidate_model_id": "candidate_model:home_price_GR1:search_...:cm1",
  "candidate_model_ids": ["candidate_model:home_price_GR1:search_...:cm1"],
  "no_candidate_reason": null,
  "warning_count": 0,
  "warnings": [],
  "diagnostics_summary": [],
  "raw_available": true
}
```

Minimum HTML card:

- Title: evaluation asset id suffix.
- Outcome row: status, selected count, candidate count, zero-selected validity.
- Lineage row: source run id, workflow id, target, segment id.
- Best candidate id when present.
- Candidate model id list, compact and copyable as text.
- Warnings summary with code, severity, count/message when present.
- Diagnostics summary with keys and sizes only; no raw captured output.
- Collapsed raw JSON fallback.

Grouping decision:

- Place EvaluationResult cards in the same "Asset Details" section as
  CandidateModel cards.
- Within each card, show source run linkage.
- Do not nest EvaluationResult under timeline rows yet. Static HTML should stay
  simple and scannable for the first feedback pass.

## Run Timeline Enrichment

The timeline should remain a fast scan of executions, not a full asset detail
view.

Extend each `runs_timeline[]` item with summary-derived fields:

- `summary_type`
- `candidate_count`
- `model_count`
- `best_model_id`
- `best_candidate_model_id`
- `best_formula`
- `metric_highlights`
- `pilot_smoke`
- `no_candidate_reason`

HTML timeline display should show:

- Existing run, workflow, status, created, target, selected, warnings, assets.
- For `fit_summary`: best formula plus one headline metric if available.
- For `search_summary`: selected count over candidate count, pilot-smoke flag,
  and zero-selected validity/no-candidate reason when applicable.

Keep detailed formula/specs/metrics in asset cards. The timeline should answer
"what happened?" while detail cards answer "what was produced?".

## Health Findings Display Policy

Health findings should remain visible, but not dominate the model story.

HTML policy:

- Show a compact Protocol Health section near the top with total finding count
  and counts by severity.
- Render finding rows grouped by severity and code.
- Keep full finding messages visible in the table.
- Do not hide legacy-run findings by default in this slice, because they reveal
  real protocol gaps in old local artifacts.
- Keep the Asset Details section before or near the health details when assets
  exist, so a reviewer sees the model/evaluation story before the warning wall.

Snapshot policy:

- Keep `health.findings[]` unchanged as the stable raw list.
- Optionally add `health.finding_counts_by_severity` and
  `health.finding_counts_by_code` for HTML rendering.
- Do not downgrade expected-asset findings just to reduce visual noise.

## Raw JSON Fallback Policy

Raw JSON should remain available, but collapsed by default.

Rules:

- Custom-rendered assets include a collapsed `<details>` block containing their
  raw asset JSON.
- Assets without a custom renderer appear in a generic Raw Asset Details list,
  also collapsed.
- Existing Run Detail raw manifests remain collapsed and limited to the newest
  few runs unless a later slice adds filtering.
- Captured stdout/stderr stay diagnostic-only. Studio may show key names and
  sizes, not full captured text in the normal page.

## Implementation Slice Handoff

Topic:

```text
Studio Detail Slice Implementation
```

Objective:

Add read-only CandidateModel and EvaluationResult detail cards to Studio Zero
HTML through the `StudioSnapshot` interface.

Recommended implementation order:

1. Add tests for `asset_details` built from resolved `candidate_model` and
   `evaluation_result` asset files.
2. Add small internal helpers in `Mindstorms/studio.py` to read resolved asset
   payloads from `asset_inventory` entries.
3. Add `asset_details` to `build_studio_snapshot()`.
4. Enrich `_run_timeline_item()` from `outputs.summary`.
5. Add HTML renderers for CandidateModel cards, EvaluationResult cards, grouped
   health counts, and collapsed raw JSON.
6. Keep raw JSON fallback for unknown asset types.
7. Verify with unit tests and the demo/export path.

Likely files:

- `Mindstorms/studio.py`
- `tests/test_mindstorms_studio.py`
- possibly `docs/studio_detail_slice_plan.md` if implementation notes need a
  small update

Avoid:

- `Technic`
- notebook files
- broad CLI changes
- new frontend framework dependencies

Suggested validation:

```bash
pytest tests/test_mindstorms_studio.py
pytest
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego studio snapshot --json
lego studio export --html .lego/studio/index.html
```

## Acceptance Criteria

Automated:

- Studio snapshot includes `asset_details` for resolved `candidate_model` and
  `evaluation_result` assets.
- CandidateModel detail exposes source run id, workflow id when resolvable,
  target, segment id, model id, formula, specs, metric highlights, and raw
  fallback availability.
- EvaluationResult detail exposes source run id, workflow id when resolvable,
  target, segment id, selected count, candidate count, zero-selected validity,
  candidate model ids, warning summary, diagnostics summary, and raw fallback
  availability.
- Run timeline includes summary-derived fit/search headline fields.
- HTML export contains CandidateModel and EvaluationResult detail sections when
  those assets exist.
- Raw JSON is collapsed by default.
- Existing empty-state and health-finding tests continue to pass.

Human review:

- I can see the selected model and formula.
- I can see model metrics without opening raw JSON.
- I can see EvaluationResult selected/candidate counts.
- I can trace model and evaluation assets back to source runs.
- I can see warnings and health findings, but they do not bury the asset story.
- I can still open raw JSON when the custom view is insufficient.

## Open Questions

1. Should a future slice add timeline-to-detail anchors so a run row links to
   produced asset cards?
2. Should Studio eventually hide legacy-run findings behind a filter, or keep
   all protocol findings visible until a migration story exists?
3. Should `metric_highlights` be computed by Studio from full asset metrics, or
   should asset writers persist the same reduced metric map used by run
   summaries?
4. Should `EvaluationResult` copy the full `search_summary`, or should Studio
   continue resolving run summary by `source_run_id`?
5. How many raw run manifests should the static HTML show by default once local
   `.lego/runs` grows large?
