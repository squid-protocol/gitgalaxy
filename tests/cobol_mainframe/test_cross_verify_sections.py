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


# ---- the `calls` suite (#3454 / #3450) ------------------------------------------
CALLS_KEY = {
    "corpus": "k",
    "ref": "0" * 40,
    "programs": {},
    "call_using": {
        "P.cbl": {
            "rows": [
                {"kind": "PROCEDURE", "name": None, "args": "LS-A,LS-B", "line": 3},
                {"kind": "CALL", "name": "SUB", "args": "WS-A,CONTENT:'X'", "line": 9},
            ],
            "call_using_validated": False,
        }
    },
    "dli_calls": {
        "P.cbl": {
            "calls": [
                {
                    "interface": "EXEC",
                    "function": "ISRT",
                    "operand": None,
                    "pcb": "1",
                    "io": "IOA",
                    "segs": ["ROOT", "CHILD"],
                    "where": ["K = V"],
                    "psb": None,
                    "line": 12,
                },
            ],
            "segment_access": ["insert CHILD", "read ROOT"],
            "dli_validated": False,
        }
    },
}


def test_calls_suite_round_trips_and_signs_its_flags():
    brief, truth = cs.render_calls(CALLS_KEY, REPO, ["P.cbl", "Q.cbl"], 1, 1)
    for leaked in ("LS-A", "SUB", "ROOT", "IOA"):
        assert leaked not in brief, leaked
    answers = {
        "files": {
            "P.cbl": {
                "using": [
                    {"kind": "PROCEDURE", "line": 3, "name": None, "args": ["LS-A", "LS-B"]},
                    {"kind": "CALL", "line": 9, "name": "SUB", "args": ["WS-A", "CONTENT:'X'"]},
                ],
                "dli": [
                    {
                        "interface": "EXEC",
                        "line": 12,
                        "function": "ISRT",
                        "pcb": "1",
                        "io_area": "IOA",
                        "segments": ["ROOT", "CHILD"],
                        "where": ["K=V"],
                    }
                ],
                "ims": [{"access": "INSERT", "segment": "child"}, {"access": "read", "segment": "ROOT"}],
            },
            "Q.cbl": {},
        }
    }
    g = cs.grade(truth, answers, REPO)
    assert g["disagreements"] == [] and g["tasks"]["ims"] == {"agree": 2, "asked": 2}
    signed = cs.sign(copy.deepcopy(CALLS_KEY), truth, g, {}, "rev", at="d")
    assert signed["call_using"]["P.cbl"]["call_using_validated"] is True
    assert signed["dli_calls"]["P.cbl"]["verification"]["tier"] == "cross_verified"
    assert cs.coverage(signed, ["P.cbl", "Q.cbl"], "calls") == {"files": [2, 2], "wide": True, "missing": []}


def test_calls_suite_normalises_function_codes_and_io_wrappers():
    _brief, truth = cs.render_calls(CALLS_KEY, REPO, ["P.cbl"], 1, 1)
    answers = {
        "files": {
            "P.cbl": {
                "using": [
                    {"kind": "PROCEDURE", "line": 3, "name": None, "args": ["LS-A", "LS-B"]},
                    {"kind": "CALL", "line": 9, "name": "SUB", "args": ["WS-A", "CONTENT:'X'"]},
                ],
                # FROM(IOA) and ISRT / GU state the key's IOA / insert / read.
                "dli": [
                    {
                        "interface": "EXEC",
                        "line": 12,
                        "function": "ISRT",
                        "pcb": "1",
                        "io_area": "FROM(IOA)",
                        "segments": ["ROOT", "CHILD"],
                        "where": ["K = V"],
                    }
                ],
                "ims": [{"access": "ISRT", "segment": "CHILD"}, {"access": "GU", "segment": "ROOT"}],
            }
        }
    }
    assert cs.grade(truth, answers, REPO)["disagreements"] == []


# ---- the `lineage` suite (#3477 / #3452): IMS in full, data moves sampled -------
LINEAGE_KEY = {
    "corpus": "k",
    "ref": "0" * 40,
    "programs": {},
    "ims_gen": {
        "P.psb": {
            "rows": [{"kind": "PCB", "line": 1, "name": "XPCB", "type": "DB", "dbd": "D", "procopt": "G"}],
            "ims_gen_validated": False,
            "verification": {},
        },
        "A.cbl": {"access_check": ["SEG denied P/XPCB:update"], "ims_gen_validated": False, "verification": {}},
    },
    "data_moves": {
        "A.cbl": {
            "moves": ["L10 MOVE WS-A -> WS-B", "L11 MOVE 'IN X' -> WS-C", "L40 COMPUTE WS-A -> WS-T"],
            "truncations": ["L11 'IN X' -> WS-C"],
            "data_moves_validated": False,
            "verification": {},
        },
    },
}


def _lineage_answers(moves_ok: bool = True) -> dict:
    rows = [
        {"line": 10, "verb": "MOVE", "source": "WS-A", "target": "WS-B", "truncates": False},
        {"line": 11, "verb": "MOVE", "source": "'IN X'", "target": "WS-C", "truncates": True},
    ]
    if not moves_ok:
        rows = rows[:1]
    return {
        "files": {
            "P.psb": {"imsdef": [{"kind": "pcb", "line": 1, "name": "xpcb", "type": "DB", "dbd": "D", "procopt": "G"}]},
            "A.cbl": {"imscheck": [{"segment": "SEG", "status": "denied", "pcbs": [{"psb": "P", "pcb": "XPCB", "denied": ["update"]}]}]},
        },
        "windows": {"A.cbl@5-16": {"moves": rows}},
    }  # fmt: skip


def test_lineage_suite_brief_is_blind_and_round_trips():
    key = copy.deepcopy(LINEAGE_KEY)
    windows = [{"file": "A.cbl", "from": 5, "to": 16}]
    brief, truth = cs.render_lineage(key, REPO, ["A.cbl", "P.psb"], windows, 1, 1)
    assert "XPCB" not in brief and "WS-B" not in brief and "A.cbl@5-16" not in brief
    # Only the window's rows are asked: L40 is outside it.
    assert truth["facts"]["moves"] == {"A.cbl@5-16": ["L10 MOVE WS-A -> WS-B", "L11 MOVE 'IN X' -> WS-C"]}
    g = cs.grade(truth, _lineage_answers(), REPO)
    assert g["disagreements"] == [] and g["tasks"]["trunc"] == {"agree": 1, "asked": 1}
    bad = cs.grade(truth, _lineage_answers(moves_ok=False), REPO)
    assert {d["task"] for d in bad["disagreements"]} == {"moves", "trunc"}


def test_lineage_sign_flags_ims_per_batch_and_data_moves_only_when_the_plan_is_done():
    key = copy.deepcopy(LINEAGE_KEY)
    w1, w2 = {"file": "A.cbl", "from": 5, "to": 16}, {"file": "A.cbl", "from": 35, "to": 46}
    key["sample_census"] = {"data_moves": {"plan": {"seed": 1, "windows": [w1, w2]}}}
    _, t1 = cs.render_lineage(key, REPO, ["A.cbl", "P.psb"], [w1], 1, 2)
    cs.sign(key, t1, cs.grade(t1, _lineage_answers(), REPO), {}, "rev", "2026-09-24")
    assert key["ims_gen"]["P.psb"]["ims_gen_validated"] is True
    assert key["data_moves"]["A.cbl"]["data_moves_validated"] is False  # one window still unsigned
    assert cs.coverage(key, [], "lineage")["missing"] == ["A.cbl@35-46"]
    _, t2 = cs.render_lineage(key, REPO, [], [w2], 2, 2)
    answers = {
        "windows": {"A.cbl@35-46": {"moves": [{"line": 40, "verb": "COMPUTE", "source": "WS-A", "target": "WS-T"}]}}
    }
    cs.sign(key, t2, cs.grade(t2, answers, REPO), {}, "rev", "2026-09-24")
    entry = key["data_moves"]["A.cbl"]
    assert entry["data_moves_validated"] is True and entry["verification"]["tier"] == "sample_verified"
    sc = key["sample_census"]["data_moves"]
    assert sc["asked"] == 4 and sc["key_errors"] == 0 and 0 < sc["upper_bound_95"] < 1
    assert cs.coverage(key, [], "lineage") == {"files": [2, 2], "wide": True, "missing": []}


def test_upper_bound_is_the_zero_failure_bound_and_grows_with_errors():
    assert cs.upper_bound_95(0, 100) == pytest.approx(0.0295, abs=1e-4)
    assert cs.upper_bound_95(0, 100) < cs.upper_bound_95(1, 100) < cs.upper_bound_95(5, 100)


# ---- the `layouts` suite (#3649 / #3602) ----------------------------------------
def _layouts_key(plan_modes: dict) -> dict:
    key = {
        "corpus": "k",
        "ref": "0" * 40,
        "programs": {},
        "copybook_layouts": {
            "C.cpy": {"units": ["REC/A @0+4", "REC/B @4+3"], "layouts_validated": False, "verification": {}},
            "D.cpy": {"units": ["D-REC/X @0+1"], "layouts_validated": False, "verification": {}},
        },
        "cics_ridflds": {
            "P.cbl": {
                "units": ["L9 READ FILE ACCTDAT RIDFLD=ACCT-KEY(1:8)", "L20 STARTBR FILE ? RIDFLD=K"],
                "ridflds_validated": False,
                "verification": {},
            },  # fmt: skip
        },
        "refmod_spans": {
            "P.cbl": {
                "units": ["L30 MOVE DFHCOMMAREA(1:LENGTH OF A) -> A"],
                "refmods_validated": False,
                "verification": {},
            },  # fmt: skip
        },
    }
    files = {"cblayout": ["C.cpy", "D.cpy"], "ridfld": ["P.cbl", "Q.cbl"], "refmod": ["P.cbl"]}
    key["sample_census"] = {"layouts": {"plan": {t: {"mode": plan_modes.get(t, "full"), "files": f}
                                                 for t, f in files.items()}}}  # fmt: skip
    return key


def _layouts_agreeing() -> dict:
    return {"files": {
        "C.cpy": {"cblayout": [{"root": "rec", "name": "a", "offset": 0, "bytes": 4},
                               {"root": "REC", "name": "B", "offset": 4, "bytes": 3}]},
        "D.cpy": {"cblayout": [{"root": "D-REC", "name": "X", "offset": 0, "bytes": 1}]},
        "P.cbl": {"ridfld": [{"line": 9, "verb": "READ", "file": "acctdat", "ridfld": "ACCT-KEY (1 : 8)"},
                             {"line": 20, "verb": "STARTBR", "file": None, "ridfld": "K"}],
                  "refmod": [{"line": 30, "verb": "MOVE", "source": "DFHCOMMAREA", "source_refmod": "1 : LENGTH OF A",
                              "target": "A", "target_refmod": None}]},
        "Q.cbl": {"ridfld": []},
    }}  # fmt: skip


def test_layouts_suite_is_blind_round_trips_and_lists_each_task_its_files():
    key = _layouts_key({})
    files = cs.corpus_files_layouts(key)
    assert files == ["C.cpy", "D.cpy", "P.cbl", "Q.cbl"]
    brief, truth = cs.render_layouts(key, REPO, files, 1, 1)
    assert "ACCT-KEY" not in brief and "@4+3" not in brief and "LENGTH OF A)" not in brief
    assert "Q.cbl" in brief.split("TASK ridfld")[1] and "Q.cbl" not in brief.split("TASK refmod")[1]
    assert truth["facts"]["ridfld"]["Q.cbl"] == []  # asked, keyed nothing: "none" is checked too
    assert "refmod" not in truth["facts"] or "C.cpy" not in truth["facts"]["refmod"]
    g = cs.grade(truth, _layouts_agreeing(), REPO)
    assert g["disagreements"] == [] and g["tasks"]["cblayout"] == {"agree": 3, "asked": 3}


def test_layouts_suite_lists_a_wrong_offset_both_ways():
    key = _layouts_key({})
    _, truth = cs.render_layouts(key, REPO, cs.corpus_files_layouts(key), 1, 1)
    answers = _layouts_agreeing()
    answers["files"]["C.cpy"]["cblayout"][1]["offset"] = 5
    ids = [d["id"] for d in cs.grade(truth, answers, REPO)["disagreements"]]
    assert ids == ["cblayout:C.cpy::REC/B @4+3", "cblayout:C.cpy::REC/B @5+3"]


def test_layouts_sign_flags_full_tasks_per_batch_and_a_sampled_task_when_its_plan_is_done():
    key = _layouts_key({"cblayout": "sample"})
    _, truth = cs.render_layouts(key, REPO, ["C.cpy", "P.cbl", "Q.cbl"], 1, 2)
    g = cs.grade(truth, _layouts_agreeing(), REPO)
    cs.sign(key, truth, g, {}, "reviewer", "2026-09-25")
    assert key["cics_ridflds"]["P.cbl"]["ridflds_validated"] is True  # full: flagged with its batch
    assert key["cics_ridflds"]["P.cbl"]["verification"]["tier"] == "cross_verified"
    assert key["copybook_layouts"]["C.cpy"]["layouts_validated"] is False  # sampled: D.cpy is still to come
    _, truth2 = cs.render_layouts(key, REPO, ["D.cpy"], 2, 2)
    cs.sign(key, truth2, cs.grade(truth2, _layouts_agreeing(), REPO), {}, "reviewer", "2026-09-25")
    entries = key["copybook_layouts"].values()
    assert all(e["layouts_validated"] and e["verification"]["tier"] == "sample_verified" for e in entries)
    sampled = key["sample_census"]["layouts"]["sampled"]["cblayout"]
    assert (sampled["asked"], sampled["key_errors"]) == (3, 0) and sampled["upper_bound_95"] > 0


def test_layouts_plan_is_full_while_small_and_sampled_with_recall_when_large(tmp_path):
    for n in range(40):
        (tmp_path / f"C{n:02d}.cpy").write_text("       01  R.\n           05 A PIC X(4).\n", encoding="utf-8")
    (tmp_path / "ROGUE.cpy").write_text("       01  R.\n           05 Z PIC 9.\n", encoding="utf-8")  # unkeyed
    small = {"copybook_layouts": {f"C{n:02d}.cpy": {"units": ["R/A @0+4"]} for n in range(40)}}
    plan = cs.layouts_plan(small, tmp_path, 7)
    assert plan["cblayout"] == {"mode": "full", "files": sorted([*small["copybook_layouts"], "ROGUE.cpy"])}
    big = {"copybook_layouts": {f"C{n:02d}.cpy": {"units": [f"R/A{i} @{i}+1" for i in range(20)]} for n in range(40)}}
    plan = cs.layouts_plan(big, tmp_path, 7)["cblayout"]
    assert plan["mode"] == "sample" and "ROGUE.cpy" in plan["files"]
    assert sum(len(big["copybook_layouts"].get(f, {}).get("units", [])) for f in plan["files"]) >= cs.LAYOUT_SAMPLE_ROWS
    assert plan == cs.layouts_plan(big, tmp_path, 7)["cblayout"]  # seeded: the same plan every time
