"""#4461: where no engine answer decides a COPY (a run without an engine, or a member outside the estate), a member held
by more than one directory is refused by name with its candidates; the translator never takes the first directory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

HEAD = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. PROG.", "DATA DIVISION.", "WORKING-STORAGE SECTION.")


def _fixed(*body: str) -> str:
    return "".join(f"       {b}\n" for b in body)


def _write(root: Path, rel: str, *body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_fixed(*body), encoding="utf-8")
    return p


def _prog(tmp_path: Path) -> Path:
    return _write(tmp_path, "cbl/PROG.cbl", *HEAD, "COPY DATEWS.", "PROCEDURE DIVISION.", "    GOBACK.")


def test_a_member_in_two_directories_is_refused_with_its_candidates(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cpy", "01 A-REC PIC X(16).")
    _write(tmp_path, "b/DATEWS.cpy", "01 B-REC PIC X(18).")
    with pytest.raises(SRC.CopyAmbiguous) as e:
        SRC.program_lines(prog, [tmp_path / "a", tmp_path / "b"])
    msg = str(e.value)
    assert "COPY DATEWS" in msg and str(tmp_path / "a/DATEWS.cpy") in msg and str(tmp_path / "b/DATEWS.cpy") in msg
    assert isinstance(e.value, SRC.CopyNotFound)  # a refusal the callers already handle


def test_the_directory_order_is_no_substitute_for_refusing(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cpy", "01 A-REC PIC X(16).")
    _write(tmp_path, "b/DATEWS.cpy", "01 B-REC PIC X(18).")
    for order in ([tmp_path / "a", tmp_path / "b"], [tmp_path / "b", tmp_path / "a"]):
        with pytest.raises(SRC.CopyAmbiguous):
            SRC.program_lines(prog, order)


def test_a_single_match_resolves(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cpy", "01 A-REC PIC X(16).")
    (tmp_path / "b").mkdir()
    lines = SRC.program_lines(prog, [tmp_path / "a", tmp_path / "b"])
    assert any("A-REC" in ln.text for ln in lines)


def test_the_same_file_through_two_directory_spellings_is_one_candidate(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cpy", "01 A-REC PIC X(16).")
    lines = SRC.program_lines(prog, [tmp_path / "a", tmp_path / "a" / ".." / "a"])
    assert any("A-REC" in ln.text for ln in lines)


def test_a_copybook_beats_a_program_of_the_same_name(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cbl", *HEAD, "01 P-REC PIC X.")
    _write(tmp_path, "b/DATEWS.cpy", "01 B-REC PIC X(18).")
    lines = SRC.program_lines(prog, [tmp_path / "a", tmp_path / "b"])
    assert any("B-REC" in ln.text for ln in lines)


def test_the_shipped_system_member_is_a_fallback_not_a_rival(tmp_path):
    prog = _write(tmp_path, "cbl/PROG.cbl", *HEAD, "COPY DFHAID.", "PROCEDURE DIVISION.", "    GOBACK.")
    _write(tmp_path, "mine/DFHAID.cpy", "01 MY-AID PIC X.")
    lines = SRC.program_lines(prog, [tmp_path / "mine", SRC._SHIPPED_COPY])
    assert any("MY-AID" in ln.text for ln in lines)
    shipped_only = SRC.program_lines(prog, [SRC._SHIPPED_COPY])
    assert shipped_only and not any("MY-AID" in ln.text for ln in shipped_only)


def test_a_member_outside_the_estate_is_refused_when_ambiguous_even_with_an_engine(tmp_path):
    prog = _prog(tmp_path)
    _write(tmp_path, "a/DATEWS.cpy", "01 A-REC PIC X(16).")
    _write(tmp_path, "b/DATEWS.cpy", "01 B-REC PIC X(18).")
    root = tmp_path / "estate"
    eng = SRC.EngineCopies.of(prog, root, {})  # the estate holds none of them: the engine resolved nothing
    with pytest.raises(SRC.CopyAmbiguous):
        SRC.program_lines(prog, [tmp_path / "a", tmp_path / "b"], eng)


def test_an_engine_answer_still_decides_without_a_search(tmp_path):
    root = tmp_path / "estate"
    prog = _write(root, "cbl/PROG.cbl", *HEAD, "COPY DATEWS.", "PROCEDURE DIVISION.", "    GOBACK.")
    _write(root, "shared/DATEWS.cpy", "01 KEY-REC PIC X(16).")
    _write(root, "apps/DATEWS.cpy", "01 OTHER-REC PIC X(18).")
    eng = SRC.EngineCopies.of(prog, root, {"cbl/PROG.cbl": ["shared/DATEWS.cpy"]})
    lines = SRC.program_lines(prog, [root / "apps", root / "shared"], eng)
    assert any("KEY-REC" in ln.text for ln in lines) and not any("OTHER-REC" in ln.text for ln in lines)


def _declared(dirs, source="DATEWS.cpy"):
    from types import SimpleNamespace

    from gitgalaxy.tools.cobol_to_java.det import cics as C

    cics = C.Cics.__new__(C.Cics)
    cics.g = SimpleNamespace(copy_dirs=dirs, engine=None)
    leaf = C.Leaf("wsDate", "String", "WS-DATE", "X(16)", "DISPLAY", 0, 16, source)
    return C, cics.declared(leaf)


def test_the_cics_dto_field_lookup_refuses_a_member_held_by_two_directories(tmp_path):
    _write(tmp_path, "a/DATEWS.cpy", "01 WS-DATE PIC X(16).")
    _write(tmp_path, "b/DATEWS.cpy", "01 WS-DATE PIC X(18).")
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    for order in ([tmp_path / "a", tmp_path / "b"], [tmp_path / "b", tmp_path / "a"]):
        with pytest.raises(C.CicsError, match="COPY DATEWS.cpy is ambiguous"):
            _declared(order)


def test_the_cics_dto_field_lookup_resolves_a_single_member(tmp_path):
    _write(tmp_path, "a/DATEWS.cpy", "01 WS-DATE PIC X(16).")
    (tmp_path / "b").mkdir()
    _, item = _declared([tmp_path / "b", tmp_path / "a"])
    assert item.name == "WS-DATE" and item.size == 16
