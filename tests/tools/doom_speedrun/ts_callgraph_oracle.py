#!/usr/bin/env python3
"""Tree-sitter call-graph body oracle for the non-C/C++ DOOM ports (#5874 item 3, extends callgraph_oracle.py, #5630).

    python tests/tools/doom_speedrun/ts_callgraph_oracle.py --root REPO_DIR --db SCAN_MASTER_DB [--json OUT]

Same contract as ``callgraph_oracle.body_oracle`` (and the same result shape, so ``doom_scorer.callgraph_columns``
scores it): each engine function is matched to the tree-sitter function node at its start line, every call in that
body whose callee is a function the port defines (bare name) is an oracle call, self-edges are dropped on both sides
(#3327). Covers the languages whose function nodes the scorer's tree-sitter oracle already knows (``SPECS``): go, java,
csharp, rust, javascript, python, kotlin. A language outside ``SPECS`` has no oracle: its functions are not read and a port
with none of ``SPECS`` reports ``callgraph`` as ``n/a`` (unscored), never a pass. An engine-only edge is ``absent``
(callee not in the caller's body: scored), ``comment/string`` (scored), ``type`` (a constructor ``new T(..)``),
``function-pointer`` (a bare reference): the last two are reported, not scored. Needs ``tree_sitter_language_pack``.
"""

import argparse
import collections
import functools
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(
    0, str(HERE.parents[2])
)  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import doom_scorer  # noqa: E402

EXAMPLES = 3
QUOTING = ("quote", "quote_spanned", "stringify")
NAME_NODES = {
    "identifier", "field_identifier", "property_identifier", "type_identifier", "simple_identifier",
    "predefined_type",  # C# `new string(..)`: a constructor of a built-in type, kind ``type`` (#6266)
    "word", "simple_word",  # a shell / Tcl command word names the command it runs (#5640)
}  # fmt: skip
# a qualified callee reduces to the field that names the function (``a.b.f`` -> ``f``)
NAME_FIELD = {
    "attribute": "attribute", "selector_expression": "field", "member_expression": "property",
    "member_access_expression": "name", "field_expression": "field", "scoped_identifier": "name",
    "generic_name": None, "generic_function": "function", "member_binding_expression": "name",
    "conditional_access_expression": "name", "navigation_suffix": None,
    "dot_index_expression": "field", "method_index_expression": "method", "command_name": None,
}  # fmt: skip
# a qualified callee whose name is the LAST child (Kotlin ``a.b.f``: ``navigation_expression`` = receiver + suffix)
LAST_CHILD = frozenset({"navigation_expression"})
TEXT_NODES = {
    "comment", "line_comment", "block_comment", "string", "string_literal", "interpreted_string_literal",
    "raw_string_literal", "rune_literal", "template_string", "verbatim_string_literal", "character_literal",
    "string_content",
    "multiline_comment", "multiline_string_literal", "raw_string", "heredoc_body",
}  # fmt: skip


# Kotlin stdlib scope / iteration functions called with only a trailing lambda (``x.run { .. }``, ``3.times { .. }``):
# by name they collide with a port's own ``run()`` override, and the oracle cannot resolve receivers, so they are no calls
KOTLIN_STDLIB = frozenset("run with apply let also takeIf takeUnless repeat times map filter forEach".split())


# a function-valued expression bound to a name is a function of its own: ``window.f = () => {..}``, ``const f = () => ..``
BINDINGS = {"assignment_expression": "right", "variable_declarator": "value", "pair": "value"}


class Spec:
    def __init__(self, parser, functions, calls, ctors=(), bound=()):
        self.parser, self.functions, self.calls, self.ctors, self.bound = (
            parser,
            frozenset(functions),
            dict(calls),
            frozenset(ctors),
            frozenset(bound),
        )

    def is_unit(self, node):
        """A function definition node, or a bound function expression (the engine names and scores it on its own)."""
        if node.type in self.functions:
            return True
        parent = node.parent
        return (
            node.type in self.bound
            and parent is not None
            and parent.type in BINDINGS
            and parent.child_by_field_name(BINDINGS[parent.type]) == node
        )


# call node type -> the field holding the callee
SPECS = {
    "go": Spec("go", {"function_declaration", "method_declaration"}, {"call_expression": "function"}),
    "java": Spec("java", {"method_declaration", "constructor_declaration"}, {"method_invocation": "name"},
                 {"object_creation_expression"}),
    "csharp": Spec("csharp", {"method_declaration", "constructor_declaration", "local_function_statement"},
                   {"invocation_expression": "function"}, {"object_creation_expression"}),
    "rust": Spec("rust", {"function_item"}, {"call_expression": "function"}),
    "javascript": Spec("javascript", {"function_declaration", "method_definition"}, {"call_expression": "function"},
                       {"new_expression"},
                       {"arrow_function", "function_expression"}),
    "python": Spec("python", {"function_definition"}, {"call": "function"}),
    # shell and Tcl: a command word naming a function defined in the port is a call (#5640); Lua is an ordinary call
    "lua": Spec("lua", {"function_declaration"}, {"function_call": "name"}),
    "shell": Spec("bash", {"function_definition"}, {"command": "name"}),
    "tcl": Spec("tcl", {"procedure"}, {"command": "name"}),
    # a callee of None is the call node's first named child (Kotlin has no field for it)
    "kotlin": Spec("kotlin", {"function_declaration", "secondary_constructor", "anonymous_initializer"},
                   {"call_expression": None}),
}  # fmt: skip


def available(lang):
    """True when the installed tree-sitter language pack lists ``lang``'s grammar (no download is attempted)."""
    import tree_sitter_language_pack

    return SPECS[lang].parser in tree_sitter_language_pack.manifest_languages()


@functools.cache
def _parser(lang):
    import tree_sitter_language_pack

    return tree_sitter_language_pack.get_parser(SPECS[lang].parser)


def text_of(node):
    return node.text.decode("utf-8", errors="surrogateescape")


def callee_name(node):
    """The bare function name a callee expression ends in, or None for a computed callee (``fs[i](x)``)."""
    while node is not None:
        if node.type in NAME_NODES:
            return text_of(node)
        if node.type in LAST_CHILD:
            node = (node.named_children or [None])[-1]
            continue
        if node.type not in NAME_FIELD:
            return None
        field = NAME_FIELD[node.type]
        node = node.child_by_field_name(field) if field else (node.named_children or [None])[0]
    return None


def _super_ctor_target(node):
    """The superclass a Java ``super(...)`` chains to (#3772): the enclosing class's ``extends`` type, or None."""
    if not node.text.startswith(b"super"):
        return None
    cls = node.parent
    while cls is not None and cls.type != "class_declaration":
        cls = cls.parent
    parent = cls.child_by_field_name("superclass") if cls is not None else None
    target = (parent.named_children or [None])[0] if parent is not None else None
    if target is not None and target.type == "generic_type":  # `extends Base<T>` names `Base`
        target = (target.named_children or [None])[0]
    return callee_name(target) if target is not None else None


def _has_arguments(call):
    """True when a Kotlin call carries a parenthesised argument list (not just a trailing lambda)."""
    return any(c.type == "value_arguments" for k in call.children if k.type == "call_suffix" for c in k.children)


class Body:
    """One function body: called names, other identifier references, constructor types, comment/string text."""

    def __init__(self, node, spec):
        self.calls, self.refs, self.types, self.text_only = set(), set(), set(), []
        stack = list(
            reversed(node.children)
        )  # the whole definition: a C# ``: base(...)`` initializer is outside the body
        callees = set()
        while stack:
            n = stack.pop()
            if n.type == "macro_invocation" and text_of(n.child_by_field_name("macro") or n).startswith(QUOTING):
                self.text_only.append(text_of(n))  # ``quote!`` emits code for another crate: not calls made here
                continue
            if n.type == "token_tree":  # a Rust macro's arguments are unparsed tokens: ``name`` + ``(...)`` is a call
                kids = n.children
                for a, b in zip(kids, kids[1:]):
                    if b.type == "token_tree" and b.text.startswith(b"(") and text_of(a).isidentifier():
                        self.calls.add(text_of(a))
                self.refs.update(text_of(k) for k in kids if not k.children and text_of(k).isidentifier())
            if n.type in TEXT_NODES:
                self.text_only.append(text_of(n))
                continue
            if spec.is_unit(n):
                continue  # a nested function is its own unit
            if n.type in spec.calls:
                field = spec.calls[n.type]
                fn = n.child_by_field_name(field) if field else (n.named_children or [None])[0]
                name = callee_name(fn) if fn is not None else None
                if spec.parser == "kotlin" and name in KOTLIN_STDLIB and not _has_arguments(n):
                    name = None
                if name is not None:
                    self.calls.add(name)
                    if fn.type in NAME_NODES:
                        callees.add(fn.id)
            elif n.type == "explicit_constructor_invocation":
                name = _super_ctor_target(n)
                if name is not None:
                    self.calls.add(name)
            elif n.type in spec.ctors:
                t = n.child_by_field_name("type") or n.child_by_field_name("constructor")
                name = callee_name(t) if t is not None else None
                if name is not None:
                    self.types.add(name)
            elif n.type in NAME_NODES and n.id not in callees:
                self.refs.add(text_of(n))
            stack.extend(reversed(n.children))

    def presence(self, name):
        if name in self.calls or name in self.refs:
            return "function-pointer"
        if name in self.types:
            return "type"
        if any(name in t for t in self.text_only):
            return "comment/string"
        return None


def bare(name):
    return name.split("::")[-1].split(".")[-1]


def function_nodes(tree, spec):
    out, stack = [], [tree.root_node]
    while stack:
        n = stack.pop()
        if spec.is_unit(n):
            out.append(n)
        stack.extend(reversed(n.children))
    return out


def definition_at(nodes, line):
    """The innermost function node whose head spans 1-based ``line`` (decorators and attributes sit above the name)."""
    row, best = line - 1, None
    for n in nodes:
        body = n.child_by_field_name("body")
        end = body.start_point[0] if body is not None else n.end_point[0]
        if n.start_point[0] <= row <= end and (best is None or n.start_point[0] >= best.start_point[0]):
            best = n
    return best


def load_port(repo, db, vendored=None):
    """Engine functions of a scan in a language of ``SPECS``: [(relpath, language, name, start_line, callees)].

    ``vendored`` (a relpath -> bool test) drops vendored code (#6097)."""
    repo = str(repo).replace("\\", "/").rstrip("/")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select f.file_path, f.language, fn.func_name, fn.start_line, fn.calls_out_to "
            "from function_data fn join file_data f on f.id = fn.file_id"
        ).fetchall()
    finally:
        con.close()
    out = []
    for path, lang, name, start, calls in rows:
        if lang not in SPECS or not name:
            continue
        rel = path.replace("\\", "/")
        if rel.startswith(repo + "/"):
            rel = rel[len(repo) + 1 :]
        if vendored and vendored(rel):
            continue
        try:
            callees = json.loads(calls) if calls else []
        except ValueError:
            callees = []
        out.append((rel, lang, name, int(start or 0), callees))
    return out


def body_oracle(repo, rows):
    """Recall / precision of ``calls_out_to`` against the tree-sitter call set, in ``callgraph_oracle.body_oracle``'s shape."""
    defined = {bare(r[2]) for r in rows}
    trees, misses, extra = {}, collections.Counter(), collections.Counter()
    examples = collections.defaultdict(list)
    n_or = n_eng = agree = unmatched = 0
    for rel, lang, fname, start, callees in rows:
        if (rel, lang) not in trees:
            try:
                tree = _parser(lang).parse((Path(repo) / rel).read_bytes())
                trees[(rel, lang)] = function_nodes(tree, SPECS[lang])
            except OSError:
                trees[(rel, lang)] = []
        node = definition_at(trees[(rel, lang)], start)
        if node is None:
            unmatched += 1
            continue
        body, caller = Body(node, SPECS[lang]), bare(fname)
        oracle = body.calls & defined
        oracle.discard(caller)
        eng = {bare(c) for c in callees} & defined
        eng.discard(caller)
        n_or, n_eng, agree = n_or + len(oracle), n_eng + len(eng), agree + len(oracle & eng)
        for callee in sorted(oracle - eng):
            misses["call"] += 1
            if len(examples["miss:call"]) < EXAMPLES:
                examples["miss:call"].append(f"{rel}:{start} {caller} -> {callee}")
        for callee in sorted(eng - oracle):
            kind = body.presence(callee) or "absent"
            extra[kind] += 1
            if len(examples["engine-only:" + kind]) < EXAMPLES:
                examples["engine-only:" + kind].append(f"{rel}:{start} {caller} -> {callee}")
    return {
        "functions": len(rows),
        "unmatched_functions": unmatched,
        "oracle_calls": n_or,
        "engine_calls": n_eng,
        "agree": agree,
        "recall": round(agree / n_or, 4) if n_or else 1.0,
        "precision": round(agree / n_eng, 4) if n_eng else 1.0,
        "misses_by_shape": dict(misses),
        "engine_only_by_kind": dict(extra.most_common()),
        "examples": dict(sorted(examples.items())),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True, help="the port's repo checkout")
    ap.add_argument("--db", type=Path, required=True, help="the scan's *_master.db")
    ap.add_argument("--json", type=Path, help="write the result here")
    args = ap.parse_args(argv)
    rows = load_port(args.root, args.db, doom_scorer._engine_vendor_test(args.root))
    if not rows:
        print("n/a: no function in a language with a tree-sitter call oracle")
        return 0
    result = body_oracle(args.root, rows)
    print(f"recall {result['recall']:.4f} precision {result['precision']:.4f} over {result['oracle_calls']} calls")
    print(f"misses {result['misses_by_shape']} engine-only {result['engine_only_by_kind']}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
