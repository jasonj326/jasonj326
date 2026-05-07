#!/usr/bin/env python3
"""shift-ocr.py — Shift OCR sections backward by 1 for +1-offset seeds.

Diagnosis: For most cackle seeds, body content discusses today's quote Q_today,
but the OCR section shows Q_tomorrow's image (date stamp = ts + 1). This is
because Jason's posting workflow attached the next day's image preview alongside
today's commentary.

Fix: For each seed N where OCR offset is exactly +1 day, replace its OCR section
with seed (N-1)'s current OCR section (which contains Q_today's image, matching
the body).

Skips:
  - image_speaks seeds (image IS the content; OCR is just description, not a quote)
  - +0 aligned seeds (already correct)
  - +2/+3/other offset seeds (need different handling, manual)
  - Seed 0 (no previous seed to take from)
  - Seeds where N-1 is image_speaks (chain broken)

Approach:
  1. Read all seeds, snapshot each one's current OCR section by source_no
  2. For each candidate seed, plan replacement
  3. Atomic write: each seed gets its NEW OCR (from N-1's snapshot)

Usage:
  python3 scripts/shift-ocr.py --dry-run
  python3 scripts/shift-ocr.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "seeds" / "posts"


def split_fm_body(raw: str) -> tuple[str, str]:
    if not raw.startswith("---\n"):
        return "", raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        return "", raw
    return raw[: end + 5], raw[end + 5 :]


def split_ocr_and_commentary(body: str) -> tuple[str, str]:
    """Returns (ocr_section_text, commentary_text). OCR section includes all
    blockquote groups + their --- separators, preserved verbatim."""
    lines = body.split("\n")
    commentary_start = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(">") or s == "---" or s == "":
            continue
        commentary_start = i
        break
    ocr = "\n".join(lines[:commentary_start]).rstrip("\n")
    commentary = "\n".join(lines[commentary_start:]).rstrip()
    return ocr, commentary


def first_ocr_date(body: str) -> date | None:
    for ln in body.split("\n"):
        s = ln.strip().lstrip(">").strip()
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass
    return None


def main(dry_run: bool) -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ {POSTS_DIR} not found", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.md"))
    seeds: dict[int, dict] = {}

    for path in files:
        raw = path.read_text(encoding="utf-8")
        fm, body = split_fm_body(raw)
        if not fm:
            continue
        sno_m = re.search(r"source_no:\s*(\d+)", fm)
        ts_m = re.search(r'ts:\s*"?(\d{4}-\d{2}-\d{2})', fm)
        if not sno_m or not ts_m:
            continue
        sno = int(sno_m.group(1))
        ts = date(int(ts_m.group(1)[:4]), int(ts_m.group(1)[5:7]), int(ts_m.group(1)[8:10]))
        ocr, commentary = split_ocr_and_commentary(body)
        ocr_d = first_ocr_date(ocr)
        is_img = ('category: "image_speaks"' in fm) or ("一圖勝千言" in body)
        seeds[sno] = {
            "path": path,
            "fm": fm,
            "ocr": ocr,
            "commentary": commentary,
            "ts": ts,
            "ocr_date": ocr_d,
            "is_img": is_img,
            "offset": (ocr_d - ts).days if ocr_d else None,
        }

    sorted_nos = sorted(seeds)
    print(f"Loaded {len(sorted_nos)} seeds")
    print()

    # Plan
    plans = []
    skip_reasons = {"image_speaks": 0, "no_offset": 0, "offset_not_1": 0, "no_prev": 0, "prev_image_speaks": 0, "prev_no_ocr": 0}

    for sno in sorted_nos:
        s = seeds[sno]
        if s["is_img"]:
            skip_reasons["image_speaks"] += 1
            continue
        if s["offset"] is None:
            skip_reasons["no_offset"] += 1
            continue
        if s["offset"] != 1:
            skip_reasons["offset_not_1"] += 1
            continue
        if (sno - 1) not in seeds:
            skip_reasons["no_prev"] += 1
            continue
        prev = seeds[sno - 1]
        if prev["is_img"]:
            skip_reasons["prev_image_speaks"] += 1
            continue
        if not prev["ocr"].strip():
            skip_reasons["prev_no_ocr"] += 1
            continue
        plans.append({
            "sno": sno,
            "path": s["path"],
            "old_ocr_date": s["ocr_date"],
            "new_ocr_date": prev["ocr_date"],
            "new_ocr": prev["ocr"],
            "fm": s["fm"],
            "commentary": s["commentary"],
        })

    print(f"=== Plan: shift OCR backward by 1 for {len(plans)} seeds ===")
    print()
    for p in plans[:8]:
        print(f"  No.{p['sno']:>3}: OCR {p['old_ocr_date']} → {p['new_ocr_date']}  ({p['path'].name})")
    if len(plans) > 8:
        print(f"  ... and {len(plans) - 8} more")
    print()
    print(f"=== Skip summary ===")
    for k, v in skip_reasons.items():
        print(f"  {k:25s}  {v}")
    print()

    if dry_run:
        print("(Dry run — no files written. Run without --dry-run to apply.)")
        return 0

    # Apply
    n_done = 0
    for p in plans:
        new_body = p["new_ocr"] + "\n\n" + p["commentary"] + "\n"
        new_raw = p["fm"] + new_body
        p["path"].write_text(new_raw, encoding="utf-8")
        n_done += 1

    print(f"✅ Applied {n_done} OCR shifts")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
