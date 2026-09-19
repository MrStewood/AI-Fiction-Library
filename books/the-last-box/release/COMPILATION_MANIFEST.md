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
book_id: "cd35e42f-5e5d-4046-b80b-e8780a33fb20"
project_id: "46fa8bdb-1307-4083-85a7-ea26cb13144e"
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
