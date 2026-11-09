"""#8075 -- no burned estate reads an EXEC SQL form the det Db2 path refuses.

`det.sql._REFUSED_VERBS` (register Q4) lists the forms with no burned reader: CONNECT, CALL, ALLOCATE, ASSOCIATE, DESCRIBE,
a dynamic PREPARE / EXECUTE and SET CURRENT. Modelling one waits for a burned program that reads it. This test is that
trigger: it scans the burned corpora (`estate4_draw.BURNED_NAMES`) and fails when a program reads one, so "nothing left to
model" is enforced, not stated. A SET that assigns a host variable (`SET :H = ...`) runs and is not a refused form.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))

CORPORA = Path(
    os.environ.get("GITGALAXY_MAINFRAME_CORPORA", Path(__file__).resolve().parents[2] / ".mainframe_corpora")
)
SOURCE_SUFFIXES = {".cbl", ".cob", ".cpy", ".pco", ".sqb", ".cobol"}
# the verb, after an optional fixed-format sequence number when the statement wraps onto the next line
_EXEC_SQL = re.compile(r"EXEC\s+SQL\s+(?:\d{6}\s+)?([A-Z]+)(\s+:)?", re.I)


def _burned_dirs():
    from estate4_draw import BURNED_NAMES

    if not CORPORA.is_dir():
        return []
    return sorted(d for d in CORPORA.iterdir() if d.is_dir() and d.name.lower() in BURNED_NAMES)


def _verbs(text):
    # fixed-format comment lines (column 7 `*` or `/`) are prose, not statements
    code = "\n".join(ln for ln in text.split("\n") if ln[6:7] not in ("*", "/"))
    for m in _EXEC_SQL.finditer(code):
        yield m.group(1).upper(), bool(m.group(2))


def test_the_verb_scan_reads_wrapped_assigning_and_commented_statements():
    text = "       EXEC SQL\n035500    SELECT A\n       EXEC SQL SET :H = X\n      * EXEC SQL CONNECT TO X\n"
    assert list(_verbs(text)) == [("SELECT", False), ("SET", True)]


@pytest.mark.parametrize("estate", _burned_dirs() or [None], ids=lambda d: d.name if d else "no-corpora")
def test_no_burned_program_reads_a_refused_sql_form(estate):
    if estate is None:
        pytest.skip("no mainframe corpora checkout")
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.tools.cobol_to_java.det.sql import _REFUSED_VERBS

    read = []
    for p in estate.rglob("*"):
        if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES:
            for verb, assigns in _verbs(read_source(p).text):
                if verb in _REFUSED_VERBS and not (verb == "SET" and assigns):
                    read.append(f"{p.relative_to(estate)}: {verb}")
    assert not read, "a burned program reads a refused EXEC SQL form; model it (register Q4):\n" + "\n".join(read)
