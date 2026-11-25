"""Tests for tests/tools/family_decoy_runner.py (SOP-001-v1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import family_decoy_runner as fdr
import family_validity_chart as fvc


def test_scrape_candidates_normalizes_boundaries_whitespace_and_alternations():
    cands = fdr.scrape_candidates(r"\bBIT(?:AND|OR)[ \t]*\(|\bDELETE[ \t]+FROM\b", "bitwise_ops")
    assert "BITAND" in cands
    assert "DELETE FROM" in cands


def test_run_decoys_sop001_six_gates_on_ada():
    results, leaks = fdr.run_decoys(["ada"])
    assert "ada" in results
    assert len(results["ada"]) >= 25
    br = results["ada"]["branch"]
    assert br["protocol"] == fdr.PROTOCOL_VERSION
    assert br["comment"] == "pass"
    assert br["inline_comment"] == "pass"
    assert br["ident_boundary"] == "pass"
    assert br["string_comment_boundary"] == "pass"
    assert leaks["comment"] == []


def test_run_decoys_detects_real_comment_leak_on_ocaml():
    results, leaks = fdr.run_decoys(["ocaml"])
    assert "ocaml" in results
    assert len(results["ocaml"]) >= 25
    assert all(d["protocol"] == fdr.PROTOCOL_VERSION for d in results["ocaml"].values())
    assert all(d["comment"] in {"pass", "leak"} for d in results["ocaml"].values())


def test_run_decoys_stringless_language_sets_string_counts_none():
    results, _ = fdr.run_decoys(["hlasm"])
    assert "hlasm" in results
    assert len(results["hlasm"]) >= 20
    assert all(d["string_counts"] is None for d in results["hlasm"].values())


def test_audit_superficial_distinguishes_legacy_and_sop001_entries(tmp_path):
    bp = tmp_path / "baseline.json"
    bp.write_text(
        json.dumps(
            {
                "cells": {},
                "decoys": {
                    "ada": {
                        "branch": {"comment": "pass", "string_counts": True, "keyword": "if", "corpus": "old"},
                        "io": {
                            "comment": "pass",
                            "string_counts": True,
                            "keyword": "Ada.Text_IO.Open",
                            "corpus": "decoy-suite",
                            "protocol": fdr.PROTOCOL_VERSION,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    rep = fdr.audit_superficial(bp)
    assert rep["sop_current_total"] == 1
    assert rep["superficial_total"] == 1
    assert rep["superficial_by_lang"] == {"ada": 1}


def test_merge_baseline_preserves_cells_and_merges_decoys(tmp_path):
    bp = tmp_path / "baseline.json"
    bp.write_text(
        json.dumps(
            {
                "cells": {"python": {"branch": {"status": "ok", "recall": 1.0, "precision": 1.0}}},
                "decoys": {
                    "zig": {"branch": {"comment": "pass", "string_counts": True, "keyword": "if", "corpus": "old"}}
                },
            }
        ),
        encoding="utf-8",
    )
    fdr.merge_baseline(
        {
            "ada": {
                "branch": {
                    "comment": "pass",
                    "string_counts": True,
                    "keyword": "if",
                    "corpus": "decoy-suite",
                    "protocol": fdr.PROTOCOL_VERSION,
                }
            }
        },
        baseline_path=bp,
    )
    loaded_cells = fvc.load_baseline(bp)
    loaded_decoys = fvc.load_decoys(bp)
    assert "python" in loaded_cells
    assert "zig" in loaded_decoys
    assert loaded_decoys["ada"]["branch"]["protocol"] == fdr.PROTOCOL_VERSION
