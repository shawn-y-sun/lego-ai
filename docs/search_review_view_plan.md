# Search Review View Plan

Status: planning draft

## Purpose

Design the smallest useful read-only Studio view for the modeler workflow step:

```text
run search -> review search results -> identify selected/best model
```

The current Studio Detail prototype is useful as a protocol/debug explorer, but
human review showed that it does not yet read as a workflow surface for a
modeler. This slice should make the selected model and search outcome obvious
before exposing protocol internals.

## Non-Goals

- Do not build an interactive dashboard or `lego studio serve`.
- Do not add React, Vue, Svelte, or a frontend framework.
- Do not run searches, fits, approvals, or edits from Studio.
- Do not introduce champion/approval workflow semantics.
- Do not operate notebook workflows for agent runs.
- Do not add `ModelingFrame`, `SearchPool`, or `ModelingIteration`.
- Do not refactor `Technic`.
- Do not migrate old `.lego` artifacts or add a database.

## Human Feedback Summary

The first Studio Detail page made protocol structures visible, but the modeler
could not quickly answer which workflow step they were seeing or which model was
selected. The most important feedback:

- `Run Timeline` is too prominent for search review and should move lower.
- `EvaluationResult` is an unclear primary UI label.
- The selected/best model needs a dedicated, obvious area.
- `CandidateModel` is a protocol term; the main UI should use modeler language.
- `Protocol Health` and raw asset cards are useful diagnostics, not the story.
- The page should clearly serve workflow steps 5 and 6: review search results
  and identify the selected/best model.

## Workflow Step Definition

The view represents the state after a search or fit run has produced reviewable
outputs. It should answer:

- What search/fit run am I reviewing?
- What target and segment does it apply to?
- Which model was selected or considered best?
- What formula, drivers/specs, and metrics explain that model?
- How many model options were considered, passed, failed, or selected?
- Are there warnings or diagnostics that affect trust in the result?
- Where can I inspect raw protocol state when the workflow view is insufficient?

## View Information Architecture

Recommended first HTML order:

```text
[Search Review Header]
View: Search Review
Target, Segment, Source Run, Status, Generated Time
Selected Models, Candidate Models, Warnings

[Selected Model]
Formula
Drivers / Specs
R2, Adj R2, AIC, BIC
Source run and asset id

[Model Options]
Compact table of candidate/model options for the reviewed run

[Search Summary]
Candidate count, selected count, model count
Built/passed/failed/error counts when available
Zero-selected validity and no-candidate reason when applicable

[Diagnostics]
Collapsed warnings, system checks, raw JSON, protocol object names

[Run History]
Secondary timeline table for nearby/latest runs
```

The first viewport should make the page identity and selected model clear. Run
history and raw assets should remain reachable but should not lead the page.

## Human-Facing Naming Decisions

Use these labels in the primary UI:

| Protocol/Internal Term | Primary UI Label | Notes |
| --- | --- | --- |
| `CandidateModel` | Model Option | Use `Selected Model` when it is the chosen/best option. |
| `EvaluationResult` | Search Results | Use `Search Run Summary` for count/status panels. |
| `Protocol Health` | Diagnostics | Include system checks under this heading. |
| `Asset Details` | Raw Details | Collapsed or secondary. |
| `Run Timeline` | Run History | Lower-priority section near the bottom. |

Protocol names may still appear in raw JSON and developer-oriented details.

## Data Sources And Protocol Fields

Keep `build_studio_snapshot()` as the durable interface for reading local
protocol state. Add a derived view model instead of making HTML determine the
workflow logic.

Proposed module shape:

```text
build_studio_snapshot() -> StudioSnapshot
build_search_review_view(snapshot) -> SearchReviewViewModel
export_studio_html(snapshot) -> static HTML
```

This keeps discovery, manifest normalization, asset resolution, lineage, and
health checks behind the existing snapshot interface, while letting the workflow
view choose a small, stable rendering shape.

Initial fields for `SearchReviewViewModel`:

- `review_run_id`
- `workflow_id`
- `status`
- `target`
- `segment_id`
- `generated_at`
- `selected_model`
- `model_options`
- `search_summary`
- `diagnostics`
- `run_history`
- `raw_detail_refs`

Source fields already available in the current Studio snapshot include:

- `runs_timeline[]`
- `asset_details[]`
- `health.findings[]`
- `warnings_summary[]`
- `errors_summary[]`
- `raw_runs[]`

Search review should prefer the latest reviewable search run with a
`search_summary`. If none exists, it may fall back to the latest fit summary with
a selected model. The empty state should say that no reviewable search results
were found.

## Selected Model Panel Design

The selected model panel is the primary object on the page.

Required fields:

- label: `Selected Model`
- model id or asset id suffix
- formula
- drivers/specs
- key metrics: `rsquared`, `rsquared_adj`, `aic`, `bic`
- source run id
- target and segment
- asset id in small secondary text

If no model is selected and zero selected is valid, show a clear selected-model
empty state:

```text
No model selected
This search completed with zero selected models, and zero-selected is valid.
Reason: <no_candidate_reason when available>
```

If no model is selected and zero selected is not known to be valid, diagnostics
should include a warning-level note.

## Model Options And Search Summary Design

First slice should show selected model plus a compact model options table for the
reviewed run. Do not show all historical `candidate_model` assets in the primary
workflow view.

Model options table columns:

- Rank or selected marker when available
- Model id
- Formula
- Drivers/spec count or short driver list
- R2 / Adj R2 / AIC / BIC
- Asset id

Search summary should show count/status facts separately from the model table:

- `candidate_count`
- `model_count`
- `selected_count`
- built/passed/failed/error counts when available
- `zero_selected_is_valid`
- `no_candidate_reason`
- `pilot_smoke`

Missing fields should be displayed as `not reported`, not inferred from thin air.

## Diagnostics And Raw Detail Policy

Diagnostics should be visible but secondary.

Default collapsed sections:

- warnings affecting the reviewed run
- health/system checks
- raw Search Results asset JSON
- raw Selected Model asset JSON
- raw run manifest
- generic asset inventory

Rules:

- Do not show captured stdout/stderr in the normal workflow path.
- Show diagnostic keys and sizes when structured diagnostics are present.
- Keep full protocol names inside diagnostics/raw details.
- Keep existing raw JSON fallback so the static export remains useful during
  protocol evolution.

## Relationship To StudioSnapshot

`StudioSnapshot` remains the stable local protocol interface. The Search Review
view should be a derived workflow model, not a replacement for the protocol
snapshot.

This gives a clean seam:

- tests can assert search-review behavior through one view-model function;
- HTML rendering can stay simple and dependency-light;
- future Studio views can share the snapshot without copying protocol discovery
  logic;
- the current protocol/debug explorer can remain available as a fallback.

## First Implementation Slice Handoff

Topic:

```text
Search Review View Implementation
```

Objective:

Add a read-only Search Review layout to the static Studio export that prioritizes
the selected model and search outcome over protocol internals.

Recommended implementation order:

1. Add tests for a small `build_search_review_view(snapshot)` helper in
   `Mindstorms/studio.py`.
2. Derive the reviewed run from latest `runs_timeline[]` item with
   `summary_type == "search_summary"`.
3. Resolve selected model from `best_candidate_model_id`, then from
   candidate/model details linked to the reviewed run.
4. Build `model_options` only from assets linked to the reviewed run.
5. Add `search_summary` and `diagnostics` sections to the view model.
6. Update `_html_document()` to render `Search Review` first.
7. Move existing `Runs Timeline`, `Protocol Health`, `Asset Inventory`, and raw
   details into lower or collapsed diagnostic sections.
8. Keep existing asset detail renderers as raw/detail fallback, but remove
   protocol object names from primary headings.

Likely files:

- `Mindstorms/studio.py`
- `tests/test_mindstorms_studio.py`
- `docs/search_review_view_plan.md` only for minor status notes

Avoid:

- `Technic`
- notebook files
- broad CLI changes
- new frontend dependencies

## Acceptance Criteria

Automated:

- `build_search_review_view(snapshot)` selects the latest reviewable search run.
- The view model exposes target, segment, source run, status, selected count,
  candidate count, and selected model.
- Selected model includes formula, specs/drivers, source run, asset id, and
  metric highlights.
- Model options are limited to the reviewed run.
- Zero-selected valid search produces a clear no-selected-model state.
- HTML export contains `Search Review`, `Selected Model`, `Model Options`,
  `Search Summary`, `Diagnostics`, and `Run History`.
- Primary HTML headings do not use `CandidateModel`, `EvaluationResult`,
  `Protocol Health`, or `Asset Details`.
- Raw JSON remains available in collapsed detail sections.
- Existing Studio snapshot tests continue to pass.

Manual:

```bash
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego studio export --html .lego/studio/index.html
```

Human review should be able to say:

- I know this page is for search/model review.
- I can immediately see the selected/best model.
- I can see formula, drivers/specs, and key metrics without opening raw JSON.
- I understand the search outcome and candidate/selected counts.
- Diagnostics exist but do not dominate the page.
- Run History is secondary, not the first thing.

## Open Questions

1. Should Studio keep a separate protocol explorer export mode, or should raw
   details remain enough for now?
2. Should the reviewed run always be the latest search run, or should the CLI
   later accept `--run-id` for export focus?
3. Should "best" and "selected" remain synonyms in the UI for now, or should a
   later workflow distinguish ranked best from human-selected?
4. Should model metrics be formatted with fixed precision in Studio, or shown as
   raw reported values until metric conventions settle?
5. Should a future slice add anchors from Run History rows to the selected/raw
   details for that run?
