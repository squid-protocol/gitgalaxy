"""
#3313 step 4: the wrapper-aware count (`wrapped_<rule>`), per
docs/wrapper_aware_count_contract.md.

  - Each file's count is the call sites IN IT that resolve to a wrapper; the
    defining file of a wrapper nobody inside it calls reads 0.
  - A chain is several sites, each counted once where it appears.
  - It lands on file_data and, summed, on repo_data; a delta scan recomputes it.
  - D1: no score reads it (guarded here against gitgalaxy/metrics).
"""

import re
import sqlite3
from pathlib import Path

from gitgalaxy.core.wrapper_resolver import WRAPPED_RULES, attach_wrappers, resolve_wrappers
from gitgalaxy.recorders import record_keeper
from gitgalaxy.recorders.record_keeper import RecordKeeper

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cand(name, hits=(), callees=(), loc=5, branches=0):
    return {
        "name": name,
        "loc": loc,
        "branches": branches,
        "aligned": True,
        "method": False,
        "hits": list(hits),
        "callees": list(callees),
    }


def _file(path, defined=(), candidates=(), calls=None, macros=(), lang="c", equations=None):
    return {
        "path": path,
        "lang_id": lang,
        "raw_imports": [],
        "equations": dict(equations or {}),
        "wrapper_facts": {
            "defined": {n: 1 for n in defined},
            "candidates": list(candidates),
            "calls": dict(calls or {}),
            "macros": list(macros),
        },
    }


def _wrf():
    return [
        _file(
            "wrf/wrapper.F",
            ["wrf_error_fatal"],
            [_cand("wrf_error_fatal", ["debug_prints", "panics_and_aborts"])],
            lang="fortran",
            equations={"debug_prints": 1, "panics_and_aborts": 1},
        ),
        _file("wrf/caller.F", ["init_domain"], calls={"wrf_error_fatal": 3}, lang="fortran"),
    ]


def test_each_file_counts_the_wrapped_sites_in_it():
    files = _wrf()
    attach_wrappers(files, resolve_wrappers(files))
    by_path = {f["path"]: f["wrapped_sites"] for f in files}
    assert by_path["wrf/caller.F"] == {"debug_prints": 3, "panics_and_aborts": 3, "memory_alloc": 0}
    # The wrapper's own `print`/`stop` are literal hits, never wrapped ones (corollary 1).
    assert by_path["wrf/wrapper.F"] == dict.fromkeys(WRAPPED_RULES, 0)


def test_a_chain_is_several_sites_each_counted_where_it_appears():
    """curl 8.18: `curl_free(p)` in a caller is a site of curl_free; the
    `curlx_free(p)` inside curl_free's body is a site of curlx_free."""
    files = [
        _file("curl_setup.h", macros=[{"name": "curlx_free", "hits": ["memory_alloc"], "called": ["free"]}]),
        _file("escape.c", ["curl_free"], [_cand("curl_free", callees=["curlx_free"])], calls={"curlx_free": 1}),
        _file("url.c", ["cleanup"], calls={"curl_free": 3, "curlx_free": 2}),
    ]
    attach_wrappers(files, resolve_wrappers(files))
    wrapped = {f["path"]: f["wrapped_sites"]["memory_alloc"] for f in files}
    assert wrapped == {"curl_setup.h": 0, "escape.c": 1, "url.c": 5}


SESSION = {
    "target": "WrapRepo",
    "git_audit": {"commit_hash": "w4", "latest_commit_date": "2026-09-23T00:00:00Z"},
}


def _record(db, files):
    rows = resolve_wrappers(files)
    attach_wrappers(files, rows)
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), wrappers=rows)


def _q(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_the_counts_land_on_file_data_and_sum_into_repo_data(tmp_path):
    db = tmp_path / "w.db"
    _record(db, _wrf())
    assert _q(
        db,
        "SELECT file_path, wrapped_debug_prints, wrapped_panics_and_aborts, wrapped_memory_alloc "
        "FROM file_data ORDER BY file_path",
    ) == [("wrf/caller.F", 3, 3, 0), ("wrf/wrapper.F", 0, 0, 0)]
    assert _q(db, "SELECT wrapped_debug_prints, wrapped_panics_and_aborts, wrapped_memory_alloc FROM repo_data") == [
        (3, 3, 0)
    ]


def test_a_delta_scan_recomputes_the_same_counts(tmp_path):
    """The count is never restored; it is re-derived from the persisted facts."""
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    db = tmp_path / "w.db"
    files = _wrf()
    _record(db, files)
    cache = StateRehydrator(str(db)).load_state("WrapRepo")["ram_cache"]
    restored = [{"path": p, **node} for p, node in sorted(cache.items())]
    attach_wrappers(restored, resolve_wrappers(restored))
    assert {f["path"]: f["wrapped_sites"] for f in restored} == {f["path"]: f["wrapped_sites"] for f in files}


def test_the_recorder_and_resolver_agree_on_the_rules():
    assert record_keeper.WRAPPED_RULES == WRAPPED_RULES


def test_no_score_reads_the_wrapper_aware_count():
    """D1: the count is report-only. A risk formula that starts reading it is a
    measured score-contract change (score-contract-audit), not a side effect."""
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in (REPO_ROOT / "gitgalaxy" / "metrics").rglob("*.py")
        if re.search(r"wrapped_(sites|debug_prints|panics_and_aborts|memory_alloc)", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
