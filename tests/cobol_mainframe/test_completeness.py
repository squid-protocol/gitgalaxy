"""
#3498: the mainframe skeleton-completeness report (GalaxyIR.completeness and
tools/cobol_to_cobol/completeness_report.py): each channel's resolved / total, the
system names that are not gaps, the gaps that map to a missing estate input, and
the pinned numbers of the three answer-keyed corpora.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.completeness_report import render_markdown
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mainframe_corpus as mc  # noqa: E402

BATCH = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BATCH1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A               PIC X(4).
       COPY MISSCPY.
       COPY DFHAID.
       PROCEDURE DIVISION.
           CALL 'NOTHERE' USING WS-A.
           CALL 'CEE3ABD'.
           CALL WS-A.
           GOBACK.
"""
ORPHAN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORPHAN1.
       PROCEDURE DIVISION.
           GOBACK.
"""
RUN = """\
//RUNJOB   JOB (1),'X'
//S1       EXEC PGM=BATCH1
//S2       EXEC PGM=IEFBR14
"""


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("completeness")
    repo = base / "estate"
    for rel, text in {"cbl/BATCH1.cbl": BATCH, "cbl/ORPHAN1.cbl": ORPHAN, "jcl/RUNJOB.jcl": RUN}.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_channels_split_system_names_from_gaps(estate):
    report = estate.completeness()
    calls = report["channels"]["program calls"]
    # BATCH1 run by JCL resolves; IEFBR14 and CEE3ABD are IBM's; NOTHERE is missing; CALL WS-A is dynamic.
    assert (calls["resolved"], calls["system"]) == (1, 2)
    assert calls["gaps"]["missing program"] == 1 and calls["gaps"]["dynamic target"] == 1
    copies = report["channels"]["copybooks"]
    assert (copies["resolved"], copies["total"], copies["system"], copies["gaps"]["missing copybook"]) == (0, 1, 1, 1)
    batch = report["channels"]["batch entry"]
    assert (batch["resolved"], batch["total"]) == (1, 2)  # ORPHAN1: no JCL step runs it
    inputs = {m["input"]: m for m in report["missing_inputs"]}
    assert inputs["copybook libraries"]["examples"] == ["MISSCPY (cbl/BATCH1.cbl)"]
    assert inputs["JCL and PROC libraries"]["examples"] == ["cbl/ORPHAN1.cbl"]
    assert any(e.startswith("NOTHERE") for e in inputs["application programs (source or load-module list)"]["examples"])
    assert report["channels"]["transactions"]["ratio"] is None  # no CICS here: left out of the score
    assert 0 < report["score"] < 1


def test_markdown_lists_every_channel_and_input(estate):
    md = render_markdown(estate.completeness(), "estate")
    assert "| program calls | 1 |" in md and "**copybook libraries**: 1" in md and "`MISSCPY (cbl/BATCH1.cbl)`" in md


# Channel (resolved, total) per corpus, at the pinned refs -- a change is either an
# engine improvement (re-pin) or a regression.
PINNED = {
    "aws-mainframe-modernization-carddemo": {
        "program calls": (63, 82), "copybooks": (173, 173), "transactions": (62, 73), "screens": (42, 47),
        "data flows": (4933, 5042), "IMS PSBs": (7, 7), "batch entry": (11, 17),
    },
    "cics-banking-sample-application-cbsa": {
        "program calls": (140, 140), "copybooks": (88, 88), "transactions": (40, 47), "screens": (36, 37),
        "data flows": (4735, 4736), "IMS PSBs": (0, 0), "batch entry": (0, 1),
    },
    "zopeneditor-sample": {
        "program calls": (4, 6), "copybooks": (6, 6), "transactions": (0, 0), "screens": (0, 0),
        "data flows": (327, 374), "IMS PSBs": (0, 0), "batch entry": (3, 3),
    },
}  # fmt: skip


@pytest.mark.parametrize("corpus", mc.load_manifest(), ids=lambda c: c["name"])
def test_pinned_corpus_completeness(corpus):
    """Local only: skipped unless the corpus is fetched at its pin."""
    if not (mc.clone_path(corpus) / ".git").exists():
        pytest.skip(f"{corpus['name']} not fetched (mainframe_corpus.py fetch)")
    report = load_galaxy_ir(mc.scan(corpus)).completeness()
    got = {name: (ch["resolved"], ch["total"]) for name, ch in report["channels"].items()}
    assert got == PINNED[corpus["name"]]
