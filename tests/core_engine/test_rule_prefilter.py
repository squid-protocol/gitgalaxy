# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
"""Unit suite for the required-literal prefilter (#3069).

The only property the engine relies on is ONE-SIDED: gate rejects => the regex
has zero matches. A gate that is missing (None) or too wide is a lost
optimization; a gate that rejects a matchable segment is a silent undercount.
Every test here is written against that asymmetry -- the adversarial cases all
attack the "never falsely reject" direction.
"""

import re

import pytest

from gitgalaxy.core.rule_prefilter import derive_literal_gate, fold_haystack
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _gate_rejects(gate, text: str) -> bool:
    literals, needs_casefold = gate
    hay = fold_haystack(text) if needs_casefold else text
    return not any(lit in hay for lit in literals)


# ==============================================================================
# EXTRACTION SHAPES
# ==============================================================================


def test_simple_literal():
    assert derive_literal_gate(re.compile(r"_Generic")) == (("_Generic",), False)


def test_word_bounded_alternation():
    gate = derive_literal_gate(re.compile(r"\b(strcpy|strcat|gets)\b"))
    assert gate is not None
    assert set(gate[0]) == {"strcpy", "strcat", "gets"}
    assert gate[1] is False


def test_empty_branch_falls_back_to_sibling_literal():
    # `(foo|)` can match zero text, so nothing inside it is required -- but
    # the sibling run "bar" still is.
    assert derive_literal_gate(re.compile(r"(foo|)bar")) == (("bar",), False)


def test_all_optional_pattern_has_no_gate():
    assert derive_literal_gate(re.compile(r"a?b*(c)?")) is None


def test_repeat_with_min_one_contributes():
    assert derive_literal_gate(re.compile(r"(ab){2,}")) == (("ab",), False)


def test_repeat_with_min_zero_contributes_nothing():
    # The only certain text left is the 1-char "x", which min_literal_len
    # rejects as a useless gate.
    assert derive_literal_gate(re.compile(r"(ab)*x")) is None


def test_char_class_breaks_literal_run():
    # "foo" and "bar" are separate runs around the class; either is a sound
    # gate, and the policy tie-break may pick either -- both are length 3.
    gate = derive_literal_gate(re.compile(r"foo[abc]bar"))
    assert gate is not None
    (lit,), needs_casefold = gate
    assert lit in ("foo", "bar")
    assert needs_casefold is False


def test_negative_lookahead_contributes_nothing():
    # The c `args` shape: a lookahead guard in front of required text.
    assert derive_literal_gate(re.compile(r"(?!typedef)struct\s+\w+")) == (("struct",), False)


def test_positive_lookahead_literal_is_harvested():
    # (?=X) asserts X matches, so X's required text gates even though the
    # match never consumes it (#3072, deferred from #3070). "delegate" beats
    # the consumed 1-char run on the length policy.
    gate = derive_literal_gate(re.compile(r"\w+(?=\s*=>\s*delegate\b)"))
    assert gate == (("=>",), False) or gate == (("delegate",), False)
    # A lookahead-only pattern (zero consumed text) now gates too.
    assert derive_literal_gate(re.compile(r"(?=.*declare)")) == (("declare",), False)


def test_positive_lookbehind_literal_is_harvested():
    assert derive_literal_gate(re.compile(r"(?<=typedef )\w+x")) == (("typedef ",), False)


def test_nested_lookaround_harvesting():
    # A negative lookaround anywhere in the chain still contributes nothing,
    # even with a positive one nested inside it.
    assert derive_literal_gate(re.compile(r"(?!(?=inner)x)\w*")) is None
    # Positive-inside-positive harvests the innermost required text.
    gate = derive_literal_gate(re.compile(r"(?=(?<=prefix)suffix)\w*"))
    assert gate is not None
    assert set(gate[0]) <= {"prefix", "suffix"}


def test_backref_to_unfixed_group_has_no_gate():
    assert derive_literal_gate(re.compile(r"(\w+)\1")) is None


def test_backref_to_literal_group_gates_on_the_group():
    assert derive_literal_gate(re.compile(r"(abc)\1")) == (("abc",), False)


def test_multiline_anchor_does_not_block_gating():
    gate = derive_literal_gate(re.compile(r"^[ \t]*(?:struct|union|enum)\b", re.M))
    assert gate is not None
    assert set(gate[0]) == {"struct", "union", "enum"}


def test_nested_groups_and_alternation():
    gate = derive_literal_gate(re.compile(r"(?:pub\s+)?(?:(unsafe|extern)\s+)?fn\s"))
    assert gate == (("fn",), False)


def test_policy_prefers_fewest_alternatives():
    # Both `alpha` and (beta|gamma) are sound; the singleton wins.
    gate = derive_literal_gate(re.compile(r"alpha.*(beta|gamma)"))
    assert gate == (("alpha",), False)


def test_common_prefix_alternation_collapses_via_parser_factoring():
    # sre_parse factors the shared "kw" prefix out of the alternation, so the
    # gate rightly collapses to the single required prefix -- smaller AND
    # sounder than enumerating the branches.
    wide = re.compile(r"\b(" + "|".join(f"kw{i}" for i in range(30)) + r")\b")
    assert derive_literal_gate(wide) == (("kw",), False)


def test_max_literals_cap_refuses_wide_sets():
    # No common prefix to factor: 30 genuinely distinct alternatives. The
    # default cap admits them (the multilingual debt rules run to ~70); an
    # explicit tighter cap refuses.
    words = [a + b + "zz" for a in "abcdef" for b in "uvwxy"][:30]
    wide = re.compile(r"\b(" + "|".join(words) + r")\b")
    assert derive_literal_gate(wide, max_literals=8) is None
    gate = derive_literal_gate(wide)
    assert gate is not None
    assert set(gate[0]) == set(words)


def test_literals_ordered_shortest_first():
    gate = derive_literal_gate(re.compile(r"\b(a1|bb22|c3)\b"))
    assert gate is not None
    lengths = [len(lit) for lit in gate[0]]
    assert lengths == sorted(lengths)


# ==============================================================================
# CASE-INSENSITIVITY
# ==============================================================================


def test_global_ignorecase_casefolds_literals():
    gate = derive_literal_gate(re.compile(r"SELECT\s+", re.I))
    assert gate == (("select",), True)


def test_scoped_ignorecase_widens_whole_gate():
    gate = derive_literal_gate(re.compile(r"(?i:Foo)bar"))
    assert gate is not None
    assert gate[1] is True


def test_scoped_case_sensitive_override_inside_ignorecase():
    # `(?-i:...)` under global re.I: literals inside are case-sensitive, but
    # gating them casefolded is still sound; assert only the invariant.
    pattern = re.compile(r"(?-i:EXACT)match", re.I)
    gate = derive_literal_gate(pattern)
    if gate is not None:
        for text in ("EXACTMATCH", "EXACTmatch", "prefix EXACTMatch suffix"):
            if pattern.search(text):
                assert not _gate_rejects(gate, text)


def test_ignorecase_sharp_s_gates_on_its_casefold():
    # The whole IGNORECASE class of 'ß' is {'ß', 'ẞ'} and both casefold to
    # 'ss', so gating on the casefolded literal is sound: every text the
    # regex matches contains 'strasse' after fold_haystack. (A haystack
    # 'STRASSE' passes the gate spuriously but re.I never matched it anyway
    # -- simple folding does not equate 'ß' with 'ss'.)
    pattern = re.compile(r"straße", re.I)
    gate = derive_literal_gate(pattern)
    assert gate == (("strasse",), True)
    for text in ("die straße", "DIE STRAẞE"):
        assert pattern.search(text) is not None, "test premise: the regex matches"
        assert not _gate_rejects(gate, text)


def test_ignorecase_cyrillic_literals_gate_foldsafely():
    # The multilingual debt-rule shape: Cyrillic entries fold 1:1, so the
    # candidate survives the fold-safety check and the gate honors the
    # invariant on every casing.
    pattern = re.compile(r"\b(FIXME|КОСТЫЛЬ|ИСПРАВИТЬ)\b", re.I)
    gate = derive_literal_gate(pattern)
    assert gate is not None
    assert set(gate[0]) == {"fixme", "костыль", "исправить"}
    for text in ("// костыль тут", "// КОСТЫЛЬ ТУТ", "# Исправить позже"):
        assert pattern.search(text) is not None, "test premise: the regex matches"
        assert not _gate_rejects(gate, text)


def test_single_cjk_char_literal_survives_length_floor():
    # min_literal_len is an ASCII-only policy: '坑' is one char but a
    # high-information probe, unlike '(' or '#'.
    pattern = re.compile(r"\b(HACK|坑|临时代码)", re.I)
    gate = derive_literal_gate(pattern)
    assert gate is not None
    assert "坑" in gate[0]


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        # re's IGNORECASE uses Unicode simple folding: each of these haystacks
        # matches the ASCII pattern, so the gate must never reject them.
        (r"session", "ſession active"),  # ſ (LATIN SMALL LONG S) matches 's'
        (r"kelvin", "Kelvin scale"),  # K (KELVIN SIGN) matches 'k'
        (r"strasse", "STRASSE"),  # plain ASCII folding sanity
        (r"istanbul", "İSTANBUL"),  # İ (U+0130): casefold inserts U+0307
        (r"istanbul", "ıstanbul"),  # ı (U+0131): casefold leaves it dotless
    ],
)
def test_unicode_folding_never_falsely_rejects(pattern, text):
    compiled = re.compile(pattern, re.I)
    assert compiled.search(text) is not None, "test premise: the regex matches"
    gate = derive_literal_gate(compiled)
    assert gate is not None
    assert not _gate_rejects(gate, text)


def test_dotted_capital_i_folding():
    # 'İ' (U+0130) casefolds to 'i' + COMBINING DOT ABOVE, which still
    # contains the ASCII 'i' the literal needs. Whether re.I itself matches
    # 'İ' against 'i' is version-dependent -- assert only the one-sided
    # invariant, on both match outcomes.
    compiled = re.compile(r"istanbul", re.I)
    gate = derive_literal_gate(compiled)
    assert gate is not None
    text = "İSTANBUL"
    if compiled.search(text):
        assert not _gate_rejects(gate, text)


# ==============================================================================
# ROBUSTNESS
# ==============================================================================


def test_non_string_pattern_refused():
    assert derive_literal_gate(re.compile(rb"binary")) is None


def test_malformed_duck_type_refused():
    class NotAPattern:
        pattern = 42
        flags = 0

    assert derive_literal_gate(NotAPattern()) is None


# ==============================================================================
# LIVE-RULESET PROPERTY TEST
# ==============================================================================

# Snippets chosen to trip careless gates: comments that talk about keywords,
# casing traps, adjacent-token forms, and plain prose. For every (rule,
# snippet) pair where the gate rejects, the rule must find nothing.
_TRICKY_SNIPPETS = (
    "",
    "x",
    "the quick brown fox\n" * 3,
    "// strcpy is banned here, use strlcpy\nint main(void) { return 0; }\n",
    "STRUCT/UNION/ENUM upper-cased prose, not code\n",
    "if(a&&b||c){for(;;){}}\n",
    "def f(x=1):\n    return x\n",
    "SELECT * FROM t WHERE a = 'IF';\n",
    "ſ K İ unicode folding bait\n",
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
)


def _every_compiled_rule():
    for lang_id, definition in sorted(LANGUAGE_DEFINITIONS.items()):
        for rule_name, pattern in (definition.get("rules") or {}).items():
            if rule_name.startswith("_") or not pattern or not hasattr(pattern, "finditer"):
                continue
            yield lang_id, rule_name, pattern


def test_extractor_never_raises_and_gates_are_one_sided_on_live_ruleset():
    seen = 0
    gated = 0
    for lang_id, rule_name, pattern in _every_compiled_rule():
        seen += 1
        gate = derive_literal_gate(pattern)  # must not raise, whatever the rule
        if gate is None:
            continue
        gated += 1
        literals, _needs_casefold = gate
        assert literals, f"{lang_id}::{rule_name} produced an empty gate"
        assert all(isinstance(lit, str) and lit for lit in literals)
        for snippet in _TRICKY_SNIPPETS:
            if _gate_rejects(gate, snippet):
                assert pattern.search(snippet) is None, (
                    f"{lang_id}::{rule_name}: gate {literals!r} rejected a snippet the rule matches: {snippet!r}"
                )
    assert seen > 1000, "premise: the live registry should expose its full ruleset"
    # The whole point of #3069: most of the ruleset must actually be gateable.
    assert gated / seen > 0.5, f"only {gated}/{seen} rules gateable"


def test_live_gates_accept_every_rules_own_matches():
    # Self-consistency: synthesize a haystack from each rule's own gate
    # literals; the gate must accept it (trivially true by construction) and,
    # stronger, any real match the rule finds in crucible-ish text containing
    # its literals must never be gated away. Here we assert the constructive
    # direction: for every gated rule, a text containing a literal passes.
    for lang_id, rule_name, pattern in _every_compiled_rule():
        gate = derive_literal_gate(pattern)
        if gate is None:
            continue
        literals, _needs_casefold = gate
        probe = f"prefix {next(iter(literals))} suffix"
        assert not _gate_rejects(gate, probe), f"{lang_id}::{rule_name} rejected its own literal"


# ==============================================================================
# DETECTOR INTEGRATION: GATED vs UNGATED PARITY
# ==============================================================================

_PARITY_SAMPLES = {
    "c": (
        "#include <stdio.h>\n"
        "typedef struct point { int x; } point_t;\n"
        "int main(int argc, char **argv) {\n"
        "    char buf[8];\n"
        "    strcpy(buf, argv[1]);\n"
        '    for (int i = 0; i < argc; i++) { printf("%d\\n", i); }\n'
        "    return 0;\n"
        "}\n"
    ),
    "typescript": (
        "import { readFile } from 'fs';\n"
        "export class Loader extends Base {\n"
        "    async load(path: string): Promise<string> {\n"
        "        if (!path) { throw new Error('no path'); }\n"
        "        return await readFile(path, 'utf8');\n"
        "    }\n"
        "}\n"
        "const x = eval('1 + 1');\n"
    ),
    "cobol": (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. HELLO.\n"
        "       PROCEDURE DIVISION USING A, B, C.\n"
        "           DISPLAY 'HELLO'.\n"
        "           STOP RUN.\n"
    ),
    "python": ("import os\ndef risky(cmd):\n    if cmd:\n        os.system(cmd)\n    return None\n"),
    # #3072: the two extra languages carry _line_gates entries, so this test
    # also proves line-gated vs fully-ungated 5-tuple parity. The samples are
    # deliberately mutation-dense AND contain gate-miss lines.
    "cpp": (
        "#include <vector>\n"
        "int sum(std::vector<int> &v) {\n"
        "    int total = 0;\n"
        "    for (auto &x : v) { total += x; }\n"
        "    v.push_back(total);\n"
        "    v.clear();\n"
        "    std::swap(total, v[0]);\n"
        "    return total;\n"
        "}\n"
    ),
    "go": (
        "package main\n"
        "func main() {\n"
        "    ch := make(chan int, 1)\n"
        "    ch <- 1\n"
        "    n := 0\n"
        "    n++\n"
        "    m := map[string]int{}\n"
        "    delete(m, \"k\")\n"
        "}\n"
    ),
}


@pytest.mark.parametrize("lang_id", sorted(_PARITY_SAMPLES))
def test_coding_analysis_output_identical_with_and_without_gates(lang_id):
    # The gate may only SKIP work whose result is provably empty, so the full
    # 5-tuple -- counts, mitigations, spatial maps (including empty-list key
    # PRESENCE, which spatial_correlation and the rce_funnel amplifier probe
    # with `in`), parents, threat locations -- must be byte-identical to an
    # ungated run.
    from gitgalaxy.core.detector import StructuralExtractor

    code = _PARITY_SAMPLES[lang_id]
    segments = [(lang_id, code, 0)]

    gated = StructuralExtractor(lang_id, LANGUAGE_DEFINITIONS)
    ungated = StructuralExtractor(lang_id, LANGUAGE_DEFINITIONS)
    # Seed the ungated instance's cache with gate=None quads: same rules, no
    # prefilter, i.e. pre-#3069 behavior.
    # (name, pat, key, None, None): no segment gate, no line gate (#3072) --
    # i.e. pre-#3069 behavior.
    ungated._active_rules_cache = {
        lang_id: [(name, pat, key, None, None) for name, pat, key, _gate, _line_gate in gated._active_coding_rules(lang_id)]
    }

    gated_telemetry: dict = {}
    ungated_telemetry: dict = {}
    result_gated = gated.coding_analysis(segments, regex_telemetry=gated_telemetry)
    result_ungated = ungated.coding_analysis(segments, regex_telemetry=ungated_telemetry)

    assert result_gated == result_ungated
    # Telemetry must keep the same KEY set either way (galaxyscope sums it);
    # only the timings may differ.
    assert set(gated_telemetry) == set(ungated_telemetry)
