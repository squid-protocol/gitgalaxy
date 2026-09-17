# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Single-scan FILE and REPO archetype classification from the frozen brains
(analysis_lens.FILE_ARCHETYPE_BRAIN / REPO_ARCHETYPE_BRAIN).

The file/repo taxonomies are population-relative: structural/graph features are
percentile-ranked against the whole corpus. Each brain ships the frozen reference
quantiles, so one scan reproduces those ranks deterministically. Pure-python (no
numpy) so it runs in zero-dependency mode; degrades gracefully when a brain is
absent or a network metric (pagerank in zero-dep mode) is missing.
"""

from __future__ import annotations

import bisect
import logging
import math
from typing import Any

from gitgalaxy.standards import analysis_lens

logger = logging.getLogger(__name__)

NONCODE_FILE_ARCHETYPES = {"Declarative / Non-Code", "Data / Markup / Trivial"}

# Quantile-range runtime canary (#3125, mechanism c). Each brain ships the frozen
# reference quantiles a feature was trained over; a scan whose observed values
# fall SYSTEMATICALLY outside that range means the feature's scale/semantics have
# drifted since training (e.g. a changed denominator), even though dimensions
# still match and no other guard fires. We count out-of-range observations per
# feature and, past these thresholds, surface a real diagnostic instead of
# classifying confidently. A handful of naturally-extreme files is expected; a
# large fraction is the signal.
_DRIFT_MIN_SAMPLES = 20
_DRIFT_FRACTION = 0.05

# Warn at most once per (message) so a parity break can't flood a scan log.
_logged_parity_warnings: set[str] = set()


def _warn_once(msg: str) -> None:
    if msg not in _logged_parity_warnings:
        _logged_parity_warnings.add(msg)
        logger.warning(msg)


def _rank(value: float, ref: list) -> float:
    """Map a value to its [0,1] percentile using frozen reference quantiles."""
    if not ref:
        return 0.0
    return bisect.bisect_right(ref, float(value)) / (len(ref) - 1)


def _record_drift(drift: dict, feature: str, value: float, ref: list) -> None:
    """Accumulate an out-of-range tally for the quantile canary. ``ref`` is the
    feature's frozen quantile reference (ascending); values below ref[0] or above
    ref[-1] were never seen at training scale."""
    if not ref:
        return
    slot = drift.setdefault(feature, {"n": 0, "below": 0, "above": 0, "max_over": 0.0})
    slot["n"] += 1
    lo, hi = ref[0], ref[-1]
    if value < lo:
        slot["below"] += 1
    elif value > hi:
        slot["above"] += 1
        slot["max_over"] = max(slot["max_over"], value - hi)


def quantile_drift_diagnostics(drift: dict) -> list[str]:
    """Turn an accumulated drift tally into human-readable diagnostics, one per
    feature that fell outside its trained range on a large enough fraction of
    files to indicate scale/semantic drift rather than a few extreme outliers.
    Returns [] when nothing is systematically off."""
    out: list[str] = []
    for feature, s in sorted(drift.items()):
        n = s["n"]
        oor = s["below"] + s["above"]
        if n < _DRIFT_MIN_SAMPLES or oor == 0:
            continue
        frac = oor / n
        if frac >= _DRIFT_FRACTION:
            out.append(
                f"archetype feature '{feature}': {frac:.0%} of {n} files fell outside the range it "
                f"was trained on ({s['below']} below / {s['above']} above; max overshoot "
                f"{s['max_over']:.3g}) -- its scale or computation may have drifted from the brain's "
                f"training corpus; composition archetypes for this scan may be unreliable"
            )
    return out


def _nearest(vec: list, centroids: dict):
    """Return (name, euclidean_distance) of the nearest centroid, or (None, None)."""
    best, best_d = None, None
    for name, c in centroids.items():
        if len(c) != len(vec):
            continue  # length guard (stale brain) -> unclassified
        d = sum((a - b) * (a - b) for a, b in zip(vec, c))
        if best_d is None or d < best_d:
            best_d, best = d, name
    return best, (math.sqrt(best_d) if best_d is not None else None)


def _fit_z(dist, name, brain) -> float:
    """Archetype-fit z-score: (distance - cluster mean) / cluster std. 0 if unknown."""
    zp = (brain.get("z_score_params") or {}).get(name)
    if not zp or dist is None:
        return 0.0
    return round((dist - zp["mean"]) / (zp["std"] or 1.0), 3)


def classify_file(f: dict[str, Any], drift: dict | None = None):
    """Return (composition_archetype, fit_z_score) for a file, or (None, None) if the
    brain is unavailable or the engine cannot honour its feature contract. Bucket
    labels (non-code) carry z=0.0. Pass a ``drift`` dict to accumulate the
    quantile-range canary tally (see ``quantile_drift_diagnostics``)."""
    b = analysis_lens.FILE_ARCHETYPE_BRAIN
    if not b:
        return None, None
    tel = f.get("telemetry", {}) or {}
    lang = str(f.get("lang_id", "")).lower()
    coding_loc = float(f.get("coding_loc", 0) or 0)
    if lang in set(b["noncode_languages"]) or coding_loc < b["min_coding_loc"]:
        return b["noncode_bucket"], 0.0

    mix = tel.get("function_archetype_mix", {}) or {}
    total = sum(mix.get(a, 0) for a in b["stoich_archetypes"])
    stoich = [(mix.get(a, 0) / total if total else 0.0) * b["stoich_weight"] for a in b["stoich_archetypes"]]

    net = tel.get("network_metrics", {}) or {}
    denom = coding_loc if coding_loc > 0 else 1.0
    raw = {
        "log_coding_loc": math.log1p(coding_loc),
        "log_function_count": math.log1p(len(f.get("functions", []))),
        "log_class_count": math.log1p(len(f.get("classes", []))),
        "log_import_count": math.log1p(len(f.get("raw_imports", []))),
        "encapsulation_ratio": min(max(float(tel.get("encapsulation_ratio", 0.0) or 0.0), 0.0), 1.0),
        "doc_ratio": min(float(f.get("doc_loc", 0) or 0) / denom, 2.0),
        "control_flow_ratio": min(float(tel.get("control_flow_ratio", 0.0) or 0.0), 5.0),
        "log_pagerank": math.log1p(max(float(net.get("pagerank_score", 0.0) or 0.0), 0.0)),
        "log_blast_radius": math.log1p(max(float(net.get("normalized_blast_radius", 0.0) or 0.0), 0.0)),
    }
    quantiles = b.get("aux_quantiles", {})
    aux = []
    for fn in b["aux_features"]:
        if fn not in raw:
            # The brain declares an aux feature this engine has no formula for --
            # a trainer/engine parity break. Degrade to unclassified (visible)
            # rather than KeyError-crash the whole scan or invent a 0.0 column.
            # test_archetype_parity fails a build long before this can ship.
            _warn_once(
                f"file archetype brain declares aux feature {fn!r} the engine cannot compute; "
                f"skipping composition classification (see archetype_parity.check_brain)"
            )
            return None, None
        ref = quantiles.get(fn) or []
        val = raw[fn]
        if drift is not None:
            _record_drift(drift, fn, val, ref)
        aux.append(_rank(val, ref))
    name, dist = _nearest(stoich + aux, b["centroids"])
    if name is None:
        return b["noncode_bucket"], 0.0
    return name, _fit_z(dist, name, b)


def _gini(vals: list) -> float:
    xs = sorted(float(x) for x in vals)
    n, s = len(xs), sum(xs)
    if n == 0 or s == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * s)


def classify_repo(parsed_files: list[dict[str, Any]]):
    """Return (repo_archetype, fit_z_score) aggregated from the scan's per-file
    composition archetypes + scale + coupling, or (None, None). Requires classify_file
    to have populated composition_file_archetype. Micro bucket carries z=0.0."""
    b = analysis_lens.REPO_ARCHETYPE_BRAIN
    if not b:
        return None, None
    file_count = len(parsed_files)
    if file_count < b["min_files"]:
        return b["micro_bucket"], 0.0

    comp_counts: dict[str, int] = {}
    noncode = 0
    total_loc = 0.0
    pageranks = []
    for f in parsed_files:
        tel = f.get("telemetry", {}) or {}
        fa = tel.get("composition_file_archetype")
        if fa in NONCODE_FILE_ARCHETYPES:
            noncode += 1
        elif fa:
            comp_counts[fa] = comp_counts.get(fa, 0) + 1
        total_loc += float(f.get("coding_loc", 0) or 0)
        pageranks.append(float((tel.get("network_metrics", {}) or {}).get("pagerank_score", 0.0) or 0.0))

    total_code = sum(comp_counts.values())
    comp = [
        (comp_counts.get(a, 0) / total_code if total_code else 0.0) * b["comp_weight"] for a in b["comp_archetypes"]
    ]
    q = b["aux_quantiles"]
    scale = [_rank(math.log1p(file_count), q["log_file_count"]), _rank(math.log1p(total_loc), q["log_total_loc"])]
    ncf = [noncode / file_count if file_count else 0.0]
    coup = [_rank(_gini(pageranks), q["pagerank_gini"])]
    name, dist = _nearest(comp + scale + ncf + coup, b["centroids"])
    if name is None:
        return None, None
    return name, _fit_z(dist, name, b)
