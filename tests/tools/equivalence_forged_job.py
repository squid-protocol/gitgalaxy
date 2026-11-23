"""#8886 slice 1: the FORGED Spring Batch job plan, compared step by step with the COBOL chain of a job case.

`equivalence_job.py` proves a chain of steps (the COBOL oracle against the ported Java, every output of every step).
This module asks the other half of #8886: does the job `BatchForge` GENERATES from the real JCL do what that chain did?
For each JCL job of a job case it

1. scans the corpus's JCL and PROC members and forges the job from the scan's own `job_steps` / `job_dds` rows (the
   facts `cobol_to_java_controller` hands the forge; nothing is mirrored here) and reads the generated `<Job>JobConfig` and `DDS_<STEP>` constants back;
2. replays the forged guard (`JclConditions.bypass / holds`, the Java the forge emits, compiled with javac, in the order
   and with the decision `JclSteps.guarded` makes) over the chain's own step return codes;
3. compares, per case step: the step order, run or bypass against ran / not reached in the chain, and the DD wiring
   (each `gdg_in` / `gdg_out` / `feeds` the case states against the forged `Dd(dd, dsn, disp, disp_normal, generation)`).

It does NOT run Spring: `JclSteps.guarded` is replayed, not executed (a later slice). A DD the JCL states only as a PROC
override (`//PROCSTEP.DD`) replaces the procedure's DD of that name: `galaxy_ir.job_dds` applies it (#8886: slice 1 found
it did not, and reported 7 of 9 steps equal), and this module now reads those rows instead of re-deriving the rule.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))  # before any gitgalaxy import: a shared venv may install another checkout

from gitgalaxy.tools.cobol_to_java import cobol_to_java_batch_forge as forge_mod  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.java_target import load_target  # noqa: E402

PKG = "com.gitgalaxy.batch"
# An RC the chain does not hold for a step IBM stopped on (ICE043A is a terminating DFSORT error). Only "not zero" and
# "above any COND limit the job states" matter to the CardDemo jobs; the value is an assumption, stated in the report.
STOP_RC = 16
UNMODELLED_RC = 0  # a JCL step the chain has no case for (IDCAMS DELETE/DEFINE, IEFBR14): assumed to end at 0

DRIVER = """package {pkg};

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.LinkedHashMap;
import java.util.Map;

/** Line: key TAB step|jobCond|cond|ifCond|given ... ; given is rc:N or - (no answer). */
public final class Drive {
    public static void main(String[] a) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        String line;
        while ((line = in.readLine()) != null) {
            String[] f = line.split("\\t");
            Map<String, Integer> rcs = new LinkedHashMap<>();
            StringBuilder out = new StringBuilder(f[0]);
            for (int i = 1; i < f.length; i++) {
                String[] p = f[i].split("\\\\|", -1);
                String name = p[0], jobCond = nul(p[1]), cond = nul(p[2]), ifCond = nul(p[3]), given = p[4];
                String action;
                if (JclConditions.bypass(jobCond, rcs) || JclConditions.bypass(cond, rcs)
                        || !JclConditions.holds(ifCond, rcs)) {
                    action = "bypass";
                } else {
                    if (!given.equals("-")) {
                        rcs.put(name, Integer.parseInt(given.substring(3)));
                    }
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

_CALL = re.compile(r'steps\.\w+\(("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*"|null), '
                   r'("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"|null)')  # fmt: skip
_DD = re.compile(r'new Dd\(("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"|null), '
                 r'("(?:[^"\\]|\\.)*"|null), ("(?:[^"\\]|\\.)*"|null)\)')  # fmt: skip
_CONST = re.compile(r"static final List<Dd> DDS_(\w+) = List\.of\((.*)\);")


def _unq(g: str) -> str | None:
    return None if g == "null" else json.loads(g)


# -- 1. forge the job from the real JCL --------------------------------------------------------------------------


def scan_estate(jcl_dir: Path, proc_dir: Path, work: Path):
    """A real scan of the corpus's JCL and PROC members (copied side by side under `work`): the `GalaxyIR` whose
    `job_steps()` / `job_dds()` rows the forge reads, as `cobol_to_java_controller` reads them (#8886 slice 2)."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    estate = work / "estate"
    for sub, src in (("jcl", jcl_dir), ("proc", proc_dir)):
        shutil.copytree(src, estate / sub)
    return load_galaxy_ir(scan_to_db(estate, work / "scan"))


def job_facts(ir, file: str) -> tuple[dict, list[dict], list[dict]]:
    """`(job_steps fact, job_dds facts, PROC override DD rows)` the scan holds for one JCL member `file`."""
    fact = next(f for f in ir.job_steps() if f["file"] == file)
    dds = [d for d in ir.job_dds() if d["file"] == file]
    # an override is a DD the job file itself states under a procedure step (`//PROCSTEP.DD`)
    overrides = [d for d in dds if d["proc_step"] and d["source"] == file]
    return fact, dds, overrides


def forge_job(fact: dict, dds: list[dict]) -> list[dict]:
    """Forge one job and read its generated config back: per step `name`, `job_cond`, `cond`, `if_cond`, `dds`."""
    progs = set()
    for s in fact["steps"]:
        for x in s.get("expands_to") or [s]:
            x["program"] = (x["program"] or s["proc"] or "STUB").upper()
            progs.add(x["program"])
        s["program"] = (s["program"] or s["proc"] or "STUB").upper()
        progs.add(s["program"])
    skeletons = {p: {"program": {"program_ids": [p], "file": f"cbl/{p}.cbl"}} for p in sorted(progs)}
    sections = {"job_steps": {"facts": [fact]}, "job_dds": {"facts": dds}}
    forge = BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))
    (src,) = forge.sources().values()
    (cfg,) = (t for k, t in src.items() if k.endswith("JobConfig"))
    consts: dict[str, list[dict]] = {}
    for ln in cfg.splitlines():
        m = _CONST.search(ln)
        if m:
            consts[m.group(1)] = [
                dict(zip(("dd", "dsn", "disp", "disp_normal", "generation"), map(_unq, d), strict=True))
                for d in _DD.findall(m.group(2))
            ]
    out = []
    for ln in cfg.splitlines():
        m = _CALL.search(ln)
        if m:
            name, jcl_, jc, c, i = (_unq(g) for g in m.groups())
            const = re.sub(r"\W", "_", jcl_ or name or "").upper()
            out.append({"name": name, "job_cond": jc, "cond": c, "if_cond": i, "dds": consts.get(const, [])})
    return out


# -- 2. replay the forged guard ----------------------------------------------------------------------------------


def _build_driver(work: Path) -> Path:
    pkg_dir = work / "src" / "com" / "gitgalaxy" / "batch"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "JclConditions.java").write_text(forge_mod._RUNTIME["JclConditions"].replace("{pkg}", PKG), "utf-8")
    (pkg_dir / "Drive.java").write_text(DRIVER.replace("{pkg}", PKG), "utf-8")
    out = work / "classes"
    out.mkdir()
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(out), *map(str, pkg_dir.glob("*.java"))],
                       capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    if r.returncode:
        raise RuntimeError(r.stderr)
    return out


def replay(classes: Path, lines: list[str]) -> list[dict[str, str]]:
    r = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), f"{PKG}.Drive"],
        input="\n".join(lines) + "\n", capture_output=True, text=True, encoding="utf-8",
    )  # fmt: skip
    if r.returncode:
        raise RuntimeError(r.stderr)
    return [dict(c.split("=", 1) for c in ln.split("\t")[1:]) for ln in r.stdout.splitlines()]


# -- 3. compare ---------------------------------------------------------------------------------------------------


def chain_rcs(report: dict) -> dict[str, int | None]:
    """The chain's RC per case step: the COBOL return code (the Java agrees where `ok`), an IDCAMS step's `rc`, the
    stop RC for the step IBM ended the job at, None where the chain holds no answer."""
    stop = (report.get("ibm_stop") or {}).get("step")
    out: dict[str, int | None] = {}
    for s in report["steps"]:
        if s["case"] == stop:
            out[s["case"]] = STOP_RC
        elif isinstance(s.get("return_code"), dict) and s["return_code"].get("cobol") is not None:
            out[s["case"]] = int(s["return_code"]["cobol"])
        elif s.get("rc") is not None and not s.get("model_only"):
            out[s["case"]] = int(s["rc"])
        else:
            out[s["case"]] = None
    return out


def _dd_by(forged_steps: list[dict], names: list[str], dd: str) -> dict | None:
    """The forged `Dd` a case DD name stands for: `NAME#2` is the 2nd DD of that name (a concatenation)."""
    nm, _, nth = dd.partition("#")
    hits = [d for s in forged_steps if s["name"] in names for d in s["dds"] if d["dd"] == nm]
    i = int(nth or 1) - 1
    return hits[i] if i < len(hits) else None


def compare(spec: dict, case: dict, report: dict, corpus: Path) -> dict:
    """The per-step comparison of a job case's chain with the forged jobs; see the module doc."""
    jcl_dir, proc_dir = corpus / spec["jcl_dir"], corpus / spec["proc_dir"]
    rcs = chain_rcs(report)
    ran = {s["case"] for s in case["steps"]} - set((report.get("ibm_stop") or {}).get("not_reached") or [])
    forged: dict[str, list[dict]] = {}
    overrides: dict[str, list[dict]] = {}
    by_case = {m["case"]: m for m in spec["steps"]}
    case_steps = {s["case"]: s for s in case["steps"]}
    # run each JCL job's forged guard over the chain's RCs
    work = Path(tempfile.mkdtemp(prefix="forged-job-"))
    try:
        ir = scan_estate(jcl_dir, proc_dir, work)
        for job, member in spec["jobs"].items():
            fact, dds, over = job_facts(ir, f"jcl/{member}")
            forged[job] = forge_job(fact, dds)
            overrides[job] = over
        classes = _build_driver(work)
        lines, keys = [], []
        for job, fsteps in forged.items():
            given: dict[str, str] = {}
            for m in spec["steps"]:
                if m["job"] != job:
                    continue
                rc = rcs.get(m["case"])
                for jn in m["jcl_steps"]:
                    given[jn] = "-" if rc is None else f"rc:{rc}"
            for jn in spec.get("unmodelled", {}).get(job, []):
                given[jn] = f"rc:{UNMODELLED_RC}"
            cells = [
                "|".join(
                    [s["name"], s["job_cond"] or "", s["cond"] or "", s["if_cond"] or "", given.get(s["name"], "-")]
                )
                for s in fsteps
            ]
            lines.append("\t".join([job, *cells]))
            keys.append(job)
        decided = dict(zip(keys, replay(classes, lines), strict=True))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rows = []
    for cname in (s["case"] for s in case["steps"]):
        m = by_case[cname]
        names = [s["name"] for s in forged[m["job"]]]
        issues: list[str] = []
        notes: list[str] = []
        missing = [j for j in m["jcl_steps"] if j not in names]
        if missing:
            issues.append(f"forged job {m['job']} has no step {missing}")
        pos = [names.index(j) for j in m["jcl_steps"] if j in names]
        if pos != sorted(pos):
            issues.append("forged step order differs from the case's")
        want = "run" if cname in ran else "bypass"
        got = {j: decided[m["job"]].get(j) for j in m["jcl_steps"]}
        for j, g in got.items():
            if g != want:
                issues.append(f"{j}: forged guard {g}, chain {'ran' if want == 'run' else 'did not reach it'}")
        # DD wiring
        cs = case_steps[cname]
        checks = 0
        for dd, base in (cs.get("gdg_out") or {}).items():
            checks += 1
            d = _dd_by(forged[m["job"]], m["jcl_steps"], m.get("dd_alias", {}).get(dd, dd))
            if d is None:
                issues.append(f"gdg_out {dd}: no forged DD {dd} (a PROC override DD the forge does not read)")
            elif d["dsn"] != base or d["generation"] != "+1":
                issues.append(f"gdg_out {dd}: forged {d['dsn']}({d['generation']}), case {base}(+1)")
        for dd, g in (cs.get("gdg_in") or {}).items():
            checks += 1
            d = _dd_by(forged[m["job"]], m["jcl_steps"], m.get("dd_alias", {}).get(dd, dd))
            if d is None:
                issues.append(f"gdg_in {dd}: no forged DD {dd}")
            elif d["dsn"] != g["base"] or d["generation"] != g["gen"]:
                issues.append(f"gdg_in {dd}: forged {d['dsn']}({d['generation']}), case {g['base']}({g['gen']})")
        for dd, src in (cs.get("feeds") or {}).items():
            pm = by_case[src["step"]]
            mine = _dd_by(forged[m["job"]], m["jcl_steps"], m.get("dd_alias", {}).get(dd, dd))
            theirs = _dd_by(forged[pm["job"]], pm["jcl_steps"], pm.get("dd_alias", {}).get(src["dd"], src["dd"]))
            if mine is None or theirs is None:
                side = f"{dd}" if mine is None else f"{src['step']}.{src['dd']}"
                notes.append(f"feeds {dd}: unchecked, no forged DD {side}")
                if theirs is None and mine is not None and pm["jcl_steps"]:
                    issues.append(f"feeds {dd}: producer DD {src['step']}.{src['dd']} is not in the forged plan")
            else:
                checks += 1
            if mine is not None and theirs is not None and mine["dsn"] != theirs["dsn"]:
                issues.append(f"feeds {dd}: forged {mine['dsn']} vs producer {theirs['dsn']}")
        rows.append(
            {"case": cname, "job": m["job"], "jcl_steps": m["jcl_steps"], "decision": got, "chain": want,
             "chain_rc": rcs.get(cname), "dd_checks": checks, "issues": issues, "notes": notes,
             "status": "differs" if issues else "equal"}
        )  # fmt: skip
    unmodelled = {j: [n for n in names if n in spec.get("unmodelled", {}).get(j, [])] for j, names in
                  ((j, [s["name"] for s in f]) for j, f in forged.items())}  # fmt: skip
    return {"rows": rows, "overrides": {j: o for j, o in overrides.items() if o},
            "unmodelled": {j: v for j, v in unmodelled.items() if v},
            "forged": {j: [{k: v for k, v in s.items() if k != "dds"} | {"dds": [d["dd"] for d in s["dds"]]} for s in f]
                       for j, f in forged.items()}}  # fmt: skip


def render(res: dict, case_name: str) -> list[str]:
    out = []
    for r in res["rows"]:
        tail = f" ({r['dd_checks']} DD checks)" if r["dd_checks"] else ""
        out.append(f"{case_name} forged step {r['case']} [{r['job']}.{'+'.join(r['jcl_steps'])}]: {r['status']}{tail}")
        out += [f"    differs: {i}" for i in r["issues"]]
        out += [f"    note: {n}" for n in r["notes"]]
    for j, v in res["unmodelled"].items():
        out.append(f"{case_name}: {j} steps the chain has no case for (assumed RC {UNMODELLED_RC}): {', '.join(v)}")
    n = sum(r["status"] == "equal" for r in res["rows"])
    out.append(f"{case_name}: forged jobs equal to the chain over {n} of {len(res['rows'])} steps "
               "(guard replayed, Spring not run)")  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True, type=Path, help="tests/equivalence/jobs/<case>.forged.json")
    ap.add_argument("--report", required=True, type=Path, help="the report.json of a `equivalence.py run <case>`")
    ap.add_argument(
        "--corpus", type=Path, help="the corpus root (default: spec's corpus under GITGALAXY_MAINFRAME_CORPORA)"
    )
    ap.add_argument("--json", type=Path, help="write the full result here")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    case = json.loads((REPO / "tests/equivalence/jobs" / f"{spec['case']}.json").read_text(encoding="utf-8"))
    report = json.loads(a.report.read_text(encoding="utf-8"))
    if a.corpus is None:
        import os

        a.corpus = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora")) / spec["corpus"]
    res = compare(spec, case, report, a.corpus)
    print("\n".join(render(res, spec["case"])))
    if a.json:
        a.json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 1 if any(r["status"] == "differs" for r in res["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main())
