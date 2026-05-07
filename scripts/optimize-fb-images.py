#!/usr/bin/env python3
"""optimize-fb-images.py — Resize/optimize FB export images, copy to seeds/assets/.

Reads:
  facebook 猜招先生/.../每日猜招/assets/*.{jpg,png}

Writes:
  seeds/assets/<filename>  (resized to max 1200px wide, JPG quality 80)

Skips:
  Already-existing seeds/assets/ files (idempotent re-run).
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "facebook 猜招先生" / "this_profile's_activity_across_facebook" / "每日猜招" / "assets"
DST = REPO / "seeds" / "assets"
POSTS = REPO / "seeds" / "posts"

MAX_DIM = 1200
JPG_QUALITY = 80


def collect_referenced_images() -> set[str]:
    """Find all asset filenames referenced from seed posts."""
    refs: set[str] = set()
    for f in POSTS.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"!\[\[assets/([^\]]+)\]\]", text):
            refs.add(m.group(1))
    return refs


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"FB assets dir not found: {SRC}")
    DST.mkdir(parents=True, exist_ok=True)

    refs = collect_referenced_images()
    print(f"Referenced images: {len(refs)}")

    processed = 0
    skipped = 0
    total_before = 0
    total_after = 0

    for name in sorted(refs):
        src = SRC / name
        dst = DST / name
        if not src.is_file():
            print(f"  ⚠️  Source missing: {name}")
            continue
        if dst.exists():
            skipped += 1
            continue

        size_before = src.stat().st_size
        ext = src.suffix.lower()
        cmd = ["sips", "-Z", str(MAX_DIM)]
        if ext in (".jpg", ".jpeg"):
            cmd += ["-s", "formatOptions", str(JPG_QUALITY)]
        cmd += [str(src), "--out", str(dst)]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"  ❌ Failed: {name} — {result.stderr.decode()[:200]}")
            continue
        size_after = dst.stat().st_size
        total_before += size_before
        total_after += size_after
        processed += 1
        if processed % 50 == 0:
            print(f"  ... {processed} processed")

    print()
    print(f"Processed: {processed}")
    print(f"Skipped (already existed): {skipped}")
    print(f"Total before: {total_before / 1024 / 1024:.1f} MB")
    print(f"Total after:  {total_after / 1024 / 1024:.1f} MB")
    if total_before:
        print(f"Reduction:    {(1 - total_after / total_before) * 100:.0f}%")


if __name__ == "__main__":
    main()
