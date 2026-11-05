"""#7646 (register C7): a case declaring comp5_byte_order is ported with COMP-5 held big-endian (translate(zos_comp5=True)),
and an undeclared one is not. The three IMS batch cases (CALL 'CBLTDLI') carry the declaration and translate whole."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[1]))

import det_port  # noqa: E402

IMS_CASES = ["carddemo-paudblod", "carddemo-paudbunl", "carddemo-dbunldgs"]


def test_the_declaration_selects_the_zos_byte_order():
    assert det_port._zos_comp5({"declared_differences": ["comp5_byte_order"]})
    assert not det_port._zos_comp5({})
    assert not det_port._zos_comp5({"declared_differences": []})


def test_the_ims_cases_declare_it():
    import equivalence as eq

    for name in IMS_CASES:
        assert det_port._zos_comp5(eq.load_case(name)), name


@pytest.mark.parametrize("name", IMS_CASES)
def test_the_ims_cases_translate_whole_under_the_declaration(name, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import equivalence as eq

    case = eq.load_case(name)
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))
    corpus = root / case["corpus"]
    if not corpus.is_dir():
        pytest.skip(f"corpus {case['corpus']} not available")
    out = det_port.port_case(name, tmp_path, det_port.estate(corpus, tmp_path), corpus)
    assert out.get("translated", True), out
    assert out["holes"] == [], out
    assert "COMP-5" not in str(out.get("error", ""))
