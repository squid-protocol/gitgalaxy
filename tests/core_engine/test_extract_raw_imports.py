"""
galaxyscope.extract_raw_imports: the import tokens a scan records per file.
Import-graph precision work: Python `from . import a, b` records the imported
names as `.a` / `.b` (the submodules they may be), never only `.`; Go records
only real import specs.
"""

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _tokens(lang, src):
    d = LANGUAGE_DEFINITIONS[lang]
    return extract_raw_imports(d["rules"]["_dependency_capture"], src, d)


def test_python_from_dots_import_records_each_name():
    src = (
        "from . import cli\n"
        "from . import typing as ft, json\n"
        "from .. import (\n    a,\n    b as c,\n)\n"
        "from .globals import g\n"
        "import os, sys as system\n"
    )
    assert _tokens("python", src) == {".cli", ".typing", ".json", "..a", "..b", ".globals", "os", "sys"}


def test_a_commented_parenthesized_list_falls_back_to_the_package():
    # the names form cannot parse a comment inside the parens; the old token stays
    assert _tokens("python", "from . import (a,  # why\n b)\n") == {"."}


def test_go_records_only_import_specs():
    src = 'package x\n\nimport (\n\t"fmt"\n\tstr "strings"\n)\n\nvar args = []string{\n\t"--help",\n\t"apple",\n}\n'
    assert _tokens("go", src) == {"fmt", "strings"}


def test_a_rust_mod_declaration_is_recorded_as_a_local_module():
    # #3554: `local_module_capture_group` -- `mod de;` is `./de`, never a crate name.
    assert _tokens("rust", "mod de;\npub mod lexical;\nmod inline { }\nuse serde::de;\n") == {
        "./de",
        "./lexical",
        "serde::de",
    }


def test_brace_selectors_distribute_their_prefix():
    # #3595: `io.circe.{ Decoder, Json }` was `io.circe. Decoder` and a bare `Json`.
    src = "import io.circe.{ Decoder, Json => J, _ }\nimport cats.syntax.show._\n"
    assert _tokens("scala", src) == {"io.circe.Decoder", "io.circe.Json", "io.circe._", "cats.syntax.show._"}
    assert _tokens("rust", "use std::{fs, io::{self, Read}};\n") == {"std::fs", "std::io", "std::io::Read"}


def test_a_shell_expansion_is_not_a_selector_group():
    assert _tokens("shell", 'source "${BASH_IT}/lib/log.bash"\n') == {"$BASH_IT/lib/log.bash"}
