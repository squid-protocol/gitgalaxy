"""#5857: the CardDemo CBPAUP0C equivalence case (a BMP entered USING its I/O PCB and DB PCB, EXEC DLI GN / GNP / DLET /
CHKP on the corpus's own DBPAUTP0 unload). The unit tests need nothing but the case; the proof itself (GnuCOBOL against
the det port) is the det sweep's, `det_port.py run carddemo-cbpaup0c`."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ims  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-cbpaup0c"
APP = "app/app-authorization-ims-db2-mq"


def _case() -> dict:
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def _corpus() -> Path | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    return corpus if (corpus / APP / "cbl/CBPAUP0C.cbl").is_file() else None


def test_the_case_states_the_step_its_card_and_its_database():
    case = _case()
    assert (case["program"], case["job"], case["step"]) == ("CBPAUP0C", "CBPAUP0J", "STEP01")
    assert case["sysin"][:2].isdigit() and case["datasets"] == {}  # PRM-INFO: expiry days first; no files
    assert case["ims"]["psb"].endswith("PSBPAUTB.psb") and case["ims"]["compare"] == ["DBPAUTP0"]
    assert set(case["ims"]["segments"]) == {"PAUTSUM0", "PAUTDTL1"}
    assert "Apache" in (CASE / "NOTICE").read_text(encoding="utf-8")


def test_the_corpus_program_is_a_bmp_whose_psb_is_cmpat_yes():
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    case = _case()
    source = (corpus / case["program_source"]).read_text(encoding="latin-1")
    assert ims.bmp_using(source) == ["IO-PCB-MASK", "PGM-PCB-MASK"]
    _, pcbs = ims.definitions(case, corpus, bmp=True)
    assert len(pcbs) == 1
    with pytest.raises(ims.Unsupported, match="CMPAT=YES"):
        ims.definitions(case, corpus)  # not a BMP: refused by name
    # the database diff reads the DBDs alone, whatever the PSB asks of the entry
    assert [s["name"] for s in ims.dbd_definitions(case, corpus)["DBPAUTP0"]["segments"]] == ["PAUTSUM0", "PAUTDTL1"]


def test_the_bmp_source_lowers_every_exec_dli_to_a_call():
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    source = (corpus / _case()["program_source"]).read_text(encoding="latin-1")
    out = ims.rewrite_bmp(source)
    assert "EXEC DLI" not in out.upper()
    assert out.count("CALL 'GGDLICHKP'") == 1 and "GGDLIX" in out
