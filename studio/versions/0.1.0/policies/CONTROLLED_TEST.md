# Controlled Test (studio policy)

When a book's `book.yaml` sets `controlled_test: true`:

1. Do not change workflow/instructions/gates mid-run unless execution is completely blocked.
2. Log non-blocking defects; remediate after the run.
3. Separate drafting (MiMo / `studio-drafter`) from craft review (DeepSeek Flash / `studio-coordinator`).
4. Short-story early reader after opening scene (never later than scene 2).
5. Preserve all evidence; write experiment metrics + postmortem.
6. **Board ask ban**: never call `request_confirmation` for stage continuation, creative decisions, or pipeline gates. The board is observational — not a co-pilot.
7. **No pipeline parking**: every open issue must have a concrete assignee + next-action comment. Never leave issues in `todo`/`in_progress` without an owner.
8. **Parent issue discipline**: never PATCH parent to `in_review`; never PATCH parent to `done` except Final Auditor release path; prefer `in_progress` or `blocked` (with real `blockedByIssueIds`).
9. **Studio CLI preference**: use `studio.py` helpers over raw API. On CLI failure: comment error → mark `blocked` → EXIT. Never create a raw `curl` workaround issue.

See templates: `CONTROLLED_TEST.md`, `EXPERIMENT_METRICS.md`, `PILOT_POSTMORTEM.md`.
