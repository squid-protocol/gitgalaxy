#!/usr/bin/env python3
"""
The registration-surface audit for adding (or auditing) a language (#3093).

A language is not just its `languages/<lang>.py` definition: it touches the
registry, the lens's collision table, the detector's dispatch and allowlists,
analysis_lens's strictness/ecosystem tables, a pinned cross-language contract
test, the status-doc index and the keyword-rosetta control corpus. The #2511
(db2_sql) landing hit two of these as CI round-trips (the strictness row and
the POSITIONAL_LANGUAGES pin) because nothing enumerated the full surface in
one place. This tool does, in one command, in under five seconds:

    python tests/tools/language_addition_audit.py --lang <lang>   # new-language mode
    python tests/tools/language_addition_audit.py                 # global invariants only

Two kinds of finding:

- HARD failures (exit 1) are cross-language invariants that must always hold;
  `tests/core_engine/test_language_addition_invariants.py` enforces the same
  functions in CI, so a hard failure here IS a future red CI run caught early:
    1. every extension claimed by two registry languages is declared in
       COLLISION_FREQUENCIES (else _calibrate_lookup_maps' registration-order
       overwrite silently hands it to whichever profile loads last -- the
       #2511 .sql/.ddl/.dml lesson);
    2. every registry language the detector slices in Mode E declares
       `invocation_model: "positional"` (#2866 corollary 4: Mode E's units are
       statement buckets, and no syntax reaches a bucket by its extracted
       name -- proven twice now, sqlite and db2_sql, the second time as a
       correction commit the rosetta census forced);
    3. the set of positional declarations matches the literal pinned in
       test_unreferenced_by_name_contract_2806.py (widening the family must
       stay a deliberate, commented edit -- this check makes the tripwire
       fire locally instead of in CI);
    4. every registry language resolves to a LANGUAGE_STRICTNESS row;
    5. every declared invocation_model is a member of the closed set.

- Soft WARNINGS (--lang mode only; never exit-code-relevant) are the
  judgment-call surfaces a new language usually wants but existing languages
  legitimately vary on: ecosystem membership, the class_start named-extraction
  allowlist (requires its own verification pass -- see the
  harden-class-start-extraction skill -- so absence is a prompt, not a bug),
  the docs/language_status index row, the keyword-rosetta data/<lang> folder,
  duplicate extension spellings, and the fidelity-table re-pin drift.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core import detector  # noqa: E402
from gitgalaxy.core.detector import (  # noqa: E402
    INVOCATION_BY_NAME,
    INVOCATION_MODELS,
    INVOCATION_POSITIONAL,
    ScopeParsingRegistry,
)
from gitgalaxy.standards.analysis_lens import (  # noqa: E402
    LANGUAGE_SECURITY_PROFILES,
    LANGUAGE_STRICTNESS,
    resolve_language_family,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG  # noqa: E402

_CONTRACT_TEST = REPO_ROOT / "tests" / "core_engine" / "test_unreferenced_by_name_contract_2806.py"


def pinned_positional_family() -> set[str]:
    """The POSITIONAL_LANGUAGES literal, read from the contract test's own AST.

    Parsed rather than imported so this tool never depends on pytest being
    importable, and so a syntax error in the test file fails loudly here too.
    """
    tree = ast.parse(_CONTRACT_TEST.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "POSITIONAL_LANGUAGES":
                    return set(ast.literal_eval(node.value))
    raise AssertionError(f"POSITIONAL_LANGUAGES literal not found in {_CONTRACT_TEST}")


def _declared_model(lang: str) -> str:
    return LANGUAGE_DEFINITIONS[lang].get("invocation_model", INVOCATION_BY_NAME)


# ------------------------------------------------------------------------------
# HARD invariants (also enforced by tests/core_engine/test_language_addition_invariants.py)
# ------------------------------------------------------------------------------


def check_contested_extensions_declared() -> list[str]:
    """Every extension claimed by >=2 languages must be in COLLISION_FREQUENCIES."""
    claims: dict[str, set[str]] = {}
    for lang, d in LANGUAGE_DEFINITIONS.items():
        for ext in {e.lower() for e in d.get("extensions", [])}:
            claims.setdefault(ext, set()).add(lang)
    cf = LENS_CONFIG["COLLISION_FREQUENCIES"]
    return [
        f"extension {ext!r} is claimed by {sorted(langs)} but is not in COLLISION_FREQUENCIES "
        f"(_lens_config.py) -- Tier 1 will hand it to whichever profile registered last"
        for ext, langs in sorted(claims.items())
        if len(langs) > 1 and ext not in cf
    ]


def check_mode_e_languages_are_positional() -> list[str]:
    """Mode E slices statement buckets; a bucket is never reached by its name (#2866 c4)."""
    return [
        f"{lang!r} slices through Mode E (terminator cleaving) but declares "
        f"invocation_model={_declared_model(lang)!r}; Mode E units are statement buckets, "
        f'so it must declare "positional" (#2866 corollary 4 -- the sqlite/db2_sql rule)'
        for lang in LANGUAGE_DEFINITIONS
        if ScopeParsingRegistry.get_mode(lang) == "mode_e" and _declared_model(lang) != INVOCATION_POSITIONAL
    ]


def check_positional_family_is_pinned() -> list[str]:
    declared = {lang for lang in LANGUAGE_DEFINITIONS if _declared_model(lang) == INVOCATION_POSITIONAL}
    pinned = pinned_positional_family()
    problems = []
    if declared - pinned:
        problems.append(
            f"{sorted(declared - pinned)} declare positional but are missing from "
            f"POSITIONAL_LANGUAGES in {_CONTRACT_TEST.name} -- add them there WITH the "
            f"corollary-4 justification comment (the family is pinned on purpose)"
        )
    if pinned - declared:
        problems.append(
            f"{sorted(pinned - declared)} are pinned in POSITIONAL_LANGUAGES but do not "
            f"declare invocation_model positional in their registry definition"
        )
    return problems


def check_strictness_rows() -> list[str]:
    return [
        f"{lang!r} has no LANGUAGE_STRICTNESS row (analysis_lens.py) for its family "
        f"{resolve_language_family(lang)!r} -- add a (static, enforced, memory, globals) "
        f"tuple or an explicit None for data/markup formats"
        for lang in LANGUAGE_DEFINITIONS
        if resolve_language_family(lang) not in LANGUAGE_STRICTNESS
    ]


def check_invocation_models_closed_set() -> list[str]:
    return [
        f"{lang!r} declares an unknown invocation_model {_declared_model(lang)!r} "
        f"(closed set: {sorted(INVOCATION_MODELS)})"
        for lang in LANGUAGE_DEFINITIONS
        if _declared_model(lang) not in INVOCATION_MODELS
    ]


HARD_CHECKS = [
    check_contested_extensions_declared,
    check_mode_e_languages_are_positional,
    check_positional_family_is_pinned,
    check_strictness_rows,
    check_invocation_models_closed_set,
]


def hard_failures() -> list[str]:
    failures: list[str] = []
    for check in HARD_CHECKS:
        failures.extend(check())
    return failures


# ------------------------------------------------------------------------------
# SOFT warnings (per-language; existing languages legitimately vary on these)
# ------------------------------------------------------------------------------


def _rosetta_data_dir() -> Path | None:
    env = os.environ.get("KEYWORD_ROSETTA_PATH")
    candidates = (
        [Path(env)] if env else [REPO_ROOT.parent.parent / "keyword-rosetta", REPO_ROOT.parent / "keyword-rosetta"]
    )
    for c in candidates:
        if (c / "data").is_dir():
            return c / "data"
    return None


def soft_warnings(lang: str) -> list[str]:
    d = LANGUAGE_DEFINITIONS[lang]
    rules = d.get("rules") or {}
    warnings: list[str] = []

    exts = [e.lower() for e in d.get("extensions", [])]
    dupes = sorted({e for e in exts if exts.count(e) > 1})
    if dupes:
        warnings.append(f"extensions list repeats {dupes} after lowercasing -- harmless but redundant")

    if any(v is not None for v in rules.values()):
        ecosystems = LANGUAGE_SECURITY_PROFILES["ECOSYSTEMS"]
        if not any(lang in members for members in ecosystems.values()):
            warnings.append(
                "not in any LANGUAGE_SECURITY_PROFILES ECOSYSTEMS set (analysis_lens.py) -- "
                "pick the family it belongs beside (db2_sql joined 'systems' with cobol/pli)"
            )

    class_start = rules.get("class_start")
    allowlisted = detector._CLASS_START_NAMED_EXTRACTION_LANGS | detector._CLASS_EXTRACTION_OUT_OF_SCOPE_LANGS
    if class_start is not None and getattr(class_start, "groups", 0) >= 1 and lang not in allowlisted:
        warnings.append(
            "class_start captures a name but the language is not in "
            "_CLASS_START_NAMED_EXTRACTION_LANGS (detector.py) -- named classes stay empty "
            "until it is added; joining requires the harden-class-start-extraction "
            "verification pass, not just the edit"
        )

    index = REPO_ROOT / "docs" / "language_status" / "README.md"
    if index.is_file() and not re.search(rf"(?m)^\|\s*(?:\*\*\[)?{re.escape(lang)}[\]\s|(]", index.read_text()):
        warnings.append("no row in docs/language_status/README.md's index table")

    data_dir = _rosetta_data_dir()
    if data_dir is None:
        warnings.append("keyword-rosetta checkout not found (set KEYWORD_ROSETTA_PATH) -- corpus checks skipped")
    else:
        if not (data_dir / lang).is_dir():
            warnings.append(
                f"no data/{lang}/ control folder in the keyword-rosetta checkout at {data_dir.parent} "
                f"(part of a language addition, not a follow-up -- how_to_add_a_language.md's closing section; "
                f"if the folder merged recently, the checkout may just be on an old branch)"
            )
        try:
            from gitgalaxy.standards.fidelity_table import FIDELITY_PROVENANCE

            folders = sum(1 for p in data_dir.iterdir() if p.is_dir())
            pinned = int(FIDELITY_PROVENANCE.get("languages", 0))
            if folders != pinned:
                warnings.append(
                    f"fidelity_table.py FIDELITY_PROVENANCE pins {pinned} corpus languages but the "
                    f"rosetta checkout has {folders} data/ folders -- a re-pin (corpus_sha + count) is owed"
                )
        except Exception as e:  # pragma: no cover -- informational only
            warnings.append(f"fidelity provenance check skipped: {e}")

    return warnings


# ------------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--lang", help="also print the soft per-language checklist for this language")
    args = parser.parse_args(argv)

    if args.lang and args.lang not in LANGUAGE_DEFINITIONS:
        print(f"FAIL: {args.lang!r} is not in LANGUAGE_DEFINITIONS -- register it first", file=sys.stderr)
        return 1

    failures = hard_failures()
    for f in failures:
        print(f"FAIL: {f}")

    if args.lang:
        for w in soft_warnings(args.lang):
            print(f"warn ({args.lang}): {w}")

    if failures:
        print(
            f"\n{len(failures)} hard failure(s) -- these WILL fail CI "
            f"(tests/core_engine/test_language_addition_invariants.py)"
        )
        return 1
    print(f"OK: all {len(HARD_CHECKS)} registration invariants hold across {len(LANGUAGE_DEFINITIONS)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
