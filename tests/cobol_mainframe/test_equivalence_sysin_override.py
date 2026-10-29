"""#5857: a batch run may carry its own SYSIN (a `faults` entry with `sysin`, and no plan), as it may its own PARM
(#5561): the COBOL staging, the Java test's system property and the fired-fault check all follow it. The CBPAUP0C case
states one control-card scenario per branch family of its PRM-INFO card."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402

CASE = {"name": "c", "program": "P", "sysin": "13 00002 00005 N", "datasets": {}}
CBPAUP0C = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-cbpaup0c" / "case.json"


def test_a_run_gets_its_own_sysin_else_the_cases():
    assert eq.run_sysin(CASE) == "13 00002 00005 N"
    assert eq.run_sysin(CASE, {"name": "f", "plan": []}) == "13 00002 00005 N"
    assert eq.run_sysin(CASE, {"name": "f", "sysin": "05 00002 00005 N"}) == "05 00002 00005 N"
    assert eq.run_sysin({"name": "c"}, {"name": "f", "sysin": "A"}) == "A"
    assert eq.run_sysin({"name": "c"}) is None
    assert eq.run_sysin(CASE, {"name": "f", "sysin": ""}) == ""  # an empty card is a card


def test_a_sysin_only_run_needs_no_fault_to_fire_but_a_planned_fault_does():
    def run(cobol, java, fault):
        out = {"RETURN-CODE": b"0"}
        return eq.compare_run(
            {"name": "c", "datasets": {}}, Path("."), {**out, "FAULTS": cobol}, {**out, "FAULTS": java}, fault=fault
        )

    assert run(b"", b"", {"name": "s", "sysin": "13", "plan": []})["ok"]
    planned = {"name": "s", "sysin": "13", "plan": [{"dd": "X", "op": "READ", "status": "23"}]}
    assert "never fired" in run(b"", b"", planned)["summary"]


def test_the_cbpaup0c_scenarios_each_state_a_card_that_differs():
    case = json.loads(CBPAUP0C.read_text(encoding="utf-8"))
    faults = {f["name"]: f for f in case["faults"]}
    cards = {n: eq.run_sysin(case, f) for n, f in faults.items() if "sysin" in f}
    assert set(cards) == {
        "debug-on",
        "card-defaults",
        "nothing-expires",
        "expiry-abend",
        "debug-expiry-abend",
        "checkpoint-display-compare",
        "checkpoint-freq-compare",
        "expiry-not-numeric",
        "declined-expired",
    }
    assert len({*cards.values(), case["sysin"]}) == 9
    # the control-card runs inject no file status, bar the frequency card (its CHKP drops the position, so a GN
    # answers AM to end the step); the rest fail one DL/I call each on the base card
    assert all(faults[n]["plan"] == [] for n in cards if n != "checkpoint-freq-compare")
    assert {n for n in faults if n not in cards} == {"gn-error", "gnp-error", "dlet-detail-error", "chkp-error"}
    assert all(eq.run_sysin(case, faults[n]) == case["sysin"] for n in faults if n not in cards)
    assert cards["debug-on"].endswith(" Y") and cards["expiry-abend"].startswith("05 ")
