"""#8161 (owner decision, docs/calls_out_rule_contract.md "Edge kinds"): a C call that ties across several
definitions -- one function defined per platform -- keeps its ambiguous `tie` row in fcall_data, and every
candidate becomes a `variant` edge in `fcall_candidates`, with the platform its path names. The confident
graph is unchanged: no variant is an fcall row, a file-graph pair or a PageRank edge."""

import sqlite3

import pytest

from gitgalaxy.core.call_resolver import confident_file_pairs, platform_of, resolve_calls
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "VariantRepo",
    "git_audit": {"commit_hash": "f8161", "latest_commit_date": "2026-11-09T00:00:00Z"},
}


def _fn(name, line, calls=()):
    return {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: [""] for c in calls},
    }


def _files():
    return [
        {"path": "src/core.c", "lang_id": "c", "raw_imports": [], "functions": [_fn("uv_run", 1, ["uv__io_poll"])]},
        {"path": "src/unix/linux.c", "lang_id": "c", "raw_imports": [], "functions": [_fn("uv__io_poll", 3)]},
        {"path": "src/unix/kqueue.c", "lang_id": "c", "raw_imports": [], "functions": [_fn("uv__io_poll", 5)]},
        {"path": "src/win/core.c", "lang_id": "c", "raw_imports": [], "functions": [_fn("uv__io_poll", 7)]},
    ]


@pytest.mark.parametrize(
    ("path", "platform"),
    [
        ("src/unix/linux.c", "linux"),
        ("src/unix/kqueue.c", "bsd"),
        ("src/unix/core.c", "unix"),
        ("src/win/core.c", "windows"),
        ("sockcompat_win32.c", "windows"),
        ("src/unix/darwin-proctitle.c", "darwin"),
        ("src/unix/os390-syscalls.c", "zos"),
        ("src/uv-common.c", None),
        ("alloc.c", None),
    ],
)
def test_the_platform_a_path_names(path, platform):
    assert platform_of(path) == platform


def test_a_tie_keeps_its_row_and_lists_every_candidate():
    sites, _ = resolve_calls(_files())
    (site,) = [s for s in sites if s["callee"] == "uv__io_poll"]
    assert (site["step"], site["dst_path"]) == ("tie", None)
    assert [(v["dst_path"], v["dst_line"], v["platform"]) for v in site["variants"]] == [
        ("src/unix/kqueue.c", 5, "bsd"),
        ("src/unix/linux.c", 3, "linux"),
        ("src/win/core.c", 7, "windows"),
    ]
    assert confident_file_pairs(sites) == {}  # the confident graph is unchanged


def test_a_resolved_call_has_no_variants():
    files = _files()[:2]
    (site,) = resolve_calls(files)[0]
    assert site["step"] == "unique"
    assert "variants" not in site


def test_variants_are_recorded_in_fcall_candidates(tmp_path):
    db = tmp_path / "v.db"
    files = _files()
    sites, stats = resolve_calls(files)
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), fcall_sites=sites, call_resolution=stats)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT s.func_name, v.callee, df.file_path, d.start_line, v.platform FROM fcall_candidates v "
            "JOIN function_data s ON s.id = v.src_func_id JOIN function_data d ON d.id = v.dst_func_id "
            "JOIN file_data df ON df.id = v.dst_file_id ORDER BY df.file_path"
        ).fetchall()
        steps = conn.execute("SELECT callee, step, dst_func_id FROM fcall_data").fetchall()
    finally:
        conn.close()
    assert rows == [
        ("uv_run", "uv__io_poll", "src/unix/kqueue.c", 5, "bsd"),
        ("uv_run", "uv__io_poll", "src/unix/linux.c", 3, "linux"),
        ("uv_run", "uv__io_poll", "src/win/core.c", 7, "windows"),
    ]
    assert steps == [("uv__io_poll", "tie", None)]
