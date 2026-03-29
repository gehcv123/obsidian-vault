#!/usr/bin/env python3
"""Analyze patterns and correlations across Obsidian Vault journal entries.

Scans all MD files, parses frontmatter (mood, sleep, energy, tags),
extracts WikiLinks, builds a connection graph, and computes basic
correlations. Outputs a JSON summary to stdout for Claude Code to interpret.

Usage:
    python Scripts/analyze_patterns.py          # from vault root
    python Scripts/analyze_patterns.py --min 14 # require minimum entries
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Vault path resolution
# ---------------------------------------------------------------------------
VAULT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {"Templates", "Scripts", ".git", ".obsidian", ".claude"}
EXCLUDED_FILES = {"Dashboard.md", "CLAUDE.md", "README.md"}

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")
_YAML_LIST_RE = re.compile(r"^\[(.+)\]$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HASHTAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z\u0590-\u05FF][\w\u0590-\u05FF]*)", re.UNICODE)


def _parse_yaml_value(raw: str):
    raw = raw.strip()
    if not raw:
        return ""
    m = _YAML_LIST_RE.match(raw)
    if m:
        return [item.strip().strip("'\"") for item in m.group(1).split(",")]
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def parse_frontmatter(text: str) -> dict:
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm = {}
    current_key = None
    for line in m.group(1).splitlines():
        if line.startswith("  - ") or line.startswith("\t- "):
            if current_key is not None:
                val = line.lstrip().lstrip("-").strip()
                existing = fm.get(current_key, [])
                if not isinstance(existing, list):
                    existing = [existing] if existing else []
                existing.append(val)
                fm[current_key] = existing
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        fm[key] = _parse_yaml_value(val)
        current_key = key
    return fm


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def iter_md_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            fpath = Path(dirpath) / fname
            if fpath.parent == root and fname in EXCLUDED_FILES:
                continue
            yield fpath


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def to_float(val) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, list):
        val = val[0] if val else None
    if val is None:
        return None
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


def collect_journal_entries(root: Path) -> list[dict]:
    """Collect daily journal entries with numeric frontmatter fields."""
    journal_dir = root / "Journal"
    entries = []
    if not journal_dir.is_dir():
        return entries

    for fname in sorted(os.listdir(journal_dir)):
        if not fname.endswith(".md"):
            continue
        stem = fname[:-3]
        if not _DATE_RE.match(stem):
            continue

        fpath = journal_dir / fname
        content = read_file(fpath)
        fm = parse_frontmatter(content)

        entry = {
            "date": stem,
            "mood": to_float(fm.get("mood")),
            "sleep_hours": to_float(fm.get("sleep_hours")),
            "energy": to_float(fm.get("energy")),
            "tags": [],
            "wikilinks": _WIKILINK_RE.findall(content),
            "hashtags": _HASHTAG_RE.findall(content),
        }

        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        entry["tags"] = [t for t in tags if t]

        entries.append(entry)

    return entries


def collect_all_notes(root: Path) -> dict:
    """Collect metadata for all notes (not just journal)."""
    notes = {}
    for fpath in iter_md_files(root):
        content = read_file(fpath)
        fm = parse_frontmatter(content)
        rel = fpath.relative_to(root).as_posix()
        wikilinks = _WIKILINK_RE.findall(content)
        hashtags = _HASHTAG_RE.findall(content)

        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        notes[rel] = {
            "stem": fpath.stem,
            "folder": fpath.parent.relative_to(root).as_posix() if fpath.parent != root else "",
            "tags": [t for t in tags if t],
            "wikilinks": wikilinks,
            "hashtags": hashtags,
        }
    return notes


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Simple Pearson correlation coefficient. Returns None if insufficient data."""
    n = len(xs)
    if n < 3:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 3)


def compute_correlations(entries: list[dict]) -> dict:
    """Compute pairwise correlations between mood, sleep, energy."""
    pairs = [
        ("sleep_hours", "mood", "שינה ↔ מצב רוח"),
        ("sleep_hours", "energy", "שינה ↔ אנרגיה"),
        ("energy", "mood", "אנרגיה ↔ מצב רוח"),
    ]
    results = {}
    for key_a, key_b, label in pairs:
        valid = [
            (e[key_a], e[key_b])
            for e in entries
            if e[key_a] is not None and e[key_b] is not None
        ]
        if len(valid) < 3:
            results[label] = {"r": None, "n": len(valid), "note": "insufficient data"}
            continue
        xs, ys = zip(*valid)
        r = pearson_r(list(xs), list(ys))
        strength = "none"
        if r is not None:
            ar = abs(r)
            if ar >= 0.7:
                strength = "strong"
            elif ar >= 0.4:
                strength = "moderate"
            elif ar >= 0.2:
                strength = "weak"
        results[label] = {"r": r, "n": len(valid), "strength": strength}
    return results


def compute_tag_mood_correlations(entries: list[dict]) -> dict:
    """Average mood when a specific tag/hashtag appears vs not."""
    all_tags = set()
    for e in entries:
        all_tags.update(e["tags"])
        all_tags.update(e["hashtags"])

    # Filter to tags that appear at least twice
    tag_counts = Counter()
    for e in entries:
        for t in set(e["tags"] + e["hashtags"]):
            tag_counts[t] += 1

    results = {}
    for tag, count in tag_counts.most_common(20):
        if count < 2:
            continue
        moods_with = [e["mood"] for e in entries if e["mood"] is not None and tag in e["tags"] + e["hashtags"]]
        moods_without = [e["mood"] for e in entries if e["mood"] is not None and tag not in e["tags"] + e["hashtags"]]
        if not moods_with or not moods_without:
            continue
        avg_with = round(sum(moods_with) / len(moods_with), 2)
        avg_without = round(sum(moods_without) / len(moods_without), 2)
        diff = round(avg_with - avg_without, 2)
        results[tag] = {
            "avg_mood_with": avg_with,
            "avg_mood_without": avg_without,
            "diff": diff,
            "count": count,
        }
    return results


def build_adjacency(notes: dict) -> dict:
    """Build WikiLink adjacency list: note -> [linked notes]."""
    stem_to_path = {}
    for rel, info in notes.items():
        stem_to_path[info["stem"].lower()] = rel

    adjacency = defaultdict(list)
    for rel, info in notes.items():
        for link in info["wikilinks"]:
            link_lower = link.lower()
            if link_lower in stem_to_path:
                target = stem_to_path[link_lower]
                if target != rel:
                    adjacency[rel].append(target)

    return dict(adjacency)


def find_hub_notes(adjacency: dict, notes: dict) -> list[dict]:
    """Find notes with the most incoming links (hub nodes)."""
    incoming = Counter()
    for src, targets in adjacency.items():
        for t in targets:
            incoming[t] += 1

    hubs = []
    for rel, count in incoming.most_common(10):
        info = notes.get(rel, {})
        hubs.append({
            "note": rel,
            "stem": info.get("stem", ""),
            "incoming_links": count,
            "outgoing_links": len(adjacency.get(rel, [])),
        })
    return hubs


def find_recurring_topics(entries: list[dict]) -> list[dict]:
    """Identify most frequently mentioned WikiLinks and hashtags across journal entries."""
    link_counter = Counter()
    tag_counter = Counter()
    for e in entries:
        for link in e["wikilinks"]:
            link_counter[link] += 1
        for tag in e["hashtags"]:
            tag_counter[tag] += 1

    recurring = []
    for item, count in (link_counter + tag_counter).most_common(15):
        if count >= 2:
            recurring.append({"topic": item, "mentions": count})
    return recurring


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    min_entries = 14

    # Parse --min flag
    args = sys.argv[1:]
    if "--min" in args:
        idx = args.index("--min")
        if idx + 1 < len(args):
            try:
                min_entries = int(args[idx + 1])
            except ValueError:
                pass

    if not VAULT_ROOT.is_dir():
        print(json.dumps({"error": f"Vault root not found: {VAULT_ROOT}"}))
        sys.exit(1)

    # Collect data
    entries = collect_journal_entries(VAULT_ROOT)
    all_notes = collect_all_notes(VAULT_ROOT)

    # Warning check
    warning = None
    if len(entries) < min_entries:
        warning = (
            f"Only {len(entries)} journal entries found (minimum {min_entries} recommended). "
            f"Results may not be statistically meaningful."
        )

    # Run analysis
    correlations = compute_correlations(entries)
    tag_mood = compute_tag_mood_correlations(entries)
    adjacency = build_adjacency(all_notes)
    hubs = find_hub_notes(adjacency, all_notes)
    recurring = find_recurring_topics(entries)

    # Averages
    averages = {}
    for field in ["mood", "sleep_hours", "energy"]:
        vals = [e[field] for e in entries if e[field] is not None]
        if vals:
            averages[field] = {
                "mean": round(sum(vals) / len(vals), 2),
                "min": min(vals),
                "max": max(vals),
                "count": len(vals),
            }

    # Output
    result = {
        "vault_root": str(VAULT_ROOT),
        "total_notes": len(all_notes),
        "journal_entries": len(entries),
        "warning": warning,
        "averages": averages,
        "correlations": correlations,
        "tag_mood_correlations": tag_mood,
        "hub_notes": hubs,
        "recurring_topics": recurring,
        "graph_edges": sum(len(v) for v in adjacency.values()),
        "graph_nodes": len(set(adjacency.keys()) | {t for ts in adjacency.values() for t in ts}),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
