#!/usr/bin/env python3
"""C/C++ call-graph validation for the DOOM Port Speedrun corpus (#5630): a tree-sitter body oracle and family consensus.

    python tests/tools/doom_speedrun/callgraph_oracle.py [--only a,b] [--family a,b] [--work DIR] [--sha SHA]
           [--clang] [--baseline FILE --fail-on-regression] [--write-baseline FILE]

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
DOOM-rosetta nightly, #5619). ``--clang`` adds the libclang reference of ``doom_clang_calls.py`` for the C ports
(its recall, precision and the disagreement count in files clang parsed without a fatal error, apart from the files
it could not) and gates the same way against the baseline's ``clang`` section. Licensed ports only: the tool refuses
any port outside ``LICENSED``.
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
    "labeled_statement",  # `abortLine:` at file scope: a label is only ever inside a function (#6266, amethyst)
}  # fmt: skip
CONDITIONAL_NODES = {"preproc_if", "preproc_ifdef"}
TEXT_NODES = {"comment", "string_literal", "raw_string_literal", "char_literal", "concatenated_string"}
# `#define NAME(params) body` (continuation lines joined by the caller): the callees a function-like macro's body names.
MACRO_DEFINE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)\(([^)\n]*)\)[ \t]*((?:[^\n\\]|\\\r?\n|\\.)*)", re.M
)
MACRO_EXPANSION_DEPTH = 4
# A conditional's opening and closing directive lines, to check tree-sitter paired a `#if` with its own `#endif`.
OPENS_CONDITIONAL = re.compile(r"[ \t]*#[ \t]*if")
CLOSES_CONDITIONAL = re.compile(r"[ \t]*#[ \t]*endif\b")
# Text fallback for a region tree-sitter misparsed (an ERROR node, or an ``else if`` split by ``#ifdef`` read as a
# nested function definition): comments and literals blanked, then every ``name (`` that is not a keyword.
STRIP = re.compile(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.S)
# An explicit destructor call (`p->~T(`, `x.~T(`, `T::~T(`) names the unit `~T`, as tree-sitter's destructor_name does.
TEXT_CALL = re.compile(
    r"(?:(?<=->)|(?<=\.)|(?<=::))\s*~\s*([A-Za-z_]\w*)\s*(?:<[^;{}()]*>\s*)?\(|\b([A-Za-z_]\w*)\s*\("
)
# `Type name(args)` in a text-fallback body declares a local (tree-sitter's declaration, never a call to `name`): the
# name follows a type word (optionally `<...>`) and a blank. These words before a name are keywords or Qt statement
# macros, so the name after them is a real call (`return f(x)`, `emit self().changed()`); so is one after an ALL-CAPS word.
DECL_TAIL = re.compile(r"([A-Za-z_]\w*)(?:[ \t]*<[^;{}()]{0,120}>)?[ \t]+\Z")
NOT_A_TYPE = frozenset(
    "return else new delete throw case goto co_return co_await co_yield emit typeid not and or xor".split()
)
# A class or struct definition head: the last word before its `:` base list or `{` is the class name.
# A specialization (`class Box<T, true> : Base<T> {`) carries its template arguments between the name and the `:`.
CLASS_HEAD = re.compile(r"\b(?:class|struct)\b[^;{}()<>]*?\b([A-Za-z_]\w*)\s*(?:<[^;{}()]*>\s*)?(?:final\s*)?[:{]")
# A class head with a base list: `class A : public B, virtual C<T> {` (the entries after the lone `:`).
BASE_LIST = re.compile(r"\b(?:class|struct)\b[^;{}()]*?[^:]:(?!:)([^;{}]*)\{")
BASE_NAME = re.compile(r"([A-Za-z_]\w*)\s*(?:<[^<>]*>)?\s*$")
# A type alias of a class: `typedef Private<PublicType> Base;` / `using Base = Private<P>;`. A constructor initializer
# naming one (`Impl(Public *i) : Base(i)`) calls the aliased base's constructor. Capitalised names only, and only when the
# target is a class the repo declares: `typedef int Bool;` (or `using type = T`) shares its name with a data member `: Bool(v)`.
ALIAS_DECL = re.compile(
    r"\btypedef\b\s*(?:typename\s+)?([A-Za-z_][\w:]*)\s*(?:<[^;{}()]*>)?[\s*&]*([A-Z]\w*)\s*;"
    r"|\busing\s+([A-Z]\w*)\s*=\s*(?:typename\s+)?([A-Za-z_][\w:]*)"
)
CLASS_DECL = re.compile(r"\b(?:class|struct)\s+(?:[A-Z_]+\s+)?([A-Za-z_]\w*)\s*[:{<;]")
ALIASES = ""  # the key of `class_names` that holds the alias names (no class is named "")
CPP_EXTS = frozenset(".h .hh .hpp .hxx .inl .cc .cpp .cxx".split())
KEYWORDS = frozenset(
    "if else while for do switch return sizeof alignof _Alignof defined case goto typeof decltype foreach Q_FOREACH".split()
)  # foreach / Q_FOREACH: Qt loop statements, which tree-sitter reads as a definition of that name


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
        elif (
            fn.type == "dependent_name"
        ):  # `q::template f<T>(x)`: the `template` keyword wraps the template method (#6266)
            fn = fn.named_children[0] if fn.named_children else None
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


def _macro_prefixed_call(n):
    """A bare macro statement (no semicolon) fused with the call after it: tree-sitter reads `MACRO f(x);` inside a
    function body as a declaration of a function `f` returning type `MACRO` (srb2's `HUDONLY`, #6266)."""
    if n.type != "declaration" or n.parent is None or n.parent.type != "compound_statement":
        return False
    return (
        len(n.children) >= 2
        and n.children[0].type == "type_identifier"
        and re.fullmatch(r"[A-Z][A-Z0-9_]+", decode_bytes(n.children[0].text))
        is not None  # a macro, not `OString s(x)`
        and n.children[1].type == "function_declarator"
    )


_LITERAL_CONDITION = re.compile(r"\(*\s*(0[xX]0+|0+|1)\s*\)*")


def _literal_value(cond):
    """True / False for a literal ``#if`` condition (``0``, ``1``, ``(0)``), None for any other (#6266)."""
    m = _LITERAL_CONDITION.fullmatch(cond.strip())
    return None if m is None else m.group(1).strip("0xX") != ""


# The port's feature toggles no file defines (#6266): `Port` installs them before it reads any body, as the engine's
# Orchestrator does for its workers (#6770). Empty decides nothing beyond a literal condition.
_UNSET = frozenset()


def _condition_value(kind, rest):
    """True / False / None for an ``#if``-family directive: a literal, then the engine's own rule over the port's
    never-defined toggles (``#ifdef X`` / ``defined(X)`` of one is false), so the oracle drops what the engine drops."""
    value = _literal_value(rest) if kind in ("if", "elif") else None
    if value is None and _UNSET:
        from gitgalaxy.core.detector import _directive_value

        value = _directive_value(kind, rest, _UNSET)
    return value


def unset_toggles_of(repo, vendored=None):
    """The engine's never-defined toggle table (`preproc_toggles.unset_toggles`) over ``repo``'s C-family and build
    files, chosen as the Orchestrator chooses them; empty when the repo has no C/C++ source. ``vendored`` drops what the
    scan drops: a vendored library's define is not in the engine's table (srb2's libpng `PNG_TEXT_SUPPORTED`)."""
    from gitgalaxy.core.preproc_toggles import unset_toggles
    from gitgalaxy.galaxyscope import Orchestrator as O

    root = Path(repo)
    files = sorted(
        p
        for p in root.rglob("*")
        if ".git" not in p.relative_to(root).parts
        and p.is_file()
        and not (vendored and vendored(p.relative_to(root).as_posix()))
    )
    c_files = [p for p in files if p.suffix.lower() in O._C_SOURCE_EXTS]
    if not any(p.suffix.lower() in (".c", ".cc", ".cpp", ".cxx", ".c++", ".m", ".mm") for p in c_files):
        return frozenset()
    build = [p for p in files if p.name.lower() in O._BUILD_FILE_NAMES or p.suffix.lower() in O._BUILD_FILE_EXTS]

    def texts(group):
        for p in group:
            try:
                yield decode_bytes(p.read_bytes()[:2_000_000])
            except OSError:
                continue

    return unset_toggles(texts(c_files), texts(build))


def _closes_on_its_last_line(n):
    """Whether a ``#if`` / ``#ifdef`` node's own ``#endif`` is its last line. Tree-sitter can pair the ``#if`` with an
    inner ``#endif`` (srb2's M_PNGText) or run past its own; a ``#else`` splitting an ``if`` head (PNG_Read) leaves an
    ERROR node inside instead, which the caller checks."""
    depth = 0
    lines = decode_bytes(n.text).split("\n")
    for i, line in enumerate(lines):
        if OPENS_CONDITIONAL.match(line):
            depth += 1
        elif CLOSES_CONDITIONAL.match(line):
            depth -= 1
            if depth == 0:
                return i == len(lines) - 1
    return False


def _live_children(n):
    """Children of a ``#if`` / ``#elif`` / ``#ifdef`` node the preprocessor keeps: a false condition (literal ``0``, or
    a toggle the port never defines, #6266) drops its own body and keeps the alternative, a true one the reverse. The
    engine drops these branches too (#6770, #6870), so a call there is no call."""
    cond, alt = n.child_by_field_name("condition"), n.child_by_field_name("alternative")
    value = None
    if cond is not None and n.type in ("preproc_if", "preproc_elif"):
        value = _condition_value(n.type.removeprefix("preproc_"), decode_bytes(cond.text))
    elif n.type in ("preproc_ifdef", "preproc_elifdef") and n.children:  # `#ifdef X` / `#ifndef X` of a toggle
        cond = n.child_by_field_name("name")
        kind = decode_bytes(n.children[0].text).lstrip("#").strip()
        value = _condition_value(kind, decode_bytes(cond.text)) if cond is not None else None
    if value is None:
        return n.children
    return [c for c in n.children if c.id != cond.id and (alt is not None and c.id == alt.id) != value]


def _unescaped_quotes(raw):
    """The `"` of a byte string that no backslash escapes, and no `'` char literal holds."""
    text = re.sub(rb"\\.|'(?:[^'\\\n]|\\.)'", b"", raw)
    return text.count(b'"')


def _local_names(node):
    """The variables a function declares, parameters included (`double delta = ..`, `int n`): a name declared as a
    variable in the function is that variable there, never a function of the port."""
    out, stack = set(), [node.child_by_field_name("declarator"), node.child_by_field_name("body")]
    while stack:
        n = stack.pop()
        if n is None or n.type == "function_definition":
            continue
        if n.type in ("init_declarator", "parameter_declaration", "optional_parameter_declaration", "declaration"):
            d = n.child_by_field_name("declarator")
            while d is not None and d.type in ("pointer_declarator", "reference_declarator", "array_declarator"):
                d = d.child_by_field_name("declarator") or next(iter(d.named_children), None)
            if d is not None and d.type == "identifier":
                out.add(decode_bytes(d.text))
        stack.extend(n.children)
    return out


class Body:
    """One function body: its calls (name -> shape of the first call), other identifier references, preprocessor and
    comment/literal text."""

    def __init__(self, node, classes=None):
        self.node = node
        self.calls, self.refs, self.preproc, self.text_only, self.types = {}, set(), [], [], set()
        self.broken = False  # an ERROR node inside: tree-sitter may have closed the body early
        self.unbalanced = False  # a conditional not ending at its own `#endif`, or holding a stray `#else`: misread
        self.nested = []  # 1-based last lines of real nested definitions (methods, or functions a misparse ran over)
        # an ERROR holding an odd number of `"`: tree-sitter lost the string boundaries (doomsday's `_E(b) "%s" _E(.)`),
        # so the literal nodes after it no longer mark text and calls (`name()`) are read as string content (#6266)
        self.desynced = False
        locals_ = _local_names(node)
        callees = set()
        for init in _initializers(node):  # `: Base(x), member(y)`: a base class entry is a constructor call
            name = callee_node(init.children[0]) if init.children else None
            if name is None and init.children and init.children[0].type == "template_type":
                name = init.children[0].child_by_field_name("name")  # `: TMap<K, V>(), info(x)`: a templated base
            if name is not None and decode_bytes(name.text) in _bases(classes or {}, node):
                self.calls.setdefault(decode_bytes(name.text), "ctor-init")
        for (
            err
        ) in node.children:  # `ID_INLINE Cls(x) : Base() {`: an unknown macro before the name makes the list an ERROR
            if err.type == "ERROR" and decode_bytes(err.text).lstrip().startswith(":"):
                head = decode_bytes(err.text)
                for name in _head_initializer_names(head):
                    if name in _bases(classes or {}, node):
                        self.calls.setdefault(name, "ctor-init")
        body = node.child_by_field_name("body") or node
        stack = [body]
        # `span_constexpr span(Cont &c) : size_(f(c)) {}`: an unknown macro before the name leaves the signature and the
        # initializer list as ERROR children outside the body: read its arguments from the head text, as TextBody does (#6266)
        if not _initializers(node) and any(
            err.type == "ERROR" and err.start_byte < body.start_byte for err in node.children
        ):
            head = re.split(r"[;}]", decode_bytes(node.text[: body.start_byte - node.start_byte]))[
                -1
            ]  # past a folded neighbour
            self._text_calls(_head_initializer_arguments(head).encode())
        for init in _initializers(node):  # `d(new Impl(this))`, `base(f(x))`: the arguments are part of the constructor
            stack.extend(init.children[1:])
        while stack:
            n = stack.pop()
            if n.type in ("preproc_if", "preproc_elif", "preproc_ifdef", "preproc_elifdef"):
                if n.type in ("preproc_if", "preproc_ifdef") and (n.has_error or not _closes_on_its_last_line(n)):
                    self.unbalanced = True
                stack.extend(reversed(_live_children(n)))
                continue
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
            elif _macro_prefixed_call(n):  # `HUDONLY\n lua_getfield(L, 1);` reads as a declaration of that name
                self._text_calls(n.text)
            elif n.type == "ERROR":
                self.broken = True
                self.desynced |= _unescaped_quotes(n.text) % 2 == 1
                self._text_calls(n.text)
            elif (
                n.type == "call_expression"
                and (fn := n.child_by_field_name("function")) is not None
                and fn.type == "template_function"
                and (name := callee_node(fn)) is not None
                and decode_bytes(name.text) in locals_
            ):  # `delta < eps || delta > (360 - eps)` on a local `double delta` parses as `delta<..>(..)`: comparisons
                self.refs.add(decode_bytes(name.text))
                stack.extend(reversed(n.children[1:]))
                stack.extend(reversed(fn.children[1:]))
                continue
            elif n.type == "call_expression":
                name = callee_node(n.child_by_field_name("function"))
                if name is not None and decode_bytes(name.text) not in KEYWORDS:  # `SERVER_ONLY(\n if (x) {..})`
                    # `p->~T<A>()`: the destructor's unit is `~T`, template arguments dropped
                    self.calls.setdefault(decode_bytes(name.text).split("<", 1)[0], shape(n))
                    callees.add(name.id)
            elif n.type == "destructor_name" and n.id not in callees and _templated_dtor(n):
                self.calls.setdefault(decode_bytes(n.text), "statement")  # `p->~T<A>()` parses as `p->~T < A > ()`
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
            name = "~" + m.group(1) if m.group(1) else m.group(2)
            if m.group(2) and _declares_local(text, m.start(2)):
                continue
            if name not in KEYWORDS:
                self.calls.setdefault(name, "unparsed")

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


# A preprocessor directive with its `\`-continued lines: a macro defined inside a function is not that function's calls
# (the engine blanks it too, #6793; the tree-sitter walk skips the node). A CRLF source continues with CR LF.
DIRECTIVE = r"^[ \t]*#(?:[^\n]*\\\r?\n)*[^\n]*$"


def _head_has_statement(head):
    """A `;` inside braces before the body's own brace: the head swallowed the body's statements (a default argument
    `= {}` in the parameter list is balanced and holds none)."""
    paren = brace = 0
    for ch in STRIP.sub(" ", head):
        paren += (ch == "(") - (ch == ")")
        brace += (ch == "{") - (ch == "}")
        if ch == ";" and paren <= 0 and brace > 0:
            return True
    return False


def _declares_local(text, pos):
    """True when the name at ``pos`` follows a type word, so ``Type name(args)`` declares a local, not a call."""
    tail = DECL_TAIL.search(text[max(0, pos - 160) : pos])
    return tail is not None and tail.group(1) not in NOT_A_TYPE and not tail.group(1).isupper()  # HUDONLY f(x): a macro


def _ends_in_continued_line(lines, end_line):
    """True when the tree-sitter node's last line continues a backslash: a `#define` body closed the function early (srb2's
    `SETUP3DVERT` inside `HWR_RenderPlane`: the macro's own `}` ended the node, #6266)."""
    return end_line >= 2 and lines[end_line - 2].rstrip().endswith("\\")


LOCAL_CLASS_OPEN = re.compile(r"\b(?:class|struct)\s+[A-Za-z_]\w*[^;{}()]*\{")


def _blank_local_classes(body):
    """``body`` with the braces of each local ``class X : Base { ... }`` blanked (newlines kept): its methods own their
    calls (a CONSOLE_COMMAND macro body that declares `class idSWFScriptFunction_Continue`, doom3-bfg, #6266)."""
    out, pos = [], 0
    while (m := LOCAL_CLASS_OPEN.search(body, pos)) is not None:
        depth, i = 1, m.end()
        while i < len(body) and depth:
            depth += (body[i] == "{") - (body[i] == "}")
            i += 1
        out.append(body[pos : m.end()] + re.sub(r"[^\n]", " ", body[m.end() : i]))
        pos = i
    return "".join(out) + body[pos:]


_BRANCH_DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(if|elif|else|endif|ifdef|ifndef)\b([^\n]*)$", re.M)


def _blank_dead_branches(text):
    """``text`` with the lines of every literal ``#if 0`` / ``#if 1 ... #else`` dead branch emptied (newlines kept)."""
    out, pos, stack, live = [], 0, [], True  # frame: [enclosing live, a branch was already taken, decided]
    for m in _BRANCH_DIRECTIVE.finditer(text):
        out.append(text[pos : m.start()] if live else re.sub(r"[^\n]", " ", text[pos : m.start()]))
        pos = m.start()
        kind, rest = m.group(1), m.group(2).split("//", 1)[0]
        if kind in ("if", "ifdef", "ifndef"):
            value = _condition_value(kind, rest)
            stack.append([live, value is True])
            live = live and value is not False
        elif kind in ("elif", "else") and stack:
            frame = stack[-1]
            value = True if kind == "else" else _condition_value(kind, rest)
            live = frame[0] and not frame[1] and value is not False
            frame[1] = frame[1] or value is True
        elif kind == "endif" and stack:
            live = stack.pop()[0]
    out.append(text[pos:] if live else re.sub(r"[^\n]", " ", text[pos:]))
    return "".join(out)


class TextBody(Body):
    """Fallback for a function tree-sitter folds into a neighbour (a macro table above it with no semicolon): the
    brace-matched body from its start line, comments and literals blanked, preprocessor lines dropped; every call is
    shape ``unparsed``. Also used when a bare macro statement (``ADD_FILE_COUNTER`` with no semicolon) makes tree-sitter
    close the body early: ``end_line`` says whether the braces reach further."""

    def __init__(self, src, line, classes=None):
        self.node, self.calls, self.refs, self.preproc, self.text_only, self.types = None, {}, set(), [], [], set()
        self.broken = False
        self.open_line = line
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
        self.open_line = line + text.count("\n", 0, open_at)
        body = text[open_at : end + 1]
        self.preproc = re.findall(DIRECTIVE, body, flags=re.M)
        body = _blank_dead_branches(body)
        body = re.sub(DIRECTIVE, " ", body, flags=re.M)
        body = _blank_local_classes(body)  # a local class's methods are their own units (as in Body)
        if MACRO_CLASS_HEAD.match(lines[line - 1]):
            self._text_calls(_member_initializers(body).encode())
        else:
            self._text_calls(body.encode())
        head = text[:open_at]
        ctor = re.match(
            r"\s*(?:[\w:<>~*&\s]*?[\s*&:])?([A-Za-z_]\w*)\s*\(", head
        )  # a constructor is named for its class
        classes = classes or {}
        known = set()
        if ctor and ctor.group(1) in classes:
            known = classes[ctor.group(1)] | classes.get(ALIASES, set())
        elif (
            ctor
        ):  # a constructor of no class the repo declares (`Impl` of a macro-headed DE_PIMPL): as `_bases`, any base
            known = set().union(*classes.values())
        for name in _head_initializer_names(head):
            if name in known:
                self.calls.setdefault(name, "ctor-init")
        args = _head_initializer_arguments(head)  # `_n(std::move(v))`: part of the constructor
        news = re.compile(r"\bnew\s+(?:[A-Za-z_]\w*\s*::\s*)*([A-Za-z_]\w*)")  # `d(new Impl(this))`: a type, as in Body
        self.types |= set(news.findall(args))
        self._text_calls(news.sub(" ", args).encode())
        trailing = re.search(r"\)[\w\s&]*->(?!\*)(.*)$", head, flags=re.S)  # `auto f() -> C<bool, g<T>()> {}`
        if trailing:
            self._text_calls(trailing.group(1).encode())
            for name in re.findall(r"\b([A-Za-z_]\w*)\s*<[^;{}()<>]*>\s*\(", trailing.group(1)):  # `g<T>()`
                if name not in KEYWORDS:
                    self.calls.setdefault(name, "unparsed")
        self.refs = set(re.findall(r"\b[A-Za-z_]\w*\b", body)) - set(self.calls)
        self.text_only = [m.group(0) for m in STRIP.finditer(raw[open_at : end + 1])]


def _head_initializer_names(head):
    """The names a constructor head's initializer list calls (`A(i) : ui::Base(i), m(x)` -> Base, m), qualifiers dropped."""
    depth, names, listed = 0, [], False
    for m in re.finditer(r"::|[:()]|[A-Za-z_]\w*", head):
        tok = m.group(0)
        if tok == "(":
            depth += 1
            if depth == 1 and listed and (prev := head[: m.start()].rstrip()[-1:]) and (prev.isalnum() or prev in "_>"):
                names.append(re.search(r"([A-Za-z_]\w*)\s*(?:<[^<>]*>)?\s*$", head[: m.start()]).group(1))
        elif tok == ")":
            depth -= 1
        elif tok == ":" and depth == 0:
            listed = True
    return names


def _head_initializer_arguments(head):
    """The text inside each entry of a constructor head's initializer list (`: Base(f(x)), m(g(y))` -> `f(x) g(y)`): the
    arguments are calls of the constructor, the entry names are not (a base class is read by `_head_initializer_names`)."""
    depth, listed, out = 0, False, []
    for m in re.finditer(r"::|[:()]|[^:()]+", head):
        tok = m.group(0)
        if tok == "(":
            depth += 1
            if depth > 1 and listed:
                out.append(tok)
        elif tok == ")":
            depth -= 1
            if depth >= 1 and listed:
                out.append(tok)
            elif depth == 0 and listed:
                out.append(" ; ")  # entries apart: `a` then `(x)` of the next must not read as a call `a(x)`
        elif tok == ":" and depth == 0:
            listed = True
        elif listed and depth >= 1:
            out.append(tok)
    return "".join(out)


def _templated_dtor(name):
    """True for the `~T` of `p->~T<A>()`, which tree-sitter reads as the comparison `p->~T < A > ()`."""
    field = name.parent
    after = field.next_sibling if field is not None and field.type == "field_expression" else None
    return after is not None and after.type == "<"


def _initializers(node):
    """The ``field_initializer`` entries of a constructor's initializer list (a child of the definition, not of its body)."""
    for child in node.children:
        if child.type == "field_initializer_list":
            return [c for c in child.children if c.type == "field_initializer"]
    return []


def _owner(node):
    """The class a constructor definition belongs to: the scope of ``Cls::Cls``, else the class body it sits in. A
    qualified name wins over the enclosing class, and a constructor named for another class is no member of it: a class
    body tree-sitter fails to close (doomsday's ``DE_GUI_PIMPL`` holding a nested class) swallows the definitions below
    it, ``PackagesWidget::PackagesWidget`` and ``Impl(Public *i)`` among them (#6266)."""
    decl = node.child_by_field_name("declarator")
    while decl is not None and decl.type not in ("qualified_identifier", "identifier", "field_identifier"):
        decl = decl.child_by_field_name("declarator")
    if decl is not None and decl.type == "qualified_identifier":
        scope = decl.child_by_field_name("scope")
        while (inner := decl.child_by_field_name("name")) is not None and inner.type == "qualified_identifier":
            decl, scope = inner, inner.child_by_field_name("scope") or scope  # `A::B::B` nests: the innermost scope
        return bare(decode_bytes(scope.text)) if scope is not None else None
    up = node.parent
    while up is not None:
        if up.type in ("class_specifier", "struct_specifier"):
            name = up.child_by_field_name("name")
            owner = decode_bytes(name.text).split("<")[0].strip() if name is not None else None  # `Box<T, true>` -> Box
            if decl is not None and _initializers(node) and decode_bytes(decl.text) != owner:
                return None  # only a constructor has an initializer list, and it is named for its own class
            return owner
        up = up.parent
    return None


class Classes(dict):
    """`class_names`: class -> the bases its head lists, plus ``declared``, every class some head defines."""

    declared = frozenset()


def _bases(classes, node):
    """The base classes its owner lists (every listed base when the owner is not found, or is a class no C++ source
    of the repo defines: a class whose header was dropped, read as `TextBody` reads such a constructor, #6266)."""
    owner = _owner(node)
    if owner in classes:
        return classes[owner] | classes.get(ALIASES, set())
    if owner is None or (isinstance(classes, Classes) and owner not in classes.declared):
        return set().union(*classes.values())
    return classes.get(ALIASES, set())


# The wrapper suffixes the engine reads through to the language beneath (`language_lens.SAFE_WRAPPERS`): it scans a
# `sdlnativefont.cpp.old` as C++, so the class its `sdlnativefont.h.old` declares is a class of the scan (#6266).
WRAPPER_EXTS = frozenset(".template .tmpl .bak .old .orig .dist .gen .in".split())


def _cpp_ext(filename):
    """The extension a file is read as: `x.h.old` -> `.h`, as the engine maps it."""
    stem, ext = os.path.splitext(filename)
    if ext.lower() in WRAPPER_EXTS and os.path.splitext(stem)[1]:
        return os.path.splitext(stem)[1].lower()
    return ext.lower()


def class_names(repo, vendored=None):
    """class -> the base classes its head lists, over a repo's C++ files: what a base-class initializer entry names (a
    data member `: type(t)` is no call, even when a vendored class elsewhere shares its name). Key ``ALIASES`` holds the
    repo's class-typedef names (`Base`). ``vendored`` (a relpath -> bool test) drops a bundled library's files: its
    `typedef GenericValue<..> Value;` must not make every first-party member `: Value(v)` a base call."""
    texts = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if _cpp_ext(f) in CPP_EXTS:
                if vendored and vendored(os.path.relpath(Path(root) / f, repo).replace("\\", "/")):
                    continue
                try:
                    texts.append(decode_bytes((Path(root) / f).read_bytes()))
                except OSError:
                    continue
    return class_names_of_text(*texts)


def _alias_owner(text, heads, pos):
    """The class an alias declared at `pos` is a member of (the nearest class head before it that opens the same line
    or sits at a lesser indent), None for a namespace-scope alias at column 0."""
    line_start = text.rfind("\n", 0, pos) + 1
    indent = pos - line_start
    if indent == 0:
        return None
    for at, name in reversed(heads):
        if at >= pos:
            continue
        head_start = text.rfind("\n", 0, at) + 1
        if head_start == line_start or len(text[head_start:at]) - len(text[head_start:at].lstrip()) < indent:
            return name
    return None


def _split_bases(listing):
    """A base list's entries: split at top-level commas only (`TArray<T, TT>` is one entry)."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(listing):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(listing[start:i])
            start = i + 1
    parts.append(listing[start:])
    return parts


def class_names_of_text(*texts):
    """``class_names`` over source texts."""
    bases_of: dict[str, set[str]] = {}
    declared, defined, aliases = set(), set(), []
    for text in texts:
        clean = STRIP.sub(" ", text)
        declared.update(CLASS_DECL.findall(clean))
        defined.update(m.group(1) for m in CLASS_HEAD.finditer(clean))  # a definition head, not `class X;`
        heads = [(m.start(), m.group(1)) for m in CLASS_DECL.finditer(clean)]
        aliases.extend(
            (m.group(2) or m.group(3), m.group(1) or m.group(4), _alias_owner(clean, heads, m.start()))
            for m in ALIAS_DECL.finditer(clean)
        )
        for head in BASE_LIST.finditer(clean):
            owner = CLASS_HEAD.search(head.group(0))
            if owner is None:
                continue
            bases_of.setdefault(owner.group(1), set()).update(
                m.group(1) for b in _split_bases(head.group(1)) if "std::" not in b and (m := BASE_NAME.search(b))
            )
    for name, target, owner in aliases:  # a member alias is the base name only inside its own class
        if owner is not None and target.rsplit("::", 1)[-1] in declared:
            bases_of.setdefault(owner, set()).add(name)
    bases_of[ALIASES] = {
        name for name, target, owner in aliases if owner is None and target.rsplit("::", 1)[-1] in declared
    }
    out = Classes(bases_of)
    out.declared = frozenset(defined)
    return out


# Macro statements that take a body, like `for` (doomsday's `DE_FOR_EACH_CONST(T, i, c) { ... }`, `DE_NOTIFY_PUBLIC(N, i) ...`,
# gzdoom's `IFVIRTUALPTRNAME(o, "C", F) { ... }`): tree-sitter reads one as a nested definition, the engine as a statement
# of its function (#5630).
MACRO_STATEMENT = re.compile(
    r"DE_(?:FOR_(?:EACH|OBSERVERS)|NOTIFY)[A-Z_]*|IF(?:VM|(?:OVERRIDEN)?VIRTUAL(?:PTR)?(?:NAME)?)"
)


def _has_toplevel_semicolon(head):
    """A `;` outside every bracket pair: a lambda in a constructor initializer (`c ? c : [] { return x; }`) has its own."""
    depth = 0
    for ch in head:  # bytes: ints
        if ch in b"({[":
            depth += 1
        elif ch in b")}]":
            depth -= 1
        elif ch == 59 and depth <= 0:
            return True
    return False


def _is_real_nested_function(node):
    """A nested ``function_definition`` that is a function (a GNU C nested function), not the ``else if (...) {`` that
    ``#ifdef`` splitting makes tree-sitter read as one (its type or declarator name is a keyword) nor a macro statement."""
    kind = node.child_by_field_name("type")
    decl = node.child_by_field_name("declarator")
    body = node.child_by_field_name("body")
    head = node.text[: body.start_byte - node.start_byte] if body is not None else node.text
    if _has_toplevel_semicolon(
        head
    ):  # `CLEAR_MEMORY(a, bool, 16);\n stmt;\n ...`: statements read as a head (edge-classic)
        return False
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
    if nxt is not None and nxt.type in CONDITIONAL_NODES:  # `#ifdef X if (..) {..} #endif` right after the closed body
        nxt = next((c for c in nxt.children if c.type in STATEMENT_NODES), nxt)
    return (
        node.parent is not None
        and (node.parent.type == "translation_unit" or node.parent.type in CONDITIONAL_NODES)
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


def macro_body_callees(repo, vendored=None):
    """Function-like macro name -> the words before ``(`` in its body, over every C-family file of ``repo``.

    Tree-sitter reads a macro invocation as a call to the macro, so a function's lexical body never holds the calls the
    macro expands to (#6770). A name two files define differently is left out, as the compiler's expansion depends on
    which definition a unit sees (crispy-doom's per-game `FTOM`): the oracle claims only what every definition agrees on."""
    table, conflicted = {}, set()
    root = Path(repo)
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".c", ".h", ".cc", ".cpp", ".hpp", ".inl"} or not path.is_file():
            continue
        if vendored and vendored(path.relative_to(root).as_posix()):
            continue
        try:
            text = decode_bytes(path.read_bytes())
        except OSError:
            continue
        for m in MACRO_DEFINE.finditer(text):
            params = {x.strip() for x in m.group(2).split(",")}
            body = STRIP.sub(" ", m.group(3).replace("\\\n", " "))
            calls = {c for c in re.findall(r"\b([A-Za-z_]\w*)\s*\(", body) if c not in params}
            if table.setdefault(m.group(1), calls) != calls:
                conflicted.add(m.group(1))
    return {n: c for n, c in table.items() if n not in conflicted}


def macro_reaches(table, invoked, callee):
    """True when a macro among ``invoked`` expands (through macros that call macros, bounded) to a call of ``callee``."""
    level, seen = {n for n in invoked if n in table}, set()
    for _ in range(MACRO_EXPANSION_DEPTH):
        if any(callee in table[n] for n in level):
            return True
        seen |= level
        level = {c for n in level for c in table[n] if c in table} - seen
    return False


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
        self.macros = macro_body_callees(self.repo, doom_scorer._engine_vendor_test(self.repo))
        global _UNSET
        _UNSET = unset_toggles_of(self.repo, doom_scorer._engine_vendor_test(self.repo))
        trees = {}
        classes = (
            class_names(self.repo, doom_scorer._engine_vendor_test(self.repo))
            if any(r[1] == "cpp" for r in rows)
            else {}
        )
        split_lines = {}
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
            body = Body(node, classes) if node is not None else TextBody(src, start, classes)
            if node is not None and not body.broken:
                # tree-sitter closed the node inside a `#define` body (srb2's `SETUP3DVERT`), or opened its body at a
                # later brace than the function's own (`HUDONLY\n f(x);` fused into the head, #6266): the braces win
                lines = split_lines.setdefault(key, decode_bytes(src).split("\n"))
                ends, opens = node.end_point[0] + 1, node.child_by_field_name("body")
                late = opens is not None and _head_has_statement("\n".join(lines[start - 1 : opens.start_point[0]]))
                if late or _ends_in_continued_line(lines, ends):
                    braces = TextBody(src, start, classes)
                    if braces.calls is not None and (
                        braces.open_line < opens.start_point[0] + 1 if late else braces.end_line > ends
                    ):
                        body = braces
            if node is not None and not isinstance(body, TextBody) and body.unbalanced:
                # srb2's M_PNGText / PNG_Read: tree-sitter paired a conditional with the wrong `#endif`, so a dead
                # branch spills into the live body or the reverse; the text view pairs directives by line (#6266),
                # when its braces agree on where the function ends (eternity's concurrentqueue: they run past it)
                braces = TextBody(src, start, classes)
                if braces.calls is not None and braces.end_line == node.end_point[0] + 1:
                    body = braces
            if node is not None and getattr(body, "desynced", False):
                braces = TextBody(src, start, classes)  # the text view blanks literals by their own quotes
                if braces.calls is not None and braces.end_line == node.end_point[0] + 1:
                    body = braces
            head_row = getattr(node, "start_point", (start - 1,))[0]  # (a test's stand-in node has only the end)
            if node is not None and head_row + 1 < start and not isinstance(body, TextBody):
                # the node's head starts lines above the function and runs over declarations (`;` at its top level):
                # doomsday's class-scope `DE_AUDIENCE(Name, void f(T &))` with no `;` became a head with an initializer
                # list down to the next inline method, whose own calls are read from its braces (#6266)
                above = src.split(b"\n")[head_row : start - 1]
                if _has_toplevel_semicolon(b"\n".join(above)):
                    braces = TextBody(src, start, classes)
                    if braces.calls is not None and braces.end_line == node.end_point[0] + 1:
                        body = braces
            if node is not None and body.broken:
                braces = TextBody(src, start, classes)
                # end_point[0], never .row: .row on the temporary Point read freed memory (tree-sitter 0.26, #5630).
                # Braces ending earlier: the node ran over the code below (srb2's bare macro statements, MSVC __asm,
                # #6266), unless the braces hold whole methods (a broken DE_PIMPL class: their calls are theirs)
                ends = node.end_point[0] + 1
                # A macro class is read by its braces anyway: TextBody keeps only its member initializers.
                macro_class = bool(MACRO_CLASS_HEAD.match(src.split(b"\n")[start - 1].decode("latin-1")))
                earlier = braces.end_line < ends and (macro_class or all(row > braces.end_line for row in body.nested))
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
    expanded = 0
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
            if kind in ("absent", "macro", "comment/string") and macro_reaches(port.macros, body.calls, callee):
                expanded += 1  # a macro this body invokes expands to the call (#6770): not a false edge
                kind = "macro-expansion"
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
        "precision": round(agree / (n_eng - expanded), 4) if n_eng - expanded else 1.0,
        "macro_expansion_calls": expanded,
        "misses_by_shape": dict(misses.most_common()),
        "engine_only_by_kind": dict(extra.most_common()),
        "examples": {k: v for k, v in sorted(examples.items())},
    }


def _presence(port, a, b, expanded=False):
    """How ``b`` appears in the body of ``a``. ``expanded`` also counts a call a macro of that body expands to (#6770):
    right for clearing an engine edge as a false-edge suspect, wrong for a hole (a macro call inside a dead `#if 0`
    would read as an engine miss)."""
    hits = [f[4].presence(b) for f in port.bodies(a)]
    if expanded:
        hits = [
            h or ("macro-expansion" if macro_reaches(port.macros, f[4].calls, b) else None)
            for h, f in zip(hits, port.bodies(a))
        ]
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
            why, f = _presence(p, a, b, expanded=True)
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
    if current.get("clang") is not None:  # compared only when this run asked for it (--clang)
        out += clang_regressions(current["clang"], baseline.get("clang", {}), tol)
    return out


def clang_regressions(current, baseline, tol=TOLERANCE):
    """Regressions of the libclang reference: recall / precision drops, and more disagreements in clean files.

    The count of disagreements in files with a fatal parse error is left out on purpose: it moves with the clone's
    missing headers, not with the engine."""
    out = []
    for name, base in sorted(baseline.items()):
        cur = current.get(name)
        if cur is None:
            out.append(f"clang {name}: in the baseline, not in this run")
            continue
        for key in ("recall", "precision"):
            if cur[key] < base[key] - tol:
                out.append(f"clang {name}: {key} {base[key]:.4f} -> {cur[key]:.4f}")
        if cur["disagreements_in_clean_files"] > base["disagreements_in_clean_files"]:
            out.append(f"clang {name}: disagreements in clean files {base['disagreements_in_clean_files']}"
                       f" -> {cur['disagreements_in_clean_files']}")  # fmt: skip
    return out


CLANG_KEYS = (
    "clang_edges",
    "engine_edges",
    "agree",
    "recall",
    "precision",
    "files_fatal",
    "disagreements_in_clean_files",
)


def clang_view(clang):
    """Numbers only (no example lists) of ``doom_clang_calls.run_port`` results, for the baseline."""
    return {n: {k: r[k] for k in CLANG_KEYS} for n, r in clang.items()}


def run_clang(ports, work, sha):
    """The libclang reference over the C ports among ``ports`` that have a scan: ({port: result}, why-not or None)."""
    import doom_clang_calls  # lazy: it imports this module, and libclang is optional

    if doom_clang_calls.clang_callgraph.libclang_version() is None:
        return {}, "libclang is not installed"
    out = {}
    for name in ports:
        if name in doom_clang_calls.C_PORTS and (res := doom_clang_calls.run_port(name, work, sha)) is not None:
            out[name] = res
    return out, None


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
                "macro_expansion_calls",
                "misses_by_shape",
                "engine_only_by_kind",
            )
        }  # fmt: skip
        for n, r in result["ports"].items()
    }
    out = {"engine_sha": result["engine_sha"], "ports": ports}
    if result.get("clang"):
        out["clang"] = clang_view(result["clang"])
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
    ap.add_argument(
        "--clang", action="store_true", help="also run the libclang reference on the C ports (needs libclang)"
    )
    ap.add_argument("--write-baseline", type=Path, help="write the numbers-only baseline JSON here")
    args = ap.parse_args(argv)
    work, sha = args.work.resolve(), args.sha or engine_sha()
    family = _names(args.family, FAMILY)
    if args.only == "all":
        only = sorted(n for n in LICENSED if find_db(work / "scans" / sha / n) is not None)
    else:
        only = _names(args.only, family)
    result, skipped = run(only, family, work, sha)
    no_clang = None
    if args.clang:
        result["clang"], no_clang = run_clang(only, work, sha)
        if no_clang:
            print(f"callgraph_oracle: --clang skipped: {no_clang}")
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
    for n, r in result.get("clang", {}).items():
        print(f"{n:16} clang recall {r['recall']:.4f} precision {r['precision']:.4f} over {r['clang_edges']} edges, "
              f"{r['disagreements_in_clean_files']} disagreements in clean files ({r['files_fatal']} fatal-error files)")  # fmt: skip
    if args.write_baseline:
        view = baseline_view(result)
        if not args.clang and args.write_baseline.is_file():  # a run without --clang keeps the committed clang numbers
            if old := json.loads(args.write_baseline.read_text()).get("clang"):
                view["clang"] = old
        args.write_baseline.write_text(json.dumps(view, indent=1, sort_keys=True) + "\n")
    if args.baseline:
        regs = regressions(result, json.loads(args.baseline.read_text()), args.tolerance)
        for line in regs:
            print(f"REGRESSION {line}")
        if regs and args.fail_on_regression:
            return 1
    return 1 if (skipped or no_clang) and args.fail_on_regression else 0


if __name__ == "__main__":
    sys.exit(main())
