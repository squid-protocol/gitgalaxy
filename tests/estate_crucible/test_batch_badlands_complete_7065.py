"""#7065 Batch Badlands: every construct the issue's checklist line names is planted, scored PASS at the pinned release,
and the level's first-time run is recorded. A construct dropped from levels.json, or a horror that regresses, fails here."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = json.loads((HERE / "levels.json").read_text(encoding="utf-8"))["levels"]
BASELINE = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))["horrors"]
BDLD = next(lv for lv in LEVELS if lv["app"] == "BDLD")

# The checklist line of #7065, one needle per construct it names, matched against the level's construct names.
ISSUE_CONSTRUCTS = {
    "COND / IF-THEN-ELSE": "COND=",
    "PARM": "PARM=",
    "DD concatenation": "DD concatenation",
    "temporary datasets": "temporary datasets",
    "SYSOUT": "SYSOUT",
    "restart": "restart",
    "DFSORT / ICETOOL cards": "ICETOOL",
    "IDCAMS / IEBGENER": "IDCAMS",
    "IKJEFT01 running a Db2 program": "IKJEFT01",
    "GDG (0) / (+1)": "GDG",
}


def test_every_construct_the_issue_names_is_planted_and_passes():
    names = [c["name"] for c in BDLD["constructs"]]
    for label, needle in ISSUE_CONSTRUCTS.items():
        owners = [c for c in BDLD["constructs"] if needle.lower() in c["name"].lower()]
        assert owners, f"no Batch Badlands construct for {label}: {names}"
        for c in owners:
            assert c["horrors"], c["name"]
            for h in c["horrors"]:
                assert BASELINE.get(h) == "PASS", f"{h} ({c['name']}) is {BASELINE.get(h)} at the pin"


def test_every_listed_horror_passes_at_the_pin():
    horrors = [h for c in BDLD["constructs"] for h in c["horrors"]]
    assert horrors, "Batch Badlands lists no horrors"
    assert [h for h in horrors if BASELINE.get(h) != "PASS"] == []


def test_the_first_time_run_is_recorded_once_with_scan_and_translate():
    run = BDLD["first_run"]
    assert run["date"] and run["engine"] and run["key"]
    assert run["scan"]["horrors"] == run["scan"]["pass"] + len(run["scan"]["fail"])
    t = run["translate"]
    assert t["programs"] == t["whole"] + t["holes"] + t["refused"]
