---
schema_version: "0.1.0"
artifact_id: "experiment-metrics"
title: "Experiment Metrics"
status: "PROPOSED"
version: 1
canonical: false
authoring_agent: "managing_editor"
created_at: "2026-09-18"
approved_by: null
approved_at: null
depends_on: []
book_id: "cd35e42f-5e5d-4046-b80b-e8780a33fb20"
project_id: "46fa8bdb-1307-4083-85a7-ea26cb13144e"
pilot_profile: "short_story"
---

# Experiment Metrics

Fill during the controlled short-story pilot. Do not delete rows after a failed run.

## Run identity
- Book slug: the-last-box
- Start (UTC):
- End (UTC):
- Studio version: 0.1.0
- Controlled-test freeze? yes

## Throughput
| Metric | Value |
|---|---:|
| Agent runs (total wake/completions) |  |
| Redrafts per scene (list SCENE-XXX: n) |  |
| Failed gates (count) |  |
| Final word count |  |
| Total generated words (all drafts) |  |
| Accepted words (final manuscript) |  |

## Elapsed time per stage (minutes)
| Stage | Minutes | Notes |
|---|---:|---|
| Intake / brief |  |  |
| Premise / bible / beats / outline |  |  |
| Drafting (all scenes) |  |  |
| Craft audits |  |  |
| Early reader checkpoint |  |  |
| Continuity / other reviews |  |  |
| Revision / line edit |  |  |
| Final audit / release |  |  |
| Wall-clock total |  |  |

## Gate log
| Unit | Gate | Result | Reason (short) | Desire-to-continue |
|---|---|---|---|---:|
| SCENE-001 | craft_lint |  |  |  |
| SCENE-001 | craft_audit | PASS/REVISE |  |  |
| SCENE-001 | early_reader | continue/revise_opening/re_outline/stop_project |  |  |

## Reviewer findings disposition
| Finding id / quote | Accepted / Rejected | Human note |
|---|---|---|
|  |  |  |

## Desire-to-continue scores
| Checkpoint | Score (1–5) |
|---|---:|
| Craft audit SCENE-001 |  |
| Early reader |  |
| Craft audit SCENE-00N |  |
| End target-reader (if any) |  |

## Human ratings (after read; 1–5)
| Dimension | Score | Notes |
|---|---:|---|
| Plot |  |  |
| Prose |  |  |
| Character |  |  |
| Emotional effect |  |  |
| Ending |  |  |

## Preservation checklist
- [ ] All drafts retained under `manuscript/` and/or `revisions/`
- [ ] Failed craft audits retained under `reviews/`
- [ ] Revision directives retained
- [ ] Rejected artifacts retained (do not delete the pilot on failure)
- [ ] Postmortem written (`00_admin/PILOT_POSTMORTEM.md`)
