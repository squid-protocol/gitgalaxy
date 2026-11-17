# ruff: noqa: S101
"""#8529: the brief's reach (16) and library (17) sections, read from the finished scan database.

Builds a tiny scan database with the columns `gitgalaxy reach` and `gitgalaxy libsurface` read, then renders the brief through the real
`_build_markdown` and through `generate_artifacts`, so the new `scan_db` argument's wiring is held, not just the two helpers."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.recorders.llm_recorder import LLMRecorder

SUFFIX = "_galaxy_llm" + ".md"  # the recorder names its brief <target>_galaxy_llm.md
SESSION = {"target": "Repo", "git_audit": {"commit_hash": "x", "latest_commit_date": "2026-11-16T00:00:00Z"}}


@pytest.fixture
def recorder():
    schemas = {
        "RISK_SCHEMA": ["tech_debt"],
        "SIGNAL_SCHEMA": ["io"],
        "EXPOSURE_LABELS": {"tech_debt": "Tech Debt Exposure"},
    }
    with patch("gitgalaxy.recorders.llm_recorder.config.RECORDING_SCHEMAS", schemas):
        yield LLMRecorder()


def _scan_db(tmp_path):
    files = [  # id, path, language, functions, loc, imports
        (1, "src/tls.c", "c", 1, 100, ["openssl/ssl.h", "stdio.h", "tls.h", "ifaddrs.h", "gnu/libc-version.h"]),
        (2, "src/main.c", "c", 1, 40, ["tls.h"]),
        (3, "src/tls.h", "c", 0, 10, []),
        (4, "app/web.py", "python", 1, 30, ["requests", "os", "app.util"]),
        (5, "app/util.py", "python", 1, 20, []),
    ]
    db = tmp_path / "Repo_galaxy_master.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT, language TEXT, function_count INTEGER, total_loc INTEGER, raw_imports TEXT, repo_name TEXT);
        CREATE TABLE function_data(id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT, is_public INTEGER DEFAULT 0, loc INTEGER);
        CREATE TABLE fcall_data(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, src_func_name TEXT, callee TEXT, step TEXT,
            kind TEXT DEFAULT 'call', candidates INTEGER, dst_file_id INTEGER, dst_func_id INTEGER, dst_class_id INTEGER);
        CREATE TABLE fcall_external(id INTEGER PRIMARY KEY, src_file_id INTEGER, callee TEXT, callers INTEGER);
        INSERT INTO function_data(id, file_id, func_name, is_public) VALUES (10,1,'tls_init',1),(11,2,'main',0),(12,4,'handler',0),(13,5,'helper',1);
        INSERT INTO fcall_data(src_file_id, src_func_id, kind, candidates, dst_file_id, dst_func_id) VALUES (2,11,'call',1,1,10),(4,12,'call',1,5,13);
        INSERT INTO fcall_external(src_file_id, callee, callers) VALUES (1,'SSL_new',3),(1,'memcpy',9);
        """
    )
    for fid, path, lang, nfun, loc, imports in files:
        con.execute("INSERT INTO file_data VALUES (?,?,?,?,?,?,'r')", (fid, path, lang, nfun, loc, json.dumps(imports)))
    con.commit()
    con.close()
    return str(db)


def _brief(recorder, scan_db):
    return recorder._build_markdown([], [], {}, SESSION, {}, None, None, scan_db)


def test_the_sections_are_absent_without_a_scan_database(recorder):
    text = _brief(recorder, None)
    assert "## 16. REACH" not in text and "## 17. LIBRARIES" not in text


def test_reach_lists_the_most_called_files_and_the_most_included_headers(recorder, tmp_path):
    text = _brief(recorder, _scan_db(tmp_path))
    section = text[text.index("## 16. REACH") : text.index("## 17. LIBRARIES")]
    assert (
        "| `src/tls.c` | 1 | 1 | 0 |" in section and "| `app/util.py` | 1 | 1 | 0 |" in section
    )  # one caller file, one caller function
    assert "| `src/tls.h` | 2 |" in section  # included by tls.c and main.c, counted from the stored include strings
    assert "lower bounds" in section and "not whether the file is defective" in section


def test_libraries_list_the_table_and_imports_but_not_c_platform_headers(recorder, tmp_path):
    text = _brief(recorder, _scan_db(tmp_path))
    section = text[text.index("## 17. LIBRARIES") :].split("\n## ", 1)[0]
    assert (
        "| openssl | 1 | 4 | 1 |" in section
    )  # 1 include (openssl/ssl.h) + SSL_new's 3 callers = 4 sites, 1 API name (memcpy is not openssl's)
    assert "| requests | 1 | 1 | 0 |" in section  # a discovered Python import
    assert "ifaddrs" not in section and "gnu" not in section  # C includes that are not in the shipped table


def test_a_database_that_cannot_be_read_never_stops_the_brief(recorder, tmp_path):
    bad = tmp_path / "not_a_database.db"
    bad.write_text("this is not sqlite")
    empty = sqlite3.connect(tmp_path / "empty.db")
    empty.close()
    for path in (str(bad), str(tmp_path / "empty.db"), str(tmp_path / "missing.db")):
        text = _brief(recorder, path)
        assert "## 16. REACH" not in text and "## 17. LIBRARIES" not in text
        assert "ARCHITECTURAL_BRIEF" in text  # the rest of the brief is intact


def test_generate_artifacts_passes_the_database_through(recorder, tmp_path):
    recorder.generate_artifacts(
        parsed_files=[],
        unparsable_files=[],
        summary={},
        session_meta={"target": "T"},
        output_dir=str(tmp_path),
        scan_db=_scan_db(tmp_path),
    )
    text = (tmp_path / f"T{SUFFIX}").read_text(encoding="utf-8")
    assert "## 16. REACH" in text and "## 17. LIBRARIES" in text
    recorder.generate_artifacts(
        parsed_files=[], unparsable_files=[], summary={}, session_meta={"target": "U"}, output_dir=str(tmp_path)
    )
    assert "## 16. REACH" not in (tmp_path / f"U{SUFFIX}").read_text(encoding="utf-8")


def test_the_sections_come_after_call_resolution_and_before_the_appendix(recorder, tmp_path):
    text = _brief(recorder, _scan_db(tmp_path))
    assert text.index("## 16. REACH") < text.index("## 17. LIBRARIES") < text.index("## APPENDIX A.")
