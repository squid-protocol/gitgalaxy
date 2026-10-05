r"""Spantree tree-sitter-cobol-enterprise referee (#4377): units, extents, PERFORM / GO TO edges,
CALL / LINK / XCTL, COPY, data items, typed EXEC CICS and EXEC SQL, as a referee-facts/1 document.

    python tests/tools/referees/treesitter_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/tree-sitter-cobol-enterprise.json

Needs py-tree-sitter (>= 0.22) and the grammar compiled to a shared library named by the
environment variable TS_COBOL_ENTERPRISE_LIB (README.md: `tree-sitter generate` + `cc -shared`).

The grammar does the parsing; this adapter only walks its tree. Two readings are the adapter's
own and are kept minimal: an identifier operand of LINK / XCTL / CALL / FILE(...) is resolved
through the single VALUE the grammar parsed on that data item (as the key and the engine do), and
an SQL statement's table names are read from the typed sql_* node's text. A member whose tree
has ERROR / MISSING nodes is `partial`: tree-sitter recovers, and the facts outside the damaged
region still count.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Optional
from collections.abc import Iterator

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

LIB_ENV = "TS_COBOL_ENTERPRISE_LIB"
NAME_TYPES = ("WORD", "numeric_name")
HEADER_TYPES = ("paragraph", "section")
_SQL_TABLE = re.compile(r"\b(FROM|JOIN|INTO|UPDATE)\s+([A-Z0-9_#@$]+(?:\.[A-Z0-9_#@$]+)?)", re.I)
_SQL_ACCESS = {"sql_select": "read", "sql_declare_cursor": "read", "sql_insert": "insert",
               "sql_update": "update", "sql_delete_sql": "delete"}  # fmt: skip


def load_language() -> Any:
    from tree_sitter import Language

    lib_path = os.environ.get(LIB_ENV)
    if not lib_path:
        raise SystemExit(f"{LIB_ENV} is not set (see tests/tools/referees/README.md)")
    lib = ctypes.cdll.LoadLibrary(lib_path)
    fn = lib.tree_sitter_cobol
    fn.restype = ctypes.c_void_p
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return Language(fn())


def grammar_version(lib_path: str) -> str:
    repo = os.environ.get("TS_COBOL_ENTERPRISE_REPO")
    if repo:
        out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo, capture_output=True, text=True)
        if out.stdout.strip():
            return out.stdout.strip()
    return Path(lib_path).name


def text(node: Any) -> str:
    return node.text.decode("latin-1")


def line(node: Any) -> int:
    return int(node.start_point[0]) + 1


def end_line(node: Any) -> int:
    row, col = node.end_point
    return int(row) + (1 if col else 0)


def walk(node: Any, types: tuple[str, ...], stop: tuple[str, ...] = ("program_definition",)) -> Iterator[Any]:
    """Descendants of `node` of the given types, not entering a nested program."""
    for c in node.children:
        if c.type in types:
            yield c
        if c.type not in stop:
            yield from walk(c, types, stop)


def first_name(node: Any) -> Optional[str]:
    for c in node.children:
        if c.type in NAME_TYPES or c.type == "string_literal":
            return text(c).strip("'\"").upper()
    return None


def has_error(node: Any) -> bool:
    return bool(node.has_error)


def _option(cmd: Any, name: str) -> Optional[Any]:
    for opt in cmd.children:
        if opt.type == "cics_option" and opt.children and text(opt.children[0]).upper() == name:
            vals = [c for c in opt.children[1:] if c.type not in ("(", ")")]
            return vals[0] if vals else None
    return None


# The key censuses SEND / RECEIVE of a BMS MAP and GET / PUT of a CONTAINER; any other form of
# those verbs (SEND TEXT, RECEIVE into a terminal buffer, GET COUNTER) is named apart so that the
# verb filter in score.py leaves it out (likewise DELETE COUNTER) instead of scoring it as a false positive.
_QUALIFIED = {"SEND": "MAP", "RECEIVE": "MAP", "GET": "CONTAINER", "PUT": "CONTAINER", "DELETE": "FILE|DATASET"}


def cics_verb(cmd: Any) -> str:
    if cmd.type == "cics_generic":
        words = text(cmd).split()
        verb = words[0].upper() if words else ""
    else:
        verb = cmd.type.removeprefix("cics_").split("_")[0].upper()
    if verb in _QUALIFIED and not re.search(rf"\b({_QUALIFIED[verb]})\b", text(cmd), re.I):
        return f"{verb}-{cmd.type.removeprefix('cics_').upper() if cmd.type != 'cics_generic' else 'OTHER'}"
    return verb


class Program:
    """One program_definition: its facts, read from the tree."""

    def __init__(self, node: Any, index: int) -> None:
        self.node = node
        self.index = index
        pid = next(walk(node, ("program_id_paragraph",)), None)
        self.program_id = first_name(pid) if pid is not None else None
        self.values: dict[str, str] = {}

    def data_items(self, facts: dict[str, set[str]]) -> None:
        for dd in walk(self.node, ("data_description",)):
            kids = {c.type: c for c in dd.children}
            lvl = kids.get("level_number")
            if lvl is None or not text(lvl).isdigit():
                continue
            name = text(kids["entry_name"]).upper() if "entry_name" in kids else "FILLER"
            pic = None
            if "picture_clause" in kids:
                ps = [c for c in kids["picture_clause"].children if c.type == "pic_string"]
                pic = text(ps[0]) if ps else None
            usage = None
            if "usage_clause" in kids:
                usage = re.sub(r"^USAGE\s+(IS\s+)?", "", text(kids["usage_clause"]).upper()).strip()
            omin = omax = None
            dep = None
            if "occurs_clause" in kids:
                o = text(kids["occurs_clause"]).upper()
                nums = [int(n) for n in re.findall(r"\b(\d+)\b", o.split("DEPENDING")[0])]
                if nums:
                    omin, omax = (nums[0], nums[1]) if " TO " in o and len(nums) > 1 else (nums[0], nums[0])
                m = re.search(r"DEPENDING\s+(?:ON\s+)?([A-Z0-9-]+)", o)
                dep = m.group(1) if m else None
            red = first_name(kids["redefines_clause"]) if "redefines_clause" in kids else None
            value = None
            if "value_clause" in kids:
                vals = [c for c in kids["value_clause"].children if c.is_named]
                value = text(vals[0]) if vals else re.sub(r"^VALUES?\s+(IS\s+|ARE\s+)?", "", text(kids["value_clause"]), flags=re.I)  # fmt: skip
                if value and value[:1] in "'\"" and name != "FILLER":
                    self.values[name] = value.strip("'\"").strip().upper()
            F.merge_item(facts, F.item_values(line(dd), int(text(lvl)), name, pic, usage, omin, omax, dep, red, value))

    def resolve(self, operand: Any) -> Optional[str]:
        if operand is None:
            return None
        if operand.type == "string_literal":
            return text(operand).strip("'\"").strip().upper()
        return self.values.get(text(operand).upper())

    def procedure(self, facts: dict[str, set[str]]) -> None:
        proc = next(walk(self.node, ("procedure_division",)), None)
        if proc is None:
            return
        items: list[tuple[str, Any]] = []

        def flatten(n: Any) -> None:
            for c in n.children:
                if c.type in HEADER_TYPES:
                    items.append(("header", c))
                    flatten(c)
                elif c.type == "sentence" or (c.is_named and c.type.endswith("_statement")):
                    items.append(("code", c))

        flatten(proc)
        current = F.MAIN_LINE
        start, last = line(proc), None
        spans: list[tuple[str, int, Optional[int]]] = []
        for kind, n in items:
            if kind == "header":
                spans.append((current, start, last))
                current = F.unit_name(self.index, self.program_id, first_name(n) or "?")
                facts["units"].add(current)
                start, last = line(n), line(n)
                continue
            last = max(last or 0, end_line(n))
            for st in walk(n, ("perform_statement", "go_to_statement")):
                if st.type == "perform_statement":
                    tgt = first_name(st)
                    if tgt:
                        facts["edges"].add(F.edge_value(current, "PERFORM", tgt))
                else:
                    for c in st.children:
                        if c.type in NAME_TYPES:
                            facts["edges"].add(F.edge_value(current, "GO_TO", text(c)))
                        elif c.type not in ("GO", "TO") and not c.is_named and text(c).upper() == "DEPENDING":
                            break
        spans.append((current, start, last))
        for name, s, e in spans:
            if e is not None and not (name == F.MAIN_LINE and e < s):
                facts["unit_extents"].add(f"{name} L{s}-{e}")

    def calls_and_exec(self, facts: dict[str, set[str]]) -> None:
        for st in walk(self.node, ("call_statement",)):
            ops = [c for c in st.children if c.is_named]
            if not ops:
                continue
            op = ops[0]
            form = "literal" if op.type == "string_literal" else "identifier"
            v = F.call_value("CALL", form, text(op))
            if v:
                facts["calls"].add(v)
            tgt = self.resolve(op)
            if tgt:
                facts["call_targets"].add(tgt)
        for st in walk(self.node, ("copy_statement", "sql_include")):
            name = first_name(st)
            if name is None and st.type == "sql_include":
                m = re.search(r"INCLUDE\s+([A-Z0-9#@$-]+)", text(st), re.I)
                name = m.group(1).upper() if m else None
            if name:
                facts["copybooks"].add(name)
        for ex in walk(self.node, ("exec_cics_statement",)):
            cmds = [c for c in ex.children if c.is_named and c.type.startswith("cics_")]
            if not cmds:
                continue
            cmd = cmds[0]
            verb = cics_verb(cmd)
            facts["cics_commands"].add(f"L{line(ex)} {verb}")
            if verb in ("LINK", "XCTL"):
                op = _option(cmd, "PROGRAM")
                if op is not None:
                    form = "literal" if op.type == "string_literal" else "identifier"
                    v = F.call_value(verb, form, text(op))
                    if v:
                        facts["calls"].add(v)
                    tgt = self.resolve(op)
                    if tgt:
                        facts["call_targets"].add(tgt)
            if verb in F.CICS_FILE_VERBS:
                ds = self.resolve(_option(cmd, "FILE") or _option(cmd, "DATASET"))
                if ds:
                    facts["cics_files"].add(f"{verb} {ds}")
        for ex in walk(self.node, ("exec_sql_statement",)):
            for st in ex.children:
                access = _SQL_ACCESS.get(st.type)
                if access is None:
                    continue
                for kw, table in _SQL_TABLE.findall(text(st)):
                    kw = kw.upper()
                    if (access == "read" and kw in ("FROM", "JOIN")) or (access == "insert" and kw == "INTO") or \
                       (access == "update" and kw == "UPDATE") or (access == "delete" and kw == "FROM"):  # fmt: skip
                        facts["sql_access"].add(f"{access} {table.upper()}")


def file_facts(parser: Any, path: Path) -> tuple[str, dict[str, set[str]], Optional[str]]:
    tree = parser.parse(path.read_bytes())
    root = tree.root_node
    facts: dict[str, set[str]] = {ch: set() for ch in F.CHANNELS if ch not in F.COPYBOOK_CHANNELS}
    progs = list(walk(root, ("program_definition",), stop=()))
    if not progs:
        return "fail", {}, "no program_definition in the tree"
    for i, node in enumerate(progs):
        p = Program(node, i)
        if p.program_id:
            facts["program_ids"].add(p.program_id)
        p.data_items(facts)
        p.procedure(facts)
        p.calls_and_exec(facts)
    if not facts["program_ids"]:
        return "fail", {}, "no PROGRAM-ID in the tree"
    errors = sum(1 for _ in walk(root, ("ERROR",), stop=())) + (1 if root.has_error else 0)
    return ("partial" if root.has_error else "ok"), facts, (f"{errors} ERROR/MISSING region(s)" if errors else None)


def treesitter_doc(corpus: str, root: Path, key: dict[str, Any]) -> dict[str, Any]:
    from tree_sitter import Parser

    parser = Parser(load_language())
    channels = [ch for ch in F.CHANNELS if ch not in F.COPYBOOK_CHANNELS]
    doc = F.new_doc("tree-sitter-cobol-enterprise", grammar_version(os.environ[LIB_ENV]), corpus, channels)
    for rel in sorted(key.get("programs", {})):
        t0 = time.perf_counter()
        try:
            status, facts, err = file_facts(parser, root / rel)
        except Exception as e:
            status, facts, err = "fail", {}, f"{type(e).__name__}: {e}"
        F.add_file(doc, rel, facts, status=status, seconds=time.perf_counter() - t0, error=err)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(treesitter_doc(args.corpus, args.root, key), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
