"""#5121: the det translator and the scanner refuse macro-level CICS and CICS Assembler BY NAME (two families), before
COPY expansion, and never touch command-level EXEC CICS programs or the macro tables. Not translated."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402
from tests.tools import support_matrix as SM  # noqa: E402
from tests.tools.cics_census import error_key  # noqa: E402
from tests.tools.feature_inventory import scan_estate  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "cics_macro_level"


def test_a_macro_level_cobol_program_is_refused_by_name_before_its_copybook_is_looked_up():
    """MACROCBL COPYs DFHTCADS, which no directory holds: the refusal is the family, not `missing copybook`."""
    with pytest.raises(SRC.MacroLevelCics, match=r"MACROCBL\.cbl:5: macro-level CICS not supported \(COPY DFHTCADS"):
        SRC.program_lines(FIXTURES / "MACROCBL.cbl", [])


def test_the_obsolete_address_csa_command_is_named():
    with pytest.raises(
        SRC.MacroLevelCics, match=r"CSACBL\.cbl:7: macro-level CICS not supported \(EXEC CICS ADDRESS CSA"
    ):
        SRC.program_lines(FIXTURES / "CSACBL.cbl", [])


@pytest.mark.parametrize(("name", "family", "what"), [
    ("MACROASM.asm", "macro-level CICS", "DFHCSADS"),
    ("CMDASM.asm", "CICS Assembler", "DFHEIENT"),
])  # fmt: skip
def test_an_assembler_source_is_refused_by_name(name, family, what):
    with pytest.raises(SRC.MacroLevelCics, match=rf"{name}:\d+: {family} not supported \({what}"):
        SRC.program_lines(FIXTURES / name, [])


def test_a_command_level_cobol_program_is_not_refused():
    lines = SRC.program_lines(FIXTURES / "CMDCBL.cbl", [])
    assert SRC.macro_level(lines) is None
    assert SRC.refusal(lines) is None


@pytest.mark.parametrize("name", ["PLAIN.asm", "DFHFCT.asm", "MAPSET.asm"])
def test_a_plain_assembler_source_a_table_and_a_map_are_not_cics_programs(name):
    assert SRC.assembler_refusal((FIXTURES / name).read_text().splitlines(), name) is None


def test_a_cobol_member_with_exec_cics_is_not_an_assembler_program():
    raw = ["       01  X PIC X.", "           EXEC CICS RETURN END-EXEC."]
    assert SRC.assembler_refusal(raw, "M.cpy") is None
    assert "CICS Assembler not supported (EXEC CICS)" in SRC.assembler_refusal(raw, "M.asm")  # the same text, an .asm
    assert SRC.assembler_refusal(["       PROGRAM-ID. P.", "         DFHEIENT"], "P.cbl") is None


def test_refusal_covers_a_copybook_that_holds_the_macro_call_and_a_survey_may_unmask_it():
    lines = SRC.logical_lines(["       PROCEDURE DIVISION.", "           CALL 'DFHPC' USING P."], "/x/P.cbl")
    assert "macro-level CICS not supported (CALL 'DFHPC')" in SRC.refusal(lines)
    with SRC.survey_unmask("cics-macro-level"):
        assert SRC.refusal(lines) is None
    assert "cics-macro-level" in SRC.UNMASKABLE


def test_the_blocker_report_keys_one_gap_per_family():
    for macro in ("DFHPC TYPE=LINK", "DFHFC TYPE=GET"):
        err = f"MacroLevelCics: P.cbl:7: macro-level CICS not supported ({macro}): the pre-command-level API (era 0)"
        assert error_key(err) == "refused: macro-level CICS"
    assert error_key("MacroLevelCics: A.asm:1: CICS Assembler not supported (DFHEIENT): x") == "refused: CICS Assembler"


def test_the_refusal_map_names_each_family_once():
    rmap = SM.load_map()
    for text, rid in (
        ("A.cbl:7: macro-level CICS not supported (DFHPC TYPE=LINK): x", "cics-macro-level"),
        ("macro-level CICS not supported", "cics-macro-level"),
        ("CICS Assembler not supported", "cics-assembler"),
    ):
        found = SM.classify(text, rmap)
        assert [e["id"] for e in found] == [rid]
        assert SM.owned(found[0])


def test_the_inventory_counts_both_families_per_estate_and_the_matrix_maps_them(tmp_path):
    estate = tmp_path / "estate"
    shutil.copytree(FIXTURES, estate)
    inv = scan_estate(estate, tmp_path / "db")
    fam = inv["refusal_families"]
    assert fam["macro-level CICS"]["programs"] == ["CSACBL.cbl", "MACROASM.asm", "MACROCBL.cbl"]
    assert fam["CICS Assembler"]["programs"] == ["CMDASM.asm", "MACROASM.asm"]
    assert {"CMDCBL.cbl", "PLAIN.asm", "DFHFCT.asm", "MAPSET.asm"}.isdisjoint(
        p for v in fam.values() for p in v["programs"]
    )
    assert sorted(x["program"] for x in inv["unparsed_programs"] if "MacroLevelCics" in x["reason"]) == [
        "CSACBL.cbl",
        "MACROCBL.cbl",
    ]
    m = SM.build_estate("estate", inv, {"programs": {}}, SM.load_map(), None)
    assert sorted(m["refusals"]) == ["cics-assembler", "cics-macro-level"]
    assert len(m["refusals"]["cics-macro-level"]["programs"]) == 3
    assert len(m["refusals"]["cics-assembler"]["programs"]) == 2
    assert m["unmapped"] == {}
    assert not any(f["feature"].startswith("refusal_families") for f in m["features"])


def test_an_estate_without_either_family_has_no_refusal_families_category(tmp_path):
    estate = tmp_path / "estate"
    estate.mkdir()
    shutil.copy(FIXTURES / "CMDCBL.cbl", estate)
    shutil.copy(FIXTURES / "DFHFCT.asm", estate)
    assert "refusal_families" not in scan_estate(estate, tmp_path / "db")


def test_the_message_names_the_file_line_and_evidence():
    why = SRC.refusal(SRC.logical_lines(["       PROCEDURE DIVISION.", "           DFHKC TYPE=WAIT."], "/x/Q.cbl"))
    assert re.match(r"Q\.cbl:2: macro-level CICS not supported \(DFHKC TYPE=WAIT\)", why)
