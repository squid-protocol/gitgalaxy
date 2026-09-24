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


# ---- the `files` suite (#3455 / #3451) ------------------------------------------
FILE_KEY = {
    "corpus": "k",
    "ref": "0" * 40,
    "programs": {},
    "file_control": {
        "P.cbl": {
            "selects": [
                {
                    "select": "X-FILE",
                    "assign": "XDD",
                    "org": "INDEXED",
                    "access": "RANDOM",
                    "key": "X-KEY",
                    "alt": ["X-ALT+DUP"],
                    "rel": None,
                    "status": "X-ST",
                    "copies": ["XREC"],
                    "line": 5,
                }
            ],
            "file_control_validated": False,
        }
    },
    "vsam_defines": {
        "D.jcl": {
            "defines": [
                {
                    "kind": "CLUSTER",
                    "name": "A.KSDS",
                    "org": "INDEXED",
                    "keys": [8, 0],
                    "rec": [80, 80],
                    "related": None,
                    "unique": None,
                    "upgrade": None,
                    "step": "S1",
                    "line": 4,
                }
            ],
            "vsam_validated": False,
        }
    },
    "job_flow": {
        "D.jcl": {
            "rows": [
                {"kind": "JOB", "name": "D", "cond": None, "line": 1},
                {
                    "kind": "STEP",
                    "ord": 1,
                    "step": "S2",
                    "pgm": "SORT",
                    "proc": None,
                    "cond": "(4,LT)",
                    "if": "(S1.RC = 0)",
                    "in": None,
                    "line": 9,
                },
                {
                    "kind": "DD",
                    "step": "S2",
                    "dd": "OUT",
                    "dsn": "A.B",
                    "disp": "NEW",
                    "gen": "+1",
                    "in": None,
                    "line": 10,
                },
            ],
            "jobflow_validated": False,
        }
    },
}


def _files_answer() -> dict:
    return {
        "files": {
            "P.cbl": {
                "selects": [
                    {
                        "line": 5,
                        "select": "X-FILE",
                        "assign": "XDD",
                        "organization": "INDEXED",
                        "access_mode": "RANDOM",
                        "record_key": "X-KEY",
                        "alternate_keys": [{"name": "X-ALT", "duplicates": True}],
                        "relative_key": None,
                        "file_status": "X-ST",
                        "fd_copies": ["XREC"],
                    }
                ]
            },
            "D.jcl": {
                "vsam": [
                    {
                        "line": 4,
                        "kind": "CLUSTER",
                        "name": "A.KSDS",
                        "organization": "INDEXED",
                        "key_length": 8,
                        "key_offset": 0,
                        "record_avg": 80,
                        "record_max": 80,
                        "step": "S1",
                    }
                ],
                "flow": [
                    {"kind": "JOB", "line": 1, "name": "D"},
                    # Blanks inside a condition and a bare `1` generation normalise.
                    {
                        "kind": "STEP",
                        "line": 9,
                        "ordinal": 1,
                        "step": "S2",
                        "program": "SORT",
                        "cond": "(4, LT)",
                        "if_cond": "(S1.RC=0)",
                    },
                    {
                        "kind": "DD",
                        "line": 10,
                        "step": "S2",
                        "dd": "OUT",
                        "dsn": "A.B",
                        "disp": "NEW",
                        "generation": "1",
                    },
                ],
            },
        }
    }


def test_files_suite_brief_is_blind_and_an_agreeing_reviewer_grades_clean():
    brief, truth = cs.render_files(FILE_KEY, REPO, ["P.cbl", "D.jcl"], 1, 1)
    for leaked in ("X-KEY", "A.KSDS", "SORT", "XREC"):
        assert leaked not in brief, leaked
    assert truth["suite"] == "files"
    g = cs.grade(truth, _files_answer(), REPO)
    assert g["disagreements"] == [] and g["tasks"]["flow"] == {"agree": 3, "asked": 3}


def test_files_suite_sign_sets_its_own_flags_and_coverage():
    _brief, truth = cs.render_files(FILE_KEY, REPO, ["P.cbl", "D.jcl"], 1, 1)
    ans = _files_answer()
    ans["files"]["D.jcl"]["flow"].pop()
    g = cs.grade(truth, ans, REPO)
    (d,) = g["disagreements"]
    signed = cs.sign(
        copy.deepcopy(FILE_KEY), truth, g, {d["id"]: {"verdict": "key_correct", "why": "D.jcl:10"}}, "rev", at="d"
    )
    assert signed["job_flow"]["D.jcl"]["jobflow_validated"] is True
    assert signed["file_control"]["P.cbl"]["verification"]["tier"] == "cross_verified"
    assert cs.coverage(signed, ["P.cbl", "D.jcl"], "files")["files"] == [2, 2]
    assert cs.coverage(signed, ["P.cbl", "D.jcl"], "channels")["files"] == [0, 2]
