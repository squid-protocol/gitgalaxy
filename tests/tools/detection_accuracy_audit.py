#!/usr/bin/env python3
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
Language-Detection Accuracy Audit (#3117)

Baseline-gated regression check for the LanguageDetector's classification
accuracy over the pinned `language-crucible` corpus. Same shape as
`tests/tools/tree_sitter_accuracy_audit.py` (which measures extraction
accuracy) and the same reason: CI enforces "no accuracy regression" without
demanding perfection first.

WHY THIS EXISTS
    The engine measured extraction accuracy (tree-sitter audits) and
    cross-language measurement consistency (keyword-rosetta), but nothing
    measured detection *correctness*. The golden crucible pins diffs, so a
    classification could be stably, permanently wrong with every gate green.
    Two real defects lived in that blind spot until someone read one file by
    hand: gitgalaxy#3110 (an EQU-only HLASM copybook classified `assembly` via
    ecosystem gravity) and gitgalaxy#3116 (canonical `tclsh`/`ts-node`
    shebangs forced to Tier 5 `undeterminable` with an "Identity Masking"
    flag). Both are exactly what this harness makes visible.

!! READ THIS BEFORE QUOTING A NUMBER FROM IT !!
    The auto-labelled majority of this corpus is labelled BY EXTENSION, and
    extension is also the detector's primary signal -- so on that subset the
    oracle and the system under test share an input, and a high score there is
    partly tautological. What it still measures, and measures well:
      * every case where detection OVERRIDES the extension -- collision
        resolution, ecosystem gravity, the lexical scan, and Tier 5 refusals.
        Both #3110 and #3116 are in this class.
      * the EXPLICIT subset (files on contested extensions, hand-labelled in
        `_EXPLICIT_LABELS` below), which is genuinely independent ground truth
        and is scored and reported separately for that reason.
      * regressions: a change that makes detection disagree where it used to
        agree moves the number, whatever the oracle's provenance.
    Report the explicit-subset accuracy when the claim needs to be defensible
    (e.g. gitgalaxy#3119's Claim 11). Report overall accuracy as coverage, not
    as a benchmark win.

USAGE
    python tests/tools/detection_accuracy_audit.py
        Full report: per-language precision/recall, confusion pairs, tier
        distribution, refusal and conflict counts.
    python tests/tools/detection_accuracy_audit.py --ci
        Terse baseline-gated regression check (what CI runs). Exits 1 on any
        regression against tests/detection_accuracy_baseline.json.
    python tests/tools/detection_accuracy_audit.py --regenerate
        Accept the current numbers as the new baseline.
    python tests/tools/detection_accuracy_audit.py --errors
        List every misclassified file, grouped by (expected -> got). This is
        the triage view -- new detection bugs show up here first.

CORPUS
    Read from $LANGUAGE_CRUCIBLE_PATH, or a `language-crucible` sibling of the
    repo root. The corpus is a separate sha-pinned checkout ON PURPOSE (its
    files are third-party, under their own licences); only the LABELS live
    here, because a label is an assertion this engine's authors make about the
    corpus and has to version with the engine's expectations.
"""

import argparse
import json
import os
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Any, Optional

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gitgalaxy.standards.gitgalaxy_config import EXACT_FILE_MATCH  # noqa: E402
from gitgalaxy.standards.language_lens import LanguageDetector  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG  # noqa: E402

BASELINE_PATH = _REPO_ROOT / "tests" / "detection_accuracy_baseline.json"

# How much a per-language rate may fall before --ci calls it a regression.
# Detection is deterministic, so this is a rounding allowance, not noise.
_RATE_TOLERANCE = 0.005

# ==============================================================================
# EXPLICIT LABELS -- the genuinely independent ground truth
# ==============================================================================
# Files on a COLLISION_FREQUENCIES extension cannot be labelled by extension
# (that is what "contested" means), so they are labelled here by corpus
# location: `(extension, "<group>/<repo>")` as it appears under
# `language-crucible/data/`. 49 entries cover all 502 contested files in the
# pinned corpus. Each is a claim that is checkable by looking at that repo.
#
# A value of None means DELIBERATELY UNSCORED -- the registry has no profile
# that is the defensible answer, so asserting one would manufacture ground
# truth. Those files are excluded from every score and counted separately.
_EXPLICIT_LABELS: dict[tuple[str, str], Optional[str]] = {
    # --- .py: python unless the project is a microcontroller runtime ---
    (".py", "python/fastapi"): "python",
    (".py", "python/numpy"): "python",
    (".py", "python/wtfpython"): "python",
    (".py", "python/twisted"): "python",
    (".py", "python/airflow"): "python",
    (".py", "python/cython"): "python",
    (".py", "cpp/NVDA"): "python",  # C++ product, python add-on layer
    (".py", "fortran/wrf"): "python",  # build/support scripts beside Fortran
    (".py", "xml/odoo"): "python",
    (".py", "embedded_python/meow_turtle"): "embedded_python",  # real MicroPython
    # --- .asm: the crucible's assembly corpus is entirely x86/6502/ARM.
    # No z/Architecture source is present, which is WHY #3110's EQU-copybook
    # misclassification was invisible here -- see the note in that issue.
    (".asm", "assembly/os_tutorial_x86"): "assembly",
    (".asm", "assembly/nasm_testsuite"): "assembly",
    (".asm", "assembly/cpm65_6502"): "assembly",
    (".asm", "assembly/raspberrypi_baremetal"): "assembly",
    (".asm", "assembly/bootos"): "assembly",
    (".inc", "assembly/cosmopolitan"): "assembly",
    # --- .sql: sqlite is this registry's generic SQL dialect; db2_sql is the
    # mainframe one. No postgres/mysql profile exists, so those two repos are
    # unscored rather than forced into sqlite.
    (".sql", "sqlite/mediawiki_sqlite_alterpatches"): "sqlite",
    (".sql", "sqlite/mediawiki_sqlite_tables"): "sqlite",
    (".sql", "sqlite/prisma_typed_sql"): "sqlite",
    (".sql", "sqlite/prisma_sqlite_migrations"): "sqlite",
    (".sql", "sqlite/sqlite_cli_scripts"): "sqlite",
    (".sql", "sqlite/yii2_sqlite_schema"): "sqlite",
    (".sql", "sqlite/sqitch_sqlite_engine"): "sqlite",
    (".sql", "sqlite/flask_tutorial_sqlite"): "sqlite",
    (".sql", "sqlite/dancer2_sqlite"): "sqlite",
    (".sql", "sql/sqlite"): "sqlite",
    (".sql", "sql/postgresql"): None,  # no postgres profile in the registry
    (".sql", "sql/mysql"): None,  # no mysql profile in the registry
    # --- .c / .h: C unless the project is C++ or Objective-C ---
    (".c", "c/micropython"): "c",
    (".c", "c/cpython"): "c",
    (".c", "c/doom"): "c",
    (".c", "c/sqlite"): "c",
    (".c", "cobol/gnucobol_internals"): "c",  # generated/runtime C beside COBOL
    (".c", "scheme/racket"): "c",  # Racket's C runtime
    (".c", "tcl/sqlite"): "c",
    (".c", "python/numpy"): "c",
    (".c", "assembly/cosmopolitan"): "c",
    (".c", "objective-c/worldwideweb"): "c",  # plain C sources in the ObjC tree
    (".h", "c/micropython"): "c",
    (".h", "c/doom"): "c",
    (".h", "cpp/godot"): "cpp",
    (".h", "cpp/powertoys"): "cpp",
    (".h", "objective-c/worldwideweb"): "objective-c",
    # --- .m: the objective-c-vs-matlab collision, both directions ---
    (".m", "matlab/eeglab"): "matlab",
    (".m", "objective-c/worldwideweb"): "objective-c",
    # --- .y: parser grammars ---
    (".y", "yacc/freebsd"): "yacc",
    (".y", "cobol/gnucobol_internals"): "yacc",
    (".y", "c/sqlite"): None,  # sqlite's parse.y is a Lemon grammar, not yacc
    # --- .cmd: the batch-vs-rexx collision (#2504) ---
    (".cmd", "batch/powertoys"): "batch",
}


def _corpus_root() -> pathlib.Path:
    env = os.environ.get("LANGUAGE_CRUCIBLE_PATH")
    candidates = [pathlib.Path(env)] if env else []
    candidates.append(_REPO_ROOT.parent / "language-crucible")
    for base in candidates:
        if (base / "data").is_dir():
            return base / "data"
    raise SystemExit(
        "language-crucible corpus not found. Set LANGUAGE_CRUCIBLE_PATH to the checkout root "
        "(the directory containing `data/`)."
    )


# Extensions that are TEMPLATE wrappers, not languages: the real language is
# whatever sits inside (`Makefile.pre.in` is Makefile syntax, `langref.html.in`
# is HTML), so a single-claimant label from the extension alone would be wrong.
# Found by this harness's own first run, where both files were scored against a
# bogus `m4` label while the detector answered correctly -- labelling-strategy
# error on our side, not a detection defect. Excluded from auto-labelling
# rather than hand-labelled, since the inner extension is the detector's own
# SAFE_WRAPPERS concept and reusing it here would add circularity.
_TEMPLATE_EXTENSIONS = {".in", ".template", ".tmpl", ".dist"}


def _single_claimant_extensions() -> dict[str, str]:
    """Extensions claimed by exactly one language and not registered as contested."""
    claims: dict[str, set[str]] = defaultdict(set)
    for lang_id, data in LANGUAGE_DEFINITIONS.items():
        for ext in data.get("extensions", []):
            claims[ext.lower()].add(lang_id)
    contested = set(LENS_CONFIG["COLLISION_FREQUENCIES"])
    return {
        ext: next(iter(langs))
        for ext, langs in claims.items()
        if len(langs) == 1 and ext not in contested and ext not in _TEMPLATE_EXTENSIONS
    }


def _label_for(path: pathlib.Path, root: pathlib.Path, by_ext: dict[str, str]) -> tuple[Optional[str], str]:
    """(expected_language, label_source). expected None => unscored."""
    ext = path.suffix.lower()
    if path.name in EXACT_FILE_MATCH:
        return EXACT_FILE_MATCH[path.name], "exact_filename"
    if ext in set(LENS_CONFIG["COLLISION_FREQUENCIES"]):
        rel = path.relative_to(root).parts
        key = (ext, "/".join(rel[:2])) if len(rel) > 1 else (ext, rel[0] if rel else "")
        if key in _EXPLICIT_LABELS:
            return _EXPLICIT_LABELS[key], "explicit"
        return None, "contested_unlabelled"
    if ext in by_ext:
        return by_ext[ext], "extension"
    return None, "unknown_extension"


def measure() -> dict[str, Any]:
    """Classify every corpus file and score against its label."""
    root = _corpus_root()
    by_ext = _single_claimant_extensions()
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})

    # The detector accepts a per-directory extension tally for its ecosystem
    # gravity tier; build it the way the real pipeline does so gravity-driven
    # verdicts (the #3110 class) are exercised rather than bypassed.
    ext_tally: dict[pathlib.Path, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    files: list[pathlib.Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        files.append(path)
        ext_tally[path.parent][path.name.lower()] += 1
        ext_tally[path.parent][path.suffix.lower()] += 1

    per_lang: dict[str, dict[str, int]] = defaultdict(lambda: {"support": 0, "correct": 0, "predicted": 0})
    confusion: Counter = Counter()
    tiers: Counter = Counter()
    sources: Counter = Counter()
    errors: list[dict[str, str]] = []
    subset_totals: dict[str, dict[str, int]] = {
        "explicit": {"scored": 0, "correct": 0},
        "auto": {"scored": 0, "correct": 0},
    }
    refusals = conflicts = 0

    for path in files:
        expected, source = _label_for(path, root, by_ext)
        sources[source] += 1
        if expected is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            sources["unreadable"] += 1
            continue

        result = detector.inspect(str(path), content, ext_tally=ext_tally[path.parent])
        got = result["lang_id"]
        tier = result["lock_tier"]
        tiers[str(tier)] += 1
        if tier == 5:
            conflicts += 1
        if got in ("undeterminable", "unknown"):
            refusals += 1

        bucket = "explicit" if source == "explicit" else "auto"
        subset_totals[bucket]["scored"] += 1
        per_lang[expected]["support"] += 1
        per_lang[got]["predicted"] += 1
        if got == expected:
            per_lang[expected]["correct"] += 1
            subset_totals[bucket]["correct"] += 1
        else:
            confusion[f"{expected} -> {got}"] += 1
            errors.append(
                {
                    "path": str(path.relative_to(root)),
                    "expected": expected,
                    "got": got,
                    "tier": str(tier),
                    "proof": result["source_proof"],
                    "label_source": source,
                }
            )

    scored = sum(b["scored"] for b in subset_totals.values())
    correct = sum(b["correct"] for b in subset_totals.values())
    languages = {
        lang: {
            "support": v["support"],
            "predicted": v["predicted"],
            "correct": v["correct"],
            "recall": round(v["correct"] / v["support"], 4) if v["support"] else None,
            "precision": round(v["correct"] / v["predicted"], 4) if v["predicted"] else None,
        }
        for lang, v in sorted(per_lang.items())
    }
    return {
        "corpus_files": len(files),
        "scored": scored,
        "correct": correct,
        "accuracy": round(correct / scored, 4) if scored else None,
        "explicit_scored": subset_totals["explicit"]["scored"],
        "explicit_correct": subset_totals["explicit"]["correct"],
        "explicit_accuracy": (
            round(subset_totals["explicit"]["correct"] / subset_totals["explicit"]["scored"], 4)
            if subset_totals["explicit"]["scored"]
            else None
        ),
        "auto_scored": subset_totals["auto"]["scored"],
        "auto_accuracy": (
            round(subset_totals["auto"]["correct"] / subset_totals["auto"]["scored"], 4)
            if subset_totals["auto"]["scored"]
            else None
        ),
        "refusals": refusals,
        "tier_5_conflicts": conflicts,
        "label_sources": dict(sorted(sources.items())),
        "tier_distribution": dict(sorted(tiers.items())),
        "languages": languages,
        "confusion": dict(confusion.most_common()),
        "_errors": errors,
    }


def _load_baseline() -> Optional[dict[str, Any]]:
    if not BASELINE_PATH.exists():
        return None
    return json.loads(BASELINE_PATH.read_text())


def _write_baseline(measured: dict[str, Any]) -> None:
    payload = {k: v for k, v in measured.items() if not k.startswith("_")}
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _report(m: dict[str, Any]) -> None:
    print("=" * 74)
    print(" LANGUAGE-DETECTION ACCURACY AUDIT (#3117)")
    print("=" * 74)
    print(f"  corpus files          : {m['corpus_files']}")
    print(f"  scored                : {m['scored']}")
    print(f"  overall accuracy      : {m['accuracy']}   (partly extension-circular, see docstring)")
    print(f"  EXPLICIT subset       : {m['explicit_correct']}/{m['explicit_scored']} = {m['explicit_accuracy']}")
    print("                          ^ independent ground truth: contested extensions, hand-labelled")
    print(f"  auto subset           : {m['auto_scored']} files, accuracy {m['auto_accuracy']}")
    print(f"  refusals              : {m['refusals']}")
    print(f"  Tier 5 conflicts      : {m['tier_5_conflicts']}   (should be 0 on a clean corpus)")
    print(f"\n  label sources         : {m['label_sources']}")
    print(f"  tier distribution     : {m['tier_distribution']}")

    print("\n  per-language (support / recall / precision):")
    for lang, v in m["languages"].items():
        if not v["support"]:
            continue
        print(f"    {lang:<18} n={v['support']:<5} recall={v['recall']:<8} precision={v['precision']}")

    if m["confusion"]:
        print("\n  confusion pairs (expected -> got):")
        for pair, n in list(m["confusion"].items())[:25]:
            print(f"    {n:>5}  {pair}")
    else:
        print("\n  confusion pairs: none")


def _compare(measured: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    regressions = []
    for key in ("accuracy", "explicit_accuracy", "auto_accuracy"):
        new, old = measured.get(key), baseline.get(key)
        if new is not None and old is not None and new < old - _RATE_TOLERANCE:
            regressions.append(f"{key} fell {old} -> {new}")
    for key, label in (("tier_5_conflicts", "Tier 5 conflicts"), ("refusals", "refusals")):
        new, old = measured.get(key, 0), baseline.get(key, 0)
        if new > old:
            regressions.append(f"{label} rose {old} -> {new}")
    base_langs = baseline.get("languages", {})
    for lang, v in measured.get("languages", {}).items():
        old = base_langs.get(lang)
        if not old or not v["support"]:
            continue
        for rate in ("recall", "precision"):
            if v[rate] is not None and old.get(rate) is not None and v[rate] < old[rate] - _RATE_TOLERANCE:
                regressions.append(f"{lang} {rate} fell {old[rate]} -> {v[rate]}")
    return regressions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="Terse baseline-gated regression check (what CI runs).")
    group.add_argument("--regenerate", action="store_true", help="Accept current numbers as the new baseline.")
    group.add_argument("--errors", action="store_true", help="List every misclassified file for triage.")
    args = parser.parse_args()

    measured = measure()

    if args.regenerate:
        _write_baseline(measured)
        print(f"Detection Accuracy Audit: baseline written to {BASELINE_PATH.relative_to(_REPO_ROOT)}")
        print(
            f"  overall {measured['accuracy']} | explicit {measured['explicit_accuracy']} "
            f"| Tier 5 conflicts {measured['tier_5_conflicts']}"
        )
        return 0

    if args.errors:
        if not measured["_errors"]:
            print("Detection Accuracy Audit: no misclassifications.")
            return 0
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for e in measured["_errors"]:
            grouped[f"{e['expected']} -> {e['got']}"].append(e)
        for pair, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            print(f"\n{pair}  ({len(items)} file{'s' if len(items) > 1 else ''})")
            for e in items[:20]:
                print(f"    [{e['label_source']}] tier {e['tier']:<4} {e['path']}")
                print(f"        proof: {e['proof']}")
            if len(items) > 20:
                print(f"    ... and {len(items) - 20} more")
        return 1

    baseline = _load_baseline()
    if args.ci:
        if baseline is None:
            print("Detection Accuracy Audit: no committed baseline; run --regenerate first.")
            return 1
        regressions = _compare(measured, baseline)
        if regressions:
            print(f"Detection Accuracy Audit: {len(regressions)} REGRESSION(S):")
            for r in regressions:
                print(f"  - {r}")
            print("\nRun without --ci for the full report, or --errors to list the offending files.")
            return 1
        print(
            f"Detection Accuracy Audit: no regression "
            f"(overall {measured['accuracy']}, explicit {measured['explicit_accuracy']}, "
            f"{measured['tier_5_conflicts']} Tier 5 conflicts)."
        )
        return 0

    _report(measured)
    if baseline is not None:
        regressions = _compare(measured, baseline)
        print(
            f"\n  vs committed baseline: {'REGRESSIONS: ' + '; '.join(regressions) if regressions else 'no regression'}"
        )
    else:
        print("\n  no committed baseline yet -- run --regenerate to create one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
