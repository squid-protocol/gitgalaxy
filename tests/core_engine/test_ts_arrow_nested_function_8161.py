"""#8161 (T1): a block-bodied TS/JS arrow ends at its balanced `}`, not at the next nested declaration.
`const C = () => { function g() {} ... }` used to end at `g`, losing every call after it."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

TS = (
    "function util1(x: string): string {\n  return x;\n}\n\n"  # 1
    "export const errA = () => {\n"  # 5
    "  function getSizing(origin: string): string | null {\n"  # 6
    "    return util1(origin);\n"
    "  }\n"
    "  return (issue: string) => {\n"
    "    const s = getSizing(issue);\n"
    "    return util1(issue) + s;\n"
    "  };\n"
    "};\n"  # 13
    "export const after = () => util1('x');\n"  # 14
)


@pytest.mark.parametrize("lang,path", [("typescript", "a.ts"), ("javascript", "a.js")])
def test_arrow_body_runs_past_a_nested_function(lang, path):
    code = TS if lang == "typescript" else TS.replace(": string | null", "").replace(": string", "")
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    units = {fn["name"]: fn for fn in parsed["functions"]}
    err = units["errA"]
    assert err["start_line"] == 5
    assert err["loc"] == 9  # through line 13, its closing `};`
    assert set(err["calls_out_to"]) == {"getSizing", "util1"}
    assert units["getSizing"]["calls_out_to"] == ["util1"]
    assert units["after"]["start_line"] == 14
    file = {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
    sites, _ = resolve_calls([file])
    edges = {(s["src_name"], s["dst_name"]) for s in sites if s["dst_name"]}
    assert {("errA", "getSizing"), ("errA", "util1"), ("getSizing", "util1"), ("after", "util1")} <= edges
