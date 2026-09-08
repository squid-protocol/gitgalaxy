# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `import` contract (#2875, docs/import_rule_contract.md), held across every
corpus language in one place.

    One hit is a statement or directive that binds an external unit -- a
    module, package, header, library, file, stage or base image -- into the
    current unit, in the language's own dependency form.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
46-language audit found the old rules disagreeing on:

  C1 the dependency form, re-exports and loader calls included: `export …
     from`, `pub use`, dart `export`/`part`, and the dynamic loader where it
     is the language's load form (`require(`, `import(`, `__import__(`,
     `Type.forName(`, `dofile(`, `load_extension(`); csharp's alias directive
     `using Alias = Target;` binds a unit and joins
  C2 the unit is the statement, not the edge: `import (…)`, `use a::{b, c};`,
     `import a, b`, `with a, b;` are one hit; a block of eight scala import
     lines is eight (the old class swallowed newlines and read ONE)
  C3 a binding, not a reference or a self-declaration: apex `acct.Id` /
     `Account.Name` (apex has no import statement -- `Type.forName(` is its
     load form), livecode's own `module com.x` header and `end module`,
     fortran `IMPORT` (host association), abap `INCLUDE TYPE`
  C4 a named unit: `FROM scratch` is the reserved empty base (class_start
     still opens the stage, #2856); agc `BANK 31` / bare `BANK` are location
     directives; `EBANK=` is an addressing directive and args' token (C6)
  C5 statement or command position: `include` in an abap template string,
     `use ysu` in a fortran string, m4's `include/Makefile` path, shell's
     `find . -name`, python's doctest `>>> import numpy`
  C6 one owner with the stated duals kept: dockerfile FROM (class_start),
     html <link href> (io), sqlite .read/.import (import's, io C2 #2841);
     markdown records None

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-statement-one-hit.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="import"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: the dependency form, re-exports and loader calls -------------------
    "csharp": (
        [
            "using System.Collections.Generic;",
            "global using System;",
            "using static System.Math;",
            "using Alias = Target.Namespace.Type;",
            "using Dict = System.Collections.Generic.Dictionary<string, int>;",
        ],
        ["using (var stream = File.OpenRead(path))", "using var f = File.Open(path);", "namespace Foo;"],
    ),
    "javascript": (
        [
            "import a from './a.js';",
            "export { b } from './b.js';",
            "const c = require('./c');",
            "await import('./d.js');",
        ],
        ["export const x = 1;", "const from = 1;"],
    ),
    "rust": (["use b;", "pub use crate::c::D;", "use std::{fmt, io};"], ["let use_it = 1;", "// use nothing"]),
    "dart": (["import 'b.dart';", "export 'c.dart';", "part 'd.dart';", "part of 'lib.dart';"], ["importer = 1;"]),
    "apex": (
        ["Type.forName('b');", "TYPE.FORNAME('c')", "Type.forName(ns, 'd')"],
        ["acct.Id", "Account.Name", "LoggingLevel.INFO", "conn.clear()", "System.debug('x');"],
    ),
    "python": (
        [
            "import a",
            "from b import probe_telemetry",
            "    import c",
            "x = 1; import os",
            "__import__('m')",
            "importlib.import_module('n')",
        ],
        ["    >>> import numpy as np", '"please import the file"', "importance = 1"],
    ),
    "embedded_python": (
        ["import machine", "from b import probe_telemetry", "__import__('m')"],
        ["    >>> import machine", "from_machine = True"],
    ),
    # --- C2: statement, not edge (see COUNTS) -----------------------------------
    "scala": (
        ["import scala.util.Try", "import java.lang.{Long => JLong}", "import a.*", "  import b.c"],
        ["// important note here", "val imported = 1"],
    ),
    # --- C3: a binding, not a reference or the file's own header ----------------
    "livecode": (
        ['start using stack "b"', "use com.livecode.foreign", 'start using behavior "x"'],
        ["module com.livecode.array", "end module", 'case "module"', "put module into x"],
    ),
    "fortran": (
        [
            "USE b",
            "use, intrinsic :: iso_c_binding",
            "USE mod, ONLY: x",
            "      INCLUDE 'b.inc'",
            '#include "defs.inc"',
        ],
        ["IMPORT :: t", "      IMPORT", "( 'module_physics_init: use ysu (option1), myj (option 2)' )", "X = 1"],
    ),
    "abap": (
        ["INCLUDE zabapgit_forms.", "INCLUDE zx IF FOUND.", "TYPE-POOLS abap."],
        [
            "INCLUDE TYPE ty_struct.",
            "INCLUDE STRUCTURE sflight.",
            "zcx=>raise( |ENHO include should not be in TADIR| ).",
        ],
    ),
    # --- C4: a named unit ---------------------------------------------------------
    "dockerfile": (
        [
            "FROM a",
            "FROM golang:1.22 AS builder",
            "FROM --platform=$BUILDPLATFORM busybox AS build-dummy",
            "COPY --from=xx / /",
            "FROM scratchy/base",
        ],
        [
            "FROM scratch",
            "FROM scratch AS binary-dummy",
            "from SCRATCH",
            'RUN echo "FROM ubuntu"',
            "COPY corpus /srv/corpus",
        ],
    ),
    "agc_assembly": (
        ["\tBANK\tb", "\tSETLOC\tFOO", "SETLOC P40S"],
        ["\tBANK", "\tBANK\t31", "\tTCF\tSETLOC", "\tEBANK=\tLST1", "\tCA\tBAR"],
    ),
    # --- C5: statement or command position ---------------------------------------
    "shell": (
        [
            "source ./lib.sh",
            ". ./b.sh",
            "  . /etc/profile",
            "if source x.sh; then",
            "true && source y.sh",
            "cmd; . z.sh",
        ],
        ["find -s . -mindepth 1", "ansible-galaxy role init --init-path . unsupported_format", "echo source lib.sh"],
    ),
    "m4": (["include(b.m4)", "m4_include([c.m4])", "sinclude(d.m4)"], ["include/Makefile \\", "AC_SUBST(FOO)"]),
    # --- conforming languages, pinned so the shape holds -------------------------
    "c": (['#include "b.c"', "#include <stdio.h>", "# include <x.h>"], ["// include nothing", "int include_count;"]),
    "go": (['import "b"', "import (", 'import _ "embed"'], ['x := "import"']),
    "java": (["import b;", "import static java.lang.Math.max;"], ["// import nothing", "importer = 1;"]),
    "haskell": (["import B", "import qualified Data.Text as T"], ["-- import nothing", "importantValue = 1"]),
    "perl": (["use b;", "require Image::ExifTool::XMP;", "no strict 'refs';"], ["use 5.010;", "my $use = 1;"]),
    "ruby": (["require 'b'", "require_relative 'c'"], ["required = true"]),
    "lua": (["require 'b'", 'local core = require("core")', 'dofile("x.lua")'], ["required = true"]),
    "cobol": (["       COPY b.", "               INCLUDE SQLCA"], ["       MOVE COPYBOOK TO X."]),
    "sqlite": ([".read b.sql", "ATTACH DATABASE 'x.db' AS x;", ".import data.csv t1"], ["SELECT * FROM t;"]),
    "yaml": (["      - uses: ./b.yml", "    image: node:18"], ["      - run: echo uses"]),
    "zig": (['const std = @import("std");', '_ = @import("b.zig");'], ["const x = 1;"]),
    "tcl": (["source b.tcl", "package require portutil 1.0", "load $pextlibname"], ["set source 1"]),
    "makefile": (["include b.mk", "-include c.mk"], ["\tinclude /etc/motd"]),
    "css": (['@import url("b.css");', "@import 'tailwindcss';"], ["import: none;"]),
    "html": (['<link rel="stylesheet" href="b.html">', '<script type="module" src="x.js">'], ["<p>import</p>"]),
}

COUNTS = [
    (
        "scala",
        "import java.util.Properties\nimport joptsimple.OptionParser\nimport kafka.server.{KafkaConfig, Server}\n\ndef main = 1",
        3,
    ),
    ("scala", "import a.b, c.d", 1),
    ("go", 'import (\n\t"fmt"\n\t"os"\n)', 1),
    ("rust", "use std::{fmt, io};", 1),
    ("python", "import os, sys", 1),
    ("python", "from x import (\n    a,\n    b,\n)", 1),
    ("ada", "with Ada.Text_IO, Ada.Strings;", 1),
    ("dockerfile", "FROM a\nCOPY corpus /srv/corpus\nFROM scratch\n", 1),
    ("embedded_python", "import machine\nimport a\n", 2),
    ("shell", "source a.sh && . b.sh; find . -name x", 2),
    ("csharp", "using System;\nusing Alias = Foo.Bar;\nusing (var s = Open()) {}\n", 2),
]

PAYLOADS = [
    "import " * 20000,
    "import " + "a" * 100000,
    "import " + "a." * 50000,
    "import a.{" + "b, " * 30000,
    "using " + "a" * 100000,
    "using " + "a = " * 30000,
    "FROM " + "s" * 100000,
    "FROM scratch" + "y" * 100000,
    "BANK " + "a" * 100000,
    "USE " + " " * 100000 + "x",
    "INCLUDE " + " " * 100000,
    "include" + " " * 100000,
    "source " + " " * 100000,
    ". " + "a" * 100000,
    "use " + "a." * 50000,
    ";" * 50000 + "import x",
    "then " * 20000 + "source x",
    "Type.forName" + " " * 100000,
    ">>> import " * 10000,
]

# C6: the deliberate duals -- both readings are correct on the language.
DUALS = [
    ("dockerfile", "class_start", "FROM golang:1.22 AS build"),
    ("html", "io", '<link rel="stylesheet" href="b.html">'),
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_import_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_import_one_statement_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


@pytest.mark.parametrize("lang,other,text", DUALS)
def test_import_deliberate_duals_are_kept(lang, other, text):
    assert _rule(lang).search(text) and _rule(lang, other).search(text)


def test_import_capture_agrees_with_the_count_on_named_units():
    """C4 at the graph layer: what the count excludes, the capture must not turn into
    an edge -- `FROM scratch` and `BANK 31` resolve to units that cannot exist."""
    assert _rule("dockerfile", "_dependency_capture").search("FROM scratch") is None
    m = _rule("dockerfile", "_dependency_capture").search("FROM a")
    assert m and m.group(1) == "a"
    assert _rule("agc_assembly", "_dependency_capture").search("\tBANK\t31") is None
    assert _rule("livecode", "_dependency_capture").search("module com.livecode.array") is None
    m = _rule("livecode", "_dependency_capture").search("use com.livecode.foreign")
    assert m and m.group(2) == "com.livecode.foreign"
    assert _rule("shell", "_dependency_capture").search("find -s . -mindepth 1") is None


def test_import_stated_absence_rows_carry_no_rule():
    """C6: markdown has no dependency form (ledger markdown-lit-plane-morphology);
    the rule stays None."""
    assert LANGUAGE_DEFINITIONS["markdown"]["rules"].get("import") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_import_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
