"""SOP-002-v1 specification-grade decoy suite for IBM Enterprise PL/I (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers all 35/35 code-stream keyword families defined in pli.py through the
real Prism.split_streams() + StructuralExtractor.splice() pipeline.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("pli", LANGUAGE_DEFINITIONS)


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "pli")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# All 35/35 PL/I code-stream families with authentic Enterprise PL/I positive controls (Req C).
PLI_FAMILIES: dict[str, str] = {
    "api": "MAIN: PROC OPTIONS(MAIN);",
    "auth_middleware": "EXEC CICS SIGNON USERID(U);",
    "bitwise_ops": "X = IAND(A, B);",
    "branch": "IF X > 0 THEN;",
    "cleanup": "CLOSE FILE(INFILE);",
    "concurrency": "ATTACH WORKER;",
    "debug_prints": "DISPLAY('HI');",
    "decorators": "MAIN: PROC OPTIONS(MAIN);",
    "encapsulation": "DCL X FIXED STATIC INTERNAL;",
    "events": "EXEC CICS SIGNAL EVENT(EV);",
    "explicit_casts": "X = UNSPEC(Y);",
    "globals": "DCL G FIXED STATIC;",
    "high_risk_execution": "STOP;",
    "immutability_locks": "DCL C FIXED NONASSIGNABLE;",
    "import": "EXEC SQL INCLUDE SQLCA;",
    "io": "EXEC CICS READQ TS QUEUE('Q1');",
    "ipc_rpc_bridges": "EXEC CICS LINK PROGRAM('SUB');",
    "listeners": "CALL MQGET(H, O, M);",
    "macros": "%DCL X FIXED;",
    "memory_alloc": "ALLOCATE BUF;",
    "panics_and_aborts": "RESIGNAL;",
    "pointers": "DCL P POINTER;",
    "reflection_metaprogramming": "DCL Y CHAR(4) DEFINED X;",
    "safety": "ON ERROR CALL HANDLER;",
    "safety_bypasses": "ON CONVERSION;",
    "scientific": "X = SQRT(Y);",
    "serialization_parsing": "X = XMLCHAR(R);",
    "ssr_boundaries": "EXEC CICS WEB SEND;",
    "state_mutation": "; X = 1;",
    "sync_locks": "EXEC CICS ENQ RESOURCE(R);",
    "telemetry": "EXEC CICS WRITEQ TD QUEUE('LOG');",
    "test": "CALL ZUNIT;",
    "thread_sleeps": "DELAY(1000);",
    "time_date_logic": "X = DATETIME();",
    "ui_framework": "DFHMDF POS=(1,1);",
}


def test_pli_covers_all_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["pli"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(PLI_FAMILIES) == expected


@pytest.mark.parametrize(("family", "snippet"), sorted(PLI_FAMILIES.items()))
def test_pli_positive_control_and_all_spec_comment_forms(family: str, snippet: str):
    # G1: Positive control
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for pli.{family}: {snippet!r}"
    # Req A: All IBM Enterprise PL/I comment forms
    # 1. Single-line block comment `/* ... */`
    assert _hits(family, f"/* {snippet} */\n") == 0, f"G2 block comment leak for pli.{family}"
    # 2. Multi-line block comment `/*\n ... \n*/`
    assert _hits(family, f"/*\n{snippet}\n*/\n") == 0, f"G3 multi-line block comment leak for pli.{family}"
    # 3. Enterprise PL/I `//` line comment
    assert _hits(family, f"// {snippet}\n") == 0, f"G2 // line comment leak for pli.{family}"
    # 4. Inline trailing `/* ... */` comment (delta over prefix)
    base_blk = _hits(family, "X = 1; /* SENTINEL_NOOP */\n")
    assert _hits(family, f"X = 1; /* {snippet} */\n") <= base_blk, f"G4 inline /* */ leak for pli.{family}"
    # 5. Inline trailing `//` comment (delta over prefix)
    base_sl = _hits(family, "X = 1; // SENTINEL_NOOP\n")
    assert _hits(family, f"X = 1; // {snippet}\n") <= base_sl, f"G4 inline // leak for pli.{family}"
    # 6. String-to-comment boundary
    base_sc = _hits(family, "S = 'http://x'; // SENTINEL_NOOP\n")
    assert _hits(family, f"S = 'http://x'; // {snippet}\n") <= base_sc, f"G6b string-comment leak for pli.{family}"


def test_pli_all_branch_word_boundaries():
    """Req B: Exhaustive all-branch G5 boundary check across PL/I rules."""
    rules = LANGUAGE_DEFINITIONS["pli"]["rules"]
    leaks: list[tuple[str, str, str]] = []
    for fam in sorted(PLI_FAMILIES):
        pat = rules[fam]
        for cand in fdr.scrape_candidates(pat.pattern, fam):
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{1,40}$", cand):
                continue
            bare_ctx = next((c for c in (cand, f"{cand}(X)") if _hits(fam, c + "\n") > 0), None)
            if bare_ctx is None:
                continue
            decoy = f"MY_{cand}(X)\n" if "(X)" in bare_ctx else f"MY_{cand}_VAL\n"
            if _hits(fam, decoy) > 0:
                leaks.append((fam, cand, decoy.strip()))
    assert leaks == [], f"PL/I word-boundary leaks: {leaks}"


@pytest.mark.xfail(strict=True, reason="https://github.com/squid-protocol/gitgalaxy/issues/9319")
def test_pli_ui_framework_national_char_boundary():
    """Req B/E: PL/I national characters (`$`, `@`, `#`) continue identifiers; `$DFHMDF` must not fire."""
    assert _hits("ui_framework", "$DFHMDF\n") == 0


@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # Req D: Cross-family / contract negative controls
        # Plain DO; END; group is not a decision point
        ("branch", "DO;\n  X = 1;\nEND;\n"),
        # EXEC SQL SELECT is SQL, not a PL/I SELECT(expr) branch
        ("branch", "EXEC SQL SELECT COL1 INTO :X FROM MYTAB;\n"),
        # Preprocessor %IF is macros, not branch
        ("branch", "%IF FLAG = 1 %THEN;\n"),
        # GO TO EXIT / CALL STOP name targets, not termination statements
        ("high_risk_execution", "GO TO EXIT;\n"),
        ("high_risk_execution", "CALL STOP;\n"),
        # EXEC SQL FETCH is SQL cursor fetch, not module FETCH
        ("high_risk_execution", "EXEC SQL FETCH C1 INTO :X;\n"),
        # Null ON-unit `ON CONVERSION;` swallows errors (safety_bypasses, not safety)
        ("safety", "ON CONVERSION;\n"),
        # Everyday prose `ON WEDNESDAY` is not a PL/I condition handler
        ("safety", "PUT LIST('MEETING ON WEDNESDAY');\n"),
    ],
)
def test_pli_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, negative_src) == 0
