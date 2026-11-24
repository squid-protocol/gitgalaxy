"""Tree-sitter oracle spec for C++ (grammar: cpp), batch C of the keyword-family validity tool (#8863).

Import after `family_oracle_ts` is on sys.path; `register()` adds `cpp` to `family_oracle_ts.SPECS` and installs `CppOracle`. The base
`TreeSitterOracle` reads C++ names and parameters like C (see `family_oracle_ts._name` / `_params`); what it cannot say is that
`std::cout << x` is a stream write and not a left shift, so `CppOracle.count` re-reads every `<<` / `>>` chain whose leftmost operand is a
standard stream: it is one `print` (or an input read, `io`, for `cin >>`) and no `bitwise`. A `catch` is a handler, not a branch (the
`branch` contract), so it is absent from the branch set. Callee lists are the author's reading of gitgalaxy/standards/signal_contracts.py.
Pattern syntax is `family_oracle_ts._matches`: a bare name matches the last segment, `a::b` the exact or suffixed qualified name.
"""

from __future__ import annotations

import family_oracle_ts as fts
from family_oracle_ts import Spec, TreeSitterOracle, _fs, _text

_CPP_CALLS = {
    "print": (
        "printf",
        "fprintf",
        "puts",
        "putchar",
        "perror",
        "vprintf",
        "vfprintf",
        "fputs",
        "fputc",
        "putc",
        "std::print",
        "std::println",
    ),
    "sleep": ("sleep", "usleep", "nanosleep", "Sleep", "sleep_for", "sleep_until"),
    "regex": (
        "regcomp",
        "regexec",
        "std::regex_match",
        "std::regex_search",
        "std::regex_replace",
    ),
    "time": (
        "time",
        "clock",
        "gettimeofday",
        "clock_gettime",
        "localtime",
        "gmtime",
        "strftime",
        "difftime",
        "mktime",
        "std::chrono::system_clock::now",
        "std::chrono::steady_clock::now",
        "std::chrono::high_resolution_clock::now",
    ),
    "io": (
        "fopen",
        "fread",
        "fwrite",
        "fclose",
        "open",
        "read",
        "write",
        "close",
        "socket",
        "send",
        "recv",
        "connect",
        "accept",
        "bind",
        "listen",
        "fgets",
        "fscanf",
        "fseek",
        "mmap",
        "std::getline",
    ),
    "bailout": ("exit", "abort", "_exit", "_Exit", "quick_exit", "std::terminate", "std::exit", "std::abort"),
}

_CTOR_IO = frozenset({"std::ifstream", "std::ofstream", "std::fstream"})
_CTOR_REGEX = frozenset({"std::regex", "std::basic_regex"})
_OUT_STREAMS = frozenset({"cout", "cerr", "clog"})
_IN_STREAMS = frozenset({"cin"})

CPP = Spec(
    "cpp",
    (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
    _fs("function_definition"),
    _fs("lambda_expression"),
    _fs(
        "if_statement",
        "for_statement",
        "for_range_loop",
        "while_statement",
        "do_statement",
        "case_statement",
        "conditional_expression",
    ),
    _fs("throw_statement"),
    _fs("call_expression"),
    _CPP_CALLS,
    skip_families=_fs("struct_closures"),
)


def _leftmost(node):
    while node is not None and node.type == "binary_expression":
        node = node.child_by_field_name("left")
    return node


def _stream_kind(node) -> str | None:
    """`out` / `in` when `node` is a `<<` / `>>` chain that starts at a standard stream, else None."""
    if node.type != "binary_expression":
        return None
    op = _text(node.child_by_field_name("operator"))
    if op not in ("<<", ">>"):
        return None
    base = _text(_leftmost(node)).replace("std::", "").strip()
    if op == "<<" and base in _OUT_STREAMS:
        return "out"
    if op == ">>" and base in _IN_STREAMS:
        return "in"
    return None


def _extra_params(fn) -> int:
    """Parameters the base C reading misses: defaulted (`int b = 1`), pack (`Args... a`) and a bare C-style `...`."""
    d = fn.child_by_field_name("declarator")
    while d is not None and d.type != "function_declarator":
        d = fts._inner(d)
    params = d.child_by_field_name("parameters") if d is not None else None
    if params is None:
        return 0
    return sum(
        1
        for c in params.children
        if c.type in ("optional_parameter_declaration", "variadic_parameter_declaration", "...")
    )


def _declared_type(node) -> str:
    """`std::ifstream in("x")` is a declaration, not a call: read the type it constructs."""
    if node.type != "declaration":
        return ""
    return "".join(_text(node.child_by_field_name("type")).split())


class CppOracle(TreeSitterOracle):
    def count(self, fn):
        n, tokens = super().count(fn)
        extra = _extra_params(fn)
        if extra:
            n["args"] += extra
        stack = list(fn.children)
        while stack:
            node = stack.pop()
            stack.extend(node.children)
            ctor = _declared_type(node)
            for key, pats in (("io", _CTOR_IO), ("regex", _CTOR_REGEX)):
                if ctor in pats:
                    n[key] += 1
                    tokens[key][ctor] += 1
            kind = _stream_kind(node)
            if kind is None:
                continue
            op = _text(node.child_by_field_name("operator"))
            n["bitwise"] -= 1  # the base oracle counted this operator as a shift
            tokens["bitwise"][op] -= 1
            parent = node.parent
            if parent is not None and _stream_kind(parent) == kind:
                continue  # only the outermost link of a chain is the one write / read
            key = "print" if kind == "out" else "io"
            n[key] += 1
            tokens[key]["cout" if kind == "out" else "cin"] += 1
        for key in [k for k, v in n.items() if v <= 0 and k == "bitwise"]:
            del n[key]
        for key in [k for k, v in tokens.items() if not +v]:
            del tokens[key]
        return n, tokens


def register() -> None:
    """Add C++ to family_oracle_ts (idempotent)."""
    fts.SPECS["cpp"] = CPP
    fts._ORACLES["cpp"] = CppOracle(CPP)
