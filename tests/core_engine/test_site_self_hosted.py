"""gitgalaxy.io must not load anything from a third party: the vendored files are intact, no page reaches for a
CDN, and the content-security-policy is enforcing and names no external host."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
VENDOR = SITE / "vendor"
# The one dev-only page that still uses a CDN; nginx returns 404 for it.
DEV_ONLY = {SITE / "tools" / "style_guide.html"}

# Things that make the browser fetch an external resource (plain links to other sites are fine).
LOADS = [
    re.compile(r"<script\b[^>]*\bsrc=[\"']https?://", re.IGNORECASE),
    re.compile(
        r"<link\b(?![^>]*rel=[\"'](?:canonical|alternate)[\"'])[^>]*\bhref=[\"']https?://",
        re.IGNORECASE,
    ),
    re.compile(r"@import\s+(?:url\()?\s*[\"']?https?://", re.IGNORECASE),
    re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE),
    re.compile(
        r"[\"'][^\"'\s]+[\"']\s*:\s*[\"']https?://[^\"']+\.(?:js|mjs)[\"']"
    ),  # import map entries
    re.compile(r"\bimport\s*(?:\(|[^;(]*?\sfrom\s)\s*[\"']https?://"),
    re.compile(r"new\s+Worker\(\s*[\"']https?://"),
]


def _site_pages() -> list[Path]:
    pages = [
        SITE / "index.html",
        *SITE.glob("blog/**/*.html"),
        *SITE.glob("css/*.css"),
        VENDOR / "fonts" / "fonts.css",
    ]
    pages += [p for p in SITE.glob("js/**/*") if p.suffix in {".js", ".html"}]
    pages += [
        p
        for p in SITE.glob("tools/*")
        if p.suffix in {".js", ".html"} and p not in DEV_ONLY
    ]
    return [p for p in pages if p.exists()]


def test_vendored_files_match_their_checksums():
    lines = (VENDOR / "SHA256SUMS").read_text().splitlines()
    assert lines, "SHA256SUMS is empty"
    listed = set()
    for line in lines:
        digest, name = line.split(None, 1)
        name = name.strip().removeprefix("./")
        listed.add(name)
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, (
            f"{name} was modified"
        )
    on_disk = {
        str(p.relative_to(VENDOR))
        for p in VENDOR.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS"
    }
    assert on_disk == listed, (
        f"unlisted or missing vendored files: {sorted(on_disk ^ listed)}"
    )


def test_every_vendored_library_ships_its_licence():
    for lic in (
        "three/LICENSE",
        "tween/LICENSE",
        "fonts/OFL-SpaceGrotesk.txt",
        "fonts/OFL-SpaceMono.txt",
    ):
        assert (VENDOR / lic).stat().st_size > 500, f"{lic} missing or empty"


def test_pages_load_nothing_from_a_third_party():
    offenders = []
    for page in _site_pages():
        text = page.read_text(encoding="utf-8", errors="replace")
        offenders += [
            f"{page.relative_to(SITE)}: {m.group(0)[:80]}"
            for rx in LOADS
            for m in rx.finditer(text)
        ]
    assert not offenders, (
        "external loads found (vendor them under site/vendor/):\n"
        + "\n".join(offenders)
    )


def test_csp_is_enforcing_and_allows_no_external_host():
    snippet = (
        SITE / "deploy" / "nginx" / "snippets" / "gitgalaxy-security-headers.conf"
    ).read_text()
    policy = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]+)"', snippet)
    assert policy, (
        "no enforcing Content-Security-Policy header (Report-Only does not count)"
    )
    assert "http://" not in policy.group(1) and "https://" not in policy.group(1), (
        policy.group(1)
    )
    assert "'unsafe-eval'" not in policy.group(1)
