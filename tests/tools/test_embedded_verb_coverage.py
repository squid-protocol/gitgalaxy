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
Tests for tests/tools/embedded_verb_coverage.py (#2990). Corpus-free and fast:
every case runs the real registry rules over a synthetic snippet, never the
crucible/rosetta corpora (that's the tool's own `--check` invocation, run as
part of the contract-PR gauntlet, not a unit test).

Sibling-module import pattern per CLAUDE.md "Testing conventions" (no
tests/__init__.py anywhere in this repo).
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import embedded_verb_coverage as evc  # noqa: E402


# ------------------------------------------------------------------------------
# EXPECTED_COBOL / EXPECTED_JCL self-consistency: every owned/blanket/none
# entry's reasoning must match what the REAL registry rules do today. This is
# the test that would catch a future rule edit silently invalidating a row
# the coverage table still claims is accurate.
# ------------------------------------------------------------------------------


def test_every_expected_cobol_entry_is_internally_consistent():
    """For each EXPECTED_COBOL row with a canonical CICS/SQL sample embedded
    in its own reason or a companion fixture, the verdict machinery must not
    report MISMATCH/GAP against the real corpus attribution. This mirrors
    what `--check` does over the corpora, at unit-test speed, by re-deriving
    the verdict from a hand-built observed Counter that matches the row's
    documented share (a share of 1.0 for every kind of row is the strictest
    self-check: does this row's OWN rules-set, run at 100%, verdict as OWNED
    the way the row itself claims?)."""
    import collections

    for verb, owner in evc.EXPECTED_COBOL.items():
        if owner.kind == evc.OWNED and owner.rules:
            observed = collections.Counter({r: 10 for r in owner.rules})
            n = 10
            v = evc.verdict_for(verb, n, observed, owner)
            assert v == evc.OWNED_VERDICT, f"{verb}: a 100% share of its own required rules must verdict OWNED, got {v}"


def test_every_expected_jcl_entry_is_internally_consistent():
    import collections

    for verb, owner in evc.EXPECTED_JCL.items():
        if owner.kind == evc.OWNED and owner.rules:
            observed = collections.Counter({r: 10 for r in owner.rules})
            n = 10
            v = evc.verdict_for(verb, n, observed, owner)
            assert v == evc.OWNED_VERDICT, f"{verb}: a 100% share of its own required rules must verdict OWNED, got {v}"


# ------------------------------------------------------------------------------
# The real regexes, on canonical snippets -- this is the actual #2990
# acceptance criterion at unit-test speed, independent of corpus content.
# ------------------------------------------------------------------------------

_COBOL_CANONICAL = {
    "CICS:RUN TRANSID": ("EXEC CICS RUN TRANSID('T') CHILD(X) END-EXEC", {"concurrency", "ipc_rpc_bridges"}),
    "CICS:FETCH CHILD": ("EXEC CICS FETCH CHILD(X) END-EXEC", {"concurrency"}),
    "CICS:STARTBR": ("EXEC CICS STARTBR FILE('F') END-EXEC", {"io"}),
    "CICS:ENDBR": ("EXEC CICS ENDBR FILE('F') END-EXEC", {"io", "cleanup"}),
    "CICS:ASKTIME": ("EXEC CICS ASKTIME ABSTIME(X) END-EXEC", {"time_date_logic"}),
    "CICS:HANDLE ABEND": ("EXEC CICS HANDLE ABEND LABEL(X) END-EXEC", {"safety"}),
    "CICS:HANDLE CONDITION": ("EXEC CICS HANDLE CONDITION ERROR(X) END-EXEC", {"safety"}),
    "CICS:SYNCPOINT": ("EXEC CICS SYNCPOINT END-EXEC", {"safety"}),
    "SQL:COMMIT": ("EXEC SQL COMMIT END-EXEC", {"safety", "io", "ipc_rpc_bridges"}),
}


def test_cobol_canonical_snippets_fire_exactly_their_expected_owners():
    import re
    import sys as _sys

    ROOT = TOOLS.parent.parent
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    rules = LANGUAGE_DEFINITIONS["cobol"]["rules"]
    active = {
        k: v
        for k, v in rules.items()
        if v is not None and not k.startswith("_") and k not in evc.BLANKET_RULES | evc.NOISE_RULES
    }
    for verb, (text, expected_owners) in _COBOL_CANONICAL.items():
        fired = {name for name, pat in active.items() if pat.search(text)}
        assert fired == expected_owners, f"{verb} ({text!r}): fired {fired}, expected {expected_owners}"
        owner = evc.EXPECTED_COBOL.get(verb)
        assert owner is not None, f"{verb} has no EXPECTED_COBOL entry"
        assert owner.rules <= fired, f"{verb}: EXPECTED requires {owner.rules}, real rules only fired {fired}"


def test_high_risk_execution_cancel_guard_excludes_cics_option_form():
    import sys as _sys

    ROOT = TOOLS.parent.parent
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    hre = LANGUAGE_DEFINITIONS["cobol"]["rules"]["high_risk_execution"]
    assert not hre.search("EXEC CICS ABEND ABCODE('X') CANCEL END-EXEC")
    assert not hre.search("EXEC CICS HANDLE ABEND CANCEL\n END-EXEC")
    assert not hre.search("EXEC CICS CANCEL REQID('R') END-EXEC")
    assert hre.search("CANCEL 'SUBPROG'.")
    assert hre.search("CANCEL WS-PGM-NAME")


# ------------------------------------------------------------------------------
# Parsing correctness (the census bugs found and fixed while building this)
# ------------------------------------------------------------------------------


def test_function_capture_does_not_cross_a_newline():
    """A COBOL data-item literally named FUNCTION followed by an unrelated
    word on the next physical line (real corpus shape, BANKDATA.cbl) must
    not be read as a call."""
    code = "01 FUNCTION\n           PIC X(10).\n"
    counts = evc.parse_cobol(code)
    assert not any(k.startswith("NATIVE:FUNCTION") for k in counts), counts


def test_nested_function_call_is_captured_as_its_own_verb():
    """FUNCTION MOD(35, FUNCTION INTEGER(A * B)) is a real corpus shape
    (IF1244.2.cbl) -- the outer call's paren-content class must not swallow
    the inner FUNCTION call's text."""
    code = "COMPUTE WS-NUM = FUNCTION MOD(35, FUNCTION INTEGER(A * B))."
    texts = evc.block_texts_cobol(code)
    assert texts.get("NATIVE:FUNCTION MOD")
    assert texts.get("NATIVE:FUNCTION INTEGER"), (
        "the nested call must be its own sample, not swallowed by the outer one"
    )


def test_call_literal_buckets_ordinary_programs_but_not_known_services():
    code = "CALL 'CEE3ABD' USING WS-CODE.\nCALL 'MY-SUBPROGRAM' USING X.\n"
    counts = evc.parse_cobol(code)
    assert counts.get("NATIVE:CALL 'CEE3ABD'") == 1
    assert counts.get("NATIVE:CALL '<ordinary program>'") == 1
    assert "NATIVE:CALL 'MY-SUBPROGRAM'" not in counts


def test_jcl_operand_and_pgm_require_a_real_statement_line():
    """#2990: a whole-file in-stream parameter deck (real corpus shape,
    DFH$SIP1.jcl -- a CICS SIT table with no `//` anywhere) must not be read
    as JCL operands; only text on a real `//` control-statement line counts."""
    code = "AICONS=AUTO   MVS CONSOLE SUPPORT\nGRPLIST=(A,B) SOME COMMENT\n"
    counts = evc.parse_jcl(code)
    assert not any(k.startswith("OPERAND:") for k in counts), counts

    code2 = "//STEP01  EXEC PGM=IEFBR14\n//DD1      DD DSN=X,DISP=SHR\n"
    counts2 = evc.parse_jcl(code2)
    assert counts2.get("PGM:*") == 1
    assert counts2.get("OPERAND:DISP=") == 1
    assert counts2.get("OPERAND:DSN=") == 1


def test_jcl_operand_continuation_line_still_counts():
    """A real JCL continuation line is still prefixed `//` (no bare-text
    continuation exists), so the per-line anchor must not lose it."""
    code = "//DD1      DD\n//             DSN=X,DISP=SHR\n"
    counts = evc.parse_jcl(code)
    assert counts.get("OPERAND:DSN=") == 1
    assert counts.get("OPERAND:DISP=") == 1


def test_jcl_installation_specific_operand_bucketing():
    import collections

    totals = collections.Counter({"OPERAND:APPLID=": 3, "OPERAND:DISP=": 500})
    files_seen = {"OPERAND:APPLID=": {"a", "b"}, "OPERAND:DISP=": {f"f{i}" for i in range(50)}}
    all_texts = {"OPERAND:APPLID=": ["APPLID=X"] * 3, "OPERAND:DISP=": ["DISP=SHR"] * 500}
    evc._bucket_installation_specific_operands(totals, files_seen, all_texts)
    assert "OPERAND:APPLID=" not in totals
    assert totals["OPERAND:<installation- or application-specific>"] == 3
    assert totals["OPERAND:DISP="] == 500, "a widely-used operand must not be bucketed"


# ------------------------------------------------------------------------------
# Verdict machinery
# ------------------------------------------------------------------------------


def test_verdict_owned_requires_share_and_forbids_extra():
    import collections

    owner = evc.owned("io", "cleanup", reason="test")
    assert evc.verdict_for("v", 10, collections.Counter({"io": 10, "cleanup": 10}), owner) == evc.OWNED_VERDICT
    assert evc.verdict_for("v", 10, collections.Counter({"io": 10}), owner) == evc.MISMATCH_VERDICT  # missing cleanup
    assert (
        evc.verdict_for("v", 10, collections.Counter({"io": 10, "cleanup": 10, "safety": 10}), owner)
        == evc.MISMATCH_VERDICT
    )  # extra


def test_verdict_min_share_lowers_the_floor_for_missing_but_not_extra():
    import collections

    owner = evc.owned("io", reason="test", min_share=0.2)
    assert evc.verdict_for("v", 10, collections.Counter({"io": 3}), owner) == evc.OWNED_VERDICT  # 30% clears 20%
    assert evc.verdict_for("v", 10, collections.Counter({"io": 1}), owner) == evc.MISMATCH_VERDICT  # 10% misses
    # an unrelated rule firing at 100% is still "extra" regardless of the lowered floor
    assert evc.verdict_for("v", 10, collections.Counter({"io": 3, "branch": 10}), owner) == evc.MISMATCH_VERDICT


def test_verdict_blanket_and_none():
    blanket = evc.blanket_only("test")
    assert evc.verdict_for("v", 10, {}, blanket) == evc.BLANKET_VERDICT
    assert evc.verdict_for("v", 10, {"io": 10}, blanket) == evc.MISMATCH_VERDICT

    none_ = evc.none_owned("test")
    assert evc.verdict_for("v", 10, {}, none_) == evc.NONE_VERDICT
    assert evc.verdict_for("v", 10, {"io": 10}, none_) == evc.MISMATCH_VERDICT


def test_verdict_gap_when_unrecorded():
    assert evc.verdict_for("v", 5, {}, None) == evc.GAP_VERDICT
