"""
#3798: Go import paths resolve through go.mod, never the file-stem name search.

`import "net/http"` used to link every importer to any `http.go` in the repo, and an
import of a package in a nested module drew no edge. The fixture is a small repo with a
root module and a nested one, written to disk; imports are extracted by the real Go
`_dependency_capture` rule and resolved by the real sensor, and the edge set is pinned.
"""

from gitgalaxy.core.go_modules import parse_go_module
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_GO = LANGUAGE_DEFINITIONS["go"]

REPO = {
    "go.mod": "module example.com/app\n\ngo 1.21\n",
    "main.go": (
        "package main\n\n"
        "import (\n"
        '\t"fmt"\n'  # stdlib: no edge
        '\t"net/http"\n'  # stdlib, and promhttp/http.go exists: still no edge
        '\tutil "example.com/app/util"\n'  # aliased, one file in the dir
        '\t_ "example.com/app/drivers/pg"\n'  # blank import
        '\t. "example.com/app/dots"\n'  # dot import
        '\t"example.com/app/multi"\n'  # several files, none named `multi.go`: the first by name
        '\t"example.com/app/named"\n'  # several files, one named after the dir
        '\t"example.com/app/nested/inner"\n'  # a longer module path shadows this one
        '\t"github.com/other/dep/util"\n'  # external, shares the `util` stem
        ")\n"
    ),
    "util/util.go": "package util\n",
    "drivers/pg/conn.go": "package pg\n",
    "dots/d.go": "package dots\n",
    "multi/a.go": "package multi\n",
    "multi/b.go": "package multi\n",
    "named/named.go": "package named\n",
    "named/extra.go": "package named\n",
    "named/named_test.go": "package named\n",
    "promhttp/http.go": 'package promhttp\n\nimport "net/http"\n',
    "tools/pkg_test.go": 'package tools\n\nimport "example.com/app/util"\n',
    # a nested module: its own path is not under the root module's directory tree
    "nested/go.mod": "module example.com/app/nested\n",
    "nested/inner/inner.go": 'package inner\n\nimport "example.com/app/nested/inner/deep"\nimport "example.com/app/util"\n',
    "nested/inner/deep/deep.go": "package deep\n",
    # vendored copies are not the repo's own modules
    "vendor/dep/go.mod": "module github.com/other/dep\n",
    "vendor/dep/util/util.go": "package util\n",
}

EXPECTED = {
    ("main.go", "util/util.go"),
    ("main.go", "drivers/pg/conn.go"),
    ("main.go", "dots/d.go"),
    ("main.go", "multi/a.go"),
    ("main.go", "named/named.go"),
    ("main.go", "nested/inner/inner.go"),
    ("tools/pkg_test.go", "util/util.go"),
    ("nested/inner/inner.go", "nested/inner/deep/deep.go"),
    ("nested/inner/inner.go", "util/util.go"),
}


def _parsed(files):
    rule = _GO["rules"]["_dependency_capture"]
    return [
        {
            "path": rel,
            "lang_id": "go",
            "raw_imports": sorted(extract_raw_imports(rule, text, _GO)),
            "functions": [],
            "classes": [],
        }
        for rel, text in files.items()
        if rel.endswith(".go")
    ]


def _edges(tmp_path, files, root=True):
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path) if root else None
    return set(sensor.resolve_import_edges(_parsed(files)))


def test_a_nested_module_repo_resolves_to_exactly_these_edges(tmp_path):
    assert _edges(tmp_path, REPO) == EXPECTED


def test_stdlib_and_external_imports_never_reach_the_name_search(tmp_path):
    edges = _edges(tmp_path, REPO)
    assert not any(dst in ("promhttp/http.go", "vendor/dep/util/util.go") for _, dst in edges)


def test_without_a_scan_root_no_go_import_draws_an_edge(tmp_path):
    # No go.mod can be read, so no path is known to be local; the stem search must not step in.
    assert _edges(tmp_path, REPO, root=False) == set()


def test_the_root_package_of_a_module_is_its_directory(tmp_path):
    files = {
        "go.mod": "module example.com/lib\n",
        "lib.go": "package lib\n",
        "cmd/run/main.go": 'package main\n\nimport "example.com/lib"\n',
    }
    assert _edges(tmp_path, files) == {("cmd/run/main.go", "lib.go")}


def test_parse_go_module_forms():
    assert parse_go_module("module example.com/a\n") == "example.com/a"
    assert parse_go_module('// c\nmodule "example.com/b"\n\ngo 1.22\n') == "example.com/b"
    assert parse_go_module("go 1.22\n") is None
