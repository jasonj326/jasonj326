#!/usr/bin/env python3
"""audit-seeds.py — Generate proofread table for all migrated seeds.

Reads seeds/posts/*.md, emits seeds-audit.md (gitignored) with:
  | No. | Canonical date | Quote (first content line) | Body (first line) |

Mismatches between canonical date and body's M月D日 jump out visually.

Usage: python3 scripts/audit-seeds.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "seeds" / "posts"
OUTPUT = REPO_ROOT / "seeds-audit.md"


def parse_seed(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    no_m = re.search(r"source_no:\s*(\d+)", raw)
    no = int(no_m.group(1)) if no_m else -1
    ts_m = re.search(r'ts:\s*"(\d{4}-\d{2}-\d{2})', raw)
    ts = ts_m.group(1) if ts_m else "UNKNOWN"

    fm_end = raw.find("\n---\n", 4)
    body = raw[fm_end + 5 :].strip() if fm_end != -1 else raw

    # First QUOTE content (skip leading date-only lines like "12/31/2020", "01/05/2021")
    quote_first = ""
    for ln in body.split("\n"):
        s = ln.strip()
        if not s.startswith(">"):
            continue
        content = s.lstrip(">").strip()
        if not content:
            continue
        # Skip pure date stamps
        if re.match(r"^\d{1,2}/\d{1,2}(/\d{2,4})?$", content):
            continue
        if re.match(r"^\d+(\.\d+)?\s*%$", content):  # percentage stamps
            continue
        quote_first = content
        break

    # First BODY line (after all blockquotes + '---' separators)
    body_first = ""
    for ln in body.split("\n"):
        s = ln.strip()
        if not s or s.startswith(">") or s == "---":
            continue
        body_first = s
        break

    return {"no": no, "ts": ts, "quote": quote_first, "body": body_first}


def trunc(s: str, n: int) -> str:
    return (s[: n - 1] + "…") if len(s) > n else s


def main() -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ Posts dir not found: {POSTS_DIR}", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.md"))
    rows = sorted([parse_seed(f) for f in files], key=lambda r: r["no"])

    lines = [
        "# Cackle Seed Proofread Audit",
        "",
        f"**Total**: {len(rows)} seeds",
        "",
        "Format: No. | Canonical date (ts) | Quote first line (after date stamp) | Body first line",
        "",
        "Look for mismatch between **Canonical date** and the M月D日 inside **Body first line**.",
        "",
        "| No. | Date | Quote | Body |",
        "|----:|-----:|------|------|",
    ]
    for r in rows:
        lines.append(f"| {r['no']} | {r['ts']} | {trunc(r['quote'], 50)} | {trunc(r['body'], 60)} |")

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ Wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
