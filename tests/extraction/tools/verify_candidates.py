#!/usr/bin/env python3
"""
Reusable "verify a candidate test case against the real compiled regex
before adding it" harness for extraction-hardening work (epic #813).

Why this exists: the methodology doc's own non-negotiable step is
"empirically verify every candidate case against the real compiled regex
before adding it to the test file" -- a wrong guess about what a payload
matches is worse than no test at all (it either bakes in a bug as
"expected" or fails for the wrong reason). Every language pass so far
(typescript/#815, the 8-language function-extraction scouting pass before
the epic existed) rewrote this exact same checker function from scratch in
a scratchpad script. This is that script, made permanent and importable so
it's written once, not 42+ more times.

USAGE (as a library, from a scratch script or a REPL)
    import sys; sys.path.insert(0, "tests/extraction/tools")
    from verify_candidates import check_case, check_many, check_redos_scaling

    check_case("go", "func_start", "func Foo[T any](x T) T {", True, "Foo", "generic func")

    check_many("go", [
        ("func_start", "func Foo[T any](x T) T {", True, "Foo", "generic func"),
        ("func_start", "Foo(a, b);", False, None, "bare call (invalid)"),
    ])

    check_redos_scaling("go", "func_start", lambda n: "func Foo(" + "a" * n)

USAGE (CLI, for a single ad-hoc check)
    python tests/extraction/tools/verify_candidates.py --lang go --rule func_start \\
        --payload 'func Foo[T any](x T) T {' --expect-match --expect-name Foo

A case that reports OK here is guaranteed to pass the equivalent
tests/extraction/_extraction_harness.py assertion too (the checks mirror
each other's logic exactly) -- this script exists purely so you can iterate
on candidate cases fast, before committing them to a real per-language test
file under tests/extraction/languages/.
"""

import argparse
import sys
import time

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def check_case(lang: str, rule_key: str, payload: str, expect_match: bool, expect_name=None, label: str = ""):
    """
    Returns True/False (or None if the rule is None for this language) and
    prints a formatted PASS/FAIL/SKIP line. See module docstring for usage.
    """
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    pattern = rules.get(rule_key)
    if pattern is None:
        print(f"[SKIP] {lang}.{rule_key} is None for this language")
        return None

    m = pattern.search(payload)
    matched = m is not None
    ok = matched == expect_match
    name_ok = True
    got = None

    if matched and expect_match and expect_name:
        if pattern.groups > 0:
            groups = [g for g in m.groups() if g is not None]
            got = groups
            name_ok = any(expect_name in g for g in groups)
        else:
            got = m.group(0)
            name_ok = expect_name in m.group(0)

    status = "OK" if (ok and name_ok) else "FAIL"
    print(f"[{status}] {lang}.{rule_key:20s} {label:50s} matched={matched!s:5s} got={got!r}")
    if status == "FAIL":
        print(f"       payload={payload!r}")
    return status == "OK"


def check_many(lang: str, cases) -> bool:
    """
    cases: iterable of (rule_key, payload, expect_match, expect_name, label)
    tuples (label may be omitted -- defaults to "").
    Prints a summary line and returns True only if every case passed.
    """
    results = []
    for case in cases:
        if len(case) == 4:
            case = (*case, "")
        results.append(check_case(lang, *case))

    real_results = [r for r in results if r is not None]
    ok_count = sum(real_results)
    print(f"\n{ok_count}/{len(real_results)} candidate cases behaved as expected")
    return ok_count == len(real_results)


def check_redos_scaling(lang: str, rule_key: str, payload_fn, sizes=(2000, 4000, 8000, 16000, 32000)) -> bool:
    """
    Times `pattern.search(payload_fn(n))` at each size in `sizes` and prints
    the durations plus the ratio between consecutive sizes. A ratio
    consistently near ~2x per doubling is linear (safe); a ratio climbing
    toward ~4x is the O(n^2) catastrophic-backtracking signature and should
    be investigated before the pattern is trusted. This is a print-and-judge
    helper, not a pass/fail assertion -- scaling verdicts need a human/LLM
    read of the actual numbers (a single ratio threshold is exactly the kind
    of flaky absolute-style check this codebase has repeatedly moved away
    from -- see tests/core_engine/test_language_standards_strict.py's own
    _best_of_timing() for the same judgment call made permanent as a real
    test assertion once a pattern is finalized).
    """
    pattern = LANGUAGE_DEFINITIONS[lang]["rules"].get(rule_key)
    if pattern is None:
        print(f"[SKIP] {lang}.{rule_key} is None for this language")
        return False

    durations = []
    for n in sizes:
        payload = payload_fn(n)
        start = time.perf_counter()
        pattern.search(payload)
        dur = time.perf_counter() - start
        durations.append(dur)
        print(f"  n={n:>7} dur={dur:.4f}s")

    print("  ratios:", ", ".join(f"{b / a:.2f}x" if a > 0 else "n/a" for a, b in zip(durations, durations[1:])))
    return True


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", required=True)
    parser.add_argument(
        "--rule", required=True, choices=["func_start", "args", "class_start", "_dependency_capture"]
    )
    parser.add_argument("--payload", required=True)
    parser.add_argument("--expect-match", action="store_true")
    parser.add_argument("--expect-name", default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    result = check_case(args.lang, args.rule, args.payload, args.expect_match, args.expect_name, args.label)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(_cli())
