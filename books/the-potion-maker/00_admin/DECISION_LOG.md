---
schema_version: "0.1.0"
artifact_id: "decision-log"
title: "Decision Log"
status: "APPROVED"
version: 2
canonical: true
authoring_agent: "managing_editor"
created_at: "2026-09-19"
approved_by: "managing_editor"
approved_at: "2026-09-19"
depends_on: []
book_id: "df9327a5-892d-42c7-ad5a-8340585034c1"
project_id: "5626ae22-e62c-452b-97c9-3e03186e4439"
---

# Decision Log

## DEC-001
- Date / stage: 2026-09-19 / intake
- Proposed change: Select short_story profile for controlled pilot
- Approving authority: Managing Editor
- Reason: User prompt specifies 4000-5000 words, 4-6 scenes, complete short story. Pilot profile matches exactly.
- Alternatives rejected: novel/novella profile (wrong scope for prompt)
- Affected artifacts: book.yaml, PROJECT_MANIFEST.md
- Downstream invalidation / regeneration: none

## DEC-002
- Date / stage: 2026-09-19 / intake
- Proposed change: Enable controlled_test mode
- Approving authority: Managing Editor
- Reason: Book is a controlled short-story pilot per project mandate.
- Alternatives rejected: standard workflow (not a pilot)
- Affected artifacts: book.yaml, CONTROLLED_TEST.md
- Downstream invalidation / regeneration: none

## DEC-003
- Date / stage: 2026-09-19 / intake
- Proposed change: Lock original prompt as canonical
- Approving authority: Managing Editor
- Reason: Prompt preserved verbatim per intake duties. Status set to LOCKED.
- Alternatives rejected: none
- Affected artifacts: ORIGINAL_PROMPT.md
- Downstream invalidation / regeneration: none
