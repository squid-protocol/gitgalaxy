#!/usr/bin/env python3
"""#4175: a branch solver over the det translator's reading of a COBOL program.

    python tests/tools/branch_solver.py check [CASE ...] [--json] [--timeout S]   # the stated infeasible outcomes
    python tests/tools/branch_solver.py reach CASE LINE:OUTCOME [...] [--inputs]   # an input that takes an outcome
    python tests/tools/branch_solver.py paragraphs CASE                            # which paragraphs any input enters
    python tests/tools/branch_solver.py backend CASE PROMPT_FILE   # strengthen.py --backend-command: inputs, no model

It reads the program through the det translator's own parser (det/stmt.py, det/expr.py, det/layout.py) and executes
it symbolically with z3: every IF and EVALUATE outcome gets the condition under which the program reaches it and takes
it. Three answers, never more:

  confirmed     no input of the program reaches the outcome (the condition is unsatisfiable) and the walk was complete
  witness       an input that reaches it, with the values the solver chose (an inconsistency with a stated
                infeasible claim, or the start of a scenario: reaching is not yet killing)
  inconclusive  the solver timed out, or the program uses a construct the walk does not follow (named in `why`)

Soundness is the design rule: whatever the walk does not model it over-approximates, so `confirmed` can be trusted
as far as the model goes, and imprecision only ever turns a `confirmed` into a `witness` or `inconclusive`:

* An item the walk cannot follow (under OCCURS or REDEFINES, a FILE SECTION record, an ambiguous name, a
  subscript or reference modification) reads as a fresh value on every read and is never assigned.
* A statement whose effect the walk does not model (CALL, EXEC, STRING, READ, ...) sets every item it names to a
  fresh value (`targets`), and runs every phrase it has (AT END and NOT AT END both).
* A loop (PERFORM UNTIL / VARYING / TIMES) is summarised: every item its body can write, through the paragraphs it
  PERFORMs or GOes TO, is set fresh at the loop head; the exit takes the UNTIL condition, one iteration its negation.
  A paragraph reached again by GO TO is walked once more from a state where every item is fresh.
* A fresh value is constrained only by its PICTURE and by the item's value set: the values the program ever stores
  in it (VALUE, MOVE / SET / INITIALIZE of constants, copies of items with a value set), flow-insensitive, and none
  (any value) when anything else writes it or it has no VALUE. That is what keeps a loop flag 'N' or 'Y'.
* A CICS command without RESP may branch to any HANDLE CONDITION / AID label, and any CICS command to a HANDLE ABEND
  label; an EXEC SQL to any WHENEVER label. ALTER, NEXT SENTENCE, EXIT PARAGRAPH / PERFORM / SECTION and ENTRY make
  the walk incomplete: `confirmed` is then reported as `inconclusive`.

What the model assumes (stated in every report): numeric DISPLAY items hold valid numbers (non-digit data is the
'undefined by IBM' class, family U, never checked here); the program is entered at its first statement; a callee
(CALL / LINK) changes only what it is passed. Caller context is not an input: a claim that rests on what every caller
passes (family G) shows up as `witness`, which says the program alone does not settle it.

Nothing is committed from here. z3 is the `solver` extra (`pip install -e .[solver]`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))
from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import layout as L  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402

FORMAT = "gitgalaxy-branch-solver/1"
MAX_VALUES = 64  # a value set larger than this is "any value"
TIMEOUT_MS = 20000
PHRASE_PAIRS = (("at_end", "not_at_end"), ("invalid_key", "not_invalid_key"), ("on_size_error", "not_on_size_error"),
                ("on_overflow", "not_on_overflow"), ("on_exception", "not_on_exception"), ("at_eop", "not_at_eop"))  # fmt: skip
READ_ONLY = {"IF", "EVALUATE", "DISPLAY", "CONTINUE", "EXIT", "GOTO", "GOBACK", "STOP", "NEXT-SENTENCE", "OPEN",
             "CLOSE", "WRITE"}  # fmt: skip
INCOMPLETE = {"ALTER": "ALTER changes a GO TO", "NEXT-SENTENCE": "NEXT SENTENCE", "ENTRY": "a second ENTRY point"}
FIG_CHAR = {"SPACES": " ", "ZEROS": "0", "LOW": "\x00", "HIGH": "\xff", "QUOTES": '"'}
# CICS options whose argument the command only reads (never writes); RESP / RESP2 / INTO / SET / ... are written
CICS_INPUT = {"FROM", "FILE", "DATASET", "QUEUE", "QNAME", "PROGRAM", "TRANSID", "MAPSET", "MAP", "ABCODE", "KEYLENGTH",
              "FROMLENGTH", "TERMID", "SYSID", "INTERVAL", "TIME", "CHANNEL", "CONTAINER", "CURSOR", "LABEL", "SECONDS",
              "MINUTES", "HOURS", "REQID", "MAXLENGTH", "TOKEN", "DATASTR", "TEXT"}  # fmt: skip
# commands that send or end: their LENGTH / RIDFLD are inputs too
CICS_QUIET = {"SEND", "WRITE", "REWRITE", "DELETE", "XCTL", "RETURN", "START", "ABEND", "HANDLE", "DELAY", "ENDBR",
              "UNLOCK", "SYNCPOINT", "PUSH", "POP", "IGNORE", "FREEMAIN", "CANCEL"}  # fmt: skip
# the EIB fields a command leaves as they were at task start
EIB_STABLE = {"EIBCALEN", "EIBTRNID", "EIBTASKN", "EIBTRMID"}
INIT_OPTIONS = re.compile(r"\b(REPLACING|VALUE|FILLER|DEFAULT|ALL)\b", re.I)  # an INITIALIZE the walk does not model
# a CICS command as a scenario's fault plan names it (tests/tools/equivalence_cics_faults.py): two-word commands, and the
# option whose argument is the resource (`file`, `program`, ...) the plan names
# SQLCODEs a scenario's sql_faults commonly plans (#4173): reach prefers these, then any value
SQLCODES = (100, -803, -811, -911, -913, -501, -530, -305, 923)
FAULT_TWO_WORDS = {"SEND-MAP", "SEND-TEXT", "RECEIVE-MAP", "WRITEQ-TS", "WRITEQ-TD", "READQ-TD", "READQ-TS"}
FAULT_RESOURCE = {"FILE": "file", "DATASET": "file", "PROGRAM": "program", "QUEUE": "queue", "TRANSID": "transid",
                  "REQID": "reqid", "MAP": "map", "RESOURCE": "resource"}  # fmt: skip
_OPTION = re.compile(r"([A-Z][A-Z0-9-]*)\s*\(((?:[^()]|\([^()]*\))*)\)")
SKIP_WORDS = {"OF", "IN", "TO", "FROM", "BY", "INTO", "GIVING", "USING", "AND", "OR", "NOT", "IS", "THAN", "ALL"}


def _z3() -> Any:
    import z3  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: PLC0415 -- the `solver` extra

    return z3


# ---- the program --------------------------------------------------------------------------------------------------
@dataclass
class Program:
    name: str
    proc: S.Procedure
    records: list[L.Item]
    source: Path
    file_status: list[str] = field(default_factory=list)


def load_program(source: Path, copy_dirs: list[Path], bms: Path | None = None) -> Program:
    """The det translator's reading of one program: its PROCEDURE DIVISION and its data items."""
    from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: PLC0415
    from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: PLC0415
    from gitgalaxy.tools.cobol_to_java.det.source import (  # noqa: PLC0415
        CopyAmbiguous,
        CopyNotFound,
        program_lines,
        program_unit,
    )

    dirs = [*copy_dirs, C.COPY]
    try:
        lines = program_unit(program_lines(source, dirs), None)
    except CopyAmbiguous:
        raise
    except CopyNotFound:
        if bms is None:
            raise
        lines = program_unit(program_lines(source, [*dirs, bms]), None)
    proc = S.parse(lines)
    records = L.parse(lines)
    if any(x.kind == "EXEC" and re.match(r"\s*EXEC\s+CICS\b", x.text, re.I)
           for q in proc.paragraphs for x in S.walk(q.body)):  # fmt: skip
        eib = P.eib_records()  # the EXEC interface block: set by CICS, an input like LINKAGE
        for r in eib:
            for it in r.walk():
                it.section = "LINKAGE"
        records += eib
    status = [n for fc in P.file_control(lines) for n in (fc.get("status") or [])]
    return Program(source.stem.upper(), proc, records, source, status)


# ---- data items ---------------------------------------------------------------------------------------------------
class Items:
    """Name resolution and the tracked / untracked split (see the module docstring)."""

    def __init__(self, records: list[L.Item]):
        self.by_name: dict[str, list[L.Item]] = {}
        self.all: list[L.Item] = []
        for r in records:
            for it in r.walk():
                self.all.append(it)
                self.by_name.setdefault(it.name.upper(), []).append(it)
                for c in it.conditions:
                    c.parent = it
                    self.by_name.setdefault(c.name.upper(), []).append(c)
        overlapped: set[int] = set()
        for r in records:
            if r.level == 1 and (r.redefines or (r.record is not None and r.record is not r)):
                overlapped |= {id(x) for x in r.walk()}
                tgt = next((o for o in records if o.level == 1 and o.name == r.redefines), None)
                if tgt is not None:
                    overlapped |= {id(x) for x in tgt.walk()}
            for it in r.walk():
                if it.redefines and it.parent is not None:
                    overlapped |= {id(x) for x in it.walk()}
                    for sib in it.parent.children:
                        if sib.name == it.redefines:
                            overlapped |= {id(x) for x in sib.walk()}
        self.overlapped = overlapped
        self.aliased: set[int] = set()  # records whose ADDRESS the program takes (never constant)

    def tracked(self, it: L.Item) -> bool:
        if it.level in (66, 88) or it.section == "FILE" or id(it) in self.overlapped or it.children:
            return False
        p: L.Item | None = it
        while p is not None:
            if p.occurs != 1 or p.depending:
                return False
            p = p.parent
        if it.category in ("ALPHANUMERIC", "ALPHABETIC"):
            return not it.justified
        return it.category == "NUMERIC" and it.usage in ("DISPLAY", "PACKED", "BINARY", "COMP-5")

    def resolve(self, ref: Any) -> list[L.Item]:
        if not isinstance(ref, E.Ref):
            return []
        cands = self.by_name.get(ref.name.upper(), [])
        for q in ref.qualifiers:
            cands = [c for c in cands if _has_ancestor(c, str(q).upper())]
        return cands

    def mentioned(self, text: str) -> list[L.Item]:
        """Every item a statement's text names (its words that are data names), with their descendants."""
        out: dict[int, L.Item] = {}
        for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", text):
            up = tok.upper()
            if up in SKIP_WORDS:
                continue
            for it in self.by_name.get(up, []):
                base = it.parent if it.level == 88 and it.parent is not None else it
                for x in base.walk():
                    out[id(x)] = x
        return list(out.values())


def _root(it: L.Item) -> L.Item:
    """The 01 whose storage an item is in (an 01 REDEFINES shares the storage of the record it redefines)."""
    r = it
    while r.parent is not None:
        r = r.parent
    return r.record if r.record is not None else r


def _under_redefines(it: L.Item, top: L.Item) -> bool:
    p: L.Item | None = it
    while p is not None and p is not top:
        if p.redefines:
            return True
        p = p.parent
    return False


def _filler(it: L.Item) -> bool:
    """An item INITIALIZE leaves alone: a FILLER, or one under a FILLER group."""
    p: L.Item | None = it
    while p is not None:
        if p.name.upper() == "FILLER":
            return True
        p = p.parent
    return False


def _has_ancestor(it: L.Item, name: str) -> bool:
    p = it.parent
    while p is not None:
        if p.name.upper() == name:
            return True
        p = p.parent
    return False


def _kind(it: L.Item) -> str:
    return "num" if it.category == "NUMERIC" else "str"


def norm_value(v: Any, it: L.Item) -> str | int | None:
    """A VALUE / literal / figurative as this item stores it (a padded string, or the number times 10**scale)."""
    if isinstance(v, tuple):
        kind = v[0]
        if kind == "fig":
            v = E.Fig(v[1])
        elif kind == "lit":
            v = E.Lit(v[1])
        elif kind == "num":
            v = E.Lit(v[1])
        elif kind == "all":
            v = E.Fig("ALL", all_literal=str(v[1][1]) if isinstance(v[1], tuple) else str(v[1]))
        elif kind == "hex":
            v = E.Lit(v[1].decode("latin-1"))
        else:
            return None
    if _kind(it) == "str":
        n = it.size
        if isinstance(v, E.Fig):
            if v.kind == "ALL" and v.all_literal:
                return (v.all_literal * (n // max(len(v.all_literal), 1) + 1))[:n]
            ch = FIG_CHAR.get(v.kind)
            return ch * n if ch else None
        if isinstance(v, E.Lit):
            if isinstance(v.value, bytes):
                text = v.value.decode("latin-1")
            elif isinstance(v.value, Decimal):
                if v.text is None or not re.fullmatch(r"\d+", v.text):
                    return None
                text = v.text
            else:
                text = v.value
            return text[:n].ljust(n)
        return None
    if isinstance(v, E.Fig):
        return 0 if v.kind == "ZEROS" else None
    if isinstance(v, E.Lit) and isinstance(v.value, Decimal):
        scaled = v.value * (Decimal(10) ** it.scale)
        if scaled != scaled.to_integral_value():
            return None
        n = int(scaled)
        if abs(n) >= 10**it.digits or (n < 0 and not it.signed):
            return None
        return n
    return None


# ---- what a statement may write ------------------------------------------------------------------------------------
class Writes:
    """`targets(stmt)`: every item a statement may change (a superset of what the walk assigns), and the
    flow-insensitive value set of each tracked item."""

    def __init__(self, prog: Program, items: Items):
        self.prog, self.items = prog, items
        self.status = [x for n in prog.file_status for it in items.by_name.get(n.upper(), []) for x in it.walk()]
        self.sqlca = [x for r in prog.records if r.name.upper() == "SQLCA" for x in r.walk()]
        self.eib = [x for r in prog.records if r.name.upper() == "DFHEIBLK" for x in r.walk()
                    if x.name.upper() not in EIB_STABLE]  # fmt: skip

    def targets(self, s: S.Stmt) -> list[L.Item]:
        k = s.kind
        d = s.data
        if k == "MOVE":
            return [x for r in d.get("to") or [] for it in self.items.resolve(r) for x in it.walk()]
        if k == "SET-TRUE":
            out = []
            for r in d.get("conds") or []:
                for c in self.items.resolve(r):
                    out += list(c.parent.walk()) if c.level == 88 and c.parent is not None else list(c.walk())
            return out
        if k == "INITIALIZE":
            return [x for r in d.get("refs") or [] for it in self.items.resolve(r) for x in it.walk()]
        if k == "PERFORM":
            v = d.get("varying")
            if not v:
                return []
            return self.items.mentioned(s.text) if re.search(r"\bAFTER\b", s.text, re.I) else self.refs([v[0]])
        precise = self.precise_targets(s)
        if precise is not None:
            return precise + list(self.status)
        if k in ("OPEN", "CLOSE", "WRITE"):
            return list(self.status)
        if k in READ_ONLY:
            return []
        if k == "EXEC":
            return self.exec_targets(s.text)
        return self.items.mentioned(s.text) + list(self.status)

    def refs(self, refs: list) -> list[L.Item]:
        """Every item (and its descendants) these references can name."""
        return [x for r in refs if isinstance(r, E.Ref) for it in self.items.resolve(r) for x in it.walk()]

    def precise_targets(self, s: S.Stmt) -> list[L.Item] | None:
        """The receiving items of a statement whose parsed form names them; None to fall back on every name."""
        k, d = s.kind, s.data
        if k == "STRING" and "into" in d:
            return self.refs([d.get("into"), d.get("pointer")])
        if k == "UNSTRING" and "intos" in d:
            outs = [r for t in d.get("intos") or [] for r in (t if isinstance(t, tuple) else (t,))]
            return self.refs([*outs, d.get("pointer"), d.get("tallying")])
        if k == "INSPECT" and "target" in d:
            inner = [x for c in d.get("clauses") or [] for x in (c if isinstance(c, (tuple, list)) else (c,))]
            return self.refs([d.get("target"), *inner])
        if k == "ARITH" and ("targets" in d or "giving" in d):
            outs = [t[0] for key in ("targets", "giving") for t in d.get(key) or []]
            return self.refs([*outs, d.get("remainder")])
        if k == "CALL" and "args" in d:
            return self.refs([r for mode, r in d.get("args") or [] if mode == "REFERENCE"] + [d.get("returning")])
        if k == "READ" and "file" in d:
            return self.refs([d.get("into")])
        if k in ("SET-TO", "SET-BY") and "targets" in d:
            return self.refs(list(d.get("targets") or []))
        return None

    def exec_targets(self, text: str) -> list[L.Item]:
        """What an EXEC may write: a CICS command's output options (every option but the read-only ones) and the
        EIB; an SQL statement's INTO host variables (all of a FETCH / CALL / SET) and the SQLCA; anything else, every
        item it names."""
        t = re.sub(r"\s+", " ", text.upper())
        m = re.match(r"\s*EXEC CICS (\w+)", t)
        if m:
            verb = m.group(1)
            out: list[L.Item] = list(self.eib)
            for opt, arg in _OPTION.findall(t[m.end() :]):
                if opt in CICS_INPUT or (verb in CICS_QUIET and opt in ("LENGTH", "RIDFLD", "FLENGTH")):
                    continue
                if verb == "FORMATTIME" and opt == "ABSTIME":
                    continue
                out += self.items.mentioned(arg)
            return out
        m = re.match(r"\s*EXEC SQL (\w+)", t)
        if m:
            verb = m.group(1)
            hosts = re.findall(r":\s*([A-Z0-9][A-Z0-9-]*)", t)
            if verb in ("FETCH", "CALL", "SET"):
                written = hosts
            else:
                into = re.search(r"\bINTO\b(.*?)(\bFROM\b|\bWHERE\b|\bVALUES\b|END-EXEC|$)", t)
                written = re.findall(r":\s*([A-Z0-9][A-Z0-9-]*)", into.group(1)) if into and verb != "INSERT" else []
            return [x for h in written for x in self.items.mentioned(h)] + list(self.sqlca)
        return self.items.mentioned(text) + list(self.status)

    def value_sets(self) -> dict[int, set[Any] | None]:
        """id(item) -> its value set, None for any value."""
        vs: dict[int, set[Any] | None] = {}
        tracked = [it for it in self.items.all if self.items.tracked(it)]
        for it in tracked:
            if it.section != "WORKING-STORAGE" and it.section != "LOCAL-STORAGE":
                vs[id(it)] = None
                continue
            if not it.values:
                vs[id(it)] = None
                continue
            v = norm_value(it.values[0], it)
            vs[id(it)] = None if v is None else {v}
        copies: list[tuple[L.Item, L.Item]] = []

        def put(it: L.Item, v: Any) -> None:
            cur = vs.get(id(it), None)
            if id(it) not in vs or cur is None:
                return
            if v is None:
                vs[id(it)] = None
            else:
                cur.add(v)

        stmts = [x for p in self.prog.proc.paragraphs for x in S.walk(p.body)]
        for s in stmts:
            precise: set[int] = set()
            if s.kind == "MOVE":
                src = s.data.get("from")
                for r in s.data.get("to") or []:
                    hit = self.items.resolve(r)
                    if len(hit) == 1 and not r.subscripts and not r.refmod and self.items.tracked(hit[0]):
                        it = hit[0]
                        precise.add(id(it))
                        s_items = self.items.resolve(src) if isinstance(src, E.Ref) else []
                        if (len(s_items) == 1 and self.items.tracked(s_items[0]) and not src.subscripts
                                and not src.refmod and _kind(s_items[0]) == _kind(it)
                                and (_kind(it) == "str" or s_items[0].scale == it.scale)):  # fmt: skip
                            copies.append((s_items[0], it))
                        else:
                            put(it, norm_value(src, it) if not isinstance(src, E.Ref) else None)
            elif s.kind == "SET-TRUE":
                for r in s.data.get("conds") or []:
                    for c in self.items.resolve(r):
                        if c.level == 88 and c.parent is not None and self.items.tracked(c.parent):
                            precise.add(id(c.parent))
                            put(c.parent, norm_value(c.values[0], c.parent) if c.values else None)
            elif s.kind == "INITIALIZE" and not INIT_OPTIONS.search(s.text):
                for x in self.targets(s):
                    if _filler(x):
                        precise.add(id(x))  # left as it is
                    elif self.items.tracked(x):
                        precise.add(id(x))
                        put(x, " " * x.size if _kind(x) == "str" else 0)
            for x in self.targets(s):
                if id(x) not in precise:
                    put(x, None)
        changed = True
        while changed:
            changed = False
            for src, dst in copies:
                a, b = vs.get(id(src)), vs.get(id(dst))
                if b is None or id(dst) not in vs:
                    continue
                if a is None:
                    vs[id(dst)] = None
                    changed = True
                    continue
                conv = {_convert_const(v, src, dst) for v in a}
                if None in conv:
                    vs[id(dst)] = None
                    changed = True
                elif not conv <= b:
                    b |= conv
                    changed = True
        return {k: (None if v is not None and len(v) > MAX_VALUES else v) for k, v in vs.items()}


def _convert_const(v: Any, src: L.Item, dst: L.Item) -> Any:
    if _kind(dst) == "str":
        return str(v)[: dst.size].ljust(dst.size)
    if abs(v) >= 10**dst.digits or (v < 0 and not dst.signed):
        return None
    return v


# ---- the symbolic walk ---------------------------------------------------------------------------------------------
@dataclass
class State:
    pc: Any
    env: dict[Any, Any]  # id(item) -> value; "flag:NAME" -> a walked Boolean (Walk flags)


class Walk:
    def __init__(self, prog: Program, evaluate_arms: dict[int, list[str]] | None = None,
                 flags: dict[str, tuple[Any, Any, Any]] | None = None):  # fmt: skip
        """`flags`: name -> (sets(stmt), clears(stmt), watched(stmt)): a Boolean the walk carries along every path,
        True after a statement that sets it, False after one that clears it, fresh at a loop head; `flag_at[name]`
        holds the condition that it is True when a watched statement runs (field_observability.py)."""
        self.flags = flags or {}
        self.flag_at: dict[str, list[Any]] = {n: [] for n in self.flags}
        self.z = _z3()
        self.prog = prog
        self.items = Items(prog.records)
        # an item whose ADDRESS is taken can be written through a pointer: none of its record is followed
        for p in prog.proc.paragraphs:
            for s in S.walk(p.body):
                for name in re.findall(r"ADDRESS\s+OF\s+([A-Z0-9][A-Z0-9-]*)", s.text, re.I):
                    for it in self.items.by_name.get(name.upper(), []):
                        if it.section in ("WORKING-STORAGE", "LOCAL-STORAGE"):
                            self.items.overlapped |= {id(x) for x in _root(it).walk()}
                            self.items.aliased.add(id(_root(it)))
        self.writes = Writes(prog, self.items)
        self.vs = self.writes.value_sets()
        self.tracked = [it for it in self.items.all if self.items.tracked(it)]
        self.axioms: dict[str, list[Any]] = {}  # symbol name -> the constraints on that symbol alone
        self.hits: dict[tuple[int, str], list[Any]] = {}
        self.entered: dict[str, list[Any]] = {}
        self.why: list[str] = []  # what makes the walk incomplete
        self.unmatched: set[int] = set()  # EVALUATE lines whose arms could not be named
        self.arms = evaluate_arms or {}
        self.symbols: dict[str, tuple[str, L.Item, int]] = {}  # z3 name -> (origin, item, line)
        self.exec_text: dict[int, str] = {}  # line -> EXEC text (where an exec: value came from)
        self.at: dict[int, list[Any]] = {}  # id(statement) -> the path conditions it runs under
        # resp symbol -> (line, command, resource key, resource name): a CICS command's response, for a fault plan
        self.resp_meta: dict[str, tuple[int, str, str | None, str | None]] = {}
        self.known_values: dict[str, set[str]] = {}
        self.sql_meta: dict[str, int] = {}  # sqlcode symbol -> the EXEC SQL's line
        self.known_sqlcodes: set[int] = set(SQLCODES)  # reach prefers these (the case's own planned codes added)
        self.received_maps = {m.upper() for p in prog.proc.paragraphs for x in S.walk(p.body) if x.kind == "EXEC"
                               for m in re.findall(r"RECEIVE\s+MAP\s*\(\s*'([^']+)'", x.text, re.I)}  # fmt: skip  # field -> text values the case's scenarios use (reach prefers them)
        self._n = 0
        paras = prog.proc.paragraphs
        self.index = {p.name.upper(): i for i, p in enumerate(paras)}
        self.sections: dict[str, list[int]] = {}
        for i, p in enumerate(paras):
            if p.section:
                self.sections.setdefault(p.section.upper(), []).append(i)
        self.handlers = self._handler_labels()
        self.para_writes = [self._block_writes(p.body) for p in paras]
        self.const_roots = self._constant_records()
        self.succ = [self._successors(i) for i in range(len(paras))]
        self.depth = 0
        self.active: list[tuple[int, int | None]] = []  # the PERFORM ranges running now, outermost first
        self.reentered: set[tuple[int, int | None]] = set()  # ranges already walked once from the all-fresh state

    # -- constant tables --
    def _constant_records(self) -> set[int]:
        """The WORKING-STORAGE records no statement writes and every elementary item of which has a VALUE: their
        bytes are the record's image for the whole run (a table of constants read by subscript)."""
        written = {id(_root(x)) for p in self.prog.proc.paragraphs for s in S.walk(p.body)
                   for x in self.writes.targets(s)}  # fmt: skip
        out = set()
        for r in self.prog.records:
            root = _root(r)
            if r.level != 1 or r.section != "WORKING-STORAGE" or id(root) in written or id(root) in self.items.aliased:
                continue
            leaves = [x for x in r.walk() if not x.children and x.level not in (66, 88) and not _under_redefines(x, r)]
            if leaves and all(x.values for x in leaves):
                out.add(id(r))
        # an 01 REDEFINES has no VALUEs of its own: its bytes are the record it redefines, constant when that one is
        for r in self.prog.records:
            if r.level == 1 and _root(r) is not r:
                if id(_root(r)) in out and id(_root(r)) not in written:
                    out.add(id(r))
                else:
                    out.discard(id(r))
        return out

    def table_values(self, it: L.Item, subs: list) -> list[Any] | None:
        """The values an item of a constant record can hold (each occurrence, or the one literal subscripts
        name), as this item stores them; None when the record is not constant or a value does not decode."""
        rec = it
        while rec.parent is not None:
            rec = rec.parent
        if id(rec) not in self.const_roots or it.level in (66, 88):
            return None
        chain = [a for a in [*reversed(_ancestors(it)), it] if a.occurs != 1]
        if any(a.depending for a in chain):
            return None
        picks: list[list[int]] = []
        lits = [int(x.value) for x in subs if isinstance(x, E.Lit) and isinstance(x.value, Decimal)]
        exact = len(lits) == len(subs) == len(chain)
        for i, a in enumerate(chain):
            picks.append([lits[i] - 1] if exact else list(range(a.occurs)))
        combos: list[int] = [0]
        for a, pick in zip(chain, picks):
            combos = [c + k * a.size for c in combos for k in pick]
            if len(combos) > 512:
                return None
        img = L.image(rec)
        out: set[Any] = set()
        for c in combos:
            data = img[it.offset + c : it.offset + c + it.size]
            if len(data) != it.size:
                return None
            if it.children or _kind(it) == "str":
                out.add(data.decode("latin-1"))
                continue
            if it.usage not in ("DISPLAY", "PACKED"):
                return None
            v = L.decode_number(it, data)
            if v is None:
                return None
            out.add(int(v * (Decimal(10) ** it.scale)))
        return sorted(out, key=str)

    # -- values --
    def fresh(self, it: L.Item, origin: str, line: int, constrained: bool = True) -> Any:
        z = self.z
        self._n += 1
        name = f"{origin}:{it.name}@{line}#{self._n}"
        ax = self.axioms.setdefault(name, [])
        if _kind(it) == "str":
            v = z.BitVec(name, 8 * it.size)  # a fixed-length text: one byte per position
        else:
            v = z.Int(name)
            bound = 10**it.digits
            ax.append(z.And(v > -bound, v < bound) if it.signed else z.And(v >= 0, v < bound))
        if constrained and self.items.tracked(it):
            vals = self.vs.get(id(it))
            if vals is not None:
                ax.append(z.Or([v == self.const(x, it) for x in vals]) if vals else z.BoolVal(False))
        self.symbols[name] = (origin, it, line)
        return v

    def const(self, v: Any, it: L.Item) -> Any:
        return self.sval(v) if _kind(it) == "str" else self.z.IntVal(v)

    # -- fixed-length text as bit-vectors (byte i is bits 8*(n-i)-1 .. 8*(n-i-1)) --
    def sval(self, text: str) -> Any:
        # one byte per character: a character past latin-1 (none in COBOL source) stands as '?' (#3813: nothing lossy)
        data = (
            bytes(ord(c) if ord(c) < 256 else 0x3F for c in text) or b" "
        )  # (no zero-length item: an empty text is one space)
        chunks = [data[i : i + 64] for i in range(0, len(data), 64)]  # (a huge int would pass Python's digit limit)
        return self.cat([self.z.BitVecVal(int.from_bytes(c, "big"), 8 * len(c)) for c in chunks])

    def sub(self, t: Any, off: int, ln: int) -> Any:
        n = t.size() // 8
        return self.z.Extract(8 * (n - off) - 1, 8 * (n - off - ln), t)

    def cat(self, parts: list[Any]) -> Any:
        return parts[0] if len(parts) == 1 else self.z.Concat(*parts)

    def initial(self) -> State:
        env: dict[Any, Any] = {}
        for it in self.tracked:
            v = (
                norm_value(it.values[0], it)
                if it.values and it.section in ("WORKING-STORAGE", "LOCAL-STORAGE")
                else None
            )
            env[id(it)] = self.const(v, it) if v is not None else self.fresh(it, "in", it.line)
        for n in self.flags:
            env[f"flag:{n}"] = self.z.BoolVal(False)
        return State(self.z.BoolVal(True), env)

    def top(self) -> State:
        env = {id(it): self.fresh(it, "loop", 0) for it in self.tracked}
        return State(self.z.BoolVal(True), {**env, **self.fresh_flags()})

    def fresh_flags(self) -> dict[Any, Any]:
        out = {}
        for n in self.flags:
            self._n += 1
            out[f"flag:{n}"] = self.z.Bool(f"flag:{n}#{self._n}")
        return out

    def havoc(self, st: State, items: list[L.Item], line: int, origin: str = "set") -> State:
        env = dict(st.env)
        for it in items:
            if id(it) in env:
                env[id(it)] = self.fresh(it, origin, line)
        return State(st.pc, env)

    def merge(self, states: list[State]) -> State | None:
        z = self.z
        states = [s for s in states if s is not None]
        if not states:
            return None
        if len(states) == 1:
            return states[0]
        env = {}
        for k in states[0].env:
            vals = [s.env[k] for s in states]
            if all(v.eq(vals[0]) for v in vals[1:]):
                env[k] = vals[0]
                continue
            acc = vals[-1]
            for s, v in zip(reversed(states[:-1]), reversed(vals[:-1])):
                acc = z.If(s.pc, v, acc)
            env[k] = acc
        return State(z.Or([s.pc for s in states]), env)

    def read(self, x: Any, st: State, line: int) -> tuple[str, Any, int] | None:
        """('str', term, length) | ('num', term, scale) | None: an operand as z3 sees it."""
        if isinstance(x, E.Ref):
            hit = self.items.resolve(x)
            if len(hit) != 1 or hit[0].level == 88:
                return None
            it = hit[0]
            if not x.refmod and (x.subscripts or not self.items.tracked(it)):
                vals = self.table_values(it, x.subscripts)
                if vals is not None:
                    return self._one_of(it, vals, line)
            if x.subscripts or x.refmod:
                if x.refmod and not x.subscripts and _kind(it) == "str" and self.items.tracked(it):
                    a, b = x.refmod
                    if isinstance(a, E.Lit) and isinstance(a.value, Decimal) and (
                            b is None or (isinstance(b, E.Lit) and isinstance(b.value, Decimal))):  # fmt: skip
                        start = int(a.value) - 1
                        ln = it.size - start if b is None else int(b.value)
                        if 0 <= start and ln > 0 and start + ln <= it.size:
                            return ("str", self.sub(st.env[id(it)], start, ln), ln)
                return None
            if self.items.tracked(it):
                v = st.env[id(it)]
                return ("str", v, it.size) if _kind(it) == "str" else ("num", v, it.scale)
            if it.children:
                parts = self._group_string(it, st)
                return ("str", parts, it.size) if parts is not None else None
            if it.category in ("ALPHANUMERIC", "ALPHABETIC", "NUMERIC") and it.usage in (
                    "DISPLAY", "PACKED", "BINARY", "COMP-5"):  # fmt: skip
                v = self.fresh(it, "read", line, constrained=False)
                return ("str", v, it.size) if _kind(it) == "str" else ("num", v, it.scale)
            return None
        if isinstance(x, E.Lit):
            if isinstance(x.value, Decimal):
                return ("lit-num", x, 0)
            text = x.value.decode("latin-1") if isinstance(x.value, bytes) else x.value
            return ("str", self.sval(text), len(text)) if text else None
        if isinstance(x, E.Fig):
            return ("fig", x, 0)
        if isinstance(x, (E.Bin, E.Neg)):
            a = self.arith(x, st, line)
            return ("num", a[0], a[1]) if a else None
        return None

    def _one_of(self, it: L.Item, vals: list[Any], line: int) -> tuple[str, Any, int]:
        """A fresh value that is one of `vals` (a constant table's entries)."""
        z = self.z
        self._n += 1
        name = f"table:{it.name}@{line}#{self._n}"
        if it.children or _kind(it) == "str":
            v = z.BitVec(name, 8 * it.size)
            self.axioms[name] = [z.Or([v == self.sval(t) for t in vals])]
            self.symbols[name] = ("table", it, line)
            return ("str", v, it.size)
        v = z.Int(name)
        self.axioms[name] = [z.Or([v == n for n in vals])]
        self.symbols[name] = ("table", it, line)
        return ("num", v, it.scale)

    def _group_string(self, g: L.Item, st: State) -> Any:
        parts: list[Any] = []
        pos = g.offset
        for c in g.children:
            if c.redefines:
                continue
            if c.offset != pos:
                return None
            if c.children:
                sub = self._group_string(c, st)
                if sub is None:
                    return None
                parts.append(sub)
            elif self.items.tracked(c) and _kind(c) == "str":
                parts.append(st.env[id(c)])
            else:
                return None
            pos += c.size * c.occurs
        if pos != g.offset + g.size or not parts:
            return None
        return self.cat(parts)

    def arith(self, x: Any, st: State, line: int) -> tuple[Any, int] | None:
        """(z3 Int, scale) of an arithmetic expression of + - and multiplication by a constant, else None."""
        z = self.z
        if isinstance(x, E.Lit) and isinstance(x.value, Decimal):
            exp = -x.value.as_tuple().exponent if x.value.as_tuple().exponent < 0 else 0  # type: ignore[operator]
            return z.IntVal(int(x.value * (Decimal(10) ** exp))), int(exp)
        if isinstance(x, E.Fig) and x.kind == "ZEROS":
            return z.IntVal(0), 0
        if isinstance(x, E.Ref):
            r = self.read(x, st, line)
            return (r[1], r[2]) if r and r[0] == "num" else None
        if isinstance(x, E.Neg):
            a = self.arith(x.operand, st, line)
            return (-a[0], a[1]) if a else None
        if isinstance(x, E.Bin) and x.op in "+-*":
            a, b = self.arith(x.left, st, line), self.arith(x.right, st, line)
            if a is None or b is None:
                return None
            if x.op == "*":
                if not (z.is_int_value(a[0]) or z.is_int_value(b[0])):
                    return None
                return a[0] * b[0], a[1] + b[1]
            s = max(a[1], b[1])
            la, lb = a[0] * (10 ** (s - a[1])), b[0] * (10 ** (s - b[1]))
            return (la + lb if x.op == "+" else la - lb), s
        return None

    # -- conditions --
    def compare(self, op: str, a: Any, b: Any, st: State, line: int) -> Any:
        ra, rb = self.read(a, st, line), self.read(b, st, line)
        if ra is None or rb is None:
            return None
        num = ("num", "lit-num")
        if ra[0] in num and rb[0] in num or (ra[0] in num and rb[0] == "fig" and rb[1].kind == "ZEROS") or (
                rb[0] in num and ra[0] == "fig" and ra[1].kind == "ZEROS"):  # fmt: skip
            x, y = self.arith(a, st, line), self.arith(b, st, line)
            if x is None or y is None:
                return None
            s = max(x[1], y[1])
            lx, ly = x[0] * (10 ** (s - x[1])), y[0] * (10 ** (s - y[1]))
            return {"=": lx == ly, "<>": lx != ly, ">": lx > ly, "<": lx < ly, ">=": lx >= ly, "<=": lx <= ly}.get(op)
        if op not in ("=", "<>"):
            return None
        sa, sb = self._as_string(ra), self._as_string(rb)
        if sa is None and sb is None:
            return None
        if sa is None and sb is not None:
            sa = self._fill(ra, sb[1])
        if sb is None and sa is not None:
            sb = self._fill(rb, sa[1])
        if sa is None or sb is None:
            return None
        n = max(sa[1], sb[1])
        ta, tb = self._pad(sa[0], sa[1], n), self._pad(sb[0], sb[1], n)
        return ta == tb if op == "=" else ta != tb

    def _as_string(self, r: tuple[str, Any, int]) -> tuple[Any, int] | None:
        if r[0] == "str":
            return r[1], r[2]
        if r[0] == "lit-num" and r[1].text is not None and re.fullmatch(r"\d+", r[1].text):
            return self.sval(r[1].text), len(r[1].text)
        return None

    def _fill(self, r: tuple[str, Any, int], n: int) -> tuple[Any, int] | None:
        if r[0] != "fig":
            return None
        f = r[1]
        if f.kind == "ALL" and f.all_literal:
            return self.sval((f.all_literal * (n // len(f.all_literal) + 1))[:n]), n
        ch = FIG_CHAR.get(f.kind)
        return (self.sval(ch * n), n) if ch else None

    def _pad(self, t: Any, n: int, to: int) -> Any:
        return t if n == to else self.z.Concat(t, self.sval(" " * (to - n)))

    def cond(self, c: Any, st: State, line: int) -> Any:
        z = self.z
        out = None
        if isinstance(c, E.Rel):
            out = self.compare(c.op, c.left, c.right, st, line)
        elif isinstance(c, E.Not):
            out = z.Not(self.cond(c.cond, st, line))
        elif isinstance(c, E.And):
            out = z.And(self.cond(c.left, st, line), self.cond(c.right, st, line))
        elif isinstance(c, E.Or):
            out = z.Or(self.cond(c.left, st, line), self.cond(c.right, st, line))
        elif isinstance(c, E.CondName):
            hit = self.items.resolve(c.ref)
            if len(hit) == 1 and hit[0].level == 88:
                out = self.cond_name(hit[0], st, line)
            elif c.abbrev is not None and hit and all(h.level != 88 for h in hit):
                op, subject, neg = c.abbrev
                r = self.compare(op, subject, c.ref, st, line)
                out = None if r is None else (z.Not(r) if neg else r)
        elif isinstance(c, E.ClassCond):
            r = self.read(c.operand, st, line)
            if r and r[0] == "num" and c.kind in ("POSITIVE", "NEGATIVE", "ZERO"):
                v = r[1]
                out = {"POSITIVE": v > 0, "NEGATIVE": v < 0, "ZERO": v == 0}[c.kind]
                out = z.Not(out) if c.negated else out
        if out is None:
            self._n += 1
            return z.Bool(f"cond@{line}#{self._n}")
        return out

    def cond_name(self, c88: L.Item, st: State, line: int) -> Any:
        z = self.z
        p = c88.parent
        if p is None:
            return None
        r: tuple[str, Any, int] | None = None
        if self.items.tracked(p):
            r = ("str", st.env[id(p)], p.size) if _kind(p) == "str" else ("num", st.env[id(p)], p.scale)
        elif p.children and (g := self._group_string(p, st)) is not None:
            r = ("str", g, p.size)
        if r is None:
            return None
        alts = []
        for v in c88.values:
            if isinstance(v, tuple) and v[0] == "range":
                lo, hi = norm_value(v[1], p), norm_value(v[2], p)
                if r[0] != "num" or lo is None or hi is None:
                    return None
                alts.append(z.And(r[1] >= lo, r[1] <= hi))
                continue
            if r[0] == "str" and not self.items.tracked(p):  # a group's condition: its whole string
                n = r[2]
                shape = L.Item(1, "_", "WORKING-STORAGE", pic=f"X({n})")
                shape.size = n  # (laid out by hand: norm_value pads to the size)
                text = norm_value(v, shape)
                if text is None:
                    return None
                alts.append(r[1] == self.sval(str(text)))
                continue
            k = norm_value(v, p)
            if k is None:
                return None
            alts.append(r[1] == self.const(k, p))
        return z.Or(alts) if alts else None

    # -- statements --
    def assign(self, st: State, it: L.Item, src: Any, line: int) -> None:
        """MOVE src TO one tracked elementary item (st.env changed in place)."""
        z = self.z
        r = self.read(src, st, line)
        v = None
        if _kind(it) == "str":
            if r is not None:
                s = self._as_string(r) or (self._fill(r, it.size) if r[0] == "fig" else None)
                if s is not None:
                    t, n = s
                    v = self.sub(t, 0, it.size) if n > it.size else self._pad(t, n, it.size)
        else:
            k = norm_value(src, it) if not isinstance(src, E.Ref) and not isinstance(src, (E.Bin, E.Neg)) else None
            if k is not None:
                v = z.IntVal(k)
            elif r is not None and r[0] == "num":
                v = self._fit(r[1], r[2], it, line)
        st.env[id(it)] = v if v is not None else self.fresh(it, "set", line)

    def _fit(self, v: Any, scale: int, it: L.Item, line: int, rounded: bool = False) -> Any:
        """A number of scale `scale` stored in a numeric item: exact when it fits, else any value of the item
        (ROUNDED into fewer decimals: any value too, the walk does not model the rounding)."""
        z = self.z
        if rounded and it.scale < scale:
            return self.fresh(it, "set", line)
        if it.scale > scale:
            w = v * (10 ** (it.scale - scale))
        elif it.scale < scale:
            k = 10 ** (scale - it.scale)
            w = z.If(v >= 0, v / k, -((-v) / k))
        else:
            w = v
        bound = 10**it.digits
        fits = z.And(w > -bound, w < bound) if it.signed else z.And(w >= 0, w < bound)
        return z.If(fits, w, self.fresh(it, "set", line))

    def move(self, st: State, s: S.Stmt) -> State:
        st = State(st.pc, dict(st.env))
        src = s.data.get("from")
        for r in s.data.get("to") or []:
            hit = self.items.resolve(r)
            if len(hit) != 1 or r.subscripts or r.refmod:
                st = self.havoc(st, [x for it in hit for x in it.walk()], s.line)
                continue
            it = hit[0]
            if self.items.tracked(it):
                self.assign(st, it, src, s.line)
            elif it.children:
                self._move_group(st, it, src, s.line)
        return st

    def _move_group(self, st: State, g: L.Item, src: Any, line: int) -> None:
        z = self.z
        r = self.read(src, st, line)
        whole = None
        if r is not None:
            s = self._as_string(r) or (self._fill(r, g.size) if r[0] == "fig" else None)
            if s is not None:
                t, n = s
                whole = self.sub(t, 0, g.size) if n > g.size else self._pad(t, n, g.size)
        zeros = isinstance(src, E.Fig) and src.kind == "ZEROS"
        for x in g.walk():
            if id(x) not in st.env:
                continue
            if whole is not None and _kind(x) == "str":
                st.env[id(x)] = self.sub(whole, x.offset - g.offset, x.size)
            elif zeros and _kind(x) == "num" and x.usage == "DISPLAY":
                st.env[id(x)] = z.IntVal(0)
            else:
                st.env[id(x)] = self.fresh(x, "set", line)

    def initialize(self, st: State, s: S.Stmt) -> State:
        if INIT_OPTIONS.search(s.text):
            return self.havoc(st, self.writes.targets(s), s.line)
        st = State(st.pc, dict(st.env))
        for x in self.writes.targets(s):
            if id(x) in st.env and not _filler(x):  # INITIALIZE leaves FILLER as it is
                st.env[id(x)] = self.const(" " * x.size if _kind(x) == "str" else 0, x)
        return st

    def set_true(self, st: State, s: S.Stmt) -> State:
        st = State(st.pc, dict(st.env))
        for r in s.data.get("conds") or []:
            for c in self.items.resolve(r):
                p = c.parent if c.level == 88 else None
                if p is None:
                    st = self.havoc(st, list(c.walk()), s.line)
                    continue
                k = norm_value(c.values[0], p) if c.values and not (
                        isinstance(c.values[0], tuple) and c.values[0][0] == "range") else None  # fmt: skip
                if id(p) in st.env:
                    st.env[id(p)] = self.const(k, p) if k is not None else self.fresh(p, "set", s.line)
                elif p.children:  # an 88 on a group: its items take the value's bytes; the walk sets them fresh
                    st = self.havoc(st, list(p.walk()), s.line)
        return st

    def compute(self, st: State, s: S.Stmt) -> State:
        st = State(st.pc, dict(st.env))
        val = self.arith(s.data.get("expr"), st, s.line)
        for ref, rounded in s.data.get("targets") or []:
            hit = self.items.resolve(ref)
            for it in hit:
                for x in it.walk():
                    if id(x) not in st.env:
                        continue
                    if (
                        val is not None
                        and len(hit) == 1
                        and not ref.subscripts
                        and not ref.refmod
                        and _kind(x) == "num"
                    ):
                        st.env[id(x)] = self._fit(val[0], val[1], x, s.line, bool(rounded))
                    else:
                        st.env[id(x)] = self.fresh(x, "set", s.line)
        return st

    def string(self, st: State, s: S.Stmt) -> State:
        """STRING ... INTO x (no POINTER): the literal pieces it starts with, each cut at its delimiter, are x's first
        bytes; the rest of x is any value (later pieces depend on data, and STRING leaves bytes past its end as they
        were). Anything else it names is set fresh, as an unmodelled statement's would be."""
        after = self.havoc(st, self.writes.targets(s), s.line)
        hit = self.items.resolve(s.data["into"])
        if len(hit) != 1 or not self.items.tracked(hit[0]) or _kind(hit[0]) != "str" or s.data["into"].refmod:
            return after
        it = hit[0]
        prefix = ""
        for operands, delim in s.data.get("parts") or []:
            cut = None if delim is None else (FIG_CHAR.get(delim.kind) if isinstance(delim, E.Fig) else
                                              delim.value if isinstance(delim, E.Lit) and isinstance(delim.value, str)
                                              else False)  # fmt: skip
            done = False
            for o in operands:
                if not (isinstance(o, E.Lit) and isinstance(o.value, str)) or cut is False:
                    done = True
                    break
                text = o.value if not cut else o.value.split(cut, 1)[0]
                prefix += text
                if cut and cut in o.value:
                    continue
            if done:
                break
        prefix = prefix[: it.size]
        if not prefix:
            return after
        rest = it.size - len(prefix)
        tail = [self.sub(after.env[id(it)], len(prefix), rest)] if rest > 0 else []
        after.env[id(it)] = self.cat([self.sval(prefix), *tail])
        return after

    def add_to(self, st: State, s: S.Stmt) -> State:
        """ADD a b TO x / SUBTRACT a b FROM x: exact when the sum and every target are numbers the walk follows."""
        st = State(st.pc, dict(st.env))
        total = None
        for o in s.data.get("operands") or []:
            a = self.arith(o, st, s.line)
            if a is None:
                total = None
                break
            if total is None:
                total = a
            else:
                sc = max(total[1], a[1])
                total = (total[0] * (10 ** (sc - total[1])) + a[0] * (10 ** (sc - a[1])), sc)
        for ref, rounded in s.data.get("targets") or []:
            hit = self.items.resolve(ref)
            for it in hit:
                for x in it.walk():
                    if id(x) not in st.env:
                        continue
                    exact = total is not None and len(hit) == 1 and not ref.subscripts and not ref.refmod
                    if exact and _kind(x) == "num":
                        assert total is not None
                        sc = max(total[1], x.scale)
                        cur = st.env[id(x)] * (10 ** (sc - x.scale))
                        delta = total[0] * (10 ** (sc - total[1]))
                        res = cur + delta if s.data["op"] == "+=" else cur - delta
                        st.env[id(x)] = self._fit(res, sc, x, s.line, bool(rounded))
                    else:
                        st.env[id(x)] = self.fresh(x, "set", s.line)
        return st

    # -- control --
    def _handler_labels(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {"cics": set(), "abend": set(), "sql": set()}
        for p in self.prog.proc.paragraphs:
            for s in S.walk(p.body):
                if s.kind != "EXEC":
                    continue
                t = re.sub(r"\s+", " ", s.text.upper())
                if re.match(r"EXEC CICS HANDLE ABEND", t):
                    out["abend"] |= set(re.findall(r"LABEL\s*\(\s*([A-Z0-9-]+)\s*\)", t))
                elif re.match(r"EXEC CICS HANDLE (CONDITION|AID)", t):
                    out["cics"] |= set(re.findall(r"\(\s*([A-Z0-9-]+)\s*\)", t))
                elif re.match(r"EXEC SQL WHENEVER", t):
                    out["sql"] |= set(re.findall(r"GO\s*TO\s+:?([A-Z0-9-]+)", t))
        return out

    def _range(self, target: str, thru: str | None) -> tuple[int, int] | None:
        t = target.upper()
        if t in self.sections:  # a SECTION (det keeps its header as a paragraph of the same name): all of it
            lo, hi = self.sections[t][0], self.sections[t][-1]
        elif t in self.index:
            lo = hi = self.index[t]
        else:
            return None
        if thru:
            u = thru.upper()
            if u in self.sections:
                hi = self.sections[u][-1]
            elif u in self.index:
                hi = self.index[u]
            else:
                return None
        return lo, hi

    def _jump(self, name: str) -> int | None:
        u = name.upper()
        if u in self.index:
            return self.index[u]
        if u in self.sections:
            return self.sections[u][0]
        return None

    def _block_writes(self, stmts: list) -> set[int]:
        return {id(x) for s in S.walk(stmts) for x in self.writes.targets(s)}

    def _successors(self, i: int) -> set[int]:
        out = {i + 1} if i + 1 < len(self.prog.proc.paragraphs) else set()
        for s in S.walk(self.prog.proc.paragraphs[i].body):
            out |= self._calls(s)
        for labels in self.handlers.values():
            out |= {j for lab in labels if (j := self._jump(lab)) is not None}
        return out

    def _calls(self, s: S.Stmt) -> set[int]:
        out: set[int] = set()
        if s.kind == "PERFORM" and not s.data.get("inline") and s.data.get("target"):
            rg = self._range(s.data["target"], s.data.get("thru"))
            if rg:
                out |= set(range(rg[0], rg[1] + 1))
        if s.kind == "GOTO":
            out |= {j for t in s.data.get("targets") or [] if (j := self._jump(t)) is not None}
        return out

    def loop_writes(self, start: list[int], stmts: list) -> list[L.Item]:
        ids = {id(x) for s in self.loop_stmts(start, stmts) for x in self.writes.targets(s)}
        return [it for it in self.tracked if id(it) in ids]

    def loop_stmts(self, start: list[int], stmts: list) -> list[S.Stmt]:
        """Every statement a loop body can run: its own, those of the ranges it PERFORMs (to each range's end), and
        from a GO TO or HANDLE label on, every paragraph control can fall through to."""
        paras = self.prog.proc.paragraphs
        out: list[S.Stmt] = list(S.walk(stmts))
        seen: set[tuple[int, bool]] = set()
        todo: list[tuple[int, bool]] = [(j, False) for j in start]

        def follow(body: list[S.Stmt]) -> None:
            for s in body:
                if s.kind == "PERFORM" and not s.data.get("inline") and s.data.get("target"):
                    rg = self._range(s.data["target"], s.data.get("thru"))
                    todo.extend((j, False) for j in (range(rg[0], rg[1] + 1) if rg else []))
                elif s.kind == "GOTO":
                    todo.extend((j, True) for t in s.data.get("targets") or [] if (j := self._jump(t)) is not None)
                elif s.kind in ("EXEC",) and self.handlers:
                    todo.extend((j, True) for labels in self.handlers.values() for lab in labels
                                if (j := self._jump(lab)) is not None)  # fmt: skip

        follow(out)
        while todo:
            j, free = todo.pop()
            if (j, free) in seen:
                continue
            seen.add((j, free))
            body = list(S.walk(paras[j].body))
            out += body
            follow(body)
            if free and j + 1 < len(paras):  # after a GO TO, control falls through to the next paragraph
                todo.append((j + 1, True))
        return out

    def _increment(self, it: L.Item, s: S.Stmt, op: str = "+") -> bool:
        """COMPUTE it = it + <positive literal> (or the literal first); with op "-": COMPUTE it = it - <literal>."""
        targets = [r for r, _ in s.data.get("targets") or []]
        e = s.data.get("expr")
        if len(targets) != 1 or self.items.resolve(targets[0]) != [it] or not isinstance(e, E.Bin) or e.op != op:
            return False
        if op == "-" and not (isinstance(e.left, E.Ref) and self.items.resolve(e.left) == [it]):
            return False
        sides = [e.left, e.right]
        refs = [x for x in sides if isinstance(x, E.Ref) and self.items.resolve(x) == [it] and not x.subscripts]
        lits = [x for x in sides if isinstance(x, E.Lit) and isinstance(x.value, Decimal) and x.value > 0]
        return len(refs) == 1 and len(lits) == 1

    def only_increased(self, it: L.Item, stmts: list[S.Stmt], down: bool = False) -> bool:
        """Every statement among `stmts` that may write `it` is `ADD <positive literals> TO it` / `COMPUTE it = it +
        <positive literal>` (`down`: SUBTRACT ... FROM it / COMPUTE it = it - ...): a loop over them only ever increases
        (decreases) it."""
        for s in stmts:
            if not any(x is it for x in self.writes.targets(s)):
                continue
            d = s.data
            if s.kind == "COMPUTE" and not s.phrases and self._increment(it, s, "-" if down else "+"):
                continue
            if s.kind != "ARITH" or d.get("op") != ("-=" if down else "+=") or s.phrases:
                return False
            refs = [r for r, _ in d.get("targets") or []]
            if any(self.items.resolve(r) != [it] or r.subscripts or r.refmod for r in refs):
                return False
            ops = d.get("operands") or []
            if not ops or not all(isinstance(o, E.Lit) and isinstance(o.value, Decimal) and o.value > 0 for o in ops):
                return False
        return True

    def block(self, stmts: list, st: State) -> tuple[State | None, list[tuple[int, State]]]:
        """Run a statement list: (the merged state at its normal end or None, [(paragraph index, state)] GO TOs)."""
        gotos: list[tuple[int, State]] = []
        cur: State | None = st
        for s in stmts:
            if cur is None:
                break
            self.at.setdefault(id(s), []).append(cur.pc)  # where the statement runs (fields_used)
            if self.flags:
                cur = self.step_flags(s, cur)
            cur, g = self.stmt(s, cur)
            gotos += g
        return cur, gotos

    def step_flags(self, s: S.Stmt, st: State) -> State:
        env = None
        for n, (sets, clears, watched) in self.flags.items():
            if watched(s):
                self.flag_at[n].append(self.z.And(st.pc, st.env[f"flag:{n}"]))
            if sets(s) or clears(s):
                env = env or dict(st.env)
                env[f"flag:{n}"] = self.z.BoolVal(bool(sets(s)))
        return st if env is None else State(st.pc, env)

    def _branch_to(self, labels: set[str], st: State, gotos: list[tuple[int, State]]) -> None:
        for lab in sorted(labels):
            j = self._jump(lab)
            if j is not None:
                gotos.append((j, st))

    def stmt(self, s: S.Stmt, st: State) -> tuple[State | None, list[tuple[int, State]]]:
        z = self.z
        k = s.kind
        gotos: list[tuple[int, State]] = []
        if k in INCOMPLETE:
            self.why.append(f"line {s.line}: {INCOMPLETE[k]}")
            return st, []
        if k == "IF":
            c = self.cond(s.data.get("cond"), st, s.line)
            self.hits.setdefault((s.line, "true"), []).append(z.And(st.pc, c))
            self.hits.setdefault((s.line, "false"), []).append(z.And(st.pc, z.Not(c)))
            ta, tb = State(z.And(st.pc, c), st.env), State(z.And(st.pc, z.Not(c)), st.env)
            a, ga = self.block(s.body, ta)
            b, gb = self.block(s.orelse, tb)
            return self.join(st, [(c, ta, a), (z.Not(c), tb, b)]), ga + gb
        if k == "EVALUATE":
            return self.evaluate(s, st)
        if k == "MOVE":
            return self.move(st, s), []
        if k == "SET-TRUE":
            return self.set_true(st, s), []
        if k == "INITIALIZE":
            return self.initialize(st, s), []
        if k == "COMPUTE" and not s.phrases:
            return self.compute(st, s), []
        if k == "STRING" and not s.phrases and not s.data.get("pointer") and s.data.get("into") is not None:
            return self.string(st, s), []
        if k == "ARITH" and not s.phrases and s.data.get("op") in ("+=", "-=") and s.data.get("targets"):
            return self.add_to(st, s), []
        if k == "GOTO":
            targets = s.data.get("targets") or []
            for t in targets:
                j = self._jump(t)
                if j is None:
                    self.why.append(f"line {s.line}: GO TO {t}, no such paragraph")
                else:
                    gotos.append((j, st))
            return (st if s.data.get("depending") else None), gotos
        if k in ("GOBACK", "STOP"):
            return None, []
        if k == "EXIT":
            what = " ".join(str(w).upper() for w in s.data.get("what") or [])
            if "PROGRAM" in what:
                # IBM: EXIT PROGRAM in a program nobody CALLs or LINKs (no USING, no CICS) does nothing
                main = not self.prog.proc.using and not any(r.name.upper() == "DFHEIBLK" for r in self.prog.records)
                return (st if main else None), []
            if what:
                self.why.append(f"line {s.line}: EXIT {what}")
            return st, []
        if k == "PERFORM":
            return self.perform(s, st)
        if k == "EXEC":
            return self.exec_(s, st)
        if k in ("DISPLAY", "CONTINUE", "OPEN", "CLOSE", "WRITE") and not s.phrases:
            return self.havoc(st, self.writes.targets(s), s.line), []
        if k == "HOLE" and re.match(r"\s*(GO|PERFORM|EXIT|ALTER|NEXT)\b", s.text, re.I):
            self.why.append(f"line {s.line}: an unmodelled control statement ({s.text.split()[0]})")
        # any other statement: what it names is set fresh; its phrases (AT END / NOT AT END ...) both run
        after = self.havoc(st, self.writes.targets(s), s.line, "set" if k != "READ" else "read")
        if s.body or s.whens:  # SEARCH / inline bodies the walk does not model: each one, or none
            outs: list[State | None] = [after]
            g: list[tuple[int, State]] = []
            for body in [s.body] + [b for _, b in s.whens]:
                o, gg = self.block(body, after)
                outs.append(o)
                g += gg
            return self.merge([o for o in outs if o is not None]), g
        if not s.phrases:
            return after, []
        phrased: list[State | None] = [after]
        branches: list[list] = []
        for yes, no in PHRASE_PAIRS:
            if yes in s.phrases or no in s.phrases:
                branches += [s.phrases.get(yes, []), s.phrases.get(no, [])]
        for body in branches:
            o, gg = self.block(body, after)
            phrased.append(o)
            gotos += gg
        return self.merge([o for o in phrased if o is not None]), gotos

    def exec_(self, s: S.Stmt, st: State) -> tuple[State | None, list[tuple[int, State]]]:
        t = re.sub(r"\s+", " ", s.text.upper())
        self.exec_text[s.line] = t
        gotos: list[tuple[int, State]] = []
        after = self.havoc(st, self.writes.targets(s), s.line, "exec")
        if t.startswith("EXEC CICS"):
            after = self.response(after, t, s.line)
            self._branch_to(self.handlers["abend"], after, gotos)
            if "RESP" not in t and "NOHANDLE" not in t:
                self._branch_to(self.handlers["cics"], after, gotos)
            if re.match(r"EXEC CICS (RETURN|XCTL|ABEND)\b", t):
                return None, gotos
        elif t.startswith("EXEC SQL"):
            after = self.sqlcode(after, s.line)
            self._branch_to(self.handlers["sql"], after, gotos)
        return after, gotos

    def response(self, st: State, t: str, line: int) -> State:
        """The command's response as one symbol: its RESP(item) and EIBRESP hold it, and it is one of IBM's DFHRESP
        values. `resp_meta` keeps the command and resource a fault plan would name, for `scenario`."""
        from gitgalaxy.standards.cics.resp import DFHRESP  # noqa: PLC0415

        z = self.z
        self._n += 1
        name = f"resp@{line}#{self._n}"
        v = z.Int(name)
        self.axioms[name] = [z.Or([v == n for n in sorted(set(DFHRESP.values()))])]
        self.resp_meta[name] = (line, *self.fault_target(t))
        env = dict(st.env)
        targets = re.findall(r"\bRESP\s*\(\s*([A-Z0-9][A-Z0-9-]*)\s*\)", t) + ["EIBRESP"]
        for tname in targets:
            hit = self.items.by_name.get(tname, [])
            if len(hit) == 1 and id(hit[0]) in env and _kind(hit[0]) == "num" and hit[0].scale == 0:
                env[id(hit[0])] = self._fit(v, 0, hit[0], line)
        return State(st.pc, env)

    def sqlcode(self, st: State, line: int) -> State:
        """The statement's SQLCODE as one symbol the SQLCA's SQLCODE holds (any value: Db2's codes are not listed
        here); `sql_meta` keeps its line, for an `sql_faults` plan (`scenario`)."""
        hit = [it for it in self.writes.sqlca if it.name.upper() == "SQLCODE"]
        if len(hit) != 1 or id(hit[0]) not in st.env or _kind(hit[0]) != "num":
            return st
        self._n += 1
        name = f"sqlcode@{line}#{self._n}"
        v = self.z.Int(name)
        self.axioms[name] = []
        self.sql_meta[name] = line
        return State(st.pc, {**st.env, id(hit[0]): self._fit(v, 0, hit[0], line)})

    def fault_target(self, t: str) -> tuple[str, str | None, str | None]:
        """(command, resource key, resource name) of an EXEC CICS text, as a fault plan names them; the name is
        None when the program computes it (no literal, no item with one value)."""
        m = re.match(r"EXEC CICS (\w+)(?: (\w+))?", t)
        verb = m.group(1) if m else ""
        two = f"{verb}-{m.group(2)}" if m and m.group(2) else verb
        cmd = two if two in FAULT_TWO_WORDS else verb
        for opt, arg in _OPTION.findall(t):
            key = FAULT_RESOURCE.get(opt)
            if not key or (opt == "MAP" and cmd not in ("SEND-MAP", "RECEIVE-MAP")):
                continue
            arg = arg.strip()
            if arg[:1] in "'\"":
                return cmd, key, arg.strip("'\"").strip()
            hit = self.items.by_name.get(arg, [])
            vals = self.vs.get(id(hit[0])) if len(hit) == 1 else None
            if vals and len(vals) == 1:
                return cmd, key, str(next(iter(vals))).strip()
            return cmd, key, None
        return cmd, None, None

    def evaluate(self, s: S.Stmt, st: State) -> tuple[State | None, list[tuple[int, State]]]:
        z = self.z
        names = self.arms.get(s.line)
        whens = s.whens
        if names is None or len(names) < len([w for w in whens if w[0] is not None]):
            self.unmatched.add(s.line)
            names = None
        subjects = s.data.get("subjects") or []
        arms: list[tuple[Any, State, State | None]] = []
        prior = z.BoolVal(False)
        gotos: list[tuple[int, State]] = []
        has_other = False
        for i, (conds, body) in enumerate(whens):
            if conds is None:
                m = z.BoolVal(True)
                has_other = True
                name = "OTHER"
            else:
                m = z.Or([self._alternative(subjects, alt, st, s.line) for alt in conds]) if conds else z.BoolVal(False)
                name = names[i] if names is not None and i < len(names) else f"WHEN#{i}"
            guard = z.And(z.Not(prior), m)
            entry = State(z.And(st.pc, guard), st.env)
            self.hits.setdefault((s.line, name), []).append(entry.pc)
            o, g = self.block(body, entry)
            arms.append((guard, entry, o))
            gotos += g
            prior = z.Or(prior, m)
        if not has_other:
            guard = z.Not(prior)
            rest = State(z.And(st.pc, guard), st.env)
            arms_n = len([w for w in whens if w[0] is not None])
            fall = names[arms_n] if names is not None and len(names) > arms_n else "OTHER"
            self.hits.setdefault((s.line, fall), []).append(rest.pc)
            arms.append((guard, rest, rest))
        return self.join(st, arms), gotos

    def join(self, st: State, arms: list[tuple[Any, State, State | None]]) -> State | None:
        """The state after a branch whose arms cover every case (IF then / else, EVALUATE's arms and the rest):
        when every arm ends normally with the path condition it started with, the path condition is the one before
        the branch and each item is If(guard, ...) over the arms (exact, and small); otherwise the general merge."""
        z = self.z
        if all(o is not None and o.pc is e.pc for _, e, o in arms):
            env = {}
            for k in st.env:
                vals = [o.env[k] for _, _, o in arms]  # type: ignore[union-attr]
                if all(v.eq(vals[0]) for v in vals[1:]):
                    env[k] = vals[0]
                    continue
                acc = vals[-1]
                for (g, _, _), v in zip(reversed(arms[:-1]), reversed(vals[:-1])):
                    acc = z.If(g, v, acc)
                env[k] = acc
            return State(st.pc, env)
        return self.merge([o for _, _, o in arms if o is not None])

    def _alternative(self, subjects: list, objs: list, st: State, line: int) -> Any:
        z = self.z
        parts = []
        for subj, obj in zip(subjects, objs):
            kind, a, b, neg = obj
            m = None
            if kind == "ANY":
                m = z.BoolVal(True)
            elif kind in ("TRUE", "FALSE"):
                m = z.BoolVal((subj == kind)) if subj in ("TRUE", "FALSE") else None
            elif kind == "COND" and subj in ("TRUE", "FALSE"):
                c = self.cond(a, st, line)
                m = c if subj == "TRUE" else z.Not(c)
            elif kind == "VALUE" and subj in ("TRUE", "FALSE"):
                c = self.cond(E.CondName(a) if isinstance(a, E.Ref) else a, st, line)
                m = c if subj == "TRUE" else z.Not(c)
            elif kind == "VALUE" and not isinstance(subj, (str, tuple)):
                m = self.compare("=", subj, a, st, line)
            elif kind == "RANGE" and not isinstance(subj, (str, tuple)):
                lo, hi = self.compare(">=", subj, a, st, line), self.compare("<=", subj, b, st, line)
                m = z.And(lo, hi) if lo is not None and hi is not None else None
            if m is None:
                self._n += 1
                m = z.Bool(f"when@{line}#{self._n}")
            parts.append(z.Not(m) if neg else m)
        return z.And(parts) if parts else z.BoolVal(True)

    def perform(self, s: S.Stmt, st: State) -> tuple[State | None, list[tuple[int, State]]]:
        z = self.z
        d = s.data
        inline = bool(d.get("inline")) or not d.get("target")
        rg = None
        if not inline:
            rg = self._range(d["target"], d.get("thru"))
            if rg is None:
                self.why.append(f"line {s.line}: PERFORM {d['target']}, no such paragraph")
                return st, []

        def once(state: State) -> tuple[State | None, list[tuple[int, State]]]:
            if inline:
                return self.block(s.body, state)
            assert rg is not None
            return self.run(rg[0], rg[1], state), []

        varying = d.get("varying")
        loop = d.get("until") is not None or varying or d.get("times") is not None
        if not loop:
            return once(st)
        gotos: list[tuple[int, State]] = []
        var = None
        if varying:  # (index, FROM, BY, UNTIL): the index starts at FROM
            hit = self.items.resolve(varying[0])
            var = hit[0] if len(hit) == 1 and self.items.tracked(hit[0]) and _kind(hit[0]) == "num" else None
            st = State(st.pc, dict(st.env))
            if var is not None:
                self.assign(st, var, varying[1], s.line)
        if d.get("test_after"):
            _, g = once(st)
            gotos += g
        body = self.loop_writes([] if rg is None else list(range(rg[0], rg[1] + 1)), s.body if inline else [])
        head = self.havoc(st, body + self.writes.targets(s), s.line, "loop")
        # a counter that holds a known number before the loop and that the loop only ever increases stays at least
        # that number on every iteration (MOVE 1 TO IX ... PERFORM UNTIL IX > 5 ... ADD 1 TO IX)
        inside = self.loop_stmts([] if rg is None else list(range(rg[0], rg[1] + 1)), s.body if inline else [])
        for it in body:
            before = st.env.get(id(it))
            if _kind(it) == "num" and before is not None and z.is_int_value(before) and it is not var:
                if self.only_increased(it, inside):
                    head = State(z.And(head.pc, head.env[id(it)] >= before), head.env)
                elif self.only_increased(it, inside, down=True):
                    head = State(z.And(head.pc, head.env[id(it)] <= before), head.env)
        if self.flags:  # a loop may set or clear a flag on any iteration
            head = State(head.pc, {**head.env, **self.fresh_flags()})
        if varying and var is not None and var not in body:
            frm, by = varying[1], varying[2]
            if all(isinstance(x, E.Lit) and isinstance(x.value, Decimal) for x in (frm, by)) and by.value > 0:
                low = norm_value(frm, var)  # the index only grows from FROM: a bound every iteration keeps
                if low is not None:
                    head = State(z.And(head.pc, head.env[id(var)] >= low), head.env)
        until = d.get("until") if d.get("until") is not None else (varying[3] if varying else None)
        c = self.cond(until, head, s.line)
        exit_ = State(z.And(head.pc, c), head.env)
        _, g = once(State(z.And(head.pc, z.Not(c)), head.env))
        return exit_, gotos + g

    def run(self, lo: int, hi: int | None, st: State) -> State | None:
        """Run from paragraph `lo` until the end of paragraph `hi` (a PERFORM's return) or the program stops.

        A range PERFORMed again while it runs (a HANDLE label that PERFORMs back into it) is walked once more from the
        state where every item is fresh, which covers every state it could be entered in; after that a re-entry
        returns that state at once, and the caller goes on from it."""
        if (lo, hi) in self.active:
            if (lo, hi) not in self.reentered:
                self.reentered.add((lo, hi))
                self.active.append((lo, hi))
                self._run(lo, hi, self.top())
                self.active.pop()
            return State(st.pc, self.top().env)
        self.active.append((lo, hi))
        try:
            return self._run(lo, hi, st)
        finally:
            self.active.pop()

    def _run(self, lo: int, hi: int | None, st: State) -> State | None:
        self.depth += 1
        if self.depth > 40:
            self.why.append("PERFORM nesting deeper than 40 (recursion?)")
            self.depth -= 1
            return st
        paras = self.prog.proc.paragraphs
        pending: dict[int, list[State]] = {lo: [st]}
        visits: dict[int, int] = {}
        returns: list[State] = []
        while pending:
            i = min(pending)
            arriving = pending.pop(i)
            visits[i] = visits.get(i, 0) + 1
            if visits[i] == 2:
                cur: State | None = self.top()
            elif visits[i] > 2:
                continue
            else:
                cur = self.merge(arriving)
            assert cur is not None
            self.entered.setdefault(paras[i].name.upper(), []).append(cur.pc)
            end, gotos = self.block(paras[i].body, cur)
            for j, g in gotos:
                pending.setdefault(j, []).append(g)
            if end is None:
                continue
            if hi is not None and i == hi:
                returns.append(end)
            elif i + 1 < len(paras):
                pending.setdefault(i + 1, []).append(end)
        self.depth -= 1
        return self.merge(returns)

    def known(self) -> set[tuple[int, str]]:
        """Every (line, outcome) the walk's reading of the program has, reached or not: an outcome named otherwise
        can never be confirmed."""
        out: set[tuple[int, str]] = set(self.hits)
        for p in self.prog.proc.paragraphs:
            for s in S.walk(p.body):
                if s.kind == "IF":
                    out |= {(s.line, "true"), (s.line, "false")}
                elif s.kind == "EVALUATE" and s.line in self.arms and s.line not in self.unmatched:
                    out |= {(s.line, n) for n in self.arms[s.line]}
        return out

    # -- the questions --
    def explore(self) -> None:
        self.run(0, None, self.initial())

    def ask(self, formulas: list[Any], timeout_ms: int = TIMEOUT_MS, printable: bool = False) -> tuple[str, Any]:
        """`printable`: prefer input text a person can type (then any bytes, if only those reach it)."""
        z = self.z
        sol = z.Solver()
        sol.set("timeout", timeout_ms)
        goal = z.Or(formulas) if formulas else z.BoolVal(False)
        sol.add([a for name in _names_in([goal]) for a in self.axioms.get(name, [])])  # each constrains one symbol
        sol.add(goal)
        if printable:
            sol.push()
            plans = plannable()
            for name in _names_in(formulas):
                if name in self.resp_meta:  # a response a scenario's fault plan can give, or NORMAL
                    _, cmd, _, _ = self.resp_meta[name]
                    codes = [0] + [DFHRESP_OF(c) for c in plans.get(cmd, {})]
                    sol.add(z.Or([z.Int(name) == c for c in codes if c is not None]))
                if name in self.sql_meta:  # success, or an SQLCODE a sql_faults plan names
                    sol.add(z.Or([z.Int(name) == c for c in [0, *sorted(self.known_sqlcodes)]]))
            for name in _names_in(formulas):
                _, it, _ = self.symbols.get(name, ("", None, 0))
                if it is not None and _kind(it) == "str":
                    v = z.BitVec(name, 8 * it.size)
                    for i in range(it.size):
                        b = self.sub(v, i, 1)
                        sol.add(z.Or(b == 32, b == 45, z.And(b >= 48, b <= 57), z.And(b >= 65, b <= 90)))
            if self.known_values:  # first: values the case's scenarios already use for the same field
                sol.push()
                for name in _names_in(formulas):
                    _, it, _ = self.symbols.get(name, ("", None, 0))
                    vals = self.known_values.get(it.name.upper()) if it is not None and _kind(it) == "str" else None
                    if vals and it is not None:
                        sol.add(z.Or([z.BitVec(name, 8 * it.size) == self.sval(v[: it.size].ljust(it.size))
                                      for v in sorted(vals)]))  # fmt: skip
                if sol.check() == z.sat:
                    return "witness", sol.model()
                sol.pop()
            if sol.check() == z.sat:
                return "witness", sol.model()
            sol.pop()
        r = sol.check()
        if r == z.sat:
            return "witness", sol.model()
        if r == z.unsat:
            return ("confirmed", None) if not self.why else ("inconclusive", None)
        return "inconclusive", None

    def witness(self, model: Any, formulas: list[Any] | None = None, limit: int = 40) -> list[dict[str, Any]]:
        """The inputs a model chose that the outcome's condition depends on: initial values (in:) and values read
        or set by unmodelled statements (exec:, read:)."""
        relevant = _names_in(formulas) if formulas else None
        out = []
        for d in model.decls():
            name = d.name()
            if name not in self.symbols or (relevant is not None and name not in relevant):
                continue
            origin, it, line = self.symbols[name]
            if origin not in ("in", "exec", "read"):
                continue
            v = model[d]
            val = _value(v, it)
            out.append({"from": origin, "item": it.name, "line": line, "value": val})
        out.sort(key=lambda x: (x["line"], x["item"]))
        return out[:limit]


def scenario(w: Walk, model: Any, formulas: list[Any], case: dict[str, Any], target: str) -> dict[str, Any]:
    """A witness as one input of strengthen.py / survivor_attack.py `try` (a CICS case): the COMMAREA fields, the
    AID and the RECEIVE MAP fields the outcome's condition depends on. Values not in it keep the case's defaults."""
    relevant = _names_in(formulas)
    roots = {seg.get("record", "").upper() for seg in (case.get("commarea") or {}).get("segments", [])}
    commarea: dict[str, Any] = {}
    receive: dict[str, dict[str, str]] = {}
    faults: list[dict[str, Any]] = []
    unplanned: list[str] = []
    plans = plannable()
    names = {v: k for k, v in _dfhresp().items()}
    for name in sorted(relevant & set(w.resp_meta), key=lambda n: w.resp_meta[n][0]):
        code = model.eval(w.z.Int(name), model_completion=True).as_long()
        if code == 0:
            continue
        line, cmd, key, res = w.resp_meta[name]
        cond = names.get(code, str(code))
        resp2 = plans.get(cmd, {}).get(cond)
        if resp2 is None or (key is not None and res is None):
            unplanned.append(f"{cmd} at line {line} answering {cond}")
            continue
        if any(x["cmd"] == cmd and x.get(key or "") == res for x in faults):
            continue  # the same command performed from two places: one plan, its first run
        f: dict[str, Any] = {"cmd": cmd, **({key: res} if key else {}), "nth": 1, "resp": cond}
        if resp2:
            f["resp2"] = resp2[0]
        faults.append(f)
    aid = None
    for d in sorted(model.decls(), key=lambda d: w.symbols.get(d.name(), ("", None, 0))[2]):
        name = d.name()
        if name not in w.symbols or name not in relevant:
            continue
        origin, it, line = w.symbols[name]
        v = model[d]
        val = _value(v, it)
        anc = {it.name.upper()} | {a.name.upper() for a in _ancestors(it)}
        if it.name.upper() == "EIBAID":
            aid = next((c.name for c in w.items.all if c.name.upper().startswith("DFH") and c.values
                        and norm_value(c.values[0], it) == val), None)  # fmt: skip
        elif anc & roots and it.name.upper() not in commarea:
            commarea[it.name] = val.rstrip() if isinstance(val, str) else val
        elif origin == "exec" and (m := re.search(r"RECEIVE MAP\s*\(\s*'([A-Z0-9#@$]+)'", w.exec_text.get(line, ""))):
            receive.setdefault(m.group(1), {})[it.name] = val.rstrip() if isinstance(val, str) else str(val)
        elif (top := (_ancestors(it) or [it])[-1].name.upper()).endswith("I") and top[:-1] in w.received_maps \
                and it.name.upper().endswith("I") and isinstance(val, str):  # fmt: skip
            receive.setdefault(top[:-1], {})[it.name] = (
                val.rstrip()
            )  # a symbolic map's input field: what RECEIVE MAP types
    out: dict[str, Any] = {"name": "solver-" + re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")}
    default_aid = next((sc.get("aid") for sc in case.get("scenarios", []) if sc.get("aid")), None)
    if aid or default_aid:  # a terminal task's key; a LINKed program's scenarios name none
        out["aid"] = aid or default_aid
    out["commarea"] = commarea or None
    if receive:
        out["receive"] = receive
    if faults:
        out["faults"] = faults
    sql = []
    for name in sorted(relevant & set(w.sql_meta), key=lambda n: w.sql_meta[n]):
        code = model.eval(w.z.Int(name), model_completion=True).as_long()
        line = w.sql_meta[name]
        if code != 0 and not any(x["line"] == line for x in sql):
            sql.append({"line": line, "nth": 1, "sqlcode": code})
    if sql:
        out["sql_faults"] = sql
    out["targets"] = [target]
    why = f"branch_solver witness for {target}: the values its condition depends on"
    if faults:
        why += "; each fault on the command's first run (nth 1): raise nth if the command runs before the one meant"
    if unplanned:
        why += "; needs " + ", ".join(unplanned) + ", which no fault plan gives (#6271): not a scenario as it stands"
    out["why"] = why
    return out


def _dfhresp() -> dict[str, int]:
    from gitgalaxy.standards.cics.resp import DFHRESP  # noqa: PLC0415

    return dict(DFHRESP)


def DFHRESP_OF(cond: str) -> int | None:  # noqa: N802 -- read as the COBOL function it mirrors
    return _dfhresp().get(cond)


def plannable() -> dict[str, dict[str, tuple[int, ...]]]:
    """Command -> {condition: IBM's RESP2 values} a scenario's fault plan may give it (equivalence_cics_faults.py's
    file-control and terminal tables, and the program-control conditions it documents); {} without the harness."""
    try:
        import equivalence_cics_faults as ecf  # noqa: PLC0415
    except Exception:  # noqa: BLE001 -- the harness is not importable here: no fault is planned
        return {}
    out: dict[str, dict[str, tuple[int, ...]]] = {}
    for cond, per_cmd in ecf.FILE_FAULT_CONDITIONS.items():
        for cmd, resp2 in per_cmd.items():
            if (cmd, cond) not in ecf.FILE_FAULT_UNMODELLED and (cmd, cond) not in ecf.DUP_KEY_REFUSED:
                out.setdefault(cmd, {})[cond] = resp2
    for cmd, conds in ecf.UI_FAULT_CONDITIONS.items():
        out.setdefault(cmd, {}).update(conds)
    out.setdefault("XCTL", {}).update({"PGMIDERR": (3,), "NOTAUTH": (101,), "INVREQ": ()})
    out.setdefault("LINK", {}).update({"PGMIDERR": (3,), "NOTAUTH": (101,), "INVREQ": (), "LENGERR": ()})
    return out


def _ancestors(it: L.Item) -> list[L.Item]:
    out = []
    p = it.parent
    while p is not None:
        out.append(p)
        p = p.parent
    return out


def _names_in(formulas: list[Any]) -> set[str]:
    """The names of the free constants of some z3 formulas."""
    z = _z3()
    seen: set[int] = set()
    out: set[str] = set()
    todo = list(formulas)
    while todo:
        e = todo.pop()
        if e.get_id() in seen:
            continue
        seen.add(e.get_id())
        if z.is_const(e) and e.decl().kind() == z.Z3_OP_UNINTERPRETED:
            out.add(e.decl().name())
        todo += e.children()
    return out


def _value(v: Any, it: L.Item) -> Any:
    """A model value as the item holds it: text (latin-1) or a number."""
    if _kind(it) == "str":
        bits = v.as_binary_string() if hasattr(v, "as_binary_string") else format(v.as_long(), "b")
        n = int(bits, 2) if bits else 0
        return n.to_bytes(it.size, "big").decode("latin-1")
    n = int(v.as_long())
    return n / (10**it.scale) if it.scale else n


# ---- cases ---------------------------------------------------------------------------------------------------------
def evaluate_arms(source: Path) -> dict[int, list[str]]:
    """EVALUATE line -> its outcome names as the coverage report names them: each WHEN arm (`WHEN@line`), then
    `OTHER`, or the fall-through name (`none`) of an EVALUATE with no WHEN OTHER."""
    import cobol_coverage as cc  # noqa: PLC0415

    from gitgalaxy.core.source_text import read_source  # noqa: PLC0415

    branches, _ = cc.branch_points(read_source(source).text)
    return {b.line: b.outcomes() for b in branches if b.kind == "EVALUATE"}


def corpus_root(name: str) -> Path:
    import mainframe_corpus as mc  # noqa: PLC0415

    if name in getattr(mc, "CRUCIBLE_CORPORA", {}):
        import cics_crucible as ccr  # noqa: PLC0415

        return Path(ccr.crucible_path(None))
    return mc.cache_root() / name


def case_program(case: str, work: Path) -> Program:
    data = json.loads((REPO / "tests" / "equivalence" / case / "case.json").read_text(encoding="utf-8"))
    base = corpus_root(data["corpus"])
    dirs = [base / d for d in data.get("copy_dirs", ["app/cpy"])]
    dirs += [base / d for d in (data.get("db2") or {}).get("include_dirs", [])]
    bms = work / f"bms-{data['corpus']}"
    if not bms.is_dir():
        from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks  # noqa: PLC0415

        bms_copybooks([p for p in base.rglob("*") if p.is_file() and p.suffix.lower() == ".bms"
                       and ".git" not in p.parts], bms)  # fmt: skip
    return load_program(base / data["program_source"], dirs, bms)


def solve_case(case: str, work: Path, timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    """Every stated infeasible outcome of one case, checked."""
    import infeasible_outcomes as io  # noqa: PLC0415

    entries = io.stated(case)
    out: dict[str, Any] = {"case": case, "entries": []}
    try:
        prog = case_program(case, work)
        w = Walk(prog, evaluate_arms(prog.source))
        w.explore()
    except Exception as e:  # a program the front end or the walk cannot read: every entry is inconclusive
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        for e_ in entries:
            out["entries"].append({"key": io.key(e_), "family": e_.get("family"), "verdict": "inconclusive",
                                   "why": [out["error"]]})  # fmt: skip
        return out
    out["incomplete"] = sorted(set(w.why))
    known = w.known()
    paras = {p.name.upper() for p in prog.proc.paragraphs}
    for e_ in entries:
        row: dict[str, Any] = {"key": io.key(e_), "family": e_.get("family")}
        if io.is_paragraph(e_):
            if str(e_["unit"]).upper() not in paras:
                row.update(verdict="inconclusive", why=[f"no paragraph {e_['unit']} in the walk's reading"])
                out["entries"].append(row)
                continue
            formulas = w.entered.get(str(e_["unit"]).upper(), [])
        else:
            line, outcome = int(e_["line"]), str(e_["outcome"])
            if e_.get("kind") == "EVALUATE" and line in w.unmatched:
                row.update(
                    verdict="inconclusive", why=["the EVALUATE's arms could not be matched to the coverage names"]
                )
                out["entries"].append(row)
                continue
            if (line, outcome) not in known:
                row.update(verdict="inconclusive", why=[f"the walk's reading has no outcome {outcome} at line {line}"])
                out["entries"].append(row)
                continue
            formulas = w.hits.get((line, outcome), [])
            if not formulas:
                row["note"] = "the walk never reaches this statement"
        verdict, model = w.ask(formulas, timeout_ms)
        row["verdict"] = verdict
        if verdict == "witness":
            row["witness"] = w.witness(model, formulas)
        if verdict == "inconclusive":
            row["why"] = sorted(set(w.why)) or ["solver timeout"]
        out["entries"].append(row)
    return out


def reach(case: str, targets: list[str], work: Path, timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    spec = json.loads((REPO / "tests" / "equivalence" / case / "case.json").read_text(encoding="utf-8"))
    prog = case_program(case, work)
    known: dict[str, set[str]] = {}
    codes = {int(f["sqlcode"]) for sc in spec.get("scenarios", []) for f in sc.get("sql_faults") or []
             if isinstance(f.get("sqlcode"), int)}  # fmt: skip
    for sc in spec.get("scenarios", []):
        for k, v in (sc.get("commarea") or {}).items():
            if isinstance(v, str):
                known.setdefault(k.upper(), set()).add(v)
        for fields in (sc.get("receive") or {}).values():
            for k, v in (fields or {}).items() if isinstance(fields, dict) else []:
                if isinstance(v, str):
                    known.setdefault(k.upper(), set()).add(v)
    w = Walk(prog, evaluate_arms(prog.source))
    w.known_values = known
    w.known_sqlcodes |= codes
    w.explore()
    out: dict[str, Any] = {"case": case, "incomplete": sorted(set(w.why)), "targets": []}
    for t in targets:
        line, _, outcome = t.partition(":")
        formulas = w.hits.get((int(line), outcome), [])
        verdict, model = w.ask(formulas, timeout_ms, printable=True)
        row: dict[str, Any] = {"target": t, "verdict": verdict}
        if model is not None:
            row["witness"] = w.witness(model, formulas)
            if spec.get("kind") == "cics":
                row["input"] = scenario(w, model, formulas, spec, t)
        out["targets"].append(row)
    return out


def paragraphs(case: str, work: Path, timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    """Each paragraph of a case's program: `confirmed` no input enters it (a survivor verdict such as "never
    PERFORMed" holds), `witness` some input does, `inconclusive` the walk could not decide."""
    prog = case_program(case, work)
    w = Walk(prog, evaluate_arms(prog.source))
    w.explore()
    rows = [{"paragraph": p.name, "line": p.line, "verdict": w.ask(w.entered.get(p.name.upper(), []), timeout_ms)[0]}
            for p in prog.proc.paragraphs]  # fmt: skip
    return {"case": case, "incomplete": sorted(set(w.why)), "paragraphs": rows}


def backend(case: str, prompt_file: Path, work: Path, timeout_ms: int = TIMEOUT_MS) -> list[dict[str, Any]]:
    """strengthen.py's backend (`--backend-command "python tests/tools/branch_solver.py backend CASE {prompt_file}"`):
    the solver's inputs for the branches the prompt lists as reached by no run, in strengthen's input format. The
    oracle then proves each one alone, as it does a model's proposal; an outcome the solver confirms unreachable gets
    no input."""
    text = prompt_file.read_text(encoding="utf-8")
    keys = re.findall(r"(?m)^- ([A-Z0-9][A-Z0-9-]*|\(MAIN\)|PROCEDURE-DIVISION):(\d+):([A-Za-z0-9@]+) \(", text)
    if not keys:
        return []
    res = reach(case, [f"{line}:{outcome}" for _, line, outcome in keys], work, timeout_ms)
    out, seen = [], set()
    for (unit, line, outcome), row in zip(keys, res["targets"]):
        inp = row.get("input")
        if not inp or inp["name"] in seen:
            continue
        seen.add(inp["name"])
        out.append({**inp, "targets": [f"{unit}:{line}:{outcome}"]})
    return out


RUNTIME_RECORDS = ("DFHEIBLK", "SQLCA", "DFHAID")  # records the det runtime reads or sets outside any statement


def fields_used(case: str, work: Path, timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    """Which WORKING-STORAGE items' accessors no reachable statement runs (`unread`): a det-port mutant of such an
    item's Field declaration (offset, length, kind) changes nothing any input can see. An item counts as `used` when a
    reachable statement names it, an ancestor or a condition-name of either; a symbolic-map item when a reachable SEND
    / RECEIVE MAP names its map; and always when the runtime may touch it outside a statement (LINKAGE, FILE SECTION,
    the EIB, DFHAID, the SQLCA, FILE STATUS, an ODO object, an item whose ADDRESS is taken, a numeric-edited item set at creation).
    Every doubt counts as used. {"case", "incomplete", "unread": [{"record", "item"}], "used": count}."""
    prog = case_program(case, work)
    spec = json.loads((REPO / "tests" / "equivalence" / case / "case.json").read_text(encoding="utf-8"))
    return {"case": case, **unread_items(prog, spec, timeout_ms)}


def unread_items(prog: Program, spec: dict[str, Any], timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    """fields_used for a loaded program and its case.json (`spec`)."""
    w = Walk(prog, evaluate_arms(prog.source))
    w.explore()
    out: dict[str, Any] = {"incomplete": sorted(set(w.why)), "unread": [], "used": 0}
    stmts = [x for p in prog.proc.paragraphs for x in S.walk(p.body)]
    maps = {m.upper() for x in stmts if x.kind == "EXEC" for m in re.findall(r"\bMAP\s*\(\s*'([^']+)'", x.text, re.I)}
    # the records the harness fills or reads through a typed DTO: the COMMAREA segments, the datasets' records
    dto = {str(seg.get("record", "")).upper() for seg in (spec.get("commarea") or {}).get("segments", [])}
    for ds in (spec.get("datasets") or {}).values():
        dto |= {str(ds.get(k, "")).upper() for k in ("record", "into") if isinstance(ds, dict) and ds.get(k)}
    always: set[int] = set()
    for r in prog.records:
        if r.name.upper() in dto:
            always |= {id(x) for x in r.walk()}
        for x in r.walk():
            # DFHAID: the runtime's AID switch reads its constants at task start (MOVE DFHPF3 TO EIBAID), no statement
            if x.section not in ("WORKING-STORAGE", "LOCAL-STORAGE") or r.name.upper() in RUNTIME_RECORDS:
                always.add(id(x))
            if x.depending:
                always |= {id(d) for d in w.items.by_name.get(x.depending.upper(), [])}
        always |= {id(x) for x in L.runtime_init(r)}
    always |= {id(x) for x in w.writes.status}
    always |= {id(x) for r in prog.records if id(_root(r)) in w.items.aliased for x in r.walk()}
    users: dict[int, list[Any]] = {}
    for x in stmts:
        if id(x) not in w.at:
            continue  # never reached by the walk: no use
        named = {id(i) for i in w.items.mentioned(x.text)}
        if x.kind == "EXEC" and re.search(r"\b(SEND|RECEIVE)\s+MAP\b", x.text, re.I):
            named |= {id(i) for r in prog.records if r.name.upper()[:-1] in maps and r.name.upper()[-1:] in "IO"
                      for i in r.walk()}  # fmt: skip
        for i in named:
            users.setdefault(i, []).extend(w.at[id(x)])
    for r in prog.records:
        for x in r.walk():
            if x.level in (66, 88):
                continue
            if id(x) in always:
                out["used"] += 1
                continue
            pcs = users.get(id(x), [])
            if pcs and w.ask(pcs, timeout_ms)[0] != "confirmed":
                out["used"] += 1
                continue
            out["unread"].append({"record": r.name, "item": x.name})
    if w.why:  # an incomplete walk settles nothing
        out["used"] += len(out["unread"])
        out["unread"] = []
    return out


def summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    tally: dict[str, dict[str, int]] = {}
    for r in results:
        for e in r["entries"]:
            fam = tally.setdefault(e.get("family") or "?", {"confirmed": 0, "witness": 0, "inconclusive": 0})
            fam[e["verdict"]] += 1
    return tally


def render(results: list[dict[str, Any]]) -> str:
    lines = ["# Branch solver: stated infeasible outcomes", "",
             ("confirmed = no input of the program reaches it (z3: unsatisfiable, walk complete); witness = an input "
              "of the program reaches it (for family G the claim may rest on callers); inconclusive = the walk or "
              "the solver could not decide."), "", "| family | confirmed | witness | inconclusive |", "|---|---|---|---|"]  # fmt: skip
    for fam, t in sorted(summary(results).items()):
        lines.append(f"| {fam} | {t['confirmed']} | {t['witness']} | {t['inconclusive']} |")
    for r in results:
        lines += ["", f"## {r['case']}", ""]
        if r.get("error"):
            lines.append(f"- could not walk: {r['error']}")
        if r.get("incomplete"):
            lines.append(f"- walk incomplete: {'; '.join(r['incomplete'][:5])}")
        for e in r["entries"]:
            extra = ""
            if e.get("witness"):
                extra = "; ".join(f"{x['item']}={x['value']!r}" for x in e["witness"][:6])
            lines.append(f"- `{e['key']}` ({e.get('family')}): **{e['verdict']}**{(' -- ' + extra) if extra else ''}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check the stated infeasible outcomes of these cases (default: all)")
    c.add_argument("cases", nargs="*")
    c.add_argument("--json", action="store_true")
    c.add_argument("--timeout", type=float, default=TIMEOUT_MS / 1000)
    c.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    r = sub.add_parser("reach", help="find an input that takes these outcomes (LINE:OUTCOME)")
    r.add_argument("case")
    r.add_argument("targets", nargs="+")
    r.add_argument("--inputs", action="store_true", help="print only the CICS inputs (a JSON array for --inputs)")
    r.add_argument("--timeout", type=float, default=TIMEOUT_MS / 1000)
    r.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    g = sub.add_parser("paragraphs", help="which paragraphs any input enters (checks 'never PERFORMed' verdicts)")
    g.add_argument("case")
    g.add_argument("--timeout", type=float, default=TIMEOUT_MS / 1000)
    g.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    fu = sub.add_parser("fields", help="WORKING-STORAGE items no reachable statement uses (Field-mutant facts)")
    fu.add_argument("case")
    fu.add_argument("--timeout", type=float, default=TIMEOUT_MS / 1000)
    fu.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    b = sub.add_parser("backend", help="strengthen.py's --backend-command: inputs for the prompt's uncovered branches")
    b.add_argument("case")
    b.add_argument("prompt_file", type=Path)
    b.add_argument("--timeout", type=float, default=TIMEOUT_MS / 1000)
    b.add_argument("--work", type=Path, default=Path("/tmp/gitgalaxy-scratch/branch-solver"))
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    ms = int(args.timeout * 1000)
    if args.cmd == "fields":
        print(json.dumps(fields_used(args.case, args.work, ms), indent=1))
        return 0
    if args.cmd == "backend":
        print(json.dumps(backend(args.case, args.prompt_file, args.work, ms), indent=1, default=str))
        return 0
    if args.cmd == "paragraphs":
        print(json.dumps(paragraphs(args.case, args.work, ms), indent=1))
        return 0
    if args.cmd == "reach":
        res = reach(args.case, args.targets, args.work, ms)
        if args.inputs:  # the inputs alone, ready for survivor_attack.py try --inputs / strengthen.py
            print(json.dumps([t["input"] for t in res["targets"] if t.get("input")], indent=1, default=str))
        else:
            print(json.dumps(res, indent=1, default=str))
        return 0
    import infeasible_outcomes as io  # noqa: PLC0415

    cases = args.cases or sorted(io.load())
    results = [solve_case(cs, args.work, ms) for cs in cases]
    print(json.dumps({"format": FORMAT, "summary": summary(results), "cases": results}, indent=1, default=str)
          if args.json else render(results), end="")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
