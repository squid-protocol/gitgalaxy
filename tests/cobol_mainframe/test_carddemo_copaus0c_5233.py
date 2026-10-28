"""#5233: the CardDemo COPAUS0C equivalence case (the pending-authorization summary screen, transid CPVS: EXEC DLI GU /
GNP browse of DBPAUTP0, three VSAM reads, BMS map COPAU0A) and the harness steps it needed. The unit tests need nothing
but the case; the proof itself (37 scenarios since #6072, GnuCOBOL against the det port, the deployed entry point too) is the det
sweep's, `det_port.py run carddemo-copaus0c`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_cics as ec  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-copaus0c"

# the screen's entry, ENTER, selection and PF-key outcomes, the VSAM file faults it handles and its DL/I status faults
SCENARIOS = [
    "first-entry-no-commarea", "entered-from-menu-no-account", "entered-from-menu-with-account", "enter-no-account",
    "enter-account-not-numeric", "enter-account-one-page", "enter-account-single-detail", "enter-account-two-pages",
    "enter-account-without-summary", "enter-account-not-in-xref", "enter-account-fifty-details", "select-row-1",
    "select-row-3", "select-row-5", "select-lowercase", "select-invalid-code", "pf3-to-menu", "pf3-no-caller",
    "pf7-at-top", "pf8-to-page-two", "pf8-at-bottom", "pf8-no-last-key", "pf7-from-page-two", "pf5-invalid-key",
    "read-xref-io-error", "read-acct-io-error", "read-cust-io-error",
    "enter-gu-system-error", "enter-gnp-system-error", "enter-gnp-end-of-db-mid-page", "pf8-reposition-system-error",
    "pf8-reposition-gnp-ge", "pf8-page-gnp-system-error",
    # #6072: SEL0004, a GNP that ends the list, an SCHD that fails once and always
    "select-row-4", "enter-account-probe-gnp-ends", "enter-schd-tc-once", "enter-schd-fails",
    # #6072: a second detail whose response code is not '00' (the scenario's own IMS seed)
    "enter-account-declined-detail",
    # #6072: CDEMO-ACCT-ID holds letters, so IS NUMERIC is false (raw COMMAREA bytes)
    "entered-with-account-id-letters",
]  # fmt: skip


def _case() -> dict:
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def test_the_case_states_every_scenario_with_its_reason():
    case = _case()
    assert [s["name"] for s in case["scenarios"]] == SCENARIOS
    assert all(s["why"].strip() for s in case["scenarios"])


def test_the_case_runs_the_program_under_its_transid_on_the_authorization_database():
    case = _case()
    assert (case["program"], case["transid"]) == ("COPAUS0C", "CPVS")
    assert case["ims"]["compare"] == ["DBPAUTP0"]
    assert {s["name"] for s in case["scenarios"] if s.get("commarea") is None} == {"first-entry-no-commarea"}


def test_each_dli_fault_is_a_plan_the_stubs_read_and_the_status_arms_are_all_planned():
    """#5233: GU and GNP (the browse's first read, a mid-page read, PF8's reposition and the read after it) each answer a
    status the program's EVALUATE handles. #6072 plans SCHD's TC too, once (TERM and schedule again) and always."""
    planned = {s["name"]: ec.dli_fault_lines(_case(), s) for s in _case()["scenarios"] if s.get("dli_faults")}
    assert planned["enter-gu-system-error"] == ["GU 1 AC"]
    assert planned["enter-gnp-end-of-db-mid-page"] == ["GNP 3 GB"]
    assert planned["pf8-reposition-gnp-ge"] == ["GNP 1 GE"]
    assert {op.split()[0] for lines in planned.values() for op in lines} == {"GU", "GNP", "SCHD"}
    assert len(planned) == 9


def test_the_case_notice_names_the_sources_own_license():
    assert "Apache" in (CASE / "NOTICE").read_text(encoding="utf-8")
    assert (CASE / "LICENSE").read_text(encoding="utf-8").lstrip().startswith("Apache License")


def test_a_table_scalar_list_is_the_numbered_occurrences_of_the_layout():
    """A DTO's `List<String>` for `OCCURS 5` is read as NAME(1) ... NAME(5), the names the COBOL side's area uses."""
    fields = [{"base": "KEYS", "name": "KEYS(1)", "subscripts": [1]}]
    assert ec.first_occurrences({"KEYS": ["a", "b", "c"], "PAGE": 2}, fields) == {
        "KEYS(1)": "a", "KEYS(2)": "b", "KEYS(3)": "c", "PAGE": 2,
    }  # fmt: skip


def test_a_dto_list_property_is_a_table_field_the_json_never_carries(tmp_path):
    """A List property sits under an `// OCCURS n TIMES` second comment line; it is a TableField, a String is not."""
    dto = tmp_path / "Dto.java"
    dto.write_text(
        "class Dto {\n"
        "    // CDEMO-PAGE: PIC 9(3)\n"
        "    private Integer cdemoPage;\n"
        "    // CDEMO-KEYS: PIC X(8)\n"
        "    // OCCURS 5 TIMES\n"
        "    private List<String> cdemoKeys;\n"
        "}\n",
        encoding="utf-8",
    )
    shape = ec._dto_file_shape(tmp_path, dto)
    assert shape == {"cdemoPage": "CDEMO-PAGE", "cdemoKeys": "CDEMO-KEYS"}
    assert isinstance(shape["cdemoKeys"], ec.TableField)
    assert not isinstance(shape["cdemoPage"], ec.TableField)


def test_the_committed_det_port_has_a_recorded_proof():
    """`evidence.py prove` records a level only for a committed port: this one is the det translator's own."""
    prov = json.loads((CASE / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["program"], prov["translator"]) == ("COPAUS0C", "det")
    assert (CASE / "port" / "service" / "Copaus0cService.java").is_file()
    rec = json.loads((CASE / "evidence.json").read_text(encoding="utf-8"))
    assert rec["proof"]["verdict"] == "proven" and not rec["proof"]["java_failed"]
    assert rec["provenance"]["written_by"] == "det"
    assert rec["proof"]["runs"] >= len(SCENARIOS)
