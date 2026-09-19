#!/usr/bin/env python3
"""Ghost in the Manuscript — process tools for the board agents.

AI-friendly CLI. Prefer these tools over freeform curl for process mutations.

Exit codes:
  0  success
  1  operational failure (API/git/disk/process rule)
  2  usage / argument error (read guidance and retry)

Default output is JSON on stdout so agents can parse it. Errors always include:
  error:     short machine-ish code
  issue:     what went wrong
  guidance:  what to do next
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from length_profiles import (
        infer_profile_from_target,
        load_length_profiles,
        profile_for_key,
        resolve_profile_for_workspace,
        resolve_scene_min_words,
    )
    from role_packs import job_card, list_work_modes, normalize_work, pack_paths
except ImportError:  # pragma: no cover
    from tools.length_profiles import (  # type: ignore
        infer_profile_from_target,
        load_length_profiles,
        profile_for_key,
        resolve_profile_for_workspace,
        resolve_scene_min_words,
    )
    from tools.role_packs import job_card, list_work_modes, normalize_work, pack_paths  # type: ignore

def _load_studio_env() -> None:
    """Load host env file if present. Never commit secrets into this repo."""
    candidates = []
    explicit = os.environ.get("STUDIO_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    # Common host-only locations (names intentionally generic).
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


def _require_env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if not v:
        fail(
            "missing_env",
            f"Required environment variable {name} is not set.",
            "Export it (see .env.example) or set STUDIO_ENV_FILE to a host-only env file.",
        )
    return v


def studio_cli() -> str:
    explicit = (os.environ.get("STUDIO_CLI") or "").strip()
    if explicit:
        return explicit
    for cand in (
        Path(__file__).resolve(),
    ):
        if cand.is_file():
            return f"python3 {cand}"
    return "python3 tools/studio.py"


CID_DEFAULT = (os.environ.get("STUDIO_COMPANY_ID") or "").strip()
API_DEFAULT = (os.environ.get("STUDIO_API_URL") or "").rstrip("/")

def board_token() -> str:
    """Resolve board bearer without hardcoding harness-specific env names in the public kit."""
    for key in ("STUDIO_BOARD_TOKEN", "BOARD_TOKEN"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    for key, val in os.environ.items():
        if not key.endswith("_API_KEY"):
            continue
        val = (val or "").strip()
        if val.startswith("pcp_"):
            return val
    return (os.environ.get("STUDIO_BOARD_TOKEN") or "").strip()


TOKEN_DEFAULT = board_token()

ROLE_ALIASES = {
    "managing_editor": "Managing Editor",
    "me": "Managing Editor",
    "studio_administrator": "Studio Administrator",
    "studio_admin": "Studio Administrator",
    "story_architect": "Story Architect",
    "architect": "Story Architect",
    "scene_planner": "Scene Planner",
    "drafting_author": "Drafting Author",
    "author": "Drafting Author",
    "drafter": "Drafting Author",
    "developmental_reviewer": "Developmental Reviewer",
    "dev_reviewer": "Developmental Reviewer",
    "continuity_reviewer": "Continuity Reviewer",
    "continuity": "Continuity Reviewer",
    "target_reader_reviewer": "Target Reader Reviewer",
    "target_reader": "Target Reader Reviewer",
    "revision_editor": "Revision Editor",
    "line_editor": "Line Editor",
    "final_auditor": "Final Auditor",
    "research_specialist": "Research Specialist",
}

WORK_ROLE = {
    "draft": "drafting_author",
    "redraft": "drafting_author",
    "revision_prose": "drafting_author",
    "scene_outline": "scene_planner",
    "scene_contract": "scene_planner",
    "git_sync": "studio_administrator",
    "continuity": "continuity_reviewer",
    "developmental_review": "developmental_reviewer",
    "craft_audit": "developmental_reviewer",
    "target_reader": "target_reader_reviewer",
    "revision": "revision_editor",
    "line_edit": "line_editor",
    "final_audit": "final_auditor",
    "release": "final_auditor",
    "premise": "story_architect",
    "beat_sheet": "story_architect",
    "story_bible": "story_architect",
    "creative_brief": "story_architect",
    "ending": "story_architect",
    "research": "research_specialist",
    "intake": "managing_editor",
    "stage_advance": "managing_editor",
}


def emit(payload: Dict[str, Any], exit_code: int = 0) -> None:
    payload.setdefault("ok", exit_code == 0)
    payload.setdefault("exit_code", exit_code)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code)


def fail(error: str, issue: str, guidance: str, *, exit_code: int = 1, **extra: Any) -> None:
    emit({"ok": False, "error": error, "issue": issue, "guidance": guidance, **extra}, exit_code=exit_code)


def usage_fail(issue: str, guidance: str, **extra: Any) -> None:
    fail("usage_error", issue, guidance, exit_code=2, **extra)


class AiArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        guidance = (
            "Re-run with valid arguments. Try: `studio <command> --help` "
            "or `studio commands` for a machine-readable command list."
        )
        tips = []
        m = re.search(r"required: (.+)$", message)
        if m:
            tips.append(f"Add the missing argument(s): {m.group(1)}")
        m = re.search(r"invalid choice: '([^']+)' \\(choose from (.+)\\)$", message)
        if not m:
            m = re.search(r"invalid choice: '([^']+)' \\(choose from (.+)\\)$", message)
        m = re.search(r"invalid choice: '([^']+)' \(choose from (.+)\)$", message)
        if m:
            tips.append(f"'{m.group(1)}' is not valid. Choose one of: {m.group(2)}")
        m = re.search(r"unrecognized arguments: (.+)$", message)
        if m:
            tips.append(f"Remove or fix unrecognized argument(s): {m.group(1)}")
        if tips:
            guidance = " ".join(tips) + " " + guidance
        usage_fail(issue=message, guidance=guidance, command=self.prog, hint="Pass --help for full flag list.")


def detect_repo() -> Path:
    candidates = [
        Path(os.environ["AI_FICTION_LIBRARY"]) if os.environ.get("AI_FICTION_LIBRARY") else None,
        Path(os.environ["STUDIO_REPO"]) if os.environ.get("STUDIO_REPO") else None,
        Path(__file__).resolve().parent.parent,
    ]
    for p in candidates:
        if p and (p / ".git").exists():
            return p
    fail(
        "repo_not_found",
        "Could not find AI-Fiction-Library git repository.",
        "Set AI_FICTION_LIBRARY or STUDIO_REPO to the repo root.",
    )
    raise AssertionError


def detect_projects_root(*, company_id: Optional[str] = None) -> Path:
    candidates = [
        Path(os.environ["STUDIO_PROJECTS_ROOT"]) if os.environ.get("STUDIO_PROJECTS_ROOT") else None,
    ]
    for p in candidates:
        if p and p.exists():
            return validate_projects_root(p, company_id=company_id)
    fail(
        "projects_root_not_found",
        "Could not find projects root.",
        "Set STUDIO_PROJECTS_ROOT to the directory that CONTAINS company folders (not the company folder itself).",
    )
    raise AssertionError


def validate_projects_root(root: Path, *, company_id: Optional[str] = None) -> Path:
    """Reject STUDIO_PROJECTS_ROOT values that already include the company id (causes doubled paths)."""
    cid = (company_id or os.environ.get("STUDIO_COMPANY_ID") or CID_DEFAULT or "").strip()
    resolved = root
    try:
        if root.exists():
            resolved = root.resolve()
    except Exception:
        resolved = root
    if cid and resolved.name == cid:
        fail(
            "projects_root_includes_company_id",
            f"STUDIO_PROJECTS_ROOT ends with company id ({cid}): {resolved}",
            "Set STUDIO_PROJECTS_ROOT to the parent of the company directory. "
            "Wrong: .../projects/<company_id>  Right: .../projects",
            projects_root=str(resolved),
            company_id=cid,
        )
    parts = resolved.parts
    if cid and len(parts) >= 2 and parts[-1] == cid and parts[-2] == cid:
        fail(
            "projects_root_doubled_company_id",
            f"STUDIO_PROJECTS_ROOT looks like a doubled company path: {resolved}",
            "Reset STUDIO_PROJECTS_ROOT to the projects parent directory.",
            projects_root=str(resolved),
            company_id=cid,
        )
    return resolved


def build_env_exports(*, projects_root: str, company_id: str) -> List[str]:
    """Exact exports agents should apply before studio commands. Never embed board tokens."""
    lines = [
        f'export STUDIO_PROJECTS_ROOT="{projects_root.rstrip("/")}"',
        f'export STUDIO_COMPANY_ID="{company_id}"',
    ]
    api = (os.environ.get("STUDIO_API_URL") or "").strip()
    if api:
        lines.append(f'export STUDIO_API_URL="{api}"')
    env_file = (os.environ.get("STUDIO_ENV_FILE") or "").strip()
    if env_file:
        lines.append(f'export STUDIO_ENV_FILE="{env_file}"')
    lines.append(f'export STUDIO_CLI="{studio_cli()}"')
    lines.append(
        "# STUDIO_BOARD_TOKEN must be injected by the runtime or STUDIO_ENV_FILE (never paste tokens into issues/chat)"
    )
    return lines


def forbidden_write_roots(write_root: str, *, company_id: str, project_id: str) -> List[str]:
    wr = write_root.rstrip("/")
    return [
        "/tmp",
        "/var/tmp",
        "**/repos/**",
        f".../{company_id}/{company_id}/{project_id}/_default",
        "shared template workspace / BOOK_TEMPLATE*",
        f"ANY path outside write_root ({wr})",
    ]


def path_is_forbidden_deliverable(
    path: Path, *, write_root: Optional[str] = None, company_id: str = ""
) -> Optional[str]:
    s = str(path)
    cid = (company_id or CID_DEFAULT or "").strip()
    if cid and f"/{cid}/{cid}/" in s:
        return "doubled_company_path_not_allowed"
    if write_root:
        wr = write_root.rstrip("/")
        if not (s == wr or s.startswith(wr + "/")):
            # Outside write_root: also classify common ephemeral/wrong roots.
            if s.startswith("/tmp/") or s.startswith("/var/tmp/") or s == "/tmp":
                return "tmp_not_allowed"
            if "/repos/" in s:
                return "repos_checkout_not_allowed"
            return "outside_write_root"
        return None
    # No write_root provided: reject known ephemeral / checkout roots.
    if (
        s.startswith("/tmp/")
        or s == "/tmp"
        or s.startswith("/var/tmp/")
    ):
        return "tmp_not_allowed"
    if "/repos/" in s:
        return "repos_checkout_not_allowed"
    return None



def api(method: str, path: str, data: Optional[dict] = None, token: str = TOKEN_DEFAULT) -> Any:
    if not API_DEFAULT:
        _require_env("STUDIO_API_URL")
    if not token:
        token = _require_env("STUDIO_BOARD_TOKEN")
    url = API_DEFAULT + path
    body = None if data is None else json.dumps(data).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    run_id = os.environ.get("STUDIO_RUN_ID")
    run_header = (os.environ.get("STUDIO_RUN_ID_HEADER") or "").strip()
    if run_id and run_header:
        headers[run_header] = run_id
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        fail(
            "api_http_error",
            f"{method} {path} returned HTTP {e.code}.",
            "Check token/path/payload. During heartbeats set STUDIO_RUN_ID for issue writes.",
            http_status=e.code,
            response_body=err[:800],
            method=method,
            path=path,
        )
    except urllib.error.URLError as e:
        fail(
            "api_unreachable",
            f"Could not reach the board API at {API_DEFAULT}: {e}",
            "Verify STUDIO_API_URL and that board is up.",
        )


def api_soft(method: str, path: str, data: Optional[dict] = None, token: str = TOKEN_DEFAULT) -> Dict[str, Any]:
    """Board API helper that never exits; used for recoverable wake/resume."""
    if not API_DEFAULT:
        return {"ok": False, "error": "missing_api_url"}
    tok = (token or TOKEN_DEFAULT or board_token() or "").strip()
    if not tok:
        return {"ok": False, "error": "missing_token"}
    url = API_DEFAULT + path
    body = None if data is None else json.dumps(data).encode()
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    run_id = os.environ.get("STUDIO_RUN_ID")
    run_header = (os.environ.get("STUDIO_RUN_ID_HEADER") or "").strip()
    if run_id and run_header:
        headers[run_header] = run_id
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            return {"ok": True, "data": payload, "http_status": getattr(resp, "status", 200)}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "error": "api_http_error",
            "http_status": e.code,
            "response_body": err[:800],
            "method": method,
            "path": path,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "method": method, "path": path}


def load_registry(repo: Path) -> List[Dict[str, Any]]:
    path = repo / "books" / "registry.yaml"
    if not path.exists():
        fail("registry_missing", f"Missing {path}", "Bootstrap a book first or pass --project-id/--parent-id.")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        books = data.get("books") or []
        if not isinstance(books, list):
            fail("registry_invalid", "books/registry.yaml 'books' is not a list.", "Fix registry.yaml.")
        return books
    except ImportError:
        books: List[Dict[str, Any]] = []
        cur: Optional[Dict[str, Any]] = None
        for line in text.splitlines():
            if re.match(r"^\s*-\s+book_(id|slug):", line):
                cur = {}
                books.append(cur)
                rest = line.split("-", 1)[1].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    cur[k.strip()] = v.strip().strip("\"'")
            elif cur is not None and ":" in line and line.strip() and not line.strip().startswith("#"):
                k, v = line.strip().split(":", 1)
                cur[k.strip()] = v.strip().strip("\"'") or None
        return books


def resolve_book(repo: Path, slug: Optional[str] = None, project_id: Optional[str] = None) -> Dict[str, Any]:
    books = load_registry(repo)
    if slug:
        for b in books:
            if b.get("book_slug") == slug:
                return b
        fail(
            "book_slug_not_found",
            f"No book with slug '{slug}' in books/registry.yaml.",
            "Use a known --slug (e.g. tide-ledger).",
            known_slugs=[b.get("book_slug") for b in books],
        )
    if project_id:
        for b in books:
            if b.get("project_id") == project_id:
                return b
        fail("project_id_not_found", f"No book with project_id '{project_id}'.", "Check registry or pass --slug.")
    if len(books) == 1:
        return books[0]
    fail(
        "book_unspecified",
        "Multiple books exist; specify --slug or --project-id.",
        "Example: studio watchdog --slug tide-ledger",
        known_slugs=[b.get("book_slug") for b in books],
    )
    raise AssertionError


def book_project_id(book: Dict[str, Any]) -> str:
    pid = (
        book.get("project_id")
        or book.get("orchestration_project_id")
    )
    if not pid:
        fail(
            "book_missing_project_id",
            f"Book '{book.get('book_slug')}' has no project_id.",
            "Repair books/registry.yaml / book.yaml (field name: project_id).",
        )
    return str(pid)


def absolute_ws(book: Dict[str, Any], cid: str = CID_DEFAULT) -> str:
    """Agent-visible absolute workspace path (from STUDIO_WORKSPACE_ABS_TEMPLATE)."""
    pid = book_project_id(book)
    company = cid or CID_DEFAULT or _require_env("STUDIO_COMPANY_ID")
    tmpl = (os.environ.get("STUDIO_WORKSPACE_ABS_TEMPLATE") or "").strip()
    projects_root = (os.environ.get("STUDIO_PROJECTS_ROOT") or "").rstrip("/")
    if tmpl:
        return tmpl.format(company_id=company, project_id=pid, projects_root=projects_root)
    return str(workspace_for(book, company))


def workspace_for(book: Dict[str, Any], cid: str = CID_DEFAULT) -> Path:
    company = cid or CID_DEFAULT or _require_env("STUDIO_COMPANY_ID")
    projects = detect_projects_root(company_id=company)
    pid = book_project_id(book)
    ws = projects / company / pid / "_default"
    if not ws.exists():
        fail(
            "workspace_missing",
            f"Project workspace not found: {ws}",
            "Confirm the project exists and _default was seeded.",
            expected_path=str(ws),
        )
    return ws



def enrich_book_from_workspace(book: Dict[str, Any], ws: Path) -> Dict[str, Any]:
    """Merge 00_admin/book.yaml length-profile fields onto a registry book dict."""
    try:
        from length_profiles import read_book_yaml

        by = read_book_yaml(ws)
    except Exception:
        by = {}
    if not by:
        return book
    out = dict(book)
    for k in (
        "format",
        "workflow_profile",
        "target_word_count",
        "target_word_min",
        "target_word_max",
        "scene_min_words",
        "scene_target_words",
        "typical_scenes_min",
        "typical_scenes_max",
        "typical_chapters_min",
        "typical_chapters_max",
        "chapters_required",
        "working_title",
        "current_stage",
    ):
        if k in by and by[k] is not None:
            out[k] = by[k]
    return out


def normalize_role(role: str) -> str:
    key = role.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in ROLE_ALIASES:
        usage_fail(
            issue=f"Unknown role '{role}'.",
            guidance="Pass a role key from valid_roles (not a display name).",
            valid_roles=sorted(set(ROLE_ALIASES.keys())),
            examples=["drafting_author", "scene_planner", "studio_administrator", "continuity_reviewer"],
        )
    return key


def fetch_agents(cid: str = CID_DEFAULT, token: str = TOKEN_DEFAULT) -> Dict[str, Dict[str, Any]]:
    agents = api("GET", f"/api/companies/{cid}/agents", token=token)
    if not isinstance(agents, list):
        fail("agents_list_invalid", "GET /agents did not return a list.", "Check API/token.")
    return {a["name"]: a for a in agents}


def role_to_agent(role_key: str, agents: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    display = ROLE_ALIASES[role_key]
    if display not in agents:
        fail(
            "agent_not_hired",
            f"Role '{role_key}' maps to '{display}', but that agent is not hired.",
            "Hire/recreate the agent, or pick a different --role.",
            role=role_key,
            expected_name=display,
            hired=sorted(agents.keys()),
        )
    return agents[display]


def find_parent_issue(cid: str, project_id: str, token: str = TOKEN_DEFAULT) -> Dict[str, Any]:
    issues = api("GET", f"/api/companies/{cid}/issues?projectId={project_id}", token=token)
    if isinstance(issues, dict):
        issues = issues.get("issues") or issues.get("items") or issues.get("data") or []
    parents = [i for i in (issues or []) if i.get("projectId") == project_id and not i.get("parentId")]
    if not parents:
        fail(
            "parent_issue_missing",
            f"No parent book issue found for project {project_id}.",
            "Create the parent BOOK issue first, or pass --parent-id.",
        )
    parents_sorted = sorted(
        parents,
        key=lambda i: (0 if i.get("status") in ("in_progress", "blocked", "todo") else 1, i.get("createdAt") or ""),
    )
    return parents_sorted[0]



def find_issue(cid: str, issue_ref: str, token: str = TOKEN_DEFAULT, project_id: Optional[str] = None) -> Dict[str, Any]:
    """Resolve an issue by UUID or identifier (e.g. GHO-131)."""
    ref = issue_ref.strip()
    if re.fullmatch(r"[0-9a-fA-F-]{36}", ref):
        issue = api("GET", f"/api/issues/{ref}", token=token)
        if not issue or not isinstance(issue, dict) or not issue.get("id"):
            fail("issue_not_found", f"No issue with id '{ref}'.", "Pass a valid UUID or identifier like GHO-131.")
        return issue
    q = urllib.request.quote(ref)
    path = f"/api/companies/{cid}/issues?q={q}&limit=20"
    if project_id:
        path += f"&projectId={project_id}"
    issues = api("GET", path, token=token)
    if isinstance(issues, dict):
        issues = issues.get("issues") or issues.get("items") or issues.get("data") or []
    matches = [i for i in (issues or []) if (i.get("identifier") or "").upper() == ref.upper() or i.get("id") == ref]
    if not matches:
        # fallback: scan project issues if project_id known
        if project_id:
            issues = api("GET", f"/api/companies/{cid}/issues?projectId={project_id}", token=token)
            if isinstance(issues, dict):
                issues = issues.get("issues") or issues.get("items") or issues.get("data") or []
            matches = [i for i in (issues or []) if (i.get("identifier") or "").upper() == ref.upper()]
    if not matches:
        fail(
            "issue_not_found",
            f"No issue matching '{ref}'.",
            "Pass the issue identifier (e.g. GHO-131) or UUID. Check `studio watchdog --slug ...`.",
            issue_ref=ref,
        )
    if len(matches) > 1:
        fail(
            "issue_ambiguous",
            f"Multiple issues matched '{ref}'.",
            "Pass the exact UUID from the API.",
            matches=[{"id": i.get("id"), "identifier": i.get("identifier"), "title": i.get("title")} for i in matches[:5]],
        )
    return matches[0]


def word_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").split())
    except Exception as e:
        fail("read_failed", f"Could not read {path}: {e}", "Check path permissions/existence.")
        raise AssertionError


def _assignment_desc(
    abs_ws: str,
    book: Dict[str, Any],
    parent_id: str,
    role_key: str,
    work: Optional[str],
    unit: Optional[str],
    *,
    workspace: Optional[Path] = None,
    title_hint: Optional[str] = None,
) -> str:
    """Issue description that embeds the ONE primary studio command for this assignment."""
    slug = book.get("book_slug") or "<slug>"
    title = book.get("working_title") or slug
    unit_u = unit.upper() if unit else None
    profile_key = str(book.get("workflow_profile") or book.get("format") or "novella")
    min_words = resolve_scene_min_words(workspace=workspace, book_yaml=book, profile_key=profile_key)
    card = job_card(role_key, work, unit_u, abs_ws, book, min_words=min_words)
    work_key = card.get("work") or work or "draft"
    primary = card.get("primary_command") or "pack"
    heading = title_hint or f"{work_key} — {title}"

    if primary == "git-sync":
        first = (
            f"{studio_cli()} git-sync --slug {slug} "
            f"--message '{title}: sync after {unit_u or 'stage'}'"
        )
    elif primary == "watchdog":
        first = f"{studio_cli()} watchdog --slug {slug}"
    else:
        unit_flag = f" --unit {unit_u}" if unit_u else ""
        first = (
            f"{studio_cli()} pack "
            f"--slug {slug} --role {role_key} --work {work_key}{unit_flag}"
        )

    deliverable = card.get("deliverable_path") or "(see job card / Revision Brief)"
    done = card.get("done_gate_command") or "verify-done on deliverable, then PATCH done"
    mission = card.get("mission") or ""

    return f"""# {heading}

## First tool call (REQUIRED — do this before hunting files)
```bash
{first}
```
Runtime must already provide `STUDIO_*`; `env_exports` is diagnostic/echo only. Use `write_root` / `job.deliverable_path` / `files[].content`.
Never write under `/tmp`, a repos checkout, or a doubled company-id path. Do not glob legacy templates.

## Project
- projectId: `{book['project_id']}`
- parentId: `{parent_id}`
- write_root / Workspace (absolute): `{abs_ws}`
- Role: `{role_key}` / work: `{work_key}`
- Format profile: `{profile_key}`

## Mission
{mission}

## Deliverable
`{deliverable}`

## Done gate (REQUIRED)
```bash
{done}
```
Paste evidence in the comment, then PATCH `done`. Do not touch the parent issue unless you are Managing Editor.
"""


def _draft_desc(abs_ws: str, unit: str, book: Dict[str, Any], parent_id: str, workspace: Optional[Path] = None) -> str:
    return _assignment_desc(
        abs_ws,
        book,
        parent_id,
        "drafting_author",
        "draft",
        unit,
        workspace=workspace,
        title_hint=f"Draft {unit.upper()} — {book.get('working_title') or book.get('book_slug')}",
    )

def _sync_desc(abs_ws: str, book: Dict[str, Any], after: str) -> str:
    slug = book["book_slug"]
    title = book.get("working_title") or slug
    cli = studio_cli()
    return f"""# Git sync — {title} after {after}

## Command (REQUIRED)
```bash
{cli} git-sync --slug {slug} \\
  --message "{title}: sync after {after}"
```

## Rules
- Mirror only; do not invent creative content.
- Sync is NOT done unless push succeeds (tool exits 0 and returns remote_sha).
- On SSH/push failure: leave issue `blocked` with the tool's issue/guidance — do not mark done.

## Workspace
`{abs_ws}`
"""


def cmd_commands(_: argparse.Namespace) -> None:
    emit(
        {
            "ok": True,
            "tool": "studio",
            "commands": [
                {"name": "commands", "purpose": "List commands (this output)."},
                {
                    "name": "roster",
                    "purpose": "Canonical role→UUID map. Use before assigning.",
                    "example": "studio roster",
                },
                {
                    "name": "verify-done",
                    "purpose": "Gate before PATCH done: file exists + length-profile min words (+ craft_lint for scenes).",
                    "example": "studio verify-done --path `{workspace_abs}/manuscript/scenes/SCENE-001.md`",
                },
                {
                    "name": "start-book",
                    "purpose": "Bootstrap a new book: board project + workspace seed + parent issue (+ optional Intake/git).",
                    "example": "studio start-book --title 'The Last Box' --prompt-file prompt.txt --format short_story --assign-intake",
                },
                {
                    "name": "profiles",
                    "purpose": "List manuscript length profiles (short_story/novelette/novella/novel) and scene floors.",
                    "example": "studio profiles",
                },
                {
                    "name": "create-issue",
                    "purpose": "Create a fully assigned issue with role enum (resolves UUID).",
                    "example": "studio create-issue --slug tide-ledger --role drafting_author --title 'Draft SCENE-007' --work draft --unit SCENE-007",
                },
                {
                    "name": "reassign",
                    "purpose": "Fix wrong assignee via role enum (resolves UUID).",
                    "example": "studio reassign --issue GHO-131 --role drafting_author",
                },
                {
                    "name": "reopen-parent",
                    "purpose": "Clear mistaken blockedBy and set BOOK parent in_progress.",
                    "example": "studio reopen-parent --issue GHO-108",
                },
                {
                    "name": "handoff",
                    "purpose": "Atomic handoff: verify unit, create Git sync + next creative issue, update CURRENT_STAGE.",
                    "example": "studio handoff --slug tide-ledger --after SCENE-006 --next-unit SCENE-007",
                },
                {
                    "name": "git-sync",
                    "purpose": "Mirror workspace→GitHub and require successful push.",
                    "example": "studio git-sync --slug tide-ledger --message 'Tide Ledger: sync after SCENE-006'",
                },
                {
                    "name": "watchdog",
                    "purpose": "One structured board snapshot + single recommended action (no pagination).",
                    "example": "studio watchdog --slug tide-ledger",
                },
                {
                    "name": "pack",
                    "purpose": "ONE slim role/work context pack (job card + files). Prefer over many reads.",
                    "example": "studio pack --slug <book> --role drafting_author --work draft --unit SCENE-013",
                },
                {
                    "name": "works",
                    "purpose": "List stage/work modes for pack/create-issue (draft, craft_audit, beat_sheet, ...).",
                    "example": "studio works",
                },
            ],
            "exit_codes": {"0": "success", "1": "operational failure", "2": "usage error"},
            "guidance": "On failure, read issue+guidance. Do not invent alternate curl workflows.",
        }
    )


def cmd_roster(args: argparse.Namespace) -> None:
    agents = fetch_agents(args.company_id, args.token)
    by_name: Dict[str, Dict[str, Any]] = {}
    for key in sorted(set(ROLE_ALIASES.keys())):
        display = ROLE_ALIASES[key]
        a = agents.get(display)
        row = {
            "name": display,
            "agent_id": a["id"] if a else None,
            "status": a.get("status") if a else "NOT_HIRED",
            "hired": bool(a),
            "role_keys": sorted(k for k, d in ROLE_ALIASES.items() if d == display),
        }
        by_name[display] = row
    emit(
        {
            "ok": True,
            "company_id": args.company_id,
            "agents": [by_name[n] for n in sorted(by_name)],
            "work_role_map": WORK_ROLE,
            "guidance": (
                "When creating issues, pass --role <role_key> to studio create-issue / handoff. "
                "Never guess UUIDs. Draft/redraft prose MUST use drafting_author."
            ),
        }
    )


def run_craft_lint(path: Path) -> Dict[str, Any]:
    """Stage-1 mechanical gate for manuscript scenes."""
    script = Path(__file__).resolve().parent / "craft_lint.py"
    if not script.exists():
        script = detect_repo() / "tools" / "craft_lint.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--path", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as e:
        return {"ok": False, "error": "craft_lint_exec_failed", "issue": str(e)}
    try:
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        payload = {
            "ok": False,
            "error": "craft_lint_bad_json",
            "raw": (proc.stdout or "")[:1000],
            "stderr": (proc.stderr or "")[:500],
        }
    payload["exit_code"] = proc.returncode
    if proc.returncode != 0:
        payload["ok"] = False
    return payload


def craft_audit_path(ws: Path, unit: str) -> Path:
    return ws / "reviews" / f"{unit.upper()}_craft_audit.json"


def target_reader_path(ws: Path, unit: str) -> Path:
    return ws / "reviews" / f"{unit.upper()}_target_reader.md"


def read_craft_audit(ws: Path, unit: str) -> Optional[Dict[str, Any]]:
    p = craft_audit_path(ws, unit)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"approved": False, "verdict": "REVISE", "error": "invalid_json", "path": str(p)}
    if not isinstance(data, dict):
        return {"approved": False, "verdict": "REVISE", "error": "not_object", "path": str(p)}
    verdict = str(data.get("verdict") or "").upper().strip()
    if not verdict:
        if data.get("approved") is True:
            verdict = "PASS"
        elif data.get("approved") is False:
            verdict = "REVISE"
        else:
            verdict = "REVISE"
    if verdict not in ("PASS", "REVISE"):
        verdict = "REVISE"
        data["error"] = data.get("error") or "invalid_verdict"
    data["verdict"] = verdict
    data["approved"] = verdict == "PASS" and not data.get("error")
    # Soft structural checks — do not invent quotes; flag thin evidence for REVISE.
    quotes = data.get("quotes") if isinstance(data.get("quotes"), list) else []
    findings = data.get("findings") if isinstance(data.get("findings"), list) else []
    for f in findings:
        if isinstance(f, dict):
            q = f.get("quotes")
            if isinstance(q, list):
                quotes = list(quotes) + [x for x in q if x]
    quotes = [q for q in quotes if isinstance(q, str) and q.strip()]
    data["_quote_count"] = len(quotes)
    dtc = data.get("desire_to_continue")
    try:
        data["desire_to_continue"] = int(dtc) if dtc is not None else None
    except Exception:
        data["desire_to_continue"] = None
    if verdict == "PASS":
        if len(quotes) < 2 or data.get("desire_to_continue") is None:
            # Prefer evidence over rubber stamps; treat as not yet approved.
            data["approved"] = False
            data["error"] = data.get("error") or "pass_missing_evidence_or_score"
    return data


def craft_audit_is_pass(audit: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(audit, dict) or audit.get("error"):
        return False
    if str(audit.get("verdict") or "").upper() == "PASS" and audit.get("approved") is True:
        return True
    return False


def _scene_index(unit: Optional[str]) -> Optional[int]:
    if not unit:
        return None
    m = re.match(r"^SCENE-(\d+)$", str(unit).upper())
    return int(m.group(1)) if m else None


def _enrich_book_reader_cadence(book: Dict[str, Any], ws: Path) -> Dict[str, Any]:
    out = dict(book)
    try:
        prof = resolve_profile_for_workspace(ws)
    except Exception:
        prof = {}
    if "target_reader_cadence" not in out and prof:
        out["target_reader_cadence"] = prof.get("target_reader_cadence")
    if "early_reader_after_scene" not in out and prof:
        out["early_reader_after_scene"] = prof.get("early_reader_after_scene")
    if "workflow_profile" not in out and prof:
        out["workflow_profile"] = prof.get("key") or out.get("format")
    return out


def early_reader_required(book: Dict[str, Any], ws: Path, unit: str) -> bool:
    """Short-story early checkpoint after opening scene (never later than scene 2)."""
    profile = str(book.get("workflow_profile") or book.get("format") or "").lower()
    cadence = str(book.get("target_reader_cadence") or "").lower()
    shortish = profile in ("short_story", "short", "ss", "short-story")
    cadence_hit = cadence in ("after_opening", "opening", "first_two", "early")
    if not (shortish or cadence_hit):
        return False
    n = _scene_index(unit)
    if n is None:
        return False
    after = book.get("early_reader_after_scene")
    try:
        after_n = int(after) if after is not None else 1
    except Exception:
        after_n = 1
    after_n = max(1, min(after_n, 2))
    if n != after_n:
        return False
    for p in (
        ws / "reviews" / "EARLY_READER_CHECKPOINT.md",
        target_reader_path(ws, f"SCENE-{after_n:03d}"),
        target_reader_path(ws, unit),
    ):
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace").lower()
            if any(
                re.search(rf"\b{v}\b", txt)
                for v in ("continue", "revise_opening", "re_outline", "stop_project")
            ):
                return False
    return True


def early_reader_blocks_next_draft(ws: Path, book: Dict[str, Any]) -> Optional[str]:
    """Return blocking reason if early reader said revise/re_outline/stop."""
    after = book.get("early_reader_after_scene")
    try:
        after_n = int(after) if after is not None else 1
    except Exception:
        after_n = 1
    paths = [
        ws / "reviews" / "EARLY_READER_CHECKPOINT.md",
        target_reader_path(ws, f"SCENE-{after_n:03d}"),
    ]
    for p in paths:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        low = txt.lower()
        for bad in ("stop_project", "re_outline", "revise_opening"):
            if re.search(rf"\b{bad}\b", low):
                return f"{p.name}:{bad}"
    return None


def cmd_verify_done(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.is_absolute():
        fail(
            "path_not_absolute",
            f"Path is not absolute: {path}",
            "Pass an absolute path under `{workspace_abs}/`...",
            path=str(path),
        )
    write_root = (getattr(args, "write_root", None) or "").strip() or None
    bad = path_is_forbidden_deliverable(path, write_root=write_root, company_id=CID_DEFAULT)
    if bad:
        fail(
            bad,
            f"Deliverable path rejected ({bad}): {path}",
            "Write/verify only under the project _default write_root from pack. Never /tmp, repos checkout, or doubled company paths.",
            path=str(path),
            write_root=write_root,
        )
    if not path.exists():
        fail(
            "file_missing",
            f"Required file does not exist: {path}",
            "Do NOT mark the issue done. Write the file first, or leave in_progress/blocked.",
            path=str(path),
        )
    if not path.is_file():
        fail("not_a_file", f"Path exists but is not a file: {path}", "Point --path at the artifact file.", path=str(path))
    words = word_count(path)
    is_scene = "/manuscript/scenes/" in str(path) and path.name.upper().startswith("SCENE-")
    if getattr(args, "min_words", None) is None:
        min_words = resolve_scene_min_words(path=path)
    else:
        min_words = int(args.min_words)
    profile_meta = None
    try:
        from length_profiles import discover_workspace_from_path

        _ws = discover_workspace_from_path(path)
        if _ws is not None:
            profile_meta = resolve_profile_for_workspace(_ws)
    except Exception:
        profile_meta = None
    if is_scene and not getattr(args, "skip_craft_lint", False):
        lint = run_craft_lint(path)
        if not lint.get("ok"):
            fail(
                "craft_lint_failed",
                f"Stage-1 craft lint failed for {path}",
                lint.get("guidance")
                or "Redraft to remove mantra loops / duplicate paragraphs / SVO inventory prose, then re-run verify-done.",
                path=str(path),
                words=words,
                craft_lint=lint,
            )
    if words < min_words:
        fail(
            "wordcount_too_low",
            f"{path} has {words} words; minimum is {min_words}"
            + (f" (profile {profile_meta.get('key')})" if isinstance(profile_meta, dict) and profile_meta.get("key") else "")
            + ".",
            "File may be an empty/seed template or below the length-profile scene floor. Keep issue in_progress and finish the artifact.",
            path=str(path),
            words=words,
            min_words=min_words,
            length_profile=(profile_meta or {}).get("key") if isinstance(profile_meta, dict) else None,
        )
    if args.not_identical_to:
        other = Path(args.not_identical_to)
        if other.exists() and other.is_file():
            a = path.read_text(encoding="utf-8", errors="replace")
            b = other.read_text(encoding="utf-8", errors="replace")
            if a.strip() == b.strip():
                fail(
                    "duplicate_content",
                    f"{path} is identical to {other}.",
                    "Rewrite with distinct content matching the scene contract before marking done.",
                    path=str(path),
                    other=str(other),
                )

    try:
        from role_packs import empty_required_sections, required_sections_for_rel
    except ImportError:  # pragma: no cover
        from tools.role_packs import empty_required_sections, required_sections_for_rel  # type: ignore

    rel_guess = path.name
    s = str(path).replace("\\", "/")
    for marker in (
        "/00_admin/",
        "/development/",
        "/bible/",
        "/structure/",
        "/outline/",
        "/reviews/",
        "/release/",
        "/manuscript/",
    ):
        if marker in s:
            rel_guess = marker.lstrip("/") + s.split(marker, 1)[1]
            break
    req_sections = required_sections_for_rel(rel_guess)
    if req_sections and path.suffix.lower() in {".md", ".markdown"}:
        body_text = path.read_text(encoding="utf-8", errors="replace")
        empty_sections = empty_required_sections(body_text, req_sections)
        if empty_sections:
            fail(
                "required_sections_empty",
                f"{path} has empty/missing required sections: {', '.join(empty_sections)}",
                "Fill each required H2 section with real content, then re-run verify-done. Do NOT mark done.",
                path=str(path),
                empty_sections=empty_sections,
                required_sections=req_sections,
            )

    guidance = "Verification passed. You may PATCH done and include these numbers in your comment."
    if is_scene:
        guidance = (
            "Stage-1 craft lint passed. PATCH draft done, then Managing Editor must route "
            "Developmental Reviewer (Craft Auditor) for Stage-2 semantic JSON before next-scene handoff."
        )
    emit(
        {
            "ok": True,
            "verified": True,
            "path": str(path),
            "words": words,
            "min_words": min_words,
            "length_profile": (profile_meta or {}).get("key") if isinstance(profile_meta, dict) else None,
            "craft_lint_required": bool(is_scene),
            "guidance": guidance,
        }
    )


def cmd_create_issue(args: argparse.Namespace) -> None:
    if not args.role and not args.work:
        usage_fail(
            issue="Provide --role and/or --work.",
            guidance="For prose drafts use --work draft (forces drafting_author).",
            valid_work=sorted(WORK_ROLE.keys()),
            valid_roles=sorted(set(ROLE_ALIASES.keys())),
        )
    repo = detect_repo()
    book = resolve_book(repo, slug=args.slug, project_id=args.project_id)
    project_id = book["project_id"]
    cid = args.company_id
    abs_ws = absolute_ws(book, cid)
    ws = workspace_for(book, cid)
    book = enrich_book_from_workspace(book, ws)

    work = args.work
    role_key = normalize_role(args.role) if args.role else None
    if work:
        work = work.strip().lower().replace("-", "_")
        if work not in WORK_ROLE:
            usage_fail(issue=f"Unknown --work '{args.work}'.", guidance="Choose from valid_work.", valid_work=sorted(WORK_ROLE.keys()))
        required = WORK_ROLE[work]
        if role_key and role_key != required:
            fail(
                "role_work_mismatch",
                f"--work {work} requires role '{required}', but --role was '{role_key}'.",
                f"Omit --role, or pass --role {required}.",
                required_role=required,
                provided_role=role_key,
            )
        role_key = required
    assert role_key

    if (
        work in ("draft", "redraft", "revision_prose")
        or re.search(r"\bDraft SCENE|\bRedraft SCENE", args.title, re.I)
    ) and role_key != "drafting_author":
        fail(
            "prose_requires_drafting_author",
            "Prose draft/redraft issues must be assigned to drafting_author.",
            "Re-run with --role drafting_author (or --work draft).",
            title=args.title,
            role=role_key,
        )

    agents = fetch_agents(cid, args.token)
    agent = role_to_agent(role_key, agents)
    parent_id = args.parent_id or find_parent_issue(cid, project_id, args.token)["id"]

    description = args.description
    if not description:
        if work == "git_sync" or (role_key == "studio_administrator" and (work in (None, "git_sync") or not work)):
            description = _sync_desc(abs_ws, book, args.after or args.unit or "stage")
        else:
            # Embed the exact one primary studio call (pack / watchdog / git-sync).
            description = _assignment_desc(
                abs_ws,
                book,
                parent_id,
                role_key,
                work,
                args.unit,
                workspace=ws,
                title_hint=args.title,
            )

    if args.dry_run:
        emit(
            {
                "ok": True,
                "dry_run": True,
                "would_create": {
                    "title": args.title,
                    "role": role_key,
                    "assigneeAgentId": agent["id"],
                    "assigneeName": agent["name"],
                    "projectId": project_id,
                    "parentId": parent_id,
                    "status": "todo",
                },
                "guidance": "Dry run only. Re-run without --dry-run to create.",
            }
        )

    issue = api(
        "POST",
        f"/api/companies/{cid}/issues",
        {
            "title": args.title,
            "description": description,
            "status": "todo",
            "projectId": project_id,
            "parentId": parent_id,
            "assigneeAgentId": agent["id"],
        },
        token=args.token,
    )
    emit(
        {
            "ok": True,
            "created": True,
            "issue": {
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "title": issue.get("title"),
                "status": issue.get("status"),
                "assigneeAgentId": issue.get("assigneeAgentId"),
                "assigneeName": agent["name"],
                "role": role_key,
                "projectId": project_id,
                "parentId": parent_id,
            },
            "guidance": (
                f"Created {issue.get('identifier')}. Optionally wake assignee via "
                f"POST /api/agents/{agent['id']}/wakeup. Do not reassign to a different role."
            ),
        }
    )



STAGE_HANDOFF_NEXT = {
    "intake": ("creative_brief", "story_architect", "Creative Brief", "creative_brief", None),
    "creative_brief": ("premise", "story_architect", "Premise", "premise", "development/CREATIVE_BRIEF.md"),
    "premise": ("story_bible", "story_architect", "Story Bible", "story_bible", "development/PREMISE_PACKAGE.md"),
    "story_bible": ("ending", "story_architect", "Ending Design", "ending", "bible/STORY_BIBLE.md"),
    "ending": ("beat_sheet", "story_architect", "Beat Sheet", "beat_sheet", "bible/ENDING_DESIGN.md"),
    "beat_sheet": ("scene_outline", "scene_planner", "Scene Outline", "scene_outline", "structure/BEAT_SHEET.md"),
    "scene_outline": ("draft", "drafting_author", "Draft SCENE-001", "drafting", "structure/SCENE_OUTLINE.md"),
}


def _stamp_artifact_approved(path: Path, *, by: str = "managing_editor") -> bool:
    if not path.is_file():
        return False
    raw = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r'(?im)^status:\s*"?APPROVED"?\s*$', raw):
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new = raw
    if re.search(r"(?im)^status:\s*", new):
        new = re.sub(r"(?im)^status:\s*.*$", 'status: "APPROVED"', new, count=1)
    if re.search(r"(?im)^approved_by:\s*", new):
        new = re.sub(r"(?im)^approved_by:\s*.*$", f'approved_by: "{by}"', new, count=1)
    else:
        new = re.sub(r'(?im)^status:\s*"APPROVED"\s*$', f'status: "APPROVED"\napproved_by: "{by}"', new, count=1)
    if re.search(r"(?im)^approved_at:\s*", new):
        new = re.sub(r"(?im)^approved_at:\s*.*$", f'approved_at: "{today}"', new, count=1)
    else:
        new = re.sub(r"(?im)^approved_by:\s*.*$", f'approved_by: "{by}"\napproved_at: "{today}"', new, count=1)
    if new != raw:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def _update_stage_files(ws: Path, *, stage: str, notes: str = "") -> None:
    admin = ws / "00_admin"
    admin.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (admin / "CURRENT_STAGE.md").write_text(
        f"""---
artifact_id: "current-stage"
title: "Current Stage"
status: "APPROVED"
approved_by: "managing_editor"
approved_at: "{today}"
---
# Current Stage
- Stage: {stage}
- Status: in_progress
- Notes: {notes or "Updated by studio handoff."}
""",
        encoding="utf-8",
    )
    yaml_path = admin / "book.yaml"
    if yaml_path.is_file():
        y = yaml_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^current_stage:\s*", y):
            y2 = re.sub(r"(?m)^current_stage:\s*.*$", f'current_stage: "{stage}"', y, count=1)
        else:
            y2 = y.rstrip() + f"\ncurrent_stage: \"{stage}\"\n"
        if y2 != y:
            yaml_path.write_text(y2, encoding="utf-8")


def _create_stage_child(
    *,
    cid: str,
    token: Optional[str],
    project_id: str,
    parent_id: str,
    abs_ws: str,
    ws: Path,
    book: Dict[str, Any],
    agents: Dict[str, Any],
    work: str,
    role_key: str,
    title: str,
    unit: Optional[str] = None,
) -> Dict[str, Any]:
    agent = role_to_agent(role_key, agents)
    desc = _assignment_desc(
        abs_ws,
        book,
        parent_id,
        role_key,
        work,
        unit,
        workspace=ws,
        title_hint=title,
    )
    return api(
        "POST",
        f"/api/companies/{cid}/issues",
        {
            "title": title,
            "description": desc,
            "status": "todo",
            "projectId": project_id,
            "parentId": parent_id,
            "assigneeAgentId": agent["id"],
        },
        token=token,
    )


def cmd_handoff(args: argparse.Namespace) -> None:
    after_raw = (args.after or "").strip()
    after_key = after_raw.lower().replace("-", "_")
    stage_handoffs = {"intake", "creative_brief", "premise", "story_bible", "ending", "beat_sheet", "scene_outline"}
    if after_key not in stage_handoffs and not args.next_unit and not args.next_title and not args.skip_next:
        usage_fail(
            issue="Provide --next-unit (e.g. SCENE-007) or --next-title, or pass --skip-next.",
            guidance="Atomic handoff needs the next creative issue unless --skip-next (rare). For Intake use --after intake.",
        )

    repo = detect_repo()
    book = resolve_book(repo, slug=args.slug, project_id=args.project_id)
    cid = args.company_id
    project_id = book["project_id"]
    abs_ws = absolute_ws(book, cid)
    ws = workspace_for(book, cid)
    book = enrich_book_from_workspace(book, ws)
    parent_id = args.parent_id or find_parent_issue(cid, project_id, args.token)["id"]
    agents = fetch_agents(cid, args.token)

    # Stage handoffs: prior stage → next creative (+ Git sync) with first-call embeds.
    if after_key in STAGE_HANDOFF_NEXT:
        title = book.get("working_title") or book.get("book_slug")
        next_work, next_role, title_prefix, next_stage, prior_rel = STAGE_HANDOFF_NEXT[after_key]
        sa = role_to_agent("studio_administrator", agents)
        unit = "SCENE-001" if next_work == "draft" else None
        content_title = args.next_title or f"{title_prefix} — {title}"
        sync_title = f"Git sync — {title} after {after_raw}"
        if args.dry_run:
            emit(
                {
                    "ok": True,
                    "dry_run": True,
                    "after": after_key,
                    "would_create": [
                        {"title": content_title, "role": next_role, "work": next_work, "unit": unit},
                        {"title": sync_title, "role": "studio_administrator", "work": "git_sync"},
                    ],
                    "next_stage": next_stage,
                    "guidance": "Dry run only. Re-run without --dry-run to create issues.",
                }
            )
        content_issue = _create_stage_child(
            cid=cid,
            token=args.token,
            project_id=project_id,
            parent_id=parent_id,
            abs_ws=abs_ws,
            ws=ws,
            book=book,
            agents=agents,
            work=next_work,
            role_key=next_role,
            title=content_title,
            unit=unit,
        )
        sync_issue = api(
            "POST",
            f"/api/companies/{cid}/issues",
            {
                "title": sync_title,
                "description": _sync_desc(abs_ws, book, after_raw),
                "status": "todo",
                "projectId": project_id,
                "parentId": parent_id,
                "assigneeAgentId": sa["id"],
            },
            token=args.token,
        )
        try:
            api("PATCH", f"/api/issues/{parent_id}", {"status": "in_progress"}, token=args.token)
        except Exception:
            pass
        stamped = False
        if prior_rel:
            stamped = _stamp_artifact_approved(ws / prior_rel)
        _update_stage_files(
            ws,
            stage=next_stage,
            notes=(
                f"studio handoff after {after_key}: "
                f"{content_issue.get('identifier')} + {sync_issue.get('identifier')}"
            ),
        )
        emit(
            {
                "ok": True,
                "command": "handoff",
                "after": after_key,
                "parent_id": parent_id,
                "next_stage": next_stage,
                "stamped_prior_artifact": stamped,
                "content_issue": {
                    "id": content_issue.get("id"),
                    "identifier": content_issue.get("identifier"),
                    "role": next_role,
                    "work": next_work,
                },
                "git_sync_issue": {
                    "id": sync_issue.get("id"),
                    "identifier": sync_issue.get("identifier"),
                    "assignee": sa.get("name"),
                },
                "guidance": (
                    f"Stage handoff after {after_key} created. Wake the content assignee and "
                    "Studio Administrator. Parent stays in_progress. EXIT."
                ),
            }
        )


    verify = None
    unit = None
    if re.match(r"^SCENE-\d+$", after_raw.upper()):
        unit = args.after.upper()
        path = ws / "manuscript" / "scenes" / f"{unit}.md"
        abs_path = f"{abs_ws}/manuscript/scenes/{unit}.md"
        if not path.exists():
            fail(
                "completed_unit_missing",
                f"Cannot hand off after {unit}: file missing at {path}",
                "Do not create the next draft until the completed unit exists. Reassign current draft to drafting_author.",
                expected_path=abs_path,
            )
        # Stage-1 mechanical gate (craft_lint) for scene units
        lint = run_craft_lint(path)
        if not lint.get("ok"):
            fail(
                "craft_lint_failed",
                f"Cannot hand off after {unit}: Stage-1 craft lint failed.",
                "Create/reassign a redraft to drafting_author. Do not advance.",
                path=abs_path,
                craft_lint=lint,
            )
        words = word_count(path)
        min_words = (
            int(args.min_words)
            if getattr(args, "min_words", None) is not None
            else resolve_scene_min_words(workspace=ws, book_yaml=book)
        )
        if words < min_words:
            fail(
                "completed_unit_too_short",
                f"{unit} has only {words} words; minimum is {min_words}.",
                "Treat current unit as incomplete; do not advance.",
                path=abs_path,
                words=words,
                min_words=min_words,
            )
        verify = {"path": abs_path, "words": words, "craft_lint": {"ok": True, "metrics": lint.get("metrics")}}

    sa = role_to_agent("studio_administrator", agents)
    sync_title = f"Git sync — {book.get('working_title') or book['book_slug']} after {args.after}"

    # Stage-2 gate: require Craft Auditor approval before creating next draft.
    audit = None
    need_craft_audit = False
    if unit and re.match(r"^SCENE-\d+$", unit) and not args.skip_next:
        audit = read_craft_audit(ws, unit)
        if not craft_audit_is_pass(audit):
            need_craft_audit = True

    if args.dry_run:
        emit(
            {
                "ok": True,
                "dry_run": True,
                "verified_unit": verify,
                "craft_audit": audit,
                "would_create": [
                    {"title": sync_title, "role": "studio_administrator", "assigneeAgentId": sa["id"]},
                    (
                        {
                            "title": f"Craft audit {unit} — {book.get('working_title') or book['book_slug']}",
                            "role": "developmental_reviewer",
                        }
                        if need_craft_audit
                        else (
                            None
                            if args.skip_next
                            else {
                                "title": args.next_title
                                or f"Draft {(args.next_unit or 'SCENE-XXX').upper()} — {book.get('working_title') or book['book_slug']}",
                                "role": "drafting_author",
                            }
                        )
                    ),
                ],
                "guidance": "Dry run only. Re-run without --dry-run to create issues.",
            }
        )

    sync_issue = api(
        "POST",
        f"/api/companies/{cid}/issues",
        {
            "title": sync_title,
            "description": _sync_desc(abs_ws, book, args.after),
            "status": "todo",
            "projectId": project_id,
            "parentId": parent_id,
            "assigneeAgentId": sa["id"],
        },
        token=args.token,
    )

    next_issue = None
    next_role = None
    if not args.skip_next:
        if need_craft_audit:
            rev = role_to_agent("developmental_reviewer", agents)
            next_role = "developmental_reviewer"
            next_title = f"Craft audit {unit} — {book.get('working_title') or book['book_slug']}"
            next_desc = _assignment_desc(
                abs_ws,
                book,
                parent_id,
                "developmental_reviewer",
                "craft_audit",
                unit,
                workspace=ws,
                title_hint=next_title,
            ) + (
                "\n\n## Reviewer model\n"
                "Use DeepSeek V4.1 Flash (`studio-coordinator`). Do not use the drafting model.\n"
                "Inputs ONLY: Creative Brief, Style Guide, scene contract, draft. "
                "No drafter self-evaluation.\n"
                "JSON must include verdict PASS|REVISE, 2–5 quotes, desire_to_continue 1–5, "
                "reader_effect + minimum_correction per finding. No rewritten prose.\n"
            )
            next_issue = api(
                "POST",
                f"/api/companies/{cid}/issues",
                {
                    "title": next_title,
                    "description": next_desc,
                    "status": "todo",
                    "projectId": project_id,
                    "parentId": parent_id,
                    "assigneeAgentId": rev["id"],
                },
                token=args.token,
            )
        else:
            book = _enrich_book_reader_cadence(book, ws)
            need_early = bool(unit and re.match(r"^SCENE-\d+$", unit) and early_reader_required(book, ws, unit))
            block = None if need_early else early_reader_blocks_next_draft(ws, book)
            if block:
                fail(
                    "early_reader_blocked",
                    f"Early reader checkpoint blocks further drafting ({block}).",
                    "Honor revise_opening / re_outline / stop_project before creating the next draft.",
                    blocker=block,
                )
            if need_early:
                tr = role_to_agent("target_reader_reviewer", agents)
                next_role = "target_reader_reviewer"
                next_title = (
                    f"Early reader checkpoint after {unit} — "
                    f"{book.get('working_title') or book['book_slug']}"
                )
                next_desc = _assignment_desc(
                    abs_ws,
                    book,
                    parent_id,
                    "target_reader_reviewer",
                    "target_reader",
                    unit,
                    workspace=ws,
                    title_hint=next_title,
                ) + (
                    "\n\n## Required checkpoint verdict\n"
                    "Exactly one of: `continue` | `revise_opening` | `re_outline` | `stop_project`.\n"
                    "Also include desire-to-continue score 1–5. No rewritten manuscript prose.\n"
                    f"Write `{abs_ws}/reviews/EARLY_READER_CHECKPOINT.md` AND "
                    f"`{abs_ws}/reviews/{unit}_target_reader.md`.\n"
                )
                next_issue = api(
                    "POST",
                    f"/api/companies/{cid}/issues",
                    {
                        "title": next_title,
                        "description": next_desc,
                        "status": "todo",
                        "projectId": project_id,
                        "parentId": parent_id,
                        "assigneeAgentId": tr["id"],
                    },
                    token=args.token,
                )
            else:
                da = role_to_agent("drafting_author", agents)
                next_role = "drafting_author"
                next_unit = (args.next_unit or "SCENE-XXX").upper()
                next_title = args.next_title or (
                    f"Draft {next_unit} — {book.get('working_title') or book['book_slug']}"
                )
                next_issue = api(
                    "POST",
                    f"/api/companies/{cid}/issues",
                    {
                        "title": next_title,
                        "description": args.next_description
                        or _draft_desc(abs_ws, next_unit, book, parent_id, workspace=ws),
                        "status": "todo",
                        "projectId": project_id,
                        "parentId": parent_id,
                        "assigneeAgentId": da["id"],
                    },
                    token=args.token,
                )

    stage_path = ws / "00_admin" / "CURRENT_STAGE.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    active = next_issue.get("identifier") if next_issue else "none"
    if next_role == "developmental_reviewer":
        assignee_label = "Craft Auditor"
    elif next_role == "target_reader_reviewer":
        assignee_label = "Target Reader"
    else:
        assignee_label = "Drafting Author"
    if need_craft_audit:
        stage_label = f"craft_audit ({unit})"
    elif next_role == "target_reader_reviewer":
        stage_label = f"early_reader ({unit})"
    else:
        stage_label = f"drafting ({args.next_unit or 'next unit'})"
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.write_text(
        f"""---
schema_version: "0.1.0"
artifact_id: "current-stage"
title: "Current Stage"
status: "APPROVED"
version: 1
canonical: false
authoring_agent: "studio_cli"
created_at: "{now}"
approved_by: "managing_editor"
approved_at: "{now}"
depends_on: []
book_id: "{book.get('book_id')}"
project_id: "{project_id}"
---

# Current Stage

- Stage: {stage_label}
- Active issue: {active}
- Assignee: {assignee_label}
- Blockers: none
- Parallel: {sync_issue.get('identifier')} — Git sync after {args.after}
- Notes: Atomic handoff via `studio handoff` at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}. Parent stays in_progress.
""",
        encoding="utf-8",
    )

    parent = api("GET", f"/api/issues/{parent_id}", token=args.token)
    comment = (
        f"studio handoff after {args.after}: created {sync_issue.get('identifier')}"
        + (f" + {next_issue.get('identifier')}" if next_issue else "")
        + (
            "; waiting Craft Auditor Stage-2"
            if need_craft_audit
            else ("; waiting Early Reader checkpoint" if next_role == "target_reader_reviewer" else "")
        )
        + ". Parent stays in_progress (delegated follow-ups)."
    )
    patch: Dict[str, Any] = {"comment": comment}
    if parent and parent.get("status") in ("blocked", "done", "cancelled", "canceled"):
        patch["status"] = "in_progress"
    api("PATCH", f"/api/issues/{parent_id}", patch, token=args.token)

    emit(
        {
            "ok": True,
            "handoff": True,
            "verified_unit": verify,
            "craft_audit_required": need_craft_audit,
            "craft_audit": audit,
            "early_reader_required": bool(next_role == "target_reader_reviewer"),
            "git_sync_issue": {
                "id": sync_issue.get("id"),
                "identifier": sync_issue.get("identifier"),
                "assigneeAgentId": sa["id"],
                "assigneeName": sa["name"],
            },
            "next_issue": (
                {
                    "id": next_issue.get("id"),
                    "identifier": next_issue.get("identifier"),
                    "title": next_issue.get("title"),
                    "assigneeAgentId": next_issue.get("assigneeAgentId"),
                    "assigneeName": assignee_label,
                    "role": next_role,
                }
                if next_issue
                else None
            ),
            "current_stage_path": f"{abs_ws}/00_admin/CURRENT_STAGE.md",
            "parent_id": parent_id,
            "guidance": (
                "Atomic handoff complete. EXIT this heartbeat. "
                "Do not write manuscript prose. Do not paginate issues."
            ),
        }
    )


def cmd_git_sync(args: argparse.Namespace) -> None:
    if not args.slug and not args.all:
        usage_fail(
            issue="Provide --slug <book-slug> or --all.",
            guidance="Example: studio git-sync --slug tide-ledger --message 'Tide Ledger: sync after SCENE-006'",
        )
    repo = detect_repo()
    sync_script = repo / "tools" / "sync_book_to_github.py"
    if not sync_script.exists():
        fail("sync_script_missing", f"Missing {sync_script}", "Ensure tools/sync_book_to_github.py is mounted.")

    key = Path("/etc/ssh/github_ai_fiction_library_deploy")
    if key.exists() and not os.access(key, os.R_OK):
        fail(
            "deploy_key_unreadable",
            f"Deploy key exists but is not readable by uid={os.getuid()}: {key}",
            "Board/ops must chown the host key to uid 1000 (node) with mode 600. Do NOT mark sync done.",
            key=str(key),
            uid=os.getuid(),
        )

    cmd = ["python3", str(sync_script)]
    if args.all:
        cmd.append("--all")
    else:
        cmd.extend(["--slug", args.slug])
    if args.message:
        cmd.extend(["--message", args.message])
    if args.dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    if key.exists() and os.access(key, os.R_OK):
        env["GIT_SSH_COMMAND"] = f"ssh -i {key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

    proc = subprocess.run(cmd, cwd=str(repo), env=env, text=True, capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or "") + "\n" + (proc.stdout or "")
        guidance = "Inspect stderr. Common cause: deploy key permissions or network."
        if "Permission denied" in err and "github_ai_fiction_library_deploy" in err:
            guidance = "SSH deploy key unreadable. Board must fix host ownership to uid 1000. Leave sync blocked."
        fail(
            "git_sync_failed",
            "sync_book_to_github.py failed.",
            guidance,
            returncode=proc.returncode,
            stdout=(proc.stdout or "")[-2000:],
            stderr=(proc.stderr or "")[-2000:],
        )

    if args.dry_run:
        emit({"ok": True, "dry_run": True, "stdout_tail": (proc.stdout or "")[-1500:], "guidance": "Dry run only."})

    ahead = subprocess.run(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=str(repo), text=True, capture_output=True)
    ahead_n = int((ahead.stdout or "0").strip() or "0")
    if ahead_n > 0:
        fail(
            "push_not_confirmed",
            f"Local branch is still ahead of origin/main by {ahead_n} commit(s).",
            "Push did not land. Fix credentials and re-run studio git-sync. Do not mark done.",
            ahead=ahead_n,
            stdout=(proc.stdout or "")[-1500:],
        )
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo), text=True, capture_output=True).stdout.strip()
    remote_sha = subprocess.run(
        ["git", "rev-parse", "--short", "origin/main"], cwd=str(repo), text=True, capture_output=True
    ).stdout.strip()
    emit(
        {
            "ok": True,
            "synced": True,
            "local_sha": sha,
            "remote_sha": remote_sha,
            "push_confirmed": sha == remote_sha,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "guidance": "Push confirmed. Comment SHA on the sync issue and PATCH done.",
        }
    )


def cmd_reassign(args: argparse.Namespace) -> None:
    if not args.issue:
        usage_fail(issue="--issue is required.", guidance="Example: studio reassign --issue GHO-131 --role drafting_author")
    if not args.role and not args.work:
        usage_fail(
            issue="Provide --role and/or --work.",
            guidance="For draft/redraft prose use --role drafting_author (or --work draft).",
            valid_roles=sorted(set(ROLE_ALIASES.keys())),
            valid_work=sorted(WORK_ROLE.keys()),
        )
    role_key = normalize_role(args.role) if args.role else None
    if args.work:
        work = args.work.strip().lower().replace("-", "_")
        if work not in WORK_ROLE:
            usage_fail(issue=f"Unknown --work '{args.work}'.", guidance="Choose from valid_work.", valid_work=sorted(WORK_ROLE.keys()))
        required = WORK_ROLE[work]
        if role_key and role_key != required:
            fail(
                "role_work_mismatch",
                f"--work {work} requires role '{required}', but --role was '{role_key}'.",
                f"Omit --role, or pass --role {required}.",
            )
        role_key = required
    assert role_key

    cid = args.company_id
    agents = fetch_agents(cid, args.token)
    agent = role_to_agent(role_key, agents)
    issue = find_issue(cid, args.issue, token=args.token, project_id=args.project_id)
    old_id = issue.get("assigneeAgentId")
    id_to_name = {a["id"]: n for n, a in agents.items()}
    old_name = id_to_name.get(old_id, old_id)

    # Safety: prose titles must go to drafting_author
    title = issue.get("title") or ""
    if re.search(r"\bDraft SCENE|\bRedraft SCENE", title, re.I) and role_key != "drafting_author":
        fail(
            "prose_requires_drafting_author",
            f"Issue '{issue.get('identifier')}' looks like prose draft but target role is '{role_key}'.",
            "Re-run with --role drafting_author (or --work draft).",
            title=title,
            role=role_key,
        )

    if old_id == agent["id"] and not args.force:
        emit(
            {
                "ok": True,
                "unchanged": True,
                "issue": {
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "title": title,
                    "assigneeAgentId": old_id,
                    "assigneeName": old_name,
                    "role": role_key,
                },
                "guidance": "Already assigned to that agent. Pass --force to comment anyway.",
            }
        )

    if args.dry_run:
        emit(
            {
                "ok": True,
                "dry_run": True,
                "would_reassign": {
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "from": {"id": old_id, "name": old_name},
                    "to": {"id": agent["id"], "name": agent["name"], "role": role_key},
                },
                "guidance": "Dry run only. Re-run without --dry-run to apply.",
            }
        )

    comment = args.comment or (
        f"studio reassign: {old_name or 'unassigned'} → {agent['name']} ({role_key})."
    )
    updated = api(
        "PATCH",
        f"/api/issues/{issue['id']}",
        {"assigneeAgentId": agent["id"], "comment": comment},
        token=args.token,
    )
    emit(
        {
            "ok": True,
            "reassigned": True,
            "issue": {
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "title": title,
                "status": (updated or issue).get("status"),
                "assigneeAgentId": agent["id"],
                "assigneeName": agent["name"],
                "role": role_key,
                "previousAssigneeAgentId": old_id,
                "previousAssigneeName": old_name,
            },
            "guidance": (
                f"Reassigned {issue.get('identifier')} to {agent['name']}. "
                f"Optionally wake via POST /api/agents/{agent['id']}/wakeup. EXIT after this mutation on timer wakes."
            ),
        }
    )



def cmd_reopen_parent(args: argparse.Namespace) -> None:
    cid = args.company_id
    issue = find_issue(cid, args.issue, token=args.token, project_id=args.project_id)
    if issue.get("parentId"):
        fail(
            "not_a_parent",
            f"{issue.get('identifier')} has a parentId — reopen-parent is for BOOK parents only.",
            "Use studio reassign / PATCH on the child instead.",
            issue_id=issue.get("id"),
        )
    blocked_ids = list(issue.get("blockedByIssueIds") or [])
    if not blocked_ids and issue.get("blockedBy"):
        blocked_ids = [b.get("id") for b in issue.get("blockedBy") if isinstance(b, dict) and b.get("id")]
    if args.dry_run:
        emit(
            {
                "ok": True,
                "dry_run": True,
                "would_patch": {
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "from_status": issue.get("status"),
                    "to_status": "in_progress",
                    "clear_blocked_by": blocked_ids,
                },
                "guidance": "Dry run only. Re-run without --dry-run to apply.",
            }
        )
    comment = args.comment or (
        "studio reopen-parent: clear mistaken blockedBy; parent stays in_progress until Final Audit."
    )
    updated = api(
        "PATCH",
        f"/api/issues/{issue['id']}",
        {"status": "in_progress", "blockedByIssueIds": [], "comment": comment},
        token=args.token,
    )
    emit(
        {
            "ok": True,
            "reopened": True,
            "issue": {
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "status": (updated or {}).get("status"),
                "previous_status": issue.get("status"),
                "cleared_blocked_by": blocked_ids,
            },
            "guidance": "Parent is in_progress. EXIT. Do not re-block on open draft children.",
        }
    )



def cmd_watchdog(args: argparse.Namespace) -> None:
    repo = detect_repo()
    book = resolve_book(repo, slug=args.slug, project_id=args.project_id)
    cid = args.company_id
    project_id = book["project_id"]
    abs_ws = absolute_ws(book, cid)
    ws = workspace_for(book, cid)
    book = enrich_book_from_workspace(book, ws)

    parent = find_parent_issue(cid, project_id, args.token)
    # List payloads often omit blockedBy; refetch full parent for disposition fields.
    parent = api("GET", f"/api/issues/{parent['id']}", token=args.token) or parent
    issues = api("GET", f"/api/companies/{cid}/issues?projectId={project_id}", token=args.token)
    if isinstance(issues, dict):
        issues = issues.get("issues") or issues.get("items") or issues.get("data") or []
    issues = [i for i in (issues or []) if i.get("projectId") == project_id]
    open_issues = [
        i
        for i in issues
        if i.get("status") in ("todo", "in_progress", "blocked", "queued", "backlog") and i.get("id") != parent.get("id")
    ]
    agents = fetch_agents(cid, args.token)
    id_to_name = {a["id"]: n for n, a in agents.items()}

    scenes = sorted((ws / "manuscript" / "scenes").glob("SCENE-*.md")) if (ws / "manuscript" / "scenes").exists() else []
    scene_stats = [{"name": p.name, "words": word_count(p)} for p in scenes]
    scene_floor = resolve_scene_min_words(workspace=ws, book_yaml=book)
    filled = [s for s in scene_stats if s["words"] >= scene_floor]
    last_unit = filled[-1]["name"].replace(".md", "") if filled else None
    open_sync = [i for i in open_issues if "git sync" in (i.get("title") or "").lower()]
    open_draft = [i for i in open_issues if re.search(r"Draft SCENE|Redraft SCENE", i.get("title") or "", re.I)]

    da_id = agents.get("Drafting Author", {}).get("id")
    wrong_role = []
    for i in open_draft:
        if da_id and i.get("assigneeAgentId") != da_id:
            wrong_role.append(
                {
                    "identifier": i.get("identifier"),
                    "title": i.get("title"),
                    "assignee": id_to_name.get(i.get("assigneeAgentId"), i.get("assigneeAgentId")),
                    "should_be": "Drafting Author",
                }
            )

    blocked_ids = list(parent.get("blockedByIssueIds") or [])
    if not blocked_ids and parent.get("blockedBy"):
        blocked_ids = [b.get("id") for b in parent.get("blockedBy") if isinstance(b, dict) and b.get("id")]
    # Open draft/sync/review children as blockedBy are a VALID the board disposition (stops parent thrash).
    productive_blockers = bool(blocked_ids) and all(
        any(
            i.get("id") == bid
            and re.search(r"Draft SCENE|Redraft SCENE|Git sync|Continuity|Review|Revision", i.get("title") or "", re.I)
            and i.get("status") in ("todo", "in_progress", "blocked", "queued", "backlog")
            for i in open_issues
        )
        for bid in blocked_ids
    )

    if parent.get("status") in ("done", "cancelled", "canceled") or (
        parent.get("status") == "blocked" and not blocked_ids
    ):
        recommendation = {
            "action": "reopen_parent",
            "command": (
                f"{studio_cli()} reopen-parent "
                f"--issue {parent.get('identifier') or parent.get('id')}"
            ),
            "reason": f"Parent is {parent.get('status')} without a valid blockedBy list.",
            "guidance": "Run reopen-parent once, then EXIT.",
            "parent_id": parent.get("id"),
            "blocked_by_issue_ids": blocked_ids,
        }
    elif wrong_role:
        first = wrong_role[0]
        recommendation = {
            "action": "fix_wrong_assignee",
            "command": (
                f"{studio_cli()} reassign "
                f"--issue {first['identifier']} --role drafting_author"
            ),
            "reason": "Open draft issue(s) assigned to someone other than Drafting Author.",
            "guidance": "Run the reassign command once, then EXIT. Do not write prose as ME.",
            "issues": wrong_role,
            "drafting_author_id": da_id,
        }
    elif open_draft:
        recommendation = {
            "action": "wait_or_wake_drafter",
            "command": None,
            "reason": "A draft issue is already open"
            + (" (parent blockedBy open children is OK)." if productive_blockers else "."),
            "guidance": "EXIT unless you need to wake Drafting Author. Do not self-write prose.",
            "open_drafts": [
                {
                    "identifier": i.get("identifier"),
                    "status": i.get("status"),
                    "assignee": id_to_name.get(i.get("assigneeAgentId")),
                    "title": i.get("title"),
                }
                for i in open_draft
            ],
        }
    elif last_unit and not open_sync and not open_draft:
        m = re.search(r"SCENE-(\d+)", last_unit)
        next_unit = f"SCENE-{int(m.group(1))+1:03d}" if m else "SCENE-XXX"
        recommendation = {
            "action": "handoff",
            "command": (
                f"{studio_cli()} handoff "
                f"--slug {book['book_slug']} --after {last_unit} --next-unit {next_unit}"
            ),
            "reason": f"Latest filled unit is {last_unit}; no open sync/draft issues.",
            "guidance": "Run the handoff command once, then EXIT.",
        }
    elif last_unit and not open_sync:
        recommendation = {
            "action": "create_git_sync",
            "command": (
                f"{studio_cli()} create-issue "
                f"--slug {book['book_slug']} --work git_sync --role studio_administrator "
                f"--title 'Git sync — {book.get('working_title') or book['book_slug']} after {last_unit}' "
                f"--after {last_unit}"
            ),
            "reason": "Workspace has manuscript units but no open Git sync issue.",
            "guidance": "Create sync (or full handoff). Do not paginate issue lists.",
        }
    else:
        recommendation = {
            "action": "exit_healthy",
            "command": None,
            "reason": "No clear single mutation from snapshot.",
            "guidance": "EXIT. Do not invent company-wide issue crawls or offset pagination.",
        }

    controlled = bool(book.get("controlled_test"))
    intervene_reasons = []
    if parent.get("status") == "in_review":
        intervene_reasons.append("parent_in_review")
    ra = parent.get("reviewAttention") or {}
    if isinstance(ra, dict):
        blob = json.dumps(ra).lower()
        if "confirmation" in blob or "request_confirmation" in blob:
            intervene_reasons.append("pending_confirmation")
    bare = []
    for i in open_issues:
        desc = i.get("description") or ""
        title_l = (i.get("title") or "").lower()
        if "git sync" in title_l and "git-sync" in desc:
            continue
        if "First tool call" not in desc or "write_root" not in desc.lower():
            bare.append(i.get("identifier") or i.get("id"))
    if bare:
        intervene_reasons.append("bare_issue_description:" + ",".join(str(x) for x in bare[:5]))
    blocked_sync = [
        i
        for i in open_sync
        if i.get("status") == "blocked"
        or "read-only" in ((i.get("title") or "") + (i.get("description") or "")).lower()
    ]
    if blocked_sync:
        intervene_reasons.append("git_sync_permission_blocker")
    for i in open_issues:
        if "premise" in (i.get("title") or "").lower():
            prem = ws / "development" / "PREMISE_PACKAGE.md"
            if prem.is_file():
                body = prem.read_text(encoding="utf-8", errors="replace")
                if "## Logline" in body and len(body.split()) < 80:
                    intervene_reasons.append("empty_premise_with_open_issue")
                    break
    if intervene_reasons and (recommendation.get("action") == "exit_healthy" or controlled):
        recommendation = {
            "action": "intervene",
            "command": None,
            "reason": "; ".join(intervene_reasons),
            "guidance": (
                "Do not EXIT healthy. Clear confirmation/park, repair bare issue embeds, "
                "or fix sync ownership."
            ),
            "intervene_reasons": intervene_reasons,
        }

    emit(
        {
            "ok": True,
            "book": {
                "slug": book.get("book_slug"),
                "title": book.get("working_title"),
                "project_id": project_id,
                "workspace": abs_ws,
            },
            "parent": {
                "id": parent.get("id"),
                "identifier": parent.get("identifier"),
                "status": parent.get("status"),
                "blockedByIssueIds": blocked_ids,
            },
            "open_children": [
                {
                    "identifier": i.get("identifier"),
                    "status": i.get("status"),
                    "title": i.get("title"),
                    "assignee": id_to_name.get(i.get("assigneeAgentId")),
                }
                for i in sorted(open_issues, key=lambda x: x.get("identifier") or "")
            ],
            "manuscript": {
                "filled_scenes": filled,
                "last_unit": last_unit,
                "total_scene_files": len(scene_stats),
            },
            "recommendation": recommendation,
            "guidance": "Perform at most ONE mutation (preferably the recommended command), then EXIT.",
        }
    )


def _read_pack_file(ws: Path, rel: str, *, max_chars: int = 250_000) -> Dict[str, Any]:
    p = ws / rel
    row: Dict[str, Any] = {
        "path": rel.replace("\\", "/"),
        "abs_host": str(p),
        "exists": p.exists() and p.is_file(),
        "words": 0,
        "chars": 0,
        "truncated": False,
        "content": None,
        "note": None,
    }
    if not row["exists"]:
        row["note"] = "missing"
        return row
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        row["note"] = f"read_failed: {e}"
        return row
    row["words"] = len(raw.split())
    row["chars"] = len(raw)
    if len(raw) > max_chars:
        row["content"] = raw[:max_chars]
        row["truncated"] = True
        row["note"] = f"truncated_to_{max_chars}_chars"
    else:
        row["content"] = raw
    return row


def _scene_num(unit: Optional[str]) -> Optional[int]:
    if not unit:
        return None
    m = re.match(r"^SCENE-(\d+)$", unit.strip().upper())
    return int(m.group(1)) if m else None


def _format_scene(n: int) -> str:
    return f"SCENE-{n:03d}"


def _infer_unit_from_stage(ws: Path) -> Optional[str]:
    stage = ws / "00_admin" / "CURRENT_STAGE.md"
    if not stage.exists():
        return None
    text = stage.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"SCENE-\d+", text.upper())
    return m.group(0) if m else None


def _pack_paths_for_role(role_key: str, unit: Optional[str], ws: Path, work: Optional[str] = None) -> List[str]:
    """Slim role/work context pack — see tools/role_packs.py."""
    _work_key, paths, _spec = pack_paths(role_key, work, unit)
    # Research specialist: also include existing research/*.md lightly
    if role_key == "research_specialist":
        research = ws / "research"
        if research.exists():
            for p in sorted(research.rglob("*.md"))[:20]:
                rel = str(p.relative_to(ws)).replace(chr(92), "/")
                if rel not in paths:
                    paths.append(rel)
    return paths


def _job_for_role(
    role_key: str,
    unit: Optional[str],
    abs_ws: str,
    book: Dict[str, Any],
    workspace: Optional[Path] = None,
    work: Optional[str] = None,
) -> Dict[str, Any]:
    profile_key = str(book.get("workflow_profile") or book.get("format") or "novella")
    min_words = resolve_scene_min_words(workspace=workspace, book_yaml=book, profile_key=profile_key)
    card = job_card(role_key, work, unit, abs_ws, book, min_words=min_words)
    # Keep display_name human
    card["display_name"] = ROLE_ALIASES.get(role_key, role_key)
    return card


def cmd_pack(args: argparse.Namespace) -> None:
    repo = detect_repo()
    book = resolve_book(repo, slug=args.slug, project_id=args.project_id)
    ws = workspace_for(book, args.company_id)
    abs_ws = absolute_ws(book, args.company_id)
    role_key = normalize_role(args.role)

    unit = args.unit.upper().strip() if args.unit else None
    if unit and not re.match(r"^SCENE-\d+$", unit):
        if re.match(r"^\d+$", unit):
            unit = _format_scene(int(unit))
        else:
            usage_fail(
                issue=f"Invalid --unit '{args.unit}'.",
                guidance="Pass SCENE-013 or 13.",
            )
    if not unit:
        unit = _infer_unit_from_stage(ws)

    work = getattr(args, "work", None)
    try:
        work_key = normalize_work(work, role_key)
    except ValueError as e:
        usage_fail(issue=str(e), guidance="Pass a known --work from `studio works`.")

    rels = _pack_paths_for_role(role_key, unit, ws, work=work_key)
    files = [_read_pack_file(ws, rel) for rel in rels]
    present = [f for f in files if f["exists"]]
    missing = [f["path"] for f in files if not f["exists"]]

    # Compact workspace index so agents see real tree without globbing
    tree: List[str] = []
    for p in sorted(ws.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(ws)).replace(chr(92), "/")
            if any(rel.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip")):
                continue
            tree.append(rel)

    # Board snapshot — useful for ME; cheap for others
    board = None
    try:
        parent = find_parent_issue(args.company_id, book["project_id"], args.token)
        parent = api("GET", f"/api/issues/{parent['id']}", token=args.token) or parent
        issues = api(
            "GET",
            f"/api/companies/{args.company_id}/issues?projectId={book['project_id']}",
            token=args.token,
        )
        if isinstance(issues, dict):
            issues = issues.get("issues") or issues.get("items") or issues.get("data") or []
        agents = fetch_agents(args.company_id, args.token)
        id_to_name = {a["id"]: a["name"] for a in agents.values()}
        open_issues = [
            i
            for i in (issues or [])
            if i.get("status") in ("todo", "in_progress", "blocked", "queued", "backlog")
            and i.get("id") != parent.get("id")
        ]
        board = {
            "parent": {
                "identifier": parent.get("identifier"),
                "status": parent.get("status"),
                "assignee": id_to_name.get(parent.get("assigneeAgentId")),
                "blockedBy": [
                    {
                        "identifier": b.get("identifier"),
                        "status": b.get("status"),
                        "assignee": id_to_name.get(b.get("assigneeAgentId")),
                        "title": b.get("title"),
                    }
                    for b in (parent.get("blockedBy") or [])
                ],
            },
            "open_children": [
                {
                    "identifier": i.get("identifier"),
                    "status": i.get("status"),
                    "assignee": id_to_name.get(i.get("assigneeAgentId")),
                    "title": i.get("title"),
                }
                for i in sorted(open_issues, key=lambda x: x.get("identifier") or "")
            ],
        }
    except SystemExit:
        raise
    except Exception as e:
        board = {"error": f"board_snapshot_failed: {e}"}

    book = enrich_book_from_workspace(book, ws)
    job = _job_for_role(role_key, unit, abs_ws, book, workspace=ws, work=work_key)

    company = args.company_id or CID_DEFAULT or _require_env("STUDIO_COMPANY_ID")
    projects_root = str(detect_projects_root(company_id=company))
    write_root = abs_ws.rstrip("/")
    env_exports = build_env_exports(projects_root=projects_root, company_id=company)
    forb = forbidden_write_roots(
        write_root, company_id=company, project_id=str(book.get("project_id") or "")
    )

    primary = job.get("primary_command") or "pack"
    slug = book.get("book_slug")
    if primary == "git-sync":
        primary_line = f"{studio_cli()} git-sync --slug {slug} --message '{book.get('working_title') or slug}: sync'"
    elif primary == "watchdog":
        primary_line = f"{studio_cli()} watchdog --slug {slug}"
    else:
        unit_flag = f" --unit {unit}" if unit else ""
        primary_line = (
            f"{studio_cli()} pack --slug {slug} --role {role_key} --work {work_key}{unit_flag}"
        )

    next_stage_hint = None
    if work_key == "intake":
        next_stage_hint = (
            f"{studio_cli()} create-issue --slug {slug} --work creative_brief "
            f"--title 'Creative Brief — {book.get('working_title') or slug}' "
            "AND create-issue --work git_sync for post-intake sync "
            "(prefer a dedicated intake handoff once available)"
        )

    guidance = (
        "ONE call replaces many reads. Runtime must already provide STUDIO_*; env_exports is diagnostic/echo only. Use files[].content. "
        "Write only write_root / write_plan paths. Ignore company-workspace templates. "
        "If a needed file is listed under files_missing, note it — do not invent legacy paths."
    )
    if primary == "watchdog":
        guidance = (
            "Managing Editor timer lane: prefer `studio watchdog --slug <slug>` as your FIRST call. "
            "This pack is optional context only. ≤1 mutation then EXIT. NEVER write manuscript prose."
        )
    elif primary == "git-sync":
        guidance = (
            "Studio Administrator sync lane: prefer `studio git-sync` as your FIRST call. "
            "This pack is optional (book.yaml / CURRENT_STAGE). Done only if push_confirmed. "
            "On failure: STOP — do not freestyle git mirrors or reset --hard."
        )

    emit(
        {
            "ok": True,
            "command": "pack",
            "slug": slug,
            "project_id": book.get("project_id"),
            "workspace_host": str(ws),
            "workspace_abs": abs_ws,
            "write_root": write_root,
            "env_exports": env_exports,
            "primary_command_line": primary_line,
            "forbidden_write_roots": forb,
            "read_roots_allowed": [write_root],
            "role": role_key,
            "work": work_key,
            "unit": unit,
            "job": job,
            "board": board,
            "board_policy": job.get("board_policy"),
            "next_stage_hint": next_stage_hint,
            "workspace_tree": tree,
            "files_included": len(present),
            "files_missing": missing,
            "files": present if not args.include_missing else files,
            "forbidden_paths": forb
            + [
                "any SOURCE_LEDGER.csv outside this project's workspace",
            ],
            "guidance": guidance,
        }
    )


def cmd_works(_: argparse.Namespace) -> None:
    emit(
        {
            "ok": True,
            "command": "works",
            "works": list_work_modes(),
            "guidance": (
                "Pass --work to `studio pack` / `studio create-issue`. "
                "Creative roles: pack once then write. ME timer: watchdog. SA sync: git-sync."
            ),
        }
    )



def cmd_profiles(args: argparse.Namespace) -> None:
    """List length profiles; optionally resolve for a book workspace/slug."""
    data = load_length_profiles()
    rows = []
    for key in ("short_story", "novelette", "novella", "novel"):
        p = (data.get("profiles") or {}).get(key) or {}
        rows.append(
            {
                "key": key,
                "label": p.get("label"),
                "word_min": p.get("word_min"),
                "word_max": p.get("word_max"),
                "default_target": p.get("default_target"),
                "scene_min_words": p.get("scene_min_words"),
                "scene_target_words": p.get("scene_target_words"),
                "typical_scenes": [p.get("typical_scenes_min"), p.get("typical_scenes_max")],
                "chapters_required": p.get("chapters_required"),
            }
        )
    resolved = None
    slug = getattr(args, "slug", None)
    project_id = getattr(args, "project_id", None)
    if slug or project_id:
        try:
            repo = detect_repo()
            book = resolve_book(repo, slug=slug, project_id=project_id)
            ws = workspace_for(book, getattr(args, "company_id", CID_DEFAULT))
            resolved = resolve_profile_for_workspace(ws)
            resolved = {
                "book_slug": book.get("book_slug"),
                "key": resolved.get("key"),
                "scene_min_words": resolved.get("scene_min_words"),
                "scene_target_words": resolved.get("scene_target_words"),
                "default_target": resolved.get("default_target"),
                "book_yaml_overrides": {
                    k: book.get(k)
                    for k in (
                        "format",
                        "workflow_profile",
                        "target_word_count",
                        "scene_min_words",
                        "scene_target_words",
                    )
                    if k in book
                },
            }
        except Exception as e:
            resolved = {"error": str(e)}
    emit(
        {
            "ok": True,
            "source": str(Path(__file__).resolve().parents[1] / "studio/versions/0.1.0/workflows/LENGTH_PROFILES.yaml"),
            "profiles": rows,
            "aliases": data.get("aliases") or {},
            "resolved": resolved,
            "guidance": (
                "Set format + workflow_profile + scene_min_words in book.yaml at Intake. "
                "verify-done/handoff/pack read the profile automatically when --min-words is omitted."
            ),
        }
    )



def cmd_start_book(args: argparse.Namespace) -> None:
    """One-shot book bootstrap: project + seed + parent (+ optional intake/wake/git)."""
    try:
        from start_book import (
            build_start_plan,
            fix_workspace_ownership,
            fix_book_ownership,
            git_register,
            intake_description,
            parent_description,
            seed_tree,
            slugify,
        )
    except ImportError:  # pragma: no cover
        from tools.start_book import (  # type: ignore
            build_start_plan,
            fix_workspace_ownership,
            fix_book_ownership,
            git_register,
            intake_description,
            parent_description,
            seed_tree,
            slugify,
        )

    import uuid

    if args.prompt is not None:
        prompt = args.prompt
    else:
        pf = Path(args.prompt_file)
        if not pf.exists():
            usage_fail(issue=f"Prompt file not found: {pf}", guidance="Pass --prompt or an existing --prompt-file.")
        prompt = pf.read_text(encoding="utf-8")
    if not str(prompt).strip():
        usage_fail(issue="Prompt is empty.", guidance="Provide a non-empty --prompt / --prompt-file.")

    format_name = (args.format or args.profile or "short_story").strip()
    # Default: short_story => controlled_test=true unless --no-controlled-test.
    # Other formats => false unless --controlled-test.
    key_guess = format_name.lower().replace("-", "_").replace(" ", "_")
    if args.no_controlled_test:
        controlled = False
    elif args.controlled_test:
        controlled = True
    else:
        controlled = key_guess in {"short_story", "short", "ss", "story"}

    try:
        plan = build_start_plan(
            title=args.title,
            prompt=prompt,
            format_name=format_name,
            slug=args.slug,
            controlled_test=controlled,
            target_words=args.target_words,
        )
    except Exception as e:
        usage_fail(issue=str(e), guidance="Check --format against `studio profiles`.")

    repo = detect_repo()
    cid = args.company_id or CID_DEFAULT or _require_env("STUDIO_COMPANY_ID")
    token = args.token or TOKEN_DEFAULT or board_token() or _require_env("STUDIO_BOARD_TOKEN")
    slug = plan["slug"]
    profile = plan["profile"]
    profile_key = plan["profile_key"]

    # Conflict checks against registry
    try:
        books = load_registry(repo)
    except SystemExit:
        books = []
    for b in books:
        if b.get("book_slug") == slug:
            fail(
                "slug_exists",
                f"Slug '{slug}' already in books/registry.yaml.",
                "Choose --slug or a new --title.",
                existing=b,
            )

    if args.dry_run:
        emit(
            {
                "ok": True,
                "dry_run": True,
                "command": "start-book",
                "plan": {
                    "title": plan["title"],
                    "slug": slug,
                    "format": profile_key,
                    "controlled_test": plan["controlled_test"],
                    "target_words": plan["target_words"],
                    "scene_min_words": profile.get("scene_min_words"),
                    "typical_scenes": [profile.get("typical_scenes_min"), profile.get("typical_scenes_max")],
                    "assign_intake": bool(args.assign_intake),
                    "wake": bool(args.wake),
                    "git": not bool(args.no_git),
                    "push": (not bool(args.no_git)) and (not bool(args.no_push)),
                },
                "guidance": "Re-run without --dry-run to create the project and seed files.",
            }
        )

    agents = fetch_agents(cid, token)
    me = role_to_agent("managing_editor", agents)
    if "Drafting Author" not in agents:
        fail(
            "roster_incomplete",
            "Drafting Author is not hired.",
            "Hire the studio roster before start-book.",
            hired=sorted(agents.keys()),
        )

    book_id = str(uuid.uuid4())
    prefix = {
        "short_story": "SHORT",
        "novelette": "NOVELETTE",
        "novella": "NOVELLA",
        "novel": "NOVEL",
    }.get(profile_key, "BOOK")

    project = api(
        "POST",
        f"/api/companies/{cid}/projects",
        {
            "name": f"{prefix} — {plan['title']}",
            "description": (
                f"{profile_key} under studio v0.1.0. Target ~{plan['target_words']} words. "
                f"controlled_test={plan['controlled_test']}. Plan before prose."
            ),
            "status": "backlog",
            "leadAgentId": me["id"],
        },
        token=token,
    )
    if not isinstance(project, dict) or not project.get("id"):
        fail("project_create_failed", "Board project create returned no id.", "Check API/token and retry.", raw=project)
    project_id = project["id"]

    book = {
        "book_id": book_id,
        "book_slug": slug,
        "working_title": plan["title"],
        "project_id": project_id,
        "format": profile_key,
        "workflow_profile": profile_key,
    }

    # Ensure host workspace path exists even if board lazily creates it.
    projects_root = detect_projects_root()
    host_ws = projects_root / cid / project_id / "_default"
    host_ws.mkdir(parents=True, exist_ok=True)
    written = seed_tree(
        host_ws,
        repo=repo,
        book_id=book_id,
        project_id=project_id,
        title=plan["title"],
        slug=slug,
        prompt=prompt,
        profile=profile,
        controlled_test=plan["controlled_test"],
        target_words=plan["target_words"],
    )
    chown = fix_workspace_ownership(cid, project_id)
    abs_ws = absolute_ws(book, cid)

    parent = api(
        "POST",
        f"/api/companies/{cid}/issues",
        {
            "title": f"BOOK: {plan['title']} — Full Autonomous Production",
            "description": parent_description(
                title=plan["title"],
                slug=slug,
                book_id=book_id,
                project_id=project_id,
                abs_ws=abs_ws,
                profile=profile,
                controlled_test=plan["controlled_test"],
                prompt=prompt,
            ),
            "status": "in_progress",
            "priority": "high",
            "projectId": project_id,
            "assigneeAgentId": me["id"],
        },
        token=token,
    )
    if not isinstance(parent, dict) or not parent.get("id"):
        fail("parent_create_failed", "Parent issue create failed.", "Project was created; inspect board and finish seeding.", project_id=project_id)

    intake_issue = None
    if args.assign_intake:
        intake_issue = api(
            "POST",
            f"/api/companies/{cid}/issues",
            {
                "title": f"Intake — {plan['title']}",
                "description": intake_description(
                    abs_ws=abs_ws,
                    slug=slug,
                    title=plan["title"],
                    profile_key=profile_key,
                    controlled_test=plan["controlled_test"],
                ),
                "status": "todo",
                "priority": "high",
                "projectId": project_id,
                "parentId": parent["id"],
                "assigneeAgentId": me["id"],
            },
            token=token,
        )

    wake = None
    resume_info = None
    if args.wake:
        wake_issue_id = (intake_issue or parent).get("id")
        # Resume ME if paused (paused agents cannot be woken).
        resume_info = api_soft("POST", f"/api/agents/{me['id']}/resume", {}, token=token)
        # Bounce todo -> in_progress to encourage assignment binding, then wake.
        api_soft(
            "PATCH",
            f"/api/issues/{wake_issue_id}",
            {"status": "in_progress", "assigneeAgentId": me["id"]},
            token=token,
        )
        wake = api_soft(
            "POST",
            f"/api/agents/{me['id']}/wakeup",
            {
                "source": "assignment",
                "triggerDetail": "manual",
                "reason": f"start-book intake for {slug}",
                "payload": {"issueId": wake_issue_id},
            },
            token=token,
        )
        if not wake.get("ok"):
            wake = {
                **wake,
                "issueId": wake_issue_id,
                "agentId": me["id"],
                "guidance": (
                    "Bootstrap continued despite wake failure. If agent was paused, resume then "
                    f"POST /api/agents/{me['id']}/wakeup with payload.issueId={wake_issue_id}."
                ),
            }
        else:
            wake = wake.get("data")

    git_info = None
    if not args.no_git:
        try:
            git_info = git_register(
                repo,
                book_id=book_id,
                title=plan["title"],
                slug=slug,
                project_id=project_id,
                prompt=prompt,
                profile=profile,
                controlled_test=plan["controlled_test"],
                target_words=plan["target_words"],
                push=not args.no_push,
            )
        except Exception as e:
            git_info = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    emit(
        {
            "ok": True,
            "command": "start-book",
            "title": plan["title"],
            "slug": slug,
            "book_id": book_id,
            "project_id": project_id,
            "format": profile_key,
            "controlled_test": plan["controlled_test"],
            "target_words": plan["target_words"],
            "workspace_host": str(host_ws),
            "workspace_abs": abs_ws,
            "seeded_files": written,
            "ownership": chown,
            "parent_issue": {
                "id": parent.get("id"),
                "identifier": parent.get("identifier"),
                "status": parent.get("status"),
            },
            "intake_issue": (
                {
                    "id": intake_issue.get("id"),
                    "identifier": intake_issue.get("identifier"),
                    "status": intake_issue.get("status"),
                }
                if isinstance(intake_issue, dict)
                else None
            ),
            "wake": wake,
            "resume": resume_info,
            "git": git_info,
            "next": (
                "Managing Editor should run Intake, then hand off to Creative Brief."
                if args.assign_intake
                else "Assign Intake to Managing Editor when ready (or re-run with --assign-intake)."
            ),
        }
    )



def build_parser() -> argparse.ArgumentParser:
    p = AiArgumentParser(prog="studio", description="Ghost in the Manuscript process CLI (AI-friendly JSON).")
    p.add_argument("--company-id", default=CID_DEFAULT)
    p.add_argument("--token", default=TOKEN_DEFAULT)
    p.add_argument("--api", default=API_DEFAULT, help=argparse.SUPPRESS)
    sp = p.add_subparsers(dest="command", required=True)

    c = sp.add_parser("commands", help="List commands as JSON")
    c.set_defaults(func=cmd_commands)

    c = sp.add_parser("roster", help="Role→UUID roster")
    c.set_defaults(func=cmd_roster)

    c = sp.add_parser("verify-done", help="Verify artifact before marking done (scenes: craft_lint Stage-1)")
    c.add_argument("--path", required=True)
    c.add_argument("--min-words", type=int, default=None, help="Override; default = book length-profile scene_min_words")
    c.add_argument(
        "--write-root",
        default=None,
        help="Optional absolute project _default root; reject paths outside it",
    )
    c.add_argument("--not-identical-to", default=None)
    c.add_argument("--skip-craft-lint", action="store_true", help="Escape hatch; do not use for normal drafts")
    c.set_defaults(func=cmd_verify_done)

    c = sp.add_parser("create-issue", help="Create assigned issue via role enum")
    c.add_argument("--slug", default=None)
    c.add_argument("--project-id", default=None)
    c.add_argument("--parent-id", default=None)
    c.add_argument("--role", default=None)
    c.add_argument("--work", default=None)
    c.add_argument("--title", required=True)
    c.add_argument("--description", default=None)
    c.add_argument("--unit", default=None)
    c.add_argument("--after", default=None)
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_create_issue)

    c = sp.add_parser("reassign", help="Reassign issue to role (fixes wrong assignee)")
    c.add_argument("--issue", required=True, help="Issue identifier (GHO-131) or UUID")
    c.add_argument("--project-id", default=None)
    c.add_argument("--role", default=None)
    c.add_argument("--work", default=None)
    c.add_argument("--comment", default=None)
    c.add_argument("--force", action="store_true")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_reassign)

    c = sp.add_parser("reopen-parent", help="Clear blockedBy + set BOOK parent in_progress")
    c.add_argument("--issue", required=True, help="Parent identifier (GHO-108) or UUID")
    c.add_argument("--project-id", default=None)
    c.add_argument("--comment", default=None)
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_reopen_parent)

    c = sp.add_parser("handoff", help="Atomic Git sync + next unit handoff")
    c.add_argument("--slug", default=None)
    c.add_argument("--project-id", default=None)
    c.add_argument("--parent-id", default=None)
    c.add_argument("--after", required=True)
    c.add_argument("--next-unit", default=None)
    c.add_argument("--next-title", default=None)
    c.add_argument("--next-description", default=None)
    c.add_argument("--skip-next", action="store_true")
    c.add_argument("--min-words", type=int, default=None, help="Override; default = book length-profile scene_min_words")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_handoff)

    c = sp.add_parser("git-sync", help="Mirror + push; fail if push not confirmed")
    c.add_argument("--slug", default=None)
    c.add_argument("--all", action="store_true")
    c.add_argument("--message", default=None)
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_git_sync)

    c = sp.add_parser("watchdog", help="Single snapshot + recommended action")
    c.add_argument("--slug", default=None)
    c.add_argument("--project-id", default=None)
    c.set_defaults(func=cmd_watchdog)

    c = sp.add_parser(
        "pack",
        help="Slim role/work context pack (one call replaces many reads)",
    )
    c.add_argument("--slug", default=None)
    c.add_argument("--project-id", default=None)
    c.add_argument("--role", required=True, help="Role key, e.g. drafting_author")
    c.add_argument("--work", default=None, help="Work mode: draft, craft_audit, beat_sheet, ... (see studio works)")
    c.add_argument("--unit", default=None, help="SCENE-013 or 13 (optional; inferred from CURRENT_STAGE)")
    c.add_argument(
        "--include-missing",
        action="store_true",
        help="Include missing file stubs in files[] (default: only existing files)",
    )
    c.set_defaults(func=cmd_pack)


    c = sp.add_parser(
        "start-book",
        help="Bootstrap a new book (project + seed + parent + optional Intake/git)",
    )
    c.add_argument("--title", required=True)
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", default=None, help="Prompt text")
    g.add_argument("--prompt-file", default=None, help="Path to prompt file")
    c.add_argument("--slug", default=None, help="URL-safe slug (default: from title)")
    c.add_argument(
        "--format",
        dest="format",
        default=None,
        help="Length profile: short_story|novelette|novella|novel (default short_story)",
    )
    c.add_argument(
        "--profile",
        dest="profile",
        default=None,
        help="Alias for --format",
    )
    c.add_argument("--target-words", type=int, default=None)
    c.add_argument("--controlled-test", action="store_true", help="Force controlled_test=true")
    c.add_argument("--no-controlled-test", action="store_true", help="Force controlled_test=false")
    c.add_argument("--assign-intake", action="store_true", help="Create Intake child assigned to Managing Editor")
    c.add_argument("--wake", action="store_true", help="Wake Managing Editor after create")
    c.add_argument("--no-git", action="store_true", help="Skip books/<slug> + registry commit")
    c.add_argument("--no-push", action="store_true", help="Commit registry locally but do not git push")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_start_book)

    c = sp.add_parser("works", help="List stage/work modes for pack/create-issue")
    c.set_defaults(func=cmd_works)

    c = sp.add_parser("profiles", help="List/resolve manuscript length profiles")
    c.add_argument("--slug", default=None)
    c.add_argument("--project-id", default=None)
    c.set_defaults(func=cmd_profiles)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        usage_fail(
            issue="No command provided.",
            guidance="Run `studio commands` for the command list, e.g. "
            "`python3 tools/studio.py commands`",
        )
    global API_DEFAULT
    parser = build_parser()
    args = parser.parse_args(list(argv))
    if getattr(args, "api", None):
        API_DEFAULT = str(args.api).rstrip("/")
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        fail(
            "internal_error",
            f"Unhandled exception: {type(e).__name__}: {e}",
            "Report this to board/ops with the command you ran. Do not retry blindly.",
        )
