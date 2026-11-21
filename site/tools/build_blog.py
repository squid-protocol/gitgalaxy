#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Build the gitgalaxy.io blog as static files.

    python site/tools/build_blog.py            # write the generated files
    python site/tools/build_blog.py --check    # exit 1 if the committed files are stale

Input : site/blog/posts/*.md        (front matter: title, date, description; optional slug, draft, canonical)
        site/blog/articles.yml      (existing articles that live on the docs site; linked, not copied)
Output: site/blog/index.html, site/blog/<slug>/index.html, site/blog/feed.xml,
        site/sitemap.xml, site/robots.txt

Output is deterministic (no build timestamps) so --check can run in CI. Needs `markdown` and `pyyaml`.
nginx serves the result as plain static files; nothing here runs on the server.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from email.utils import format_datetime
from pathlib import Path

import markdown
import yaml

SITE_URL = "https://gitgalaxy.io"
DOCS_URL = "https://squid-protocol.github.io/gitgalaxy/"
GITHUB_URL = "https://github.com/squid-protocol/gitgalaxy"
BLOG_TITLE = "GitGalaxy blog"
BLOG_DESC = "Studies and write-ups from the GitGalaxy project: what code looks like when you measure its structure."

SITE = Path(__file__).resolve().parent.parent
POSTS = SITE / "blog" / "posts"
ARTICLES = SITE / "blog" / "articles.yml"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)

# Locations the viewer's data and nginx already use; a post slug must not shadow them.
RESERVED = {"data", "backend", "museum", "api", "css", "js", "tools", "config", "blog"}


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


class Post:
    def __init__(self, path: Path):
        raw = path.read_text(encoding="utf-8")
        m = FRONT_RE.match(raw)
        if not m:
            raise SystemExit(f"{path.name}: missing front matter (--- ... ---)")
        meta = yaml.safe_load(m.group(1)) or {}
        for key in ("title", "date", "description"):
            if not meta.get(key):
                raise SystemExit(f"{path.name}: front matter needs '{key}'")
        self.title = str(meta["title"])
        d = meta["date"]
        self.date = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))
        self.description = str(meta["description"])
        self.slug = str(meta.get("slug") or path.stem)
        if not SLUG_RE.match(self.slug) or self.slug in RESERVED:
            raise SystemExit(f"{path.name}: bad or reserved slug '{self.slug}'")
        self.draft = bool(meta.get("draft", False))
        self.canonical = meta.get("canonical") or f"{SITE_URL}/blog/{self.slug}/"
        self.body_html = markdown.markdown(
            m.group(2), extensions=["fenced_code", "tables", "toc", "sane_lists"]
        )

    @property
    def url(self) -> str:
        return f"{SITE_URL}/blog/{self.slug}/"


def load_posts() -> list[Post]:
    posts = [
        Post(p)
        for p in sorted(POSTS.glob("*.md"))
        if not p.name.startswith(("_", "README"))
    ]
    posts = [p for p in posts if not p.draft]
    slugs = [p.slug for p in posts]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("duplicate post slugs")
    return sorted(posts, key=lambda p: (p.date, p.slug), reverse=True)


def shell(
    title: str,
    description: str,
    canonical: str,
    body: str,
    *,
    current: str = "",
    extra_head: str = "",
) -> str:
    def cur(name: str) -> str:
        return ' aria-current="page"' if name == current else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="theme-color" content="#010103">
<meta property="og:site_name" content="GitGalaxy">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="{esc(BLOG_TITLE)}" href="/blog/feed.xml">
<link rel="stylesheet" href="/blog/blog.css">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
<a class="brand" href="/">GitGalaxy</a>
<nav aria-label="Site">
<a href="/">Viewer</a>
<a href="/blog/"{cur("blog")}>Blog</a>
<a href="{DOCS_URL}">Docs</a>
<a href="{GITHUB_URL}">GitHub</a>
</nav>
</header>
<main id="main">
{body}</main>
<footer class="site-footer">GitGalaxy &middot; <a href="{GITHUB_URL}">source</a> &middot; <a href="/blog/feed.xml">RSS</a></footer>
</body>
</html>
"""


def render_post(p: Post) -> str:
    ld = (
        '{"@context":"https://schema.org","@type":"BlogPosting",'
        f'"headline":{_json(p.title)},"datePublished":"{p.date.isoformat()}",'
        f'"description":{_json(p.description)},"mainEntityOfPage":{_json(p.canonical)},'
        '"author":{"@type":"Person","name":"Joe Esquibel"}}'
    )
    head = f'<script type="application/ld+json">{ld}</script>\n'
    body = (
        f"<article>\n<h1>{esc(p.title)}</h1>\n"
        f'<p class="meta"><time datetime="{p.date.isoformat()}">{p.date.isoformat()}</time></p>\n'
        f"{p.body_html}\n</article>\n"
    )
    return shell(
        f"{p.title} | GitGalaxy",
        p.description,
        p.canonical,
        body,
        current="blog",
        extra_head=head,
    )


def _json(value: str) -> str:
    import json

    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_index(posts: list[Post], groups: list[dict], base: str) -> str:
    parts = [f"<h1>{esc(BLOG_TITLE)}</h1>\n", f'<p class="lede">{esc(BLOG_DESC)}</p>\n']
    if posts:
        parts.append('<h2>Posts</h2>\n<ul class="entries">\n')
        for p in posts:
            parts.append(
                f'<li><span class="date">{p.date.isoformat()}</span><br>'
                f'<a class="title" href="/blog/{esc(p.slug)}/">{esc(p.title)}</a>'
                f'<span class="desc">{esc(p.description)}</span></li>\n'
            )
        parts.append("</ul>\n")
    for g in groups:
        parts.append(f'<h2>{esc(g["title"])}</h2>\n<ul class="entries">\n')
        for it in g["items"]:
            parts.append(
                f'<li><a class="title" href="{esc(base + it["path"])}">{esc(it["title"])}</a>'
                f'<span class="desc">{esc(it["description"])}</span></li>\n'
            )
        parts.append("</ul>\n")
    return shell(
        BLOG_TITLE + " | GitGalaxy",
        BLOG_DESC,
        f"{SITE_URL}/blog/",
        "".join(parts),
        current="blog",
    )


def render_feed(posts: list[Post]) -> str:
    def rfc822(d: dt.date) -> str:
        return format_datetime(
            dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc)
        )

    items = "".join(
        f'<item><title>{esc(p.title)}</title><link>{esc(p.url)}</link><guid isPermaLink="true">{esc(p.url)}</guid>'
        f"<pubDate>{rfc822(p.date)}</pubDate><description>{esc(p.description)}</description></item>\n"
        for p in posts[:30]
    )
    last = f"<lastBuildDate>{rfc822(posts[0].date)}</lastBuildDate>\n" if posts else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n<channel>\n'
        f"<title>{esc(BLOG_TITLE)}</title>\n<link>{SITE_URL}/blog/</link>\n<description>{esc(BLOG_DESC)}</description>\n"
        f"<language>en</language>\n{last}{items}</channel>\n</rss>\n"
    )


def render_sitemap(posts: list[Post]) -> str:
    urls = [
        (f"{SITE_URL}/", None),
        (f"{SITE_URL}/blog/", posts[0].date if posts else None),
    ]
    urls += [(p.url, p.date) for p in posts]
    body = "".join(
        f"<url><loc>{esc(u)}</loc>"
        + (f"<lastmod>{d.isoformat()}</lastmod>" if d else "")
        + "</url>\n"
        for u, d in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'


def render_robots() -> str:
    # The galaxy data files are large JSON that no search result needs; keep crawlers off them.
    return (
        "User-agent: *\nAllow: /\nDisallow: /data/\nDisallow: /backend/\nDisallow: /museum/\nDisallow: /api/\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def build() -> dict[Path, str]:
    cfg = yaml.safe_load(ARTICLES.read_text(encoding="utf-8"))
    posts = load_posts()
    out: dict[Path, str] = {
        SITE / "blog" / "index.html": render_index(posts, cfg["groups"], cfg["base"]),
        SITE / "blog" / "feed.xml": render_feed(posts),
        SITE / "sitemap.xml": render_sitemap(posts),
        SITE / "robots.txt": render_robots(),
    }
    for p in posts:
        out[SITE / "blog" / p.slug / "index.html"] = render_post(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail if committed output differs from a fresh build",
    )
    args = ap.parse_args()
    files = build()
    if args.check:
        stale = [
            str(p.relative_to(SITE))
            for p, text in files.items()
            if not p.exists() or p.read_text(encoding="utf-8") != text
        ]
        if stale:
            print(
                "stale generated files (run: python site/tools/build_blog.py):",
                *stale,
                sep="\n  ",
            )
            return 1
        print(f"blog up to date ({len(files)} files)")
        return 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
