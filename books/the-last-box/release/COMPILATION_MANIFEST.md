---
schema_version: "0.1.0"
artifact_id: "compilation-manifest"
title: "Compilation Manifest"
status: "PROPOSED"
version: 1
canonical: false
authoring_agent: "final_auditor"
created_at: "2026-09-18"
approved_by: null
approved_at: null
depends_on: []
book_id: "2e64d4cf-7b56-42f2-9aaa-6934fe48dd0d"
project_id: "51909d1d-2f17-4748-bc81-a9641f41a640"
---

# Compilation Manifest

Assemble approved manuscript units in this exact order.

| Order | Path | Title | Artifact version | Include |
|---:|---|---|---:|---|
| 1 | manuscript/chapters/001-....md |  | 1 | yes |

## Separators / heading rules
- Chapter heading:
- Scene break:

## Word-count method
Split on whitespace; count tokens in compiled Markdown body excluding YAML front matter and HTML comments.
