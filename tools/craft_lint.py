#!/usr/bin/env python3
"""Mechanical craft lint for manuscript scene drafts (book-agnostic).

Fails (exit 1) when a manuscript unit shows known degradation patterns:
- duplicate / near-duplicate paragraphs
- n-gram mantra loops (>6 repeats of any 3-word phrase)
- SVO / inventory-prose run-lengths (pronoun/article/character-name starters)

Emits JSON on stdout for studio verify-done / agents.

IMPORTANT:
This tool must not hardcode any book title, character name, or scene ID.
Character/POV name starters are loaded from the active book's planning docs:
  - outline/scenes/<UNIT>.md  (POV character, Present characters, Character names)
  - bible/STORY_BIBLE.md       (Protagonist Name, supporting-cast table, Names section)
  - bible/STORY_BIBLE_SLIM.md  (optional slim cast)
  - bible/CRAFT_LEXICON.md     (optional explicit starter lexicon)
  - YAML front matter keys if present (pov_character, character_names, craft_starters)

If planning docs are missing, it falls back to pronoun/article starters only
(plus an optional weak draft-inferred proper-noun fallback when --allow-draft-infer is set).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PRONOUN_ARTICLE_STARTERS = {"she", "he", "they", "it", "the", "i", "we"}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
WORD_RE = re.compile(r"[A-Za-z']+")
PROPER_TOKEN_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:'[A-Za-z]+)?)\b")
PROPER_RE = re.compile(r"^[A-Z][A-Za-z]*(?:'[A-Za-z]+)?$")
PARA_SPLIT = re.compile(r"\n\s*\n+")

# Common non-name Titlecase words we should never treat as character starters.
STOP_PROPER = {
    "the", "a", "an", "and", "or", "but", "if", "when", "then", "this", "that",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "chapter", "scene", "lot", "zone", "day", "night", "morning", "afternoon",
    "evening", "county", "state", "office", "house", "road", "street", "bay",
    "water", "fog", "sky", "wind", "door", "desk", "folder", "paper", "record",
}


def emit(payload: Dict[str, Any], code: int) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(code)


def normalize_para(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def sentences(text: str) -> List[str]:
    parts = [s.strip() for s in SENTENCE_SPLIT.split(text) if s and s.strip()]
    out = []
    for s in parts:
        if s.startswith("#") or s.startswith("---"):
            continue
        if len(WORD_RE.findall(s)) < 3:
            continue
        out.append(s)
    return out


def discover_workspace(scene_path: Path) -> Optional[Path]:
    """Walk upward from a manuscript scene until we find a book workspace root.

    Recognizes either:
      <ws>/manuscript/scenes/SCENE-XXX.md
    or a directory that contains bible/ + outline/ (+ optional manuscript/).
    """
    cur = scene_path.resolve().parent
    for _ in range(8):
        if (cur / "bible").is_dir() and (cur / "outline").is_dir():
            return cur
        if cur.name == "_default" and (cur / "bible").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def unit_from_path(scene_path: Path) -> Optional[str]:
    m = re.match(r"^(SCENE-\d+)", scene_path.stem.upper())
    return m.group(1) if m else None


def parse_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 4 :]
    data: Dict[str, Any] = {}
    # Minimal YAML-ish parser for simple keys we care about.
    for line in fm_raw.splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        data[key] = val
    return data, body


def name_tokens_from_phrase(phrase: str) -> Set[str]:
    """Extract likely first/last name tokens from a planning-doc phrase."""
    out: Set[str] = set()
    cleaned = re.sub(r"\(.*?\)", " ", phrase)
    cleaned = cleaned.replace("/", " ").replace("|", " ").replace("—", " ").replace("-", " ")
    for tok in PROPER_TOKEN_RE.findall(cleaned):
        low = tok.lower()
        if low in STOP_PROPER or low in PRONOUN_ARTICLE_STARTERS:
            continue
        if len(tok) < 2:
            continue
        out.add(low)
    return out


def extract_names_from_contract(text: str) -> Set[str]:
    names: Set[str] = set()
    patterns = [
        r"(?im)^-\s*POV character:\s*(.+)$",
        r"(?im)^-\s*Present characters:\s*(.+)$",
        r"(?im)^-\s*Character names:\s*(.+)$",
        r"(?im)^-\s*Characters present:\s*(.+)$",
        r"(?im)^-\s*CRAFT_STARTERS:\s*(.+)$",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            names |= name_tokens_from_phrase(m.group(1))
    return names


def extract_names_from_bible(text: str) -> Set[str]:
    """Extract only protagonist / explicit cast names, not locations or terminology.

    Priority:
    1) Protagonist `- Name:` line under Characters
    2) Supporting-cast markdown table rows while inside that section
    """
    names: Set[str] = set()
    lines = text.splitlines()
    section = None
    for i, line in enumerate(lines):
        if re.match(r"(?i)^##\s+characters\b", line):
            section = "characters"
            continue
        if re.match(r"^##\s+", line):
            section = None
            continue
        if section != "characters":
            continue
        if re.match(r"(?i)^###\s+protagonist\b", line):
            # next Name: line(s)
            for j in range(i + 1, min(i + 12, len(lines))):
                if re.match(r"^###\s+", lines[j]) or re.match(r"^##\s+", lines[j]):
                    break
                m = re.match(r"(?im)^-\s*Name:\s*(.+)$", lines[j])
                if m:
                    names |= name_tokens_from_phrase(m.group(1))
        if re.match(r"(?i)^###\s+supporting cast\b", line):
            for j in range(i + 1, min(i + 80, len(lines))):
                if re.match(r"^###\s+", lines[j]) or re.match(r"^##\s+", lines[j]):
                    break
                row = lines[j].strip()
                if not row.startswith("|"):
                    continue
                cols = [c.strip() for c in row.strip("|").split("|")]
                if not cols:
                    continue
                head = cols[0]
                if head.lower() in {"name"} or set(head) <= {"-", ":"}:
                    continue
                names |= name_tokens_from_phrase(head)
    return names


def extract_names_from_lexicon(text: str) -> Set[str]:
    names: Set[str] = set()
    for pat in [
        r"(?im)^-\s*character_starters?:\s*(.+)$",
        r"(?im)^-\s*craft_starters?:\s*(.+)$",
        r"(?im)^-\s*pov_names?:\s*(.+)$",
        r"(?im)^-\s*names?:\s*(.+)$",
    ]:
        for m in re.finditer(pat, text):
            for part in re.split(r"[,;/]", m.group(1)):
                names |= name_tokens_from_phrase(part)
    in_block = False
    for line in text.splitlines():
        if re.match(r"(?i)^##\s+.*character.*starter", line) or re.match(r"(?i)^##\s+craft lexicon", line):
            in_block = True
            continue
        if in_block and re.match(r"^##\s+", line):
            in_block = False
        if in_block:
            m = re.match(r"^[-*]\s+(.+)$", line)
            if m:
                names |= name_tokens_from_phrase(m.group(1))
    return names


def extract_names_from_front_matter(fm: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for key in (
        "pov_character",
        "pov",
        "character_names",
        "characters",
        "craft_starters",
        "character_starters",
    ):
        val = fm.get(key)
        if not val:
            continue
        if isinstance(val, str):
            for part in re.split(r"[,;/]", val):
                names |= name_tokens_from_phrase(part)
    return names


def load_planning_names(scene_path: Path, ws: Optional[Path], unit: Optional[str]) -> Dict[str, Any]:
    """Load character-name starters for SVO detection.

    Precedence (most specific wins additions):
    1) scene-contract POV / CRAFT_STARTERS / Character names
    2) bible/CRAFT_LEXICON.md explicit character_starters
    3) story-bible protagonist name (fallback if POV missing)
    4) continuity Present characters for this unit only

    Full supporting-cast dumps are intentionally NOT used for SVO detection;
    they inflate false positives in dialogue-heavy good scenes.
    """
    sources: List[str] = []
    names: Set[str] = set()
    pov_names: Set[str] = set()
    if ws is None:
        return {"names": [], "sources": [], "workspace": None, "pov_names": []}

    if unit:
        contract = ws / "outline" / "scenes" / f"{unit}.md"
        if contract.exists():
            raw = contract.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_front_matter(raw)
            # POV character specifically
            for m in re.finditer(r"(?im)^-\s*POV character:\s*(.+)$", body):
                pov_names |= name_tokens_from_phrase(m.group(1))
            got = extract_names_from_front_matter(fm) | extract_names_from_contract(body)
            if got or pov_names:
                names |= got | pov_names
                sources.append(str(contract))

    lexicon = ws / "bible" / "CRAFT_LEXICON.md"
    if lexicon.exists():
        raw = lexicon.read_text(encoding="utf-8", errors="replace")
        _, body = parse_front_matter(raw)
        got = extract_names_from_lexicon(body)
        if got:
            names |= got
            sources.append(str(lexicon))

    # Protagonist fallback only if we still have no POV/lexicon names
    if not names:
        for rel in ("bible/STORY_BIBLE.md", "bible/STORY_BIBLE_SLIM.md"):
            p = ws / rel
            if not p.exists():
                continue
            raw = p.read_text(encoding="utf-8", errors="replace")
            _, body = parse_front_matter(raw)
            got = extract_names_from_bible(body)
            # Prefer only first Name: under protagonist if possible
            m = re.search(r"(?is)###\s+Protagonist\b.*?^-\s*Name:\s*(.+)$", body, re.M)
            if m:
                got = name_tokens_from_phrase(m.group(1))
            if got:
                names |= got
                sources.append(str(p))
                break

    if unit:
        cont = ws / "manuscript" / "continuity" / "CONTINUITY_LEDGER.md"
        if cont.exists():
            raw = cont.read_text(encoding="utf-8", errors="replace")
            m = re.search(rf"(?is)##\s*{re.escape(unit)}\b(.*?)(?=\n##\s+|\Z)", raw)
            block = m.group(1) if m else ""
            for mm in re.finditer(r"(?im)^-\s*Present characters:\s*(.+)$", block):
                names |= name_tokens_from_phrase(mm.group(1))
                sources.append(str(cont))

    names = {n for n in names if n not in STOP_PROPER and n not in PRONOUN_ARTICLE_STARTERS and len(n) >= 2}
    # If CRAFT_LEXICON and POV both exist, keep union but drop possessives junk
    names = {n[:-2] if n.endswith("'s") else n for n in names}
    names = {n for n in names if n.isalpha() and len(n) >= 2}
    return {
        "names": sorted(names),
        "pov_names": sorted(pov_names),
        "sources": sources,
        "workspace": str(ws),
    }


def infer_pov_name_starters(sents: List[str], *, min_hits: int = 3) -> Set[str]:
    """Weak fallback: infer recurring sentence-initial proper nouns from the draft."""
    counts: Counter[str] = Counter()
    for s in sents:
        first = WORD_RE.findall(s)
        if not first:
            continue
        token = first[0]
        if PROPER_RE.match(token):
            low = token.lower()
            if low not in PRONOUN_ARTICLE_STARTERS and low not in STOP_PROPER:
                counts[low] += 1
    return {name for name, n in counts.items() if n >= min_hits}


def find_duplicate_paragraphs(text: str) -> List[Dict[str, Any]]:
    paras = [p.strip() for p in PARA_SPLIT.split(text) if p.strip()]
    usable = []
    for p in paras:
        if p.startswith("#") or p.startswith("---"):
            continue
        words = WORD_RE.findall(p)
        if len(words) < 12:
            continue
        usable.append(p)
    counts: Counter[str] = Counter(normalize_para(p) for p in usable)
    dups = []
    seen = set()
    for p in usable:
        key = normalize_para(p)
        if counts[key] >= 2 and key not in seen:
            seen.add(key)
            dups.append({"count": counts[key], "sample": p[:220]})
    return dups


def find_ngram_loops(text: str, n: int = 3, max_repeats: int = 6) -> List[Dict[str, Any]]:
    words = [w.lower() for w in WORD_RE.findall(text)]
    if len(words) < n:
        return []
    grams = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    counts = Counter(grams)
    bad = []
    for gram, c in counts.most_common(40):
        if c > max_repeats:
            bad.append({"ngram": gram, "count": c})
    return bad


def svo_run_stats(text: str, character_names: Iterable[str]) -> Dict[str, Any]:
    sents = sentences(text)
    char_set = {c.lower() for c in character_names}
    if not sents:
        return {
            "ratio": 0.0,
            "hits": 0,
            "sentences": 0,
            "examples": [],
            "max_streak": 0,
            "avg_words": 0.0,
            "starter_lexicon": sorted(PRONOUN_ARTICLE_STARTERS | char_set),
            "character_names": sorted(char_set),
        }
    starters = set(PRONOUN_ARTICLE_STARTERS) | char_set
    hits = []
    flags = []
    for s in sents:
        first = WORD_RE.findall(s)
        is_hit = bool(first) and first[0].lower() in starters
        flags.append(is_hit)
        if is_hit:
            hits.append(s[:160])
    max_streak = streak = 0
    for f in flags:
        if f:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    lengths = [len(WORD_RE.findall(s)) for s in sents]
    avg_words = sum(lengths) / max(len(lengths), 1)
    ratio = len(hits) / max(len(sents), 1)
    return {
        "ratio": ratio,
        "hits": len(hits),
        "sentences": len(sents),
        "examples": hits[:8],
        "max_streak": max_streak,
        "avg_words": avg_words,
        "starter_lexicon": sorted(starters),
        "character_names": sorted(char_set),
    }


def lint_text(
    text: str,
    *,
    character_names: Optional[Iterable[str]] = None,
    allow_draft_infer: bool = False,
    planning_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dups = find_duplicate_paragraphs(text)
    loops = find_ngram_loops(text, n=3, max_repeats=6)
    names = set(character_names or [])
    inferred: Set[str] = set()
    if allow_draft_infer and not names:
        inferred = infer_pov_name_starters(sentences(text))
        names |= inferred
    svo = svo_run_stats(text, names)
    ratio = svo["ratio"]
    hit_n = svo["hits"]
    sent_n = svo["sentences"]
    examples = svo["examples"]
    failures = []
    if dups:
        failures.append(
            {
                "rule": "duplicate_paragraphs",
                "detail": f"{len(dups)} duplicated paragraph group(s)",
                "examples": dups[:3],
            }
        )
    if loops:
        failures.append(
            {
                "rule": "ngram_mantra_loop",
                "detail": f"{len(loops)} 3-gram(s) repeated >6 times",
                "examples": loops[:5],
            }
        )
    inventory = (
        sent_n >= 8
        and (
            # short inventory lists
            (ratio > 0.48 and svo["avg_words"] < 14 and svo["max_streak"] >= 6)
            # extreme monotony regardless of length
            or ratio > 0.82
            # long streak only counts when sentences are also short/choppy
            or (svo["max_streak"] >= 12 and svo["avg_words"] < 12)
        )
    )
    if inventory:
        failures.append(
            {
                "rule": "svo_run_length",
                "detail": (
                    f"{ratio:.1%} SVO-starters; avg_words={svo['avg_words']:.1f}; "
                    f"max_streak={svo['max_streak']} (inventory threshold)"
                ),
                "examples": examples,
                "hits": hit_n,
                "sentences": sent_n,
            }
        )
    return {
        "ok": not failures,
        "failures": failures,
        "metrics": {
            "duplicate_paragraph_groups": len(dups),
            "ngram_loop_count": len(loops),
            "svo_ratio": round(ratio, 4),
            "svo_hits": hit_n,
            "svo_max_streak": svo["max_streak"],
            "svo_avg_words": round(svo["avg_words"], 2),
            "character_names_from_planning": sorted(set(character_names or [])),
            "character_names_inferred_from_draft": sorted(inferred),
            "planning_sources": (planning_meta or {}).get("sources", []),
            "workspace": (planning_meta or {}).get("workspace"),
            "sentence_count": sent_n,
            "words": len(WORD_RE.findall(text)),
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description="Mechanical craft lint for manuscript scenes (book-agnostic; names from planning docs)"
    )
    p.add_argument("--path", required=True, help="Absolute path to scene markdown")
    p.add_argument(
        "--workspace",
        default=None,
        help="Optional book workspace root containing bible/ and outline/",
    )
    p.add_argument(
        "--names",
        default=None,
        help="Optional comma-separated character name starters override",
    )
    p.add_argument(
        "--allow-draft-infer",
        action="store_true",
        help="If planning docs yield no names, weakly infer recurring draft proper nouns",
    )
    p.add_argument("--json-only", action="store_true")
    args = p.parse_args()
    path = Path(args.path)
    if not path.exists():
        emit({"ok": False, "error": "file_missing", "path": str(path)}, 1)

    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_front_matter(text)

    ws = Path(args.workspace).resolve() if args.workspace else discover_workspace(path)
    unit = unit_from_path(path)
    planning = load_planning_names(path, ws, unit)
    names: Set[str] = set(planning.get("names") or [])
    names |= extract_names_from_front_matter(fm)
    if args.names:
        for part in args.names.split(","):
            names |= name_tokens_from_phrase(part.strip())

    result = lint_text(
        body,
        character_names=names,
        allow_draft_infer=args.allow_draft_infer,
        planning_meta=planning,
    )
    result["path"] = str(path)
    if result["ok"]:
        result["guidance"] = (
            "Craft lint passed. Proceed to Craft Auditor (developmental_reviewer) semantic gate."
        )
        emit(result, 0)
    result["error"] = "craft_lint_failed"
    result["guidance"] = (
        "Do NOT PATCH done. Redraft to remove mantra/repetition and SVO inventory prose. "
        "Follow the active book's STYLE_GUIDE micro-craft rules and positive/negative "
        "exemplars, then re-run craft_lint."
    )
    emit(result, 1)


if __name__ == "__main__":
    main()
