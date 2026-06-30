# Agent Instructions

- `Technic` is the core modeling engine. Avoid changing it unless explicitly asked.
- `Mindstorms` is the agent-facing control layer for CLI workflows and run manifests.
- Prefer `lego ... --json` commands for agent runs.
- Inspect `.lego/runs/latest` and `.lego/runs/<run_id>/manifest.json` for run state.
- Do not operate the notebook workflow directly for agent runs.
- If search is slow, use `lego demo fit-single --vars USMORT30Y --json` first.
- Generated `.lego/` artifacts are local run outputs and should not be committed.
