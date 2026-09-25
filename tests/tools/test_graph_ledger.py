"""#3641: the graph comparison ledger -- import disagreement causes, and the shared ledger
plumbing (a symbol type's merge never stales the other's shapes; verdicts move the
validated numbers only as the credit geometry says)."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import graph_ledger as gl
import import_graph_accuracy as iga

# The scala truth side parses with tree-sitter; the full-suite job does not install it.
needs_ts = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_language_pack") is None, reason="tree-sitter-language-pack not installed"
)


def test_import_cause_layers():
    union = {"src/a/foo.py", "src/b/bar.py"}
    assert iga.import_cause("fn", {"x/a.h", "y/a.h"}, union, [], True) == "fn:truth-names-several-files"
    assert iga.import_cause("fn", {"src/a/foo.py"}, union, ["..a.foo"], True) == "fn:token-unresolved"
    assert (
        iga.import_cause("fn", {"m/com/x/meta/util.kt"}, union, ["com.x.meta.isPrimary"], True)
        == "fn:declaration-unresolved"
    )
    assert iga.import_cause("fn", {"src/a/foo.py"}, union, ["other"], True) == "fn:capture-missed"
    assert iga.import_cause("fn", {"src/a/foo.py"}, union, [], False) == "fn:capture-none-in-file"
    assert iga.import_cause("fp", {"lib/foo.py"}, set(), [], True) == "fp:truth-sees-no-import-in-file"
    assert iga.import_cause("fp", {"lib/foo.py"}, union, [], True) == "fp:same-name-other-path"
    assert iga.import_cause("fp", {"tests/test_zed.py"}, union, [], True) == "fp:target-is-test-file"
    assert iga.import_cause("fp", {"lib/zed.py"}, union, [], True) == "fp:target-not-imported"


def _results(cause, count):
    return {
        "go": {
            "tp": 90,
            "fp": 10,
            "fn": 10,
            "precision_pct": 90.0,
            "recall_pct": 90.0,
            "top_causes": [{"cause": cause, "count": count, "examples": []}],
        }
    }


def test_verdicts_move_validated_numbers_by_the_credit_geometry(tmp_path):
    ledger = tmp_path / "ledger.json"
    counts = ("tp", "fp", "tp", "fn")
    fp = _results("fp:x", 10)
    gl.merge(fp, "call", ledger)
    assert gl.validated(fp, "call", counts, ledger)["go"]["precision_pct"] == 90.0  # open: as raw

    data = __import__("tri_comparison_ledger").load_ledger(ledger)
    (key,) = data["entries"]
    data["entries"][key].update(status="validated", credit_tools=["gitgalaxy"])
    __import__("tri_comparison_ledger").save_ledger(data, ledger)
    v = gl.validated(fp, "call", counts, ledger)["go"]
    assert v["precision_pct"] == 100.0 and v["open_shapes"] == 0  # GitGalaxy was right

    fn = _results("fn:y", 10)
    gl.merge(fn, "call", ledger)
    data = __import__("tri_comparison_ledger").load_ledger(ledger)
    data["entries"]["go/call/y/agree[tree_sitter]_vs[gitgalaxy]"].update(status="validated", credit_tools=[])
    __import__("tri_comparison_ledger").save_ledger(data, ledger)
    assert gl.validated(fn, "call", counts, ledger)["go"]["recall_pct"] == 100.0  # tree-sitter was wrong


def test_merging_one_symbol_type_never_stales_the_other(tmp_path):
    ledger = tmp_path / "ledger.json"
    gl.merge(_results("fp:x", 1), "call", ledger)
    gl.merge(_results("fn:z", 1), "import", ledger)
    entries = __import__("tri_comparison_ledger").load_ledger(ledger)["entries"]
    assert all(e["still_reproduces"] for e in entries.values())
    assert {e["symbol_type"] for e in entries.values()} == {"call", "import"}


@needs_ts
def test_scala_import_is_not_a_declaration(tmp_path):
    """#3641: `import cats.data.OneAnd` in io.circe declared nothing named `cats`; indexing it
    as a declaration resolved every external `cats.*` import to every importing file."""
    (tmp_path / "A.scala").write_text("package io.circe\nimport cats.data.OneAnd\nobject A\n")
    (tmp_path / "B.scala").write_text("package io.circe\nimport cats.data.OneAnd\nobject B\n")
    group = iga.Group({"A.scala": "scala", "B.scala": "scala"}, tmp_path)
    assert iga.scala_imports((tmp_path / "A.scala").read_bytes(), "A.scala", group) == [set()]


@needs_ts
def test_scala_package_wildcard_is_its_package_object_only(tmp_path):
    """Import contract C7: a whole-package wildcard is an edge to the package object, or none."""
    (tmp_path / "package.scala").write_text("package io\npackage object circe\n")
    (tmp_path / "Json.scala").write_text("package io.circe\nclass Json\n")
    (tmp_path / "Use.scala").write_text("package app\nimport io.circe._\nimport other.pkg._\n")
    files = {f: "scala" for f in ("package.scala", "Json.scala", "Use.scala")}
    group = iga.Group(files, tmp_path)
    got = iga.scala_imports((tmp_path / "Use.scala").read_bytes(), "Use.scala", group)
    assert got == [{"package.scala"}, set()]


@needs_ts
def test_scala_member_imports_never_cut_into_the_package(tmp_path):
    """#3641: `munit.FunSuite` (retried under io.circe) and `io.circe.optics.JsonPath` (optics not
    in the repo) are not the io.circe package object; `io.circe.syntax.EncoderOps` is syntax's."""
    (tmp_path / "circe.scala").write_text("package io\npackage object circe\n")
    (tmp_path / "syntax.scala").write_text("package io.circe\npackage object syntax\n")
    src = b"package io.circe.bench\nimport munit.FunSuite\nimport io.circe.optics.JsonPath\nimport io.circe.syntax.EncoderOps\n"
    (tmp_path / "Use.scala").write_bytes(src)
    files = {f: "scala" for f in ("circe.scala", "syntax.scala", "Use.scala")}
    group = iga.Group(files, tmp_path)
    assert iga.scala_imports(src, "Use.scala", group) == [set(), set(), {"syntax.scala"}]
