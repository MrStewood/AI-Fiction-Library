---
schema_version: "0.1.0"
artifact_id: "controlled-test"
title: "Controlled Test Policy"
status: "APPROVED"
version: 1
canonical: false
authoring_agent: "managing_editor"
created_at: "2026-09-18"
approved_by: "managing_editor"
approved_at: "2026-09-18"
depends_on: []
book_id: "2e64d4cf-7b56-42f2-9aaa-6934fe48dd0d"
project_id: "51909d1d-2f17-4748-bc81-a9641f41a640"
---

# Controlled Test Policy

This book is a **controlled pilot**. Goal: one stable process, observable evidence — not mid-run perfection.

## Freeze
Once the run starts:
1. Do **not** change workflow, agent instructions, pack matrices, or gate schemas unless execution is **completely blocked**.
2. Log non-blocking defects in `00_admin/DECISION_LOG.md` (tag `pilot-defect`).
3. Fix defects **after** the run; record recommendations in `PILOT_POSTMORTEM.md`.

## Separation of roles
- Drafting / redrafting: MiMo 2.5 (`studio-drafter`) — Drafting Author
- Craft / developmental review: DeepSeek V4.1 Flash (`studio-coordinator`) — Developmental Reviewer
- Reviewer inputs: Creative Brief + Style Guide + scene contract + draft **only** (no drafter self-eval)

## Short-story pilot profile
- 4,000–5,000 words; ~4–6 scenes; one central conflict
- Minimal cast/locations; no subplot unless essential
- Early target-reader after opening scene (never later than scene 2)

## Preserve evidence
Keep all drafts, failed reviews, revision directives, and rejected artifacts. Do not delete the pilot if it fails.

## Metrics + postmortem
Maintain `00_admin/EXPERIMENT_METRICS.md` during the run and `00_admin/PILOT_POSTMORTEM.md` at the end.
