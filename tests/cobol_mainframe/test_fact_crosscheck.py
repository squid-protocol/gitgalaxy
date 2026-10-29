"""The engine-vs-translator fact cross-check (#4273): tests/tools/fact_crosscheck.py and
tests/tools/referees/translator_adapter.py.

No corpus is scanned here (the Fact Cross-check workflow does that); these tests pin the comparison
rules, the gate, the committed ledger's integrity, and the translator adapter on a toy program; #5649's
record_layout tests scan one toy repository.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
for p in (str(TOOLS), str(TOOLS / "referees")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fact_crosscheck as X
import translator_adapter as TA

from gitgalaxy.core.copy_libraries import STAND_IN_DIR, stand_in_registers, stand_in_text
from gitgalaxy.standards.mq import LENGTHS, STAND_INS
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import ZOS_POINTER_BYTES, load_galaxy_ir
from scan_server import scan_to_db
from gitgalaxy.tools.cobol_to_java.det.cics import POINTER_BYTES


def _doc(source: str, files: dict) -> dict:
    return {
        "schema": "referee-facts/1",
        "source": source,
        "channels": list(X.COMPARED) + ["program_ids"],
        "files": files,
    }


def _file(facts: dict, status: str = "ok", failed: list | None = None, error: str | None = None) -> dict:
    return {"status": status, "error": error, "failed": failed or [], "facts": {"program_ids": ["P"], **facts}}


def _key(files: dict) -> dict:
    return {"files": files}


# ------------------------------------------------------------------------------
# compare
# ------------------------------------------------------------------------------
def test_compare_lists_each_side_only_value_with_an_id() -> None:
    eng = _doc("engine", {"A.cbl": _file({"units": ["P1", "P2"], "edges": ["P1 -> PERFORM P2"]})})
    tr = _doc("translator", {"A.cbl": _file({"units": ["P1", "P3"], "edges": ["P1 -> PERFORM P2"]})})
    res = X.compare("toy", eng, tr, _key({}), set())
    ids = sorted(d["id"] for d in res["disagreements"])
    assert ids == ["toy :: units | A.cbl | engine | P2", "toy :: units | A.cbl | translator | P3"]
    assert res["stats"]["units"]["both"] == 1 and res["stats"]["edges"]["both"] == 1


def test_a_refused_division_is_one_status_disagreement_not_a_flood() -> None:
    eng = _doc("engine", {"A.cbl": _file({"units": ["P1"], "data_items": ["L5 01 X"], "pic": ["L5 X X"]})})
    tr = _doc("translator", {"A.cbl": _file({"units": ["P1"]}, "partial", ["data"], "layout: LayoutError: x")})
    res = X.compare("toy", eng, tr, _key({}), set())
    assert [(d["channel"], d["only"]) for d in res["disagreements"]] == [("status", "engine")]
    assert "data_items" not in {d["channel"] for d in res["disagreements"]}
    assert res["stats"]["units"]["both"] == 1


def test_a_program_refused_whole_compares_no_copy_channels() -> None:
    eng = _doc("engine", {"A.cbl": _file({"copybooks": ["X"], "copy_resolution": ["X -> c/X.cpy"]})})
    tr = _doc("translator", {"A.cbl": _file({}, "fail", ["data", "procedure"], "layout: ...; procedure: ...")})
    res = X.compare("toy", eng, tr, _key({}), set())
    assert {d["channel"] for d in res["disagreements"]} == {"status"}


def test_cics_commands_compare_only_the_verbs_the_key_censuses() -> None:
    key = _key({"A.cbl": {"facts": {"program_ids": ["P"], "cics_commands": ["L9 READ"]}}})
    eng = _doc("engine", {"A.cbl": _file({"cics_commands": ["L9 READ"]})})
    tr = _doc("translator", {"A.cbl": _file({"cics_commands": ["L9 READ", "L12 ASKTIME"]})})
    res = X.compare("toy", eng, tr, key, {"A.cbl"})
    assert res["disagreements"] == []
    assert res["stats"]["cics_commands"]["engine_tp"] == 1 and res["stats"]["cics_commands"]["translator_tp"] == 1


def test_offsets_are_scored_against_the_key_on_records_all_three_lay_out() -> None:
    key = _key({"A.cbl": {"facts": {"program_ids": ["P"], "offsets": ["R (record) +4", "R/F @0+4", "K (record) +2"]}}})
    eng = _doc("engine", {"A.cbl": _file({"offsets": ["R (record) +4", "R/F @0+4", "S (record) +1"]})})
    tr = _doc("translator", {"A.cbl": _file({"offsets": ["R (record) +8", "R/F @0+8", "S (record) +1"]})})
    s = X.compare("toy", eng, tr, key, {"A.cbl"})["stats"]["offsets"]
    assert (s["true"], s["engine_tp"], s["translator_tp"]) == (2, 2, 0)


# ------------------------------------------------------------------------------
# the gate and the ledger
# ------------------------------------------------------------------------------
def _ledger(disagreements: dict, causes: dict | None = None) -> dict:
    causes = causes if causes is not None else {"c": {"side": "engine", "issue": 1, "summary": "s"}}
    return {"schema": X.SCHEMA, "causes": causes, "disagreements": disagreements}


def test_gate_fails_on_new_and_lists_gone_without_failing() -> None:
    led = _ledger({"a": "c", "b": "c"})
    new, problems, gone = X.gate(led, [{"id": "a"}, {"id": "z"}])
    assert new == ["z"] and gone == ["b"] and problems == []


def test_check_is_a_two_way_ratchet() -> None:
    led = _ledger({"a": "c", "b": "c"})
    new, problems, gone = X.gate(led, [{"id": "a"}])
    fail = X.gate_failures(new, problems, gone)
    assert gone == ["b"] and len(fail) == 1 and "fact_crosscheck.py update" in fail[0]
    assert X.gate_failures(*X.gate(led, [{"id": "a"}, {"id": "b"}])) == []
    assert X.gate_failures(*X.gate(led, [{"id": "a"}, {"id": "b"}, {"id": "z"}]))[0].startswith("1 new")


def test_check_fails_on_a_stale_ledger_entry(monkeypatch, tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "ledger.json"
    X.save_ledger(
        _ledger({"toy :: units | A.cbl | engine | P2": "c", "toy :: units | A.cbl | engine | P9": "c"}), ledger
    )
    now = [{"id": "toy :: units | A.cbl | engine | P2"}]
    monkeypatch.setattr(X, "run_all", lambda *a, **k: {"corpora": {}, "disagreements": now, "seconds": {}})
    assert X.main(["check", "--no-crucible", "--ledger", str(ledger)]) == 1
    out = capsys.readouterr().out
    assert "GONE toy :: units | A.cbl | engine | P9" in out and "fact_crosscheck.py update" in out
    X.save_ledger(_ledger({"toy :: units | A.cbl | engine | P2": "c"}), ledger)
    assert X.main(["check", "--no-crucible", "--ledger", str(ledger)]) == 0


def test_update_without_corpus_drops_stale_entries(monkeypatch, tmp_path: Path) -> None:
    """#4472: a plain `update` lowers the ledger; a --corpus one only touches its own corpora."""
    ledger = tmp_path / "ledger.json"
    old = {
        "toy :: units | A.cbl | engine | P2": "c",
        "toy :: units | A.cbl | engine | P9": "c",
        "zoo :: units | B.cbl | engine | Q": "c",
    }
    now = [{"id": "toy :: units | A.cbl | engine | P2"}]
    monkeypatch.setattr(X, "run_all", lambda *a, **k: {"corpora": {}, "disagreements": now, "seconds": {}})
    X.save_ledger(_ledger(old), ledger)
    assert X.main(["update", "--no-crucible", "--corpus", "toy", "--ledger", str(ledger)]) == 0
    assert set(X.load_ledger(ledger)["disagreements"]) == {
        "toy :: units | A.cbl | engine | P2",
        "zoo :: units | B.cbl | engine | Q",
    }
    X.save_ledger(_ledger(old), ledger)
    assert X.main(["update", "--no-crucible", "--ledger", str(ledger)]) == 0
    assert set(X.load_ledger(ledger)["disagreements"]) == {"toy :: units | A.cbl | engine | P2"}


def test_engine_extras_lays_out_the_replaced_records_of_a_section_copy() -> None:
    """#4472: the copybook's own item sits at the translator's (file, line); the replaced record
    (ef.copied_items / ef.records, at the COPY line) is what the engine lays out."""
    from types import SimpleNamespace as NS

    def item(name: str, line: int) -> NS:
        return NS(name=name, level=1, line=line)

    own, replaced = item("CB-COMMAREA", 8), item("DFHCOMMAREA", 200)
    cb = NS(file_path="cb.cpy", data_items=[own], records=[own])
    ef = NS(file_path="p.cbl", data_items=[], copied_items=[replaced], records=[replaced], data_moves=[], copy_deps=[])
    laid: list[str] = []

    class IR:
        def _copy_files(self, f: object) -> list:
            return [cb] if f is ef else []

        def record_layout(self, owner: object, it: NS, ext: object, pointer_bytes: int | None = None) -> dict:
            laid.append(it.name)
            return {"fields": [{"pic": "X", "name": "F", "offset": 0, "bytes": 4}], "bytes": 4}

    rec = NS(name="DFHCOMMAREA", level=1)
    out = X.engine_extras(IR(), ef, [(rec, "cb.cpy", 8)])
    assert laid == ["DFHCOMMAREA"]
    assert out["offsets"] == {"DFHCOMMAREA/F @0+4", "DFHCOMMAREA (record) +4"}


def test_ledger_rejects_untriaged_unknown_and_incomplete_causes() -> None:
    led = _ledger({"a": None, "b": "nope", "c": "bad"}, {"bad": {"side": "neither", "issue": "x", "summary": ""}})
    errs = X.validate_ledger(led)
    assert any(e.startswith("UNTRIAGED a") for e in errs)
    assert any("unknown cause 'nope'" in e for e in errs)
    assert any("cause bad: side" in e for e in errs) and any("cause bad: no issue" in e for e in errs)


def test_committed_ledger_is_triaged_and_portable() -> None:
    led = X.load_ledger()
    assert X.validate_ledger(led) == []
    for did in led["disagreements"]:
        assert "/srv/" not in did and "/home/" not in did and "/tmp/" not in did, did
        corpus, rest = did.split(" :: ", 1)
        assert rest.count(" | ") >= 3, did
    sides = {c["side"] for c in led["causes"].values()}
    assert sides <= set(X.SIDES)


# ------------------------------------------------------------------------------
# canonical operands (engine text and translator AST meet here)
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "canon"),
    [
        ("'N'", "'N'"),
        ("ZERO", "ZEROES"),
        ("SPACES", "SPACES"),
        ("+1", "1"),
        ("5.50", "5.50"),
        ("0010", "10"),
        ("WS-X(1:2)", "WS-X"),
        ("A IN B", "A OF B"),
        ("LENGTH OF WS-REC", "LENGTH OF WS-REC"),
        ("FUNCTION CURRENT-DATE", "FUNCTION CURRENT-DATE"),
        ("X'0D'", "X'0D'"),
    ],
)
def test_canon_text_operand(text: str, canon: str) -> None:
    assert TA.canon_text_operand(text) == canon


def test_move_value_folds_case_like_the_key() -> None:
    assert TA.move_value(7, "'Abc'", "WS-X") == "L7 MOVE 'ABC' -> WS-X"


def test_census_kind() -> None:
    assert TA.census_kind(["READ"], {"FILE": "'F'"}) == "FILE"
    assert TA.census_kind(["SEND"], {"MAP": "'M'"}) == "MAP"
    assert TA.census_kind(["SEND"], {"TEXT": None}) is None
    assert TA.census_kind(["GET"], {"COUNTER": "X"}) is None
    assert TA.census_kind(["WEB", "PARSE"], {"URL": "U"}) is None
    assert TA.census_kind(["WEB", "OPEN"], {}) == "WEB"


# ------------------------------------------------------------------------------
# the translator adapter on a toy program
# ------------------------------------------------------------------------------
TOY = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TOY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC.
           05  WS-A               PIC X(4) VALUE 'AB'.
           05  WS-B               PIC S9(4) COMP.
           05  WS-P               POINTER.
       01  WS-T.
           COPY TOYCPY.
       PROCEDURE DIVISION.
           PERFORM P1 THRU P1-EXIT.
           GOBACK.
       P1.
           MOVE 'x' TO WS-A
           GO TO P1-EXIT.
       P1-EXIT.
           EXIT.
"""
TOYCPY = """\
           05  T-ONE              PIC 9(3).
           05  T-TWO              PIC X(2).
"""


def test_translator_adapter_on_a_toy_program(tmp_path: Path) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "TOY.cbl").write_text(TOY, encoding="latin-1")
    (tmp_path / "TOYCPY.cpy").write_text(TOYCPY, encoding="latin-1")
    r = TA.program_facts(tmp_path, tmp_path / "TOY.cbl", [tmp_path])
    f = r["facts"]
    assert r["status"] == "ok", r["error"]
    assert f["units"] == {"P1", "P1-EXIT"}
    assert f["unit_extents"] == {"(procedure division) L11-13", "P1 L14-16", "P1-EXIT L17-18"}
    # PERFORM A THRU B is one edge, to A (the key's shape)
    assert f["edges"] == {"(procedure division) -> PERFORM P1", "P1 -> GO TO P1-EXIT"}
    assert f["moves"] == {"L15 MOVE 'X' -> WS-A"}
    assert f["copybooks"] == {"TOYCPY"} and f["copy_resolution"] == {"TOYCPY -> TOYCPY.cpy"}
    assert "L7 WS-B COMP" in f["usage"] and "L6 WS-A = AB" in f["value"]
    # the translator's storage: POINTER is 8 bytes (GnuCOBOL x86-64), so WS-REC is 4 + 2 + 8
    assert {"WS-REC (record) +14", "WS-REC/WS-A @0+4", "WS-REC/WS-B @4+2", "WS-T/T-TWO @3+2"} <= f["offsets"]


BLL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-KEY                 PIC X(10).
       LINKAGE SECTION.
       01  PARMLIST.
           02  PARM-BLL               PIC S9(8) COMP.
       01  BLL-CELLS.
           02  FILLER                 PIC S9(8) COMP.
           02  REC-BLL                PIC S9(8) COMP.
       01  REC-AREA.
           02  REC-ID                 PIC X(10).
       PROCEDURE DIVISION.
       0000-MAINLINE SECTION.
           SERVICE RELOAD PARMLIST
           MOVE SPACES TO WS-KEY
           SERVICE RELOAD REC-AREA
           GOBACK.
"""


def test_a_bll_program_is_read_as_the_translator_lowers_it(tmp_path: Path) -> None:
    """#6960: SERVICE RELOAD is no statement of the grammar's; the translator lowers it first, so the referee must too
    (INVTRLD was refused as `does not parse`), while the layout stays the source's (cells keep their fullword width)."""
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "BLLPGM.cbl").write_text(BLL, encoding="latin-1")
    r = TA.program_facts(tmp_path, tmp_path / "BLLPGM.cbl", [tmp_path])
    f = r["facts"]
    assert r["status"] == "ok", r["error"]
    assert f["units"] == {"0000-MAINLINE"}
    assert f["moves"] == {"L17 MOVE SPACES -> WS-KEY"}
    assert "BLL-CELLS/REC-BLL @4+4" in f["offsets"]


def test_keyed_copybook_layouts_state_offsets_at_ibm_pointer_width(tmp_path: Path) -> None:
    """#5649: the `layouts` channel is the key's (IBM, POINTER 4 bytes), the `offsets` channel the translator's storage
    (8): a field after a POINTER sits 4 bytes later in `offsets` than in `layouts`, and a field before it does not move."""
    pytest.importorskip("tree_sitter_language_pack")
    cpy = tmp_path / "PTRCPY.cpy"
    cpy.write_text(
        "       01  PTR-REC.\n           05  P-A                PIC X(3).\n           05  P-PTR              POINTER.\n"
        "           05  P-B                PIC 9(2).\n",
        encoding="latin-1",
    )
    units, err = TA.copybook_layouts(cpy, [tmp_path])
    assert err is None
    assert units == {"PTR-REC/P-A @0+3", "PTR-REC/P-B @7+2"}


def test_translator_extent_stops_before_end_program(tmp_path: Path) -> None:
    """#4630: a lone program's last unit ends at its last code line, not at `END PROGRAM 'X'.`"""
    pytest.importorskip("tree_sitter_language_pack")
    src = TOY + "       END PROGRAM 'TOY'.\n"
    (tmp_path / "TOY.cbl").write_text(src, encoding="latin-1")
    (tmp_path / "TOYCPY.cpy").write_text(TOYCPY, encoding="latin-1")
    f = TA.program_facts(tmp_path, tmp_path / "TOY.cbl", [tmp_path])["facts"]
    assert f["unit_extents"] == {"(procedure division) L11-13", "P1 L14-16", "P1-EXIT L17-18"}


# ------------------------------------------------------------------------------
# #5649 slice 1: the engine lays records out the way the translator's storage does
# ------------------------------------------------------------------------------
# #5649 slice 1: the engine lays records out the way the translator needs them.
#
# 1. A POINTER's width is a parameter of GalaxyIR.record_layout: z/OS's 4 bytes (LP(32)) by default, the
#    translator's 8 (GnuCOBOL x86-64, oracle register C9) when its storage is what a layout is compared with.
#    IBM Enterprise COBOL, "USAGE POINTER phrase": a pointer data item is 4 bytes under LP(32); SYNC aligns
#    it on a fullword. Under SYNC the boundary follows the width.
# 2. A `COPY` of a system member the estate does not ship, where GitGalaxy writes a stand-in (CMQ*: register
#    W1, CEEIGZCT: L4), is laid out from that stand-in -- the same text the translator falls back on -- and
#    the layout says so (`stand_ins`). A copybook the repository holds always wins over a stand-in.
PTR_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRMQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC.
           05  WS-A               PIC X(4).
           05  WS-B               PIC S9(4) COMP.
           05  WS-P               POINTER.
           05  WS-C               PIC X.
       01  WS-SYNC.
           05  S-A                PIC X.
           05  S-P                POINTER SYNC.
       01  MQM-OD.
           COPY CMQODV.
       01  MQM-MD.
           COPY CMQMDV.
       01  OWN-GMO.
           COPY CMQGMOV.
       PROCEDURE DIVISION.
           GOBACK.
"""
# the estate's own CMQGMOV: shorter than the stand-in, and it must win
OWN_CMQGMOV = """\
           10  MQGMO.
               15  MQGMO-STRUCID      PIC X(4).
               15  MQGMO-VERSION      PIC S9(9) BINARY.
"""


@pytest.fixture(scope="module")
def ptr_ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("pointer_stand_ins_5649")
    (base / "repo").mkdir()
    (base / "repo" / "PTRMQ.cbl").write_text(PTR_PROGRAM, encoding="utf-8")
    (base / "repo" / "CMQGMOV.cpy").write_text(OWN_CMQGMOV, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(base / "repo", base / "scan"))


def _ptr_layout(ir, name, **kw):
    ef = ir.files["PTRMQ.cbl"]
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name), **kw)


def _ptr_fields(layout):
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_a_pointer_is_four_bytes_by_default_and_the_callers_width_when_given(ptr_ir):
    assert ZOS_POINTER_BYTES == 4 and POINTER_BYTES == 8
    assert _ptr_fields(_ptr_layout(ptr_ir, "WS-REC")) == [
        ("WS-A", 0, 4),
        ("WS-B", 4, 2),
        ("WS-P", 6, 4),
        ("WS-C", 10, 1),
    ]
    wide = _ptr_layout(ptr_ir, "WS-REC", pointer_bytes=POINTER_BYTES)
    assert _ptr_fields(wide) == [("WS-A", 0, 4), ("WS-B", 4, 2), ("WS-P", 6, 8), ("WS-C", 14, 1)]
    assert wide["bytes"] == 15


def test_a_synchronized_pointer_aligns_on_its_own_width(ptr_ir):
    assert _ptr_fields(_ptr_layout(ptr_ir, "WS-SYNC")) == [("S-A", 0, 1), ("S-P", 4, 4)]
    assert _ptr_fields(_ptr_layout(ptr_ir, "WS-SYNC", pointer_bytes=8)) == [("S-A", 0, 1), ("S-P", 8, 8)]


@pytest.mark.parametrize("record, member", [("MQM-OD", "CMQODV"), ("MQM-MD", "CMQMDV")])
def test_an_unshipped_mq_copybook_is_laid_out_from_its_stand_in(ptr_ir, record, member):
    layout = _ptr_layout(ptr_ir, record)
    assert layout["bytes"] == LENGTHS[member]  # IBM's documented version-1 length
    assert layout["unexpanded"] == [] and layout["stand_ins"] == [f"stand-in#{member}"]


def test_the_estates_own_copybook_wins_over_the_stand_in(ptr_ir):
    layout = _ptr_layout(ptr_ir, "OWN-GMO")
    assert layout["copybooks"] == ["CMQGMOV.cpy"] and "stand_ins" not in layout
    assert layout["bytes"] == 8


def test_a_record_with_no_stand_in_keeps_its_old_shape(ptr_ir):
    assert "stand_ins" not in _ptr_layout(ptr_ir, "WS-REC")


def test_every_registered_stand_in_is_shipped_and_comment_free():
    registers = stand_in_registers()
    assert set(STAND_INS) | {"CEEIGZCT"} == set(registers)
    for member in registers:
        assert (STAND_IN_DIR / f"{member}.cpy").is_file()
        assert "GitGalaxy-written" not in stand_in_text(member)  # the comment block is blanked
    assert stand_in_text("DFHAID") is None  # shipped for the translator, but not a register stand-in
