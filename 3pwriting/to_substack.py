#!/usr/bin/env python3
"""Prepare a 3pwriting markdown post for paste into Substack's editor.

Substack auto-converts pasted markdown but breaks on:
- frontmatter YAML (renders as code)
- relative image paths (Substack can only fetch absolute URLs)
- <iframe> embeds (Substack ignores HTML iframes; bare YouTube URLs auto-embed)

This script normalizes those, copies the result to the clipboard, and prints
the title / subtitle / cover image URL pulled from frontmatter so you can
paste those into the Substack form fields without rummaging through the file.

Usage:
    python3 to_substack.py posts/2026-Q1-Review-Builder.en.md
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SITE_URL = "https://jasonjlai.net"


def parse_frontmatter(md_text):
    """Return (frontmatter_dict, body_without_frontmatter). Frontmatter is YAML-lite."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md_text, re.DOTALL)
    if not m:
        return {}, md_text
    fm_block, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_block.splitlines():
        kv = re.match(r"^([\w_-]+):\s*(.*)$", line)
        if kv and kv.group(2).strip():
            fm[kv.group(1)] = kv.group(2).strip().strip('"\'')
    return fm, body


def absolutize_images(body):
    """Convert ![alt](/relative.png) → ![alt](https://jasonjlai.net/relative.png).
    Skips already-absolute URLs."""
    def repl(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        if not src.startswith("/"):
            src = "/" + src
        return f"![{alt}]({SITE_URL}{src})"
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, body)


def iframe_to_youtube_url(body):
    """Replace <iframe ... youtube/embed/X ...></iframe> with bare https://youtu.be/X
    on its own line. Substack auto-embeds bare YouTube URLs."""
    def repl(m):
        block = m.group(0)
        src_m = re.search(r'src="([^"]+)"', block)
        if not src_m:
            return ""
        src = src_m.group(1)
        # /embed/{id} → /watch?v={id}; trim query/fragment
        id_m = re.search(r"/embed/([\w-]+)", src)
        if id_m:
            url = f"https://youtu.be/{id_m.group(1)}"
        else:
            url = re.sub(r"[?#].*$", "", src)
        return f"\n{url}\n"
    return re.sub(r"<iframe\b[^>]*>.*?</iframe>", repl, body, flags=re.DOTALL)


def to_substack(md_text):
    fm, body = parse_frontmatter(md_text)
    body = absolutize_images(body)
    body = iframe_to_youtube_url(body)
    return fm, body.strip() + "\n"


def copy_to_clipboard(text):
    # Inherit parent env, force UTF-8 locale so pbcopy preserves em-dashes /
    # CJK / smart quotes. (Bare env={LANG:..} discards PATH and breaks pbcopy.)
    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        env=env,
        check=True,
    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 to_substack.py <markdown-file>", file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"❌ File not found: {src}", file=sys.stderr)
        sys.exit(1)

    fm, body = to_substack(src.read_text(encoding="utf-8"))
    copy_to_clipboard(body)

    print(f"✅ Substack-ready markdown copied to clipboard ({len(body):,} chars).")
    print()
    print("Paste into Substack editor body. Then fill the form fields manually:")
    print()
    print(f"  Title    : {fm.get('title', '(missing in frontmatter)')}")
    print(f"  Subtitle : {fm.get('summary', '(missing in frontmatter)')}")
    cover = fm.get("image")
    if cover and not cover.startswith("http"):
        cover = SITE_URL + (cover if cover.startswith("/") else "/" + cover)
    print(f"  Cover    : {cover or '(none)'}")
    print()
    print("⚠️  Don't trust `pbpaste | head` for verification — it mangles UTF-8 from")
    print("   subprocess-set clipboards. Browsers (Substack) read via Cocoa APIs and")
    print("   handle UTF-8 correctly. Trust-the-paste, not the terminal preview.")


if __name__ == "__main__":
    main()
