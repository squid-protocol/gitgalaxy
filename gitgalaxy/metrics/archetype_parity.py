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
import re
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


# ==============================================================================
# Archetype validation: graded, per-level trust state (#4100)
# ==============================================================================
# Retraining the brains (gitgalaxy-population-analyses) takes far longer than an
# engine change, so the engine is allowed to move ahead of them. What it must
# not do is present the archetypes as equally trustworthy afterwards. Each level
# of the tower -- function -> file -> composition file -> composition repo --
# therefore carries its own state:
#
#   VALIDATED    agreement with the trained state >= thresholds.validated
#   DRIFTING     agreement >= thresholds.degraded: engine changes have moved
#                some labels; still used, and the drift is reported
#   UNVALIDATED  no measurement covers the brain actually loaded
#   DEGRADED     agreement below thresholds.degraded, or a partial structural
#                break (some inputs dead); still used, qualified, retrain due
#   INVALID      the level cannot honour its contract (a dimension/feature
#                break, or input labels that match nothing); its labels are
#                WITHHELD rather than printed as confident nonsense
#
# "Agreement" is the share of crucible files whose label the current engine
# still assigns the way the engine the brain was trained against did. It is
# stability with respect to the trained state, NOT accuracy -- there is no
# ground-truth archetype to be accurate against.
#
# Two sources feed the state. Structural problems are computed LIVE from the
# loaded brains (cheap, deterministic, no corpus). Agreement comes from
# ``archetype_validation.json``, which ``tests/tools/archetype_drift.py``
# re-measures on language-crucible after every push to main. Only the
# structural half may change what a scan EMITS (withholding an INVALID level):
# the record is refreshed by automation, and a scan's labels must not depend on
# when that last ran.

# A label the trainer never named: a cluster index, not an archetype.
_UNNAMED_CLUSTER = re.compile(r"^(?:[A-Za-z_]*cluster_\d+|Cluster \d+)$")

# The tower, bottom-up. Each level's labels feed the next.
LEVELS: tuple[str, ...] = ("function", "file", "composition_file", "composition_repo")

STATES: tuple[str, ...] = ("VALIDATED", "DRIFTING", "UNVALIDATED", "DEGRADED", "INVALID")
_RANK = {s: i for i, s in enumerate(STATES)}

DEFAULT_THRESHOLDS: dict[str, float] = {"validated": 0.98, "degraded": 0.95}

# What a withheld (INVALID) level emits in place of a label.
WITHHELD_LABEL = "Unvalidated"


def worst(*states: str) -> str:
    return max(states, key=lambda s: _RANK.get(s, 0)) if states else "VALIDATED"


def brain_fingerprint(brain: dict[str, Any]) -> str:
    """16-hex sha of everything in a brain that can change a classification.
    ``provenance`` is excluded: it documents a brain, it does not score with it."""
    return _sha({k: v for k, v in (brain or {}).items() if k != "provenance"})


def _labels(level: str, brain: dict[str, Any]) -> list[str]:
    if level in ("function", "file"):
        return list(brain.get("cluster_names") or [])
    return list((brain.get("centroids") or {}).keys())


def _input_parity(level: str, produced: list[str], consumed: list[str], producer: str) -> list[tuple[str, str]]:
    """Problems with a level that reads ``producer``'s labels by name."""
    if not produced or not consumed:
        return []
    matched = [n for n in consumed if n in produced]
    if not matched:
        return [
            (
                "INVALID",
                f"{level} reads {producer} labels by name, but none of its {len(consumed)} inputs "
                f"(e.g. {consumed[0]!r}) is a label {producer} emits (e.g. {produced[0]!r}) -- every input "
                "column is 0.0",
            )
        ]
    unread = [n for n in produced if n not in consumed]
    dead = [n for n in consumed if n not in produced]
    if unread or dead:
        return [
            (
                "DEGRADED",
                f"{level} inputs disagree with {producer}'s labels: never read {unread}, never emitted {dead} "
                "-- those units drop out and those input columns are always 0.0",
            )
        ]
    return []


def structural_problems(brains: dict[str, dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    """Per level, every problem detectable from the loaded brains alone, as
    ``(severity, message)`` with severity INVALID, DEGRADED or NOTE. Never raises.
    ``brains`` is keyed by ``LEVELS``."""
    fn = brains.get("function") or {}
    fl = brains.get("file") or {}
    cf = brains.get("composition_file") or {}
    cr = brains.get("composition_repo") or {}
    out: dict[str, list[tuple[str, str]]] = {lvl: [] for lvl in LEVELS}

    for lvl, b in (("function", fn), ("file", fl), ("composition_file", cf), ("composition_repo", cr)):
        if not b:
            out[lvl].append(("INVALID", "brain is empty/unloaded"))
            continue
        names = _labels(lvl, b)
        bad = [n for n in names if _UNNAMED_CLUSTER.match(str(n))]
        if bad:
            out[lvl].append(
                (
                    "NOTE",
                    f"{len(bad)}/{len(names)} labels are unnamed cluster indices (e.g. {bad[0]!r}) -- reports "
                    "show a cluster number, not an archetype",
                )
            )

    # Per-brain engine parity (#3125) for the two composition brains.
    out["composition_file"] += [("INVALID", p) for p in check_brain(cf, "file")] if cf else []
    out["composition_repo"] += [("INVALID", p) for p in check_brain(cr, "repo")] if cr else []

    # function -> file: log_micro_<i>_pct indexes the function model's cluster order.
    fn_names = _labels("function", fn)
    micro = [f for f in fl.get("FEATURE_NAMES") or [] if f.startswith("log_micro_")]
    if fn_names and micro and len(micro) != len(fn_names):
        out["file"].append(
            (
                "INVALID",
                f"{len(micro)} log_micro_<i>_pct features for {len(fn_names)} function clusters -- the "
                "per-function composition columns are misaligned",
            )
        )
    # function -> composition_file, composition_file -> composition_repo: by name.
    out["composition_file"] += _input_parity(
        "composition_file", fn_names, list(cf.get("stoich_archetypes") or []), "the function model"
    )
    out["composition_repo"] += _input_parity(
        "composition_repo",
        _labels("composition_file", cf),
        list(cr.get("comp_archetypes") or []),
        "the composition_file brain",
    )

    # A level whose input level is INVALID cannot be better than INVALID.
    for lower, upper in zip(LEVELS, LEVELS[1:]):
        if any(sev == "INVALID" for sev, _ in out[lower]) and not any(sev == "INVALID" for sev, _ in out[upper]):
            out[upper].append(("INVALID", f"its input level {lower!r} is INVALID"))
    return out


def measured_state(agreement: float | None, thresholds: dict[str, float]) -> str:
    if agreement is None:
        return "UNVALIDATED"
    if agreement >= thresholds["validated"]:
        return "VALIDATED"
    if agreement >= thresholds["degraded"]:
        return "DRIFTING"
    return "DEGRADED"


def withheld_levels(brains: dict[str, dict[str, Any]]) -> set[str]:
    """Levels whose labels a scan must withhold: structurally INVALID ones.
    Depends only on the loaded brains, never on the drift record."""
    return {lvl for lvl, probs in structural_problems(brains).items() if any(s == "INVALID" for s, _ in probs)}


def validation_status(brains: dict[str, dict[str, Any]], record: dict[str, Any]) -> dict[str, Any]:
    """The trust state of every archetype level for THIS engine + THESE brains.

    Returns ``{"trained": {...}, "measured": {...}, "thresholds": {...},
    "retrain_issue": int|None, "levels": {level: {"state", "agreement",
    "reasons": [...], "notes": [...], ...}}}``. Never raises.
    """
    record = record or {}
    thresholds = {**DEFAULT_THRESHOLDS, **(record.get("thresholds") or {})}
    trained = record.get("trained") or {}
    fingerprints = trained.get("brain_fingerprints") or {}
    recorded_levels = record.get("levels") or {}
    structural = structural_problems(brains)

    levels: dict[str, dict[str, Any]] = {}
    for lvl in LEVELS:
        rec = recorded_levels.get(lvl) or {}
        reasons: list[str] = []
        notes = [m for sev, m in structural[lvl] if sev == "NOTE"]
        live_fp = brain_fingerprint(brains.get(lvl) or {})
        if not record:
            state, agreement = "UNVALIDATED", None
            reasons.append("no archetype validation record shipped")
        elif fingerprints.get(lvl) != live_fp:
            state, agreement = "UNVALIDATED", None
            reasons.append(f"brain changed since the validation record was cut (fingerprint {live_fp})")
        else:
            agreement = rec.get("agreement")
            state = measured_state(agreement, thresholds) if "agreement" in rec else "UNVALIDATED"
            # A level with no measurable agreement of its own (the crucible is one
            # repo) inherits the measured state of the level that feeds it.
            if rec.get("inherits"):
                state = levels.get(rec["inherits"], {}).get("state", state)
                reasons.append(f"not measurable on one corpus; inherits {rec['inherits']}'s measured state")
            elif state in ("DRIFTING", "DEGRADED") and agreement is not None:
                reasons.append(
                    f"engine changes since training relabelled {1 - agreement:.1%} of crucible files "
                    f"(agreement {agreement:.1%})"
                )
            elif state == "UNVALIDATED":
                reasons.append("never measured against the crucible")
        for sev, msg in structural[lvl]:
            if sev in ("INVALID", "DEGRADED"):
                state = worst(state, sev)
                reasons.append(msg)
        levels[lvl] = {
            "state": state,
            "agreement": agreement,
            "reasons": reasons,
            "notes": notes,
            "eroding": rec.get("eroding") or {},
            "withheld": state == "INVALID",
        }
    return {
        "trained": {k: v for k, v in trained.items() if k != "brain_fingerprints"},
        "measured": record.get("measured") or {},
        "thresholds": thresholds,
        "retrain_issue": record.get("retrain_issue"),
        "levels": levels,
    }


def needs_retrain(status: dict[str, Any]) -> bool:
    return any(v["state"] in ("DEGRADED", "INVALID") for v in status["levels"].values())


_LEVEL_TITLES = {
    "function": "Function archetypes",
    "file": "File archetypes",
    "composition_file": "Composition (file)",
    "composition_repo": "Composition (repo)",
}


def summary_lines(status: dict[str, Any]) -> list[str]:
    """One human-readable line per level, for reports. Pure function of status."""
    out = []
    issue = status.get("retrain_issue")
    for lvl in LEVELS:
        v = status["levels"][lvl]
        bits = [f"**{v['state']}**"]
        if v["agreement"] is not None:
            bits.append(f"{v['agreement']:.1%} agreement with trained state")
        if v["withheld"]:
            bits.append("labels withheld")
        line = f"{_LEVEL_TITLES[lvl]}: " + ", ".join(bits)
        if v["reasons"]:
            line += " -- " + "; ".join(v["reasons"])
        if v["state"] in ("DEGRADED", "INVALID") and issue:
            line += f" (retrain tracked in #{issue})"
        out.append(line)
    return out


def trained_line(status: dict[str, Any]) -> str:
    t = status.get("trained") or {}
    if not t:
        return "no archetype validation record shipped (#4100)"
    return (
        f"trained against engine {t.get('engine_version', '?')} ({t.get('engine_commit', '?')}, "
        f"{t.get('trained_at', '?')}); last measured at engine "
        f"{(status.get('measured') or {}).get('engine_commit', 'never')} on "
        f"{(status.get('measured') or {}).get('corpus', '?')}"
    )
