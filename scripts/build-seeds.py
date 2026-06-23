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


SENTENCE_FINAL = "。！？.!?…"


def reflow_ocr_text(text: str) -> str:
    """Merge OCR's image-width-imposed line breaks; preserve paragraph breaks.

    Rules:
      - Blank line = paragraph break, preserve
      - Within paragraph, if previous line ends with sentence-final punctuation
        (。！？.!?…) → keep the break
      - Otherwise → merge: no separator if CJK-CJK boundary, single space if any Latin

    This recovers natural sentence flow from OCR output where each line in the
    image (limited by image width) becomes its own physical line.
    """
    paragraphs = re.split(r"\n\s*\n", text.strip())
    out_paragraphs = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        merged: list[str] = []
        for line in lines:
            if not merged:
                merged.append(line)
                continue
            prev = merged[-1]
            last_char = prev[-1]
            if last_char in SENTENCE_FINAL:
                merged.append(line)
            else:
                # Include CJK punctuation + fullwidth forms so "，" / "、" → no space
                cjk_re = r"[　-〿一-鿿぀-ヿ＀-￯]"
                is_cjk_prev = bool(re.match(cjk_re, last_char))
                is_cjk_next = bool(re.match(cjk_re, line[0]))
                sep = "" if (is_cjk_prev and is_cjk_next) else " "
                merged[-1] = prev + sep + line
        out_paragraphs.append("\n".join(merged))
    return "\n\n".join(out_paragraphs)


def _strip_blockquote_prefix(line: str) -> str:
    """Strip leading `>` markdown blockquote marker from a line.

    `> foo` → `foo`, `>foo` → `foo`, `>` → ``, `> > nested` → `> nested`.
    """
    s = line.strip()
    if s == ">":
        return ""
    if s.startswith("> "):
        return s[2:]
    if s.startswith(">"):
        return s[1:].lstrip()
    return s


def _block_to_quote_text(block_lines: list[str]) -> str:
    """Convert a block of `>`-prefixed lines (one quote) to clean text."""
    text_lines = [_strip_blockquote_prefix(ln) if ln.strip() else "" for ln in block_lines]
    text = "\n".join(text_lines).strip()
    return reflow_ocr_text(text) if text else ""


# Commentary header pattern: e.g. "12月14日，No.348" / "12月19日，No. 353"
COMMENTARY_HEADER = re.compile(r"^\s*\d+月\d+日[，,]\s*[Nn][oO]\.?\s*\d+")


def _is_quote_terminator(line: str) -> bool:
    """Lines that DEFINITELY end a blockquote run, even if no blank precedes.

    Used for lazy plain-text continuation: once we're inside a `>` run and
    encounter plain text, it's quote content unless it matches one of these.
    """
    s = line.strip()
    if not s:
        return False  # blank handled separately
    if COMMENTARY_HEADER.match(line):
        return True
    if s.startswith("#"):
        return True  # markdown heading or hashtag — not quote content
    return False


def split_ocr_and_body(body: str) -> tuple[list[dict], str]:
    """Split body into OCR quotes + Jason's commentary.

    Lazy markdown semantics: a blockquote run starts at the first `>` line
    and continues through (a) more `>` lines, (b) `---` / blank separators
    when followed by more quote content, (c) plain text lines that are
    quote continuations. The run ends on a blank-with-no-more-quote-ahead,
    or a definite terminator (M月D日 commentary header, `#` heading/hashtag).

    Pragmatic, not strict CommonMark — Jason's OCR-pasted content often has
    `>` markers around plain text rather than `> ` on every line. Parser
    follows the visual intent rather than literal markdown.
    """
    lines = body.split("\n")
    quotes: list[dict] = []
    leftover: list[str] = []
    seen_commentary = False
    i = 0
    n = len(lines)

    while i < n:
        if not lines[i].strip().startswith(">"):
            leftover.append(lines[i])
            if lines[i].strip() and lines[i].strip() != "---":
                seen_commentary = True
            i += 1
            continue

        # Found a `>` — position: trailing if commentary already seen, else leading.
        # Lets the renderer keep a quote at the END (after Jason's commentary) instead
        # of hoisting every blockquote to the top of the card.
        quote_pos = "trail" if seen_commentary else "lead"
        # pop trailing separators from leftover (OCR buffer noise)
        while leftover and (leftover[-1].strip() == "" or leftover[-1].strip() == "---"):
            leftover.pop()

        # Collect run
        run: list[str] = []
        while i < n:
            s = lines[i].strip()
            if s.startswith(">"):
                run.append(lines[i])
                i += 1
                continue
            if s == "" or s == "---":
                # Separator — peek past more separators for `>`
                j = i
                while j < n and (lines[j].strip() == "" or lines[j].strip() == "---"):
                    j += 1
                if j < n and lines[j].strip().startswith(">"):
                    while i < j:
                        run.append(lines[i])
                        i += 1
                    continue
                break
            # Plain text within run — lazy quote continuation, unless terminator
            if _is_quote_terminator(lines[i]):
                break
            run.append(lines[i])
            i += 1

        # Run ended. Skip trailing separators so they don't pollute body.
        while i < n and (lines[i].strip() == "" or lines[i].strip() == "---"):
            i += 1

        # Split run by `---` into individual quote blocks
        block: list[str] = []
        for ln in run:
            if ln.strip() == "---":
                text = _block_to_quote_text(block)
                if text:
                    quotes.append({"text": text, "pos": quote_pos})
                block = []
            else:
                block.append(ln)
        text = _block_to_quote_text(block)
        if text:
            quotes.append({"text": text, "pos": quote_pos})

    commentary = "\n".join(leftover).strip()
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


EXCLUDE_TAGS = {"playbook", "playgrounds", "partnership"}  # 3pwriting major_tags, not seed tags


IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def extract_media(text: str) -> tuple[list, str]:
    """Extract markdown image refs into media list; return (media, text_without_imgs)."""
    media: list[dict] = []

    def _swap(m: re.Match) -> str:
        media.append({"type": "image", "url": m.group(2), "alt": m.group(1) or ""})
        return ""

    cleaned = IMG_RE.sub(_swap, text)
    # collapse triple-newlines that result from removed lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return media, cleaned


def build_seed(fm: dict, body: str, file_id: str) -> dict:
    media, body = extract_media(body)
    quotes, commentary = split_ocr_and_body(body)
    all_text = " ".join([q["text"] for q in quotes] + [commentary])
    raw_tags = fm.get("tags", [])
    tags = [t for t in raw_tags if t not in EXCLUDE_TAGS]
    # Filename is the source of truth for id. If frontmatter `id:` disagrees
    # (e.g. a seed was renamed but its frontmatter not updated), the filename
    # wins and we warn — so renames never silently break lineage/permalinks.
    fm_id = fm.get("id", "")
    if fm_id and fm_id != file_id:
        print(f"  ⚠️  {file_id}: frontmatter id '{fm_id}' ≠ filename — using filename")
    seed = {
        "id": file_id,
        "ts": fm.get("ts", ""),
        "tags": tags,
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
        "search_text": make_search_text(quotes, commentary, tags),
        "media_count": len(media),
    }
    if media:
        seed["media"] = media
    # Optional fields, only emit if present
    for opt in ("sprouted_into", "archived_at", "derived_from", "updated_at"):
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
        seeds.append(build_seed(parsed["frontmatter"], parsed["body"], path.stem))

    # Normalize derived_from to list[str], compute derived_descendants reverse map
    ts_by_id = {s["id"]: s["ts"] for s in seeds}
    descendants: dict[str, list[str]] = {}
    for s in seeds:
        df = s.get("derived_from")
        if df is None:
            continue
        parents = df if isinstance(df, list) else [df]
        s["derived_from"] = parents
        for parent_id in parents:
            if parent_id == s["id"]:
                print(f"  ⚠️  {s['id']}: derived_from references self, skipping")
                continue
            if parent_id not in ts_by_id:
                print(f"  ⚠️  {s['id']}: derived_from '{parent_id}' not found")
            descendants.setdefault(parent_id, []).append(s["id"])
    for s in seeds:
        kids = descendants.get(s["id"])
        if kids:
            kids.sort(key=lambda cid: ts_by_id.get(cid, ""), reverse=True)
            s["derived_descendants"] = kids

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
