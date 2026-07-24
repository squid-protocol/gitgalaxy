# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
"""
Structural Colocalization: shared proximity-correlation primitives.

Extracted from detector.py (#346) so the same distance-sweep can be reused
outside the StructuralExtractor -- and, in this module, given real
function-level scoping instead of a flat character radius as its only notion
of "nearby".

NAMING NOTE: this is proximity correlation between independent signal
classes, not taint tracking. It never follows a specific value through
assignment/parameter-binding; it only asks whether two kinds of regex hit
occurred close together (optionally: within the same function). See the
V2.5.0 epic (#102) discussion for why "taint tracker" overclaims what this
does versus security_lens.py's actual variable-identity echo check.
"""
import bisect
from typing import Dict, List, Optional, Sequence, Tuple


def correlate_signals(targets: List[int], dampeners: List[int], max_distance: int = 500) -> Tuple[int, int]:
    """
    Sweeps two sorted lists of indices to find how many targets are within
    'max_distance' of a dampener. Runs in O(N) linear time.
    """
    if not targets:
        return 0, 0
    if not dampeners:
        return len(targets), 0

    unmitigated_count = 0
    mitigated_count = 0

    damp_idx = 0
    damp_len = len(dampeners)

    for t_pos in targets:
        # Move the dampener pointer forward until it is somewhat near the target
        while damp_idx < damp_len and dampeners[damp_idx] < (t_pos - max_distance):
            damp_idx += 1

        # Check if the closest dampener is within the blast radius
        if damp_idx < damp_len and abs(dampeners[damp_idx] - t_pos) <= max_distance:
            mitigated_count += 1
        else:
            unmitigated_count += 1

    return unmitigated_count, mitigated_count


def filter_positions_in_range(positions: Sequence[int], start: int, end: int) -> List[int]:
    """
    Returns the subset of a SORTED position list falling within [start, end).
    Same O(log N) bisect approach _calculate_block_metrics already uses to
    build a satellite's own hit_vector -- reused here so correlation and
    per-function metrics agree on what "inside this function" means.
    """
    left = bisect.bisect_left(positions, start)
    right = bisect.bisect_left(positions, end)
    return list(positions[left:right])


def correlate_scoped(
    targets: List[int],
    dampeners: List[int],
    satellite_ranges: Optional[List[Tuple[int, int]]],
    max_distance: int = 500,
) -> Tuple[int, int]:
    """
    Same contract as correlate_signals (returns unmitigated_count,
    mitigated_count) but requires a target and its dampener to additionally
    fall within the SAME satellite/function range to correlate.

    A target that doesn't fall inside any known satellite range (module-level
    code, or a segment where no functions were sliced at all) falls back to
    the flat, distance-only behavior against the full dampener list -- this
    is exactly today's pre-scoping behavior, so nothing that correlated
    before stops correlating; code inside a detected function just gets the
    stricter, more correct same-function requirement on top.

    Assumes satellite_ranges are sorted by start and non-overlapping, which
    holds for every existing slicer (_slice_by_braces, _slice_by_indentation,
    etc. all track last_end_idx to skip overlapping matches).
    """
    if not targets:
        return 0, 0
    if not satellite_ranges:
        return correlate_signals(targets, dampeners, max_distance)

    starts = [r[0] for r in satellite_ranges]
    covered_targets: Dict[int, List[int]] = {}
    uncovered_targets: List[int] = []

    for pos in targets:
        idx = bisect.bisect_right(starts, pos) - 1
        if idx >= 0 and satellite_ranges[idx][0] <= pos < satellite_ranges[idx][1]:
            covered_targets.setdefault(idx, []).append(pos)
        else:
            uncovered_targets.append(pos)

    total_unmitigated = 0
    total_mitigated = 0

    for sat_idx, sat_targets in covered_targets.items():
        sat_start, sat_end = satellite_ranges[sat_idx]
        scoped_dampeners = filter_positions_in_range(dampeners, sat_start, sat_end)
        unmit, mit = correlate_signals(sat_targets, scoped_dampeners, max_distance)
        total_unmitigated += unmit
        total_mitigated += mit

    if uncovered_targets:
        unmit, mit = correlate_signals(uncovered_targets, dampeners, max_distance)
        total_unmitigated += unmit
        total_mitigated += mit

    return total_unmitigated, total_mitigated


def apply_dampener_correlations(
    spatial_map: Dict[str, List[int]],
    satellite_ranges: List[Tuple[int, int]],
    counts: Dict[str, int],
    mitigations: Dict[str, int],
) -> None:
    """
    Runs the three dampener-pair correlations (#346 phase 1) scoped to real
    function boundaries instead of a flat character radius: a target and its
    dampener must fall within the SAME satellite to mitigate one another.

    A target outside every known satellite range (module-level code, or a
    segment where no functions were sliced at all) falls back to the
    pre-scoping flat behavior -- see correlate_scoped()'s docstring. Nothing
    that correlated before this change stops correlating; code inside a
    detected function just gets the stricter, same-function requirement these
    dampeners always should have had.

    Mutates `counts`/`mitigations` in place, matching the style
    detector.py's coding_analysis() already uses throughout.
    """
    # 2. The Silencer Region (True Safety)
    if "high_risk_execution" in spatial_map and "safety" in spatial_map:
        _, mitigated_danger = correlate_scoped(
            targets=spatial_map["high_risk_execution"],
            dampeners=spatial_map["safety"],
            satellite_ranges=satellite_ranges,
            max_distance=500,
        )
        counts["high_risk_execution"] -= mitigated_danger
        mitigations["mitigated_danger"] += mitigated_danger

    # 3. The Race Condition Radar. Only the dampener half (sync_locks
    # mitigating state_mutation) is scoped here -- the amplifier half
    # (concurrency near state_mutation) is a lower-urgency false-positive
    # risk, not the false-negative class this phase targets, and is left on
    # the flat radius pending #348.
    if "concurrency" in spatial_map and "state_mutation" in spatial_map:
        unmitigated_flux, _ = correlate_scoped(
            targets=spatial_map["state_mutation"],
            dampeners=spatial_map.get("sync_locks", []),
            satellite_ranges=satellite_ranges,
            max_distance=300,
        )
        if unmitigated_flux > 0:
            _, race_conditions = correlate_signals(
                targets=spatial_map["concurrency"],
                dampeners=spatial_map["state_mutation"],
                max_distance=150,
            )
            counts["concurrency"] += race_conditions * 5
            mitigations["amplified_race_conditions"] += race_conditions

    # 5. The Memory Leak / UAF Tracker
    if "memory_alloc" in spatial_map:
        unmitigated_allocs, _ = correlate_scoped(
            targets=spatial_map["memory_alloc"],
            dampeners=spatial_map.get("cleanup", []),
            satellite_ranges=satellite_ranges,
            max_distance=800,
        )
        original_allocs = len(spatial_map["memory_alloc"])
        mitigated = original_allocs - unmitigated_allocs

        counts["memory_alloc"] = unmitigated_allocs
        mitigations["mitigated_memory_allocs"] += mitigated
