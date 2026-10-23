"""#5649 slice 2: the translator lays its records out from the engine's layouts (GalaxyIR.record_layout), at its own
POINTER width, with a check mode that refuses where the two computations differ (det.engine_layout).

The toy estate scans once; each test parses the program's records with the translator and hands them to
EngineLayouts. At the translator's width (8, GnuCOBOL x86-64, oracle register C9) the two agree; at z/OS's 4 the
engine's numbers move every item after a POINTER, a REDEFINES overlay with its target and an OCCURS group's stride,
and check mode names the item."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import ZOS_POINTER_BYTES, load_galaxy_ir
from scan_server import scan_to_db
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det.cics import POINTER_BYTES
from gitgalaxy.tools.cobol_to_java.det.engine_layout import EngineLayouts, LayoutDisagrees, adopt
from gitgalaxy.tools.cobol_to_java.det.source import program_lines

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common  # noqa: E402 -- the shared engine_layouts helper (bare import: tests/ has no package)

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LAYTOY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC.
           05  WS-A               PIC X(4).
           05  WS-B               PIC S9(4) COMP.
           05  WS-P               POINTER.
           05  WS-C               PIC X.
       01  WS-R.
           05  R-P                POINTER.
           05  R-X                PIC X(4).
           05  R-ALT REDEFINES R-X.
               10  R-A            PIC X(2).
               10  R-B            PIC X(2).
           05  R-Z                PIC X.
       01  WS-T.
           05  T-E OCCURS 3.
               10  T-P            POINTER.
               10  T-X            PIC X.
           05  T-END              PIC X.
           COPY LAYCPY.
           COPY SYSREC.
       PROCEDURE DIVISION.
           GOBACK.
"""
LAYCPY = """\
       01  CP-REC.
           05  CP-P               POINTER.
           05  CP-N               PIC 9(3).
"""
# a system member outside the estate (the way DFHAID reaches a port): the engine reads no record there
SYSREC = """\
       01  SYS-REC.
           05  SYS-P              POINTER.
           05  SYS-N              PIC X(2).
"""


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("engine_layout_5649")
    repo, system = base / "repo", base / "system"
    repo.mkdir()
    system.mkdir()
    (repo / "LAYTOY.cbl").write_text(PROGRAM, encoding="utf-8")
    (repo / "LAYCPY.cpy").write_text(LAYCPY, encoding="utf-8")
    (system / "SYSREC.cpy").write_text(SYSREC, encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    return ir, repo, system


def _records(estate):
    _, repo, system = estate
    lines = program_lines(repo / "LAYTOY.cbl", [repo, system], None)
    return L.parse(lines), lines


def _at(recs, name):
    it = next(x for r in recs for x in r.walk() if x.name == name)
    return it.offset, it.size


def test_at_the_translators_width_every_estate_record_is_the_engines_and_agrees(estate):
    recs, lines = _records(estate)
    own = {x.name: (x.offset, x.size) for r in recs for x in r.walk()}
    lay = EngineLayouts.from_ir(estate[0], "LAYTOY.cbl", estate[1], mode="check")
    assert lay.pointer_bytes == POINTER_BYTES == 8
    lay.apply(recs, lines)
    assert lay.consumed == ["WS-REC", "WS-R", "WS-T", "CP-REC"]  # the copied record too
    assert lay.own == ["SYS-REC"]  # outside the estate: the translator's own layout
    assert {x.name: (x.offset, x.size) for r in recs for x in r.walk()} == own


def test_engine_mode_takes_the_engines_offsets_and_groups_follow(estate):
    recs, lines = _records(estate)
    lay = EngineLayouts.from_ir(estate[0], "LAYTOY.cbl", estate[1], "engine", ZOS_POINTER_BYTES)
    lay.apply(recs, lines)
    assert [_at(recs, n) for n in ("WS-P", "WS-C", "WS-REC")] == [(6, 4), (10, 1), (0, 11)]
    # the REDEFINES overlay sits on its moved target; its items move with it
    assert [_at(recs, n) for n in ("R-X", "R-ALT", "R-A", "R-B", "R-Z", "WS-R")] == [
        (4, 4), (4, 4), (4, 2), (6, 2), (8, 1), (0, 9)]  # fmt: skip
    # an OCCURS group's stride is its children's span
    assert [_at(recs, n) for n in ("T-E", "T-X", "T-END", "WS-T")] == [(0, 5), (4, 1), (15, 1), (0, 16)]
    assert _at(recs, "CP-N") == (4, 3)
    assert _at(recs, "SYS-N") == (8, 2)  # (not the engine's: unchanged)


def test_check_mode_refuses_where_the_two_differ_by_name(estate):
    recs, lines = _records(estate)
    lay = EngineLayouts.from_ir(estate[0], "LAYTOY.cbl", estate[1], "check", ZOS_POINTER_BYTES)
    with pytest.raises(LayoutDisagrees, match=r"LAYTOY\.cbl:5: 01 WS-REC: .*WS-P engine @6\+4, translator @6\+8"):
        lay.apply(recs, lines)


def test_a_record_the_engine_cannot_size_or_pair_refuses():
    rec = L.Item(1, "R", "WORKING-STORAGE", children=[L.Item(5, "A", "WORKING-STORAGE", pic="X(2)")])
    L.layout(rec)
    with pytest.raises(LayoutDisagrees, match="does not know the record's width"):
        adopt(rec, {"bytes": None, "fields": [], "unexpanded": ["MISSING"]}, "R")
    with pytest.raises(LayoutDisagrees, match="do not pair"):
        adopt(rec, {"bytes": 2, "fields": [{"name": "B", "offset": 0, "bytes": 2}]}, "R")


def test_an_unknown_mode_or_program_is_none_or_refused(estate):
    assert EngineLayouts.from_ir(estate[0], "NOPE.cbl", estate[1]) is None
    with pytest.raises(ValueError):
        EngineLayouts.from_ir(estate[0], "LAYTOY.cbl", estate[1], mode="loose")


def test_a_path_outside_the_root_is_not_the_estates(estate):
    lay = EngineLayouts.from_ir(estate[0], "LAYTOY.cbl", estate[1])
    assert lay.rel(str(estate[1] / "LAYCPY.cpy")) == "LAYCPY.cpy"
    assert lay.rel(str(Path(estate[2]) / "SYSREC.cpy")) is None


CODEPTR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRTOY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PP.
           05  PP-A               PIC X(2).
           05  PP-PROC            USAGE PROCEDURE-POINTER.
           05  PP-B               PIC X.
           05  PP-FUNC            FUNCTION-POINTER.
           05  PP-C               PIC X.
           05  PP-TBL             PROCEDURE-POINTER OCCURS 2.
           05  PP-D               PIC X.
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def codeptr_estate(tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("engine_layout_5694")
    repo = base / "repo"
    repo.mkdir()
    (repo / "PTRTOY.cbl").write_text(CODEPTR, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan")), repo


def test_code_pointers_have_a_width_the_engine_can_hand_the_translator(codeptr_estate):
    """#5694: a record holding a PROCEDURE- / FUNCTION-POINTER is consumed, not refused. At the translator's width both
    are its POINTER (8); at z/OS's, a procedure pointer is 8 and a function pointer 4 (register C9)."""
    ir, repo = codeptr_estate
    lines = program_lines(repo / "PTRTOY.cbl", [repo], None)
    recs = L.parse(lines)
    own = {x.name: (x.offset, x.size) for r in recs for x in r.walk()}
    lay = EngineLayouts.from_ir(ir, "PTRTOY.cbl", repo, mode="check")
    lay.apply(recs, lines)
    assert lay.consumed == ["WS-PP"] and lay.own == []
    assert {x.name: (x.offset, x.size) for r in recs for x in r.walk()} == own
    assert [_at(recs, n) for n in ("PP-PROC", "PP-FUNC", "PP-TBL", "PP-D", "WS-PP")] == [
        (2, 8), (11, 8), (20, 8), (36, 1), (0, 37)]  # fmt: skip
    ef = ir.files["PTRTOY.cbl"]
    top = next(i for i in ef.data_items if i.name == "WS-PP")
    fields = {f["name"]: (f["offset"], f["bytes"]) for f in ir.record_layout(ef, top)["fields"]}  # z/OS: no override
    assert [fields[n] for n in ("PP-PROC", "PP-FUNC", "PP-TBL", "PP-D")] == [(2, 8), (11, 4), (16, 16), (32, 1)]


def test_the_shared_helper_finds_the_estate_scan_beside_the_project(tmp_path):
    """#5649: det_port and equivalence_java take the engine's layouts from the clean room's scan DB beside the
    generated project; without one the translator keeps its own (None)."""
    pytest.importorskip("tree_sitter_language_pack")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "LAYTOY.cbl").write_text(PROGRAM, encoding="utf-8")
    (corpus / "LAYCPY.cpy").write_text(LAYCPY, encoding="utf-8")
    project = tmp_path / "estate" / "project"
    project.mkdir(parents=True)
    assert equivalence_common.engine_layouts(project, corpus, "LAYTOY.cbl") is None
    db = scan_to_db(corpus, tmp_path / "scan")
    dumps = project.parent / "x_gitgalaxy_clean_1" / "04_ir_state_dumps"
    dumps.mkdir(parents=True)
    shutil.copy(db, dumps / "x_galaxy_master.db")
    lay = equivalence_common.engine_layouts(project, corpus, "LAYTOY.cbl")
    assert lay is not None and lay.mode == "check" and lay.pointer_bytes == POINTER_BYTES
    assert equivalence_common.engine_layouts(project, corpus, "NOPE.cbl") is None


def test_the_porting_loop_and_crucible_callers_hand_translate_the_engine_layouts(tmp_path, monkeypatch):
    """#5649: port_runner.det_port takes the layouts from the scan beside its project, as det_port and
    equivalence_java do; without a scan it passes None and the translator lays out on its own."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java import port_runner
    from gitgalaxy.tools.cobol_to_java.det import program as P

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "LAYTOY.cbl").write_text(PROGRAM, encoding="utf-8")
    (corpus / "LAYCPY.cpy").write_text(LAYCPY, encoding="utf-8")
    project = tmp_path / "estate" / "project"
    svc = project / "src" / "main" / "java" / "pkg" / "service"
    svc.mkdir(parents=True)
    (svc / "LaytoyService.java").write_text("package pkg.service;\n", encoding="utf-8")
    ticket = {"program": {"file": "LAYTOY.cbl"}, "target": {"service": "LaytoyService"}}
    seen: list = []

    class _Stop(Exception):
        pass

    def fake_translate(*args, **kw):
        seen.append(kw.get("layouts"))
        raise _Stop

    monkeypatch.setattr(P, "translate", fake_translate)
    for expect_scan in (False, True):
        if expect_scan:
            dumps = project.parent / "x_gitgalaxy_clean_1" / "04_ir_state_dumps"
            dumps.mkdir(parents=True)
            shutil.copy(scan_to_db(corpus, tmp_path / "scan"), dumps / "x_galaxy_master.db")
        with pytest.raises(_Stop):
            port_runner.det_port(project, ticket, corpus, tmp_path / "work", "dispatch", False)
    assert seen[0] is None
    assert isinstance(seen[1], EngineLayouts) and seen[1].mode == "check"


SYNCED = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SYNTOY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ONE                 PIC S9(8) COMP SYNC.
       01  WS-TWO                 PIC S9(4) COMP-5 SYNC VALUE 9.
       01  WS-SY.
           05  S-A                PIC X.
           05  S-B                PIC S9(4) COMP SYNC.
           05  S-C                PIC X.
           05  S-D                PIC S9(8) COMP SYNC.
           05  S-P                POINTER SYNC.
           05  S-E                PIC X.
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def sync_estate(tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("engine_layout_5694_sync")
    repo = base / "repo"
    repo.mkdir()
    (repo / "SYNTOY.cbl").write_text(SYNCED, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan")), repo


def test_sync_slack_is_the_engines_and_check_mode_refuses_what_the_translator_does_not_model(sync_estate):
    """#5694: the engine lays SYNC slack out, the translator's own layout does not. A level-01 SYNC item (every
    burned one: genapp lgwebst5, the async credit-card SEQPNT / ASYNCPNT) starts a record and has no slack, so the two
    agree. Mid-record slack, and a POINTER SYNC at either width, is the engine's in engine mode; check mode refuses
    by name rather than let the translator's unaligned offsets stand."""
    ir, repo = sync_estate
    lines = program_lines(repo / "SYNTOY.cbl", [repo], None)

    def run(mode, width):
        recs = L.parse(lines)
        lay = EngineLayouts.from_ir(ir, "SYNTOY.cbl", repo, mode, width)
        return recs, lay

    recs = L.parse(lines)
    own = {x.name: (x.offset, x.size) for r in recs for x in r.walk()}
    assert [own[n] for n in ("WS-ONE", "WS-TWO")] == [(0, 4), (0, 2)]
    assert [own[n] for n in ("S-A", "S-B", "S-C", "S-D", "S-P", "S-E")] == [
        (0, 1),
        (1, 2),
        (3, 1),
        (4, 4),
        (8, 8),
        (16, 1),
    ]  # fmt: skip  (the translator: packed, no slack)

    for width, want in (
        (ZOS_POINTER_BYTES, [(0, 1), (2, 2), (4, 1), (8, 4), (12, 4), (16, 1)]),
        (POINTER_BYTES, [(0, 1), (2, 2), (4, 1), (8, 4), (16, 8), (24, 1)]),
    ):
        recs, lay = run("engine", width)
        lay.apply(recs, lines)
        assert lay.consumed == ["WS-ONE", "WS-TWO", "WS-SY"]
        assert [_at(recs, n) for n in ("WS-ONE", "WS-TWO")] == [(0, 4), (0, 2)]  # level 01: no slack
        assert [_at(recs, n) for n in ("S-A", "S-B", "S-C", "S-D", "S-P", "S-E")] == want
        assert _at(recs, "WS-SY")[1] == want[-1][0] + 1

    recs, lay = run("check", POINTER_BYTES)
    with pytest.raises(LayoutDisagrees, match=r"01 WS-SY: .*S-B engine @2\+2, translator @1\+2"):
        lay.apply(recs, lines)
