"""
Call-graph accuracy, Level 1: callee-name extraction (#3332, Epic #3265 step 5).

Precision and recall of the engine's per-function `calls_out_to` against
tree-sitter call nodes, on language-crucible, per language.

WHAT IS COMPARED
  For every function both sides find (same file, same name, start lines within
  a few lines of each other), the SET of callee names:
    engine: function_data.calls_out_to, from one in-process scan of the crucible
            with THIS checkout's engine;
    tree-sitter: every call node inside the function, attributed to its
            INNERMOST enclosing function, named by its callee's rightmost
            identifier (`a.b.save()` -> `save`, `new Foo()` -> `Foo`,
            `Store::make()` -> `make`, `println!()` -> `println`).
  Both sides follow the #3327 contract: names are deduplicated, and the
  function's own name is dropped (recursion). Built-ins count as calls on both
  sides (#3361 removed the engine's built-in filter).
  Keyword captures (#3359) and nested-declaration captures (#3360) show up as
  lost precision. Function detection is NOT scored here: a function only one
  side finds is skipped. tree_sitter_accuracy_audit.py scores that.

  Tree-sitter works at the same unresolved-name level as calls_out, so this is
  a like-for-like comparison. It is NOT a resolution benchmark; that is Level 2
  (call_graph_resolution.py). Disagreements are leads, to be checked against
  source (CLAUDE.md's comparative-correctness rule), not verdicts.

    python tests/tools/call_graph_accuracy.py                # report
    python tests/tools/call_graph_accuracy.py --samples 8    # + top FP/FN names
    python tests/tools/call_graph_accuracy.py --buckets 3    # + FP/FN by CAUSE, 3 examples each
    python tests/tools/call_graph_accuracy.py --ledger       # merge the shapes into the ledger

RECONCILED, NOT GRADED (#3641)
  Like the structural tri-comparison (docs/self_scan/tri_comparison_README.md), a
  disagreement is a discrepancy until someone reads the source. `--buckets` groups each
  one into a SHAPE (language / `call` / cause label / which reader claims it), and
  `--ledger` merges the shapes into docs/self_scan/graph_comparison_ledger.json through
  tri_comparison_ledger.py -- the same module, schema and lifecycle, a separate file. A
  validated entry moves the VALIDATED numbers with the ledger's own credit geometry:
    agree[gitgalaxy]   credit gitgalaxy   -> GitGalaxy was right  (FP becomes TP)
                       no credit          -> GitGalaxy was wrong  (stays FP)
    agree[tree_sitter] credit tree_sitter -> GitGalaxy missed it  (stays FN)
                       no credit          -> tree-sitter was wrong (leaves FN)
  With two readers there is no consensus, so an unvalidated shape counts exactly as it
  does raw: the validated numbers only ever move on a recorded verdict. The --ci gate
  stays on the raw numbers.
    python tests/tools/call_graph_accuracy.py --ci           # gate vs the baseline
    python tests/tools/call_graph_accuracy.py --regenerate   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
BASELINE = REPO_ROOT / "tests" / "call_graph_accuracy_baseline.json"
sys.path.insert(0, str(TOOLS))
import graph_ledger as gl  # noqa: E402

LEDGER = gl.LEDGER

# The languages #3329 scoped for qualifier capture, plus C and Rust: the
# C-style invocation family where tree-sitter's call node is unambiguous.
LANGS = (
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "c",
    "cpp",
    "csharp",
    "php",
    "ruby",
    "rust",
    "kotlin",
    "scala",
    "swift",
    "lua",
    "zig",
    "dart",
    "haskell",
    "perl",
    "solidity",
    "apex",
    "powershell",
    "tcl",
)

CALL_NODE_TYPES = frozenset(
    {
        "call",  # python, ruby
        "call_expression",  # js/ts, c/cpp, go, rust, kotlin, scala, swift
        "new_expression",  # js/ts constructor
        "method_invocation",  # java
        "object_creation_expression",  # java, c#, php
        "invocation_expression",  # c#
        "function_call_expression",  # php
        "member_call_expression",  # php
        "nullsafe_member_call_expression",  # php
        "scoped_call_expression",  # php
        "macro_invocation",  # rust
        "function_call",  # lua
        "instance_expression",  # scala `new Foo(1)`
        "method_call_expression",  # perl `$o->meth(1)`
        "ambiguous_function_call_expression",  # perl `print "x"`, `save $x`
        "func1op_call_expression",  # perl unary built-ins: `shift`, `defined $x`
        "apply",  # haskell `f x y` (curried: the outer applies share the leftmost callee)
        "infix",  # haskell `f $ x` (any other operator is no call)
        "FnCallArguments",  # zig: the callee is the sibling before the argument list
        "argument_part",  # dart: the argument list of `f(x)`, `a.f(x)`, `a?.f(x)`, `a..f(x)`
        "const_object_expression",  # dart `const Foo(1)`
        "type_conversion_expression",  # go `[]byte(s)` -- a conversion is a call (C3)
        "command",  # powershell `Get-Item $x`, tcl `puts $x`
        "invokation_expression",  # powershell `$o.Save(1)`, `[Foo]::Make(2)`
    }
)
_CALLEE_FIELDS = ("function", "method", "name", "macro", "constructor", "type")
_MEMBER_FIELDS = ("property", "field", "name", "attribute", "method", "suffix")
_LEAF_SUFFIXES = ("identifier", "constant")
_QUALIFIED_TYPES = frozenset({"scoped_identifier", "qualified_identifier", "scoped_type_identifier"})
_LINE_SLACK = 3  # decorators/annotations/doc comments can move a start line

# #3359: names tree-sitter parses as a call node but the #3327 contract says are
# keywords, never calls (C2) -- language constructs and operator keywords the
# engine's `_calls_out_ignore` now drops. Removed from the tree-sitter side so
# both sides score the same contract instead of the engine losing "recall" for
# following it. Built-ins are NOT here: they are calls (decision 1, #3361).
CONTRACT_NON_CALLS: dict[str, frozenset[str]] = {
    "php": frozenset({"isset", "empty", "unset", "die", "exit", "array", "list"}),
    "csharp": frozenset({"nameof"}),
}

# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5


# ----------------------------------------------------------------------------- tree-sitter side


def _leaf_name(node: Any, depth: int = 0) -> str | None:
    """The rightmost identifier a callee expression names."""
    if node is None or depth > 8:
        return None
    if node.type == "generic_function":  # rust `collect::<Vec<_>>()`: the function, not the type
        return _leaf_name(node.child_by_field_name("function"), depth + 1)
    if node.type in ("generic_name", "generic_type"):  # c# `OfType<T>()`, java `new HashMap<K, V>()`
        return _leaf_name(node.named_children[0], depth + 1) if node.named_children else None
    if node.type == "stable_type_identifier" and node.named_children:  # scala `new util.HashSet[T]()`
        return _leaf_name(node.named_children[-1], depth + 1)
    if node.type in _QUALIFIED_TYPES:  # `ControlFlow::Continue`, `OS::get_singleton`
        child = node.child_by_field_name("name")
        return _leaf_name(child, depth + 1) if child is not None else None
    # solidity `t.call{value: v}(d)` names the call, not `value`
    if node.type == "struct_expression" and node.named_children:
        return _leaf_name(node.named_children[0], depth + 1)
    if node.type in ("function", "method") and not node.named_children:  # perl `Foo::bar` -> `bar`
        return node.text.decode("utf-8", "replace").rsplit("::", 1)[-1]
    if node.type.endswith(_LEAF_SUFFIXES) or node.type == "name":
        return node.text.decode("utf-8", "replace")
    for field in _MEMBER_FIELDS:
        child = node.child_by_field_name(field)
        if child is not None:
            return _leaf_name(child, depth + 1)
    for child in reversed(node.named_children):
        got = _leaf_name(child, depth + 1)
        if got:
            return got
    return None


def _is_subscript(node: Any) -> bool:
    """swift parses `headers["k"]` as a call whose argument list opens with `[`: an index is no call (C3)."""
    suffix = next((c for c in node.named_children if c.type == "call_suffix"), None)
    args = suffix.named_children[0] if suffix is not None and suffix.named_children else None
    return args is not None and args.type == "value_arguments" and args.children[0].type == "["


def _hs_callee(node: Any) -> str | None:
    """haskell `f x y` is apply(apply(f, x), y): the callee is the leftmost function of the chain.
    `f $ x` applies its left operand, so a `$` infix is a call too."""
    if node.type == "infix":
        op = node.child_by_field_name("operator")
        if op is None or op.text != b"$":
            return None
        fn = node.child_by_field_name("left_operand")
    else:
        fn = node.child_by_field_name("function")
    for _ in range(64):
        if fn is None or fn.type != "apply":
            break
        fn = fn.child_by_field_name("function")
    if fn is not None and fn.type == "qualified":  # `Map.insert`: the id after the module
        fn = fn.child_by_field_name("id")
    return fn.text.decode("utf-8", "replace") if fn is not None and fn.type in ("variable", "constructor") else None


_HS_PATTERN_SPINE = frozenset({"apply", "parens", "infix", "tuple", "list", "as_pattern", "irrefutable"})


def _hs_is_pattern(node: Any) -> bool:
    """haskell `isPara (Para _) = True`, `Left e -> ..`, `\\(Just x) -> ..`: tree-sitter parses a constructor
    pattern as an `apply`, but a pattern is no call (C3). True when `node` sits in a pattern position."""
    cur = node
    while cur.parent is not None:
        par = cur.parent
        if par.type == "patterns":
            return True
        pat = par.child_by_field_name("pattern")
        if pat is not None and pat.id == cur.id:
            return True
        if par.type not in _HS_PATTERN_SPINE:
            return False
        cur = par
    return False


def _dart_callee(node: Any) -> str | None:
    """dart has no call node: `a.b.save(x)` is identifier, selector(.b), selector(.save), selector(argument_part).

    The call is the `argument_part`; its callee is the name just before it: the identifier, or the
    selector (`.save`, `?.save`) or cascade selector (`..save`) holding one.
    """
    if node.type != "argument_part":
        # `const Foo(1)` opens with a `const_builtin` token; `const Foo.named(1)` names `named` (the
        # rightmost identifier, as for `a.b.save()`): the callee is the last name before `arguments` (#6454)
        named = [c for c in node.named_children if c.type in ("identifier", "type_identifier")]
        return _leaf_name(named[-1]) if named else None
    parent = node.parent
    prev = parent.prev_named_sibling if parent is not None and parent.type == "selector" else node.prev_named_sibling
    if prev is None:
        return None
    if prev.type == "identifier":
        return prev.text.decode("utf-8", "replace")
    holder = prev.named_children[0] if prev.type == "selector" and prev.named_children else prev
    ident = next((c for c in holder.named_children if c.type == "identifier"), None)
    return ident.text.decode("utf-8", "replace") if ident is not None else None


def _ps_tcl_callee(node: Any) -> str | None:
    """powershell and tcl `command` nodes and powershell `invokation_expression`.

    powershell: the callee is the `command_name` field when it is a plain `command_name` token; a
    `command_name_expr` (`& $g`, `. ./a.ps1`) is dynamic or dot-sourcing, no named call. A method call
    names the `member_name` (`$o.Save(1)`, `[Foo]::Make(2)`); a property read has no `argument_list`.
    tcl: the callee is the first word (`name` field); `ns::k` names its rightmost segment, as the engine does.
    """
    if node.type == "invokation_expression":
        member = next((c for c in node.named_children if c.type == "member_name"), None)
        has_args = any(c.type == "argument_list" for c in node.named_children)
        return member.text.decode("utf-8", "replace") if member is not None and has_args else None
    name = node.child_by_field_name("name")
    if name is not None:  # tcl
        return name.text.decode("utf-8", "replace").rsplit("::", 1)[-1] if name.type == "simple_word" else None
    cname = node.child_by_field_name("command_name")
    if cname is not None and cname.type == "command_name":
        return cname.text.decode("utf-8", "replace")
    return None


def _callee(node: Any) -> str | None:
    if node.type in ("command", "invokation_expression"):
        return _ps_tcl_callee(node)
    if node.type in ("apply", "infix"):
        return _hs_callee(node)
    if node.type == "func1op_call_expression":  # perl `shift`, `defined $x`: the built-in is the first token
        return node.children[0].text.decode("utf-8", "replace") if node.children else None
    if node.type == "FnCallArguments":
        prev = node.prev_named_sibling
        # the engine names a builtin without its sigil: `@intCast(x)` -> `intCast`
        return (
            prev.text.decode("utf-8", "replace").lstrip("@")
            if prev is not None and prev.type.endswith("IDENTIFIER")
            else None
        )
    if node.type in ("argument_part", "const_object_expression") or (
        node.type == "new_expression" and node.child_by_field_name("constructor") is None
    ):
        return _dart_callee(node)  # js `new Foo()` has a `constructor` field; dart's does not
    if _is_subscript(node):
        return None
    for field in _CALLEE_FIELDS:
        child = node.child_by_field_name(field)
        if child is not None:
            return _leaf_name(child)
    if node.type in ("call_expression", "instance_expression") and node.named_children:
        # kotlin, swift `f(x)` and scala `new Foo(x)` carry no callee field: the callee comes first
        return _leaf_name(node.named_children[0])
    if node.type == "object_creation_expression":  # php: `new Foo(...)` has no field
        for child in node.named_children:
            if child.type in ("name", "qualified_name"):
                return _leaf_name(child)
    return None


_UNIT_NAME_SEPARATORS = ("::", ".", "->")


def _is_own_leaf_call(node: Any, callee: str, owner: str) -> bool:
    """#3644: is this call recursion on a qualified unit (`Class::method` calling `method(`)?

    `_pair` drops the unit's own name, but a C++ out-of-class unit is named
    `Class::method` while its recursive call names the bare `method`. Mirrors the
    engine: the leaf is dropped when the call is bare, `this->`/`self.`-qualified
    or qualified by the unit's own class; `child->method(` is another object's
    method and stays a call.
    """
    parts = [owner]
    for sep in _UNIT_NAME_SEPARATORS:
        parts = [p for part in parts for p in part.split(sep)]
    if len(parts) < 2 or callee != parts[-1]:
        return False
    fn = node.child_by_field_name("function")
    if fn is None or fn.type == "identifier":
        return True
    if fn.type in ("field_expression", "member_expression", "attribute"):
        recv = fn.child_by_field_name("argument") or fn.child_by_field_name("object")
        return recv is not None and recv.type in ("this", "self")
    if fn.type == "qualified_identifier":
        scope = fn.child_by_field_name("scope")
        return scope is not None and scope.text.decode("utf-8", "replace") in parts[:-1]
    return False


_KEEP_TREE: list[Any] = [None]


def _body_of(node: Any) -> Any:
    """zig `FnProto` and dart `*_signature` hold no body: it is the next sibling (dart: of the wrapper)."""
    if node.type == "FnProto":
        nxt = node.next_named_sibling
        return nxt if nxt is not None and nxt.type == "Block" else None
    if node.type.endswith("_signature") or node.type == "local_function_declaration":
        top = node
        while top.parent is not None and top.parent.type.endswith("_signature"):
            top = top.parent  # method_signature wraps function_signature
        nxt = top.next_named_sibling
        return nxt if nxt is not None and nxt.type == "function_body" else None
    return None


def _bodies_of(node: Any) -> list[Any]:
    """Every subtree that belongs to `node`'s unit: its body, plus a dart constructor's initializer list (#6454).

    The dart grammar puts `initializers` beside `constructor_signature`, not inside it, so
    `: x = x ?? const Foo(), y = bar()` is outside the signature and the body: the call there
    would otherwise read as a not-a-call (the callee's first textual occurrence is its parameter type).
    """
    bodies = []
    if node.type == "constructor_signature":
        nxt = node.next_named_sibling
        if nxt is not None and nxt.type == "initializers":
            bodies.append(nxt)
    body = _body_of(node)
    if body is not None:
        bodies.append(body)
    return bodies


def ts_functions(source: bytes, lang: str, audit: Any) -> list[tuple[str, int, set[str], Any]]:
    """(name, start_line, callee names, node) for every function tree-sitter finds."""
    import tree_sitter_language_pack

    spec = audit.NODE_MAPS[lang]
    tree = tree_sitter_language_pack.get_parser(spec["ts_lang"]).parse(source)
    _KEEP_TREE[0] = tree  # the returned nodes are only valid while their tree lives
    func_types = spec["func_node_types"]
    non_calls = CONTRACT_NON_CALLS.get(lang, frozenset())
    out: list[tuple[str, int, set[str], Any]] = []
    stack: list[tuple[Any, list[tuple[str, set[str]]]]] = [(tree.root_node, [])]
    # iterative walk; `owners` is the chain of enclosing function call-sets
    body_owners: dict[int, list[tuple[str, set[str]]]] = {}
    while stack:
        node, owners = stack.pop()
        owners = body_owners.pop(node.id, owners)
        if node.type in func_types:
            name = audit._get_node_name(node)
            # C8 (#3641): an anonymous function is no unit of its own -- its calls stay with the
            # enclosing named unit. Only a named function starts a new owner.
            if name:
                calls: set[str] = set()
                out.append((name, node.start_point[0] + 1, calls, node))
                owners = [*owners, (name, calls)]
                for body in _bodies_of(node):
                    body_owners[body.id] = owners
        elif node.type in CALL_NODE_TYPES and owners:
            name = _callee(node)
            owner, calls = owners[-1]
            if lang == "haskell" and node.type == "apply" and _hs_is_pattern(node):
                name = None
            if name and name not in non_calls and not _is_own_leaf_call(node, name, owner):
                calls.add(name)
        stack.extend((child, owners) for child in reversed(node.children))
    return out


# ----------------------------------------------------------------------------- engine side


def engine_functions(crucible: Path) -> dict[tuple[str, str], list[tuple[str, int, list[str]]]]:
    """(language, path relative to the scan root) -> [(name, start_line, calls_out_to)]."""
    sys.path.insert(0, str(REPO_ROOT))
    import gitgalaxy
    from gitgalaxy.galaxyscope import main as galaxyscope_main

    if Path(gitgalaxy.__file__).resolve().parents[1] != REPO_ROOT:
        raise SystemExit(f"engine import resolved to {gitgalaxy.__file__}, not {REPO_ROOT} -- set PYTHONPATH")
    out: dict[tuple[str, str], list[tuple[str, int, list[str]]]] = collections.defaultdict(list)
    with tempfile.TemporaryDirectory() as tmp:
        argv = sys.argv
        sys.argv = ["galaxyscope", str(crucible / "data"), "--output", f"{tmp}/c.json", "--db-only"]
        try:
            galaxyscope_main()
        finally:
            sys.argv = argv
        (db,) = Path(tmp).glob("*_master.db")
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT fd.language, fd.file_path, fn.func_name, fn.start_line, fn.calls_out_to "
                "FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id"
            ).fetchall()
        finally:
            conn.close()
    for lang, path, name, line, calls in rows:
        lang = str(lang or "").lower()
        if lang in LANGS:
            out[(lang, path)].append((name, int(line or 0), json.loads(calls or "[]")))
    return out


# ----------------------------------------------------------------------------- comparison


def _pair(
    gg: list[tuple[str, int, list[str]]], ts: list[tuple[str, int, set[str], Any]]
) -> list[tuple[str, set[str], set[str], Any]]:
    """Match functions by name, then nearest start line within the slack."""
    by_name: dict[str, list[tuple[int, set[str], Any]]] = collections.defaultdict(list)
    for name, line, calls, node in ts:
        by_name[name].append((line, calls, node))
    pairs = []
    for name, line, calls in gg:
        cands = by_name.get(name)
        if not cands:
            continue
        i = min(range(len(cands)), key=lambda k: abs(cands[k][0] - line))
        if abs(cands[i][0] - line) > _LINE_SLACK:
            continue
        _, ts_calls, node = cands.pop(i)
        pairs.append((name, set(calls) - {name}, set(ts_calls) - {name}, node))
    return pairs


# ----------------------------------------------------------------------------- disagreement causes


def _walk(node: Any):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _owner(node: Any, func_types: frozenset[str], top: Any, audit: Any) -> Any:
    """The innermost NAMED function node enclosing `node`, stopping at `top` (C8: an
    anonymous function is part of the unit it is written in)."""
    p = node.parent
    while p is not None and p.id != top.id:
        if p.type in func_types and audit._get_node_name(p):
            return p
        p = p.parent
    return top


_ERROR_SPANS: dict[tuple[int, int], list[tuple[int, int]]] = {}


def _overlaps_parse_error(fn: Any, body: Any) -> bool:
    """True when tree-sitter's tree has an ERROR or MISSING node over the function (a grammar that
    cannot parse the construct, e.g. zig tuple destructuring `_, const x = f();`): the callee is
    absent from the tree because the tree is broken there, not because the call is not one."""
    root = fn
    while root.parent is not None:
        root = root.parent
    key = (root.id, root.end_byte)
    if key not in _ERROR_SPANS:
        _ERROR_SPANS[key] = [
            (n.start_point[0], n.end_point[0]) for n in _walk(root) if n.type == "ERROR" or n.is_missing
        ]
    # rows, not bytes: a broken body starts after the `FnProto` ends, on the same line
    lo, hi = fn.start_point[0], (body if body is not None else fn).end_point[0]
    return any(start <= hi and end >= lo for start, end in _ERROR_SPANS[key])


def _cause(kind: str, callee: str, fn: Any, lang: str, audit: Any, engine_elsewhere: bool) -> tuple[str, Any]:
    """Why one side has `callee` in `fn` and the other does not, as a shape label.

    `kind` is "fp" (engine only) or "fn" (tree-sitter only). Returns the label and
    the node that exemplifies it (None when the name has no node in the function).
    The labels are leads for a person to verify, not verdicts (CLAUDE.md's
    comparative-correctness rule): a `ts-...` label says the ground truth side
    may be the one that is wrong.
    """
    func_types = frozenset(audit.NODE_MAPS[lang]["func_node_types"])
    bodies = _bodies_of(fn)
    calls = [
        n
        for n in [*_walk(fn), *(n for b in bodies for n in _walk(b))]
        if n.type in CALL_NODE_TYPES and _callee(n) == callee
    ]
    if kind == "fp":
        if callee in CONTRACT_NON_CALLS.get(lang, ()):
            return "fp:contract-non-call", None
        for n in calls:  # tree-sitter sees the call, but gives it to an inner function
            inner = _owner(n, func_types, fn, audit)
            if inner.id != fn.id:
                return f"fp:inner-named-{inner.type}", n
        scope = [*_walk(fn), *(n for b in bodies for n in _walk(b))]
        ids = [n for n in scope if n.text == callee.encode() and not n.children]
        if ids:
            parent = ids[0].parent
            grand = parent.parent if parent is not None else None
            shape = f"{parent.type if parent else '?'}<{grand.type if grand else '?'}"
            return f"fp:not-a-call-in-ts:{shape}", ids[0]
        if _overlaps_parse_error(fn, bodies[-1] if bodies else None):
            return "fp:ts-parse-error", None
        return "fp:outside-ts-function", None
    if engine_elsewhere:
        return "fn:engine-attributes-to-another-function", calls[0] if calls else None
    if not calls:
        return "fn:?", None
    n = calls[0]
    field = next((n.child_by_field_name(f) for f in _CALLEE_FIELDS if n.child_by_field_name(f) is not None), None)
    shape = f"{n.type}/{field.type if field is not None else '-'}"
    text = (field.text if field is not None else n.text).decode("utf-8", "replace")
    flags = "".join(
        f for f, hit in (("+generic", "<" in text), ("+bang", callee.endswith("!") or "!" in text[-2:])) if hit
    )
    return f"fn:{shape}{flags}", n


def _example(src: bytes, path: str, node: Any) -> str:
    if node is None:
        return path
    line = src.splitlines()[node.start_point[0]].decode("utf-8", "replace").strip()
    return f"{path}:{node.start_point[0] + 1}: {line[:110]}"


def measure(crucible: Path, samples: int = 0, buckets: int = 0) -> dict[str, dict[str, Any]]:
    sys.path.insert(0, str(TOOLS))
    import tree_sitter_accuracy_audit as audit

    engine = engine_functions(crucible)
    results: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        tp = fp = fn = funcs = parse_failures = 0
        fps: collections.Counter[str] = collections.Counter()
        fns: collections.Counter[str] = collections.Counter()
        causes: collections.Counter[str] = collections.Counter()
        examples: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for (elang, path), gg in sorted(engine.items()):
            if elang != lang:
                continue
            src = crucible / "data" / path
            if not src.is_file():
                continue
            try:
                ts = ts_functions(src.read_bytes(), lang, audit)
            except Exception:  # a parse failure is tree_sitter_accuracy_audit's to report
                parse_failures += 1
                continue
            source = src.read_bytes() if buckets else b""
            engine_names = {c for _, _, calls in gg for c in calls}
            for fname, mine, theirs, node in _pair(gg, ts):
                funcs += 1
                tp += len(mine & theirs)
                fp += len(mine - theirs)
                fn += len(theirs - mine)
                fps.update(mine - theirs)
                fns.update(theirs - mine)
                if not buckets:
                    continue
                for kind, names in (("fp", mine - theirs), ("fn", theirs - mine)):
                    for callee in names:
                        label, ex = _cause(kind, callee, node, lang, audit, callee in engine_names)
                        causes[label] += 1
                        if len(examples[label]) < buckets:
                            examples[label].append(
                                {
                                    "file_path": path,
                                    "name": f"{fname} -> {callee}",
                                    "line": ex.start_point[0] + 1 if ex is not None else None,
                                    "text": _example(source, path, ex),
                                }
                            )
        if not funcs:
            continue
        results[lang] = {
            "matched_functions": funcs,
            "parse_failures": parse_failures,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision_pct": round(100.0 * tp / (tp + fp), 1) if tp + fp else None,
            "recall_pct": round(100.0 * tp / (tp + fn), 1) if tp + fn else None,
        }
        if samples:
            results[lang]["top_fp"] = fps.most_common(samples)
            results[lang]["top_fn"] = fns.most_common(samples)
        if buckets:
            results[lang]["top_causes"] = [
                {"cause": c, "count": k, "examples": examples[c]} for c, k in causes.most_common()
            ]
    return results


# ----------------------------------------------------------------------------- ledger

# The ledger plumbing is shared with import_graph_accuracy.py (graph_ledger.py).
COUNTS = ("tp", "fp", "tp", "fn")


def validated(results: dict[str, dict[str, Any]], ledger_path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    return gl.validated(results, "call", COUNTS, ledger_path)


def render(results: dict[str, dict[str, Any]]) -> str:
    lines = ["| language | functions | precision | recall | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
    for lang, r in results.items():
        lines.append(
            f"| {lang} | {r['matched_functions']} | {r['precision_pct']}% | {r['recall_pct']}% | "
            f"{r['tp']} | {r['fp']} | {r['fn']} |"
        )
    return "\n".join(lines)


def regressions(results: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for lang, base in baseline.items():
        cur = results.get(lang)
        if cur is None:
            out.append(f"{lang}: no longer measured (baseline had {base['matched_functions']} functions)")
            continue
        out.extend(
            f"{lang}: {metric} {base[metric]} -> {cur.get(metric)}"
            for metric in ("precision_pct", "recall_pct")
            if base.get(metric) is not None and (cur.get(metric) or 0.0) < base[metric] - TOLERANCE_PP
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=int, default=0, help="print the N most frequent FP/FN names per language")
    ap.add_argument("--buckets", type=int, default=0, help="classify every FP/FN by cause, N examples each")
    ap.add_argument("--ledger", action="store_true", help="merge the discrepancy shapes into the ledger")
    ap.add_argument("--ci", action="store_true", help="fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args(argv)
    if not (CRUCIBLE / "data").is_dir():
        print(f"call_graph_accuracy: no crucible at {CRUCIBLE} (set LANGUAGE_CRUCIBLE_PATH)")
        return 2
    buckets = max(a.buckets, gl.LEDGER_EXAMPLES) if a.ledger else a.buckets
    results = measure(CRUCIBLE, a.samples, buckets)
    print(render(results))
    if buckets:
        print(gl.render_causes(results, COUNTS))
        if a.ledger:
            gl.merge(results, "call")
            print(f"\ncall_graph_accuracy: shapes merged into {LEDGER.relative_to(REPO_ROOT)}")
        print("\n" + gl.render_validated(results, validated(results)))
    if a.samples:
        for lang, r in results.items():
            print(f"\n{lang}  FP: {r['top_fp']}\n{' ' * len(lang)}  FN: {r['top_fn']}")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2) + "\n")
    stripped = {k: {m: v for m, v in r.items() if not m.startswith("top_")} for k, r in results.items()}
    if a.regenerate:
        BASELINE.write_text(json.dumps(stripped, indent=2, sort_keys=True) + "\n")
        print(f"call_graph_accuracy: baseline rewritten -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not BASELINE.exists():
            print("call_graph_accuracy: no baseline; run --regenerate")
            return 1
        bad = regressions(stripped, json.loads(BASELINE.read_text()))
        if bad:
            print("call_graph_accuracy: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print("call_graph_accuracy: OK -- no language dropped beyond the baseline tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
