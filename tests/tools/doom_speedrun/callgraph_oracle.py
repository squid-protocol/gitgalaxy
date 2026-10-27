#!/usr/bin/env python3
"""C/C++ call-graph validation for the DOOM Port Speedrun corpus (#5630): a tree-sitter body oracle and family consensus.

    python tests/tools/doom_speedrun/callgraph_oracle.py [--only a,b] [--family a,b] [--work DIR] [--sha SHA]
           [--baseline FILE --fail-on-regression] [--write-baseline FILE]

Reads the scans ``doom_speedrun.py scan`` leaves under ``<work>/scans/<sha>/<port>`` and the clones under
``<work>/repos/<port>``; it never fetches or scans itself.

1. **Body oracle** (per port): each engine function is matched to the tree-sitter ``function_definition`` at its
   start line, and every ``call_expression`` in that body whose callee is a function the port defines is an oracle
   call. Compared with ``calls_out_to`` (restricted to defined names; self-edges ignored on both sides, as the engine
   drops recursion by contract, #3327): recall, precision, each miss classified by the shape around the call, each engine-only edge by how the callee
   appears.
2. **Family consensus** (near-identical vanilla-lineage ports): an edge a->b that >= 75% of the siblings defining both
   ends carry, missing from one port, is looked up in that port's body of ``a``: a call or reference there is an
   engine miss, otherwise a real divergence. A lone edge no sibling carries, whose callee is not in the body, is a
   possible false edge.

Results go to ``<work>/results/<sha>/callgraph.{json,md}``. ``--baseline`` compares with a committed baseline and
``--fail-on-regression`` exits 1 when a port's recall or precision drops, or a consensus count grows (the hook for the
DOOM-rosetta nightly, #5619). Licensed ports only: the tool refuses any port outside ``LICENSED``.
Needs ``tree_sitter_language_pack`` (the selfscan venv has it).
"""

import argparse
import collections
import functools
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import doom_scorer  # noqa: E402

DEFAULT_WORK = Path(os.environ.get("DOOM_SPEEDRUN_WORK", "/tmp/gitgalaxy-scratch/doom-speedrun"))
DEFAULT_BASELINE = HERE / "callgraph_baseline.json"

# C/C++ ports of the manifest whose license was read from the repo files (owner ruling 2026-10-19). A port outside
# this set is never run, reported or committed by this tool.
LICENSED = frozenset(
    "linuxdoom chocolate-doom crispy-doom doomgeneric doomretro prboom-plus dsda-doom woof eternity odamex gzdoom "
    "doom-wasm fastdoom puredoom doom3-bfg doom-ascii srb2 doomsday edge-classic nugget-doom inter-doom sdl-doom "
    "doom3do".split()
)
# Near-identical vanilla-lineage ports: they vote on each other's edges.
FAMILY = (
    "linuxdoom", "doomgeneric", "doom-ascii", "sdl-doom", "puredoom", "chocolate-doom", "crispy-doom", "doom-wasm",
    "inter-doom",
)  # fmt: skip
QUORUM = 0.75
MIN_HOLDERS = 3  # siblings defining both ends before a missing edge is a hole
MIN_LONE_HOLDERS = 4  # siblings defining both ends, none with the edge, before a lone edge is suspect
EXAMPLES = 3
TOLERANCE = 0.001

PARSER_LANG = {"c": "c", "cpp": "cpp"}
CALLER_SCOPES = {"function_definition", "lambda_expression"}
SKIP_PARENTS = {"parenthesized_expression", "condition_clause"}
SHAPE_OF_PARENT = {
    "cast_expression": "after-cast",
    "argument_list": "nested-argument",
    "subscript_expression": "subscript",
    "subscript_argument_list": "subscript",
    "binary_expression": "after-operator",
    "unary_expression": "after-operator",
    "update_expression": "after-operator",
    "conditional_expression": "after-operator",
    "pointer_expression": "after-operator",
    "comma_expression": "after-operator",
    "assignment_expression": "assignment-rhs",
    "init_declarator": "assignment-rhs",
    "initializer_list": "assignment-rhs",
    "return_statement": "condition/return",
    "if_statement": "condition/return",
    "while_statement": "condition/return",
    "do_statement": "condition/return",
    "for_statement": "condition/return",
    "switch_statement": "condition/return",
    "expression_statement": "statement",
}
PREPROC = {"preproc_def", "preproc_function_def", "preproc_call", "preproc_arg"}
# Statements that cannot sit at file scope: one right after a function means tree-sitter closed that function early
STATEMENT_NODES = {
    "for_statement", "while_statement", "do_statement", "if_statement", "switch_statement", "return_statement",
    "for_range_loop", "try_statement", "expression_statement",
}  # fmt: skip
TEXT_NODES = {"comment", "string_literal", "raw_string_literal", "char_literal", "concatenated_string"}
# Text fallback for a region tree-sitter misparsed (an ERROR node, or an ``else if`` split by ``#ifdef`` read as a
# nested function definition): comments and literals blanked, then every ``name (`` that is not a keyword.
STRIP = re.compile(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.S)
TEXT_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
# A class or struct definition head: the last word before its `:` base list or `{` is the class name.
CLASS_HEAD = re.compile(r"\b(?:class|struct)\b[^;{}()<>]*?\b([A-Za-z_]\w*)\s*(?:final\s*)?[:{]")
# A class head with a base list: `class A : public B, virtual C<T> {` (the entries after the lone `:`).
BASE_LIST = re.compile(r"\b(?:class|struct)\b[^;{}()]*?[^:]:(?!:)([^;{}]*)\{")
BASE_NAME = re.compile(r"([A-Za-z_]\w*)\s*(?:<[^<>]*>)?\s*$")
CPP_EXTS = frozenset(".h .hh .hpp .hxx .inl .cc .cpp .cxx".split())
KEYWORDS = frozenset(
    "if else while for do switch return sizeof alignof _Alignof defined case goto typeof decltype".split()
)


def bare(name):
    """``ns::Class::f`` / ``obj.f`` -> ``f``: call edges are compared by unqualified name."""
    return name.split("::")[-1].split(".")[-1]


@functools.cache
def _parser(lang):
    import tree_sitter_language_pack

    return tree_sitter_language_pack.get_parser(PARSER_LANG[lang])


def callee_node(fn):
    """The name node of a call's ``function`` node, or None for an expression (``(*p)(x)``, ``t[i](x)``)."""
    while fn is not None:
        if fn.type in ("identifier", "field_identifier", "destructor_name"):
            return fn
        if fn.type == "field_expression":
            fn = fn.child_by_field_name("field")
        elif fn.type in ("qualified_identifier", "template_function", "template_method"):
            fn = fn.child_by_field_name("name")
        else:
            return None
    return None


def shape(call):
    """The syntactic position of a call: the first meaningful parent decides (issue #5630's shape list)."""
    p = call.parent
    while p is not None and p.type in SKIP_PARENTS:
        p = p.parent
    if p is None:
        return "other"
    return SHAPE_OF_PARENT.get(p.type, "other")


def decode_bytes(raw):
    """Lossless and offset-stable (one character per undecodable byte, #3813): TextBody counts lines in the decoded
    text, so a whole-file codec guess must not reflow it, and per-node decoding stays cheap."""
    return raw.decode("utf-8", errors="surrogateescape")


class Body:
    """One function body: its calls (name -> shape of the first call), other identifier references, preprocessor and
    comment/literal text."""

    def __init__(self, node, classes=None):
        self.node = node
        self.calls, self.refs, self.preproc, self.text_only, self.types = {}, set(), [], [], set()
        self.broken = False  # an ERROR node inside: tree-sitter may have closed the body early
        self.nested = []  # 1-based last lines of real nested definitions (methods, or functions a misparse ran over)
        callees = set()
        for init in _initializers(node):  # `: Base(x), member(y)`: a base class entry is a constructor call
            name = callee_node(init.children[0]) if init.children else None
            if name is not None and decode_bytes(name.text) in _bases(classes or {}, node):
                self.calls.setdefault(decode_bytes(name.text), "ctor-init")
        body = node.child_by_field_name("body") or node
        stack = [body]
        for init in _initializers(node):  # `d(new Impl(this))`, `base(f(x))`: the arguments are part of the constructor
            stack.extend(init.children[1:])
        while stack:
            n = stack.pop()
            if n.type in PREPROC:
                self.preproc.append(decode_bytes(n.text))
                continue
            if n.type in TEXT_NODES:
                self.text_only.append(decode_bytes(n.text))
                continue
            if n.type == "function_definition":
                if n.parent is not None and n.parent.type == "field_declaration_list":
                    continue  # a local class's method is its own unit
                if _is_real_nested_function(n):
                    self.nested.append(n.end_point[0] + 1)
                    continue  # nyx-o8: a nested function's calls are credited to it, not to the outer (as the engine does)
                if _keyword_named(n):  # `MACRO\n if (x)` reads as a definition named `if`
                    self.broken = True
                inner = n.child_by_field_name("body")  # C has no nested functions: a misparsed statement
                end = inner.start_byte if inner is not None else n.end_byte
                self._text_calls(n.text[: end - n.start_byte])
            elif n.type == "ERROR":
                self.broken = True
                self._text_calls(n.text)
            elif n.type == "call_expression":
                name = callee_node(n.child_by_field_name("function"))
                if name is not None:
                    self.calls.setdefault(decode_bytes(name.text), shape(n))
                    callees.add(name.id)
            elif n.type == "identifier" and n.id not in callees:  # a struct field is never a function reference
                self.refs.add(decode_bytes(n.text))
            elif n.type == "type_identifier":  # C++ `new T(...)` / `T v(...)`: a constructor, not a named call
                self.types.add(decode_bytes(n.text))
            stack.extend(reversed(n.children))
        if _runs_into_statements(node):  # `QRYNEWINFO(7) {..} else {..}` (an `if` macro) ends the node with no ERROR
            self.broken = True

    def _text_calls(self, raw):
        text = STRIP.sub(" ", decode_bytes(raw))
        for m in TEXT_CALL.finditer(text):
            if m.group(1) not in KEYWORDS:
                self.calls.setdefault(m.group(1), "unparsed")

    def presence(self, name):
        """How ``name`` appears in the body: ``call:<shape>``, ``function-pointer``, ``type`` (a C++ constructor),
        ``macro``, ``comment/string`` or None."""
        if name in self.calls:
            return "call:" + self.calls[name]
        if name in self.refs:
            return "function-pointer"
        if name in self.types:
            return "type"
        if any(_word_in(name, t) for t in self.preproc):
            return "macro"
        if any(_word_in(name, t) for t in self.text_only):
            return "comment/string"
        return None


# A macro class (`DE_PIMPL(X) { ... }`, `DE_GUI_PIMPL(X),\nDE_OBSERVES(A, B)\n{ ... }`) is a class: its members are declarations
# and nested definitions, which own their calls (#5630).
MACRO_CLASS_HEAD = re.compile(r"[ \t]*[A-Z0-9_]*PIMPL[A-Z0-9_]*[ \t]*\(")


def _member_initializers(body):
    """A macro class's own code: the right-hand side of each member initializer (``Mat3f m = f();``) at the class's top
    level. A declaration or a definition head (``bool isValid() const;``, ``Impl(Public *i) : Base(i)``) names a member,
    it calls nothing, and a nested ``{...}`` is a method whose calls are its own."""
    own, chunk, depth, parens = [], [], 0, 0
    for ch in body:
        if ch == "{":
            depth += 1
            if depth == 1:
                continue
        elif ch == "}":
            depth -= 1
            if depth == 1:  # a nested method or aggregate closed: the chunk before it was its head
                chunk = []
            continue
        if depth != 1:
            continue
        parens += (ch == "(") - (ch == ")")
        if ch == ";" and parens <= 0:
            text = "".join(chunk)
            chunk = []
            if m := re.search(r"(?<![=!<>])=(?!=)", re.sub(r"\([^()]*\)", lambda x: " " * len(x.group(0)), text)):
                own.append(text[m.end() :])
        else:
            chunk.append(ch)
    return "\n".join(own)


class TextBody(Body):
    """Fallback for a function tree-sitter folds into a neighbour (a macro table above it with no semicolon): the
    brace-matched body from its start line, comments and literals blanked, preprocessor lines dropped; every call is
    shape ``unparsed``. Also used when a bare macro statement (``ADD_FILE_COUNTER`` with no semicolon) makes tree-sitter
    close the body early: ``end_line`` says whether the braces reach further."""

    def __init__(self, src, line):
        self.node, self.calls, self.refs, self.preproc, self.text_only, self.types = None, {}, set(), [], [], set()
        self.end_line = line
        lines = decode_bytes(src).split("\n")
        raw = "\n".join(lines[max(0, line - 1) :])
        text = STRIP.sub(lambda m: " " * len(m.group(0)), raw)
        depth, open_at, end = 0, None, None
        for i, ch in enumerate(text):
            if ch == "{":
                open_at = i if open_at is None else open_at
                depth += 1
            elif ch == "}" and open_at is not None:
                depth -= 1
                if depth == 0:
                    end = i
                    break
            elif ch == ";" and open_at is None:
                break
        if end is None:
            self.calls = None
            return
        self.end_line = line + text.count("\n", 0, end)
        body = text[open_at : end + 1]
        self.preproc = re.findall(r"^[ \t]*#.*$", body, flags=re.M)
        body = re.sub(r"^[ \t]*#.*$", " ", body, flags=re.M)
        if MACRO_CLASS_HEAD.match(lines[line - 1]):
            self._text_calls(_member_initializers(body).encode())
        else:
            self._text_calls(body.encode())
        self.refs = set(re.findall(r"\b[A-Za-z_]\w*\b", body)) - set(self.calls)
        self.text_only = [m.group(0) for m in STRIP.finditer(raw[open_at : end + 1])]


def _initializers(node):
    """The ``field_initializer`` entries of a constructor's initializer list (a child of the definition, not of its body)."""
    for child in node.children:
        if child.type == "field_initializer_list":
            return [c for c in child.children if c.type == "field_initializer"]
    return []


def _owner(node):
    """The class a constructor definition belongs to: the class body it sits in, else the scope of ``Cls::Cls``."""
    up = node.parent
    while up is not None:
        if up.type in ("class_specifier", "struct_specifier"):
            name = up.child_by_field_name("name")
            return decode_bytes(name.text) if name is not None else None
        up = up.parent
    decl = node.child_by_field_name("declarator")
    while decl is not None and decl.type != "qualified_identifier":
        decl = decl.child_by_field_name("declarator")
    scope = decl.child_by_field_name("scope") if decl is not None else None
    while (
        decl is not None
        and (inner := decl.child_by_field_name("name")) is not None
        and inner.type == "qualified_identifier"
    ):
        decl, scope = (
            inner,
            inner.child_by_field_name("scope") or scope,
        )  # `A::B::B` nests: the class is the innermost scope
    return bare(decode_bytes(scope.text)) if scope is not None else None


def _bases(classes, node):
    """The base classes its owner lists (every listed base when the owner is not found)."""
    owner = _owner(node)
    if owner in classes:
        return classes[owner]
    return set().union(*classes.values()) if owner is None else set()


def class_names(repo):
    """class -> the base classes its head lists, over a repo's C++ files: what a base-class initializer entry names (a
    data member `: type(t)` is no call, even when a vendored class elsewhere shares its name)."""
    bases_of: dict[str, set[str]] = {}
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if os.path.splitext(f)[1].lower() in CPP_EXTS:
                try:
                    text = (Path(root) / f).read_bytes()
                except OSError:
                    continue
                clean = STRIP.sub(" ", decode_bytes(text))
                for head in BASE_LIST.finditer(clean):
                    owner = CLASS_HEAD.search(head.group(0))
                    if owner is None:
                        continue
                    bases_of.setdefault(owner.group(1), set()).update(
                        m.group(1) for b in head.group(1).split(",") if (m := BASE_NAME.search(b))
                    )
    return bases_of


# Macro statements that take a body, like `for` (doomsday's `DE_FOR_EACH_CONST(T, i, c) { ... }`, `DE_NOTIFY_PUBLIC(N, i) ...`,
# gzdoom's `IFVIRTUALPTRNAME(o, "C", F) { ... }`): tree-sitter reads one as a nested definition, the engine as a statement
# of its function (#5630).
MACRO_STATEMENT = re.compile(r"DE_(?:FOR_(?:EACH|OBSERVERS)|NOTIFY)[A-Z_]*|IF(?:VM|(?:OVERRIDEN)?VIRTUAL(?:PTR)?(?:NAME)?)")


def _is_real_nested_function(node):
    """A nested ``function_definition`` that is a function (a GNU C nested function), not the ``else if (...) {`` that
    ``#ifdef`` splitting makes tree-sitter read as one (its type or declarator name is a keyword) nor a macro statement."""
    kind = node.child_by_field_name("type")
    decl = node.child_by_field_name("declarator")
    while decl is not None and decl.type in ("pointer_declarator", "reference_declarator"):
        # `Hash &hashFor(int)` / `Item *find()`: the function_declarator sits under the `&` / `*` (a DE_PIMPL method
        # returning one was read as no function, so its calls were credited to the class, 1085 doomsday misses, #6266)
        decl = decl.child_by_field_name("declarator") or next(iter(decl.named_children), None)
    name = callee_node(decl.child_by_field_name("declarator")) if decl is not None else None
    if name is None or decode_bytes(name.text) in KEYWORDS or MACRO_STATEMENT.fullmatch(decode_bytes(name.text)):
        return False
    return kind is None or decode_bytes(kind.text) not in KEYWORDS


def _runs_into_statements(node):
    """True when the next non-comment sibling of a file-scope function is a statement: the code below it is the rest of
    this function, which tree-sitter closed early (an `if`-like macro before a braced block, #5630)."""
    nxt = node.next_sibling
    while nxt is not None and nxt.type == "comment":
        nxt = nxt.next_sibling
    return (
        node.parent is not None
        and node.parent.type == "translation_unit"
        and nxt is not None
        and nxt.type in STATEMENT_NODES
    )


def _word_in(word, text):
    i = text.find(word)
    while i >= 0:
        before = text[i - 1] if i else " "
        after = text[i + len(word)] if i + len(word) < len(text) else " "
        if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
            return True
        i = text.find(word, i + 1)
    return False


def function_nodes(tree):
    """Every function_definition, outermost first."""
    out, stack = [], [tree.root_node]
    while stack:
        n = stack.pop()
        if n.type == "function_definition":
            out.append(n)
        stack.extend(reversed(n.children))
    return out


def _keyword_named(node):
    """A ``function_definition`` tree-sitter made of a statement: ``INLEVEL\n if (x) ...`` (a bare macro statement, no
    semicolon) reads as a K&R definition named ``if`` whose head can run to the end of the file (srb2, #6266)."""
    decl = node.child_by_field_name("declarator")
    name = callee_node(decl.child_by_field_name("declarator")) if decl is not None else None
    return name is not None and decode_bytes(name.text) in KEYWORDS


def definition_at(nodes, line):
    """The function_definition whose head spans 1-based ``line`` (start row <= line <= body's first row); never a
    keyword-named misparse, whose head would swallow every function below it."""
    row = line - 1
    best = None
    for n in nodes:
        body = n.child_by_field_name("body")
        if body is None or _keyword_named(n):
            continue
        if n.start_point[0] <= row <= body.start_point[0] and (best is None or n.start_point[0] >= best.start_point[0]):
            best = n
    return best


def find_db(scan_dir):
    hits = sorted(glob.glob(str(Path(scan_dir) / "*_master.db")))
    return hits[0] if hits else None


def load_port(repo, db, vendored=None):
    """Engine functions of a scan: [(relpath, language, name, start_line, calls_out_to list)] for C and C++ files.

    ``vendored`` (a relpath -> bool test, ``doom_scorer._engine_vendor_test``) drops vendored code: a library's functions
    are neither oracle callers nor defined names (#6097)."""
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
        if lang not in PARSER_LANG or not name:
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


class Port:
    """A port's engine functions, each with its tree-sitter body (None when no definition sits at its start line)."""

    def __init__(self, name, repo, rows):
        self.name, self.repo = name, Path(repo)
        self.defined = {bare(r[2]) for r in rows}
        self.functions = []  # (rel, name, start, engine callee set, Body / TextBody or None)
        self.edges = set()
        trees = {}
        classes = class_names(self.repo) if any(r[1] == "cpp" for r in rows) else {}
        for rel, lang, fname, start, callees in rows:
            key = (rel, lang)
            if key not in trees:
                try:
                    src = (self.repo / rel).read_bytes()
                    trees[key] = (src, function_nodes(_parser(lang).parse(src)))
                except OSError:
                    trees[key] = (b"", [])
            src, nodes = trees[key]
            node = definition_at(nodes, start)
            body = Body(node, classes) if node is not None else TextBody(src, start)
            if node is not None and body.broken:
                braces = TextBody(src, start)
                # end_point[0], never .row: .row on the temporary Point read freed memory (tree-sitter 0.26, #5630).
                # Braces ending earlier: the node ran over the code below (srb2's bare macro statements, MSVC __asm,
                # #6266), unless the braces hold whole methods (a broken DE_PIMPL class: their calls are theirs)
                ends = node.end_point[0] + 1
                earlier = braces.end_line < ends and all(row > braces.end_line for row in body.nested)
                if braces.calls is not None and (braces.end_line > ends or earlier):
                    body = braces
            caller = bare(fname)
            eng = {bare(c) for c in callees} & self.defined
            eng.discard(caller)
            self.edges |= {(caller, c) for c in eng}
            self.functions.append((rel, caller, start, eng, body if body.calls is not None else None))

    def bodies(self, name):
        return [f for f in self.functions if f[1] == name and f[4] is not None]


def body_oracle(port):
    """Per-port recall/precision of ``calls_out_to`` against the tree-sitter call set, misses by shape."""
    misses, extra = collections.Counter(), collections.Counter()
    examples = collections.defaultdict(list)
    n_or = n_eng = agree = unmatched = text = 0
    for rel, caller, start, eng, body in port.functions:
        if body is None:
            unmatched += 1
            continue
        text += isinstance(body, TextBody)
        oracle = set(body.calls) & port.defined
        oracle.discard(caller)
        n_or += len(oracle)
        n_eng += len(eng)
        agree += len(oracle & eng)
        for callee in sorted(oracle - eng):
            kind = body.calls[callee]
            misses[kind] += 1
            if len(examples["miss:" + kind]) < EXAMPLES:
                examples["miss:" + kind].append(f"{rel}:{start} {caller} -> {callee}")
        for callee in sorted(eng - oracle):
            kind = body.presence(callee) or "absent"
            kind = "function-pointer" if kind.startswith("call:") else kind  # a call the oracle saw is in `oracle`
            extra[kind] += 1
            if len(examples["engine-only:" + kind]) < EXAMPLES:
                examples["engine-only:" + kind].append(f"{rel}:{start} {caller} -> {callee}")
    return {
        "functions": len(port.functions),
        "unmatched_functions": unmatched,
        "text_fallback_functions": text,
        "oracle_calls": n_or,
        "engine_calls": n_eng,
        "agree": agree,
        "recall": round(agree / n_or, 4) if n_or else 1.0,
        "precision": round(agree / n_eng, 4) if n_eng else 1.0,
        "misses_by_shape": dict(misses.most_common()),
        "engine_only_by_kind": dict(extra.most_common()),
        "examples": {k: v for k, v in sorted(examples.items())},
    }


def _presence(port, a, b):
    hits = [f[4].presence(b) for f in port.bodies(a)]
    hits = [h for h in hits if h and h != "comment/string"]
    return (hits[0], port.bodies(a)[0]) if hits else (None, (port.bodies(a) or [None])[0])


def consensus(ports):
    """Family vote on each edge; holes looked up in source to split engine misses from real divergences."""
    missed, divergent, suspects = [], 0, []
    for p in ports:
        sibs = [q for q in ports if q is not p]
        for a, b in sorted(set().union(*(q.edges for q in sibs))):
            if a == b or a not in p.defined or b not in p.defined or (a, b) in p.edges or not p.bodies(a):
                continue
            holders = [q for q in sibs if a in q.defined and b in q.defined]
            have = sum((a, b) in q.edges for q in holders)
            if len(holders) < MIN_HOLDERS or have / len(holders) < QUORUM:
                continue
            why, f = _presence(p, a, b)
            if why:
                missed.append({"port": p.name, "edge": f"{a} -> {b}", "votes": f"{have}/{len(holders)}",
                               "at": f"{f[0]}:{f[2]}", "shape": why.removeprefix("call:")})  # fmt: skip
            else:
                divergent += 1
        for a, b in sorted(p.edges):
            holders = [q for q in sibs if a in q.defined and b in q.defined]
            if len(holders) < MIN_LONE_HOLDERS or any((a, b) in q.edges for q in holders) or not p.bodies(a):
                continue
            why, f = _presence(p, a, b)
            if not why:
                suspects.append({"port": p.name, "edge": f"{a} -> {b}", "votes": f"0/{len(holders)}",
                                 "at": f"{f[0]}:{f[2]}"})  # fmt: skip
    return {
        "family": [p.name for p in ports],
        "quorum": QUORUM,
        "holes": len(missed) + divergent,
        "engine_missed": len(missed),
        "divergent": divergent,
        "false_edge_suspects": len(suspects),
        "missed_by_port": dict(collections.Counter(m["port"] for m in missed).most_common()),
        "missed_by_shape": dict(collections.Counter(m["shape"] for m in missed).most_common()),
        "missed": missed,
        "suspects": suspects,
    }


def regressions(current, baseline, tol=TOLERANCE):
    """Human-readable regressions of ``current`` against ``baseline`` (empty list = no regression)."""
    out = []
    for name, base in sorted(baseline.get("ports", {}).items()):
        cur = current.get("ports", {}).get(name)
        if cur is None:
            out.append(f"{name}: in the baseline, not in this run")
            continue
        for key in ("recall", "precision"):
            if cur[key] < base[key] - tol:
                out.append(f"{name}: {key} {base[key]:.4f} -> {cur[key]:.4f}")
    bc, cc = baseline.get("consensus"), current.get("consensus")
    if bc and cc and bc.get("family") == cc.get("family"):
        for key in ("engine_missed", "false_edge_suspects"):
            if cc[key] > bc[key]:
                out.append(f"consensus: {key} {bc[key]} -> {cc[key]}")
    elif bc:
        out.append("consensus: family differs from the baseline's (or was not run)")
    return out


def baseline_view(result):
    """The committed baseline: numbers only (no example lists), so it diffs cleanly."""
    ports = {
        n: {
            k: r[k]
            for k in (
                "functions",
                "unmatched_functions",
                "text_fallback_functions",
                "oracle_calls",
                "engine_calls",
                "agree",
                "recall",
                "precision",
                "misses_by_shape",
                "engine_only_by_kind",
            )
        }  # fmt: skip
        for n, r in result["ports"].items()
    }
    out = {"engine_sha": result["engine_sha"], "ports": ports}
    if result.get("consensus"):
        c = result["consensus"]
        out["consensus"] = {k: c[k] for k in ("family", "quorum", "holes", "engine_missed", "divergent",
                                               "false_edge_suspects", "missed_by_port", "missed_by_shape")}  # fmt: skip
    return out


def render(result):
    lines = [f"# C/C++ call-graph oracle: engine `{result['engine_sha']}`", "",
             "| port | functions | unmatched | text fallback | oracle calls | engine calls | recall | precision | misses by shape | engine-only |",
             "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for n, r in result["ports"].items():
        fmt = lambda d: ", ".join(f"{k} {v}" for k, v in d.items()) or "-"  # noqa: E731
        lines.append(f"| {n} | {r['functions']} | {r['unmatched_functions']} | {r['text_fallback_functions']} | "
                     f"{r['oracle_calls']} | "
                     f"{r['engine_calls']} | {r['recall']:.4f} | {r['precision']:.4f} | {fmt(r['misses_by_shape'])} | "
                     f"{fmt(r['engine_only_by_kind'])} |")  # fmt: skip
    for n, r in result["ports"].items():
        if r["examples"]:
            lines += ["", f"## {n} examples", ""] + [f"- `{k}` {e}" for k, v in r["examples"].items() for e in v]
    c = result.get("consensus")
    if c:
        lines += ["", f"## Family consensus ({', '.join(c['family'])}; quorum {c['quorum']:.0%})", "",
                  f"holes {c['holes']}: engine missed {c['engine_missed']}, real divergence {c['divergent']}; "
                  f"possible false edges {c['false_edge_suspects']}", ""]  # fmt: skip
        lines += [f"- missed {m['port']} {m['edge']} ({m['votes']}, {m['shape']}) at {m['at']}" for m in c["missed"]]
        lines += [f"- suspect {s['port']} {s['edge']} ({s['votes']}) at {s['at']}" for s in c["suspects"]]
    return "\n".join(lines) + "\n"


def engine_sha():
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=9", "HEAD"], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() or "unknown"


def _names(arg, default):
    names = [n for n in (arg.split(",") if arg else default) if n]
    if bad := sorted(set(names) - LICENSED):
        raise SystemExit(f"callgraph_oracle: not in the licensed C/C++ port set: {', '.join(bad)}")
    return names


def run(only, family, work, sha):
    """Load each port once; body oracle over ``only``, consensus over ``family`` (both may name the same ports)."""
    loaded, skipped = {}, []
    for name in dict.fromkeys(only + family):
        repo, db = work / "repos" / name, find_db(work / "scans" / sha / name)
        if db is None or not repo.is_dir():
            skipped.append(name)
            continue
        loaded[name] = Port(name, repo, load_port(repo, db, doom_scorer._engine_vendor_test(repo)))
    result = {"engine_sha": sha, "ports": {n: body_oracle(loaded[n]) for n in only if n in loaded}}
    fam = [loaded[n] for n in family if n in loaded]
    result["consensus"] = consensus(fam) if len(fam) > MIN_HOLDERS else None
    return result, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="ports for the body oracle (default: the family; all: every licensed port scanned)")
    ap.add_argument("--family", help="ports that vote in the consensus (default: the vanilla-lineage family)")
    ap.add_argument("--work", type=Path, default=DEFAULT_WORK, help=f"doom_speedrun work dir (default {DEFAULT_WORK})")
    ap.add_argument("--sha", help="engine SHA of the scans to read (default: this checkout's HEAD)")
    ap.add_argument("--baseline", type=Path, help=f"compare with a baseline JSON (e.g. {DEFAULT_BASELINE.name})")
    ap.add_argument("--fail-on-regression", action="store_true", help="with --baseline: exit 1 on any regression")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE, help="allowed recall/precision drop")
    ap.add_argument("--write-baseline", type=Path, help="write the numbers-only baseline JSON here")
    args = ap.parse_args(argv)
    work, sha = args.work.resolve(), args.sha or engine_sha()
    family = _names(args.family, FAMILY)
    if args.only == "all":
        only = sorted(n for n in LICENSED if find_db(work / "scans" / sha / n) is not None)
    else:
        only = _names(args.only, family)
    result, skipped = run(only, family, work, sha)
    for name in skipped:
        print(f"callgraph_oracle: no scan or clone for {name} under {work} at {sha} (run doom_speedrun.py scan)")
    dest = work / "results" / sha
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "callgraph.json").write_text(json.dumps(result, indent=1) + "\n")
    (dest / "callgraph.md").write_text(render(result))
    for n, r in result["ports"].items():
        print(f"{n:16} recall {r['recall']:.4f} precision {r['precision']:.4f} over {r['oracle_calls']} calls")
    if c := result["consensus"]:
        print(f"consensus: holes {c['holes']}, engine missed {c['engine_missed']}, suspects {c['false_edge_suspects']}")
    print(f"wrote {dest / 'callgraph.md'}")
    if args.write_baseline:
        args.write_baseline.write_text(json.dumps(baseline_view(result), indent=1, sort_keys=True) + "\n")
    if args.baseline:
        regs = regressions(result, json.loads(args.baseline.read_text()), args.tolerance)
        for line in regs:
            print(f"REGRESSION {line}")
        if regs and args.fail_on_regression:
            return 1
    return 1 if skipped and args.fail_on_regression else 0


if __name__ == "__main__":
    sys.exit(main())
