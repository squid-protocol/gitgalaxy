"""#5401: COTRN00C sends and receives map COTRN0A of mapset COTRN00. The tranlist case stated no "maps", so the stub did not
check the mapset on the COBOL side. The case now states it: a SEND MAP / RECEIVE MAP for a map its mapset does not hold abends ABM0.
(The two survivors that named the gap, 31b9d4be47 and 16f2ecb581, were already killed by the comparator's mapset field, #5862.) Pure JSON."""

import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-tranlist" / "case.json"


def test_the_case_states_the_mapset_of_every_screen_it_uses():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    assert case["maps"] == {"COTRN0A": {"mapset": "COTRN00"}}
    assert set(case["screens"]) <= set(case["maps"])


def test_the_stated_mapset_is_the_one_the_screen_copybook_comes_from():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    assert case["screens"]["COTRN0A"]["copybook"].endswith("/COTRN00.CPY")
