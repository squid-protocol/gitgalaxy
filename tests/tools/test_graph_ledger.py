"""#3641: the graph comparison ledger -- import disagreement causes, and the shared ledger
plumbing (a symbol type's merge never stales the other's shapes; verdicts move the
validated numbers only as the credit geometry says)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import graph_ledger as gl
import import_graph_accuracy as iga


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
