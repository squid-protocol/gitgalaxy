"""The proof harness's speedups keep what a proof compares: the Db2 database pool (a case per database), the
batched catalog reads and dumps, and the per-estate cache (a restored refactor is the refactor a fresh run makes)."""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_cache as ec  # noqa: E402
import equivalence_db2 as db2  # noqa: E402


# ---- the Db2 pool ------------------------------------------------------------------------------------------
@pytest.fixture
def fresh_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(db2, "_LOCK", None)
    monkeypatch.setattr(db2, "DATABASE", db2.DATABASE0)
    return tmp_path


def test_pool_names_and_size(monkeypatch):
    monkeypatch.setenv(db2.POOL_ENV, "3")
    assert db2.pool() == ["GGDB", "GGDB1", "GGDB2"]
    monkeypatch.setenv(db2.POOL_ENV, "0")
    assert db2.pool() == ["GGDB"]  # at least the container's own


def test_a_case_takes_the_first_free_database(monkeypatch, fresh_lock):
    monkeypatch.setenv(db2.POOL_ENV, "3")
    # GGDB keeps the lock file older checkouts take, so they and the pool never share a database
    assert db2._lock_path("GGDB") == fresh_lock / ".cache" / "gitgalaxy-db2.lock"
    db2._lock_path("GGDB").parent.mkdir(parents=True)
    held = db2._lock_path("GGDB").open("w")
    fcntl.flock(held, fcntl.LOCK_EX)  # another run holds GGDB
    try:
        db2.hold_lock()
        assert db2.DATABASE == "GGDB1"
        assert db2._lock_path("GGDB1").name == "gitgalaxy-db2-GGDB1.lock"
    finally:
        held.close()
        db2._LOCK.close()


def test_connections_name_the_held_database(monkeypatch):
    monkeypatch.setattr(db2, "DATABASE", "GGDB2")
    case = {"db2": {"qualifier": "IBMUSER"}}
    conn = db2.cobol_docker_args(case)[-1]
    assert "DATABASE=GGDB2;" in conn and "CURRENTSCHEMA=IBMUSER;" in conn
    assert "/GGDB2:currentSchema=IBMUSER;" in db2.java_props(case)


# ---- batched catalog reads and dumps ---------------------------------------------------------------------
def fake_clp(monkeypatch, answers):
    calls = []

    def clp(script, check=True):
        calls.append(script)
        for needle, out in answers:
            if needle in script:
                return 0, out
        return 0, ""

    monkeypatch.setattr(db2, "_clp", clp)
    monkeypatch.setattr(db2, "_META", {})
    return calls


CATALOG = """SELECT RTRIM(TABSCHEMA) || '|' || ...
IBMUSER|ACCOUNT|ACCOUNT_NUMBER|N
IBMUSER|ACCOUNT|ACCOUNT_TYPE|N
IBMUSER|PROCTRAN|PROCTRAN_ID|Y
IBMUSER|PROCTRAN|PROCTRAN_AMOUNT|N
"""


def test_columns_and_identity_come_from_one_catalog_read(monkeypatch):
    calls = fake_clp(monkeypatch, [("SYSCAT.COLUMNS", CATALOG)])
    case = {"db2": {"compare": ["IBMUSER.ACCOUNT", "IBMUSER.PROCTRAN"]}}
    script = db2.reset_script(case, Path("."))
    assert db2.columns("IBMUSER.ACCOUNT") == ["ACCOUNT_NUMBER", "ACCOUNT_TYPE"]
    assert db2.columns("ibmuser.proctran") == ["PROCTRAN_ID", "PROCTRAN_AMOUNT"]
    assert script == ("DELETE FROM IBMUSER.ACCOUNT;\nDELETE FROM IBMUSER.PROCTRAN;\n"
                      "ALTER TABLE IBMUSER.PROCTRAN ALTER COLUMN PROCTRAN_ID RESTART;\n")  # fmt: skip
    assert len(calls) == 1  # both tables, columns and identity, in one query
    with pytest.raises(RuntimeError, match="no table"):
        db2.columns("IBMUSER.NOPE")


def test_dumps_split_one_call_back_into_tables(monkeypatch):
    rows = ("SELECT COALESCE(...) FROM IBMUSER.ACCOUNT ORDER BY ACCOUNT_NUMBER, ACCOUNT_TYPE\n"
            "[0001]|[CURRENT ]   \n[0002]|NULL\n\nVALUES 'GG-DUMP-END'\nGG-DUMP-END\n"
            "SELECT COALESCE(...) FROM IBMUSER.PROCTRAN ORDER BY PROCTRAN_ID, PROCTRAN_AMOUNT\n"
            "\nVALUES 'GG-DUMP-END'\nGG-DUMP-END\n")  # fmt: skip
    calls = fake_clp(monkeypatch, [("SYSCAT.COLUMNS", CATALOG), ("GG-DUMP-END", rows)])
    out = db2.dumps({}, ["IBMUSER.ACCOUNT", "IBMUSER.PROCTRAN"])
    # the bytes dump() always wrote: the column names, then each row as CLP renders it, trailing blanks trimmed
    assert out["IBMUSER.ACCOUNT"] == b"ACCOUNT_NUMBER|ACCOUNT_TYPE\n[0001]|[CURRENT ]\n[0002]|NULL\n"
    assert out["IBMUSER.PROCTRAN"] == b"PROCTRAN_ID|PROCTRAN_AMOUNT\n\n"  # an empty table, as before
    assert len(calls) == 2  # the catalog once, then every table's query in one call
    assert (
        calls[1].count("ORDER BY") == 2
        and db2.dump_query("IBMUSER.ACCOUNT", ["ACCOUNT_NUMBER", "ACCOUNT_TYPE"]) in calls[1]
    )


# ---- the per-estate cache --------------------------------------------------------------------------------
def make_corpus(path: Path) -> Path:
    path.mkdir()
    (path / "PROG.cbl").write_text("       IDENTIFICATION DIVISION.\n", encoding="ascii")
    git = ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "c"], check=True)
    return path


def fake_refactor(corpus: Path, work: Path, scan: bool = False) -> Path:
    """A refactor's shape: the corpus copied into work, a dated clean room whose IR records that copy's path."""
    import shutil

    copy = work / corpus.name
    shutil.copytree(corpus, copy, ignore=shutil.ignore_patterns(".git"))
    clean = work / f"{corpus.name}_gitgalaxy_clean_20261002_120000"
    (clean / "04_ir_state_dumps").mkdir(parents=True)
    ir = {"metadata": {"path": str(copy / "PROG.cbl")}, "scan": scan}
    (clean / "04_ir_state_dumps" / "PROG_ir.json").write_text(json.dumps(ir), encoding="utf-8")
    (clean / "04_ir_state_dumps" / "data.db").write_bytes(b"SQLite\0no paths here")
    return clean


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes().replace(str(root).encode(), b"<WORK>")
            for p in sorted(root.rglob("*")) if p.is_file()}  # fmt: skip


def test_a_restored_refactor_is_the_fresh_one(monkeypatch, tmp_path):
    import java_target_matrix as jtm

    built = []
    monkeypatch.setattr(jtm, "refactor", lambda c, w, scan=False: built.append(w) or fake_refactor(c, w, scan))
    monkeypatch.setenv(ec.CACHE_ENV, str(tmp_path / "cache"))
    corpus = make_corpus(tmp_path / "estate")
    fake_refactor(corpus, tmp_path / "fresh", scan=True)
    for run in ("one", "two"):
        clean = ec.refactor(corpus, tmp_path / run, scan=True)
        assert clean.parent == tmp_path / run
        assert tree(tmp_path / run) == tree(tmp_path / "fresh")  # its own paths, byte for byte
    assert len(built) == 1  # built once, restored twice


def test_a_path_in_a_binary_file_falls_back_to_a_fresh_refactor(monkeypatch, tmp_path):
    import java_target_matrix as jtm

    def binary_path(corpus, work, scan=False):
        clean = fake_refactor(corpus, work, scan)
        (clean / "04_ir_state_dumps" / "data.db").write_bytes(b"SQLite\0" + str(work).encode())
        return clean

    built = []
    monkeypatch.setattr(jtm, "refactor", lambda c, w, scan=False: built.append(w) or binary_path(c, w, scan))
    monkeypatch.setenv(ec.CACHE_ENV, str(tmp_path / "cache"))
    corpus = make_corpus(tmp_path / "estate")
    clean = ec.refactor(corpus, tmp_path / "run", scan=True)
    assert built[-1] == tmp_path / "run"  # refactored afresh in place, not a copy with a stale path
    assert (clean / "04_ir_state_dumps" / "data.db").read_bytes().endswith(str(tmp_path / "run").encode())


def test_the_key_follows_the_engine_the_corpus_and_the_environment(monkeypatch, tmp_path):
    corpus = make_corpus(tmp_path / "estate")
    k = ec.key("refactor", corpus)
    assert ec.key("refactor", corpus) == k
    (corpus / "PROG.cbl").write_text("changed\n", encoding="ascii")  # an uncommitted edit
    assert ec.key("refactor", corpus) != k
    k2 = ec.key("refactor", corpus)
    monkeypatch.setenv("GITGALAXY_SOMETHING", "1")
    assert ec.key("refactor", corpus) != k2
    monkeypatch.delenv("GITGALAXY_SOMETHING")
    monkeypatch.setattr(ec, "_ENGINE_HASH", "another engine")
    assert ec.key("refactor", corpus) != k2


def test_off_builds_every_time(monkeypatch, tmp_path):
    import java_target_matrix as jtm

    built = []
    monkeypatch.setattr(jtm, "refactor", lambda c, w, scan=False: built.append(w) or fake_refactor(c, w, scan))
    monkeypatch.setenv(ec.CACHE_ENV, "off")
    corpus = make_corpus(tmp_path / "estate")
    ec.refactor(corpus, tmp_path / "a", scan=True)
    ec.refactor(corpus, tmp_path / "b", scan=True)
    assert built == [tmp_path / "a", tmp_path / "b"]
