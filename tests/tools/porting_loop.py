#!/usr/bin/env python3
"""
The porting loop, driven end to end on one equivalence case (#3753 port_runner + the #3624 harness): a model ports
the case's program from its porting ticket, the harness proves the port (every output, every fault run), and a
failed proof's findings go back to the model as the next attempt's feedback -- until the port is proven or the
attempts run out. What each attempt got wrong is the lesson: in the model, the ticket, the generator or the harness.

    python tests/tools/porting_loop.py run <case> --work DIR [--attempts 3] [--model claude-sonnet-5-5]
                                       [--faults all|none|NAME,...] [--backend-command "..."]
    python tests/tools/porting_loop.py report DIR          # loop.md again from loop.json
    python tests/tools/porting_loop.py run-many CASE... --work-root DIR [--jobs 6]   # many loops at once
    python tests/tools/porting_loop.py adopt CASE DIR       # a proven port into the case, with its provenance

`run` generates the case's Java project once (the same refract -> cobol-to-java path the harness proves in, target
config h2), which writes the porting ticket, then per attempt:

  1. port_runner run    the ticket -> the model -> a proposed port (attempt 2 on: --feedback, the last proof's
                        findings and the port that failed);
  2. port_runner prove  `equivalence.py run <case> --port <the proposed overlay>`: proven, or the report's
                        feedback (the first differing records per output, each failing fault run, compile errors).

The default backend is Claude Code headless (`claude -p`), with NO tools, no MCP servers and no settings from this
repository, run inside the attempt's own directory: the model sees the ticket's prompt and nothing else -- not this
repository, not the committed hand ports. Any other `command` backend can be given with --backend-command
({prompt_file} / {prompt_dir}). Everything is logged by port_runner (ai_agent_jobs/ports/port_log.jsonl); this
tool adds loop.json / loop.md in DIR: per attempt, the verdict, what was wrong, the model's notes, time and tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

# Claude Code headless as a text-only model: no tools, no MCP, no slash commands, nothing persisted, run in the
# attempt's own directory (so no CLAUDE.md of this repository is discovered). The prompt arrives on stdin.
CLAUDE = (
    "bash -c \"cd {prompt_dir} && exec claude -p --model MODEL --tools '' --strict-mcp-config "
    '--disable-slash-commands --no-session-persistence --output-format text < {prompt_file}"'
)


# A model port is derived from its program: the corpus's licence, as the case's LICENSE / NOTICE state it.
PORT_LICENCE = {
    "aws-mainframe-modernization-carddemo": "derived from CardDemo (Apache-2.0; Copyright Amazon.com, Inc. or its "
    "affiliates) -- see LICENSE and NOTICE in this case's directory",
    "cics-banking-sample-application-cbsa": "derived from the CICS Bank Sample Application (EPL-2.0; Copyright IBM "
    "Corp.) -- see LICENSE and NOTICE in this case's directory",
    "cics-genapp": "derived from the CICS General Insurance Application (EPL-2.0; Copyright IBM Corp.) -- see LICENSE "
    "and NOTICE in this case's directory",
}


def _python() -> str:
    return sys.executable


def _run(argv: list[str], log: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=REPO_ROOT)  # noqa: S603
    with log.open("a", encoding="utf-8") as f:
        f.write(f"$ {shlex.join(argv)}\n{proc.stdout}{proc.stderr}\n")
    return proc


def generate_project(case_name: str, work: Path) -> Path:
    """The case's generated Java project (port=False: the service as generated), with its porting tickets."""
    import equivalence as eq
    import equivalence_java as ej
    import mainframe_corpus as mc

    case = eq.load_case(case_name)
    (entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(entry)
    project = ej.prepare_project(case, corpus, work / "generate", "", port=False)
    ticket_key(project, case["program"])
    return project


def ticket_key(project: Path, program: str) -> str:
    """The program's porting-ticket key as the generator wrote it: the source member's name, so `lgicdb01` for
    GenApp's lower-case members, `INQACC` for CBSA's."""
    for p in sorted((project / "ai_agent_jobs").glob("*_port_ticket.json")):
        key = p.name[: -len("_port_ticket.json")]
        if key.upper() == program.upper():
            return key
    raise SystemExit(f"no porting ticket for {program} in {project / 'ai_agent_jobs'}")


def _overlay_files(overlay: Path) -> list[str]:
    return sorted(f.relative_to(overlay).as_posix() for f in overlay.rglob("*.java")) if overlay.is_dir() else []


def start_baseline(
    case_name: str, project: Path, program: str, work: Path
) -> tuple[subprocess.Popen[bytes], list[str]]:
    """A proof of the generated service itself (it fails: it is the stub), started while the model writes: its COBOL
    side and its built project are what every attempt's proof then reuses (equivalence.py --reuse) -- 13 s instead
    of 45 for CardDemo's sign-on, regenerating nothing. Its overlay is the generated service, so a port that
    replaces the same file reuses it; one that replaces others is proven in full."""
    import equivalence_java as ej

    svc = ej._service_class(program)
    rel = f"service/{svc}.java"
    overlay = work / "baseline_overlay"
    (overlay / "service").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "src/main/java" / ej.PKG_DIR / rel, overlay / rel)
    log = (work / "baseline.log").open("wb")
    argv = [_python(), str(TOOLS / "equivalence.py"), "run", case_name, "--port", str(overlay), "--keep",
            str(work / "baseline")]  # fmt: skip
    return subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=REPO_ROOT), [rel]  # noqa: S603


def _baseline_built(baseline: Path) -> bool:
    """Whether the baseline proof got as far as running the Java side: a generated service that does not even
    compile (no runBatch for a program its estate's JCL never runs) leaves nothing to reuse -- prove in full."""
    report = baseline / "report.json"
    if not report.is_file():
        return False
    return not json.loads(report.read_text(encoding="utf-8")).get("java_failed")


def _events(project: Path) -> list[dict[str, Any]]:
    log = project / "ai_agent_jobs" / "ports" / "port_log.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] if log.is_file() else []


def run_loop(case_name: str, work: Path, attempts: int, model: str, faults: Optional[str],
             backend_command: Optional[str]) -> dict[str, Any]:  # fmt: skip
    import equivalence as eq

    case = eq.load_case(case_name)
    work.mkdir(parents=True, exist_ok=True)
    log = work / "loop.log"
    t0 = time.time()
    project = generate_project(case_name, work)
    key = ticket_key(project, case["program"])
    baseline, baseline_files = start_baseline(case_name, project, key, work)
    command = backend_command or CLAUDE.replace("MODEL", model)
    prove = f"{_python()} {TOOLS / 'equivalence.py'} run {case_name} --port {{port_dir}} --keep {{report_dir}}"
    if faults:
        prove += f" --faults {faults}"
    overlay = project / "ai_agent_jobs" / "ports" / key / "overlay"
    record: dict[str, Any] = {"case": case_name, "program": key, "model": model,
                              "backend": "command" if backend_command else "claude-code-headless",
                              "project": str(project), "attempts": [], "proven": False}  # fmt: skip
    runner = [_python(), "-m", "gitgalaxy.tools.cobol_to_java.port_runner"]
    for n in range(1, attempts + 1):
        started = time.time()
        argv = [*runner, "run", str(project), "--ticket", key, "--backend", "command", "--model", model,
                "--command", command, *(["--feedback"] if n > 1 else [])]  # fmt: skip
        ran = _run(argv, log)
        att: dict[str, Any] = {"n": n, "port_seconds": round(time.time() - started)}
        proposed = next((e for e in reversed(_events(project)) if e.get("ticket") == key and e.get("event") in
                         ("proposed", "no-port")), None)  # fmt: skip
        att["prompt_tokens"] = (proposed or {}).get("prompt_tokens")
        att["notes"] = (proposed or {}).get("notes", "")
        if ran.returncode != 0 or not proposed or proposed.get("event") != "proposed":
            att["verdict"] = "no-port"
            att["error"] = (ran.stdout + ran.stderr)[-1500:]
            record["attempts"].append(att)
            continue
        started = time.time()
        baseline.wait()
        reuse = _baseline_built(work / "baseline") and _overlay_files(overlay) == baseline_files
        att["reused"] = reuse
        command_ = prove + (f" --reuse {work / 'baseline'}" if reuse else "")
        proof = _run([*runner, "prove", str(project), "--ticket", key, "--command", command_], log)
        att["prove_seconds"] = round(time.time() - started)
        # port_runner numbers proofs by port proposed, not by loop attempt (an attempt that returned no Java takes
        # no number): the newest proof is this attempt's
        proofs = sorted((project / "ai_agent_jobs" / "ports" / key / "attempts").glob("*_proof"))
        report = proofs[-1] / "report.json" if proofs else Path("/nonexistent")
        r = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        att["verdict"] = "proven" if proof.returncode == 0 else "not proven"
        att["java_failed"] = bool(r.get("java_failed"))
        att["outputs"] = {dd: f"{o['equal']}/{o['records']}" for dd, o in (r.get("outputs") or {}).items()}
        att["faults"] = {f["name"]: f["ok"] for f in r.get("faults", [])}
        att["coverage"] = (r.get("coverage") or {}).get("paragraphs"), (r.get("coverage") or {}).get("branches")
        att["feedback"] = (r.get("feedback") or "")[:4000]
        record["attempts"].append(att)
        if proof.returncode == 0:
            record["proven"] = True
            break
    record["seconds"] = round(time.time() - t0)
    (work / "loop.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    (work / "loop.md").write_text(loop_md(record), encoding="utf-8")
    return record


def loop_md(r: dict[str, Any]) -> str:
    """The loop as Markdown: per attempt what the proof found."""
    head = (f"proven on attempt {len(r['attempts'])}" if r["proven"]
            else f"not proven after {len(r['attempts'])} attempt(s)")  # fmt: skip
    lines = [f"# Porting loop: {r['program']} ({r['case']})", "",
             f"Model `{r['model']}` ({r['backend']}): **{head}**, {r.get('seconds', 0)} s.", "",
             "| attempt | verdict | outputs | faults proven | prompt tokens | port s | prove s |",
             "|---|---|---|---|---|---|---|"]  # fmt: skip
    for a in r["attempts"]:
        f = a.get("faults") or {}
        faults = f"{sum(f.values())}/{len(f)}" if f else "--"
        outs = ", ".join(f"{k} {v}" for k, v in (a.get("outputs") or {}).items()) or (
            "Java failed" if a.get("java_failed") else "--")  # fmt: skip
        lines.append(f"| {a['n']} | {a['verdict']} | {outs} | {faults} | {a.get('prompt_tokens')} | "
                     f"{a.get('port_seconds')} | {a.get('prove_seconds', '--')} |")  # fmt: skip
    for a in r["attempts"]:
        lines += ["", f"## Attempt {a['n']}: {a['verdict']}", ""]
        if a.get("error"):
            lines += ["```", a["error"], "```"]
        if a.get("feedback"):
            lines += [a["feedback"]]
        if a.get("notes"):
            lines += ["", "The model's notes:", "", "```", a["notes"], "```"]
    return "\n".join(lines) + "\n"


def adopt(case_name: str, work: Path) -> Path:
    """A proven loop's port into the case: the model's files as the loop stored them -- never edited -- and
    port/provenance.json from the loop's own records (model, attempt, ticket hash, prompt tokens). Refused unless the
    loop proved it."""
    import equivalence as eq

    record = json.loads((work / "loop.json").read_text(encoding="utf-8"))
    if not record.get("proven") or record.get("case") != case_name:
        raise SystemExit(f"{work}: not a proven loop of {case_name}")
    case = eq.load_case(case_name)
    project = Path(record["project"])
    key = ticket_key(project, case["program"])
    overlay = project / "ai_agent_jobs" / "ports" / key / "overlay"
    proposed = [e for e in _events(project) if e.get("event") == "proposed" and e.get("ticket") == key][-1]
    dest = eq.CASES / case_name / "port"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(overlay, dest)
    provenance = {
        "format": "porting-loop-provenance/1", "program": case["program"],
        "written_by": "model (the #4023 follow-up porting loop), not a person", "model": record["model"],
        "backend": "claude-code-headless: claude -p, no tools, only the ticket's prompt", "proposed": proposed.get("at"),
        "attempt": len(record["attempts"]), "attempts": [{"n": a["n"], "verdict": a["verdict"]} for a in record["attempts"]],
        "ticket_sha256": proposed.get("ticket_sha256"), "prompt_tokens": proposed.get("prompt_tokens"),
        "proof": f"tests/tools/equivalence.py run {case_name}",
        "edited_after": "none: the files are the model's answer as the loop stored it",
        "licence": case.get("port_licence") or PORT_LICENCE[case["corpus"]],
    }  # fmt: skip
    (dest / "provenance.json").write_text(json.dumps(provenance, indent=1) + "\n", encoding="utf-8")
    return dest


def run_many(cases: list[str], root: Path, jobs: int, attempts: int, model: str) -> dict[str, bool]:
    """Many loops at once, each its own process and work directory (root/<case>); the model's time, not the
    harness's, is what a loop mostly waits on. Starts are staggered so the generations do not all coincide."""
    from concurrent.futures import ThreadPoolExecutor

    def one(i_case: tuple[int, str]) -> tuple[str, bool]:
        i, name = i_case
        time.sleep(min(i, jobs) * 15)
        work = root / name
        if work.exists():
            shutil.rmtree(work)
        argv = [_python(), str(Path(__file__).resolve()), "run", name, "--work", str(work), "--attempts",
                str(attempts), "--model", model]  # fmt: skip
        with (root / f"{name}.out").open("w", encoding="utf-8") as out:
            proc = subprocess.run(argv, stdout=out, stderr=subprocess.STDOUT, check=False, cwd=REPO_ROOT)  # noqa: S603
        return name, proc.returncode == 0

    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = dict(pool.map(one, enumerate(cases)))
    for name in cases:
        r = (
            json.loads((root / name / "loop.json").read_text(encoding="utf-8"))
            if (root / name / "loop.json").is_file()
            else {}
        )
        verdict = f"proven on attempt {len(r['attempts'])}" if r.get("proven") else "not proven"
        print(f"{name:<28} {verdict:<22} {r.get('seconds', '--')} s")
    return results


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--attempts", type=int, default=3)
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--faults", help="the proof's fault runs: all (default) | none | NAME,...")
    r.add_argument("--backend-command", help="another command backend ({prompt_file} / {prompt_dir})")
    p = sub.add_parser("report")
    p.add_argument("work", type=Path)
    m = sub.add_parser("run-many")
    m.add_argument("cases", nargs="+")
    m.add_argument("--work-root", type=Path, required=True)
    m.add_argument("--jobs", type=int, default=6)
    m.add_argument("--attempts", type=int, default=4)
    m.add_argument("--model", default="claude-sonnet-5-5")
    a = sub.add_parser("adopt")
    a.add_argument("case")
    a.add_argument("work", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "run-many":
        os.environ.setdefault("PYTHONUTF8", "1")
        results = run_many(args.cases, args.work_root.resolve(), args.jobs, args.attempts, args.model)
        return 0 if all(results.values()) else 1
    if args.cmd == "adopt":
        print(adopt(args.case, args.work.resolve()))
        return 0
    if args.cmd == "report":
        record = json.loads((args.work / "loop.json").read_text(encoding="utf-8"))
        (args.work / "loop.md").write_text(loop_md(record), encoding="utf-8")
        print((args.work / "loop.md").read_text(encoding="utf-8"))
        return 0
    os.environ.setdefault("PYTHONUTF8", "1")
    record = run_loop(args.case, args.work.resolve(), args.attempts, args.model, args.faults, args.backend_command)
    print((args.work / "loop.md").read_text(encoding="utf-8"))
    return 0 if record["proven"] else 1


if __name__ == "__main__":
    sys.exit(main())
