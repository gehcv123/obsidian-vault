#!/usr/bin/env python3
"""Regenerate Dashboard.md from Obsidian Vault metadata.

Usage:
    python Scripts/update_dashboard.py          # from vault root
    python /path/to/Scripts/update_dashboard.py  # from anywhere
"""

import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Vault path resolution
# ---------------------------------------------------------------------------
# Default: script's parent's parent (Scripts/ -> vault root)
VAULT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = VAULT_ROOT / "Dashboard.md"

EXCLUDED_DIRS = {"Templates", "Scripts", ".git", ".obsidian"}
EXCLUDED_FILES = {"Dashboard.md"}

# ---------------------------------------------------------------------------
# Frontmatter parser (stdlib only — no PyYAML)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_YAML_LIST_RE = re.compile(r"^\[(.+)\]$")  # inline list: [a, b, c]


def _parse_yaml_value(raw: str) -> str | list[str]:
    """Parse a simple YAML scalar or inline list. No nested structures."""
    raw = raw.strip()
    if not raw:
        return ""
    m = _YAML_LIST_RE.match(raw)
    if m:
        return [item.strip().strip("'\"") for item in m.group(1).split(",")]
    # Strip surrounding quotes
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text into a flat dict."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    current_key = None
    for line in m.group(1).splitlines():
        # Continuation list item (- value under a key)
        if line.startswith("  - ") or line.startswith("\t- "):
            if current_key is not None:
                val = line.lstrip().lstrip("-").strip()
                existing = fm.get(current_key, [])
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    fm[current_key] = [existing, val] if existing else [val]
                fm[current_key] = existing if isinstance(existing, list) else fm[current_key]
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        parsed = _parse_yaml_value(val)
        fm[key] = parsed
        current_key = key
    return fm


# ---------------------------------------------------------------------------
# Vault scanning helpers
# ---------------------------------------------------------------------------


def iter_md_files(root: Path):
    """Yield (Path, relative_posix) for every .md file, excluding ignored dirs/files."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDED_DIRS
        ]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root).as_posix()
            # Skip excluded files at vault root
            if fpath.parent == root and fname in EXCLUDED_FILES:
                continue
            yield fpath, rel


def read_file(path: Path) -> str:
    """Read a file with UTF-8, falling back to latin-1."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def build_journal_section(root: Path) -> str:
    """Recent Journal Entries — last 10 days."""
    journal_dir = root / "Journal"
    entries: list[tuple[str, dict]] = []

    if journal_dir.is_dir():
        date_re = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
        cutoff = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

        for fname in os.listdir(journal_dir):
            m = date_re.match(fname)
            if not m:
                continue
            date_str = m.group(1)
            if date_str < cutoff:
                continue
            fpath = journal_dir / fname
            fm = parse_frontmatter(read_file(fpath))
            entries.append((date_str, fm))

    entries.sort(key=lambda x: x[0], reverse=True)

    lines = [
        "## Recent Journal Entries",
        "",
        "| Date | Mood | Sleep | Energy |",
        "|------|------|-------|--------|",
    ]
    if not entries:
        lines.append("| *No entries yet* | | | |")
    else:
        for date_str, fm in entries:
            mood = fm.get("mood", "") or ""
            sleep = fm.get("sleep_hours", "") or ""
            energy = fm.get("energy", "") or ""
            lines.append(f"| {date_str} | {mood} | {sleep} | {energy} |")
    return "\n".join(lines)


def build_projects_section(root: Path) -> str:
    """Active Projects — status == active."""
    projects_dir = root / "Projects"
    rows: list[tuple[str, str, str]] = []

    if projects_dir.is_dir():
        for fname in os.listdir(projects_dir):
            if not fname.endswith(".md"):
                continue
            fpath = projects_dir / fname
            fm = parse_frontmatter(read_file(fpath))
            status = fm.get("status", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            if str(status).lower() != "active":
                continue
            title = fm.get("title", fname.replace(".md", ""))
            created = fm.get("created", "")
            if isinstance(title, list):
                title = ", ".join(title)
            if isinstance(created, list):
                created = created[0] if created else ""
            rows.append((str(title), str(status), str(created)))

    rows.sort(key=lambda x: x[2], reverse=True)

    lines = [
        "## Active Projects",
        "",
        "| Project | Status | Created |",
        "|---------|--------|---------|",
    ]
    if not rows:
        lines.append("| *No projects yet* | | |")
    else:
        for title, status, created in rows:
            lines.append(f"| {title} | {status} | {created} |")
    return "\n".join(lines)


def build_recent_notes_section(root: Path) -> str:
    """10 most recently modified .md files (excluding Templates/, Scripts/, Dashboard.md)."""
    files_with_mtime: list[tuple[float, str, Path]] = []
    for fpath, rel in iter_md_files(root):
        files_with_mtime.append((fpath.stat().st_mtime, rel, fpath))

    files_with_mtime.sort(key=lambda x: x[0], reverse=True)
    top10 = files_with_mtime[:10]

    lines = ["## Recent Notes", ""]
    if not top10:
        lines.append("*No notes yet.*")
    else:
        for mtime, rel, fpath in top10:
            modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            # Use wiki-link style for Obsidian — strip .md extension
            note_name = fpath.stem
            lines.append(f"- [[{note_name}]] — {modified}")
    return "\n".join(lines)


def build_statistics_section(root: Path) -> str:
    """Total notes, total WikiLinks, most common tags."""
    total_notes = 0
    total_wikilinks = 0
    tag_counter: Counter = Counter()

    for fpath, rel in iter_md_files(root):
        total_notes += 1
        content = read_file(fpath)
        total_wikilinks += len(_WIKILINK_RE.findall(content))

        fm = parse_frontmatter(content)
        tags = fm.get("tags", [])
        if isinstance(tags, str) and tags:
            tags = [tags]
        if isinstance(tags, list):
            for t in tags:
                if t:
                    tag_counter[str(t)] += 1

    if tag_counter:
        top_tags = ", ".join(
            f"`{tag}` ({count})" for tag, count in tag_counter.most_common(5)
        )
    else:
        top_tags = "\u2014"

    lines = [
        "## Statistics",
        "",
        f"- Total notes: {total_notes}",
        f"- Total WikiLinks: {total_wikilinks}",
        f"- Top tags: {top_tags}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not VAULT_ROOT.is_dir():
        print(f"Error: vault root not found: {VAULT_ROOT}", file=sys.stderr)
        sys.exit(1)

    sections = [
        "---",
        "tags: [dashboard]",
        "---",
        "# Dashboard",
        "",
        "> Auto-generated by `Scripts/update_dashboard.py`. Do not edit manually.",
        "",
        build_journal_section(VAULT_ROOT),
        "",
        build_projects_section(VAULT_ROOT),
        "",
        build_recent_notes_section(VAULT_ROOT),
        "",
        build_statistics_section(VAULT_ROOT),
        "",
    ]

    output = "\n".join(sections)
    DASHBOARD.write_text(output, encoding="utf-8")
    print(f"Dashboard updated: {DASHBOARD}")


if __name__ == "__main__":
    main()
