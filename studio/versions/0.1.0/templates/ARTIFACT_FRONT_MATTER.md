# Artifact front matter convention (MVP)

Put YAML front matter at the top of every durable artifact:

```yaml
---
schema_version: "0.1.0"
artifact_id: "creative-brief"
title: "Creative Brief"
status: "PROPOSED"  # PROPOSED | IN_REVIEW | REVISION_REQUIRED | APPROVED | LOCKED | STALE | SUPERSEDED | REJECTED
version: 1
canonical: false
authoring_agent: "managing_editor"
created_at: "YYYY-MM-DD"
approved_by: null
approved_at: null
depends_on: []
book_id: "REPLACE"
project_id: "REPLACE"
---
```

Only Managing Editor may set APPROVED, LOCKED, or REJECTED.
