"""#4506: every element of a SEND MAP the equivalence compare claims to check is pinned, one mutation at a time."""

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec


def _send(**over):
    base = {
        "event": "SEND-MAP",
        "map": "M",
        "mapset": "S",
        "screen": {"MSG": "OK", "NAME": "ANN"},
        "subfields": {"MSG": {"attr": 0xC1, "color": 0xF2, "hilight": 0xF1}, "NAME": {"length": -1}},
        "options": ["ERASE"],
        "cursor": None,
    }
    return {**base, **over}


MUTATIONS = {
    "screen.MSG": {"screen": {"MSG": "BAD", "NAME": "ANN"}},
    "subfields.MSG attr": {
        "subfields": {"MSG": {"attr": 0xC8, "color": 0xF2, "hilight": 0xF1}, "NAME": {"length": -1}}
    },
    "subfields.MSG color": {
        "subfields": {"MSG": {"attr": 0xC1, "color": 0xF4, "hilight": 0xF1}, "NAME": {"length": -1}}
    },
    "subfields.MSG hilight": {
        "subfields": {"MSG": {"attr": 0xC1, "color": 0xF2, "hilight": 0xF2}, "NAME": {"length": -1}}
    },
    "subfields.NAME cursor field": {"subfields": {"MSG": {"attr": 0xC1, "color": 0xF2, "hilight": 0xF1}}},
    "cursor": {"cursor": 5},
    "options": {"options": ["ERASE", "ALARM"]},
    "map": {"map": "N"},
    "mapset": {"mapset": "T"},
}


def test_the_identical_event_is_equal():
    assert ec.compare_events([_send()], [_send()]) == {"events": 1, "equal": 1, "diffs": []}


EXPECTED = {
    "screen.MSG": "screen.MSG",
    "subfields.MSG attr": "subfields.MSG",
    "subfields.MSG color": "subfields.MSG",
    "subfields.MSG hilight": "subfields.MSG",
    "subfields.NAME cursor field": "subfields.NAME",
    "cursor": "cursor",
    "options": "options",
    "map": "map",
    "mapset": "mapset",
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_compared_element_is_caught(name):
    out = ec.compare_events([_send()], [_send(**MUTATIONS[name])])
    assert [f["field"] for f in out["diffs"][0]["fields"]] == [EXPECTED[name]]


def test_a_send_missing_or_extra_is_a_diff():
    assert ec.compare_events([_send()], [])["diffs"][0]["java"] is None
    assert ec.compare_events([], [_send()])["diffs"][0]["cobol"] is None


def test_cleared_and_unpainted_bytes_are_not_claimed():
    java = _send(subfields={"MSG": {"attr": 0x00, "color": 0x40, "hilight": 0}, "NAME": {"length": -1}})
    cobol = _send(subfields={"NAME": {"length": -1}})
    assert ec.compare_events([cobol], [java])["equal"] == 1


def test_the_report_says_what_is_compared():
    src = inspect.getsource(ec.report_markdown)
    assert "attribute bytes are not compared" not in src
    assert "colour and highlight bytes, cursor and options" in src
