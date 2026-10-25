"""ladder_gaps (#6072): the uncovered list of a case, with COBOL context, the scan's PERFORM path, stated infeasible
entries and oracle refusals. A tiny synthetic corpus; the scan is stubbed except in one real-scan test."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_coverage_ledger as dcl
import infeasible_outcomes
import ladder_gaps as lg

SRC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TINY.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM CHECK-IT
           GOBACK.
       CHECK-IT.
           IF WS-A = 1
              AND WS-B = 2
              MOVE 1 TO WS-C
           ELSE
              MOVE 2 TO WS-C
           END-IF
           EVALUATE WS-C
              WHEN 1
                 PERFORM RARE-PARA
              WHEN 2
                 MOVE 3 TO WS-D
           END-EVALUATE.
       RARE-PARA.
           MOVE 9 TO WS-D.
"""


@pytest.fixture
def tree(tmp_path, monkeypatch):
    cases = tmp_path / "cases"
    (cases / "tiny-case").mkdir(parents=True)
    (cases / "tiny-twin").mkdir()
    for name in ("tiny-case", "tiny-twin"):
        meta = {"program": "TINY", "program_source": "src/TINY.cbl", "corpus": "x",
                "bounds_refused": {"over-run": "drives an item past its bounds; register X8"}}  # fmt: skip
        (cases / name / "case.json").write_text(json.dumps(meta), encoding="utf-8")
    corpus = tmp_path / "corpus"
    (corpus / "src").mkdir(parents=True)
    (corpus / "src" / "TINY.cbl").write_text(SRC, encoding="utf-8")
    monkeypatch.setattr(lg, "CASES", cases)
    monkeypatch.setattr(infeasible_outcomes, "stated", lambda case, path=None: [])
    return cases, corpus


def sweep_dir(tmp_path, case="tiny-case", paragraphs=(), branches=(), refused=None):
    proof = tmp_path / "sweep" / case / "proof" / "cobol"
    proof.mkdir(parents=True)
    cj = {"paragraphs": {"uncovered": list(paragraphs)}, "branches": {"uncovered": list(branches)}}
    (proof / "coverage.json").write_text(json.dumps(cj), encoding="utf-8")
    if refused:
        (proof / "refused.json").write_text(json.dumps(refused), encoding="utf-8")
    return tmp_path / "sweep"


SCAN = {
    "MAIN-PARA": {"start_line": 4, "complexity": 0, "loc": 3, "calls": ["CHECK-IT"], "transfers": []},
    "CHECK-IT": {"start_line": 7, "complexity": 5, "loc": 12, "calls": ["RARE-PARA"], "transfers": []},
    "RARE-PARA": {"start_line": 20, "complexity": 0, "loc": 2, "calls": [], "transfers": []},
}


def test_resolve_case_program_and_unknown(tree):
    assert lg.resolve(["tiny-case"]) == ["tiny-case"]
    assert lg.resolve(["tiny"]) == ["tiny-case", "tiny-twin"]  # a program is every case that runs it
    assert lg.resolve(["tiny-case", "TINY"]) == ["tiny-case", "tiny-twin"]
    with pytest.raises(SystemExit):
        lg.resolve(["nope"])


def test_paragraph_and_branch_gaps_with_context(tree, tmp_path, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    sw = sweep_dir(tmp_path, paragraphs=[{"name": "RARE-PARA", "line": 20}],
                   branches=[{"line": 8, "kind": "IF", "outcome": "false", "unit": "CHECK-IT"},
                             {"line": 14, "kind": "EVALUATE", "outcome": "WHEN@15", "unit": "CHECK-IT"},
                             {"line": 14, "kind": "EVALUATE", "outcome": "none", "unit": "CHECK-IT"}])  # fmt: skip
    rep = lg.build_case_report("tiny-case", sw, {}, corpus)
    assert rep["origin"] == "coverage.json" and rep["scan"] == "ok" and rep["entry"] == "MAIN-PARA"
    (para,) = rep["paragraphs"]
    assert (para["name"], para["line"], para["complexity"]) == ("RARE-PARA", 20, 0)
    assert para["perform_path"] == ["MAIN-PARA", "CHECK-IT", "RARE-PARA"]
    iff, when, none = rep["branches"]
    assert iff["condition"] == "IF WS-A = 1 AND WS-B = 2"  # a continuation line joins; the MOVE stops it
    assert iff["complexity"] == 5 and iff["perform_path"] == ["MAIN-PARA", "CHECK-IT"]
    assert when["condition"] == "WHEN 1"  # a WHEN arm shows its WHEN line
    assert none["condition"] == "EVALUATE WS-C"
    assert [r["scenario"] for r in rep["refusals"]] == ["over-run"]


def test_a_failed_scan_leaves_question_marks_not_zeros(tree, tmp_path, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: None)
    sw = sweep_dir(tmp_path, paragraphs=[{"name": "RARE-PARA", "line": 20}])
    rep = lg.build_case_report("tiny-case", sw, {}, corpus)
    assert rep["scan"] == "failed"
    p = rep["paragraphs"][0]
    assert (p["complexity"], p["loc"], p["perform_path"]) == ("?", "?", "?")


def test_a_paragraph_the_scan_lacks_is_still_reported(tree, tmp_path, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: {"MAIN-PARA": SCAN["MAIN-PARA"]})
    sw = sweep_dir(tmp_path, paragraphs=[{"name": "RARE-PARA", "line": 20}])
    p = lg.build_case_report("tiny-case", sw, {}, corpus)["paragraphs"][0]
    assert p["name"] == "RARE-PARA" and p["complexity"] == "?" and p["perform_path"] == "?"


def test_a_stated_infeasible_entry_marks_its_gap_and_stays_listed(tree, tmp_path, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    entry = {"unit": "CHECK-IT", "line": 8, "kind": "IF", "outcome": "false", "family": "G", "reason": "caller checked"}
    monkeypatch.setattr(infeasible_outcomes, "stated", lambda case, path=None: [entry])
    sw = sweep_dir(tmp_path, branches=[{"line": 8, "kind": "IF", "outcome": "false", "unit": "CHECK-IT"},
                                       {"line": 8, "kind": "IF", "outcome": "true", "unit": "CHECK-IT"}])  # fmt: skip
    rep = lg.build_case_report("tiny-case", sw, {}, corpus)
    assert rep["branches"][0]["infeasible"] == {"family": "G", "reason": "caller checked"}
    assert "infeasible" not in rep["branches"][1] and rep["infeasible_stated"] == [entry]


def test_refused_json_kinds(tree, tmp_path):
    case = lg.load_case("tiny-case")
    sw = sweep_dir(tmp_path, refused={"a": "drives an item past its bounds (x); register X8",
                                      "b": "EXEC CICS FOO is not modelled", "c": "other"})  # fmt: skip
    proof = sw / "tiny-case" / "proof" / "cobol"
    got = {r["scenario"]: r["kind"] for r in lg.refusals(case, proof)}
    assert got == {"over-run": "X8 bounds_refused", "a": "X8 bounds", "b": "X23 not modelled", "c": "refused"}


def test_ledger_and_sweep_json_sources_use_compact_lists_and_fill_kind_and_unit(tree, tmp_path, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    led = {"tiny-case": {"paragraphs": {"covered": 2, "live": 3}, "branches": {"covered": 0, "total": 3},
                         "uncovered": {"paragraphs": ["RARE-PARA:20"], "branches": ["8:false", "14:WHEN@15"]}}}  # fmt: skip
    monkeypatch.setattr(dcl, "last_coverage", lambda case, ledger_: {"coverage": (2, 3, 0, 3), "stale_inputs": []})
    rep = lg.build_case_report("tiny-case", None, led, corpus)
    assert rep["origin"] == "ledger"
    assert [(b["kind"], b["unit"], b["outcome"]) for b in rep["branches"]] == [("IF", "CHECK-IT", "false"),
                                                                              ("EVALUATE", "CHECK-IT", "WHEN@15")]  # fmt: skip
    assert rep["paragraphs"][0]["line"] == 20
    row = {"uncovered": ["8:false"], "uncovered_paragraphs": ["RARE-PARA:20"]}
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "sweep.json").write_text(json.dumps({"det": {"tiny-case": row}}), encoding="utf-8")
    rep = lg.build_case_report("tiny-case", tmp_path / "s", {}, corpus)
    assert rep["origin"] == "sweep.json" and len(rep["branches"]) == 1


def test_paragraph_strings_in_the_branch_list_are_paragraphs_not_outcomes():
    """A ledger / sweep row lists "paragraph:NAME" beside the "line:outcome" strings (a copybook paragraph is also
    "NAME:None" in the paragraph list): none of them may reach int() (#6072)."""
    got = lg.from_strings("ledger", ["COPY-PARA:None", "RARE-PARA:20"],
                          ["paragraph:COPY-PARA", "8:false", "paragraph:ONLY-IN-BRANCHES", "14:WHEN@15"])  # fmt: skip
    assert [(p["name"], p["line"]) for p in got["paragraphs"]] == [("COPY-PARA", None), ("RARE-PARA", 20),
                                                                 ("ONLY-IN-BRANCHES", None)]  # fmt: skip
    assert [(b["line"], b["outcome"]) for b in got["branches"]] == [(8, "false"), (14, "WHEN@15")]
    assert lg.from_strings("ledger", [], ["paragraph:X"])["branches"] == []


def test_a_copybook_paragraph_without_a_line_is_reported(tree, monkeypatch):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    led = {"tiny-case": {"paragraphs": {"covered": 2, "live": 3}, "branches": {"covered": 0, "total": 3},
                         "uncovered": {"paragraphs": ["COPY-PARA:None"], "branches": ["paragraph:COPY-PARA", "8:false"]}}}  # fmt: skip
    monkeypatch.setattr(dcl, "last_coverage", lambda case, ledger_: {"coverage": (2, 3, 0, 3), "stale_inputs": []})
    rep = lg.build_case_report("tiny-case", None, led, corpus)
    assert [(p["name"], p["line"]) for p in rep["paragraphs"]] == [("COPY-PARA", None)]
    assert len(rep["branches"]) == 1
    assert "src/TINY.cbl (COPY member)" in lg.render_md([rep]) and "None" not in lg.render_md([rep])


def test_a_stale_or_missing_measurement_says_how_to_get_one(tree, monkeypatch):
    _, corpus = tree
    led = {"tiny-case": {"paragraphs": {"covered": 2, "live": 3}, "branches": {"covered": 0, "total": 3},
                         "uncovered": {"branches": ["8:false"]}}}  # fmt: skip
    monkeypatch.setattr(
        dcl, "last_coverage", lambda case, ledger_: {"coverage": (2, 3, 0, 3), "stale_inputs": ["case"]}
    )
    rep = lg.build_case_report("tiny-case", None, led, corpus)
    assert "stale" in rep["unavailable"] and "proof_sweep.py --det-only --cases tiny-case" in rep["unavailable"]
    assert "paragraphs" not in rep  # no gaps are invented
    assert (
        "no entry" in lg.unavailable("tiny-case", {})
        or "no entry" in lg.build_case_report("tiny-twin", None, {}, corpus)["unavailable"]
    )


def test_json_and_markdown_render(tree, tmp_path, monkeypatch, capsys):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    sw = sweep_dir(tmp_path, paragraphs=[{"name": "RARE-PARA", "line": 20}],
                   branches=[{"line": 8, "kind": "IF", "outcome": "false", "unit": "CHECK-IT"}])  # fmt: skip
    base = ["tiny-case", "--sweep", str(sw), "--corpus-dir", str(corpus)]
    assert lg.main([*base, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["format"] == lg.FORMAT and data["cases"][0]["branches"][0]["line"] == 8
    assert lg.main(base) == 0
    md = capsys.readouterr().out
    assert "| `RARE-PARA` |" in md and "MAIN-PARA > CHECK-IT > RARE-PARA" in md and "over-run" in md


def test_free_format_source_conditions(tmp_path):
    lines = [">>SOURCE FORMAT FREE", "if a = 'X'", "   display 'hi'", "end-if"]
    assert lg.condition_text(lines, 2) == "if a = 'X'"
    assert lg.line_text(lines, 99) == ""


def test_path_from_follows_goto_and_sections():
    edges = lg.graph({"A": {"calls": [], "transfers": ["B"]}, "B": {"calls": [], "transfers": []}},
                     [{"name": "S", "kind": "section", "line": 1}, {"name": "P", "kind": "paragraph", "line": 2}])  # fmt: skip
    assert lg.path_from(edges, "A", "B") == ["A", "B"]
    assert lg.path_from(edges, "S", "P") == ["S", "P"]
    assert lg.path_from(edges, "B", "A") is None


def test_the_real_scan_reads_paragraph_start_lines(tmp_path):
    src = tmp_path / "TINY.cbl"
    src.write_text(SRC, encoding="utf-8")
    scan = lg.scan_program(src)
    if scan is None:
        pytest.skip("galaxyscope --db-only did not run here")
    assert scan["CHECK-IT"]["start_line"] == 7 and "RARE-PARA" in scan["CHECK-IT"]["calls"]


@pytest.mark.parametrize("with_line", [False, True])
def test_a_stated_paragraph_entry_marks_its_gap_with_or_without_a_line(tree, tmp_path, monkeypatch, with_line):
    _, corpus = tree
    monkeypatch.setattr(lg, "scan_program", lambda src: SCAN)
    para = {"unit": "rare-para", "kind": "PARAGRAPH", "outcome": "entered", "family": "R", "reason": "DJ status"}
    if with_line:
        para["line"] = 20
    branch = {"unit": "CHECK-IT", "line": 8, "kind": "IF", "outcome": "false", "family": "G", "reason": "checked"}
    monkeypatch.setattr(infeasible_outcomes, "stated", lambda case, path=None: [para, branch])
    sw = sweep_dir(tmp_path, paragraphs=[{"name": "RARE-PARA", "line": 20}, {"name": "MAIN-PARA", "line": 4}],
                   branches=[{"line": 8, "kind": "IF", "outcome": "false", "unit": "CHECK-IT"}])  # fmt: skip
    rep = lg.build_case_report("tiny-case", sw, {}, corpus)
    marks = {p["name"]: p.get("infeasible") for p in rep["paragraphs"]}
    assert marks == {"RARE-PARA": {"family": "R", "reason": "DJ status"}, "MAIN-PARA": None}
    assert rep["branches"][0]["infeasible"] == {"family": "G", "reason": "checked"}
    assert rep["infeasible_stated"] == [para, branch]
    out = lg.render_md([rep])
    assert "| infeasible |" in out and "R: DJ status" in out
