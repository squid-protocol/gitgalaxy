"""SOP-002-v1 specification-grade decoy suite for IBM Enterprise COBOL / ISO COBOL-2002 (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers all 38/38 code-stream keyword families defined in cobol.py through the
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
_EXTRACTOR = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS)


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "cobol")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# All 38/38 COBOL code-stream families with authentic COBOL positive controls (Req C).
COBOL_FAMILIES: dict[str, str] = {
    "api": "       ENTRY 'MYENTRY'.",
    "auth_middleware": "       EXEC CICS SIGNON USERID(U) END-EXEC.",
    "bitwise_ops": "       COMPUTE X = FUNCTION BIT-AND(A B).",
    "branch": "       IF WS-X > 0",
    "cleanup": "       CLOSE IN-FILE.",
    "concurrency": "       EXEC CICS ENQ RESOURCE(WS-RES) END-EXEC.",
    "debug_prints": "       DISPLAY 'HELLO'.",
    "decorators": "       >>IF DEBUG-MODE = 1",
    "encapsulation": "       01 WS-LOCAL PIC X(10) PRIVATE.",
    "events": "       EXEC CICS SIGNAL EVENT('EV1') END-EXEC.",
    "explicit_casts": "       01 WS-B REDEFINES WS-A PIC 9(4).",
    "generics": "       CLASS-ID. MY-LIST USING T.",
    "globals": "       PROGRAM-ID. MYPROG IS COMMON.",
    "high_risk_execution": "       STOP RUN.",
    "immutability_locks": "       01 WS-C CONSTANT AS 42.",
    "import": "       COPY MYCOPY.",
    "io": "       READ IN-FILE.",
    "ipc_rpc_bridges": "       CALL 'SUBPROG'.",
    "listeners": "       CALL 'MQGET' USING H O M.",
    "macros": "       >>DEFINE DEBUG-MODE AS 1",
    "memory_alloc": "       ALLOCATE WS-BUF.",
    "panics_and_aborts": "       STOP RUN.",
    "pointers": "       01 WS-PTR USAGE POINTER.",
    "reflection_metaprogramming": "       01 WS-B REDEFINES WS-A PIC 9(4).",
    "regex_execution": "       INSPECT WS-STR TALLYING WS-CNT FOR ALL 'A'.",
    "safety": "       DECLARATIVES.",
    "safety_bypasses": "       NEXT SENTENCE.",
    "scientific": "       COMPUTE X = FUNCTION SQRT(Y).",
    "serialization_parsing": "       UNSTRING WS-IN DELIMITED BY ',' INTO WS-A.",
    "ssr_boundaries": "       EXEC CICS WEB SEND END-EXEC.",
    "state_mutation": "       MOVE 1 TO WS-X.",
    "sync_locks": "       EXEC CICS ENQ RESOURCE(WS-RES) END-EXEC.",
    "telemetry": "       EXEC CICS WRITEQ TD QUEUE('LOG1') FROM(WS-MSG) END-EXEC.",
    "test": "       CALL 'ZUNIT'.",
    "test_skip": "       IGNORE.",
    "thread_sleeps": "       EXEC CICS DELAY FOR SECONDS(5) END-EXEC.",
    "time_date_logic": "       MOVE FUNCTION CURRENT-DATE TO WS-DT.",
    "ui_framework": "       SCREEN SECTION.",
}


def test_cobol_covers_all_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["cobol"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(COBOL_FAMILIES) == expected


@pytest.mark.parametrize(("family", "stmt"), sorted(COBOL_FAMILIES.items()))
def test_cobol_positive_control_and_all_spec_comment_forms(family: str, stmt: str):
    # G1: Positive control
    assert _hits(family, stmt + "\n") >= 1, f"G1 failed for cobol.{family}: {stmt!r}"
    body = stmt.lstrip()
    # Req A: All IBM Enterprise COBOL / ISO COBOL-2002 comment forms
    # 1. Fixed-format column-7 `*` comment line
    assert _hits(family, f"      * {body}\n") == 0, f"G2 col-7 * comment leak for cobol.{family}"
    # 2. Fixed-format column-7 `/` page-eject comment line
    assert _hits(family, f"      / {body}\n") == 0, f"G2 col-7 / comment leak for cobol.{family}"
    # 3. COBOL-2002 full-line `*>` comment
    assert _hits(family, f"      *> {body}\n") == 0, f"G3 *> comment leak for cobol.{family}"
    # 4. COBOL-2002 inline trailing `*>` comment (delta over prefix)
    base_inline = _hits(family, "       CONTINUE *> SENTINEL_NOOP\n")
    assert _hits(family, f"       CONTINUE *> {body}\n") <= base_inline, f"G4 trailing *> leak for cobol.{family}"
    # 5. String-to-comment boundary
    base_sc = _hits(family, "       DISPLAY 'http://x' *> SENTINEL_NOOP\n")
    assert _hits(family, f"       DISPLAY 'http://x' *> {body}\n") <= base_sc, (
        f"G6b string-comment leak for cobol.{family}"
    )


def test_cobol_all_branch_hyphenated_word_boundaries():
    """Req B: Exhaustive all-branch G5 check using COBOL hyphenated identifiers (`WS-<KW>-VAL`)."""
    rules = LANGUAGE_DEFINITIONS["cobol"]["rules"]
    leaks: list[tuple[str, str, str]] = []
    for fam in sorted(COBOL_FAMILIES):
        pat = rules[fam]
        for cand in fdr.scrape_candidates(pat.pattern, fam):
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]{1,40}$", cand):
                continue
            bare_ctx = next((c for c in (f"       {cand}", f"       {cand}(X)") if _hits(fam, c + "\n") > 0), None)
            if bare_ctx is None:
                continue
            decoy = f"       MY-{cand}(X)\n" if "(X)" in bare_ctx else f"       WS-{cand}-VAL\n"
            if _hits(fam, decoy) > 0:
                leaks.append((fam, cand, decoy.strip()))
    assert leaks == [], f"COBOL hyphenated word-boundary leaks: {leaks}"


@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # Req D: Cross-family / contract negative controls
        # Closing scope terminators are not decision points
        ("branch", "       END-IF.\n       END-EVALUATE.\n       END-PERFORM.\n"),
        # Hyphenated COBOL data names containing keywords
        ("branch", "       01 WS-IF-FLAG PIC X.\n"),
        ("high_risk_execution", "       01 WS-STOP-RUN PIC X.\n"),
        ("io", "       01 WS-OPEN-FILE PIC X.\n"),
        # Bare DISPLAY is debug_prints, not structured telemetry
        ("telemetry", "       DISPLAY 'HELLO'.\n"),
        # Time/date read is not a thread sleep
        ("thread_sleeps", "       MOVE FUNCTION CURRENT-DATE TO WS-DT.\n"),
    ],
)
def test_cobol_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, negative_src) == 0
