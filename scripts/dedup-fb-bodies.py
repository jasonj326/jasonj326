#!/usr/bin/env python3
"""dedup-fb-bodies.py — Remove duplicate body content in FB-export seeds.

The FB export produced .md files where the body appears twice (second copy
with each line prefixed by a leading space). Pattern:

    [header line: M月D日，No.X，topic]
    [body lines]
    ...
    [hashtags]
    [SAME header line]      ← duplicate starts
    [body lines with leading space]
    ...
    [hashtags with leading space]

    ---
    ![](image)              ← optional image section after duplicate

This script:
  1. Detects the second occurrence of the M月D日，No.X header
  2. Truncates everything from that point through the duplicate body
  3. Preserves any trailing `---\\n\\n![](image)` section
"""
from __future__ import annotations
import re
from pathlib import Path

POSTS = Path(__file__).resolve().parent.parent / "seeds" / "posts"
HEADER_RE = re.compile(r"\d+月\d+日[，,]\s*[Nn][oO]\.?\s*\d+")
IMG_SECTION_RE = re.compile(r"\n+---\n+!\[")


def dedup_body(raw: str) -> tuple[str, bool]:
    """Return (new_text, changed)."""
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return raw, False
    pre, fm, body = parts[0], parts[1], parts[2]

    matches = list(HEADER_RE.finditer(body))
    if len(matches) < 2:
        return raw, False
    if matches[0].group() != matches[1].group():
        # Different headers — not a self-dup, skip
        return raw, False

    h2_start = matches[1].start()
    body_pre = body[:h2_start].rstrip()
    after_h2 = body[h2_start:]

    img_match = IMG_SECTION_RE.search(after_h2)
    if img_match:
        # Keep image section starting at `---`
        img_section = after_h2[img_match.start():].lstrip("\n")
        new_body = f"{body_pre}\n\n{img_section}"
    else:
        new_body = body_pre + "\n"

    new_text = f"{pre}---{fm}---\n{new_body}"
    if not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, True


def main() -> None:
    changed = 0
    for f in sorted(POSTS.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        new_text, did_change = dedup_body(text)
        if did_change:
            f.write_text(new_text, encoding="utf-8")
            changed += 1
    print(f"Deduped {changed} files")


if __name__ == "__main__":
    main()
