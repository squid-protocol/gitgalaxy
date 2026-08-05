#!/usr/bin/env python3
"""
Rerunnable audit of tests/extraction/languages/test_<lang>_strict.py against
gitgalaxy/standards/language_standards.py's LANGUAGE_DEFINITIONS -- the
coverage-gap detector behind epic #1069 (the #518-lineage follow-on that
applies epic #813's harder rigor standard to the non-extraction-pillar
structural-signature suite).

Why this exists: the audit that founded #1069 was a one-off scratch script.
That's the same mistake epic #813 avoided by checking in
tests/extraction/tools/verify_candidates.py -- an ad hoc audit script dies
in a session's scratchpad and has to be reconstructed from scratch the next
time someone wants to know "how much of the gap is left." This is that
script, made permanent.

What it checks per language, cross-referenced against LANGUAGE_DEFINITIONS'
actual non-None rule keys (excluding func_start/args/class_start/
_dependency_capture/_named_token_capture, which are epic #813's concern via
test_<lang>.py, not this file's):
  - which signature keys have literally zero case coverage in `_SIMPLE_CASES`
  - how many cases have `None` in the negative/ghost-prevention slot
  - how many `assert_redos_immune`/`_best_of_timing` calls the file makes

USAGE
    python tests/extraction/tools/audit_strict_coverage.py                # full table, all languages
    python tests/extraction/tools/audit_strict_coverage.py --lang python  # one language, human-readable
    python tests/extraction/tools/audit_strict_coverage.py --lang python --json   # machine-readable

The --json form is meant for a cheap/mechanical "scout" pass (see
tests/extraction/how_to_harden_strict_signatures.md) -- it hands a case-
writing agent the exact gap list for one language without that agent
needing to read language_standards.py or the existing _strict.py file cold.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LANG_DIR = REPO_ROOT / "tests" / "extraction" / "languages"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(LANG_DIR))

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

# filename-stem -> LANGUAGE_DEFINITIONS key, for the handful that don't match
# a straight underscore-stripped transform (e.g. the dict key has a hyphen).
LANG_KEY_OVERRIDES = {
    "objectivec": "objective-c",
}

# These are the four extraction-pillar rules (epic #813's concern, tested in
# test_<lang>.py) plus python/typescript's dependency-precision extension --
# their absence from a _strict.py file's cases is by design, not a gap.
EXTRACTION_PILLAR_KEYS = {"func_start", "args", "class_start", "_dependency_capture", "_named_token_capture"}


def _lang_key_for(stem: str) -> str:
    lang = stem[len("test_") : -len("_strict")]
    return LANG_KEY_OVERRIDES.get(lang, lang)


def _load_simple_cases(path: Path):
    """Import the test module for real and grab its `..._SIMPLE_CASES` list.

    Deliberately a real import (not ast.literal_eval) -- some files build
    entries with non-literal expressions (e.g. dockerfile's
    `"FROM alpine@sha256:" + "a" * 64`), which a literal-only parse can't
    evaluate.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, val in vars(mod).items():
        if name.endswith("_SIMPLE_CASES") and isinstance(val, list):
            return val
    return None


def audit_language(path: Path) -> dict:
    lang = _lang_key_for(path.stem)
    src = path.read_text()

    cases = _load_simple_cases(path)
    signatures_covered = {c[0] for c in cases if len(c) >= 1} if cases is not None else set()
    no_negative = [c[0] for c in cases if len(c) >= 3 and c[2] is None] if cases is not None else []

    rules = LANGUAGE_DEFINITIONS.get(lang, {}).get("rules", {})
    non_none_keys = {k for k, v in rules.items() if v is not None}
    missing_entirely = sorted(non_none_keys - signatures_covered - EXTRACTION_PILLAR_KEYS)

    return {
        "lang": lang,
        "file": str(path.relative_to(REPO_ROOT)),
        "n_signatures_applicable": len(non_none_keys - EXTRACTION_PILLAR_KEYS),
        "n_cases": len(cases) if cases is not None else None,
        "missing_case_entirely": missing_entirely,
        "no_negative_case": sorted(no_negative),
        "redos_immune_calls": len(re.findall(r"\bassert_redos_immune\(", src)),
        "best_of_timing_calls": len(re.findall(r"\b_best_of_timing\(", src)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", default=None, help="audit a single language (e.g. python); default: all")
    parser.add_argument("--json", action="store_true", help="machine-readable output for the given --lang")
    args = parser.parse_args()

    paths = sorted(LANG_DIR.glob("test_*_strict.py"))
    if args.lang:
        paths = [p for p in paths if _lang_key_for(p.stem) == args.lang]
        if not paths:
            print(f"no _strict.py file found for lang={args.lang!r}", file=sys.stderr)
            return 1

    results = [audit_language(p) for p in paths]

    if args.json:
        print(json.dumps(results[0] if args.lang else results, indent=2))
        return 0

    header = f"{'lang':<16}{'sigs':>6}{'cases':>7}{'missing':>9}{'no_neg':>8}{'redos':>7}{'scaled':>8}"
    print(header)
    zero_redos, has_missing, thin_negative = [], [], []
    for r in results:
        n_cases = r["n_cases"] if r["n_cases"] is not None else -1
        print(
            f"{r['lang']:<16}{r['n_signatures_applicable']:>6}{n_cases:>7}"
            f"{len(r['missing_case_entirely']):>9}{len(r['no_negative_case']):>8}"
            f"{r['redos_immune_calls']:>7}{r['best_of_timing_calls']:>8}"
        )
        if r["redos_immune_calls"] == 0 and r["best_of_timing_calls"] == 0:
            zero_redos.append(r["lang"])
        if r["missing_case_entirely"]:
            has_missing.append((r["lang"], r["missing_case_entirely"]))
        if r["n_cases"] and len(r["no_negative_case"]) / r["n_cases"] > 0.7:
            thin_negative.append((r["lang"], len(r["no_negative_case"]), r["n_cases"]))

    if not args.lang:
        print(f"\n=== Zero per-language ReDoS assertions ({len(zero_redos)}) ===")
        for lang in zero_redos:
            print(f" - {lang}")

        print(f"\n=== Signature keys missing case coverage entirely ({len(has_missing)} languages) ===")
        for lang, missing in has_missing:
            print(f" - {lang}: {missing}")

        print(f"\n=== >70% of cases have no negative/ghost-prevention check ({len(thin_negative)} languages) ===")
        for lang, no_neg, total in thin_negative:
            print(f" - {lang}: {no_neg}/{total}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
