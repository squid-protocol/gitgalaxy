"""#8161 (X5): a bare call through a renamed import (`import { add as plus2 }`, `from m import f as g`,
`use a::b as c`) reaches the imported definition: the detector records the rename per unit
(`calls_out_renames`) and the resolver looks the call up under the imported name."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.import_renames import import_renames
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _sites(lang: str, files: dict[str, str], edges):
    parsed = []
    for path, code in files.items():
        p = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
        parsed.append({"path": path, "lang_id": lang, "functions": p["functions"], "classes": p.get("classes", [])})
    sites, _ = resolve_calls(parsed, edges)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"]) for s in sites}


@pytest.mark.parametrize(
    "lang,files,edges,caller,callee,target",
    [
        (
            "typescript",
            {
                "src/lib/math.ts": "export function add(a: number, b: number) {\n  return a + b;\n}\n",
                "src/use.ts": 'import { add as plus2, type X as Y } from "./lib/math";\n'
                "export function run() {\n  return plus2(1, 2);\n}\n",
            },
            [{"src": "src/use.ts", "dst": "src/lib/math.ts"}],
            "run",
            "plus2",
            "src/lib/math.ts",
        ),
        (
            "python",
            {
                "pkg/util.py": "def helper(x):\n    return x\n",
                "pkg/app.py": "from pkg.util import helper as h\n\ndef main():\n    return h(1)\n",
            },
            [{"src": "pkg/app.py", "dst": "pkg/util.py"}],
            "main",
            "h",
            "pkg/util.py",
        ),
        (
            "rust",
            {
                "src/util.rs": "pub fn compute(x: u8) -> u8 {\n    x\n}\n",
                "src/main.rs": "mod util;\nuse crate::util::compute as rt;\n\nfn main() {\n    rt(1);\n}\n",
            },
            [{"src": "src/main.rs", "dst": "src/util.rs"}],
            "main",
            "rt",
            "src/util.rs",
        ),
    ],
)
def test_a_renamed_import_reaches_its_definition(lang, files, edges, caller, callee, target):
    step, dst = _sites(lang, files, edges)[(caller, callee)]
    assert dst == target and step in ("import", "unique", "qualified", "file")


def test_rename_maps():
    assert import_renames("typescript", 'import a, { b as c, default as d, e } from "x";') == {"c": "b"}
    assert import_renames("python", "from m import (a as b,\n    c)\nimport numpy as np\n") == {"b": "a"}
    assert import_renames("rust", "use a::{b as c, d, self as e};\nuse x::y as _;\n") == {"c": "b"}
    # one local name bound to two different imports is no rename
    assert import_renames("python", "from m import a as b\nfrom n import z as b\n") == {}
