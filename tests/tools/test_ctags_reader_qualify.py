"""Regression test for ctags_reader.py's tcl namespace-qualification fix.

tcl/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter] (93 occurrences, all in
macports_port_api/*.tcl): GitGalaxy's func_start and tree-sitter-tcl both read a namespace-
qualified proc's full identifier straight out of the source text (`proc portfetch::percent_encode
{str} {` -> `portfetch::percent_encode`), matching each other exactly; ctags splits it into a bare
`name:percent_encode` tag plus a separate `scope:portfetch`/`scopeKind:namespace` field, landing
as an apparent ctags-only claim -- a pure naming mismatch, not a real disagreement about whether
these procs exist. Fixed by adding "tcl" to `_QUALIFY_NAME_WITH_SCOPE`, reusing the identical
scope-joining + verbatim-source-line guard mechanism already proven for C++'s `Class::method`
out-of-class-definition convention (tcl's `namespace` scope kind and `::` separator are both
already covered by that generic machinery, unchanged).

Integration-style, not a pure unit test: `read_ctags_symbols` shells out to the real `ctags`
binary, so this needs Universal Ctags on PATH (skipped otherwise, matching how the rest of this
tri-comparison tooling treats ctags as an optional, verification-only dependency).

Per this repo's testing conventions (tests/ has no __init__.py anywhere): the sibling tool
directory is put on sys.path and the modules are imported as bare top-level names, never as
`tests.tools.x`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ctags_reader  # noqa: E402

pytestmark = pytest.mark.skipif(not ctags_reader.ctags_available("tcl"), reason="ctags not on PATH")


def test_namespace_qualified_proc_matches_gitgalaxy_convention(tmp_path):
    """The confirmed corpus shape: an explicitly-qualified `proc ns::name` outside any
    `namespace eval` block. ctags must report the full `ns::name`, matching what GitGalaxy's
    func_start and tree-sitter both read straight out of the source text."""
    tcl_file = tmp_path / "fetch_common.tcl"
    tcl_file.write_text(
        "namespace eval portfetch {\n"
        "    variable urlmap\n"
        "}\n"
        "\n"
        "proc portfetch::percent_encode {str} {\n"
        "    return $str\n"
        "}\n",
        encoding="utf-8",
    )
    symbols = ctags_reader.read_ctags_symbols(tcl_file, "tcl")
    names = {s.name for s in symbols if s.kind == "p"}
    assert "portfetch::percent_encode" in names, f"expected qualified name, got: {names}"
    assert "percent_encode" not in names, "must not ALSO emit the bare, unqualified name"


def test_bare_proc_inside_namespace_eval_stays_unqualified(tmp_path):
    """The guard's other half: a proc written WITHOUT the namespace prefix, lexically inside a
    `namespace eval` block, must NOT be over-qualified just because ctags' own tag data reports
    the same `scope:ns` field for it -- GitGalaxy/tree-sitter read the bare name here (that's
    genuinely all the source text says), so ctags must too. Mirrors the identical guard already
    proven for C++'s in-class-body methods (`class Foo { void bar() {} }` staying `bar`, not
    `Foo::bar`) -- confirmed via the verbatim-source-line check finding no `ns::name` text to
    match."""
    tcl_file = tmp_path / "namespaced.tcl"
    tcl_file.write_text(
        "namespace eval myns {\n"
        "    proc helper {x} {\n"
        "        return $x\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    symbols = ctags_reader.read_ctags_symbols(tcl_file, "tcl")
    names = {s.name for s in symbols if s.kind == "p"}
    assert "helper" in names, f"expected bare name preserved, got: {names}"
    assert "myns::helper" not in names, "must not invent a qualifier the source text never wrote"


def test_cpp_operator_normalization_still_applies_only_to_cpp(tmp_path):
    """Regression guard for the fix's own scoping: _normalize_cpp_operator_name must stay
    cpp-only now that _QUALIFY_NAME_WITH_SCOPE covers a second language -- a Tcl proc literally
    named `operator` (legal, if unconventional, since Tcl proc names are just strings) must not
    have "operator" silently stripped the way a real C++ `operator<` tag name would be."""
    tcl_file = tmp_path / "odd_name.tcl"
    tcl_file.write_text("proc myns::operator {a b} {\n    return [expr {$a + $b}]\n}\n", encoding="utf-8")
    symbols = ctags_reader.read_ctags_symbols(tcl_file, "tcl")
    names = {s.name for s in symbols if s.kind == "p"}
    assert "myns::operator" in names, f"expected qualified 'operator' proc name preserved, got: {names}"
