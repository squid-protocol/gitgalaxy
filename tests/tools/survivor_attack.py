#!/usr/bin/env python3
"""Attack a surviving det-port mutant before excusing it (#4628).

A survivor means no test tells the mutant from the port. That is a claim about the TESTS until shown otherwise, so the
first move is an input that kills it, not a verdict. This tool makes the attack one command and leaves the record
`det_mutation.py state` asks for.

    python tests/tools/survivor_attack.py next [CASE ...] [--limit 20]        # the likeliest wrong verdicts first
    python tests/tools/survivor_attack.py facts CASE --work DIR               # what the port itself settles
    python tests/tools/survivor_attack.py packet CASE ID --work DIR           # everything needed to attack one mutant
    python tests/tools/survivor_attack.py try CASE ID[,ID...] --inputs F.json --work DIR   # run the attack
    python tests/tools/survivor_attack.py lint [CASE ...]                     # stated reasons that are not reasons

`facts` and `try` write DIR/attempts.json; `det_mutation.py state CASE TRIAGE.json --attempts DIR/attempts.json` refuses
an `equivalent` / `unreachable` verdict with no attempt behind it. The model proposes inputs and never an expected
result: the COBOL oracle decides, as in tests/tools/strengthen.py (which also handles batch cases, not handled here).

`try` proves the case's det port on the new inputs alone, then each mutant on the same inputs:
  killed      the port is equal and the mutant differs: the input belongs in case.json;
  survived    both are equal: this input did not separate them;
  port-differs the port itself differs from the COBOL on the input: a real translator or harness finding, stop and report;
  refused     the oracle refused the input: no information, try another;
  stillborn   the mutant does not compile.

Runs on the box, never in CI: a proof is one Docker oracle and one JVM. Reading a stated verdict needs nothing else.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shlex
import sys
import time
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import det_mutation as dm  # noqa: E402

CONTEXT = 15  # lines of Java each side of the mutant
ENTRY_POINTS = ("runTask", "runProgram", "runBatch", "handleTransaction", "handleLink", "handleCall", "main")
# what each shape of Java line usually needs: the first thing to try
HINTS = (
    (re.compile(r"eibresp|respond|\bresp\b", re.I),
     "A response store: plan a `faults` entry so a command answers a condition, then look for a later IF on the value."),
    (re.compile(r"linkArea|caBack|\braw\b|commarea", re.I),
     "COMMAREA bytes: the program can be entered by XCTL or LINK from another program. Try a `{\"hex\": ...}` field "
     "value and a longer or shorter area than the layout."),
    (re.compile(r'"[^"]*"\.|\.contains|indexOf|tally|inspect', re.I),
     "A text scan: try a value that holds the searched text. Install values such as URIMAP paths are inputs too."),
    (re.compile(r"\bif\b|\bwhile\b"),
     "A condition: find the boundary value that makes the original and the mutant take different branches."),
    (re.compile(r"length|\blen\b|maxlength", re.I),
     "A length: try exactly the limit, one over it, and empty."),
)
_METHOD = re.compile(r"(?m)^    (?:public|private|protected)[^;{=\n]*?\b(\w+)\(")
_CALL = re.compile(r"\b(\w+)\s*\(")
_CONSTANT = re.compile(r"\bstatic final [\w<>\[\], ]+\s+(\w+)\s*=")


# ---- what the port itself settles -------------------------------------------------------------------------------
def methods(text: str) -> dict[str, list[tuple[int, int]]]:
    """{method name: [(first line, last line), ...]}: every overload, from each signature to its closing brace."""
    import mutation as mu

    mask, _ = mu.code_mask(text)
    out: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    for m in _METHOD.finditer(text):
        at = next((k for k in range(m.end(), len(text)) if mask[k] and text[k] == "{"), None)
        if at is None or text.find(";", m.end(), at) != -1:
            continue
        depth, end = 0, at
        for k in range(at, len(text)):
            if mask[k] and text[k] == "{":
                depth += 1
            elif mask[k] and text[k] == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        out[m.group(1)].append((text.count("\n", 0, m.start()) + 1, text.count("\n", 0, end) + 1))
    return dict(out)


def enclosing(spans: dict[str, list[tuple[int, int]]], line: int) -> str | None:
    return next((n for n, ss in spans.items() for a, b in ss if a <= line <= b), None)


def live_methods(text: str) -> set[str]:
    """The methods any entry point of the program reaches, following calls by name (an overload counts as its name,
    so this errs toward live). The roots are the program's entry points, every public method included: code a test
    never calls is not dead code. That is the difference between `unreachable` and a case gap."""
    spans = methods(text)
    lines = text.splitlines()
    body = {n: "\n".join("\n".join(lines[a - 1 : b]) for a, b in ss) for n, ss in spans.items()}
    public = {m.group(1) for m in _METHOD.finditer(text) if m.group(0).lstrip().startswith("public")}
    live = {n for n in spans if n in ENTRY_POINTS or n in public}
    todo = list(live)
    while todo:
        for name in _CALL.findall(body.get(todo.pop(), "")):
            if name in spans and name not in live:
                live.add(name)
                todo.append(name)
    return live


def port_fact(text: str, mutant: dict[str, Any]) -> dict[str, str] | None:
    """What the port's text alone settles about a mutant, or None. `result` is one of `dm.ATTACK_SETTLED`."""
    spans = methods(text)
    owner = enclosing(spans, int(mutant["line"]))
    if owner and owner not in live_methods(text):
        return {"result": "no-entry-path", "fact": f"{owner}() is reached from no entry point of the program"}
    constant = _CONSTANT.search(mutant.get("before") or "")
    if constant and len(re.findall(rf"\b{re.escape(constant.group(1))}\b", text)) == 1:
        return {"result": "constant-unused", "fact": f"{constant.group(1)} is declared and never read"}
    return None


# ---- the likeliest wrong verdicts -------------------------------------------------------------------------------
def suspicion(entry: dict[str, Any], shared: int) -> tuple[int, list[str]]:
    """(score, why) for a stated verdict: how much it deserves an attack first. `shared`: entries with this reason."""
    score, why = 0, []
    reason = str(entry.get("reason") or "")
    if entry.get("verdict") not in dm.ACCOUNTED:
        return 0, []
    for problem in dm.reason_problems(entry["verdict"], reason):
        score, why = score + 3, [*why, problem]
    if dm.VAGUE_REASON.search(reason):
        score, why = score + 2, [*why, "the reason could be said of any line"]
    if entry.get("op") == "DEL" and re.search(r"eibresp|respond|\bresp", str(entry.get("before")), re.I):
        score, why = score + 2, [*why, "deletes a response store: a later IF may read the stale value"]
    if re.search(r"linkArea|caBack|\braw\b", str(entry.get("before"))):
        score, why = score + 2, [*why, "touches the COMMAREA bytes: another program can enter here"]
    if shared >= 20:
        score, why = score + 1, [*why, f"one reason shared by {shared} survivors"]
    if not entry.get("tried"):
        score, why = score + 1, [*why, "no attack on record"]
    return score, why


def ranked(survivors: dict[str, list[dict[str, Any]]], cases: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    for case, entries in sorted(survivors.items()):
        if cases and case not in cases:
            continue
        counts = collections.Counter(str(e.get("reason"))[:60] for e in entries)
        for e in entries:
            score, why = suspicion(e, counts[str(e.get("reason"))[:60]])
            if score:
                out.append({"case": case, "id": e["id"], "score": score, "verdict": e["verdict"], "why": why})
    return sorted(out, key=lambda r: (-r["score"], r["case"], r["id"]))


# ---- the attack ---------------------------------------------------------------------------------------------------
def judge(base: dict[str, Any], mutant: dict[str, Any]) -> str:
    """The attack's result from the proof of the port and the proof of the mutant on the same inputs."""
    if base["verdict"] in ("error", "timeout") or (base.get("report") or {}).get("refused"):
        return "refused"
    if base["verdict"] != "proven":
        return "port-differs"
    return {"proven": "survived", "refuted": "killed", "timeout": "killed"}.get(mutant["verdict"], "refused")


def attack_case(case: dict[str, Any], proposals: list[dict[str, Any]], ca_names: set[str] | None) -> dict[str, Any]:
    """The case with only `proposals` as its inputs. Their extra keys pass through: the harness knows more scenario
    fields than the model's format (a WEB body, a clock); `targets` is the model's note and goes."""
    import strengthen as st

    taken = {e["name"] for e in st.entries(case)}
    kept = []
    for p in proposals:
        bad = st.validate(case, p, taken, ca_names)
        if bad:
            raise SystemExit(f"{p.get('name')}: {bad}")
        taken.add(p["name"])
        kept.append({k: v for k, v in p.items() if k != "targets"})
    out = json.loads(json.dumps(case))
    out[st.KINDS[case["kind"]]] = kept
    return out


def load_attempts(work: Path) -> dict[str, list[dict[str, Any]]]:
    f = work / "attempts.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def add_attempts(work: Path, new: dict[str, dict[str, Any]]) -> None:
    all_ = load_attempts(work)
    for mid, attempt in new.items():
        all_.setdefault(mid, []).append(attempt)
    (work / "attempts.json").write_text(json.dumps(all_, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def det_port(case: str, work: Path) -> Path:
    """The case's det port under `work`, translated once."""
    port = work / "det" / case / "port"
    if not port.is_dir():
        work.mkdir(parents=True, exist_ok=True)
        dm.translate([case], work)
    if not port.is_dir():
        raise SystemExit(f"{case}: no det port (see {work / 'det' / 'summary.json'})")
    return port


def port_text(port: Path, file: str = dm.FILES) -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(port.glob(file)))


def find_mutants(case: str, port: Path, ids: list[str]) -> dict[str, Any]:
    """{id: mutation.Mutant}; an id the port no longer has is found by its stated Java line before / after."""
    import mutation as mu

    every = mu.all_mutants(port, set(mu.OPERATORS), dm.FILES)
    by_id = {m.id: m for m in every}
    by_text = {(m.before.strip(), m.after.strip()): m for m in every}
    stated = dm.stated(case)
    out = {}
    for i in ids:
        s = stated.get(i, {})
        m = by_id.get(i) or by_text.get((str(s.get("before")).strip(), str(s.get("after")).strip()))
        if m is None:
            raise SystemExit(f"{case}: {i} is not a mutant of this port (the port moved? `det_mutation.py refresh`)")
        out[i] = m
    return out


def attack(case_name: str, ids: list[str], inputs: Path, work: Path, timeout: float) -> dict[str, dict[str, Any]]:
    import equivalence as eq
    import mainframe_corpus as mc
    import mutation as mu
    import strengthen as st

    case = eq.load_case(case_name)
    if case.get("kind", "batch") not in st.KINDS:
        raise SystemExit(f"{case_name}: kind {case.get('kind', 'batch')}: use `strengthen.py run --mutation` for records")
    (corpus_entry,) = mc.select([case["corpus"]])
    proposals = json.loads(inputs.read_text(encoding="utf-8"))
    trial = attack_case(case, proposals, st.commarea_names(case, mc.require_clone(corpus_entry)))
    port = det_port(case_name, work)
    mutants = find_mutants(case_name, port, ids)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    here = work / "attacks" / stamp
    here.mkdir(parents=True)
    cf = here / "case.json"
    cf.write_text(json.dumps({k: v for k, v in trial.items() if k != "name"}, indent=1) + "\n", encoding="utf-8")
    flags = ("--case-file", str(cf), "--no-facades", "--faults", "none")
    print(f"{case_name}: proving the port on {len(proposals)} new input(s)", flush=True)
    base = mu.prove(case_name, port, here / "baseline", 3600, flags)
    names = [p["name"] for p in proposals]
    results: dict[str, dict[str, Any]] = {}
    classpath = mu.baseline_classpath(here / "baseline", here) if base["verdict"] == "proven" else ""
    for i, m in mutants.items():
        record: dict[str, Any] = {"inputs": names, "date": time.strftime("%Y-%m-%d")}
        mdir = here / i
        if base["verdict"] != "proven":
            record["result"] = judge(base, {"verdict": "error"})
            record["detail"] = (base.get("why") or str((base.get("report") or {}).get("feedback") or ""))[:400]
        else:
            ok, why = mu.compiles(mu.write_mutant(port, m, mdir / "port"), classpath, mdir / "classes")
            if not ok:
                record.update(result="stillborn", detail=why[:400])
            else:
                res = mu.prove(case_name, mdir / "port", mdir / "proof", timeout,
                               (*flags, "--reuse", str(here / "baseline"), "--first-difference"))  # fmt: skip
                record.update(result=judge(base, res), killed_by=res.get("killed_by", []))
        results[i] = record
        print(f"  {i} {m.op} {m.file}:{m.line}: {record['result']}", flush=True)
    add_attempts(work, results)
    return results


# ---- the commands ---------------------------------------------------------------------------------------------------
def cmd_next(cases: list[str], limit: int) -> int:
    rows = ranked(dm.load_survivors(), cases or None)
    for r in rows[:limit]:
        print(f"{r['score']:>2} {r['case']} {r['id']} {r['verdict']}: {'; '.join(r['why'])}")
    print(f"{len(rows)} verdicts worth an attack; {min(limit, len(rows))} shown")
    return 0


def cmd_facts(case: str, work: Path) -> int:
    port = det_port(case, work)
    entry = dm.load().get(case) or {}
    settled: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    for s in entry.get("survived", []):
        text = texts.setdefault(s["file"], (port / s["file"]).read_text(encoding="utf-8"))
        fact = port_fact(text, s)
        if fact:
            settled[s["id"]] = {**fact, "date": time.strftime("%Y-%m-%d")}
    add_attempts(work, settled)
    total = len(entry.get("survived", []))
    print(f"{case}: the port settles {len(settled)} of {total} survivors; the other {total - len(settled)} need `try`")
    return 0


def cmd_packet(case: str, mid: str, work: Path) -> int:
    import strengthen as st

    port = det_port(case, work)
    m = find_mutants(case, port, [mid])[mid]
    text = (port / m.file).read_text(encoding="utf-8")
    lines = text.splitlines()
    spec = json.loads((dm.CASES / case / "case.json").read_text(encoding="utf-8"))
    stated = dm.stated(case).get(mid, {})
    span = range(max(0, m.line - CONTEXT - 1), min(len(lines), m.line + CONTEXT))
    print(f"# Attack {mid}: {case} ({spec.get('program')}), {m.op} at {m.file}:{m.line}\n")
    print(f"Before: `{m.before.strip()}`\nAfter:  `{m.after.strip()}`\n")
    print(f"In method: {enclosing(methods(text), m.line) or '(class level)'}")
    print(f"The port settles it: {port_fact(text, {'line': m.line, 'before': m.before}) or 'no: it needs an attack'}")
    if stated:
        print(f"Stated: {stated.get('verdict')}: {stated.get('reason')}")
        for problem in dm.reason_problems(str(stated.get("verdict")), str(stated.get("reason"))):
            print(f"Refused as written: {problem}")
    print("\n## The Java\n```java")
    print("\n".join(f"{'>' if i + 1 == m.line else ' '}{i + 1:5} {lines[i]}" for i in span))
    print(f"```\n\nThe COBOL: {spec.get('program_source')} in corpus {spec.get('corpus')}. Read it: the Java is one reading.")
    hints = [h for rx, h in HINTS if rx.search(m.before)]
    print("\n## Where to start\n" + ("\n".join(f"- {h}" for h in hints) or "- Read how this value reaches an output."))
    kind = spec.get("kind", "batch")
    if kind in st.INPUT_FORMAT:
        names = [e.get("name") for e in spec.get(st.KINDS[kind], [])]
        print(f"\n## The input format\n{st.INPUT_FORMAT[kind]}\n\nInputs the case has: {names}")
    print("\n## The command\n```bash")
    print(f"python tests/tools/survivor_attack.py try {case} {mid} --inputs INPUTS.json --work {shlex.quote(str(work))}")
    print("```\nINPUTS.json is a JSON array of inputs. Never state an expected result: the COBOL decides.")
    return 0


def cmd_lint(cases: list[str]) -> int:
    bad = 0
    for case, entries in sorted(dm.load_survivors().items()):
        if cases and case not in cases:
            continue
        for e in entries:
            for problem in dm.reason_problems(str(e.get("verdict")), str(e.get("reason"))):
                print(f"{case} {e['id']} {e['verdict']}: {problem}")
                bad += 1
    print(f"{bad} stated reasons `det_mutation.py state` would refuse today")
    return 0  # a report: committed verdicts are re-attacked, not failed in bulk


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("cases", nargs="*")
    n.add_argument("--limit", type=int, default=20)
    f = sub.add_parser("facts")
    f.add_argument("case")
    f.add_argument("--work", type=Path, required=True)
    p = sub.add_parser("packet")
    p.add_argument("case")
    p.add_argument("id")
    p.add_argument("--work", type=Path, required=True)
    t = sub.add_parser("try")
    t.add_argument("case")
    t.add_argument("ids", help="mutant ids, comma separated: one input can be aimed at several")
    t.add_argument("--inputs", type=Path, required=True, help="a JSON array of inputs in the case's format")
    t.add_argument("--work", type=Path, required=True)
    t.add_argument("--timeout", type=float, default=600, help="seconds per mutant")
    li = sub.add_parser("lint")
    li.add_argument("cases", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "next":
        return cmd_next(args.cases, args.limit)
    if args.cmd == "facts":
        return cmd_facts(args.case, args.work.resolve())
    if args.cmd == "packet":
        return cmd_packet(args.case, args.id, args.work.resolve())
    if args.cmd == "lint":
        return cmd_lint(args.cases)
    results = attack(args.case, args.ids.split(","), args.inputs, args.work.resolve(), args.timeout)
    wins = [i for i, r in results.items() if r["result"] == "killed"]
    if wins:
        print(f"killed {', '.join(wins)}: add the input to tests/equivalence/{args.case}/case.json and re-run the ledger")
    if any(r["result"] == "port-differs" for r in results.values()):
        print("port-differs: the port is not equal to the COBOL on this input. Stop and report it: that is a real finding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
