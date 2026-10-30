"""#4767: a case with no committed port gets an evidence record for its det port, built from the det-sweep ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_coverage_ledger as dcl  # noqa: E402
import evidence as ev  # noqa: E402

CASE = "zecs-zecs003"


def _entry(case: str = CASE, **over: object) -> dict:
    fp = dcl.fingerprints(case)
    return {"format": dcl.FORMAT, "scenarios": 18, "paragraphs": {"covered": 21, "live": 21},
            "branches": {"covered": 30, "total": 30}, "inputs": fp, "measured_at": "abc1234", **over}  # fmt: skip


@pytest.fixture
def det(tmp_path, monkeypatch):
    t = ev.equivalence_target(CASE)
    monkeypatch.setattr(ev, "save", lambda target, rec: tmp_path.joinpath("rec.json").write_text(json.dumps(rec)))
    monkeypatch.setattr(ev, "load", lambda target: None)
    return t


def test_the_case_has_no_committed_port(det):
    assert ev.det_only(det)
    assert det.key not in {t.key for t in ev.targets()}


def test_record_names_its_source_and_carries_the_ledger_numbers(det):
    rec = ev.record_det_port(det, {CASE: _entry()}, mutation={})
    p = rec["proof"]
    assert (p["verdict"], p["source"], p["runs"]) == ("proven", ev.DET_SOURCE, 18)
    assert p["det_sweep"]["measured_at"] == "abc1234"
    assert rec["port"]["paths"] == [] and rec["provenance"]["written_by"] == "det"
    assert rec["coverage"]["branches"] == {"covered": 30, "total": 30}
    assert "det_mutation" not in p
    assert ev.validate(rec) == []
    claim = ev.claim(rec, ev.status(rec, det))
    assert "det sweep at abc1234" in claim and "21/21 paragraphs" in claim


def test_det_mutation_numbers_are_added_when_the_case_has_them(det):
    rec = ev.record_det_port(
        det, {CASE: _entry()}, mutation={"score": 0.9, "survived": 2, "l5": False, "current": True}
    )
    assert rec["proof"]["det_mutation"] == {"score": 0.9, "survived": 2, "l5": False, "current": True}


def test_no_ledger_entry_refuses(det):
    with pytest.raises(ValueError, match="no det-sweep coverage ledger entry"):
        ev.record_det_port(det, {}, mutation={})


def test_a_moved_case_refuses(det):
    entry = _entry()
    entry["inputs"] = {**entry["inputs"], "case": "0" * 64}
    with pytest.raises(ValueError, match="stale on case"):
        ev.record_det_port(det, {CASE: entry}, mutation={})


def test_a_changed_input_makes_the_record_stale(det, monkeypatch):
    rec = ev.record_det_port(det, {CASE: _entry()}, mutation={})
    assert ev.status(rec, det)["stale"] == []
    now = ev.compute_inputs(det, rec["differences"])
    now["case"] = {**now["case"], "sha256": "1" * 64}
    monkeypatch.setattr(ev, "compute_inputs", lambda *a, **k: now)
    st = ev.status(rec, det)
    assert st["status"] == "stale" and "case" in st["blocking"]


def test_prove_routes_a_portless_case_to_the_det_record(det, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(ev, "record_det_port", lambda t: seen.append(t.key) or {})
    monkeypatch.setattr(ev, "status", lambda *a, **k: {"status": "proven, unapproved"})
    assert ev.prove(det, tmp_path)["status"]["status"] == "proven, unapproved"
    assert seen == [CASE]


def test_prove_reports_a_refusal_as_an_error(det, monkeypatch, tmp_path):
    def refuse(t):
        raise ValueError("no entry")

    monkeypatch.setattr(ev, "record_det_port", refuse)
    assert ev.prove(det, tmp_path) == {"key": CASE, "error": "no entry"}


def test_committed_det_records_validate_and_are_listed():
    keys = {t.key for t in ev.det_targets()}
    assert {"zecs-zecs000", "zecs-zecs003"} <= keys
    for t in ev.det_targets():
        rec = ev.load(t)
        assert ev.validate(rec) == [] and rec["proof"]["source"] == ev.DET_SOURCE
        assert ev.status(rec, t)["status"].startswith(("proven", "stale"))
