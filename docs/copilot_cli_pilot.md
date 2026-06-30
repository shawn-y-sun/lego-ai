# Copilot CLI Pilot

This pilot pack lets GitHub Copilot CLI or another coding agent install and drive the Mindstorms demo CLI without operating the notebook workflow directly.

## Setup

Preferred path: editable install, then use the `lego` console command:

```bash
git clone https://github.com/shawn-y-sun/lego-ai.git LEGO_AI
cd LEGO_AI
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
lego --version
```

Corporate fallback path: use the source wrapper only when PyPI, SSL, venv, or editable install is blocked but a Python with the project dependencies is already available:

```bat
git clone https://github.com/shawn-y-sun/lego-ai.git LEGO_AI
cd LEGO_AI
set LEGO_PYTHON=C:\Path\To\Your\Python.exe
scripts\lego.cmd --version
scripts\lego.cmd help --json
scripts\lego.cmd demo fit-single --vars USMORT30Y --json
```

If `py -3` or `python` already points to a Python with the required dependencies, `LEGO_PYTHON` is optional. The wrapper sets `PYTHONPATH` to the repository root and invokes `Mindstorms.cli` from source, so it does not require package installation.

## Smoke Test

```bash
lego --version
lego help --json
lego demo init --json
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego run inspect latest --json
```

When using the source wrapper, replace `lego` with `scripts\lego.cmd` in the same commands.

`demo search-smoke` is the reliable pilot search path. It runs a tiny demo-only search with relaxed filters so agents can confirm search plumbing and should return at least one selected model on the demo data.

`demo search` remains an honest modeling search. A successful run can select zero models if no candidate passes the configured filters; JSON outputs include `selected_count` and `zero_selected_is_valid` to distinguish that outcome from a command failure.

`demo fit-single` is another reliable fallback when broader search is slow or noisy:

```bash
lego demo fit-single --vars USMORT30Y --json
lego run inspect latest --json
```

## Agent Notes

Mindstorms writes run manifests under `.lego/runs/`. Inspect `.lego/runs/latest` to find the newest run ID, then read `.lego/runs/<run_id>/manifest.json` for structured state and outputs.

Command outputs and manifests include structured non-fatal warning summaries when known repeated warnings are captured. Raw captured stdout/stderr may still be present for diagnosis, but agents should prefer the `warnings` field for quick status.

Generated `.lego/` artifacts are local run outputs and should not be committed.

## Starter Prompt for Copilot CLI

Paste this into Copilot CLI from the repository root after setup:

```text
You are helping me test the Project LEGO Mindstorms CLI pilot.

Read AGENTS.md and docs/copilot_cli_pilot.md first.

Use the agent-facing CLI, not the notebooks. Prefer commands that emit JSON.

If the `lego` command is unavailable because package installation is blocked, use `scripts\lego.cmd` instead. If needed, set `LEGO_PYTHON` to the full path of a Python executable that already has the project dependencies installed.

Please run these checks and summarize the result:

1. lego --version
2. lego help --json
3. lego demo init --json
4. lego demo fit-single --vars USMORT30Y --json
5. lego demo search-smoke --json
6. lego run inspect latest --json

If those pass and runtime looks reasonable, also run:

lego demo search --top-n 5 --max-var-num 2 --max-lag 1 --json

After each run, inspect .lego/runs/latest and the latest manifest at .lego/runs/<run_id>/manifest.json. Tell me:

- whether each command succeeded
- the latest run_id
- the workflow name
- whether selected_models is present
- any structured warnings, captured warnings, or errors worth knowing about

Do not modify Technic unless I explicitly ask. Do not commit generated .lego/ or Segment artifacts.
```
