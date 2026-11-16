# ruff: noqa: S101, S603
"""`gitgalaxy reach`: caller counts from a finished scan database, header include counts, and the edge filters.

Builds a tiny scan database with the real `fcall_data` columns, so the SQL is held against the schema the engine writes."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from gitgalaxy.tools.sensors import reach

REPO = Path(__file__).resolve().parents[2]


def _make(tmp: Path) -> Path:
    for d, name, body in [
        ("a", "x.h", "int f(void);"),
        ("b", "x.h", "int g(void);"),
        ("a", "one.c", '#include "x.h"\nint f(void){return 1;}'),
        ("b", "two.c", '#include "x.h"\n#include <stdio.h>\nint g(void){return f();}'),
        ("b", "three.c", '#include "a/x.h"\nvoid h(void){g();}'),
    ]:
        (tmp / d).mkdir(exist_ok=True)
        (tmp / d / name).write_text(body)
    db = tmp / "s_galaxy_master.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT, language TEXT, function_count INTEGER);
        CREATE TABLE function_data(id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT, is_public INTEGER DEFAULT 0, loc INTEGER);
        CREATE TABLE fcall_data(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, src_func_name TEXT, callee TEXT,
            step TEXT, kind TEXT DEFAULT 'call', candidates INTEGER, dst_file_id INTEGER, dst_func_id INTEGER, dst_class_id INTEGER);
        CREATE TABLE fcall_candidates(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, callee TEXT, dst_file_id INTEGER, dst_func_id INTEGER, platform TEXT);
        CREATE TABLE fcall_external(id INTEGER PRIMARY KEY, src_file_id INTEGER, callee TEXT, callers INTEGER);
        INSERT INTO fcall_external(src_file_id,callee,callers) VALUES (3,'free',2),(5,'free',1),(2,'free',4);
        INSERT INTO file_data VALUES (1,'a/x.h','c',0),(2,'b/x.h','c',0),(3,'a/one.c','c',1),(4,'b/two.c','c',1),(5,'b/three.c','c',1),(6,'README','text',0);
        INSERT INTO function_data VALUES (10,3,'f',1,2),(11,4,'g',1,2),(12,5,'h',1,2);
        INSERT INTO fcall_candidates(src_file_id,src_func_id,callee,dst_file_id,dst_func_id) VALUES
            (5,12,'f',3,10),     -- three.c also possibly calls f in one.c, but already calls it: not a new possible caller
            (6,NULL,'g',4,11),   -- README ties across candidates incl. two.c: a possible caller of two.c
            (6,NULL,'g',2,NULL); -- a candidate with no function is still a file-level possibility, not counted twice
        INSERT INTO fcall_data(src_file_id,src_func_id,kind,candidates,dst_file_id,dst_func_id) VALUES
            (4,11,'call',1,3,10), (5,12,'call',1,4,11), (5,12,'call',1,3,10),
            (5,12,'call',NULL,NULL,NULL),          -- a tie: no destination
            (4,11,'call',2,3,10),                  -- ambiguous: two candidates, a guess
            (4,11,'reference',1,3,10),             -- a reference, not a call
            (3,NULL,'call',1,4,11);                -- top-level slice, no calling function
        """
    )
    con.commit()
    con.close()
    return db


def test_caller_counts_and_one_hop(tmp_path):
    out = reach.build(_make(tmp_path), tmp_path)
    rows = {r["path"]: r for r in out["rows"]}
    assert (
        rows["a/one.c"]["reach_files"] == 2
        and rows["a/one.c"]["caller_functions"] == 2
        and rows["a/one.c"]["one_hop_out"] == 1
    )
    # two.c is called by three.c (a function) and by one.c's top-level code (a file, but not a function)
    assert (
        rows["b/two.c"]["reach_files"] == 2
        and rows["b/two.c"]["caller_functions"] == 1
        and rows["b/two.c"]["one_hop_out"] == 0
    )
    assert out["public_functions"][0] == {"function": "f", "path": "a/one.c", "called_from_files": 2}


def test_edge_filters(tmp_path):
    out = reach.build(_make(tmp_path), tmp_path)
    assert (
        out["edges_counted"] == 4
    )  # three function calls plus the top-level one; the tie, the ambiguous edge and the reference are not counted
    assert out["edges_left_out"] == 2  # the tie and the ambiguous call (a reference is not a call edge at all)


def test_headers_resolve_by_path(tmp_path):
    rows = {r["path"]: r for r in reach.build(_make(tmp_path), tmp_path)["rows"]}
    assert rows["a/x.h"]["reach_files"] == 2 and rows["b/x.h"]["reach_files"] == 1  # same-named headers stay separate


def test_headers_need_src_and_unmeasured_is_explicit(tmp_path):
    out = reach.build(_make(tmp_path))
    reasons = {n["path"]: n["reason"] for n in out["not_measured"]}
    assert reasons["README"] == "no functions found"
    assert "needs --src" in reasons["a/x.h"]
    assert not [r for r in out["rows"] if r["kind"] == "header"]


def test_report_states_its_limits(tmp_path):
    text = reach.report(reach.build(_make(tmp_path), tmp_path))
    assert "lower bounds" in text and "left out" in text


def test_command_end_to_end(tmp_path):
    db = _make(tmp_path)
    out_json = tmp_path / "r.json"
    res = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "reach", str(db), "--src", str(tmp_path), "--json", str(out_json)],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "REACH" in res.stdout and json.loads(out_json.read_text())["files"] == 6
    missing = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "reach", str(tmp_path / "nope.db")],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert missing.returncode == 2


def test_database_is_opened_read_only(tmp_path):
    db = _make(tmp_path)
    before = db.read_bytes()
    reach.build(db, tmp_path)
    assert db.read_bytes() == before


def test_tied_calls_are_possible_callers_not_counted_ones(tmp_path):
    result = reach.build(_make(tmp_path), tmp_path)
    rows = {r["path"]: r for r in result["rows"]}
    assert (
        rows["b/two.c"]["possible_caller_files"] == 1 and rows["b/two.c"]["reach_files"] == 2
    )  # counted reach unchanged
    assert rows["a/one.c"]["possible_caller_files"] == 0  # three.c already counts
    assert "(+1 possible, tied calls)" in reach.report(result, all_roles=True)


def test_database_without_candidates_table(tmp_path):
    db = _make(tmp_path)
    con = sqlite3.connect(db)
    con.execute("DROP TABLE fcall_candidates")
    con.commit()
    con.close()
    rows = {r["path"]: r for r in reach.build(db, tmp_path)["rows"]}
    assert rows["b/two.c"]["possible_caller_files"] == 0


def test_scope_of_a_name_the_repository_does_not_define(tmp_path):
    out = reach.scope(_make(tmp_path), "free")
    assert out["files"] == 3 and out["callers"] == 7 and out["external_recorded"]
    assert [r["path"] for r in out["rows"]][0] == "b/x.h"  # most callers first
    assert not any(r["defined_in_repository"] for r in out["rows"])
    assert "external to the repository" in reach.report_scope(out)


def test_scope_of_a_name_the_repository_defines(tmp_path):
    out = reach.scope(_make(tmp_path), "f")
    assert {(r["path"], r["callers"]) for r in out["rows"]} == {("b/two.c", 1), ("b/three.c", 1)}
    assert all(r["defined_in_repository"] for r in out["rows"])


def test_scope_on_a_scan_without_the_external_table_says_so(tmp_path):
    db = _make(tmp_path)
    con = sqlite3.connect(db)
    con.execute("DROP TABLE fcall_external")
    con.commit()
    con.close()
    out = reach.scope(db, "free")
    assert out["rows"] == [] and not out["external_recorded"]
    assert "did not record external calls" in reach.report_scope(out)


def test_scope_from_the_command_line(tmp_path):
    res = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "reach", str(_make(tmp_path)), "--callee", "free"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert res.returncode == 0 and "SCOPE  free: called from 3 files" in res.stdout
