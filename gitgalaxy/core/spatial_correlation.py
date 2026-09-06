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
from collections.abc import Mapping, Sequence
from typing import Optional


def correlate_signals(targets: list[int], dampeners: list[int], max_distance: int = 500) -> tuple[int, int]:
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


def filter_positions_in_range(positions: Sequence[int], start: int, end: int) -> list[int]:
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
    targets: list[int],
    dampeners: list[int],
    satellite_ranges: Optional[list[tuple[int, int]]],
    max_distance: int = 500,
) -> tuple[int, int]:
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
    covered_targets: dict[int, list[int]] = {}
    uncovered_targets: list[int] = []

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


# ==============================================================================
# THE PROXIMITY WEIGHT TABLE (#2813, contract roadmap Phase 2 / decision D1)
#
# A recorded signal count is a COUNT: the number of rule hits in the file. The
# six proximity pairs below used to add their weights into `counts[...]` in
# place (the x3 cascading flux, the silencer dampener, the x5 / x100 / +1
# amplifiers), so `state_mutation` in every recorder, golden master and
# keyword-rosetta manifest was `raw + 2 * cascading` -- a score wearing a
# count's name (#2546/#2631 documented it and made the raw count recoverable;
# this table finishes the move). The pairs now write ONLY to the per-file
# `mitigation_telemetry` tally, and the score layer reads
# `weighted_count()` -- exactly the figure the recorded count used to carry --
# so every risk formula is unchanged by construction while the count is a count.
#
#   signal -> ((telemetry key, weight per tallied pairing), ...)
#   weighted = raw + sum(weight * mitigations[telemetry key])
# ==============================================================================
PROXIMITY_WEIGHTS: dict[str, tuple[tuple[str, int], ...]] = {
    # Block 2, The Silencer Region: a same-function safety net cancels one danger hit.
    "high_risk_execution": (("mitigated_danger", -1),),
    # Block 3, The Race Condition Radar: +5 per concurrency hit near unsynchronised flux.
    "concurrency": (("amplified_race_conditions", 5),),
    # Block 5, The Memory Leak / UAF Tracker: an alloc with a same-function cleanup is mitigated.
    "memory_alloc": (("mitigated_memory_allocs", -1),),
    # Block 0, The Exfiltration Distance Check: +100 per memory read paired with an outbound socket.
    "memory_scraping": (("amplified_exfiltration", 100),),
    # Block 1, Taint Tracking: +1 per danger hit corroborated by nearby io. The raw count here is
    # security_lens.py's own variable-echo finding, merged additively in galaxyscope.py (#344).
    "sec_tainted_injection": (("amplified_rce", 1),),
    # Block 6, The OOM Bomb: +2 per cascading mutation = x3 net (the flux weighting, #2546).
    "state_mutation": (("amplified_cascading_flux", 2),),
}

WEIGHTED_SIGNALS: tuple[str, ...] = tuple(PROXIMITY_WEIGHTS)


def weighted_count(raw_signals: Mapping[str, int], mitigations: Mapping[str, int], key: str) -> int:
    """
    The score-layer view of one signal: the raw count plus every proximity
    weight the correlation pass tallied for it. For a signal with no entry in
    PROXIMITY_WEIGHTS this is the raw count itself. Never below zero: a
    dampener can cancel at most the hits it mitigated.
    """
    value = int(raw_signals.get(key, 0) or 0)
    for telemetry_key, weight in PROXIMITY_WEIGHTS.get(key, ()):
        value += weight * int(mitigations.get(telemetry_key, 0) or 0)
    return max(value, 0)


def weighted_view(raw_signals: Mapping[str, int], mitigations: Mapping[str, int]) -> dict[str, int]:
    """
    A copy of `raw_signals` with every PROXIMITY_WEIGHTS signal replaced by its
    weighted_count(). Consumers that combine signals into a score (the risk
    formulas, the archetype fingerprint, the ML feature frame, the statistical
    gates) read this so they see exactly what the recorded count used to be;
    recorders and the corpus read `raw_signals` itself.
    """
    view = dict(raw_signals)
    for key in WEIGHTED_SIGNALS:
        if key in view or any(mitigations.get(tk, 0) for tk, _ in PROXIMITY_WEIGHTS[key]):
            view[key] = weighted_count(raw_signals, mitigations, key)
    return view


def apply_dampener_correlations(
    spatial_map: dict[str, list[int]],
    satellite_ranges: list[tuple[int, int]],
    mitigations: dict[str, int],
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

    Mutates `mitigations` in place and nothing else (#2813): the recorded
    signal counts stay raw, and the score layer applies these tallies through
    weighted_count() / PROXIMITY_WEIGHTS above.
    """
    # 2. The Silencer Region (True Safety)
    if "high_risk_execution" in spatial_map and "safety" in spatial_map:
        _, mitigated_danger = correlate_scoped(
            targets=spatial_map["high_risk_execution"],
            dampeners=spatial_map["safety"],
            satellite_ranges=satellite_ranges,
            max_distance=500,
        )
        mitigations["mitigated_danger"] = mitigations.get("mitigated_danger", 0) + mitigated_danger

    # 3. The Race Condition Radar (both halves now scoped, #348: the sync_locks
    # dampener check first, then the concurrency amplifier check only against
    # the SAME-scoped state_mutation hits that survived it).
    if "concurrency" in spatial_map and "state_mutation" in spatial_map:
        unmitigated_flux, _ = correlate_scoped(
            targets=spatial_map["state_mutation"],
            dampeners=spatial_map.get("sync_locks", []),
            satellite_ranges=satellite_ranges,
            max_distance=300,
        )
        if unmitigated_flux > 0:
            _, race_conditions = correlate_scoped(
                targets=spatial_map["concurrency"],
                dampeners=spatial_map["state_mutation"],
                satellite_ranges=satellite_ranges,
                max_distance=150,
            )
            mitigations["amplified_race_conditions"] = mitigations.get("amplified_race_conditions", 0) + race_conditions

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
        mitigations["mitigated_memory_allocs"] = mitigations.get("mitigated_memory_allocs", 0) + mitigated


def apply_amplifier_correlations(
    spatial_map: dict[str, list[int]],
    satellite_ranges: list[tuple[int, int]],
    mitigations: dict[str, int],
) -> None:
    """
    Runs the three remaining in-segment amplifier-pair correlations (#348, #102)
    scoped to real function boundaries, for consistency with
    apply_dampener_correlations().

    Unlike a wrong-scope dampener, a wrong-scope amplifier only costs one extra
    review item (a false positive) -- an accepted tradeoff for this project, not
    the false-negative risk phase 1 targeted. These are migrated here mainly so
    every correlate() call in the pipeline shares the same scoping semantics,
    not because the flat radius was actively harmful the way the dampeners were.

    Mutates `mitigations` in place and nothing else (#2813), matching
    apply_dampener_correlations(); the multipliers live in PROXIMITY_WEIGHTS.
    """
    # 0. The Exfiltration Distance Check (memory read -> outbound socket).
    # The one correlate() pair #346/#348 missed when they enumerated and
    # migrated the other six -- it kept running flat/unscoped in
    # coding_analysis() until #102 closed out the last "sporadic" gap.
    # Tallied under its own key (#2813): `amplified_leaks` is the Active
    # Hemorrhage's key (galaxyscope.py Phase 5.5, sec_hardcoded_secrets near a
    # telemetry sink) and the two used to share it, so a weighted
    # memory_scraping could not be told apart from a hemorrhaging secret.
    if "memory_scraping" in spatial_map and "exfiltration_camouflage" in spatial_map:
        _, confirmed_exfiltration = correlate_scoped(
            targets=spatial_map["memory_scraping"],
            dampeners=spatial_map["exfiltration_camouflage"],
            satellite_ranges=satellite_ranges,
            max_distance=200,  # If they happen within 200 chars of each other, it's a confirmed attack
        )
        mitigations["amplified_exfiltration"] = mitigations.get("amplified_exfiltration", 0) + confirmed_exfiltration

    # 1. Taint Tracking (RCE Weaponization)
    if "high_risk_execution" in spatial_map and "io" in spatial_map:
        _, corroborated_rce = correlate_scoped(
            targets=spatial_map["high_risk_execution"],
            dampeners=sorted(spatial_map["io"]),
            satellite_ranges=satellite_ranges,
            max_distance=250,
        )
        mitigations["amplified_rce"] = mitigations.get("amplified_rce", 0) + corroborated_rce

    # 6. The OOM Bomb (Cascading State Flux) -- the x3 flux weighting (#2546).
    #
    # SEMANTICS (documented per #2546; mapped by the #1096 keyword-rosetta
    # control corpus, ledger entry `state-flux-branch-weighting`): every
    # state_mutation hit with a branch hit within 150 CHARACTERS *and* inside
    # the SAME function (correlate_scoped; flat-radius fallback for
    # module-level code) is "cascading" and is tallied here; the score layer
    # weights it +2 on top of the raw hit -- x3 net -- through
    # PROXIMITY_WEIGHTS. State mutated under nearby control flow is
    # deliberately weighted as riskier than straight-line mutation; this feeds
    # risk_state_flux / cognitive-load scoring downstream.
    #
    # NOT a blanket per-function toggle: the corpus first described this as
    # "branch context anywhere in the function triples every mutation", which
    # only *looked* true because its probe functions were shorter than the
    # 150-char radius. A mutation >150 chars from every branch in its
    # function stays x1.
    #
    # OBSERVABILITY (#2813): the recorded `state_mutation` IS the raw hit
    # count. The tally below is `amplified_cascading_flux` in
    # mitigation_telemetry, surfaced per file in the audit report ("6.
    # Contextual Mitigations & Amplifications") next to the weighted view:
    #     weighted = recorded_state_mutation + 2 * amplified_cascading_flux.
    #
    # KNOWN AMPLIFIER FP (#2535, deliberately NOT fixed here): languages
    # whose branch rules aren't literal-shielded let a branch keyword inside
    # a STRING ("if eval fails, try open") create phantom branch context that
    # triples real, unrelated mutations nearby. That is the literal-shielding
    # question's highest-leverage scoring consequence and lands with
    # whichever direction #2535 takes.
    #
    # Behavior pinned by tests/core_engine/test_spatial_correlation.py's
    # flux-weighting micro-repros -- change those on purpose or not at all.
    if "state_mutation" in spatial_map and "branch" in spatial_map:
        _, cascading_flux = correlate_scoped(
            targets=spatial_map["state_mutation"],
            dampeners=spatial_map["branch"],
            satellite_ranges=satellite_ranges,
            max_distance=150,  # If state is mutated near heavy branching
        )
        mitigations["amplified_cascading_flux"] = mitigations.get("amplified_cascading_flux", 0) + cascading_flux


def correlate_against_ledger(
    threat_locations: dict[str, list[int]],
    functions: list[dict[str, int]],
    source_key: str,
    sink_key: str,
    max_distance: int = 10,
) -> tuple[int, int]:
    """
    Correlates two named signals from a POST-HOC pipeline stage -- outside
    detector.py entirely, e.g. dev_agent_firewall.py or ai_appsec_sensor.py,
    both of which run over fully-assembled parsed_files after coding_analysis()'s
    transient spatial_map is long gone (#346/#348).

    Reads only what already survives to that stage: file_data["threat_locations"]
    (rule_name -> [line_numbers], persisted for every rule detector.py runs) and
    file_data["functions"] (satellites, each carrying file-global start_line/
    end_line). No new field or schema change is required on either -- this is a
    query-time join, not a persisted association, which also means it can never
    go stale relative to whichever satellites _function_slice() last computed.

    `max_distance` here is in LINES, not characters -- these two lists are
    line-indexed, not char-offset-indexed, unlike correlate_scoped().

    Returns (unmitigated_count, mitigated_count), same contract as
    correlate_scoped(): a dampener-style caller (e.g. "is metaprogramming
    undocumented") wants the unmitigated count; a corroboration/amplifier-style
    caller (e.g. "is this API route near a DB call") wants the mitigated count.
    """
    sources = sorted(threat_locations.get(source_key, []))
    sinks = sorted(threat_locations.get(sink_key, []))

    satellite_ranges = sorted(
        (f["start_line"], f["end_line"] + 1)  # end_line is inclusive; correlate_scoped wants an exclusive upper bound
        for f in functions
        if "start_line" in f and "end_line" in f
    )

    return correlate_scoped(sources, sinks, satellite_ranges, max_distance)
