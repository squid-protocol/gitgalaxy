"""Ruby keyword-family validity baseline stays green on the pinned crucible (#9331, part of #8863).

#9360 fixed the Ruby `doc` rule but left its baseline row at the pre-fix 0.07 / 0.02; the row was only re-measured later.
This pins that every Ruby cell scored on a pinned crucible is 0.8 or better, so a stale or regressed row fails here.
"""

import json
from pathlib import Path

BASELINE = Path(__file__).resolve().parents[2] / "family_validity_baseline.json"
FLOOR = 0.8


def _ruby_cells():
    return json.loads(BASELINE.read_text(encoding="utf-8"))["cells"]["ruby"]


def test_every_pinned_ruby_cell_is_at_or_above_the_floor():
    red = {
        fam: (c["recall"], c["precision"])
        for fam, c in _ruby_cells().items()
        if c["pinned"] and min(c["recall"], c["precision"]) < FLOOR
    }
    assert red == {}


def test_ruby_doc_cell_is_scored_on_the_pinned_crucible():
    doc = _ruby_cells()["doc"]
    assert doc["pinned"] is True
    assert doc["status"] == "ok"
