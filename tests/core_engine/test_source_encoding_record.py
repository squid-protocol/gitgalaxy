"""#3813: each file's decode record (source_encoding / source_decode) reaches the master DB, heals
onto a DB that predates it, survives a delta scan, and is surfaced in the LLM brief."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "EncRepo",
    "git_audit": {"commit_hash": "e3813", "latest_commit_date": "2026-09-27T00:00:00Z"},
}


def _files():
    base = {"lang_id": "cobol", "raw_imports": [], "classes": [], "functions": []}
    return [
        {**base, "path": "src/a.cbl", "source_encoding": "utf-8", "source_decode": "utf-8"},
        {**base, "path": "legacy/b.cbl", "source_encoding": "cp1252", "source_decode": "cp1252-fallback"},
        {**base, "path": "jp/c.cbl", "source_encoding": "shift_jis", "source_decode": "declared"},
        {**base, "path": "old/d.cbl"},  # rehydrated from a DB that predates the columns
    ]


def _rows(db):
    conn = sqlite3.connect(db)
    try:
        return {p: (e, h) for p, e, h in conn.execute("SELECT file_path, source_encoding, source_decode FROM file_data")}
    finally:
        conn.close()


def test_the_decode_record_persists_and_rehydrates(tmp_path):
    db = tmp_path / "m.db"
    RecordKeeper().record_mission(_files(), [], {}, SESSION, str(db))
    assert _rows(db) == {
        "src/a.cbl": ("utf-8", "utf-8"),
        "legacy/b.cbl": ("cp1252", "cp1252-fallback"),
        "jp/c.cbl": ("shift_jis", "declared"),
        "old/d.cbl": (None, None),  # unknown, not a guess
    }
    cache = StateRehydrator(str(db)).load_state("EncRepo")["ram_cache"]
    assert (cache["legacy/b.cbl"]["source_encoding"], cache["legacy/b.cbl"]["source_decode"]) == (
        "cp1252",
        "cp1252-fallback",
    )
    assert cache["old/d.cbl"]["source_encoding"] is None


def test_the_columns_heal_onto_a_db_that_predates_them(tmp_path):
    db = tmp_path / "old.db"
    RecordKeeper().record_mission(_files(), [], {}, SESSION, str(db))
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE file_data DROP COLUMN source_encoding")
    conn.execute("ALTER TABLE file_data DROP COLUMN source_decode")
    conn.commit()
    conn.close()
    # the rehydrator reads the old DB without the columns ...
    cache = StateRehydrator(str(db)).load_state("EncRepo")["ram_cache"]
    assert cache["src/a.cbl"]["source_encoding"] is None
    # ... and the next record heals them in
    session = {**SESSION, "git_audit": {"commit_hash": "e3814", "latest_commit_date": "2026-09-28T00:00:00Z"}}
    RecordKeeper().record_mission(_files(), [], {}, session, str(db))
    assert _rows(db)["legacy/b.cbl"] == ("cp1252", "cp1252-fallback")


def test_the_llm_brief_names_the_guessed_decodes():
    lines = LLMRecorder()._source_encoding_lines(_files())
    assert lines[0] == "## 4.1 SOURCE ENCODINGS"
    assert "1 file(s) had no BOM" in lines[1]
    assert "| cp1252 | cp1252-fallback | 1 |" in lines
    assert "| unknown | unknown | 1 |" in lines


def test_an_all_utf8_repo_gets_one_line():
    files = [{"source_encoding": "utf-8", "source_decode": "utf-8"}] * 3
    assert LLMRecorder()._source_encoding_lines(files) == [
        "## 4.1 SOURCE ENCODINGS",
        "All 3 parsed files are UTF-8.",
        "",
    ]
    assert LLMRecorder()._source_encoding_lines([]) == []
