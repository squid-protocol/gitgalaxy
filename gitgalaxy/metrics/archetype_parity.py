# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Algorithmic parity gate between the offline archetype trainers
(gitgalaxy-population-analyses) and this engine (#3125).

The composition brains in ``standards/archetype_brains/`` are trained in a
separate repo and consumed here by ``archetype_classifier``. The engine builds
each file/repo feature vector *from the brain's own* ``stoich_archetypes`` /
``aux_features`` / ``comp_archetypes`` lists, so reorders and renames are followed
automatically -- but there is no free lunch: if a refrozen brain declares an aux
feature the engine cannot compute, or its feature space drifts from what the
trainer recorded, the old behaviour was a ``KeyError`` mid-scan or a silently
wrong classification. v2.8.0 shipped exactly that class of drift.

This module is the machine-checkable half of the contract:

* ``feature_contract_sha`` recomputes, byte-for-byte, the same hash the trainer
  baked into ``provenance.feature_contract_sha`` (see
  ``gitgalaxy-population-analyses/freeze_archetype_brains.py::_contract_sha``).
  Keep the canonicalization -- ``sort_keys=True`` + compact separators, list
  order preserved -- identical on both sides; it *is* the contract.
* ``check_brain`` validates a loaded brain against (1) the engine's own set of
  computable features, (2) its declared centroid dimensionality, and (3) the
  provenance sha. It returns a list of human-readable problems (empty == OK) and
  never raises, so it is safe to call at load time and in CI.

This is a leaf module: stdlib only, no engine imports, importable in
zero-dependency mode.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# --- The engine's side of the contract -----------------------------------------
# The aux features the FILE classifier knows how to compute from a scanned file,
# in the order it emits them. MUST equal the keys of the ``raw`` map built in
# ``archetype_classifier.classify_file`` (guarded by test_archetype_parity). A
# brain that declares an aux feature outside this set cannot be scored here.
ENGINE_FILE_AUX_FEATURES: tuple[str, ...] = (
    "log_coding_loc",
    "log_function_count",
    "log_class_count",
    "log_import_count",
    "encapsulation_ratio",
    "doc_ratio",
    "control_flow_ratio",
    "log_pagerank",
    "log_blast_radius",
)

# The REPO classifier hardcodes these graph/scale features (it reads their frozen
# quantiles from the brain's ``aux_quantiles``).
ENGINE_REPO_SCALE_FEATURES: tuple[str, ...] = ("log_file_count", "log_total_loc")
ENGINE_REPO_COUPLING_FEATURE: str = "pagerank_gini"


def _sha(contract: dict[str, Any]) -> str:
    blob = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def feature_contract(brain: dict[str, Any], level: str) -> dict[str, Any]:
    """Reconstruct the ordered feature contract from the brain's LIVE top-level
    fields -- the exact ones ``archetype_classifier`` consumes -- so its sha
    reflects the space the engine will actually score against, not a possibly
    stale copy stored inside the provenance block.
    """
    if level == "file":
        return {
            "level": "file",
            "k": brain.get("k"),
            "stoich_weight": brain.get("stoich_weight"),
            "stoich_archetypes": brain.get("stoich_archetypes"),
            "aux_features": brain.get("aux_features"),
            "noncode_languages": brain.get("noncode_languages"),
            "min_coding_loc": brain.get("min_coding_loc"),
        }
    if level == "repo":
        return {
            "level": "repo",
            "k": brain.get("k"),
            "comp_weight": brain.get("comp_weight"),
            "comp_archetypes": brain.get("comp_archetypes"),
            "scale_features": brain.get("scale_features"),
            "coupling_feature": brain.get("coupling_feature"),
            "feature_order": brain.get("feature_order"),
            "min_files": brain.get("min_files"),
        }
    raise ValueError(f"unknown brain level {level!r}")


def feature_contract_sha(brain: dict[str, Any], level: str) -> str:
    """The 16-hex-char sha of the brain's live feature contract. Must equal the
    trainer's baked ``provenance.feature_contract_sha`` when the brain and the
    engine agree on the feature space."""
    return _sha(feature_contract(brain, level))


def _expected_centroid_dim(brain: dict[str, Any], level: str) -> int | None:
    try:
        if level == "file":
            return len(brain["stoich_archetypes"]) + len(brain["aux_features"])
        if level == "repo":
            # comp_archetypes + scale_features + non_code_fraction(1) + coupling(1)
            return len(brain["comp_archetypes"]) + len(brain["scale_features"]) + 2
    except (KeyError, TypeError):
        return None
    return None


def check_brain(brain: dict[str, Any], level: str) -> list[str]:
    """Validate a loaded composition brain. Returns a list of problem strings
    (empty == parity holds). Never raises -- safe at load time and in CI.

    Checks:
      1. the brain declares a feature contract the engine can compute,
      2. its centroids match its declared feature dimensionality,
      3. its live contract sha matches the trainer's baked provenance sha.
    """
    problems: list[str] = []
    if not brain:
        return ["brain is empty/unloaded"]

    if level == "file":
        aux = brain.get("aux_features") or []
        unknown = [a for a in aux if a not in ENGINE_FILE_AUX_FEATURES]
        if unknown:
            problems.append(
                f"file brain declares aux feature(s) the engine cannot compute: {unknown} "
                f"(engine knows: {list(ENGINE_FILE_AUX_FEATURES)})"
            )
    elif level == "repo":
        sf = brain.get("scale_features") or []
        if list(sf) != list(ENGINE_REPO_SCALE_FEATURES):
            problems.append(f"repo brain scale_features {sf} != engine's {list(ENGINE_REPO_SCALE_FEATURES)}")
        if brain.get("coupling_feature") != ENGINE_REPO_COUPLING_FEATURE:
            problems.append(
                f"repo brain coupling_feature {brain.get('coupling_feature')!r} != "
                f"engine's {ENGINE_REPO_COUPLING_FEATURE!r}"
            )
    else:
        return [f"unknown brain level {level!r}"]

    # 2. centroid dimensionality vs declared contract
    expected = _expected_centroid_dim(brain, level)
    centroids = brain.get("centroids") or {}
    if expected is not None and centroids:
        bad = {n: len(c) for n, c in centroids.items() if len(c) != expected}
        if bad:
            problems.append(
                f"{level} brain centroid dim mismatch: expected {expected} from the feature "
                f"contract, got {sorted(set(bad.values()))} (e.g. {next(iter(bad))!r})"
            )

    # 3. provenance sha vs live contract sha
    prov = brain.get("provenance") or {}
    baked = prov.get("feature_contract_sha")
    if not baked:
        problems.append(
            "brain carries no provenance.feature_contract_sha -- cannot verify trainer/engine parity "
            "(refreeze with a trainer that bakes provenance, #3124)"
        )
    else:
        live = feature_contract_sha(brain, level)
        if live != baked:
            problems.append(
                f"feature_contract_sha mismatch: brain's live feature fields hash to {live} but "
                f"provenance records {baked} -- the brain's feature space was altered after freezing, "
                f"or the engine and trainer disagree on the contract"
            )
    return problems
