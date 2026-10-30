"""det_parity.py: a det port whose methods or branches stray far from what its COBOL predicts is a warning."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import cobol_coverage  # noqa: E402
import det_parity as dp  # noqa: E402
import det_port  # noqa: E402


def _cobol(paragraphs: int, cics: bool = False) -> str:
    head = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. PARTEST.", "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.", "       01 WS-N PIC 9(4) VALUE 0.", "       PROCEDURE DIVISION."]  # fmt: skip
    body = []
    for i in range(paragraphs):
        body += [f"       PARA-{i}.", "           IF WS-N > 1", "               ADD 1 TO WS-N", "           END-IF."]
    if cics:
        body += ["       PARA-END.", "           EXEC CICS RETURN END-EXEC."]
    return "\n".join(head + body) + "\n"


def _java(methods: int, branches_each: int = 1) -> str:
    out = ["package p;", "public class S {", "  int n;"]
    for i in range(methods):
        out.append(f"  void m{i}() {{")
        out += ["    if (n > 1) { n++; }"] * branches_each
        out.append("  }")
    return "\n".join([*out, "}"]) + "\n"


def test_counts_are_the_scanners():
    c = dp.structure(_cobol(5), "cobol")
    j = dp.structure(_java(7), "java")
    assert c["functions"] >= 5 and c["branches"] >= 5
    assert j["functions"] == 7 and j["branches"] >= 7


def test_a_port_shaped_like_the_estate_is_quiet():
    cobol = _cobol(10)
    m = round(
        dp.MODEL["batch"]["methods"][0] + dp.MODEL["batch"]["methods"][1] * dp.structure(cobol, "cobol")["functions"]
    )
    r = dp.parity("PARTEST", cobol, _java(m))
    assert r["kind"] == "batch" and 0.6 <= r["methods"]["ratio"] <= 1.6
    assert not [w for w in r["warnings"] if "methods" in w]


def test_dropped_or_duplicated_paragraphs_warn():
    cobol = _cobol(40)
    few = dp.parity("PARTEST", cobol, _java(5))
    many = dp.parity("PARTEST", cobol, _java(400))
    assert any("methods" in w for w in few["warnings"])
    assert any("methods" in w for w in many["warnings"])


def test_kind_follows_exec_cics():
    assert dp.parity("P", _cobol(3, cics=True), _java(25))["kind"] == "cics"
    assert dp.parity("P", _cobol(3), _java(15))["kind"] == "batch"


def test_a_failing_check_is_a_warning_not_an_error(tmp_path):
    (tmp_path / "service").mkdir()
    out = det_port._parity(tmp_path, tmp_path, [("NOSUCH", "missing.cbl")])
    assert out["parity"] == [] and out["parity_warnings"][0].startswith("NOSUCH: parity check failed")


def _asm(*code: str) -> str:
    data = ["DFHEISTG DSECT", "W_A      DS    CL4", "W_B      DS    CL4"]
    regs = [f"R{n}       EQU   {n}" for n in (10, 11, 12)]
    entry = "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11"
    return "\n".join([*data, entry, *code, *regs, "         END   PROG"]) + "\n"


_ASM_BRANCH = _asm("         CLC   W_A,W_B", "         BC    B'1000',DONE", "         MVC   W_A,W_B",
                   "DONE     DS    0H", "         EXEC CICS RETURN")  # fmt: skip


def test_an_hlasm_program_is_counted_as_its_lowered_cobol():
    """#7011: the raw .asm has no paragraphs (the 'expected from 0' warning); the lowered COBOL has."""
    raw = dp.structure(_ASM_BRANCH, "cobol")
    r = dp.parity("PROG", _ASM_BRANCH, _java(25))
    assert raw["functions"] == 0 and r["cobol"]["functions"] > 0 and r["cobol"]["branches"] > 0
    assert r["kind"] == "cics"
    assert not [w for w in r["warnings"] if "from 0 in" in w]


def test_a_refused_or_lowered_program_is_counted_as_written():
    bad = _asm("         XYZZY W_A,W_B")
    assert dp.parity("P", bad, _java(5))["cobol"] == dp.structure(bad, "cobol")
    low = cobol_coverage.lowered_original(_ASM_BRANCH)  # already COBOL: not lowered twice
    assert dp.parity("P", low, _java(25))["cobol"] == dp.structure(low, "cobol")


def test_a_linked_hlasm_program_is_checked_as_its_lowered_cobol(tmp_path):
    """#7011: det_port._parity reads a LINK target's .asm member too; it is counted as lowered, never 'from 0'."""
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "Source").mkdir()
    (tmp_path / "Source" / "PROG.asm").write_text(_ASM_BRANCH, encoding="utf-8")
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text(_java(25), encoding="utf-8")
    out = det_port._parity(tmp_path, tmp_path, [("PROG", "Source/PROG.asm")])
    assert out["parity"][0]["cobol"]["functions"] > 0 and out["parity"][0]["kind"] == "cics"
    assert not [w for w in out["parity_warnings"] if "from 0 in" in w or "parity check failed" in w]
