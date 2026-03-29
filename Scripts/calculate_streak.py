#!/usr/bin/env python3
"""Calculate current streak for 'הדבר' habit tracking.

Counts consecutive days with the_thing: 0 going backwards from yesterday.
Outputs JSON: {"streak": N, "best": M, "last_reset": "YYYY-MM-DD"}

Usage:
    python Scripts/calculate_streak.py          # from vault root
"""

import io
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

VAULT_ROOT = Path(__file__).resolve().parent.parent
JOURNAL_DIR = VAULT_ROOT / "Journal"

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_the_thing(filepath: Path) -> int | None:
    try:
        content = filepath.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    m = _FM_RE.match(content)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("the_thing:"):
            val = line.split(":", 1)[1].strip()
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
    return None


def main():
    if not JOURNAL_DIR.is_dir():
        print(json.dumps({"streak": 0, "best": 0, "last_reset": None}))
        return

    # Collect all journal dates with the_thing values
    entries = {}
    for fname in os.listdir(JOURNAL_DIR):
        if not fname.endswith(".md"):
            continue
        stem = fname[:-3]
        if not _DATE_RE.match(stem):
            continue
        val = parse_the_thing(JOURNAL_DIR / fname)
        if val is not None:
            entries[stem] = val

    if not entries:
        print(json.dumps({"streak": 0, "best": 0, "last_reset": None}))
        return

    # Calculate current streak (consecutive 0s going backwards from yesterday)
    today = datetime.now().strftime("%Y-%m-%d")
    streak = 0
    last_reset = None
    check_date = datetime.now() - timedelta(days=1)

    while True:
        date_str = check_date.strftime("%Y-%m-%d")
        if date_str not in entries:
            break
        if entries[date_str] == 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            last_reset = date_str
            break

    # If today has data and is 0, include it
    if today in entries and entries[today] == 0:
        streak += 1
    elif today in entries and entries[today] > 0:
        streak = 0
        last_reset = today

    # Calculate best streak ever
    sorted_dates = sorted(entries.keys())
    best = 0
    current = 0
    for d in sorted_dates:
        if entries[d] == 0:
            current += 1
            best = max(best, current)
        else:
            current = 0

    print(json.dumps({
        "streak": streak,
        "best": best,
        "last_reset": last_reset,
        "total_days_tracked": len(entries),
        "clean_days": sum(1 for v in entries.values() if v == 0),
    }))


if __name__ == "__main__":
    main()
