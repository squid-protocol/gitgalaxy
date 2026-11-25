"""family_sweep_nightly: the diff, the PR body, and the stamp are what a nightly PR is built from (#8863)."""

import argparse
import datetime
import sys
from pathlib import Path

import family_sweep_nightly as fsn

OLD = {
    "cells": {
        "go": {
            "closures": {"recall": 1.0, "precision": 0.36},
            "io": {"recall": 0.9, "precision": 0.9},
            "time": {"recall": 0.9, "precision": 0.9},
        }
    }
}
NEW = {
    "cells": {
        "go": {
            "closures": {"recall": 1.0, "precision": 1.0},  # improved
            "io": {"recall": 0.5, "precision": 0.9},  # regressed
            "time": {"recall": 0.9, "precision": 0.88},  # inside the noise band
            "regex_execution": {"recall": 0.9, "precision": 0.9},  # new
        }
    }
}


def test_diff_cells_sorts_movers_and_ignores_noise():
    d = fsn.diff_cells(OLD, NEW)
    assert d["improved"] == ["go closures: 0.36 -> 1.00"]
    assert d["regressed"] == ["go io: 0.90 -> 0.50"]
    assert d["new"] == ["go regex_execution"]


def test_pr_body_lists_regressions_before_improvements():
    body = fsn.pr_body("a" * 40, 91, 70, fsn.diff_cells(OLD, NEW), ["- [ ] **go**: 1 red cell"])
    assert body.index("Regressions") < body.index("Improvements")
    assert "**91 -> 70**" in body and "- [ ] **go**: 1 red cell" in body and "aaaaaaaaaaaa" in body


def test_pr_body_with_nothing_moved_has_no_empty_sections():
    body = fsn.pr_body("b" * 40, 5, 5, {"regressed": [], "improved": [], "new": []}, [])
    assert "Regressions" not in body and "Improvements" not in body


def test_stamp_is_per_sha_per_utc_day(tmp_path):
    s = fsn.stamp_file(tmp_path, "c" * 40)
    today = f"{datetime.datetime.now(datetime.UTC):%Y-%m-%d}"
    assert s == Path(tmp_path) / "family-sweep-nightly" / f"{today}-cccccccccccc.done"


def test_windows_skips_before_any_subprocess(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(fsn.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("spawned")))
    assert fsn.run(argparse.Namespace(root=None, force=True)) == 0
    assert "skipped" in capsys.readouterr().out
