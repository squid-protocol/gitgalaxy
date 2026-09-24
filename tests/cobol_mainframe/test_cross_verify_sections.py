"""
Blind census of the key's fact-channel sections (tests/tools/cross_verify_sections.py):
the brief never leaks the key's answers, a reviewer who agrees grades clean, every
disagreement is listed, and signing sets the section flags only once all are ruled.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cross_verify_sections as cs  # noqa: E402

REPO = Path("/repo")
KEY = {
    "corpus": "k",
    "ref": "0" * 40,
    "programs": {},
    "sql_access": {"A.cbl": {"accesses": ["read ACCOUNT"], "sql_access_validated": False, "verification": {}}},
    "mq_calls": {
        "A.cbl": {
            "calls": [
                {
                    "verb": "MQOPEN",
                    "direction": "put",
                    "queue": "Q.OUT",
                    "resolution": "literal",
                    "open_line": None,
                    "line": 5,
                },
                {
                    "verb": "MQGET",
                    "direction": "get",
                    "queue": None,
                    "resolution": "trigger",
                    "open_line": 3,
                    "line": 9,
                },
            ],
            "mq_validated": False,
            "verification": {},
        }
    },
    "uow_handlers": {
        "B.cbl": {
            "rows": [
                {
                    "kind": "RESP_CHECK",
                    "source": "CICS",
                    "verb": "READ",
                    "condition": "NORMAL,NOTFND",
                    "target": None,
                    "target_kind": None,
                    "resp_var": "WS-R",
                    "attributes": None,
                    "line": 7,
                }
            ],
            "uow_validated": False,
            "verification": {},
        }
    },
    "job_submissions": {"J.jcl": {"submissions": ["intrdr SYSUT2 -> JOB J2 = J2.jcl"], "submissions_validated": False}},
}


def _agreeing() -> dict:
    return {
        "files": {
            "A.cbl": {
                "sql": [{"access": "READ", "table": "account"}],
                "mq": [
                    {"line": 5, "verb": "MQOPEN", "direction": "put", "queue": "Q.OUT", "open_line": None},
                    {"line": 9, "verb": "MQGET", "direction": "get", "queue": "<trigger>", "open_line": 3},
                ],
            },
            "B.cbl": {
                "uow": [
                    {
                        "line": 7,
                        "kind": "RESP_CHECK",
                        "verb": "READ",
                        "condition": ["NOTFND", "NORMAL"],
                        "resp_var": "WS-R",
                    }
                ]
            },
            "C.cbl": {},
        },
        "jobs": {"J.jcl": ["intrdr SYSUT2 -> JOB J2 = J2.jcl"]},
        "triggers": {},
    }


def test_brief_is_blind_and_asks_every_file():
    brief, truth = cs.render(KEY, REPO, ["A.cbl", "B.cbl", "C.cbl"], 1, 1)
    for leaked in ("ACCOUNT", "Q.OUT", "NOTFND", "J2.jcl", "WS-R"):
        assert leaked not in brief, leaked
    assert all(str(REPO / f) in brief for f in ("A.cbl", "B.cbl", "C.cbl"))
    assert "TASK JOBS" in brief and truth["wide"]
    assert "TASK JOBS" not in cs.render(KEY, REPO, ["C.cbl"], 2, 2)[0]


def test_an_agreeing_reviewer_grades_clean():
    _brief, truth = cs.render(KEY, REPO, ["A.cbl", "B.cbl", "C.cbl"], 1, 1)
    g = cs.grade(truth, _agreeing(), REPO)
    assert g["disagreements"] == []
    assert g["tasks"]["mq"] == {"agree": 2, "asked": 2} and g["tasks"]["jobs"] == {"agree": 1, "asked": 1}


def test_misses_and_extras_are_both_listed():
    _brief, truth = cs.render(KEY, REPO, ["A.cbl", "B.cbl", "C.cbl"], 1, 1)
    ans = _agreeing()
    ans["files"]["A.cbl"]["sql"] = []
    ans["files"]["C.cbl"]["uow"] = [{"line": 1, "kind": "COMMIT", "verb": "SYNCPOINT"}]
    ids = {d["id"] for d in cs.grade(truth, ans, REPO)["disagreements"]}
    assert ids == {"sql:A.cbl::read ACCOUNT", "uow:C.cbl::L1 COMMIT SYNCPOINT C=- T=- TK=- V=- A=-"}


def test_sign_needs_rulings_then_sets_the_flags_of_its_files():
    _brief, truth = cs.render(KEY, REPO, ["A.cbl", "B.cbl", "C.cbl"], 1, 1)
    ans = _agreeing()
    ans["files"]["A.cbl"]["sql"] = []
    g = cs.grade(truth, ans, REPO)
    with pytest.raises(SystemExit, match="no ruling"):
        cs.sign(copy.deepcopy(KEY), truth, g, {}, "rev")
    rid = g["disagreements"][0]["id"]
    with pytest.raises(SystemExit, match="still disagrees"):
        cs.sign(copy.deepcopy(KEY), truth, g, {rid: {"verdict": "key_fixed", "why": "w"}}, "rev")
    signed = cs.sign(
        copy.deepcopy(KEY), truth, g, {rid: {"verdict": "key_correct", "why": "line 12 SELECT"}}, "rev", at="d"
    )
    assert signed["sql_access"]["A.cbl"]["sql_access_validated"] is True
    assert signed["uow_handlers"]["B.cbl"]["verification"]["census"] == {"by": "rev", "at": "d"}
    assert signed["uow_handlers"]["B.cbl"]["verification"]["tier"] == "cross_verified"
    assert signed["job_submissions"]["J.jcl"]["submissions_validated"] is True
    assert cs.coverage(signed, ["A.cbl", "B.cbl", "C.cbl", "D.cbl"]) == {
        "files": [3, 4],
        "wide": True,
        "missing": ["D.cbl"],
    }


def test_batches_cover_every_file_once():
    files = ["A.cbl", "B.cbl", "C.cbl", "D.cbl"]
    packed = cs.batches(KEY, files, max_items=3)
    flat = [f for b in packed for f in b]
    assert sorted(flat) == files and len(flat) == len(set(flat))


def test_a_verb_the_kind_fixes_may_be_omitted():
    full = {"line": 3, "kind": "HANDLE_ABEND", "verb": "HANDLE ABEND", "target": "P9", "target_kind": "LABEL"}
    assert cs.canon_uow(dict(full, verb=None)) == cs.canon_uow(full)
    assert cs.canon_uow({"line": 3, "kind": "RESP_CHECK", "verb": None}) != cs.canon_uow(
        {"line": 3, "kind": "RESP_CHECK", "verb": "READ"}
    )
