# LEGO AI

LEGO AI is an AI-native modeling workflow project for PPR and regulatory-style
financial modeling. It is evolving from the original Project LEGO notebook-based
Python package into a command-line, protocol-driven, agent-operable modeling
system.

The current goal is not only to fit models. The goal is to make every modeling
step inspectable, reproducible, and usable by coding agents through structured
commands and durable local artifacts.

## Project Shape

LEGO AI currently uses three LEGO-themed layers:

- `Technic`: the long-term name for the modeling engine. The current
  `Technic/` folder is legacy/reference code designed for notebook-oriented
  human workflows. Future Technic work may replace or rewrite this engine for
  AI/CLI-native workflows.
- `Mindstorms`: the agent-facing control layer. It exposes the `lego` CLI,
  writes run manifests, creates durable protocol assets, and adapts existing
  modeling behavior into structured outputs.
- `Studio`: the human visual layer. Studio Zero currently exports static HTML
  from protocol state so humans can inspect runs, assets, model options, and
  diagnostics.

The current state surface is file-based:

- `.lego/runs/<run_id>/manifest.json`
- `.lego/runs/latest`
- `.lego/assets/index.json`
- `.lego/assets/...`
- `.lego/studio/index.html`

Generated `.lego/` and `Segment/` artifacts are local outputs and should not be
committed.

## Start Here

For project memory and planning context, read:

- `ASSISTANT.md`: shared coding-agent contract.
- `docs/lego_ai_master_plan.md`: stable architecture decisions, vocabulary, and
  roadmap.
- `docs/lego_ai_tracker.md`: current status, completed milestones, next work,
  and backlog.

The old Project LEGO README has been replaced because it described the legacy
notebook package, not the current LEGO AI product direction.

## Install

Recommended local setup:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
lego --version
```

Corporate laptop fallback, when editable install or package indexes are blocked:

```bat
set LEGO_PYTHON=C:\Path\To\Python.exe
scripts\lego.cmd --version
```

The fallback requires a Python environment that already has the project
dependencies available.

## Agent-Friendly Commands

Use the command catalog first:

```bash
lego help --json
```

Reliable demo path:

```bash
lego demo init --json
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego run inspect latest --json
```

Protocol asset inspection:

```bash
lego assets list --json
lego asset inspect <asset_id> --json
```

Feature recipe and deterministic feature build path:

```bash
lego recipe propose --request "Create yield slope" --name USYC10_2 --expression "USGOV10Y - USGOV2Y" --source-columns USGOV10Y USGOV2Y --json
lego recipe approve --proposal-id <proposal_asset_id> --approved-by <name> --json
lego features build --recipe-id <recipe_asset_id> --source-csv "Demo Data/macro_monthly.csv" --date-column observation_date --output-name macro_monthly_enriched --json
```

Studio Zero:

```bash
lego studio snapshot --json
lego studio export --html .lego/studio/index.html
```

Open the exported Studio page:

```text
file:///D:/Project/LEGO_AI/.lego/studio/index.html
```

## Current Capabilities

Implemented and validated so far:

- Mindstorms CLI MVP.
- Corporate Copilot CLI pilot.
- Asset/Run Protocol v0.1 spine.
- Durable CandidateModel and EvaluationResult assets for fit/search workflows.
- Deterministic FeatureRecipe proposal, approval, and build-features path.
- Studio Zero static snapshot/export.
- Search Review prototype focused on selected model and search result review.

## Current Roadmap

Near-term direction:

1. Per-Model Review Artifact Protocol.
2. Technic Next architecture planning for an AI/CLI-native modeling engine.
3. ModelingFrame minimal.
4. SearchPool, once real driver curation rationale exists.
5. Richer Search Review and Studio workflow tabs.

See `docs/lego_ai_tracker.md` for the current active status and backlog.

## Development Notes

- Prefer `lego ... --json` for agent-run workflows.
- Do not use notebooks as the agent execution path.
- Keep raw stdout/stderr diagnostic-only; important modeling state should become
  structured summaries or durable assets.
- Adapter-local IDs such as `cm1` are not durable by themselves. Scope durable
  asset IDs by run or another stable protocol context.
- Update `docs/lego_ai_master_plan.md` when architecture decisions change.
- Update `docs/lego_ai_tracker.md` when work status, next steps, or backlog
  changes.

## Tests

Run the full suite:

```bash
python -m pytest
```

Targeted Studio tests:

```bash
python -m pytest tests/test_mindstorms_studio.py
```
