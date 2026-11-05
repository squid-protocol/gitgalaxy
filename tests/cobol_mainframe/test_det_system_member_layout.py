"""#5694 / #5649: the system members the translator ships (DFHAID, DFHBMSCA, DFHEIBLK, SQLCA, SQLDA) are laid out by
the engine from the same shipped text (core/copy_libraries.system_member_text, flagged `stand-in#`), and the translator
takes that layout.

Two pins. (1) IBM's documented sizes and offsets (the reference: DFHEIBLK is 85 bytes, SQLCA 136, SQLCODE at 12,
SQLWARN0 at 120, an SQLVAR 44 bytes at z/OS's 4-byte POINTER), on the translator's own layout. (2) The engine's layout
of a plain `COPY <member>` equals the translator's own (read before the engine's is taken) at POINTER width 8, and
differs from it only by the POINTER width at 4."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scan_server import scan_to_db
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det.cics import COPY, POINTER_BYTES
from gitgalaxy.tools.cobol_to_java.det.engine_layout import EngineLayouts
from gitgalaxy.tools.cobol_to_java.det.source import program_lines

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

MEMBERS = ("DFHAID", "DFHBMSCA", "DFHEIBLK", "SQLCA", "SQLDA")


def _program(member: str) -> str:
    prog = f"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n" \
           f"       WORKING-STORAGE SECTION.\n           COPY {member}.\n       PROCEDURE DIVISION.\n           GOBACK.\n"  # fmt: skip
    return prog


def _record(tmp_path: Path, member: str) -> L.Item:
    src = tmp_path / "P.cbl"
    src.write_text(_program(member), encoding="utf-8")
    (rec,) = L.parse(program_lines(src, [COPY]))
    return rec


def _at(rec: L.Item, name: str) -> tuple[int, int]:
    it = next(x for x in rec.walk() if x.name == name)
    return it.offset, it.size


def test_dfheiblk_is_ibms_85_bytes(tmp_path):
    rec = _record(tmp_path, "DFHEIBLK")
    assert _at(rec, "DFHEIBLK") == (0, 85)
    assert [_at(rec, n) for n in ("EIBTIME", "EIBDATE", "EIBTRNID", "EIBTASKN", "EIBTRMID", "DFHEIGDI")] == [
        (0, 4), (4, 4), (8, 4), (12, 4), (16, 4), (20, 2)]  # fmt: skip
    assert [_at(rec, n) for n in ("EIBCALEN", "EIBAID", "EIBFN", "EIBRCODE", "EIBDS", "EIBREQID", "EIBRSRCE")] == [
        (24, 2), (26, 1), (27, 2), (29, 6), (35, 8), (43, 8), (51, 8)]  # fmt: skip
    assert [_at(rec, n) for n in ("EIBSYNC", "EIBERR", "EIBERRCD", "EIBSYNRB", "EIBNODAT", "EIBRESP", "EIBRESP2", "EIBRLDBK")] == [
        (59, 1), (69, 1), (70, 4), (74, 1), (75, 1), (76, 4), (80, 4), (84, 1)]  # fmt: skip


def test_sqlca_is_db2s_136_bytes_with_sqlcode_and_sqlwarn0_where_the_sql_lowering_reads_them(tmp_path):
    rec = _record(tmp_path, "SQLCA")
    assert _at(rec, "SQLCA") == (0, 136)
    assert [_at(rec, n) for n in ("SQLCAID", "SQLCABC", "SQLCODE", "SQLERRM", "SQLERRP", "SQLERRD", "SQLWARN", "SQLSTATE")] == [
        (0, 8), (8, 4), (12, 4), (16, 72), (88, 8), (96, 4), (120, 11), (131, 5)]  # fmt: skip
    assert _at(rec, "SQLWARN0") == (120, 1)
    assert next(x for x in rec.walk() if x.name == "SQLERRD").occurs == 6


def test_sqlda_header_is_16_bytes_and_an_sqlvar_is_the_pointer_width_dependent_stride(tmp_path):
    rec = _record(tmp_path, "SQLDA")
    assert [_at(rec, n) for n in ("SQLDAID", "SQLDABC", "SQLN", "SQLD", "SQLVAR")][:4] == [
        (0, 8),
        (8, 4),
        (12, 2),
        (14, 2),
    ]
    assert _at(rec, "SQLVAR")[0] == 16
    # 2 + 2 + two POINTERs + a 32-byte name: 44 at z/OS's 4, 52 at the translator's 8 (oracle_assumptions.md C9)
    assert POINTER_BYTES == 8
    assert _at(rec, "SQLVAR")[1] == 4 + 2 * POINTER_BYTES + 32 == 52
    assert [_at(rec, n)[0] - 16 for n in ("SQLTYPE", "SQLLEN", "SQLDATA", "SQLIND", "SQLNAME")] == [
        0,
        2,
        4,
        4 + 8,
        4 + 16,
    ]


@pytest.mark.parametrize("member", ("DFHAID", "DFHBMSCA"))
def test_the_attribute_and_aid_constants_are_each_one_byte_back_to_back(tmp_path, member):
    rec = _record(tmp_path, member)
    items = [x for x in rec.children if x.level not in (66, 88)]
    assert len(items) >= 30
    assert [(x.offset, x.size) for x in items] == [(i, 1) for i in range(len(items))]
    assert _at(rec, member) == (0, len(items))


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("system_member_5649")
    repo = base / "repo"
    repo.mkdir()
    (repo / "SYSTOY.cbl").write_text(_program_of(MEMBERS), encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan")), repo


def _program_of(members) -> str:
    body = "".join(f"           COPY {m}.\n" for m in members)
    return ("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. SYSTOY.\n       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n       01  WS-FIRST PIC X.\n" + body + "       PROCEDURE DIVISION.\n           GOBACK.\n")  # fmt: skip


def _laid(estate, mode, pointer_bytes):
    ir, repo = estate
    lines = program_lines(repo / "SYSTOY.cbl", [COPY], None)
    recs = L.parse(lines)
    own = {r.name: [(x.name, x.offset, x.size) for x in r.walk()] for r in recs}
    lay = EngineLayouts.from_ir(ir, "SYSTOY.cbl", repo, mode=mode, pointer_bytes=pointer_bytes)
    lay.apply(recs, lines)
    return recs, own, lay


def test_the_engine_lays_out_each_system_member_from_the_shipped_text_and_agrees_with_the_translators_own(estate):
    """#5649: a `COPY <member>` after a data entry is read by the engine from the stand-in directory (flagged
    `stand-in#`), so the translator takes the engine's layout of every one of the five; at the translator's POINTER width
    no offset or width differs from the translator's own."""
    recs, own, lay = _laid(estate, "engine", POINTER_BYTES)
    assert lay.consumed == ["WS-FIRST", *MEMBERS] and lay.own == []
    assert {r.name: [(x.name, x.offset, x.size) for x in r.walk()] for r in recs} == own
    ef = estate[0].files["SYSTOY.cbl"]
    assert sorted(f.file_path for f in ef.stand_in_copies) == sorted(f"stand-in#{m}" for m in MEMBERS)


def test_the_engines_pointer_width_parameter_reaches_the_system_members(estate):
    """SQLDA's SQLVAR holds two POINTERs: 44 bytes at z/OS's 4, 52 at the translator's 8; the engine's width is taken."""
    recs, own, lay = _laid(estate, "engine", 4)
    assert [x[2] for x in own["SQLDA"] if x[0] == "SQLVAR"] == [52]
    assert lay.own == [] and _at(next(r for r in recs if r.name == "SQLDA"), "SQLVAR") == (16, 44)


def test_the_estates_own_member_wins_over_the_shipped_one(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "SQLCA.cpy").write_text("       01  SQLCA.\n           05  SQLCODE PIC S9(9) COMP.\n", encoding="utf-8")
    (repo / "SYSTOY.cbl").write_text(_program_of(["SQLCA"]), encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))
    assert ir.files["SYSTOY.cbl"].stand_in_copies == []


BARE = ("DFHAID", "DFHBMSCA", "DFHEIBLK", "SQLCA", "SQLDA", "CEEIGZCT", "CMQV")


def _bare_estate(tmp_path_factory, members, lead=False):
    pytest.importorskip("tree_sitter_language_pack")
    base = tmp_path_factory.mktemp("bare_copy_5649")
    repo = base / "repo"
    repo.mkdir()
    prog = _program_of(members)
    if not lead:  # nothing above the first COPY in its section
        prog = prog.replace("       01  WS-FIRST PIC X.\n", "")
    (repo / "SYSTOY.cbl").write_text(prog, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan")), repo


@pytest.mark.parametrize("member", BARE)
@pytest.mark.parametrize("width", [4, 8])
def test_a_bare_copy_that_opens_its_section_is_laid_out_by_the_engine(tmp_path_factory, member, width):
    """#5649: a COPY with no data entry above it is no entry's `copy_members`; its statement row still attaches the
    stand-in, so the translator takes the engine's layout (both POINTER widths)."""
    estate = _bare_estate(tmp_path_factory, [member])
    ef = estate[0].files["SYSTOY.cbl"]
    assert [f.file_path for f in ef.stand_in_copies] == [f"stand-in#{member}"]
    if member not in MEMBERS:
        return  # the CEEIGZCT / CMQ stand-ins: attached; the translator lays out no 01 record from them here
    _, _, lay = _laid(estate, "engine", width)
    assert lay.own == [] and lay.consumed


def test_a_bare_copy_beside_an_entry_copy_attaches_each_member_once(tmp_path_factory):
    estate = _bare_estate(tmp_path_factory, MEMBERS, lead=True)
    ef = estate[0].files["SYSTOY.cbl"]
    assert sorted(f.file_path for f in ef.stand_in_copies) == sorted(f"stand-in#{m}" for m in MEMBERS)


def test_a_bare_copy_of_a_member_nobody_ships_attaches_nothing(tmp_path_factory):
    estate = _bare_estate(tmp_path_factory, ["NOSUCHMEM"])
    assert estate[0].files["SYSTOY.cbl"].stand_in_copies == []
