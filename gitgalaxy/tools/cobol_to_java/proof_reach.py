"""Which of a port's methods its proof can run (#4255).

The equivalence harness and the CICS crucible drive a port through one method per program: runTask(CicsTask) for
a CICS program, handleCall(...) for a CALLed one, runBatch(dds, parm) for a batch one. Code the proof never calls
is not proven, however the port's proof turns out -- the mutation scores of #4047 found 37 survivors in such code:
controller-style entry points (executeX, handleTransaction, handleLink, onAbendLnn, dispatchXLnn, submitX) and
generated TS helpers the models kept beside runTask.

This reads the port's Java -- no build -- and follows, from those roots, every call by name inside the port's
classes (and through a field typed as another analysed class: casubService.handleLink(...)). A method none of
them reaches is **unproven**; one whose body is more than the forge's stub (a log line, a TODO, return null /
the request) is **ported but unproven** -- behaviour that ships in the Java and no proof covers.

The match is by name, so it errs toward "reached": a port method that shares its name with a method the reached
code calls on something else (task.xctl(...) and a port method xctl) counts as reached.

    python -m gitgalaxy.tools.cobol_to_java.proof_reach PATH [PATH ...] [--json] [--strict]

PATH is a .java file or a directory (a port overlay, a generated project's service package). --strict exits 1
when any method is ported but unproven.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The methods a proof calls: equivalence_cics.py / cics_crucible.py (runTask), equivalence_call.py (handleCall, and
# withCallAreas before it on a port that has one: #4778, the USING items' bytes), equivalence_java.py (runBatch).
PROOF_ROOTS = ("runTask", "handleCall", "withCallAreas", "runBatch")

# A declaration's header is the code between the `;`, `{` or `}` before a `{` and that `{`; each pattern below is
# matched against one header, whole (fullmatch), so a scan is linear in the file. `<type> <name>(...)` headers that
# are statements, not declarations (else if (...), return new X(...)), are told apart by these words.
_MODIFIERS = {"public", "protected", "private", "static", "final", "synchronized", "abstract", "native", "default"}
_NOT_A_TYPE = {"new", "return", "else", "throw", "case", "yield", "assert", "do", *_MODIFIERS}  # + a constructor
_NOT_A_NAME = {"if", "for", "while", "switch", "catch", "synchronized", "try", "do", "else", "return", "new"}
_ANNOTATIONS = r"(?P<ann>(?:@[\w.$]+(?:\s*\([^()]*\))?\s*)*)"
_MODS = r"(?P<mods>(?:(?:public|protected|private|static|final|synchronized|abstract|native|default|strictfp)\s+)*)"
_PARAMS = r"\s*\((?P<params>[^()]*(?:\([^()]*\)[^()]*)*)\)\s*(?:throws\s+[\w.$,\s]+)?"
_DECL = re.compile(
    _ANNOTATIONS + _MODS + r"(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>\s*)?"
    r"(?P<type>[\w.$]+(?:\s*<[^()]*>)?(?:\s*\[\s*\])*)\s+(?P<name>[A-Za-z_$][\w$]*)" + _PARAMS
)
# A constructor `Name(...)`, and a record's compact constructor `Name`, when Name is a class of the file.
_CTOR = re.compile(_ANNOTATIONS + _MODS + r"(?P<name>[A-Z][\w$]*)(?:" + _PARAMS + r")?")
_CALL = re.compile(
    r"(?<![\w$])(?:(?P<recv>[A-Za-z_$][\w$]*)\s*\.\s*)?(?<![\w$])(?P<name>[A-Za-z_$][\w$]*)\s*\(|::\s*(?P<ref>[\w$]+)"
)
_FIELD = re.compile(r"\b(?P<type>[A-Z][\w$]*)\s+(?P<var>[a-z_$][\w$]*)\s*[;=,)]")
_CLASS = re.compile(r"\b(?:class|record|enum|interface)\s+(?P<name>[A-Z][\w$]*)")
# What the forge puts in a handler it generates and leaves to the porter (cobol_to_java_*_forge.py): a log line, a
# bare return, return null / the request / 0, return ResponseEntity...; each matched against one statement.
_STUB_STATEMENT = re.compile(
    r"(?:log|logger|LOG)\s*\.\s*\w+\s*\(.*\)|return(?:\s+(?:null|request|0))?|return\s+ResponseEntity\s*\..*",
    re.S,
)


def strip_java(text: str) -> str:
    """The source with every comment and string / char literal blanked (newlines and the quotes kept), so braces,
    parentheses and names inside them are not read as code."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            out.append('"' + re.sub(r"[^\n]", " ", text[i + 1 : j - 1]) + '"')
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(c + " " * max(j - i - 2, 0) + (c if j - i >= 2 else ""))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _close(text: str, start: int) -> int:
    """The index just past the brace that closes the one at `start`."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return k + 1
    return len(text)


@dataclass
class Method:
    cls: str
    name: str
    line: int
    end: int
    visibility: str
    stub: bool
    body: str = field(repr=False, default="")
    override: bool = False  # @Override: the JDK or a framework calls it (compareTo, run, apply)
    constructor: bool = False  # run whenever its class is made, which this does not follow
    generated: bool = False  # its body is the generated service's, unchanged (set by analyse(generated=...))

    def as_dict(self) -> dict[str, Any]:
        return {"method": self.name, "line": self.line, "end": self.end, "visibility": self.visibility,
                "stub": self.stub, "generated": self.generated}  # fmt: skip


def _norm(body: str) -> str:
    return re.sub(r"\s+", "", body)


@dataclass
class JavaUnit:
    """One .java file: its top-level class, its methods, and its fields' declared types."""

    path: Path
    cls: str
    methods: list[Method]
    fields: dict[str, str]
    outside: str = ""  # the code outside every method: field initialisers and initialiser blocks run anyway


def _visibility(mods: str) -> str:
    words = mods.split()
    return next((v for v in ("public", "protected", "private") if v in words), "package")


def _is_stub(body: str) -> bool:
    inner = body.strip()[1:-1] if body.strip().startswith("{") else body
    if "{" in inner or "}" in inner:
        return False
    return all(_STUB_STATEMENT.fullmatch(st.strip()) for st in inner.split(";") if st.strip())


def _headers(src: str) -> Iterator[tuple[int, str]]:
    """(offset, text) of the code before each `{`, back to the previous `;`, `{` or `}`."""
    last = 0
    for i, c in enumerate(src):
        if c in ";}":
            last = i + 1
        elif c == "{":
            yield last, src[last:i]
            last = i + 1


def parse_java(path: Path, text: str | None = None) -> JavaUnit:
    """The methods declared in a Java file (methods of named nested classes included; those of anonymous classes
    and local classes belong to the method they sit in)."""
    raw = path.read_text(encoding="utf-8") if text is None else text
    src = strip_java(raw)
    classes = {c.group("name") for c in _CLASS.finditer(src)}
    top = _CLASS.search(src)
    cls = top.group("name") if top else path.stem
    # (name offset, body end, name, visibility, @Override, constructor)
    found: list[tuple[int, int, str, str, bool, bool]] = []
    for at, head in _headers(src):
        lead = len(head) - len(head.lstrip())
        h = head.strip()
        brace = at + len(head)
        m = _DECL.fullmatch(h)
        if m and m.group("name") not in _NOT_A_NAME and m.group("type").split("<")[0].strip() not in _NOT_A_TYPE:
            found.append((at + lead + m.start("name"), _close(src, brace), m.group("name"),
                          _visibility(m.group("mods")), "@Override" in m.group("ann"), False))  # fmt: skip
            continue
        c = _CTOR.fullmatch(h)
        if c and c.group("name") in classes:
            found.append((at + lead + c.start("name"), _close(src, brace), c.group("name"),
                          _visibility(c.group("mods")), False, True))  # fmt: skip
    methods: list[Method] = []
    inside_until = 0
    outside: list[str] = []
    for start, end, name, vis, override, ctor in found:
        if start < inside_until:  # an anonymous / local class's method: part of the enclosing method
            continue
        outside.append(src[inside_until:start])
        inside_until = end
        body = src[src.index("{", start) : end]
        methods.append(Method(cls=cls, name=name, line=src.count("\n", 0, start) + 1,
                              end=src.count("\n", 0, end) + 1, visibility=vis, stub=_is_stub(body), body=body,
                              override=override, constructor=ctor))  # fmt: skip
    outside.append(src[inside_until:])
    rest = "".join(outside)
    # A field's declared type (outside every method): what `casubService.handleLink(...)` resolves through.
    fields = {f.group("var"): f.group("type") for f in reversed(list(_FIELD.finditer(rest)))}
    return JavaUnit(path=path, cls=cls, methods=methods, fields=fields, outside=rest)


def java_files(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        out += sorted(p.rglob("*.java")) if p.is_dir() else [p]
    return out


def reach(units: list[JavaUnit], roots: Iterable[str] = PROOF_ROOTS) -> dict[str, Any]:
    """{class: {"roots": [...], "methods": n, "reached": [...], "unproven": [method dicts]}} for every unit
    that declares a proof root; a unit with none (a DTO, a helper class) is reached only through the others."""
    roots = tuple(roots)
    by_class: dict[str, list[JavaUnit]] = {}
    for u in units:
        by_class.setdefault(u.cls, []).append(u)
    names = {(u.cls, m.name) for u in units for m in u.methods}
    reached: set[tuple[str, str]] = set()
    todo = [(u.cls, m.name) for u in units for m in u.methods if m.name in roots or m.constructor or m.override]

    def calls(u: JavaUnit, code: str) -> None:
        for c in _CALL.finditer(code):
            callee = c.group("name") or c.group("ref")
            recv = c.group("recv")
            target = u.fields.get(recv) if recv else None
            if target and (target, callee) in names:
                todo.append((target, callee))
            elif (u.cls, callee) in names:
                todo.append((u.cls, callee))

    for u in units:  # field initialisers and initialiser blocks run whenever the class is used
        calls(u, u.outside)
    analysed = sorted({u.cls for u in units if any(m.name in roots for m in u.methods)})
    while todo:
        key = todo.pop()
        if key in reached:
            continue
        reached.add(key)
        cls, name = key
        for u in by_class.get(cls, []):
            for m in u.methods:
                if m.name == name:
                    calls(u, m.body)
    out: dict[str, Any] = {}
    for cls in analysed:
        ms = [m for u in by_class[cls] for m in u.methods]
        unproven = [m.as_dict() for m in ms if (cls, m.name) not in reached]
        out[cls] = {
            "files": sorted(str(u.path) for u in by_class[cls]),
            "roots": sorted({m.name for m in ms if m.name in roots}),
            "methods": len(ms),
            "unproven": unproven,
            # behaviour the port added (not a stub, not the generator's own body) that no proof runs
            "ported_unproven": [m["method"] for m in unproven if not m["stub"] and not m["generated"]],
        }
    return out


def analyse(
    paths: Iterable[Path], roots: Iterable[str] = PROOF_ROOTS, generated: Iterable[Path] = ()
) -> dict[str, Any]:
    """The reach report of the port's Java under `paths`. `generated`: the generated project's files the port
    was made from; a method whose body is still theirs (a forge helper the port left alone) is reported as
    generated rather than ported."""
    units = [parse_java(p) for p in java_files(paths)]
    bodies: dict[tuple[str, str], set[str]] = {}
    for g in java_files(generated):
        if g.is_file():
            for m in parse_java(g).methods:
                bodies.setdefault((m.cls, m.name), set()).add(_norm(m.body))
    for u in units:
        for m in u.methods:
            m.generated = _norm(m.body) in bodies.get((m.cls, m.name), set())
    return reach(units, roots)


def summary(report: dict[str, Any]) -> str:
    """One line per class: what the proof runs it through, and the methods it never runs."""
    lines = []
    for cls, r in report.items():
        through = " / ".join(r["roots"])
        ported = r["ported_unproven"]
        stubs = [m["method"] for m in r["unproven"] if m["stub"] or m["generated"]]
        if not ported and not stubs:
            lines.append(f"{cls}: proven through {through}; every method is reached")
            continue
        parts = []
        if ported:
            parts.append(f"{len(ported)} ported method(s) the proof never runs: {', '.join(sorted(set(ported)))}")
        if stubs:
            parts.append(f"{len(stubs)} left as generated: {', '.join(sorted(set(stubs)))}")
        lines.append(f"{cls}: proven through {through} only; " + "; ".join(parts))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", type=Path, help=".java files or directories")
    ap.add_argument("--generated", nargs="*", type=Path, default=[],
                    help="the generated service file(s) the port was made from: their unchanged methods are not "
                         "counted as ported")  # fmt: skip
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a ported method is never run by the proof")
    opts = ap.parse_args(argv)
    report = analyse(opts.paths, generated=opts.generated)
    print(json.dumps(report, indent=1) if opts.json else summary(report))
    return 1 if opts.strict and any(r["ported_unproven"] for r in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
