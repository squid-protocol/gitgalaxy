"""det_parity.py: a det port whose methods or branches stray far from what its COBOL predicts is a warning."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

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
