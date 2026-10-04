#!/usr/bin/env python3
"""
#4023: COBOL paragraph and branch coverage from a GnuCOBOL trace -- how much of a program a run proves.

A proof (the CICS crucible's scenarios, an equivalence case, a fresh estate's own test) only proves the paths it
runs. This module says which ones those are, per program:

  paragraphs   every paragraph and section the run entered, out of the program's LIVE ones -- the engine's own
               reachability (cobol_graveyard_finder.procedure_units / reachable_units: PERFORM, THRU, GO TO,
               fall-through, CICS HANDLE labels) sets dead code apart, so "no scenario reaches it" and "nothing
               can reach it" are never the same line of the report
  branches     every outcome of every IF (true / false) and EVALUATE (each WHEN arm, WHEN OTHER, or no arm when
               there is no OTHER) in live code, and whether the run took it
  handler      the labels an EXEC CICS HANDLE CONDITION / AID / ABEND names, and whether the run entered them

How: the program is compiled with `cobc -ftraceall` (TRACE_FLAG) and run with COB_SET_TRACE / COB_TRACE_FILE
(trace_env). GnuCOBOL then writes every paragraph / section entered and every statement executed, with its
verb and source line, in execution order. A paragraph is matched by name. A branch outcome is read from the
statement that executes right after the IF / EVALUATE: it is the first statement of the arm taken, or --
for an IF with no ELSE, an EVALUATE with no WHEN OTHER -- a statement outside every arm.

The compiled text need not be the original: the CICS harness translates each EXEC CICS into several lines
(equivalence_cics.translate), and the equivalence harness blanks CBL cards. LineMap aligns the compiled lines
with the original's (difflib), so a trace line maps to the original line exactly (an unchanged line), loosely
(a line of a rewritten block maps to the block's first original line, verb unknown), or not at all (a line the
harness inserted, which the trace reading skips). Branch points are found in the original source, so the
translator's own IFs (RESP tests, the condition dispatch) are never counted.

Counted as unresolvable, not guessed: an IF / EVALUATE whose own line the compiled text changed, and one whose
arms cannot be told apart by (line, verb) -- `IF A MOVE 1 TO X ELSE MOVE 2 TO X` on one line.

    python tests/tools/cobol_coverage.py measure --source ORIG.cbl [--compiled COMPILED.cbl] --trace T [T ...]
                                                 [--copybooks DIR] [--encoding ENC] [--json OUT]
    python tests/tools/cobol_coverage.py autotest CASE_DIR [CASE_DIR ...] --out DIR [--image IMAGE]

`measure` reads traces a harness kept (cics_crucible.py --keep, equivalence.py run --keep: the trace.txt files
beside each run). `autotest` runs at_extract cases (a GNU Autotest suite's programs, e.g. the opensourcecobol4j
fresh estate) under GnuCOBOL with tracing: `${COMPILE}` / `${COBJ}` and friends compile each source as a traced
module, `java PROG` runs it with cobcrun, and each case gets its programs' coverage (coverage.json, coverage.md).
The CICS crucible (cics_crucible.py) and the equivalence harness (equivalence.py, CardDemo) measure it on every
COBOL run.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.tools.cobol_to_cobol import cobol_graveyard_finder as gy  # noqa: E402

FORMAT = "cobol-coverage/1"
TRACE_FLAG = "-ftraceall"
TRACE_NAME = "trace.txt"


def trace_env(path: str) -> str:
    """The shell prefix that makes a -ftraceall program write its trace to `path` (it overwrites the file)."""
    return f"COB_SET_TRACE=Y COB_TRACE_FILE={path} "


# ---- the program: units, dead units, branch points --------------------------------------------------------
# A statement starts at one of these words (reserved, so never a data name). NEXT only with SENTENCE.
VERBS = frozenset(
    "ACCEPT ADD ALLOCATE ALTER CALL CANCEL CLOSE COMMIT COMPUTE CONTINUE DELETE DISPLAY DIVIDE ENTRY EVALUATE "
    "EXAMINE EXEC EXHIBIT EXIT FREE GENERATE GO GOBACK IF INITIALIZE INITIATE INSPECT INVOKE JSON MERGE MOVE "
    "MULTIPLY OPEN PERFORM RAISE READ READY RELEASE RESET RESUME RETURN REWRITE ROLLBACK SEARCH SET SORT START "
    "STOP STRING SUBTRACT SUPPRESS TERMINATE TRANSFORM UNLOCK UNSTRING VALIDATE WRITE XML".split()
)
_TOKEN = re.compile(r"""\.(?=\s|$)|[^\s.,;()=<>+*/:&'"]+(?:\.[^\s.,;()=<>+*/:&'"]+)*|\S""")
_PROGRAM_ID = re.compile(r"PROGRAM-ID\s*\.?\s*['\"]?([^\s.'\"]+)", re.I)
_PROCEDURE = re.compile(r"PROCEDURE[ \t]+DIVISION", re.I)
_FREE = re.compile(r">>\s*SOURCE\s+(?:FORMAT\s+)?(?:IS\s+)?FREE", re.I)


@dataclasses.dataclass
class Arm:
    """One outcome of a branch point: `first` the (line, verb) of its first statement, None if it has none."""

    outcome: str
    first: Optional[tuple[int, str]] = None


@dataclasses.dataclass
class Branch:
    kind: str  # IF | EVALUATE
    line: int
    unit: Optional[str]
    arms: list[Arm]
    fallthrough: Optional[str] = None  # the outcome taken when no arm's first statement follows (false / none)

    def outcomes(self) -> list[str]:
        return [a.outcome for a in self.arms] + ([self.fallthrough] if self.fallthrough else [])


@dataclasses.dataclass
class Inventory:
    program: str
    source: str
    units: list[dict[str, Any]]  # {name, kind, line}
    dead: set[str]
    branches: list[Branch]
    unresolvable: list[dict[str, Any]]  # branch points the trace cannot resolve, and why
    handler_labels: list[str]

    @property
    def live(self) -> list[str]:
        return [u["name"] for u in self.units if u["name"] not in self.dead]

    def unit_of(self, line: int) -> Optional[str]:
        name = None
        for u in self.units:
            if u["line"] and u["line"] <= line:
                name = u["name"]
        return name


def _code_lines(text: str) -> list[tuple[int, str]]:
    """(1-based line, the code part upper-cased with literals blanked) for each line of the PROCEDURE DIVISION."""
    lines = text.split("\n")
    free = bool(_FREE.search(text))
    start = next((i for i, x in enumerate(lines) if _PROCEDURE.search(x) and not _is_comment(x, free)), None)
    if start is None:
        return []
    out = []
    for i in range(start, len(lines)):
        raw = lines[i].rstrip("\r")
        if free:
            code = None if raw.lstrip().startswith("*>") else gy._blank_literals(raw).split("*>", 1)[0]
        else:
            code = gy._code_area(raw)
        if code is None:
            continue
        if i == start:  # the header sentence itself (USING ...) holds no statement
            code = _PROCEDURE.sub(" ", code.upper(), count=1)
        out.append((i + 1, code.upper()))
    return out


def _is_comment(line: str, free: bool) -> bool:
    if free:
        return line.lstrip().startswith("*>")
    return len(line) > 6 and line[6] in "*/"


def _unit_lines(text: str) -> dict[str, int]:
    """{unit name: its header's 1-based line} from the raw source (fixed format, as procedure_units reads it)."""
    found: dict[str, int] = {}
    lines = text.split("\n")
    start = next((i for i, x in enumerate(lines) if _PROCEDURE.search(x)), None)
    for i in range(start + 1 if start is not None else len(lines), len(lines)):
        line = gy._trim_fixed_format(lines[i].rstrip("\r")).upper()
        if len(line) > 6 and line[6] in "*/D":
            continue
        name = gy.unit_header(line)
        if name is None:
            m = gy._UNIT_HEADER_INLINE.match(line) or gy._UNIT_HEADER_OPEN.match(line)
            name = m.group(1) if m and not gy._NOT_A_PARAGRAPH.fullmatch(m.group(1)) else None
        if name and name not in found:
            found[name] = i + 1
    return found


class _Open:
    def __init__(self, kind: str, line: int) -> None:
        self.kind, self.line = kind, line
        self.then_first: Optional[tuple[int, str]] = None
        self.else_first: Optional[tuple[int, str]] = None
        self.has_else = False
        self.arms: list[dict[str, Any]] = []  # EVALUATE: {outcome, first, other}


def branch_points(text: str) -> tuple[list[Branch], Counter[tuple[int, str]]]:
    """Every IF and EVALUATE of the PROCEDURE DIVISION with its arms' first statements, and how many statements
    start with each (line, verb) -- a key used twice cannot be told apart in a trace."""
    tokens = [(ln, m.group(0)) for ln, code in _code_lines(text) for m in _TOKEN.finditer(code)]
    stmts: Counter[tuple[int, str]] = Counter()
    stack: list[_Open] = []
    done: list[Branch] = []

    def close(o: _Open) -> None:
        if o.kind == "IF":
            arms = [Arm("true", o.then_first)] + ([Arm("false", o.else_first)] if o.has_else else [])
            done.append(Branch("IF", o.line, None, arms, None if o.has_else else "false"))
        elif o.kind == "EVALUATE" and o.arms:
            arms = [Arm(a["outcome"], a["first"]) for a in o.arms]
            other = any(a["other"] for a in o.arms)
            done.append(Branch("EVALUATE", o.line, None, arms, None if other else "none"))

    def pop_to(kind: str) -> None:
        if not any(o.kind == kind for o in stack):
            return
        while stack:
            o = stack.pop()
            close(o)
            if o.kind == kind:
                return

    in_exec = False
    i = 0
    while i < len(tokens):
        line, tok = tokens[i]
        nxt = tokens[i + 1][1] if i + 1 < len(tokens) else ""
        i += 1
        if in_exec:
            in_exec = tok != "END-EXEC"
            continue
        if tok == ".":
            while stack:
                close(stack.pop())
        elif tok == "ELSE":
            while stack and stack[-1].kind == "IF" and stack[-1].has_else:
                close(stack.pop())
            if stack and stack[-1].kind == "IF":
                stack[-1].has_else = True
        elif tok == "END-IF":
            pop_to("IF")
        elif tok == "END-EVALUATE":
            pop_to("EVALUATE")
        elif tok == "END-SEARCH":
            pop_to("SEARCH")
        elif tok == "WHEN":
            while stack and stack[-1].kind == "IF":  # an IF left open in the previous arm ends with it
                close(stack.pop())
            if stack and stack[-1].kind == "EVALUATE":
                ev = stack[-1]
                other = nxt == "OTHER"
                if ev.arms and ev.arms[-1]["first"] is None and not other and not ev.arms[-1]["other"]:
                    continue  # WHEN a WHEN b: one arm
                ev.arms.append({"outcome": "OTHER" if other else f"WHEN@{line}", "first": None, "other": other})
        elif tok in VERBS or (tok == "NEXT" and nxt == "SENTENCE"):
            key = (line, tok)
            stmts[key] += 1
            if stack:
                top = stack[-1]
                if top.kind == "IF" and not top.has_else and top.then_first is None:
                    top.then_first = key
                elif top.kind == "IF" and top.has_else and top.else_first is None:
                    top.else_first = key
                elif top.kind == "EVALUATE" and top.arms and top.arms[-1]["first"] is None:
                    top.arms[-1]["first"] = key
            if tok in ("IF", "EVALUATE", "SEARCH"):
                stack.append(_Open(tok, line))
            elif tok == "EXEC":
                in_exec = True
    while stack:
        close(stack.pop())
    return sorted(done, key=lambda b: b.line), stmts


def program_id(text: str) -> Optional[str]:
    """The PROGRAM-ID's name, read in the code area (columns 8-72): a name on the line after `PROGRAM-ID.` must not
    be the sequence number in columns 73-80 / 1-6 (COTRTUPC's `002200 PROGRAM-ID. ... 00220000`)."""
    area = "\n".join("" if len(ln) > 6 and ln[6] in "*/" else ln[7:72] for ln in text.split("\n"))
    m = _PROGRAM_ID.search(area)
    return m.group(1).upper() if m else None


def inventory(path: Path, copybook_root: Optional[Path] = None, encoding: Optional[str] = None,
              text: Optional[str] = None, label: Optional[str] = None) -> Inventory:  # fmt: skip
    """What a program holds: its units (paragraphs and sections, with the dead ones -- the engine's
    reachability, copybooks resolved as x_ray_dead_code resolves them), its branch points and HANDLE labels."""
    from gitgalaxy.core.source_text import read_source

    raw = text if text is not None else read_source(path, declared=encoding).text
    upper = raw.upper()
    content = gy.resolve_copybooks(upper, path, copybook_root, None, encoding) if path.exists() else upper
    split = gy.split_procedure_division(content)
    units = gy.procedure_units(split[1]) if split else []
    names = [u["name"] for u in units if u["name"]]
    dead = set(names) - gy.reachable_units(units) if units else set()
    where = _unit_lines(raw)
    handler: list[str] = []
    for u in units:
        for m in gy._CICS_HANDLE.finditer(u["text"]):
            handler += [t for t in gy._CICS_LABEL.findall(m.group(1)) if t in names and t not in handler]
    inv = Inventory(program=program_id(raw) or path.stem.upper(), source=label or str(path),
                    units=[{"name": u["name"], "kind": u["kind"], "line": where.get(u["name"])}
                           for u in units if u["name"]],
                    dead=dead, branches=[], unresolvable=[], handler_labels=handler)  # fmt: skip
    branches, stmts = branch_points(raw)
    for b in branches:
        b.unit = inv.unit_of(b.line)
        keys = [(b.line, b.kind)] + [a.first for a in b.arms if a.first]
        firsts = [a.first for a in b.arms if a.first]
        if any(stmts[k] > 1 for k in keys) or len(set(firsts)) < len(firsts):
            inv.unresolvable.append({"line": b.line, "kind": b.kind, "unit": b.unit,
                                     "why": "two statements on its line share a verb: the trace cannot tell them apart"})  # fmt: skip
        elif any(a.first is None for a in b.arms):
            inv.unresolvable.append({"line": b.line, "kind": b.kind, "unit": b.unit,
                                     "why": "an arm with no statement: the trace cannot show it taken"})  # fmt: skip
        else:
            inv.branches.append(b)
    return inv


# ---- the trace ---------------------------------------------------------------------------------------------
@dataclasses.dataclass
class Event:
    program: str
    kind: str  # Entry | Section | Paragraph | Exit | stmt
    name: str  # the unit's name, or the statement's verb as GnuCOBOL prints it (GO TO, STOP RUN, ...)
    line: int
    source: str


_EVENT = re.compile(r"^Program-Id:\s+(\S+)\s+(?:(Entry|Section|Paragraph|Exit):\s+)?(\S.*?)\s+Line:\s+(\d+)\s*$")
_SOURCE = re.compile(r"^Source:\s+'(.*)'\s*$")


def read_trace(data: bytes, encoding: str = "utf-8") -> list[Event]:
    """A GnuCOBOL -ftraceall trace as events, in execution order."""
    events: list[Event] = []
    source = ""
    for raw in data.decode(encoding, "replace").splitlines():
        m = _SOURCE.match(raw)
        if m:
            source = Path(m.group(1)).name
            continue
        m = _EVENT.match(raw)
        if m:
            events.append(Event(m.group(1).upper(), m.group(2) or "stmt", m.group(3).strip().upper(), int(m.group(4)),
                                source))  # fmt: skip
    return events


class LineMap:
    """Compiled line -> (original line, exact). Unchanged lines map exactly, and so does a line the harness
    rewrote in place (`IF WS-RESP NOT = DFHRESP(NORMAL)` -> `... NOT = 0`: paired by similarity inside the
    rewritten block, in order); any other line of a rewritten block maps, not exactly, to the original line it
    stands for (the first unpaired one after the last pair: an EXEC CICS's expansion maps to the EXEC); a line
    the harness inserted maps to nothing."""

    SIMILAR = 0.75  # difflib ratio at which a rewritten line is the same line

    def __init__(self, original: str, compiled: Optional[str] = None) -> None:
        a = [x.rstrip() for x in original.split("\n")]
        b = a if compiled is None else [x.rstrip() for x in compiled.split("\n")]
        self.map: dict[int, tuple[int, bool]] = {}
        self.exact: set[int] = set()
        if a == b:
            self.map = {i + 1: (i + 1, True) for i in range(len(a))}
            self.exact = set(self.map)
            return
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "equal":
                for k in range(j2 - j1):
                    self.map[j1 + k + 1] = (i1 + k + 1, True)
                    self.exact.add(i1 + k + 1)
            elif tag == "replace":
                pairs = self._pairs(a, b, i1, i2, j1, j2)
                nxt = i1
                for j in range(j1, j2):
                    if j in pairs:
                        self.map[j + 1] = (pairs[j] + 1, True)
                        self.exact.add(pairs[j] + 1)
                        nxt = pairs[j] + 1
                    else:
                        self.map[j + 1] = (min(nxt, i2 - 1) + 1, False)

    def _pairs(self, a: list[str], b: list[str], i1: int, i2: int, j1: int, j2: int) -> dict[int, int]:
        """{compiled index: original index} for the lines of a rewritten block that are the same line, in order."""
        if i2 - i1 == j2 - j1:
            return {j1 + k: i1 + k for k in range(j2 - j1)}
        pairs: dict[int, int] = {}
        start = j1
        for i in range(i1, i2):
            best, score = None, self.SIMILAR
            for j in range(start, j2):
                r = difflib.SequenceMatcher(None, a[i].strip(), b[j].strip(), autojunk=False).ratio()
                if r >= score:
                    best, score = j, r
            if best is not None:
                pairs[best] = i
                start = best + 1
        return pairs

    def get(self, line: int) -> Optional[tuple[int, bool]]:
        return self.map.get(line)


@dataclasses.dataclass
class Hits:
    """What one run (or several, merged) executed of one program."""

    units: set[str] = dataclasses.field(default_factory=set)
    outcomes: set[tuple[int, str]] = dataclasses.field(default_factory=set)  # (branch line, outcome)

    def merge(self, other: "Hits") -> "Hits":
        return Hits(self.units | other.units, self.outcomes | other.outcomes)

    def as_dict(self) -> dict[str, Any]:
        return {"units": sorted(self.units), "outcomes": [f"{ln}:{o}" for ln, o in sorted(self.outcomes)]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Hits":
        outs = set()
        for s in d.get("outcomes", []):
            ln, _, o = s.partition(":")
            outs.add((int(ln), o))
        return cls(set(d.get("units", [])), outs)


def hits(inv: Inventory, events: Iterable[Event], lines: LineMap, compiled_name: Optional[str] = None) -> Hits:
    """The units entered and branch outcomes taken by `inv`'s program in a trace. `compiled_name` is the file
    the program was compiled from as the trace names it (its basename); statements from other sources -- a
    COPY member's -- are not the program's own lines."""
    mine = [e for e in events if e.program == inv.program]
    # every unit entered, the ones the inventory lacks too (summary: `unread`); `L$0`-style names are GnuCOBOL's own
    out = Hits(units={e.name for e in mine if e.kind in ("Section", "Paragraph") and "$" not in e.name})
    points = {b.line: b for b in inv.branches}
    stmts: list[tuple[int, str, bool]] = []  # (original line, verb, exact)
    for e in mine:
        if e.kind != "stmt" or (compiled_name and e.source and e.source != compiled_name):
            continue
        if e.name.split()[0] not in VERBS and e.name != "NEXT SENTENCE":  # GnuCOBOL traces some WHENs too
            continue
        m = lines.get(e.line)
        if m is not None:
            stmts.append((m[0], e.name.split()[0], m[1]))
    for n, (line, verb, exact) in enumerate(stmts):
        b = points.get(line)
        if b is None or not exact or verb != b.kind or n + 1 >= len(stmts):
            continue
        nl, nv, nexact = stmts[n + 1]
        taken = next((a.outcome for a in b.arms if a.first and nl == a.first[0] and (not nexact or nv == a.first[1])),
                     b.fallthrough)  # fmt: skip
        if taken:
            out.outcomes.add((b.line, taken))
    return out


def counted(inv: Inventory, got: Hits, blind: Iterable[int] = ()) -> Hits:
    """`got` restricted to what summary() counts: live units, and outcomes of the live, traceable branch points."""
    blind = set(blind)
    ok = {(b.line, o) for b in inv.branches if b.unit not in inv.dead and b.line not in blind for o in b.outcomes()}
    return Hits(got.units & set(inv.live), got.outcomes & ok)


def untraceable(inv: Inventory, lines: LineMap) -> list[int]:
    """Branch points whose own line the compiled text changed: the trace cannot see them."""
    return [b.line for b in inv.branches if b.line not in lines.exact]


# ---- the summary ---------------------------------------------------------------------------------------------
def summary(inv: Inventory, got: Hits, blind: Iterable[int] = ()) -> dict[str, Any]:
    """Coverage of `inv` by `got`: paragraphs (live units entered / live units; dead units apart), branch
    outcomes in live code (taken / all), HANDLE labels entered, and the live code no run reached."""
    blind = set(blind)
    live = inv.live
    covered = [n for n in live if n in got.units]
    counted = [b for b in inv.branches if b.unit not in inv.dead and b.line not in blind]
    outcomes = [(b, o) for b in counted for o in b.outcomes()]
    taken = [(b, o) for b, o in outcomes if (b.line, o) in got.outcomes]
    labels = [lbl for lbl in inv.handler_labels if lbl not in inv.dead]
    return {
        "program": inv.program,
        "source": inv.source,
        # a dead unit a run entered: the engine's reachability missed a path (an engine defect to log)
        "paragraphs": {
            "covered": len(covered),
            "live": len(live),
            "dead": sorted(inv.dead),
            "dead_but_executed": sorted(inv.dead & got.units),
            # a unit a run entered that the engine does not read as one: the counts above miss it
            "unread": sorted(got.units - {u["name"] for u in inv.units}),
            "uncovered": [
                {"name": n, "line": next(u["line"] for u in inv.units if u["name"] == n)}
                for n in live
                if n not in got.units
            ],
        },  # fmt: skip
        "branches": {
            "covered": len(taken),
            "total": len(outcomes),
            "uncovered": [
                {"line": b.line, "kind": b.kind, "outcome": o, "unit": b.unit}
                for b, o in outcomes
                if (b.line, o) not in got.outcomes
            ],
            "in_dead_code": sum(len(b.outcomes()) for b in inv.branches if b.unit in inv.dead),
            "unresolvable": inv.unresolvable
            + [
                {"line": ln, "kind": "?", "unit": inv.unit_of(ln), "why": "the compiled text changed its line"}
                for ln in sorted(blind)
            ],
        },  # fmt: skip
        "handler_labels": {
            "covered": sum(lbl in got.units for lbl in labels),
            "total": len(labels),
            "uncovered": [lbl for lbl in labels if lbl not in got.units],
        },  # fmt: skip
    }


def covers(s: dict[str, Any], runs: int, what: str = "run") -> str:
    """`N runs cover X/Y paragraphs and A/B branches`: what ran, claiming nothing."""
    p, b = s["paragraphs"], s["branches"]
    return (f"{runs} {what}{' covers' if runs == 1 else 's cover'} {p['covered']}/{p['live']} paragraphs and "
            f"{b['covered']}/{b['total']} branches")  # fmt: skip


def claim(s: dict[str, Any], scenarios: int, what: str = "scenario") -> str:
    """`proven on N scenarios, covering X/Y paragraphs and A/B branches` (#4023's wording)."""
    p, b = s["paragraphs"], s["branches"]
    return (f"proven on {scenarios} {what}{'' if scenarios == 1 else 's'}, covering {p['covered']}/{p['live']} "
            f"paragraphs and {b['covered']}/{b['total']} branches")  # fmt: skip


def gaps_md(s: dict[str, Any]) -> list[str]:
    """The live code no run reached, as Markdown bullets: each one a scenario to propose."""
    out = [f"- paragraph `{u['name']}` (line {u['line']})" for u in s["paragraphs"]["uncovered"]]
    out += [f"- {u['kind']} at line {u['line']}{' in `' + u['unit'] + '`' if u['unit'] else ''}: "
            f"{_outcome_words(u['outcome'])}" for u in s["branches"]["uncovered"]]  # fmt: skip
    out += [f"- HANDLE label `{lbl}` never entered" for lbl in s["handler_labels"]["uncovered"]]
    return out


def _outcome_words(o: str) -> str:
    if o in ("true", "false"):
        return f"never {o}"
    if o == "none":
        return "no WHEN arm matched: never"
    return f"`{o.replace('@', ' at line ')}` never taken"


def run_coverage(source: Path, original: str, compiled: Optional[str], traces: list[Path], compiled_name: str,
                 copybooks: Optional[Path] = None, encoding: Optional[str] = None) -> dict[str, Any]:  # fmt: skip
    """One program's coverage over a harness's traces: `source` the original (its path, for COPY members; its
    text `original`), `compiled` the text the harness compiled as `compiled_name` (None: the original)."""
    inv = inventory(source, copybooks, encoding, text=original)
    lines = LineMap(original, compiled)
    got = Hits()
    for t in traces:
        got = got.merge(hits(inv, read_trace(t.read_bytes(), encoding or "utf-8"), lines, compiled_name))
    return summary(inv, got, untraceable(inv, lines))


def measure_files(source: Path, traces: list[Path], compiled: Optional[Path] = None,
                  copybooks: Optional[Path] = None, encoding: Optional[str] = None) -> dict[str, Any]:  # fmt: skip
    """The `measure` command: one program's coverage over the traces a harness kept."""
    from gitgalaxy.core.source_text import read_source

    orig = read_source(source, declared=encoding).text
    comp = read_source(compiled, declared=encoding).text if compiled else None
    return run_coverage(source, orig, comp, traces, (compiled or source).name, copybooks, encoding)


def write_run_coverage(out: Path, **kw: Any) -> Optional[dict[str, Any]]:
    """run_coverage into `out` (coverage.json) for a harness that must not fail on it: an error is written and
    printed, and the run goes on (the proof is the outputs; coverage only says how much it proves)."""
    try:
        s: dict[str, Any] = run_coverage(**kw)
    except Exception as e:  # noqa: BLE001 -- reported, never fatal to the harness's run
        s = {"error": f"{type(e).__name__}: {e}"}
        print(f"COBOL coverage not measured: {s['error']}", file=sys.stderr)
    out.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return s if "error" not in s else None


def headline(s: dict[str, Any], runs: int, proven: bool, what: str = "run") -> str:
    """The claim when the proof holds; else how much the COBOL runs covered, without claiming anything."""
    return claim(s, runs, what) if proven else f"not proven; {covers(s, runs, what)}"


def report_lines(s: Optional[dict[str, Any]], runs: int, proven: bool, what: str = "run") -> list[str]:
    """A harness report's coverage section (Markdown): the headline, then the gaps."""
    if not s:
        return []
    rest = summary_md(s, runs, what)[1:]
    while rest and not rest[0]:
        rest.pop(0)
    return [
        "",
        "## COBOL coverage (#4023)",
        "",
        f"{s['program']}: {headline(s, runs, proven, what)}.",
        "",
        *rest,
    ]


def summary_md(s: dict[str, Any], runs: int, what: str = "run") -> list[str]:
    lines = [f"**{s['program']}** ({s['source']}): {covers(s, runs, what)}; HANDLE labels "
             f"{s['handler_labels']['covered']}/{s['handler_labels']['total']}."]  # fmt: skip
    if s["paragraphs"]["dead"]:
        lines.append(f"Dead (nothing can reach them): {', '.join(f'`{n}`' for n in s['paragraphs']['dead'])}.")
    if s["paragraphs"].get("unread"):
        lines.append(
            "**A run entered units the engine does not read** (not counted above -- an engine defect): "
            + ", ".join(f"`{n}`" for n in s["paragraphs"]["unread"])
            + "."
        )
    if s["paragraphs"].get("dead_but_executed"):
        lines.append(
            "**The engine calls these dead, but a run entered them** (a reachability defect): "
            + ", ".join(f"`{n}`" for n in s["paragraphs"]["dead_but_executed"])
            + "."
        )
    gaps = gaps_md(s)
    if gaps:
        lines += ["", "Live code no run reached:", "", *gaps]
    if s["branches"]["unresolvable"]:
        lines += ["", "Branch points the trace cannot resolve (not counted):", ""]
        lines += [f"- {u['kind']} at line {u['line']}: {u['why']}" for u in s["branches"]["unresolvable"]]
    return lines


# ---- autotest: a GNU Autotest suite's programs (at_extract cases) under GnuCOBOL -----------------------------
IMAGE = "gitgalaxy-gnucobol:3"
_SOURCE_EXTS = (".cob", ".cbl", ".CBL", ".COB")
# The Autotest variables a check's command compiles or runs with (opensourcecobol4j's atlocal); each becomes a
# shim on PATH. A compile builds every COBOL source it names as a traced module; `java PROG` runs PROG's module.
_SHIM_VARS = ("COMPILE", "COMPILE_DEFAULT", "COMPILE_SUBSCRIPT", "COMPILE_JP_COMPAT", "COMPILE_JP_COMPAT_DEFAULT",
              "COMPILE_LIMIT_TEST", "COMPILE_MODULE", "COMPILE_MODULE_JP_COMPAT", "COMPILE_MODULE_LIMIT_TEST",
              "COMPILE_MODULE_ESQL", "COMPILE_ONLY", "COMPILE_ONLY_JP_COMPAT", "COMPILE_ONLY_LIMIT_TEST", "COBJ",
              "COBC")  # fmt: skip
# the rest of atlocal as GnuCOBOL answers it: no split keys (so the "not yet" tests run), SKIP_TEST skips
_AT_ENV = ("RUN_MODULE=java", "RUN_MODULE_LOG=java", "SKIP_TEST='exit 77'", "COB_SPLITKEY_FLAGS=no")
_COMPILES = re.compile(r"\$\{?(?:" + "|".join(_SHIM_VARS) + r")\b")
STATUSES = ("ran", "skipped", "compile failed", "no run")
_SHIM_COMPILE = r"""#!/bin/bash
# #4023: an Autotest compile (cobj / cobc and its flags) as a traced GnuCOBOL module per COBOL source
free=""
for a in "$@"; do case "$a" in -free|-F|--free) free="-free";; esac; done
rc=0
for a in "$@"; do
  case "$a" in
    *.cob|*.cbl|*.COB|*.CBL)
      stem=$(basename "${a%.*}")
      cobc -m -ftraceall $free -o "$stem.so" "$a" || rc=1 ;;
  esac
done
exit $rc
"""
_SHIM_RUN = r"""#!/bin/bash
# #4023: `java [options] PROG [args]` -> the PROG module under cobcrun, traced to /work/trace/NNN.txt
while [ $# -gt 0 ]; do
  case "$1" in -cp|-classpath|--class-path) shift 2;; -*) shift;; *) break;; esac
done
prog="$1"; shift
n=$(ls /work/trace | wc -l)
COB_LIBRARY_PATH=. COB_SET_TRACE=Y COB_TRACE_FILE=$(printf '/work/trace/%03d.txt' "$n") cobcrun "$prog" "$@"
"""


def _case_programs(case: Path) -> dict[str, Path]:
    """{program id: its source} for each COBOL source a case writes (its last version)."""
    out: dict[str, Path] = {}
    for p in sorted(case.rglob("*")):
        if p.is_file() and p.suffix in _SOURCE_EXTS:
            text = p.read_bytes().decode("utf-8", "replace")
            pid = program_id(text)
            if pid and _PROCEDURE.search(text):
                out[pid] = p
    return out


def run_autotest_case(case: Path, work: Path, image: str = IMAGE) -> dict[str, Any]:
    """Run one at_extract case's steps under GnuCOBOL, traced; its programs' coverage."""
    exp = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    enc = exp.get("encoding") or "utf-8"
    if work.exists():
        shutil.rmtree(work)
    (work / "case").mkdir(parents=True)
    (work / "trace").mkdir()
    (work / "bin").mkdir()
    for p in case.iterdir():
        if p.name != "expected.json":
            (shutil.copytree if p.is_dir() else shutil.copy)(p, work / "case" / p.name)
    (work / "bin" / "gg-compile").write_text(_SHIM_COMPILE, encoding="ascii")
    (work / "bin" / "java").write_text(_SHIM_RUN, encoding="ascii")
    script = ["cd /work/run", "export PATH=/work/bin:$PATH", *(f"export {v}=gg-compile" for v in _SHIM_VARS),
              *(f"export {v}" for v in _AT_ENV)]  # fmt: skip
    for n, st in enumerate(exp["steps"]):
        if st["kind"] == "data":
            script.append(f"mkdir -p \"$(dirname '{st['path']}')\" && cp '/work/case/{st['file']}' '{st['path']}'")
        elif st["kind"] == "check":
            (work / f"step{n:03d}.sh").write_bytes(st["command"].encode(enc, "replace") + b"\n")
            script.append(f"(bash /work/step{n:03d}.sh) > /work/step{n:03d}.out 2>&1; rc=$?; echo $rc > /work/step{n:03d}.rc; "
                          "[ $rc -eq 77 ] && exit 77")  # fmt: skip
    (work / "run").mkdir()
    (work / "run.sh").write_text("\n".join(script) + "\nexit 0\n", encoding="utf-8")
    for f in ("gg-compile", "java"):
        (work / "bin" / f).chmod(0o755)
    user = ["--user", f"{_uid()}"] if _uid() else []
    proc = subprocess.run(["docker", "run", "--rm", *user, "-v", f"{work}:/work", image, "bash", "/work/run.sh"],  # noqa: S603, S607
                          capture_output=True, check=False, timeout=600)  # fmt: skip
    traces = sorted((work / "trace").glob("*.txt"))
    failed = [n for n, st in enumerate(exp["steps"]) if st["kind"] == "check" and _COMPILES.search(st["command"])
              and (work / f"step{n:03d}.rc").is_file()
              and (work / f"step{n:03d}.rc").read_text().strip() not in ("0", "")]  # fmt: skip
    status = "skipped" if proc.returncode == 77 else "ran" if traces else "compile failed" if failed else "no run"
    events = [e for t in traces for e in read_trace(t.read_bytes(), enc)]
    programs = {}
    for pid, src in _case_programs(work / "case").items():
        text = src.read_bytes().decode(enc, "replace")
        inv = inventory(src, work / "case", text=text, label=str(src.relative_to(work / "case")))
        got = hits(inv, events, LineMap(text), None)
        programs[pid] = summary(inv, got)
    return {"case": exp.get("case") or case.name, "suite": exp.get("suite"), "status": status,
            "skipped": status == "skipped", "runs": len(traces), "programs": programs if traces else {}}  # fmt: skip


def _uid() -> Optional[str]:
    import os

    return f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else None


def autotest_md(results: list[dict[str, Any]]) -> str:
    lines = ["# COBOL coverage of an Autotest suite's own tests (#4023)", "",
             ("Each case run under GnuCOBOL with `-ftraceall` (tests/tools/cobol_coverage.py autotest): per program, "
             "the paragraphs and branch outcomes the case's own runs execute."), "",
             "| case | program | runs | paragraphs | branches | HANDLE labels |", "|---|---|---|---|---|---|"]  # fmt: skip
    by = Counter(r["status"] for r in results)
    lines[4:4] = [f"Cases: {len(results)} -- " + ", ".join(f"{by[k]} {k}" for k in STATUSES if by[k]) + ". A case "
                  "that is skipped (exit 77), does not compile under GnuCOBOL (a dialect feature it lacks) or never "
                  "runs a program (a compile-only test) has no coverage to report.", ""]  # fmt: skip
    tot: Counter[str] = Counter()
    for r in results:
        if r["status"] != "ran":
            continue
        for pid, s in r["programs"].items():
            p, b, h = s["paragraphs"], s["branches"], s["handler_labels"]
            unread = f" (+{len(p['unread'])} unread)" if p.get("unread") else ""
            lines.append(f"| `{r['case']}` | {pid} | {r['runs']} | {p['covered']}/{p['live']}{unread} | "
                         f"{b['covered']}/{b['total']} | {h['covered']}/{h['total']} |")  # fmt: skip
            tot.update({"pc": p["covered"], "pl": p["live"], "bc": b["covered"], "bt": b["total"]})
    lines += [f"| **all** | | | **{tot['pc']}/{tot['pl']}** | **{tot['bc']}/{tot['bt']}** | |", ""]
    unread = [(r["case"], pid, s["paragraphs"]["unread"]) for r in results for pid, s in r["programs"].items()
              if s["paragraphs"].get("unread")]  # fmt: skip
    if unread:
        lines += ["## Units the engine does not read", "",
                  ("A run entered these, but the engine's unit reader (cobol_graveyard_finder) does not see them as "
                  "paragraphs or sections, so they are missing from the counts above -- an engine defect, not a gap "
                  "in the tests."), ""]  # fmt: skip
        lines += [f"- `{c}` {pid}: {', '.join(f'`{n}`' for n in names)}" for c, pid, names in unread] + [""]
    for r in results:
        for pid, s in r["programs"].items():
            gaps = gaps_md(s)
            if gaps and not r["skipped"]:
                lines += [f"## `{r['case']}` {pid}", "", *gaps, ""]
    return "\n".join(lines) + "\n"


# ---- CLI -------------------------------------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="one program's coverage over kept traces")
    m.add_argument("--source", type=Path, required=True, help="the original program")
    m.add_argument("--compiled", type=Path, help="the text that was compiled, when the harness rewrote it")
    m.add_argument("--trace", type=Path, nargs="+", required=True)
    m.add_argument("--copybooks", type=Path, help="where COPY members are (default: the source's directory)")
    m.add_argument("--encoding", help="the sources' and traces' code page (default: the engine's ladder / utf-8)")
    m.add_argument("--json", type=Path, help="write the summary here")
    a = sub.add_parser("autotest", help="run at_extract cases under GnuCOBOL, traced")
    a.add_argument("cases", type=Path, nargs="+", help="case directories (with expected.json), or suite directories")
    a.add_argument("--out", type=Path, required=True, help="work tree, coverage.json and coverage.md")
    a.add_argument("--image", default=IMAGE)
    args = ap.parse_args(argv)
    if args.cmd == "measure":
        s = measure_files(args.source, args.trace, args.compiled, args.copybooks, args.encoding)
        if args.json:
            args.json.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
        print("\n".join(summary_md(s, len(args.trace))))
        return 0
    dirs = []
    for d in args.cases:
        dirs += [d] if (d / "expected.json").is_file() else sorted(p.parent for p in d.glob("*/expected.json"))
    results = []
    for d in dirs:
        r = run_autotest_case(d.resolve(), (args.out / "work" / d.name).resolve(), args.image)
        results.append(r)
        n = sum(s["paragraphs"]["covered"] for s in r["programs"].values())
        t = sum(s["paragraphs"]["live"] for s in r["programs"].values())
        print(f"{r['case']}: " + (r["status"] if r["status"] != "ran" else f"{r['runs']} run(s), {n}/{t} paragraphs"))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "coverage.json").write_text(json.dumps({"format": FORMAT, "cases": results}, indent=1) + "\n",
                                            encoding="utf-8")  # fmt: skip
    (args.out / "coverage.md").write_text(autotest_md(results), encoding="utf-8")
    print(f"coverage: {args.out / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
