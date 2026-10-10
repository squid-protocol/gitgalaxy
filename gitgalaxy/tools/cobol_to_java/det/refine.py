"""A model refactors a proven deterministic port, one paragraph method at a time, every step proven (det-port B2).

For each paragraph method the model gets the method, the COBOL each statement came from (its comments), the fields
it touches and the runtime's contract, and returns the method rewritten for a reader -- same signature, same
behaviour. The rewrite is applied and the port proven again; it is kept when it proves, else retried with the
proof's feedback, else reverted. The port is therefore proven after every step.

Neither the model nor the proof is this module's: `ask(system, user, prompt_dir)` returns the model's answer (the
customer's backend), `prove()` proves the port as it stands and returns (proven, feedback). The callers are
port_runner's `refine` (the operator's proof command) and tests/tools/det_refine.py (the equivalence harness)."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from collections.abc import Callable

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
- Some items are typed Java fields instead (`private String endOfFile;  // END-OF-FILE PIC X(01)`, `long`, \
`BigDecimal`): a String holds exactly its PICTURE's length (space-padded), and they are assigned only through the \
forms already used (`Cobol.fit`, `Cobol.binary`, `Cobol.zoned`, `Cobol.packed`). Keep those forms.
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
    """The paragraph methods: (name, start, end) of `    /** NAME. */ private void|int name() { ... }`."""
    out = []
    for m in re.finditer(r"    /\*\* [^\n]*\*/\n    private (?:void|int) (\w+)\(\) \{\n", java):
        end = java.index("\n    }\n", m.end()) + len("\n    }\n")
        out.append((m.group(1), m.start(), end))
    return out


def glossary(java: str, method: str) -> list[str]:
    """The declarations of the fields a method uses (`acctId = Field.zoned(...)`, `private String endOfFile;`)."""
    decl = dict(re.findall(r"^        (\w+) = (Field\.\w+\([^;]*\));$", java, re.M))
    for typ, name, note in re.findall(r"^    private (String|long|BigDecimal) (\w+);(.*)$", java, re.M):
        decl[name] = f"{typ}{note}"
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
    if not code.startswith("    "):  # four-space class indentation, as the port's
        code = "\n".join(("    " + ln) if ln.strip() else ln for ln in code.splitlines()) + "\n"
    return code


def refine(service: Path, ask: Callable[[str, str, Path], str], prove: Callable[[], tuple[bool, str]], work: Path,
           only: list[str] | None = None, skip: list[str] | None = None, largest: int | None = None,
           retries: int = 1, on_step: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:  # fmt: skip
    """Refine `service` (a proven port's service file) in place; returns {before, after, steps, seconds}. `prove`
    proves the port as it is on disk. Each step -- {method, verdict, attempts, before, after} -- goes to `on_step`
    as it ends. A model that fails to answer ends that method's step ("backend failed"), not the run."""
    t0 = time.time()
    src = service.read_text(encoding="utf-8")
    record: dict[str, Any] = {"before": metrics(src), "steps": []}
    names = [n for n, _, _ in methods(src)]
    if only:
        names = [n for n in names if n in only]
    if skip:
        names = [n for n in names if n not in skip]
    if largest:
        size = {n: metrics(src[s:e])["lines"] for n, s, e in methods(src)}
        keep = set(sorted(names, key=lambda n: -size[n])[:largest])
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
        for _ in range(1 + retries):
            step["attempts"] += 1
            pdir = work / "prompts" / name
            pdir.mkdir(parents=True, exist_ok=True)
            try:
                answer = ask(SYSTEM, prompt(java, name, body, feedback), pdir)
            except (SystemExit, Exception) as e:  # the backend's failure is this step's verdict
                step["verdict"] = f"backend failed: {e}"
                break
            (pdir / f"answer{step['attempts']}.md").write_text(answer, encoding="utf-8")
            code = extract(answer, name)
            if code is None:
                feedback = "No ```java block with the method's own signature was found in the answer."
                continue
            service.write_text(java[: span[0]] + code + java[span[1] :], encoding="utf-8")
            ok, fb = prove()
            if ok:
                step.update({"verdict": "kept", "after": metrics(code)})
                break
            service.write_text(java, encoding="utf-8")  # revert: the port stays proven
            feedback = fb
        else:
            step["verdict"] = "reverted"
        record["steps"].append(step)
        if on_step:
            on_step(step)
    record["after"] = metrics(service.read_text(encoding="utf-8"))
    record["seconds"] = round(time.time() - t0)
    return record
