"""construct_map.py: paragraphs are tagged by construct, and lined up with the det port exactly and the model port by
evidence."""

from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "tools"), str(ROOT)]

import construct_map as cm  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det.stmt import Stmt  # noqa: E402


def test_exec_blocks_are_tagged_by_what_they_do():
    assert cm.exec_tag("EXEC CICS SEND MAP('COSGN0A') MAPSET('COSGN00') ERASE END-EXEC") == "cics-screen"
    assert cm.exec_tag("EXEC CICS RECEIVE MAP('X') END-EXEC") == "cics-screen"
    assert cm.exec_tag("EXEC CICS READ DATASET('ACCTDAT') INTO(A) RIDFLD(K) END-EXEC") == "cics-file"
    assert cm.exec_tag("EXEC CICS WRITEQ TS QUEUE('Q') FROM(A) END-EXEC") == "cics-queue"
    assert cm.exec_tag("EXEC CICS XCTL PROGRAM('COMEN01C') END-EXEC") == "cics-control"
    assert cm.exec_tag("EXEC SQL FETCH ACC-CURSOR INTO :A END-EXEC") == "db2-cursor"
    assert cm.exec_tag("EXEC SQL SELECT X INTO :X FROM T END-EXEC") == "db2-singleton"


def test_a_paragraph_is_its_dominant_construct():
    move = Stmt("MOVE", 1, "MOVE A TO B")
    tags = cm.tag_paragraph([move] * 6 + [Stmt("IF", 2, "IF A = 1")], set())
    assert tags == {"record-move": 6, "if": 1} and cm.dominant(tags) == "record-move"
    # an OPEN with its file-status IFs is a file-io paragraph: one I/O statement outweighs two IFs
    opened = [Stmt("OPEN", 1, "OPEN INPUT F"), Stmt("IF", 2, "IF FS = '00'"), Stmt("IF", 3, "IF FS = '10'")]
    assert cm.dominant(cm.tag_paragraph(opened, set())) == "file-io"
    # an IF on an 88-level name, and SET ... TO TRUE, are 88-level tests
    tags = cm.tag_paragraph([Stmt("IF", 1, "IF ERR-FLG-ON"), Stmt("SET-TRUE", 2, "SET ERR-FLG-ON TO TRUE")],
                            {"ERR-FLG-ON"})  # fmt: skip
    assert tags["88-level"] == 2
    nested = Stmt("IF", 1, "IF A", body=[Stmt("IF", 2, "IF B")])
    assert cm.tag_paragraph([nested], set()) == {"if": 1, "nested-if": 1}
    assert cm.dominant(collections.Counter()) == "trivial"


DET = """
    /** 1000-SEND-MAP. */
    private int p3() {
        // EXEC CICS SEND MAP
        if (x) {
            y("}");
        }
        return -1;
    }

    /** 1000-EXIT. */
    private int p4() {
        return -1;
    }
"""


def test_det_methods_come_from_the_emitter_javadoc_and_spans_match_braces():
    assert cm.det_methods(DET) == {"1000-SEND-MAP": "p3", "1000-EXIT": "p4"}
    lines = DET.splitlines()
    start = next(i for i, ln in enumerate(lines, 1) if "p3()" in ln)
    assert cm.method_span(lines, start) == (start, start + 6)  # the "}" in a string does not close it


MODEL = """
    // 9000-READ-ACCT: 9200-GETCARDXREF-BYACCT, 9300-GETACCTDATA-BYACCT
    private void readAcct(CicsTask task) {
        // 9200-GETCARDXREF-BYACCT
        a();
    }

    private void sendMap(CicsTask task) {
        // 1400-SEND-SCREEN
        b();
    }
"""


def test_model_methods_are_matched_by_name_then_comments():
    rows = [{"func_name": "readAcct", "start_line": 3}, {"func_name": "sendMap", "start_line": 8}]
    names = ["9000-READ-ACCT", "9200-GETCARDXREF-BYACCT", "9300-GETACCTDATA-BYACCT", "1400-SEND-SCREEN", "A010"]
    got = cm.model_alignment(MODEL, rows, names)
    assert got["9000-READ-ACCT"] == ("readAcct", "high")  # the name, without its number
    assert got["9200-GETCARDXREF-BYACCT"] == ("readAcct", "medium")  # named in the comment before the method
    assert got["9300-GETACCTDATA-BYACCT"] == ("readAcct", "medium")
    assert got["1400-SEND-SCREEN"] == ("sendMap", "low")  # only a comment inside the method
    assert "A010" not in got


def test_idioms_and_det_parts():
    text = "switch (x) { }\nOptional<A> a = repo.findById(k);\nreturn a; return b;\nString s = fit(t, 8);"
    assert {"switch", "optional-stream", "repository", "early-return", "string-helpers"} <= cm.idioms(text)
    assert "typed-accessors" not in cm.idioms("a.getB();")  # one accessor is not the idiom
    rows = [{"func_name": n, "loc": 10} for n in ("p0", "fields0", "in_Commarea", "runTask", "perform", "zz")]
    assert cm.det_parts(rows, {"p0"}) == {"paragraph methods": 10, "storage field declarations": 10,
                                          "DTO bridges (COMMAREA / record objects to storage)": 10,
                                          "entry points (task, batch, link)": 10, "PERFORM / GO TO dispatch": 10,
                                          "other helpers": 10}  # fmt: skip
