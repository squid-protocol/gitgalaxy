"""
Blind cross-verification of an answer key (tests/tools/cross_verify.py).

The brief must not leak the key's answers; grading must list every disagreement;
signing must refuse until each one is settled and any key fix is really in the key.
All on a synthetic key -- no corpus needed.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cross_verify as cv  # noqa: E402

REPO = Path("/repo")


def _prog(pid, units, dead=(), copybooks=(), calls=(), files=()):
    return {
        "program_id": pid,
        "units": [{"name": u, "kind": "paragraph", "line": i + 1} for i, u in enumerate(units)],
        "dead": {d: {"reason": "r", "trivial": False} for d in dead},
        "copybooks": [{"name": n, "resolves_to": r} for n, r in copybooks],
        "calls": [{"verb": v, "operand": o} for v, o in calls],
        "files": [{"dd": d, "modes": m} for d, m in files],
        "verification": {"status": "validated", "tier": "llm_verified", "by": "m", "at": "d", "notes": []},
    }


KEY = {
    "corpus": "k",
    "ref": "0" * 40,
    "programs": {
        "A.cbl": _prog(
            "PROGA",
            ["MAIN", "DEAD-1", "LIVE-1", "LIVE-2"],
            dead=["DEAD-1"],
            copybooks=[("CPY1", "cpy/CPY1.cpy"), ("DFHAID", None)],
            calls=[("CALL", "SUB"), ("XCTL", "WS-PGM")],
            files=[("INDD", ["INPUT"])],
        ),
        "B.cbl": _prog("PROGB", ["MAIN", "OTHER"]),
    },
}


def _answers(truth):
    """A reviewer who agrees with the key on everything."""
    return {
        "A": [{"n": t["n"], "reachable": t["reachable"], "evidence": "e"} for t in truth["A"]],
        "B": {str(REPO / p): pid for p, pid in truth["B"].items()},
        "C": {p: [{"member": m, "resolves_to": r} for m, r in v] for p, v in truth["C"].items()},
        "D": {p: [{"verb": verb, "operand": op} for verb, op in v] for p, v in truth["D"].items()},
        "E": {p: [{"dd": dd, "modes": list(m)} for dd, m in v] for p, v in truth["E"].items()},
    }


def test_brief_is_blind_and_mixes_dead_with_live_controls():
    brief, truth = cv.build(KEY, REPO, live=2, programs=2, seed=1)
    asked = {(t["program"], t["unit"]) for t in truth["A"]}
    assert ("A.cbl", "DEAD-1") in asked  # every dead verdict is re-asked
    assert sum(t["reachable"] for t in truth["A"]) >= 1  # with live controls beside it
    # The key's answers never appear: not its PROGRAM-IDs, resolutions, DD names or verdicts.
    for leaked in ("PROGA", "PROGB", "cpy/CPY1.cpy", "INDD", "trivial", '"reachable": false'):
        assert leaked not in brief, leaked
    assert "reachable" in brief and "read only inside that directory" in brief
    assert truth["root"] == str(REPO)


def test_brief_is_deterministic_for_a_seed():
    assert cv.build(KEY, REPO, 2, 2, 7) == cv.build(KEY, REPO, 2, 2, 7)


def test_notes_bearing_programs_are_always_sampled():
    key = copy.deepcopy(KEY)
    key["programs"]["B.cbl"]["verification"]["notes"] = ["a finding"]
    _brief, truth = cv.build(key, REPO, live=1, programs=0, seed=1)
    assert "B.cbl" in truth["C"]


def test_full_agreement_grades_clean():
    _brief, truth = cv.build(KEY, REPO, 2, 2, 1)
    g = cv.grade(truth, _answers(truth), REPO)
    assert g["disagreements"] == []
    assert all(t["agree"] == t["asked"] for t in g["tasks"].values())


def test_every_kind_of_disagreement_is_listed():
    _brief, truth = cv.build(KEY, REPO, 2, 2, 1)
    ans = _answers(truth)
    dead_n = next(t["n"] for t in truth["A"] if not t["reachable"])
    next(a for a in ans["A"] if a["n"] == dead_n)["reachable"] = True
    ans["B"][str(REPO / "B.cbl")] = "00220000"
    ans["C"]["A.cbl"] = [{"member": "CPY1", "resolves_to": "other/CPY1.cpy"}]
    ans["D"]["A.cbl"].append({"verb": "CALL", "operand": "'EXTRA'"})
    ans["E"]["A.cbl"] = []
    ids = {d["id"] for d in cv.grade(truth, ans, REPO)["disagreements"]}
    assert "A:A.cbl::DEAD-1" in ids
    assert "B:B.cbl" in ids
    assert any(i.startswith("C:A.cbl::") and "other/CPY1.cpy" in i for i in ids)  # reviewer-only resolution
    assert any(i.startswith("C:A.cbl::") and "DFHAID" in i for i in ids)  # key-only member
    assert any(i.startswith("D:A.cbl::") and "EXTRA" in i for i in ids)
    assert any(i.startswith("E:A.cbl::") and "INDD" in i for i in ids)


def test_operands_compare_without_quotes_or_case():
    _brief, truth = cv.build(KEY, REPO, 2, 2, 1)
    ans = _answers(truth)
    ans["D"]["A.cbl"] = [{"verb": "call", "operand": "'sub'"}, {"verb": "XCTL", "operand": "ws-pgm"}]
    assert not [d for d in cv.grade(truth, ans, REPO)["disagreements"] if d["task"] == "D"]


def test_sign_refuses_unruled_and_bad_rulings_then_signs():
    _brief, truth = cv.build(KEY, REPO, 2, 2, 1)
    ans = _answers(truth)
    ans["B"][str(REPO / "B.cbl")] = "WRONG"
    g = cv.grade(truth, ans, REPO)
    with pytest.raises(SystemExit, match="no ruling"):
        cv.sign(copy.deepcopy(KEY), truth, g, {}, "rev")
    with pytest.raises(SystemExit, match="still disagrees"):
        cv.sign(copy.deepcopy(KEY), truth, g, {"B:B.cbl": {"verdict": "key_fixed", "why": "w"}}, "rev")
    with pytest.raises(SystemExit, match="need verdict"):
        cv.sign(copy.deepcopy(KEY), truth, g, {"B:B.cbl": {"verdict": "meh", "why": "w"}}, "rev")
    signed = cv.sign(
        copy.deepcopy(KEY),
        truth,
        g,
        {"B:B.cbl": {"verdict": "key_correct", "why": "source says PROGB"}},
        "rev",
        at="2026-09-24",
    )
    v = signed["programs"]["A.cbl"]["verification"]
    assert (v["tier"], v["cross_by"], v["cross_at"]) == ("cross_verified", "rev", "2026-09-24")
    (record,) = signed["cross_verification"]
    assert record["by"] == "rev" and record["rulings"]["B:B.cbl"]["verdict"] == "key_correct"


def test_parse_answers_tolerates_a_fence():
    assert cv.parse_answers('here you go\n```json\n{"A": []}\n```') == {"A": []}
