---
schema_version: "0.1.0"
artifact_id: "compilation-manifest"
title: "Compilation Manifest"
status: "PROPOSED"
version: 1
canonical: false
authoring_agent: "final_auditor"
created_at: "YYYY-MM-DD"
approved_by: null
approved_at: null
depends_on: []
book_id: "REPLACE"
project_id: "REPLACE"
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
