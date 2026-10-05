"""estate4_draw: selection arithmetic, allow-list, committed request log, heuristics."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import estate4_draw as e4  # noqa: E402

LOG = ROOT / "docs" / "language_status" / "estate4_candidates_requests.json"
CANDS = ROOT / "docs" / "language_status" / "estate4_candidates.json"


def _fake() -> list[dict]:
    return [
        {"full_name": "a/one", "weight": 1},
        {"full_name": "b/two", "weight": 3},
        {"full_name": "c/three", "weight": 2},
    ]


def test_selection_walks_cumulative_weights():
    cands = _fake()  # cumulative: a 0, b 1-3, c 4-5, total 6
    expected = {0: "a/one", 1: "b/two", 3: "b/two", 4: "c/three", 5: "c/three"}
    for idx, name in expected.items():
        seed = format(6 * 1000 + idx, "064x")  # int(seed,16) mod 6 == idx
        got_idx, total, win = e4.select(cands, seed)
        assert (got_idx, total, win["full_name"]) == (idx, 6, name)


def test_seed_is_sha256_of_randomness_plus_candidates_hash():
    data = b'{"candidates": []}'
    rnd = "ab" * 32
    want = hashlib.sha256((rnd + hashlib.sha256(data).hexdigest()).encode()).hexdigest()
    assert e4.compute_seed(rnd, data) == want
    cands = _fake()
    _, _, win = e4.select(cands, want)
    assert win in cands


def test_target_round_arithmetic():
    r = e4.round_for_time(e4.TARGET_TIME)
    assert e4.round_time(r) >= e4.TARGET_TIME
    assert e4.round_time(r - 1) < e4.TARGET_TIME
    assert e4.round_time(1) == dt.datetime.fromtimestamp(e4.DRAND_GENESIS, tz=dt.UTC)
    assert r == 6531446


@pytest.mark.parametrize(
    "url",
    [
        "https://api.github.com/repos/o/r/contents/x.cbl",
        "https://api.github.com/repos/o/r/readme",
        "https://api.github.com/repos/o/r/git/blobs/abc",
        "https://raw.githubusercontent.com/o/r/main/x",
        "https://api.github.com/search/code?q=x",
        "https://api.github.com/repos/o/r/git/trees/main",
        "https://api.github.com/repos/o/r/git/blobs/" + "a" * 40,
        "https://api.github.com/repos/o/r/git/commits/main",
        "https://api.github.com/repos/o/r/git/commits/" + "a" * 40 + "/comments",
        "https://api.github.com/repos/o/r/commits/main",
        "https://api.github.com/repos/o/r/git/ref/tags/v1",
    ],
)
def test_allow_list_blocks_content_endpoints(url):
    assert not e4.is_allowed("GET", url)


def test_allow_list_permits_metadata_endpoints():
    ok = [
        "https://api.github.com/search/repositories?q=language%3ACOBOL&per_page=1",
        "https://api.github.com/repos/o/r.github.io",
        "https://api.github.com/repos/o/r/languages",
        "https://api.github.com/repos/o/r/license",
        "https://api.github.com/repos/o/r/git/trees/main?recursive=1",
        "https://api.github.com/users/o",
        "https://api.github.com/repos/o/r/git/ref/heads/main",
        "https://api.github.com/repos/o/r/git/commits/" + "a" * 40,
    ]
    assert all(e4.is_allowed("GET", u) for u in ok)
    assert not e4.is_allowed("POST", ok[0])


def test_client_refuses_forbidden_request_before_any_network():
    client = e4.ApiClient("t", Path("/nonexistent/cache.json"))
    with pytest.raises(PermissionError):
        client.get("/repos/o/r/contents/a")


def test_committed_request_log_has_no_forbidden_endpoint():
    if not LOG.exists():
        pytest.skip("no request log committed yet")
    entries = json.loads(LOG.read_text())
    assert entries, "empty log"
    assert e4.forbidden_in_log(entries) == []


def test_committed_candidates_are_sorted_and_weights_consistent():
    if not CANDS.exists():
        pytest.skip("no candidates committed yet")
    doc = json.loads(CANDS.read_text())
    names = [c["full_name"] for c in doc["candidates"]]
    assert names == sorted(names)
    assert all(c["weight"] == 1 + c["foreign"] + c["hard"] for c in doc["candidates"])
    assert doc["total_weight"] == sum(c["weight"] for c in doc["candidates"])
    assert all(c["license"] in e4.OK_LICENSES for c in doc["candidates"])


def test_foreign_and_hard_heuristics():
    assert e4.compute_foreign("Sistema de cadastro para clientes", [], [], None) == 1
    assert e4.compute_foreign("Banking sample application", [], ["a/b.cbl"], "Austin, TX") == 0
    assert e4.compute_foreign("x", [], ["src/é.cbl"], "Sao Paulo, Brazil") == 2
    assert e4.location_foreign("Dublin, Ireland") is False
    assert e4.location_foreign("Bangalore") is True
    assert e4.compute_hard(["jcl/a.txt", "x.pli", "asm/y.s", "z.sql"], 60) == 5
    assert e4.compute_hard(["a.cbl"], 3) == 0


def test_burned_overlap_threshold():
    burned = {"e": ["a", "b", "c"]}
    assert e4.burned_overlap(["a", "x", "y"], burned)[0] == pytest.approx(1 / 3)
    assert e4.burned_overlap([], burned)[0] == 0.0
