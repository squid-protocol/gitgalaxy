"""#4443 item 3: the spot-check note lists the equivalent survivors it re-read; each must still be one."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NOTE = REPO / "docs" / "language_status" / "mutation_equivalent_spot_check.md"
SCORES = REPO / "docs" / "language_status" / "mutation_scores.json"
ROW = re.compile(r"^\| ([0-9a-f]{10}) \| ([A-Z0-9]+) \|", re.MULTILINE)
# GTWORK has no equivalent survivor, so it has no row.
SAMPLED_PORTS = {
    "CALINK", "CASUB", "CAXA", "CAXB", "GTSTART", "GTSHOW", "GTTERM", "HCMAIN", "HCSUB", "HCQREAD", "HXATTR", "HXEXT",
}  # fmt: skip


def _equivalent_ids():
    ports = json.loads(SCORES.read_text(encoding="utf-8"))["ports"]
    return {(m["id"], p["program"]) for p in ports for m in p["survivors"] if m["verdict"] == "equivalent"}


def test_every_sampled_mutant_is_still_an_equivalent_survivor():
    rows = ROW.findall(NOTE.read_text(encoding="utf-8"))
    assert rows, "the note lists no sampled mutants"
    assert len(set(rows)) == len(rows)
    assert not set(rows) - _equivalent_ids()


def test_the_sample_covers_every_port_that_has_an_equivalent_survivor():
    rows = ROW.findall(NOTE.read_text(encoding="utf-8"))
    assert {port for _, port in rows} == SAMPLED_PORTS
