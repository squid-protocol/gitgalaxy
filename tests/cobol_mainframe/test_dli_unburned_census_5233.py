"""#5233 (register I5), checklist [c:51f08617]: the DL/I members no burned program needs -- AIBTDLI, the FLD / POS / INQY
calls, secondary indexes (XDFLD, PROCSEQ), logical relationships, HDAM / PHDAM / DEDB access -- stay refused by name, and
this census pins that no burned estate source, DBD or PSB uses them: one that starts to must fail here first.

CardDemo's DBPAUTP0 / DBPAUTX0 pair is a HIDAM primary index (LCHILD POINTER=INDX), which the engine does not model as a
hierarchy and a case never loads; it is not a secondary index and the census allows exactly that pair."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_ims as ei  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
BURNED = ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp",
          "dbb-mortgage-application", "zecs", "cics-async-api-credit-card-application-example"]  # fmt: skip
EXTS = {".cbl", ".cob", ".cpy", ".dbd", ".psb", ".jcl", ".asm", ".mac"}
IMS = CORPORA / "aws-mainframe-modernization-carddemo" / "app" / "app-authorization-ims-db2-mq" / "ims"
HEAD = "         DBD     NAME=X,ACCESS=(HIDAM,VSAM)\n"
SEGM = "         SEGM    NAME=R,PARENT=0,BYTES=10\n"
KEY = "         FIELD   NAME=(K,SEQ,U),START=1,BYTES=2,TYPE=C\n"
# a member's regex per census row; quote-bounded so a paragraph or data name that contains the word is not a hit
MEMBERS = {
    "AIBTDLI": r"AIBTDLI",
    "FLD / POS / INQY call": r"(?:'|\")(?:FLD |POS |INQY)(?:'|\")",
    "XDFLD (secondary index)": r"\bXDFLD\b",
    "PROCSEQ (secondary index)": r"\bPROCSEQ\b",
    "logical relationship": r"\bPAIR\s*=|\bLPARENT\b|POINTER\s*=\s*\(?\s*(?:SNGL|DBLE|SYMB|LPARNT)",
    "HDAM / PHDAM / DEDB / logical DBD": r"ACCESS\s*=\s*\(\s*(?:P?HDAM|DEDB|LOGICAL)\b|\bPHDAM\b|\bDEDB\b",
}


def _code(text: str) -> str:
    """Source with its comment lines dropped (column 7 of COBOL, column 1 of an assembler / DBD line)."""
    return "\n".join(ln for ln in text.splitlines() if ln[:1] != "*" and not (len(ln) > 6 and ln[6] in "*/")).upper()


def _sources():
    for name in BURNED:
        for p in sorted((CORPORA / name).rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTS:
                yield p, _code(read_source(p).text)


@pytest.fixture(scope="module")
def census():
    if not (IMS / "DBPAUTP0.dbd").is_file():
        pytest.skip("the burned corpora are not checked out (GITGALAXY_MAINFRAME_CORPORA)")
    files = list(_sources())
    assert any(p.name.upper() == "PAUDBLOD.CBL" for p, _ in files), "the CardDemo IMS programs were not scanned"
    return files


@pytest.mark.parametrize("member", sorted(MEMBERS))
def test_no_burned_source_uses_a_member_the_model_refuses(census, member):
    hits = [p.name for p, text in census if re.search(MEMBERS[member], text)]
    assert hits == [], f"{member} is now used by a burned program ({hits}): model it, then drop its refusal"


def test_the_only_lchild_in_the_burned_estates_is_the_hidam_primary_index(census):
    rows = [(p.name.upper(), m) for p, text in census for m in re.findall(r"\bLCHILD\b[^\n]*(?:\n[^\n]*)?", text)]
    assert sorted({n for n, _ in rows}) == ["DBPAUTP0.DBD", "DBPAUTX0.DBD"], rows
    assert all(re.search(r"POINTER=INDX?\b|\bINDEX=", m) for _, m in rows), rows


def test_the_primary_index_dbd_pair_is_read_but_the_index_database_is_no_hierarchy():
    if not (IMS / "DBPAUTP0.dbd").is_file():
        pytest.skip("the burned corpora are not checked out")
    d = ei.dbd((IMS / "DBPAUTP0.dbd").read_text(encoding="latin-1"), "DBPAUTP0.dbd")
    assert d["name"] == "DBPAUTP0"
    with pytest.raises(ei.Unsupported, match="ACCESS=INDEX"):
        ei.dbd((IMS / "DBPAUTX0.dbd").read_text(encoding="latin-1"), "DBPAUTX0.dbd")


@pytest.mark.parametrize(
    "text, why",
    [
        (HEAD.replace("HIDAM", "HDAM") + SEGM + KEY, "ACCESS=HDAM"),
        (HEAD.replace("HIDAM", "PHDAM") + SEGM + KEY, "ACCESS=PHDAM"),
        (HEAD.replace("HIDAM", "DEDB") + SEGM + KEY, "ACCESS=DEDB"),
        (HEAD.replace("HIDAM", "INDEX") + SEGM + KEY, "ACCESS=INDEX"),
        (HEAD + SEGM + KEY + "         LCHILD  NAME=(I,XD),POINTER=INDX\n         XDFLD   NAME=XF,SRCH=K\n",
         "XDFLD (a secondary index)"),
        (HEAD + SEGM + KEY + "XF       XDFLD   NAME=XF,SRCH=K\n", "XDFLD (a secondary index)"),
        (HEAD + SEGM + KEY + "         LCHILD  NAME=(L,Y),POINTER=SNGL,PAIR=P\n", "not a primary index"),
        (HEAD + SEGM + KEY + "         LCHILD  NAME=(L,Y),POINTER=DBLE\n", "not a primary index"),
    ],
)  # fmt: skip
def test_a_dbd_with_one_of_these_members_is_refused_by_name(text, why):
    with pytest.raises(ei.Unsupported, match=re.escape(why)):
        ei.dbd(text, "X.dbd")


def test_a_primary_index_lchild_and_a_commented_xdfld_are_accepted():
    ok = HEAD + SEGM + KEY + "         LCHILD  NAME=(I,XD),POINTER=INDX\n*        XDFLD   NAME=XF,SRCH=K\n"
    assert ei.dbd(ok, "X.dbd")["name"] == "X"


def test_a_pcb_with_procseq_is_refused_by_name():
    psb = ("         PCB     TYPE=DB,DBDNAME=X,PROCOPT=G,KEYLEN=2,PROCSEQ=XD\n         SENSEG  NAME=R\n"
           "         PSBGEN  PSBNAME=P,LANG=COBOL\n")  # fmt: skip
    dbds = {"X": {"segments": [{"name": "R", "fields": []}]}}
    with pytest.raises(ei.Unsupported, match="PROCSEQ"):
        ei.psb(psb, "P.psb", dbds)


def test_aibtdli_is_refused_by_name_in_a_det_port():
    from gitgalaxy.tools.cobol_to_java.det import dli

    assert "AIBTDLI" in dli.REFUSED_BY_NAME and "not modelled" in dli.REFUSED_BY_NAME["AIBTDLI"]
    gen = Path(dli.__file__).with_name("gen.py").read_text(encoding="utf-8")
    assert "*dli.REFUSED_BY_NAME" in gen


@pytest.mark.parametrize("fn", ["FLD ", "POS ", "INQY"])
def test_fld_pos_and_inqy_are_refused_by_name_on_both_runtimes(fn):
    java = (ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/dli/DetDli.java").read_text(encoding="utf-8")
    c = (ROOT / "tests/equivalence/ims/ggdli.c").read_text(encoding="utf-8")
    assert f'"{fn}"' in java.split("OTHER = List.of(", 1)[1].split(");", 1)[0]
    assert fn in c, fn


# the SSA members of the same census: only a program that issues DL/I can carry one
DLI_USERS = r"CBLTDLI|CEETDLI|EXEC\s+DLI"
SSA_MEMBERS = {
    "# (independent AND) operator": r"'#'",
    "subset-pointer command code (M R S W Z 1-9)": r"'[A-Z0-9 ]{8}\*[A-Z0-9-]*[MRSWZ1-9][A-Z0-9-]*[ (]",
}


@pytest.mark.parametrize("member", sorted(SSA_MEMBERS))
def test_no_burned_dli_program_uses_an_ssa_member_the_model_refuses(census, member):
    hits = [p.name for p, text in census
            if re.search(DLI_USERS, text) and re.search(SSA_MEMBERS[member], text)]  # fmt: skip
    assert hits == [], f"{member} is now used by a burned program ({hits}): model it, then drop its refusal"


@pytest.mark.parametrize("member", sorted(SSA_MEMBERS))
def test_the_ssa_census_patterns_match_what_they_name(member):
    sample = {"# (independent AND) operator": "VALUE '#'",
              "subset-pointer command code (M R S W Z 1-9)": "VALUE 'DEPT    *M '"}  # fmt: skip
    assert re.search(SSA_MEMBERS[member], sample[member])
    assert not re.search(SSA_MEMBERS[member], "VALUE 'DEPT    *L '")


def test_the_oracle_refuses_what_the_census_names():
    c = (ROOT / "tests/equivalence/ims/ggdli.c").read_text(encoding="utf-8")
    assert "the independent AND operator (#)" in c
    assert 'snprintf(what, sizeof what, "the command code %c"' in c
