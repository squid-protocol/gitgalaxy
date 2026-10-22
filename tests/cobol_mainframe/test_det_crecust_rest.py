"""#4884 (rest of CBSA CRECUST): CEELOCT's runtime model, EXEC CICS FETCH ANY / FETCH CHILD NOSUSPEND with
DFHRESP(NOTFINISHED), and RUN TRANSID CHANNEL."""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

pytest.importorskip("tree_sitter_language_pack")

import test_det_translate as T  # noqa: E402

from gitgalaxy.standards.cics.resp import DFHRESP  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import gen as G  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402


def test_notfinished_is_resp_113():
    # IBM CICS TS, FETCH ANY / FETCH CHILD: NOTFINISHED RESP 113
    assert DFHRESP["NOTFINISHED"] == 113
    from decimal import Decimal

    assert E.parse_condition("R = DFHRESP(NOTFINISHED)") == E.Rel("=", E.Ref("R"), E.Lit(Decimal(113)))


def test_fetch_any_nosuspend_writes_what_the_child_left_on_normal():
    """#4950: on NORMAL the token (ANY), the reply channel (CHANNEL), the abend code (ABCODE, only for an abended child)
    and COMPSTATUS's CVDA are written; on any other condition, nothing."""
    out = T._ChanCics().command("FETCH ANY(TKN) CHANNEL(CH) NOSUSPEND COMPSTATUS(ST) ABCODE(AB) RESP(R) RESP2(R2)", "")
    assert out[0] == 'CicsTask.FetchResult fetch1 = task.fetch(null, "NOSUSPEND", 0, true);'
    assert (
        out[1] == "if (fetch1.child() != null) {" and out[-1] == "OUTCOME(DetCics.resp(fetch1.resp()), fetch1.resp2());"
    )
    assert any("fetch1.channel()" in ln for ln in out) and any("fetch1.abcode() != null" in ln for ln in out)


def test_fetch_child_names_its_token():
    out = T._ChanCics().command("FETCH CHILD(TKN) NOSUSPEND RESP(R) RESP2(R2)", "")
    assert out[0] == 'CicsTask.FetchResult fetch1 = task.fetch(TKN.strip(), "NOSUSPEND", 0, false);'


@pytest.mark.parametrize(
    "text, mode",
    [
        ("FETCH ANY(TKN) RESP(R)", '"WAIT", 0'),  # #4950: it waits -- the children not yet run are dispatched
        ("FETCH CHILD(TKN) RESP(R)", '"WAIT", 0'),
        ("FETCH ANY(TKN) TIMEOUT(5) RESP(R)", '"TIMEOUT", 5'),
        ("FETCH CHILD(TKN) TIMEOUT(5)", '"TIMEOUT", 5'),
    ],
)
def test_a_fetch_that_waits_or_times_out_is_modelled(text, mode):
    assert f"{mode}, false);" in T._ChanCics().command(text, "")[0]


def test_nosuspend_and_timeout_together_are_refused():
    with pytest.raises(C.CicsError, match="FETCH NOSUSPEND and TIMEOUT together"):
        T._ChanCics().command("FETCH ANY(TKN) NOSUSPEND TIMEOUT(5)", "")


def test_run_channel_is_the_childs_copy_by_name():
    out = T._ChanCics().command("RUN TRANSID('GT24') CHANNEL(CH) CHILD(REC) RESP(R) RESP2(R2)", "")
    assert out[0] == "CicsTask.RunResult run1 = task.runTransid('GT24'.strip(), CH.strip());"


def test_free_child_is_modelled():
    """#4950: FREE CHILD(token) on CicsTask.freeChild (it was refused under the name FREE)."""
    out = T._ChanCics().command("FREE CHILD(TKN) RESP(R)", "")
    assert out == ["CicsTask.FetchResult freed1 = task.freeChild(TKN.strip());",
                   "OUTCOME(DetCics.resp(freed1.resp()), freed1.resp2());"]  # fmt: skip


def test_ceeloct_reads_the_runs_clock_and_stores_its_seconds_by_value():
    assert G.LIBRARY["CEELOCT"][1] == 4 and "CEELOCT" in G.LIBRARY_CLOCK
    java = (Path(P.__file__).parent / "cobolrt/le/Ceeloct.java").read_text(encoding="utf-8")
    assert "Cobol.store(seconds" in java and "civil(1582, 10, 14)" in java


@pytest.mark.skipif(not shutil.which("gcc"), reason="needs a C compiler")
def test_the_ceeloct_model_against_the_calendar(tmp_path):
    """Lilian days since 14 October 1582 (IBM), the Gregorian string and the seconds, from the pinned clock; refuses
    without one."""
    (tmp_path / "t.c").write_text(
        "#include <stdio.h>\n#include <string.h>\n"
        "int CEELOCT(unsigned char*, unsigned char*, unsigned char*, unsigned char*);\n"
        "int main(void) { unsigned char l[4], s[8], g[18], fc[12]; double d; memset(fc, 7, 12);\n"
        "CEELOCT(l, s, g, fc); memcpy(&d, s, 8); g[17] = 0;\n"
        'printf("%ld %.2f %s %d\\n", ((long)l[0] << 24) | (l[1] << 16) | (l[2] << 8) | l[3], d, g, fc[0] | fc[11]);'
        " return 0; }\n"
    )
    src = ROOT / "tests/equivalence/le/ceeloct.c"
    run = subprocess.run(  # noqa: S603
        ["gcc", "-o", str(tmp_path / "t"), str(tmp_path / "t.c"), str(src)], capture_output=True, text=True, check=False
    )
    assert run.returncode == 0, run.stderr
    ok = subprocess.run(  # noqa: S603
        [str(tmp_path / "t")], env={"COB_CURRENT_DATE": "2026/10/01 10:30:15.25"}, capture_output=True, text=True
    )
    days = (datetime.date(2026, 10, 1) - datetime.date(1582, 10, 14)).days
    secs = days * 86400 + 10 * 3600 + 30 * 60 + 15
    assert ok.stdout.split() == [str(days), f"{secs}.25", "20261001103015250", "0"], ok
    bare = {k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ} if os.name == "nt" else {}  # no clock pinned
    refused = subprocess.run([str(tmp_path / "t")], env=bare, capture_output=True, text=True)  # noqa: S603
    assert refused.returncode == 98 and "not modelled" in refused.stderr


def test_a_fetch_is_compared_by_what_it_answered():
    """#4950 (X18 ASSUMED, no longer DIFFERS): the children run at their parent's waits on both runtimes, so a FETCH is
    compared like any event -- equal when both answered the same, a difference when the child fetched differs."""
    import equivalence_cics as ec

    ev = [{"event": "FETCH", "resp": "NORMAL", "resp2": 0, "child": "GGCHILD000000002", "compstatus": "NORMAL",
           "abcode": None, "channel": "GGREPLY000000001"}]  # fmt: skip
    assert ec.compare_events(ev, [dict(ev[0])])["equal"] == 1
    d = ec.compare_events(ev, [dict(ev[0], child="GGCHILD000000001")])
    assert d["equal"] == 0 and d["diffs"][0]["fields"] == [
        {"field": "child", "cobol": "GGCHILD000000002", "java": "GGCHILD000000001"}
    ]
