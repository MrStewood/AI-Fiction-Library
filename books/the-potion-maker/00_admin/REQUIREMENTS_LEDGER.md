---
schema_version: "0.1.0"
artifact_id: "requirements-ledger"
title: "Requirements Ledger"
status: "APPROVED"
version: 1
canonical: true
authoring_agent: "managing_editor"
created_at: "2026-09-19"
approved_by: "managing_editor"
approved_at: "2026-09-19"
depends_on: ["original-prompt"]
book_id: "df9327a5-892d-42c7-ad5a-8340585034c1"
project_id: "5626ae22-e62c-452b-97c9-3e03186e4439"
---

# Requirements Ledger

## Requirements

| ID | Requirement | Source | Priority | Verification | Status |
|---|---|---|---|---|---|
| REQ-001 | Original fantasy short story: 4000-5000 words, 4-6 scenes, complete story (not outline) | explicit prompt | mandatory | word count gate + scene count check at release | open |
| REQ-002 | Premise: potion-maker crafts emotion potions; customer seeks to forget grief; potion requires surrendering the emotion; grief is all they have left of a loved one | explicit prompt | mandatory | premise/package review | open |
| REQ-003 | One central conflict only: whether and how they decide what to keep and what to let go | explicit prompt | mandatory | beat sheet + scene outline review | open |
| REQ-004 | Exactly two speaking characters (potion maker + customer). No new major characters. | explicit prompt | mandatory | cast check at scene outline | open |
| REQ-005 | At most two locations (potion shop + one other). Prefer mostly the shop. | explicit prompt | mandatory | scene outline location check | open |
| REQ-006 | Timeline: roughly one evening or a few hours | explicit prompt | mandatory | scene outline timeline check | open |
| REQ-007 | No subplot, romance arc, crime plot, supernatural twist, or institutional conspiracy | explicit prompt | mandatory | brief + outline review | open |
| REQ-008 | Tone: literary fantasy; contemplative but not bleak; PG-13; non-graphic | explicit prompt | mandatory | style guide + craft audit | open |
| REQ-009 | End on a hard character choice with lasting consequence; no neat moral tidy | explicit prompt | mandatory | ending design + final audit | open |
| REQ-010 | Grounded magic system: clear rules, clear costs, no deus ex machina | explicit prompt | mandatory | story bible magic-system section | open |
| REQ-011 | Concrete sensory grounding (smells of potions, textures of ingredients, light in the shop) | explicit prompt | mandatory | craft audit / line edit | open |
| REQ-012 | Dialogue with subtext: deflection, hesitation, things unsaid | explicit prompt | mandatory | craft audit | open |
| REQ-013 | Clear goal / opposition / agency for protagonist in each scene | explicit prompt | mandatory | beat sheet + scene outline | open |
| REQ-014 | Causal scene-to-scene pressure driving reader to next scene | explicit prompt | mandatory | beat sheet + scene outline | open |
| REQ-015 | Controlled pilot profile: 4-5k words, 4-6 scenes, one conflict, minimal cast/locations | controlled_test policy | mandatory | book.yaml profile check | open |
| REQ-016 | Drafting model MiMo (studio-drafter); craft review model DeepSeek Flash (studio-coordinator) | controlled_test policy | mandatory | adapter config check | open |
| REQ-017 | Early target-reader checkpoint after opening scene (after SCENE-001, before SCENE-003) | controlled_test policy | mandatory | scene outline + workflow check | open |
| REQ-018 | Preserve all drafts, failed reviews, revision directives, rejected artifacts | controlled_test policy | mandatory | file-system audit at release | open |
| REQ-019 | Maintain EXPERIMENT_METRICS.md during run; write PILOT_POSTMORTEM.md at end | controlled_test policy | mandatory | file existence check | open |
| REQ-020 | Board is observational in controlled test; no request_confirmation for stage continuation | controlled_test policy | mandatory | issue-thread audit | open |

## Assumptions

- Short-story pilot profile freezes workflow once run starts.
- Only the Final Auditor release path may mark the parent BOOK issue done.
- One central conflict; no subplot unless essential.
- Literary fantasy audience; general adult / YA crossover appropriate.
- Magic system costs are emotional and existential, not physical violence.
- The potion shop is the primary location; at most one secondary setting.
