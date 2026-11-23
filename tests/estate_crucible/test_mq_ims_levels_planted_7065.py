"""#7065 Warlords of the Message Seas (MQSA) and The Hierarchy Keep (HKEP): what each level plants today, pinned.

Neither checklist line is complete (batch-MQ model, MQ structures beyond the stand-ins; DL/I beyond the first slices,
IMS TM / MFS), so this is not a "complete" guard like the Batch Badlands and Alternate Index Archipelago ones. It pins the
state: every horror a level lists is PASS at the pinned release, the constructs still planted but unscored are exactly the
stated set (a new one must be a decision), and the first-time run is recorded once with scan and translate numbers."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = json.loads((HERE / "levels.json").read_text(encoding="utf-8"))["levels"]
BASELINE = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))["horrors"]
BY_APP = {lv["app"]: lv for lv in LEVELS}

UNSCORED = {
    "MQSA": [
        "RRS stubs (CSQBRSTB, CSQBSTUB link-edit)",
        "an MQ-only back-out fixture",
        "trigger monitor start-up (MQTMC2)",
    ],
    "HKEP": ["EXEC DLI", "a DFSRRC00 batch step", "IMS TM and MFS"],
}


def test_every_listed_horror_passes_at_the_pin():
    for app in UNSCORED:
        horrors = [h for c in BY_APP[app]["constructs"] for h in c["horrors"]]
        assert horrors, f"{app} lists no horrors"
        assert [h for h in horrors if BASELINE.get(h) != "PASS"] == [], app


def test_the_unscored_constructs_are_the_stated_set():
    for app, expected in UNSCORED.items():
        unscored = [c["name"] for c in BY_APP[app]["constructs"] if not c["horrors"]]
        assert unscored == expected, app


def test_the_first_time_run_is_recorded_once_with_scan_and_translate():
    for app in UNSCORED:
        run = BY_APP[app]["first_run"]
        assert run["date"] and run["engine"] and run["key"], app
        assert run["scan"]["horrors"] == run["scan"]["pass"] + len(run["scan"]["fail"]), app
        t = run["translate"]
        assert t["programs"] == t["whole"] + t["holes"] + t["refused"], app
