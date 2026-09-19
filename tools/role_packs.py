#!/usr/bin/env python3
"""Role/job pack matrix for Ghost in the Manuscript.

Goal: one primary tool call per assignment.
  - Creative roles: studio pack --role X [--work W] [--unit SCENE-N]
  - Managing Editor timer: studio watchdog
  - Studio Administrator sync: studio git-sync

Placeholders in file templates:
  {unit}      SCENE-013
  {prev}      SCENE-012
  {prev2}     SCENE-011
  {next}      SCENE-014
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# work keys also used by studio create-issue --work
WORK_ALIASES = {
    "draft": "draft",
    "redraft": "draft",
    "revision_prose": "draft",
    "craft_audit": "craft_audit",
    "developmental_review": "craft_audit",
    "continuity": "continuity",
    "target_reader": "target_reader",
    "scene_outline": "scene_outline",
    "scene_contract": "scene_outline",
    "premise": "premise",
    "creative_brief": "creative_brief",
    "story_bible": "story_bible",
    "beat_sheet": "beat_sheet",
    "ending": "story_bible",
    "revision": "revision",
    "line_edit": "line_edit",
    "final_audit": "release",
    "release": "release",
    "research": "research",
    "git_sync": "git_sync",
    "intake": "intake",
    "stage_advance": "stage_advance",
}

# Default work when only --role is given
DEFAULT_WORK_BY_ROLE = {
    "drafting_author": "draft",
    "developmental_reviewer": "craft_audit",
    "continuity_reviewer": "continuity",
    "target_reader_reviewer": "target_reader",
    "scene_planner": "scene_outline",
    "story_architect": "story_bible",
    "revision_editor": "revision",
    "line_editor": "line_edit",
    "final_auditor": "release",
    "research_specialist": "research",
    "studio_administrator": "git_sync",
    "managing_editor": "stage_advance",
}

# Primary command the agent should run first for this work
PRIMARY_CALL_BY_WORK = {
    "stage_advance": "watchdog",  # ME timer / board ops
    "git_sync": "git-sync",
    # everything else: pack
}

# Required markdown H2 sections that must be non-empty before verify-done PASS.
REQUIRED_SECTIONS_BY_REL = {
    "development/CREATIVE_BRIEF.md": [
        "One-sentence concept",
        "Format and target length",
        "Audience",
        "Genre and story promise",
        "Tone and emotional experience",
        "POV and tense",
        "Required elements",
        "Forbidden elements",
    ],
    "development/PREMISE_PACKAGE.md": [
        "Logline",
        "Short pitch",
        "Central dramatic question",
    ],
    "00_admin/REQUIREMENTS_LEDGER.md": [
        "Requirements",
    ],
}


def required_sections_for_rel(rel: Optional[str]) -> List[str]:
    if not rel:
        return []
    norm = rel.replace("\\", "/").lstrip("./")
    if norm in REQUIRED_SECTIONS_BY_REL:
        return list(REQUIRED_SECTIONS_BY_REL[norm])
    base = norm.split("/")[-1]
    for key, sections in REQUIRED_SECTIONS_BY_REL.items():
        if key.endswith("/" + base) or key.endswith(base):
            return list(sections)
    return []


def empty_required_sections(text: str, sections: List[str]) -> List[str]:
    """Return section titles whose H2 body is missing or whitespace-only."""
    empty: List[str] = []
    for section in sections:
        m = re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", text)
        if not m:
            empty.append(section)
            continue
        start = m.end()
        nxt = re.search(r"(?m)^##\s+", text[start:])
        end = start + nxt.start() if nxt else len(text)
        body = text[start:end]
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
        if not body:
            empty.append(section)
    return empty

# Slim file lists per work mode. Keep tight — writing time > reading time.
WORK_PACKS: Dict[str, Dict[str, Any]] = {
    "intake": {
        "roles": ["managing_editor"],
        "needs_unit": False,
        "deliverable": "00_admin/REQUIREMENTS_LEDGER.md",
        "also_write": [
            "00_admin/PROJECT_MANIFEST.md",
            "00_admin/book.yaml",
            "00_admin/CURRENT_STAGE.md",
            "00_admin/DECISION_LOG.md",
        ],
        "files": [
            "00_admin/ORIGINAL_PROMPT.md",
            "00_admin/book.yaml",
            "00_admin/PROJECT_MANIFEST.md",
            "00_admin/CURRENT_STAGE.md",
        ],
        "done_gate": "verify-done",
        "mission": "Preserve prompt; extract requirements; set length profile in book.yaml; leave parent in_progress.",
    },
    "creative_brief": {
        "roles": ["story_architect", "managing_editor"],
        "needs_unit": False,
        "deliverable": "development/CREATIVE_BRIEF.md",
        "files": [
            "00_admin/ORIGINAL_PROMPT.md",
            "00_admin/REQUIREMENTS_LEDGER.md",
            "00_admin/book.yaml",
            "00_admin/CURRENT_STAGE.md",
            "development/CREATIVE_BRIEF.md",
        ],
        "done_gate": "verify-done",
        "mission": (
            "Write Creative Brief matching requirements + chosen length profile. "
            "MANDATORY CHECKLIST before accept: "
            "(1) unspoken event class locked in ONE sentence — OR Decision Log defers with single candidate + reason; "
            "(2) the box is framed as catalyst/pressure source, NOT puzzle inventory or MacGuffin. "
            "If either check fails: REJECT with structured Revision Brief."
        ),
    },
    "premise": {
        "roles": ["story_architect"],
        "needs_unit": False,
        "deliverable": "development/PREMISE_PACKAGE.md",
        "files": [
            "00_admin/ORIGINAL_PROMPT.md",
            "00_admin/REQUIREMENTS_LEDGER.md",
            "00_admin/book.yaml",
            "development/CREATIVE_BRIEF.md",
            "development/PREMISE_PACKAGE.md",
            "revisions/REVISION_BRIEF_PREMISE.md",
        ],
        "done_gate": "verify-done",
        "mission": "Write Premise Package from approved Creative Brief. No manuscript prose.",
    },
    "story_bible": {
        "roles": ["story_architect"],
        "needs_unit": False,
        "deliverable": "bible/STORY_BIBLE.md",
        "also_write": ["bible/ENDING_DESIGN.md", "bible/STYLE_GUIDE.md", "bible/STORY_BIBLE_SLIM.md"],
        "files": [
            "00_admin/book.yaml",
            "00_admin/REQUIREMENTS_LEDGER.md",
            "development/CREATIVE_BRIEF.md",
            "development/PREMISE_PACKAGE.md",
            "bible/STORY_BIBLE.md",
            "bible/ENDING_DESIGN.md",
            "bible/STYLE_GUIDE.md",
            "revisions/REVISION_BRIEF_STORY_BIBLE.md",
        ],
        "done_gate": "verify-done",
        "mission": "Write Story Bible + Ending Design (+ Style Guide / slim bible if assigned). No prose.",
    },
    "beat_sheet": {
        "roles": ["story_architect"],
        "needs_unit": False,
        "deliverable": "structure/BEAT_SHEET.md",
        "files": [
            "00_admin/book.yaml",
            "development/CREATIVE_BRIEF.md",
            "development/PREMISE_PACKAGE.md",
            "bible/STORY_BIBLE.md",
            "bible/ENDING_DESIGN.md",
            "structure/BEAT_SHEET.md",
            "revisions/REVISION_BRIEF_BEAT_SHEET.md",
        ],
        "done_gate": "verify-done",
        "mission": "Write Save-the-Cat Beat Sheet with causality. Fit length profile.",
    },
    "scene_outline": {
        "roles": ["scene_planner"],
        "needs_unit": False,
        "deliverable": "outline/SCENE_OUTLINE.md",
        "also_write": ["outline/scenes/SCENE-*.md"],
        "files": [
            "00_admin/book.yaml",
            "bible/STORY_BIBLE.md",
            "bible/ENDING_DESIGN.md",
            "structure/BEAT_SHEET.md",
            "outline/SCENE_OUTLINE.md",
            "revisions/REVISION_BRIEF_SCENE_OUTLINE.md",
        ],
        "done_gate": "verify-done",
        "mission": "Write Scene Outline + per-scene contracts under outline/scenes/. No prose.",
    },
    "draft": {
        "roles": ["drafting_author"],
        "needs_unit": True,
        "deliverable": "manuscript/scenes/{unit}.md",
        "files": [
            "bible/STYLE_GUIDE.md",
            "bible/STORY_BIBLE_SLIM.md",
            "00_admin/CURRENT_STAGE.md",
            "outline/scenes/{unit}.md",
            "manuscript/scenes/{prev}.md",
            "revisions/REVISION_BRIEF_{unit}.md",
            "reviews/{unit}_craft_audit.json",
        ],
        "done_gate": "verify-done-scene",
        "mission": "Write ONLY this scene's prose to the deliverable path. Then verify-done.",
    },
    "craft_audit": {
        "roles": ["developmental_reviewer"],
        "needs_unit": True,
        "deliverable": "reviews/{unit}_craft_audit.json",
        "files": [
            "development/CREATIVE_BRIEF.md",
            "bible/STYLE_GUIDE.md",
            "outline/scenes/{unit}.md",
            "manuscript/scenes/{unit}.md",
        ],
        # Explicitly excluded: drafter self-evals, prior craft audits as self-justification,
        # production logs, decision dumps.
        "files_never": [
            "reviews/{unit}_self_eval.md",
            "reviews/{unit}_drafter_notes.md",
        ],
        "done_gate": "craft_audit_json",
        "mission": (
            "Independent craft/dev review. Inputs: Creative Brief, Style Guide, scene contract, draft ONLY. "
            "No drafter self-evaluation. Diagnose only — do not rewrite manuscript prose."
        ),
    },
    "continuity": {
        "roles": ["continuity_reviewer"],
        "needs_unit": True,
        "deliverable": "reviews/{unit}_continuity.md",
        "files": [
            "manuscript/continuity/CONTINUITY_LEDGER.md",
            "bible/STORY_BIBLE.md",
            "outline/scenes/{unit}.md",
            "manuscript/scenes/{unit}.md",
            "manuscript/scenes/{prev}.md",
        ],
        "done_gate": "verify-done",
        "mission": "Audit unit vs canon + ledger. Write continuity review. Do not rewrite prose.",
    },
    "target_reader": {
        "roles": ["target_reader_reviewer"],
        "needs_unit": True,
        "deliverable": "reviews/{unit}_target_reader.md",
        "also_write": ["reviews/EARLY_READER_CHECKPOINT.md"],
        "files": [
            "development/CREATIVE_BRIEF.md",
            "bible/STYLE_GUIDE.md",
            "outline/scenes/{unit}.md",
            "manuscript/scenes/{unit}.md",
            "manuscript/scenes/{prev}.md",
            "00_admin/book.yaml",
        ],
        "done_gate": "verify-done",
        "mission": (
            "Audience checkpoint. For short-story early gate after opening (≤ scene 2): "
            "verdict must be continue | revise_opening | re_outline | stop_project. "
            "Diagnose only — no prose rewrite."
        ),
    },
    "revision": {
        "roles": ["revision_editor", "drafting_author"],
        "needs_unit": False,
        "deliverable": "manuscript/scenes/{unit}.md",  # in-place when unit set; else brief names target
        "files": [
            "00_admin/CURRENT_STAGE.md",
            "revisions/REVISION_BRIEF_{unit}.md",
            "revisions/REVISION_BRIEF_SCENE_OUTLINE.md",
            "revisions/REVISION_BRIEF_STORY_BIBLE.md",
            "revisions/REVISION_BRIEF_BEAT_SHEET.md",
            "revisions/REVISION_BRIEF_PREMISE.md",
            "bible/STORY_BIBLE.md",
            "bible/STYLE_GUIDE.md",
            "outline/scenes/{unit}.md",
            "manuscript/scenes/{unit}.md",
            "structure/BEAT_SHEET.md",
            "outline/SCENE_OUTLINE.md",
        ],
        "done_gate": "verify-done",
        "mission": "Apply ONLY the approved Revision Brief. Prefer updating the same artifact path. Log changes under revisions/.",
    },
    "line_edit": {
        "roles": ["line_editor"],
        "needs_unit": False,
        "deliverable": "manuscript/scenes/{unit}.md",
        "also_write": ["revisions/LINE_EDIT_LOG.md"],
        "files": [
            "bible/STYLE_GUIDE.md",
            "00_admin/CURRENT_STAGE.md",
            "manuscript/scenes/{unit}.md",
            "manuscript/scenes/{prev}.md",
            "revisions/LINE_EDIT_LOG.md",
        ],
        "done_gate": "verify-done",
        "mission": "Line-edit assigned material for clarity/rhythm. Do not change plot/canon outcomes.",
    },
    "release": {
        "roles": ["final_auditor"],
        "needs_unit": False,
        "deliverable": "release/RELEASE_AUDIT.md",
        "also_write": ["release/COMPILATION_MANIFEST.md"],
        "files": [
            "00_admin/ORIGINAL_PROMPT.md",
            "00_admin/REQUIREMENTS_LEDGER.md",
            "00_admin/book.yaml",
            "development/CREATIVE_BRIEF.md",
            "bible/ENDING_DESIGN.md",
            "structure/BEAT_SHEET.md",
            "outline/SCENE_OUTLINE.md",
            "manuscript/continuity/CONTINUITY_LEDGER.md",
            "release/COMPILATION_MANIFEST.md",
            "release/RELEASE_AUDIT.md",
        ],
        "done_gate": "verify-done",
        "mission": "Full release audit. PASS only if criteria met; write RELEASE_AUDIT.md.",
    },
    "research": {
        "roles": ["research_specialist"],
        "needs_unit": False,
        "deliverable": "research/{unit}/NOTES.md",
        "files": [
            "00_admin/CURRENT_STAGE.md",
            "development/CREATIVE_BRIEF.md",
            "bible/STORY_BIBLE.md",
            "outline/scenes/{unit}.md",
            "research/{unit}/NOTES.md",
            "research/{unit}.md",
        ],
        "done_gate": "verify-done",
        "mission": "Story-relevant research notes only. Cite sources; mark uncertainty.",
    },
    "git_sync": {
        "roles": ["studio_administrator"],
        "needs_unit": False,
        "deliverable": None,
        "primary_command": "git-sync",
        "files": [
            "00_admin/book.yaml",
            "00_admin/CURRENT_STAGE.md",
        ],
        "done_gate": "git-sync-exit-0",
        "mission": "Run studio git-sync. Mirror only. Done only if push_confirmed.",
    },
    "stage_advance": {
        "roles": ["managing_editor"],
        "needs_unit": False,
        "deliverable": None,
        "primary_command": "watchdog",
        "files": [
            "00_admin/CURRENT_STAGE.md",
            "00_admin/book.yaml",
            "00_admin/DECISION_LOG.md",
            "00_admin/PROJECT_MANIFEST.md",
        ],
        "done_gate": "handoff-or-exit",
        "mission": "Timer: watchdog → ≤1 mutation → EXIT. Assignment: handoff / create-issue. NEVER write manuscript prose.",
    },
}


def normalize_work(work: Optional[str], role_key: str) -> str:
    if work:
        key = work.strip().lower().replace("-", "_").replace(" ", "_")
        key = WORK_ALIASES.get(key, key)
        if key not in WORK_PACKS:
            raise ValueError(f"Unknown work '{work}'. Valid: {sorted(WORK_PACKS)}")
        return key
    return DEFAULT_WORK_BY_ROLE.get(role_key, "draft")


def _scene_num(unit: Optional[str]) -> Optional[int]:
    if not unit:
        return None
    m = re.match(r"^SCENE-(\d+)$", unit.upper())
    return int(m.group(1)) if m else None


def _format_scene(n: int) -> str:
    return f"SCENE-{n:03d}"


def expand_placeholders(template: str, unit: Optional[str]) -> Optional[str]:
    """Return None if template needs a missing unit/prev."""
    n = _scene_num(unit)
    u = unit.upper() if unit else ""
    prev = _format_scene(n - 1) if n and n - 1 >= 1 else ""
    prev2 = _format_scene(n - 2) if n and n - 2 >= 1 else ""
    nxt = _format_scene(n + 1) if n else ""

    needs = set(re.findall(r"\{(unit|prev|prev2|next)\}", template))
    if "unit" in needs and not u:
        return None
    if "prev" in needs and not prev:
        return None
    if "prev2" in needs and not prev2:
        return None
    if "next" in needs and not nxt:
        return None
    return (
        template.replace("{unit}", u)
        .replace("{prev}", prev)
        .replace("{prev2}", prev2)
        .replace("{next}", nxt)
    )


def pack_paths(role_key: str, work: Optional[str], unit: Optional[str]) -> Tuple[str, List[str], Dict[str, Any]]:
    """Return (work_key, relative paths, work_spec)."""
    work_key = normalize_work(work, role_key)
    spec = WORK_PACKS[work_key]
    paths: List[str] = []
    for tmpl in spec.get("files") or []:
        expanded = expand_placeholders(tmpl, unit)
        if expanded:
            paths.append(expanded)
    # de-dupe preserve order
    seen = set()
    out: List[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return work_key, out, spec


def _cli() -> str:
    import os
    from pathlib import Path

    explicit = (os.environ.get("STUDIO_CLI") or "").strip()
    if explicit:
        return explicit
    for cand in (
        Path(__file__).resolve().parent / "studio.py",
    ):
        if cand.is_file():
            return f"python3 {cand}"
    return "python3 tools/studio.py"


def job_card(
    role_key: str,
    work: Optional[str],
    unit: Optional[str],
    abs_ws: str,
    book: Dict[str, Any],
    *,
    min_words: int = 800,
) -> Dict[str, Any]:
    work_key, _paths, spec = pack_paths(role_key, work, unit)
    title = book.get("working_title") or book.get("book_slug")
    u = (unit or "UNIT").upper()

    deliverable_rel = expand_placeholders(spec.get("deliverable") or "", unit) if spec.get("deliverable") else None
    # Special-cases when unit missing for line_edit/research etc.
    if spec.get("deliverable") and deliverable_rel is None and "{unit}" in (spec.get("deliverable") or ""):
        deliverable_rel = None

    deliverable = f"{abs_ws}/{deliverable_rel}" if deliverable_rel else None
    also = []
    for tmpl in spec.get("also_write") or []:
        exp = expand_placeholders(tmpl, unit)
        if exp and "*" not in exp:
            also.append(f"{abs_ws}/{exp}")
        elif tmpl:
            also.append(tmpl if tmpl.startswith("outline/") else f"{abs_ws}/{tmpl}" if not tmpl.startswith("/") else tmpl)

    primary = spec.get("primary_command") or PRIMARY_CALL_BY_WORK.get(work_key) or "pack"
    done_kind = spec.get("done_gate")
    done_gate = None
    if done_kind == "verify-done-scene" and deliverable:
        done_gate = (
            _cli() + " verify-done "
            f"--path {deliverable} --min-words {min_words}"
            "  # Stage-1 craft_lint auto-runs for manuscript/scenes"
        )
    elif done_kind == "verify-done" and deliverable:
        done_gate = (
            _cli() + " verify-done "
            f"--path {deliverable} --write-root {abs_ws.rstrip('/')}"
        )
    elif done_kind == "craft_audit_json" and deliverable:
        done_gate = (
            f"Write STRICT JSON to {deliverable} with verdict PASS|REVISE, "
            "2–5 direct quotations, reader_effect + minimum_correction per finding, "
            "desire_to_continue score. No rewritten manuscript prose."
        )
    elif done_kind == "git-sync-exit-0":
        slug = book.get("book_slug") or "<slug>"
        done_gate = (
            f"{_cli()} git-sync --slug {slug} "
            f"--message '{title}: sync after {u}'"
        )
    elif done_kind == "handoff-or-exit":
        done_gate = (
            "Timer: studio watchdog --slug <slug> then ≤1 mutation then EXIT. "
            "Assignment: studio handoff --slug <slug> --after <UNIT> --next-unit <NEXT>"
        )

    hard = [
        "Prefer the primary_command below. Do not hunt files with glob/read when pack already included them.",
        "Never read/write company workspace templates: BOOK_TEMPLATE*, BOOK_TEMPLATE_OLD_LEGACY*, shared template workspace/...",
        "Never use empty SOURCE_LEDGER.csv under company workspace — use manuscript/continuity/CONTINUITY_LEDGER.md.",
        "Chat text is not a deliverable — files on disk are.",
    ]
    if role_key == "managing_editor":
        hard.append("NEVER write manuscript prose. Assign drafting_author.")
    if role_key == "studio_administrator":
        hard.append("Mirror only. Sync is NOT done unless push succeeds.")

    write_root = abs_ws.rstrip("/")
    req_sections = required_sections_for_rel(deliverable_rel)
    write_plan = []
    if deliverable and deliverable_rel:
        write_plan.append(
            {
                "path": deliverable,
                "rel": deliverable_rel,
                "purpose": "primary_deliverable",
                "min_words": min_words if done_kind in ("verify-done-scene",) else (80 if req_sections else 1),
                "required_sections": req_sections,
            }
        )
    for pth in also:
        if not pth or "*" in pth:
            continue
        rel = pth[len(write_root) + 1 :] if pth.startswith(write_root + "/") else pth
        write_plan.append(
            {
                "path": pth,
                "rel": rel,
                "purpose": "also_write",
                "min_words": 1,
                "required_sections": required_sections_for_rel(rel),
            }
        )

    controlled = bool(book.get("controlled_test"))
    board_policy = {
        "controlled_test": controlled,
        "allow_board_approval": (not controlled),
        "rule": (
            "controlled_test: do not request board approval / ask_user_questions except explicit stop_project gates"
            if controlled
            else "board approval allowed only when the issue explicitly requires it"
        ),
    }

    done_gate_obj = {
        "kind": done_kind,
        "command": done_gate,
        "require_path_prefix": write_root,
        "reject_if_sections_empty": req_sections,
        "min_words": (
            min_words
            if done_kind == "verify-done-scene"
            else (80 if (done_kind == "verify-done" and req_sections) else None)
        ),
    }

    hard = list(hard)
    hard.append(f"Write ONLY under write_root: {write_root}")
    hard.append("Forbidden write roots: /tmp/** , any repos checkout mirror, doubled company-id project paths.")
    if controlled:
        hard.append(board_policy["rule"])

    return {
        "role": role_key,
        "work": work_key,
        "display_name": role_key,
        "book_title": title,
        "unit": unit,
        "mission": spec.get("mission"),
        "primary_command": primary,
        "deliverable_path": deliverable,
        "also_write": also,
        "write_root": write_root,
        "write_plan": write_plan,
        "done_gate": done_gate_obj,
        "done_gate_command": done_gate,
        "board_policy": board_policy,
        "hard_rules": hard,
        "how_to_use_this_pack": (
            "1) Runtime must already provide STUDIO_*; env_exports is diagnostic/echo only. "
            "2) If primary_command is watchdog or git-sync, run THAT first (pack is optional context). "
            "3) Otherwise call studio pack once, then use files[].content. "
            "4) Write only write_plan paths under write_root (never /tmp or repos checkout). "
            "5) Run done_gate.command / done_gate_command, PATCH done only on exit 0, EXIT."
        ),
        "valid_work_for_role": sorted(
            k for k, v in WORK_PACKS.items() if role_key in (v.get("roles") or []) or role_key == "managing_editor"
        ),
    }


def list_work_modes() -> List[Dict[str, Any]]:
    rows = []
    for key, spec in WORK_PACKS.items():
        rows.append(
            {
                "work": key,
                "roles": spec.get("roles"),
                "needs_unit": bool(spec.get("needs_unit")),
                "primary_command": spec.get("primary_command") or PRIMARY_CALL_BY_WORK.get(key) or "pack",
                "deliverable": spec.get("deliverable"),
                "mission": spec.get("mission"),
            }
        )
    return rows
