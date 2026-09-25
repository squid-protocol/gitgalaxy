"""import_graph_accuracy.py: the parser side resolves each language's imports by
the language's own rule, and the gate reads a DROP as a regression."""

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


try:
    import tree_sitter_language_pack  # noqa: F401

    _HAS_TS = True
except ImportError:
    _HAS_TS = False
needs_ts = pytest.mark.skipif(not _HAS_TS, reason="tree-sitter-language-pack not installed")


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
