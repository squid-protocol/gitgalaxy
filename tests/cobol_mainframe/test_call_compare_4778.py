"""#4778: a CALLed program's USING items, and a COMMAREA's trailing FILLER, are compared whole.

The follow-ups of #4765 (which made COMMAREA and file-record compares cover every occurrence by name and subscript):

- equivalence_call.compare_dto compared a group USING item only at the fields its DTO maps: the bytes no property
  names (a FILLER, a table's occurrences past the first) were never compared -- a port that changed one was proven.
  Now compare_item reads the item by its whole layout, every occurrence by subscript; a port that takes the items'
  bytes (a det port's withCallAreas) gives back what it left in them, compared as bytes are (every field, each
  FILLER as bytes); a port that gives back only its DTO has every named field compared (absent when unmapped), and
  the unnamed bytes it cannot carry are listed as not compared, with the reason.
- a det DTO whose record ends in a FILLER no property names (CBSA's CUSTCTRL DFHCOMMAREA, GenApp LGICVS01's) spans
  its declared record (Dto.size), as a table's (#4765) does; a COMMAREA's FILLER is compared as bytes when both
  sides are bytes, and declared not compared when the Java side is a DTO.
- a symbolic map with OCCURS is refused by name (screen_layout): screens are compared at a single-occurrence layout.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_call as call  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402

ITEM = """\
       01 PARM-REC.
          03 PARM-ID                 PIC X(2).
          03 PARM-N                  PIC 9(1).
          03 PARM-ROW OCCURS 3.
             05 PARM-KEY             PIC X(2).
             05 PARM-AMT             PIC 9(2).
          03 FILLER                  PIC X(4).
"""
SIZE = 2 + 1 + 3 * 4 + 4
# the DTO the call forge generates: an OCCURS group's fields once, no FILLER
PROPS = {"PARM-ID": ("parmId", "String"), "PARM-N": ("parmN", "Integer"), "PARM-KEY": ("parmKey", "String"),
         "PARM-AMT": ("parmAmt", "Integer")}  # fmt: skip


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "parm.cpy").write_text(ITEM, encoding="utf-8")
    return tmp_path


def _case():
    return {"name": "t", "using": [{"name": "PARM-REC", "size": SIZE, "record": {"copybook": "parm.cpy",
                                                                                 "name": "PARM-REC"}}]}  # fmt: skip


def _bytes(rows=(("AA", "01"), ("BB", "02"), ("CC", "03")), filler=b"    ") -> bytes:
    return b"ID3" + b"".join(k.encode() + a.encode() for k, a in rows) + filler


def _cmp(corpus, java_area=None, dto=None, cobol=None):
    u = _case()["using"][0]
    return call.compare_item(_case(), corpus, u, cobol if cobol is not None else _bytes(), dto, java_area, PROPS,
                             "latin-1")  # fmt: skip


# ---- the bytes a port gave back (withCallAreas) ------------------------------------------------------------------
def test_equal_bytes_are_equal(corpus):
    assert _cmp(corpus, java_area=_bytes()) == ([], [])


def test_a_filler_byte_the_port_changed_is_a_difference(corpus):
    """The unmapped byte: no DTO property names it; the caller's storage holds it all the same."""
    bad, skipped = _cmp(corpus, java_area=_bytes(filler=b"   X"))
    assert [d["field"] for d in bad] == [f"PARM-REC.FILLER@{SIZE - 4}"] and skipped == []


def test_the_third_occurrence_is_compared_by_its_subscript(corpus):
    bad, _ = _cmp(corpus, java_area=_bytes(rows=(("AA", "01"), ("BB", "02"), ("CC", "09"))))
    assert [(d["field"], d["cobol"], d["java"]) for d in bad] == [("PARM-REC.PARM-AMT(3)", "3", "9")]


# ---- a DTO only (a model port) -----------------------------------------------------------------------------------
def test_a_dto_is_compared_at_every_named_field_and_occurrence(corpus):
    """The DTO carries the first occurrence; the second and third are absent, compared -- never assumed equal."""
    dto = {"parmId": "ID", "parmN": 3, "parmKey": "AA", "parmAmt": 1}
    bad, skipped = _cmp(corpus, dto=dto)
    assert [d["field"] for d in bad] == ["PARM-REC.PARM-KEY(2)", "PARM-REC.PARM-AMT(2)", "PARM-REC.PARM-KEY(3)",
                                         "PARM-REC.PARM-AMT(3)"]  # fmt: skip
    assert skipped == [f"FILLER@{SIZE - 4}"]  # declared not compared: a DTO has no property for it


def test_a_dto_field_that_differs_is_a_difference(corpus):
    bad, _ = _cmp(corpus, dto={"parmId": "ZZ", "parmN": 3, "parmKey": "AA", "parmAmt": 1})
    assert "PARM-REC.PARM-ID" in [d["field"] for d in bad]


def test_compare_dto_reports_what_it_did_not_compare(corpus, tmp_path, monkeypatch):
    """A whole call through compare_dto: the DTO's FILLER is listed with its reason, never counted equal silently;
    with the bytes it is compared, and the changed byte fails the call."""
    monkeypatch.setattr(call, "dto_properties", lambda root, cls: PROPS)
    case = dict(_case(), calls=[{"name": "c1", "args": ["x"]}])
    cobol = _bytes() + b"+0000"
    dto = {"parmId": "ID", "parmN": 3, "parmKey": "AA", "parmAmt": 1}
    rows = [{"items": [dto], "rc": 0}]
    d = call.compare_dto(case, corpus, cobol, json.dumps(rows).encode(), tmp_path, ["ParmRec"])
    assert d["not_compared"] == {f"PARM-REC.FILLER@{SIZE - 4}": call.UNNAMED_IN_A_DTO}
    rows[0]["areas"] = [base64.b64encode(_bytes(filler=b"   X")).decode()]
    d = call.compare_dto(case, corpus, cobol, json.dumps(rows).encode(), tmp_path, ["ParmRec"])
    assert d["equal"] == 0 and "not_compared" not in d
    assert [f["field"] for f in d["diffs"][0]["fields"]] == [f"PARM-REC.FILLER@{SIZE - 4}"]


def test_the_java_test_passes_and_returns_the_bytes():
    case = {"name": "t", "program": "EPSNBRVL", "clock": "2026/10/03 10:30:15.00", "using": [{"name": "A", "size": 2}]}
    src = call.java_test_dto(case, ["ParmRec"], areas=True)
    assert "withCallAreas(areas);" in src and 'rec.put("areas", left);' in src and "areas.json" in src
    assert "withCallAreas" not in call.java_test_dto(case, ["ParmRec"])
    assert call.takes_areas("    public void withCallAreas(byte[]... areas) {")
    assert not call.takes_areas("    public int handleCall(ParmRec arg1) {")


# ---- a COMMAREA's FILLER ---------------------------------------------------------------------------------------
def test_a_commarea_filler_is_read_as_bytes_only_when_asked(corpus):
    fields = common.layout_fields(corpus, "parm.cpy", "PARM-REC", occurrences=True)
    assert "FILLER@15" not in ec.decode_record(_bytes(), fields, "latin-1", exact=True)
    assert ec.decode_record(_bytes(), fields, "latin-1", exact=True, unnamed=True)["FILLER@15"] == "20202020"


def test_a_commarea_filler_against_a_dto_is_declared_not_compared():
    cobol = [{"event": "COMMAREA", "commarea": {"A": "1", "FILLER@1": "20"}}]
    dto = [{"event": "COMMAREA", "commarea": {"A": "1"}, "commarea_dto": True}]
    d = ec.compare_events(cobol, dto)
    assert d["equal"] == 1 and d["not_compared"] == {"commarea.FILLER@1": ec.UNNAMED_IN_A_DTO}
    raw = [{"event": "COMMAREA", "commarea": {"A": "1", "FILLER@1": "58"}}]  # bytes: compared, and they differ
    d = ec.compare_events(cobol, raw)
    assert d["equal"] == 0 and d["diffs"][0]["fields"][0]["field"] == "commarea.FILLER@1"


def test_a_det_dto_with_a_trailing_filler_spans_its_record(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    dto = (
        "package com.x.dto.contract;\n/**\n * COBOL record DFHCOMMAREA (src/CUSTCTRL.cbl), 30 bytes, from GitGalaxy's"
        " verified skeleton.\n */\npublic class CtlDfhcommarea {\n\n"
        "    // CTL-EYE: PIC X(4), offset 0, 4 bytes (src/CUSTCTRL.cpy)\n    private String ctlEye;\n\n"
        "    // CTL-FLAG: PIC X, offset 4, 1 bytes (src/CUSTCTRL.cpy)\n    private String ctlFlag;\n}\n"
    )
    contract = tmp_path / "src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "CtlDfhcommarea.java").write_text(dto, encoding="utf-8")
    d = C.Generated(tmp_path, "public class CtlService {}\n").dto("CtlDfhcommarea")
    assert (d.record, d.occurs, d.extent, d.size) == (30, False, 5, 30)  # its 25 bytes of FILLER travel too


# ---- the det CALL entry ---------------------------------------------------------------------------------------
def test_a_det_call_entry_takes_the_items_bytes(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "CALLEE.cbl"
    src.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALLEE.\n       DATA DIVISION.\n"
                   "       LINKAGE SECTION.\n       01 A PIC X(10).\n       PROCEDURE DIVISION USING A.\n"
                   "           MOVE 'DONE' TO A.\n           GOBACK.\n", encoding="utf-8")  # fmt: skip
    stub = ("package com.x.service;\nimport com.x.call.CobolRef;\npublic class CalleeService {\n"
            "    public int handleCall(CobolRef<String> a) {\n        return 0;\n    }\n}\n")  # fmt: skip
    r = P.translate(src, [], stub, "com.x", None, tmp_path / "proj")
    assert not r.stats["holes"]
    assert "public void withCallAreas(byte[]... areas) {" in r.java
    assert call.takes_areas(r.java)
    body = r.java.split("public int handleCall(", 1)[1]
    assert "byte[][] areas = callAreas;" in body and body.count("System.arraycopy(") == 2


# ---- screens: a symbolic map with OCCURS is refused by name -------------------------------------------------------
MAP = """\
       01 MAPI.
          02 FILLER                  PIC X(12).
          02 ROWL                    COMP PIC S9(4).
          02 ROWF                    PIC X.
          02 ROWI                    PIC X(5).
"""
MAP_OCCURS = """\
       01 MAPI.
          02 FILLER                  PIC X(12).
          02 LINES OCCURS 3.
             03 ROWL                 COMP PIC S9(4).
             03 ROWF                 PIC X.
             03 ROWI                 PIC X(5).
"""


def test_a_symbolic_map_with_occurs_is_refused(tmp_path):
    (tmp_path / "map.cpy").write_text(MAP, encoding="utf-8")
    (tmp_path / "occ.cpy").write_text(MAP_OCCURS, encoding="utf-8")
    assert [f["name"] for f in ec.screen_layout(tmp_path, "map.cpy", "MAPI")] == ["FILLER", "ROWL", "ROWF", "ROWI"]
    with pytest.raises(ec.Unsupported, match="symbolic map with OCCURS"):
        ec.screen_layout(tmp_path, "occ.cpy", "MAPI")


def _corpora() -> Path | None:
    p = Path(
        os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or Path(__file__).resolve().parents[2] / ".mainframe_corpora"
    )
    return p if p.is_dir() else None


def test_no_case_map_has_occurs_today():
    """The screens' single-occurrence compare holds for every case's map; the first map with OCCURS fails here (and
    is refused by its proof) until the screen compare names every occurrence."""
    root = _corpora()
    if root is None:
        pytest.skip("no mainframe corpora")
    import equivalence as eq

    seen = 0
    for path in sorted(eq.CASES.glob("*/case.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        corpus = root / case.get("corpus", "")
        if not case.get("screens") or not corpus.is_dir():
            continue
        for name in case["screens"]:
            for side in ("input", "output"):
                ec.screen_fields(corpus, case, name, side)  # raises Unsupported on an OCCURS
                seen += 1
    if not seen:
        pytest.skip("no case's corpus is checked out")
