"""#4847: the nightly cache prune keeps main's newest caches and deletes stale branch/PR caches down to the target."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cache_prune as cp  # noqa: E402

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
MB = 1_000_000
_ids = iter(range(1, 1000))


def cache(ref, key, mb, days_ago):
    when = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": next(_ids), "ref": ref, "key": key, "size_in_bytes": mb * MB, "last_accessed_at": when}


def run(caches, prs=(), branches=(), target_gb=0.5, stale=7):
    return cp.plan(caches, set(prs), set(branches), int(target_gb * cp.GB), stale, NOW)


def test_family_blanks_hashes_and_run_numbers():
    a = "setup-python-Linux-x64-python-3.12-pip-" + "a" * 64
    b = "setup-python-Linux-x64-python-3.12-pip-" + "b" * 64
    assert cp.family(a) == cp.family(b) != cp.family(a.replace("3.12", "3.11"))
    assert (
        cp.family("gradle-home-v2|Linux-X64|compile[" + "1" * 32 + "]-" + "2" * 40)
        == "gradle-home-v2|Linux-X64|compile[#]-#"
    )
    assert cp.family("test-durations-123456789") == cp.family("test-durations-987654321")


def test_closed_pr_and_dead_branch_caches_go_open_pr_stays():
    caches = [
        cache("refs/pull/1/merge", "pip-" + "a" * 64, 400, 0),
        cache("refs/pull/2/merge", "pip-" + "a" * 64, 400, 0),
        cache("refs/heads/gone", "pip-" + "a" * 64, 10, 0),
        cache("refs/heads/live", "pip-" + "a" * 64, 10, 0),
    ]
    got = {c["ref"] for c, _ in run(caches, prs={2}, branches={"live"}, target_gb=5)}
    assert got == {"refs/pull/1/merge", "refs/heads/gone"}


def test_stale_non_main_caches_go_even_under_target():
    caches = [cache("refs/pull/2/merge", "x-" + "a" * 64, 1, 8), cache("refs/pull/2/merge", "y-" + "a" * 64, 1, 1)]
    got = run(caches, prs={2}, target_gb=5)
    assert [c["key"][0] for c, _ in got] == ["x"]


def test_over_target_drops_coldest_non_main_first_then_main_duplicates_but_never_the_newest():
    old, new = "pip-" + "a" * 64, "pip-" + "b" * 64
    caches = [
        cache("refs/heads/main", old, 300, 5),
        cache("refs/heads/main", new, 300, 1),
        cache("refs/heads/main", "gradle-" + "c" * 64, 300, 30),  # only copy of its family: protected however old
        cache("refs/pull/2/merge", "z-" + "d" * 64, 300, 2),
    ]
    got = run(caches, prs={2}, target_gb=0.5)
    assert [c["ref"] for c, _ in got] == ["refs/pull/2/merge", "refs/heads/main"]
    assert got[1][0]["key"] == old
    assert not {c["key"] for c, _ in run(caches, prs={2}, target_gb=0.0)} & {new, "gradle-" + "c" * 64}


def test_under_target_deletes_nothing():
    caches = [cache("refs/heads/main", "k-" + "a" * 64, 100, 1), cache("refs/pull/2/merge", "k-" + "a" * 64, 100, 1)]
    assert run(caches, prs={2}, target_gb=5) == []
