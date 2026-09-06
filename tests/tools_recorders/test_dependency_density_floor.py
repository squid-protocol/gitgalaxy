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
dependency_density under the evidence-mass floor (#2770).

The column used to divide by `max(int(coding_loc * control_flow_ratio), 1)`, which
failed three ways at once:

  * control_flow_ratio is `branch / (branch + structural_boundaries)`, so it is 0
    for ANY file with no branches -- config, constants modules, data classes, most
    yaml/dockerfile. The denominator then collapsed onto its own max(..., 1) floor
    and the "density" reported the raw import COUNT, up to 20x the value the same
    file recorded after one `if` was added to it.
  * the int() truncated the product BEFORE the floor, so any product under 2.0 also
    landed on 1 (measured on keyword-rosetta: 4 of the 5 files in every one of the
    46 languages).
  * where a language's structural_boundaries rule never fires, control_flow_ratio is
    1.0 and the denominator silently became coding_loc -- the right answer, reached
    by accident.

The replacement is coupling per line of code over EVIDENCE_MASS_FLOOR, the same
denominator every other per-file density equation uses (#2655, pinned by
tests/core_engine/test_uef_length_invariance.py). This module pins the same
four properties its per-function sibling pins in test_func_internal_density_floor.py,
plus the one specific to this fix:

  1. INVARIANCE  -- below the floor, an identical import count scores identically at
                    any file length.
  2. CONTINUITY  -- the value at the floor equals the value just below it.
  3. PARITY      -- at floor+1 and above, the column is import_count / coding_loc.
  4. INDEPENDENCE - the column does not move with control_flow_ratio (the regression).
  5. ZERO        -- no imports records 0, and coding_loc 0 does not divide by zero.

Driven through RecordKeeper.record_mission, the only place the column is computed.
"""

import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.standards.analysis_lens import ENGINE_CONSTANTS

FLOOR = int(ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"])


@pytest.fixture
def keeper():
    schemas = {"RISK_SCHEMA": ["cognitive_load"], "SIGNAL_SCHEMA": ["branch", "io"]}
    with patch("gitgalaxy.recorders.record_keeper.RECORDING_SCHEMAS", schemas):
        return RecordKeeper()


def _file(coding_loc, imports=2, cfr=0.1):
    return {
        "path": "main.py",
        "name": "main.py",
        "lang_id": "python",
        "directory_group": ".",
        "lock_tier": 0,
        "total_loc": coding_loc + 5,
        "coding_loc": coding_loc,
        "doc_loc": 1,
        "file_impact": 1.0,
        "raw_imports": [f"dep_{i}.py" for i in range(imports)],
        "hit_vector": [3, 1],
        "telemetry": {"control_flow_ratio": cfr, "network_metrics": {}, "domain_context": {}},
        "classes": [],
        "functions": [],
    }


def _density(keeper, tmp_path, parsed):
    db = tmp_path / "out.db"
    if db.exists():
        db.unlink()
    keeper.record_mission(parsed, [], {}, {"target": "t", "git_audit": {}}, str(db))
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT dependency_density FROM file_data").fetchone()[0]
    finally:
        conn.close()


@pytest.mark.parametrize("coding_loc", [1, 5, 13, 25, FLOOR - 1])
def test_identical_imports_score_identically_below_the_floor(keeper, tmp_path, coding_loc):
    """Property 1: the rosetta shells are 4-21 coding lines; every one of them must
    read the same density as the same import count at the floor."""
    at_floor = _density(keeper, tmp_path, [_file(FLOOR)])
    shorter = _density(keeper, tmp_path, [_file(coding_loc)])
    assert shorter == pytest.approx(at_floor)
    # and that shared value is the rescaled import count, nothing else
    assert shorter == pytest.approx(2 / FLOOR)


def test_no_cliff_at_the_floor(keeper, tmp_path):
    """Property 2: floor and floor-1 agree; floor+1 is the first point on the curve."""
    below = _density(keeper, tmp_path, [_file(FLOOR - 1)])
    at = _density(keeper, tmp_path, [_file(FLOOR)])
    above = _density(keeper, tmp_path, [_file(FLOOR + 1)])
    assert below == pytest.approx(at)
    assert above < at  # the density regime resumes, monotonically


@pytest.mark.parametrize("coding_loc", [FLOOR + 1, 150, 500])
def test_density_regime_is_imports_per_coding_loc(keeper, tmp_path, coding_loc):
    """Property 3: at or above the floor the column is exactly import_count / coding_loc."""
    assert _density(keeper, tmp_path, [_file(coding_loc, imports=3)]) == pytest.approx(3 / coding_loc)


@pytest.mark.parametrize("cfr", [0.0, 0.05, 0.5, 1.0])
def test_column_does_not_move_with_control_flow_ratio(keeper, tmp_path, cfr):
    """Property 4, the #2770 regression itself. A measure of imports has no reason to
    move when branch structure does. Under the old formula the cfr=0.0 case divided by
    max(int(200 * 0.0), 1) == 1 and recorded 2.0 -- its raw import count, 400x the
    cfr=0.5 case, for a file whose imports are identical."""
    assert _density(keeper, tmp_path, [_file(200, cfr=cfr)]) == pytest.approx(2 / 200)


def test_no_imports_records_zero(keeper, tmp_path):
    """Property 5a."""
    assert _density(keeper, tmp_path, [_file(200, imports=0)]) == 0.0


def test_empty_file_does_not_divide_by_zero(keeper, tmp_path):
    """Property 5b: the floor absorbs coding_loc 0 (a file the prism found no code in),
    which the old max(..., 1) guard was carrying."""
    assert _density(keeper, tmp_path, [_file(0)]) == pytest.approx(2 / FLOOR)


def test_floor_is_the_shared_file_level_constant():
    """The column must track EVIDENCE_MASS_FLOOR itself, not a private copy of 50 --
    the point of #2655 was that one constant governs every per-file density."""
    from gitgalaxy.recorders import record_keeper

    assert record_keeper.EVIDENCE_MASS_FLOOR == float(ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"])
