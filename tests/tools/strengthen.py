#!/usr/bin/env python3
"""
The test-strengthening loop (#4049): mutation survivors and uncovered COBOL branches -> new test inputs.

A proof proves only the paths its runs take. Mutation testing (#4047) finds the mistakes a proof would miss, and
COBOL coverage (#4023) says which branches no run reaches. This loop asks a model for new INPUTS that reach them --
a CALL's arguments, a CICS scenario -- and never for an expected result: the expected result always comes from
running the COBOL (the oracle), so the model cannot write a wrong expectation.

    python tests/tools/strengthen.py run <case> --work DIR [--mutation MDIR] [--rounds 2] [--model M]
                                     [--backend-command "..."] [--jobs 3] [--no-mutation]
    python tests/tools/strengthen.py report DIR

Per round:
  1. the gaps: the uncovered branches of the case's proof (its coverage report), with their COBOL lines, and the
     surviving mutants of a mutation run (MDIR's mutation.json; the first round only, as hints);
  2. the model proposes new inputs as JSON, each naming the branch it targets and why;
  3. each proposal is proven ALONE (the case with only that input): the COBOL may refuse it (an IBM service model
     refuses what IBM does not document -- the proposal is dropped, with the reason), it covers some branches,
     and the port is equal on it or not -- a port that differs on a new input is a port gap found, kept;
  4. the case with every useful proposal is proven together: coverage before and after.
Then the surviving mutants are judged again against the strengthened case (mutation.py --only --case-file).

Nothing is committed: DIR/candidate_case.json is the strengthened case for a person to review (and copy over
tests/equivalence/<case>/case.json), DIR/strengthen.md the report. A gap no proposal reaches is reported as such:
unreachable through the program, or behind an oracle that refuses (a z/OS run would settle it, #4050).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS))

import equivalence as eq  # noqa: E402
import porting_loop as pl  # noqa: E402

KINDS = {"call": "calls", "cics": "scenarios"}  # the case's list of inputs, per kind (batch: not yet)
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.S)


# ---- the gaps --------------------------------------------------------------------------------------------------
def entries(case: dict[str, Any]) -> list[dict[str, Any]]:
    kind = case.get("kind", "batch")
    if kind not in KINDS:
        raise SystemExit(f"{case['name']}: kind {kind!r} -- the strengthening loop handles {sorted(KINDS)} so far")
    return case[KINDS[kind]]


def branch_key(b: dict[str, Any]) -> str:
    return f"{b['unit']}:{b['line']}:{b['outcome']}"


def uncovered(report: dict[str, Any]) -> list[dict[str, Any]]:
    cov = report.get("coverage") or {}
    return list((cov.get("branches") or {}).get("uncovered") or [])


def source_lines(case: dict[str, Any], corpus: Path) -> list[str]:
    text = (corpus / case["program_source"]).read_bytes().decode("latin-1")
    return text.splitlines()


def survivors(mutation_dir: Path | None) -> list[dict[str, Any]]:
    if mutation_dir is None or not (mutation_dir / "mutation.json").is_file():
        return []
    data = json.loads((mutation_dir / "mutation.json").read_text(encoding="utf-8"))
    return [r for r in data["results"] if r["verdict"] == "survived"]


# ---- the prompt ----------------------------------------------------------------------------------------------
INPUT_FORMAT = {
    "call": (
        'Each input is one CALL of the program: {"name": "kebab-case-name", "args": [one string per USING '
        'item, at most its size], "targets": ["UNIT:LINE:OUTCOME", ...], "why": "one sentence"}. The '
        "USING items: {using}."
    ),
    "cics": (
        'Each input is one CICS task (a scenario): {"name": "kebab-case-name", "aid": "DFHENTER" or another '
        'DFH AID, "commarea": {COBOL field name: value} or null (no COMMAREA), "receive": {map name: {input '
        'field name: typed text}} (optional), "targets": ["UNIT:LINE:OUTCOME", ...], "why": "one sentence"}. '
        "Use only COMMAREA and screen field names the existing scenarios use."
    ),
}


def prompt(case: dict[str, Any], src: list[str], gaps: list[dict[str, Any]], hints: list[dict[str, Any]],
           feedback: list[str], oracle_notes: str) -> str:  # fmt: skip
    kind = case.get("kind")
    shown = []
    for b in gaps:
        lo = max(0, b["line"] - 3)
        ctx = "\n".join(f"{i + 1:5} {src[i]}" for i in range(lo, min(len(src), b["line"] + 20)))
        shown.append(f"- {branch_key(b)} ({b['kind']} {b['outcome']} in {b['unit']}):\n```\n{ctx}\n```")
    fmt = INPUT_FORMAT[kind].replace("{using}", json.dumps(case.get("using", [])))
    parts = [
        f"You are extending the test case of the COBOL program {case['program']} so that its runs reach code "
        "they never reach today. Propose NEW INPUTS ONLY. Never an expected result: each input is run through the "
        "real COBOL program, and whatever the program does is the expected result.",
        "",
        "## The branches no run reaches",
        *shown,
        "",
        "## The program",
        "```cobol",
        "\n".join(f"{i + 1:5} {line}" for i, line in enumerate(src)),
        "```",
        "",
        f"## The case's current inputs ({len(entries(case))})",
        "```json",
        json.dumps(entries(case), indent=1),
        "```",
    ]
    if hints:
        parts += ["", "## Hints: small changes to the Java port that no current input notices",
                  *[f"- {h['file']}:{h['line']}: `{h['before']}` -> `{h['after']}`" for h in hints[:40]]]  # fmt: skip
    if oracle_notes:
        parts += ["", "## What the test environment can and cannot run", oracle_notes]
    if feedback:
        parts += ["", "## What happened to your earlier proposals", *feedback]
    parts += [
        "",
        "## Answer",
        fmt,
        "Propose at most 8 inputs, each aimed at one or more of the branches above. If you conclude that a branch "
        "cannot be reached through this program (for example because the program always passes a fixed length), "
        'say so instead of proposing an input for it: {"name": "unreachable", "targets": [...], "why": '
        '"..."}. Answer with one JSON array in a ```json block and nothing else.',
    ]
    return "\n".join(parts) + "\n"


def oracle_notes(case: dict[str, Any]) -> str:
    """What the oracle refuses, so the model does not propose it blindly (#4023: an IBM service is modelled only
    where IBM documents it)."""
    notes = []
    le = eq.CASES / "le"
    for c in sorted(le.glob("*.c")) if le.is_dir() else []:
        head = c.read_text(encoding="utf-8").split("*/", 1)[0]
        notes.append(f"`{c.stem.upper()}` is a model of the IBM service, not the real one:\n```\n{head}*/\n```")
    if case.get("kind") == "cics":
        notes.append("CICS runs under a stub runtime that handles the commands the program uses; a scenario may "
                     "inject a CICS response with `\"faults\": [{\"cmd\": \"READ\", \"file\": NAME, \"resp\": "
                     "\"NOTFND\"}]`.")  # fmt: skip
    return "\n\n".join(notes)


# ---- the model -------------------------------------------------------------------------------------------------
def ask(prompt_text: str, work: Path, model: str, command: str | None) -> tuple[str, float]:
    work.mkdir(parents=True, exist_ok=True)
    pf = work / "prompt.md"
    pf.write_text(prompt_text, encoding="utf-8")
    cmd = (command or pl.CLAUDE.replace("MODEL", model)).format(prompt_file=pf, prompt_dir=work)
    start = time.time()
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, check=False, timeout=1800)  # noqa: S603
    (work / "response.md").write_text(proc.stdout + ("\n" + proc.stderr if proc.returncode else ""), encoding="utf-8")
    return proc.stdout, time.time() - start


def parse(response: str) -> list[dict[str, Any]]:
    m = _JSON_BLOCK.search(response)
    raw = m.group(1) if m else response.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def validate(case: dict[str, Any], p: dict[str, Any], taken: set[str]) -> str | None:
    """Why a proposal is malformed, or None."""
    name = str(p.get("name", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", name) or name in taken:
        return f"name {name!r} is not a new kebab-case name"
    if case["kind"] == "call":
        using = case["using"]
        args = p.get("args")
        if not isinstance(args, list) or len(args) != len(using):
            return f"args must be {len(using)} strings"
        for a, u in zip(args, using):
            if not isinstance(a, str) or len(a) > u["size"]:
                return f"{u['name']}: {a!r} is not a string of at most {u['size']}"
    if case["kind"] == "cics":
        known_ca = {k for sc in case["scenarios"] for k in (sc.get("commarea") or {})}
        ca = p.get("commarea")
        if ca is not None and (not isinstance(ca, dict) or set(ca) - known_ca):
            return f"commarea fields not in the existing scenarios: {sorted(set(ca or {}) - known_ca)}"
        if not isinstance(p.get("aid", "DFHENTER"), str) or not str(p.get("aid", "DFHENTER")).startswith("DFH"):
            return "aid must be a DFH AID name"
    return None


def as_entry(case: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    keep = {"call": ("name", "args"), "cics": ("name", "aid", "commarea", "receive", "faults")}[case["kind"]]
    e = {k: p[k] for k in keep if k in p}
    e["why"] = f"#4049 (proposed for {', '.join(p.get('targets') or []) or 'a gap'}): {p.get('why', '')}".strip()
    return e


# ---- proving -------------------------------------------------------------------------------------------------
def prove(case_name: str, case_obj: dict[str, Any], work: Path) -> dict[str, Any]:
    """The case from `case_obj` proven by the harness; its report, or why the COBOL side refused."""
    work.mkdir(parents=True, exist_ok=True)
    cf = work.parent / f"{work.name}.case.json"
    cf.write_text(json.dumps({k: v for k, v in case_obj.items() if k != "name"}, indent=1) + "\n", encoding="utf-8")
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case_name, "--case-file", str(cf), "--keep",
            str(work)]  # fmt: skip
    proc = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=REPO_ROOT)  # noqa: S603
    (work.parent / f"{work.name}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    report_file = work / "report.json"
    if report_file.is_file():
        return json.loads(report_file.read_text(encoding="utf-8"))
    refused = re.search(r"(\w+: [^\n]*not modelled[^\n]*)", proc.stdout + proc.stderr)
    return {"refused": refused.group(1) if refused else (proc.stdout + proc.stderr).strip()[-400:]}


def failing_entries(case: dict[str, Any], report: dict[str, Any]) -> list[str]:
    if report.get("java_failed"):
        return ["(the Java side failed)"]
    outs = report.get("outputs") or {}
    if case["kind"] == "cics":
        return [n for n, o in outs.items() if o.get("diffs") or o.get("equal") != o.get("records")]
    calls = outs.get("CALLS") or {}
    return [case["calls"][d["record"] - 1]["name"] for d in calls.get("diffs", []) if d["record"] <= len(case["calls"])]


# ---- the loop ------------------------------------------------------------------------------------------------
def run(case_name: str, work: Path, rounds: int, model: str, command: str | None, mutation_dir: Path | None,
        jobs: int, judge: bool) -> dict[str, Any]:  # fmt: skip
    import mainframe_corpus as mc

    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    case = eq.load_case(case_name)
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    src = source_lines(case, corpus)
    print(f"{case_name}: proving the case as committed", flush=True)
    base = prove(case_name, case, work / "baseline")
    if not base.get("proven"):
        raise SystemExit(f"{case_name}: the committed case is not proven; nothing to strengthen")
    gaps_before = uncovered(base)
    hints = survivors(mutation_dir)
    current = copy.deepcopy(case)
    accepted: list[dict[str, Any]] = []
    port_equal: list[str] = []  # the accepted inputs the port is equal on: the mutants are judged on these
    log: list[dict[str, Any]] = []
    feedback: list[str] = []
    gaps = list(gaps_before)
    for rnd in range(1, rounds + 1):
        if not gaps:
            break
        rw = work / f"round{rnd}"
        text = prompt(current, src, gaps, hints if rnd == 1 else [], feedback, oracle_notes(case))
        print(f"round {rnd}: {len(gaps)} uncovered branches; asking {model}", flush=True)
        response, secs = ask(text, rw, model, command)
        proposals = parse(response)
        taken = {e["name"] for e in entries(current)}
        feedback = []
        gap_keys = {branch_key(b) for b in gaps}
        for p in proposals:
            item: dict[str, Any] = {"round": rnd, "name": p.get("name"), "targets": p.get("targets") or [],
                                    "why": p.get("why", "")}  # fmt: skip
            if p.get("name") == "unreachable":
                item["verdict"] = "declared unreachable"
                log.append(item)
                continue
            bad = validate(current, p, taken)
            if bad:
                item["verdict"], item["detail"] = "malformed", bad
                log.append(item)
                feedback.append(f"- `{p.get('name')}`: malformed -- {bad}")
                continue
            entry = as_entry(current, p)
            alone = copy.deepcopy(current)
            alone[KINDS[current["kind"]]] = [entry]
            print(f"  {entry['name']}: proving it alone", flush=True)
            r = prove(case_name, alone, rw / entry["name"])
            if "refused" in r:
                item["verdict"], item["detail"] = "refused by the oracle", r["refused"]
                feedback.append(f"- `{entry['name']}`: the COBOL side refused it: {r['refused']}")
            else:
                covered = sorted(gap_keys - {branch_key(b) for b in uncovered(r)})
                item["covers"] = covered
                item["port_equal"] = bool(r.get("proven"))
                if not r.get("proven"):
                    item["port_differs_on"] = failing_entries(alone, r)
                if covered or not r.get("proven"):
                    item["verdict"] = "accepted"
                    accepted.append(entry)
                    if r.get("proven"):
                        port_equal.append(entry["name"])
                    taken.add(entry["name"])
                    current[KINDS[current["kind"]]] = [*entries(current), entry]
                    gap_keys -= set(covered)
                    feedback.append(f"- `{entry['name']}`: accepted, reaches {covered or 'no new branch'}")
                else:
                    item["verdict"] = "no new branch"
                    feedback.append(f"- `{entry['name']}`: ran, but reaches none of the target branches")
            log.append(item)
        log.append({"round": rnd, "model_seconds": round(secs), "proposals": len(proposals)})
        gaps = [b for b in gaps if branch_key(b) in gap_keys]
    print(f"{case_name}: proving the strengthened case ({len(accepted)} new inputs)", flush=True)
    after = prove(case_name, current, work / "strengthened") if accepted else base
    (work / "candidate_case.json").write_text(
        json.dumps({k: v for k, v in current.items() if k != "name"}, indent=2) + "\n", encoding="utf-8"
    )
    # The mutants are judged against the case plus the new inputs the port is equal on: a mutation proof needs a
    # proven baseline, and an input the port differs on is a port gap to fix first, not a test to score with.
    judge_case = copy.deepcopy(case)
    judge_case[KINDS[case["kind"]]] = [*entries(case), *[e for e in accepted if e["name"] in port_equal]]
    (work / "judge_case.json").write_text(
        json.dumps({k: v for k, v in judge_case.items() if k != "name"}, indent=2) + "\n", encoding="utf-8"
    )
    judged = judge_survivors(case_name, work, mutation_dir, jobs) if judge and port_equal and hints else None
    result = {"case": case_name, "program": case["program"], "model": model, "seconds": round(time.time() - started),
              "coverage_before": (base.get("coverage") or {}).get("branches", {}),
              "coverage_after": (after.get("coverage") or {}).get("branches", {}),
              "proven_after": bool(after.get("proven")), "differs_on": failing_entries(current, after)
              if not after.get("proven") else [], "accepted": [e["name"] for e in accepted],
              "proposals": log, "unreached": [branch_key(b) for b in uncovered(after)],
              "survivors_before": len(hints), "mutants": judged, "port_equal": port_equal}  # fmt: skip
    (work / "strengthen.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (work / "strengthen.md").write_text(report_md(result), encoding="utf-8")
    return result


def judge_survivors(case_name: str, work: Path, mutation_dir: Path, jobs: int) -> dict[str, Any] | None:
    """The surviving mutants judged again against the strengthened case."""
    data = json.loads((mutation_dir / "mutation.json").read_text(encoding="utf-8"))
    only = work / "survivors"
    only.mkdir(parents=True, exist_ok=True)
    data["results"] = [r for r in data["results"] if r["verdict"] == "survived"]
    (only / "mutation.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    mw = work / "rejudge"
    argv = [sys.executable, str(TOOLS / "mutation.py"), "run", case_name, "--work", str(mw), "--only", str(only),
            "--case-file", str(work / "judge_case.json"), "--jobs", str(jobs)]  # fmt: skip
    print(f"re-judging {len(data['results'])} surviving mutants against the strengthened case", flush=True)
    subprocess.run(argv, cwd=REPO_ROOT, check=False, capture_output=True, text=True)  # noqa: S603
    out = mw / "mutation.json"
    if not out.is_file():
        return None
    res = json.loads(out.read_text(encoding="utf-8"))["results"]
    killed = [r for r in res if r["verdict"] in ("killed", "timeout")]
    return {"judged": len(res), "killed": len(killed), "still_surviving": len(res) - len(killed),
            "killed_ids": [r["id"] for r in killed]}  # fmt: skip


def report_md(r: dict[str, Any]) -> str:
    cb, ca = r["coverage_before"], r["coverage_after"]
    lines = [f"# Test strengthening: {r['case']} ({r['program']})", "",
             f"Model `{r['model']}`, {r['seconds']} s. **Branches covered: {cb.get('covered')}/{cb.get('total')} -> "
             f"{ca.get('covered')}/{ca.get('total')}**; the strengthened case is "
             + ("proven" if r["proven_after"] else f"NOT proven -- the port differs on {r['differs_on']}") + ".", ""]  # fmt: skip
    if r.get("mutants"):
        m = r["mutants"]
        lines += [f"**Surviving mutants: {r['survivors_before']} before; {m['killed']} of {m['judged']} now killed** "
                  f"(judged with the {len(r.get('port_equal') or [])} new inputs the port is equal on).", ""]  # fmt: skip
    elif r.get("survivors_before"):
        lines += [f"Surviving mutants ({r['survivors_before']}) not re-judged: no new input the port is equal on.", ""]
    lines += [f"New inputs: {', '.join(f'`{n}`' for n in r['accepted']) or 'none'} (in `candidate_case.json`, for a "
              "person to review).", "", "| round | proposal | verdict | reaches | detail |", "|---|---|---|---|---|"]  # fmt: skip
    for p in r["proposals"]:
        if "verdict" not in p:
            continue
        detail = p.get("detail") or (
            f"port differs on {p['port_differs_on']}" if p.get("port_differs_on") else p.get("why", "")
        )
        lines.append(f"| {p['round']} | `{p['name']}` | {p['verdict']} | {', '.join(p.get('covers') or []) or '-'} "
                     f"| {str(detail).replace('|', '/')[:160]} |")  # fmt: skip
    if r["unreached"]:
        lines += ["", "## Still unreached", "", "Each is unreachable through the program, behind an oracle that "
                  "refuses (only a z/OS run settles it, #4050), or a case for another round.", "",
                  *[f"- `{k}`" for k in r["unreached"]]]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--rounds", type=int, default=2)
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--backend-command", help="any CLI: {prompt_file} / {prompt_dir} (default: claude -p, no tools)")
    r.add_argument("--mutation", type=Path, help="a mutation.py run directory of this case: its survivors")
    r.add_argument("--jobs", type=int, default=3)
    r.add_argument("--no-mutation", action="store_true", help="do not re-judge the survivors")
    rp = sub.add_parser("report")
    rp.add_argument("work", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "report":
        data = json.loads((args.work / "strengthen.json").read_text(encoding="utf-8"))
        print(report_md(data))
        return 0
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    result = run(args.case, args.work, args.rounds, args.model, args.backend_command, args.mutation, args.jobs,
                 not args.no_mutation)  # fmt: skip
    print(report_md(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
