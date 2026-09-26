"""call_graph_resolution.py --ci: the Level 2 gate reads a DROP in a gated python
metric beyond the tolerance as a regression, and never a rise."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import call_graph_resolution as cgr


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
