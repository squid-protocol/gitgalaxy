"""#5233: GSAM PCBs in the burned CardDemo IMS estate. Only DBUNLDGS uses GSAM, in load mode (PROCOPT LS, ISRT with no
SSA); no burned program reads a GSAM file (PROCOPT G), so that stays refused by name. This pins both facts: a later
program or PSB that needs GSAM read fails here, and so does a dropped refusal or rule."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ei  # noqa: E402

APP = "aws-mainframe-modernization-carddemo/app/app-authorization-ims-db2-mq"
RUNTIME = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/dli/DetDli.java"
GSAM_PSBS = {"DLIGSAMP.PSB"}


def _app() -> Path:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    app = corpora / APP
    if not app.is_dir():
        pytest.skip("the CardDemo corpus is not available")
    return app


def test_every_burned_gsam_pcb_is_a_load_mode_pcb_and_only_one_psb_has_any():
    app = _app()
    with_gsam: set[str] = set()
    for psb in sorted((app / "ims").iterdir()):
        if psb.suffix.lower() != ".psb":
            continue
        rows = ei.ims_gen_macros(read_source(psb).text)
        gsam = [r for r in rows if r["kind"] == "PCB" and (r["pcb_type"] or "").upper() == "GSAM"]
        if gsam:
            with_gsam.add(psb.name)
        for r in gsam:
            assert (r["procopt"] or "").upper() == "LS", (psb.name, r["procopt"])
    assert with_gsam == GSAM_PSBS


def test_dbunldgs_only_inserts_into_its_gsam_pcbs():
    text = read_source(_app() / "cbl" / "DBUNLDGS.CBL").text
    code = "\n".join(ln[6:72] for ln in text.splitlines() if len(ln) > 6 and ln[6] not in "*/")
    calls = re.findall(r"CALL\s+'CBLTDLI'\s+USING\s+(FUNC-\w+)\s+(\w+)((?:\s+[\w-]+)*?)\s*\.", code, re.S)
    gsam = [(fn, pcb, rest.split()) for fn, pcb, rest in calls if pcb in ("PASFLPCB", "PADFLPCB")]
    assert sorted(pcb for _, pcb, _ in gsam) == ["PADFLPCB", "PASFLPCB"]
    for fn, _, rest in gsam:
        assert fn == "FUNC-ISRT" and len(rest) == 1, (fn, rest)  # one I/O area, no SSA
    assert {fn for fn, pcb, _ in calls if pcb == "PAUTBPCB"} == {"FUNC-GN", "FUNC-GNP"}


def test_a_gsam_pcb_that_reads_is_refused_by_name_and_the_load_rule_is_in_the_runtime():
    dbd = "         DBD     NAME=G,ACCESS=(GSAM,BSAM)\nDSG001   DATASET DD1=IN,DD2=OUT,RECORD=(100),RECFM=F\n         DBDGEN\n"
    gen = "         PSBGEN  PSBNAME=P,LANG=COBOL\n"
    db = {"G": ei.dbd(dbd, "G.dbd")}
    ok = ei.psb("G        PCB     TYPE=GSAM,DBDNAME=G,PROCOPT=LS\n" + gen, "P.psb", db)
    assert [p["gsam"] for p in ok] == [100]
    for procopt in ("G", "GO", "GS", "A"):
        with pytest.raises(ei.Unsupported, match="reading a GSAM file is not"):
            ei.psb(f"G        PCB     TYPE=GSAM,DBDNAME=G,PROCOPT={procopt}\n" + gen, "P.psb", db)
    assert "[rule RT-DLI-GSAM]" in RUNTIME.read_text(encoding="utf-8")
