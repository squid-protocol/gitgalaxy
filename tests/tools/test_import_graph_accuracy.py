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
