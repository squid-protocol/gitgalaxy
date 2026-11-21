#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver, ...) which wiki pages changed.

Run by .github/workflows/deploy-docs.yml after `mkdocs gh-deploy`. It maps the
docs/wiki/*.md files changed between two commits to their published URLs and POSTs
only those, so unchanged pages are never resubmitted (IndexNow asks for changes only).

The key is public by design: the protocol proves site ownership by fetching
<site>/<key>.txt, so the key file lives in docs/wiki/ and ships with the site.
Google does not read IndexNow; it needs Search Console.

stdlib only; exit 0 on every network failure so a ping never blocks a docs deploy.

    python scripts/indexnow_submit.py --base <sha> --head <sha> [--dry-run]
    python scripts/indexnow_submit.py --all [--dry-run]   # one-time: every sitemap URL
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://squid-protocol.github.io/gitgalaxy/"
HOST = "squid-protocol.github.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
DOCS = Path("docs/wiki")
ZERO_SHA = "0" * 40
KEY_FILE_RE = re.compile(r"^[0-9a-f]{8,128}\.txt$")
MAX_URLS = 10_000  # protocol limit per request


def find_key(docs: Path = DOCS) -> str:
    """Return the key: the one `<hex>.txt` file in docs/wiki whose content is its own name."""
    keys = [
        p.stem
        for p in docs.glob("*.txt")
        if KEY_FILE_RE.match(p.name) and p.read_text().strip() == p.stem
    ]
    if len(keys) != 1:
        raise SystemExit(
            f"expected exactly one IndexNow key file in {docs}, found {keys}"
        )
    return keys[0]


def page_url(md_path: str) -> str | None:
    """docs/wiki/foo.md -> SITE/foo/ ; index.md -> SITE ; non-markdown -> None."""
    rel = Path(md_path)
    try:
        rel = rel.relative_to(DOCS)
    except ValueError:
        return None
    if rel.suffix != ".md":
        return None
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "index":
        parts.pop()
    return SITE + "".join(urllib.parse.quote(p) + "/" for p in parts)


def changed_pages(base: str, head: str) -> list[str]:
    if not base or base == ZERO_SHA:
        base = f"{head}~1"
    proc = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=AMR",
            base,
            head,
            "--",
            str(DOCS),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:  # e.g. a shallow checkout missing the base commit
        print(
            f"git diff failed, nothing to submit: {proc.stderr.strip()}",
            file=sys.stderr,
        )
        return []
    out = proc.stdout.split()
    return sorted({u for p in out if (u := page_url(p))})


def sitemap_pages() -> list[str]:
    """Every URL in the live sitemap, for a one-time bulk submit (`--all`)."""
    with urllib.request.urlopen(f"{SITE}sitemap.xml", timeout=30) as r:
        xml = r.read().decode()
    urls = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        parts = urllib.parse.urlsplit(html.unescape(loc))
        urls.add(
            parts._replace(path=urllib.parse.quote(parts.path, safe="/%")).geturl()
        )
    return sorted(urls)


def wait_for_key(key: str, timeout: int) -> bool:
    """The new site goes live a minute or two after gh-deploy; IndexNow fetches the key file."""
    url = f"{SITE}{key}.txt"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                if r.status == 200 and r.read().decode().strip() == key:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(15)
    return False


def submit(key: str, urls: list[str]) -> int:
    body = json.dumps(
        {
            "host": HOST,
            "key": key,
            "keyLocation": f"{SITE}{key}.txt",
            "urlList": urls[:MAX_URLS],
        }
    ).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except (
        urllib.error.HTTPError
    ) as e:  # 200/202 ok; 403 bad key; 422 url/host mismatch; 429 slow down
        return e.code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument(
        "--wait",
        type=int,
        default=300,
        help="seconds to wait for the key file to go live",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="submit every URL in the live sitemap (one-time bulk)",
    )
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = find_key()
    urls = sitemap_pages() if a.all else changed_pages(a.base, a.head)
    print(f"{len(urls)} {'sitemap' if a.all else 'changed wiki'} page(s)")
    for u in urls[:20]:
        print(" ", u)
    if not urls or a.dry_run:
        return 0
    if not wait_for_key(key, a.wait):
        print(
            "key file not live yet; skipping (next docs change will resubmit)",
            file=sys.stderr,
        )
        return 0
    status = submit(key, urls)
    print(f"IndexNow responded {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
