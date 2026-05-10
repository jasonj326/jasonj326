#!/usr/bin/env python3
"""3pwriting publish.py — bilingual publish (EN + ZH) with /zh/ namespace.

Rebuilt 2026-05-10 for Phase 4a:
- URL pattern: /3pwriting/{major}/{slug}.html (EN) | /zh/3pwriting/{major}/{slug}.html (ZH)
- Family-stem sibling pairing (Foo.md ↔ Foo.en.md) drives hreflang + switcher
- Redirect stubs via frontmatter `redirect_from:` list (silent meta-refresh)
- 1 RSS feed, family_stem dedup, dc:language per item, feed_canonical override
- ZH index uses Chinese display labels (做人/處事/逍遙遊)
"""
import os, re, yaml, markdown, datetime, json
from pathlib import Path
from xml.sax.saxutils import escape
import math

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"
SITE_DIR = ROOT
REPO_ROOT = ROOT.parent
ZH_BASE = REPO_ROOT / "zh" / "3pwriting"  # ZH mirror root
SITE_URL = "https://jasonjlai.net"
POSTS_PER_PAGE = 30

# Language conventions
KNOWN_LANG_CODES = {'en', 'ja', 'zh', 'es', 'fr', 'de'}
LANG_NORMALIZE = {'zh': 'zh-Hant', 'zh-TW': 'zh-Hant'}
LANG_LABELS = {'en': 'English', 'zh-Hant': '中文', 'zh': '中文', 'zh-TW': '中文', 'ja': '日本語'}
LANG_DISPLAY_ORDER = ['zh-Hant', 'en', 'ja']

# Feed canonical priority — when frontmatter `feed_canonical: true` not set,
# pick by this language priority. Reflects Jason's ZH-first writing convention.
FEED_LANG_PRIORITY = ['zh-Hant', 'en', 'ja']

SITE_AUTHOR_DESC = "New York-qualified attorney and legal engineer designing and shipping AI and blockchain regulatory architecture across the US and APAC. Focused on governance design, compliance by design, and cross-border digital asset strategy."

# Sitemap: static landing pages with priority + changefreq.
# ZH paths added incrementally as Phases 1/2/3/5 ship.
SITEMAP_STATIC_PAGES = [
    ("/",                                  "1.0", "weekly"),
    ("/zh/",                               "1.0", "weekly"),  # ZH home (Phase 2 first cut)
    ("/about/",                            "0.8", "monthly"),  # Phase 1
    ("/zh/about/",                         "0.8", "monthly"),  # Phase 1
    ("/now/",                              "0.9", "weekly"),
    ("/3pwriting/",                        "0.9", "weekly"),
    ("/zh/3pwriting/",                     "0.9", "weekly"),  # Phase 4a
    ("/PIF12/",                            "0.9", "weekly"),
    ("/PIF12/zh/",                         "0.9", "weekly"),  # legacy until Phase 3
    ("/long-game/",                        "0.7", "monthly"),
    ("/communication/",                    "0.6", "monthly"),
    ("/communication-zh/",                 "0.6", "monthly"),  # legacy until Phase 3
    ("/japanese/",                         "0.6", "monthly"),
    ("/qualia/",                           "0.5", "monthly"),
    ("/seeds/",                            "0.8", "weekly"),
    ("/privacy/",                          "0.3", "monthly"),
    ("/contribute/",                       "0.4", "monthly"),
]

# UI labels per language (drives index / tag pages)
UI_LABELS = {
    "en": {
        "html_lang": "en",
        "page_title": "3P Writing - Jason J. Lai",
        "h1": "Writing on 3P",
        "intro_html": '> <span class="text-emerald-500 font-bold">Partnership</span>. <span class="text-blue-500 font-bold">Playbooks</span>. <span class="text-amber-500 font-bold">Playground</span>.',
        "all_logs": "All Logs",
        "tag_labels": {
            "partnership": "Partnership",
            "playbooks": "Playbooks",
            "playgrounds": "Playgrounds",
            "skill-tree": "Skill Tree",
            "quarterly-review": "Quarterly Review",
            "translated": "Translated",
        },
        "no_logs": "No logs found here.",
        "prev_word": "← Prev",
        "next_word": "Next →",
        "random_word": "Random",
        "page_label": "Page",
        "site_root_3pwriting": "/3pwriting/",
    },
    "zh-Hant": {
        "html_lang": "zh-Hant",
        "page_title": "3P 寫作 - Jason J. Lai",
        "h1": "3P 寫作",
        "intro_html": '> <span class="text-emerald-500 font-bold">做人 (Partnership)</span>・<span class="text-blue-500 font-bold">做事 (Playbooks)</span>・<span class="text-amber-500 font-bold">逍遙遊 (Playground)</span>。',
        "all_logs": "全部",
        "tag_labels": {
            "partnership": "做人",
            "playbooks": "做事",
            "playgrounds": "逍遙遊",
            "skill-tree": "技能樹",
            "quarterly-review": "季報",
            "translated": "翻譯",
        },
        "no_logs": "這裡還沒有文章。",
        "prev_word": "← 上一頁",
        "next_word": "下一頁 →",
        "random_word": "隨機",
        "page_label": "頁",
        "site_root_3pwriting": "/zh/3pwriting/",
    }
}

# Nav i18n — used in both article pages and index pages.
# ZH labels are provisional; Phase 2 will reconcile site-wide.
NAV_LABELS = {
    "en": {
        "jason_full": "Jason_Lai", "jason_mobile": "Jason",
        "long_full": "Long Game",  "long_mobile": "Game",
        "p3_full":   "Writing on 3P", "p3_mobile": "3P",
        "qualia_full": "Qualia",   "qualia_mobile": "AI",
        "seeds_full":  "Seeds",    "seeds_mobile":  "Seeds",
    },
    "zh-Hant": {
        "jason_full": "Jason_Lai", "jason_mobile": "Jason",
        "long_full": "長期遊戲",   "long_mobile": "遊戲",
        "p3_full":   "3P 寫作",     "p3_mobile":   "3P",
        "qualia_full": "Qualia",   "qualia_mobile": "Lia",
        "seeds_full":  "種子",     "seeds_mobile":  "種子",
    }
}

# --- Helpers ---

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
    dt = datetime.datetime.fromisoformat(str(date_str))
    return dt.strftime("%a, %d %b %Y 00:00:00 +0000")

def detect_language(text):
    """Auto-detect zh-TW / ja / en from body text."""
    clean_text = re.sub(r'\s+', '', text)
    if not clean_text:
        return "en"
    kana_chars = re.findall(r'[぀-ヿ]', clean_text)
    if len(kana_chars) / len(clean_text) > 0.01:
        return "ja"
    cjk_chars = re.findall(r'[一-鿿]', clean_text)
    if len(cjk_chars) / len(clean_text) > 0.05:
        return "zh-TW"
    return "en"

def add_target_blank_to_external(html):
    """Auto-add target='_blank' rel='noopener noreferrer' to external links."""
    def repl(m):
        attrs = m.group(1)
        if 'target=' in attrs:
            return m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', attrs)
        if not href_m:
            return m.group(0)
        href = href_m.group(1)
        if href.startswith(('/', '#', 'mailto:', 'tel:')):
            return m.group(0)
        if 'jasonjlai.net' in href:
            return m.group(0)
        if not href.startswith(('http://', 'https://')):
            return m.group(0)
        return f'<a {attrs} target="_blank" rel="noopener noreferrer">'
    return re.sub(r'<a ([^>]+)>', repl, html)

def post_paths(major, slug, final_lang):
    """Compute (out_dir, relative_link, full_link) per language."""
    if final_lang.startswith("zh"):
        out_dir = ZH_BASE / major
        rel = f"/zh/3pwriting/{major}/{slug}.html"
    else:
        out_dir = SITE_DIR / major
        rel = f"/3pwriting/{major}/{slug}.html"
    return out_dir, rel, SITE_URL + rel

def is_zh(lang):
    return lang.startswith("zh")

def get_color_for_tag(t):
    t_lower = t.lower()
    if 'playbook' in t_lower: return "bg-blue-500"
    if 'partnership' in t_lower: return "bg-emerald-500"
    if 'playground' in t_lower: return "bg-amber-500"
    return "bg-violet-500"

# --- Templates ---

# Shared nav block (used by both HTML_TMPL & INDEX_TMPL).
# ui_lang: "en" | "zh-Hant"; active: "long" | "p3" | "qualia" | "seeds" | None
# lang_switch_url: target URL for opposite-language version (None hides the switch icon)
def build_nav(ui_lang, active=None, lang_switch_url=None):
    L = NAV_LABELS[ui_lang]
    is_zh_ui = ui_lang.startswith("zh")
    home_href = "/zh/" if is_zh_ui else "/"
    long_href = "/zh/long-game/" if is_zh_ui else "/long-game/"
    p3_href = "/zh/3pwriting/" if is_zh_ui else "/3pwriting/"
    qualia_href = "/zh/qualia/" if is_zh_ui else "/qualia/"
    seeds_href = "/zh/seeds/" if is_zh_ui else "/seeds/"

    def link(href, lucide, full, mobile, key):
        active_cls = ("text-indigo-600 dark:text-emerald-400"
                      if active == key
                      else "text-slate-500 hover:text-indigo-600 dark:hover:text-emerald-400")
        return (
            f'<a href="{href}" class="flex items-center gap-1.5 font-mono font-bold tracking-tight transition-colors {active_cls}">'
            f'<i data-lucide="{lucide}" class="w-4 h-4 sm:w-5 sm:h-5"></i>'
            f'<span class="hidden sm:inline">{full}</span>'
            f'<span class="sm:hidden text-sm">{mobile}</span>'
            f'</a>'
        )

    # Language-switch icon (placed before GitHub icon). ZH page → "EN" link, EN page → "中" link.
    if lang_switch_url:
        target_label = "EN" if is_zh_ui else "中"
        target_full = "English" if is_zh_ui else "中文"
        lang_switch_html = (
            f'<a href="{lang_switch_url}" class="text-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors flex items-center gap-1" '
            f'aria-label="Switch to {target_full}" title="{target_full}">'
            f'<i data-lucide="languages" class="w-4 h-4 sm:w-5 sm:h-5"></i>'
            f'<span class="text-xs sm:text-sm font-mono font-bold">{target_label}</span>'
            f'</a>'
        )
    else:
        lang_switch_html = ""

    return f"""
  <nav class="sticky top-0 z-40 backdrop-blur-md bg-white/70 dark:bg-slate-900/70 border-b border-slate-200 dark:border-slate-800 transition-colors duration-500">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 min-h-[4rem] py-2 flex flex-wrap items-center justify-between gap-y-2 gap-x-4">
          <div class="flex flex-wrap items-center gap-3 sm:gap-5">
              {link(home_href, 'terminal', L['jason_full'], L['jason_mobile'], 'home')}
              {link(long_href, 'target', L['long_full'], L['long_mobile'], 'long')}
              {link(p3_href, 'book-open', L['p3_full'], L['p3_mobile'], 'p3')}
              {link(qualia_href, 'cpu', L['qualia_full'], L['qualia_mobile'], 'qualia')}
              {link(seeds_href, 'sprout', L['seeds_full'], L['seeds_mobile'], 'seeds')}
          </div>
          <div class="flex items-center gap-3 sm:gap-4 ml-auto">
              <div class="flex items-center gap-3 sm:gap-4">
                  {lang_switch_html}
                  <a href="https://github.com/jasonj326" target="_blank" rel="noopener noreferrer" class="text-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors" aria-label="GitHub Profile">
                      <svg class="w-4 h-4 sm:w-5 sm:h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.24c3-.34 6-1.53 6-6.76a5.5 5.5 0 0 0-1.5-3.8 5.4 5.4 0 0 0-.15-3.8s-1.2-.38-3.9 1.5a13.38 13.38 0 0 0-7 0C6.2 1.62 5 2 5 2a5.4 5.4 0 0 0-.15 3.8A5.5 5.5 0 0 0 3 9.5c0 5.23 3 6.42 6 6.76a4.8 4.8 0 0 0-1 3.24v4"></path>
                      </svg>
                  </a>
                  <a href="https://linkedin.com/in/psjasonlai" target="_blank" rel="noopener noreferrer" class="text-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors" aria-label="LinkedIn Profile">
                      <svg class="w-4 h-4 sm:w-5 sm:h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path>
                          <rect x="2" y="9" width="4" height="12"></rect>
                          <circle cx="4" cy="4" r="2"></circle>
                      </svg>
                  </a>
                  <a href="mailto:hello@jasonjlai.net" class="text-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors" aria-label="Email Contact">
                      <svg class="w-4 h-4 sm:w-5 sm:h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <rect width="20" height="16" x="2" y="4" rx="2"></rect>
                          <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
                      </svg>
                  </a>
              </div>
              <div class="hidden sm:block w-px h-5 bg-slate-300 dark:bg-slate-700"></div>
              <button onclick="toggleTheme()" class="p-2 -mr-2 sm:mr-0 rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors" aria-label="Toggle dark mode">
                  <i data-lucide="sun" id="icon-sun" class="w-4 h-4 sm:w-5 sm:h-5 text-amber-400 hidden"></i>
                  <i data-lucide="moon" id="icon-moon" class="w-4 h-4 sm:w-5 sm:h-5 text-slate-600"></i>
              </button>
          </div>
      </div>
  </nav>
"""

# Article HTML template (single post). {nav_html} injected from build_nav.
HTML_TMPL = """<!DOCTYPE html>
<html lang="{lang}" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title} - Jason J. Lai</title>
<meta name="description" content="{summary}">
<meta name="author" content="Jason J. Lai">
<meta property="og:title" content="{title} - Jason J. Lai">
<meta property="og:description" content="{summary}">
<meta property="og:image" content="{og_image}">
<meta property="og:url" content="{full_link}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}",
  "image": "{og_image}",
  "datePublished": "{date}",
  "author": {
    "@type": "Person",
    "name": "Jason J. Lai",
    "url": "https://jasonjlai.net",
    "jobTitle": "Attorney & Legal Engineer",
    "description": "{site_author_desc}"
  },
  "description": "{summary}"
}
</script>
<link rel="icon" type="image/png" href="/favicon.png" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
{hreflang_tags}
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.tailwindcss.com?plugins=typography"></script>
<script>
    tailwind.config = { darkMode: 'class' }
</script>
<script src="https://unpkg.com/lucide@latest"></script>
<style>
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    [x-cloak] { display: none !important; }
    .footnote-ref { text-decoration: none !important; color: rgb(79 70 229) !important; }
    .dark .footnote-ref { color: rgb(52 211 153) !important; }
    .footnote-backref { text-decoration: none !important; font-family: sans-serif; }
    .footnote { padding-top: 4rem; margin-top: -4rem; }
</style>
              <link rel="stylesheet" href="/assets/fab-subscribe.css">
</head>
<body class="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 transition-colors duration-300">
{nav_html}
  <main class="max-w-3xl mx-auto px-6 py-12 animate-[fadeIn_0.5s_ease-out]">
    <article class="prose prose-slate dark:prose-invert prose-indigo dark:prose-emerald max-w-none font-sans">
        <header>
          <h1 class="mb-6 tracking-tight">{title}</h1>
          <div class="flex flex-wrap items-center gap-3 font-mono text-sm text-slate-500 dark:text-slate-400 not-prose mb-10 pb-8 border-b border-slate-200 dark:border-slate-800">
            <time datetime="{date}" class="font-bold bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded border border-slate-200 dark:border-slate-700">{date}</time>
            <span class="text-slate-300 dark:text-slate-700">|</span>
            <div class="flex flex-wrap items-center">
               {tags_html}
            </div>
          </div>
          {lang_switcher}
        </header>

        {content}

        <div class="not-prose mt-16 mb-8 pt-8 border-t border-slate-200 dark:border-slate-800">
            <div class="flex flex-col sm:flex-row justify-between items-center gap-6 font-mono text-sm">
                <div class="w-full sm:w-2/5 flex justify-start">
                    {prev_button}
                </div>
                <div class="w-full sm:w-1/5 flex justify-center shrink-0">
                    <button onclick="goToRandomPost()" class="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-indigo-100 hover:text-indigo-600 dark:hover:bg-emerald-900/30 dark:hover:text-emerald-400 rounded-lg transition-colors border border-slate-200 dark:border-slate-700 font-bold" aria-label="Random Post">
                        <i data-lucide="shuffle" class="w-4 h-4"></i> {random_word}
                    </button>
                </div>
                <div class="w-full sm:w-2/5 flex justify-end text-right">
                    {next_button}
                </div>
            </div>
        </div>

        <div class="not-prose mt-12 p-6 rounded-xl bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-sm text-slate-500 dark:text-slate-400 leading-relaxed font-sans shadow-sm">
          <strong class="font-bold text-slate-700 dark:text-slate-300 mr-1">{disclaimer_label}</strong>
          {disclaimer_body}
        </div>
    </article>
  </main>

  <footer class="border-t border-slate-200 dark:border-slate-800 py-12 mt-12">
    <div class="max-w-4xl mx-auto px-6 flex flex-col justify-center items-center gap-3 text-sm font-mono text-slate-500">
        <p class="text-center"><a href="/privacy/" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">Privacy</a> · <a href="/contribute/" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">Contribute</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">CC BY 4.0</a> © <span id="current-year"></span> Jason J. Lai</p>
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

    const allPosts = {all_links_array};
    function goToRandomPost() {
        const currentPath = window.location.pathname;
        const otherPosts = allPosts.filter(p => p !== currentPath);
        if (otherPosts.length > 0) {
            window.location.href = otherPosts[Math.floor(Math.random() * otherPosts.length)];
        }
    }
  </script>
    <script src="/assets/fab-subscribe.js" defer></script>
</body>
</html>
"""

# Index/tag page template. {nav_html}, {ui_*}, {tags_nav}, {items}, {pagination} injected.
INDEX_TMPL = """<!DOCTYPE html>
<html lang="{ui_html_lang}" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{ui_page_title}</title>
  <meta name="description" content="{site_description}">
  <meta property="og:title" content="{ui_page_title}">
  <meta property="og:description" content="{site_description}">
  <meta property="og:image" content="https://jasonjlai.net/og-cover.jpeg">
  <meta property="og:url" content="https://jasonjlai.net{ui_site_root}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "{ui_page_title}",
    "url": "https://jasonjlai.net{ui_site_root}",
    "description": "{site_description}",
    "author": {
      "@type": "Person",
      "name": "Jason J. Lai",
      "jobTitle": "Attorney & Legal Engineer",
      "description": "{site_description}"
    }
  }
  </script>
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
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
              <link rel="stylesheet" href="/assets/fab-subscribe.css">
</head>
<body class="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 transition-colors duration-300 selection:bg-indigo-200 dark:selection:bg-emerald-900">
{nav_html}
  <main class="max-w-3xl mx-auto px-6 py-12 animate-[fadeIn_0.5s_ease-out]">
    <div class="mb-10">
      <h1 class="text-4xl md:text-5xl font-bold font-mono tracking-tight mb-4 flex items-center gap-3">
        {ui_h1}
        <a href="/3pwriting/feed.xml" class="text-orange-500 hover:scale-110 transition-transform">
          <i data-lucide="rss" class="w-7 h-7"></i>
        </a>
      </h1>
      <p class="text-lg text-slate-600 dark:text-slate-400 font-mono">
        {ui_intro_html}
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
    <div class="max-w-4xl mx-auto px-6 flex flex-col justify-center items-center gap-3 text-sm font-mono text-slate-500">
        <p class="text-center"><a href="/privacy/" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">Privacy</a> · <a href="/contribute/" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">Contribute</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener" class="underline decoration-slate-400 hover:text-indigo-600 dark:hover:text-emerald-400">CC BY 4.0</a> © <span id="current-year"></span> Jason J. Lai</p>
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
    <script src="/assets/fab-subscribe.js" defer></script>
</body>
</html>
"""

ARTICLE_CARD_TMPL = """
      <article class="p-6 rounded-2xl bg-white dark:bg-slate-800 border-2 border-slate-900 dark:border-slate-300 game-shadow game-shadow-hover transition-all cursor-pointer group"
               onclick="navigateTo('{link}')">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 mb-3">
          <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <span class="text-sm font-mono font-bold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded border border-slate-200 dark:border-slate-700 whitespace-nowrap shrink-0">
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

# RSS feed template — adds dc namespace for per-item language tag.
FEED_TMPL = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>3P Writing</title>
<link>{site_url}/3pwriting/</link>
<description>Latest posts</description>
<language>zh-Hant</language>
{items}
</channel>
</rss>
"""

ITEM_TMPL = """<item>
<title>{title}</title>
<link>{link}</link>
<guid>{guid}</guid>
<pubDate>{pubdate}</pubDate>
<dc:language>{lang}</dc:language>
<description>{summary}</description>
</item>
"""

# Redirect stub — silent meta refresh + JS fallback. Used for old URLs.
REDIRECT_STUB_TMPL = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={new_url}">
<link rel="canonical" href="{new_url}">
<meta name="robots" content="noindex">
<title>Redirecting…</title>
</head>
<body>
<p>Redirecting to <a href="{new_url}">{new_url}</a>…</p>
<script>location.replace('{new_url}');</script>
</body>
</html>
"""

# --- Builders ---

def build_tags_nav(active_tag, all_tags, ui_lang):
    """All Logs + tag chip buttons. Display labels come from UI_LABELS[ui_lang]."""
    L = UI_LABELS[ui_lang]
    site_root = L["site_root_3pwriting"]
    tag_labels = L["tag_labels"]

    core_tags = ['playbooks', 'partnership', 'playgrounds']
    display_tags = ['all'] + core_tags
    other_tags = sorted([t for t in all_tags if t.lower() not in core_tags and t.lower() != 'all'])
    display_tags.extend(other_tags)

    html_parts = []
    for t in display_tags:
        t_lower = t.lower()
        is_active = "active" if active_tag.lower() == t_lower else ""
        css_class = f"tag-{t_lower}"
        if t_lower == 'all':
            href = site_root
            icon = '<i data-lucide="layers" class="w-4 h-4"></i>'
            label = L["all_logs"]
        else:
            href = f"{site_root}{t_lower}/"
            icon = '<i data-lucide="tag" class="w-4 h-4"></i>'
            if 'playbook' in t_lower: icon = '<i data-lucide="book-open" class="w-4 h-4"></i>'
            if 'partnership' in t_lower: icon = '<i data-lucide="handshake" class="w-4 h-4"></i>'
            if 'playground' in t_lower: icon = '<i data-lucide="gamepad-2" class="w-4 h-4"></i>'
            label = tag_labels.get(t_lower, t.capitalize() if not t.isdigit() else t)
        html_parts.append(f'<a href="{href}" class="tag-btn {is_active} {css_class}">{icon} {label}</a>')
    return "\n".join(html_parts)

def build_pagination_html(prev_url, next_url, current_page, total_pages, ui_lang):
    if total_pages <= 1: return ""
    L = UI_LABELS[ui_lang]
    html = '<div class="flex justify-center items-center space-x-4 mt-12 font-mono">'
    if prev_url:
        html += f'<a href="{prev_url}" class="px-4 py-2 border-2 border-slate-900 dark:border-slate-300 rounded-lg hover:bg-slate-900 hover:text-white dark:hover:bg-slate-200 dark:hover:text-slate-900 transition-colors">{L["prev_word"]}</a>'
    else:
        html += f'<span class="px-4 py-2 border-2 border-slate-300 dark:border-slate-700 text-slate-400 rounded-lg cursor-not-allowed">{L["prev_word"]}</span>'
    html += f'<span class="font-bold">{L["page_label"]} {current_page} / {total_pages}</span>'
    if next_url:
        html += f'<a href="{next_url}" class="px-4 py-2 border-2 border-slate-900 dark:border-slate-300 rounded-lg hover:bg-slate-900 hover:text-white dark:hover:bg-slate-200 dark:hover:text-slate-900 transition-colors">{L["next_word"]}</a>'
    else:
        html += f'<span class="px-4 py-2 border-2 border-slate-300 dark:border-slate-700 text-slate-400 rounded-lg cursor-not-allowed">{L["next_word"]}</span>'
    html += '</div>'
    return html

def build_articles_html(post_chunk, ui_lang):
    L = UI_LABELS[ui_lang]
    if not post_chunk:
        return f"""<div class="text-center py-12 text-slate-500 font-mono border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl"><i data-lucide="ghost" class="w-12 h-12 mx-auto mb-3 opacity-50"></i><p>{L["no_logs"]}</p></div>"""
    items_html_list = []
    for p in post_chunk:
        tags_html_parts = []
        for t in p["tags"]:
            color_class = get_color_for_tag(t)
            tags_html_parts.append(f'<a href="{L["site_root_3pwriting"]}{t.lower()}/" class="inline-flex items-center gap-1 text-xs font-mono uppercase text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-emerald-400 transition-colors"><span class="w-2 h-2 rounded-full {color_class}"></span>{t}</a>')
        tags_html = ' <span class="mx-2 text-slate-300 dark:text-slate-700">|</span> '.join(tags_html_parts)
        pinned_badge = '<span class="inline-flex items-center gap-2 text-xs font-mono font-bold uppercase px-2 py-1 rounded border-2 border-slate-900 dark:border-slate-300 bg-white/80 dark:bg-slate-900/60"><i data-lucide="pin" class="w-4 h-4"></i> Pinned</span>' if p["pinned"] else ""
        card_html = ARTICLE_CARD_TMPL.replace("{link}", p["link"]).replace("{date}", p["date"]).replace("{tags_html}", tags_html).replace("{pinned_badge}", pinned_badge).replace("{title}", escape(p["title"])).replace("{summary}", escape(p["summary"]))
        items_html_list.append(card_html)
    return "\n".join(items_html_list)

def generate_paginated_list(posts_subset, out_base_dir, url_base, active_tag, all_tags, ui_lang):
    """Render paginated index/tag pages. ui_lang controls UI text + nav language."""
    ensure_dir(out_base_dir)
    L = UI_LABELS[ui_lang]
    chunks = [posts_subset[i:i + POSTS_PER_PAGE] for i in range(0, max(1, len(posts_subset)), POSTS_PER_PAGE)] or [[]]
    total_pages = len(chunks)
    # Lang-switch URL for index/tag pages: swap /zh/ prefix
    if ui_lang == "en":
        lang_switch_url = "/zh" + url_base
    else:
        lang_switch_url = url_base.replace("/zh/", "/", 1)
    nav_html = build_nav(ui_lang, active="p3", lang_switch_url=lang_switch_url)
    for i, chunk in enumerate(chunks):
        page_num = i + 1
        page_dir = out_base_dir if page_num == 1 else out_base_dir / f"page{page_num}"
        ensure_dir(page_dir)
        prev_url = ""
        next_url = ""
        if page_num > 1: prev_url = url_base if page_num == 2 else f"{url_base}page{page_num-1}/"
        if page_num < total_pages: next_url = f"{url_base}page{page_num+1}/"

        tags_nav_html = build_tags_nav(active_tag, all_tags, ui_lang)
        pagination_html = build_pagination_html(prev_url, next_url, page_num, total_pages, ui_lang)
        articles_html = build_articles_html(chunk, ui_lang)

        html = (INDEX_TMPL
                .replace("{tags_nav}", tags_nav_html)
                .replace("{items}", articles_html)
                .replace("{pagination}", pagination_html)
                .replace("{site_description}", escape(SITE_AUTHOR_DESC))
                .replace("{ui_html_lang}", L["html_lang"])
                .replace("{ui_page_title}", L["page_title"])
                .replace("{ui_h1}", L["h1"])
                .replace("{ui_intro_html}", L["intro_html"])
                .replace("{ui_site_root}", L["site_root_3pwriting"])
                .replace("{nav_html}", nav_html))
        (page_dir / "index.html").write_text(html, encoding="utf-8")

def generate_redirect_stubs(posts):
    """For each post with frontmatter `redirect_from:` list, write meta-refresh stub HTML
    at each old path. Old paths are absolute URLs (e.g. `/3pwriting/partnership/20260501/foo.html`)."""
    stub_count = 0
    for p in posts:
        old_paths = p.get("redirect_from") or []
        if isinstance(old_paths, str):
            old_paths = [old_paths]
        new_url = p["full_link"]
        for old_path in old_paths:
            if not old_path.startswith("/"):
                print(f"⚠️  redirect_from must be absolute path starting with /: {old_path}")
                continue
            stub_path = REPO_ROOT / old_path.lstrip("/")
            ensure_dir(stub_path.parent)
            stub_html = (REDIRECT_STUB_TMPL
                         .replace("{lang}", p["final_lang"])
                         .replace("{new_url}", new_url))
            stub_path.write_text(stub_html, encoding="utf-8")
            stub_count += 1
    return stub_count

def generate_sitemap(posts, all_tags):
    """sitemap.xml at repo root: static pages + 3pwriting articles + tag listings (EN+ZH)."""
    today = datetime.date.today().isoformat()
    entries = []
    for path, priority, freq in SITEMAP_STATIC_PAGES:
        entries.append((SITE_URL + path, today, freq, priority))
    # Tag listings — both EN and ZH
    for tag in sorted(all_tags):
        entries.append((f"{SITE_URL}/3pwriting/{tag.lower()}/", today, "weekly", "0.5"))
        entries.append((f"{SITE_URL}/zh/3pwriting/{tag.lower()}/", today, "weekly", "0.5"))
    # Articles — full_link already routes to /zh/ for ZH posts
    for p in posts:
        if "readme" in p["slug"].lower():
            continue
        entries.append((p["full_link"], p["date"], "monthly", "0.7"))
    body = "\n".join(
        f'  <url>\n    <loc>{escape(loc)}</loc>\n    <lastmod>{lastmod}</lastmod>\n    <changefreq>{freq}</changefreq>\n    <priority>{priority}</priority>\n  </url>'
        for loc, lastmod, freq, priority in entries
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'
    (REPO_ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    return len(entries)

def pick_feed_canonical(family):
    """Within a family_stem (lang -> post dict), pick which version goes into RSS.
    Priority: explicit `feed_canonical: true` → FEED_LANG_PRIORITY → first available."""
    explicit = [p for p in family.values() if p.get("feed_canonical")]
    if explicit:
        return explicit[0]
    for lang in FEED_LANG_PRIORITY:
        if lang in family:
            return family[lang]
    return next(iter(family.values()))

def generate_feed(raw_posts, lang_families):
    """1 RSS feed at /3pwriting/feed.xml. family_stem dedup, dc:language per item.
    pubDate: max(canonical.date, sibling.date) — sibling publish acts as update."""
    canonicals = []
    for stem, family in lang_families.items():
        canonical = pick_feed_canonical(family)
        if "readme" in canonical["slug"].lower():
            continue
        # pubDate: pick latest among family (treat sibling publish as update)
        latest_date = max((p.get("updated") or p["date"]) for p in family.values())
        canonicals.append({
            "title": canonical["title"],
            "link": canonical["full_link"],
            "guid": f"{SITE_URL}/3pwriting/guid/{canonical['slug']}",  # slug-stable across language switches
            "pubdate": rfc2822(latest_date),
            "lang": canonical["final_lang"],
            "summary": canonical["summary"],
            "_sort_key": latest_date,
        })
    canonicals.sort(key=lambda x: x["_sort_key"], reverse=True)
    feed_items = "\n".join([
        ITEM_TMPL.replace("{title}", escape(c["title"]))
                 .replace("{link}", c["link"])
                 .replace("{guid}", c["guid"])
                 .replace("{pubdate}", c["pubdate"])
                 .replace("{lang}", c["lang"])
                 .replace("{summary}", escape(c["summary"]))
        for c in canonicals[:20]
    ])
    feed_xml = FEED_TMPL.replace("{site_url}", SITE_URL).replace("{items}", feed_items)
    (SITE_DIR / "feed.xml").write_text(feed_xml, encoding="utf-8")
    return len(canonicals)

def main():
    posts = []
    all_tags_set = set()
    ensure_dir(POSTS_DIR)

    raw_posts = []
    link_dict = {}

    for md in POSTS_DIR.glob("*.md"):
        try:
            fm, body = parse_md(md)
            title = fm["title"]
            date = str(fm["date"])
            slug = fm.get("slug") or re.sub(r"[^a-z0-9\-]+", "-", title.lower()).strip("-")
            major = fm["major_tag"]
            summary = (fm.get("summary") or "").strip() or SITE_AUTHOR_DESC

            raw_tags = fm.get("tags", [])
            tags_list = [t.strip() for t in raw_tags.split(',')] if isinstance(raw_tags, str) else raw_tags
            for t in tags_list: all_tags_set.add(t)
            pinned = bool(fm.get("pinned", False))

            article_image = fm.get("image")
            if article_image:
                if article_image.startswith("/"):
                    og_image_url = f"{SITE_URL}{article_image}"
                elif article_image.startswith("http"):
                    og_image_url = article_image
                else:
                    og_image_url = f"{SITE_URL}/{article_image}"
            else:
                og_image_url = f"{SITE_URL}/og-cover.jpeg"

            # Detect language: prefer frontmatter `lang:`, fallback to filename suffix, fallback to body detect.
            stem_parts = md.stem.rsplit('.', 1)
            if len(stem_parts) == 2 and stem_parts[1].lower() in KNOWN_LANG_CODES:
                family_stem = stem_parts[0]
                lang_explicit = stem_parts[1].lower()
            else:
                family_stem = md.stem
                lang_explicit = None
            fm_lang = (fm.get("lang") or "").strip()
            detected_lang = detect_language(body)
            chosen = fm_lang or lang_explicit or detected_lang
            final_lang = LANG_NORMALIZE.get(chosen, chosen)

            # URL pattern: /3pwriting/{major}/{slug}.html or /zh/3pwriting/{major}/{slug}.html
            _, relative_link, full_link = post_paths(major, slug, final_lang)

            # frontmatter `url:` sanity check (kept for back-compat with downstream readers).
            fm_url = fm.get("url", "").strip() if isinstance(fm.get("url"), str) else ""
            if fm_url and fm_url != full_link:
                print(f"⚠️  {md.name}: frontmatter `url:` ({fm_url}) doesn't match computed ({full_link}) — update or remove the field")

            updated_raw = fm.get("updated")
            updated = str(updated_raw) if updated_raw else None

            # redirect_from: list of old absolute paths to write meta-refresh stubs at
            redirect_from = fm.get("redirect_from") or []
            if isinstance(redirect_from, str):
                redirect_from = [redirect_from]

            feed_canonical = bool(fm.get("feed_canonical", False))

            raw_posts.append({
                "md_path": md, "title": title, "date": date, "major": major, "slug": slug,
                "link": relative_link, "full_link": full_link, "summary": summary,
                "tags": tags_list, "pinned": pinned, "og_image_url": og_image_url,
                "body": body,
                "lang": detected_lang,
                "updated": updated,
                "family_stem": family_stem,
                "lang_explicit": lang_explicit,
                "final_lang": final_lang,
                "redirect_from": redirect_from,
                "feed_canonical": feed_canonical,
            })

            link_dict[title] = relative_link
            link_dict[md.stem] = relative_link

        except Exception as e:
            print(f"⚠️ Error parsing {md.name} in pass 1: {e}")

    raw_posts.sort(key=lambda x: x["date"], reverse=True)

    # Build language family map: family_stem -> {final_lang: post}
    lang_families = {}
    for p in raw_posts:
        lang_families.setdefault(p["family_stem"], {})[p["final_lang"]] = p

    all_links_json = json.dumps([p["link"] for p in raw_posts])

    for i, p in enumerate(raw_posts):
        body = p["body"]
        ui_lang = "zh-Hant" if is_zh(p["final_lang"]) else "en"
        L = UI_LABELS[ui_lang]
        site_root = L["site_root_3pwriting"]

        def wikilink_replacer(match):
            inner = match.group(1)
            if '|' in inner:
                target, display = inner.split('|', 1)
            else:
                target = inner
                display = inner
            target_clean = target.strip()
            if target_clean in link_dict:
                return f'<a href="{link_dict[target_clean]}" class="text-indigo-600 dark:text-emerald-400 hover:text-indigo-800 dark:hover:text-emerald-300 font-medium underline transition-colors">{display}</a>'
            return display

        body = re.sub(r'\[\[(.*?)\]\]', wikilink_replacer, body)

        article_tags_html_parts = []
        for t in p["tags"]:
            color_class = get_color_for_tag(t)
            tag_link = f"{site_root}{t.lower()}/"
            article_tags_html_parts.append(f'<a href="{tag_link}" class="inline-flex items-center gap-1 uppercase hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors"><span class="w-2 h-2 rounded-full {color_class}"></span>{t}</a>')
        article_tags_html = ' <span class="mx-2 text-slate-300 dark:text-slate-700">|</span> '.join(article_tags_html_parts)

        older_post = raw_posts[i+1] if i + 1 < len(raw_posts) else None
        newer_post = raw_posts[i-1] if i - 1 >= 0 else None
        prev_btn_html = f'<a href="{older_post["link"]}" class="inline-flex items-center gap-2 text-slate-500 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors group" title="{escape(older_post["title"])}"><i data-lucide="arrow-left" class="w-4 h-4 shrink-0 group-hover:-translate-x-1 transition-transform"></i><span class="truncate max-w-[120px] sm:max-w-[200px]">{escape(older_post["title"])}</span></a>' if older_post else '<span></span>'
        next_btn_html = f'<a href="{newer_post["link"]}" class="inline-flex items-center gap-2 text-slate-500 hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors justify-end group" title="{escape(newer_post["title"])}"><span class="truncate max-w-[120px] sm:max-w-[200px]">{escape(newer_post["title"])}</span><i data-lucide="arrow-right" class="w-4 h-4 shrink-0 group-hover:translate-x-1 transition-transform"></i></a>' if newer_post else '<span></span>'

        out_dir, _, _ = post_paths(p["major"], p["slug"], p["final_lang"])
        ensure_dir(out_dir)

        safe_summary = escape(p["summary"]).replace('"', '&quot;')

        content_html = markdown.markdown(body, extensions=["fenced_code", "tables", "footnotes"])
        content_html = add_target_blank_to_external(content_html)
        if p.get('updated'):
            if is_zh(p["final_lang"]):
                label, sep = '最後更新', '：'
            else:
                label, sep = 'Last updated', ': '
            content_html += f'\n<p class="text-sm italic text-slate-400 dark:text-slate-500 mt-12 pt-6 border-t border-slate-200 dark:border-slate-700">{label}{sep}{p["updated"]}</p>'

        # hreflang tags + language switcher
        family = lang_families.get(p["family_stem"], {})
        if len(family) > 1:
            hreflang_lines = [f'<link rel="alternate" hreflang="{p["final_lang"]}" href="{p["full_link"]}" />']
            for lang_code, sibling in family.items():
                if sibling is p:
                    continue
                hreflang_lines.append(f'<link rel="alternate" hreflang="{lang_code}" href="{sibling["full_link"]}" />')
            default_url = family.get("zh-Hant", p)["full_link"]
            hreflang_lines.append(f'<link rel="alternate" hreflang="x-default" href="{default_url}" />')
            hreflang_html = "\n".join(hreflang_lines)

            switcher_parts = []
            for lang_code in LANG_DISPLAY_ORDER:
                if lang_code not in family:
                    continue
                label = LANG_LABELS.get(lang_code, lang_code.upper())
                if lang_code == p["final_lang"]:
                    switcher_parts.append(f'<span class="font-bold text-slate-900 dark:text-slate-100">{label}</span>')
                else:
                    switcher_parts.append(f'<a href="{family[lang_code]["full_link"]}" class="hover:text-indigo-600 dark:hover:text-emerald-400 transition-colors">{label}</a>')
            sep_html = ' <span class="text-slate-300 dark:text-slate-700">|</span> '
            switcher_html = f'<div class="not-prose flex gap-2 items-center text-sm font-mono text-slate-500 dark:text-slate-400 mb-8 -mt-4">{sep_html.join(switcher_parts)}</div>'
        else:
            hreflang_html = ""
            switcher_html = ""

        # Disclaimer i18n
        if is_zh(p["final_lang"]):
            disclaimer_label = "免責聲明："
            disclaimer_body = "此網站僅代表本人觀點，不代表任何相關機構。所有內容僅供參考，未提供具體法律、醫療、稅務或投資建議。請尋求自身專業諮詢。文章內容「按現況」提供，不保證無誤或為最新；請自行研究並承擔依賴本站任何資訊所致之後果。"
        else:
            disclaimer_label = "Disclaimer:"
            disclaimer_body = "This is my website representing my view only, not my affiliated entities. All information is for informational purpose only. No specific legal, medical, tax, investment advice is rendered here. Seek your own professional advice. The content of this post is provided “as is;” and no representations are made that the content is error-free or up-to-date. Thus, please do your own research and take full responsibility for the consequences if you rely on any information here."

        # Lang-switch URL for article pages: prefer sibling article, else fallback to opposite-lang index
        sibling_url = None
        for lang_code, sibling in family.items():
            if sibling is not p:
                sibling_url = sibling["link"]  # relative link works for in-site navigation
                break
        if not sibling_url:
            sibling_url = "/3pwriting/" if is_zh(p["final_lang"]) else "/zh/3pwriting/"
        nav_html = build_nav(ui_lang, active="p3", lang_switch_url=sibling_url)
        random_word = L["random_word"]

        html = (HTML_TMPL
                .replace("{title}", escape(p["title"]))
                .replace("{lang}", p["final_lang"])
                .replace("{date}", escape(p["date"]))
                .replace("{summary}", safe_summary)
                .replace("{og_image}", escape(p["og_image_url"]))
                .replace("{full_link}", escape(p["full_link"]))
                .replace("{tags_html}", article_tags_html)
                .replace("{content}", content_html)
                .replace("{site_author_desc}", escape(SITE_AUTHOR_DESC))
                .replace("{prev_button}", prev_btn_html)
                .replace("{next_button}", next_btn_html)
                .replace("{all_links_array}", all_links_json)
                .replace("{hreflang_tags}", hreflang_html)
                .replace("{lang_switcher}", switcher_html)
                .replace("{nav_html}", nav_html)
                .replace("{random_word}", random_word)
                .replace("{disclaimer_label}", disclaimer_label)
                .replace("{disclaimer_body}", disclaimer_body))

        out_path = out_dir / f"{p['slug']}.html"
        out_path.write_text(html, encoding="utf-8")

        posts.append({
            "title": p["title"], "date": p["date"], "major": p["major"], "slug": p["slug"],
            "link": p["link"], "full_link": p["full_link"], "summary": p["summary"],
            "tags": p["tags"], "pinned": p["pinned"], "updated": p.get("updated"),
            "final_lang": p["final_lang"], "family_stem": p["family_stem"],
            "redirect_from": p["redirect_from"], "feed_canonical": p["feed_canonical"],
        })

    posts.sort(key=lambda x: (x["pinned"], x["date"]), reverse=True)
    all_tags = list(all_tags_set)

    # Index pages — split EN vs ZH
    en_posts = [p for p in posts if not is_zh(p["final_lang"])]
    zh_posts = [p for p in posts if is_zh(p["final_lang"])]
    generate_paginated_list(en_posts, SITE_DIR, "/3pwriting/", "all", all_tags, ui_lang="en")
    generate_paginated_list(zh_posts, ZH_BASE, "/zh/3pwriting/", "all", all_tags, ui_lang="zh-Hant")

    # Tag pages — split EN vs ZH
    for tag in all_tags:
        tag_lower = tag.lower()
        en_tag = [p for p in en_posts if any(t.lower() == tag_lower for t in p["tags"])]
        zh_tag = [p for p in zh_posts if any(t.lower() == tag_lower for t in p["tags"])]
        generate_paginated_list(en_tag, SITE_DIR / tag_lower, f"/3pwriting/{tag_lower}/", tag, all_tags, ui_lang="en")
        generate_paginated_list(zh_tag, ZH_BASE / tag_lower, f"/zh/3pwriting/{tag_lower}/", tag, all_tags, ui_lang="zh-Hant")

    # RSS feed (1 feed, family_stem dedup)
    feed_count = generate_feed(raw_posts, lang_families)

    # Redirect stubs
    stub_count = generate_redirect_stubs(posts)

    # Sitemap
    sitemap_count = generate_sitemap(posts, all_tags)

    print(f"✅ Built {len(posts)} posts ({len(en_posts)} EN + {len(zh_posts)} ZH)")
    print(f"✅ feed.xml: {feed_count} family-stem canonical items")
    print(f"✅ redirect stubs: {stub_count}")
    print(f"✅ sitemap.xml: {sitemap_count} URLs")

if __name__ == "__main__":
    main()
