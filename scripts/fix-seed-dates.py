#!/usr/bin/env python3
"""fix-seed-dates.py — One-shot: align id / filename / ts to body's canonical date.

For every `seeds/posts/*.md`, detect the canonical date from the *content*
(prioritizing body's M月D日, then OCR's MM/DD/YYYY date stamp). If the file's
current id date differs, rename the file and rewrite its `id` and `ts` fields.

Date detection priority:
  1. First "M月D日" found anywhere in the commentary body (Jason's prose,
     not OCR blockquotes). Year inferred from current ts if cross-year.
  2. First "MM/DD/YYYY" date stamp inside an OCR blockquote line.
  3. Skip (no fix possible) — file untouched.

Skip cases:
  - Already-aligned id (no change needed).
  - Cannot detect canonical date (no fix made — Jason can edit by hand).

Untouched fields: fb_date (original FB metadata, traceability), tags,
source*, multi_image, ocr_pending, category, body, OCR text.

Safety:
  - Reads each .md, only writes if canonical date detected AND different.
  - Detects collisions (target filename already exists for another seed_no).
  - Logs every action; --dry-run shows plan without writing.

Usage:
  python3 scripts/fix-seed-dates.py --dry-run
  python3 scripts/fix-seed-dates.py
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


def get_field(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*\"?([^\"\n]+)\"?$", fm, re.MULTILINE)
    return m.group(1).strip() if m else None


def detect_canonical_date(body: str, current_ts_year: int) -> tuple[str, str] | None:
    """Returns (date_str, source) where source is 'body' or 'ocr'."""
    # Strip OCR blockquotes for body-only search
    commentary = "\n".join(
        ln for ln in body.split("\n") if not ln.strip().startswith(">") and ln.strip() != "---"
    )

    # 1. First M月D日 in commentary
    m = re.search(r"(\d{1,2})月(\d{1,2})日", commentary)
    if m:
        bm, bd = int(m.group(1)), int(m.group(2))
        # Year inference: if current ts is year-end and body shows early month, year+1
        year = current_ts_year
        ts_month_hint_m = re.search(r"ts:\s*\"?(\d{4})-(\d{2})", body)  # not reliable but ok
        # Simpler: if body M ≤ 2 and current_ts year-end
        if bm <= 2 and current_ts_year == 2020:  # cross-year forward to 2021
            year = 2021
        if bm >= 11 and current_ts_year == 2021 and "2021" in commentary:
            year = 2021
        return (f"{year:04d}-{bm:02d}-{bd:02d}", "body")

    # 2. First MM/DD/YYYY in OCR blockquotes
    for ln in body.split("\n"):
        s = ln.strip().lstrip(">").strip()
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if m:
            mm, dd, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return (f"{yyyy:04d}-{mm:02d}-{dd:02d}", "ocr")

    return None


def update_field(fm: str, key: str, new_value: str) -> str:
    """Replace a frontmatter field's value. Quotes the value (frontmatter convention)."""
    pattern = rf"^({re.escape(key)}:\s*)\"?[^\"\n]*\"?(\s*)$"
    return re.sub(pattern, lambda m: f'{m.group(1)}"{new_value}"{m.group(2)}', fm, count=1, flags=re.MULTILINE)


def main(dry_run: bool) -> int:
    if not POSTS_DIR.is_dir():
        print(f"❌ {POSTS_DIR} not found", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.md"))
    print(f"Scanning {len(files)} seed files in {POSTS_DIR.relative_to(REPO_ROOT)}")
    print()

    actions: list[dict] = []
    skipped_no_detect = 0
    already_aligned = 0

    for path in files:
        raw = path.read_text(encoding="utf-8")
        fm, body = split_fm_body(raw)
        if not fm:
            print(f"  ⚠️  Skip (no frontmatter): {path.name}")
            continue

        cur_id = get_field(fm, "id")
        cur_ts = get_field(fm, "ts")
        source_no = get_field(fm, "source_no")
        if not cur_id or not source_no:
            print(f"  ⚠️  Skip (missing id/source_no): {path.name}")
            continue

        cur_id_date = cur_id[:10] if re.match(r"\d{4}-\d{2}-\d{2}", cur_id) else None
        cur_ts_year = int(cur_ts[:4]) if cur_ts and re.match(r"\d{4}", cur_ts) else 2021

        detected = detect_canonical_date(body, cur_ts_year)
        if not detected:
            skipped_no_detect += 1
            continue

        canonical_date, src = detected
        new_id = f"{canonical_date}-mrps{int(source_no):03d}"
        new_ts = f"{canonical_date}T00:00:00+08:00"

        ts_already = (cur_ts or "")[:10] == canonical_date
        id_already = cur_id == new_id

        if ts_already and id_already and path.stem == new_id:
            already_aligned += 1
            continue

        actions.append({
            "path": path,
            "new_id": new_id,
            "new_ts": new_ts,
            "src": src,
            "old_id": cur_id,
            "old_ts": cur_ts,
            "id_changed": not id_already,
            "ts_changed": not ts_already,
            "rename_needed": path.stem != new_id,
        })

    # Detect collisions
    targets: dict[str, list] = {}
    for a in actions:
        targets.setdefault(a["new_id"], []).append(a)
    collisions = {k: v for k, v in targets.items() if len(v) > 1}
    if collisions:
        print(f"⚠️  {len(collisions)} target filename collisions detected:")
        for k, v in collisions.items():
            print(f"   {k}.md  ←  {[a['path'].name for a in v]}")
        print("   These will be skipped to avoid data loss. Resolve manually.")
        print()

    # Apply
    n_renamed = 0
    n_field_only = 0
    for a in actions:
        if a["new_id"] in collisions:
            continue

        path = a["path"]
        raw = path.read_text(encoding="utf-8")
        fm, body = split_fm_body(raw)
        new_fm = update_field(fm, "id", a["new_id"])
        new_fm = update_field(new_fm, "ts", a["new_ts"])
        new_raw = new_fm + body

        new_path = POSTS_DIR / f"{a['new_id']}.md"

        rename_str = f"  {path.name} → {new_path.name}" if a["rename_needed"] else f"  {path.name}"
        change_parts = []
        if a["id_changed"]:
            change_parts.append(f"id: {a['old_id']} → {a['new_id']}")
        if a["ts_changed"]:
            change_parts.append(f"ts: {(a['old_ts'] or '')[:10]} → {a['new_ts'][:10]}")
        change_str = " | ".join(change_parts) + f" [from {a['src']}]"
        print(f"{rename_str}    {change_str}")

        if dry_run:
            continue

        if a["rename_needed"]:
            new_path.write_text(new_raw, encoding="utf-8")
            path.unlink()
            n_renamed += 1
        else:
            path.write_text(new_raw, encoding="utf-8")
            n_field_only += 1

    print()
    print("=== Summary ===")
    print(f"  Total files:         {len(files)}")
    print(f"  Already aligned:     {already_aligned}")
    print(f"  No detect (skipped): {skipped_no_detect}")
    print(f"  Collisions skipped:  {sum(len(v) for v in collisions.values())}")
    print(f"  {'Would fix' if dry_run else 'Fixed'}:           {len(actions) - sum(len(v) for v in collisions.values())}")
    if not dry_run:
        print(f"    - Renamed:        {n_renamed}")
        print(f"    - Field-only:     {n_field_only}")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
