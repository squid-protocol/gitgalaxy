"""Regression tests for tree_sitter_accuracy_audit._html_embedded_ts_funcs' `<script>` gating.

The audit (and, through it, tri_comparison_gatherer) injects the JavaScript grammar into every
`<script>` element to compare apples-to-apples with GitGalaxy's polyglot detector. It must NOT do
that for `<script src=...>` (external load, no inline code) or for a `<script type="...">` whose
type is not an executable-JS value -- reveal.js `type="text/template"` slide samples,
`x-shader/*` GLSL, `math/tex`, etc. are inert data blocks the browser never runs, GitGalaxy does
not descend into, and ctags does not read; counting phantom functions from them dragged html's
recall down (ledger `html/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

pytest.importorskip("tree_sitter_language_pack")

import tree_sitter_accuracy_audit as tsaa  # type: ignore


def _script_funcs(html: str) -> list[str]:
    """Parse `html`, find its first `<script>` element, return the embedded func names the audit
    would score."""
    parser = tsaa.tree_sitter_language_pack.get_parser("html")
    root = parser.parse(html.encode()).root_node

    found: list = []

    def walk(node):
        if node.type == "script_element":
            found.append(node)
        for c in node.children:
            walk(c)

    walk(root)
    assert found, "no <script> element parsed out of the fixture"
    return [name for name, _line, _pc, _node in tsaa._html_embedded_ts_funcs(found[0])]


_BODY = "function alpha() { return 1; }\nfunction beta(a, b) { return a + b; }"


def test_plain_script_is_parsed() -> None:
    assert _script_funcs(f"<script>\n{_BODY}\n</script>") == ["alpha", "beta"]


def test_module_script_is_parsed() -> None:
    assert _script_funcs(f'<script type="module">\n{_BODY}\n</script>') == ["alpha", "beta"]


def test_explicit_javascript_type_is_parsed() -> None:
    assert _script_funcs(f'<script type="text/javascript">\n{_BODY}\n</script>') == ["alpha", "beta"]


def test_text_template_is_skipped() -> None:
    assert _script_funcs(f'<script type="text/template">\n{_BODY}\n</script>') == []


def test_shader_type_is_skipped() -> None:
    assert _script_funcs(f'<script type="x-shader/x-vertex">\n{_BODY}\n</script>') == []


def test_mathtex_type_with_params_is_skipped() -> None:
    assert _script_funcs(f'<script type="math/tex; mode=display">\n{_BODY}\n</script>') == []


def test_src_script_is_skipped() -> None:
    assert _script_funcs(f'<script src="app.js">\n{_BODY}\n</script>') == []
