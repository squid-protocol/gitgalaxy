"""Estate 4, IBM DBB MortgageApplication: the translator, harness and IR fixes onboarding it needed.

- the IR expands a COPY that follows a copied elementary root inside its copybook (EPSMTCOM: `10 PROCESS-INDICATOR`
  then `COPY EPSMTINP.` / `COPY EPSMTOUT.`), so the generated COMMAREA DTO is the whole record, not one byte;
- the harness supplies the period IBM's compiler assumes after a PROGRAM-ID name (EPSNBRVL), stages a lower-case
  copybook under its member name, and a CALL case may pass a group USING item (a contract DTO on the Java side, its
  argument given as text or as field values);
- a CICS task with no COMMAREA that MOVEs DFHCOMMAREA anyway: the fields it copies from nowhere are undefined
  (oracle_assumptions.md X12).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_call as ecall  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. MORTPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  W-COMMUNICATION-AREA.
           COPY MORTCOM.
       PROCEDURE DIVISION.
           MOVE 'X' TO PROCESS-INDICATOR OF W-COMMUNICATION-AREA
           GOBACK.
"""
MORTCOM = """          10  PROCESS-INDICATOR               PIC X.
          COPY MORTINP.
          COPY MORTOUT.
"""
MORTINP = """          10 IN-AMOUNT                PIC S9(9)V99 COMP.
          10 IN-IND                   PIC X.
"""
MORTOUT = """          10 OUT-PAYMENT              PIC S9(7)V99 COMP.
          10 OUT-ERRMSG               PIC X(10).
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("estate4")
    repo = base / "mort"
    files = {"cobol/mortpgm.cbl": PROGRAM, "copybook/mortcom.cpy": MORTCOM, "copybook/mortinp.cpy": MORTINP,
             "copybook/mortout.cpy": MORTOUT}  # fmt: skip
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_a_copy_after_a_copied_elementary_root_expands_as_its_siblings(scanned):
    ir = load_galaxy_ir(scanned)
    prog = ir.files["cobol/mortpgm.cbl"]
    area = next(i for i in prog.data_items if i.name == "W-COMMUNICATION-AREA")
    layout = ir.record_layout(prog, area)
    names = [f["name"] for f in layout["fields"]]
    assert names == ["PROCESS-INDICATOR", "IN-AMOUNT", "IN-IND", "OUT-PAYMENT", "OUT-ERRMSG"]
    assert layout["bytes"] == 1 + 8 + 1 + 4 + 10


def test_a_program_id_without_its_period_gets_the_one_ibm_assumes():
    src = "       ID DIVISION.\n       PROGRAM-ID. EPSNBRVL\n       ENVIRONMENT DIVISION.\n       PROGRAM-ID. OK.\n"
    out = common.ibm_assumed_periods(src).split("\n")
    assert out[1] == "       PROGRAM-ID. EPSNBRVL." and out[3] == "       PROGRAM-ID. OK."


def test_a_lower_case_copybook_is_staged_under_its_member_name(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "copybook").mkdir(parents=True)
    (corpus / "copybook" / "epsnbrpm.cpy").write_text("       01 A PIC X.\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    common.stage_copybooks({"copy_dirs": ["copybook"]}, corpus, src)
    assert sorted(p.name for p in src.iterdir()) == ["EPSNBRPM.cpy", "epsnbrpm.cpy"]


def _undefined(commarea, cobol_value):
    cev = [{"event": "RETURN", "commarea": {"RETCODE": cobol_value, "IND": "3"}}]
    jev = [{"event": "RETURN", "commarea": {"RETCODE": 0, "IND": "3"}}]
    n = [0]
    c, j = ec.mask_absent_commarea({"commarea": commarea}, cev, jev, n)
    return c, j, n[0]


def test_a_field_copied_from_an_absent_commarea_is_left_out_and_counted():
    c, j, n = _undefined(None, "<invalid b'\\x00\\x00\\x00\\x00'>")
    assert c == j == [{"event": "RETURN", "commarea": {"IND": "3"}}] and n == 1


def test_the_undefined_rule_needs_no_commarea_and_all_low_values():
    _, _, n = _undefined({"IND": "3"}, "<invalid b'\\x00\\x00\\x00\\x00'>")  # the task had a COMMAREA
    assert n == 0
    c, _, n = _undefined(None, "<invalid b'\\x00\\x40\\x00\\x00'>")  # not all LOW-VALUES: compared as usual
    assert n == 0 and c[0]["commarea"]["RETCODE"].startswith("<invalid")


def _call_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / "cpy").mkdir(parents=True)
    (corpus / "cpy" / "parm.cpy").write_text(
        "       01  PARM-AREA.\n           03 P-AMOUNT    PIC S9(9)V99 COMP.\n           03 P-IND       PIC X.\n",
        encoding="utf-8",
    )
    case = {"program": "PGM", "name": "t", "copy_dirs": ["cpy"],
            "using": [{"name": "PARM-AREA", "size": 9, "record": {"copybook": "cpy/parm.cpy", "name": "PARM-AREA"}}],
            "calls": [{"name": "c", "args": [{"P-AMOUNT": "1.50", "P-IND": "Y"}]}]}  # fmt: skip
    return corpus, case


def test_a_group_item_given_as_field_values_is_set_as_its_bytes(tmp_path):
    corpus, case = _call_corpus(tmp_path)
    b = ecall.arg_bytes(case, corpus, case["using"][0], case["calls"][0]["args"][0])
    assert b == (150).to_bytes(8, "big", signed=True) + b"Y"
    driver = ecall.cobol_driver(case, corpus)
    assert "MOVE X'000000000000009659' TO A0(1:9)" in driver  # up to 16 bytes per MOVE


def test_a_dto_is_read_from_its_offset_comments(tmp_path):
    root = tmp_path / "java"
    d = root / "com" / "x" / "dto" / "contract"
    d.mkdir(parents=True)
    (d / "ParmArea.java").write_text(
        "public class ParmArea {\n"
        "    // P-AMOUNT: PIC S9(9)V99 COMP, offset 0, 8 bytes (cpy/parm.cpy)\n    private BigDecimal pAmount;\n"
        "    // P-IND: PIC X, offset 8, 1 bytes (cpy/parm.cpy)\n    private String pInd;\n}\n",
        encoding="utf-8",
    )
    assert ecall.dto_properties(root, "ParmArea") == {
        "P-AMOUNT": ("pAmount", "BigDecimal"),
        "P-IND": ("pInd", "String"),
    }


def test_the_dto_test_imports_cobolref_only_when_a_text_item_needs_it():
    case = {"program": "PGM", "name": "t", "clock": "2026/10/03 10:30:15.00",
            "using": [{"name": "A", "size": 1, "record": {}}], "calls": []}  # fmt: skip
    dto_only = ecall.java_test_dto(case, ["ParmArea"])
    assert "call.CobolRef" not in dto_only and "treeToValue(c.get(0), ParmArea.class)" in dto_only
    assert "call.CobolRef" in ecall.java_test_dto(case, ["CobolRef<String>"])
