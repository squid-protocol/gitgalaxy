#!/usr/bin/env python3
"""More third-party CardDemo ports run through our equivalence harness: Lightyear and SENTINEL IDE.

    python tests/tools/thirdparty_port.py --work DIR [--port lightyear,sentinel,devin] [--program CBACT04C,...]
                                          [--environments all|default,...] [--external-faults] [--jdk21 PATH]

The pattern of #4177 (IBM) and #4190 (Devin, tests/tools/devin_port.py): each port is fetched at a pinned commit
(neither repository carries a licence: nothing of theirs is committed here), built as it ships, run on the inputs
one of our proven cases gives GnuCOBOL, and judged by the harness's own comparison (equivalence.compare_run).
Results: docs/research/third-party-ports-harness.md.

The adapter -- this file and tests/tools/thirdparty/adapter -- and nothing more:
  - inputs: the case's input data sets as text, one record per line (both ports read lines: Lightyear with
    Files.readAllLines, SENTINEL with BufferedReader.readLine) -- the same bytes GnuCOBOL is given, an indexed one
    in primary-key order as a KSDS unloads, each record followed by a newline;
  - outputs: the lines the port wrote, each of the record's fixed length, concatenated back into fixed records
    (`records_from_lines` refuses a line of any other length); an indexed output in primary-key order (a KSDS is
    read back in key order whatever order it was written in);
  - launching: Lightyear's Spring Boot jar with its documented `--carddemo.*` properties; SENTINEL's program
    classes (no main method) constructed with their String file paths and PARM and execute() called, as its own
    unit tests do (thirdparty/adapter/tpadapter/ProgramLauncher.java), with logback set to message-only on stdout
    so its log lines (its DISPLAYs) read as the job log;
  - the JVM default locale and time zone of each harness environment (#3821);
  - an abend as the port reports it (SENTINEL: an exception carrying "ABCODE n"), recorded as the harness's Unnnn.
Not applied: the case's injected fault runs (no I/O seam in either port). Instead, with --external-faults, each
case fault that is an OPEN of an input data set failing with status 35 ("file not present") is reproduced from
outside -- the port runs with that input file absent -- and compared with the COBOL fault run.

Comparison tiers, reported separately:
  - `full`: compare_run as for our own ports (RETURN-CODE or ABEND, every compared data set field by field, SYSOUT);
  - `data`: the same without SYSOUT (Lightyear writes a JSON receipt and Spring's log, not the COBOL DISPLAYs);
  - `clock-masked`: `data`, after a port that reads the wall clock (no clock seam) has its run-time timestamp
    fields set to the COBOL side's -- only where the port's value is a DB2-format timestamp within a day of the
    run (oracle_assumptions.md M4's rule for clock fields).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path[:0] = [str(TOOLS), str(REPO_ROOT)]
import devin_port as dp  # noqa: E402
import equivalence as eq  # noqa: E402
import equivalence_java as ej  # noqa: E402
import mainframe_corpus as mc  # noqa: E402
from equivalence_common import _fixed, _input_path, sysout_lines  # noqa: E402

from gitgalaxy.core.source_text import decode_bytes  # noqa: E402
import subprocess  # noqa: F401 -- kept (#4496)

ADAPTER = TOOLS / "thirdparty" / "adapter"
LOGBACK = ADAPTER / "logback-message-only.xml"
LIGHTYEAR_JAR = "candidate-java/target/carddemo-spring-batch-candidate-0.1.0-SNAPSHOT.jar"

PORTS: dict[str, dict[str, Any]] = {
    "lightyear": {
        "repo": "https://github.com/howardweale/lightyear-carddemo-modernization",
        "sha": "e24d77822f7097dea3b1207026a55a95d8e6060f", "sparse": ["candidate-java"],
        "about": "Lightyear's Spring Batch candidate for CBACT04C (candidate-java/)",
        "build": ("jar", "candidate-java", LIGHTYEAR_JAR),
        "programs": {"CBACT04C": {"case": "carddemo-intcalc", "files": {
            "TCATBALF": "tcatbal.txt", "DISCGRP": "discgrp.txt", "XREFFILE": "cardxref.txt",
            "ACCTFILE": "acctdata.txt", "TRANSACT": "transactions.txt"}}},
    },
    "sentinel": {
        "repo": "https://github.com/noahlabsai/aws-mainframe-modernization-carddemo-JAVA",
        "sha": "47af18641ee602e072128c04bae4db78c4ac8ec5",
        "about": "SENTINEL IDE by NOAH Labs: CardDemo, one Java class per COBOL program",
        # the project as shipped does not compile (18 errors, all in three files no batch program uses:
        # screen/MainMenuScreenController, config/BatchConfig, screen/SessionCommArea); the program classes are
        # compiled as they are, with javac -sourcepath pulling in only what they reference (`build_programs`)
        "build": ("programs", ".", None),
        # each program: our case, and its constructor's arguments in order ({DD}: the data set's file, PARM)
        "programs": {
            "CBACT02C": {"case": "carddemo-readcard", "args": ["CARDFILE"]},
            "CBACT03C": {"case": "carddemo-readxref", "args": ["XREFFILE"]},
            "CBCUS01C": {"case": "carddemo-readcust", "args": ["CUSTFILE"]},
            "CBACT04C": {"case": "carddemo-intcalc",
                         "args": ["TCATBALF", "XREFFILE", "DISCGRP", "ACCTFILE", "TRANSACT", "PARM"],
                         "clock_fields": {"TRANSACT": ["TRAN-ORIG-TS", "TRAN-PROC-TS"]}},
            "CBTRN02C": {"case": "carddemo-posttran",
                         "args": ["DALYTRAN", "TRANFILE", "XREFFILE", "DALYREJS", "ACCTFILE", "TCATBALF"],
                         "clock_fields": {"TRANFILE": ["TRAN-PROC-TS"]}},
        },
    },
}  # fmt: skip

# What was looked at and not run, and why (reported with the results).
SKIPPED = {
    ("sentinel", "CBTRN01C"): "its constructor takes SeqFileReader / IndexedFileReader interfaces (records as "
    "Map<String,Object>) and the port ships no implementation; supplying one means writing its file I/O and "
    "record decoding -- translation work, not an adapter",
    ("sentinel", "CBTRN03C"): "the same: SeqFileReader / IndexedFileReader / ReportWriter interfaces, no "
    "implementation shipped",
    ("sentinel", "COBTUPDT"): "the Db2 program: its port uses Spring Data JPA against the app's own schema; not "
    "attempted in this pass",
    ("lightyear", "COACTVWC"): "CicsVsamAccountViewService is a read-only lookup service with no CICS task, "
    "COMMAREA or BMS map; our case compares the screen and COMMAREA a CICS task produces, so an adapter would have "
    "to write the screen logic -- not a fair or thin adapter",
}


# ---- fetch and build ----------------------------------------------------------------------------------------------
def fetch(port: dict[str, Any], work: Path) -> Path:
    """The port's repository at its pinned commit; a sparse checkout of `sparse` paths when given."""
    tree = work / "src" / port["sha"][:12]
    if (tree / ".git").exists():
        return tree
    tree.parent.mkdir(parents=True, exist_ok=True)
    p = dp.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", port["repo"], str(tree)])
    if p.returncode:
        raise RuntimeError(f"git clone {port['repo']}: {decode_bytes(p.stderr)}")
    if port.get("sparse"):
        dp.run(["git", "-C", str(tree), "sparse-checkout", "set", "--cone", *port["sparse"]])
    p = dp.run(["git", "-C", str(tree), "checkout", "-q", port["sha"]])
    if p.returncode:
        raise RuntimeError(f"checkout {port['sha']}: {decode_bytes(p.stderr)}")
    return tree


def build_programs(port: dict[str, Any], tree: Path, work: Path) -> str:
    """The port's program classes compiled as they are -- `javac -sourcepath` compiles each named class and only
    the sources it references -- against the project's declared dependencies; returns the classpath."""
    cpf = tree / "target" / "gg-classpath.txt"
    out = tree / "target" / "gg-programs"
    if not out.is_dir():
        p = dp.run(["mvn", "-q", "-B", f"-Dmaven.repo.local={work / 'm2'}", "dependency:build-classpath",
                    f"-Dmdep.outputFile={cpf}"], cwd=tree)  # fmt: skip
        if p.returncode:
            raise RuntimeError(f"dependency classpath:\n{decode_bytes(p.stdout)[-2000:]}")
        deps = cpf.read_text(encoding="utf-8").strip()
        out.mkdir(parents=True)
        sources = [str(tree / "src/main/java/com/cardemo/cbl" / f"{name}.java") for name in port["programs"]]
        p = dp.run([dp.tool(None, "javac"), "--release", "17", "-proc:none", "-encoding", "UTF-8", "-d", str(out),
                    "-cp", deps, "-sourcepath", str(tree / "src/main/java"), *sources])  # fmt: skip
        if p.returncode:
            raise RuntimeError(f"javac:\n{decode_bytes(p.stderr)[-2000:]}")
    return f"{out}:{cpf.read_text(encoding='utf-8').strip()}"


def adapter_classes(work: Path, classpath: str) -> Path:
    out = work / "tpadapter-classes"
    if not (out / "tpadapter" / "ProgramLauncher.class").is_file():
        out.mkdir(parents=True, exist_ok=True)
        p = dp.run([dp.tool(None, "javac"), "--release", "17", "-d", str(out),
                    *map(str, ADAPTER.rglob("*.java"))])  # fmt: skip
        if p.returncode:
            raise RuntimeError(decode_bytes(p.stderr))
    return out


# ---- the records, as lines ------------------------------------------------------------------------------------------
def lines_from_records(data: bytes, reclen: int) -> bytes:
    """Fixed records as text lines: each record, then a newline."""
    if len(data) % reclen:
        raise ValueError(f"{len(data)} bytes is not a whole number of {reclen}-byte records")
    return b"".join(data[i : i + reclen] + b"\n" for i in range(0, len(data), reclen))


def records_from_lines(text: bytes, reclen: int) -> bytes:
    """The lines a port wrote back as fixed records. A CRLF ending is taken as the newline; a line of any length
    but the record's is refused (it is not the record, and padding or cutting it would hide that)."""
    out = []
    for n, line in enumerate(text.split(b"\n"), 1):
        line = line[:-1] if line.endswith(b"\r") else line
        if not line and n == text.count(b"\n") + 1:
            continue
        if len(line) != reclen:
            raise ValueError(f"line {n}: {len(line)} bytes, the record is {reclen}")
        out.append(line)
    return b"".join(out)


def stage(case: dict[str, Any], corpus: Path, into: Path, names: dict[str, str] | None = None,
          absent: str | None = None) -> dict[str, Path]:  # fmt: skip
    """{DD: file}: each input as text lines (an indexed one in key order); an output, no file. `names`: the file
    name a port expects per DD; `absent`: an input left out (an external fault)."""
    into.mkdir(parents=True, exist_ok=True)
    dds = {}
    for dd, spec in case["datasets"].items():
        f = into / ((names or {}).get(dd) or f"{dd}.txt")
        dds[dd] = f
        if "input" not in spec or dd == absent:
            continue
        data = _fixed(_input_path(case, corpus, spec["input"]), spec["reclen"], "latin-1")
        if spec.get("organization") == "indexed":
            data = dp.key_ordered(data, spec["reclen"], spec["keys"][0])
        f.write_bytes(lines_from_records(data, spec["reclen"]))
    return dds


def read_outputs(
    case: dict[str, Any], files: dict[str, Path], fallback: dict[str, Path] | None = None
) -> dict[str, bytes]:
    """Every compared data set back as fixed records ({} entries for a file the port never wrote). `fallback`: where
    an in-place data set lives when the port publishes nothing (Lightyear's all-or-nothing output: an account
    master it did not publish is the one it was given)."""
    outs = {}
    for dd, spec in case["datasets"].items():
        if not spec.get("compare"):
            continue
        f = files[dd] if files[dd].is_file() else (fallback or {}).get(dd)
        try:
            data = records_from_lines(f.read_bytes(), spec["reclen"]) if f and f.is_file() else b""
        except ValueError as e:  # a line that is not the record: compared as written (newlines dropped), noted
            data = f.read_bytes().replace(b"\r\n", b"").replace(b"\n", b"")
            outs[f"NOTE {dd}"] = f"record framing: {e}".encode()
            outs[dd] = data
            continue
        if data and spec.get("organization") == "indexed":
            data = dp.key_ordered(data, spec["reclen"], spec["keys"][0])
        outs[dd] = data
    return outs


# ---- clock fields -----------------------------------------------------------------------------------------------------
DB2_TS = re.compile(rb"\d{4}-\d\d-\d\d-\d\d\.\d\d\.\d\d\.\d{6}")


def mask_clock(case: dict[str, Any], corpus: Path, cobol: dict[str, bytes], java: dict[str, bytes],
               fields: dict[str, list[str]], ran_at: datetime) -> tuple[dict[str, bytes], int]:  # fmt: skip
    """java with each named clock field set to the COBOL side's, record by record -- only where the port's value is
    a DB2-format timestamp within a day of `ran_at` (a time the run itself wrote). Returns it and the fields masked."""
    out, masked = dict(java), 0
    for dd, names in fields.items():
        spec = case["datasets"][dd]
        n = spec["reclen"]
        layout = {f["name"]: f for f in eq.layout_fields(corpus, spec["copybook"], spec.get("record"))}
        a, b = cobol.get(dd, b""), bytearray(java.get(dd, b""))
        for r in range(0, min(len(a), len(b)) // n):
            for name in names:
                f = layout[name]
                lo, hi = r * n + f["offset"], r * n + f["offset"] + f["bytes"]
                value = bytes(b[lo:hi])
                if not DB2_TS.fullmatch(value):
                    continue
                when = datetime.strptime(value.decode()[:19], "%Y-%m-%d-%H.%M.%S")
                if abs(when - ran_at) <= timedelta(days=1):
                    b[lo:hi] = a[lo:hi]
                    masked += 1
        out[dd] = bytes(b)
    return out, masked


# ---- running a port -----------------------------------------------------------------------------------------------------
def run_lightyear(port: dict[str, Any], prog: dict[str, Any], case: dict[str, Any], corpus: Path, tree: Path,
                  run_dir: Path, env: dict[str, str], absent: str | None, work: Path) -> tuple[dict[str, bytes], Any]:  # fmt: skip
    names = prog["files"]
    inputs = stage(case, corpus, run_dir / "in", names, absent)
    outdir = run_dir / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    clock = datetime.strptime(case["clock"][:19], "%Y/%m/%d %H:%M:%S")
    launcher = dp.adapter_classes(work, None)  # Devin's EnvLauncher: locale and time zone, then their main
    argv = [dp.tool(None, "java"), "-cp", f"{launcher}:{tree / LIGHTYEAR_JAR}", "devinadapter.EnvLauncher",
            env["locale"], env["tz"], "org.springframework.boot.loader.launch.JarLauncher",
            f"--carddemo.input-dir={run_dir / 'in'}", f"--carddemo.output-dir={outdir}",
            f"--carddemo.processing-date={case['parm']}",
            f"--carddemo.timestamp={clock.strftime('%Y-%m-%d-%H.%M.%S')}.000000"]  # fmt: skip
    proc = dp.run(argv, cwd=run_dir, timeout=600)
    outs = read_outputs(case, {dd: outdir / names[dd] for dd in names}, fallback=inputs)
    outs["SYSOUT"] = b""  # Lightyear writes Spring's log and a JSON receipt, not the COBOL DISPLAYs
    outs["RETURN-CODE"] = str(proc.returncode).encode()
    return outs, proc


def run_sentinel(port: dict[str, Any], prog: dict[str, Any], case: dict[str, Any], corpus: Path, classpath: str,
                 run_dir: Path, env: dict[str, str], absent: str | None, work: Path, program: str) -> tuple[dict[str, bytes], Any]:  # fmt: skip
    dds = stage(case, corpus, run_dir, None, absent)
    args = [case["parm"] if a == "PARM" else str(dds[a]) for a in prog["args"]]
    launcher = adapter_classes(work, classpath)
    argv = [dp.tool(None, "java"), "-cp", f"{launcher}:{classpath}", "tpadapter.ProgramLauncher", env["locale"],
            env["tz"], str(LOGBACK), f"com.cardemo.cbl.{program}", *args]  # fmt: skip
    proc = dp.run(argv, cwd=run_dir, timeout=600)
    outs = read_outputs(case, dds)
    outs["SYSOUT"] = proc.stdout
    m = re.search(rb"USER ABEND U(\d+)", proc.stderr)
    if m:
        outs["ABEND"] = f"U{int(m.group(1)) % 4096:04d}".encode()
    else:
        outs["RETURN-CODE"] = str(proc.returncode).encode()
    return outs, proc


def verdicts(case: dict[str, Any], corpus: Path, cobol: dict[str, bytes], java: dict[str, bytes],
             clock_fields: dict[str, list[str]] | None, ran_at: datetime) -> dict[str, Any]:  # fmt: skip
    full = eq.compare_run(case, corpus, cobol, java)
    data = eq.compare_run({**case, "sysout": False}, corpus, cobol, java)
    out = {"full": {"ok": full["ok"], "summary": full["summary"], "first": dp.first_difference(full)},
           "data": {"ok": data["ok"], "summary": data["summary"], "first": dp.first_difference(data)},
           "sysout": {k: full.get("sysout", {}).get(k) for k in ("lines", "equal", "compared")},
           "abend": full["abend"], "return_code": full["return_code"],
           "notes": {k[5:]: decode_bytes(v) for k, v in java.items() if k.startswith("NOTE ")}}  # fmt: skip
    if clock_fields:
        masked_java, n = mask_clock(case, corpus, cobol, java, clock_fields, ran_at)
        m = eq.compare_run({**case, "sysout": False}, corpus, cobol, masked_java)
        out["clock-masked"] = {"ok": m["ok"], "summary": m["summary"], "first": dp.first_difference(m),
                               "fields_masked": n}  # fmt: skip
    return out


def external_faults(case: dict[str, Any]) -> list[dict[str, Any]]:
    """The case's fault runs that are an input data set's OPEN failing with status 35 ("not present")."""
    out = []
    for f in case.get("faults", []):
        plan = f["plan"]
        if len(plan) == 1 and plan[0]["op"] == "OPEN" and plan[0]["status"] == "35" and \
                "input" in case["datasets"].get(plan[0]["dd"], {}):  # fmt: skip
            out.append(f)
    return out


def judge(name: str, program: str, work: Path, envs: list[str], with_faults: bool) -> dict[str, Any]:
    port = PORTS[name]
    prog = port["programs"][program]
    case = eq.load_case(prog["case"])
    (entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(entry)
    cobol_dir = work / "cobol" / prog["case"]
    cobol = eq.run_cobol(case, corpus, cobol_dir)
    coverage = eq.cobol_coverage(case, corpus, [cobol_dir / eq.cov.TRACE_NAME], work / f"{prog['case']}-coverage.json")
    result: dict[str, Any] = {"port": name, "sha": port["sha"], "program": program, "case": prog["case"],
                              "coverage": coverage, "runs": [], "external_faults": []}  # fmt: skip
    try:
        tree = fetch(port, work)
        classpath = (
            build_programs(port, tree, work) if port["build"][0] == "programs" else dp.build(port, tree, work, None)
        )
    except RuntimeError as e:
        result["build_error"] = str(e)[:2000]
        return result

    def one(env_name: str, run_dir: Path, absent: str | None) -> tuple[dict[str, bytes], Any, datetime]:
        env = ej.environment(env_name)
        ran_at = datetime.now()
        if name == "lightyear":
            java, proc = run_lightyear(port, prog, case, corpus, tree, run_dir, env, absent, work)
        else:
            java, proc = run_sentinel(port, prog, case, corpus, classpath, run_dir, env, absent, work, program)
        (run_dir / "stdout.txt").write_bytes(proc.stdout)
        (run_dir / "stderr.txt").write_bytes(proc.stderr)
        return java, proc, ran_at

    base = work / "runs" / name / program
    for env_name in envs:
        java, proc, ran_at = one(env_name, base / env_name, None)
        v = verdicts(case, corpus, cobol, java, prog.get("clock_fields"), ran_at)
        result["runs"].append({"environment": env_name, **v, "stderr": decode_bytes(proc.stderr)[-600:],
                               "sysout_classes": dp.sysout_classes(case, cobol.get("SYSOUT", b""), java["SYSOUT"])})  # fmt: skip
    if with_faults:
        for f in external_faults(case):
            dd = f["plan"][0]["dd"]
            cobol_f = eq.run_cobol(case, corpus, work / "cobol" / f"{prog['case']}-{f['name']}", fault=f)
            java, proc, ran_at = one("default", base / f"fault-{f['name']}", dd)
            v = verdicts(case, corpus, cobol_f, java, prog.get("clock_fields"), ran_at)
            result["external_faults"].append({
                "fault": f["name"], "absent": dd, "cobol_fired": decode_bytes(cobol_f.get("FAULTS", b"")).strip(),
                **v, "cobol_sysout_tail": sysout_lines(cobol_f.get("SYSOUT", b""), "latin-1")[-4:],
                "java_sysout_tail": sysout_lines(java.get("SYSOUT", b""), "latin-1")[-4:],
                "java_stderr_tail": decode_bytes(proc.stderr)[-400:]})  # fmt: skip
    return result


def devin_external_faults(work: Path, jdk21: Path | None) -> list[dict[str, Any]]:
    """Devin's eval arms with an input file absent, against the COBOL fault run (the same external-fault rule)."""
    out = []
    for name, port in dp.PORTS.items():
        for program, (case_name, template) in port["programs"].items():
            case = eq.load_case(case_name)
            (entry,) = mc.select([case["corpus"]])
            corpus = mc.require_clone(entry)
            jdk = jdk21 if port["jdk"] >= 21 else None
            tree = dp.fetch(port, work)
            classpath = dp.build(port, tree, work, jdk)
            adapter = dp.adapter_classes(work, jdk)
            for f in external_faults(case):
                dd = f["plan"][0]["dd"]
                cobol_f = eq.run_cobol(case, corpus, work / "cobol" / f"{case_name}-{f['name']}", fault=f)
                run_dir = work / "runs" / name / program / f"fault-{f['name']}"
                dds = dp.stage_inputs(case, corpus, run_dir, port["input"])
                dds[dd].unlink()
                outdir = run_dir / "out"
                outdir.mkdir()
                env = ej.environment("default")
                argv = [dp.tool(jdk, "java"), "-cp", f"{adapter}:{classpath}", "devinadapter.EnvLauncher",
                        env["locale"], env["tz"], port["main"], *dp.command(port, template, case, dds, outdir)]  # fmt: skip
                proc = dp.run(argv, cwd=run_dir, timeout=600)
                java = dp.java_outputs(case, port, dds, outdir, proc)
                v = verdicts(case, corpus, cobol_f, java, None, datetime.now())
                out.append({"port": name, "program": program, "case": case_name, "fault": f["name"], "absent": dd,
                            "cobol_fired": decode_bytes(cobol_f.get("FAULTS", b"")).strip(), **v,
                            "cobol_sysout_tail": sysout_lines(cobol_f.get("SYSOUT", b""), "latin-1")[-4:],
                            "java_sysout_tail": sysout_lines(java.get("SYSOUT", b""), "latin-1")[-4:],
                            "java_stderr_tail": decode_bytes(proc.stderr)[-400:]})  # fmt: skip
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--port", default="lightyear,sentinel")
    ap.add_argument("--program", help="only these programs")
    ap.add_argument("--environments", default="all")
    ap.add_argument("--external-faults", action="store_true")
    ap.add_argument("--jdk21", type=Path, help="a JDK 21 for Devin's eval arms (port 'devin')")
    args = ap.parse_args()
    envs = list(ej.ENVIRONMENTS) if args.environments == "all" else args.environments.split(",")
    work = args.work.resolve()
    wanted = set(args.program.split(",")) if args.program else None
    results: dict[str, Any] = {"ports": [], "devin_external_faults": [],
                               "skipped": [{"port": p, "program": g, "why": w} for (p, g), w in SKIPPED.items()]}  # fmt: skip
    for name in args.port.split(","):
        if name == "devin":
            results["devin_external_faults"] = devin_external_faults(work, args.jdk21)
            for r in results["devin_external_faults"]:
                print(f"devin {r['port']} {r['program']} {r['fault']}: full {r['full']['summary']}")
            continue
        for program in PORTS[name]["programs"]:
            if wanted and program not in wanted:
                continue
            r = judge(name, program, work, envs, args.external_faults)
            results["ports"].append(r)
            if "build_error" in r:
                print(f"{name} {program}: BUILD FAILED {r['build_error'][:300]}")
                continue
            for x in r["runs"]:
                tiers = "  ".join(f"{t}={'EQUAL' if x[t]['ok'] else 'differs'}" for t in ("full", "data", "clock-masked")
                                  if t in x)  # fmt: skip
                print(f"{name} {program} {x['environment']}: {tiers}  | {x['full']['summary']}")
            for x in r["external_faults"]:
                print(f"{name} {program} {x['fault']} (absent {x['absent']}): full {x['full']['summary']}")
    (work / "thirdparty-results.json").write_text(json.dumps(results, indent=1, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
