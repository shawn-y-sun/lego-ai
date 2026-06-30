# Agent Instructions

- `Technic` is the core modeling engine. Avoid changing it unless explicitly asked.
- `Mindstorms` is the agent-facing control layer for CLI workflows and run manifests.
- Prefer `lego ... --json` commands for agent runs.
- Use `lego help --json` to discover the current machine-readable command catalog.
- Inspect `.lego/runs/latest` and `.lego/runs/<run_id>/manifest.json` for run state.
- Do not operate the notebook workflow directly for agent runs.
- Preferred CLI setup is `pip install -e .` followed by the `lego` console command.
- Corporate fallback is `scripts\lego.cmd` when install/PyPI/SSL is blocked but a Python with dependencies exists; set `LEGO_PYTHON=C:\Path\To\Python.exe` if needed.
- If search is slow or a reliable demo candidate is needed, use `lego demo fit-single --vars USMORT30Y --json` or `lego demo search-smoke --json` first.
- Generated `.lego/` artifacts are local run outputs and should not be committed.
