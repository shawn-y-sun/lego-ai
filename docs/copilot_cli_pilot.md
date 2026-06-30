# Copilot CLI Pilot

This pilot pack lets GitHub Copilot CLI or another coding agent install and drive the Mindstorms demo CLI without operating the notebook workflow directly.

## Setup

```bash
git clone https://github.com/shawn-y-sun/lego-ai.git LEGO_AI
cd LEGO_AI
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Smoke Test

```bash
lego --version
lego demo init --json
lego demo fit-single --vars USMORT30Y --json
lego demo search --top-n 5 --max-var-num 2 --max-lag 1 --json
lego run inspect latest --json
```

`demo fit-single` is the reliable fallback when search is slow or noisy:

```bash
lego demo fit-single --vars USMORT30Y --json
lego run inspect latest --json
```

## Agent Notes

Mindstorms writes run manifests under `.lego/runs/`. Inspect `.lego/runs/latest` to find the newest run ID, then read `.lego/runs/<run_id>/manifest.json` for structured state and outputs.

Generated `.lego/` artifacts are local run outputs and should not be committed.

## Starter Prompt for Copilot CLI

Paste this into Copilot CLI from the repository root after setup:

```text
You are helping me test the Project LEGO Mindstorms CLI pilot.

Read AGENTS.md and docs/copilot_cli_pilot.md first.

Use the agent-facing CLI, not the notebooks. Prefer commands that emit JSON.

Please run these checks and summarize the result:

1. lego --version
2. lego demo init --json
3. lego demo fit-single --vars USMORT30Y --json
4. lego run inspect latest --json

If those pass and runtime looks reasonable, also run:

lego demo search --top-n 5 --max-var-num 2 --max-lag 1 --json

After each run, inspect .lego/runs/latest and the latest manifest at .lego/runs/<run_id>/manifest.json. Tell me:

- whether each command succeeded
- the latest run_id
- the workflow name
- whether selected_models is present
- any captured warnings or errors worth knowing about

Do not modify Technic unless I explicitly ask. Do not commit generated .lego/ or Segment artifacts.
```
