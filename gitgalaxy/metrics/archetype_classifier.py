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

import bisect
import math
from typing import Any, Optional

from gitgalaxy.standards import analysis_lens

NONCODE_FILE_ARCHETYPES = {"Declarative / Non-Code", "Data / Markup / Trivial"}


def _rank(value: float, ref: list) -> float:
    """Map a value to its [0,1] percentile using frozen reference quantiles."""
    if not ref:
        return 0.0
    return bisect.bisect_right(ref, float(value)) / (len(ref) - 1)


def _nearest(vec: list, centroids: dict) -> Optional[str]:
    best, best_d = None, None
    for name, c in centroids.items():
        if len(c) != len(vec):
            continue  # length guard (stale brain) -> unclassified
        d = sum((a - b) * (a - b) for a, b in zip(vec, c))
        if best_d is None or d < best_d:
            best_d, best = d, name
    return best


def classify_file(f: dict[str, Any]) -> Optional[str]:
    """Assign a file its composition archetype (function-stoichiometry + structure
    + graph role). Returns None if the brain is unavailable."""
    b = analysis_lens.FILE_ARCHETYPE_BRAIN
    if not b:
        return None
    tel = f.get("telemetry", {}) or {}
    lang = str(f.get("lang_id", "")).lower()
    coding_loc = float(f.get("coding_loc", 0) or 0)
    if lang in set(b["noncode_languages"]) or coding_loc < b["min_coding_loc"]:
        return b["noncode_bucket"]

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
    aux = [_rank(raw[fn], b["aux_quantiles"][fn]) for fn in b["aux_features"]]
    return _nearest(stoich + aux, b["centroids"]) or b["noncode_bucket"]


def _gini(vals: list) -> float:
    xs = sorted(float(x) for x in vals)
    n, s = len(xs), sum(xs)
    if n == 0 or s == 0:
        return 0.0
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * s)


def classify_repo(parsed_files: list[dict[str, Any]]) -> Optional[str]:
    """Aggregate the scan's per-file composition archetypes + scale + coupling into a
    repo archetype. Requires classify_file to have populated composition_file_archetype."""
    b = analysis_lens.REPO_ARCHETYPE_BRAIN
    if not b:
        return None
    file_count = len(parsed_files)
    if file_count < b["min_files"]:
        return b["micro_bucket"]

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
    return _nearest(comp + scale + ncf + coup, b["centroids"])
