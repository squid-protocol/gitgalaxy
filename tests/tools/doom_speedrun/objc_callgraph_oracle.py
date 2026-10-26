#!/usr/bin/env python3
"""Objective-C / Objective-C++ call-graph body oracle for the licensed DOOM ports (#5639, extends #5630).

    python tests/tools/doom_speedrun/objc_callgraph_oracle.py --root REPO_DIR --db SCAN_MASTER_DB [--json OUT]

Independent of the engine's regexes: a tree-sitter ``objc`` parse finds, in each engine unit's body, every C call
(``call_expression``) and every message send (``message_expression``, selector = first keyword or the unary
selector). An oracle call counts when its name is a unit the port defines (bare name, case-sensitive); self-edges
are dropped on both sides (the engine drops recursion by contract, #3327). A unit tree-sitter cannot parse (an ERROR
node, or ObjC++ constructs the objc grammar lacks) is read by a text fallback over the unit's lines (comments and
literals blanked, ``name(`` and ``[recv sel`` forms) and counted separately. Licensed ports only (``LICENSED``).
Needs ``tree_sitter_language_pack`` (the selfscan venv has it).
"""

import argparse
import collections
import functools
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(
    0, str(HERE.parents[2])
)  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import doom_scorer  # noqa: E402

LICENSED = frozenset("chocolate-doom prboom-plus eternity gzdoom".split())
UNIT_NODES = {"method_definition", "function_definition"}
STRIP = re.compile(r"/\*.*?\*/|//[^\n]*|@?\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.S)
TEXT_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
TEXT_SEND = re.compile(r"\[\s*[^\[\];]+?\s+([A-Za-z_]\w*)\s*[:\]]")
KEYWORDS = frozenset("if else while for do switch return sizeof defined case goto typeof".split())


@functools.cache
def _parser():
    import tree_sitter_language_pack

    return tree_sitter_language_pack.get_parser("objc")


def _has_error(node):
    return node.type == "ERROR" or node.is_missing or any(_has_error(c) for c in node.children)


def tree_calls(node, text):
    """Names called inside ``node``: C calls by callee identifier, message sends by selector."""
    out = {}
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "call_expression":
            fn = n.children[0] if n.children else None
            if fn is not None and fn.type == "identifier":
                out.setdefault(text[fn.start_byte : fn.end_byte].decode("utf-8", "replace"), "c-call")
        elif n.type == "message_expression" and len(n.children) > 2:
            sel = n.children[2]
            if sel.type == "identifier":
                out.setdefault(text[sel.start_byte : sel.end_byte].decode("utf-8", "replace"), "send")
        stack.extend(n.children)
    return out


def text_calls(lines):
    body = STRIP.sub(lambda m: " " * len(m.group(0)), "\n".join(lines))
    out = {}
    for m in TEXT_CALL.finditer(body):
        if m.group(1) not in KEYWORDS:
            out.setdefault(m.group(1), "c-call")
    for m in TEXT_SEND.finditer(body):
        out.setdefault(m.group(1), "send")
    return out


def unit_index(tree):
    """start line (1-based) -> the method/function definition node that starts there (outermost first)."""
    idx = {}
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        if n.type in UNIT_NODES:
            idx.setdefault(n.start_point[0] + 1, n)
        stack.extend(n.children)
    return idx


def score(root, db, port="", vendored=None):
    """Recall/precision of ``calls_out_to`` on Objective-C units; ``vendored`` (a relpath -> bool test) drops vendored code (#6097)."""
    root = Path(root)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "select f.file_path, fn.func_name, fn.start_line, fn.loc, fn.calls_out_to from function_data fn "
        "join file_data f on f.id = fn.file_id where f.language = 'objective-c' order by f.file_path, fn.start_line"
    ).fetchall()
    if vendored:
        rows = [
            r for r in rows if not vendored(r[0][len(str(root)) + 1 :] if r[0].startswith(str(root) + "/") else r[0])
        ]
    defined = {r[1].split(".")[-1] for r in rows}
    files = {}
    tot_o = tot_hit = tot_e = tot_x = 0
    by_how = collections.Counter()
    misses = []
    for path, name, start, loc, calls in rows:
        rel = path[len(str(root)) + 1 :] if path.startswith(str(root) + "/") else path
        if rel not in files:
            raw = (root / rel).read_bytes() if (root / rel).is_file() else b""
            files[rel] = (raw, unit_index(_parser().parse(raw)), raw.decode("utf-8", "replace").split("\n"))
        raw, idx, lines = files[rel]
        node = idx.get(start)
        if node is not None and not _has_error(node):
            oracle, how = tree_calls(node, raw), "tree-sitter"
        else:
            oracle, how = text_calls(lines[start : start + max(loc, 1) - 1]), "text-fallback"
        me = name.split(".")[-1]
        want = {k for k in oracle if k in defined and k != me}
        got = {k.split(".")[-1] for k in json.loads(calls or "[]")} & defined
        got.discard(me)
        hit = want & got
        tot_o += len(want)
        tot_hit += len(hit)
        tot_e += len(got)
        tot_x += len(got - want)
        by_how[how] += len(want)
        for k in sorted(want - got):
            misses.append((rel, start, name, k, oracle[k], how))
    return {
        "port": port,
        "units": len(rows),
        "oracle_calls": tot_o,
        "found": tot_hit,
        "recall": round(tot_hit / tot_o, 3) if tot_o else None,
        "engine_edges": tot_e,
        "engine_only": tot_x,
        "precision": round(tot_hit / tot_e, 3) if tot_e else None,
        "oracle_calls_by_reader": dict(by_how),
        "misses": misses,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True, type=Path, help="the port's clone")
    ap.add_argument("--db", required=True, type=Path, help="the scan's *_master.db")
    ap.add_argument("--json", type=Path, help="write the result here")
    ap.add_argument("--misses", type=int, default=10, help="misses to print")
    args = ap.parse_args(argv)
    port = args.root.name
    if port not in LICENSED:
        print(f"refusing {port}: not a licensed port", file=sys.stderr)
        return 2
    res = score(args.root, args.db, port, doom_scorer._engine_vendor_test(args.root))
    print({k: v for k, v in res.items() if k != "misses"})
    for m in res["misses"][: args.misses]:
        print("  miss", *m)
    if args.json:
        args.json.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
