# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
"""Unit suite for the per-line gate (#3072).

Unlike the segment gate's one-sided contract, line_gated_finditer claims EXACT
equivalence: same matches, same spans, same groups, same order as a whole
segment finditer. Every corner case here attacks a leg of the equivalence
argument documented on line_gated_finditer itself; the corpus-wide leg lives
in tests/tools/gate_parity_audit.py.
"""

import re

import pytest

from gitgalaxy.core.rule_prefilter import (
    build_line_gate,
    derive_line_literals,
    line_gated_finditer,
    pattern_is_line_local,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _assert_parity(pattern, text):
    line_gate = build_line_gate(pattern)
    assert line_gate is not None, f"pattern refused a line gate: {pattern.pattern!r}"
    expected = [(m.span(), m.groups()) for m in pattern.finditer(text)]
    actual = [(m.span(), m.groups()) for m in line_gated_finditer(pattern, line_gate, text)]
    assert actual == expected


# ==============================================================================
# ELIGIBILITY: pattern_is_line_local
# ==============================================================================


def test_shipped_rules_are_line_local():
    for lang in ("c", "cpp", "go"):
        pattern = LANGUAGE_DEFINITIONS[lang]["rules"]["state_mutation"]
        assert pattern_is_line_local(pattern), f"{lang} state_mutation must stay line-local"


def test_whitespace_class_refuses():
    # \s matches \n: the exact construct whose reintroduction must demote the
    # rule to whole-segment (the cpp pre-narrowing shape).
    assert not pattern_is_line_local(re.compile(r"\bstd::swap\s*\(", re.M))


def test_dotall_refuses_but_plain_dot_passes():
    assert not pattern_is_line_local(re.compile(r"a.b", re.S))
    assert pattern_is_line_local(re.compile(r"a.b"))
    # Scoped (?s:...) is the same hazard through a subpattern.
    assert not pattern_is_line_local(re.compile(r"(?s:a.b)"))


def test_string_anchors_refuse_and_line_anchors_require_multiline():
    assert not pattern_is_line_local(re.compile(r"\Aint\b"))
    assert not pattern_is_line_local(re.compile(r"\bint\Z"))
    # ^/$ without re.M anchor to the string, and a window edge is not the
    # string edge -- refuse.
    assert not pattern_is_line_local(re.compile(r"^int$"))
    assert pattern_is_line_local(re.compile(r"^int$", re.M))
    assert pattern_is_line_local(re.compile(r"\bint\b"))


def test_lookaround_containing_newline_refuses():
    assert not pattern_is_line_local(re.compile(r"x(?=\n)", re.M))
    assert not pattern_is_line_local(re.compile(r"x(?!\s*\()", re.M))
    # \n-free lookarounds in both polarities are fine (the c state_mutation
    # trailing-comma guard is exactly this shape).
    assert pattern_is_line_local(re.compile(r"x=(?![=])(?![^\n(]{0,300},[ \t]*$)", re.M))


def test_negated_class_must_exclude_newline():
    assert not pattern_is_line_local(re.compile(r"[^x]+", re.M))
    assert pattern_is_line_local(re.compile(r"[^x\n]+", re.M))
    # Single-char negation parses as NOT_LITERAL: only [^\n] itself is safe.
    assert pattern_is_line_local(re.compile(r"[^\n]+", re.M))


def test_class_categories():
    assert pattern_is_line_local(re.compile(r"[\w.]+=", re.M))
    assert pattern_is_line_local(re.compile(r"[\S]+=", re.M))
    assert not pattern_is_line_local(re.compile(r"[\s;]x", re.M))
    assert not pattern_is_line_local(re.compile(r"[\W]x", re.M))


def test_backref_refuses():
    # Sound in principle (a backref to \n-free text is \n-free) but refused
    # conservatively -- update the walk if a shipped rule ever needs it.
    assert not pattern_is_line_local(re.compile(r"(=+)x\1", re.M))


# ==============================================================================
# LITERAL DERIVATION: derive_line_literals
# ==============================================================================


def test_shipped_literal_sets_are_pinned():
    # Pins _pick_most_selective's policy: these exact sets are what the bench
    # numbers were measured against. A policy change that alters them needs
    # re-measurement, which is what this failure should prompt.
    c = derive_line_literals(LANGUAGE_DEFINITIONS["c"]["rules"]["state_mutation"])
    assert c == ("=", "++", "--")
    go = derive_line_literals(LANGUAGE_DEFINITIONS["go"]["rules"]["state_mutation"])
    assert go == ("=", "++", "--", "<-", "atomic.", "delete(")
    cpp = derive_line_literals(LANGUAGE_DEFINITIONS["cpp"]["rules"]["state_mutation"])
    assert cpp is not None
    assert {"=", "++", "--", "std::"} <= set(cpp)
    assert "." not in cpp, "selectivity policy regressed to the bare-dot candidate"


def test_selectivity_beats_fewest_alternatives():
    # _pick_best would take the singleton `.`; the line policy must take the
    # rarer method names.
    pattern = re.compile(r"\.(?:push_back|emplace|erase)[ \t]*\(", re.M)
    assert derive_line_literals(pattern) == ("erase", "emplace", "push_back")


def test_ignorecase_refuses():
    assert derive_line_literals(re.compile(r"MOVE\s", re.I)) is None
    assert build_line_gate(re.compile(r"MOVE[ \t]", re.I | re.M)) is None


def test_single_char_literals_are_accepted():
    # min length 1 is the whole point of the line gate (contrast with the
    # segment gate's min_literal_len=2).
    assert derive_line_literals(re.compile(r"\w+[ \t]*=(?![=])", re.M)) == ("=",)


def test_build_line_gate_requires_both_checks():
    # Line-local but no derivable literal:
    assert build_line_gate(re.compile(r"\w+", re.M)) is None
    # Derivable literal but not line-local:
    assert build_line_gate(re.compile(r"swap\s*\(", re.M)) is None


# ==============================================================================
# EVALUATION: line_gated_finditer exact parity
# ==============================================================================

def _c_sm():
    return LANGUAGE_DEFINITIONS["c"]["rules"]["state_mutation"]


def test_parity_on_representative_c_text():
    _assert_parity(
        _c_sm(),
        "int x;\n"
        "x = 1;\n"
        "/* comment line */\n"
        "x += 2; y--;\n"
        "if (a) { b = c; }\n"
        "no mutation here\n"
        "++counter;\n",
    )


def test_parity_last_line_without_trailing_newline():
    _assert_parity(_c_sm(), "a = 1;\nb = 2")
    _assert_parity(_c_sm(), "b = 2")


def test_parity_trailing_comma_lookahead_at_window_end():
    # The `(?![^\n(]{0,300},[ \t]*$)` guard must reject/accept identically
    # when `$` sits at the window's endpos instead of before a real `\n`.
    _assert_parity(_c_sm(), "ENUM_A = 1,\n")
    _assert_parity(_c_sm(), "ENUM_A = 1,")
    _assert_parity(_c_sm(), "x = f(a, b),\n")
    _assert_parity(_c_sm(), "x = call(y), z = 2;\n")


def test_parity_equals_as_last_char_before_newline():
    _assert_parity(_c_sm(), "x =\n1;\n")
    _assert_parity(_c_sm(), "x ==\ny;\n")


def test_parity_delimiter_at_end_of_line():
    # The `(?:^|[;{}(),])` statement anchor and its operand on the same line;
    # a delimiter as the line's last char must not fabricate a cross-line
    # match.
    _assert_parity(_c_sm(), "f(a);\nb = 2;\n")
    _assert_parity(_c_sm(), "if (x) {\ny = 3;\n}\n")


def test_parity_increment_touching_line_edges():
    _assert_parity(_c_sm(), "x\n++y;\n")  # ++ at line start
    _assert_parity(_c_sm(), "x++\n;\n")  # operand and ++ same line, ; next
    _assert_parity(_c_sm(), "a--\n--b\n")


def test_parity_crlf_text():
    # \r is ordinary line content to both evaluations.
    _assert_parity(_c_sm(), "a = 1;\r\nplain\r\nb += 2;\r\n")


def test_parity_empty_and_gateless_inputs():
    _assert_parity(_c_sm(), "")
    _assert_parity(_c_sm(), "\n\n\n")
    _assert_parity(_c_sm(), "no hits at all\nnot one\n")


def test_parity_run_coalescing_and_splitting():
    # Adjacent surviving lines must form ONE window (a match may not span
    # them, but the resume discipline must still be exercised across the
    # shared boundary), and gaps must split windows.
    dense = "a = 1;\nb = 2;\nc = 3;\n"
    gapped = "a = 1;\nplain line\nb = 2;\n\nplain\nc = 3;\n"
    _assert_parity(_c_sm(), dense)
    _assert_parity(_c_sm(), gapped)


def test_parity_literal_only_inside_string():
    # The gate is a superset test: a line whose `=` sits in a string literal
    # survives the gate and the regex then treats it exactly as it always has
    # (rule 18: strings are never masked).
    _assert_parity(_c_sm(), 'printf("a = b");\n')


def test_parity_go_channel_and_delete_forms():
    pattern = LANGUAGE_DEFINITIONS["go"]["rules"]["state_mutation"]
    _assert_parity(
        pattern,
        "ch <- v\n"
        "n++\n"
        "delete(m, k)\n"
        "atomic.AddInt64(&c, 1)\n"
        "plain line\n"
        "x := 1\n",
    )


def test_parity_cpp_method_forms():
    pattern = LANGUAGE_DEFINITIONS["cpp"]["rules"]["state_mutation"]
    _assert_parity(
        pattern,
        "v.push_back(x);\n"
        "v .push_back (x);\n"
        "std::swap(a, b);\n"
        "std::mem::replace(a, b);\n"
        "note: swap( on a gate-surviving line that the rule rejects\n"
        "total += x;\n",
    )


def test_zero_width_candidate_line_cannot_loop():
    # A pathological gate regex can never yield zero-width windows (every
    # candidate line contains a literal of length >= 1), but assert the loop
    # terminates and agrees on a single-char text anyway.
    _assert_parity(_c_sm(), "=")


# ==============================================================================
# REGISTRY: every declared _line_gates entry must actually build
# ==============================================================================


def test_every_declared_line_gate_builds():
    # THE loud guard: if a rule edit breaks line-locality (say `[ \t]*` drifts
    # back to `\s*`), build_line_gate starts returning None and the engine
    # silently loses the optimization. This test turns that silence into a
    # failure naming the rule.
    declared = 0
    for lang_id, definition in sorted(LANGUAGE_DEFINITIONS.items()):
        rules = definition.get("rules", {})
        for rule_name in rules.get("_line_gates") or ():
            declared += 1
            pattern = rules.get(rule_name)
            assert pattern is not None and hasattr(pattern, "finditer"), (
                f"{lang_id}: _line_gates names '{rule_name}', which is not a compiled rule"
            )
            assert pattern_is_line_local(pattern), f"{lang_id}::{rule_name} is no longer line-local"
            assert build_line_gate(pattern) is not None, f"{lang_id}::{rule_name} no longer builds a line gate"
    assert declared >= 3, "premise: c/cpp/go state_mutation ship with line gates"


def test_detector_cache_carries_line_gates():
    from gitgalaxy.core.detector import StructuralExtractor

    extractor = StructuralExtractor("c", LANGUAGE_DEFINITIONS)
    quints = extractor._active_coding_rules("c")
    by_name = {name: line_gate for name, _pat, _key, _gate, line_gate in quints}
    assert by_name["state_mutation"] is not None
    # A rule not named in _line_gates must not grow one.
    others = [lg for name, lg in by_name.items() if name != "state_mutation"]
    assert all(lg is None for lg in others)
