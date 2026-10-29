"""#6967: CSUTLDTC's EVALUATE over the CEEDAYS feedback token: which arms are stated infeasible, which stay open.

The arms IBM can raise for a numeric 'YYYY-MM-DD' / 'YYYYMMDD' picture and a 10-byte date are run by carddemo-dateutil
(valid, 2508, 2513, 2520). 2507, era, bad picture and year-in-era-zero are stated infeasible with a reason. Two stay open
on purpose and are pinned here, so a new open arm fails instead of reading as covered:
  - WHEN FC-INVALID-MONTH (2517): whether a numeric month outside 1-12 is 2508 or 2517 is not settled by IBM's
    documentation (register L1); the model refuses it. COTRN02C and CORPT00C do not check the month first. Owner question.
  - WHEN OTHER: a token no listed message matches; nothing in the model returns one.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "tests/equivalence"
OPEN_ON_PURPOSE = {(128, "WHEN@139"), (128, "OTHER")}
STATED = {(128, "WHEN@131"), (128, "WHEN@135"), (128, "WHEN@141"), (128, "WHEN@145")}


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
    msgs = {"WHEN@131": "2507", "WHEN@135": "2509", "WHEN@141": "2518", "WHEN@145": "2521"}
    for e in _stated():
        assert e["family"] == "G"
        assert msgs[e["outcome"]] in e["reason"]
        assert "YYYY" in e["reason"]
