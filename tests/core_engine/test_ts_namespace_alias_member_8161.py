"""#8161 (T3a): `ns.f()` through a namespace import (`import * as ns`, #3788) reaches the module's export
`f`, never an object-literal or prototype member that happens to be named `f` there (zod's `z.set(...)`
landed on a descriptor's `set(...)`). In JavaScript a CommonJS module's exports ARE members
(`exports.f = function`), so one is kept when the module has nothing else of that name."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _sites(lang: str, files: dict[str, str], aliases: dict[str, dict[str, str]]):
    parsed_files = []
    for path, code in files.items():
        parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append(
            {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files, namespace_aliases=aliases)
    return {s["callee"]: (s["step"], s["dst_path"], s["dst_line"]) for s in sites}


def test_ts_namespace_alias_skips_an_object_literal_member():
    files = {
        "lib.ts": (
            "export const desc = {\n  set(v: number): number {\n    return v;\n  },\n};\n"
            "export function other(v: number): number {\n  return v;\n}\n"
        ),
        "main.ts": (
            'import * as lib from "./lib";\nexport function use(): number {\n  return lib.set(1) + lib.other(2);\n}\n'
        ),
    }
    sites = _sites("typescript", files, {"main.ts": {"lib": "lib.ts"}})
    assert sites["set"][1] is None  # the descriptor's `set` is not `lib.set`
    assert sites["other"] == ("import", "lib.ts", 6)


def test_js_commonjs_member_export_is_still_reached():
    files = {
        "lib.js": "exports.set = function (v) {\n  return v;\n};\n",
        "main.js": 'const lib = require("./lib");\nfunction use() {\n  return lib.set(1);\n}\n',
    }
    sites = _sites("javascript", files, {"main.js": {"lib": "lib.js"}})
    assert sites["set"] == ("import", "lib.js", 1)
