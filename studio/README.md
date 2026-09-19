# Studio kit (recreate guide)

This directory is the **harness-agnostic** recreate kit for Ghost in the Manuscript.

It is meant for learning and porting: roles, stage gates, templates, and CLI tools.
It is **not** a turnkey deployment for any specific orchestration product.

## What this kit contains

| Path | Purpose |
|---|---|
| `versions/<x.y.z>/agents/` | Role instructions (mission, tools, heartbeat, soul) |
| `versions/<x.y.z>/templates/` | Planning + manuscript artifact templates |
| `versions/<x.y.z>/workflows/` | Stages + length profiles |
| `versions/<x.y.z>/policies/` | Shared constitution / policy |
| `versions/<x.y.z>/schemas/` | Optional structured contracts |
| `../tools/` | CLI: pack, verify-done, handoff, git-sync, craft lint, start-book |
| `../tests/` | Offline smoke tests (no live board required) |
| `../books/` | Creative artifacts + registry (library output) |

## Design principles

1. **One primary tool call per assignment** — creative roles `pack` once; coordinators use `watchdog` / `git-sync`.
2. **Files on disk are deliverables** — chat text is not.
3. **Length profiles** — short story / novelette / novella / novel set scene floors.
4. **Craft gates** — mechanical lint before semantic craft audit for scenes.
5. **No harness names in kit docs** — wire your orchestrator via environment variables.

## Environment (required for board-aware CLI)

Copy [`.env.example`](../.env.example) and export before using board mutations:

- `STUDIO_API_URL` — board/orchestration API base
- `STUDIO_BOARD_TOKEN` — auth token
- `STUDIO_COMPANY_ID` — org/company id
- `STUDIO_PROJECTS_ROOT` — host path to project workspaces
- `STUDIO_WORKSPACE_ABS_TEMPLATE` — absolute workspace pattern agents write to
- `STUDIO_CLI` — how agents should invoke the CLI (default `python3 tools/studio.py`)

Offline commands (`profiles`, `works`, `craft_lint`, most of `verify-done`) work without a board.

## Start a new book (one command)

```bash
python3 tools/studio.py start-book \
  --title "The Last Box" \
  --prompt-file /path/to/prompt.txt \
  --format short_story \
  --assign-intake
```

What it does:

1. Creates the board project
2. Seeds the project `_default` workspace from studio templates
3. Writes profile-aware `00_admin/book.yaml` (+ pilot files when controlled)
4. Creates the parent BOOK issue assigned to Managing Editor
5. Optionally creates an Intake child (`--assign-intake`) and/or wakes ME (`--wake`)
6. Registers `books/<slug>/` + `books/registry.yaml` (skip with `--no-git`)

Useful flags:

- `--dry-run` — print the plan only
- `--controlled-test` / `--no-controlled-test`
- `--target-words 4500`
- `--slug the-last-box`
- `--no-push` — commit registry locally without remote push
- `--format novelette|novella|novel` — non-short defaults

Short stories default to `controlled_test: true` unless `--no-controlled-test`.

## Typical agent lanes

```text
Creative / review / planning
  tools/studio.py pack --slug <book> --role <role> --work <work> [--unit SCENE-N]
  → write deliverable → verify-done → mark done → exit

Coordinator (timer)
  tools/studio.py watchdog --slug <book>
  → at most one mutation → exit

Librarian / sync
  tools/studio.py git-sync --slug <book> --message '...'
  → exit only if push confirmed
```

List work modes: `python3 tools/studio.py works`

## Porting to another harness

1. Pin a studio version in `studio/current.yaml` and each book's `book.yaml`.
2. Map roles to your agents; keep one prose writer and one stage owner.
3. Mount/copy `tools/` into the agent environment.
4. Expand `STUDIO_CLI` + workspace template into runtime instructions if your agents need absolute paths.
5. Keep secrets in your host secret store — never in git.

## Controlled short-story pilot

First observable test profile (`LENGTH_PROFILES.yaml` → `short_story`):

- 4,000–5,000 words; ~4–6 scenes; one conflict; minimal cast/locations
- Draft = MiMo; craft audit = DeepSeek Flash (no drafter self-eval in the pack)
- Early target-reader after opening scene (≤ scene 2)
- Templates: `EXPERIMENT_METRICS.md`, `PILOT_POSTMORTEM.md`, `CONTROLLED_TEST.md`
- Freeze workflow once the run starts; preserve failed artifacts

## Fiction policy

Primary scope is original fiction. PG-13 / non-graphic defaults unless a book's brief sets other bounds.
