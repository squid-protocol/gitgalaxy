"""#5233: the CardDemo COPAUS1C equivalence case (the pending-authorization detail screen, transid CPVD: EXEC DLI SCHD / GU /
GNP / REPL on DBPAUTP0, SEARCH ALL over the decline-reason table, XCTL, and a LINK to the Db2 fraud service COPAUS2C). The
unit tests need nothing but the case; the proof itself (33 scenarios and the two SQL fault runs, GnuCOBOL against the det
port, the deployed entry point too) is the det sweep's, `det_port.py run carddemo-copaus1c`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_cics as ec  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-copaus1c"

# the screen's entry, ENTER and PF-key outcomes, every decline reason the table lookup can end on, the fraud toggle,
# and the DL/I status faults
SCENARIOS = [
    "first-entry-no-commarea", "entry-approved", "entry-insufficient-fund", "entry-fraud-confirmed",
    "entry-fraud-removed", "entry-reason-not-in-table", "entry-reason-last-entry", "entry-single-detail",
    "entry-account-not-numeric", "entry-no-selected-key", "entry-account-without-summary", "reenter-enter",
    "pf3-to-summary", "pf9-invalid-key", "pf8-next-detail", "pf8-at-last-detail", "pf8-single-detail",
    "pf5-report-new-fraud", "pf5-report-existing-row", "pf5-remove-fraud", "pf5-confirm-removed-fraud",
    "pf5-service-insert-fails", "pf5-link-fails",
    "entry-gu-system-error", "entry-gu-end-of-db", "entry-gnp-system-error", "entry-gnp-end-of-db",
    "pf8-gnp-system-error", "pf8-gnp-end-of-db", "pf5-repl-fails",
    "entry-schd-tc-once", "entry-schd-fails", "pf8-schd-fails",
]  # fmt: skip


def _case() -> dict:
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def test_the_case_states_every_scenario_with_its_reason():
    case = _case()
    assert [s["name"] for s in case["scenarios"]] == SCENARIOS
    assert all(s["why"].strip() for s in case["scenarios"])


def test_the_case_runs_the_program_under_its_transid_with_the_fraud_service_it_links_to():
    case = _case()
    assert (case["program"], case["transid"]) == ("COPAUS1C", "CPVD")
    assert [p["program"] for p in case["programs"]] == ["COPAUS2C"]
    assert case["ims"]["compare"] == ["DBPAUTP0"]
    assert case["db2"]["compare"] == ["CARDDEMO.AUTHFRDS"]
    assert {s["name"] for s in case["scenarios"] if s.get("commarea") is None} == {"first-entry-no-commarea"}


def test_the_database_is_stated_in_the_case_and_is_in_key_order():
    """The seed is hand-stated (inline hex), so its segment sizes and root order are checked here, not by a sweep."""
    segments = _case()["ims"]["seed"]["DBPAUTP0"]["segments"]
    size = {"PAUTSUM0": 100, "PAUTDTL1": 200}
    assert all(len(s["hex"]) == 2 * size[s["segment"]] for s in segments)
    roots = [s["hex"][:12] for s in segments if s["segment"] == "PAUTSUM0"]
    assert roots == sorted(roots)
    assert len(set(roots)) == len(roots)


def test_the_selected_key_of_each_scenario_is_a_segment_of_the_database():
    """A scenario's CDEMO-CPVD-PAU-SELECTED is the 8 packed key bytes of a PAUTDTL1 (or a stated blank / foreign one)."""
    case = _case()
    keys = {
        bytes.fromhex(s["hex"])[:8] for s in case["ims"]["seed"]["DBPAUTP0"]["segments"] if s["segment"] == "PAUTDTL1"
    }
    chosen = {
        s["commarea"]["CDEMO-CPVD-PAU-SELECTED"].encode("latin-1")
        for s in case["scenarios"]
        if s.get("commarea") and s["commarea"].get("CDEMO-CPVD-PAU-SELECTED", " ").strip()
    }
    assert chosen <= keys


def test_the_case_notice_names_the_sources_own_license():
    assert "Apache" in (CASE / "NOTICE").read_text(encoding="utf-8")
    assert (CASE / "LICENSE").read_text(encoding="utf-8").lstrip().startswith("Apache License")


def test_each_dli_fault_is_a_plan_the_stubs_read():
    """#5233: GU, the qualified and the unqualified GNP and REPL each answer a status the program's EVALUATE handles
    (AC the system-error arm, GB the end-of-database one). SCHD answers TC only (once, or on every call), which takes the
    program's schedule-failure arm (branch 48/48)."""
    case = _case()
    planned = {s["name"]: ec.dli_fault_lines(case, s) for s in case["scenarios"] if s.get("dli_faults")}
    assert planned["entry-gu-end-of-db"] == ["GU 1 GB"]
    assert planned["pf8-gnp-system-error"] == ["GNP 2 AC"]
    assert planned["pf5-repl-fails"] == ["REPL 1 AC"]
    assert {line.split()[0] for lines in planned.values() for line in lines} == {"GU", "GNP", "REPL", "SCHD"}
    assert planned["entry-schd-tc-once"] == ["SCHD 1 TC"]
    assert planned["entry-schd-fails"] == ["SCHD * TC"]
    assert len(planned) == 10


def test_the_committed_det_port_has_a_recorded_proof():
    """`evidence.py prove` records a level only for a committed port: this one is the det translator's own."""
    prov = json.loads((CASE / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["program"], prov["translator"]) == ("COPAUS1C", "det")
    assert (CASE / "port" / "service" / "Copaus1cService.java").is_file()
    rec = json.loads((CASE / "evidence.json").read_text(encoding="utf-8"))
    assert rec["proof"]["verdict"] == "proven" and not rec["proof"]["java_failed"]
    assert rec["provenance"]["written_by"] == "det"
    assert rec["proof"]["runs"] >= len(SCENARIOS)
