"""#4317: the estate-crucible scorer (tests/tools/estate_crucible.py).

The unit tests pin the projection of each channel onto the master DB with hand-made engine
facts, so they need no checkout. The end-to-end test scans a checkout of the crucible at the
pin and skips cleanly when there is none (ESTATE_CRUCIBLE_PATH, else ../estate-crucible
beside the main checkout). It asserts the scorecard's shape, not a score: the scorer is not
a gate yet (#4317 phase 5), and the seed horrors are open engine bugs.
"""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import _estate_crucible_pin as pin  # noqa: E402
import estate_crucible as ec  # noqa: E402


class FakeEngine:
    def __init__(self, units=None, synthetic=None, files=None, raw_imports=None):
        self.units = units or {}
        self.synthetic = synthetic or {}
        self.files = files or {}
        self.raw_imports = raw_imports or {}
        self.excluded = {}


def _unit(name, start, end, calls=(), transfers=()):
    return {
        "name": name,
        "start": start,
        "end": end,
        "calls": list(calls),
        "transfers": list(transfers),
        "synthetic": False,
    }


def _statuses(sc):
    return sorted((c.channel, c.fact, c.status, c.horror) for c in sc.checks)


def test_a_unit_is_scored_on_its_extent_not_only_its_name():
    eng = FakeEngine(units={"p.cbl": [_unit("A", 10, 12), _unit("B", 20, 25)]})
    entry = {
        "units": [
            {"name": "A", "kind": "paragraph", "start_line": 10, "end_line": 18, "horror": "H-0002"},
            {"name": "B", "kind": "paragraph", "start_line": 20, "end_line": 25},
        ]
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, eng)
    got = {c.fact: c for c in sc.checks}
    assert got["A"].status == "fail" and "end_line: key 18 engine 12" in got["A"].detail and got["A"].horror == "H-0002"
    assert got["B"].status == "pass"


def test_the_main_line_is_found_as_a_synthetic_unit_or_missing():
    entry = {
        "units": [{"name": None, "kind": "mainline", "start_line": 5, "end_line": 9, "horror": "H-0003"}],
        "edges": [{"kind": "perform", "from": None, "target": "INIT", "line": 6, "horror": "H-0003"}],
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, FakeEngine())
    ec.score_edges(sc, "p.cbl", entry, FakeEngine())
    assert [c.status for c in sc.checks] == ["missing", "missing"]
    synth = {
        "p.cbl": [{"name": "main", "start": 5, "end": None, "calls": ["INIT"], "transfers": [], "synthetic": True}]
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, FakeEngine(synthetic=synth))
    ec.score_edges(sc, "p.cbl", entry, FakeEngine(synthetic=synth))
    assert [c.status for c in sc.checks] == ["pass", "pass"]


def test_an_unkeyed_callee_is_a_phantom_attributed_through_the_keys_phantom_list():
    eng = FakeEngine(units={"p.cbl": [_unit("MAIN", 1, 9, calls=["WORK", "TEST", "STRAY"], transfers=["000900"])]})
    entry = {
        "units": [{"name": "MAIN", "kind": "paragraph", "start_line": 1, "end_line": 9}],
        "edges": [
            {"kind": "perform", "from": "MAIN", "target": "WORK", "line": 2},
            {"kind": "goto", "from": "MAIN", "target": "END-PARA", "line": 4, "horror": "H-0001"},
        ],
        "phantoms": [
            {"channel": "edges", "kind": "perform", "from": "MAIN", "target": "TEST", "why": "w", "horror": "H-0006"},
            {"channel": "edges", "kind": "goto", "from": "MAIN", "target": "000900", "why": "w", "horror": "H-0001"},
            {
                "channel": "edges",
                "kind": "perform",
                "from": "MAIN",
                "target": "FOREVER",
                "why": "w",
                "horror": "H-0006",
            },
        ],
    }
    sc = ec.Score()
    ec.score_edges(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("edges", "MAIN -perform-> WORK @2", "pass", None),
            ("edges", "MAIN -goto-> END-PARA @4", "missing", "H-0001"),
            ("edges", "MAIN.calls_out_to STRAY", "phantom", None),
            ("edges", "MAIN.calls_out_to TEST", "phantom", "H-0006"),
            ("edges", "MAIN.transfers_to 000900", "phantom", "H-0001"),
            ("edges", "not MAIN -> FOREVER", "pass", "H-0006"),
        ]
    )


def test_a_copy_needs_the_raw_import_and_the_edge_and_accepts_an_alternative():
    ef = SimpleNamespace(copy_deps=["bms/MAPS.bms", "copybook/REC.cpy"])
    eng = FakeEngine(files={"p.cbl": ef}, raw_imports={"p.cbl": ["REC", "MAPS", "000600"]})
    entry = {
        "copies": [
            {"member": "REC", "kind": "copy", "line": 5, "resolves_to": "copybook/REC.cpy"},
            {
                "member": "MAPS",
                "kind": "copy",
                "line": 6,
                "resolves_to": "copybook/MAPS.cpy",
                "alternatives": ["bms/MAPS.bms"],
            },
            {"member": "SQLCA", "kind": "sql-include", "line": 7, "resolves_to": None},
        ],
        "phantoms": [{"channel": "copies", "member": "000600", "why": "seq", "horror": "H-0001"}],
    }
    sc = ec.Score()
    ec.score_copies(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("copies", "REC @5", "pass", None),
            ("copies", "MAPS @6", "pass", None),
            ("copies", "SQLCA @7", "missing", None),
            ("copies", "raw import 000600", "phantom", "H-0001"),
        ]
    )


def test_a_call_site_is_matched_on_verb_and_operand_then_compared():
    call = SimpleNamespace(verb="CALL", form="literal", operand="SUB", target="SUB", resolves_to=None, line=9)
    eng = FakeEngine(files={"p.cbl": SimpleNamespace(calls=[call])})
    entry = {
        "call_sites": [
            {
                "verb": "CALL",
                "form": "literal",
                "operand": "SUB",
                "target": "SUB",
                "line": 9,
                "resolves_to": "cobol/SUB.cbl",
                "depends_on": ["H-0008"],
            }
        ]
    }
    sc = ec.Score()
    ec.score_call_sites(sc, "p.cbl", entry, eng)
    (c,) = sc.checks
    assert c.status == "fail" and "resolves_to" in c.detail and c.depends_on == ["H-0008"]


def test_a_value_keeps_the_blanks_inside_its_literal():
    assert ec._val("'PAGE '") == "PAGE "
    assert ec._val("PAGE ") == "PAGE "
    assert ec._val("ZERO") == "ZERO"


def test_a_key_in_another_format_is_refused(tmp_path):
    (tmp_path / "key").mkdir()
    (tmp_path / "key" / "manifest.json").write_text(json.dumps({"format": "estate-crucible-key/2", "members": {}}))
    with pytest.raises(ValueError, match="estate-crucible-key/2"):
        ec.load_key(tmp_path)


def test_the_pin_is_one_sed_readable_line():
    text = (TESTS / "_estate_crucible_pin.py").read_text()
    found = re.findall(r'^PINNED_REF = "(.*)"$', text, flags=re.M)
    assert found == [pin.PINNED_REF] and re.fullmatch(r"[0-9a-f]{40}|v\d+\.\d+\.\d+", pin.PINNED_REF)


# ---- end to end: a checkout of the crucible at the pin -----------------------------------------


def _checkout():
    path = ec.crucible_path(None)
    if not (path / "key" / "manifest.json").is_file():
        pytest.skip(f"no estate-crucible checkout at {path} (set {pin.PATH_ENV})")
    msg = pin.pin_mismatch(path)
    if msg:
        pytest.skip(msg)
    return path


def test_every_key_fact_is_scored_against_a_scan(tmp_path):
    crucible = _checkout()
    sc = ec.score(crucible, ec.scan(crucible, tmp_path))
    _, key = ec.load_key(crucible)
    assert {c.status for c in sc.checks} <= set(ec.STATUSES)
    keyed = sum(len(e.get(ch, [])) for e in key.values() for ch in ec.CHANNELS)
    scored = sum(1 for c in sc.checks if c.status != "phantom" and not c.fact.startswith("not "))
    assert scored >= keyed  # every keyed fact has at least one check (a layout's overlays add one)
    verdicts = ec.horror_verdicts(sc, crucible)
    assert [h["id"] for h in verdicts] == sorted(
        json.loads((crucible / "key" / "manifest.json").read_text())["horrors"]
    )
    assert ec.markdown(sc, crucible).count("| H-") == len(verdicts)
