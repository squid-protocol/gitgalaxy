"""import_graph_accuracy.py: the parser side resolves each language's imports by
the language's own rule, and the gate reads a DROP as a regression."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_graph_accuracy as iga


def _group(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return iga.Group(files, tmp_path)


def test_python_absolute_import_needs_a_source_root(tmp_path):
    # `import types` is the stdlib, not pkg/types.py (that file is `pkg.types`).
    g = _group(tmp_path, {"pkg/__init__.py": "", "pkg/types.py": "", "src/app/__init__.py": "", "src/app/core.py": ""})
    assert g.python_module("types") == set()
    assert g.python_module("pkg.types") == {"pkg/types.py"}
    assert g.python_module("app.core") == {"src/app/core.py"}  # src/ is a root: it is not a package
    assert g.python_module("app") == {"src/app/__init__.py"}


def test_python_statements_resolve_from_and_relative_forms(tmp_path):
    g = _group(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "", "pkg/b.py": ""})
    src = b"import pkg.a\nfrom pkg import b\nfrom . import a\nfrom .b import x\nimport os\n"
    sets = iga.python_imports(src, "pkg/c.py", g)
    assert sets == [{"pkg/a.py"}, {"pkg/__init__.py", "pkg/b.py"}, {"pkg/a.py"}, {"pkg/b.py"}, set()]


def test_regressions_read_a_drop_and_skip_thin_languages():
    base = {
        "python": {"imports": 100, "engine_edges": 90, "precision_pct": 90.0, "recall_pct": 60.0},
        "rust": {"imports": 2, "engine_edges": 1, "precision_pct": 100.0, "recall_pct": 50.0},
    }
    assert iga.regressions({"python": {"precision_pct": 89.6, "recall_pct": 60.0}, "rust": {}}, base) == []
    assert iga.regressions({"python": {"precision_pct": 89.0, "recall_pct": 61.0}, "rust": {}}, base) == [
        "python: precision_pct 90.0 -> 89.0"
    ]
    assert iga.regressions({"rust": {}}, base) == ["python: no longer measured (baseline had 100 resolvable imports)"]


def test_score_counts_statements_and_edges_against_the_resolved_sets(tmp_path):
    files = {"pkg/__init__.py": "", "pkg/a.py": "import pkg.b\nimport pkg.c\n", "pkg/b.py": "", "pkg/c.py": ""}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    langs = {rel: "python" for rel in files}
    # engine: one right edge (a -> b), one wrong edge (a -> __init__), c missed
    edges = {("pkg/a.py", "pkg/b.py"), ("pkg/a.py", "pkg/__init__.py")}
    r = iga.score_group(tmp_path, langs, edges, ("python",))["python"]
    assert (r["imports"], r["found"], r["edges"], r["correct"]) == (2, 1, 2, 1)


def test_manifest_pins_every_scored_language_to_a_full_commit():
    repos = json.loads(iga.MANIFEST.read_text())["repos"]
    assert {e["language"] for e in repos} == set(iga.LANGS)
    assert all(len(e["commit"]) == 40 and set(e["commit"]) <= set("0123456789abcdef") for e in repos)


needs_ts = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_language_pack") is None, reason="tree-sitter-language-pack not installed"
)


@needs_ts
def test_go_uses_the_module_path_from_go_mod(tmp_path):
    g = _group(tmp_path, {"go.mod": "module example.com/m\n\ngo 1.21\n", "m.go": "", "sub/x.go": "", "sub/y.go": ""})
    g.files.discard("go.mod")  # a scan does not record go.mod; the rule reads it from disk
    src = b'package doc\nimport (\n "example.com/m"\n "example.com/m/sub"\n "fmt"\n)\n'
    assert iga.go_imports(src, "doc/d.go", g) == [{"m.go"}, {"sub/x.go", "sub/y.go"}, set()]


@needs_ts
def test_c_quoted_include_prefers_the_including_directory(tmp_path):
    g = _group(tmp_path, {"src/unix/internal.h": "", "src/win/internal.h": "", "include/uv.h": ""})
    src = b'#include "internal.h"\n#include <uv.h>\n#include <stdio.h>\n'
    assert iga.c_imports("c")(src, "src/unix/core.c", g) == [{"src/unix/internal.h"}, {"include/uv.h"}, set()]


@needs_ts
def test_typescript_esm_js_spelling_resolves_to_the_ts_source(tmp_path):
    g = _group(tmp_path, {"src/a.ts": "", "src/lib/index.ts": ""})
    src = b'import { a } from "./a.js";\nexport * from "./lib";\nimport z from "zod";\n'
    assert iga.js_imports("typescript")(src, "src/main.ts", g) == [{"src/a.ts"}, {"src/lib/index.ts"}]


@needs_ts
def test_php_resolves_use_and_trait_use_through_psr4(tmp_path):
    composer = json.dumps({"autoload": {"psr-4": {"Acme\\": "src/"}}})
    g = _group(tmp_path, {"composer.json": composer, "src/Http/Client.php": "", "src/Tools.php": ""})
    src = b"<?php\nnamespace Acme\\Http;\nuse Acme\\Tools;\nclass X {\n  use Tools;\n  use Helper;\n}\n"
    # `use Acme\Tools` and the trait `Tools` (an imported alias) both land on src/Tools.php;
    # `Helper` resolves in the current namespace (Acme\Http\Helper), which does not exist.
    assert iga.php_imports(src, "src/Http/X.php", g) == [{"src/Tools.php"}, {"src/Tools.php"}, set()]


@needs_ts
def test_rust_mod_declaration_follows_the_module_tree(tmp_path):
    g = _group(tmp_path, {"src/lib.rs": "", "src/de.rs": "", "src/lexical/mod.rs": "", "src/lexical/num.rs": ""})
    assert iga.rust_imports(b"mod de;\nmod lexical;\nmod inline { }\n", "src/lib.rs", g) == [
        {"src/de.rs"},
        {"src/lexical/mod.rs"},
    ]
    assert iga.rust_imports(b"mod num;\n", "src/lexical/mod.rs", g) == [{"src/lexical/num.rs"}]


@needs_ts
def test_rust_use_paths_follow_the_module_tree_and_cargo(tmp_path):
    # #4544: crate::/super::, a sibling crate by its package name, a re-export, std (external),
    # and `use super::*` inside an inline test module (this file: no import).
    g = _group(
        tmp_path,
        {
            "a/Cargo.toml": '[package]\nname = "a-core"\nedition = "2021"\n',
            "a/src/lib.rs": "mod geom;\npub use geom::Point;\n",
            "a/src/geom.rs": "pub struct Point;\n",
            "a/src/geom/shape.rs": "",
            "b/Cargo.toml": '[package]\nname = "b"\nedition = "2021"\n[dependencies]\na-core = { path = "../a" }\n',
            "b/src/main.rs": "",
        },
    )
    src = b"use super::Point;\nuse crate::geom::shape;\nuse std::io;\nmod tests { use super::*; }\n"
    assert iga.rust_imports(src, "a/src/geom/shape.rs", g) == [
        {"a/src/geom.rs"},
        set(),  # crate::geom::shape is this file
        set(),
        set(),
    ]
    assert iga.rust_imports(b"use a_core::Point;\n", "b/src/main.rs", g) == [{"a/src/lib.rs", "a/src/geom.rs"}]


@needs_ts
def test_rust_bin_path_is_a_crate_root(tmp_path):
    # #3798: ripgrep's `[[bin]] path = "crates/core/main.rs"` roots `crate::` for the files under it.
    g = _group(
        tmp_path,
        {
            "Cargo.toml": '[package]\nname = "rg"\nedition = "2021"\n[[bin]]\nname = "rg"\npath = "crates/core/main.rs"\n',
            "crates/core/main.rs": "mod flags;\n",
            "crates/core/flags/mod.rs": "",
            "crates/core/flags/defs.rs": "",
        },
    )
    assert iga.rust_imports(b"use crate::flags::defs;\n", "crates/core/flags/mod.rs", g) == [
        {"crates/core/flags/defs.rs"}
    ]


@needs_ts
def test_java_nested_class_import_lives_in_the_outer_class_file(tmp_path):
    g = _group(tmp_path, {"src/com/acme/TestTypes.java": "", "src/com/acme/Util.java": ""})
    src = b"import com.acme.TestTypes.BagOfPrimitives;\nimport static com.acme.Util.helper;\n"
    assert iga.java_imports(src, "src/com/acme/X.java", g) == [
        {"src/com/acme/TestTypes.java"},
        {"src/com/acme/Util.java"},
    ]


@needs_ts
def test_kotlin_and_scala_resolve_by_package_and_declared_name(tmp_path):
    # Neither language ties a file's path or name to what it declares.
    g = _group(
        tmp_path,
        {
            "src/Names.kt": "package com.acme\nfun String.asName() = this\nclass Named\n",
            "src/other/Util.kt": "package com.acme.util\n\nobject Util {\n    const val X = 1\n}\n",
            "java/com/acme/Legacy.java": "package com.acme; class Legacy {}",
            "scala/pkg.scala": "package io.circe\npackage object syntax { }\n",
            "scala/Dec.scala": "package io.circe.`export`\ncase class Exported(x: Int)\n",
            "scala/Json.scala": "package io.circe\nclass Json\nobject Decoder\n",
            "scala/Y.scala": "package io.circe\n",  # the importer: its package anchors relative imports
        },
    )
    kt = b"package x\nimport com.acme.asName\nimport com.acme.util.Util.X\nimport com.acme.util.*\nimport com.acme.Legacy\n"
    assert iga.kotlin_imports(kt, "src/X.kt", g) == [
        {"src/Names.kt"},
        {"src/other/Util.kt"},
        set(),  # import contract C7: a package wildcard is its package object's edge, and kotlin has none
        {"java/com/acme/Legacy.java"},  # a JVM language imports Java classes by Java's rule
    ]
    sc = b"package io.circe\nimport io.circe.{ Json, Decoder => D }\nimport io.circe.export.Exported\nimport syntax._\n"
    assert iga.scala_imports(sc, "scala/Y.scala", g) == [
        {"scala/Json.scala"},
        {"scala/Json.scala"},
        {"scala/Dec.scala"},  # a backquoted package segment is the plain name
        {"scala/pkg.scala"},  # relative to the enclosing package: io.circe.syntax
    ]


@needs_ts
def test_dart_package_uris_resolve_through_pubspec(tmp_path):
    g = _group(
        tmp_path,
        {
            "pkgs/http/pubspec.yaml": "name: http\n",
            "pkgs/http/lib/http.dart": "",
            "pkgs/http/lib/src/client.dart": "",
            "pkgs/web/lib/web.dart": "",
        },
    )
    src = b"import 'package:http/http.dart';\nimport 'client.dart';\nimport 'package:async/async.dart';\nimport 'dart:io';\n"
    # `package:async` is not in the repo and `dart:io` is the SDK: neither is scored
    assert iga.dart_imports(src, "pkgs/http/lib/src/base.dart", g) == [
        {"pkgs/http/lib/http.dart"},
        {"pkgs/http/lib/src/client.dart"},
    ]


@needs_ts
def test_haskell_shell_and_solidity_rules(tmp_path):
    g = _group(
        tmp_path,
        {
            "src/ShellCheck/AST.hs": "",
            "themes/powerline/powerline.base.bash": "",
            "themes/gitline/powerline.base.bash": "",
            "lib/helpers.bash": "",
            "contracts/package.json": json.dumps({"name": "@openzeppelin/contracts"}),
            "contracts/access/Ownable.sol": "",
            "contracts/utils/Context.sol": "",
        },
    )
    assert iga.haskell_imports(b"import ShellCheck.AST\nimport Data.Map\n", "src/Main.hs", g) == [
        {"src/ShellCheck/AST.hs"},
        set(),
    ]
    sh = b'source "${BASH_IT?}/themes/powerline/powerline.base.bash"\n. ./lib/helpers.bash\nsource "$HOME/.rvm/scripts/rvm"\n'
    assert iga.shell_imports(sh, "x.bash", g) == [{"themes/powerline/powerline.base.bash"}, {"lib/helpers.bash"}, set()]
    sol = b'import "../utils/Context.sol";\nimport {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";\nimport "forge-std/Test.sol";\n'
    assert iga.solidity_imports(sol, "contracts/access/Foo.sol", g) == [
        {"contracts/utils/Context.sol"},
        {"contracts/access/Ownable.sol"},
        set(),
    ]


@needs_ts
def test_csharp_resolves_by_namespace_and_type_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            # file name and directory mean nothing: the type is found by what the file declares
            "src/Misc/Odd.cs": "namespace Acme.Util\n{\n    public class Helper { public enum Kind { A } }\n}\n",
            "src/Scoped.cs": "namespace Acme.Scoped;\n\npublic struct Pair { }\n",
            # declarations wrapped in #if / #region are still declarations
            "src/Wrapped.cs": "#if NET\n#region r\nnamespace Acme.Wrapped\n{\n    public interface IThing { }\n}\n#endregion\n#endif\n",
            "src/Partial1.cs": "namespace Acme.Util { public partial class Split { } }\n",
            "src/Partial2.cs": "namespace Acme.Util { public partial class Split { } }\n",
        },
    )
    src = (
        b"using System;\n"
        b"using Acme.Util;\n"  # a namespace: contract C7, no edge
        b"using static Acme.Util.Helper;\n"
        b"using static Acme.Util.Helper.Kind;\n"  # a nested type falls back to its owner
        b"using Pair = Acme.Scoped.Pair;\n"
        b"using Ns = Acme.Wrapped;\n"  # an alias of a namespace is a namespace
        b"global using static Acme.Util.Split;\n"
        b"using static Missing.Thing;\n"
        b"namespace Acme.Util { using Scoped; using static Helper; class C { void M() { using (var x = new D()) { } } } }\n"
    )
    assert iga.csharp_imports(src, "src/Use.cs", g) == [
        set(),  # System
        set(),
        {"src/Misc/Odd.cs"},
        {"src/Misc/Odd.cs"},
        {"src/Scoped.cs"},
        set(),
        {"src/Partial1.cs", "src/Partial2.cs"},  # a partial type is several files
        set(),
        set(),  # relative `using Scoped;` under Acme.Util is no namespace of the repo
        {"src/Misc/Odd.cs"},  # `using static Helper;` under the enclosing Acme.Util
    ]


def _star(hub, leaves):
    return {(leaf, hub) for leaf in leaves}


def test_hub_agreement_identical_graphs_agree_fully():
    nodes = [f"f{i}.py" for i in range(14)]
    edges = _star("f0.py", nodes[1:]) | _star("f1.py", nodes[3:])
    h = iga.hub_agreement(edges, set(edges), nodes)
    assert (h["overlap_at_k"], h["spearman"], h["k"], h["n"]) == (1.0, 1.0, 10, 14)


def test_hub_agreement_drops_when_the_engine_misses_the_hub():
    nodes = [f"f{i:02}.py" for i in range(30)]
    truth = {(f"f{i:02}.py", f"f{i - 20:02}.py") for i in range(20, 30)}  # f00-f09 are the hubs
    engine = {(f"f{i:02}.py", f"f{i - 10:02}.py") for i in range(20, 30)}  # f10-f19 instead
    h = iga.hub_agreement(engine, truth, nodes)
    assert h["overlap_at_k"] < 1.0
    assert h["spearman"] is not None and h["spearman"] < 1.0


def test_hub_agreement_is_none_for_thin_input():
    nodes = [f"f{i}.py" for i in range(9)]
    edges = _star("f0.py", nodes[1:])
    assert iga.hub_agreement(edges, edges, nodes) is None  # fewer than k files
    more = [f"f{i}.py" for i in range(12)]
    assert iga.hub_agreement(edges, set(), more) is None  # no truth edges


def test_hub_agreement_ignores_edges_outside_the_node_set_and_edge_order():
    nodes = [f"f{i}.py" for i in range(12)]
    truth = _star("f0.py", nodes[1:])
    a = iga.hub_agreement(truth | {("f1.py", "other.c")}, truth, nodes)
    b = iga.hub_agreement(set(reversed(sorted(truth))), truth, nodes)
    assert a == b == iga.hub_agreement(truth, truth, nodes)


def test_score_group_records_hubs_with_one_edge_per_file_of_a_statement(tmp_path):
    files = {f"pkg/m{i}.py": "" for i in range(12)}
    files["pkg/__init__.py"] = ""
    files["pkg/user.py"] = "from pkg import m1, m2\n"
    (tmp_path / "pkg").mkdir(exist_ok=True)
    for rel, text in files.items():
        (tmp_path / rel).write_text(text)
    langs = {rel: "python" for rel in files}
    r = iga.score_group(tmp_path, langs, {("pkg/user.py", "pkg/m1.py")}, ("python",))["python"]
    assert r["hubs"]["n"] == 14 and r["hubs"]["k"] == 10
    assert 0.0 <= r["hubs"]["overlap_at_k"] <= 1.0


def test_regressions_ignore_hub_fields_and_old_baselines_still_load():
    base = {"python": {"imports": 100, "engine_edges": 90, "precision_pct": 90.0, "recall_pct": 60.0}}
    cur = {"python": {"precision_pct": 90.0, "recall_pct": 60.0, "hub_overlap_at_10": 0.0, "hub_spearman": -1.0}}
    assert iga.regressions(cur, base) == []
    assert "n/a" in iga.render({"python": {**base["python"], "repos": "r", "files": 1, "fp": 0, "fn": 0}})


@needs_ts
def test_swift_resolves_by_target_and_declared_type_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            "Package.swift": (
                "import PackageDescription\n"
                'let package = Package(name: "P", targets: [\n'
                '  .target(name: "Core", dependencies: ["Odd"]),\n'
                '  .target(name: "Odd", path: "Vendor/odd"),\n'
                '  .testTarget(name: "CoreTests", dependencies: ["Core"]),\n'
                "])\n"
            ),
            # file name and directory mean nothing: the name is found by what the file declares
            "Sources/Core/Misc.swift": (
                "public struct Pair { public enum Kind { case a } }\n"
                "public protocol Proto {}\n"
                "public typealias Alias = Int\n"
                "public func helper() {}\n"
                "public let limit = 1\n"
                "public var counter = 0\n"
                "#if os(Linux)\npublic final class Wrapped {}\n#endif\n"
            ),
            "Sources/Core/Split1.swift": "public struct Split {}\n",
            "Sources/Core/Split2.swift": "extension Split {}\n",
            "Vendor/odd/Thing.swift": "public class Thing {}\n",
            "Tests/CoreTests/Pair.swift": "struct Pair {}\n",
        },
    )
    src = (
        b"import Foundation\n"
        b"import Core\n"  # a module: contract C7, no edge
        b"@testable import Core\n"
        b"@_exported import Odd\n"
        b"public import Core\n"
        b"import struct Core.Pair\n"
        b"import struct Core.Pair.Kind\n"  # a nested type falls back to its owner
        b"import protocol Core.Proto\n"
        b"import typealias Core.Alias\n"
        b"import func Core.helper\n"
        b"import let Core.limit\n"
        b"import var Core.counter\n"
        b"import class Core.Wrapped\n"
        b"import struct Core.Split\n"  # a type and its extension are two files
        b"import class Odd.Thing\n"  # a custom `path:` is honoured
        b"import struct WinSDK.CONSOLE_SCREEN_BUFFER_INFO\n"  # no target of the repo
        b"import struct Core.Missing\n"
    )
    assert iga.swift_imports(src, "Sources/App/Use.swift", g) == [
        set(),
        set(),
        set(),
        set(),
        set(),
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Misc.swift"},
        {"Sources/Core/Split1.swift", "Sources/Core/Split2.swift"},
        {"Vendor/odd/Thing.swift"},
        set(),
        set(),
    ]


@needs_ts
def test_powershell_import_module_dot_source_and_using_module(tmp_path):
    g = _group(
        tmp_path,
        {
            "a/m.psm1": "",
            "a/x.ps1": "",
            "bin/P.psd1": "",
            "lib/h.ps1": "",
        },
    )
    src = (
        b"Import-Module $PSScriptRoot\\..\\bin\\P.psd1 -DisableNameChecking\n"
        b"Import-Module -Name 'm.psm1'\n"
        b"Import-Module P\n"
        b'$r = . "$PSScriptRoot/x.ps1"\n'
        b". $f\n"
        b"using module m\n"
        b"using namespace System.IO\n"
        b"# . lib/h.ps1\n"
        b'$s = "Import-Module lib/h.ps1"\n'
        b"Import-Module -Force $root\\lib\\h.ps1\n"
        b"Import-Module Other\n"
    )
    assert iga.powershell_imports(src, "a/z.ps1", g) == [
        {"bin/P.psd1"},
        {"a/m.psm1"},
        {"bin/P.psd1"},
        {"a/x.ps1"},
        {"a/m.psm1"},
        {"lib/h.ps1"},
        set(),
    ]


@needs_ts
def test_tcl_source_literal_tail_and_package_provide(tmp_path):
    g = _group(
        tmp_path,
        {
            "m/main.tcl": "",
            "m/foo.tcl": "package provide foo::bar 1.0\n",
            "m/q.tcl": "",
            "m/a.tcl": "",
            "m/x/y.tcl": "",
            "tm/baz-1.2.tm": "",
        },
    )
    src = (
        b"source [file join $d x y.tcl]\n"
        b"source $d/a.tcl\n"
        b'source "q.tcl"\n'
        b"package require -exact foo::bar 1.0\n"
        b"package require baz\n"
        b"package require Tcl 8.6\n"
        b"source [lindex $a 0]\n"
        b"# source a.tcl\n"
        b'puts "source a.tcl"\n'
    )
    assert iga.tcl_imports(src, "m/main.tcl", g) == [
        {"m/x/y.tcl"},
        {"m/a.tcl"},
        {"m/q.tcl"},
        {"m/foo.tcl"},
        {"tm/baz-1.2.tm"},
        set(),
        set(),
    ]


def test_groovy_resolves_by_package_and_declared_type_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            # file name and directory mean nothing: the name is found by what the file declares
            "src/main/groovy/Misc.groovy": (
                "package a.b\n\n"
                "class Pair { static class Inner {} static int helper() { 1 } }\n"
                "interface Proto {}\n"
                "trait Walks {}\n"
                "enum Kind { A }\n"
                "@interface Marker {}\n"
            ),
            "x/Split1.groovy": "package a.b\nclass Split {}\n",
            "x/Split2.groovy": "package a.b\nclass Split {}\n",
            "scripts/build.gradle": "def x = 1\n",
            "scripts/Tool.groovy": "println 'hi'\n",
            "lib/c/Other.groovy": "package c\nclass Other {}\n",
            "lib/a/b/Native.java": "package a.b;\npublic class Native {}\n",
        },
    )
    src = (
        b"package app\n"
        b"import a.b.Pair\n"
        b"import a.b.Pair as P\n"
        b"import a.b.Pair.Inner\n"  # a nested name falls back to its owner
        b"import static a.b.Pair.helper\n"
        b"import static a.b.Pair.*\n"  # an owner's members: its file
        b"import a.b.*\n"  # a package: contract C7, no edge
        b"import a.b.Proto\n"
        b"import a.b.Walks\n"
        b"import a.b.Kind\n"
        b"import a.b.Marker\n"
        b"import a.b.Split\n"  # declared in two files
        b"import Tool\n"  # a script declares its file stem
        b"import c.Other\n"
        b"import a.b.Native\n"  # a Java class, by Java's path rule
        b"import java.util.List\n"
        b"import groovy.json.JsonSlurper\n"
        b"import a.b.Missing\n"
        b"// import c.Other\n"
        b"/* import c.Other */\n"
        b"def s = '''\nimport c.Other\n'''\n"
    )
    misc = {"src/main/groovy/Misc.groovy"}
    assert iga.groovy_imports(src, "app/Use.groovy", g) == [
        misc,
        misc,
        misc,
        misc,
        misc,
        set(),
        misc,
        misc,
        misc,
        misc,
        {"x/Split1.groovy", "x/Split2.groovy"},
        {"scripts/Tool.groovy"},
        {"lib/c/Other.groovy"},
        {"lib/a/b/Native.java"},
        set(),
        set(),
        set(),
    ]


def test_fortran_resolves_by_module_name_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            # the file name means nothing: the module is found by what the file declares
            "src/a_file.f90": "module Alpha_Mod\ncontains\n  module subroutine s()\n  end subroutine\nend module Alpha_Mod\n",
            "src/beta.F90": "! module ghost\nmodule beta\nend module beta\n",
            "src/dup1.f90": "module twin\nend module\n",
            "lib/dup2.f90": "module twin\nend module\n",
            "old/fixed.f": "c module cmt\n      module fixedmod\n      end module\n",
            "src/sub.f90": "submodule (alpha_mod) child\nend submodule\n",
            "src/iso_fortran_env.f90": "module iso_fortran_env\nend module\n",
            "inc/consts.inc": "integer :: k\n",
            "src/notes.txt": "module notmine\n",
        },
    )
    src = (
        b"program p\n"
        b"  use alpha_mod\n"  # case-insensitive
        b"  use :: beta\n"
        b"  USE beta, only: x\n"
        b"  use, non_intrinsic :: beta\n"
        b"  use, intrinsic :: iso_fortran_env\n"  # the standard's module: no edge
        b"  use twin\n"  # declared in two files
        b"  use fixedmod\n"
        b"  use ghost\n"  # only in a comment
        b"  use child\n"  # a submodule is not usable
        b"  use notmine\n"  # not a Fortran file
        b"  use missing_mod\n"
        b"  ! use beta\n"
        b"  use_count = 3\n"  # not a use statement
        b"  module_x = 1\n"
        b"  include 'consts.inc'\n"
        b"  include 'absent.inc'\n"
        b"end program\n"
    )
    assert iga.fortran_imports(src, "inc/main.f90", g) == [
        {"src/a_file.f90"},
        {"src/beta.F90"},
        {"src/beta.F90"},
        {"src/beta.F90"},
        set(),
        {"src/dup1.f90", "lib/dup2.f90"},
        {"old/fixed.f"},
        set(),
        set(),
        set(),
        set(),
        {"inc/consts.inc"},
        set(),
    ]


def test_fortran_fixed_form_comment_column_one_is_not_a_statement(tmp_path):
    g = _group(tmp_path, {"a.f90": "module a\nend module\n"})
    src = b"c      use a\n*      use a\n      use a\n"
    assert iga.fortran_imports(src, "old/x.f", g) == [{"a.f90"}]


def test_objc_framework_include_finds_the_header_in_a_framework_the_repo_builds(tmp_path):
    g = _group(
        tmp_path,
        {
            "Kit.podspec": "Pod::Spec.new do |s|\n  s.header_dir = 'KitHeaders'\nend\n",
            "Source/A.h": "",
            "Source/Sub/B+Private.h": "",
            "Source/C.mm": "",
            "Other/Kit/D.h": "",
            "Elsewhere.xcodeproj/project.pbxproj": "",
            "Source/E.h": "",
        },
    )
    src = (
        b"#import <Kit/A.h>\n"  # the framework is `Kit.podspec`
        b"#import <KitHeaders/B+Private.h>\n"  # header_dir, a flattened path tail
        b"#include <Kit/C.h>\n"  # absent header
        b"#import <Kit/D.h>\n"  # a real path wins: Other/Kit/D.h
        b"#import <Elsewhere/E.h>\n"  # `Elsewhere.xcodeproj`
        b"#import <Foundation/Foundation.h>\n"  # not this repo's framework
        b"#import <vector>\n"
        b'#import "A.h"\n'
        b"@import UIKit;\n"
    )
    expect = [
        {"Source/A.h"},
        {"Source/Sub/B+Private.h"},
        set(),
        {"Other/Kit/D.h"},
        {"Source/E.h"},
        set(),
        set(),
        {"Source/A.h"},  # `"A.h"` quoted: not beside the file, so by suffix
    ]
    for rel in ("inc/main.m", "inc/main.mm", "inc/main.h"):
        assert iga.EXTRACTORS["objective-c"](src, rel, g) == expect


def test_c_angle_include_searches_only_the_include_path(tmp_path):
    """#8161: libuv's `<errno.h>` is libc's, not include/uv/errno.h -- libuv's `-Iinclude` reaches that file only as
    `uv/errno.h`. An angle include resolves through an include root: the repo root, include/ or inc/, or a directory a
    multi-segment include of the repo resolves through (test/gtest/, from `"gtest/gtest.h"`)."""
    g = _group(
        tmp_path,
        {
            "include/uv.h": '#include "uv/errno.h"\n',
            "include/uv/errno.h": "",
            "src/core.c": "",
            "adapters/poll.h": "",
            "hiredis.h": "",
            "test/gtest/gtest/gtest.h": "",
            "test/gtest/gtest/gtest-spi.h": "",
            "test/a.cc": '#include "gtest/gtest.h"\n',
        },
    )
    src = (
        b"#include <errno.h>\n"  # libc: include/uv/ is not on the include path
        b"#include <uv/errno.h>\n"  # through include/
        b"#include <uv.h>\n"
        b"#include <poll.h>\n"  # adapters/ is not on it either
        b"#include <hiredis.h>\n"  # the repo root is
        b"#include <gtest/gtest-spi.h>\n"  # test/gtest/ is, by test/a.cc's include
        b'#include "errno.h"\n'  # quoted: beside the file, else any directory (build config we do not read)
    )
    assert iga.c_imports("c")(src, "src/core.c", g) == [
        set(),
        {"include/uv/errno.h"},
        {"include/uv.h"},
        set(),
        {"hiredis.h"},
        {"test/gtest/gtest/gtest-spi.h"},
        {"include/uv/errno.h"},
    ]
    assert g.include_roots() == {"", "include", "test/gtest"}


def test_c_does_not_use_the_objc_framework_rule(tmp_path):
    g = _group(tmp_path, {"Kit.podspec": "", "Source/A.h": ""})
    assert iga.EXTRACTORS["c"](b"#include <Kit/A.h>\n", "x.c", g) == [set()]


def test_matlab_resolves_by_package_and_name_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            "+pkg/+sub/Widget.m": "classdef Widget\nend\n",
            "+pkg/helper.m": "function helper()\nend\n",
            "@Old/Old.m": "classdef Old\nend\n",
            "@Old/method.m": "function method(o)\nend\n",
            "ETS.m": "classdef ETS\nend\n",
            "+pkg/private/hidden.m": "function hidden()\nend\n",
        },
    )
    src = (
        b"import pkg.sub.Widget\n"
        b"  import pkg.helper;\n"
        b"import pkg.sub.*\n"  # a package: no file, no edge
        b"import ETS.*\n"  # a class: its static members
        b"import ETS.make\n"  # a member: the owner's file
        b"import Old.*\n"
        b"import pkg.Widget pkg.helper\n"  # two arguments on one line
        b"import matlab.unittest.TestCase\n"  # external
        b"import pkg.sub.Missing\n"
        b"% import pkg.helper\n"
        b"%{\nimport ETS.*\n%}\n"
        b"important = 1\n"
        b"import = 2\n"
    )
    assert iga.matlab_imports(src, "t/test.m", g) == [
        {"+pkg/+sub/Widget.m"},
        {"+pkg/helper.m"},
        set(),
        {"ETS.m"},
        {"ETS.m"},
        {"@Old/Old.m"},
        set(),
        {"+pkg/helper.m"},
        set(),
        set(),
    ]


def test_elixir_resolves_by_module_name_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            "lib/a/conn.ex": "defmodule App.Conn do\n  defmodule Inner do\n  end\nend\n",
            "lib/b/router.ex": "defmodule App.Router do\nend\n",
            "lib/c/util.exs": "defmodule App.Util do\nend\n",
            "lib/d/doc.ex": 'defmodule App.Doc do\n  @moduledoc """\n  alias App.Router\n  """\nend\n',
        },
    )
    src = (
        b"defmodule App.Main do\n"
        b"  alias App.Conn\n"
        b"  alias App.Router, as: R\n"
        b"  import App.Util, only: [x: 1]\n"
        b"  require App.Conn.Inner\n"
        b"  use App.Doc\n"
        b"  alias App.{Conn,\n    Router}\n"
        b"  alias __MODULE__.Missing\n"
        b"  alias Elixir.App.Conn\n"
        b"  alias Plug.Conn\n"  # external
        b"  alias App\n"  # a namespace prefix: no file
        b"  # alias App.Router\n"
        b'  @doc """\n  alias App.Util\n  """\n'
        b"  alias App.Main\n"  # own module: no edge
        b"  import :erlang\n"
        b"end\n"
    )
    assert iga.elixir_imports(src, "lib/main.ex", g) == [
        {"lib/a/conn.ex"},
        {"lib/b/router.ex"},
        {"lib/c/util.exs"},
        {"lib/a/conn.ex"},
        {"lib/d/doc.ex"},
        {"lib/a/conn.ex"},
        {"lib/b/router.ex"},
        set(),
        {"lib/a/conn.ex"},
        set(),
        set(),
        set(),
    ]


def test_erlang_resolves_by_module_and_include_never_by_guess(tmp_path):
    g = _group(
        tmp_path,
        {
            "src/app_sup.erl": "-module(app_sup).\n",
            "src/app_handler.erl": "-module(app_handler).\n",
            "src/sub/app_util.erl": "-module(app_util).\n",
            "src/app.hrl": "",
            "include/app_defs.hrl": "",
            "src/sub/local.hrl": "",
            "test/t_SUITE.erl": "-module(t_SUITE).\n",
            "apps/core/include/core.hrl": "",
        },
    )
    src = (
        b"-module(app_main).\n"
        b'-include("app.hrl").\n'  # beside this file
        b'-include("app_defs.hrl").\n'  # ../include/
        b'-include("sub/local.hrl").\n'  # relative path
        b'-include_lib("core/include/core.hrl").\n'  # app dir in the repo
        b'-include_lib("kernel/include/file.hrl").\n'  # OTP: external
        b'-include("missing.hrl").\n'
        b"-behaviour(app_handler).\n"
        b"-behavior(app_sup).\n"
        b"-behaviour(gen_server).\n"  # OTP
        b"-import(app_util, [f/1, g/2]).\n"
        b"-import(lists, [map/2]).\n"
        b"-behaviour(app_main).\n"  # own module: no edge
        b'% -include("app.hrl").\n'
        b'X = "-behaviour(app_sup).",\n'
        b"-spec f() -> ok.\n"
    )
    assert iga.erlang_imports(src, "src/app_main.erl", g) == [
        {"src/app.hrl"},
        {"include/app_defs.hrl"},
        {"src/sub/local.hrl"},
        {"apps/core/include/core.hrl"},
        set(),
        set(),
        {"src/app_handler.erl"},
        {"src/app_sup.erl"},
        set(),
        {"src/sub/app_util.erl"},
        set(),
        set(),
    ]
    # an .hrl is found from a test directory by the same rule, and a file's own include is no edge
    assert iga.erlang_imports(b'-include("../include/app_defs.hrl").\n', "test/t_SUITE.erl", g) == [
        {"include/app_defs.hrl"}
    ]
    assert iga.erlang_imports(b'-include("app.hrl").\n', "src/app.hrl", g) == [set()]


def test_ocaml_resolves_by_module_name_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            "src/lib_util.ml": "",
            "src/lib_util.mli": "",
            "src/lib_core.ml": "",
            "src/sub/lib_extra.ml": "",
            "src/lib.ml": "",
            "src/lib_main.ml": "",
        },
    )
    src = (
        b"open Lib_util\n"
        b"open! Lib_core\n"
        b"  include Lib_extra\n"
        b"open Lib.Term.Syntax\n"  # first component with a file
        b"open Stdlib.Printf\n"  # external
        b"open Missing\n"
        b"let f () = let open Lib_core in x\n"
        b"open Lib_main\n"  # own module: no edge
        b"(* open Lib_core (* nested open Lib_util *) open Lib_util *)\n"
        b'let s = "open Lib_core"\n'
        b"let c = '\"'\n"
        b"open Lib_util\n"  # a char literal does not start a string
        b"module X = Lib_core\n"  # an alias is not an import statement
        b"let y = Lib_core.z\n"
    )
    assert iga.ocaml_imports(src, "src/lib_main.ml", g) == [
        {"src/lib_util.ml", "src/lib_util.mli"},
        {"src/lib_core.ml"},
        {"src/sub/lib_extra.ml"},
        {"src/lib.ml"},
        set(),
        set(),
        {"src/lib_core.ml"},
        set(),
        {"src/lib_util.ml", "src/lib_util.mli"},
    ]
    # an .mli sees its own .ml's module as itself
    assert iga.ocaml_imports(b"open Lib_util\n", "src/lib_util.mli", g) == [set()]
    assert iga.ocaml_imports(b"", "src/lib_util.ml", g) == []


def test_julia_resolves_by_module_name_never_by_path(tmp_path):
    g = _group(
        tmp_path,
        {
            "src/Pkg.jl": "module Pkg\nend\n",
            "src/graphs/Local.jl": "module Local\nmodule Inner\nend\nend\n",
            "src/other/Sub.jl": "baremodule Sub\nend\n",
            "src/Test/Test.jl": "module Test\nend\n",
            "src/main.jl": "",
        },
    )
    src = (
        b"using .Local\n"
        b"import ..Pkg: a, b\n"  # after `:` only the first path
        b"using Pkg.Local.Inner\n"  # absolute: entry, then deepest declared submodule
        b"using .Sub, .Local\n"  # each path of a list
        b"using Pkg\n"  # package entry file
        b"using Test\n"  # stdlib, not the repo's own `module Test`
        b"using Statistics: mean\n"  # external
        b"using .Missing\n"
        b"import .Sub as S\n"
        b"using Pkg # using .Local\n"
        b"#= using .Local\nusing .Sub =#\n"
        b'x = "using .Local"\n'
        b'doc = """\nusing .Sub\n"""\n'
        b"c = '\"'\n"
        b"using .Sub\n"  # a char literal does not start a string
        b'include("other/Sub.jl")\n'  # not an import statement
    )
    assert iga.julia_imports(src, "src/main.jl", g) == [
        {"src/graphs/Local.jl"},
        {"src/Pkg.jl"},
        {"src/graphs/Local.jl"},
        {"src/other/Sub.jl"},
        {"src/graphs/Local.jl"},
        {"src/Pkg.jl"},
        set(),
        set(),
        set(),
        {"src/other/Sub.jl"},
        {"src/Pkg.jl"},
        {"src/other/Sub.jl"},
    ]
    # a file's reference to its own module is no edge; an empty file has no statements
    assert iga.julia_imports(b"using .Local\n", "src/graphs/Local.jl", g) == [set()]
    assert iga.julia_imports(b"", "src/main.jl", g) == []


def test_nim_resolves_by_path_and_reads_every_import_form(tmp_path):
    g = _group(
        tmp_path,
        {
            "lib/pkg.nim": "",
            "lib/pkg/a.nim": "",
            "lib/pkg/b.nim": "",
            "lib/pkg/sub/c.nim": "",
            "lib/util.nim": "",
            "lib/pkg/loc.nim": "",
            "lib/main.nim": "",
        },
    )
    src = (
        b"import pkg/a\n"
        b"import pkg/[a, b, sub/c]\n"  # a bracket group scores each leaf
        b"import ./util, std/os\n"  # a list; std is the stdlib
        b"from pkg/b import x, y\n"  # only the module
        b"include util\n"
        b"import\n  pkg/a,\n  pkg/b\n"  # continues after a bare import and a trailing comma
        b"import pkg/a as pa\n"
        b"import pkg/b except foo, bar\n"
        b"import missing\n"
        b"export pkg/a\n"  # not an import
        b"#[ import util\n  #[ nested ]# import pkg/a ]#\n"
        b"##[ import pkg/b ]##\n"
        b"# import util\n"
        b'x = "import util"\n'
        b'y = """\nimport pkg/a\n"""\n'
        b"z = a[0]#import util\n"
        b"  import pkg/loc\n"  # indented (inside a `when`)
    )
    assert iga.nim_imports(src, "lib/main.nim", g) == [
        {"lib/pkg/a.nim"},
        {"lib/pkg/a.nim"},
        {"lib/pkg/b.nim"},
        {"lib/pkg/sub/c.nim"},
        {"lib/util.nim"},
        set(),
        {"lib/pkg/b.nim"},
        {"lib/util.nim"},
        {"lib/pkg/a.nim"},
        {"lib/pkg/b.nim"},
        {"lib/pkg/a.nim"},
        {"lib/pkg/b.nim"},
        set(),
        {"lib/pkg/loc.nim"},
    ]
    # a relative path resolves from the importing file; a file's own module is no edge
    assert iga.nim_imports(b"import ../util\nimport a\n", "lib/pkg/b.nim", g) == [{"lib/util.nim"}, {"lib/pkg/a.nim"}]
    assert iga.nim_imports(b"import b\n", "lib/pkg/b.nim", g) == [set()]
    assert iga.nim_imports(b"", "lib/main.nim", g) == []


def test_hcl_local_module_source_names_a_directory(tmp_path):
    g = _group(
        tmp_path,
        {"main.tf": "", "modules/vpc/a.tf": "", "modules/vpc/b.tf": "", "modules/vpc/README.md": "", "env/x.tf": ""},
    )
    src = (
        b'# module "c" { source = "./modules/vpc" }\n'
        b'module "vpc" {\n  source = "./modules/vpc"\n  tags = { source = "./nope" }\n}\n'
        b'module "up" {\n  providers = { aws = aws }\n  source = "../modules/vpc"\n}\n'
        b'module "reg" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
        b'module "git" {\n  source = "git::https://example.com/x.git"\n}\n'
        b'module "gone" {\n  source = "./missing"\n}\n'
        b'resource "aws_s3_object" "o" {\n  source = "./modules/vpc"\n}\n'
        b'locals {\n  t = <<EOT\nmodule "h" {\n  source = "./modules/vpc"\n}\nEOT\n}\n'
    )
    both = {"modules/vpc/a.tf", "modules/vpc/b.tf"}
    assert iga.hcl_imports(src, "main.tf", g) == [both, set(), set(), set(), set()]
    assert iga.hcl_imports(src, "env/x.tf", g) == [set(), both, set(), set(), set()]
    assert iga.hcl_imports(b"", "main.tf", g) == []
    own = b'module "m" {\n  source = "./"\n}\n'
    assert iga.hcl_imports(own, "modules/vpc/a.tf", g) == [{"modules/vpc/b.tf"}]
