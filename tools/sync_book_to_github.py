#!/usr/bin/env python3
"""Mirror a project workspace into AI-Fiction-Library and push.

Cadence (studio policy): run after every stage/unit artifact lands.
Caller: Studio Administrator (preferred) or board/ops.

Examples:
  python3 sync_book_to_github.py --slug tide-ledger \\
    --message "Tide Ledger: sync after Scene Outline"
  python3 sync_book_to_github.py --all
  python3 sync_book_to_github.py --slug tide-ledger --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


CID_DEFAULT = (os.environ.get("STUDIO_COMPANY_ID") or "").strip()

STAGE_ORDER = [
    "intake",
    "creative_brief",
    "premise",
    "story_bible",
    "beat_sheet",
    "scene_outline",
    "drafting",
    "full_draft_review",
    "developmental_revision",
    "line_edit",
    "final_audit",
    "release",
]

STAGE_LABELS = {
    "intake": "Intake",
    "creative_brief": "Creative Brief",
    "premise": "Premise Package",
    "story_bible": "Story Bible + Ending",
    "beat_sheet": "Beat Sheet",
    "scene_outline": "Scene Outline",
    "drafting": "Drafting",
    "full_draft_review": "Full-draft Review",
    "developmental_revision": "Developmental Revision",
    "line_edit": "Line Edit",
    "final_audit": "Final Audit",
    "release": "Release",
}

PROGRESS_BEGIN = "<!-- BEGIN AUTO-PROGRESS -->"
PROGRESS_END = "<!-- END AUTO-PROGRESS -->"


def _load_studio_env() -> None:
    explicit = os.environ.get("STUDIO_ENV_FILE", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parents[1] / "studio.env",
            here.parents[2] / "studio.env",
            Path.home() / ".config" / "ghost-studio" / "studio.env",
        ]
    )
    for path in candidates:
        try:
            if not path.is_file():
                continue
        except Exception:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
        break


_load_studio_env()


def detect_paths() -> Tuple[Path, Path]:
    """Return (repo_root, projects_root)."""
    here = Path(__file__).resolve().parent

    def env_path(name: str) -> Optional[Path]:
        v = os.environ.get(name, "").strip()
        return Path(v) if v else None

    candidates_repo = [
        env_path("AI_FICTION_LIBRARY"),
        env_path("STUDIO_REPO"),
        here.parent,
    ]
    repo = next((p for p in candidates_repo if p is not None and (p / ".git").exists()), None)
    if repo is None:
        raise SystemExit("Could not find AI-Fiction-Library git repo (set AI_FICTION_LIBRARY)")

    projects = env_path("STUDIO_PROJECTS_ROOT")
    if projects is None or not projects.exists():
        raise SystemExit("Could not find projects root (set STUDIO_PROJECTS_ROOT)")
    return repo, projects



def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # Prefer deploy key when present (host or container).
    key_candidates = [
        Path(os.environ["STUDIO_GIT_SSH_KEY"]) if os.environ.get("STUDIO_GIT_SSH_KEY") else None,
        Path("/etc/ssh/github_ai_fiction_library_deploy"),
    ]
    key_candidates = [k for k in key_candidates if k is not None]
    for key in key_candidates:
        if key.exists():
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
            )
            break
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True, check=check)


def load_yaml(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    # Minimal fallback parser for flat key: value maps / simple lists used here.
    data: Dict[str, Any] = {}
    books: List[Dict[str, Any]] = []
    current_book: Optional[Dict[str, Any]] = None
    in_books = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("books:"):
            in_books = True
            data["books"] = books
            continue
        if in_books and (line.startswith("  - ") or line.startswith("- ")):
            current_book = {}
            books.append(current_book)
            rest = line.split("- ", 1)[1]
            if ":" in rest:
                k, v = rest.split(":", 1)
                current_book[k.strip()] = _parse_scalar(v.strip())
            continue
        if in_books and current_book is not None and ":" in line and line.startswith(" "):
            k, v = line.strip().split(":", 1)
            current_book[k.strip()] = _parse_scalar(v.strip())
            continue
        if (not in_books) and ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            data[k.strip()] = _parse_scalar(v.strip())
    return data


def dump_flat_yaml(data: Dict[str, Any]) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, indent=2)
    lines = []
    for k, v in data.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            s = str(v)
            if any(ch in s for ch in [":", "#", "{", "}", "[", "]", '"', "'"]):
                lines.append(f'{k}: "{s}"')
            else:
                lines.append(f"{k}: \"{s}\"" if " " in s else f'{k}: "{s}"' if False else f"{k}: \"{s}\"")
                # always quote strings for safety in fallback
                lines[-1] = f'{k}: "{s}"'
    return "\n".join(lines) + "\n"


def _parse_scalar(v: str) -> Any:
    if v in ("null", "Null", "~", ""):
        return None
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        return int(v)
    except Exception:
        return v


def parse_stage_from_current_stage(text: str) -> Optional[str]:
    m = re.search(r"(?im)^\s*-\s*Stage:\s*(.+?)\s*$", text)
    if not m:
        return None
    raw = m.group(1).strip().lower()
    raw = raw.split("(")[0].strip()
    raw = raw.replace("—", "-").replace("–", "-")
    aliases = {
        "story bible + ending": "story_bible",
        "story bible": "story_bible",
        "ending design": "story_bible",
        "premise package": "premise",
        "creative brief": "creative_brief",
        "beat sheet": "beat_sheet",
        "scene outline": "scene_outline",
        "full-draft review": "full_draft_review",
        "full draft review": "full_draft_review",
        "developmental revision": "developmental_revision",
        "line edit": "line_edit",
        "final audit": "final_audit",
        "final audit + release": "release",
    }
    if raw in aliases:
        return aliases[raw]
    key = raw.replace(" ", "_").replace("-", "_")
    if key in STAGE_LABELS:
        return key
    for k, label in STAGE_LABELS.items():
        if label.lower() in raw or k in key:
            return k
    return key


def infer_stage_from_files(book_dir: Path) -> str:
    checks = [
        ("release", book_dir / "release" / "RELEASE_AUDIT.md"),
        ("final_audit", book_dir / "release" / "RELEASE_AUDIT.md"),
        ("line_edit", book_dir / "manuscript"),
        ("drafting", book_dir / "manuscript"),
        ("scene_outline", book_dir / "outline" / "SCENE_OUTLINE.md"),
        ("beat_sheet", book_dir / "structure" / "BEAT_SHEET.md"),
        ("story_bible", book_dir / "bible" / "STORY_BIBLE.md"),
        ("premise", book_dir / "development" / "PREMISE_PACKAGE.md"),
        ("creative_brief", book_dir / "development" / "CREATIVE_BRIEF.md"),
        ("intake", book_dir / "00_admin" / "ORIGINAL_PROMPT.md"),
    ]

    def filled(path: Path) -> bool:
        if not path.exists():
            return False
        if path.is_dir():
            files = list(path.rglob("*.md"))
            # ignore continuity template-only if tiny
            return any(p.stat().st_size > 1200 for p in files)
        try:
            words = len(path.read_text(encoding="utf-8", errors="replace").split())
        except Exception:
            return False
        return words > 200

    # Prefer CURRENT_STAGE if present
    cs = book_dir / "00_admin" / "CURRENT_STAGE.md"
    if cs.exists():
        stage = parse_stage_from_current_stage(cs.read_text(encoding="utf-8", errors="replace"))
        if stage:
            return stage

    for stage, path in checks:
        if filled(path):
            return stage
    return "intake"


def word_count_tree(path: Path, patterns: Tuple[str, ...] = ("*.md",)) -> int:
    total = 0
    if not path.exists():
        return 0
    files: List[Path] = []
    if path.is_file():
        files = [path]
    else:
        for pat in patterns:
            files.extend(path.rglob(pat))
    for f in files:
        try:
            total += len(f.read_text(encoding="utf-8", errors="replace").split())
        except Exception:
            pass
    return total


def sync_book(
    repo: Path,
    projects_root: Path,
    cid: str,
    slug: str,
    project_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    src = projects_root / cid / project_id / "_default"
    dst = repo / "books" / slug
    if not src.exists():
        raise SystemExit(f"Workspace missing: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    # Copy tree; preserve book.yaml at dst root if workspace has 00_admin/book.yaml or book.yaml
    if dry_run:
        print(f"DRY-RUN copy {src} -> {dst}")
    else:
        # Remove tracked content except .gitkeep-like; simplest: copy2 tree with dirs_exist_ok
        for root, dirs, files in os.walk(src):
            rel = Path(root).relative_to(src)
            target_dir = dst / rel
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in files:
                if name.startswith(".node_write_test") or name.startswith(".write_test"):
                    continue
                sfile = Path(root) / name
                dfile = target_dir / name
                shutil.copy2(sfile, dfile)
        # Ensure root book.yaml exists / updated
        candidates = [src / "book.yaml", src / "00_admin" / "book.yaml", dst / "book.yaml"]
        book_yaml_src = next((p for p in candidates if p.exists()), None)
        book_data: Dict[str, Any] = load_yaml(book_yaml_src) if book_yaml_src else {}
        stage = infer_stage_from_files(dst)
        manuscript_words = word_count_tree(dst / "manuscript")
        # subtract continuity ledger-ish tiny files by using scenes/chapters if present
        status = book_data.get("status") or "development"
        if stage == "release" or (dst / "release" / "RELEASE_AUDIT.md").exists() and word_count_tree(dst / "release" / "RELEASE_AUDIT.md") > 200:
            # only mark released if audit looks filled AND manuscript has substantial words
            if manuscript_words > 5000:
                status = "released"
        book_data.update(
            {
                "book_id": book_data.get("book_id") or "",
                "working_title": book_data.get("working_title") or slug,
                "format": book_data.get("format") or "novella",
                "status": status,
                "repository": "https://github.com/MrStewood/AI-Fiction-Library",
                "book_root": f"books/{slug}",
                "project_id": project_id,
                "studio_version": book_data.get("studio_version") or "0.1.0",
                "workflow_profile": book_data.get("workflow_profile") or book_data.get("format") or "novella",
                "default_branch": book_data.get("default_branch") or "main",
                "current_stage": stage,
                "current_approved_commit": book_data.get("current_approved_commit"),
                "target_word_count": book_data.get("target_word_count") or 30000,
                "series": book_data.get("series"),
                "last_synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "manuscript_word_count": manuscript_words,
            }
        )
        (dst / "book.yaml").write_text(dump_flat_yaml(book_data), encoding="utf-8")

    stage = infer_stage_from_files(dst)
    words = word_count_tree(dst / "manuscript")
    return {
        "slug": slug,
        "project_id": project_id,
        "src": str(src),
        "dst": str(dst),
        "stage": stage,
        "manuscript_word_count": words,
    }


def update_registry(repo: Path, sync_results: List[Dict[str, Any]]) -> None:
    reg_path = repo / "books" / "registry.yaml"
    data = load_yaml(reg_path) if reg_path.exists() else {"schema_version": "1.0.0", "books": []}
    books = data.get("books") or []
    by_slug = {b.get("book_slug"): b for b in books if isinstance(b, dict)}
    for r in sync_results:
        book_yaml = load_yaml(repo / "books" / r["slug"] / "book.yaml")
        entry = by_slug.get(r["slug"]) or {
            "book_id": book_yaml.get("book_id"),
            "working_title": book_yaml.get("working_title") or r["slug"],
            "book_slug": r["slug"],
            "book_root": f"books/{r['slug']}",
            "project_id": r["project_id"],
            "format": book_yaml.get("format") or "novella",
            "studio_version": book_yaml.get("studio_version") or "0.1.0",
            "series_id": None,
            "created_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        status = book_yaml.get("status") or "development"
        entry.update(
            {
                "working_title": book_yaml.get("working_title") or entry.get("working_title"),
                "project_id": r["project_id"],
                "project_status": "released" if status == "released" else "active",
                "current_stage": r["stage"],
                "manuscript_word_count": r.get("manuscript_word_count") or 0,
                "last_synced_at": book_yaml.get("last_synced_at"),
                "current_approved_commit": book_yaml.get("current_approved_commit"),
            }
        )
        by_slug[r["slug"]] = entry
    # Preserve order: existing first, then new
    ordered = []
    seen = set()
    for b in books:
        slug = b.get("book_slug")
        if slug in by_slug:
            ordered.append(by_slug[slug])
            seen.add(slug)
    for slug, entry in by_slug.items():
        if slug not in seen:
            ordered.append(entry)
    data["schema_version"] = data.get("schema_version") or "1.0.0"
    data["books"] = ordered
    if yaml is not None:
        reg_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, indent=2), encoding="utf-8")
    else:
        # write a readable fallback
        lines = [
            "# Authoritative index of book_id ↔ project ↔ book_root.",
            "# Only Studio Administrator / administrative create workflows may modify this file.",
            "# Normal book agents: read-only.",
            'schema_version: "1.0.0"',
            "books:",
        ]
        for b in ordered:
            lines.append(f'  - book_id: "{b.get("book_id")}"')
            for k in [
                "working_title",
                "book_slug",
                "book_root",
                "project_id",
                "format",
                "project_status",
                "current_stage",
                "studio_version",
                "series_id",
                "created_date",
                "manuscript_word_count",
                "last_synced_at",
                "current_approved_commit",
            ]:
                v = b.get(k)
                if v is None:
                    lines.append(f"    {k}: null")
                else:
                    lines.append(f'    {k}: "{v}"' if not isinstance(v, (int, float)) else f"    {k}: {v}")
        reg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")



def _scene_progress(book_dir: Path) -> Dict[str, Any]:
    scenes_dir = book_dir / "manuscript" / "scenes"
    if not scenes_dir.exists():
        return {"filled": 0, "total_files": 0, "words": 0, "last_unit": None}
    files = sorted(scenes_dir.glob("SCENE-*.md"))
    words = 0
    filled = 0
    last = None
    for p in files:
        try:
            w = len(p.read_text(encoding="utf-8", errors="replace").split())
        except Exception:
            w = 0
        words += w
        if w >= 200:
            filled += 1
            last = p.stem
    return {"filled": filled, "total_files": len(files), "words": words, "last_unit": last}


def _timeline_line(stage_key: str) -> str:
    parts = []
    try:
        cur = STAGE_ORDER.index(str(stage_key))
    except ValueError:
        cur = -1
    for i, key in enumerate(STAGE_ORDER):
        label = STAGE_LABELS.get(key, key)
        if i < cur:
            parts.append("✅ " + label)
        elif i == cur:
            parts.append("**▶ " + label + "**")
        else:
            parts.append("⬜ " + label)
    return " → ".join(parts)


def render_progress_markdown(repo: Path) -> str:
    reg = load_yaml(repo / "books" / "registry.yaml")
    books = reg.get("books") or []
    in_progress = []
    completed = []
    featured = None
    for b in books:
        slug = b.get("book_slug")
        book_dir = repo / "books" / slug if slug else None
        book_yaml = {}
        if book_dir and (book_dir / "book.yaml").exists():
            book_yaml = load_yaml(book_dir / "book.yaml")
        status = book_yaml.get("status") or b.get("project_status") or "development"
        stage = book_yaml.get("current_stage") or b.get("current_stage") or "intake"
        stage_key = str(stage).replace("story_bible_and_ending", "story_bible")
        title = book_yaml.get("working_title") or b.get("working_title") or slug
        fmt = book_yaml.get("format") or b.get("format") or "?"
        scene = _scene_progress(book_dir) if book_dir else {"filled": 0, "words": 0, "last_unit": None}
        words = book_yaml.get("manuscript_word_count") or b.get("manuscript_word_count") or scene.get("words") or 0
        synced = book_yaml.get("last_synced_at") or b.get("last_synced_at") or "—"
        link = f"books/{slug}/"
        stage_label = STAGE_LABELS.get(stage_key, str(stage))
        try:
            idx = STAGE_ORDER.index(stage_key)
            pct = int(round(100 * (idx + 1) / len(STAGE_ORDER)))
        except ValueError:
            pct = 0
        row = {
            "title": title,
            "format": fmt,
            "stage": stage_label,
            "stage_key": stage_key,
            "pct": pct,
            "words": words,
            "synced": synced,
            "link": link,
            "status": status,
            "filled": scene.get("filled") or 0,
            "last_unit": scene.get("last_unit"),
            "timeline": _timeline_line(stage_key),
        }
        if status == "released" or str(b.get("project_status")) == "released":
            completed.append(row)
        else:
            in_progress.append(row)
            if featured is None:
                featured = row

    nl = "\n"
    lines = [
        "## Library progress",
        "",
        "Auto-generated from each book's `book.yaml` + `books/registry.yaml`.",
        "Do not edit inside the AUTO-PROGRESS markers.",
        "",
    ]

    if featured:
        lines += [
            f"### Now reading: {featured['title']}",
            "",
            f"- **Format:** {featured['format']}",
            f"- **Stage:** {featured['stage']} ({featured['pct']}%)",
            f"- **Manuscript words:** {featured['words']}",
        ]
        if featured.get("filled"):
            extra = f"- **Scenes on disk:** {featured['filled']}"
            if featured.get("last_unit"):
                extra += f" (through {featured['last_unit']})"
            lines.append(extra)
        lines += [
            f"- **Path:** [`{featured['link']}`]({featured['link']})",
            f"- **Last synced:** {featured['synced']}",
            "",
            "#### Stage timeline",
            "",
            featured["timeline"],
            "",
        ]

    lines += ["### In progress", ""]
    if not in_progress:
        lines += ["_No active books._", ""]
    else:
        lines += [
            "| Book | Format | Stage | Progress | Words | Scenes | Path |",
            "|---|---|---|---:|---:|---:|---|",
        ]
        for r in in_progress:
            lines.append(
                f"| {r['title']} | {r['format']} | {r['stage']} | {r['pct']}% | {r['words']} | {r['filled']} | [`{r['link']}`]({r['link']}) |"
            )
        lines.append("")

    lines += ["### Completed", ""]
    if not completed:
        lines += ["_No completed books yet._", ""]
    else:
        lines += [
            "| Book | Format | Words | Released / synced | Path |",
            "|---|---|---:|---|---|",
        ]
        for r in completed:
            lines.append(
                f"| {r['title']} | {r['format']} | {r['words']} | {r['synced']} | [`{r['link']}`]({r['link']}) |"
            )
        lines.append("")

    return nl.join(lines)


def update_readme(repo: Path) -> None:
    readme = repo / "README.md"
    body = render_progress_markdown(repo)
    block = PROGRESS_BEGIN + "\n" + body + "\n" + PROGRESS_END
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
    else:
        text = (
            "# AI-Fiction-Library\n\n"
            "A library of original fiction produced by **Ghost in the Manuscript**, "
            "plus the versioned studio kit used to make it.\n\n"
            "This front page tracks **books and progress only**. "
            "Studio process docs live under [`studio/`](studio/).\n\n"
        )
    if PROGRESS_BEGIN in text and PROGRESS_END in text:
        text = re.sub(
            re.escape(PROGRESS_BEGIN) + r".*?" + re.escape(PROGRESS_END),
            block,
            text,
            flags=re.S,
        )
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    # Keep README front-door only: drop legacy harness sections if still present.
    for heading in ("## Layout", "## Rules", "## Studio version", "## Spec", "### How sync works"):
        if heading in text and PROGRESS_BEGIN in text:
            # remove from heading until next ## or AUTO block end already handled
            pass
    # Strip static sections after progress that mention studio pin/spec
    text = re.sub(r"\n## Studio version\n.*", "\n", text, flags=re.S)
    text = re.sub(r"\n## Spec\n.*", "\n", text, flags=re.S)
    readme.write_text(text.rstrip() + "\n", encoding="utf-8")



def git_commit_push(repo: Path, message: str, dry_run: bool = False) -> Optional[str]:
    # HARD GUARD: never run sync from a repo that lost the studio kit.
    studio = repo / "tools" / "studio.py"
    if not studio.is_file():
        raise SystemExit(
            "REFUSING git-sync: tools/studio.py missing. "
            "Repo kit was clobbered; restore tools/studio/tests before syncing books."
        )
    # Container mounts may be owned by a different uid than the git caller.
    run(["git", "config", "--global", "--add", "safe.directory", str(repo)], check=False)
    run(["git", "config", "user.name", "Ghost in the Manuscript"], cwd=repo, check=False)
    run(["git", "config", "user.email", "studio@users.noreply.github.com"], cwd=repo, check=False)
    # Prefer SSH remote when deploy key is available
    key_exists = Path("/etc/ssh/github_ai_fiction_library_deploy").exists() or Path(
        "github_ai_fiction_library_deploy"
    ).exists()
    if key_exists:
        run(
            ["git", "remote", "set-url", "origin", "git@github.com:MrStewood/AI-Fiction-Library.git"],
            cwd=repo,
            check=False,
        )
    # NEVER git add -A / pull --rebase / reset. Sync may only touch book artifacts + progress index.
    allowed = [
        "books",
        "README.md",
    ]
    status = run(["git", "status", "--porcelain", "--"] + allowed, cwd=repo)
    if not status.stdout.strip():
        print("No book/README changes to commit")
        head = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=False)
        return (head.stdout or "").strip() or None
    if dry_run:
        print("DRY-RUN would commit:\n", status.stdout)
        return None
    run(["git", "add", "--"] + allowed, cwd=repo)
    # Refuse if staged changes include kit paths (defense in depth)
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=repo)
    bad = [
        ln for ln in (staged.stdout or "").splitlines()
        if ln and not (ln.startswith("books/") or ln == "README.md")
    ]
    if bad:
        run(["git", "reset", "HEAD"], cwd=repo, check=False)
        raise SystemExit(f"REFUSING git-sync: attempted to stage non-book paths: {bad[:10]}")
    commit = run(["git", "commit", "-m", message], cwd=repo)
    print(commit.stdout)
    push = run(["git", "push", "origin", "HEAD"], cwd=repo)
    print(push.stdout or push.stderr)
    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo)
    return head.stdout.strip()


def resolve_targets(repo: Path, slug: Optional[str], all_books: bool) -> List[Tuple[str, str]]:
    reg = load_yaml(repo / "books" / "registry.yaml")
    books = reg.get("books") or []
    out = []
    for b in books:
        s = b.get("book_slug")
        pid = b.get("project_id")
        if not s or not pid:
            continue
        if all_books or (slug and s == slug):
            out.append((s, pid))
    if slug and not out:
        raise SystemExit(f"Slug not found in registry: {slug}")
    if not out:
        raise SystemExit("No books selected")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Mirror the board book workspace to GitHub")
    ap.add_argument("--slug", help="Book slug (e.g. tide-ledger)")
    ap.add_argument("--all", action="store_true", help="Sync all registry books")
    ap.add_argument("--company-id", default=CID_DEFAULT)
    ap.add_argument("--message", default=None, help="Commit message")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("Provide --slug or --all")

    repo, projects = detect_paths()
    print(f"repo={repo}")
    print(f"projects={projects}")
    targets = resolve_targets(repo, args.slug, args.all)
    results = []
    for slug, pid in targets:
        print(f"Syncing {slug} ({pid})...")
        results.append(sync_book(repo, projects, args.company_id, slug, pid, dry_run=args.dry_run))
        print(f"  stage={results[-1]['stage']} manuscript_words={results[-1]['manuscript_word_count']}")

    if not args.dry_run:
        update_registry(repo, results)
        update_readme(repo)

    if args.no_push or args.dry_run:
        print("Skipping commit/push")
        return 0

    if len(results) == 1:
        r = results[0]
        msg = args.message or (
            f"{r['slug']}: sync after {STAGE_LABELS.get(r['stage'], r['stage'])} "
            f"({r['manuscript_word_count']} manuscript words)"
        )
    else:
        msg = args.message or f"Sync {len(results)} books + progress README"
    sha = git_commit_push(repo, msg, dry_run=False)
    print(f"Done. HEAD={sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        raise
