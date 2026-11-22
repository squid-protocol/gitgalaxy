"""#8413: IBM-written answers for the GDG DDs of a library procedure that calls another, under JOB RESTART.

`tests/equivalence/jcl/gdg/nested.json` holds the JCL, the two JCLLIB library members (OUTR calls INNR between its
steps) and the answers: the absolute generation each GDG DD names and the catalog after the run, written from the JCL
User's Guide (Appendix A, generation data sets) and the JCL Reference (JOB: RESTART) BEFORE the resolver saw a nested
call's DDs. A nested step is named CALLSTEP.PROCSTEP (ASSUMED A2, `restart/nested.json`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitgalaxy.core import job_flow
from gitgalaxy.core.jcl_gdg import JclGdgRefused
from gitgalaxy.core.jcl_proc import JclProcRefused
from gitgalaxy.core.jcl_restart import resolve_gdg_restart

ROOT = Path(__file__).resolve().parents[2]
DOC = json.loads((ROOT / "tests" / "equivalence" / "jcl" / "gdg" / "nested.json").read_text(encoding="utf-8"))
TEXT = "\n".join(DOC["library_jcl"]) + "\n"
ROWS = job_flow.jcl_job_flow(TEXT)
LIBS = {lib: {m: "\n".join(ls) + "\n" for m, ls in ms.items()} for lib, ms in DOC["libraries"].items()}
CAT = {"PAY.GDG": {"limit": 6, "generations": [6, 7]}}


def test_every_nested_gdg_case_line_fits_columns_1_to_72():
    members = [ln for ms in DOC["libraries"].values() for ls in ms.values() for ln in ls]
    assert all(len(ln) <= 72 for ln in DOC["library_jcl"] + members)


def test_the_scenarios_cover_a_restart_before_inside_and_after_the_inner_call():
    ids = " ".join(s["id"] for s in DOC["scenarios"])
    for word in ("restart-first-step", "after-the-inner-call", "checkpoint"):
        assert word in ids, word
    assert all(s["basis"] for s in DOC["scenarios"])


@pytest.mark.parametrize("sc", DOC["scenarios"], ids=lambda s: s["id"])
def test_the_resolver_reproduces_every_nested_procedure_gdg_restart_answer(sc):
    names, after = resolve_gdg_restart(ROWS, sc["job"], sc["catalog"], sc["given"], TEXT, LIBS)
    assert names == sc["expect"], sc["id"]
    assert after == sc["catalog_after"], sc["id"]


@pytest.mark.parametrize("r", DOC["refused"], ids=lambda r: r["id"])
def test_a_nested_gdg_restart_that_is_not_answered_is_refused_by_name(r):
    with pytest.raises((JclGdgRefused, JclProcRefused), match=r["match"]):
        resolve_gdg_restart(ROWS, r["job"], CAT, r["given"], TEXT, LIBS)
