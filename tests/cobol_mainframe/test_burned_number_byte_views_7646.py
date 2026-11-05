"""#7646 (registers C6 / C7): no burned program is stopped by a COMP-1 / COMP-2 / COMP-5 byte-view refusal.

The HFP byte view (an X item over a float, a group moved to a differently laid group, a reference modification) is
refused by name because IBM's bytes are not the oracle's. Estate policy section 2 says nothing is built for a construct
no burned program reads; this pins that fact. Every burned program that declares a float (CBSA BNK1CAC, BANKDATA,
CRECUST and others, DBB EPSMPMT) is translated, and the async credit-card pair (the burned COMP-5 programs that take
no external CALL) under the `zos_comp5` switch; none may carry a hole that names the bytes of a float or COMP-5 item.
A burned program that starts to read those bytes fails here until the byte view is modelled or the hole is accounted.
The CardDemo IMS trio is pinned by test_det_zos_comp5.py. Other holes of these programs are out of scope here.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", Path(__file__).resolve().parents[2] / ".mainframe_corpora"))
CBSA = CORPORA / "cics-banking-sample-application-cbsa/src/base"
BMS = CORPORA / "_bms/cics-banking-sample-application-cbsa"  # the generated map copybooks
DBB = CORPORA / "dbb-mortgage-application/zBuilder/MortgageApplication"
ASYNC = CORPORA / "cics-async-api-credit-card-application-example/src"
FLOAT = re.compile(r"(?<![A-Z0-9-])\d\d\s+[A-Z][A-Z0-9-]*\s+(?:USAGE\s+(?:IS\s+)?)?COMP(?:UTATIONAL)?-[12]\s*[.\s]", re.I)
# the refusal texts of Gen.field_expr / check_record_bytes / cond_field for a float or COMP-5 byte use
BYTE_HOLE = re.compile(r"its bytes hold \S+ COMP-[125]|the bytes of a COMP-[125] item|the record holds \S+ COMP-[125]", re.I)

PROGRAMS = [(CBSA / "cobol_src" / f"{n}.cbl", [CBSA / "cobol_copy", BMS], False)
            for n in ("BNK1CAC", "BNK1CRA", "BNK1UAC", "BANKDATA", "BNK1TFN", "CRECUST")]  # fmt: skip
PROGRAMS += [(DBB / "cobol/epsmpmt.cbl", [DBB / "copybook"], False)]
PROGRAMS += [(ASYNC / f"{n}.cbl", [ASYNC], True) for n in ("ASYNCPNT", "SEQPNT")]


def _translate(src: Path, copy_dirs: list[Path], zos_comp5: bool, tmp_path: Path):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    return P.translate(src, [d for d in copy_dirs if d.is_dir()], "public class NdbService {\n}\n", "p", None,
                       tmp_path, zos_comp5=zos_comp5)  # fmt: skip


def test_the_byte_hole_pattern_matches_the_translator_texts():
    for text in ("F: its bytes hold FV COMP-5, as a group holding it (x)", "F: the bytes of a COMP-2 item (x)",
                 "READ: the record holds F COMP-1 (x)"):  # fmt: skip
        assert BYTE_HOLE.search(text), text
    assert not BYTE_HOLE.search("X: its bytes hold nothing of note")


@pytest.mark.parametrize(("src", "copy_dirs", "zos_comp5"), PROGRAMS, ids=[p[0].stem for p in PROGRAMS])
def test_no_burned_program_is_refused_for_the_bytes_of_a_number(src, copy_dirs, zos_comp5, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    if not src.is_file():
        pytest.skip(f"{src.name} is not available (GITGALAXY_MAINFRAME_CORPORA)")
    r = _translate(src, copy_dirs, zos_comp5, tmp_path)
    byte_holes = [h for h in r.stats["holes"] if BYTE_HOLE.search(h)]
    assert not byte_holes, byte_holes


def test_the_float_programs_listed_are_every_burned_one_declaring_a_float():
    """The list above is the census of test_hfp_burned_float_census.py, not a sample."""
    from gitgalaxy.core.source_text import read_source

    seen = set()
    for base in (CBSA / "cobol_src", DBB / "cobol"):
        if not base.is_dir():
            pytest.skip("the burned CBSA / DBB corpora are not checked out")
        for p in sorted(base.iterdir()):
            if p.suffix.lower() in (".cbl", ".cob") and FLOAT.search(read_source(p).text):
                seen.add(p)
    assert seen <= {p[0] for p in PROGRAMS}, sorted(p.name for p in seen - {q[0] for q in PROGRAMS})
