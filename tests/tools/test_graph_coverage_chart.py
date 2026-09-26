"""The graph coverage chart (#3796): a pure function of the committed baselines and the graph
comparison ledger, so every case here builds its own small baseline and ledger."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import graph_coverage_chart as gcc
import graph_ledger as gl


def _ledger(tmp_path, entries):
    """Entries as (language, symbol_type, cause, count, status, credit)."""
    results = {}
    for lang, _st, cause, count, _status, _credit in entries:
        results.setdefault(lang, {"top_causes": []})["top_causes"].append(
            {"cause": cause, "count": count, "examples": []}
        )
    out = {}
    for lang, groups in gl.shape_groups(results, entries[0][1]).items():
        for g, (_l, st, cause, count, status, credit) in zip(groups, [e for e in entries if e[0] == lang]):
            out[g.shape_key] = {
                "language": lang,
                "symbol_type": st,
                "metric": cause.split(":", 1)[1],
                "agreeing_tools": sorted(g.agreeing_tools),
                "dissenting_tools": sorted(g.dissenting_tools),
                "last_seen_count": count,
                "still_reproduces": True,
                "status": status,
                "credit_tools": credit,
            }
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"entries": out}))
    return path


IMPORTS = {
    "go": {
        "engine_edges": 10,
        "fp": 2,
        "imports": 12,
        "fn": 1,
        "precision_pct": 80.0,
        "recall_pct": 91.7,
        "files": 5,
        "repos": "a/b, c/d",
    },
    "java": {
        "engine_edges": 400,
        "fp": 0,
        "imports": 400,
        "fn": 0,
        "precision_pct": 100.0,
        "recall_pct": 100.0,
        "files": 90,
        "repos": "x/y",
    },
}


def test_a_verdict_moves_only_its_side_and_clears_only_its_star(tmp_path):
    base = tmp_path / "imports.json"
    base.write_text(json.dumps(IMPORTS))
    ledger = _ledger(
        tmp_path,
        [
            ("go", "import", "fp:same-name-other-path", 2, "validated", ["gitgalaxy"]),  # GitGalaxy was right
            ("go", "import", "fn:capture-missed", 1, "unvalidated", []),
        ],
    )
    cells = gcc.import_cells(base, ledger)
    go = cells["go"]
    assert (go.precision, go.raw_precision) == (100.0, 80.0)  # both FPs credited back
    assert go.recall == 91.7  # an open shape counts exactly as raw
    assert (gcc._star(go, "P"), gcc._star(go, "R")) == ("", "*")
    assert (go.n_precision, go.n_recall, go.small) == (10, 12, True)
    assert cells["java"].open_shapes == 0 and not cells["java"].small


def test_resolution_cells_name_their_reference(tmp_path):
    (tmp_path / "call_graph_resolution_typescript_baseline.json").write_text(
        json.dumps(
            {
                "confident_precision_pct": 99.9,
                "recall_pct": 57.1,
                "confident_judged": 1520,
                "pyan_edges": 2661,
                "reference_version": "6.0.2",
            }
        )
    )
    cells = gcc.resolution_cells(tmp_path)
    assert list(cells) == ["typescript"]  # python has no baseline in tmp_path: not measured
    ts = cells["typescript"]
    assert (ts.reference, ts.n, ts.precision, ts.recall) == ("tsc 6.0.2", 2661, 99.9, 57.1)


def _data(tmp_path):
    base = tmp_path / "imports.json"
    base.write_text(json.dumps(IMPORTS))
    ledger = tmp_path / "empty.json"
    ledger.write_text(json.dumps({"entries": {}}))
    return {"imports": gcc.import_cells(base, ledger), "calls": {}, "resolution": {}}


def test_the_chart_lists_every_unmeasured_language_and_mutes_small_n(tmp_path):
    data = _data(tmp_path)
    languages = ["cobol", "go", "java", "swift"]
    svg = gcc.render_svg(data, languages)
    assert "Not measured in any panel (2 of 4)" in svg and "cobol, swift" in svg
    assert "imports 2, callee names 0, call resolution 0 of 4 languages" in svg
    assert gcc._MUTED in svg  # go: 12 imports, below SMALL_N
    assert "a/b +1" in svg  # first repo, and how many more
    md = gcc.render_markdown(data, languages)
    assert "| go | 80.0% / 91.7% (12, small n) | not measured | not measured |" in md
    assert "Not measured in any panel (2 of 4): cobol, swift." in md


def test_history_appends_only_when_a_number_moves(tmp_path):
    data = _data(tmp_path)
    path = tmp_path / "history.csv"
    assert gcc.append_history(path, gcc.history_rows(data, "sha1", "2026-09-26T00:00:00Z"))
    assert not gcc.append_history(path, gcc.history_rows(data, "sha2", "2026-09-27T00:00:00Z"))
    data["imports"]["go"].recall = 100.0
    assert gcc.append_history(path, gcc.history_rows(data, "sha3", "2026-09-28T00:00:00Z"))
    lines = path.read_text().splitlines()
    assert lines[0].startswith("timestamp_utc,") and len(lines) == 1 + 2 * 2


def test_the_denominator_is_the_engine_registry_minus_data_formats():
    langs = gcc.all_languages()
    assert {"python", "cobol", "proto"} <= set(langs)
    assert not gcc.NOT_CODE & set(langs)


def test_the_committed_chart_renders_from_the_committed_data():
    gcc.render_svg(gcc.load(), gcc.all_languages())  # every committed baseline and ledger parses
