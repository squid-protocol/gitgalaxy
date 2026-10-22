"""#5121: macro-level CICS and CICS Assembler are named (two refusal families), never confused with command-level
CICS, the macro TABLES (resource definitions) or BMS map macros. Every macro family, both hosts, the negatives."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from gitgalaxy.core import cics_macro_level as ML

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cics_macro_level"


def _asm(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def _cobol(name: str) -> list[str]:
    """The columns-8-72 text of each code line (det's logical lines, less the comment lines), which cobol_hits reads."""
    return [x[7:72] for x in (FIXTURES / name).read_text(encoding="utf-8").splitlines() if x[6:7] not in ("*", "/")]


@pytest.mark.parametrize("macro", ML.MACROS)
def test_every_macro_family_is_macro_level_in_assembler(macro):
    hits = ML.assembler_hits([f"LBL      DFH{macro} TYPE=GET,DATASET=X", "         END"])
    assert [(h.family, h.what) for h in hits] == [
        (ML.FAMILY_MACRO, f"DFH{macro} TYPE=GET"),
        (ML.FAMILY_ASSEMBLER, "macro-level CICS in assembler"),
    ]


@pytest.mark.parametrize("macro", ML.MACROS)
def test_every_macro_family_is_macro_level_in_cobol(macro):
    assert [h.what for h in ML.cobol_hits([f"    CALL 'DFH{macro}' USING P."])] == [f"CALL 'DFH{macro}'"]
    assert [h.what for h in ML.cobol_hits([f"    DFH{macro} TYPE=PUT,DATASET=X."])] == [f"DFH{macro} TYPE=PUT"]


def test_assembler_macro_program_is_in_both_families_and_continuations_join():
    hits = ML.assembler_hits(_asm("MACROASM.asm"))
    assert ML.families(hits) == [ML.FAMILY_MACRO, ML.FAMILY_ASSEMBLER]
    whats = [h.what for h in hits if h.family == ML.FAMILY_MACRO]
    assert whats == ["DFHCSADS (CSA / TCA addressing)", "DFHPC TYPE=LINK", "DFHFC TYPE=GET", "DFHPC TYPE=RETURN"]
    assert [h.line for h in hits if h.family == ML.FAMILY_MACRO] == [3, 4, 6, 8]


def test_csa_tca_addressing_forms():
    asm = ["         USING DFHTCADS,R11", "         L     R5,CSATCA", "         COPY  DFHCSADS", "TCA      DFHTCADS"]
    assert [h.what for h in ML.assembler_hits(asm) if h.family == ML.FAMILY_MACRO] == [
        "DFHTCADS (CSA / TCA addressing)",
        "CSATCA (CSA / TCA addressing)",
        "DFHCSADS (CSA / TCA addressing)",
        "DFHTCADS (CSA / TCA addressing)",
    ]
    cobol = ["    COPY DFHTCADS.", "    EXEC CICS ADDRESS TCA(P) END-EXEC."]
    assert [h.what for h in ML.cobol_hits(cobol)] == [
        "COPY DFHTCADS (CSA / TCA addressing)",
        "EXEC CICS ADDRESS TCA (CSA / TCA addressing)",
    ]


def test_cobol_address_csa_spans_lines_and_reports_its_first_line():
    hits = ML.cobol_hits(_cobol("CSACBL.cbl"))
    assert [(h.family, h.what) for h in hits] == [(ML.FAMILY_MACRO, "EXEC CICS ADDRESS CSA (CSA / TCA addressing)")]
    assert _cobol("CSACBL.cbl")[hits[0].line - 1].strip().startswith("EXEC CICS ADDRESS")


def test_cobol_macro_fixture():
    assert [h.what for h in ML.cobol_hits(_cobol("MACROCBL.cbl"))] == [
        "COPY DFHTCADS (CSA / TCA addressing)",
        "CALL 'DFHFC'",
    ]


@pytest.mark.parametrize(
    "extra", ["EXEC CICS SEND MAP('A') MAPSET('B') END-EXEC", "EXEC CICS ADDRESS EIB(P) COMMAREA(Q) END-EXEC"]
)
def test_command_level_cobol_is_not_macro_level(extra):
    assert ML.cobol_hits(["    " + extra]) == []


def test_command_level_cobol_fixture_is_clean():
    # DFHRESP, DFHEIBLK, a comment line naming DFHFC TYPE=GET and a literal naming DFHPC TYPE=LINK
    assert ML.cobol_hits(_cobol("CMDCBL.cbl")) == []


@pytest.mark.parametrize(
    "line",
    [
        "    CALL 'DFHEI1' USING X.",  # the command-level stub
        "    MOVE 'DFHFC TYPE=GET' TO X.",
        '    MOVE "DFHPC TYPE=LINK" TO X.',
        "    IF EIBRESP = DFHRESP(NORMAL) CONTINUE.",
        "    01 DFHCOMMAREA PIC X.",
        "    *> DFHFC TYPE=GET",
        "    COPY DFHAID.",
        "    COPY DFHBMSCA.",
        "    DFHFCT TYPE=DATASET.",  # a table macro is no program statement
        "    DFHFC IS A NAME.",  # no TYPE=
    ],
)
def test_cobol_negatives(line):
    assert ML.cobol_hits([line]) == []


def test_command_level_assembler_is_cics_assembler_only():
    hits = ML.assembler_hits(_asm("CMDASM.asm"))
    assert ML.families(hits) == [ML.FAMILY_ASSEMBLER]
    assert [h.what for h in hits] == ["DFHEIENT", "EXEC CICS", "DFHEIRET", "DFHEISTG"]


@pytest.mark.parametrize("name", ["PLAIN.asm", "DFHFCT.asm", "MAPSET.asm"])
def test_not_cics_programs_are_not_refused(name):
    """A plain assembler program, a macro TABLE (a resource definition, read by cics_macro_tables) and a BMS map."""
    assert ML.assembler_hits(_asm(name)) == []


@pytest.mark.parametrize("table", ["FCT", "PCT", "PPT", "DCT", "TST", "SIT", "TCT", "JCT", "RCT", "MCT", "SRT"])
def test_every_macro_table_is_a_resource_definition(table):
    assert ML.assembler_hits([f"         DFH{table} TYPE=INITIAL", f"         DFH{table} TYPE=FINAL"]) == []


def test_assembler_comments_and_other_ops_are_not_evidence():
    assert ML.assembler_hits(["* DFHPC TYPE=LINK", ".* DFHFC TYPE=GET", "         MVC   X,=C'DFHPC TYPE=LINK'"]) == []
    assert ML.assembler_hits(["         DFHPC", "         DFHPC OTHER=1"]) == []  # no TYPE=


def test_the_families_and_refusal_text():
    hit = ML.Hit(ML.FAMILY_MACRO, "DFHPC TYPE=LINK", 7)
    assert ML.refusal_text(hit, "A.cbl").startswith("A.cbl:7: macro-level CICS not supported (DFHPC TYPE=LINK)")
    hit = ML.Hit(ML.FAMILY_ASSEMBLER, "DFHEIENT", 1)
    assert "CICS Assembler not supported (DFHEIENT)" in ML.refusal_text(hit, "B.asm")
    assert ML.families([]) == []


@pytest.mark.parametrize("unit", ["DFHPC TYPE=" + "A" * 50000, " " * 60000 + "DFHFC", "EXEC CICS ADDRESS " * 5000])
def test_pathological_input_is_linear(unit):
    t0 = time.perf_counter()
    ML.cobol_hits([unit])
    ML.assembler_hits(["LBL      " + unit])
    assert time.perf_counter() - t0 < 2.0


def test_the_register_entry_lists_every_macro_family_as_assumed():
    """#5158: X55 states each family's status by name; a family added to MACROS without a row there fails here."""
    text = (Path(__file__).resolve().parents[2] / "docs" / "language_status" / "register" / "X55.md").read_text(
        encoding="utf-8"
    )
    rows = dict(re.findall(r"^\s*\| [^|]*\| `DFH(\w+)` \| (\w+) \|$", text, re.M))
    assert set(rows) == set(ML.MACROS)
    assert set(rows.values()) == {"ASSUMED"}
    for name in ML._CSA_TCA_NAMES:
        assert name in text
