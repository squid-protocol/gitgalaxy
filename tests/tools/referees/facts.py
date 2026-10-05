r"""Common fact format for the COBOL / CICS referee panel (#4377).

Every source of facts -- the engine (master DB via GalaxyIR), an independent open-source parser
(a "referee"), and the hand-verified answer key (ground truth) -- is reduced to the same shape:

    {
      "schema": "referee-facts/1",
      "source": "engine" | "key" | "<referee>",
      "version": "<commit / release the facts came from>",
      "corpus": "<corpus name from tests/cobol_mainframe/corpora.json>",
      "channels": [<channels this source can produce at all>],
      "files": {
        "<path relative to the corpus root>": {
          "status": "ok" | "partial" | "fail",   # clean parse / parsed with recovered errors / no facts
          "seconds": <wall time for this member, or null>,
          "error": <short message or null>,
          "facts": {"<channel>": ["<value>", ...], ...}
        }
      }
    }

A channel value is a canonical string, so that comparing two sources is plain set arithmetic. The
shapes follow the answer key's own score pairs (tests/tools/cobol_answer_key.py) wherever one
exists, so the engine-vs-key numbers here reproduce that tool's:

    program_ids   PROGRAM-ID
    units         paragraph / section name (`PROG:NAME` for a second program in a file)
    unit_extents  `NAME L<start>-<end>`, the main line as `(procedure division)`
    edges         `FROM -> PERFORM TARGET` / `FROM -> GO TO TARGET` (THRU scores as PERFORM)
    calls         `CALL 'LIT'` (static form) / `CALL IDENT` (dynamic form), also LINK / XCTL
    call_targets  the program a CALL / LINK / XCTL names, through a VALUE for an identifier
    copybooks     COPY / EXEC SQL INCLUDE member name
    data_items    `L<line> <level> NAME` of every data description in the program's own source
    pic, usage, occurs, redefines, value   `L<line> NAME <clause>` per item that carries it
    layouts       `ROOT/NAME @offset+bytes` per elementary PIC item of a copybook (#3602 contract)
    sql_access    `<read|insert|update|delete> TABLE`
    cics_commands `L<line> VERB` of an EXEC CICS command (scored over the verbs the key censuses)
    cics_files    `VERB DATASET` of an EXEC CICS file-control command, the name resolved
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional
from collections.abc import Iterable

SCHEMA = "referee-facts/1"

CHANNELS = (
    "program_ids",
    "units",
    "unit_extents",
    "edges",
    "calls",
    "call_targets",
    "copybooks",
    "data_items",
    "pic",
    "usage",
    "occurs",
    "redefines",
    "value",
    "layouts",
    "sql_access",
    "cics_commands",
    "cics_files",
)

# Channels whose universe of files is the key's copybook layouts rather than its programs.
COPYBOOK_CHANNELS = frozenset({"layouts"})
MAIN_LINE = "(procedure division)"
CICS_FILE_VERBS = frozenset({"READ", "WRITE", "REWRITE", "DELETE", "STARTBR", "READNEXT", "READPREV", "ENDBR", "RESETBR", "UNLOCK"})  # fmt: skip

_USAGE_ALIASES = {
    "COMPUTATIONAL": "COMP",
    "COMPUTATIONAL-1": "COMP-1",
    "COMPUTATIONAL-2": "COMP-2",
    "COMPUTATIONAL-3": "COMP-3",
    "COMPUTATIONAL-4": "COMP-4",
    "COMPUTATIONAL-5": "COMP-5",
    "PACKED-DECIMAL": "COMP-3",
    "COMP-4": "COMP",
    "BINARY": "COMP",
}
_FIGURATIVE = {
    "SPACE": "SPACES",
    "ZERO": "ZEROES",
    "ZEROS": "ZEROES",
    "HIGH-VALUE": "HIGH-VALUES",
    "LOW-VALUE": "LOW-VALUES",
    "QUOTE": "QUOTES",
}


def new_doc(source: str, version: str, corpus: str, channels: Iterable[str]) -> dict[str, Any]:
    return {"schema": SCHEMA, "source": source, "version": version, "corpus": corpus,
            "channels": sorted(channels), "files": {}}  # fmt: skip


def add_file(
    doc: dict[str, Any],
    rel: str,
    facts: dict[str, Iterable[str]],
    status: str = "ok",
    seconds: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    doc["files"][rel] = {
        "status": status,
        "seconds": seconds,
        "error": error,
        "facts": {ch: sorted(set(v)) for ch, v in facts.items() if ch in CHANNELS},
    }


def dump(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path}: not a {SCHEMA} document")
    return doc


# ------------------------------------------------------------------------------
# Canonical value builders, shared by every adapter so the shapes cannot drift.
# ------------------------------------------------------------------------------
def norm_usage(usage: Optional[str]) -> Optional[str]:
    if not usage:
        return None
    u = re.sub(r"\s+", " ", usage.upper().strip())
    return _USAGE_ALIASES.get(u, u)


def norm_value(value: Optional[str]) -> Optional[str]:
    """A VALUE clause's first literal: quotes dropped, figurative-constant synonyms folded,
    `ALL` kept, numerics as written."""
    if value is None:
        return None
    v = value.strip()
    if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
        v = v[1:-1]
    elif re.fullmatch(r"[+-]?[0-9.,]+", v):
        v = v.lstrip("+")  # the key reads `+12` as `12`
    v = v.upper().strip()  # the key folds case and trims a literal's blanks (definitional, #4377)
    return _FIGURATIVE.get(v, v)


def norm_pic(pic: Optional[str]) -> Optional[str]:
    return re.sub(r"\s+", "", pic.upper()) if pic else None


def item_values(
    line: int,
    level: int,
    name: str,
    pic: Optional[str] = None,
    usage: Optional[str] = None,
    occurs_min: Optional[int] = None,
    occurs_max: Optional[int] = None,
    depending_on: Optional[str] = None,
    redefines: Optional[str] = None,
    value: Optional[str] = None,
) -> dict[str, str]:
    """The per-item channel values of one data description entry."""
    name = (name or "FILLER").upper()
    out = {"data_items": f"L{line} {level:02d} {name}"}
    if pic:
        out["pic"] = f"L{line} {name} {norm_pic(pic)}"
    u = norm_usage(usage)
    if u and u != "DISPLAY":
        out["usage"] = f"L{line} {name} {u}"
    if occurs_max is not None:
        lo = occurs_min if occurs_min is not None else occurs_max
        # the key names the DEPENDING ON item unqualified (`X OF Y` -> `X`)
        dep = f" DEPENDING ON {depending_on.split()[0].upper()}" if depending_on else ""
        out["occurs"] = f"L{line} {name} {lo}..{occurs_max}{dep}"
    if redefines:
        out["redefines"] = f"L{line} {name} REDEFINES {redefines.upper()}"
    v = norm_value(value)
    if v is not None:
        out["value"] = f"L{line} {name} = {v}"
    return out


def merge_item(facts: dict[str, set[str]], values: dict[str, str]) -> None:
    for ch, v in values.items():
        facts.setdefault(ch, set()).add(v)


def call_value(verb: str, form: str, operand: Optional[str]) -> Optional[str]:
    if not operand:
        return None
    op = operand.strip().strip("'\"").strip().upper()  # CICS names are blank-padded literals
    return f"{verb.upper()} '{op}'" if form == "literal" else f"{verb.upper()} {op}"


def cics_verb(verb: str) -> str:
    """An EXEC CICS command's first word (`WEB OPEN` -> `WEB`, `START ATTACH` -> `START`)."""
    return verb.split()[0].upper() if verb.strip() else ""


def cics_command(line: int, verb: str) -> str:
    return f"L{line} {cics_verb(verb)}"


def edge_value(unit: str, verb: str, target: str) -> str:
    return f"{unit} -> {'GO TO' if verb in ('GO_TO', 'GO TO') else 'PERFORM'} {target.upper()}"


def unit_name(program_index: int, program_id: Optional[str], name: str) -> str:
    """#4206: a second or later program's units are `PROG:NAME`."""
    return f"{(program_id or '').upper()}:{name.upper()}" if program_index and name != MAIN_LINE else name.upper()


# ------------------------------------------------------------------------------
# The answer key as a fact source (ground truth).
# ------------------------------------------------------------------------------
def _key_blocks(prog: dict[str, Any]) -> list[tuple[Optional[str], dict[str, Any]]]:
    return [(None, prog), *prog.get("siblings", {}).items()]


def key_doc(key: dict[str, Any]) -> dict[str, Any]:
    """The answer key (tests/cobol_mainframe/answer_key/<corpus>.json) as a fact document."""
    doc = new_doc("key", key.get("ref", "")[:12], key["corpus"], CHANNELS)
    cics_ops: dict[str, list[dict[str, Any]]] = {}
    for rel, entry in key.get("cics_resources", {}).items():
        cics_ops.setdefault(rel, []).extend(entry.get("operations", []))
    tasks = {rel: entry.get("operations", []) for rel, entry in key.get("cics_tasks", {}).items()}
    sql = {rel: entry.get("accesses", []) for rel, entry in key.get("sql_access", {}).items()}
    for rel, prog in key.get("programs", {}).items():
        f: dict[str, set[str]] = {ch: set() for ch in CHANNELS if ch not in COPYBOOK_CHANNELS}
        for pid, block in _key_blocks(prog):
            f["program_ids"].add((block.get("program_id") or pid or "").upper())
            units = list(block.get("units", []))
            if block.get("main_line"):
                units.append({"name": MAIN_LINE, **block["main_line"]})
            for u in units:
                name = f"{pid}:{u['name']}" if pid and u["name"] != MAIN_LINE else u["name"]
                if u["name"] != MAIN_LINE:
                    name = name.upper()
                    f["units"].add(name)
                if u.get("end") is not None:
                    f["unit_extents"].add(f"{name} L{u['line']}-{u['end']}")
                for e in u.get("edges", []):
                    f["edges"].add(edge_value(name, e["verb"], e["target"]))
        f["program_ids"].discard("")
        for c in prog.get("calls", []):
            v = call_value(c["verb"], c.get("form", "literal"), c.get("operand"))
            if v:
                f["calls"].add(v)
            if c.get("target"):
                f["call_targets"].add(c["target"].upper())
            if c["verb"].upper() in ("LINK", "XCTL") and c.get("line"):
                f["cics_commands"].add(cics_command(c["line"], c["verb"]))
        f["copybooks"] = {c["name"].upper() for c in prog.get("copybooks", [])}
        for r in prog.get("records", []):
            merge_item(f, item_values(r["line"], r["level"], r["name"], r.get("pic"), r.get("usage"),
                                      r.get("occurs_min"), r.get("occurs_max"), r.get("occurs_depending_on"),
                                      r.get("redefines"), r.get("value")))  # fmt: skip
        f["sql_access"] = set(sql.get(rel, []))
        for op in cics_ops.get(rel, []):
            f["cics_commands"].add(cics_command(op["line"], op["verb"]))
            if op.get("kind") == "FILE" and op.get("name"):
                f["cics_files"].add(f"{cics_verb(op['verb'])} {op['name'].upper()}")
        for op in tasks.get(rel, []):
            f["cics_commands"].add(cics_command(op["line"], op["verb"]))
        add_file(doc, rel, f)
    for rel, entry in key.get("copybook_layouts", {}).items():
        add_file(doc, rel, {"layouts": entry.get("units", [])})
    return doc
