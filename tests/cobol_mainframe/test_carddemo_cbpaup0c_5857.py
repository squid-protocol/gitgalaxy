"""#5857: the CardDemo CBPAUP0C equivalence case (a BMP entered USING its I/O PCB and DB PCB, EXEC DLI GN / GNP / DLET /
CHKP on the corpus's own DBPAUTP0 unload). The unit tests need nothing but the case; the proof itself (GnuCOBOL against
the det port) is the det sweep's, `det_port.py run carddemo-cbpaup0c`."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ims  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-cbpaup0c"
APP = "app/app-authorization-ims-db2-mq"


def _case() -> dict:
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def _corpus() -> Path | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    return corpus if (corpus / APP / "cbl/CBPAUP0C.cbl").is_file() else None


def test_the_case_states_the_step_its_card_and_its_database():
    case = _case()
    assert (case["program"], case["job"], case["step"]) == ("CBPAUP0C", "CBPAUP0J", "STEP01")
    assert case["sysin"][:2].isdigit() and case["datasets"] == {}  # PRM-INFO: expiry days first; no files
    assert case["ims"]["psb"].endswith("PSBPAUTB.psb") and case["ims"]["compare"] == ["DBPAUTP0"]
    assert set(case["ims"]["segments"]) == {"PAUTSUM0", "PAUTDTL1"}
    assert "Apache" in (CASE / "NOTICE").read_text(encoding="utf-8")


def test_the_corpus_program_is_a_bmp_whose_psb_is_cmpat_yes():
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    case = _case()
    source = (corpus / case["program_source"]).read_text(encoding="latin-1")
    assert ims.bmp_using(source) == ["IO-PCB-MASK", "PGM-PCB-MASK"]
    _, pcbs = ims.definitions(case, corpus, bmp=True)
    assert len(pcbs) == 1
    with pytest.raises(ims.Unsupported, match="CMPAT=YES"):
        ims.definitions(case, corpus)  # not a BMP: refused by name
    # the database diff reads the DBDs alone, whatever the PSB asks of the entry
    assert [s["name"] for s in ims.dbd_definitions(case, corpus)["DBPAUTP0"]["segments"]] == ["PAUTSUM0", "PAUTDTL1"]


def test_the_bmp_source_lowers_every_exec_dli_to_a_call():
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    source = (corpus / _case()["program_source"]).read_text(encoding="latin-1")
    out = ims.rewrite_bmp(source)
    assert "EXEC DLI" not in out.upper()
    assert out.count("CALL 'GGDLICHKP'") == 1 and "GGDLIX" in out


def test_coverage_reads_the_rewritten_text_a_bmp_ran():
    """The trace is of the BMP-rewritten program (DIB inserted, EXEC DLI expanded): mapped against the original text,
    every line after the first rewrite is lost. Mapped against the rewrite, every original IF keeps its exact line."""
    import cobol_coverage as cov

    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    source = (corpus / _case()["program_source"]).read_text(encoding="latin-1")
    lines = cov.LineMap(source, ims.rewrite_bmp(source))
    ifs = [
        i + 1 for i, x in enumerate(source.split("\n")) if x[6:7] != "*" and x[7:].lstrip().upper().startswith("IF ")
    ]
    assert ifs and set(ifs) <= lines.exact
    # the bug: the unrewritten text is a different length from what ran
    assert len(ims.rewrite_bmp(source).split("\n")) != len(source.split("\n"))


def test_a_dli_fault_is_a_five_word_line_the_file_layers_skip():
    """#5857: a DL/I status rides the fault plan as `# DLI FUNC NTH STATUS`; ggfault.c / CobolFiles read four words and
    skip it, DetDli reads it, and the COBOL side gets ggdli.c's own `FUNC NTH STATUS` file."""
    import equivalence as eq

    plan = eq.fault_plan(
        {
            "name": "x",
            "plan": [
                {"dd": "DLI", "op": "GNP", "nth": 3, "status": "AM"},
                {"dd": "SYSIN", "op": "READ", "nth": 1, "status": "10"},
            ],
        }
    )
    assert plan.splitlines()[0] == "# DLI GNP 3 AM" and len(plan.splitlines()[1].split()) == 4
    assert eq.dli_fault_plan(plan) == "GNP 3 AM\n"
    assert eq.dli_fault_plan("SYSIN READ 1 10\n") == ""


@pytest.mark.parametrize("function", ["GU", "GN", "GNP", "ISRT", "REPL", "DLET", "CHKP"])
def test_every_dli_function_a_fault_run_may_fail_is_accepted(function):
    import equivalence as eq

    plan = eq.fault_plan({"name": "x", "plan": [{"dd": "DLI", "op": function, "nth": "*", "status": "GE"}]})
    assert eq.dli_fault_plan(plan) == f"{function} * GE\n"


@pytest.mark.parametrize(
    "step",
    [
        {"dd": "DLI", "op": "GHN", "status": "AM"},  # the hold form is the get's, not its own function
        {"dd": "DLI", "op": "GN", "status": "ZZ"},  # not a status the model has
        {"dd": "DLI", "op": "GN", "status": "  "},
    ],
)
def test_a_bad_dli_function_or_status_is_refused(step):
    import equivalence as eq

    with pytest.raises(ValueError, match="DL/I"):
        eq.fault_plan({"name": "x", "plan": [step]})


def test_the_cbpaup0c_scenarios_fail_each_dli_call_the_program_checks():
    """The program tests DIBSTAT after GN, GNP, DLET (detail), DLET (summary) and CHKP: a failed one of each is a
    scenario, and every planned status is one the DL/I model has."""
    import equivalence as eq

    faults = {f["name"]: f for f in _case()["faults"]}
    planned = {s["op"] for f in faults.values() for s in f["plan"] if s.get("dd") == "DLI"}
    assert planned == {"GN", "GNP", "DLET", "CHKP"}
    for f in faults.values():
        eq.fault_plan(f)  # raises on a bad function or status
    # the summary DLET always answers DJ (no get-hold of the summary precedes it), so its failure is the abend scenario
    assert faults["expiry-abend"]["sysin"].startswith("05") and faults["debug-expiry-abend"]["sysin"].endswith("Y")
    assert faults["expiry-not-numeric"]["sysin"][:2] == "XX"


def test_the_committed_det_port_has_a_recorded_proof():
    """`evidence.py prove` records a level only for a committed port: this one is the det translator's own."""
    prov = json.loads((CASE / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["program"], prov["translator"]) == ("CBPAUP0C", "det")
    assert (CASE / "port" / "service" / "Cbpaup0cService.java").is_file()
    rec = json.loads((CASE / "evidence.json").read_text(encoding="utf-8"))
    assert rec["proof"]["verdict"] == "proven" and not rec["proof"]["java_failed"]
    assert rec["proof"]["return_code_equal"] and rec["provenance"]["written_by"] == "det"
    assert rec["coverage"]["branches"]["total"] == 40
