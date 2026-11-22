"""#8881: the Java side of an IDCAMS job step (tests/tools/equivalence_idcams_java.py). The TRANIDX chain (STEP20 DEFINE
ALTERNATEINDEX, STEP25 DEFINE PATH, STEP30 BLDINDEX, SC23-6846-60) run as one job-step deck through the model and through
cobolrt/job/Idcams.java: they must agree on the return code, the path's records in alternate-key order (duplicates in the
base's order) and every refusal. A Java side that differs is reported, never passed. Needs a JDK (skips without one)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_idcams_java as eij

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M

BASE, AIX, PATH = "APP.TRAN.KSDS", "APP.TRAN.KSDS.AIX", "APP.TRAN.KSDS.AIX.PATH"
TRANIDX = (  # columns 1-72 only: IDCAMS ignores the rest of a line
    f" DEFINE ALTERNATEINDEX (NAME({AIX}) RELATE({BASE}) -\n"
    "   KEYS(4 4) NONUNIQUEKEY UPGRADE RECORDSIZE(40,40) -\n"
    "   VOLUMES(VOL001) CYLINDERS(5,1)) -\n"
    f"   DATA (NAME({AIX}.DATA)) -\n   INDEX (NAME({AIX}.INDEX))\n"
    f" DEFINE PATH (NAME({PATH}) PATHENTRY({AIX}))\n"
    f" BLDINDEX INDATASET({BASE}) OUTDATASET({AIX})\n"
)
ROWS = [b"0001BBBB..", b"0002AAAA..", b"0003BBBB..", b"0004CCCC..", b"0005AAAA.."]
pytestmark = pytest.mark.skipif(eij.jdk_bin() is None, reason="no JDK (JDK_17 / JAVA_HOME)")


def _base(indexed=True, rows=ROWS):
    return {BASE: M.Cluster(BASE, indexed, 4 if indexed else 0, 0, 10, 10, sorted(rows) if indexed else list(rows))}


@pytest.mark.parametrize("indexed", [True, False], ids=["ksds", "esds"])
def test_the_tranidx_chain_agrees_and_the_path_is_in_alternate_key_order(indexed):
    cat = _base(indexed)
    got = eij.compare(TRANIDX, cat, {})
    assert got["equal"], got
    lines = eij.model_lines(TRANIDX, cat, {})
    assert lines[0] == "RC 0 0 0"
    path = next(x for x in lines if x.startswith(f"PATH {PATH} "))
    keys = [bytes.fromhex(h)[4:8] for h in path.split()[2].split(",")]
    assert keys == sorted(keys) and len(keys) == 5
    assert path.split()[2].split(",")[:2] == [ROWS[1].hex(), ROWS[4].hex()]  # AAAA: 0002 then 0005, the base's order


@pytest.mark.parametrize(
    "deck",
    [
        TRANIDX.replace("NONUNIQUEKEY", "UNIQUEKEY"),  # duplicates: the model refuses by name
        TRANIDX.replace("RECORDSIZE(40,40)", "RECORDSIZE(20,20)"),
        " PRINT INFILE(IN)\n",
        TRANIDX.replace(" BLDINDEX", " BLDINDEX INFILE(IN)"),
    ],
    ids=["unique-over-dups", "recordsize-too-small", "print", "bldindex-infile"],
)
def test_a_refusal_or_error_reads_the_same_on_both_sides(deck):
    assert eij.compare(deck, _base(), {})["equal"]


def test_a_java_side_that_differs_is_reported_not_passed(monkeypatch):
    monkeypatch.setattr(eij, "java_lines", lambda *a: ["RC 4 0 4"])
    got = eij.compare(TRANIDX, _base(), {})
    assert not got["equal"] and got["differs"][0][1] == "RC 4 0 4"


def test_no_jdk_is_none_never_equal(monkeypatch):
    monkeypatch.setattr(eij, "jdk_bin", lambda: None)
    assert eij.compare(TRANIDX, _base(), {}) is None
