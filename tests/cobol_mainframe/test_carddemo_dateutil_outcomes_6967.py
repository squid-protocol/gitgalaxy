"""#6967: CSUTLDTC's EVALUATE over the CEEDAYS feedback token: which arms are stated infeasible, which stay open.

The arms IBM can raise for a numeric 'YYYY-MM-DD' / 'YYYYMMDD' picture and a 10-byte date are run by carddemo-dateutil
(valid, 2508, 2513, 2520). 2507, era, bad picture and year-in-era-zero are stated infeasible with a reason. One stays open
on purpose and is pinned here, so a new open arm fails instead of reading as covered (the month arm is stated):
  - WHEN FC-INVALID-MONTH (2517) is stated infeasible on the owner's ruling (2026-10-29, register L1, ASSUMED): a numeric
    month outside 1-12 is 2508, so the model never raises 2517. COTRN02C and CORPT00C do not check the month first, so a
    caller reaches the month-13 case; it runs the 2508 arm (WHEN FC-BAD-DATE-VALUE), which carddemo-dateutil now also takes
    with month 13 and 00.
  - WHEN OTHER: a token no listed message matches; nothing in the model returns one.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "tests/equivalence"
OPEN_ON_PURPOSE = {(128, "OTHER")}
STATED = {(128, "WHEN@131"), (128, "WHEN@135"), (128, "WHEN@139"), (128, "WHEN@141"), (128, "WHEN@145")}


def _uncovered() -> set[tuple[int, str]]:
    cov = json.loads((CASE / "carddemo-dateutil/evidence.json").read_text(encoding="utf-8"))["coverage"]
    return {(b["line"], b["outcome"]) for b in cov["uncovered_branches"]}


def _stated() -> list[dict]:
    path = CASE / "infeasible_outcomes/carddemo-dateutil.json"
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


def test_every_uncovered_arm_is_stated_or_a_named_open_arm():
    stated = {(e["line"], e["outcome"]) for e in _stated()}
    assert stated == STATED
    assert _uncovered() - stated == OPEN_ON_PURPOSE


def test_no_open_arm_is_also_stated_infeasible():
    assert not ({(e["line"], e["outcome"]) for e in _stated()} & OPEN_ON_PURPOSE)


def test_each_stated_arm_names_its_message_number_and_the_callers_pictures():
    msgs = {"WHEN@131": "2507", "WHEN@135": "2509", "WHEN@139": "2517", "WHEN@141": "2518", "WHEN@145": "2521"}
    for e in _stated():
        assert e["family"] == "G"
        assert msgs[e["outcome"]] in e["reason"]
        assert "YYYY" in e["reason"]


def test_month_13_and_00_are_run_as_2508_calls():
    case = json.loads((CASE / "carddemo-dateutil/case.json").read_text(encoding="utf-8"))
    months = {c["args"][0]: c for c in case["calls"] if c["args"][1] == "YYYY-MM-DD"}
    for date in ("2022-13-01", "2022-00-15"):
        assert date in months
        assert "2508" in months[date]["why"]
