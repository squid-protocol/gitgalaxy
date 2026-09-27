"""#3825: COBOL ROUNDED semantics reach the port.

Plain ROUNDED rounds half AWAY from zero (2.5 -> 3, -2.5 -> -3): Java's HALF_UP, not banker's
HALF_EVEN and not Math.round. Each ROUNDED MODE maps to one RoundingMode; no ROUNDED truncates.
The engine lists every rounding / SIZE ERROR statement (rounding_facts), the porting ticket carries
them with the rule, and a GnuCOBOL probe (tests/equivalence/rounding/RND.cbl) pins the table.
"""

import json
import os
import re
import subprocess
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
)
from pathlib import Path

import pytest

from gitgalaxy.core.data_moves import ROUNDING_MODES, rounding_facts
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import build_ticket, ticket_markdown

PROBE = Path(__file__).resolve().parents[1] / "equivalence" / "rounding" / "RND.cbl"
# java.math.RoundingMode and Python's decimal share these semantics name for name
PYTHON = {"DOWN": ROUND_DOWN, "HALF_UP": ROUND_HALF_UP, "HALF_EVEN": ROUND_HALF_EVEN, "UP": ROUND_UP,
          "HALF_DOWN": ROUND_HALF_DOWN, "CEILING": ROUND_CEILING, "FLOOR": ROUND_FLOOR}  # fmt: skip
# the probe's columns: none, ROUNDED, then each MODE it runs
COLUMNS = {"NONE": None, "ROUNDED": "NEAREST-AWAY-FROM-ZERO", "EVEN": "NEAREST-EVEN", "AWAY": "AWAY-FROM-ZERO",
           "NTZ": "NEAREST-TOWARD-ZERO", "CEIL": "TOWARD-GREATER", "FLOOR": "TOWARD-LESSER", "TRUNC": "TRUNCATION"}  # fmt: skip
# GnuCOBOL 3's output on the probe (the ties, and two non-ties), pinned
PROBED = {
    "-2.6": {"NONE": -2, "ROUNDED": -3, "EVEN": -3, "AWAY": -3, "NTZ": -3, "CEIL": -2, "FLOOR": -3, "TRUNC": -2},
    "-2.5": {"NONE": -2, "ROUNDED": -3, "EVEN": -2, "AWAY": -3, "NTZ": -2, "CEIL": -2, "FLOOR": -3, "TRUNC": -2},
    "-1.5": {"NONE": -1, "ROUNDED": -2, "EVEN": -2, "AWAY": -2, "NTZ": -1, "CEIL": -1, "FLOOR": -2, "TRUNC": -1},
    "-0.5": {"NONE": 0, "ROUNDED": -1, "EVEN": 0, "AWAY": -1, "NTZ": 0, "CEIL": 0, "FLOOR": -1, "TRUNC": 0},
    "0.5": {"NONE": 0, "ROUNDED": 1, "EVEN": 0, "AWAY": 1, "NTZ": 0, "CEIL": 1, "FLOOR": 0, "TRUNC": 0},
    "1.5": {"NONE": 1, "ROUNDED": 2, "EVEN": 2, "AWAY": 2, "NTZ": 1, "CEIL": 2, "FLOOR": 1, "TRUNC": 1},
    "2.4": {"NONE": 2, "ROUNDED": 2, "EVEN": 2, "AWAY": 3, "NTZ": 2, "CEIL": 3, "FLOOR": 2, "TRUNC": 2},
    "2.5": {"NONE": 2, "ROUNDED": 3, "EVEN": 2, "AWAY": 3, "NTZ": 2, "CEIL": 3, "FLOOR": 2, "TRUNC": 2},
}


def _java(value: str, column: str) -> int:
    mode = ROUNDING_MODES[COLUMNS[column]]
    return int(Decimal(value).quantize(Decimal(1), rounding=PYTHON[mode]))


@pytest.mark.parametrize("value", sorted(PROBED))
def test_each_mode_maps_to_the_rounding_mode_that_reproduces_cobol(value):
    assert {c: _java(value, c) for c in COLUMNS} == PROBED[value]


def test_the_facts_name_each_target_mode_and_size_error():
    src = """       PROCEDURE DIVISION.
           COMPUTE WS-A ROUNDED = WS-B / 3.
           COMPUTE WS-C ROUNDED MODE IS NEAREST-EVEN, WS-D = WS-B * 2
               ON SIZE ERROR DISPLAY 'TOO BIG'
           END-COMPUTE
           ADD 1 TO WS-E
           DIVIDE WS-B BY 7 GIVING WS-F ROUNDED MODE TOWARD-LESSER REMAINDER WS-G.
           MULTIPLY 2 BY WS-H ON SIZE ERROR PERFORM 9999-ABEND.
           EXEC SQL SELECT ROUNDED INTO :X FROM T END-EXEC.
"""
    got = [(f["verb"], f["line"], [(t["target"], t["java"]) for t in f["targets"]], f["size_error"])
           for f in rounding_facts(src)]  # fmt: skip
    assert got == [
        ("COMPUTE", 2, [("WS-A", "HALF_UP")], False),
        ("COMPUTE", 3, [("WS-C", "HALF_EVEN")], True),  # WS-D has no ROUNDED: it truncates
        ("DIVIDE", 7, [("WS-F", "FLOOR")], False),
        ("MULTIPLY", 8, [], True),
    ]  # the plain ADD truncates and is not listed; EXEC SQL is not COBOL arithmetic


def test_a_program_default_rounded_mode_applies_to_plain_rounded():
    src = ("       IDENTIFICATION DIVISION.\n       OPTIONS.\n           DEFAULT ROUNDED MODE IS NEAREST-EVEN.\n"
           "       PROCEDURE DIVISION.\n           COMPUTE WS-A ROUNDED = WS-B / 3.\n")  # fmt: skip
    (f,) = rounding_facts(src)
    assert f["targets"] == [{"target": "WS-A", "mode": "NEAREST-EVEN", "java": "HALF_EVEN"}]


def _ticket(tmp_path: Path, culture: dict) -> dict:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "INT.cbl").write_text(
        "       PROCEDURE DIVISION.\n           COMPUTE WS-INT ROUNDED = WS-BAL * WS-RATE / 1200.\n", encoding="utf-8"
    )
    skeleton = {"program": {"file": "INT.cbl", "language": "cobol", "program_ids": ["INT"]}, "sections": {}}
    return build_ticket("INT", skeleton, tmp_path, "com.acme", tmp_path / "src", None, [], {"culture": culture}, None)


def test_the_ticket_carries_the_statements_and_the_rule(tmp_path):
    t = _ticket(tmp_path, {"rounding": "cobol"})
    assert t["rounding"] == [{"verb": "COMPUTE", "line": 2, "size_error": False,
                              "targets": [{"target": "WS-INT", "mode": "NEAREST-AWAY-FROM-ZERO", "java": "HALF_UP"}]}]  # fmt: skip
    assert any("half AWAY from zero" in r and "Math.round" in r for r in t["rules"])
    assert not any("half_even" in r for r in t["rules"])
    assert "| 2 | COMPUTE | `WS-INT`: HALF_UP (NEAREST-AWAY-FROM-ZERO) |" in ticket_markdown(t)
    json.dumps(t)  # the ticket stays plain JSON


def test_a_declared_half_even_deviation_reaches_the_rules(tmp_path):
    t = _ticket(tmp_path, {"rounding": "half_even"})
    assert any("culture.rounding: half_even" in r and "HALF_EVEN" in r for r in t["rules"])


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL)")
def test_gnucobol_rounds_as_the_table_says(tmp_path):
    (tmp_path / "RND.cbl").write_text(PROBE.read_text(encoding="utf-8"), encoding="utf-8")
    out = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", "gitgalaxy-gnucobol:3",  # noqa: S603, S607
                          "sh", "-c", "cobc -x -free -o rnd RND.cbl && ./rnd"],
                         capture_output=True, text=True, check=True).stdout  # fmt: skip
    lines = out.splitlines()
    assert len(lines) == len(PROBED)
    for line in lines:  # `A=-002.5 NONE=-002 ROUNDED=-003 ...` (an edited sign may print as a space)
        cells = dict(re.findall(r"([A-Z]+)=\s*([-+]?[0-9.]+)", line))
        value = str(Decimal(cells.pop("A")).normalize())
        assert {k: int(v) for k, v in cells.items()} == {c: _java(value, c) for c in COLUMNS}, line
