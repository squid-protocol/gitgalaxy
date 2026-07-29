from gitgalaxy.core.spatial_correlation import (
    correlate_signals,
    correlate_scoped,
    filter_positions_in_range,
    apply_dampener_correlations,
    correlate_against_ledger,
)


# ==============================================================================
# TEST 1: BASELINE CORRELATION (unchanged behavior, moved from detector.py)
# ==============================================================================
def test_correlate_signals_basic_proximity():
    """Proves the extracted primitive still sweeps distance identically."""
    # Target at 100 is within 50 of a dampener at 120 -> mitigated
    unmit, mit = correlate_signals(targets=[100], dampeners=[120], max_distance=50)
    assert (unmit, mit) == (0, 1)

    # Target at 100 is NOT within 50 of a dampener at 500 -> unmitigated
    unmit, mit = correlate_signals(targets=[100], dampeners=[500], max_distance=50)
    assert (unmit, mit) == (1, 0)

    # No dampeners at all -> everything unmitigated
    unmit, mit = correlate_signals(targets=[10, 20], dampeners=[], max_distance=50)
    assert (unmit, mit) == (2, 0)

    # No targets -> nothing to report
    unmit, mit = correlate_signals(targets=[], dampeners=[10, 20], max_distance=50)
    assert (unmit, mit) == (0, 0)


# ==============================================================================
# TEST 2: RANGE FILTERING (the satellite-scoping primitive)
# ==============================================================================
def test_filter_positions_in_range():
    positions = [10, 50, 99, 100, 150, 200, 201]
    assert filter_positions_in_range(positions, 100, 200) == [100, 150]
    assert filter_positions_in_range(positions, 0, 10) == []
    assert filter_positions_in_range(positions, 0, 11) == [10]
    assert filter_positions_in_range([], 0, 100) == []


# ==============================================================================
# TEST 3: SATELLITE-SCOPED CORRELATION (#346 phase 1 -- the actual fix)
# ==============================================================================
def test_correlate_scoped_no_satellites_matches_flat_behavior():
    """With no satellite data at all, correlate_scoped must equal correlate_signals."""
    targets, dampeners = [100, 900], [120, 850]
    flat = correlate_signals(targets, dampeners, max_distance=50)
    scoped = correlate_scoped(targets, dampeners, satellite_ranges=None, max_distance=50)
    assert scoped == flat

    scoped_empty_list = correlate_scoped(targets, dampeners, satellite_ranges=[], max_distance=50)
    assert scoped_empty_list == flat


def test_correlate_scoped_rejects_cross_function_mitigation():
    """
    The core false-negative fix: a dampener in a DIFFERENT function must not
    mitigate a target, even though it's well within the flat character radius.
    """
    # Two adjacent functions: [0, 200) and [200, 400).
    satellites = [(0, 200), (200, 400)]

    # Danger at offset 190 (function A), safety net at offset 210 (function B) --
    # only 20 chars apart, well inside a 500-char flat radius.
    targets = [190]
    dampeners = [210]

    flat_unmit, flat_mit = correlate_signals(targets, dampeners, max_distance=500)
    assert (flat_unmit, flat_mit) == (0, 1), "Sanity check: flat correlation should mitigate this pair"

    scoped_unmit, scoped_mit = correlate_scoped(targets, dampeners, satellites, max_distance=500)
    assert (scoped_unmit, scoped_mit) == (1, 0), (
        "Scoped correlation must NOT let a dampener in a different function silently cancel real risk in this one"
    )


def test_correlate_scoped_allows_same_function_mitigation():
    """A dampener in the SAME function still mitigates, exactly as today."""
    satellites = [(0, 200), (200, 400)]
    targets = [50]
    dampeners = [60]  # Same function (A), 10 chars away

    unmit, mit = correlate_scoped(targets, dampeners, satellites, max_distance=500)
    assert (unmit, mit) == (0, 1)


def test_correlate_scoped_falls_back_for_module_level_targets():
    """
    A target that falls OUTSIDE every known satellite range (module-level
    code, or a segment with zero sliced functions) must fall back to the
    flat, whole-segment behavior against the full dampener list -- this is
    the "no regression for unsliced code" guarantee.
    """
    satellites = [(100, 200)]  # Only one function, at [100, 200)
    targets = [900]  # Module-level code, far outside the only known function
    dampeners = [910]  # Also module-level, right next to the target

    unmit, mit = correlate_scoped(targets, dampeners, satellites, max_distance=50)
    assert (unmit, mit) == (0, 1), (
        "Module-level target/dampener pairs outside any satellite must still "
        "correlate via the flat fallback, matching pre-scoping behavior"
    )


def test_correlate_scoped_mixed_covered_and_uncovered_targets():
    """Covered and uncovered targets are handled independently in one call."""
    satellites = [(0, 100)]
    # in-function target, mitigated by an out-of-function dampener -> must NOT mitigate
    # module-level target, mitigated by another module-level dampener -> must mitigate
    targets = [50, 500]
    dampeners = [500 + 10]  # far from the in-function target, close to the module-level one

    unmit, mit = correlate_scoped(targets, dampeners, satellites, max_distance=50)
    assert unmit == 1, "In-function target must not be mitigated by an out-of-function dampener"
    assert mit == 1, "Module-level target must still be mitigated via the flat fallback"


# ==============================================================================
# TEST 4: apply_dampener_correlations (the three relocated blocks, #346)
# ==============================================================================
def _fresh_mitigations():
    return {
        "mitigated_danger": 0,
        "mitigated_memory_allocs": 0,
        "amplified_rce": 0,
        "amplified_race_conditions": 0,
        "amplified_leaks": 0,
    }


def test_apply_dampener_correlations_silencer_region_respects_scope():
    """
    Block 2 (The Silencer Region): a safety check in a DIFFERENT function
    must not cancel out a danger signal in this one.
    """
    satellite_ranges = [(0, 200), (200, 400)]
    spatial_map = {"high_risk_execution": [190], "safety": [210]}
    counts = {"high_risk_execution": 1}
    mitigations = _fresh_mitigations()

    apply_dampener_correlations(spatial_map, satellite_ranges, counts, mitigations)

    assert counts["high_risk_execution"] == 1, (
        "Cross-function safety check must not silently mitigate this danger signal"
    )
    assert mitigations["mitigated_danger"] == 0


def test_apply_dampener_correlations_silencer_region_same_function():
    """A safety check in the SAME function still mitigates, as before."""
    satellite_ranges = [(0, 200)]
    spatial_map = {"high_risk_execution": [50], "safety": [60]}
    counts = {"high_risk_execution": 1}
    mitigations = _fresh_mitigations()

    apply_dampener_correlations(spatial_map, satellite_ranges, counts, mitigations)

    assert counts["high_risk_execution"] == 0, "Same-function safety check should still mitigate"
    assert mitigations["mitigated_danger"] == 1


def test_apply_dampener_correlations_memory_leak_scoped():
    """Block 5: a cleanup() in a different function must not hide a real leak."""
    satellite_ranges = [(0, 100), (100, 200)]
    spatial_map = {"memory_alloc": [50], "cleanup": [150]}
    counts = {"memory_alloc": 1}
    mitigations = _fresh_mitigations()

    apply_dampener_correlations(spatial_map, satellite_ranges, counts, mitigations)

    assert counts["memory_alloc"] == 1, "Cross-function cleanup() must not hide this leak"
    assert mitigations["mitigated_memory_allocs"] == 0


def test_apply_dampener_correlations_race_condition_still_amplifies():
    """
    Block 3: unmitigated state flux (no sync_lock nearby, scoped) should
    still trigger the (unscoped, phase-1-deferred) race condition amplifier.
    """
    satellite_ranges = [(0, 500)]
    spatial_map = {"concurrency": [40], "state_mutation": [50]}  # no sync_locks at all
    counts = {"concurrency": 0}
    mitigations = _fresh_mitigations()

    apply_dampener_correlations(spatial_map, satellite_ranges, counts, mitigations)

    assert counts["concurrency"] == 5, "Race condition amplifier should have fired (unmitigated flux)"
    assert mitigations["amplified_race_conditions"] == 1


def test_apply_dampener_correlations_no_satellites_matches_pre_scoping_behavior():
    """With zero known satellite ranges, behavior must match the old flat correlation exactly."""
    spatial_map = {"high_risk_execution": [10], "safety": [20], "memory_alloc": [5], "cleanup": [15]}
    counts = {"high_risk_execution": 1, "memory_alloc": 1}
    mitigations = _fresh_mitigations()

    apply_dampener_correlations(spatial_map, [], counts, mitigations)

    assert counts["high_risk_execution"] == 0, "Flat fallback should still mitigate a nearby danger"
    assert mitigations["mitigated_danger"] == 1
    assert counts["memory_alloc"] == 0, "Flat fallback should still mitigate a nearby leak"
    assert mitigations["mitigated_memory_allocs"] == 1


# ==============================================================================
# TEST 5: correlate_against_ledger (post-hoc, line-indexed, #348)
# ==============================================================================
def test_correlate_against_ledger_scopes_by_function_line_range():
    """
    Reflection/metaprogramming on line 50 of function A (lines 1-60) must not
    be considered "documented" just because a doc comment sits on line 5 of a
    totally different function.
    """
    threat_locations = {"reflection_metaprogramming": [50], "doc": [5]}
    functions = [
        {"name": "documented_helper", "start_line": 1, "end_line": 10},
        {"name": "undocumented_reflector", "start_line": 40, "end_line": 60},
    ]

    unmit, mit = correlate_against_ledger(
        threat_locations, functions, "reflection_metaprogramming", "doc", max_distance=10
    )
    assert unmit == 1, "Metaprogramming in a different, undocumented function must be flagged"
    assert mit == 0


def test_correlate_against_ledger_same_function_is_documented():
    """Reflection/metaprogramming with a doc comment in the SAME function is not flagged."""
    threat_locations = {"reflection_metaprogramming": [45], "doc": [40]}
    functions = [{"name": "documented_reflector", "start_line": 40, "end_line": 60}]

    unmit, mit = correlate_against_ledger(
        threat_locations, functions, "reflection_metaprogramming", "doc", max_distance=10
    )
    assert unmit == 0
    assert mit == 1


def test_correlate_against_ledger_missing_keys_are_empty():
    """Absent signal keys behave like empty lists, not a KeyError."""
    unmit, mit = correlate_against_ledger({}, [], "reflection_metaprogramming", "doc")
    assert (unmit, mit) == (0, 0)


def test_correlate_against_ledger_corroboration_style_reads_mitigated():
    """
    The #105 shape (amplifier/corroboration, not a dampener): an API route and
    a DB hook in the SAME function is the corroborated, deterministic signal --
    read from the "mitigated" side of the same return contract.
    """
    threat_locations = {"api": [12], "db_hooks": [15]}
    functions = [{"name": "user_route", "start_line": 10, "end_line": 20}]

    _, corroborated = correlate_against_ledger(threat_locations, functions, "api", "db_hooks", max_distance=10)
    assert corroborated == 1, "API route and DB hook in the same function should corroborate"
