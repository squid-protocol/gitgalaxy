#!/usr/bin/env python3
"""Keep the Actions cache under GitHub's 10 GB limit by deleting stale branch and PR caches (#4847).

    python tests/tools/cache_prune.py                 # dry run: print the plan and the before/after numbers
    python tests/tools/cache_prune.py --delete        # execute it (the nightly workflow does)

GitHub evicts oldest-first at 10 GB, which can evict main's useful caches (the pip, gradle and m2 caches every PR
restores from) while stale PR caches survive. This prunes on purpose instead, until the total is at or under
`--target-gb` (default 6.5), in this order:

1. caches of PRs that are no longer open (`refs/pull/N/merge`) and of branches nobody pushes to any more;
2. caches not accessed for `--stale-days` (default 7) on any ref but main;
3. while still over target: the least recently accessed non-main cache;
4. last resort: main's older duplicates of a key family (see `family`), oldest first.

The newest cache of every key family on main is never deleted. A PR restores main's caches (same key, different ref),
which is why the pip caches are keyed on file hashes only (test_cache_keys.py).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

REPO = "squid-protocol/gitgalaxy"
MAIN = "refs/heads/main"
GB = 1_000_000_000


def family(key: str) -> str:
    """The key with its content hashes and run numbers blanked: all versions of one cache share a family."""
    key = re.sub(r"\[[0-9a-f]{16,}\]", "[#]", key)  # gradle-home-v2|Linux-X64|compile[<hash>]-<hash>
    key = re.sub(r"[0-9a-f]{16,}", "#", key)
    return re.sub(r"\d{6,}", "#", key)


def _when(cache: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(cache["last_accessed_at"].replace("Z", "+00:00"))


def _pr_number(ref: str) -> int | None:
    m = re.fullmatch(r"refs/pull/(\d+)/merge", ref)
    return int(m.group(1)) if m else None


def plan(
    caches: list[dict[str, Any]],
    open_prs: set[int],
    live_branches: set[str],
    target_bytes: int,
    stale_days: int,
    now: datetime,
) -> list[tuple[dict[str, Any], str]]:
    """The (cache, reason) pairs to delete, in deletion order."""
    newest: dict[str, dict[str, Any]] = {}
    for c in caches:
        fam = family(c["key"])
        if c["ref"] == MAIN and (fam not in newest or _when(c) > _when(newest[fam])):
            newest[fam] = c
    protected = {c["id"] for c in newest.values()}
    total = sum(c["size_in_bytes"] for c in caches)
    out: list[tuple[dict[str, Any], str]] = []
    gone: set[int] = set()

    def drop(c: dict[str, Any], why: str) -> None:
        nonlocal total
        if c["id"] in gone or c["id"] in protected:
            return
        gone.add(c["id"])
        total -= c["size_in_bytes"]
        out.append((c, why))

    others = sorted((c for c in caches if c["ref"] != MAIN), key=_when)
    for c in others:  # 1. dead refs
        n = _pr_number(c["ref"])
        if n is not None and n not in open_prs:
            drop(c, f"PR #{n} is not open")
        elif n is None and c["ref"].removeprefix("refs/heads/") not in live_branches:
            drop(c, "branch no longer exists")
    cutoff = now - timedelta(days=stale_days)
    for c in others:  # 2. stale
        if _when(c) < cutoff:
            drop(c, f"not accessed since {c['last_accessed_at'][:10]}")
    for c in others:  # 3. over target: coldest first
        if total <= target_bytes:
            break
        drop(c, "over target: least recently accessed branch/PR cache")
    for c in sorted((c for c in caches if c["ref"] == MAIN), key=_when):  # 4. main's old duplicates
        if total <= target_bytes:
            break
        drop(c, "over target: main's older copy of a key family")
    return out


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _paged(path: str, field: str | None = None) -> list[Any]:
    """Every item of a paginated list endpoint (`field` names the array inside each page's object)."""
    jq = f".{field}[]" if field else ".[]"
    return [json.loads(line) for line in _gh("api", "--paginate", "-q", jq, path).splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delete", action="store_true", help="delete for real (default: print the plan)")
    ap.add_argument("--target-gb", type=float, default=6.5)
    ap.add_argument("--stale-days", type=int, default=7)
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args(argv)

    caches = _paged(f"repos/{args.repo}/actions/caches?per_page=100", "actions_caches")
    prs = {p["number"] for p in _paged(f"repos/{args.repo}/pulls?state=open&per_page=100")}
    branches = {b["name"] for b in _paged(f"repos/{args.repo}/branches?per_page=100")}
    doomed = plan(caches, prs, branches, int(args.target_gb * GB), args.stale_days, datetime.now(timezone.utc))

    before = sum(c["size_in_bytes"] for c in caches)
    freed = sum(c["size_in_bytes"] for c, _ in doomed)
    print(f"before: {before / GB:.2f} GB in {len(caches)} caches")
    for c, why in doomed:
        print(
            f"  {'delete' if args.delete else 'would delete'} {c['id']} {c['size_in_bytes'] / 1e6:7.1f} MB {c['ref']} {c['key'][:70]} ({why})"
        )
    print(f"after:  {(before - freed) / GB:.2f} GB in {len(caches) - len(doomed)} caches (target {args.target_gb} GB)")
    if args.delete:
        for c, _ in doomed:
            _gh("api", "-X", "DELETE", f"repos/{args.repo}/actions/caches/{c['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
