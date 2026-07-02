# LEGO AI Master Plan

Status: living project control document

This document is the stable memory for LEGO AI. It records the north star,
architecture decisions, vocabulary, and roadmap principles that should survive
across sessions and agents.

For day-to-day progress, read `docs/lego_ai_tracker.md`.

## North Star

LEGO AI is an AI-native modeling workflow for PPR and regulatory-style financial
modeling. It should let agents and humans build, inspect, evaluate, and document
models through structured commands and durable protocol assets rather than
notebook side effects.

The guiding principle:

```text
Make modeling state clear, structured, inspectable, and reproducible before
making the agent more autonomous.
```

## Architecture Decisions

### LEGO Naming

- `Technic` is the long-term name for the modeling engine.
- The current `Technic/` folder is legacy/reference code designed for
  notebook-oriented human workflows.
- Future Technic work may rewrite or replace the current engine with an
  AI/CLI-native implementation.
- `Mindstorms` is the agent-facing control layer for CLI workflows, run
  manifests, and protocol assets.
- `Studio` is the human visual layer for inspecting protocol state and workflow
  outputs.

### Technic Legacy And Technic Next

Earlier MVP work treated `Technic` as something not to touch. That was a short
term safety rule, not a permanent architecture principle.

Current decision:

```text
Do not casually patch legacy Technic for protocol/UI needs.
It is valid to design and build a new AI-native Technic that eventually
replaces the legacy notebook-oriented engine.
```

Legacy `Technic` remains valuable as a reference implementation for data loading,
feature construction, fitting, search, diagnostics, scenario behavior, and export
logic.

Future Technic should be:

- command-friendly
- deterministic
- structured-input and structured-output first
- protocol-asset first
- warning/error-as-data oriented
- inspectable and testable without notebook state
- free of meaningful stdout as a state channel

### Protocol First

LEGO AI should expose stable protocol state instead of requiring agents or
humans to understand internal Python objects.

Stable state currently lives in:

- run manifests under `.lego/runs`
- durable assets under `.lego/assets`
- Studio snapshots derived from runs and assets

Raw stdout/stderr are diagnostic-only. Important modeling meaning should migrate
into structured summaries and durable assets.

### Studio Direction

Studio started as a read-only protocol explorer. Human review showed that a
generic protocol explorer is not enough. Studio should become a set of
workflow-specific review surfaces.

Near-term Studio direction:

```text
Search Review should help a modeler review a search round, inspect selected or
top model options, and understand model artifacts without reading raw JSON.
```

Static HTML is a first renderer, not the Studio architecture. `StudioSnapshot`
and workflow view models are the interfaces to protect.

## Vocabulary

- `Run`: one command/workflow execution with a manifest, status, inputs,
  outputs, warnings, errors, and artifacts.
- `Workflow`: a named action pattern such as fit-single, search-smoke,
  build-features, or recipe-approve.
- `Asset`: a durable protocol object written under `.lego/assets`.
- `ArtifactRef`: a reference to a local output, legacy Technic object, or
  protocol asset.
- `CandidateModel`: protocol asset representing a model option produced by a fit
  or search run.
- `Model Option`: human-facing UI term for a candidate model.
- `Selected Model`: best/selected model for a run. This is not necessarily the
  final human-approved champion.
- `EvaluationResult`: protocol asset representing a fit/search evaluation
  outcome. UI should usually call this `Search Results` or `Search Summary`.
- `SearchConfig`: concrete search execution parameters.
- `SearchPool`: future curated driver-selection judgment with rationale and
  screening evidence. Do not synthesize it from SearchConfig alone.
- `ModelingFrame`: future durable definition of the modeling problem, including
  target, frequency, sample windows, scenario policy, datasets, feature universe,
  and effective assumptions.
- `ModelReviewArtifact`: planned per-model review output for charts, time series,
  tests, scenario summaries, and metrics.

## Completed Milestones

1. Mindstorms CLI MVP.
2. Copilot CLI pilot pack.
3. Corporate laptop Copilot CLI pilot.
4. Asset/Run Protocol v0.1 spine.
5. Durable asset index/list/inspect commands.
6. CandidateModel and EvaluationResult assets for fit/search.
7. Deterministic FeatureRecipe proposal, approval, and build-features path.
8. Studio Zero read-only snapshot/export.
9. Search/Fit Visibility protocol tightening.
10. Studio Detail prototype.
11. Search Review prototype.

See `docs/lego_ai_tracker.md` for current status and latest commits.

## Current Feedback And Learnings

- Agents can operate LEGO AI through the `lego` CLI.
- Corporate environments may block package indexes; `scripts/lego.cmd` is the
  documented source-wrapper fallback.
- Protocol assets are useful, but raw protocol object views are not enough for
  humans.
- Studio needs workflow-specific views.
- Search Review should be organized around search rounds and model options, not
  raw asset cards.
- Per-model review needs richer artifacts before UI polish will be useful.
- Adapter-local IDs such as `cm1` are not durable. Asset IDs must be scoped by a
  stable context such as run id.

## Current Roadmap

Recommended near-term path:

```text
Per-Model Review Artifact Protocol
-> Technic Next Architecture Planning
-> ModelingFrame minimal
-> SearchPool
-> Search Review richer UI and Studio workflow tabs
```

Rationale:

The current Search Review prototype showed the right workflow direction but also
showed that useful per-model review needs model-level chart/test/scenario
artifacts first.

## Open Questions

- What is the minimal useful `ModelReviewArtifact`?
- Should per-model review produce chart-ready data, static image artifacts, or
  both?
- What is the first Technic Next vertical?
- Which legacy Technic behavior should be wrapped versus rewritten?
- When does `Selected Model` become a human-approved champion?
- How should Search Review handle top N: selected candidates, ranked survivors,
  or all model options?
- Should Studio keep a separate protocol/debug explorer export mode?

## Agent Reading Order

New coding agents should read:

1. `ASSISTANT.md`
2. `README.md`
3. `docs/lego_ai_master_plan.md`
4. `docs/lego_ai_tracker.md`
5. `lego help --json`

Agents should update this file when architecture decisions, vocabulary, or
roadmap principles change.
