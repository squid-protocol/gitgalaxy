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
dependency_density under the evidence-mass floor (#2770), over the resolved-edge
numerator (#2801).

Two fixes stack in this column:

  * #2770 replaced the denominator. It used to divide by
    `max(int(coding_loc * control_flow_ratio), 1)`, which was 0 for any branch-free
    file (config, constants modules, data classes, most yaml/dockerfile), so the
    denominator collapsed onto its own max(..., 1) floor and the "density" reported
    the raw NUMERATOR, up to 20x the value the same file recorded after one `if`.
    The replacement is per coding_loc over EVIDENCE_MASS_FLOOR, the same denominator
    every other per-file density equation uses (#2655, pinned by
    tests/core_engine/test_uef_length_invariance.py).

  * #2801 then fixed the numerator. `dependency_density` is coupling per line, and
    coupling is INTERNAL coupling -- the resolved edges network_risk_sensor put in the
    DAG (its out_degree), the same edge set popularity/pagerank/blast_radius read. The
    old numerator was `len(raw_imports)`, the raw pre-resolution capture surface, which
    counts every `import machine` / `FROM scratch` / `DSN=CORPUS.DATA` that resolves to
    no node in the scan. Dividing that made a vendored-dependency-free service read as
    import-dense purely on external-library surface, which says nothing about coupling.

This module pins the four properties its per-function sibling pins in
test_func_internal_density_floor.py, plus the two specific to these fixes:

  1. INVARIANCE   -- below the floor, an identical edge count scores identically at
                     any file length.
  2. CONTINUITY   -- the value at the floor equals the value just below it.
  3. PARITY       -- at floor+1 and above, the column is out_degree / coding_loc.
  4. INDEPENDENCE -- the column does not move with control_flow_ratio (#2770).
  5. RESOLVED     -- the numerator is the resolved edge count (out_degree), NOT the raw
                     capture count: unresolved captures do not move it (#2801).
  6. ZERO         -- no edges records 0, and coding_loc 0 does not divide by zero.

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


def _file(coding_loc, links=2, cfr=0.1, raw_imports=None):
    """A file whose resolved-edge count (network_risk_sensor's out_degree) is ``links``.

    ``raw_imports`` defaults to a DIFFERENT, larger capture set than ``links`` so a test
    that forgets to distinguish the two fails loudly -- the whole point of #2801 is that
    dependency_density reads the resolved count, not this list.
    """
    if raw_imports is None:
        raw_imports = [f"dep_{i}.py" for i in range(links + 3)]
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
        "raw_imports": raw_imports,
        "hit_vector": [3, 1],
        "telemetry": {
            "control_flow_ratio": cfr,
            "network_metrics": {"out_degree": links},
            "domain_context": {},
        },
        "classes": [],
        "functions": [],
    }


def _cols(keeper, tmp_path, parsed, columns="dependency_density"):
    db = tmp_path / "out.db"
    if db.exists():
        db.unlink()
    keeper.record_mission(parsed, [], {}, {"target": "t", "git_audit": {}}, str(db))
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT {columns} FROM file_data").fetchone()
    finally:
        conn.close()


def _density(keeper, tmp_path, parsed):
    return _cols(keeper, tmp_path, parsed)[0]


@pytest.mark.parametrize("coding_loc", [1, 5, 13, 25, FLOOR - 1])
def test_identical_edges_score_identically_below_the_floor(keeper, tmp_path, coding_loc):
    """Property 1: the rosetta shells are 4-21 coding lines; every one of them must
    read the same density as the same edge count at the floor."""
    at_floor = _density(keeper, tmp_path, [_file(FLOOR)])
    shorter = _density(keeper, tmp_path, [_file(coding_loc)])
    assert shorter == pytest.approx(at_floor)
    # and that shared value is the rescaled edge count, nothing else
    assert shorter == pytest.approx(2 / FLOOR)


def test_no_cliff_at_the_floor(keeper, tmp_path):
    """Property 2: floor and floor-1 agree; floor+1 is the first point on the curve."""
    below = _density(keeper, tmp_path, [_file(FLOOR - 1)])
    at = _density(keeper, tmp_path, [_file(FLOOR)])
    above = _density(keeper, tmp_path, [_file(FLOOR + 1)])
    assert below == pytest.approx(at)
    assert above < at  # the density regime resumes, monotonically


@pytest.mark.parametrize("coding_loc", [FLOOR + 1, 150, 500])
def test_density_regime_is_edges_per_coding_loc(keeper, tmp_path, coding_loc):
    """Property 3: at or above the floor the column is exactly out_degree / coding_loc."""
    assert _density(keeper, tmp_path, [_file(coding_loc, links=3)]) == pytest.approx(3 / coding_loc)


@pytest.mark.parametrize("cfr", [0.0, 0.05, 0.5, 1.0])
def test_column_does_not_move_with_control_flow_ratio(keeper, tmp_path, cfr):
    """Property 4, the #2770 regression itself. A measure of coupling has no reason to
    move when branch structure does. Under the old formula the cfr=0.0 case divided by
    max(int(200 * 0.0), 1) == 1 and recorded 2.0 -- its raw numerator, 400x the
    cfr=0.5 case, for a file whose dependencies are identical."""
    assert _density(keeper, tmp_path, [_file(200, cfr=cfr)]) == pytest.approx(2 / 200)


@pytest.mark.parametrize("unresolved", [0, 1, 5, 40])
def test_numerator_is_resolved_edges_not_raw_captures(keeper, tmp_path, unresolved):
    """Property 5, the #2801 fix itself. The column reads out_degree (resolved edges),
    so padding raw_imports with captures that resolve to nothing -- embedded_python's
    `import machine`, dockerfile's `FROM scratch`, jcl's `DSN=` -- must not move it. The
    three resolved edges stay three no matter how much external surface is captured."""
    raw = [f"dep_{i}.py" for i in range(3)] + [f"unresolved_{i}" for i in range(unresolved)]
    density = _density(keeper, tmp_path, [_file(200, links=3, raw_imports=raw)])
    assert density == pytest.approx(3 / 200)


def test_import_count_stays_the_raw_capture_surface(keeper, tmp_path):
    """The split's other half: import_count keeps every capture (external-dependency
    surface), while internal_dependency_links carries the resolved edges. embedded_python
    reads 7 captures / 3 edges; both columns must be recoverable, and they must differ."""
    raw = [f"dep_{i}.py" for i in range(3)] + [f"machine_{i}" for i in range(4)]
    import_count, internal_links = _cols(
        keeper,
        tmp_path,
        [_file(200, links=3, raw_imports=raw)],
        columns="import_count, internal_dependency_links",
    )
    assert import_count == 7  # raw capture surface, unchanged from pre-#2801
    assert internal_links == 3  # resolved DAG edges (out_degree)


def test_no_edges_records_zero(keeper, tmp_path):
    """Property 6a."""
    assert _density(keeper, tmp_path, [_file(200, links=0)]) == 0.0


def test_missing_network_metrics_records_zero(keeper, tmp_path):
    """Property 6a, degenerate: a file the network sensor never annotated (no
    out_degree) reads 0 edges, not a crash and not the raw capture count."""
    f = _file(200, links=0)
    f["telemetry"]["network_metrics"] = {}
    assert _density(keeper, tmp_path, [f]) == 0.0


def test_empty_file_does_not_divide_by_zero(keeper, tmp_path):
    """Property 6b: the floor absorbs coding_loc 0 (a file the prism found no code in),
    which the old max(..., 1) guard was carrying."""
    assert _density(keeper, tmp_path, [_file(0)]) == pytest.approx(2 / FLOOR)


def test_floor_is_the_shared_file_level_constant():
    """The column must track EVIDENCE_MASS_FLOOR itself, not a private copy of 50 --
    the point of #2655 was that one constant governs every per-file density."""
    from gitgalaxy.recorders import record_keeper

    assert record_keeper.EVIDENCE_MASS_FLOOR == float(ENGINE_CONSTANTS["EVIDENCE_MASS_FLOOR"])
