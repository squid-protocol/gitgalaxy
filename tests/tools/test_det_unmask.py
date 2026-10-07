"""det.source.survey_unmask (#4270 `cics_census.py blockers --unmask`): ONE refusal check off for a survey's what-if,
only inside the `with` block, only ever opened by tests/tools/det_survey.py -- never by a production path."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

HEAD = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. PROG.", "DATA DIVISION.", "WORKING-STORAGE SECTION.")


def _fixed(*body: str) -> list[str]:
    return [f"       {b}" for b in body]


def _cut_program() -> list:
    cut = ("    MOVE '" + "A LITERAL RUNNING ON " * 3)[:65]  # (columns 8-72)
    raw = _fixed(*HEAD, "01  A PIC X(80).", "PROCEDURE DIVISION.", cut + "N 73.'", "        TO A.", "    GOBACK.")
    return SRC.logical_lines(raw, "/x/PROG.cbl")


def test_off_by_default_and_only_inside_the_block():
    lines = _cut_program()
    assert "source defect" in (SRC.refusal(lines) or "")
    assert not SRC.unmasked("cut-literal")
    with SRC.survey_unmask("cut-literal"):
        assert SRC.unmasked("cut-literal") and SRC.refusal(lines) is None
        with SRC.survey_unmask("missing-copybook"):  # nested: both off, the outer one restored after
            assert SRC.unmasked("cut-literal") and SRC.unmasked("missing-copybook")
        assert not SRC.unmasked("missing-copybook")
    assert not SRC.unmasked("cut-literal") and "source defect" in (SRC.refusal(lines) or "")


def test_restored_when_the_block_raises():
    with pytest.raises(RuntimeError), SRC.survey_unmask("unmodelled"):
        raise RuntimeError("boom")
    assert not SRC.unmasked("unmodelled")


def test_an_unknown_check_is_refused():
    with (
        pytest.raises(ValueError, match="not an unmaskable refusal check: everything"),
        SRC.survey_unmask("everything"),
    ):
        pass


def test_the_cut_literal_what_if_reaches_the_parsers():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = _cut_program()
    with pytest.raises(E.ExprError, match="source defect"):
        ST.parse(lines)
    with SRC.survey_unmask("cut-literal"):
        L.parse(lines)  # the DATA DIVISION reads
        move = ST.parse(lines).paragraphs[0].body[0]  # the literal read with its text past column 72, as if fixed
        assert move.kind == "MOVE" and move.data["from"].value.endswith("N 73.")
    with pytest.raises(L.LayoutError, match="source defect"):
        L.parse(lines)


def test_a_missing_copybook_expands_to_nothing_only_in_the_what_if(tmp_path):
    raw = _fixed(*HEAD, "    COPY NOWHERE.", "01  A PIC X.", "PROCEDURE DIVISION.", "    GOBACK.")
    lines = SRC.logical_lines(raw, str(tmp_path / "PROG.cbl"))
    with pytest.raises(SRC.CopyNotFound, match="COPY NOWHERE found in none"):
        SRC.expand(lines, [tmp_path])
    with SRC.survey_unmask("missing-copybook"):
        out = SRC.expand(lines, [tmp_path])
    assert [ln.text.strip() for ln in out][-3:] == ["01  A PIC X.", "PROCEDURE DIVISION.", "GOBACK."]
    assert not any("NOWHERE" in ln.text for ln in out)


def test_no_production_path_opens_the_what_if():
    """Only tests/tools/det_survey.py may call survey_unmask; nothing under gitgalaxy/ but its definition."""
    callers = []
    for base in (ROOT / "gitgalaxy", ROOT / "tests" / "tools"):
        for f in base.rglob("*.py"):
            text = "" if f.name.startswith("test_") else f.read_text(encoding="utf-8")
            calls = re.findall(r"\bsurvey_unmask\s*\(", text.replace("def survey_unmask(", ""))
            if calls:
                callers.append(f.relative_to(ROOT).as_posix())
    assert callers == ["tests/tools/det_survey.py"]
    assert (
        "environ"
        not in Path(SRC.__file__).read_text(encoding="utf-8").split("def survey_unmask")[1].split("def refusal")[0]
    )
