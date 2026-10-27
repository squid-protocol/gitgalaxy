"""#6166: COUSR00C ends its task with an XCTL (no COMMAREA) or an abend (first-page browse), and the port must return
there. The two `return;` statements in Cousr00cService (after returnToPrevScreen, and under `if (ended)` after
processEnterKey) were each shielded by the other guard, or no scenario reached the path, so deleting either survived.
The harness does record events after a dead task; the gap was in the case. Each scenario below makes one deletion
visible. Pure JSON, no Java or Docker."""

import json
from pathlib import Path

CASES = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-userlist"


def _by_name():
    scenarios = json.loads((CASES / "case.json").read_text(encoding="utf-8"))["scenarios"]
    names = [s["name"] for s in scenarios]
    assert len(set(names)) == len(names)
    return dict(zip(names, scenarios, strict=True))


def test_abend_on_first_page_endbr_ends_the_task():
    found = _by_name()["first-entry-endbr-ioerr"]
    assert found["aid"] == "DFHENTER"
    assert found["commarea"]["CDEMO-PGM-CONTEXT"] == 0
    assert [(f["cmd"], f["file"], f["resp"]) for f in found["faults"]] == [("ENDBR", "USRSEC", "IOERR")]


def test_failed_xctl_with_no_commarea_is_followed_by_a_fault_only_a_dead_task_reaches():
    found = _by_name()["no-commarea-xctl-fails-browse-fault-unreached"]
    assert found["aid"] == "DFHENTER"
    assert found["commarea"] is None
    xctl, browse = found["faults"]
    assert (xctl["cmd"], xctl["program"], xctl["resp"]) == ("XCTL", "COSGN00C", "PGMIDERR")
    assert (browse["cmd"], browse["file"], browse["resp"]) == ("STARTBR", "USRSEC", "IOERR")
