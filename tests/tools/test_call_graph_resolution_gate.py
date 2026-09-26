"""call_graph_resolution.py --ci: the Level 2 gate reads a DROP in a gated python
metric beyond the tolerance as a regression, and never a rise."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import call_graph_resolution as cgr
import callgraph_refs


def test_gated_metrics_flatten_the_scored_result():
    py = {
        "confident": {"agree": 98, "wrong": 2, "precision_pct": 98.0},
        "ambiguous": {"agree": 1, "wrong": 1, "precision_pct": 50.0},
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "pyan_edges": 3492,
        "decorator": {"agree": 575, "wrong": 0, "precision_pct": 100.0},
        "recall_with_decorators_pct": 67.9,
        "reference_edges": {"agree": 322, "wrong": 1, "precision_pct": 99.7},
        "recall_all_kinds_pct": 77.3,
    }
    assert cgr.gated_metrics(py) == {
        "confident_precision_pct": 98.0,
        "confident_judged": 100,
        "ambiguous_precision_pct": 50.0,
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "pyan_edges": 3492,
        "decorator_precision_pct": 100.0,
        "decorator_judged": 575,
        "recall_with_decorators_pct": 67.9,
        "reference_precision_pct": 99.7,
        "reference_judged": 323,
        "recall_all_kinds_pct": 77.3,
    }


def test_regressions_respect_the_tolerance_and_ignore_the_ungated_metric():
    base = {
        "confident_precision_pct": 98.7,
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "ambiguous_precision_pct": 50.0,
    }
    ok = {
        "confident_precision_pct": 98.3,
        "recall_pct": 40.0,
        "resolution_recall_pct": 71.8,
        "ambiguous_precision_pct": 0.0,
    }
    assert cgr.regressions(ok, base) == []
    bad = dict(ok, confident_precision_pct=98.0)
    assert cgr.regressions(bad, base) == ["python: confident_precision_pct 98.7 -> 98.0"]


def test_typescript_metrics_report_the_checkers_external_verdict():
    ts = {
        "reference": "tsc",
        "reference_version": cgr.TYPESCRIPT_VERSION,
        "confident": {
            "agree": 96,
            "wrong": 1,
            "external": 3,
            "unmapped": 7,
            "precision_pct": 99.0,
            "strict_precision_pct": 96.0,
        },
        "ambiguous": {"agree": 1, "wrong": 1, "precision_pct": 50.0},
        "recall_pct": 56.9,
        "resolution_recall_pct": 73.7,
        "pyan_edges": 2661,
    }
    m = cgr.gated_metrics(ts)
    assert m["confident_judged"] == 97
    assert (m["confident_external"], m["confident_strict_precision_pct"], m["confident_unmapped"]) == (3, 96.0, 7)
    assert "decorator_precision_pct" not in m and "reference_precision_pct" not in m
    base = dict(m, recall_pct=60.0)
    assert cgr.regressions(m, base, "typescript") == ["typescript: recall_pct 60.0 -> 56.9"]


def test_verdict_order_agree_wrong_external_unconfirmed():
    a, b, c = ("f.ts", "caller", 1), ("f.ts", "trim", 9), ("g.ts", "trim", 3)
    ref = cgr.RefGraph({}, {(a, b)}, {(a, "trim"): {b}}, {(a, "trim"), (a, "has")})
    assert cgr._verdict(ref, a, b) == "agree"
    assert cgr._verdict(ref, a, c) == "wrong"  # the reference links the same name elsewhere
    assert cgr._verdict(ref, a, ("h.ts", "has", 5)) == "external"
    assert cgr._verdict(ref, a, ("h.ts", "save", 5)) == "unconfirmed"


def test_ts_callgraph_resolves_calls_with_the_type_checker(tmp_path):
    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    env = callgraph_refs.node_env()
    # a typescript whose package has the JavaScript compiler API: 7.x (the native
    # port, what a bare `npm install -g typescript` gives) has none
    probe = "process.exit(typeof require('typescript').createProgram === 'function' ? 0 : 1)"
    if subprocess.run(["node", "-e", probe], env=env, capture_output=True).returncode:
        pytest.skip("no typescript with the JavaScript compiler API (<= 6.x) on NODE_PATH")
    (tmp_path / "util.ts").write_text("export function clone(x: number) {\n  return x;\n}\n")
    (tmp_path / "main.ts").write_text(
        'import { clone } from "./util";\n'
        "class Str {\n"
        "  trim() {\n"
        "    return 1;\n"
        "  }\n"
        "}\n"
        "export const run = (s: string, t: Str) => {\n"
        "  s.trim();\n"
        "  t.trim();\n"
        "  new Str();\n"
        "  return clone(1);\n"
        "};\n"
    )
    out = subprocess.run(
        ["node", str(cgr.TOOLS / "ts_callgraph.js"), str(tmp_path)], env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    g = json.loads(out.stdout)
    run = ["main.ts", "run", 7]
    assert sorted(g["defs"]) == [run, ["main.ts", "trim", 3], ["util.ts", "clone", 1]]
    # each edge carries its first call site: `t.trim()` on line 9, `clone(1)` on line 11
    assert sorted(g["edges"]) == [[run, ["main.ts", "trim", 3], 9], [run, ["util.ts", "clone", 1], 11]]
    assert g["external"] == [[run, "trim"]]  # s.trim() is String.prototype.trim
