"""#5401: burned CardDemo CICS cases with an XCTL site state a scenario where that XCTL answers PGMIDERR (the source
has no RESP, so CICS abends the task): tranlist select to COTRN01C (9e54fb034b) and PF3 to COMEN01C, report PF3 to
COMEN01C, userupd PF3 after the save to COADM01C. The older cases (cardview, tranadd, billpay) predate #5401 and are pinned
without the issue tag; cardlist has its own test. A last test counts each program's XCTL sites in the corpus source and
requires the case to state at least as many faulted-XCTL scenarios. Pure JSON, no Java or Docker."""

import json
import os
import re
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

EQUIVALENCE = Path(__file__).resolve().parents[1] / "equivalence"

# case -> [(scenario, faulted XCTL target)]
STATED = {
    "carddemo-tranlist": [("select-xctl-fails", "COTRN01C"), ("pf3-xctl-fails", "COMEN01C")],
    "carddemo-report": [("pf3-xctl-fails", "COMEN01C")],
    "carddemo-userupd": [("pf3-saves-then-xctl-fails", "COADM01C")],
}

# #4049: userlist's three XCTL sites (U and D selections, and RETURN-TO-PREV-SCREEN, reached by PF3 and, with no
# COMMAREA, aimed at COSGN00C); the scenarios' why carries #4049 rather than #5401
USERLIST = [
    ("pf3-xctl-fails", "COADM01C"),
    ("select-update-xctl-fails", "COUSR02C"),
    ("select-delete-xctl-fails", "COUSR03C"),
    ("no-commarea-xctl-to-signon-fails", "COSGN00C"),
]


# #6166: XCTL sites other cases left unfaulted: the EIBCALEN 0 hop to COSGN00C in useradd / userdel / tranview, and
# PGMIDERR (their older scenarios answer NOTAUTH) at signon's two XCTLs
SIBLINGS = {
    "carddemo-useradd": [("no-commarea-xctl-fails", "COSGN00C")],
    "carddemo-userdel": [("no-commarea-xctl-fails", "COSGN00C")],
    "carddemo-tranview": [("no-commarea-xctl-fails", "COSGN00C")],
    "carddemo-signon": [("admin-xctl-fails", "COADM01C"), ("user-xctl-fails", "COMEN01C")],
}


# case -> [(scenario, faulted XCTL target)]: stated before #5401, so no issue tag in the scenario's why
PRIOR = {
    "carddemo-cardview": [("pf3-xctl-fails-abend-routine", "COCRDLIC")],
    "carddemo-tranadd": [("pf3-xctl-fails", "COMEN01C")],
    "carddemo-billpay": [("pf3-xctl-fails", "COMEN01C")],
}

# the seven ports of #5401, plus userlist (#4049) and the #6166 siblings: case -> (program, XCTL sites in its source)
SITES = {
    "carddemo-cardview": ("COCRDSLC", 1),
    "carddemo-cardlist": ("COCRDLIC", 3),
    "carddemo-tranlist": ("COTRN00C", 2),
    "carddemo-tranadd": ("COTRN02C", 1),
    "carddemo-userupd": ("COUSR02C", 1),
    "carddemo-billpay": ("COBIL00C", 1),
    "carddemo-report": ("CORPT00C", 1),
    "carddemo-userlist": ("COUSR00C", 3),
    "carddemo-useradd": ("COUSR01C", 1),
    "carddemo-userdel": ("COUSR03C", 1),
    "carddemo-tranview": ("COTRN01C", 1),
    "carddemo-signon": ("COSGN00C", 2),
}


def _scenarios(name):
    case = json.loads((EQUIVALENCE / name / "case.json").read_text(encoding="utf-8"))
    return case["scenarios"]


@pytest.mark.parametrize("name", sorted(STATED))
def test_case_states_failed_xctl(name):
    scenarios = _scenarios(name)
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names), f"{name}: duplicate scenario names"
    for scenario, target in STATED[name]:
        (found,) = [s for s in scenarios if s["name"] == scenario]
        assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]
        assert "#5401" in found["why"]


def test_userlist_states_failed_xctl_at_every_site():
    scenarios = _scenarios("carddemo-userlist")
    for scenario, target in USERLIST:
        (found,) = [s for s in scenarios if s["name"] == scenario]
        assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]
        assert "#4049" in found["why"]


@pytest.mark.parametrize("name", sorted(SIBLINGS))
def test_sibling_case_states_failed_xctl(name):
    scenarios = _scenarios(name)
    for scenario, target in SIBLINGS[name]:
        (found,) = [s for s in scenarios if s["name"] == scenario]
        assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]
        assert "#6166" in found["why"]


@pytest.mark.parametrize("name", sorted(PRIOR))
def test_older_case_states_failed_xctl(name):
    scenarios = _scenarios(name)
    for scenario, target in PRIOR[name]:
        (found,) = [s for s in scenarios if s["name"] == scenario]
        assert found["faults"] == [{"cmd": "XCTL", "program": target, "nth": 1, "resp": "PGMIDERR", "resp2": 3}]


@pytest.mark.parametrize("name", sorted(SITES))
def test_every_xctl_site_has_a_failed_xctl_scenario(name):
    program, expected = SITES[name]
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    source = Path(root or "") / "aws-mainframe-modernization-carddemo" / "app" / "cbl" / f"{program}.cbl"
    if not root or not source.is_file():
        pytest.skip("CardDemo corpus not fetched")
    lines = read_source(source).text.splitlines()
    sites = sum(1 for ln in lines if ln[6:7] not in ("*", "/") and re.search(r"\bXCTL\b", ln[7:72]))
    assert sites == expected, f"{program}: {sites} XCTL sites in the source, the test pins {expected}"
    faulted = [s for s in _scenarios(name) if any(f.get("cmd") == "XCTL" for f in s.get("faults") or [])]
    assert len(faulted) >= sites
