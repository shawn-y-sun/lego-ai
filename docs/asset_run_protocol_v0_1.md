# LEGO AI Asset/Run Protocol v0.1 Design Baseline

Status: draft living design

This document captures the current design baseline for an AI-native
Asset/Run Protocol for LEGO AI. It is intended to be updated as new design
concepts emerge.

## Purpose

The Asset/Run Protocol defines a stable, inspectable state surface for LEGO AI
modeling work. It should support agents, command-line workflows, future Studio
views, model documentation, and project memory without depending on the current
internal shape of the `Technic` package.

The core design goal is:

> Make modeling state explicit, structured, traceable, and reusable before
> making agents more autonomous.

`Technic` can remain a reusable modeling engine adapter, especially for data
handling, feature construction, model search, fit, evaluation, and reporting.
The protocol should not inherit `Technic`'s object model as its public
interface.

## Non-Goals

- Do not design a database for v0.1.
- Do not require replacing existing `Technic` persistence.
- Do not require every workflow to be implemented immediately.
- Do not force all projects into one sample window, frequency, or scenario
  policy.
- Do not make raw stdout, backend dumps, or notebook state part of the stable
  contract.
- Do not make model search the first-class root of the system; it is one stage
  in a broader modeling workflow.

## AI-Native Design Principles

1. Workflows produce assets.
2. Runs record executions of workflows.
3. Assets form a lineage graph.
4. Artifacts are file or directory references behind assets.
5. Run manifests contain asset references; durable assets must be persisted as
   standalone asset JSON files.
6. Modeling is iterative, not linear.
7. Human and agent judgment should be explicit, especially feature design,
   search-pool curation, model diagnosis, and approval.
8. Every `ModelingFrame` must be self-contained. Project-level context can
   suggest defaults, but the frame must declare its effective assumptions.
9. Stable fields are safe for agents and Studio to rely on. Diagnostic fields
   are not.
10. Roadmap slices should stay vertical: each slice should connect a small
    protocol concept through CLI output, run manifests, persisted assets when
    needed, and tests so the project can iterate quickly from real feedback.

## Vocabulary

### Workflow

A workflow is an agent-callable capability or recipe. It describes what the
system can do, what inputs it expects, and what assets or summaries it can
produce.

Examples:

- `define_project_context`
- `register_dataset`
- `profile_dataset`
- `build_features`
- `define_modeling_frame`
- `curate_search_pool`
- `prepare_search_config`
- `search_candidate_models`
- `evaluate_candidates`
- `diagnose_model_gaps`
- `approve_candidate_model`
- `publish_model_package`
- `fit_candidate_model` as an on-demand workflow

### Run

A run is one execution record of a workflow. It answers: what happened, when,
with what inputs, with what status, and what assets/artifacts were produced.

A run is not a full modeling project and not necessarily a full modeling
iteration.

### Asset

An asset is a durable semantic output that later workflows, agents, Studio, or
reports can refer to. Assets should have stable IDs, types, source lineage, and
optional artifact references.

### AssetRef

An asset reference is a small pointer from a run manifest or another object to a
durable Asset. `outputs.assets` should contain AssetRefs, not full Asset
payloads. The referenced Asset must be persisted as standalone JSON at a stable
protocol URI.

Preferred URI-like example:

- `asset://candidate_model/home_price_GR1/cm17.json`

### ArtifactRef

An artifact reference points to concrete files, directories, reports, plots, or
backend outputs. Artifact paths should not require absolute machine-specific
paths as the stable contract.

Preferred URI-like examples:

- `repo://Demo Data/housing_market.csv`
- `run://manifest.json`
- `technic://Segment/home_price_GR1/cms/search_001`

### ProjectContext

ProjectContext groups a modeling project and holds project-level defaults,
governance preferences, scenario sets, project memory, and lists of modeling
frames.

ProjectContext does not force all frames to use the same sample windows,
frequency, or scenario policy.

### ModelingFrame

ModelingFrame defines the effective modeling problem for one target or segment:
target, frequency, sample windows, scenario policy, source datasets, feature
universe, and other assumptions required for model development.

ModelingFrame is the source of truth for effective assumptions.

### ModelingIteration

ModelingIteration captures one improvement cycle for a ModelingFrame. It groups
the feature-building, search-pool curation, model search, evaluation, and
diagnosis work performed in one attempt to improve model options.

### FeatureRecipe

FeatureRecipe defines how to construct one or more features from available
data. Recipes can be global, domain-level, or project-specific.

### FeatureSet

FeatureSet is a modeling-facing group of generated features. It records names,
expressions, source columns, business meaning, and whether features are allowed
for search.

### SearchPool

SearchPool is the curated set of drivers that are allowed into a candidate
model search for a ModelingFrame or ModelingIteration. It records inclusion and
exclusion judgment.

### SearchConfig

SearchConfig records the concrete parameters used to execute one model search:
driver pool, forced-in variables, lag limits, maximum variable count, periods,
filter profile, engine options, and runtime budget.

SearchConfig answers "what did this search run do?" SearchPool answers "why
were these drivers allowed into the search?"

### CandidateModel

CandidateModel is a model option produced by model search or an on-demand fit.
It records formula/specs, target, source ModelingFrame, metrics, diagnostics,
and artifact references.

### EvaluationResult

EvaluationResult records model quality assessment, weakness diagnosis,
evidence, and recommended next actions.

### ApprovalDecision

ApprovalDecision records whether a candidate model has been accepted, rejected,
or sent back for improvement.

### ModelPackage

ModelPackage is the publication/export bundle for an approved candidate model:
documentation, charts, model outputs, model cards, and implementation artifacts.

## Workflow Map

The workflow is not a straight line. It has setup work followed by an iterative
development loop.

### Setup Phase

1. `define_project_context`
2. `register_dataset`
3. `profile_dataset`
4. `define_modeling_frame`

### Development Loop

1. `build_features`
2. `curate_search_pool`
3. `prepare_search_config`
4. `search_candidate_models`
5. `evaluate_candidates`
6. `diagnose_model_gaps`

The loop repeats until the model owner or senior reviewer approves a candidate
model.

### Exit Phase

1. `approve_candidate_model`
2. `publish_model_package`

### On-Demand Workflow

`fit_candidate_model` is useful when a user asks to fit a specific set of
variables. It is not required in the main path because `search_candidate_models`
already fits many candidate models internally.

## Core Asset Graph

```text
ProjectContext
  |
  v
DatasetSnapshot --> DerivedDatasetSnapshot --> FeatureSet
  |                                             |
  v                                             v
DataProfile ----------------------------> ModelingFrame
                                                |
                                                v
                                         ModelingIteration
                                                |
                                                v
                                           SearchPool
                                                |
                                                v
                                          SearchConfig
                                                |
                                                v
                                        CandidateModel(s)
                                                |
                                                v
                                      EvaluationResult
                                                |
                         +----------------------+----------------+
                         |                                       |
                         v                                       v
              next ModelingIteration                    ApprovalDecision
                                                                 |
                                                                 v
                                                          ModelPackage
```

## Protocol Objects

The examples below show intended object shape. v0.1 should keep these schemas
small and expandable. For readability, type-specific examples may omit common
Base Asset Envelope fields that still apply to durable Asset JSON files.

### v0.1 Object Maturity

Required in the v0.1 protocol core:

- `RunManifest`
- `Asset`
- `AssetRef`
- `ArtifactRef`
- `WarningRecord`
- `ErrorRecord`

Required for the current Mindstorms candidate-model slice:

- `CandidateModel`
- `SearchConfig` as stable search-run input; it may become a durable Asset when
  another object needs to reference it directly

Required when the corresponding lifecycle workflow is implemented:

- `ProjectContext`
- `DatasetSnapshot`
- `ModelingFrame`
- `ModelingIteration`
- `FeatureSet`
- `SearchPool`
- `EvaluationResult`
- `ApprovalDecision`

Optional in v0.1:

- `DataProfile`
- `DerivedDatasetSnapshot`
- `FeatureRecipe`
- durable `SearchConfig` asset files
- `.lego/assets/index.json`
- recipe library folders
- full `.lego/projects/<project_id>/` layout
- compatibility reader for pre-v0.1 run manifests

Future or experimental:

- `FeatureRecipeProposal`
- natural-language recipe generation lifecycle
- stable formula language beyond simple expression metadata
- separate `ScreeningResult` assets
- full `ModelPackage` schema
- Studio-facing view models
- database-backed asset registry
- delegated human/agent approval workflow

### Base Asset Envelope

Every durable Asset JSON should share a small stable envelope. Type-specific
fields can extend this envelope, but consumers should be able to read lineage,
provenance, and artifacts from these common fields.

Required stable fields:

- `protocol_version`
- `asset_id`
- `type`
- `created_at`
- `created_by_run_id`
- `source_asset_ids`
- `artifact_refs`

Recommended optional fields:

- `project_context_id`
- `modeling_frame_id`
- `modeling_iteration_id`
- `name`
- `description`
- `tags`

Example:

```json
{
  "protocol_version": "0.1",
  "asset_id": "candidate_model:home_price_GR1:cm17",
  "type": "candidate_model",
  "created_at": "2026-06-30T10:24:12Z",
  "created_by_run_id": "search_20260630_102300",
  "source_asset_ids": [
    "modeling_frame:home_price_GR1:v1",
    "search_pool:home_price_GR1:iter_003"
  ],
  "artifact_refs": [
    {
      "uri": "technic://Segment/home_price_GR1/cms/search_20260630_102300/cm17",
      "media_type": "application/vnd.lego.technic-candidate"
    }
  ]
}
```

### AssetRef Shape

AssetRefs are lightweight pointers to durable Asset JSON files. They are safe
to embed in run manifests, asset fields, summaries, or indexes.

Required stable fields:

- `asset_id`
- `type`
- `uri`

Recommended optional fields:

- `role`
- `label`

Example:

```json
{
  "asset_id": "candidate_model:home_price_GR1:cm17",
  "type": "candidate_model",
  "role": "best_candidate",
  "uri": "asset://candidate_model/home_price_GR1/cm17.json"
}
```

### Run Manifest

`Run` manifests live under `.lego/runs/<run_id>/manifest.json`.

Required stable fields:

- `protocol_version`
- `run_id`
- `workflow_id`
- `status`
- `created_at`
- `inputs`
- `outputs`
- `warnings`
- `errors`

Recommended optional fields:

- `workflow_version`
- `started_at`
- `completed_at`
- `initiator`
- `project_context_id`
- `modeling_frame_id`
- `modeling_iteration_id`

Example:

```json
{
  "protocol_version": "0.1",
  "run_id": "search_20260630_102300",
  "workflow_id": "search_candidate_models",
  "workflow_version": "0.1",
  "status": "succeeded",
  "created_at": "2026-06-30T10:23:00Z",
  "started_at": "2026-06-30T10:23:01Z",
  "completed_at": "2026-06-30T10:24:12Z",
  "initiator": {
    "type": "agent",
    "name": "codex"
  },
  "project_context_id": "project_context:housing_ppnr_2026:v1",
  "modeling_frame_id": "modeling_frame:home_price_GR1:v1",
  "modeling_iteration_id": "modeling_iteration:home_price_GR1:iter_003",
  "inputs": {
    "search_pool_id": "search_pool:home_price_GR1:iter_003"
  },
  "outputs": {
    "summary": {
      "selected_count": 5,
      "best_candidate_model_id": "candidate_model:home_price_GR1:cm17"
    },
    "assets": [
      {
        "asset_id": "candidate_model:home_price_GR1:cm17",
        "type": "candidate_model",
        "role": "best_candidate",
        "uri": "asset://candidate_model/home_price_GR1/cm17.json"
      }
    ],
    "diagnostics": {}
  },
  "warnings": [],
  "errors": [],
  "artifacts": []
}
```

Run statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

`outputs.summary` is stable when fields are documented for a workflow.
`outputs.assets` is the stable list of AssetRefs produced by the run. It is not
the storage location for full Asset payloads. `outputs.diagnostics` is not a
long-term contract.

Design rule:

> Run manifests record execution. Asset files record durable modeling state.
> ArtifactRefs point from assets or runs to concrete backend files and
> directories.

### Timestamp Policy

Protocol timestamps should be stored as UTC ISO-8601 strings with a `Z` suffix.
This keeps run manifests and asset JSON stable across agents, CI, servers, and
team members in different North American time zones.

Human-facing surfaces should convert protocol timestamps to the viewer's local
or selected project time zone. CLI, Studio, and reports may display a local
time zone label, but should not replace the stable UTC protocol value.

Example:

```json
{
  "created_at": "2026-06-30T14:23:00Z",
  "initiator": {
    "type": "agent",
    "name": "codex",
    "timezone": "America/Toronto"
  }
}
```

Possible human-facing display:

```text
2026-06-30 10:23 AM America/Toronto
```

### ProjectContext

```json
{
  "asset_id": "project_context:housing_ppnr_2026:v1",
  "type": "project_context",
  "project_id": "housing_ppnr_2026",
  "name": "Housing PPNR 2026",
  "defaults": {
    "scenario_set": "CCAR_2026",
    "scenario_names": ["Base", "Adv", "Sev"],
    "validation_policy": {
      "prefer_oos_metrics": true,
      "prefer_scenario_outputs": true
    }
  },
  "modeling_frame_groups": [
    {
      "name": "monthly_growth_targets",
      "modeling_frame_ids": [
        "modeling_frame:home_price_GR1:v1"
      ]
    },
    {
      "name": "quarterly_level_targets",
      "modeling_frame_ids": [
        "modeling_frame:mortgage_originations_Q:v1"
      ]
    }
  ]
}
```

Design rule:

> ProjectContext may suggest defaults. ModelingFrame must declare resolved
> effective assumptions.

### DatasetSnapshot

```json
{
  "asset_id": "dataset_snapshot:internal:housing_market:20260630",
  "type": "dataset_snapshot",
  "role": "internal",
  "name": "housing_market",
  "grain": "monthly",
  "time_index": "date",
  "date_range": {
    "start": "2006-01-31",
    "end": "2025-09-30"
  },
  "schema_ref": "artifact:schema:housing_market",
  "artifact_refs": [
    {
      "uri": "repo://Demo Data/housing_market.csv",
      "media_type": "text/csv"
    }
  ]
}
```

Use `dataset_snapshot`, not just `dataset`, because model lineage depends on
the specific data state used by a run.

### DataProfile

```json
{
  "asset_id": "data_profile:internal:housing_market:20260630",
  "type": "data_profile",
  "source_asset_ids": [
    "dataset_snapshot:internal:housing_market:20260630"
  ],
  "row_count": 240,
  "column_count": 12,
  "date_range": {
    "start": "2006-01-31",
    "end": "2025-09-30"
  },
  "quality_flags": [
    {
      "code": "MISSING_VALUES_DETECTED",
      "severity": "warning",
      "column": "home_price_index"
    }
  ]
}
```

### FeatureRecipe

Reusable recipes can live in global, domain, or project libraries.

```json
{
  "recipe_id": "recipe:yield_slope:10y_2y:v1",
  "type": "feature_recipe",
  "name": "10Y-2Y Treasury yield slope",
  "scope": "global",
  "recipe_kind": "arithmetic",
  "expression_template": "{gov_yield_10y} - {gov_yield_2y}",
  "required_inputs": [
    {
      "slot": "gov_yield_10y",
      "semantic_type": "government_yield",
      "tenor": "10Y"
    },
    {
      "slot": "gov_yield_2y",
      "semantic_type": "government_yield",
      "tenor": "2Y"
    }
  ],
  "default_output_name": "USYC10_2",
  "category": "yield_slope"
}
```

Recipe scopes:

- `global`: reusable across many projects
- `domain`: reusable across a modeling domain
- `project`: specific to one project

Recipe kinds should be extensible. Initial examples:

- `arithmetic`
- `ratio`
- `lag`
- `growth`
- `rolling`
- `regime`
- `interaction`
- `clip`
- `standardize`

### FeatureRecipeProposal

Natural-language feature requests should produce proposals before mutating or
materializing data.

```json
{
  "protocol_version": "0.1",
  "asset_id": "feature_recipe_proposal:yield_curve_steepness",
  "type": "feature_recipe_proposal",
  "created_at": "2026-06-30T14:23:00Z",
  "created_by_run_id": "recipe_proposal_20260630_142300",
  "source_asset_ids": [],
  "artifact_refs": [],
  "source_run_id": "recipe_proposal_20260630_142300",
  "status": "proposed",
  "scope": "project",
  "request": "Create variables that capture yield curve steepness.",
  "available_columns": ["USGOV10Y", "USGOV2Y", "USGOV3M"],
  "proposed_recipes": [
    {
      "name": "USYC10_2",
      "recipe_kind": "arithmetic",
      "expression": "USGOV10Y - USGOV2Y",
      "expression_language": "lego_formula_v0",
      "source_columns": ["USGOV10Y", "USGOV2Y"],
      "category": "yield_slope",
      "rationale": "Classic 10Y-2Y slope."
    }
  ]
}
```

The initial Mindstorms implementation creates deterministic proposal assets
from explicit CLI arguments:

```text
lego recipe propose --request "Create yield slope" --name USYC10_2 --expression "USGOV10Y - USGOV2Y" --source-columns USGOV10Y USGOV2Y --category yield_slope --scope project --json
```

The command writes a `propose_feature_recipes` run manifest and one
`feature_recipe_proposal` asset. It does not call an LLM, materialize features,
create a `FeatureSet`, or create a `DerivedDatasetSnapshot`.

Recommended proposal lifecycle:

- `proposed`
- `reviewed`
- `approved`
- `applied`
- `rejected`

### DerivedDatasetSnapshot and FeatureSet

`build_features` should not mutate a raw DatasetSnapshot. It should produce a
derived dataset snapshot plus a modeling-facing FeatureSet.

```json
{
  "asset_id": "dataset_snapshot:mev:macro_monthly_enriched:20260630",
  "type": "derived_dataset_snapshot",
  "source_asset_ids": [
    "dataset_snapshot:mev:macro_monthly:20260630"
  ],
  "added_columns": ["USYC10_2", "USMORT30_T10_SPRD"]
}
```

```json
{
  "asset_id": "feature_set:macro_yield_spreads:v1",
  "type": "feature_set",
  "source_asset_ids": [
    "dataset_snapshot:mev:macro_monthly_enriched:20260630"
  ],
  "features": [
    {
      "name": "USYC10_2",
      "expression": "USGOV10Y - USGOV2Y",
      "expression_language": "lego_formula_v0",
      "source_columns": ["USGOV10Y", "USGOV2Y"],
      "category": "yield_slope",
      "description": "10-year Treasury yield less 2-year Treasury yield.",
      "allowed_for_search": true
    }
  ]
}
```

### ModelingFrame

```json
{
  "asset_id": "modeling_frame:home_price_GR1:v1",
  "type": "modeling_frame",
  "project_context_id": "project_context:housing_ppnr_2026:v1",
  "target": {
    "name": "home_price_GR1",
    "frequency": "monthly",
    "expression": "pct_change(home_price_index, 1).shift(-1)",
    "source_columns": ["home_price_index"]
  },
  "sample_policy": {
    "in_sample": {
      "start": "2006-01-31",
      "end": "2023-09-30"
    },
    "out_of_sample": {
      "start": "2023-10-31",
      "end": "2025-09-30"
    },
    "full_sample": {
      "end": "2025-09-30"
    }
  },
  "scenario_policy": {
    "jump_off_date": "2023-09-30",
    "scenario_set": "CCAR_2026",
    "scenario_names": ["Base", "Adv", "Sev"]
  },
  "source_asset_ids": [
    "dataset_snapshot:internal:housing_market:20260630",
    "dataset_snapshot:mev:macro_monthly_enriched:20260630",
    "feature_set:macro_yield_spreads:v1"
  ],
  "feature_universe": {
    "feature_set_ids": ["feature_set:macro_yield_spreads:v1"],
    "allowed_features": ["USYC10_2", "USMORT30_T10_SPRD"]
  }
}
```

### ModelingIteration

```json
{
  "asset_id": "modeling_iteration:home_price_GR1:iter_003",
  "type": "modeling_iteration",
  "modeling_frame_id": "modeling_frame:home_price_GR1:v1",
  "iteration_number": 3,
  "status": "evaluated",
  "goal": "Improve OOS performance and reduce scenario instability.",
  "started_from": {
    "previous_iteration_id": "modeling_iteration:home_price_GR1:iter_002",
    "diagnosis": [
      "Top candidates had acceptable in-sample fit but weak OOS error.",
      "Mortgage spread variables dominated the pool; labor market features were underexplored."
    ]
  },
  "run_ids": [
    "feature_20260630_1010",
    "pool_20260630_1015",
    "search_20260630_1020",
    "eval_20260630_1045"
  ],
  "produced_asset_ids": [
    "feature_set:labor_market_pressure:v1",
    "search_pool:home_price_GR1:iter_003",
    "candidate_model:home_price_GR1:cm17",
    "evaluation_result:home_price_GR1:iter_003"
  ]
}
```

Suggested iteration statuses:

- `planned`
- `running`
- `searched`
- `evaluated`
- `needs_improvement`
- `approved`
- `abandoned`

### SearchConfig

SearchConfig records how a specific model search was executed. It is separate
from SearchPool because execution parameters are not the same thing as driver
selection judgment.

In early v0.1 implementation, SearchConfig can live directly in the
`search_candidate_models` run `inputs`. It should only be persisted as a
durable Asset if another Asset needs to reference it directly or if the same
configuration is reused across runs.

```json
{
  "asset_id": "search_config:home_price_GR1:search_20260630_1020",
  "type": "search_config",
  "modeling_frame_id": "modeling_frame:home_price_GR1:v1",
  "modeling_iteration_id": "modeling_iteration:home_price_GR1:iter_003",
  "search_pool_id": "search_pool:home_price_GR1:iter_003",
  "engine": {
    "name": "technic_model_search",
    "version": "legacy_adapter"
  },
  "driver_pool": ["USMORT30_T10_SPRD", "USPRIME_FF_SPRD", "USUNRATE"],
  "forced_in": [],
  "constraints": {
    "top_n": 5,
    "max_var_num": 2,
    "max_lag": 1,
    "periods": [1]
  },
  "filter_profile": "default",
  "runtime_budget": {
    "max_candidates": null,
    "max_seconds": null
  }
}
```

Design rules:

- SearchConfig records execution facts.
- SearchPool records curation judgment.
- Legacy CLI inputs such as `desired_pool`, `top_n`, `max_var_num`, and
  `max_lag` should become SearchConfig fields first.
- Do not synthesize a SearchPool from CLI inputs alone unless the workflow also
  records driver inclusion/exclusion rationale or screening evidence.
- If no SearchPool exists yet, CandidateModel assets can rely on
  `source_run_id` plus the run's stable SearchConfig input for reproducibility.

### SearchPool

```json
{
  "asset_id": "search_pool:home_price_GR1:iter_003",
  "type": "search_pool",
  "modeling_frame_id": "modeling_frame:home_price_GR1:v1",
  "modeling_iteration_id": "modeling_iteration:home_price_GR1:iter_003",
  "source_asset_ids": [
    "modeling_frame:home_price_GR1:v1",
    "feature_set:macro_yield_spreads:v1",
    "feature_set:labor_market_pressure:v1"
  ],
  "target": "home_price_GR1",
  "included_drivers": [
    {
      "name": "USMORT30_T10_SPRD",
      "reason": "Mortgage spread has direct economic relevance to housing affordability.",
      "source_asset_id": "feature_set:macro_yield_spreads:v1"
    },
    {
      "name": "USPRIME_FF_SPRD",
      "reason": "Bank pricing spread may proxy credit conditions."
    }
  ],
  "excluded_drivers": [
    {
      "name": "USYC30_10",
      "reason": "Highly overlapping with other yield slope candidates selected for this search."
    }
  ],
  "selection_method": {
    "type": "agent_assisted",
    "criteria": [
      "economic relevance",
      "data availability",
      "correlation with target",
      "avoid near-duplicate drivers",
      "search runtime budget"
    ]
  }
}
```

### CandidateModel

```json
{
  "asset_id": "candidate_model:home_price_GR1:cm17",
  "type": "candidate_model",
  "model_id": "cm17",
  "modeling_frame_id": "modeling_frame:home_price_GR1:v1",
  "modeling_iteration_id": "modeling_iteration:home_price_GR1:iter_003",
  "source_run_id": "search_20260630_1020",
  "target": "home_price_GR1",
  "formula": "home_price_GR1 ~ USMORT30_T10_SPRD + USUNRATE",
  "specs": ["USMORT30_T10_SPRD", "USUNRATE"],
  "model_family": "ols",
  "metrics": [
    {
      "name": "rsquared",
      "value": 0.82,
      "sample": "in_sample"
    },
    {
      "name": "rmse",
      "value": 0.031,
      "sample": "out_of_sample"
    }
  ],
  "artifact_refs": [
    {
      "uri": "technic://Segment/home_price_GR1/cms/search_20260630_1020/cm17",
      "role": "technic_candidate_model",
      "media_type": "application/vnd.lego.technic-candidate"
    }
  ]
}
```

When a CandidateModel comes from the current Technic search adapter, v0.1 may
include both the search directory and candidate-specific backend references:

```json
[
  {
    "uri": "technic://Segment/home_price_GR1/cms/search_20260630_1020",
    "role": "technic_search_directory",
    "media_type": "application/vnd.lego.technic-search"
  },
  {
    "uri": "technic://Segment/home_price_GR1/cms/search_20260630_1020/cm17",
    "role": "technic_candidate_model",
    "media_type": "application/vnd.lego.technic-candidate"
  }
]
```

The stable URI should be derived from `segment_id`, `search_id`, and
`model_id`. Machine-local fields such as `outputs.artifacts_dir` can help the
adapter discover context, but should not be copied into stable `artifact_refs`.

### EvaluationResult

```json
{
  "protocol_version": "0.1",
  "asset_id": "evaluation_result:home_price_GR1:search_20260630_1020",
  "type": "evaluation_result",
  "created_at": "2026-06-30T10:24:12Z",
  "created_by_run_id": "search_20260630_1020",
  "source_asset_ids": [
    "candidate_model:home_price_GR1:cm17"
  ],
  "artifact_refs": [],
  "source_run_id": "search_20260630_1020",
  "target": "home_price_GR1",
  "candidate_model_ids": [
    "candidate_model:home_price_GR1:cm17"
  ],
  "best_candidate_model_id": "candidate_model:home_price_GR1:cm17",
  "summary": {
    "status": "needs_review",
    "selected_count": 1,
    "zero_selected_is_valid": true,
    "warning_count": 0
  },
  "weaknesses": [],
  "recommended_next_actions": []
}
```

The initial Mindstorms implementation writes one EvaluationResult asset for
successful search workflows. It summarizes the selected candidate count,
candidate model asset IDs, an obvious best candidate when one exists, whether
zero selected models is valid, and warning count. If zero candidates are
selected and `zero_selected_is_valid` is true, `summary.status` is
`no_candidates_selected`; otherwise the default status is `needs_review`.

Full diagnostic weakness codes, scenario-path analysis, and approval semantics
remain future work.

### ApprovalDecision

```json
{
  "asset_id": "approval_decision:home_price_GR1:cm17",
  "type": "approval_decision",
  "candidate_model_id": "candidate_model:home_price_GR1:cm17",
  "decision": "approved",
  "approved_by": {
    "role": "model_owner",
    "name": "TBD"
  },
  "rationale": "Best balance of interpretability, OOS performance, and scenario behavior.",
  "created_at": "2026-06-30T15:30:00Z"
}
```

## Warning and Error Records

Warning records should be structured and stable enough for agents to summarize
or branch on known codes.

```json
{
  "code": "SCENARIO_INTERNAL_DATA_FALLBACK",
  "count": 2,
  "severity": "info",
  "fatal": false,
  "message": "No scenario internal data was available for some scenarios; main internal data was used as feature-engineering context.",
  "scenarios": ["Base", "Sev"]
}
```

Known warning codes can be documented as stable enums. Unknown future warning
codes must not break consumers.

Error records should be a list, not a single object, because future workflows
can have partial failures.

```json
{
  "code": "ARTIFACT_WRITE_FAILED",
  "severity": "error",
  "fatal": false,
  "message": "The model chart could not be written, but candidate evaluation succeeded."
}
```

## Stable Fields vs Diagnostic Fields

Stable fields are part of the protocol contract. Agents and Studio may parse
them long term.

Examples:

- `protocol_version`
- `run_id`
- `workflow_id`
- `status`
- `created_at`
- `completed_at`
- `inputs`
- `outputs.summary`
- `outputs.assets`
- `warnings`
- `errors`
- `asset_id`
- `type`
- `source_asset_ids`
- `artifact_refs`

Diagnostic fields are useful for debugging but are not stable.

Examples:

- `captured_stdout`
- `captured_stderr`
- backend raw dumps
- stack traces
- temporary absolute paths
- notebook cell outputs

Diagnostic data should live under `outputs.diagnostics` or a clearly marked
diagnostic artifact.

## File Layout Recommendation

Keep v0.1 file-based.

Recommended layout:

```text
.lego/
  runs/
    latest
    <run_id>/
      manifest.json
  projects/
    <project_id>/
      context.json
      modeling_frames/
        <frame_id>.json
      iterations/
        <iteration_id>.json
  assets/
    candidate_model/
      <target>/
        <model_id>.json
    search_pool/
      <target>/
        <iteration_id>.json
    evaluation_result/
      <target>/
        <run_id>.json
    index.json
  recipes/
    global/
      <recipe_id>.json
    domain/
      <domain>/
        <recipe_id>.json
    projects/
      <project_id>/
        <recipe_id>.json
```

v0.1 should use run manifests as execution records, not as the only durable
asset store. Each durable Asset emitted in `outputs.assets` must have a
standalone JSON file addressable by its AssetRef `uri`.

Run manifests are execution records. Asset JSON files are durable modeling
state. The asset storage seam owns asset path, index, read, and write
mechanics; workflow code should construct semantic asset payloads rather than
hand-roll storage details.

`.lego/assets/index.json` is useful for cross-run lookup, but it is an optional
index over asset files rather than the source of truth. A reader should be able
to resolve an AssetRef directly to the corresponding asset JSON without the
index.

AssetRef URI mapping should be direct and local in v0.1:

```text
asset://candidate_model/home_price_GR1/cm17.json
-> .lego/assets/candidate_model/home_price_GR1/cm17.json
```

Rules:

- The URI scheme must be `asset://`.
- The URI path must be relative to `.lego/assets/`.
- The URI path should end in `.json`.
- The URI path should not contain `..`, drive letters, or absolute paths.
- The URI path should be stable across machines and should not include
  machine-local temporary directories.

Generated `.lego/` artifacts remain local run outputs and should not be
committed unless a specific fixture or example is intentionally added.

## Technic Adapter Strategy

The protocol should be a deep module interface for modeling state. `Technic`
should sit behind an adapter seam.

The adapter can:

- Register or load data through existing loaders.
- Apply feature construction functions.
- Build current `Segment` objects internally when needed.
- Run existing model search and fit machinery.
- Convert `Technic` candidate models into protocol `CandidateModel` assets.
- Convert `Technic` output directories into `ArtifactRef` records.

The protocol should not expose `Technic Segment`, `DataManager`, `CM`, or
search directory details as required public concepts. They can appear in
diagnostics or `technic://` artifact references.

## How Current Mindstorms Maps to v0.1

Current `.lego/runs/<run_id>/manifest.json` fields map naturally:

- `workflow` becomes `workflow_id`.
- `run_id`, `created_at`, `completed_at`, `status`, and `inputs` remain stable.
- `outputs.selected_models` becomes standalone `CandidateModel` asset files,
  referenced from `outputs.assets[]` with `type = candidate_model`.
- `outputs.selected_count` becomes `outputs.summary.selected_count`.
- `outputs.artifacts_dir` can be mapped to stable `technic://` `ArtifactRef`
  URIs; the absolute local path itself should not become the protocol URI.
- Successful search runs also emit a minimal `EvaluationResult` asset,
  referenced from `outputs.assets[]` with `role = search_evaluation`.
- `warnings` keep their current structured shape.
- `captured_stdout` and `captured_stderr` move under `outputs.diagnostics`.

Backward compatibility can be maintained by supporting old manifests during a
transition period.

## Command Catalog

`lego help --json` is related but should be treated as a separate command
protocol rather than part of the Asset/Run Protocol.

The Asset/Run Protocol can reference workflows by `workflow_id`. The command
catalog can explain which CLI command invokes a workflow, whether it is safe for
agents, and what input flags it accepts.

## Open Questions

1. Should `ProjectContext` also have a project metadata mirror under
   `.lego/projects/<project_id>/context.json`, or only exist as an Asset?
2. How much formula language should v0.1 standardize for feature recipes?
3. Should feature recipes be executable definitions, descriptive definitions, or
   both?
4. Should `SearchPool` include statistical screening outputs directly, or
   reference a separate screening asset?
5. Should `SearchConfig` remain only as stable run input for v0.1, or should
   search runs also write durable `search_config` assets?
6. Should `EvaluationResult` define a stable weakness-code enum in v0.1?
7. Should approval require a human identity field, or allow agent-recommended
   approval proposals that still require human acceptance?
8. How should sensitive data paths or corporate-only data references be
   represented without leaking machine-local paths?

## Future Implementation Slices

1. Add a compatibility reader that maps pre-v0.1 manifests to v0.1 shape.
2. Add richer `CandidateModel` asset conversion from current demo fit/search
   outputs, including stable artifact references when available.
3. Add stable `SearchConfig` mapping for search runs, keeping legacy CLI search
   parameters separate from curated `SearchPool` judgment.
4. Add `SearchPool` asset writing only after there is a workflow or input
   surface that captures included/excluded driver rationale or screening
   evidence.
5. Add `EvaluationResult` asset writing for the modeling loop.
6. Add a transition plan for eventually hiding or dropping legacy manifest
   fields once downstream consumers use v0.1 fields.
7. Add recipe proposal/build feature design prototypes before implementing full
   natural-language feature engineering.
