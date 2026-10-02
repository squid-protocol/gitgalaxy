#!/usr/bin/env python3
"""A model refactors a proven deterministic port, one paragraph method at a time, every step proven.

    python tests/tools/det_refine.py run CASE --port DIR --work DIR [--backend command|anthropic|openai]
                                     [--model M] [--command "..."] [--methods NAME,...] [--retries 1]

The port (a `det_port.py --style structured` port, already proven) is copied to DIR/port. For each paragraph
method the model gets the method, the COBOL each statement came from (its comments), the fields it touches and
the runtime's contract, and returns the method rewritten for a reader -- same signature, same behaviour. The
rewrite is applied and the case proven (equivalence.py, the first run's build reused); kept when proven, else
retried once with the proof's feedback, else reverted. The port is proven after every kept step.

The model is the customer's (gitgalaxy.tools.cobol_to_java.port_runner backends: an OpenAI-compatible endpoint,
Anthropic's API, or any command). DIR/refine.json: per method, the verdict and the size before / after; DIR/port:
the refined port."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

CLAUDE = ("bash -c \"cd {prompt_dir} && exec claude -p --model MODEL --tools '' --strict-mcp-config "
          "--disable-slash-commands --no-session-persistence --output-format text < {prompt_file}\"")  # fmt: skip

SYSTEM = """You refactor one Java method of a COBOL program's deterministic Java port, for a human reader. The port \
is proven equivalent to the COBOL; your rewrite must keep it so -- every byte the program reads and writes, every \
statement's effect, in the same order. It will be proven again; a rewrite that changes behaviour is rejected.

How the port works (do not change this machinery):
- The program's data is byte storage. Each COBOL item is a `Field` (fields of the class, named after the COBOL \
names). `Cobol.move(src, dst, CS)` is COBOL's MOVE (truncation, padding, numeric editing); `Cobol.compare(a, b, \
CS)` compares as COBOL does (alphanumeric: the shorter operand padded with spaces; numeric: by value); \
`Cobol.num(f, CS)` is a numeric item's value (BigDecimal), `Cobol.text(f, CS)` an item's bytes as text; \
`Cobol.store(f, value, rounded, CS)` stores an arithmetic result with COBOL's truncation. Constants `D16` etc. are \
BigDecimal literals.
- Other methods are the program's other paragraphs; calling one is PERFORMing it. `throw new Goback()` ends the \
program. The `// ...` comments give the COBOL statement each line came from.

What you may do: give the method a Javadoc saying what the paragraph does; restructure conditions (else-if chains, \
early returns where control flow is unchanged, switch on a value); extract well-named private helper methods \
(e.g. `boolean isApplAok()`) placed after the method; introduce local variables; drop `if (true)` around a final \
throw; keep or shorten the COBOL comments (keep the paragraph's COBOL name in the Javadoc).
A method returning `int` belongs to a program with GO TO: it returns the index of the paragraph to run next \
(`return GOTO | n` is a GO TO, the final `return n` falls through). Keep every return -- its value and the \
conditions under which it happens -- exactly.
What you must not do: change the method's name or signature; touch fields, storage or other methods; replace a \
Cobol.* call with plain Java unless it is exactly equivalent for every value (an alphanumeric compare is \
space-padded; a numeric MOVE truncates); reorder statements with effects; add I/O, logging or state.

Answer with ONE ```java code block holding the method and any helpers you added -- nothing else in the block."""


def methods(java: str) -> list[tuple[str, int, int]]:
    """The paragraph methods: (name, start, end) of `    /** NAME. */ private void name() { ... }` in the source."""
    out = []
    for m in re.finditer(r"    /\*\* [^\n]*\*/\n    private (?:void|int) (\w+)\(\) \{\n", java):
        end = java.index("\n    }\n", m.end()) + len("\n    }\n")
        out.append((m.group(1), m.start(), end))
    return out


def glossary(java: str, method: str) -> list[str]:
    """The declarations of the fields a method uses (`acctId = Field.zoned(...)`)."""
    decl = dict(re.findall(r"^        (\w+) = (Field\.\w+\([^;]*\));$", java, re.M))
    used = sorted(set(re.findall(r"\b(\w+)\b", method)) & set(decl))
    return [f"{u} = {decl[u]}" for u in used]


def metrics(text: str) -> dict[str, int]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    depth = max((len(ln) - len(ln.lstrip())) // 4 for ln in lines) if lines else 0
    return {"lines": len(lines), "cobol_calls": text.count("Cobol."), "max_depth": depth,
            "if_true": text.count("if (true)")}  # fmt: skip


def prompt(java: str, name: str, body: str, feedback: str | None) -> str:
    parts = [f"Refactor the method `{name}` of this COBOL program's Java port.", "", "Fields it uses:",
             *[f"    {g}" for g in glossary(java, body)], "", "The method:", "```java", body.rstrip(), "```"]  # fmt: skip
    if feedback:
        parts += ["", "Your previous rewrite was REJECTED -- the proof (or the build) found:", feedback[:4000],
                  "Rewrite it again, keeping the behaviour exactly."]  # fmt: skip
    return "\n".join(parts)


def extract(answer: str, name: str) -> str | None:
    m = re.search(r"```java\n(.*?)```", answer, re.S)
    if not m:
        return None
    code = m.group(1).rstrip() + "\n"
    if not re.search(rf"\bprivate (?:void|int) {re.escape(name)}\(\) \{{", code):
        return None
    # four-space class indentation, as the port's
    if not code.startswith("    "):
        code = "\n".join(("    " + ln) if ln.strip() else ln for ln in code.splitlines()) + "\n"
    return code


def prove(case: str, port: Path, keep: Path, reuse: Path | None, faults: str) -> tuple[bool, str]:
    shutil.rmtree(keep, ignore_errors=True)
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case, "--port", str(port), "--keep", str(keep),
            "--faults", faults, *(["--reuse", str(reuse)] if reuse else [])]  # fmt: skip
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT, check=False, timeout=3600)  # noqa: S603
    report = keep / "report.json"
    rep = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    ok = proc.returncode == 0 and bool(rep) and bool(rep.get("proven", True)) and not rep.get("java_failed")
    return ok, (rep.get("feedback") or proc.stdout[-3000:] + proc.stderr[-2000:])


def run(opts: argparse.Namespace) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_java import port_runner

    work: Path = opts.work.resolve()
    port = work / "port"
    shutil.rmtree(port, ignore_errors=True)
    shutil.copytree(opts.port, port)
    service = next(port.glob("service/*.java"))
    record: dict[str, Any] = {"case": opts.case, "backend": opts.backend, "model": opts.model, "steps": []}
    t0 = time.time()
    ok, fb = prove(opts.case, port, work / "baseline", None, opts.faults)
    if not ok:
        raise SystemExit(f"the starting port does not prove -- refine a proven port only:\n{fb[:2000]}")
    record["before"] = metrics(service.read_text(encoding="utf-8"))
    names = [n for n, _, _ in methods(service.read_text(encoding="utf-8"))]
    if opts.methods:
        names = [n for n in names if n in opts.methods.split(",")]
    if opts.largest:
        src = service.read_text(encoding="utf-8")
        size = {n: metrics(src[s:e])["lines"] for n, s, e in methods(src)}
        keep = set(sorted(names, key=lambda n: -size[n])[: opts.largest])
        names = [n for n in names if n in keep]
    for name in names:
        java = service.read_text(encoding="utf-8")
        span = next(((s, e) for n, s, e in methods(java) if n == name), None)
        if span is None:
            continue
        body = java[span[0] : span[1]]
        if metrics(body)["lines"] <= 3:  # nothing to refactor (an EXIT paragraph)
            continue
        step: dict[str, Any] = {"method": name, "before": metrics(body), "attempts": 0}
        feedback = None
        for _ in range(1 + opts.retries):
            step["attempts"] += 1
            pdir = work / "prompts" / name
            pdir.mkdir(parents=True, exist_ok=True)
            user = prompt(java, name, body, feedback)
            opts.command = opts.command or CLAUDE.replace("MODEL", opts.model)
            try:
                answer = port_runner.ask(opts.backend, SYSTEM, user, opts, pdir)
            except SystemExit as e:
                step["verdict"] = f"backend failed: {e}"
                break
            (pdir / f"answer{step['attempts']}.md").write_text(answer, encoding="utf-8")
            code = extract(answer, name)
            if code is None:
                feedback = "No ```java block with the method's own signature was found in the answer."
                continue
            # the javadoc line above the method is the model's now (keep the COBOL name: the prompt asks it to)
            new_java = java[: span[0]] + code + java[span[1] :]
            service.write_text(new_java, encoding="utf-8")
            ok, fb = prove(opts.case, port, work / "steps" / name, work / "baseline", opts.faults)
            if ok:
                step.update({"verdict": "kept", "after": metrics(code)})
                break
            service.write_text(java, encoding="utf-8")  # revert: the port stays proven
            feedback = fb
        else:
            step["verdict"] = "reverted"
        record["steps"].append(step)
        (work / "refine.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        print(f"{name}: {step.get('verdict')} ({step['attempts']} attempt(s))", flush=True)
    record["after"] = metrics(service.read_text(encoding="utf-8"))
    record["seconds"] = round(time.time() - t0)
    (work / "refine.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--port", type=Path, required=True, help="a proven det port directory (service/ + cobolrt/)")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--backend", default="command", choices=("command", "anthropic", "openai"))
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--command", help="the command backend ({prompt_file} / {prompt_dir}); default: claude -p")
    r.add_argument("--base-url", help="the openai backend's endpoint")
    r.add_argument("--api-key-env", help="the environment variable holding the API key")
    r.add_argument("--methods", help="only these methods (comma-separated)")
    r.add_argument("--largest", type=int, help="only the N largest methods")
    r.add_argument("--retries", type=int, default=1)
    r.add_argument("--faults", default="all")
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("--max-tokens", type=int, default=16000)
    opts = r.parse_args(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "run" else ap.parse_args()
    record = run(opts)
    b, a = record["before"], record["after"]
    kept = sum(1 for s in record["steps"] if s.get("verdict") == "kept")
    print(f"{record['case']}: {kept}/{len(record['steps'])} methods refactored and proven; lines {b['lines']} -> "
          f"{a['lines']}, Cobol.* calls {b['cobol_calls']} -> {a['cobol_calls']}, if(true) {b['if_true']} -> "
          f"{a['if_true']}, {record['seconds']} s")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
