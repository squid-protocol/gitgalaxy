"""#6572: `replace X => ../local` (go.mod or go.work) maps the import path X to a scanned directory."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_go_module_resolution_3798 import _edges  # noqa: E402

from gitgalaxy.core.go_modules import parse_go_replaces


@pytest.mark.parametrize(
    "text, expected",
    [
        ("replace example.com/x => ../x\n", [("example.com/x", "../x")]),
        ("replace example.com/x v1.2.3 => ./x\n", [("example.com/x", "./x")]),
        ('replace "example.com/x" => "./x"\n', [("example.com/x", "./x")]),
        (
            "replace (\n\texample.com/a => ../a\n\texample.com/b v1.0.0 => ./b // c\n)\n",
            [("example.com/a", "../a"), ("example.com/b", "./b")],
        ),
        ("replace example.com/x => example.com/y v1.0.0\n", []),  # another module, not a local dir
        ("replace example.com/x => /abs/x\n", []),
        ("require example.com/x v1.0.0\n", []),
    ],
)
def test_parse_go_replaces_forms(text, expected):
    assert parse_go_replaces(text) == expected


def test_go_mod_replace_resolves_a_sibling_directory_import(tmp_path):
    files = {
        "app/go.mod": "module example.com/app\n\nreplace example.com/lib => ../lib\n",
        "app/main.go": 'package main\n\nimport "example.com/lib/sub"\nimport "example.com/lib"\n',
        "lib/go.mod": "module example.com/lib\n",
        "lib/lib.go": "package lib\n",
        "lib/sub/s.go": "package sub\n",
    }
    assert _edges(tmp_path, files) == {("app/main.go", "lib/lib.go"), ("app/main.go", "lib/sub/s.go")}


def test_replace_to_a_dir_without_its_own_go_mod_and_block_form(tmp_path):
    files = {
        "go.mod": "module example.com/app\n\nreplace (\n\texample.com/vend v1.0.0 => ./third_party/vend\n)\n",
        "main.go": 'package main\n\nimport "example.com/vend/pkg"\n',
        "third_party/vend/pkg/p.go": "package pkg\n",
    }
    assert _edges(tmp_path, files) == {("main.go", "third_party/vend/pkg/p.go")}


def test_go_work_replace_and_use_resolve_across_modules(tmp_path):
    files = {
        "go.work": "go 1.22\n\nuse (\n\t./a\n\t./b\n)\n\nreplace example.com/ext => ./ext\n",
        "a/go.mod": "module example.com/a\n",
        "a/a.go": 'package a\n\nimport "example.com/b"\nimport "example.com/ext"\n',
        "b/go.mod": "module example.com/b\n",
        "b/b.go": "package b\n",
        "ext/ext.go": "package ext\n",
    }
    assert _edges(tmp_path, files) == {("a/a.go", "b/b.go"), ("a/a.go", "ext/ext.go")}


def test_replace_outside_the_scan_or_to_a_remote_module_draws_no_edge(tmp_path):
    files = {
        "go.mod": "module example.com/app\n\nreplace example.com/gone => ../../gone\nreplace example.com/fork => example.com/fork2 v1.0.0\n",
        "main.go": 'package main\n\nimport "example.com/gone"\nimport "example.com/fork"\n',
        "fork/fork.go": "package fork\n",
        "gone.go": "package gone\n",
    }
    assert _edges(tmp_path, files) == set()


def test_a_vendored_import_draws_no_edge_with_or_without_modules_txt(tmp_path):
    # `vendor/` is an ignored directory: its packages are never scanned, so `vendor/modules.txt`
    # has no target to point an import at (stated absence, not a gap)
    files = {
        "go.mod": "module example.com/app\n",
        "main.go": 'package main\n\nimport "github.com/dep/util"\n',
        "vendor/modules.txt": "# github.com/dep/util v1.0.0\ngithub.com/dep/util\n",
        "vendor/github.com/dep/util/util.go": "package util\n",
    }
    assert _edges(tmp_path, files) == set()
