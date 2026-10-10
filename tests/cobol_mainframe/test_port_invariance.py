"""port_invariance.py: the scanner reads a COBOL program and its proven det port alike where it should."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import port_invariance as pi  # noqa: E402


@pytest.fixture(scope="module")
def measured():
    return pi.measure(pi.fixture_pairs())


def test_spearman_handles_ties_and_both_directions():
    assert pi.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert pi.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert pi.spearman([1, 1, 2, 3], [5, 5, 6, 7]) == pytest.approx(1.0)  # ties share their average rank
    assert pi.spearman([1, 1, 1], [1, 2, 3]) is None


def test_fixture_is_the_contracted_pairs_with_their_sources():
    manifest = json.loads((pi.FIXTURE_DIR / "pairs.json").read_text(encoding="utf-8"))
    assert {p["program"] for p in manifest} == set(pi.FIXTURE)
    assert {p["estate"] for p in manifest} == {"aws-mainframe-modernization-carddemo",
                                              "cics-banking-sample-application-cbsa", "cics-genapp"}  # fmt: skip
    for p in manifest:
        java = (pi.FIXTURE_DIR / p["java"]).read_text(encoding="utf-8")
        assert java.startswith(f"// gitgalaxy-det-port: COBOL {p['program']} "), p["java"]  # emitted by the det port
        assert (pi.FIXTURE_DIR / p["estate"] / "LICENSE").is_file()
        assert (pi.FIXTURE_DIR / p["estate"] / "SOURCE.md").is_file()


def test_contract_holds_on_the_committed_pairs(measured):
    report, problems = pi.evaluate(measured, "fixture")
    assert problems == []
    assert len(measured) == len(pi.FIXTURE)
    for col, r in report.items():
        assert r["rho"] >= pi.CONTRACT[col][2], col


def test_a_reading_that_depends_on_the_language_is_caught(measured):
    # a scanner change that stops seeing the port's I/O breaks both the rank and the presence check
    broken = copy.deepcopy(measured)
    for m in broken:
        m["java_r"]["arch_io"] = 0
    _, problems = pi.evaluate(broken, "fixture")
    assert any(p.startswith("arch_io: rho None") for p in problems)
    assert any("file I/O in one form only" in p for p in problems)
    # one that reads Java branches in the reverse order of COBOL's
    broken = copy.deepcopy(measured)
    order = sorted(broken, key=lambda m: m["cobol_r"]["struct_branch"])
    for m, rank in zip(order, range(len(order), 0, -1), strict=False):  # reason: length may differ
        m["java_r"]["struct_branch"] = rank
    _, problems = pi.evaluate(broken, "fixture")
    assert any(p.startswith("struct_branch: rho -0.9") for p in problems)  # (COBOL ties keep it off -1)
    # and a port that lost paragraphs
    broken = copy.deepcopy(measured)
    broken[0]["java_r"]["function_count"] = broken[0]["cobol_r"]["function_count"] - 1
    _, problems = pi.evaluate(broken, "fixture")
    assert any("methods <" in p for p in problems)


@pytest.mark.skipif(not os.environ.get("PORT_INVARIANCE_WORK"),
                    reason="set PORT_INVARIANCE_WORK to a det sweep's work dir (and GITGALAXY_MAINFRAME_CORPORA)")  # fmt: skip
def test_contract_holds_on_every_swept_port():
    import mainframe_corpus

    pairs = pi.sweep_pairs(Path(os.environ["PORT_INVARIANCE_WORK"]), mainframe_corpus.cache_root())
    assert len(pairs) >= 45
    _, problems = pi.evaluate(pi.measure(pairs), "full")
    assert problems == [], problems
