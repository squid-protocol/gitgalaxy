"""#7065 Alternate Index Archipelago: every construct the issue's checklist line names (ESDS, RRDS, AIX + PATH with
duplicate keys, RBA / RRN access, their file status codes) is planted, scored PASS at the pinned release, and the level's
first-time run is recorded. A construct dropped from levels.json, or a horror that regresses, fails here."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = json.loads((HERE / "levels.json").read_text(encoding="utf-8"))["levels"]
BASELINE = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))["horrors"]
AIXA = next(lv for lv in LEVELS if lv["app"] == "AIXA")

# The checklist line of #7065, one needle per construct it names, matched against the level's construct names.
ISSUE_CONSTRUCTS = {
    "ESDS": "ESDS",
    "RRDS": "RRDS",
    "AIX": "ALTERNATEINDEX",
    "PATH": "PATH",
    "duplicate alternate keys": "WITH DUPLICATES",
    "RBA / RRN access": "RBA / RRN",
    "file status codes": "file status",
}


def test_every_construct_the_issue_names_is_planted_and_passes():
    names = [c["name"] for c in AIXA["constructs"]]
    for label, needle in ISSUE_CONSTRUCTS.items():
        owners = [c for c in AIXA["constructs"] if needle.lower() in c["name"].lower()]
        assert owners, f"no Alternate Index Archipelago construct for {label}: {names}"
        for c in owners:
            assert c["horrors"], c["name"]
            for h in c["horrors"]:
                assert BASELINE.get(h) == "PASS", f"{h} ({c['name']}) is {BASELINE.get(h)} at the pin"


def test_every_listed_horror_passes_at_the_pin():
    horrors = [h for c in AIXA["constructs"] for h in c["horrors"]]
    assert horrors, "Alternate Index Archipelago lists no horrors"
    assert [h for h in horrors if BASELINE.get(h) != "PASS"] == []


def test_a_construct_with_no_horror_is_the_stated_upgrade_set_gap_only():
    # Planted but unscored: the pin names it so the gap stays visible. A second unscored construct must be a decision.
    unscored = [c["name"] for c in AIXA["constructs"] if not c["horrors"]]
    assert unscored == ["alternate-index upgrade-set behaviour"]


def test_the_first_time_run_is_recorded_once_with_scan_and_translate():
    run = AIXA["first_run"]
    assert run["date"] and run["engine"] and run["key"]
    assert run["scan"]["horrors"] == run["scan"]["pass"] + len(run["scan"]["fail"])
    t = run["translate"]
    assert t["programs"] == t["whole"] + t["holes"] + t["refused"]
