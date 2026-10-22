"""#4726 `gitgalaxy assess`, the translate-only dry run: whole / holes / refused per program, counts and a refusal's
class name only (a hole's text can quote the program), the schema holding it, and `--no-translate` leaving it out.

In-process: the dry run installs no network guard (the command's own tests run as subprocesses)."""

import json
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det translator; the ground-truth CI job has no translator extra

from gitgalaxy.tools.readiness import dryrun
from gitgalaxy.tools.readiness import schema as SC

REPO = Path(__file__).resolve().parents[2]
MARK = "ZQX"


def _program(name: str, data: list[str], proc: list[str]) -> str:
    rows = [
        "       ID DIVISION.",
        f"       PROGRAM-ID. {name}.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
    ]
    rows += [f"       {d}" for d in data] + ["       PROCEDURE DIVISION."] + [f"           {p}" for p in proc]
    return "\n".join([*rows, "           GOBACK."]) + "\n"


SOURCES = {
    "WHOLE1.cbl": _program("WHOLE1", ["01 WS-A PIC 9(4)."], ["MOVE 1 TO WS-A.", "ADD 1 TO WS-A."]),
    # SET <alphanumeric> TO NULL is a hole whose message quotes the data name
    "HOLE1.cbl": _program("HOLE1", ["01 WS-ZQX-NAME PIC X(8)."], ["SET WS-ZQX-NAME TO NULL."]),
    "CICS1.cbl": _program("CICS1", ["01 WS-A PIC X(8)."], ["EXEC CICS ASKTIME END-EXEC."]),
    "NOTCOBOL.cbl": "ZQX THIS IS NOT COBOL 'ZQX'\n<html>ZQX</html>\n",
}


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory):
    estate = tmp_path_factory.mktemp("dry")
    for name, text in SOURCES.items():
        (estate / name).write_text(text)
    return dryrun.dry_run(estate, [estate], None, sorted(estate.glob("*.cbl")))


def test_a_program_is_whole_with_holes_or_refused(outcomes):
    assert outcomes["WHOLE1.cbl"]["translation"] == "whole" and outcomes["WHOLE1.cbl"]["holes"] == 0
    assert outcomes["WHOLE1.cbl"]["statements"] == outcomes["WHOLE1.cbl"]["translated_statements"] > 0
    assert outcomes["HOLE1.cbl"]["translation"] == "holes" and outcomes["HOLE1.cbl"]["holes"] == 1
    assert outcomes["NOTCOBOL.cbl"]["translation"] == "refused"
    assert set(outcomes["CICS1.cbl"]) and outcomes["CICS1.cbl"]["translation"] in dryrun.TRANSLATIONS


def test_the_outcome_holds_counts_and_a_class_name_never_text(outcomes):
    assert MARK not in json.dumps(outcomes)
    assert outcomes["NOTCOBOL.cbl"]["refusal"].isidentifier()


def test_a_timeout_is_a_refusal_by_name(tmp_path, monkeypatch):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    def slow(*_a, **_k):
        raise dryrun.Timeout

    monkeypatch.setattr(P, "translate", slow)
    (tmp_path / "WHOLE1.cbl").write_text(SOURCES["WHOLE1.cbl"])
    got = dryrun.dry_run(tmp_path, [tmp_path], None, [tmp_path / "WHOLE1.cbl"])
    assert got["WHOLE1.cbl"] == {"translation": "refused", "refusal": "Timeout"}


def _inventory(programs: list[str], unparsed: list[str]) -> dict:
    inv = {c: {} for c in SC.CATEGORIES}
    inv["copybook_resolution_gaps"] = {}
    inv["unparsed_programs"] = [{"program": p, "reason": "NotCobol - x"} for p in unparsed]
    inv["eras"] = {"programs": {p: {"era": 4, "earliest": 4, "mixed": False, "tells": []} for p in programs}}
    return inv


def test_project_keeps_the_translation_of_parsed_programs_only(outcomes):
    inv = _inventory(sorted(SOURCES), ["NOTCOBOL.cbl"])
    report = SC.project(inv, translation=outcomes)
    assert SC.validate(report) == []
    rows = {r["name"]: r for r in report["programs"]}
    assert "translation" not in rows["NOTCOBOL.cbl"]  # unparsed: already reported as such
    assert rows["WHOLE1.cbl"]["translation"] == "whole" and rows["HOLE1.cbl"]["holes"] == 1
    t = report["totals"]["translation"]
    assert t["whole"] >= 1 and t["holes"] == 1 and sum(t.values()) == 3
    assert MARK not in json.dumps(report)


def test_without_a_dry_run_the_report_is_the_inventory_alone():
    inv = _inventory(["A.cbl"], [])
    report = SC.project(inv)
    assert "translation" not in report["totals"] and "translation" not in report["programs"][0]
    assert SC.validate(report) == []


def test_redaction_still_labels_every_name(outcomes):
    report = SC.project(_inventory(sorted(SOURCES), []), redact_key=b"k", translation=outcomes)
    assert SC.validate(report) == []
    assert not any(n in json.dumps(report) for n in ("WHOLE1", "HOLE1", "CICS1"))


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda r: r.update(translation="proven"), "translation"),
        (lambda r: r.update(refusal="has spaces and ZQX text"), "refusal"),
        (lambda r: r.update(holes="MOVE A TO B"), "holes"),
        (lambda r: r.update(holes=-1), "holes"),
        (lambda r: r.update(hole_text="SET X TO NULL"), "keys"),
    ],
)
def test_validate_refuses_a_widened_translation(outcomes, mutate, needle):
    report = SC.project(_inventory(sorted(SOURCES), []), translation=outcomes)
    row = next(r for r in report["programs"] if r["name"] == "HOLE1.cbl")
    mutate(row)
    assert any(needle in p for p in SC.validate(report)), SC.validate(report)


def test_a_refusal_is_only_valid_on_a_refused_program(outcomes):
    report = SC.project(_inventory(sorted(SOURCES), []), translation=outcomes)
    next(r for r in report["programs"] if r["name"] == "WHOLE1.cbl")["refusal"] = "CopyUnresolved"
    assert any("refusal" in p for p in SC.validate(report))
