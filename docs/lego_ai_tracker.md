# LEGO AI Tracker

Status: living progress tracker

This document records current progress, next work, backlog, and status changes.
For stable architecture decisions and vocabulary, read
`docs/lego_ai_master_plan.md`.

## Current Status

Current phase:

```text
Project memory consolidation
```

Latest accepted direction:

```text
Search Review prototype is useful as learning, but the next product slice should
produce per-model review artifacts before more Studio UI polish.
```

## Completed

- Mindstorms CLI MVP.
- Copilot CLI pilot pack.
- Corporate laptop Copilot CLI pilot.
- Asset/Run Protocol v0.1 spine.
- Durable asset storage, index, list, and inspect commands.
- CandidateModel assets from fit/search.
- EvaluationResult assets from search workflows.
- Deterministic feature recipe proposal and approval lifecycle.
- Deterministic build-features path.
- Studio Zero snapshot/export.
- Search/Fit Visibility protocol tightening.
- Studio Detail prototype.
- Search Review prototype.
- Project memory reset started with new README, master plan, and tracker.

## In Progress

- Replace old Project LEGO README with LEGO AI project overview.
- Establish `ASSISTANT.md` as the shared coding-agent contract.
- Establish `docs/lego_ai_master_plan.md` and `docs/lego_ai_tracker.md` as
  shared project memory.

## Next

1. Finish and review the Project Memory + README Reset.
2. Commit the documentation reset when accepted.
3. Plan `Per-Model Review Artifact Protocol`.
4. Hand off implementation slices for model review artifacts.

## Backlog

- Per-Model Review Artifact Protocol.
- Technic Next Architecture Planning.
- First Technic Next vertical, likely AI-native fit-single.
- ModelingFrame minimal.
- SearchPool with real driver curation rationale and screening evidence.
- ModelingIteration loop.
- Richer Search Review with search rounds, top N model options, and per-model
  review tabs.
- Studio workflow tabs.
- Wiki/memory ingestion from approved protocol assets and selected summaries.
- Model documentation/export pipeline.

## Decisions To Revisit

- When to start Technic Next.
- Whether to keep current static Studio HTML as a protocol/debug fallback.
- What `Selected Model` means before human champion selection.
- Whether Search Review should show top 10 ranked survivors or top N selected
  candidates.
- Whether per-model review should generate chart-ready data, image artifacts, or
  both.

## Latest Important Commits

- `f31ea47 Add Search Review studio prototype`
- `f4a2e8a Tighten search fit visibility protocol`
- `2f965e0 Add Studio Zero snapshot export`
- `3950f1a Add deterministic recipe approval lifecycle`
- `c3776f2 Add deterministic build features path`
- `b6ffdf5 Add deterministic feature recipe proposals`
- `c285ed7 Add protocol asset storage seam`
- `38f6e29 Harden Mindstorms pilot reliability`

## Current Reliable Commands

```bash
lego help --json
lego demo fit-single --vars USMORT30Y --json
lego demo search-smoke --json
lego assets list --json
lego studio snapshot --json
lego studio export --html .lego/studio/index.html
```

## Shared Memory Rules

- Update `docs/lego_ai_master_plan.md` when architecture decisions, vocabulary,
  or long-term roadmap principles change.
- Update this tracker when completed work, active status, next steps, backlog,
  important commits, or handoff state changes.
- If a session makes no project-memory changes, its final response should say
  that no master plan or tracker update was needed.
