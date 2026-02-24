#!/usr/bin/env python3
import os, re, yaml, markdown, datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"
SITE_DIR = ROOT
SITE_URL = "https://jasonjlai.net"

# 加入 Tailwind CSS 與 Typography 插件，讓產出的文章頁面直接變美！
HTML_TMPL = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.tailwindcss.com?plugins=typography"></script>
<script>
    tailwind.config = {{ darkMode: 'class' }}
</script>
</head>
<body class="bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 min-h-screen py-12 px-6 transition-colors duration-300">
<main class="max-w-3xl mx-auto">
    <a href="/3pwriting/" class="inline-flex items-center text-indigo-600 dark:text-emerald-400 font-mono font-bold mb-8 hover:underline">
        &larr; Back to 3P Writing
    </a>
    <article class="prose prose-slate dark:prose-invert max-w-none font-sans">
        <h1>{title}</h1>
        <p class="font-mono text-sm text-slate-500 not-prose mb-8">> {date} · [{major_tag}]</p>
        {content}
    </article>
</main>
</body>
</html>
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>3P Writing</title></head>
<body>
<main>
<h1>Writing on 3P</h1>
<ul>
{items}
</ul>
</main>
</body>
</html>
"""

FEED_TMPL = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>3P Writing</title>
<link>{site_url}/3pwriting/</link>
<description>Latest posts</description>
{items}
</channel>
</rss>
"""

ITEM_TMPL = """<item>
<title>{title}</title>
<link>{link}</link>
<guid>{link}</guid>
<pubDate>{pubdate}</pubDate>
<description>{summary}</description>
</item>
"""

def parse_md(p):
    txt = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", txt, re.S)
    if not m:
        raise ValueError(f"frontmatter missing: {p.name}")
    fm = yaml.safe_load(m.group(1))
    body = m.group(2)
    return fm, body

def ensure_dir(d):
    d.mkdir(parents=True, exist_ok=True)

def rfc2822(date_str):
    dt = datetime.datetime.fromisoformat(date_str)
    return dt.strftime("%a, %d %b %Y 00:00:00 +0000")

def main():
    posts = []
    for md in POSTS_DIR.glob("*.md"):
        fm, body = parse_md(md)
        title = fm["title"]
        # 💡 修正 1: 強制轉為字串，避免 yaml.safe_load 解析成 datetime.date 物件導致後續 replace 失敗
        date = str(fm["date"]) 
        slug = fm.get("slug") or re.sub(r"[^a-z0-9\-]+", "-", title.lower()).strip("-")
        major = fm["major_tag"]
        summary = fm.get("summary","")
        out_dir = SITE_DIR / "3pwriting" / major / date.replace("-", "")
        ensure_dir(out_dir)
        html = HTML_TMPL.format(
            title=title,
            date=date,
            major_tag=major,
            # 加入 fenced_code 和 tables 套件支援更多 MD 語法
            content=markdown.markdown(body, extensions=["fenced_code","tables"])
        )
        out_path = out_dir / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        posts.append({
            "title": title,
            "date": date,
            "major": major,
            "slug": slug,
            "link": f"{SITE_URL}/3pwriting/{major}/{date.replace('-','')}/{slug}.html",
            "summary": summary
        })

    posts.sort(key=lambda x: x["date"], reverse=True)

    items_html = "\n".join([
        f'<li><a href="{p["link"]}">{escape(p["title"])}</a> · {p["date"]} · {p["major"]}</li>'
        for p in posts
    ])
    (SITE_DIR / "3pwriting" / "index.html").write_text(
        INDEX_TMPL.format(items=items_html), encoding="utf-8"
    )

    feed_items = "\n".join([
        ITEM_TMPL.format(
            title=escape(p["title"]),
            link=p["link"],
            pubdate=rfc2822(p["date"]),
            summary=escape(p["summary"])
        )
        for p in posts[:20]
    ])
    (SITE_DIR / "3pwriting" / "feed.xml").write_text(
        FEED_TMPL.format(site_url=SITE_URL, items=feed_items), encoding="utf-8"
    )

    print(f"Built {len(posts)} posts.")

if __name__ == "__main__":
    main()
