"""#8161 (G3): a bare Go call follows Go's scoping: the caller's own file, then its own package (a
directory: confident even when another package defines the name), then the packages it DOT-imports. An
ordinary import never puts a name in bare scope (`New()` in package util is util's `New`, never an
imported `labels.New`)."""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.network_risk_sensor import GO_DOT_IMPORT_PREFIX
from gitgalaxy.galaxyscope import extract_namespace_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FILES = {
    "labels/labels.go": "package labels\n\nfunc New() int { return 1 }\n\nfunc validate() bool { return true }\n",
    "util/new.go": "package util\n\nfunc New() int { return 2 }\n",
    "util/use.go": (
        'package util\n\nimport "example.com/m/labels"\n\nfunc Use() int {\n\treturn New() + labels.Count()\n}\n'
    ),
    "util/check.go": "package util\n\nfunc validate() bool { return false }\n",
    "util/other.go": "package util\n\nfunc Other() bool {\n\treturn validate()\n}\n",
    "x/x.go": "package x\n\nfunc Hidden() int { return 3 }\n",
    "app/app.go": 'package app\n\nimport (\n\t. "example.com/m/x"\n)\n\nfunc Run() int {\n\treturn Hidden()\n}\n',
    "far/far.go": "package far\n\nfunc Lonely() int { return 4 }\n",
    "near/near.go": "package near\n\nfunc Call() int {\n\treturn Lonely()\n}\n",
}
IMPORTS = [{"src": "util/use.go", "dst": "labels/labels.go"}, {"src": "app/app.go", "dst": "x/x.go"}]


def _sites():
    parsed_files = []
    for path, code in FILES.items():
        parsed = StructuralExtractor("go", LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append(
            {"path": path, "lang_id": "go", "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    aliases = {"app/app.go": {GO_DOT_IMPORT_PREFIX + "example.com/m/x": "x/x.go"}}
    sites, _ = resolve_calls(parsed_files, IMPORTS, namespace_aliases=aliases)
    return {(s["src_name"], s["callee"]): (s["step"], s["dst_path"]) for s in sites}


def test_own_package_beats_an_imported_package():
    assert _sites()[("Use", "New")] == ("import", "util/new.go")


def test_own_package_is_confident_although_another_package_defines_the_name():
    assert _sites()[("Other", "validate")] == ("import", "util/check.go")


def test_a_dot_import_puts_the_package_in_bare_scope():
    assert _sites()[("Run", "Hidden")] == ("import", "x/x.go")


def test_a_name_outside_every_bare_scope_is_unseen():
    assert _sites()[("Call", "Lonely")] == ("unseen", "far/far.go")


def test_dot_imports_are_extracted():
    code = 'package app\n\nimport (\n\t"fmt"\n\t. "example.com/m/x"\n)\nimport . "example.com/m/y"\n'
    assert extract_namespace_imports(code, "go") == {
        "fmt": "fmt",  # #8161 (G1): an ordinary import binds its name
        GO_DOT_IMPORT_PREFIX + "example.com/m/x": "example.com/m/x",
        GO_DOT_IMPORT_PREFIX + "example.com/m/y": "example.com/m/y",
    }
