#!/usr/bin/env python3
"""migrate-fb-cackle.py — Replace cackle seeds mrps032-mrps334 with cleaner FB export.

Reads:
  facebook 猜招先生/this_profile's_activity_across_facebook/每日猜招/2021每日猜招 No. N.md

Writes:
  seeds/posts/YYYY-MM-DD-mrpsNNN.md (filename derived from day-count rule:
  day 0 = 2020-12-31, day 32 = 2021-02-01, day 334 = 2021-11-30)

Deletes:
  seeds/posts/* with source_no in [32, 334] from existing cackle data.

Run from repo root: python3 scripts/migrate-fb-cackle.py
"""
from __future__ import annotations
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "facebook 猜招先生" / "this_profile's_activity_across_facebook" / "每日猜招"
POSTS = REPO / "seeds" / "posts"

EPOCH = date(2020, 12, 31)
N_RANGE = (32, 334)


def parse_fb_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"No frontmatter: {path.name}")
    end = raw.find("\n---\n", 4)
    fm_raw = raw[4:end]
    body = raw[end + 5:].strip()

    # Extract date and tags
    fb_date_m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", fm_raw, re.MULTILINE)
    fb_date = fb_date_m.group(1) if fb_date_m else None

    title_m = re.search(r'^title:\s*"([^"]+)"', fm_raw, re.MULTILINE)
    title = title_m.group(1) if title_m else None

    return {"fb_date": fb_date, "title": title, "body": body}


def main():
    if not SRC_DIR.is_dir():
        raise SystemExit(f"FB source dir not found: {SRC_DIR}")

    # Step 1: Delete existing cackle files in N-range
    deleted = 0
    for f in sorted(POSTS.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^source_no:\s*(\d+)", text, re.MULTILINE)
        if m:
            n = int(m.group(1))
            if N_RANGE[0] <= n <= N_RANGE[1]:
                f.unlink()
                deleted += 1
    print(f"Deleted {deleted} existing cackle files (mrps032-mrps334 range)")

    # Step 2: Migrate FB files
    written = 0
    warnings = []
    for src in sorted(SRC_DIR.glob("*.md")):
        if "No. " not in src.name:
            continue
        try:
            n = int(src.stem.split("No. ")[1].strip())
        except (IndexError, ValueError):
            continue
        if not (N_RANGE[0] <= n <= N_RANGE[1]):
            continue

        parsed = parse_fb_file(src)
        derived_date = EPOCH + timedelta(days=n)
        date_str = derived_date.isoformat()
        seed_id = f"{date_str}-mrps{n:03d}"

        # Sanity check body header vs derived date
        body_md = re.search(r"(\d+)月(\d+)日", parsed["body"])
        if body_md:
            bm, bd = int(body_md.group(1)), int(body_md.group(2))
            if (bm, bd) != (derived_date.month, derived_date.day):
                warnings.append(
                    f"  No.{n}: body says {bm}月{bd}日 but derived={derived_date}"
                )

        # Build new frontmatter (cackle seed schema)
        fm_lines = [
            "---",
            f'id: "{seed_id}"',
            f'ts: "{date_str}T00:00:00+08:00"',
            f'fb_date: "{parsed["fb_date"]}"' if parsed["fb_date"] else "fb_date:",
            "tags:",
            "  - playgrounds",
            "  - y2021",
            "  - playbook",
            "  - partnership",
            'source: "cackle"',
            f"source_no: {n}",
            f'source_title: "{parsed["title"]}"' if parsed["title"] else 'source_title:',
            "multi_image: false",
            "ocr_pending: false",
            "category: null",
            "---",
            "",
            parsed["body"],
            "",
        ]
        out_path = POSTS / f"{seed_id}.md"
        out_path.write_text("\n".join(fm_lines), encoding="utf-8")
        written += 1

    print(f"Wrote {written} new seed files")
    if warnings:
        print(f"\n⚠️  Body M月D日 vs N-derived date mismatches ({len(warnings)}):")
        for w in warnings:
            print(w)
        print("(These are body typos; filename uses day-count rule as truth.)")


if __name__ == "__main__":
    main()
