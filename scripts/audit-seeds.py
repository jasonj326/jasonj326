#!/usr/bin/env python3
"""audit-seeds.py — Proofread audit table for migrated seeds.

Reads seeds/posts/*.md, emits seeds-audit.md (gitignored) with:
  | Flag | No. | Date | Quote | Body | Edit |

Flags:
  ✗  Date mismatch — canonical ts ≠ body's M月D日
  ⚠  OCR concern — quote looks like garbage (empty, only quotation
      marks, very short, AI image-description, page markers)
  🚧 OCR pending — no OCR text at all

Cmd+click the [edit](seeds/posts/...) link in VS Code Markdown preview
to jump straight into the source file.

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
    id_m = re.search(r'id:\s*"([^"]+)"', raw)
    seed_id = id_m.group(1) if id_m else path.stem
    ocr_pending_m = re.search(r"ocr_pending:\s*(true|false)", raw)
    ocr_pending = ocr_pending_m.group(1) == "true" if ocr_pending_m else False

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

    # Full body text (for date detection — may live anywhere in commentary)
    body_full = "\n".join(
        ln for ln in body.split("\n") if not ln.strip().startswith(">") and ln.strip() != "---"
    )

    return {
        "no": no,
        "ts": ts,
        "id": seed_id,
        "ocr_pending": ocr_pending,
        "quote": quote_first,
        "body": body_first,
        "body_full": body_full,
        "filename": path.name,
    }


def detect_flags(seed: dict) -> str:
    """Return concatenated flag glyphs for the seed."""
    flags = []

    # Date mismatch: canonical ts vs body's M月D日 (search whole commentary)
    if seed["ts"] and len(seed["ts"]) >= 10 and seed.get("body_full"):
        ts_month = int(seed["ts"][5:7])
        ts_day = int(seed["ts"][8:10])
        m = re.search(r"(\d{1,2})月(\d{1,2})日", seed["body_full"])
        if m and (int(m.group(1)), int(m.group(2))) != (ts_month, ts_day):
            flags.append("✗")

    # OCR concerns
    q = seed["quote"]
    if seed["ocr_pending"]:
        flags.append("🚧")
    elif not q:
        flags.append("⚠")
    elif len(q) <= 4:
        flags.append("⚠")
    elif re.fullmatch(r"['\"`''""\s]+", q):  # only quotation marks/whitespace
        flags.append("⚠")
    elif re.fullmatch(r"\[.+\]", q):  # AI image description like "[Sculpture image of...]"
        flags.append("⚠")
    elif re.match(r"^\(P\d+/P?\d+\)", q):  # page markers like "(P1/P3)"
        flags.append("⚠")

    return "".join(flags)


def trunc(s: str, n: int) -> str:
    return (s[: n - 1] + "…") if len(s) > n else s


def main() -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ Posts dir not found: {POSTS_DIR}", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.md"))
    rows = sorted([parse_seed(f) for f in files], key=lambda r: r["no"])

    # Compute flags + tally
    for r in rows:
        r["flags"] = detect_flags(r)
    n_mismatch = sum("✗" in r["flags"] for r in rows)
    n_ocr_warn = sum("⚠" in r["flags"] for r in rows)
    n_pending = sum("🚧" in r["flags"] for r in rows)

    lines = [
        "# Cackle Seed Proofread Audit",
        "",
        f"**Total**: {len(rows)} seeds",
        "",
        f"- ✗ **Date mismatch**: {n_mismatch} (canonical ts ≠ body M月D日 — search `✗`)",
        f"- ⚠ **OCR concern**: {n_ocr_warn} (garbage / image-description / page marker — search `⚠`)",
        f"- 🚧 **OCR pending**: {n_pending} (no OCR — search `🚧`)",
        "",
        "**Workflow**: Cmd+click the `edit` link to open the source `.md` in VS Code. "
        "Edit `id` field + filename + `ts` field as needed; OCR text in body's blockquote can also be polished. "
        "After edits, run `python3 scripts/build-seeds.py` to regenerate `seeds.json`. "
        "**Do not re-run `migrate-cackle.py`** — it overwrites `seeds/posts/`.",
        "",
        "| | No. | Date | Quote | Body | Edit |",
        "|---|----:|-----:|------|------|------|",
    ]
    for r in rows:
        flag = r["flags"] or " "
        edit_link = f"[edit](seeds/posts/{r['filename']})"
        lines.append(
            f"| {flag} | {r['no']} | {r['ts']} | {trunc(r['quote'], 50)} | "
            f"{trunc(r['body'], 60)} | {edit_link} |"
        )

    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"✅ Wrote {OUTPUT.relative_to(REPO_ROOT)}: "
        f"{len(rows)} rows · ✗{n_mismatch} ⚠{n_ocr_warn} 🚧{n_pending}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
