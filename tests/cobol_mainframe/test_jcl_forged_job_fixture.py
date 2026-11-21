"""#4891 slice 2: the GENERATED Spring Batch jobs against the level fixture's IBM-written answers (FLOW + IFFLOW).

Slice 1 (`test_jcl_forged_job_carddemo.py`) ran CardDemo's 34 EXEC COND answers through what `BatchForge` emits. The
level fixture holds the shapes CardDemo does not use: EVEN / ONLY, IF / THEN / ELSE with NOT, nesting, `.RUN`,
ABEND / ABENDCC and procedure steps. `tests/equivalence/jcl/fixture/scenarios.json` (FLOW.jcl, 14) and
`ifflow_scenarios.json` (IFFLOW.jcl, 28) carry answers written from IBM's JCL Reference before any evaluator ran.

Each job is forged from the `job_steps` fact shape (a procedure call carries `expands_to`, as `galaxy_ir.job_steps`
writes it), read back, and decided by the forge's own `JclConditions` Java in the order `JclSteps.guarded` uses (the
driver and helpers are slice 1's). The forge documents that EVEN / ONLY and ABEND tests are not evaluated, so some
answers differ. `KNOWN_DIFFERENCES` names every one with its reason; the test fails on a new difference AND on a listed
one that no longer reproduces, so the list is the measurement, not an excuse.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_jcl_forged_job_carddemo as slice1  # noqa: E402

from gitgalaxy.core import job_flow  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests/equivalence/jcl/fixture"
SETS = [("FLOW.jcl", "scenarios.json"), ("IFFLOW.jcl", "ifflow_scenarios.json")]

# Slice 1's driver splits a step cell on `|`, which an IF expression uses (OR): the same driver, split on U+001F.
SEP = "\x1f"
DRIVER = slice1.DRIVER.replace('split("\\\\|", -1)', 'split("\\u001f", -1)')
assert DRIVER != slice1.DRIVER

needs_javac = pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")


ONLY = "COND=ONLY is not read (the forge's COND regex takes (code,op) tests only): the step runs after a clean step"
FLUSH = "an abend ends a Spring Batch job (the tasklet throws), so a step IBM runs after an abend (EVEN / ONLY / IF ABEND) never starts"
RUN = "`stepname.RUN` is not a relation the forge's IF parser reads: (and any `= value` after it) reads as true, so `.RUN = FALSE` and NOT `.RUN` come out inverted"
ABENDCC = (
    "`stepname.ABENDCC = code` ends the parse after the left token (the operator and code are not consumed): the whole "
    "expression reads as one false relation, so NOT (...) holds whatever RC is"
)
KNOWN_DIFFERENCES = {
    **dict.fromkeys(
        [("cond-all-zero", "S6"), ("cond-s1-rc6", "S6"), ("cond-s1-rc8", "S6"), ("even-only-rc0", "T3")], ONLY
    ),
    **dict.fromkeys(
        [
            ("cond-s1-abend", "S5"),
            ("cond-s1-abend", "S6"),
            ("cond-s3-abend", "S5"),
            ("cond-s3-abend", "S6"),
            ("even-only-abend", "T2"),
            ("even-only-abend", "T3"),
            ("if-i1-abend", "I5"),
            ("if-i2-abend", "I5"),
            ("abn-a1-u0012", "A4"),
            ("abn-a1-u0012", "A5"),
            ("abn-a2-s0c4", "A3"),
            ("abn-a2-s0c4", "A5"),
            ("prc6-u0012", "STEP2ERR"),
            ("prc6-other-abend", "NOERR"),
            ("mix-m1-abend", "M4"),
            ("mix-m1-abend", "M5"),
            ("mix-m2-abend", "M4"),
            ("mix-m2-abend", "M5"),
        ],
        FLUSH,
    ),  # fmt: skip
    **dict.fromkeys([("if-i1-rc4", "I6"), ("if-i1-rc12", "I6"), ("not-rc8", "T4"), ("not-rc11", "T4")], RUN),
    **dict.fromkeys([("abn-clean", "A7"), ("abn-a2-rc12", "A6")], ABENDCC),
}


def _jobs(member: str) -> dict[str, tuple[dict, list[dict]]]:
    """job -> (JOB row, the job_steps `steps` list): a PROC call carries `expands_to` its procedure's steps."""
    rows = job_flow.jcl_job_flow((FIXTURE / member).read_text(encoding="utf-8"))
    out: dict[str, tuple[dict, list[dict]]] = {}
    current: list[dict] = []
    for r in rows:
        if r["kind"] == "JOB":
            current = []
            out[r["name"]] = (r, current)
        elif r["kind"] == "STEP":
            current.append(r)
    result = {}
    for name, (job, srows) in out.items():
        steps = []
        for r in srows:
            if r["in_proc"]:
                continue
            e = {"ordinal": r["step_ordinal"], "step": r["step_name"]}
            e.update({k: r[k] for k in ("program", "proc", "cond", "if_cond", "line")})
            if r["proc"]:
                e["expands_to"] = [
                    {"step": s["step_name"], "program": s["program"], "cond": s["cond"], "if_cond": s["if_cond"]}
                    for s in srows
                    if s["in_proc"] == r["proc"]
                ]
            steps.append(e)
        result[name] = (job, steps)
    return result


def _forged() -> dict[str, list[dict]]:
    out = {}
    for member, _ in SETS:
        for name, (job, steps) in _jobs(member).items():
            for s in steps:  # every program gets an empty skeleton so the forge plans the job (slice 1)
                s["program"] = (s["program"] or s["proc"] or "STUB").upper()
                for p in s.get("expands_to", []):
                    p["program"] = (p["program"] or "STUB").upper()
            progs = sorted(
                {s["program"] for s in steps} | {p["program"] for s in steps for p in s.get("expands_to", [])}
            )
            skeletons = {p: {"program": {"program_ids": [p], "file": f"cbl/{p}.cbl"}} for p in progs}
            facts = [{"file": f"j/{member}", "job": name, "cond": job["cond"], "steps": steps}]
            forge = slice1.BatchForge(
                skeletons, {"sections": {"job_steps": {"facts": facts}}}, "com.gitgalaxy", slice1.load_target(None)
            )
            out[name] = slice1._forged_steps(forge)
    return out


@pytest.fixture(scope="module")
def decided(tmp_path_factory) -> dict[str, dict[str, str]]:
    d = tmp_path_factory.mktemp("jclfix")
    pkg_dir = d / "src" / "com" / "gitgalaxy" / "batch"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "JclConditions.java").write_text(
        slice1.forge_mod._RUNTIME["JclConditions"].replace("{pkg}", slice1.PKG), "utf-8"
    )
    (pkg_dir / "Drive.java").write_text(DRIVER.replace("{pkg}", slice1.PKG), "utf-8")
    classes = d / "classes"
    classes.mkdir()
    r = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(classes), *map(str, pkg_dir.glob("*.java"))],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    forged = _forged()
    lines = [_line(sc["id"], forged[sc["job"]], sc["given"]) for _, sc in _scenarios()]
    return {row[0]: dict(c.split("=") for c in row[1:]) for row in slice1._drive(classes, lines)}


def _scenarios() -> list[tuple[str, dict]]:
    return [(m, sc) for m, f in SETS for sc in json.loads((FIXTURE / f).read_text(encoding="utf-8"))["scenarios"]]


def _line(key: str, forged: list[dict], given: dict) -> str:
    cells = []
    for s in forged:
        g = given.get(s["name"])
        gv = "-" if g is None else "abend" if "abend" in g else f"rc:{g['rc']}"
        cells.append(SEP.join([s["name"], s["job_cond"] or "", s["cond"] or "", s["if_cond"] or "", gv]))
    return "\t".join([key, *cells])


@needs_javac
def test_the_forged_job_plans_the_steps_the_answers_name_in_order():
    forged = _forged()
    for _, sc in _scenarios():
        assert [x["name"] for x in forged[sc["job"]]] == list(sc["expect"]), sc["id"]


@needs_javac
def test_the_forged_job_differs_from_the_ibm_written_answers_exactly_where_the_list_says(decided):
    got = {
        (sc["id"], step): (decided[sc["id"]][step], want)
        for _, sc in _scenarios()
        for step, want in sc["expect"].items()
        if decided[sc["id"]][step] != want
    }
    # every difference is a step the forge ran that IBM bypasses, or one it bypassed that IBM runs; never anything else
    assert {v for v in got.values()} <= {("run-without-answer", "bypass"), ("bypass", "run")}
    assert set(got) == set(KNOWN_DIFFERENCES), sorted(set(got) ^ set(KNOWN_DIFFERENCES))
    scenarios = {i for i, _ in got}
    assert (len(_scenarios()), len(scenarios), len(got)) == (42, 21, 28)
