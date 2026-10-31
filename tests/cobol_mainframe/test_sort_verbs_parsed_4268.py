"""#4268 [c:336a82a2]: SORT, MERGE, RELEASE and RETURN each parse to their own statement (never a hole), in every
phrase combination IBM Enterprise COBOL 6.4 allows; a malformed SORT / MERGE stays a named hole. The statements run
against GnuCOBOL in test_det_programs.py; this pins the parse of the whole class. No burned program uses them."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from gitgalaxy.tools.cobol_to_java.det import stmt as S

HEAD = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01 A PIC X.", "PROCEDURE DIVISION.", "P1."]  # fmt: skip


def _stmts(body: list[str]) -> list:
    proc = S.parse(SRC.logical_lines(["       " + t for t in HEAD + body], "t.cbl"))
    return [s for p in proc.paragraphs for s in S.walk(p.body)]


def _one(body: list[str], kind: str):
    found = [s for s in _stmts(body) if s.kind == kind]
    assert len(found) == 1, [(s.kind, s.data.get("why")) for s in _stmts(body)]
    return found[0]


def test_sort_using_giving_with_every_phrase():
    s = _one(["SORT SF ON ASCENDING KEY K1 K2 ON DESCENDING KEY K3 WITH DUPLICATES IN ORDER",
              "COLLATING SEQUENCE IS ALPH USING F1 F2 GIVING G1 G2."], "SORT")  # fmt: skip
    d = s.data
    assert d["file"] == "SF" and d["using"] == ["F1", "F2"] and d["giving"] == ["G1", "G2"]
    assert [asc for _, asc in d["keys"]] == [True, True, False]
    assert d["duplicates"] is True and d["collating"] == "ALPH" and not d["table"]


def test_sort_input_and_output_procedure_with_thru():
    s = _one(["SORT SF ASCENDING KEY K1 INPUT PROCEDURE IS LOAD-A THRU LOAD-B",
              "OUTPUT PROCEDURE SHOW-A THROUGH SHOW-B."], "SORT")  # fmt: skip
    assert s.data["input"] and s.data["output"] and not s.data["using"] and not s.data["giving"]


@pytest.mark.parametrize(
    "tail,using,giving",
    [("USING F1 OUTPUT PROCEDURE SHOW-A.", True, False), ("INPUT PROCEDURE LOAD-A GIVING G1.", False, True)],
)
def test_sort_mixed_phrases(tail, using, giving):
    s = _one(["SORT SF ASCENDING KEY K1 " + tail], "SORT")
    assert bool(s.data["using"]) is using and bool(s.data["giving"]) is giving


def test_sort_of_a_table_is_format_2():
    s = _one(["SORT TBL ON ASCENDING KEY TK."], "SORT")
    assert s.data["table"] is True and s.data["keys"]


@pytest.mark.parametrize("tail", ["GIVING G1.", "OUTPUT PROCEDURE SHOW-A."])
def test_merge_with_two_using_files(tail):
    s = _one(["MERGE MF ON ASCENDING KEY K1 USING F1 F2 F3 " + tail], "MERGE")
    assert s.data["using"] == ["F1", "F2", "F3"]


def test_release_and_return_forms():
    r = _stmts(["RELEASE SR.", "RELEASE SR FROM WS-REC."])
    assert [s.kind for s in r] == ["RELEASE", "RELEASE"]
    assert r[0].data["from"] is None and r[1].data["from"] is not None
    ret = _stmts(["RETURN SF RECORD INTO WS-REC AT END MOVE 'Y' TO A",
            "NOT AT END MOVE 'N' TO A END-RETURN.",
                  "RETURN SF AT END MOVE 'Y' TO A."])  # fmt: skip
    rets = [s for s in ret if s.kind == "RETURN"]
    assert len(rets) == 2 and rets[0].data["into"] is not None and rets[1].data["into"] is None
    assert rets[0].data["file"] == "SF" and set(rets[0].phrases) == {"AT-END", "NOT-AT-END"}


@pytest.mark.parametrize(
    "body",
    [
        "MERGE MF ON ASCENDING KEY K1 USING F1 GIVING G1.",
        "MERGE MF ON ASCENDING KEY K1 USING F1 F2 WITH DUPLICATES IN ORDER GIVING G1.",
        "MERGE MF ON ASCENDING KEY K1 INPUT PROCEDURE LOAD-A USING F1 GIVING G1.",
        "SORT SF ASCENDING KEY USING F1 GIVING G1.",
        "SORT SF ASCENDING KEY K1 USING F1.",
        "SORT SF ASCENDING KEY K1 GIVING G1.",
    ],
)
def test_malformed_sort_or_merge_is_a_named_hole(body):
    holes = [s for s in _stmts([body]) if s.kind == "HOLE"]
    assert len(holes) == 1 and holes[0].data["why"]


def test_no_burned_program_uses_the_sort_verbs():
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("no mainframe corpora checkout")
    verb = re.compile(
        r"^.{6}[ ]+(?:SORT\s+[A-Z0-9-]+\s+(?:ON\s+|ASCENDING|DESCENDING)|MERGE\s+[A-Z0-9-]+\s+(?:ON\s+|ASCENDING)|RELEASE\s+[A-Z0-9-]+\s*(?:FROM|\.|$))",
        re.I | re.M,
    )
    hits = [
        str(p)
        for ext in ("cbl", "cob", "cobol")
        for p in Path(root).rglob("*." + ext)
        if verb.search(p.read_text(errors="replace"))
    ]
    assert hits == [], "a burned program now uses SORT / MERGE: add its equivalence case (#4268)"
