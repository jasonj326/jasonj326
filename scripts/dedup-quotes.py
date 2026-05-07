#!/usr/bin/env python3
"""dedup-quotes.py — Remove duplicate OCR quote blocks within each seed.

Many cackle seeds have FB-album-split images that capture the same content
twice (zh, en, zh, en). The OCR'd them all, leaving redundant quote blocks.
This script keeps the first occurrence of each unique-content block.

Detection:
  Each '> ...' blockquote section is normalized (strip date stamp,
  percentage stamps, @ mentions, # hashtags, all whitespace + punctuation),
  then compared. Identical normalized strings = duplicate, drop the later one.

Untouched: zh-vs-en pairs (different content), partial-overlap fragments
(different normalized strings), body commentary, frontmatter (except
multi_image flag, which is updated to reflect post-dedup count).

Usage:
  python3 scripts/dedup-quotes.py --dry-run
  python3 scripts/dedup-quotes.py
"""

from __future__ import annotations

import re
import sys
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


def split_ocr_and_commentary(body: str) -> tuple[list[str], str]:
    """Walk lines: OCR phase = '>' / '---' / empty; first non-OCR line starts commentary.
    Returns (list of quote-block strings, commentary string)."""
    lines = body.split("\n")
    commentary_start = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(">") or s == "---" or s == "":
            continue
        commentary_start = i
        break

    ocr_lines = lines[:commentary_start]
    commentary = "\n".join(lines[commentary_start:]).rstrip()

    # Split OCR lines into quote groups by standalone '---'
    groups: list[list[str]] = []
    current: list[str] = []
    for line in ocr_lines:
        if line.strip() == "---":
            if current and any(ln.strip() for ln in current):
                groups.append(current)
            current = []
        else:
            current.append(line)
    if current and any(ln.strip() for ln in current):
        groups.append(current)

    blocks = ["\n".join(g).strip("\n") for g in groups]
    return blocks, commentary


def normalize_for_dedup(block: str) -> str:
    """Strip date stamps, % stamps, @-handles, #hashtags, all whitespace + punctuation."""
    text = "\n".join(line.lstrip(">").strip() for line in block.split("\n"))
    # Remove date stamps
    text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", text)
    # Remove percentage stamps
    text = re.sub(r"\d+(\.\d+)?\s*%", "", text)
    # Remove @-handles + #hashtags
    text = re.sub(r"@\S+", "", text)
    text = re.sub(r"#\S+", "", text)
    # Strip all whitespace + common punctuation for comparison
    text = re.sub(r"[\s\.,，。！？!?\'\"`：:;；()（）<>《》—\-_*]", "", text)
    return text


def update_multi_image(fm: str, multi: bool) -> str:
    """Set multi_image field. Add if missing (rare)."""
    val = "true" if multi else "false"
    if re.search(r"^multi_image:", fm, re.MULTILINE):
        return re.sub(r"^multi_image:.*$", f"multi_image: {val}", fm, count=1, flags=re.MULTILINE)
    # Insert after ocr_pending or before closing ---
    return fm.replace("\n---\n", f"\nmulti_image: {val}\n---\n", 1)


def main(dry_run: bool) -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ {POSTS_DIR} not found", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.md"))
    print(f"Scanning {len(files)} seed files")
    print()

    n_changed = 0
    n_total_blocks_removed = 0
    histogram: dict[int, int] = {}  # blocks_removed -> count

    for path in files:
        raw = path.read_text(encoding="utf-8")
        fm, body = split_fm_body(raw)
        if not fm:
            continue

        blocks, commentary = split_ocr_and_commentary(body)
        if len(blocks) <= 1:
            continue

        # Dedup
        seen: set[str] = set()
        kept: list[str] = []
        for block in blocks:
            norm = normalize_for_dedup(block)
            if not norm:
                # Empty after normalization (e.g., only date stamp) — keep one,
                # treat empties as "same"
                if "" in seen:
                    continue
                seen.add("")
                kept.append(block)
            elif norm not in seen:
                seen.add(norm)
                kept.append(block)

        removed = len(blocks) - len(kept)
        if removed == 0:
            continue

        n_changed += 1
        n_total_blocks_removed += removed
        histogram[removed] = histogram.get(removed, 0) + 1

        # Rebuild body
        ocr_section = "\n\n---\n\n".join(kept)
        new_body = ocr_section + ("\n\n" + commentary if commentary else "") + "\n"

        # Update multi_image flag
        new_fm = update_multi_image(fm, multi=(len(kept) > 1))
        new_raw = new_fm + new_body

        action = f"  {path.name}: {len(blocks)} → {len(kept)} blocks (-{removed})"
        print(action)

        if not dry_run:
            path.write_text(new_raw, encoding="utf-8")

    print()
    print("=== Summary ===")
    print(f"  Files scanned:        {len(files)}")
    print(f"  {'Would change' if dry_run else 'Changed'}:         {n_changed}")
    print(f"  Total blocks removed: {n_total_blocks_removed}")
    if histogram:
        print(f"  Distribution (blocks removed → seed count):")
        for k in sorted(histogram):
            print(f"    -{k}: {histogram[k]} seeds")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
