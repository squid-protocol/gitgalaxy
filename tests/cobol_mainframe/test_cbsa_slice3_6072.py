"""CBSA L3->L4 slice 3 (#6072): the fault and input scenarios added to delcus, bnk1uac and bnk1cra.

JSON-only checks: each added scenario exists and injects the fault its name says, and each class
(a file command failing, a LINK failing) is covered for every response the class lists.
"""

import json
from pathlib import Path

EQUIV = Path(__file__).resolve().parents[1] / "equivalence"


def _stated(case):
    return json.loads((EQUIV / "infeasible_outcomes" / f"{case}.json").read_text(encoding="utf-8"))["entries"]


def _scenarios(case):
    data = json.loads((EQUIV / case / "case.json").read_text(encoding="utf-8"))
    return {s["name"]: s for s in data["scenarios"]}


def _faults(case):
    return {
        (f["cmd"], f.get("file") or f.get("program"), f["resp"])
        for s in _scenarios(case).values()
        for f in s.get("faults", [])
    }


def test_delcus_covers_file_commands_failing():
    sc = _scenarios("cbsa-delcus")
    assert sc["read-notfnd-after-inquiry"]["faults"][0]["resp"] == "NOTFND"
    assert sc["read-ioerr"]["faults"][0]["resp"] == "IOERR"
    assert sc["delete-sysiderr-retried"]["faults"][0]["cmd"] == "DELETE"
    faults = _faults("cbsa-delcus")
    for want in (("READ", "CUSTOMER", "NOTFND"), ("READ", "CUSTOMER", "IOERR"), ("DELETE", "CUSTOMER", "SYSIDERR")):
        assert want in faults


def test_bnk1uac_covers_every_link_failing():
    faults = _faults("cbsa-bnk1uac")
    for program in ("INQACC", "UPDACC"):
        for resp in ("PGMIDERR", "NOTAUTH"):
            assert ("LINK", program, resp) in faults
    sc = _scenarios("cbsa-bnk1uac")
    assert sc["rate-signed-whole"]["receive"]["BNK1UA"]["INTRTI"] == "+5"


def test_bnk1cra_covers_dbcrfun_link_failing_and_amount_shapes():
    faults = _faults("cbsa-bnk1cra")
    for resp in ("PGMIDERR", "NOTAUTH"):
        assert ("LINK", "DBCRFUN", resp) in faults
    sc = _scenarios("cbsa-bnk1cra")
    assert sc["amount-zero"]["receive"]["BNK1CD"]["AMTI"] == "0.00"
    assert sc["amount-leading-spaces-whole"]["receive"]["BNK1CD"]["AMTI"] == "  12"


def test_infeasible_entries_name_a_family_and_a_reason():
    for case in ("cbsa-bnk1uac", "cbsa-bnk1cra"):
        entries = _stated(case)
        assert entries
        for e in entries:
            assert e["family"] in "GCR"
            assert e["reason"]
