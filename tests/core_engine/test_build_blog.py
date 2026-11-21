"""site/tools/build_blog.py: front matter rules, generated files, and that the committed output is fresh."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("markdown")
pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "build_blog", ROOT / "site" / "tools" / "build_blog.py"
)
bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bb)

POST = "---\ntitle: {title}\ndate: {date}\ndescription: {desc}\n{extra}---\n\nHello **world**.\n"


def _site(tmp_path, monkeypatch, posts: dict[str, str]):
    (tmp_path / "blog" / "posts").mkdir(parents=True)
    for name, text in posts.items():
        (tmp_path / "blog" / "posts" / name).write_text(text, encoding="utf-8")
    (tmp_path / "blog" / "articles.yml").write_text(
        "base: https://example.org/m/\ngroups:\n  - title: G\n    items:\n      - {title: T, path: t/, description: D}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "SITE", tmp_path)
    monkeypatch.setattr(bb, "POSTS", tmp_path / "blog" / "posts")
    monkeypatch.setattr(bb, "ARTICLES", tmp_path / "blog" / "articles.yml")


def test_committed_output_is_up_to_date():
    stale = [
        p
        for p, text in bb.build().items()
        if not p.exists() or p.read_text(encoding="utf-8") != text
    ]
    assert not stale, f"run python site/tools/build_blog.py ({[str(p) for p in stale]})"


def test_post_is_built_listed_and_in_sitemap(tmp_path, monkeypatch):
    _site(
        tmp_path,
        monkeypatch,
        {
            "my-post.md": POST.format(
                title="A <b>title</b>", date="2026-11-21", desc="Why & how", extra=""
            )
        },
    )
    out = bb.build()
    page = out[tmp_path / "blog" / "my-post" / "index.html"]
    assert (
        "<strong>world</strong>" in page
        and 'rel="canonical" href="https://gitgalaxy.io/blog/my-post/"' in page
    )
    assert "A &lt;b&gt;title&lt;/b&gt;" in page, "titles must be HTML-escaped"
    assert "/blog/my-post/" in out[tmp_path / "blog" / "index.html"]
    assert (
        "<loc>https://gitgalaxy.io/blog/my-post/</loc>" in out[tmp_path / "sitemap.xml"]
    )
    assert (
        "<title>A &lt;b&gt;title&lt;/b&gt;</title>"
        in out[tmp_path / "blog" / "feed.xml"]
    )


def test_no_posts_still_builds(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, {})
    out = bb.build()
    assert "https://example.org/m/t/" in out[tmp_path / "blog" / "index.html"]
    assert "Sitemap: https://gitgalaxy.io/sitemap.xml" in out[tmp_path / "robots.txt"]


def test_drafts_and_underscore_files_are_skipped(tmp_path, monkeypatch):
    _site(
        tmp_path,
        monkeypatch,
        {
            "d.md": POST.format(
                title="D", date="2026-11-21", desc="d", extra="draft: true\n"
            ),
            "_x.md": POST.format(title="X", date="2026-11-21", desc="x", extra=""),
            "README.md": "# not a post",
        },
    )
    assert not any("blog/d/" in str(p) or "blog/_x/" in str(p) for p in bb.build())


@pytest.mark.parametrize("slug", ["data", "api", "Bad Slug", "../x"])
def test_reserved_or_bad_slugs_are_rejected(tmp_path, monkeypatch, slug):
    _site(
        tmp_path,
        monkeypatch,
        {
            "p.md": POST.format(
                title="T", date="2026-11-21", desc="d", extra=f'slug: "{slug}"\n'
            )
        },
    )
    with pytest.raises(SystemExit):
        bb.build()


def test_missing_front_matter_fails_clearly(tmp_path, monkeypatch):
    _site(tmp_path, monkeypatch, {"p.md": "no front matter"})
    with pytest.raises(SystemExit, match="front matter"):
        bb.build()
