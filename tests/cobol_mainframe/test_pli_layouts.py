"""#3720: PL/I record layouts, the PL/I COMMAREA and its DTO.

pli_mapping is pinned against IBM's own worked example -- Enterprise PL/I for z/OS
Language Reference, "Example of structure mapping", Figure 12 "Offsets in final mapping
of structure A": every offset, the 80-byte length and the structure's offset of 4 from a
doubleword boundary -- then the same declaration UNALIGNED (no padding but the bits
after a bit string), and the element widths one by one.

A real scan of a small PL/I CICS estate then pins the engine side: the external
procedure's parameter as its entry point, the structure BASED on that pointer as the
program's COMMAREA (`program_interfaces` basis `parameter`), LIKE borrowing a structure's
members, a gap naming the %INCLUDE member the scan could not find, and the COMMAREA DTO
with PL/I's types in Java.
"""

import json
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.core.mainframe_boundary import _pli_entry_points
from gitgalaxy.tools.cobol_to_cobol import pli_mapping
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import java_type

IBM_EXAMPLE = """\
1 A {align}
2 B fixed bin(31)
2 C
3 D float decimal(14)
3 E
4 F entry
4 G
5 H character(2)
5 I float decimal(13)
4 J fixed binary(31,0)
3 K character(2)
3 L fixed binary(20,0)
2 M
3 N
4 P fixed binary(15)
4 Q character(5)
4 R float decimal(2)
3 S
4 T float decimal(15)
4 U bit(3)
4 V char(1)
3 W fixed bin(31)
2 X picture '$9V99'"""


def _tree(declaration: str):
    """(items in order, children map) of a `level name attributes` declaration, one per line."""
    items, stack, children = [], [], {}
    for line in declaration.splitlines():
        level, name, *rest = line.split(None, 2)
        text = rest[0] if rest else ""
        pic = text.split("'")[1] if text.startswith("picture") else None
        it = SimpleNamespace(name=name, level=int(level), usage=None if pic else text or None, pic=pic,
                             attributes="" if pic else text, occurs_max=None)  # fmt: skip
        if "(" in name:  # `X(3)`: a dimension
            it.name, dim = name.rstrip(")").split("(")
            it.occurs_max = int(dim)
        while stack and stack[-1].level >= it.level:
            stack.pop()
        if stack:
            children.setdefault(id(stack[-1]), []).append(it)
        stack.append(it)
        items.append(it)
    return items, children


def _offsets(declaration: str) -> tuple[dict, dict]:
    items, children = _tree(declaration)
    lay = pli_mapping.layout(items[0], children)
    return {it.name: lay[id(it)][0] for it in items}, {it.name: lay[id(it)][1] for it in items}


def test_ibm_structure_mapping_example_figure_12():
    items, children = _tree(IBM_EXAMPLE.format(align="aligned"))
    unit = pli_mapping.map_item(items[0], children)
    assert (unit.length // 8, unit.residue // 8) == (80, 4)  # 80 bytes, 4 past a doubleword
    bits, _ = _offsets(IBM_EXAMPLE.format(align="aligned"))
    assert {k: v // 8 for k, v in bits.items()} == {
        "A": 0, "B": 0, "C": 4, "D": 4, "E": 16, "F": 16, "G": 26, "H": 26, "I": 28, "J": 36, "K": 40, "L": 44,
        "M": 48, "N": 48, "P": 48, "Q": 50, "R": 56, "S": 60, "T": 60, "U": 68, "V": 69, "W": 72, "X": 76,
    }  # fmt: skip


def test_unaligned_packs_everything_but_the_bits_after_a_bit_string():
    bits, lengths = _offsets(IBM_EXAMPLE.format(align="unaligned"))
    assert lengths["A"] == 8 * 69  # 69 bytes: only U's BIT(3) leaves padding, 5 bits before V
    assert {k: v // 8 for k, v in bits.items() if k in "BCDEFGHIJKLMNPQRSTUVWX"} == {
        "B": 0, "C": 4, "D": 4, "E": 12, "F": 12, "G": 20, "H": 20, "I": 22, "J": 30, "K": 34, "L": 36, "M": 40,
        "N": 40, "P": 40, "Q": 42, "R": 47, "S": 51, "T": 51, "U": 59, "V": 60, "W": 61, "X": 65,
    }  # fmt: skip
    assert (bits["U"], lengths["U"]) == (59 * 8, 3)


def test_aligned_on_a_structure_aligns_its_bit_strings():
    _, lengths = _offsets(IBM_EXAMPLE.format(align="aligned"))
    assert lengths["U"] == 8  # IBM's example: U BIT(3) under ALIGNED A takes its byte (V at 69)
    bits, lengths = _offsets("1 R\n2 C bit(1)\n2 D bit(1)")  # no attribute: strings stay unaligned
    assert (bits["D"], lengths["R"]) == (1, 2)


def test_bit_strings_share_a_byte_and_arrays_stride_by_alignment():
    bits, lengths = _offsets("1 R\n2 A char(3)\n2 B fixed bin(31)\n2 C bit(1)\n2 D bit(1)\n2 E fixed dec(7,2)")
    assert {k: (v // 8, v % 8) for k, v in bits.items()} == {
        "R": (0, 0), "A": (0, 0), "B": (3, 0), "C": (7, 0), "D": (7, 1), "E": (8, 0)}  # fmt: skip
    assert lengths["R"] == 12 * 8
    _, lengths = _offsets("1 T\n2 X(3) fixed bin(15)\n2 Y(2) char(3) varying")
    assert (lengths["X"], lengths["Y"]) == (48, 80)  # 3 x 2; 2 x (3 + 2-byte prefix), halfword stride


@pytest.mark.parametrize(
    "usage, pic, attributes, aligned, expected",
    [
        ("CHAR(10)", None, "CHAR(10)", False, (80, 8)),
        ("CHAR(10) VARYING", None, "CHAR(10) VARYING", True, (96, 16)),
        ("BIT(12)", None, "BIT(12)", False, (12, 1)),
        ("BIT(12)", None, "BIT(12)", True, (16, 8)),
        ("FIXED DEC(7,2)", None, "FIXED DEC(7,2)", True, (32, 8)),
        ("FIXED", None, "FIXED", True, (24, 8)),  # FIXED alone is DECIMAL(5,0)
        ("FIXED BIN(15)", None, "FIXED BIN(15)", True, (16, 16)),
        ("FIXED BIN(31)", None, "FIXED BIN(31)", False, (32, 8)),
        ("FIXED BIN(63)", None, "FIXED BIN(63)", True, (64, 64)),
        ("FLOAT DEC(6)", None, "FLOAT DEC(6)", True, (32, 32)),
        ("DEC(16)", None, "DEC(16)", True, (64, 64)),  # DECIMAL without FIXED is FLOAT
        ("POINTER", None, "POINTER", True, (32, 32)),
        (None, "(5)9V99", "", False, (56, 8)),
        (None, "( 4)9", "", False, (32, 8)),
        (None, "S999V99CR", "", False, (64, 8)),
        ("AREA(100)", None, "AREA(100)", True, None),
    ],
)
def test_element_widths(usage, pic, attributes, aligned, expected):
    assert pli_mapping.element(usage, pic, attributes, aligned) == expected


def test_pli_java_types():
    def jt(cls, usage=None, pic=None):
        return java_type({"class": cls, "usage": usage, "pic": pic, "dialect": "pli"})

    assert [jt("P", "FIXED DEC(9)"), jt("P", "FIXED DEC(11)"), jt("P", "FIXED DEC(7,2)"), jt("P", "FIXED")] == [
        "Integer", "Long", "BigDecimal", "Integer"]  # fmt: skip
    assert [jt("B", "FIXED BIN(31)"), jt("B", "FIXED BIN(63)"), jt("F", "FLOAT DEC(6)")] == [
        "Integer", "Long", "Double"]  # fmt: skip
    assert [jt("9", pic="(11)9"), jt("9", pic="S(5)9V99"), jt("9", pic="ZZ9")] == ["Long", "BigDecimal", "String"]
    assert [jt("T", "BIT(1)"), jt("T", "BIT(8)"), jt("A", "POINTER"), jt("X", "CHAR(4)")] == [
        "Boolean", "String", "Long", "String"]  # fmt: skip
    assert java_type({"class": "9", "pic": "9(5)", "usage": None}) == "Integer"  # COBOL unchanged


def test_entry_point_is_the_external_procedure_and_its_parameters():
    src = " %M: PROC; %END;\n R001B1: PROC( COMMAREA_PEKER , X) OPTIONS (MAIN);\n I: PROC(Z); END I;\n END R001B1;"
    assert _pli_entry_points(src) == [{"kind": "PROCEDURE", "entry_name": "R001B1", "params": "COMMAREA_PEKER,X",
                                       "line": 2}]  # fmt: skip
    assert _pli_entry_points(" OTHERP: PROC OPTIONS(MAIN); END;")[0]["params"] is None
    assert _pli_entry_points(" DCL X CHAR(1);") == []


ACCTP = """\
 ACCTP: PROC(CA_PTR) OPTIONS(MAIN);
   DCL CA_PTR POINTER;
   DCL 1 ACCT_CA BASED(CA_PTR),
         2 ACCT_ID   CHAR(3),
         2 ACCT_SEQ  FIXED BIN(31),
         2 ACCT_ACT  BIT(1),
         2 ACCT_DEL  BIT(1),
         2 ACCT_BAL  FIXED DEC(7,2),
         2 ACCT_NO   PIC '(5)9';
   DCL 1 SAVED LIKE ACCT_CA;
   EXEC CICS WRITEQ TS QUEUE('ACCTQ') FROM(SAVED);
   EXEC CICS RETURN;
 END ACCTP;
"""

BATCHP = """\
 BATCHP: PROC(PARM_PTR) OPTIONS(MAIN);
   DCL PARM_PTR POINTER;
   DCL 1 PARM BASED(PARM_PTR),
         2 PARM_LEN  FIXED BIN(15),
         2 PARM_TEXT CHAR(8);
 END BATCHP;
"""

LOSTP = """\
 LOSTP: PROC(KOM_PTR) OPTIONS(MAIN);
   %INCLUDE KOMAREA;
   %INCLUDE LOCALINC;
   DCL KOM_PTR POINTER;
   EXEC CICS SYNCPOINT;
   EXEC CICS RETURN;
 END LOSTP;
"""

LOCALINC = """\
   DCL WS_FLAG CHAR(1);
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("pli_layouts")
    repo = base / "estate"
    for rel, text in {
        "src/ACCTP.pli": ACCTP,
        "src/LOSTP.pli": LOSTP,
        "src/BATCHP.pli": BATCHP,
        "inc/LOCALINC.pli": LOCALINC,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_the_structure_based_on_the_parameter_is_the_commarea(scanned):
    ir = load_galaxy_ir(scanned[1])
    acctp = ir.files["src/ACCTP.pli"]
    assert [(e.kind, e.entry_name, e.parameters) for e in acctp.entry_points] == [("PROCEDURE", "ACCTP", ["CA_PTR"])]
    area = ir.program_interfaces("pli")["src/ACCTP.pli"]["commarea"]
    assert (area["record"], area["basis"], area["bytes"], area["variable"]) == ("ACCT_CA", "parameter", 17, False)
    got = {f["name"]: (f["offset"], f["bytes"], f.get("bit_offset")) for f in area["fields"]}
    assert got == {"ACCT_ID": (0, 3, None), "ACCT_SEQ": (3, 4, None), "ACCT_ACT": (7, 1, 56),
                   "ACCT_DEL": (7, 1, 57), "ACCT_BAL": (8, 4, None), "ACCT_NO": (12, 5, None)}  # fmt: skip


def test_a_batch_main_procedure_parameter_is_not_a_commarea(scanned):
    ir = load_galaxy_ir(scanned[1])
    iface = ir.program_interfaces("pli")["src/BATCHP.pli"]
    assert iface["commarea"] is None and iface["commarea_gap"].startswith("no CICS evidence")
    parm = next(r for r in ir.files["src/BATCHP.pli"].records if r.name == "PARM")
    assert ir.record_layout(ir.files["src/BATCHP.pli"], parm)["bytes"] == 10  # still laid out


def test_like_borrows_the_members_of_its_base(scanned):
    ir = load_galaxy_ir(scanned[1])
    acctp = ir.files["src/ACCTP.pli"]
    saved = next(r for r in acctp.records if r.name == "SAVED")
    layout = ir.record_layout(acctp, saved)
    assert layout["bytes"] == 17 and [f["name"] for f in layout["fields"]][:2] == ["ACCT_ID", "ACCT_SEQ"]


def test_a_missing_include_is_named_in_the_gap(scanned):
    iface = load_galaxy_ir(scanned[1]).program_interfaces("pli")["src/LOSTP.pli"]
    assert iface["commarea"] is None
    assert "parameter KOM_PTR" in iface["commarea_gap"]
    assert "%INCLUDE members not in the repository: KOMAREA;" in iface["commarea_gap"]  # LOCALINC was found


def test_the_commarea_dto_carries_pli_types(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    (dto_path,) = java.rglob("dto/contract/*AcctCa.java")
    dto = dto_path.read_text(encoding="utf-8")
    assert "PL/I structure ACCT_CA (src/ACCTP.pli), 17 bytes" in dto
    assert "main procedure's parameter (ACCT_CA)" in dto
    for line in ("private String acctId;", "private Integer acctSeq;", "private Boolean acctAct;",
                 "private BigDecimal acctBal;", "private Integer acctNo;"):  # fmt: skip
        assert line in dto
    assert "// ACCT_DEL: BIT(1), offset 7 bit 1, 1 bits" in dto
    assert "// ACCT_NO: PIC '(5)9', offset 12, 5 bytes" in dto
    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    assert any(a["symbol"].endswith("#acctBal") for a in manifest["artifacts"])


# ---- #3728: an %INCLUDE inside a declaration ---------------------------------------
INCP = """\
 INCP: PROC OPTIONS(MAIN);
   DCL 1 TRAN,
         2 T_ID    CHAR(3),
         %INCLUDE TRANREST;
   DCL 1 LISTE BASED(P),
         3 LINJE (5),
         %INCLUDE LINJEINC;
   DCL 1 HALF,
         2 H_ID    CHAR(4),
         %INCLUDE GONE;
   DCL P POINTER;
 END INCP;
"""


@pytest.fixture(scope="module")
def included(tmp_path_factory):
    base = tmp_path_factory.mktemp("pli_dcl_include")
    repo = base / "estate"
    files = {
        "src/INCP.pli": INCP,
        "inc/TRANREST.pli": "   2 T_SEQ   FIXED BIN(31),\n   2 T_FLAG  CHAR(2);\n",
        "inc/LINJEINC.pli": "   5 L_KODE  CHAR(2),\n   5 L_BELOP PIC '(3)9';\n",
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_an_include_inside_a_declaration_is_spliced_in_where_it_stands(included):
    ef = included.files["src/INCP.pli"]
    tran = next(r for r in ef.records if r.name == "TRAN")
    layout = included.record_layout(ef, tran)
    got = [(f["name"], f["offset"], f["bytes"], f["file"]) for f in layout["fields"]]
    assert got == [("T_ID", 0, 3, "src/INCP.pli"), ("T_SEQ", 3, 4, "inc/TRANREST.pli"),
                   ("T_FLAG", 7, 2, "inc/TRANREST.pli")]  # fmt: skip
    assert (layout["bytes"], layout["unexpanded"], layout["copybooks"]) == (9, [], ["inc/TRANREST.pli"])


def test_a_fragment_nests_by_its_level_numbers(included):
    ef = included.files["src/INCP.pli"]
    layout = included.record_layout(ef, next(r for r in ef.records if r.name == "LISTE"))
    assert [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]] == [("L_KODE", 0, 2), ("L_BELOP", 2, 3)]
    assert layout["bytes"] == 25  # LINJE (5) of 5 bytes each


def test_a_missing_member_leaves_the_structure_unknown_and_named(included):
    ef = included.files["src/INCP.pli"]
    layout = included.record_layout(ef, next(r for r in ef.records if r.name == "HALF"))
    assert layout["bytes"] is None and layout["unexpanded"] == ["GONE"]  # not a 4-byte structure
