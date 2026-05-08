#!/usr/bin/env python3
"""seed-touch.py — fill ts on new seed; update updated_at on modified.

Called from .git/hooks/pre-commit.

Usage:
  python3 scripts/seed-touch.py --new --file <path> --now <iso>
  python3 scripts/seed-touch.py --modified --file <path> --now <iso>
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (fm, body) where fm is the YAML-ish content between --- markers."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    return text[4:end], text[end + 5 :]


def has_field(fm: str, key: str) -> bool:
    return bool(re.search(rf"^{re.escape(key)}:", fm, re.MULTILINE))


def get_field(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def set_field(fm: str, key: str, value: str) -> str:
    """Replace existing key:value or append."""
    pattern = rf"^{re.escape(key)}:.*$"
    new_line = f'{key}: "{value}"'
    if re.search(pattern, fm, re.MULTILINE):
        return re.sub(pattern, new_line, fm, count=1, flags=re.MULTILINE)
    # Append before final newline of fm
    return fm.rstrip() + f"\n{new_line}\n"


def is_full_iso(value: str | None) -> bool:
    """True if value looks like 2026-05-08T14:30:15+08:00."""
    return bool(value and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value))


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--new", action="store_true")
    group.add_argument("--modified", action="store_true")
    parser.add_argument("--file", required=True)
    parser.add_argument("--now", required=True, help="ISO 8601 timestamp")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        return 0  # nothing to do

    text = path.read_text(encoding="utf-8")
    parsed = parse_frontmatter(text)
    if parsed is None:
        return 0  # no frontmatter — skip
    fm, body = parsed

    # Always fill ts if missing/incomplete (safety net for both modes)
    ts = get_field(fm, "ts")
    if ts is None or not is_full_iso(ts):
        fm = set_field(fm, "ts", args.now)

    # --modified: also stamp updated_at
    if args.modified:
        fm = set_field(fm, "updated_at", args.now)

    new_text = f"---\n{fm}\n---\n{body}"
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
