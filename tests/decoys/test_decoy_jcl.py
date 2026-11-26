"""SOP-002-v1 specification-grade decoy suite for IBM z/OS JCL (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers all 13/13 code-stream keyword families defined in jcl.py through the
real Prism.split_streams() + StructuralExtractor.splice() pipeline.
"""

from __future__ import annotations

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
_EXTRACTOR = StructuralExtractor("jcl", LANGUAGE_DEFINITIONS)


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "jcl")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# All 13/13 JCL code-stream families with authentic z/OS JCL card positive controls (Req C).
JCL_FAMILIES: dict[str, str] = {
    "api": "//MYPROC   PROC",
    "branch": "//IF1      IF (RC = 0) THEN",
    "cleanup": "//DD1      DD DSN=MY.DATA,DISP=(OLD,DELETE)",
    "globals": "//JOBLIB   DD DSN=MY.LOADLIB,DISP=SHR",
    "high_risk_execution": "//STEP1    EXEC PGM=IKJEFT01",
    "import": "//INC1     INCLUDE MEMBER=MYMEM",
    "io": "//INFILE   DD DSN=MY.DATA.FILE,DISP=SHR",
    "safety": "//STEP1    EXEC PGM=MYPROG,COND=(4,LT)",
    "safety_bypasses": "//STEP1    EXEC PGM=MYPROG,COND=EVEN",
    "state_mutation": "//SET1     SET ENV=PROD",
    "sync_locks": "//DD1      DD DSN=MY.FILE,DISP=OLD",
    "system_config_mutation": "//CSD1     EXEC PGM=DFHCSDUP",
    "telemetry": "//MYJOB    JOB CLASS=A,MSGCLASS=X",
}


def test_jcl_covers_all_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["jcl"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(JCL_FAMILIES) == expected


@pytest.mark.parametrize(("family", "card"), sorted(JCL_FAMILIES.items()))
def test_jcl_positive_control_and_comment_card(family: str, card: str):
    # G1: Positive control fires through Prism + StructuralExtractor
    assert _hits(family, card + "\n") >= 1, f"G1 positive control failed for jcl.{family}: {card!r}"
    # G2 (Req A): Full-line `//*` JCL comment card suppresses the keyword
    comment_body = card[2:].lstrip() if card.startswith("//") else card
    assert _hits(family, f"//* {comment_body}\n") == 0, f"G2 comment leak for jcl.{family}"


@pytest.mark.parametrize(
    ("family", "decoy_src"),
    [
        # Req B: Identifier/operand boundary precision
        ("high_risk_execution", "//STEP1    EXEC PGM=IKJEFT01X\n"),
        ("high_risk_execution", "//STEP1    EXEC MYPGM=IKJEFT01\n"),
        ("system_config_mutation", "//STEP1    EXEC PGM=DFHCSDUPX\n"),
        ("sync_locks", "//DD1      DD DSN=MY.FILE,MYDISP=OLD\n"),
        ("cleanup", "//DD1      DD DSN=MY.FILE,MYDISP=(OLD,DELETE)\n"),
        ("safety_bypasses", "//STEP1    EXEC PGM=MYPROG,MYCOND=EVEN\n"),
        ("telemetry", "//MYJOB    JOB CLASS=A,XMSGCLASS=X\n"),
    ],
)
def test_jcl_operand_boundaries(family: str, decoy_src: str):
    assert _hits(family, decoy_src) == 0


@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # Req D: Cross-family / contract negative controls
        # #2751: ordinary utilities / IEFBR14 / IDCAMS are not arbitrary command execution
        ("high_risk_execution", "//STEP1    EXEC PGM=IEFBR14\n"),
        ("high_risk_execution", "//STEP1    EXEC PGM=IDCAMS\n"),
        # #3010: BIND PACKAGE( outside a DD */DD DATA in-stream payload must not fire
        ("high_risk_execution", "BIND PACKAGE(MYPKG) MEMBER(MYMEM)\n"),
        # #2899: a step named DFHCSDUP running IEFBR14 is not invoking DFHCSDUP
        ("system_config_mutation", "//DFHCSDUP EXEC PGM=IEFBR14\n"),
        # #2841 C5: DSN=&& temporary dataset is job-local, not external I/O
        ("io", "//TEMP     DD DSN=&&TMPFILE,DISP=(NEW,PASS)\n"),
        # Closing ENDIF is not a decision point
        ("branch", "//END1     ENDIF\n"),
        # Normal COND=(4,LT) is defensive (safety), not a bypass (safety_bypasses)
        ("safety_bypasses", "//STEP1    EXEC PGM=MYPROG,COND=(4,LT)\n"),
    ],
)
def test_jcl_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, negative_src) == 0
