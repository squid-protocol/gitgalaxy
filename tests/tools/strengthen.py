#!/usr/bin/env python3
"""
The test-strengthening loop (#4049): mutation survivors and uncovered COBOL branches -> new test inputs.

A proof proves only the paths its runs take. Mutation testing (#4047) finds the mistakes a proof would miss, and
COBOL coverage (#4023) says which branches no run reaches. This loop asks a model for new INPUTS that reach them --
a CALL's arguments, a CICS scenario -- and never for an expected result: the expected result always comes from
running the COBOL (the oracle), so the model cannot write a wrong expectation.

    python tests/tools/strengthen.py run <case> --work DIR [--mutation MDIR] [--case-gaps [RESULTS]] [--rounds 2]
                                     [--model M] [--backend-command "..."] [--jobs 3] [--no-mutation]
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

`--case-gaps` (#4049, the mutation scores of #4047): only the survivors docs/language_status/mutation_scores.json
triaged as case gaps are targets (an equivalent or unreachable mutant no input can kill), and a call or CICS case is
driven by them as well as by its uncovered branches: every round shows the remaining survivors, a proposal aimed at
one is kept when the port is equal on it, the survivors are judged again after the round, and at the end a proposal
that reached no new branch and killed no mutant is dropped.

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
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS))

import equivalence as eq  # noqa: E402
import porting_loop as pl  # noqa: E402

KINDS = {"call": "calls", "cics": "scenarios"}  # the case's list of inputs, per kind (batch: records, run_batch)
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


def survivors(mutation_dir: Path | None, only: set[str] | None = None) -> list[dict[str, Any]]:
    """The surviving mutants of a mutation run, or only those whose id is in `only`."""
    if mutation_dir is None or not (mutation_dir / "mutation.json").is_file():
        return []
    data = json.loads((mutation_dir / "mutation.json").read_text(encoding="utf-8"))
    return [r for r in data["results"] if r["verdict"] == "survived" and (only is None or r["id"] in only)]


SCORES = REPO_ROOT / "docs" / "language_status" / "mutation_scores.json"


def case_gaps(results: Path, case_name: str, program: str | None = None) -> set[str]:
    """The ids of the survivors the committed mutation scores (#4047) triaged as case gaps: inputs the case lacks.
    `case_name` is an equivalence case, or `crucible:<case>` with the crucible port's `program`."""
    data = json.loads(results.read_text(encoding="utf-8"))
    return {s["id"] for p in data["ports"] if p["case"] == case_name and (program is None or p["program"] == program)
            for s in p.get("survivors") or [] if s.get("verdict") == "case_gap"}  # fmt: skip


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
        "Use only COMMAREA fields of the case's COMMAREA layout and screen field names the existing scenarios "
        'use. A scenario may also plan CICS conditions: "faults": [{"cmd": COMMAND, "file" or "program" or "queue": '
        'NAME, "nth": 1, "resp": CONDITION}] (see the notes on the test environment), and add records to the '
        'files every scenario reads: "records": [{"dataset": DSN, "based_on": the number of an existing record '
        'to copy, "set": {FIELD: value}}] -- a record keyed like no other, of a dataset with a layout.'
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
        parts += ["", "## Mistakes no current input exposes: small changes to the Java port that every run still "
                  "passes. An input on which the original and the changed code behave differently kills one; name "
                  "the ids you aim at in `targets`.",
                  *[f"- {'`' + h['id'] + '` ' if h.get('id') else ''}{h['file']}:{h['line']}: `{h['before']}` -> `{h['after']}`"
                    for h in hints[:40]]]  # fmt: skip
    if oracle_notes:
        parts += ["", "## What the test environment can and cannot run", oracle_notes]
    if feedback:
        parts += ["", "## What happened to your earlier proposals", *feedback]
    parts += [
        "",
        "## Answer",
        fmt,
        "Propose at most 8 inputs, each aimed at one or more of the branches or mistakes above. If you conclude that a branch "
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


def validate(case: dict[str, Any], p: dict[str, Any], taken: set[str], ca_names: set[str] | None = None) -> str | None:
    """Why a proposal is malformed, or None. `ca_names`: the COMMAREA layout's field names (a CICS case), else the
    fields the existing scenarios use."""
    name = str(p.get("name", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", name) or name in taken:
        return f"name {name!r} is not a new kebab-case name"
    if case["kind"] == "call":
        using = case["using"]
        args = p.get("args")
        if not isinstance(args, list) or len(args) != len(using):
            return f"args must be {len(using)} strings"
        for a, u in zip(args, using, strict=False):  # reason: length may differ
            if not isinstance(a, str) or len(a) > u["size"]:
                return f"{u['name']}: {a!r} is not a string of at most {u['size']}"
    if case["kind"] == "cics":
        known_ca = ca_names or {k for sc in case["scenarios"] for k in (sc.get("commarea") or {})}
        ca = p.get("commarea")
        if ca is not None and (not isinstance(ca, dict) or set(ca) - known_ca):
            where = "the COMMAREA layout" if ca_names else "the existing scenarios"
            return f"commarea fields not in {where}: {sorted(set(ca or {}) - known_ca)}"
        if not isinstance(p.get("aid", "DFHENTER"), str) or not str(p.get("aid", "DFHENTER")).startswith("DFH"):
            return "aid must be a DFH AID name"
        try:
            eq_cics().fault_lines({"name": name, "faults": p.get("faults")})
        except eq_cics().Unsupported as e:
            return str(e)
    return None


def as_entry(case: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    keep = {"call": ("name", "args"), "cics": ("name", "aid", "commarea", "receive", "faults")}[case["kind"]]
    e = {k: p[k] for k in keep if k in p}
    e["why"] = f"#4049 (proposed for {', '.join(p.get('targets') or []) or 'a gap'}): {p.get('why', '')}".strip()
    return e


def eq_cics() -> Any:
    import equivalence_cics as ec

    return ec


def commarea_names(case: dict[str, Any], corpus: Path) -> set[str] | None:
    if case.get("kind") != "cics" or not case.get("commarea"):
        return None
    return {f["name"] for f in eq_cics().commarea_fields(corpus, case)}


def cics_inputs(case: dict[str, Any], corpus: Path) -> dict[str, dict[str, Any]]:
    """#4049: the CICS case's files with a layout (a dataset's `copybook` and `record`): fields, record length and
    records, so a proposal can add a record the way a batch one does."""
    import equivalence_common as common

    out = {}
    for dd, spec in (case.get("datasets") or {}).items():
        if not spec.get("copybook") or not spec.get("input"):
            continue
        src = corpus / spec["copybook"]
        dirs = [src.parent, *(corpus / d for d in case.get("copy_dirs", [])), corpus]
        fields = common.layout_fields(corpus, spec["copybook"], spec.get("record"), dirs)
        reclen = max(f["offset"] + f["bytes"] for f in fields)
        data = eq_cics().case_file_records(case, corpus, spec, reclen, common.data_encoding(case))
        recs = [data[i : i + reclen] for i in range(0, len(data), reclen)]
        out[dd] = {"fields": fields, "records": recs, "spec": {**spec, "reclen": reclen}}
    return out


def cics_with_records(case: dict[str, Any], inputs: dict[str, Any], added: dict[str, list[bytes]],
                      work: Path) -> dict[str, Any]:  # fmt: skip
    """#4049: the CICS case with `added` records after each file's own: the dataset's `append` file (a text file
    under `work`) holds them, after any the case already appends."""
    import equivalence_common as common

    out = copy.deepcopy(case)
    enc = common.data_encoding(case)
    for dd, new in added.items():
        if not new:
            continue
        spec = case["datasets"][dd]
        reclen = inputs[dd]["spec"]["reclen"]
        had = (
            common._fixed(common._input_path(case, Path("/"), spec["append"]), reclen, enc)
            if spec.get("append")
            else b""
        )
        old = [had[i : i + reclen] for i in range(0, len(had), reclen)]
        lines = [r.decode(enc).rstrip(" ") for r in old + new]
        path = work / "inputs" / Path(spec["input"]).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("\n".join(lines) + "\n").encode(enc))
        out["datasets"][dd]["append"] = str(path)
    return out


def proposal_records(case: dict[str, Any], inputs: dict[str, Any], p: dict[str, Any]
                     ) -> tuple[dict[str, list[bytes]], str | None]:  # fmt: skip
    """#4049: a CICS proposal's new records by dataset, or why one cannot be built (its key is taken: a keyed
    file holds a key once, and the first field of each layout is the file's key here)."""
    out: dict[str, list[bytes]] = {}
    for r in p.get("records") or []:
        rec, bad = build_record(case, inputs, r)
        if bad:
            return {}, bad
        assert rec is not None
        f0 = inputs[r["dataset"]]["fields"][0]
        key = rec[f0["offset"] : f0["offset"] + f0["bytes"]]
        if any(x[f0["offset"] : f0["offset"] + f0["bytes"]] == key for x in inputs[r["dataset"]]["records"]):
            return {}, f"{r['dataset']}: a record with {f0['name']} {key!r} is already there"
        out.setdefault(r["dataset"], []).append(rec)
    return out, None


# ---- proving -------------------------------------------------------------------------------------------------
def prove(case_name: str, case_obj: dict[str, Any], work: Path, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    """The case from `case_obj` proven by the harness; its report, or why the COBOL side refused."""
    work.mkdir(parents=True, exist_ok=True)
    cf = work.parent / f"{work.name}.case.json"
    cf.write_text(json.dumps({k: v for k, v in case_obj.items() if k != "name"}, indent=1) + "\n", encoding="utf-8")
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case_name, "--case-file", str(cf), "--keep",
            str(work), *extra]  # fmt: skip
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
        jobs: int, judge: bool, gap_ids: set[str] | None = None) -> dict[str, Any]:  # fmt: skip
    """`gap_ids` (--case-gaps): the survivors to aim at, and drive the rounds with (see the module docstring)."""
    import mainframe_corpus as mc

    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    case = eq.load_case(case_name)
    if case.get("kind", "batch") == "batch":
        return run_batch(case_name, work, rounds, model, command, mutation_dir, jobs, gap_ids)
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    src = source_lines(case, corpus)
    print(f"{case_name}: proving the case as committed", flush=True)
    base = prove(case_name, case, work / "baseline")
    if not base.get("proven"):
        raise SystemExit(f"{case_name}: the committed case is not proven; nothing to strengthen")
    gaps_before = uncovered(base)
    hints = survivors(mutation_dir, gap_ids)
    driven = gap_ids is not None and mutation_dir is not None  # the survivors drive the rounds too
    targets = list(hints) if driven else []
    killed_ids: list[str] = []
    killers: set[str] = set()  # the accepted inputs some re-judged mutant was killed by
    ca_names = commarea_names(case, corpus)
    inputs = cics_inputs(case, corpus) if case["kind"] == "cics" else {}
    added: dict[str, list[bytes]] = {}  # the accepted proposals' new records, by dataset
    brought: dict[str, dict[str, list[bytes]]] = {}  # each accepted proposal's own new records

    def with_entries(ents: list[dict[str, Any]], tag: str) -> dict[str, Any]:
        """The committed case plus `ents`, and the records those entries brought."""
        out = copy.deepcopy(case)
        recs: dict[str, list[bytes]] = {}
        for e in ents:
            for dd, rs in brought.get(e["name"], {}).items():
                recs.setdefault(dd, []).extend(rs)
        if recs:
            out = cics_with_records(out, inputs, recs, work / tag)
        out[KINDS[case["kind"]]] = [*entries(case), *ents]
        return out

    current = copy.deepcopy(case)
    accepted: list[dict[str, Any]] = []
    port_equal: list[str] = []  # the accepted inputs the port is equal on: the mutants are judged on these
    log: list[dict[str, Any]] = []
    feedback: list[str] = []
    gaps = list(gaps_before)
    for rnd in range(1, rounds + 1):
        if not gaps and not targets:
            break
        rw = work / f"round{rnd}"
        text = prompt(
            current, src, gaps, targets if driven else hints if rnd == 1 else [], feedback, oracle_notes(case)
        )
        print(f"round {rnd}: {len(gaps)} uncovered branches, {len(targets)} survivors; asking {model}", flush=True)
        response, secs = ask(text, rw, model, command)
        proposals = parse(response)
        taken = {e["name"] for e in entries(current)}
        feedback = []
        gap_keys = {branch_key(b) for b in gaps}
        target_ids = {t["id"] for t in targets}
        round_aimed: list[str] = []
        for p in proposals:
            item: dict[str, Any] = {"round": rnd, "name": p.get("name"), "targets": p.get("targets") or [],
                                    "why": p.get("why", "")}  # fmt: skip
            if p.get("name") == "unreachable":
                item["verdict"] = "declared unreachable"
                log.append(item)
                continue
            bad = validate(current, p, taken, ca_names)
            if bad:
                item["verdict"], item["detail"] = "malformed", bad
                log.append(item)
                feedback.append(f"- `{p.get('name')}`: malformed -- {bad}")
                continue
            entry = as_entry(current, p)
            recs, bad = proposal_records(case, inputs, p) if p.get("records") else ({}, None)
            if bad:
                item["verdict"], item["detail"] = "malformed", bad
                log.append(item)
                feedback.append(f"- `{p.get('name')}`: malformed -- {bad}")
                continue
            trial = {dd: [*added.get(dd, []), *recs.get(dd, [])] for dd in {*added, *recs}}
            base_case = cics_with_records(current, inputs, trial, rw / entry["name"]) if trial else current
            alone = copy.deepcopy(base_case)
            alone[KINDS[current["kind"]]] = [entry]
            print(f"  {entry['name']}: proving it alone", flush=True)
            r = prove(case_name, alone, rw / entry["name"])
            if r.get("refused"):  # a report carries `refused: {}` when nothing was refused
                item["verdict"], item["detail"] = "refused by the oracle", r["refused"]
                feedback.append(f"- `{entry['name']}`: the COBOL side refused it: {r['refused']}")
            else:
                covered = sorted(gap_keys - {branch_key(b) for b in uncovered(r)})
                item["covers"] = covered
                item["port_equal"] = bool(r.get("proven"))
                if not r.get("proven"):
                    item["port_differs_on"] = failing_entries(alone, r)
                aimed = bool(target_ids & {str(t) for t in item["targets"]}) and bool(r.get("proven"))
                if covered or not r.get("proven") or aimed:
                    item["verdict"] = "accepted"
                    if aimed:
                        round_aimed.append(entry["name"])
                    accepted.append(entry)
                    if r.get("proven"):
                        port_equal.append(entry["name"])
                    taken.add(entry["name"])
                    if recs:
                        added = trial
                        brought[entry["name"]] = recs
                    current = with_entries(accepted, "current-data")
                    gap_keys -= set(covered)
                    feedback.append(f"- `{entry['name']}`: accepted, reaches {covered or 'no new branch'}")
                else:
                    item["verdict"] = "no new branch"
                    feedback.append(f"- `{entry['name']}`: ran, but reaches none of the target branches")
            log.append(item)
        log.append({"round": rnd, "model_seconds": round(secs), "proposals": len(proposals)})
        gaps = [b for b in gaps if branch_key(b) in gap_keys]
        if driven and round_aimed and targets:
            jc = with_entries([e for e in accepted if e["name"] in port_equal], f"round{rnd}-judge-data")
            cf = work / f"round{rnd}-judge.case.json"
            cf.write_text(json.dumps({k: v for k, v in jc.items() if k != "name"}, indent=2) + "\n", encoding="utf-8")
            judged_now = rejudge(case_name, work / f"round{rnd}-judge", cf, targets, mutation_dir, jobs)
            if judged_now:
                killed = set(judged_now["killed_ids"])
                killed_ids += sorted(killed)
                for k in judged_now.get("killed_by") or []:  # a call case's runs are `call N`: its Nth call
                    n = re.fullmatch(r"call (\d+)", k)
                    killers.add(jc["calls"][int(n.group(1)) - 1]["name"] if n and case["kind"] == "call" else k)
                targets = [t for t in targets if t["id"] not in killed]
                feedback.append(f"- after this round, {len(killed)} of the mutants were killed; {len(targets)} survive")
    if driven:
        # An input that reached no new branch and killed nothing adds runs to the proof for nothing: dropped (a
        # mutant the Java side crashed on, killed_by `java`, names no input: every input is kept then).
        keep_all = "java" in killers
        useful = {e["name"] for e in accepted if keep_all or e["name"] in killers or e["name"] not in port_equal}
        useful |= {i["name"] for i in log if i.get("covers")}
        dropped = [e["name"] for e in accepted if e["name"] not in useful]
        for i in log:
            if i.get("name") in dropped:
                i["verdict"], i["detail"] = "dropped", "reached no new branch and killed no surviving mutant"
        accepted = [e for e in accepted if e["name"] in useful]
        port_equal = [n for n in port_equal if n in useful]
        current = with_entries(accepted, "current-data")
    print(f"{case_name}: proving the strengthened case ({len(accepted)} new inputs)", flush=True)
    after = prove(case_name, current, work / "strengthened") if accepted else base
    (work / "candidate_case.json").write_text(
        json.dumps({k: v for k, v in current.items() if k != "name"}, indent=2) + "\n", encoding="utf-8"
    )
    # The mutants are judged against the case plus the new inputs the port is equal on: a mutation proof needs a
    # proven baseline, and an input the port differs on is a port gap to fix first, not a test to score with.
    judge_case = with_entries([e for e in accepted if e["name"] in port_equal], "judge-data")
    (work / "judge_case.json").write_text(
        json.dumps({k: v for k, v in judge_case.items() if k != "name"}, indent=2) + "\n", encoding="utf-8"
    )
    if driven:
        judged = {"judged": len(hints), "killed": len(killed_ids), "still_surviving": len(hints) - len(killed_ids),
                  "killed_ids": killed_ids} if killed_ids or round_count(log) else None  # fmt: skip
    else:
        judged = judge_survivors(case_name, work, mutation_dir, jobs) if judge and port_equal and hints else None
    result = {"case": case_name, "program": case["program"], "model": model, "seconds": round(time.time() - started),
              "coverage_before": (base.get("coverage") or {}).get("branches", {}),
              "coverage_after": (after.get("coverage") or {}).get("branches", {}),
              "proven_after": bool(after.get("proven")), "differs_on": failing_entries(current, after)
              if not after.get("proven") else [], "accepted": [e["name"] for e in accepted],
              "proposals": log, "unreached": [branch_key(b) for b in uncovered(after)],
              "survivors_before": len(hints), "mutants": judged, "port_equal": port_equal,
              "still_surviving": [t["id"] for t in targets] if driven else None}  # fmt: skip
    (work / "strengthen.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (work / "strengthen.md").write_text(report_md(result), encoding="utf-8")
    return result


def round_count(log: list[dict[str, Any]]) -> int:
    return sum(1 for i in log if "model_seconds" in i)


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
    r.add_argument("--case-gaps", type=Path, nargs="?", const=SCORES, metavar="RESULTS",
                   help="aim only at the survivors a mutation results file triaged as case gaps, and let them drive "
                   f"the rounds (default file: {SCORES.relative_to(REPO_ROOT)})")  # fmt: skip
    rp = sub.add_parser("report")
    rp.add_argument("work", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "report":
        data = json.loads((args.work / "strengthen.json").read_text(encoding="utf-8"))
        print(report_md(data))
        return 0
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    gap_ids = case_gaps(args.case_gaps, args.case) if args.case_gaps else None
    result = run(args.case, args.work, args.rounds, args.model, args.backend_command, args.mutation, args.jobs,
                 not args.no_mutation, gap_ids)  # fmt: skip
    print(report_md(result))
    return 0


# ---- batch cases: new records --------------------------------------------------------------------------------
# A batch input is a fixed-width record. The model does not write one: it names an existing record of an input
# dataset and the fields to change ({"dataset", "based_on", "set"}), and the record is encoded from the dataset's
# layout -- found from the program itself: SELECT ... ASSIGN TO <DD> gives the file, READ <file> INTO <record> the
# record, whose 01 is in a copybook of the case's copy directories or in the program.
_SELECT = re.compile(r"SELECT\s+([A-Z0-9-]+)\s+ASSIGN\s+(?:TO\s+)?['\"]?([A-Z0-9-]+)", re.I)
_READ_INTO = re.compile(r"\bREAD\s+([A-Z0-9-]+)(?:\s+NEXT)?(?:\s+RECORD)?\s+INTO\s+([A-Z0-9-]+)", re.I)
_TEXT_USAGES = (None, "", "DISPLAY")


def input_layout(case: dict[str, Any], corpus: Path, dd: str) -> list[dict[str, Any]] | None:
    """The fields of input dataset `dd`'s record, or None when they cannot be found."""
    import equivalence_common as common

    spec = case["datasets"][dd]
    if spec.get("copybook"):
        return common.layout_fields(corpus, spec["copybook"], spec.get("record"))
    src = (corpus / case["program_source"]).read_bytes().decode("latin-1")
    files = {assign.upper(): f.upper() for f, assign in _SELECT.findall(src)}
    fname = files.get(dd.upper())
    record = next((r.upper() for f, r in _READ_INTO.findall(src) if f.upper() == fname), None) if fname else None
    if record is None:
        return None
    level01 = re.compile(rf"^.{{6}}\s*01\s+{re.escape(record)}\s*\.", re.I | re.M)
    candidates = [case["program_source"]] + [
        str(p.relative_to(corpus)) for d in case.get("copy_dirs", []) for p in sorted((corpus / d).glob("*"))
        if p.is_file()
    ]  # fmt: skip
    for rel in candidates:
        if level01.search((corpus / rel).read_bytes().decode("latin-1")):
            fields = common.layout_fields(corpus, rel, record)
            if sum(f["bytes"] for f in fields) <= spec["reclen"]:
                return fields
    return None


def records(case: dict[str, Any], corpus: Path, dd: str) -> list[bytes]:
    import equivalence_common as common

    spec = case["datasets"][dd]
    data = common._fixed(common._input_path(case, corpus, spec["input"]), spec["reclen"], common.data_encoding(case))
    return [data[i : i + spec["reclen"]] for i in range(0, len(data), spec["reclen"])]


def batch_inputs(case: dict[str, Any], corpus: Path) -> dict[str, dict[str, Any]]:
    """Per input dataset with a layout: its fields and its records."""
    out = {}
    for dd, spec in case["datasets"].items():
        if "input" not in spec or str(spec["input"]).startswith("@generate"):
            continue
        fields = input_layout(case, corpus, dd)
        if fields:
            out[dd] = {"fields": fields, "records": records(case, corpus, dd), "spec": spec}
    return out


def build_record(case: dict[str, Any], inputs: dict[str, Any], p: dict[str, Any]) -> tuple[bytes | None, str | None]:
    """The new record of proposal `p`, or why it cannot be built."""
    import equivalence_cics as ec
    import equivalence_common as common

    dd = p.get("dataset")
    if dd not in inputs:
        return None, f"dataset {dd!r} is not an input with a known layout: {sorted(inputs)}"
    recs = inputs[dd]["records"]
    n = p.get("based_on")
    if not isinstance(n, int) or not 1 <= n <= len(recs):
        return None, f"based_on must be a record number 1..{len(recs)}"
    by_name = {f["name"]: f for f in inputs[dd]["fields"]}
    rec = bytearray(recs[n - 1])
    enc = common.data_encoding(case)
    for name, value in (p.get("set") or {}).items():
        f = by_name.get(str(name).upper())
        if f is None:
            return None, f"{dd} has no field {name}"
        if (f.get("usage") or "").upper() not in _TEXT_USAGES:
            return None, f"{name} is {f['usage']}: only DISPLAY fields keep a text input file text"
        num = common._pic_numeric(f["pic"]) if f["pic"] else None
        if num is not None:
            try:
                exponent = Decimal(str(value)).as_tuple().exponent
            except ArithmeticError:
                return None, f"{name} = {value!r} is not a number"
            if isinstance(exponent, int) and -exponent > num[2]:
                return None, f"{name} = {value!r} has more decimals than its PICTURE {f['pic']} holds"
        try:
            rec[f["offset"] : f["offset"] + f["bytes"]] = ec.encode_field(value, f["pic"], f["usage"], f["bytes"], enc)
        except (ValueError, ArithmeticError) as e:
            return None, f"{name} = {value!r}: {e}"
    keys = inputs[dd]["spec"].get("keys") or []
    for k in keys:
        key = bytes(rec[k["offset"] : k["offset"] + k["length"]])
        taken = any(r[k["offset"] : k["offset"] + k["length"]] == key for r in recs)
        if taken and inputs[dd]["spec"].get("organization") == "indexed":
            return None, f"{dd}'s key {key.decode(enc)!r} is already a record's (a keyed file holds it once)"
    return bytes(rec), None


def with_records(case: dict[str, Any], corpus: Path, added: dict[str, list[bytes]], work: Path) -> dict[str, Any]:
    """The case with `added` records appended to its input datasets, each as a text file under `work`."""
    import equivalence_common as common

    out = copy.deepcopy(case)
    enc = common.data_encoding(case)
    for dd, new in added.items():
        if not new:
            continue
        lines = [r.decode(enc).rstrip(" ") for r in records(case, corpus, dd) + new]
        path = work / "inputs" / f"{dd}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("\n".join(lines) + "\n").encode(enc))
        out["datasets"][dd]["input"] = str(path)
    return out


def batch_prompt(case: dict[str, Any], src: list[str], inputs: dict[str, Any], targets: list[dict[str, Any]],
                 gaps: list[dict[str, Any]], feedback: list[str]) -> str:  # fmt: skip
    import equivalence_cics as ec
    import equivalence_common as common

    enc = common.data_encoding(case)
    shown = []
    for dd, inp in inputs.items():
        layout = ", ".join(f"{f['name']} {f.get('pic') or 'X'}@{f['offset']}" for f in inp["fields"])
        sample = [json.dumps(ec.decode_record(r, inp["fields"], enc)) for r in inp["records"][:3]]
        shown += [f"### {dd} ({len(inp['records'])} records; keyed: {bool(inp['spec'].get('keys'))})",
                  f"Fields: {layout}", "First records:", *[f"{i + 1}. {s}" for i, s in enumerate(sample)], ""]  # fmt: skip
    parts = [
        f"You are extending the test data of the COBOL batch program {case['program']} so that its runs expose "
        "mistakes they miss today. Propose NEW INPUT RECORDS ONLY. Never an expected result: the real COBOL "
        "program runs on your records, and whatever it writes is the expected result.",
        "",
        "## Mistakes the current data does not expose",
        "Each is a small change to the program's Java port that still gives the same output on today's data. A "
        "record that makes the original and the changed code behave differently exposes it (a boundary value, an "
        "equal date, a digit 9, a record that takes another path).",
        *[f"- `{t['id']}` {t['file']}:{t['line']}: `{t['before']}` -> `{t['after']}`" for t in targets[:30]],
    ]
    if gaps:
        parts += ["", "## COBOL branches no run reaches", *[f"- {branch_key(b)}" for b in gaps]]
    parts += ["", "## The input datasets", *shown, "## The program", "```cobol",
              "\n".join(f"{i + 1:5} {line}" for i, line in enumerate(src)), "```"]  # fmt: skip
    if feedback:
        parts += ["", "## What happened to your earlier proposals", *feedback]
    parts += [
        "",
        "## Answer",
        'Each proposal is one new record: {"name": "kebab-case-name", "dataset": DD, "based_on": the number '
        'of an existing record of that dataset to copy, "set": {FIELD: new value, ...}, "targets": [mutant ids '
        'or branches], "why": "one sentence"}. Change only DISPLAY fields; in a keyed dataset give the record a '
        "key no other record has. Every record goes into the same run: a record that makes the program ABEND ends "
        "the run for all the others and is rejected -- aim at paths the run continues through. At most 8 "
        "proposals, in one JSON array in a ```json block, nothing else.",
    ]
    return "\n".join(parts) + "\n"


def run_batch(case_name: str, work: Path, rounds: int, model: str, command: str | None, mutation_dir: Path | None,
              jobs: int, gap_ids: set[str] | None = None) -> dict[str, Any]:  # fmt: skip
    """The loop for a batch case: driven by the surviving mutants (a batch proof's branches are mostly covered;
    its survivors are boundaries), judged again after each round."""
    import mainframe_corpus as mc

    started = time.time()
    case = eq.load_case(case_name)
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    src = source_lines(case, corpus)
    inputs = batch_inputs(case, corpus)
    if not inputs:
        raise SystemExit(f"{case_name}: no input dataset with a layout found")
    print(f"{case_name}: proving the case as committed (inputs with layouts: {sorted(inputs)})", flush=True)
    base = prove(case_name, case, work / "baseline")
    if not base.get("proven"):
        raise SystemExit(f"{case_name}: the committed case is not proven; nothing to strengthen")
    targets = survivors(mutation_dir, gap_ids)
    survivors_before = len(targets)
    added: dict[str, list[bytes]] = {}
    accepted: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []
    feedback: list[str] = []
    judged = None
    killed_ids: list[str] = []
    current = case
    for rnd in range(1, rounds + 1):
        if not targets:
            break
        rw = work / f"round{rnd}"
        text = batch_prompt(case, src, inputs, targets, uncovered(base), feedback)
        print(f"round {rnd}: {len(targets)} surviving mutants; asking {model}", flush=True)
        response, secs = ask(text, rw, model, command)
        feedback = []
        round_new = []
        for p in parse(response):
            item: dict[str, Any] = {"round": rnd, "name": p.get("name"), "targets": p.get("targets") or [],
                                    "why": p.get("why", "")}  # fmt: skip
            rec, bad = build_record(case, inputs, p)
            if bad:
                item["verdict"], item["detail"] = "malformed", bad
                feedback.append(f"- `{p.get('name')}`: malformed -- {bad}")
                log.append(item)
                continue
            trial = {dd: list(v) for dd, v in added.items()}
            trial.setdefault(p["dataset"], []).append(rec)
            print(f"  {p.get('name')}: proving the case with it", flush=True)
            r = prove(case_name, with_records(case, corpus, trial, rw / str(p.get("name"))), rw / str(p.get("name")),
                      extra=("--faults", "none"))  # fmt: skip
            ends = (r.get("abend") or {}).get("cobol")
            if r.get("refused"):  # a report carries `refused: {}` when nothing was refused
                item["verdict"], item["detail"] = "refused by the COBOL side", r["refused"]
                feedback.append(f"- `{p.get('name')}`: the COBOL side failed on it: {r['refused'][:200]}")
            elif ends and ends != (base.get("abend") or {}).get("cobol"):
                # Every record shares one input file and one run: a record that abends the step hides every record
                # after it and every fault plan aimed past it. An error path is a fault plan's job, not a record's.
                item["verdict"], item["detail"] = "ends the run early", f"the COBOL step abends {ends} on it"
                feedback.append(f"- `{p.get('name')}`: rejected -- the step abends {ends} on it, which cuts the run "
                                "short for every other record; propose records that keep the run going")  # fmt: skip
            elif not r.get("proven"):
                item["verdict"] = "port differs"
                item["detail"] = (r.get("feedback") or "")[:300]
                feedback.append(f"- `{p.get('name')}`: the port differs from the COBOL on it -- a port gap, kept")
                added = trial
                accepted.append({**p, "port_equal": False})
                round_new.append(p.get("name"))
            else:
                item["verdict"] = "accepted"
                added = trial
                accepted.append({**p, "port_equal": True})
                round_new.append(p.get("name"))
                feedback.append(f"- `{p.get('name')}`: accepted (the COBOL ran it, the port is equal on it)")
            log.append(item)
        log.append({"round": rnd, "model_seconds": round(secs), "proposals": len(round_new)})
        if not round_new:
            continue
        current = with_records(case, corpus, added, work / "current")
        (work / "candidate_case.json").write_text(
            json.dumps({k: v for k, v in current.items() if k != "name"}, indent=2) + "\n", encoding="utf-8"
        )
        if any(not a["port_equal"] for a in accepted):
            continue  # a port gap: the mutants are judged against a proven case only
        judged = rejudge(case_name, work / f"round{rnd}-judge", work / "candidate_case.json", targets, mutation_dir,
                         jobs)  # fmt: skip
        if judged:
            killed = set(judged["killed_ids"])
            killed_ids += sorted(killed)
            targets = [t for t in targets if t["id"] not in killed]
            feedback.append(f"- after this round, {len(killed)} of the mutants were killed; {len(targets)} survive")
    print(f"{case_name}: proving the strengthened case with every fault run", flush=True)
    after = prove(case_name, current, work / "strengthened") if accepted else base
    result = {"case": case_name, "program": case["program"], "model": model, "seconds": round(time.time() - started),
              "coverage_before": (base.get("coverage") or {}).get("branches", {}),
              "coverage_after": (after.get("coverage") or {}).get("branches", {}),
              "proven_after": bool(after.get("proven")), "differs_on": [] if after.get("proven") else ["(see report)"],
              "accepted": [a["name"] for a in accepted], "proposals": log,
              "unreached": [branch_key(b) for b in uncovered(after)], "survivors_before": survivors_before,
              "survivors_after": len(targets),
              "port_equal": [a["name"] for a in accepted if a["port_equal"]],
              "mutants": {"judged": survivors_before, "killed": survivors_before - len(targets),
                          "still_surviving": len(targets), "killed_ids": killed_ids} if judged else None,
              "records": {dd: len(v) for dd, v in added.items()}}  # fmt: skip
    (work / "strengthen.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (work / "strengthen.md").write_text(report_md(result), encoding="utf-8")
    return result


def rejudge(case_name: str, work: Path, case_file: Path, targets: list[dict[str, Any]], mutation_dir: Path,
            jobs: int) -> dict[str, Any] | None:  # fmt: skip
    """`targets` (surviving mutants) judged again against `case_file`."""
    data = json.loads((mutation_dir / "mutation.json").read_text(encoding="utf-8"))
    ids = {t["id"] for t in targets}
    data["results"] = [r for r in data["results"] if r["id"] in ids]
    only = work / "survivors"
    only.mkdir(parents=True, exist_ok=True)
    (only / "mutation.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    argv = [sys.executable, str(TOOLS / "mutation.py"), "run", case_name, "--work", str(work / "m"), "--only",
            str(only), "--case-file", str(case_file), "--jobs", str(jobs)]  # fmt: skip
    print(f"  re-judging {len(ids)} surviving mutants", flush=True)
    subprocess.run(argv, cwd=REPO_ROOT, check=False, capture_output=True, text=True)  # noqa: S603
    out = work / "m" / "mutation.json"
    if not out.is_file():
        return None
    res = json.loads(out.read_text(encoding="utf-8"))["results"]
    killed = [r for r in res if r["verdict"] in ("killed", "timeout")]
    return {"killed_ids": [r["id"] for r in killed],
            "killed_by": sorted({k for r in killed for k in r.get("killed_by") or ["java"]})}  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
