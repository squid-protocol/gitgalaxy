"""SOP-002-v1 gap-cell decoy suite for IBM High Level Assembler (HLASM) (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers only the three code-stream families of hlasm.py that had no decoy row before this suite:
bitwise_ops, pointers and ssr_boundaries. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline.

HLASM is fixed-format: a statement is name (column 1), operation, operands, then a free-text
remarks field. The comment forms the HLASM Language Reference defines are the `*` column-1 comment
line, the `.*` macro-language comment line, and the trailing remarks field. Columns 72-80 (the
continuation and sequence fields) are not exercised here.
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
_EXTRACTOR = StructuralExtractor("hlasm", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_REMARKS_ISSUE = "https://github.com/squid-protocol/gitgalaxy/issues/9422"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "hlasm")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# Authentic HLASM statements in fixed columns (name col 1, operation col 10).
HLASM_GAP_FAMILIES: dict[str, str] = {
    "bitwise_ops": "         NR    R1,R2",
    "pointers": "ADDR     DC    A(TARGET)",
    "ssr_boundaries": "         EXEC CICS WEB SEND FROM(OUT) END-EXEC",
}


def test_hlasm_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["hlasm"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(HLASM_GAP_FAMILIES) <= expected


def test_hlasm_baseline_has_sop002_row_for_each_covered_family():
    import json

    rows = json.loads(_BASELINE.read_text())["decoys"]["hlasm"]
    for family in HLASM_GAP_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family


@pytest.mark.parametrize(("family", "stmt"), sorted(HLASM_GAP_FAMILIES.items()))
def test_hlasm_positive_control(family: str, stmt: str):
    assert _hits(family, stmt + "\n") >= 1, f"G1 failed for hlasm.{family}: {stmt!r}"


@pytest.mark.parametrize(("family", "stmt"), sorted(HLASM_GAP_FAMILIES.items()))
def test_hlasm_full_line_comment_forms(family: str, stmt: str):
    body = stmt.strip()
    # `*` in column 1 is a comment statement
    assert _hits(family, "*" + stmt[1:] + "\n") == 0
    assert _hits(family, f"* {body}\n") == 0
    # `.*` in column 1 is a macro-language comment statement
    assert _hits(family, ".*" + stmt[2:] + "\n") == 0
    assert _hits(family, f".* {body}\n") == 0
    # a comment block of several lines (a banner)
    assert _hits(family, f"**********\n* {body}\n**********\n") == 0


@pytest.mark.parametrize(
    "family",
    [
        "bitwise_ops",
        pytest.param("pointers", marks=pytest.mark.xfail(strict=True, reason=_REMARKS_ISSUE)),
        pytest.param("ssr_boundaries", marks=pytest.mark.xfail(strict=True, reason=_REMARKS_ISSUE)),
    ],
)
def test_hlasm_trailing_remarks_field(family: str):
    """The remarks field after the operands is a comment; the keyword in it must not count."""
    body = HLASM_GAP_FAMILIES[family].strip()
    assert _hits(family, f"         LR    R1,R2      {body}\n") == 0
    # string-to-remarks boundary: the blank after the quoted operand ends the operands
    assert _hits(family, f"         WTO   'http://x'   {body}\n") == 0


@pytest.mark.parametrize(
    ("family", "string_src", "counts"),
    [
        # G6: strings count by design (#2535) for the rules that are not column-anchored
        ("pointers", "         MVC   OUT,=C'DC A(TARGET)'\n", True),
        ("ssr_boundaries", "         MVC   OUT,=C'EXEC CICS WEB SEND'\n", True),
        # bitwise_ops is anchored to the operation field, so a string never counts
        ("bitwise_ops", "         MVC   OUT,=C'NR R1,R2'\n", False),
    ],
)
def test_hlasm_string_literal_behaviour(family: str, string_src: str, counts: bool):
    assert (_hits(family, string_src) > 0) is counts


def _branches(family: str) -> list[str]:
    pat = LANGUAGE_DEFINITIONS["hlasm"]["rules"][family].pattern
    if family == "bitwise_ops":
        m = re.search(r"\(\?:(N\|NR[^)]*)\)", pat)
        assert m, pat
        return m.group(1).split("|")
    raise AssertionError(family)


_BITWISE_OPS = _branches("bitwise_ops")


def test_hlasm_bitwise_branch_list_is_complete():
    assert len(_BITWISE_OPS) == 24


@pytest.mark.parametrize("op", _BITWISE_OPS)
def test_hlasm_bitwise_all_branches(op: str):
    """Req B: every branch fires as an operation, and never inside a longer symbol."""
    assert _hits("bitwise_ops", f"         {op:<6}R1,R2\n") == 1
    # operation field is a longer mnemonic that merely starts with the branch
    assert _hits("bitwise_ops", f"         {op}X    R1,R2\n") == 0
    assert _hits("bitwise_ops", f"         {op}1    R1,R2\n") == 0
    # the branch text embedded in a name-field symbol of another statement
    assert _hits("bitwise_ops", f"MY{op}VAL  DS    F\n") == 0
    assert _hits("bitwise_ops", f"{op}VAL     DS    F\n") == 0
    # the branch text as an operand of another instruction
    assert _hits("bitwise_ops", f"         LR    R1,{op}\n") == 0
    assert _hits("bitwise_ops", f"         B     {op}\n") == 0


@pytest.mark.parametrize(
    "src",
    [
        "MY_DC     DS    A\n",  # name field containing DC
        "         DC    AD(TARGET)\n",  # not an address constant type
        "         DC    AB(TARGET)\n",
        "         DCA(TARGET)\n",  # no blank after DC
        "MYDC      DC    X'00'\n",
    ],
)
def test_hlasm_pointers_boundaries(src: str):
    assert _hits("pointers", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        "         DC    AL4(TARGET)\n",  # address constant with a length modifier
        "         DC    V(EXTSUB)\n",
        "         DC    2A(T1,T2)\n",
        "         LA    R1,=A(TARGET)\n",
        "         L     R15,=V(EXTSUB)\n",
        "         L     R15,=AL4(TARGET)\n",
    ],
)
def test_hlasm_pointers_every_literal_branch_fires(src: str):
    assert _hits("pointers", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "         MY_EXEC CICS WEB SEND FROM(OUT)\n",
        "         EXEC CICS MYWEB SEND FROM(OUT)\n",
        "         EXEC CICS WEBSEND FROM(OUT)\n",
        "         EXEC CICS MYDOCUMENT CREATE\n",
        "         EXEC CICS DOCUMENTS CREATE\n",
        "         EXEC CICS MY_SOAPFAULT CREATE\n",
        "         EXEC CICS SOAPFAULTS CREATE\n",
        "         EXEC CICS MYEXTRACT WEB\n",
        "         EXEC CICS EXTRACT MYWEB\n",
        "         EXEC CICS EXTRACT WEBX\n",
        "         EXEC CICS EXTRACT TCPIPS\n",
        "         EXEC CICS EXTRACT CERTIFICATES\n",
    ],
)
def test_hlasm_ssr_boundaries_branch_boundaries(src: str):
    assert _hits("ssr_boundaries", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        "         EXEC CICS WEB RECEIVE INTO(IN)\n",
        "         EXEC CICS DOCUMENT CREATE DOCTOKEN(T)\n",
        "         EXEC CICS SOAPFAULT CREATE CLIENT\n",
        "         EXEC CICS EXTRACT WEB HTTPMETHOD(M)\n",
        "         EXEC CICS EXTRACT TCPIP CLIENTADDR(A)\n",
        "         EXEC CICS EXTRACT CERTIFICATE ISSUERDN(D)\n",
    ],
)
def test_hlasm_ssr_boundaries_every_literal_branch_fires(src: str):
    assert _hits("ssr_boundaries", src) >= 1


@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # Req D: storage RMW forms belong to state_mutation, not bitwise_ops (hlasm.py contract)
        ("bitwise_ops", "         OI    FLAGS,X'80'\n"),
        ("bitwise_ops", "         NI    FLAGS,X'7F'\n"),
        ("bitwise_ops", "         XI    FLAGS,X'01'\n"),
        ("bitwise_ops", "         OC    A(8),B\n"),
        ("bitwise_ops", "         NC    A(8),B\n"),
        ("bitwise_ops", "         XC    A(8),A\n"),
        # branches and ordinary arithmetic are not bitwise
        ("bitwise_ops", "         BR    R14\n"),
        ("bitwise_ops", "         AR    R1,R2\n"),
        ("bitwise_ops", "         LR    R1,R2\n"),
        # LA is everyday unsigned arithmetic, deliberately not an address-of (hlasm.py ruling)
        ("pointers", "         LA    R1,4(,R1)\n"),
        ("pointers", "         LA    R1,BUFFER\n"),
        # non-address constants
        ("pointers", "COUNT    DC    F'1'\n"),
        ("pointers", "NAME     DC    CL8'PROGRAM'\n"),
        # other CICS commands are not the web/document API
        ("ssr_boundaries", "         EXEC CICS SEND MAP('MAP1') END-EXEC\n"),
        ("ssr_boundaries", "         EXEC CICS EXTRACT PROCESS PROCNAME(P)\n"),
        ("ssr_boundaries", "         EXEC CICS READ FILE('F') INTO(R)\n"),
    ],
)
def test_hlasm_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, negative_src) == 0
