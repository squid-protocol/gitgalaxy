"""
#3360 (contract C5, docs/calls_out_rule_contract.md): a function declared inside a body is not a
call. `CALLS_OUT_C_STYLE` used to capture the nested header (`def inner(`, `local function f (`,
a nested `fn`), so the enclosing function listed `inner` as a callee. The detector now drops a
capture that sits on a header its own `func_start` rule matches, and keeps every real call.

Each case has two outer functions: `o2` only declares `helper` (so `helper` must not appear), and
`outer` declares `inner` and then really calls it (so `inner` must still appear). Driven through
`StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


_PY = (
    "def outer(x):\n"
    "    def inner(y):\n"
    "        return y\n"
    "    return inner(x)\n"
    "\n"
    "def o2(x):\n"
    "    def helper(y):\n"
    "        return y\n"
    "    return helper\n"
)

CASES = {
    "python": _PY,
    "embedded_python": _PY,
    "javascript": (
        "function outer(a) {\n  function inner(b) {\n    return b;\n  }\n  return inner(a);\n}\n"
        "function o2(a) {\n  function helper(b) {\n    return b;\n  }\n  return helper;\n}\n"
    ),
    "typescript": (
        "function outer(a: number): number {\n  function inner(b: number): number {\n    return b;\n  }\n"
        "  return inner(a);\n}\n"
        "function o2(a: number) {\n  function helper(b: number) {\n    return b;\n  }\n  return helper;\n}\n"
    ),
    "lua": (
        "function outer(a)\n  local function inner (b)\n    return b\n  end\n  return inner(a)\nend\n"
        "function o2(a)\n  local function helper(b)\n    return b\n  end\n  return helper\nend\n"
    ),
    "rust": (
        "fn outer(a: i32) -> i32 {\n    fn inner(b: i32) -> i32 {\n        b\n    }\n    inner(a)\n}\n"
        "fn o2(a: i32) -> i32 {\n    fn helper(b: i32) -> i32 {\n        b\n    }\n    a\n}\n"
    ),
    "zig": (
        "fn outer(a: i32) i32 {\n    const S = struct {\n        fn inner(b: i32) i32 {\n"
        "            return b;\n        }\n    };\n    return S.inner(a);\n}\n"
        "fn o2(a: i32) i32 {\n    const S = struct {\n        fn helper(b: i32) i32 {\n"
        "            return b;\n        }\n    };\n    return a;\n}\n"
    ),
    "scala": (
        "object M {\n"
        "  def outer(a: Int): Int = {\n    def inner(b: Int): Int = {\n      b\n    }\n    inner(a)\n  }\n"
        "  def o2(a: Int): Int = {\n    def helper(b: Int): Int = {\n      b\n    }\n    a\n  }\n"
        "}\n"
    ),
}


@pytest.mark.parametrize("lang", sorted(CASES))
def test_nested_declaration_header_is_not_a_call(lang):
    assert "helper" not in _calls(lang, CASES[lang])["o2"]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_real_call_to_the_nested_unit_is_still_a_call(lang):
    assert "inner" in _calls(lang, CASES[lang])["outer"]


def test_recursion_is_still_dropped():
    # Decision 2 is unchanged: the function's own name never appears.
    code = "def walk(n):\n    def visit(m):\n        return m\n    return walk(visit(n))\n"
    assert _calls("python", code)["walk"] == ["visit"]


def test_decorator_factory_on_a_nested_def_is_still_a_call():
    # C1: `@retry(3)` is invoked. It sits inside the nested header's func_start match, so the
    # header test must take only the header's own name, not every name in the match.
    code = "def outer():\n    @retry(3)\n    def inner():\n        return 1\n    return inner\n"
    assert _calls("python", code)["outer"] == ["retry"]


def test_default_argument_call_on_a_nested_header_is_still_a_call():
    code = "def outer():\n    def inner(x=make()):\n        return x\n    return inner\n"
    assert _calls("python", code)["outer"] == ["make"]


def test_header_shaped_call_the_slicer_rejected_is_still_a_call():
    # csharp's raw func_start fits `this.SetCurrentSolution(\n x =>\n {` (roslyn Workspace.cs),
    # but the slicer emits no unit there. Only a header the slicer really emitted is dropped.
    code = (
        "class W\n{\n"
        "    protected internal virtual void OnProjectRemoved(ProjectId projectId)\n    {\n"
        "        this.SetCurrentSolution(\n            oldSolution =>\n            {\n"
        "                CheckProjectIsInSolution(oldSolution, projectId);\n"
        "                return oldSolution.RemoveProject(projectId);\n            },\n"
        "            WorkspaceChangeKind.ProjectRemoved, projectId,\n"
        "            onBeforeUpdate: (oldSolution, _) =>\n            {\n"
        "                this.ClearProjectData(projectId);\n            });\n    }\n}\n"
    )
    assert _calls("csharp", code)["OnProjectRemoved"][0] == "SetCurrentSolution"


def test_no_false_fcall_edge_from_outer_to_nested_declaration():
    # Downstream (#3328 resolver, #3330 function graph): a nested header used to resolve by the
    # `file` step to the nested function itself, a confident outer -> inner fcall edge. With the
    # capture gone, `o2` has no edge to `helper`; `outer` keeps its real edge to `inner`.
    from gitgalaxy.core.call_resolver import resolve_calls
    from gitgalaxy.core.function_graph import function_metrics

    functions = StructuralExtractor("python", LANGUAGE_DEFINITIONS).splice(_PY, "")["functions"]
    files = [{"path": "m.py", "lang_id": "python", "functions": functions}]
    sites, _ = resolve_calls(files)
    pairs = {(s["src_name"], s["dst_name"]) for s in sites}
    assert ("o2", "helper") not in pairs
    assert ("outer", "inner") in pairs

    metrics = {name: m for (_, name, _), m in function_metrics(files, sites).items()}
    assert metrics["o2"]["func_fan_out"] == 0
    assert metrics["helper"]["func_fan_in"] == 0
    assert metrics["inner"]["func_fan_in"] == 1
