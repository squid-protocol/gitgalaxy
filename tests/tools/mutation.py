#!/usr/bin/env python3
"""
Mutation testing of a proven port: does "proven" mean anything? (#3753 porting loop, #4023 coverage.)

A proof says the port and the COBOL program agree on the case's runs. It proves only what those runs look at. This
tool breaks a proven port on purpose -- one small change at a time (a flipped comparison, `+` for `-`, a constant
off by one, a deleted statement, a changed literal) -- and proves each broken port ("mutant") with the same harness.
A mutant the proof still calls proven SURVIVED: either the change means nothing (an equivalent mutant) or the case
never looks there -- a gap in the case, which a port could get wrong and still be "proven".

    python tests/tools/mutation.py run <case> --work DIR [--jobs 4] [--sample N] [--seed 0] [--ops ROR,AOR,...]
    python tests/tools/mutation.py list <case> [--ops ...]     # the mutants, without running them
    python tests/tools/mutation.py report DIR                  # mutation.md again from mutation.json

`run`:
  1. proves the port as committed (`equivalence.py run <case> --keep DIR/baseline`): it must be proven, or there is
     nothing to measure;
  2. writes every mutant of the port's .java files (outside comments; string and char literals only by LIT);
  3. drops the STILLBORN ones -- a mutant `javac` refuses against the baseline's classpath is caught by the
     compiler, not the proof, so it counts for nothing (about 1 s each);
  4. proves each remaining mutant (`equivalence.py run <case> --port <mutant>`), --jobs at a time, each under a time
     limit (a mutant that loops forever is TIMEOUT: caught, but by the clock);
  5. writes DIR/mutation.json and DIR/mutation.md: the score (killed / (killed + survived)), which runs killed what
     (a mutant only a fault run kills is what the fault runs are for), and every survivor with its line.

A survivor is not automatically a gap: read it. An equivalent mutant (`x >= 0` for `x > 0` where x is never 0 there,
a deleted statement whose effect is overwritten) is noise; anything else is a case to extend (a record, a scenario,
a fault) or, when the COBOL can't reach it either, dead code in the port. Logging statements are never mutated.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

EQUIVALENCE = TOOLS / "equivalence.py"
CASES = REPO_ROOT / "tests" / "equivalence"

# ---- the mutation operators ---------------------------------------------------------------------------------------
# Each operator rewrites one site in code (never inside a comment; string / char literals only by LIT). The binary
# operators are matched with a space on each side: that is how every port writes them, and it keeps generics
# (`List<Dd>`), lambdas (`->`) and shifts out.
OPERATORS = {
    "ROR": "relational: < <= > >= == != swapped for a neighbour",
    "COR": "conditional: && for || and back",
    "NEG": "a whole if / while condition negated",
    "AOR": "arithmetic: + - * / % swapped; ++ for --, += for -=",
    "BDM": "BigDecimal: add / subtract / multiply / negate, and the rounding mode",
    "CON": "an integer constant: 0 -> 1, n -> n + 1",
    "LIT": "a string or char literal: its first character changed",
    "RET": "return true for return false and back",
    "DEL": "one statement deleted (an expression statement, a break or a continue)",
}
_BINARY = {
    "ROR": {"<": ["<=", ">="], "<=": ["<", ">"], ">": [">=", "<="], ">=": [">", "<"], "==": ["!="], "!=": ["=="]},
    "COR": {"&&": ["||"], "||": ["&&"]},
    "AOR": {"+": ["-"], "-": ["+"], "*": ["/"], "/": ["*"], "%": ["*"]},
}
_BINARY_RE = re.compile(r"(?<=\s)(<=|>=|==|!=|&&|\|\||<|>|\+|-|\*|/|%)(?=\s)")
_ASSIGN_OPS = {"++": "--", "--": "++", "+=": "-=", "-=": "+="}
_ASSIGN_RE = re.compile(r"\+\+|--|\+=|-=")
_BIGDECIMAL = {".add(": ".subtract(", ".subtract(": ".add(", ".multiply(": ".divide(", ".negate()": "",
               "RoundingMode.HALF_UP": "RoundingMode.DOWN", "RoundingMode.DOWN": "RoundingMode.HALF_UP",
               "RoundingMode.HALF_EVEN": "RoundingMode.HALF_UP"}  # fmt: skip
_BIGDECIMAL_RE = re.compile("|".join(re.escape(k) for k in sorted(_BIGDECIMAL, key=len, reverse=True)))
_INT_RE = re.compile(r"(?<![\w.])(0x[0-9A-Fa-f]+|\d+)(?![\w.])")
_COND_RE = re.compile(r"\b(if|while)\s*\(")
_RETURN_RE = re.compile(r"\breturn (true|false);")
# an expression statement: a call, an assignment or an increment -- not a declaration, return or throw
_STATEMENT_RE = re.compile(
    r"^(\s*)((?:this\.)?[\w.\[\]]+(?:\(.*\))?(?:\s*[-+*/]?=\s*.+|\+\+|--)?;|break;|continue;)\s*$"
)
_DECLARATION_RE = re.compile(r"^\s*(?:final\s+)?[\w.]+(?:<[^;=]*>)?(?:\[\])*\s+\w+\s*(?:=|;)")
_LOGGING_RE = re.compile(r"^\s*(?:log|LOG|logger|LOGGER)\.")


@dataclass
class Mutant:
    id: str
    file: str  # relative to the port directory
    line: int
    op: str
    before: str  # the line as it was
    after: str  # the line as mutated
    offset: int = 0
    length: int = 0
    replacement: str = ""


def code_mask(text: str) -> tuple[list[bool], list[tuple[int, int]]]:
    """Per character: is it code (not a comment, not inside a literal)? And the literal spans (quotes included)."""
    mask = [True] * len(text)
    literals: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif text.startswith('"""', i):  # a text block
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            literals.append((i, j))
        else:
            i += 1
            continue
        for k in range(i, j):
            mask[k] = False
        i = j
    return mask, literals


def _line_of(text: str, offset: int) -> tuple[int, int, int]:
    """(1-based line number, line start, line end) of `offset`."""
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return text.count("\n", 0, offset) + 1, start, len(text) if end < 0 else end


def _matching_paren(text: str, mask: list[bool], open_at: int) -> int | None:
    depth = 0
    for k in range(open_at, len(text)):
        if not mask[k]:
            continue
        if text[k] == "(":
            depth += 1
        elif text[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return None


def mutants_of(rel: str, text: str, ops: set[str]) -> list[Mutant]:
    """Every mutant of one Java file, in source order."""
    mask, literals = code_mask(text)
    sites: list[tuple[str, int, int, str]] = []  # (op, offset, length, replacement)

    def code(m: re.Match[str]) -> bool:
        return all(mask[m.start() : m.end()])

    skip_lines = {_line_of(text, m.start())[0] for m in re.finditer(r"(?m)^\s*(?:import|package)\b|^\s*@", text)}
    for m in _BINARY_RE.finditer(text):
        if not code(m):
            continue
        sites += [(op, m.start(), len(m.group(1)), rep) for op, table in _BINARY.items()
                  for rep in table.get(m.group(1), [])]  # fmt: skip
    sites += [("AOR", m.start(), 2, _ASSIGN_OPS[m.group(0)]) for m in _ASSIGN_RE.finditer(text) if code(m)]
    sites += [("BDM", m.start(), len(m.group(0)), _BIGDECIMAL[m.group(0)]) for m in _BIGDECIMAL_RE.finditer(text)
              if code(m)]  # fmt: skip
    for m in _INT_RE.finditer(text):
        if not code(m):
            continue
        lit = m.group(1)
        if lit.startswith("0x"):  # stays hex, as wide as it was
            rep = f"0x{int(lit, 16) + 1:0{len(lit) - 2}X}"
        else:
            rep = str(int(lit) + 1) if int(lit) else "1"
        sites.append(("CON", m.start(), len(lit), rep))
    for m in _COND_RE.finditer(text):
        if not code(m):
            continue
        close = _matching_paren(text, mask, m.end() - 1)
        if close is not None:
            cond = text[m.end() : close]
            sites.append(("NEG", m.end(), len(cond), f"!({cond})"))
    for m in _RETURN_RE.finditer(text):
        if code(m):
            flip = "false" if m.group(1) == "true" else "true"
            sites.append(("RET", m.start(1), len(m.group(1)), flip))
    for start, end in literals:
        body = text[start + 1 : end - 1]
        if not body or _LOGGING_RE.match(text[_line_of(text, start)[1] : start]):
            continue
        first = body[0]
        if first == "\\":  # an escape: replace the whole escape by a plain character
            width = 6 if body.startswith("\\u") else 2
            sites.append(("LIT", start + 1, width, "X"))
        else:
            sites.append(("LIT", start + 1, 1, "Y" if first == "X" else "X"))
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        m = _STATEMENT_RE.match(stripped)
        if m and not _DECLARATION_RE.match(stripped) and not _LOGGING_RE.match(stripped):
            body_at = offset + len(m.group(1))
            if all(mask[body_at : offset + len(stripped.rstrip())]) or stripped.strip() in ("break;", "continue;"):
                sites.append(("DEL", body_at, len(m.group(2)), f"/* {m.group(2).replace('*/', '* /')} */"))
        offset += len(line)

    out: list[Mutant] = []
    seen: set[tuple[int, int, str]] = set()
    for op, at, length, rep in sorted(sites, key=lambda s: (s[1], s[0], s[3])):
        if op not in ops or (at, length, rep) in seen:
            continue
        seen.add((at, length, rep))
        line_no, ls, le = _line_of(text, at)
        if line_no in skip_lines or _LOGGING_RE.match(text[ls:le]):
            continue
        after_line = text[ls:at] + rep + text[at + length : le]
        if op == "NEG" and "\n" in text[at : at + length]:  # a condition over several lines: show its first line
            after_line = text[ls:at] + "!(" + text[at:le]
        ident = hashlib.sha1(f"{rel}:{at}:{length}:{op}:{rep}".encode(), usedforsecurity=False).hexdigest()[:10]
        out.append(Mutant(ident, rel, line_no, op, text[ls:le].strip(), after_line.strip(), at, length, rep))
    return out


def port_dir(case: str) -> Path:
    return CASES / case / "port"


def all_mutants(port: Path, ops: set[str]) -> list[Mutant]:
    out: list[Mutant] = []
    for f in sorted(port.rglob("*.java")):
        out += mutants_of(f.relative_to(port).as_posix(), f.read_text(encoding="utf-8"), ops)
    return out


def sample(mutants: list[Mutant], n: int | None, seed: int) -> list[Mutant]:
    """At most `n`, spread over the operators (round-robin over each operator's shuffled mutants)."""
    if n is None or n >= len(mutants):
        return mutants
    rng = random.Random(seed)  # noqa: S311 -- a repeatable sample, not a secret
    by_op: dict[str, list[Mutant]] = {}
    for m in mutants:
        by_op.setdefault(m.op, []).append(m)
    for ms in by_op.values():
        rng.shuffle(ms)
    picked: list[Mutant] = []
    while len(picked) < n:
        for op in sorted(by_op):
            if by_op[op] and len(picked) < n:
                picked.append(by_op[op].pop())
    return sorted(picked, key=lambda m: (m.file, m.offset, m.op))


def write_mutant(port: Path, m: Mutant, dest: Path) -> Path:
    """The port with `m` applied, laid out like the port (the harness's --port)."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(port, dest, ignore=shutil.ignore_patterns("*.json", "*.md"))
    f = dest / m.file
    text = f.read_text(encoding="utf-8")
    f.write_text(text[: m.offset] + m.replacement + text[m.offset + m.length :], encoding="utf-8")
    return dest


# ---- the Java side: the baseline's classpath, for the javac check ----------------------------------------------
def _java_env() -> dict[str, str]:
    import java_target_matrix as jtm

    env = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    return env


def baseline_classpath(baseline: Path, work: Path) -> str:
    """The compile classpath of the baseline's generated project: Maven's own (-X), from a clean copy."""
    (pom,) = sorted(baseline.glob("java/*/pom.xml"))[:1] or [None]
    if pom is None:
        raise SystemExit(f"no generated project under {baseline / 'java'}")
    project = pom.parent
    scratch = work / "classpath-project"
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(project, scratch, ignore=shutil.ignore_patterns("target"))
    proc = subprocess.run(["mvn", "-o", "-X", "-B", "compile"], cwd=scratch, env=_java_env(),  # noqa: S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    m = re.search(r"-classpath (\S+)", proc.stdout)
    if proc.returncode != 0 or not m:
        raise SystemExit(f"could not read the baseline's classpath (mvn exit {proc.returncode})")
    return m.group(1).replace(str(scratch / "target" / "classes"), str(project / "target" / "classes"))


def compiles(mutant_port: Path, classpath: str, out: Path) -> tuple[bool, str]:
    out.mkdir(parents=True, exist_ok=True)
    sources = [str(p) for p in sorted(mutant_port.rglob("*.java"))]
    proc = subprocess.run(["javac", "-nowarn", "-d", str(out), "-cp", classpath, *sources],  # noqa: S603, S607
                          env=_java_env(), capture_output=True, text=True, check=False)  # fmt: skip
    errors = [x for x in proc.stderr.splitlines() if ": error: " in x]
    return proc.returncode == 0, (errors[0].split(": error: ", 1)[1] if errors else proc.stderr.strip()[:200])


# ---- proving one mutant ---------------------------------------------------------------------------------------------
def prove(case: str, port: Path | None, work: Path, timeout: float, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    """`equivalence.py run <case> [--port]` in its own process group; the report, or TIMEOUT."""
    argv = [sys.executable, str(EQUIVALENCE), "run", case, "--keep", str(work)]
    if port is not None:
        argv += ["--port", str(port)]
    argv += list(extra)
    start = time.time()
    with (work.parent / f"{work.name}.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(argv, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT,  # noqa: S603
                                start_new_session=True)  # fmt: skip
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return {"verdict": "timeout", "seconds": round(time.time() - start)}
    report_file = work / "report.json"
    if not report_file.is_file():
        return {"verdict": "error", "seconds": round(time.time() - start), "why": f"no report (exit {proc.returncode})"}
    report = json.loads(report_file.read_text(encoding="utf-8"))
    return {"verdict": "proven" if report.get("proven") else "refuted", "seconds": round(time.time() - start),
            "killed_by": killers(report), "report": report}  # fmt: skip


def killers(report: dict[str, Any]) -> list[str]:
    """Which of the proof's runs saw the mutant: `main`, a fault run's name, a CICS scenario, a CALL, or `java`
    (the port crashed or failed to build)."""
    if report.get("java_failed"):
        return ["java"]
    if report.get("kind") == "call":
        return [f"call {d['record']}" for d in report["outputs"]["CALLS"].get("diffs", [])]
    if report.get("kind") == "cics":
        out = []
        for name, o in report.get("outputs", {}).items():
            fired = o.get("fired")
            if o["equal"] != o["records"] or o.get("diffs") or (fired and fired["cobol"] != fired["java"]):
                out.append(name)
        return out
    out = ["main"] if not all(e.get("ok") for e in report.get("environments", [{"ok": True}])) else []
    return out + [f["name"] for f in report.get("faults", []) if not f.get("ok")]


# ---- the run -----------------------------------------------------------------------------------------------------
def run(case: str, work: Path, jobs: int, n: int | None, seed: int, ops: set[str], timeout: float | None,
        keep: bool, full: bool = False, only: Path | None = None) -> dict[str, Any]:  # fmt: skip
    work.mkdir(parents=True, exist_ok=True)
    port = port_dir(case)
    started = time.time()
    print(f"{case}: proving the port as committed (baseline)", flush=True)
    base = prove(case, None, work / "baseline", timeout=3600)
    if base["verdict"] != "proven":  # the committed port must be proven
        raise SystemExit(f"{case}: the committed port is not proven ({base['verdict']}); nothing to measure")
    limit = timeout or max(300.0, 3 * base["seconds"])
    classpath = baseline_classpath(work / "baseline", work)
    # fast (the default): each mutant reuses the baseline's COBOL side and generated project, compiles only the
    # port, and stops at the first run that differs -- the same verdict as --full, which re-proves from scratch
    fast = () if full else ("--reuse", str(work / "baseline"), "--first-difference")
    every = all_mutants(port, ops)
    chosen = sample(every, n, seed)
    if only is not None:  # the mutants another run judged (e.g. a --full reference), to compare against it
        judged = {r["id"] for r in json.loads((only / "mutation.json").read_text(encoding="utf-8"))["results"]
                  if r["verdict"] != "pending"}  # fmt: skip
        chosen = [m for m in every if m.id in judged]
    print(f"{case}: {len(every)} mutants, {len(chosen)} chosen; baseline {base['seconds']} s, limit {limit:.0f} s",
          flush=True)  # fmt: skip
    results: dict[str, dict[str, Any]] = {}
    live: list[Mutant] = []
    for m in chosen:
        mdir = write_mutant(port, m, work / "mutants" / m.id / "port")
        ok, why = compiles(mdir, classpath, work / "mutants" / m.id / "classes")
        if ok:
            live.append(m)
        else:
            results[m.id] = {"verdict": "stillborn", "why": why}
    print(f"{case}: {len(chosen) - len(live)} stillborn (javac), {len(live)} to prove, {jobs} at a time", flush=True)

    def one(m: Mutant) -> tuple[Mutant, dict[str, Any]]:
        mw = work / "mutants" / m.id
        res = prove(case, mw / "port", mw / "proof", limit, fast)
        res.pop("report", None)
        res["verdict"] = {"proven": "survived", "refuted": "killed"}.get(res["verdict"], res["verdict"])
        if not keep and res["verdict"] in ("killed", "timeout"):
            shutil.rmtree(mw / "proof", ignore_errors=True)
        return m, res

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for m, res in pool.map(one, live):
            results[m.id] = res
            done += 1
            print(f"  [{done}/{len(live)}] {m.op} {m.file}:{m.line} {res['verdict']} "
                  f"{','.join(res.get('killed_by', []))[:60]}", flush=True)  # fmt: skip
            _save(work, case, base, every, chosen, results, started, seed, "full" if full else "fast")
    return _save(work, case, base, every, chosen, results, started, seed, "full" if full else "fast")


def _save(work: Path, case: str, base: dict[str, Any], every: list[Mutant], chosen: list[Mutant],
          results: dict[str, dict[str, Any]], started: float, seed: int, mode: str) -> dict[str, Any]:  # fmt: skip
    log = work / "baseline.log"
    claim = re.search(r"COBOL coverage: (.+)", log.read_text(encoding="utf-8")) if log.is_file() else None
    summary = {"case": case, "program": (base.get("report") or {}).get("program"), "mutants": len(every),
               "chosen": len(chosen), "seed": seed, "mode": mode, "seconds": round(time.time() - started),
               "coverage": claim.group(1) if claim else None,
               "results": [{**{k: v for k, v in asdict(m).items() if k not in ("offset", "length", "replacement")},
                            **results.get(m.id, {"verdict": "pending"})} for m in chosen]}  # fmt: skip
    (work / "mutation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (work / "mutation.md").write_text(mutation_md(summary), encoding="utf-8")
    return summary


def score(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(("killed", "timeout", "survived", "stillborn", "error", "pending"), 0)
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts


def mutation_md(s: dict[str, Any]) -> str:
    c = score(s["results"])
    caught = c["killed"] + c["timeout"]
    judged = caught + c["survived"]
    pct = f"{100 * caught / judged:.0f}%" if judged else "n/a"
    lines = [f"# Mutation testing: {s['case']} ({s.get('program') or '?'})", "",
             f"**Score: {caught}/{judged} caught ({pct})** -- killed {c['killed']}, timeout {c['timeout']}, "
             + f"survived {c['survived']}; stillborn (javac) {c['stillborn']}, error {c['error']}, "
             + f"pending {c['pending']}. {s['chosen']} of {s['mutants']} mutants run (seed {s['seed']}, "
             + f"{s.get('mode', 'full')} mode), {s['seconds']} s.", ""]  # fmt: skip
    if s.get("coverage"):
        lines += [f"The proof, as committed: {s['coverage']}.", ""]
    ops: dict[str, dict[str, int]] = {}
    for r in s["results"]:
        ops.setdefault(r["op"], {}).setdefault(r["verdict"], 0)
        ops[r["op"]][r["verdict"]] += 1
    lines += ["| operator | killed | timeout | survived | stillborn |", "|---|---|---|---|---|"]
    for op in sorted(ops):
        o = ops[op]
        lines.append(f"| {op} | {o.get('killed', 0)} | {o.get('timeout', 0)} | {o.get('survived', 0)} "
                     f"| {o.get('stillborn', 0)} |")  # fmt: skip
    only_faults = [r for r in s["results"] if r["verdict"] == "killed" and r.get("killed_by")
                   and "main" not in r["killed_by"] and "java" not in r["killed_by"]
                   and not any(k.startswith("call ") for k in r["killed_by"])]  # fmt: skip
    if only_faults and any(r.get("killed_by") and "main" in r["killed_by"] for r in s["results"]):
        lines += ["", f"**Killed only by fault runs: {len(only_faults)}** (the normal run alone would have "
                  + "proven them)."]  # fmt: skip
    survivors = [r for r in s["results"] if r["verdict"] == "survived"]
    if survivors:
        lines += ["", "## Survivors", "", "Each is an equivalent mutant (noise) or a place the case never looks. "
                  + "Read each one.", ""]  # fmt: skip
        for r in survivors:
            lines += [f"- `{r['id']}` {r['op']} {r['file']}:{r['line']}", f"  - was: `{r['before']}`",
                      f"  - now: `{r['after']}`"]  # fmt: skip
    return "\n".join(lines) + "\n"


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Two runs of the same case (fast and --full): the mutants both judged, and every one they judge differently.
    Caught (killed or timeout) against survived is the verdict; stillborn is javac's in both."""

    def caught(v: str) -> str:
        return {"killed": "caught", "timeout": "caught"}.get(v, v)

    ra = {r["id"]: r for r in a["results"]}
    rb = {r["id"]: r for r in b["results"]}
    both = [i for i in ra if i in rb and "pending" not in (ra[i]["verdict"], rb[i]["verdict"])]
    differ = [{"id": i, "op": ra[i]["op"], "line": ra[i]["line"], a.get("mode", "a"): ra[i]["verdict"],
               b.get("mode", "b"): rb[i]["verdict"]} for i in both
              if caught(ra[i]["verdict"]) != caught(rb[i]["verdict"])]  # fmt: skip
    secs = {m: sum(r.get("seconds", 0) for r in x["results"] if r["id"] in both) for m, x in (("a", a), ("b", b))}
    return {"judged_by_both": len(both), "agree": len(both) - len(differ), "differ": differ,
            "proof_seconds": {a.get("mode", "a"): secs["a"], b.get("mode", "b"): secs["b"]}}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--sample", type=int, help="at most N mutants, spread over the operators (default: all)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--ops", default=",".join(OPERATORS), help="operators: " + ", ".join(OPERATORS))
    r.add_argument("--timeout", type=float, help="seconds per mutant (default: 3x the baseline, at least 300)")
    r.add_argument("--keep", action="store_true", help="keep killed mutants' proof directories too")
    r.add_argument("--only", type=Path, help="run exactly the mutants another run's DIR judged (its "
                   "mutation.json), e.g. to check the fast mode against a --full reference")  # fmt: skip
    r.add_argument("--full", action="store_true", help="prove each mutant from scratch (the COBOL side, the whole "
                   "estate regenerated, every run): slow, the reference the default fast mode must agree with")  # fmt: skip
    ls = sub.add_parser("list")
    ls.add_argument("case")
    ls.add_argument("--ops", default=",".join(OPERATORS))
    rp = sub.add_parser("report")
    rp.add_argument("work", type=Path)
    cp = sub.add_parser("compare", help="two runs of one case (fast and --full): do their verdicts agree?")
    cp.add_argument("a", type=Path)
    cp.add_argument("b", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        loaded = [json.loads((w / "mutation.json").read_text(encoding="utf-8")) for w in (args.a, args.b)]
        print(json.dumps(compare(*loaded), indent=2))
        return 0
    if args.cmd == "report":
        s = json.loads((args.work / "mutation.json").read_text(encoding="utf-8"))
        (args.work / "mutation.md").write_text(mutation_md(s), encoding="utf-8")
        print(mutation_md(s))
        return 0
    ops = {o.strip() for o in args.ops.split(",") if o.strip()}
    if ops - set(OPERATORS):
        raise SystemExit(f"unknown operators: {sorted(ops - set(OPERATORS))}")
    if args.cmd == "list":
        ms = all_mutants(port_dir(args.case), ops)
        for m in ms:
            print(f"{m.id} {m.op} {m.file}:{m.line}  {m.after}")
        counts: dict[str, int] = {}
        for m in ms:
            counts[m.op] = counts.get(m.op, 0) + 1
        print(f"{len(ms)} mutants: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        return 0
    s = run(args.case, args.work, args.jobs, args.sample, args.seed, ops, args.timeout, args.keep, args.full, args.only)
    print(mutation_md(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
