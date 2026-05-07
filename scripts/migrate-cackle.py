#!/usr/bin/env python3
"""migrate-cackle.py — Migrate 366 cackle seeds from Obsidian vault into seed wall source format.

Reads (READ-ONLY, no modifications to vault):
  /Users/jsl/Documents/每日猜招/每日猜招_圖檔文字.md  (master OCR file, 362 entries)
  /Users/jsl/Documents/每日猜招/2021每日猜招 No. X.md  (366 source posts)

Writes:
  seeds/posts/{seed_id}.md  (366 transformed seed source files)

Behavior:
  - 362 seeds with OCR: original quote inlined as blockquote at top of body.
    Multiple OCR images per seed: blockquotes separated by '---' lines.
  - 4 seeds without OCR (No. 262/338/347/351): no quote inlined,
    flagged ocr_pending: true.
  - 52 seeds tagged 一圖勝千言 (hashtag in body): flagged category: image_speaks.
  - All seeds get source: cackle + source_no for traceability.

Usage:
  python3 migrate-cackle.py            # write to seeds/posts/
  python3 migrate-cackle.py --dry-run  # preview without writing
  python3 migrate-cackle.py --verbose  # per-file log
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

VAULT = Path("/Users/jsl/Documents/每日猜招")
MASTER = VAULT / "每日猜招_圖檔文字.md"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "seeds" / "posts"


def parse_master_ocr() -> dict[int, list[tuple[str, str]]]:
    """Parse master OCR file → {seed_num: [(filename, ocr_text), ...]}."""
    text = MASTER.read_text(encoding="utf-8")
    result: dict[int, list[tuple[str, str]]] = defaultdict(list)

    sections = re.split(r"^## No\. (\d+)\s*$", text, flags=re.MULTILINE)
    # sections = ["preamble", "0", "content for 0", "1", "content for 1", ...]
    for i in range(1, len(sections), 2):
        seed_num = int(sections[i])
        section_body = sections[i + 1]
        # Each image: **filename.ext**\n\n```\nOCR text\n```
        pattern = re.compile(
            r"\*\*([^*]+\.(?:png|jpg|jpeg))\*\*\s*\n+```\s*\n(.*?)\n```",
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(section_body):
            filename = match.group(1).strip()
            ocr_text = match.group(2).strip()
            if ocr_text:
                result[seed_num].append((filename, ocr_text))

    return dict(result)


def parse_seed_file(path: Path) -> dict | None:
    """Read a vault .md → {frontmatter: dict, body: str}."""
    raw = path.read_text(encoding="utf-8")
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
        elif ":" in line:
            current_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                fm[key] = []
                current_list = fm[key]
            else:
                fm[key] = val.strip('"').strip("'")
    return {"frontmatter": fm, "body": body}


def extract_seed_num(filename: str) -> int | None:
    """'2021每日猜招 No. 100.md' → 100."""
    match = re.search(r"No\.\s*(\d+)\.md", filename)
    return int(match.group(1)) if match else None


def parse_body_date(body: str, fb_date: str) -> str | None:
    """Extract Jason's stated date from body's first content line.

    The FB metadata date (`fb_date`, e.g. '2020-12-30') is the day Jason
    *wrote* the post. The first body line contains the date the seed is
    *for* (e.g. '12/31/2020' or '4月10日'). Body date is the canonical
    'seed date'.

    Returns 'YYYY-MM-DD' string, or None if cannot parse.
    """
    if not fb_date or len(fb_date) != 10:
        return None
    fb_year = int(fb_date[0:4])
    fb_month = int(fb_date[5:7])

    first_line = body.lstrip().split("\n", 1)[0]

    # Pattern 1: MM/DD/YYYY (explicit year, e.g. '12/31/2020')
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", first_line)
    if m:
        mm, dd, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yyyy:04d}-{mm:02d}-{dd:02d}"

    # Pattern 2: M月D日 (Chinese, year inferred from fb context)
    m = re.search(r"(\d{1,2})月(\d{1,2})日", first_line)
    if m:
        bm, bd = int(m.group(1)), int(m.group(2))
        # Cross-year heuristic: fb in late year (Nov/Dec) and body in early year (Jan/Feb) → next year
        year = fb_year
        if fb_month >= 11 and bm <= 2:
            year = fb_year + 1
        elif fb_month <= 2 and bm >= 11:
            year = fb_year - 1
        return f"{year:04d}-{bm:02d}-{bd:02d}"

    return None


def strip_body(body: str) -> str:
    """Drop image wikilinks + embedded OCR section; keep just Jason's prose."""
    parts = re.split(r"\n+---\n+", body, maxsplit=1)
    return parts[0].strip()


def make_seed_id(date_str: str, seed_num: int) -> str:
    """'2021-04-09', 100 → '2021-04-09-mrps100'."""
    return f"{date_str}-mrps{seed_num:03d}"


def render_ocr_blocks(ocr_blocks: list[tuple[str, str]]) -> str:
    """Format OCR list as blockquote section: each quote prefixed '> ', multi-quote joined with '---'."""
    if not ocr_blocks:
        return ""
    quotes = []
    for _filename, text in ocr_blocks:
        # Each line of OCR text → '> line'; preserve internal blank lines as '>'
        quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in text.split("\n"))
        quotes.append(quoted)
    return "\n\n---\n\n".join(quotes)


def render_yaml(fm: dict) -> str:
    """Minimal YAML output — handles strings, ints, bools, nulls, list[str]."""
    lines = ["---"]
    for k, v in fm.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
        else:
            s = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{s}"')
    lines.append("---")
    return "\n".join(lines)


def build_seed_md(seed_num: int, fm: dict, body: str, ocr_blocks: list, has_image_speaks: bool) -> str:
    """Assemble the new seed .md content."""
    fb_date = fm.get("date", "0000-00-00")
    seed_date = parse_body_date(body, fb_date) or fb_date
    seed_id = make_seed_id(seed_date, seed_num)
    out_fm = {
        "id": seed_id,
        "ts": f"{seed_date}T00:00:00+08:00",
        "fb_date": fb_date,  # original FB metadata date (writing date) for traceability
        "tags": fm.get("tags", []),
        "source": "cackle",
        "source_no": seed_num,
        "source_title": fm.get("title", ""),
        "multi_image": len(ocr_blocks) > 1,
        "ocr_pending": len(ocr_blocks) == 0,
        "category": "image_speaks" if has_image_speaks else None,
    }

    parts = [render_yaml(out_fm)]
    ocr_section = render_ocr_blocks(ocr_blocks)
    if ocr_section:
        parts.append(ocr_section)
    parts.append(body.strip())
    return "\n\n".join(parts) + "\n"


def main(dry_run: bool, verbose: bool) -> int:
    if not VAULT.is_dir():
        print(f"❌ Vault not found: {VAULT}", file=sys.stderr)
        return 1
    if not MASTER.is_file():
        print(f"❌ Master OCR not found: {MASTER}", file=sys.stderr)
        return 1

    print("Parsing master OCR…")
    ocr_map = parse_master_ocr()
    print(f"  → {len(ocr_map)} seeds with OCR")

    seed_files = sorted(VAULT.glob("2021每日猜招 No. *.md"))
    print(f"Found {len(seed_files)} cackle .md files in vault")

    if not dry_run:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        # Clean stale output (so renames from old IDs to new IDs don't leave duplicates)
        for stale in OUTPUT.glob("*.md"):
            stale.unlink()
        print(f"Output → {OUTPUT.relative_to(REPO_ROOT)} (cleaned)")

    stats = {
        "total": 0,
        "with_ocr": 0,
        "ocr_pending": 0,
        "image_speaks": 0,
        "multi_image": 0,
        "skipped": 0,
    }

    for path in seed_files:
        seed_num = extract_seed_num(path.name)
        if seed_num is None:
            print(f"  ⚠️  Skip (no seed num): {path.name}")
            stats["skipped"] += 1
            continue

        parsed = parse_seed_file(path)
        if parsed is None:
            print(f"  ⚠️  Skip (parse fail): {path.name}")
            stats["skipped"] += 1
            continue

        fm = parsed["frontmatter"]
        body_full = parsed["body"]
        body = strip_body(body_full)
        ocr_blocks = ocr_map.get(seed_num, [])
        has_image_speaks = "一圖勝千言" in body_full

        new_md = build_seed_md(seed_num, fm, body, ocr_blocks, has_image_speaks)
        fb_date = fm.get("date", "0000-00-00")
        seed_date = parse_body_date(body, fb_date) or fb_date
        seed_id = make_seed_id(seed_date, seed_num)
        out_path = OUTPUT / f"{seed_id}.md"

        if not dry_run:
            out_path.write_text(new_md, encoding="utf-8")

        if verbose:
            flags = []
            if not ocr_blocks:
                flags.append("ocr_pending")
            if len(ocr_blocks) > 1:
                flags.append(f"multi×{len(ocr_blocks)}")
            if has_image_speaks:
                flags.append("image_speaks")
            tag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  No. {seed_num:3d} → {out_path.name}{tag_str}")

        stats["total"] += 1
        if ocr_blocks:
            stats["with_ocr"] += 1
        else:
            stats["ocr_pending"] += 1
        if has_image_speaks:
            stats["image_speaks"] += 1
        if len(ocr_blocks) > 1:
            stats["multi_image"] += 1

    print()
    print(f"=== Migration {'(dry run) ' if dry_run else ''}complete ===")
    print(f"  Total processed: {stats['total']}")
    print(f"  With OCR:        {stats['with_ocr']}")
    print(f"  Pending OCR:     {stats['ocr_pending']}")
    print(f"  Image-speaks:    {stats['image_speaks']}")
    print(f"  Multi-image OCR: {stats['multi_image']}")
    if stats["skipped"]:
        print(f"  Skipped:         {stats['skipped']}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(
        main(
            dry_run="--dry-run" in args,
            verbose="--verbose" in args,
        )
    )
