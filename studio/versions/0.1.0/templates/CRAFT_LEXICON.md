---
schema_version: "0.1.0"
artifact_id: "craft-lexicon"
title: "Craft Lexicon"
status: "PROPOSED"
version: 1
canonical: false
authoring_agent: "managing_editor"
created_at: "YYYY-MM-DD"
approved_by: null
approved_at: null
depends_on: ["story-bible", "style-guide"]
book_id: "REPLACE"
project_id: "REPLACE"
---

# Craft Lexicon

Optional book-local helper for mechanical craft gates. Shared tools read this file when present.

## Character starters
List first names and surnames that commonly begin sentences in this book's prose.
`craft_lint.py` treats these like pronoun/article starters for inventory-prose detection.

- character_starters: [FirstName, Surname, AnotherName]

## Notes
- Keep this book-specific. Do not put these names into shared studio tools or agent templates.
- Prefer also maintaining POV / Present characters in each scene contract.
