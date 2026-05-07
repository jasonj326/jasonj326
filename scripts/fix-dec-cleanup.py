#!/usr/bin/env python3
"""fix-dec-cleanup.py — One-shot cleanup of December edit residue.

Aligns source_no + source_title to id (id = canonical) for misaligned seeds.
Renames the typo'd file. Migrates pasted images from repo root to seeds/assets/.
Converts Obsidian-style ![[Pasted image ...]] wikilinks to standard markdown
image references with web-accessible paths.

Usage: python3 scripts/fix-dec-cleanup.py
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO_ROOT / "seeds" / "posts"
ASSETS_DIR = REPO_ROOT / "seeds" / "assets"


def fix_field(raw: str, key: str, new_value: str) -> str:
    """Replace `key: ...` line value (with or without quotes) with new_value (quoted)."""
    pattern = rf"^({re.escape(key)}:\s*)\"?[^\"\n]*\"?(\s*)$"
    return re.sub(pattern, lambda m: f'{m.group(1)}"{new_value}"{m.group(2)}', raw, count=1, flags=re.MULTILINE)


def fix_field_int(raw: str, key: str, new_int: int) -> str:
    pattern = rf"^({re.escape(key)}:\s*)\d+(\s*)$"
    return re.sub(pattern, lambda m: f"{m.group(1)}{new_int}{m.group(2)}", raw, count=1, flags=re.MULTILINE)


def main() -> int:
    # Step 1: Rename typo file 2021-12-15-mrps350.md → 2021-12-15-mrps349.md
    typo = POSTS_DIR / "2021-12-15-mrps350.md"
    target = POSTS_DIR / "2021-12-15-mrps349.md"
    if typo.exists():
        if target.exists():
            print(f"⚠️  {target.name} already exists, skipping rename")
        else:
            typo.rename(target)
            print(f"  Renamed {typo.name} → {target.name}")

    # Step 2: Sync source_no + source_title to id across all .md
    n_synced = 0
    for path in sorted(POSTS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        id_m = re.search(r'id:\s*"?(\d{4}-\d{2}-\d{2}-mrps(\d+))"?', raw)
        if not id_m:
            continue
        seed_id = id_m.group(1)
        id_num = int(id_m.group(2))

        src_m = re.search(r"source_no:\s*(\d+)", raw)
        title_m = re.search(r'source_title:\s*"?([^"\n]+)"?', raw)

        changed = False
        if src_m and int(src_m.group(1)) != id_num:
            raw = fix_field_int(raw, "source_no", id_num)
            changed = True
        expected_title = f"2021每日猜招 No. {id_num}"
        if title_m:
            current_title = title_m.group(1).strip()
            if current_title != expected_title:
                raw = fix_field(raw, "source_title", expected_title)
                changed = True

        if changed:
            path.write_text(raw, encoding="utf-8")
            print(f"  Synced {path.name}: source_no/title → {id_num}")
            n_synced += 1

    # Step 3: Move referenced "Pasted image XXX.png" files to seeds/assets/
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    referenced_imgs: set[str] = set()
    for path in POSTS_DIR.glob("*.md"):
        raw = path.read_text(encoding="utf-8")
        for m in re.finditer(r"!\[\[Pasted image (\d+\.png)\]\]", raw):
            referenced_imgs.add(m.group(1))

    moved = []
    for src in sorted(REPO_ROOT.glob("Pasted image *.png")):
        digit_match = re.search(r"(\d+)\.png$", src.name)
        if not digit_match:
            continue
        digit = digit_match.group(1) + ".png"
        if digit in referenced_imgs:
            new_name = f"cackle-{digit}"
            dest = ASSETS_DIR / new_name
            if not dest.exists():
                shutil.move(str(src), str(dest))
                moved.append((src.name, new_name))
                print(f"  Moved {src.name} → seeds/assets/{new_name}")

    # Step 4: Convert wikilinks ![[Pasted image XXX.png]] → standard ![](/seeds/assets/cackle-XXX.png)
    n_links = 0
    for path in POSTS_DIR.glob("*.md"):
        raw = path.read_text(encoding="utf-8")

        def replace(m: re.Match) -> str:
            digit = m.group(1)
            return f"![](/seeds/assets/cackle-{digit}.png)"

        new_raw, count = re.subn(r"!\[\[Pasted image (\d+\.png)\]\]", replace, raw)
        if count:
            path.write_text(new_raw, encoding="utf-8")
            n_links += count
            print(f"  Converted {count} wikilink(s) in {path.name}")

    print()
    print(f"=== Summary ===")
    print(f"  source_no/title synced: {n_synced} seeds")
    print(f"  Images moved:           {len(moved)}")
    print(f"  Wikilinks converted:    {n_links}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
