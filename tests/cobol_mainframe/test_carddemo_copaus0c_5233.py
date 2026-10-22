"""#5233: the CardDemo COPAUS0C equivalence case (the pending-authorization summary screen, transid CPVS: EXEC DLI GU /
GNP browse of DBPAUTP0, three VSAM reads, BMS map COPAU0A) and the harness steps it needed. The unit tests need nothing
but the case; the proof itself (27 scenarios, GnuCOBOL against the det port, the deployed entry point too) is the det
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

# the screen's entry, ENTER, selection and PF-key outcomes, and the VSAM file faults it handles
SCENARIOS = [
    "first-entry-no-commarea", "entered-from-menu-no-account", "entered-from-menu-with-account", "enter-no-account",
    "enter-account-not-numeric", "enter-account-one-page", "enter-account-single-detail", "enter-account-two-pages",
    "enter-account-without-summary", "enter-account-not-in-xref", "enter-account-fifty-details", "select-row-1",
    "select-row-3", "select-row-5", "select-lowercase", "select-invalid-code", "pf3-to-menu", "pf3-no-caller",
    "pf7-at-top", "pf8-to-page-two", "pf8-at-bottom", "pf8-no-last-key", "pf7-from-page-two", "pf5-invalid-key",
    "read-xref-io-error", "read-acct-io-error", "read-cust-io-error",
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
