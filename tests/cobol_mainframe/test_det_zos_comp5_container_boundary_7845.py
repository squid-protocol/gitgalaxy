"""#7845 (#7709, register C7): the boundary of COMP-5 in a CICS container, pinned. A PUT / GET CONTAINER area over a
COMP-5 item translates under the default (z/OS order) and under an explicit `zos_comp5=True`; a code-page conversion
(FROMCCSID) rewrites the binary bytes, so it is refused by name under True and falls back to the oracle's order under
the default. The comparator does not reverse container bytes against the oracle, so no burned equivalence case may hold
a COMP-5 item in a container AND declare `comp5_byte_order`: it would compare unreversed bytes. Synthetic programs only."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STUB = "public class Zc5Service {\n    public int handleCall(CobolRef<byte[]> a) {\n        return 0;\n    }\n}\n"
SWAP = "Cobol.swapZosComp5(true)"


def _program(opt: str) -> str:
    lines = [
        "IDENTIFICATION DIVISION.", "PROGRAM-ID. ZC5.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01 G.", "   05 T PIC X(2).", "   05 A PIC S9(9) COMP-5.",
        "01 H.", "   05 U PIC X(2).", "   05 B PIC S9(9) COMP-5.",
        "01 LEN PIC S9(8) COMP VALUE 6.", "PROCEDURE DIVISION.",
        "    EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(G)",
        f"      FLENGTH(LEN) {opt} END-EXEC",
        "    EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(H)",
        f"      FLENGTH(LEN) {opt} END-EXEC",
        "    EXEC CICS RETURN END-EXEC.", "    GOBACK.",
    ]  # fmt: skip
    return "\n".join(f"       {x}" for x in lines) + "\n"


def _translate(tmp_path, opt: str, zos_comp5):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "ZC5.cbl").write_text(_program(opt))
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "ZC5.cbl", [], STUB, "p", None, tmp_path / "project", zos_comp5=zos_comp5)


@pytest.mark.parametrize("zos_comp5", [None, True])
def test_a_comp5_area_translates_in_z_os_order_by_default_and_when_asked(tmp_path, zos_comp5):
    assert SWAP in _translate(tmp_path, "", zos_comp5).java


def test_the_oracle_order_is_unchanged_when_switched_off(tmp_path):
    assert SWAP not in _translate(tmp_path, "", False).java


def test_a_code_page_conversion_is_refused_by_name_when_asked_and_falls_back_by_default(tmp_path):
    with pytest.raises(ValueError, match=r"FROM CONTAINER: the area holds A COMP-5, and a code-page conversion"):
        _translate(tmp_path, "FROMCCSID(1140)", True)
    assert SWAP not in _translate(tmp_path, "FROMCCSID(1140)", None).java


def test_the_census_has_no_bytes_overlap_row():
    gaps = json.loads((REPO / "tests/fixtures/gap_prevalence/census_summary.json").read_text(encoding="utf-8"))["gaps"]
    assert not [g["gap"] for g in gaps if "bytes overlap" in g["gap"].lower()]


# the two async credit-card ports hold COMP-5 items, but their PUT / GET CONTAINER areas are text (C7.md): no COMP-5 byte
# crosses a container, so the comparator's missing reversal does not touch them
TEXT_ONLY_CONTAINERS = {"asynccc-asyncpnt", "asynccc-seqpnt"}


def test_no_other_case_declaring_the_comp5_difference_uses_containers():
    """The comparator gap (C7.md, "Not covered"): a new case on both sides of it must be built with the reversal."""
    hit = []
    for case in sorted((REPO / "tests/equivalence").glob("*/case.json")):
        text = case.read_text(encoding="utf-8")
        if "comp5_byte_order" not in text or not re.search(r"(?i)\bCONTAINERS\b", text):
            continue
        if case.parent.name not in TEXT_ONLY_CONTAINERS:
            hit.append(case.parent.name)
    assert not hit, f"{hit}: comp5_byte_order with a CONTAINERS event needs the comparator's container reversal"
