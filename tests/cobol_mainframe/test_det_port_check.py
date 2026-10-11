"""det_port.py check: which ports a change moves -- each case's port compared file by file with the base's."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_port  # noqa: E402


def _port(work: Path, case: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        f = work / case / "port" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def test_a_changed_port_is_named_with_its_file_and_lines(tmp_path):
    base, new = tmp_path / "base", tmp_path / "new"
    svc = "service/XService.java"
    _port(base, "same", {svc: "a\nb\n"})
    _port(new, "same", {svc: "a\nb\n"})
    _port(base, "moved", {svc: "a\nb\nc\n", "cobolrt/Cobol.java": "x\n"})
    _port(new, "moved", {svc: "a\nB\nc\n", "cobolrt/Cobol.java": "x\n"})
    _port(new, "added", {svc: "a\n"})
    rows = {r["case"]: r for r in det_port.compare(base, new)}
    assert rows["same"]["status"] == "unchanged"
    assert rows["moved"]["status"] == "changed"
    assert rows["moved"]["files"] == [{"file": svc, "lines": 2}]  # one line out, one in; the runtime unchanged
    assert rows["added"]["status"] == "new"


def test_every_case_is_listed():
    cases = det_port.all_cases()
    assert "carddemo-cobtupdt" in cases and any(c.startswith("cbsa-") for c in cases)
    assert cases == sorted(cases)


def test_a_cases_subprograms_are_translated_with_it_4803(tmp_path):
    """A CALLed program (a case's `subprograms`) is det-translated like a LINKed one (`programs`): its service is the
    program, not the generator's empty handleCall stub (#4803: EPSCSMRT -> EPSMPMT)."""
    import pytest

    pytest.importorskip("tree_sitter_language_pack")
    import equivalence as eq

    case = eq.load_case("mortgage-cmort")
    corpus = Path(__import__("os").environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpus / case["corpus"]
    if not corpus.is_dir():
        pytest.skip(f"corpus {case['corpus']} not available")
    project = det_port.estate(corpus, tmp_path)
    out = det_port.port_case("mortgage-cmort", tmp_path, project, corpus)
    assert out.get("translated", True), out
    f = tmp_path / "mortgage-cmort" / "port" / "service" / "EpsnbrvlService.java"
    assert f.is_file(), "EPSNBRVL (CALLed by EPSCMORT) is not in the port: the Java side runs the empty stub"
    assert any(row["program"] == "EPSNBRVL" for row in out["parity"])


def test_a_caller_inherits_its_called_programs_holes_4803():
    """Owner decision 2026-10-11: a caller whose LINKed / CALLed program has a hole -- one no scenario reaches -- is
    not proven, though its proof passed."""
    import proof_sweep

    assert proof_sweep.port_proved({"proved": True})
    assert proof_sweep.port_proved({"proved": True, "called_holes": []})
    assert not proof_sweep.port_proved({"proved": True, "called_holes": ["EPSMPMT: line 125: COMPUTE exponentiation"]})
    assert not proof_sweep.port_proved({"proved": False})


def test_extra_programs_are_links_then_calls_without_duplicates_4803():
    case = {"program": "A", "programs": [{"program": "B", "program_source": "b.cbl"}],
            "subprograms": ["x/c.cbl", "x/B.cbl", "x/a.cbl"]}  # fmt: skip
    assert [x["program"] for x in det_port._extra_programs(case)] == ["B", "C"]
