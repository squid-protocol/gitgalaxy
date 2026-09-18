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
BMS strict structural-signature coverage (#2505). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology -- an adversarial pass against the signatures registered
in languages/bms.py, not a continuation of the generation work.

Every snippet is a real BMS shape: the macro statements are lifted from the map
sources of IBM's cics-genapp / cics-banking-sample family of samples (DFHMSD mapset
headers with TYPE=&SYSPARM, DFHMDI maps, named and literal DFHMDF fields, column-72
continuations, TYPE=FINAL + END closers).

#2505's core claim is also pinned here: `.bms` no longer belongs to jcl, and the
signals a map emits are UI-shaped (ui_framework), not job-control-shaped.
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG
from gitgalaxy.core.prism import Prism

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

BMS = LANGUAGE_DEFINITIONS["bms"]
BMS_RULES = BMS["rules"]

# A realistic mapset: comment banner, macro comment, mapset header with a
# column-72 continuation, one map, a named field, a literal (unnamed) field
# whose INITIAL carries inline-comment-shaped characters, and the closers.
_REAL_MAPSET = (
    "* CUSTOMER INQUIRY SCREEN\n"
    ".* GENERATED FOR CICSTS56 -- DO NOT EDIT\n"
    "CUSTSET  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,      X\n"
    "               TIOAPFX=YES,CTRL=(FREEKB,FRSET)\n"
    "CUSTMAP  DFHMDI SIZE=(24,80),LINE=1,COLUMN=1\n"
    "TITLEF   DFHMDF POS=(1,20),LENGTH=30,ATTRB=(ASKIP,BRT),                X\n"
    "               INITIAL='ACCOUNT! *> \"INQUIRY\"'\n"
    "         DFHMDF POS=(3,1),LENGTH=12,ATTRB=ASKIP,INITIAL='ACCOUNT NO:'\n"
    "ACCTNO   DFHMDF POS=(3,15),LENGTH=8,ATTRB=(UNPROT,IC,NUM)\n"
    "         DFHMSD TYPE=FINAL\n"
    "         END\n"
)

# ==============================================================================
# TEST 1: PER-SIGNATURE POSITIVE/NEGATIVE COVERAGE
# ==============================================================================
_BMS_SIMPLE_CASES = [
    # A named field declares a symbolic-map data field; an unnamed one is a
    # screen literal and declares nothing.
    ("args", "ACCTNO   DFHMDF POS=(3,15),LENGTH=8,ATTRB=(UNPROT,IC)", "         DFHMDF POS=(3,1),LENGTH=12"),
    ("structural_boundaries", "         END", "ENDING  DFHMDF POS=(1,1)"),
    ("structural_boundaries", "         DFHMSD TYPE=FINAL", "CUSTSET  DFHMSD TYPE=&SYSPARM,MODE=INOUT"),
    ("structural_boundaries", "         PRINT NOGEN", "PRINTF   DFHMDF POS=(5,1)"),
    ("func_start", "CUSTMAP  DFHMDI SIZE=(24,80),LINE=1,COLUMN=1", "         DFHMDI SIZE=(24,80)"),
    ("class_start", "CUSTSET  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL", "CUSTSET  DFHMSD TYPE=FINAL"),
    ("api", "CUSTMAP  DFHMDI SIZE=(24,80)", "         DFHMSD TYPE=FINAL"),
    (
        "dead_code",
        "*ACCTNO  DFHMDF POS=(3,15),LENGTH=8",
        "* THE DFHMDF FIELDS BELOW DEFINE THE DETAIL LINES",
    ),
    ("ui_framework", "         DFHMDF POS=(3,1),LENGTH=12,INITIAL='X'", "* SEE THE DFHMDF MACROS BELOW"),
    ("import", "         COPY ATTRDEFS", "COPYRT   DFHMDF POS=(24,1),INITIAL='COPYRIGHT ACME'"),
    ("macros", "         AIF   ('&SYSPARM' EQ 'DSECT').SKIPIT", "AIFX     DFHMDF POS=(1,1)"),
    ("macros", ".SKIPIT  ANOP", None),
    ("ownership", "* AUTHOR: MAINFRAME MODERNIZATION TEAM", "* THE AUTHOR OF THIS MAP IS UNKNOWN"),
    ("planned_debt", "* TODO: WIDEN THE ACCOUNT FIELD TO 12 DIGITS", None),
    ("fragile_debt", "* HACK: SUFFIX FORCED TO M TO DODGE DFHMAPS BUG", None),
    ("spec_exposure", "* [SPEC-2505] INQUIRY SCREEN LAYOUT", "MDFSPEC  DFHMDF POS=(1,1),INITIAL='[SPEC-1]'"),
]


@pytest.mark.parametrize(("signature", "positive", "negative"), _BMS_SIMPLE_CASES)
def test_bms_signature_positive_and_negative(signature, positive, negative):
    pattern = BMS_RULES[signature]
    assert pattern is not None, f"bms's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"bms {signature!r} failed its documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"bms {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _BMS_SIMPLE_CASES}
    live = {k for k, v in BMS_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


# ==============================================================================
# TEST 2: SCHEMA COMPLETENESS (Rule 4 / Step 4 item 9)
# ==============================================================================
_BASELINE_KEYS = [
    "branch", "args", "structural_boundaries", "func_start", "class_start",
    "safety", "safety_bypasses", "high_risk_execution", "io", "api",
    "state_mutation", "dead_code", "doc", "test",
    "concurrency", "ui_framework", "closures", "globals", "decorators",
    "generics", "comprehensions", "scientific", "reflection_metaprogramming",
    "import", "_dependency_capture", "ownership",
    "planned_debt", "fragile_debt", "hardcoded_secrets", "spec_exposure",
    "ssr_boundaries", "events", "dependency_injection",
    "macros", "pointers", "memory_alloc", "inline_asm",
    "telemetry", "debug_prints", "explicit_casts", "panics_and_aborts",
    "thread_sleeps", "bitwise_ops", "sync_locks", "immutability_locks",
    "cleanup", "encapsulation", "listeners", "test_skip",
    "serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges",
    "auth_middleware",
]  # fmt: skip

# BMS is a purely declarative screen definition: no control flow, no error
# channel, no execution, no data movement of its own (the hosting COBOL/PL/I
# program owns EXEC CICS SEND/RECEIVE), no state, no types, no tests. What it
# HAS is the UI surface (ui_framework), the mapset/map/field structure, HLASM's
# COPY and conditional assembly, and the `*` comment surface.
_EXPECTED_NONE_KEYS = {
    "branch", "safety", "safety_bypasses", "high_risk_execution", "io",
    "state_mutation", "doc", "test", "concurrency", "closures", "globals",
    "decorators", "generics", "comprehensions", "scientific",
    "reflection_metaprogramming", "hardcoded_secrets", "ssr_boundaries",
    "events", "dependency_injection", "pointers", "memory_alloc", "inline_asm",
    "telemetry", "debug_prints", "explicit_casts", "panics_and_aborts",
    "thread_sleeps", "bitwise_ops", "sync_locks", "immutability_locks",
    "cleanup", "encapsulation", "listeners", "test_skip",
    "serialization_parsing", "regex_execution", "time_date_logic",
    "ipc_rpc_bridges", "auth_middleware",
}  # fmt: skip


def test_bms_schema_completeness():
    missing = set(_BASELINE_KEYS) - set(BMS_RULES)
    assert not missing, f"bms rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(BMS_RULES) - set(_BASELINE_KEYS)
    assert extra == set(), f"unexpected non-baseline keys: {extra}"


def test_bms_none_keys_are_the_intended_set():
    actual_none = {k for k, v in BMS_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


# ==============================================================================
# TEST 3: REGISTRATION -- THE #2505 DIVORCE ITSELF
# ==============================================================================
def test_bms_registration_and_jcl_divorce():
    assert set(BMS["extensions"]) == {".bms", ".map"}
    assert ".bms" not in LANGUAGE_DEFINITIONS["jcl"]["extensions"], "#2505: .bms must no longer be jcl's"
    assert BMS["case_insensitive_imports"] is True
    assert BMS["lexical_family"] == "positional_anchored"


def test_map_extension_is_a_registered_collision():
    # `.map` is JS source maps and linker maps in the wild; it must never lock
    # to bms on extension alone (Tier 1 refuses COLLISION_FREQUENCIES members).
    assert ".map" in LENS_CONFIG["COLLISION_FREQUENCIES"]
    assert BMS.get("internal_discriminator") is not None
    # And ecosystem gravity must collapse for a `.map` living among web build
    # output or linker artifacts (#377's toxic-neighbor mechanism): the
    # single-candidate gravity fallback would otherwise self-support `.map`
    # with its own count and lock a JS source map to bms sight unseen.
    assert {".js", ".css", "package.json"} <= set(BMS["disqualifiers"])


def test_bms_invocation_model_is_top_level_and_not_a_rule():
    # jcl.py's own warning, re-pinned for bms: language_lens.py's pre-compiler
    # turns every STRING inside `rules` into a compiled regex, so the
    # declaration only survives at the definition's top level.
    assert BMS["invocation_model"] == "positional"
    assert "invocation_model" not in BMS_RULES


# ==============================================================================
# TEST 4: LEXICAL-FAMILY SANITY (Step 4 item 8), through the real Prism
# ==============================================================================
def test_bms_prism_strips_star_and_macro_comments_only():
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(_REAL_MAPSET, "bms")
    code = streams["code_stream"]
    comments = streams["comment_stream"]

    # Both full-line comment styles land in the comment stream...
    assert "CUSTOMER INQUIRY SCREEN" in comments
    assert "GENERATED FOR CICSTS56" in comments
    assert "CUSTOMER INQUIRY SCREEN" not in code
    # ...and every macro statement stays in the code stream, including the
    # continuation line whose INITIAL literal carries `!`, `*>` and `"` --
    # HLASM has no inline comment marker, so nothing may split on them.
    assert "CUSTSET  DFHMSD" in code
    assert "INITIAL='ACCOUNT! *> \"INQUIRY\"'" in code


def test_bms_names_starting_with_shared_anchor_chars_survive():
    # The #1898 ABAP-class-header bug, re-armed for BMS: the shared positional
    # anchor set ({'*','/','C','c','!'}) would erase any statement whose
    # column-1 name field starts with C/c/! -- and real mapsets are FULL of
    # C-names (CUSTMAP, CLRSCRN...). The bms prism mode must keep them.
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "CUSTMAP  DFHMDI SIZE=(24,80)\nclrfld   DFHMDF POS=(1,1),LENGTH=8\n/SLASH   DFHMDF POS=(2,1)\n"
    code = prism.split_streams(sample, "bms")["code_stream"]
    assert "CUSTMAP  DFHMDI" in code
    assert "clrfld   DFHMDF" in code
    assert "/SLASH   DFHMDF" in code, "'/' is not a BMS comment marker (it is Fortran/COBOL's)"


def test_bms_debt_rules_fire_on_the_comment_stream():
    # #2610's jcl lesson: debt rules are dead if the language's comment surface
    # never reaches comment_analysis. Confirm the plumbing end-to-end: the
    # comment stream carries the marker and the shared rule matches it there.
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = "* TODO: WIDEN THE ACCOUNT FIELD\nACCTNO   DFHMDF POS=(3,15),LENGTH=8\n"
    comments = prism.split_streams(sample, "bms")["comment_stream"]
    assert BMS_RULES["planned_debt"].search(comments)


# ==============================================================================
# TEST 5: REALISTIC-FORM & BOUNDARY AUDIT (Rules 9/10/15)
# ==============================================================================
def test_bms_counts_on_the_real_mapset_are_exact():
    counts = {k: len(list(BMS_RULES[k].finditer(_REAL_MAPSET))) for k, v in BMS_RULES.items() if v is not None}
    # 6 macro statements: 2 DFHMSD (header + FINAL), 1 DFHMDI, 3 DFHMDF.
    assert counts["ui_framework"] == 6
    assert counts["func_start"] == 1  # CUSTMAP
    assert counts["class_start"] == 1  # CUSTSET (FINAL excluded)
    assert counts["args"] == 2  # TITLEF, ACCTNO -- the literal field declares nothing
    assert counts["api"] == 2  # CUSTSET + CUSTMAP
    assert counts["structural_boundaries"] == 2  # TYPE=FINAL closer + END
    assert counts["import"] == 0
    assert counts["dead_code"] == 0


def test_bms_class_start_excludes_final_even_when_named():
    # Real closers frequently repeat the mapset name -- a documented exclusion
    # must actually exclude (Rule 15).
    assert not BMS_RULES["class_start"].search("CUSTSET  DFHMSD TYPE=FINAL")
    assert not BMS_RULES["api"].search("CUSTSET  DFHMSD TYPE=FINAL")
    assert BMS_RULES["structural_boundaries"].search("CUSTSET  DFHMSD TYPE=FINAL")


def test_bms_continuation_lines_do_not_double_count():
    stmt = (
        "CUSTSET  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,      X\n"
        "               TIOAPFX=YES,                                            X\n"
        "               CTRL=(FREEKB,FRSET)\n"
    )
    assert len(list(BMS_RULES["ui_framework"].finditer(stmt))) == 1


def test_bms_macro_words_inside_initial_literals_do_not_match():
    # Rule 18: strings are never masked, so the rules' statement-position
    # anchor is the only shield. A screen literal SAYING the macro's name must
    # not read as a macro statement.
    line = "HELPTX   DFHMDF POS=(22,1),LENGTH=40,INITIAL='USE DFHMDI TO ADD A MAP'\n"
    hits = list(BMS_RULES["ui_framework"].finditer(line))
    assert len(hits) == 1, "the DFHMDF statement itself is the only hit"
    assert not BMS_RULES["func_start"].search(line)


def test_bms_lowercase_source_still_matches():
    # HLASM shops normally shout, but lowercase source assembles fine; every
    # statement rule carries re.I.
    assert BMS_RULES["func_start"].search("custmap  dfhmdi size=(24,80)")
    assert BMS_RULES["ui_framework"].search("         dfhmdf pos=(1,1),length=8")


# ==============================================================================
# TEST 6: `re.M` COMPLETENESS AUDIT (Rule 13)
# ==============================================================================
def test_bms_caret_anchored_rules_all_set_multiline_flag():
    for key, pattern in BMS_RULES.items():
        if pattern is None or not isinstance(pattern, re.Pattern):
            continue
        if "^" in pattern.pattern.replace("[^", ""):
            assert pattern.flags & re.M, f"bms {key!r} uses '^' without re.M"
    disc = BMS["internal_discriminator"]
    assert disc.flags & re.M, "internal_discriminator uses '^' without re.M"


# ==============================================================================
# TEST 7: ReDoS IMMUNITY (Rule 5/14), scaled adversarial payloads
# ==============================================================================
_N = 32000


@pytest.mark.parametrize(
    ("signature", "payload"),
    [
        ("ui_framework", "A" * _N),
        ("ui_framework", ("A" * 31 + " DFHMD") * (_N // 40)),
        ("args", "A" * _N + " DFHMDF"),
        ("func_start", "@" + "#" * _N),
        ("class_start", "CUSTSET  DFHMSD " + "A" * _N),
        ("api", "CUSTMAP  DFHMSD " + " " * _N),
        ("structural_boundaries", "X DFHMSD " + "A" * _N),
        ("dead_code", "*A DFHMDF " + "A" * _N),
        ("import", "X COPY " + " " * _N),
        ("_dependency_capture", "X COPY " + "A" * _N),
        ("macros", "&" + "A" * _N),
        ("ownership", "* Author:" + " " * _N),
        ("spec_exposure", "*" + "A" * 199 + "[SPEC-" + "1" * _N),
    ],
    ids=lambda v: v if len(v) <= 30 else f"{v[:10].strip()}...x{len(v)}",
)
def test_bms_redos_immunity(signature, payload):
    pattern = BMS_RULES[signature] if signature in BMS_RULES else BMS[signature]
    assert_redos_immune(pattern, payload, timeout_sec=3.0)


# ==============================================================================
# TEST 8: FUNCTION SLICING through Mode A (gitgalaxy#3077)
# ==============================================================================
def test_bms_maps_slice_through_mode_a_as_named_units():
    """bms is registered in detector.py's Mode A tuple (the abap/dockerfile/jcl/m4
    slot). Without it the language falls through to brace slicing -- HLASM macro
    source has no braces -- and 0 of the raw DFHMDI matches ever reach
    function_data (#3077: functions_found 0, every per-function descriptor
    undefined, found by the keyword-rosetta bias report the day #2505 landed)."""
    from gitgalaxy.core.detector import StructuralExtractor

    functions = StructuralExtractor("bms", LANGUAGE_DEFINITIONS).splice(_REAL_MAPSET, "")["functions"]
    names = {f["name"] for f in functions}
    assert names == {"CUSTMAP"}, f"the named map is the unit; got {names}"


def test_bms_is_in_the_mode_a_dispatch_and_named_class_allowlist():
    import inspect

    from gitgalaxy.core import detector

    assert "bms" in detector._CLASS_START_NAMED_EXTRACTION_LANGS
    source = inspect.getsource(detector)
    assert '"bms",' in source


# ==============================================================================
# TEST 9: `.map` COLLISION RESOLUTION through the real LanguageDetector
# ==============================================================================
_SOURCEMAP_JSON = (
    '{"version":3,"file":"app.min.js","sources":["../src/app.js"],'
    '"names":["require","module","exports"],'
    '"mappings":"AAAA,SAASA,EAAQC,GACvB,IAAIC"}'
)


def test_bms_extension_classifies_directly():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("maps/custset.bms", _REAL_MAPSET)
    assert lang == "bms"


def test_map_extension_with_bms_content_resolves_to_bms():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("maps/custset.map", _REAL_MAPSET)
    assert lang == "bms", "a real BMS map named .map must resolve through the internal discriminator"


def test_js_sourcemap_never_reads_as_bms():
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus("dist/app.min.js.map", _SOURCEMAP_JSON)
    assert lang != "bms", f"a JS source map classified as bms (got {lang!r})"


def test_internal_discriminator_rejects_non_bms_map_content():
    disc = BMS["internal_discriminator"]
    assert disc.search(_REAL_MAPSET)
    assert not disc.search(_SOURCEMAP_JSON)
    linker_map = "Memory Configuration\n\nName    Origin    Length\nFLASH   0x08000000 0x00080000\n"
    assert not disc.search(linker_map)
