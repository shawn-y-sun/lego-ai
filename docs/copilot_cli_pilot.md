# Copilot CLI Pilot

This pilot pack lets GitHub Copilot CLI or another coding agent install and drive the Mindstorms demo CLI without operating the notebook workflow directly.

## Setup

```bash
git clone https://github.com/shawn-y-sun/lego-ai.git
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
