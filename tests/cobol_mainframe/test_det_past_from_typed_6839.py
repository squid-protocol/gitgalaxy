"""#6839 (row C, #5252): a CICS command that reads LENGTH bytes from FROM's first reads the items after FROM in its
record too. Under the typed translation (B3) an item held as a Java field never reaches those bytes, so every lifted
item such a read can span stays byte storage (GenApp LGSETUP: SEND TEXT FROM(WRITE-MSG-H) LENGTH(24) sent
WRITE-MSG-High as 0000000000)."""

import re
from pathlib import Path

import pytest

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PASTFROM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WRITE-MSG.
         03 WRITE-MSG-H            PIC X(14) VALUE 'HIGH CUSTOMER='.
         03 WRITE-MSG-HIGH         PIC 9(10).
       01  OTHER-NUM               PIC 9(10).
       PROCEDURE DIVISION.
           MOVE 50 TO WRITE-MSG-HIGH
           MOVE 7 TO OTHER-NUM
           EXEC CICS SEND TEXT FROM(WRITE-MSG-H)
                LENGTH(__LENGTH__)
           END-EXEC
           EXEC CICS RETURN END-EXEC.
"""


def _java(tmp_path: Path, length: str) -> str:
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "PASTFROM.cbl").write_text(PROGRAM.replace("__LENGTH__", length), encoding="ascii")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class PastfromService {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "PASTFROM.cbl", [], stub, "com.x", {}, tmp_path / "proj", typed=True)
    assert r.stats["holes"] == [], r.stats["holes"]
    return r.java


def _bytes(java: str, name: str) -> bool:
    """Whether the item is byte storage (a Field over its record), not a typed Java field."""
    return re.search(rf"Field f\d+_{name} = Field\.", java) is not None


def test_a_send_text_past_from_keeps_the_items_it_sends_as_bytes(tmp_path):
    java = _java(tmp_path, "24")
    assert "DetCics.withinRecord(" in java
    assert _bytes(java, "WRITE_MSG_HIGH")
    assert not _bytes(java, "OTHER_NUM")  # another record: the read does not reach it, so it stays typed


def test_a_send_text_within_from_leaves_the_next_item_typed(tmp_path):
    java = _java(tmp_path, "14")
    assert "DetCics.withinRecord(" not in java
    assert not _bytes(java, "WRITE_MSG_HIGH")
