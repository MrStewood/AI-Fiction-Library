#!/usr/bin/env python3
"""Book-agnostic manuscript length profiles.

Source of truth: studio/versions/0.1.0/workflows/LENGTH_PROFILES.yaml
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

PROFILE_REL = Path("studio/versions/0.1.0/workflows/LENGTH_PROFILES.yaml")


def detect_repo(start: Optional[Path] = None) -> Path:
    cur = (start or Path(__file__)).resolve().parent
    for _ in range(6):
        if (cur / "studio" / "versions").is_dir() and (cur / "books").is_dir():
            return cur
        if (cur / "AI-Fiction-Library" / "studio" / "versions").is_dir():
            return cur / "AI-Fiction-Library"
        if cur.parent == cur:
            break
        cur = cur.parent
    # fallback: this file lives in tools/
    return Path(__file__).resolve().parents[1]


def profiles_path(repo: Optional[Path] = None) -> Path:
    return (repo or detect_repo()) / PROFILE_REL


def _parse_yaml(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    profiles: Dict[str, Dict[str, Any]] = {}
    aliases: Dict[str, str] = {}
    section = None
    current = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":") and not line.startswith("-"):
            section = line[:-1]
            current = None
            continue
        if section == "profiles" and indent == 2 and line.endswith(":"):
            current = line[:-1]
            profiles[current] = {"key": current}
            continue
        if section == "profiles" and current and indent >= 4 and ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v.lower() in {"null", "none", "~"}:
                val: Any = None
            elif v.lower() in {"true", "false"}:
                val = v.lower() == "true"
            else:
                try:
                    val = int(v)
                except ValueError:
                    val = v
            profiles[current][k] = val
            continue
        if section == "aliases" and ":" in line and not line.startswith("-"):
            k, v = line.split(":", 1)
            aliases[k.strip()] = v.strip()
    return {"profiles": profiles, "aliases": aliases}


def load_length_profiles(repo: Optional[Path] = None) -> Dict[str, Any]:
    p = profiles_path(repo)
    if not p.exists():
        raise FileNotFoundError(f"Missing length profiles: {p}")
    data = _parse_yaml(p.read_text(encoding="utf-8"))
    if not data.get("profiles"):
        raise ValueError(f"No profiles parsed from {p}")
    return data


def normalize_profile_key(name: str, data: Optional[Dict[str, Any]] = None) -> str:
    data = data or load_length_profiles()
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        str(k).strip().lower().replace(" ", "_").replace("-", "_"): str(v).strip().lower().replace(" ", "_").replace("-", "_")
        for k, v in (data.get("aliases") or {}).items()
    }
    key = aliases.get(key, key)
    if key not in (data.get("profiles") or {}):
        raise KeyError(f"Unknown length profile '{name}'. Valid: {sorted((data.get('profiles') or {}).keys())}")
    return key


def profile_for_key(key: str, repo: Optional[Path] = None) -> Dict[str, Any]:
    data = load_length_profiles(repo)
    key = normalize_profile_key(key, data)
    prof = dict((data.get("profiles") or {})[key])
    prof["key"] = key
    return prof


def infer_profile_from_target(words: int, repo: Optional[Path] = None) -> Dict[str, Any]:
    data = load_length_profiles(repo)
    for key in ("short_story", "novelette", "novella", "novel"):
        p = (data.get("profiles") or {}).get(key) or {}
        wmin = int(p.get("word_min") or 0)
        wmax = p.get("word_max")
        if words < wmin:
            continue
        if wmax is None or words <= int(wmax):
            return profile_for_key(key, repo)
    return profile_for_key("novel", repo)


def read_book_yaml(ws: Path) -> Dict[str, Any]:
    for rel in ("00_admin/book.yaml", "book.yaml"):
        p = ws / rel
        if not p.exists():
            continue
        out: Dict[str, Any] = {}
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip() or line.strip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if val.lower() in {"null", "none", "~", ""}:
                out[key] = None
            elif val.lower() in {"true", "false"}:
                out[key] = val.lower() == "true"
            else:
                try:
                    out[key] = int(val)
                except ValueError:
                    out[key] = val
        return out
    return {}


def discover_workspace_from_path(path: Path) -> Optional[Path]:
    cur = path.resolve().parent
    for _ in range(8):
        if (cur / "00_admin" / "book.yaml").exists() or ((cur / "bible").is_dir() and (cur / "outline").is_dir()):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def resolve_profile_for_workspace(ws: Path, repo: Optional[Path] = None) -> Dict[str, Any]:
    by = read_book_yaml(ws)
    key = by.get("workflow_profile") or by.get("format") or "novella"
    try:
        prof = profile_for_key(str(key), repo)
    except Exception:
        target = by.get("target_word_count")
        if isinstance(target, int):
            prof = infer_profile_from_target(target, repo)
        else:
            prof = profile_for_key("novella", repo)
    for field in ("scene_min_words", "scene_target_words"):
        if isinstance(by.get(field), int):
            prof[field] = by[field]
    if isinstance(by.get("target_word_count"), int):
        prof["default_target"] = by["target_word_count"]
    prof["book_yaml"] = by
    return prof


def resolve_scene_min_words(
    *,
    path: Optional[Path] = None,
    workspace: Optional[Path] = None,
    book_yaml: Optional[Dict[str, Any]] = None,
    profile_key: Optional[str] = None,
    explicit: Optional[int] = None,
    repo: Optional[Path] = None,
) -> int:
    if explicit is not None:
        return int(explicit)
    if book_yaml and isinstance(book_yaml.get("scene_min_words"), int):
        return int(book_yaml["scene_min_words"])
    ws = workspace
    if ws is None and path is not None:
        ws = discover_workspace_from_path(path)
    if ws is not None:
        return int(resolve_profile_for_workspace(ws, repo).get("scene_min_words") or 800)
    if profile_key:
        return int(profile_for_key(profile_key, repo).get("scene_min_words") or 800)
    if book_yaml:
        key = book_yaml.get("workflow_profile") or book_yaml.get("format")
        if key:
            return int(profile_for_key(str(key), repo).get("scene_min_words") or 800)
    return 800


def apply_profile_to_book_yaml_text(text: str, profile: Dict[str, Any], *, target: Optional[int] = None) -> str:
    """Rewrite/insert profile fields in a book.yaml document."""
    key = profile.get("key") or "novella"
    target = int(target if target is not None else profile.get("default_target") or 30000)
    fields = {
        "format": key,
        "workflow_profile": key,
        "target_word_count": target,
        "target_word_min": profile.get("word_min"),
        "target_word_max": profile.get("word_max"),
        "scene_min_words": profile.get("scene_min_words"),
        "scene_target_words": profile.get("scene_target_words"),
        "typical_scenes_min": profile.get("typical_scenes_min"),
        "typical_scenes_max": profile.get("typical_scenes_max"),
        "typical_chapters_min": profile.get("typical_chapters_min"),
        "typical_chapters_max": profile.get("typical_chapters_max"),
        "chapters_required": profile.get("chapters_required"),
    }

    lines = text.splitlines()
    out = []
    seen = set()
    for line in lines:
        if ":" in line and not line.strip().startswith("#"):
            k = line.split(":", 1)[0].strip()
            if k in fields:
                val = fields[k]
                if isinstance(val, bool):
                    rendered = "true" if val else "false"
                elif val is None:
                    rendered = "null"
                elif isinstance(val, int):
                    rendered = str(val)
                else:
                    rendered = f'"{val}"'
                out.append(f"{k}: {rendered}")
                seen.add(k)
                continue
        out.append(line)
    # append missing before series if possible
    missing = [k for k in fields if k not in seen]
    if missing:
        insert = []
        for k in missing:
            val = fields[k]
            if isinstance(val, bool):
                rendered = "true" if val else "false"
            elif val is None:
                rendered = "null"
            elif isinstance(val, int):
                rendered = str(val)
            else:
                rendered = f'"{val}"'
            insert.append(f"{k}: {rendered}")
        # place before series: null if present
        placed = False
        final = []
        for line in out:
            if not placed and re.match(r"^series:\s*", line):
                final.extend(insert)
                placed = True
            final.append(line)
        if not placed:
            final.extend(insert)
        out = final
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


if __name__ == "__main__":
    import json

    print(json.dumps(load_length_profiles(), indent=2)[:2000])
