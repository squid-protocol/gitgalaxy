"""#4891 slice 1: the GENERATED Spring Batch jobs against the IBM-written JCL answer key (CardDemo).

`tests/equivalence/jcl/carddemo/scenarios.json` holds, per CardDemo job with an EXEC COND, 34 run / bypass answers
written from IBM's JCL Reference before any evaluator ran (`test_jcl_flow_carddemo_case.py` proves `JclFlow` on them).
This file proves the OTHER implementation of the same rules: what `BatchForge` emits. For each job the forge plans the
steps from the real `job_flow` rows (the `job_steps` fact shape of `galaxy_ir.job_steps`), and the test reads the forged
`<Job>JobConfig` back: its step order and the (job COND, COND, IF) strings each `steps.*(...)` call carries. Those go,
with each scenario's forced return codes, through the forge's own `JclConditions` Java (compiled with javac, the
`_RUNTIME["JclConditions"]` text) in the order and with the exact decision `JclSteps.guarded` makes. An abend ends a
Spring Batch job (the tasklet throws), so no later step starts: that is JCL's flush because no CardDemo COND says
EVEN or ONLY.

Stand-ins: the forge only generates a job when a step runs a program of the estate, so every program a job names gets
an empty skeleton (a step then forges as `steps.program`; the COND text and the order do not depend on that).
Not covered, named in the PR: the Spring `JclSteps.guarded` body is pinned by text, not run (needs the Spring jars);
DD binding, the step's own RC production and job-level exit status are later slices.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.source_text import read_source
from gitgalaxy.tools.cobol_to_java import cobol_to_java_batch_forge as forge_mod
from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.java_target import load_target

REPO = Path(__file__).resolve().parents[2]
DOC = json.loads((REPO / "tests/equivalence/jcl/carddemo/scenarios.json").read_text(encoding="utf-8"))
CORPUS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora")) / DOC["corpus"]
SCENARIOS = [(j["job"], s) for j in DOC["jobs"] for s in j["scenarios"]]
PKG = "com.gitgalaxy.batch"

needs_corpus = pytest.mark.skipif(not CORPUS.is_dir(), reason="the CardDemo corpus is not checked out")
needs_javac = pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")

DRIVER = """package {pkg};

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.LinkedHashMap;
import java.util.Map;

/** Line: key TAB step|jobCond|cond|ifCond|given ... ; given is rc:N, abend or - (never started). */
public final class Drive {
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        String line;
        while ((line = in.readLine()) != null) {
            String[] f = line.split("\\t");
            Map<String, Integer> rcs = new LinkedHashMap<>();
            boolean abended = false;
            StringBuilder out = new StringBuilder(f[0]);
            for (int i = 1; i < f.length; i++) {
                String[] p = f[i].split("\\\\|", -1);
                String name = p[0], jobCond = nul(p[1]), cond = nul(p[2]), ifCond = nul(p[3]), given = p[4];
                String action;
                if (abended || JclConditions.bypass(jobCond, rcs) || JclConditions.bypass(cond, rcs)
                        || !JclConditions.holds(ifCond, rcs)) {
                    action = "bypass";
                } else if (given.equals("-")) {
                    action = "run-without-answer";
                } else if (given.equals("abend")) {
                    abended = true;
                    action = "run";
                } else {
                    rcs.put(name, Integer.parseInt(given.substring(3)));
                    action = "run";
                }
                out.append('\\t').append(name).append('=').append(action);
            }
            System.out.println(out);
        }
    }

    private static String nul(String s) {
        return s.isEmpty() ? null : s;
    }
}
"""


def _steps_of(member: str) -> tuple[dict, list[dict]]:
    rows = job_flow.jcl_job_flow(read_source(CORPUS / member).text)
    job = next(r for r in rows if r["kind"] == "JOB")
    steps = [
        {
            "ordinal": r["step_ordinal"],
            "step": r["step_name"],
            "program": r["program"],
            "proc": r["proc"],
            "cond": r["cond"],
            "if_cond": r["if_cond"],
            "line": r["line"],
        }
        for r in rows
        if r["kind"] == "STEP"
    ]
    return job, steps


def _forge(file: str, name: str, cond: str | None, steps: list[dict]) -> BatchForge:
    progs = sorted({(s["program"] or s["proc"] or "STUB").upper() for s in steps})
    for s in steps:
        s["program"] = (s["program"] or s["proc"] or "STUB").upper()
    skeletons = {p: {"program": {"program_ids": [p], "file": f"cbl/{p}.cbl"}} for p in progs}
    sections = {"job_steps": {"facts": [{"file": file, "job": name, "cond": cond, "steps": steps}]}}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


_CALL = re.compile(r'steps\.\w+\(("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*"|null), '
                   r'("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"|null)')  # fmt: skip


def _forged_steps(forge: BatchForge) -> list[dict]:
    """Read the generated job config back: each step's name, job COND, COND and IF, in the order it is chained."""
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    out = []
    for ln in cfg.splitlines():
        m = _CALL.search(ln)
        if m:
            name, _jcl, jc, c, i = (None if g == "null" else json.loads(g) for g in m.groups())
            out.append({"name": name, "job_cond": jc, "cond": c, "if_cond": i})
    chain = [ln.strip() for ln in cfg.splitlines() if ln.strip().startswith((".start(", ".next("))]
    assert [re.search(r'StepBuilder\("([^"]+)"', c).group(1) for c in chain] == [s["name"] for s in out]  # type: ignore[union-attr]
    return out


@pytest.fixture(scope="module")
def conditions_class(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("jclcond")
    pkg_dir = d / "src" / "com" / "gitgalaxy" / "batch"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "JclConditions.java").write_text(forge_mod._RUNTIME["JclConditions"].replace("{pkg}", PKG), "utf-8")
    (pkg_dir / "Drive.java").write_text(DRIVER.replace("{pkg}", PKG), "utf-8")
    out = d / "classes"
    out.mkdir()
    r = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(out), *map(str, pkg_dir.glob("*.java"))],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    return out


def _drive(classes: Path, lines: list[str]) -> list[list[str]]:
    r = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), f"{PKG}.Drive"],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    return [ln.split("\t") for ln in r.stdout.splitlines()]


def _line(key: str, forged: list[dict], given: dict) -> str:
    cells = []
    for s in forged:
        g = given.get(s["name"])
        gv = "-" if g is None else "abend" if "abend" in g else f"rc:{g['rc']}"
        cells.append("|".join([s["name"], s["job_cond"] or "", s["cond"] or "", s["if_cond"] or "", gv]))
    return "\t".join([key, *cells])


def test_the_forge_guard_is_the_one_the_driver_mirrors():
    """The driver restates `JclSteps.guarded`'s decision; pin that text so a change to it fails here, not silently."""
    guarded = forge_mod._RUNTIME["JclSteps"]
    assert (
        "if (JclConditions.bypass(jobCond, rcs) || JclConditions.bypass(cond, rcs)\n"
        "                    || !JclConditions.holds(ifCond, rcs)) {" in guarded
    )
    assert "rcs.put(jcl, rc);" in guarded and 'new ExitStatus("BYPASSED")' in guarded


def test_a_synthetic_job_forges_its_steps_in_order_with_each_cond():
    steps = [
        {"ordinal": i, "step": n, "program": "P", "proc": None, "cond": c, "if_cond": None, "line": i}
        for i, (n, c) in enumerate([("S1", None), ("S2", "(0,NE)"), ("S3", "(4,LT,S1)")], 1)
    ]
    got = _forged_steps(_forge("j/X.jcl", "X", "(8,LE)", steps))
    assert got == [
        {"name": "S1", "job_cond": "(8,LE)", "cond": None, "if_cond": None},
        {"name": "S2", "job_cond": "(8,LE)", "cond": "(0,NE)", "if_cond": None},
        {"name": "S3", "job_cond": "(8,LE)", "cond": "(4,LT,S1)", "if_cond": None},
    ]


@needs_corpus
def test_the_forge_plans_every_answer_key_job_with_the_answer_keys_steps():
    for j in DOC["jobs"]:
        assert hashlib.sha256((CORPUS / j["member"]).read_bytes()).hexdigest() == j["sha256"], j["member"]
        job, steps = _steps_of(j["member"])
        forge = _forge(j["member"], job["name"], job["cond"], steps)
        assert [a.job for a in forge.applications] == [j["job"]], j["job"]
        assert [s["name"] for s in _forged_steps(forge)] == j["steps"], j["job"]


@needs_corpus
@needs_javac
def test_every_scenario_the_forged_job_agrees_with_the_ibm_written_answer(conditions_class):
    forged: dict[str, list[dict]] = {}
    for j in DOC["jobs"]:
        job, steps = _steps_of(j["member"])
        forged[j["job"]] = _forged_steps(_forge(j["member"], job["name"], job["cond"], steps))
    lines = [_line(f"{job}/{s['id']}", forged[job], s["given"]) for job, s in SCENARIOS]
    got = {row[0]: dict(c.split("=") for c in row[1:]) for row in _drive(conditions_class, lines)}
    wrong = {
        key: (got[key], s["expect"])
        for (job, s), key in zip(SCENARIOS, (f"{j}/{s['id']}" for j, s in SCENARIOS), strict=True)
        if got[key] != s["expect"]
    }
    assert len(got) == len(SCENARIOS) == 34
    assert not wrong, json.dumps(wrong, indent=1)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
