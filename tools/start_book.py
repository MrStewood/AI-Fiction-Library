#!/usr/bin/env python3
"""Bootstrap a new book: board project + workspace seed + registry (+ optional Intake).

Used by `studio start-book`. Kept harness-agnostic: secrets/URLs come from env.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from length_profiles import normalize_profile_key, profile_for_key

TEMPLATE_COPIES = {
    "ORIGINAL_PROMPT.md": "00_admin/ORIGINAL_PROMPT.md",
    "PROJECT_MANIFEST.md": "00_admin/PROJECT_MANIFEST.md",
    "REQUIREMENTS_LEDGER.md": "00_admin/REQUIREMENTS_LEDGER.md",
    "DECISION_LOG.md": "00_admin/DECISION_LOG.md",
    "CURRENT_STAGE.md": "00_admin/CURRENT_STAGE.md",
    "CREATIVE_BRIEF.md": "development/CREATIVE_BRIEF.md",
    "PREMISE_PACKAGE.md": "development/PREMISE_PACKAGE.md",
    "STORY_BIBLE.md": "bible/STORY_BIBLE.md",
    "ENDING_DESIGN.md": "bible/ENDING_DESIGN.md",
    "STYLE_GUIDE.md": "bible/STYLE_GUIDE.md",
    "BEAT_SHEET.md": "structure/BEAT_SHEET.md",
    "SCENE_OUTLINE.md": "outline/SCENE_OUTLINE.md",
    "SCENE_CONTRACT.md": "outline/scenes/SCENE-001.md",
    "CONTINUITY_LEDGER.md": "manuscript/continuity/CONTINUITY_LEDGER.md",
    "COMPILATION_MANIFEST.md": "release/COMPILATION_MANIFEST.md",
    "RELEASE_AUDIT.md": "release/RELEASE_AUDIT.md",
}

PILOT_COPIES = {
    "CONTROLLED_TEST.md": "00_admin/CONTROLLED_TEST.md",
    "EXPERIMENT_METRICS.md": "00_admin/EXPERIMENT_METRICS.md",
    "PILOT_POSTMORTEM.md": "00_admin/PILOT_POSTMORTEM.md",
    "EARLY_READER_CHECKPOINT.md": "reviews/EARLY_READER_CHECKPOINT.md",
}

WORKSPACE_DIRS = [
    "00_admin",
    "development",
    "bible",
    "structure",
    "outline/scenes",
    "manuscript/scenes",
    "manuscript/chapters",
    "manuscript/continuity",
    "reviews",
    "revisions",
    "research",
    "release",
]


def slugify(title: str, explicit: Optional[str] = None) -> str:
    if explicit:
        s = explicit.strip().lower()
    else:
        s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:60] or f"book-{uuid.uuid4().hex[:8]}")


def yaml_quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_\-./]+", text):
        return json.dumps(text) if (" " in text or ":" in text) else f'"{text}"'
    return json.dumps(text)


def render_book_yaml(
    *,
    book_id: str,
    title: str,
    slug: str,
    project_id: str,
    profile: Dict[str, Any],
    controlled_test: bool,
    target_words: Optional[int] = None,
) -> str:
    key = profile.get("key") or "novella"
    target = int(target_words if target_words is not None else (profile.get("default_target") or 30000))
    tw_min = profile.get("target_word_min")
    tw_max = profile.get("target_word_max")
    if tw_min is None:
        tw_min = profile.get("word_min")
    if tw_max is None:
        tw_max = profile.get("word_max")
    lines = [
        f'book_id: "{book_id}"',
        f'working_title: {json.dumps(title)}',
        f'format: "{key}"',
        'status: "development"',
        'repository: "https://github.com/MrStewood/AI-Fiction-Library"',
        f'book_root: "books/{slug}"',
        f'project_id: "{project_id}"',
        'studio_version: "0.1.0"',
        f'workflow_profile: "{key}"',
        'default_branch: "main"',
        'current_stage: "intake"',
        "current_approved_commit: null",
        f"target_word_count: {target}",
        f"target_word_min: {tw_min if tw_min is not None else 'null'}",
        f"target_word_max: {tw_max if tw_max is not None else 'null'}",
        f"scene_min_words: {int(profile.get('scene_min_words') or 800)}",
        f"scene_target_words: {int(profile.get('scene_target_words') or 1000)}",
        f"typical_scenes_min: {int(profile.get('typical_scenes_min') or 0)}",
        f"typical_scenes_max: {int(profile.get('typical_scenes_max') or 0)}",
        f"typical_chapters_min: {int(profile.get('typical_chapters_min') or 0)}",
        f"typical_chapters_max: {int(profile.get('typical_chapters_max') or 0)}",
        f"chapters_required: {yaml_quote(bool(profile.get('chapters_required')))}",
        "series: null",
        f"target_reader_cadence: {yaml_quote(profile.get('target_reader_cadence'))}",
        f"early_reader_after_scene: {yaml_quote(profile.get('early_reader_after_scene'))}",
        f"max_cast: {yaml_quote(profile.get('max_cast'))}",
        f"max_locations: {yaml_quote(profile.get('max_locations'))}",
        f"subplots: {yaml_quote(profile.get('subplots'))}",
        f"controlled_test: {yaml_quote(bool(controlled_test))}",
        "",
    ]
    return "\n".join(lines)


def map_template_text(
    text: str,
    *,
    book_id: str,
    project_id: str,
    title: str,
    slug: str,
    profile_key: str,
) -> str:
    today = date.today().isoformat()
    s = text
    replacements = [
        ('book_id: "REPLACE"', f'book_id: "{book_id}"'),
        ('project_id: "REPLACE"', f'project_id: "{project_id}"'),
        ('book_id: "immutable-unique-id"', f'book_id: "{book_id}"'),
        ('project_id: "immutable-board-project-id"', f'project_id: "{project_id}"'),
        ("Working Title", title),
        ("books/example-book", f"books/{slug}"),
        ("YYYY-MM-DD", today),
    ]
    for a, b in replacements:
        s = s.replace(a, b)
    # Soft format hints in templates
    s = s.replace('format: "novella"', f'format: "{profile_key}"')
    s = s.replace('workflow_profile: "novella"', f'workflow_profile: "{profile_key}"')
    s = s.replace("Format: short_story | novelette | novella | novel", f"Format: {profile_key}")
    return s


def template_dir(repo: Path) -> Path:
    return repo / "studio" / "versions" / "0.1.0" / "templates"


def seed_tree(
    dest: Path,
    *,
    repo: Path,
    book_id: str,
    project_id: str,
    title: str,
    slug: str,
    prompt: str,
    profile: Dict[str, Any],
    controlled_test: bool,
    target_words: Optional[int] = None,
) -> List[str]:
    written: List[str] = []
    for d in WORKSPACE_DIRS:
        (dest / d).mkdir(parents=True, exist_ok=True)

    tdir = template_dir(repo)
    copies = dict(TEMPLATE_COPIES)
    if controlled_test:
        copies.update(PILOT_COPIES)

    profile_key = str(profile.get("key") or "novella")
    for src_name, dest_rel in copies.items():
        src = tdir / src_name
        if not src.exists():
            continue
        out = dest / dest_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        text = map_template_text(
            src.read_text(encoding="utf-8"),
            book_id=book_id,
            project_id=project_id,
            title=title,
            slug=slug,
            profile_key=profile_key,
        )
        if src_name == "ORIGINAL_PROMPT.md":
            text = text.replace("PASTE PROMPT HERE", prompt.rstrip())
        if src_name == "CURRENT_STAGE.md":
            text = text.replace("- Stage: intake", "- Stage: intake\n- Notes: seeded by studio start-book")
        if src_name == "EXPERIMENT_METRICS.md":
            text = text.replace("- Book slug:", f"- Book slug: {slug}")
            text = text.replace("- Studio version:", "- Studio version: 0.1.0")
            text = text.replace("- Controlled-test freeze? yes/no", "- Controlled-test freeze? yes")
        out.write_text(text, encoding="utf-8")
        written.append(dest_rel)

    book_yaml = render_book_yaml(
        book_id=book_id,
        title=title,
        slug=slug,
        project_id=project_id,
        profile=profile,
        controlled_test=controlled_test,
        target_words=target_words,
    )
    (dest / "00_admin" / "book.yaml").write_text(book_yaml, encoding="utf-8")
    written.append("00_admin/book.yaml")

    note = f"""# Bootstrap note

- Profile: {profile_key}
- Target words: {target_words or profile.get('default_target')}
- Controlled test: {controlled_test}
- project_id: {project_id}
- book_id: {book_id}
- book_root: books/{slug}/
- Seeded by `studio start-book`
- Do not pre-create the full issue DAG. Managing Editor creates only the next stage.
"""
    (dest / "00_admin" / "README_BOOTSTRAP.md").write_text(note, encoding="utf-8")
    written.append("00_admin/README_BOOTSTRAP.md")
    return written


def append_registry_entry(
    repo: Path,
    *,
    book_id: str,
    title: str,
    slug: str,
    project_id: str,
    profile_key: str,
    controlled_test: bool,
) -> Path:
    registry = repo / "books" / "registry.yaml"
    if not registry.exists():
        registry.write_text(
            '# Authoritative index of book_id ↔ project ↔ book_root.\n'
            'schema_version: "1.0.0"\n'
            "books: []\n",
            encoding="utf-8",
        )
    entry = (
        f'  - book_id: "{book_id}"\n'
        f"    working_title: {json.dumps(title)}\n"
        f'    book_slug: "{slug}"\n'
        f'    book_root: "books/{slug}"\n'
        f'    project_id: "{project_id}"\n'
        f'    format: "{profile_key}"\n'
        f'    workflow_profile: "{profile_key}"\n'
        f"    controlled_test: {'true' if controlled_test else 'false'}\n"
        f'    project_status: "seeded"\n'
        f'    studio_version: "0.1.0"\n'
        f"    series_id: null\n"
        f'    created_date: "{date.today().isoformat()}"\n'
        f"    current_approved_commit: null\n"
    )
    text = registry.read_text(encoding="utf-8")
    if f'book_slug: "{slug}"' in text:
        raise ValueError(f"Slug already registered: {slug}")
    if re.search(rf'project_id:\s*"{re.escape(project_id)}"', text):
        raise ValueError(f"project_id already registered: {project_id}")
    if re.search(r"(?m)^books:\s*\[\s*\]\s*$", text):
        text = re.sub(r"(?m)^books:\s*\[\s*\]\s*$", "books:\n" + entry.rstrip(), text)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += entry
    registry.write_text(text, encoding="utf-8")
    return registry


AGENT_UID = "1000:1000"


def fix_workspace_ownership(cid: str, project_id: str) -> Optional[str]:
    """Agents often run as container user `node`; root-owned trees cause EACCES.

    Host-only: set STUDIO_RUNTIME_CONTAINER and STUDIO_WORKSPACE_ABS_TEMPLATE.
    """
    container = (os.environ.get("STUDIO_RUNTIME_CONTAINER") or "").strip()
    if not container:
        return "chown_skipped:no_STUDIO_RUNTIME_CONTAINER"
    tmpl = (os.environ.get("STUDIO_WORKSPACE_ABS_TEMPLATE") or "").strip()
    projects_root = (os.environ.get("STUDIO_PROJECTS_ROOT") or "").rstrip("/")
    if not tmpl:
        return "chown_skipped:no_STUDIO_WORKSPACE_ABS_TEMPLATE"
    abs_default = tmpl.format(company_id=cid, project_id=project_id, projects_root=projects_root)
    target = str(Path(abs_default).parent)
    try:
        proc = subprocess.run(
            ["docker", "exec", container, "chown", "-R", "node:node", target],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return "chown_ok"
        return f"chown_skipped:{proc.returncode}:{proc.stderr.strip()[:200]}"
    except Exception as e:  # pragma: no cover
        return f"chown_unavailable:{type(e).__name__}"


def fix_book_ownership(repo: Path, slug: str) -> Optional[str]:
    """Chown books/<slug> to agent uid so agents (node, uid 1000) can write.

    Tries direct chown (works if we are root or have permission);
    falls back to docker exec on STUDIO_RUNTIME_CONTAINER.
    """
    book_root = repo / "books" / slug
    if not book_root.exists():
        return "chown_skipped:book_root_missing"
    # Attempt direct chown first (works when running as root or with sudo)
    try:
        proc = subprocess.run(
            ["chown", "-R", AGENT_UID, str(book_root)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return "chown_ok:direct"
        # Permission denied — fall through to docker exec
    except Exception:
        pass  # chown binary missing or not applicable; try docker exec
    container = (os.environ.get("STUDIO_RUNTIME_CONTAINER") or "").strip()
    if not container:
        return "chown_skipped:no_direct_no_STUDIO_RUNTIME_CONTAINER"
    repo_mount = (os.environ.get("STUDIO_REPO") or "/runtime/repos/AI-Fiction-Library").rstrip("/")
    try:
        proc = subprocess.run(
            ["docker", "exec", container, "chown", "-R", "node:node", f"{repo_mount}/books/{slug}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return "chown_ok:docker_exec"
        return f"chown_skipped:{proc.returncode}:{proc.stderr.strip()[:200]}"
    except Exception as e:  # pragma: no cover
        return f"chown_unavailable:{type(e).__name__}"


def git_register(
    repo: Path,
    *,
    book_id: str,
    title: str,
    slug: str,
    project_id: str,
    prompt: str,
    profile: Dict[str, Any],
    controlled_test: bool,
    target_words: Optional[int],
    push: bool,
) -> Dict[str, Any]:
    book_root = repo / "books" / slug
    if book_root.exists():
        raise ValueError(f"Git book_root already exists: {book_root}")
    seed_tree(
        book_root,
        repo=repo,
        book_id=book_id,
        project_id=project_id,
        title=title,
        slug=slug,
        prompt=prompt,
        profile=profile,
        controlled_test=controlled_test,
        target_words=target_words,
    )
    shutil.copy2(book_root / "00_admin" / "book.yaml", book_root / "book.yaml")
    append_registry_entry(
        repo,
        book_id=book_id,
        title=title,
        slug=slug,
        project_id=project_id,
        profile_key=str(profile.get("key")),
        controlled_test=controlled_test,
    )
    book_chown = fix_book_ownership(repo, slug)
    if book_chown and not str(book_chown).startswith("chown_ok"):
        print(f"WARNING: book ownership fix incomplete: {book_chown}", flush=True)
    subprocess.run(["git", "add", f"books/{slug}", "books/registry.yaml"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Ghost Studio",
            "-c",
            "user.email=studio@local",
            "commit",
            "-m",
            f"Register book seed: {title} ({profile.get('key')})",
        ],
        cwd=repo,
        check=True,
    )
    pushed = False
    push_error = None
    if push:
        env = os.environ.copy()
        key = (os.environ.get("STUDIO_GIT_SSH_KEY") or "").strip()
        if key:
            env["GIT_SSH_COMMAND"] = f"ssh -i {key} -o IdentitiesOnly=yes"
        proc = subprocess.run(["git", "push"], cwd=repo, env=env, capture_output=True, text=True, check=False)
        pushed = proc.returncode == 0
        if not pushed:
            push_error = (proc.stderr or proc.stdout or "")[:500]
    return {"book_root": f"books/{slug}", "committed": True, "pushed": pushed, "push_error": push_error, "ownership": book_chown}


def parent_description(
    *,
    title: str,
    slug: str,
    book_id: str,
    project_id: str,
    abs_ws: str,
    profile: Dict[str, Any],
    controlled_test: bool,
    prompt: str,
) -> str:
    key = profile.get("key")
    target = profile.get("default_target")
    return f"""# BOOK — {title}

## Bootstrap
- Format / profile: `{key}`
- Target words: ~{target}
- Controlled test: `{controlled_test}`
- book_id: `{book_id}`
- book_slug: `{slug}`
- book_root: `books/{slug}/`
- project_id: `{project_id}`
- workspace: `{abs_ws}`

## Original prompt
```text
{prompt.strip()}
```

## Process
1. Managing Editor runs **Intake** (`studio pack --role managing_editor --work intake`)
2. Then atomic handoff: Git sync + Creative Brief
3. Do **not** pre-create the full stage DAG
4. Parent stays `in_progress` until Final Auditor PASS + `release/`

## Definition of done (parent)
Final Auditor PASS + release package under `release/`.
"""


def intake_description(*, abs_ws: str, slug: str, title: str, profile_key: str, controlled_test: bool) -> str:
    return f"""# Intake — {title}

## First tool call
```bash
python3 tools/studio.py pack --slug {slug} --role managing_editor --work intake
```
Apply `env_exports` from the pack JSON before any other studio command.

## write_root
`{abs_ws}`

## Deliverables
- `00_admin/ORIGINAL_PROMPT.md` (already seeded; verify lock)
- `00_admin/REQUIREMENTS_LEDGER.md`
- `00_admin/book.yaml` (profile `{profile_key}`; controlled_test={controlled_test})
- `00_admin/PROJECT_MANIFEST.md`
- `00_admin/CURRENT_STAGE.md`
- `00_admin/DECISION_LOG.md`
- Pilot files if controlled_test: EXPERIMENT_METRICS / CONTROLLED_TEST / PILOT_POSTMORTEM

## After Intake (REQUIRED — use studio tools, not raw curl)
```bash
python3 tools/studio.py handoff --slug {slug} --after intake
```
That creates exactly one Creative Brief issue + one Git sync issue with embedded first-tool-call text.
Leave parent `in_progress`. Do not create duplicate Creative Brief issues.
"""


def build_start_plan(
    *,
    title: str,
    prompt: str,
    format_name: str,
    slug: Optional[str] = None,
    controlled_test: bool = False,
    target_words: Optional[int] = None,
) -> Dict[str, Any]:
    if not title.strip():
        raise ValueError("title is empty")
    if not prompt.strip():
        raise ValueError("prompt is empty")
    profile = profile_for_key(format_name)
    key = normalize_profile_key(format_name)
    # Short-story pilots imply controlled_test unless explicitly false caller already set.
    if key == "short_story" and controlled_test is False:
        # leave as provided; caller decides
        pass
    slug_final = slugify(title, slug)
    return {
        "title": title.strip(),
        "slug": slug_final,
        "profile": profile,
        "profile_key": key,
        "controlled_test": bool(controlled_test),
        "target_words": target_words if target_words is not None else profile.get("default_target"),
        "prompt_chars": len(prompt),
    }
