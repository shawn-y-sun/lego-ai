# LEGO AI Agent Contract

These instructions are shared by all coding agents working in this repository.

## Start Every Session

Before planning or implementation, read:

1. `README.md`
2. `docs/lego_ai_master_plan.md`
3. `docs/lego_ai_tracker.md`
4. `lego help --json`

Treat these repo files as shared memory. Do not rely on temp handoff files as
long-term source of truth.

## Architecture Posture

- `Technic` is the long-term modeling-engine name. The current `Technic/` folder
  is legacy/reference notebook-oriented code, not a protected baseline.
- It is valid to refactor, replace, or rewrite Technic when that better serves
  the AI/CLI-native LEGO AI direction.
- `Mindstorms` is the agent-facing CLI/control/protocol layer.
- `Studio` is the human visual layer over protocol state.

## Agent Run Workflow

- Prefer `lego ... --json` commands for agent runs.
- Inspect `.lego/runs/latest` and `.lego/runs/<run_id>/manifest.json` for run
  state.
- Use `lego assets list --json` and `lego asset inspect <asset_id> --json` for
  durable protocol assets.
- Do not operate notebook workflows directly for agent runs.
- If search is slow or a reliable demo candidate is needed, use
  `lego demo fit-single --vars USMORT30Y --json` or
  `lego demo search-smoke --json` first.

## Shared Memory Updates

- Update `docs/lego_ai_master_plan.md` when architecture decisions, vocabulary,
  or long-term roadmap principles change.
- Update `docs/lego_ai_tracker.md` when completed work, active status, next
  steps, backlog, important commits, or handoff state changes.
- Before final handoff/response, either update those files or state that no
  master-plan/tracker update was needed.

## Local CLI Setup

- Preferred setup is `pip install -e .` followed by the `lego` console command.
- Corporate fallback is `scripts\lego.cmd` when install, PyPI, or SSL is blocked
  but a Python with dependencies exists.
- Set `LEGO_PYTHON=C:\Path\To\Python.exe` when the fallback script needs an
  explicit Python executable.

## Generated Artifacts

- Generated `.lego/`, `Segment/`, cache, and egg-info artifacts are local outputs
  and should not be committed unless a session explicitly converts something
  into a fixture.
