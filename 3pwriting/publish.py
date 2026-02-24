#!/usr/bin/env python3
import os, re, yaml, markdown, datetime
from pathlib import Path
from xml.sax.saxutils import escape
import math

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"

# ✅ 3pwriting 這個資料夾本身就是輸出根目錄（會生成 ROOT/index.html、ROOT/feed.xml、ROOT/<tag>/...）
OUT_DIR = ROOT

SITE_URL = "https://jasonjlai.net"
POSTS_PER_PAGE = 30

HTML_TMPL = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.tailwindcss.com?plugins=typography"></script>
<script>
    tailwind.config = { darkMode: 'class' }
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
<html lang="zh-TW" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>3P Writing - Jason J. Lai</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: { extend: {
          fontFamily: {
            sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
          }
      } }
    }
  </script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .game-shadow { box-shadow: 4px 4px 0 0 rgba(15, 23, 42, 1); }
    .dark .game-shadow { box-shadow: 4px 4px 0 0 rgba(203, 213, 225, 1); }
    .game-shadow-hover:hover { box-shadow: 6px 6px 0 0 rgba(15, 23, 42, 1); transform: translateY(-2px); }
    .dark .game-shadow-hover:hover { box-shadow: 6px 6px 0 0 rgba(203, 213, 225, 1); }
    
    .tag-btn { border-width: 2px; border-style: solid; border-radius: 0.5rem; padding: 0.5rem 1rem; font-family: ui-monospace, monospace; font-size: 0.875rem; font-weight: 700; display: inline-flex; align-items: center; gap: 0.5rem; transition: all 150ms ease; cursor: pointer; user-select: none; text-decoration: none; }
    .tag-btn:not(.active) { background-color: rgb(226 232 240); color: rgb(71 85 105); border-color: rgb(203 213 225); }
    .dark .tag-btn:not(.active) { background-color: rgb(30 41 59); color: rgb(148 163 184); border-color: rgb(51 65 85); }
    .tag-btn:not(.active):hover { transform: translateY(-2px); box-shadow: 2px 2px 0 0 rgba(15, 23, 42, 0.5); }
    .dark .tag-btn:not(.active):hover { box-shadow: 2px 2px 0 0 rgba(203, 213, 225, 0.5); }
    .tag-btn.active { box-shadow: 4px 4px 0 0 rgba(15, 23, 42, 1); }
    .dark .tag-btn.active { box-shadow: 4px 4px 0 0 rgba(203, 213, 225, 1); }
    
    .tag-btn.active.tag-all { background-color: rgb(15 23 42); color: white; border-color: rgb(15 23 42); }
    .dark .tag-btn.active.tag-all { background-color: rgb(241 245 249); color: rgb(15 23 42); border-color: rgb(241 245 249); }
    .tag-btn.active.tag-playbooks { background-color: rgb(37 99 235); color: white; border-color: rgb(30 64 175); }
    .dark .tag-btn.active.tag-playbooks { border-color: rgb(96 165 250); }
    .tag-btn.active.tag-partnership { background-color: rgb(5 150 105); color: white; border-color: rgb(6 95 70); }
    .dark .tag-btn.active.tag-partnership { border-color: rgb(52 211 153); }
    .tag-btn.active.tag-playgrounds { background-color: rgb(217 119 6); color: white; border-color: rgb(146 64 14); }
    .dark .tag-btn.active.tag-playgrounds { border-color: rgb(251 191 36); }
    .tag-btn.active { background-color: rgb(124 58 237); color: white; border-color: rgb(91 33 182); }
    .dark .tag-btn.active { border-color: rgb(167 139 250); }
  </style>
</head>
<body class="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 transition-colors duration-300 selection:bg-indigo-200 dark:selection:bg-emerald-900">
  <nav class="sticky top-0 z-40 backdrop-blur-md bg-white/70 dark:bg-slate-900/70 border-b border-slate-200 dark:border-slate-800">
    <div class="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
      <div class="flex space-x-6 items-center">
        <a href="/" class="font-mono font-bold tracking-tight transition-colors text-slate-500 hover:text-indigo-600 dark:hover:text-emerald-400">
          <i data-lucide="arrow-left" class="w-5 h-5 inline-block mr-1 mb-1"></i>Main_Quest
        </a>
        <a href="/3pwriting/" class="font-mono font-bold tracking-tight transition-colors text-indigo-600 dark:text-emerald-400">
          <i data-lucide="book-open" class="w-5 h-5 inline-block mr-2 mb-1"></i>3P_Writing
        </a>
      </div>
      <div class="flex items-center space-x-4">
        <button onclick="toggleTheme()" class="p-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors" aria-label="Toggle dark mode">
          <i data-lucide="sun" id="icon-sun" class="w-5 h-5 text-amber-400 hidden"></i>
          <i data-lucide="moon" id="icon-moon" class="w-5 h-5 text-slate-600"></i>
        </button>
      </div>
    </div>
  </nav>

  <main class="max-w-3xl mx-auto px-6 py-12 animate-[fadeIn_0.5s_ease-out]">
    <div class="mb-10">
      <h1 class="text-4xl md:text-5xl font-bold font-mono tracking-tight mb-4 flex items-center gap-3">
        Writing on 3P
        <a href="/3pwriting/feed.xml" class="text-orange-500 hover:scale-110 transition-transform">
          <i data-lucide="rss" class="w-7 h-7"></i>
        </a>
      </h1>
      <p class="text-lg text-slate-600 dark:text-slate-400 font-mono">
        > <span class="text-emerald-500 font-bold">Partnership</span>.
        <span class="text-amber-500 font-bold">Playground</span>.
        <span class="text-blue-500 font-bold">Playbooks</span>.
      </p>
    </div>

    <div class="flex flex-wrap gap-3 mb-8">
      {tags_nav}
    </div>

    <hr class="border-2 border-slate-900 dark:border-slate-700 mb-8 rounded-full" />

    <div class="space-y-6">
      {items}
    </div>

    {pagination}
  </main>

  <footer class="border-t border-slate-200 dark:border-slate-800 py-12 mt-12">
    <div class="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center text-sm font-mono text-slate-500">
      <p>© <span id="current-year"></span> Jason J. Lai. Built with Python & Tailwind.</p>
    </div>
  </footer>

  <script>
    document.getElementById('current-year').textContent = new Date().getFullYear();
    lucide.createIcons();
    const htmlElement = document.documentElement;
    const iconSun = document.getElementById('icon-sun');
    const iconMoon = document.getElementById('icon-moon');
    function initTheme() {
      const savedTheme = localStorage.getItem('theme');
      if (savedTheme === 'light') {
        htmlElement.classList.remove('dark');
        iconSun.classList.add('hidden');
        iconMoon.classList.remove('hidden');
      } else {
        htmlElement.classList.add('dark');
        iconSun.classList.remove('hidden');
        iconMoon.classList.add('hidden');
      }
    }
    function toggleTheme() {
      if (htmlElement.classList.contains('dark')) {
        htmlElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
        iconSun.classList.add('hidden');
        iconMoon.classList.remove('hidden');
      } else {
        htmlElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
        iconSun.classList.remove('hidden');
        iconMoon.classList.add('hidden');
      }
    }
    initTheme();
    function navigateTo(path) { window.location.href = path; }
  </script>
</body>
</html>
"""

ARTICLE_CARD_TMPL = """
      <article class="p-6 rounded-2xl bg-white dark:bg-slate-800 border-2 border-slate-900 dark:border-slate-300 game-shadow game-shadow-hover transition-all cursor-pointer group"
               onclick="navigateTo('{link}')">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 mb-3">
          <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <span class="text-sm font-mono font-bold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded border border-slate-200 dark:border-slate-700">
              {date}
            </span>
            <div class="flex flex-wrap items-center">
              {tags_html}
            </div>
          </div>
          {pinned_badge}
        </div>
        <h2 class="text-2xl font-bold font-mono mb-3 group-hover:text-indigo-600 dark:group-hover:text-emerald-400 transition-colors">
          {title}
        </h2>
        <p class="text-slate-600 dark:text-slate-400 leading-relaxed">
          {summary}
        </p>
      </article>
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
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter invalid (must be mapping): {p.name}")
    body = m.group(2)
    return fm, body

def ensure_dir(d):
    d.mkdir(parents=True, exist_ok=True)

def normalize_date(value):
    # YAML 可能給 datetime.date / datetime.datetime
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    # 只保留 YYYY-MM-DD
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    raise ValueError(f"invalid date: {value!r} (use YYYY-MM-DD)")

def rfc2822(date_str):
    d = datetime.datetime.fromisoformat(date_str)
    return d.strftime("%a, %d %b %Y 00:00:00 +0000")

def get_color_for_tag(t):
    t_lower = str(t).lower()
    if 'playbook' in t_lower: return "bg-blue-500"
    if 'partnership' in t_lower: return "bg-emerald-500"
    if 'playground' in t_lower: return "bg-amber-500"
    return "bg-violet-500"

def build_tags_nav(active_tag, all_tags):
    core_tags = ['playbooks', 'partnership', 'playgrounds']
    display_tags = ['all'] + core_tags
    other_tags = sorted([t for t in all_tags if str(t).lower() not in core_tags and str(t).lower() != 'all'])
    display_tags.extend(other_tags)

    html_parts = []
    for t in display_tags:
        t_lower = str(t).lower()
        is_active = "active" if str(active_tag).lower() == t_lower else ""
        css_class = f"tag-{t_lower}"

        if t_lower == 'all':
            href = "/3pwriting/"
            icon = '<i data-lucide="layers" class="w-4 h-4"></i>'
            label = "All Logs"
        else:
            href = f"/3pwriting/{t_lower}/"
            icon = '<i data-lucide="tag" class="w-4 h-4"></i>'
            if 'playbook' in t_lower: icon = '<i data-lucide="book-open" class="w-4 h-4"></i>'
            if 'partnership' in t_lower: icon = '<i data-lucide="handshake" class="w-4 h-4"></i>'
            if 'playground' in t_lower: icon = '<i data-lucide="gamepad-2" class="w-4 h-4"></i>'
            label = str(t).capitalize() if not str(t).isdigit() else str(t)

        html_parts.append(f'<a href="{href}" class="tag-btn {is_active} {css_class}">{icon} {label}</a>')

    return "\n".join(html_parts)

def build_pagination_html(prev_url, next_url, current_page, total_pages):
    if total_pages <= 1:
        return ""

    html = '<div class="flex justify-center items-center space-x-4 mt-12 font-mono">'

    if prev_url:
        html += f'<a href="{prev_url}" class="px-4 py-2 border-2 border-slate-900 dark:border-slate-300 rounded-lg hover:bg-slate-900 hover:text-white dark:hover:bg-slate-200 dark:hover:text-slate-900 transition-colors">&larr; Prev</a>'
    else:
        html += f'<span class="px-4 py-2 border-2 border-slate-300 dark:border-slate-700 text-slate-400 rounded-lg cursor-not-allowed">&larr; Prev</span>'

    html += f'<span class="font-bold">Page {current_page} / {total_pages}</span>'

    if next_url:
        html += f'<a href="{next_url}" class="px-4 py-2 border-2 border-slate-900 dark:border-slate-300 rounded-lg hover:bg-slate-900 hover:text-white dark:hover:bg-slate-200 dark:hover:text-slate-900 transition-colors">Next &rarr;</a>'
    else:
        html += f'<span class="px-4 py-2 border-2 border-slate-300 dark:border-slate-700 text-slate-400 rounded-lg cursor-not-allowed">Next &rarr;</span>'

    html += '</div>'
    return html

def build_articles_html(post_chunk):
    if not post_chunk:
        return """<div class="text-center py-12 text-slate-500 font-mono border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl"><i data-lucide="ghost" class="w-12 h-12 mx-auto mb-3 opacity-50"></i><p>No logs found here.</p></div>"""

    items_html_list = []
    for p in post_chunk:
        tags_html_parts = []
        for t in p["tags"]:
            t_lower = str(t).lower()
            color_class = get_color_for_tag(t)
            tags_html_parts.append(
                f'<a href="/3pwriting/{t_lower}/" class="inline-flex items-center gap-1 text-xs font-mono uppercase text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-emerald-400 transition-colors"><span class="w-2 h-2 rounded-full {color_class}"></span>{escape(str(t))}</a>'
            )

        tags_html = ' <span class="mx-2 text-slate-300 dark:text-slate-700">|</span> '.join(tags_html_parts)
        pinned_badge = '<span class="inline-flex items-center gap-2 text-xs font-mono font-bold uppercase px-2 py-1 rounded border-2 border-slate-900 dark:border-slate-300 bg-white/80 dark:bg-slate-900/60"><i data-lucide="pin" class="w-4 h-4"></i> Pinned</span>' if p["pinned"] else ""

        card_html = (ARTICLE_CARD_TMPL
                     .replace("{link}", p["link"])
                     .replace("{date}", p["date"])
                     .replace("{tags_html}", tags_html)
                     .replace("{pinned_badge}", pinned_badge)
                     .replace("{title}", escape(p["title"]))
                     .replace("{summary}", escape(p["summary"])))
        items_html_list.append(card_html)

    return "\n".join(items_html_list)

def generate_paginated_list(posts_subset, out_base_dir, url_base, active_tag, all_tags):
    ensure_dir(out_base_dir)

    chunks = [posts_subset[i:i + POSTS_PER_PAGE] for i in range(0, len(posts_subset), POSTS_PER_PAGE)]
    if not chunks:
        chunks = [[]]

    total_pages = len(chunks)

    for i, chunk in enumerate(chunks):
        page_num = i + 1
        if page_num == 1:
            page_dir = out_base_dir
        else:
            page_dir = out_base_dir / f"page{page_num}"
            ensure_dir(page_dir)

        prev_url = ""
        next_url = ""
        if page_num > 1:
            prev_url = url_base if page_num == 2 else f"{url_base}page{page_num-1}/"
        if page_num < total_pages:
            next_url = f"{url_base}page{page_num+1}/"

        tags_nav_html = build_tags_nav(active_tag, all_tags)
        pagination_html = build_pagination_html(prev_url, next_url, page_num, total_pages)
        articles_html = build_articles_html(chunk)

        html = (INDEX_TMPL
                .replace("{tags_nav}", tags_nav_html)
                .replace("{items}", articles_html)
                .replace("{pagination}", pagination_html))
        (page_dir / "index.html").write_text(html, encoding="utf-8")

def main():
    posts = []
    all_tags_set = set()

    for md in POSTS_DIR.glob("*.md"):
        fm, body = parse_md(md)

        title = str(fm["title"]).strip()
        date = normalize_date(fm["date"])
        slug = str(fm.get("slug") or re.sub(r"[^a-z0-9\-]+", "-", title.lower()).strip("-")).lower()
        major = str(fm["major_tag"]).strip().lower()
        summary = str(fm.get("summary", "")).strip()

        raw_tags = fm.get("tags", [])
        tags_list = [t.strip() for t in raw_tags.split(',')] if isinstance(raw_tags, str) else [str(t).strip() for t in raw_tags]
        tags_list = [t for t in tags_list if t]

        for t in tags_list:
            all_tags_set.add(t)

        pinned = bool(fm.get("pinned", False))

        # ✅ 修正：不要再 OUT_DIR / "3pwriting" / ...
        out_dir = OUT_DIR / major / date.replace("-", "")
        ensure_dir(out_dir)

        html = (HTML_TMPL
                .replace("{title}", escape(title))
                .replace("{date}", escape(date))
                .replace("{major_tag}", escape(major))
                .replace("{content}", markdown.markdown(body, extensions=["fenced_code","tables"])))
        out_path = out_dir / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")

        posts.append({
            "title": title,
            "date": date,
            "major": major,
            "slug": slug,
            "link": f"/3pwriting/{major}/{date.replace('-','')}/{slug}.html",
            "full_link": f"{SITE_URL}/3pwriting/{major}/{date.replace('-','')}/{slug}.html",
            "summary": summary,
            "tags": tags_list,
            "pinned": pinned
        })

    posts.sort(key=lambda x: (x["pinned"], x["date"]), reverse=True)
    all_tags = list(all_tags_set)

    # ✅ 修正：主列表輸出到 OUT_DIR/index.html（也就是 /3pwriting/index.html）
    generate_paginated_list(posts, OUT_DIR, "/3pwriting/", "all", all_tags)

    # ✅ 修正：tag 頁輸出到 OUT_DIR/<tag>/index.html（也就是 /3pwriting/<tag>/index.html）
    for tag in all_tags:
        tag_lower = str(tag).lower()
        tag_posts = [p for p in posts if any(str(t).lower() == tag_lower for t in p["tags"])]

        tag_out_dir = OUT_DIR / tag_lower
        tag_url_base = f"/3pwriting/{tag_lower}/"
        generate_paginated_list(tag_posts, tag_out_dir, tag_url_base, tag, all_tags)

    feed_items = "\n".join([
        (ITEM_TMPL
         .replace("{title}", escape(p["title"]))
         .replace("{link}", escape(p["full_link"]))
         .replace("{pubdate}", rfc2822(p["date"]))
         .replace("{summary}", escape(p["summary"])))
        for p in posts[:20]
    ])

    # ✅ 修正：feed.xml 放在 OUT_DIR/feed.xml（也就是 /3pwriting/feed.xml）
    (OUT_DIR / "feed.xml").write_text(
        FEED_TMPL.replace("{site_url}", SITE_URL).replace("{items}", feed_items),
        encoding="utf-8"
    )

    print(f"✅ Built {len(posts)} posts. Tags: {sorted([str(t) for t in all_tags])}")

if __name__ == "__main__":
    main()
