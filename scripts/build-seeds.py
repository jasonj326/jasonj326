#!/usr/bin/env python3
"""build-seeds.py — Generate seeds/seeds.json from seeds/posts/*.md

Reads:
  seeds/posts/*.md (source markdown files)

Writes:
  seeds/seeds.json (sorted desc by ts; full data + derived fields)

Derived fields (frontend treats read-only):
  word_count   — CJK chars + Latin word tokens
  excerpt      — first ~80 chars of Jason's commentary, sentence-boundary aware
  search_text  — lowercase normalized text for fast client-side search
  media_count  — 0 for now (cackle seeds); populated when new R2-backed seeds arrive
  ocr_quotes   — list of {text} extracted from blockquote section
  body_text    — body stripped of OCR section (Jason's commentary only)

Usage:
  python3 scripts/build-seeds.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "seeds" / "posts"
OUTPUT = REPO_ROOT / "seeds" / "seeds.json"


def parse_md(raw: str) -> dict | None:
    """Parse markdown with YAML-ish frontmatter."""
    if not raw.startswith("---\n"):
        return None
    end = raw.find("\n---\n", 4)
    if end == -1:
        return None
    fm_raw = raw[4:end]
    body = raw[end + 5 :].strip()

    fm: dict = {}
    current_list: list | None = None
    for line in fm_raw.split("\n"):
        if line.startswith("  - "):
            if current_list is not None:
                current_list.append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        current_list = None
        key, _, val = line.partition(":")
        key = key.strip()
        val_s = val.strip()
        if val_s == "":
            fm[key] = []
            current_list = fm[key]
        elif val_s == "null":
            fm[key] = None
        elif val_s == "true":
            fm[key] = True
        elif val_s == "false":
            fm[key] = False
        elif val_s == "[]":
            fm[key] = []
        elif val_s.lstrip("-").isdigit():
            fm[key] = int(val_s)
        else:
            fm[key] = val_s.strip('"').strip("'")
    return {"frontmatter": fm, "body": body}


def split_ocr_and_body(body: str) -> tuple[list[dict], str]:
    """Split body into OCR blockquotes (at top) + Jason's commentary.

    OCR section format:
      > line one of quote
      > line two
      >

      ---

      > another quote
      > ...

    Returns (ocr_quotes_list, commentary_text).
    """
    lines = body.split("\n")
    in_ocr = False
    last_ocr_idx = -1
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith(">") or stripped == ">":
            in_ocr = True
            last_ocr_idx = i
            i += 1
        elif stripped == "---" and in_ocr:
            i += 1
            in_ocr = False
        elif stripped == "":
            i += 1
        else:
            break

    if last_ocr_idx == -1:
        return [], body.strip()

    ocr_section = "\n".join(lines[: last_ocr_idx + 1])
    commentary = "\n".join(lines[i:]).strip()

    # Split by '---' separator and parse each blockquote
    quotes: list[dict] = []
    for block in re.split(r"\n+---\n+", ocr_section):
        text_lines = []
        for ln in block.split("\n"):
            if ln.startswith("> "):
                text_lines.append(ln[2:])
            elif ln.strip() == ">":
                text_lines.append("")
        text = "\n".join(text_lines).strip()
        if text:
            quotes.append({"text": text})

    return quotes, commentary


def count_words(text: str) -> int:
    """CJK chars + Latin word tokens."""
    cjk = re.findall(r"[一-鿿぀-ゟ゠-ヿ]", text)
    latin = re.findall(r"\b[a-zA-Z]+\b", text)
    return len(cjk) + len(latin)


def make_excerpt(commentary: str, fallback: str = "", max_chars: int = 80) -> str:
    """Sentence-boundary aware excerpt."""
    text = (commentary or fallback).strip().replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    boundaries = [truncated.rfind(c) for c in ["。", "！", "？", ".", "!", "?"]]
    last = max(boundaries)
    if last > max_chars - 30:
        return truncated[: last + 1]
    return truncated + "…"


def make_search_text(quotes: list, commentary: str, tags: list) -> str:
    """Normalized lowercase concat of quotes + body + tags for client search."""
    parts = [q["text"] for q in quotes] + [commentary] + tags
    text = " ".join(parts).lower()
    text = re.sub(r"[^一-鿿぀-ゟ゠-ヿ\w\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_seed(fm: dict, body: str) -> dict:
    quotes, commentary = split_ocr_and_body(body)
    all_text = " ".join([q["text"] for q in quotes] + [commentary])
    seed = {
        "id": fm.get("id", ""),
        "ts": fm.get("ts", ""),
        "tags": fm.get("tags", []),
        "source": fm.get("source"),
        "source_no": fm.get("source_no"),
        "source_title": fm.get("source_title"),
        "multi_image": fm.get("multi_image", False),
        "ocr_pending": fm.get("ocr_pending", False),
        "category": fm.get("category"),
        "ocr_quotes": quotes,
        "body_text": commentary,
        "word_count": count_words(all_text),
        "excerpt": make_excerpt(commentary, quotes[0]["text"] if quotes else ""),
        "search_text": make_search_text(quotes, commentary, fm.get("tags", [])),
        "media_count": 0,
    }
    # Optional fields, only emit if present
    for opt in ("sprouted_into", "archived_at", "derived_from", "media"):
        if opt in fm and fm[opt] not in (None, []):
            seed[opt] = fm[opt]
    return seed


def main() -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ Posts dir not found: {POSTS_DIR}", file=sys.stderr)
        return 1

    md_files = sorted(POSTS_DIR.glob("*.md"))
    print(f"Found {len(md_files)} seed files in {POSTS_DIR.relative_to(REPO_ROOT)}")

    seeds: list[dict] = []
    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        parsed = parse_md(raw)
        if parsed is None:
            print(f"  ⚠️  Skip (parse fail): {path.name}")
            continue
        seeds.append(build_seed(parsed["frontmatter"], parsed["body"]))

    seeds.sort(key=lambda s: s["ts"], reverse=True)

    OUTPUT.write_text(json.dumps(seeds, ensure_ascii=False, indent=2), encoding="utf-8")

    size = OUTPUT.stat().st_size
    avg_wc = sum(s["word_count"] for s in seeds) / max(len(seeds), 1)
    print()
    print(f"✅ Wrote {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"   Seeds:           {len(seeds)}")
    print(f"   Size:            {size:,} bytes ({size / 1024:.1f} KB)")
    print(f"   Avg word count:  {avg_wc:.0f}")
    print(f"   OCR pending:     {sum(1 for s in seeds if s['ocr_pending'])}")
    print(f"   Multi-image:     {sum(1 for s in seeds if s['multi_image'])}")
    print(f"   Image-speaks:    {sum(1 for s in seeds if s['category'] == 'image_speaks')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
