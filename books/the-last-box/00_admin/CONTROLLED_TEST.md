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
book_id: "d76f728c-2b4a-4665-b286-b23395129738"
project_id: "cd3bd67d-1512-4284-abc1-19ce59a69fb7"
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

## Board / confirmation bans (HARD)
1. **Never** call `request_confirmation` for stage continuation, creative decisions, or pipeline gates. The board is observational.
2. **Never** park an issue in `todo` or `in_progress` without a concrete assignee and next-action comment.
3. **Never** PATCH the parent BOOK to `in_review` for stage continuation.
4. **Never** PATCH the parent BOOK to `done` except through Final Auditor release path (`release/` on disk + `studio handoff --after final_audit`).
5. **Studio CLI preference**: use `studio.py` helpers (`pack`, `handoff`, `watchdog`, `verify-done`, `create-issue`, `reassign`, `reopen-parent`). On CLI failure: comment error → mark `blocked` → EXIT. Do **not** create a raw `curl` workaround issue.
6. **If assigned issue already done**: EXIT immediately — no zombie continuation.

## Metrics + postmortem
Maintain `00_admin/EXPERIMENT_METRICS.md` during the run and `00_admin/PILOT_POSTMORTEM.md` at the end.
