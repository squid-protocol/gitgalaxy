"""#5694: the system members the translator ships (DFHAID, DFHBMSCA, DFHEIBLK, SQLCA, SQLDA) are laid out by the
translator alone: the engine skips a system member's COPY, so engine mode keeps the translator's own layout.

Two pins stand in for the missing engine entry. (1) IBM's documented sizes and offsets (the reference: DFHEIBLK is 85
bytes, SQLCA 136, SQLCODE at 12, SQLWARN0 at 120, an SQLVAR 44 bytes at z/OS's 4-byte POINTER). (2) The shipped text
scanned as an estate copybook under another name: the engine's layout of it must equal the translator's in check mode,
so the translator's arithmetic for these members is the engine's."""

from __future__ import annotations

import shutil
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
    base = tmp_path_factory.mktemp("system_member_5694")
    repo = base / "repo"
    repo.mkdir()
    body = ""
    for m in MEMBERS:
        shutil.copy(COPY / f"{m}.cpy", repo / f"Z{m}.cpy")  # the shipped text, under a name the engine does not skip
        body += f"           COPY Z{m}.\n"
    (repo / "SYSTOY.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. SYSTOY.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n" + body + "       PROCEDURE DIVISION.\n           GOBACK.\n",
        encoding="utf-8",
    )
    return load_galaxy_ir(scan_to_db(repo, base / "scan")), repo


def test_the_engines_layout_of_the_shipped_text_is_the_translators_in_check_mode(estate):
    ir, repo = estate
    lines = program_lines(repo / "SYSTOY.cbl", [repo], None)
    recs = L.parse(lines)
    lay = EngineLayouts.from_ir(ir, "SYSTOY.cbl", repo, mode="check")
    lay.apply(recs, lines)  # LayoutDisagrees on any offset or width that differs
    assert lay.consumed == list(MEMBERS)
    assert lay.own == []
