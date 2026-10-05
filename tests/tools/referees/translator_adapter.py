r"""The det translator's own parse (gitgalaxy/tools/cobol_to_java/det: source / layout / stmt / cics) as
a referee-facts/1 document (#4273), so the engine-vs-translator cross-check
(tests/tools/fact_crosscheck.py) and the referee scorecard (score.py) read it like any other source.

    python tests/tools/referees/translator_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/translator.json

Nothing here re-parses COBOL: every value comes from the structures the translator builds when it
translates a program (the expanded `Line`s, the `layout.Item` trees, the `stmt.Paragraph`s). Two
readings are this adapter's and are kept minimal:
- the USAGE as written. The translator stores an item's *effective* usage (a group's USAGE inherited
  by its children); the key and the engine record it as written. `parse_layout` snapshots each
  item's usage just before `layout._inherit_usage` runs (a wrapper, no translator change), so the
  `usage` channel compares like with like. Sizes and offsets still use the effective usage.
- an identifier FILE(...) operand is resolved through the single VALUE the translator parsed on
  that item, as the key and the engine do.

Channels (facts.py shapes): units, unit_extents, edges, calls, copybooks, data_items, pic, usage,
occurs, redefines, value, layouts (keyed copybooks, each parsed on its own), cics_commands,
cics_files, plus three the cross-check adds (`EXTRA_CHANNELS`):
    offsets          `ROOT/NAME @offset+bytes` per elementary PIC item of every record the program
                     lays out (outside REDEFINES), and `ROOT (record) +bytes`
    moves            `L<line> MOVE <source> -> <target>`, operands canonical (canon_operand)
    copy_resolution  `MEMBER -> <path in the corpus>` for each COPY / INCLUDE expanded
Not produced: program_ids (the translator takes the program's name from its caller), call_targets
(it does not resolve a dynamic CALL / LINK through a VALUE), sql_access.

A program whose COPY members are not all found, or whose DATA / PROCEDURE DIVISION the translator
refuses (#4411), reports `fail` (or `partial`, with `failed` naming the division: `data` /
`procedure`) with the translator's own message: that is a fact too (the gate tracks it as the
`status` channel and does not count the refused division's channels as disagreements).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from collections.abc import Iterator

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for p in (str(REPO_ROOT), str(HERE.parent), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import facts as F

EXTRA_CHANNELS = ("offsets", "moves", "copy_resolution")
CHANNELS = tuple(ch for ch in F.CHANNELS if ch not in ("program_ids", "call_targets", "sql_access")) + EXTRA_CHANNELS
COPY_SUFFIXES = {".cpy", ".copy", ".cbl", ".cob", ".dcl", ""}
SYNTHETIC = "<fact-crosscheck>"
_INCLUDE = re.compile(r"^\s*EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9#@$-]+)", re.I)

_FIG = {"SPACE": "SPACES", "SPACES": "SPACES", "ZERO": "ZEROES", "ZEROS": "ZEROES", "ZEROES": "ZEROES",
        "LOW-VALUE": "LOW-VALUES", "LOW-VALUES": "LOW-VALUES", "HIGH-VALUE": "HIGH-VALUES",
        "HIGH-VALUES": "HIGH-VALUES", "QUOTE": "QUOTES", "QUOTES": "QUOTES", "NULL": "NULLS", "NULLS": "NULLS"}  # fmt: skip
_DET_FIG = {"SPACES": "SPACES", "ZEROS": "ZEROES", "LOW": "LOW-VALUES", "HIGH": "HIGH-VALUES", "QUOTES": "QUOTES"}
_DET_USAGE = {"BINARY": "COMP", "PACKED": "COMP-3"}


def _copy_not_found(e: Exception) -> str:
    """`COPY NAME` of a CopyNotFound, without the machine's directory list (the ledger must be portable)."""
    m = re.search(r"COPY \S+", str(e))
    return m.group(0) if m else str(e).split(" found in")[0][-80:]


def det():
    """The translator's modules; ImportError (with the extra to install) when tree-sitter-language-pack is
    missing. Called first by every entry point, so a missing extra fails loudly instead of skipping."""
    from gitgalaxy.tools.cobol_to_java.det import cics as C
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import source as S
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    S.cobol_parser()  # the language pack, imported now
    return C, E, L, S, ST


# ------------------------------------------------------------------------------
# Copy directories (the translator takes them from its caller)
# ------------------------------------------------------------------------------
def copy_dirs(root: Path) -> list[Path]:
    """Every directory of the corpus holding a copybook-like member (det_survey.py's rule)."""
    return sorted({p.parent for p in root.rglob("*") if p.is_file() and p.suffix.lower() in COPY_SUFFIXES
                   and ".git" not in p.parts and not p.name.startswith(".")})  # fmt: skip


def nearest_first(prog: Path, dirs: list[Path]) -> list[Path]:
    """`dirs` ordered by how much of the program's path they share (its own application's copybooks first),
    then by name: a stable stand-in for the copy libraries a det-port case names in its case.json."""

    def shared(d: Path) -> int:
        n = 0
        for a, b in zip(prog.parent.parts, d.parts):
            if a != b:
                break
            n += 1
        return n

    return sorted(dirs, key=lambda d: (-shared(d), str(d)))


def bms_dir(root: Path, cache: Path) -> Path:
    """The symbolic maps generated from the corpus's BMS sources (det.source.bms_copybooks), built once."""
    _, _, _, S, _ = det()
    out = cache / "bms" / root.name
    if not (out / ".done").is_file():
        bms = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".bms" and ".git" not in p.parts]
        S.bms_copybooks(bms, out)
        (out / ".done").write_text("", encoding="utf-8")
    return out


# ------------------------------------------------------------------------------
# Canonical operands (shared with the engine and key sides in fact_crosscheck.py)
# ------------------------------------------------------------------------------
def canon_name(s: str) -> str:
    """A data reference without subscripts / reference modification, `IN` as `OF`, upper case."""
    s = s.upper()
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\([^()]*\)", "", s)
    return " ".join(re.sub(r"(?<=\s)IN(?=\s)", "OF", f" {s} ").split())


def canon_number(text: str) -> str:
    try:
        v = Decimal(text)
    except ArithmeticError:
        return text
    return str(int(v)) if v == v.to_integral() else str(v)


def canon_text_operand(src: Optional[str]) -> str:
    """A MOVE source as written (`'N'`, `ZERO`, `+1`, `WS-X(1:2)`, `LENGTH OF X`) in the canonical form."""
    s = (src or "").strip()
    u = s.upper()
    if not s:
        return "-"
    if s[:1] in "'\"":
        return "'" + s[1:-1].replace(s[0] * 2, s[0]) + "'"
    if re.match(r"(?i)^[XN]['\"]", s):
        return u[0] + "'" + u[2:-1] + "'"
    if re.fullmatch(r"[+-]?\d*\.?\d+", s):
        return canon_number(s)
    if u.startswith("ALL "):
        rest = u[4:].strip()
        return "ALL " + (_FIG.get(rest) or ("'" + s[4:].strip()[1:-1] + "'" if rest[:1] in "'\"" else rest))
    if u in _FIG:
        return _FIG[u]
    if u.startswith("FUNCTION "):
        return "FUNCTION " + u[9:].split("(")[0].split()[0]
    m = re.match(r"(?i)^LENGTH\s+OF\s+(.*)$", s)
    if m:
        return "LENGTH OF " + canon_name(m.group(1))
    return canon_name(s)


def canon_operand(o: Any) -> str:
    """A translator operand (det.expr) in the canonical form of canon_text_operand."""
    _, E, _, _, _ = det()
    if isinstance(o, E.Ref):
        return " OF ".join([o.name.upper(), *[q.upper() for q in o.qualifiers]])
    if isinstance(o, E.Fig):
        if o.all_literal is not None:
            return f"ALL '{o.all_literal}'"
        return _DET_FIG.get(o.kind, _FIG.get(o.kind, o.kind))
    if isinstance(o, E.Lit):
        v = o.value
        if isinstance(v, Decimal):
            return canon_number(str(v))
        if isinstance(v, bytes):
            return "X'" + v.hex().upper() + "'"
        return f"'{v}'"
    if isinstance(o, E.Func):
        return "FUNCTION " + o.name.upper()
    if isinstance(o, E.LengthOf):
        return "LENGTH OF " + canon_operand(o.ref)
    return type(o).__name__.upper()


def move_value(line: int, source: str, target: str) -> str:
    """Upper case throughout: the key folds a literal's case (cobol_answer_key.data_move_keys)."""
    return f"L{line} MOVE {source} -> {target}".upper()


# ------------------------------------------------------------------------------
# The DATA DIVISION
# ------------------------------------------------------------------------------
@contextmanager
def _written_usage() -> Iterator[dict[int, str]]:
    """Each item's USAGE as written, recorded just before the translator applies group inheritance."""
    _, _, L, _, _ = det()
    seen: dict[int, str] = {}
    original = L._inherit_usage

    def recording(it: Any, usage: Optional[str]) -> None:
        if usage is None:  # the record's own call, before anything was inherited
            for x in it.walk():
                seen.setdefault(id(x), x.usage)
        original(it, usage)

    L._inherit_usage = recording
    try:
        yield seen
    finally:
        L._inherit_usage = original


def parse_layout(lines: list[Any]) -> tuple[list[Any], dict[int, str]]:
    """layout.parse(lines) plus each item's written usage (id(item) -> usage)."""
    _, _, L, _, _ = det()
    with _written_usage() as seen:
        records = L.parse(lines)
    return records, seen


def value_text(v: Any) -> Optional[str]:
    """A translator VALUE (layout._value) as facts.norm_value spells the key's first literal."""
    if not isinstance(v, tuple):
        return None
    kind = v[0]
    if kind == "range":
        return value_text(v[1])
    if kind == "lit":
        return str(v[1]).upper().strip()
    if kind == "num":
        return F.norm_value(str(v[1]))
    if kind == "fig":
        return _DET_FIG.get(v[1], v[1])
    if kind == "hex":
        return "X'" + v[1].hex().upper() + "'"
    if kind == "all":
        inner = v[1]
        if inner[0] == "lit":
            return f"ALL '{inner[1]}'".upper()
        return "ALL " + (value_text(inner) or "")
    return None


def elementary(rec: Any) -> list[Any]:
    """The elementary storage items of a record in storage order, REDEFINES subtrees (below the root) left
    out, as GalaxyIR.record_layout lists its `fields`."""
    out: list[Any] = []

    def walk(it: Any) -> None:
        if it.level in (66, 88) or (it is not rec and it.redefines):
            return
        if it.children and it.pic is None:
            for c in it.children:
                walk(c)
            return
        if it.pic is None and it.usage == "DISPLAY":
            return  # an empty group: no storage of its own
        out.append(it)

    walk(rec)
    return out


def layout_units(rec: Any, base: int = 0, root_name: Optional[str] = None) -> set[str]:
    """`ROOT/NAME @offset+bytes` per elementary PIC item (FILLER aside), as the key's `layouts`."""
    name = root_name or rec.name
    return {f"{name}/{it.name} @{it.offset - base}+{it.size * it.occurs}"
            for it in elementary(rec) if it.pic and it.name != "FILLER"}  # fmt: skip


def record_bytes(rec: Any) -> str:
    return f"{rec.name} (record) +{rec.size * rec.occurs}"


def copybook_layouts(path: Path, dirs: list[Path], engine: Any = None) -> tuple[Optional[set[str]], Optional[str]]:
    """A keyed copybook's layout units, the member parsed on its own inside a synthetic program (wrapped in an
    01 when its first entry is not one, each top-level entry then laid out from its own offset)."""
    _, _, L, S, _ = det()
    try:
        body = S.expand(S.logical_lines(S._raw_lines(path), str(path)), dirs, chain=frozenset({path.resolve()}),
                        engine=engine)  # fmt: skip
    except S.CopyNotFound as e:
        return None, f"CopyNotFound: {_copy_not_found(e)}"
    first = next((re.match(r"\s*(\d+)\s", ln.text) for ln in body if re.match(r"\s*\d+\s", ln.text)), None)
    wrap = first is not None and int(first.group(1)) not in (1, 77)
    head = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. GGXCHK.", "DATA DIVISION.", "WORKING-STORAGE SECTION."]
    if wrap:
        head.append("01 GG-XCHECK-WRAP.")
    lines = [S.Line(t, SYNTHETIC, 0) for t in head] + body
    try:
        records = L.parse(lines)
    except Exception as e:  # noqa: BLE001 -- the translator's refusal is the result
        return None, f"{type(e).__name__}: {str(e)[:200]}"
    roots = [c for r in records for c in r.children] if wrap else records
    out: set[str] = set()
    for r in roots:
        if r.level in (66, 88) or r.redefines:
            continue
        out |= layout_units(r, base=r.offset)
    return out, None


# ------------------------------------------------------------------------------
# One program
# ------------------------------------------------------------------------------
def program_facts(
    root: Path, prog: Path, dirs: list[Path], key_prog: Optional[dict[str, Any]] = None, engine: Any = None
) -> dict[str, Any]:
    """{status, error, seconds, facts: {channel: set}, records: [(root Item, file, line)]} for one program.
    `engine` (det.source.EngineCopies, #4468): the engine's COPY resolution, which the translator takes as it does
    when it translates (None: its own directory search, as a referee with no scan)."""
    import cobol_answer_key as ak

    C, E, L, S, ST = det()
    key_prog = key_prog or {}
    t0 = time.monotonic()
    out: dict[str, Any] = {"status": "ok", "error": None, "facts": {ch: set() for ch in CHANNELS}, "records": [],
                           "failed": []}  # fmt: skip
    f = out["facts"]
    progfile = str(prog)

    def rel(file: str) -> str:
        return os.path.relpath(file, root).replace("\\", "/")

    try:
        lines = S.program_lines(prog, dirs, engine)
    except S.CopyNotFound as e:
        out.update(status="fail", error=f"CopyNotFound: {_copy_not_found(e)}", failed=["copy", "data", "procedure"])
        out["seconds"] = round(time.monotonic() - t0, 3)
        return out

    # copybooks: the members the program's own text COPYs / INCLUDEs (the translator's own COPY pattern), and
    # the file in the corpus each expanded to (system / BMS-generated members resolve outside it: name only)
    direct = set()
    own_logical = S.logical_lines(S._raw_lines(prog), progfile)
    for i, ln in enumerate(own_logical):
        m = S._COPY.match(ln.text)
        if m:
            direct.add(m.group(2).upper())
        elif re.match(r"\s*EXEC\s+SQL\b", ln.text, re.I):
            block, j = ln.text, i  # an EXEC SQL INCLUDE block over several lines, joined as det.source.expand does
            while not re.search(r"\bEND-EXEC\b", block, re.I) and j + 1 < len(own_logical):
                j += 1
                block += " " + own_logical[j].text
            inc = _INCLUDE.match(block)
            if inc:
                direct.add(inc.group(1).upper())
    f["copybooks"] = set(direct)
    for ln in lines:
        member = Path(ln.file).stem.upper()
        if ln.file != progfile and member in direct:
            r = rel(ln.file)
            if not r.startswith(".."):
                f["copy_resolution"].add(f"{member} -> {r}")

    errors = []
    # ---- the DATA DIVISION ----
    try:
        records, written = parse_layout(lines)
    except Exception as e:  # noqa: BLE001 -- LayoutError, a refused VALUE (#4411): the translator's verdict
        records, written = None, {}
        errors.append(f"layout: {type(e).__name__}: {str(e)[:160]}")
        out["failed"].append("data")
    values_of: dict[str, list[str]] = {}
    if records is not None:
        for rec in records:
            src = lines[rec.line - 1]
            if not rel(src.file).startswith(".."):  # a system or BMS-generated member: not the corpus's record
                out["records"].append((rec, rel(src.file), src.line))
                f["offsets"] |= layout_units(rec)
                f["offsets"].add(record_bytes(rec))
            for it in rec.walk():
                for x in [it, *it.conditions]:
                    ln = lines[x.line - 1]
                    v = value_text(x.values[0]) if x.values else None
                    if v is not None and x.values[0][0] == "lit":
                        values_of.setdefault(x.name, []).append(x.values[0][1])
                    if ln.file != progfile:
                        continue
                    u = written.get(id(x), x.usage) if x.level != 88 else None
                    has_occurs = x.occurs != 1 or x.occurs_min is not None or x.depending
                    vals = F.item_values(
                        ln.line, x.level, x.name, x.pic, _DET_USAGE.get(u or "", u),
                        x.occurs_min if has_occurs else None, x.occurs if has_occurs else None,
                        x.depending, x.redefines, None,
                    )  # fmt: skip
                    if v is not None:
                        vals["value"] = f"L{ln.line} {x.name.upper()} = {v}"
                    F.merge_item(f, vals)

    # ---- the PROCEDURE DIVISION ----
    try:
        proc = ST.parse(lines)
    except Exception as e:  # noqa: BLE001 -- ExprError: the translator refuses the program
        proc = None
        errors.append(f"procedure: {type(e).__name__}: {str(e)[:160]}")
        out["failed"].append("procedure")
    if proc is not None:
        own = [ln for ln in lines if ln.file == progfile]
        pd_line = next((ln.line for ln in own if re.match(r"\s*PROCEDURE\s+DIVISION\b", ln.text, re.I)), None)

        def header_file(p: Any) -> Optional[str]:
            # the header's period may stand on the next line (`2000-SEND-MAP` / `.`, CardDemo COTRTLIC)
            pat = re.compile(rf"^\s*{re.escape(p.name)}(\s+SECTION)?\s*(\.|$)", re.I)
            hit = next((ln.file for ln in lines if ln.line == p.line and pat.match(ln.text)), None)
            return hit

        named = [(p, header_file(p)) for p in proc.paragraphs if p.name != "(MAIN)"]
        heads = sorted(p.line for p, hf in named if hf == progfile)
        # code lines of the source itself: a procedure-division COPY statement is code (its lines are replaced by
        # the member's in `lines`)
        own_lines = sorted({ln.line for ln in own} | {ln.line for ln in own_logical})

        def extent_end(start: int) -> int:
            nxt = next((h for h in heads if h > start), None)
            return max((n for n in own_lines if n >= start and (nxt is None or n < nxt)), default=start)

        own_text: dict[int, str] = {ln.line: ln.text.upper() for ln in own}

        def in_program(st: Any) -> bool:
            """A statement's line is a line of its file, which the translator does not keep: one from a procedure
            copybook (`COPY CSSETATY REPLACING ...` in a paragraph) carries the copybook's line. It is the
            program's own when the program's line of that number holds the statement's verb."""
            verb = (st.text.split() or [""])[0].upper()
            return verb in own_text.get(st.line, "")

        for p in proc.paragraphs:
            if p.name == "(MAIN)":
                if not p.body or pd_line is None:
                    continue
                uname, start = F.MAIN_LINE, pd_line
                first = heads[0] if heads else None
                f["unit_extents"].add(
                    f"{uname} L{start}-{max((n for n in own_lines if n >= start and (first is None or n < first)), default=start)}"
                )
            else:
                if header_file(p) != progfile:
                    continue  # a paragraph a procedure copybook brought in: not this source's unit
                uname = ak.keyed_unit_name(key_prog, p.name, p.line)
                f["units"].add(uname)
                f["unit_extents"].add(f"{uname} L{p.line}-{extent_end(p.line)}")
            for s in ST.walk(p.body):
                if s.kind == "PERFORM" and s.data.get("target") and not s.data.get("inline"):
                    # `PERFORM A THRU B` is one edge, to A (the key's shape; B is reached by fall-through)
                    f["edges"].add(F.edge_value(uname, "PERFORM", s.data["target"]))
                elif s.kind == "GOTO":
                    for t in s.data["targets"]:
                        f["edges"].add(F.edge_value(uname, "GO_TO", t))
                elif s.kind == "CALL":
                    f["calls"].add(F.call_value("CALL", "literal", s.data["program"]))
                elif s.kind == "HOLE" and s.data.get("why") == "dynamic CALL":
                    m = re.match(r"\s*CALL\s+([A-Z0-9-]+)", s.text, re.I)
                    if m:
                        f["calls"].add(F.call_value("CALL", "identifier", m.group(1)))
                elif s.kind == "MOVE" and in_program(s):
                    for t in s.data["to"]:
                        f["moves"].add(move_value(s.line, canon_operand(s.data["from"]), canon_operand(t)))
                elif s.kind == "EXEC" and re.match(r"\s*EXEC\s+CICS\b", s.text, re.I):
                    try:
                        words, opts = C.parse_exec(s.text)
                    except Exception:  # noqa: BLE001 -- an EXEC the translator cannot read names no command
                        continue
                    if not words:
                        continue
                    verb = words[0]
                    if in_program(s) and census_kind(words, opts):
                        f["cics_commands"].add(F.cics_command(s.line, verb))
                    if verb in ("LINK", "XCTL") and opts.get("PROGRAM"):
                        a = opts["PROGRAM"] or ""
                        lit = a[:1] in "'\""
                        f["calls"].add(
                            F.call_value(verb, "literal" if lit else "identifier", a if lit else canon_name(a))
                        )
                    if verb in F.CICS_FILE_VERBS:
                        a = opts.get("FILE") or opts.get("DATASET")
                        if a:
                            name = a.strip("'\"") if a[:1] in "'\"" else None
                            if name is None:
                                vals = values_of.get(canon_name(a).split(" OF ")[0], [])
                                name = vals[0] if len(set(vals)) == 1 else None
                            if name:
                                f["cics_files"].add(f"{verb} {name.strip().upper()}")
    if errors:
        out["status"] = "fail" if records is None and proc is None else "partial"
        out["error"] = "; ".join(errors)
    out["seconds"] = round(time.monotonic() - t0, 3)
    return out


_WEB_VERBS = frozenset({"OPEN", "CLOSE", "CONVERSE", "SEND", "RECEIVE", "READ", "WRITE"})  # not PARSE / EXTRACT
_TASK_VERBS = frozenset({"START", "RETRIEVE", "DELAY", "ENQ", "DEQ", "CANCEL", "RUN", "FETCH"})


def census_kind(words: list[str], opts: dict[str, Optional[str]]) -> Optional[str]:
    """The resource kind of an EXEC CICS command when it is one the keys census and the engine records
    (file control on a FILE / DATASET, BMS SEND / RECEIVE MAP, TS / TD queues, channels' containers, LINK /
    XCTL, task control, WEB); None for the rest (ASKTIME, RETURN, SEND TEXT, RECEIVE INTO, GET COUNTER ...),
    which neither censuses as a command."""
    verb = words[0] if words else ""
    if verb in F.CICS_FILE_VERBS and ("FILE" in opts or "DATASET" in opts):
        return "FILE"
    if verb in ("SEND", "RECEIVE") and "MAP" in opts:
        return "MAP"
    if verb in ("WRITEQ", "READQ", "DELETEQ"):
        return "QUEUE"
    if verb in ("GET", "PUT", "MOVE", "DELETE") and "CONTAINER" in opts:
        return "CONTAINER"
    if verb in ("LINK", "XCTL"):
        return "PROGRAM"
    if verb in _TASK_VERBS:
        return "TASK"
    if verb == "WEB" and len(words) > 1 and words[1] in _WEB_VERBS:
        return "WEB"
    return None


def translator_version() -> str:
    import subprocess

    r = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def translator_doc(root: Path, corpus: str, key: dict[str, Any], cache: Path,
                   case_dirs: Optional[dict[str, list[Path]]] = None, ir: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:  # fmt: skip
    """(the referee-facts/1 document over the key's programs and keyed copybooks, the per-program context
    (records) the cross-check's offsets channel needs). `case_dirs`: the copy directories a det-port case
    names for a program, used instead of the corpus-wide ones. `ir` (GalaxyIR of the scan, #4468): the translator
    takes each COPY's member from the engine's resolution, as det.program.translate does from the port ticket."""
    C, _, _, S, _ = det()
    doc = F.new_doc("translator", translator_version(), corpus, CHANNELS)
    ctx: dict[str, Any] = {}
    all_dirs = copy_dirs(root)
    extra = [bms_dir(root, cache), C.COPY]
    for rel in sorted(key.get("programs", {})):
        prog = root / rel
        dirs = [root / d for d in (case_dirs or {}).get(rel, [])] or nearest_first(prog, all_dirs)
        engine = S.engine_copies_from_ir(ir, rel, root) if ir is not None else None
        r = program_facts(root, prog, [*dirs, *extra], key["programs"][rel], engine)
        doc["files"][rel] = {"status": r["status"], "seconds": r["seconds"], "error": r["error"],
                             "failed": r["failed"], "facts": {ch: sorted(v) for ch, v in r["facts"].items()}}  # fmt: skip
        ctx[rel] = r
    for rel in sorted(key.get("copybook_layouts", {})):
        path = root / rel
        engine = S.engine_copies_from_ir(ir, rel, root) if ir is not None else None
        units, err = copybook_layouts(path, [*nearest_first(path, all_dirs), *extra], engine)
        doc["files"][rel] = {"status": "fail" if units is None else "ok", "seconds": None, "error": err,
                             "facts": {"layouts": sorted(units or [])}}  # fmt: skip
    return doc, ctx


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--cache",
        type=Path,
        default=Path(os.environ.get("REFEREES_CACHE", Path.home() / ".cache" / "gitgalaxy-referees")),
    )
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    doc, _ = translator_doc(args.root, args.corpus, key, args.cache)
    F.dump(doc, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
