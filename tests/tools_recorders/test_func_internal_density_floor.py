# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Per-function evidence-mass floor (#2705): func_internal_density must not read
function length where the branch structure is held equal.

The file-level equations got this property from #2655 (EVIDENCE_MASS_FLOOR, pinned
by tests/core_engine/test_uef_length_invariance.py). The recorder-side per-function
density was left out: avg_func_complexity / avg_func_loc with no floor, so the
keyword-rosetta corpus -- the same 13 functions at 46 lengths -- measured the column
as file length (Spearman -0.96 against coding_loc with branch/args/func_start held).
This module pins the same four properties for the per-function analog:

  1. INVARIANCE  -- below ENGINE_CONSTANTS["FUNC_EVIDENCE_MASS_FLOOR"], identical
                    branch structure scores identically at any function length.
  2. CONTINUITY  -- the value at the floor equals the value just below it.
  3. PARITY      -- at floor+1 and above, the column is byte-identical to the
                    pre-#2705 definition avg_comp / avg_loc.
  4. ZERO        -- a file with no functions still records 0 (the max() absorbed the
                    old `avg_loc > 0` guard; nothing divides by zero).

Driven through RecordKeeper.record_mission, the only place the column is computed.
"""

import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.standards.analysis_lens import ENGINE_CONSTANTS

FLOOR = int(ENGINE_CONSTANTS["FUNC_EVIDENCE_MASS_FLOOR"])

# The rosetta shell shape: a fixed branch/args profile per function; only `loc` sweeps.
ROSETTA_BRANCHES = [3, 0, 0, 0]  # main.* plants 3 branches in probe_branch, siblings 0
ROSETTA_ARGS = [1, 1, 1, 1]


@pytest.fixture
def keeper():
    schemas = {"RISK_SCHEMA": ["cognitive_load"], "SIGNAL_SCHEMA": ["branch", "io"]}
    with patch("gitgalaxy.recorders.record_keeper.RECORDING_SCHEMAS", schemas):
        return RecordKeeper()


def _file(func_locs, branches=ROSETTA_BRANCHES, args=ROSETTA_ARGS):
    functions = [
        {
            "name": f"probe_{i}",
            "type_id": "function",
            "loc": loc,
            "branch": b,
            "args": a,
            "impact": 1.0,
            "hit_vector": {},
        }
        for i, (loc, b, a) in enumerate(zip(func_locs, branches, args))
    ]
    return {
        "path": "main.py",
        "name": "main.py",
        "lang_id": "python",
        "directory_group": ".",
        "lock_tier": 0,
        "total_loc": sum(func_locs) + 5,
        "coding_loc": sum(func_locs) + 2,
        "doc_loc": 1,
        "file_impact": 1.0,
        "raw_imports": [],
        "hit_vector": [3, 1],
        "telemetry": {"control_flow_ratio": 0.1, "network_metrics": {}, "domain_context": {}},
        "classes": [],
        "functions": functions,
    }


def _density(keeper, tmp_path, parsed):
    db = tmp_path / "out.db"
    if db.exists():
        db.unlink()
    keeper.record_mission(parsed, [], {}, {"target": "t", "git_audit": {}}, str(db))
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT func_internal_density, avg_func_complexity, avg_func_loc FROM file_data").fetchone()
    finally:
        conn.close()


@pytest.mark.parametrize("avg_loc", [1, 2, 3, 5, FLOOR - 1])
def test_identical_structure_scores_identically_below_the_floor(keeper, tmp_path, avg_loc):
    """Property 1: the rosetta shells average 1-6 lines per function; every one of them
    must read the same density as the same structure at the floor."""
    at_floor = _density(keeper, tmp_path, [_file([FLOOR] * 4)])
    shorter = _density(keeper, tmp_path, [_file([avg_loc] * 4)])
    assert shorter[0] == pytest.approx(at_floor[0])
    # and that shared value is the rescaled branch structure, nothing else
    assert shorter[0] == pytest.approx(shorter[1] / FLOOR)


def test_no_cliff_at_the_floor(keeper, tmp_path):
    """Property 2: floor and floor-1 agree; floor+1 is the first point on the old curve."""
    below = _density(keeper, tmp_path, [_file([FLOOR - 1] * 4)])[0]
    at = _density(keeper, tmp_path, [_file([FLOOR] * 4)])[0]
    above = _density(keeper, tmp_path, [_file([FLOOR + 1] * 4)])[0]
    assert below == pytest.approx(at)
    assert above < at  # the density regime resumes, monotonically


@pytest.mark.parametrize("avg_loc", [FLOOR + 1, 20, 50, 200])
def test_density_regime_unchanged_above_the_floor(keeper, tmp_path, avg_loc):
    """Property 3: at or above the floor the column is the pre-#2705 avg_comp / avg_loc."""
    density, avg_comp, got_avg_loc = _density(keeper, tmp_path, [_file([avg_loc] * 4)])
    assert got_avg_loc == pytest.approx(avg_loc)
    assert density == pytest.approx(avg_comp / avg_loc)


def test_one_line_one_branch_functions_no_longer_read_as_maximal_density(keeper, tmp_path):
    """The golden-master shape that motivated the floor: five find*.sql files whose
    functions average one line and one branch each read a flat 1.00 -- the densest
    file in the corpus -- for having the shortest functions."""
    density = _density(keeper, tmp_path, [_file([1, 1, 1, 1], branches=[1, 1, 1, 1])])[0]
    assert density == pytest.approx(1.0 / FLOOR)


def test_no_functions_records_zero(keeper, tmp_path):
    """Property 4: the max() absorbed the old `avg_loc > 0` guard."""
    parsed = [_file([])]
    parsed[0]["functions"] = []
    assert _density(keeper, tmp_path, parsed)[0] == 0.0


def test_floor_matches_the_file_floor_derivation():
    """Both floors sit at their population's golden-master median (#2655: coding_loc 51
    -> 50; #2705: avg_func_loc 12.0 -> 12). Pin the ratio so a future retune of one
    without the other is a deliberate act, not drift."""
    assert ENGINE_CONSTANTS["FUNC_EVIDENCE_MASS_FLOOR"] == 12
    assert ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"] == 50
