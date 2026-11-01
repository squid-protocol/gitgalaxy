"""#5274: a program that takes no COMMAREA, and a scenario's stated COMMAREA length (X23). Split out of test_equivalence_cics.py, which every CICS slice appended to."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
from cics_test_cases import facade_case as _facade_case  # noqa: E402


# ---- #4270: a program that takes no COMMAREA; a scenario's stated COMMAREA length (X23) ---------------------------
def test_a_case_says_its_program_takes_no_commarea(tmp_path):
    """#4270 (the async credit-card services: an empty LINKAGE SECTION, a det service handleLink()): `"commarea": null`
    describes no COMMAREA -- no fields, no DTO, EIBCALEN 0 on both sides. A case that says nothing, or an empty
    segment list, is refused by name (it was a KeyError / IndexError), and so is a scenario that gives one anyway."""
    assert ec.commarea_fields(tmp_path, {"commarea": None}) == []
    with pytest.raises(ec.Unsupported, match='"commarea": null for a program that takes none'):
        ec.commarea_fields(tmp_path, {})
    with pytest.raises(ec.Unsupported, match="describes nothing"):
        ec.commarea_fields(tmp_path, {"commarea": {"segments": []}})
    svc = tmp_path / "GetpolService.java"
    svc.write_text("public class GetpolService {\n    public void handleLink() {\n    }\n}\n", encoding="utf-8")
    assert ec.commarea_class({"commarea": None}, tmp_path, svc) is None
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {}, "commarea": None, "linked": True}
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert "Object commarea = null;" in java and "treeToValue" not in java
    assert "ScreenModel" not in java  # an estate with no BMS map has no screen view models (dto.screen)
    assert 'm = method(service, "handleLink", 0);' in java  # the facade side enters handleLink() itself


@pytest.mark.parametrize("sig", ["handleTransaction(String transid, Object request)", "handleLink(Object request)"])
def test_an_object_service_carries_the_cases_commarea_record_dto(tmp_path, sig):
    """#6072: a service typed `Object` (PCCONF, PCDETL, PCIMMA) still carries the DTO of the case's COMMAREA record when
    the case states one and the forge generated it; otherwise no DTO (an HLASM facade, #5859; a case with none)."""
    svc = tmp_path / "PcconfService.java"
    svc.write_text(f"public class PcconfService {{\n    public Object {sig} {{\n    }}\n}}\n", encoding="utf-8")
    typed = {"program": "PCCONF", "commarea": {"segments": [{"copybook": "PCCONF.cbl", "record": "WS-STATE"}]}}
    assert ec.commarea_class(typed, tmp_path, svc) is None  # the DTO was not generated
    # a shared copybook record is named bare; the program's own record after its declarer (PcconfWsState), and the
    # service also imports the XCTL target's PcwizWsState: the case program's own wins
    (tmp_path / "WsState.java").write_text("public class WsState {}", encoding="utf-8")
    assert ec.commarea_class(typed, tmp_path, svc) == "WsState"
    for dto in ("PcwizWsState", "PcconfWsState"):
        (tmp_path / f"{dto}.java").write_text(f"public class {dto} {{}}", encoding="utf-8")
    svc.write_text(
        "import x.dto.contract.PcwizWsState;\nimport x.dto.contract.PcconfWsState;\n" + svc.read_text(),
        encoding="utf-8",
    )
    assert ec.commarea_class(typed, tmp_path, svc) == "PcconfWsState"
    for none in ({"commarea": None}, {"commarea": {}}, {"commarea": {"segments": []}}, {}):
        assert ec.commarea_class(none, tmp_path, svc) is None


def test_a_typed_service_keeps_its_own_commarea_class(tmp_path):
    svc = tmp_path / "XService.java"
    svc.write_text("public void handleTransaction(String transid, XCa request) {}", encoding="utf-8")
    case = {"commarea": {"segments": [{"copybook": "X.cbl", "record": "OTHER"}]}}
    assert ec.commarea_class(case, tmp_path, svc) == "XCa"


def test_a_commarea_in_an_event_of_a_case_with_none_is_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 RETURN level=1 transid= len=4\n", encoding="ascii")
    (out / "001.bin").write_bytes(b"ABCD")
    with pytest.raises(ec.Unsupported, match="describes none"):
        ec.outputs(out, {"name": "x"}, tmp_path, [])


def test_a_scenario_states_a_commarea_shorter_than_its_record():
    """#4270 (X23): `"commarea_length": N` is EIBCALEN -- the caller passed the record's first N bytes and no more
    (GenApp's IF EIBCALEN < 91, its '98' returns). 0 to the record's length; never on a scenario with no COMMAREA."""
    fields = [{"name": "CA-A", "offset": 0, "bytes": 2}, {"name": "CA-B", "offset": 2, "bytes": 98}]
    assert ec.commarea_length({"name": "s", "commarea": {}}, fields) is None
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 60}, fields) == 60
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 100}, fields) == 100
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 0}, fields) == 0  # #4049: EIBCALEN 0
    for bad in (101, -1, "60", True, 6.0):
        with pytest.raises(ec.Unsupported, match="is not a length"):
            ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": bad}, fields)
    with pytest.raises(ec.Unsupported, match="with no COMMAREA"):
        ec.commarea_length({"name": "s", "commarea": None, "commarea_length": 10}, fields)


def test_the_driver_runs_the_program_on_the_area_the_stub_chose():
    """#4270 (X23): GGCAREA moves a COMMAREA of a stated length before a guard page; the driver passes whatever area
    it chose (LK-CA), and writes back from it."""
    drv = ec.cics_driver("PROG", True)
    assert "CALL 'GGCAREA' USING WS-PTR BY VALUE WS-LEN" in drv and "SET ADDRESS OF LK-CA TO WS-PTR" in drv
    assert "CALL 'PROG' USING LK-CA" in drv and "CALL 'GGCAOUT' USING LK-CA BY VALUE WS-LEN" in drv
    assert "CALL 'PROG'\n" in ec.cics_driver("PROG", False)
    assert all(len(ln) <= 72 for ln in drv.splitlines())


def test_a_padded_writeq_is_named_on_the_task_and_kept_out_of_its_display_log(tmp_path):
    """X6 (ASSUMED, owner 2026-10-21): the stub's line on the padded path names the WRITEQ on the task (so a proof
    states X6 for it) and is not part of the task's DISPLAY output, which the Java side never prints."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 RETURN level=1\n", encoding="ascii")
    (tmp_path / "stdout.txt").write_bytes(b"BEFORE\n" + ec.X6_PADDED_SAID.encode("ascii") + b"WRITEQ TD\nAFTER\n")
    res = ec.outputs(out, {"name": "x"}, tmp_path, [])
    assert res["x6_padded"] == ["WRITEQ TD"] and res["sysout"] == b"BEFORE\nAFTER\n"
    (tmp_path / "stdout.txt").write_bytes(b"BEFORE\n")
    assert "x6_padded" not in ec.outputs(out, {"name": "x"}, tmp_path, [])  # no padded WRITEQ, no key


def test_a_writeq_past_from_runs_on_padded_for_ts_and_td_and_a_huge_length_is_refused_x6():
    """X6 (ASSUMED): WRITEQ TS and WRITEQ TD alike write FROM then spaces when LENGTH runs past the item, and the task
    runs on (no judged-up-to stop); only a LENGTH over the pad record's 32767 bytes is still refused by name, and a
    literal FROM is left alone."""
    for what, stub in (("WRITEQ TS", "GGCWRTQ"), ("WRITEQ TD", "GGCWRTD")):
        call = ec._call(stub, ["BY REFERENCE WS-MSG"])
        got = "\n".join(ec._write_from("GG-LEN", "WS-MSG", what, call))
        assert f"DISPLAY '{ec.X6_PADDED_SAID}{what}'" in got and "BY REFERENCE GG-PADQ" in got
        assert got.count(f"DISPLAY '{what} LENGTH > FROM: not modelled'") == 1  # the over-32767 refusal, by name
        assert ec.x6_writeq_refusal(f"{what} LENGTH > FROM: not modelled")
        assert ec._write_from(None, "WS-MSG", what, call) == call  # no LENGTH: nothing past FROM
        assert ec._write_from("23", "'LITERAL'", what, call) == call


def test_no_case_says_a_writeq_past_from_is_refused():
    """#6271: since #6573 a WRITEQ whose LENGTH runs past FROM is written padded (X6) and the task is compared whole;
    only a LENGTH over 32767 is still refused. A case note or scenario `why` that says a task is judged up to a
    "refused WRITEQ" misstates that, in any case (LGSTSQ's error logger, LGICVS01's LOW / HIGH CUSTOMER items, ...)."""
    import json

    root = Path(__file__).resolve().parents[1] / "equivalence"
    cases = sorted(root.glob("*/case.json"))
    assert len(cases) > 100  # the glob found the corpus, not an empty directory
    stale = []
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps([case.get("notes"), [sc.get("why") for sc in case.get("scenarios", [])]])
        if "refused WRITEQ" in text:
            stale.append(path.parent.name)
    assert stale == [], stale
    for n in ("lgtestp1", "lgtestp2", "lgtestp3", "lgtestp4", "lgtestc1"):
        case = json.loads((root / f"genapp-{n}" / "case.json").read_text(encoding="utf-8"))
        assert "padded" in json.dumps([case.get("notes"), [sc.get("why") for sc in case["scenarios"]]]), n


def test_a_reference_past_a_stated_eibcalen_is_judged_up_to_it_x22(tmp_path):
    """#4270 (X23): the stub's guard-page stop is judged up to, as X6's WRITEQ is; the report says which assumption."""
    said = "COMMAREA past EIBCALEN: not modelled\n"
    assert ec.judged_refusal(said) == "COMMAREA past EIBCALEN: not modelled"
    assert ec.judged_refusal("WRITEQ TS LENGTH > FROM: not modelled") == "WRITEQ TS LENGTH > FROM: not modelled"
    assert ec.judged_refusal("START LENGTH > FROM: not modelled") is None
    (tmp_path / "s.x6").write_text("COMMAREA past EIBCALEN (60 bytes): not modelled", encoding="utf-8")
    ev = [{"event": "RETURN", "transid": None, "commarea": None}, {"event": "COMMAREA", "commarea": {"A": "1"}}]
    cev, jev, x = ec.x6_judged({"name": "s", "prefix_x6": said.strip()}, tmp_path, ev, ev)
    assert x == {"cobol": said.strip(), "java": "COMMAREA past EIBCALEN (60 bytes): not modelled", "ok": True,
                 "assumes": "X23"}  # fmt: skip
    assert cev == jev == ev[:1] and ec.judged_to(x).startswith("the refused reference past EIBCALEN (X23")
    _, _, w = ec.x6_judged({"name": "t", "prefix_x6": "WRITEQ TD LENGTH > FROM: not modelled"}, tmp_path, ev, ev)
    assert w["assumes"] == "X6" and not w["ok"] and ec.judged_to(w) == ec.X6_JUDGED
    # both sides refused, but not at the same thing (the det port read past EIBCALEN, the stub stopped at the WRITEQ)
    _, _, m = ec.x6_judged({"name": "s", "prefix_x6": "WRITEQ TD LENGTH > FROM: not modelled"}, tmp_path, ev, ev)
    assert m["assumes"] == "X6" and m["java"].startswith("COMMAREA past EIBCALEN") and not m["ok"]


_AREA_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int GGCAREA(char **area, int len);
int main(int argc, char **argv) {
    char buf[200];
    char *a = buf;
    memset(buf, 'x', sizeof buf);
    GGCAREA(&a, atoi(argv[1]));
    printf("moved=%d first=%c\n", a != buf, a[0]);
    fflush(stdout);
    a[atoi(argv[2])] = 'y';
    printf("wrote\n");
    return 0;
}
"""


def test_a_scenario_states_untyped_commarea_bytes_for_a_case_with_no_layout():
    """#5859 (ZECSNC): `"commarea_hex"` is the exact bytes the caller passed to a program with no typed COMMAREA (an
    HLASM DSECT); EIBCALEN is their count. Refused by name when typed, mixed with a typed key, empty or not hex."""
    case = {"commarea": None}
    assert ec.untyped_commarea(case, {"name": "s"}, []) is None
    assert ec.untyped_commarea(case, {"name": "s", "commarea_hex": "00ff5A43"}, []) == b"\x00\xffZC"
    for bad in ("", "0", "zz", 12, "00 00"):
        with pytest.raises(ec.Unsupported, match="hex byte pairs"):
            ec.untyped_commarea(case, {"name": "s", "commarea_hex": bad}, [])
    for extra in ({"commarea": {}}, {"commarea_length": 4}):
        with pytest.raises(ec.Unsupported, match="commarea_length"):
            ec.untyped_commarea(case, {"name": "s", "commarea_hex": "0000", **extra}, [])
    with pytest.raises(ec.Unsupported, match="no layout"):
        ec.untyped_commarea({"commarea": {}}, {"name": "s", "commarea_hex": "0000"}, [{"name": "A"}])
    with pytest.raises(ec.Unsupported, match="no layout"):
        ec.untyped_commarea(case, {"name": "s", "commarea_hex": "0000"}, [{"name": "A"}])


def test_the_java_side_gets_the_untyped_commarea_in_the_region_page():
    """#5859: the stub reads commarea.in in the case's data page; the port's byte[] is in the region's (CCSID 037),
    as a START's data is, and its length is EIBCALEN."""
    case = {"commarea": None, "data_encoding": "ascii"}
    got = ec._java_untyped_commarea(case, {"name": "s", "commarea_hex": "5A433031"}, [])
    assert got == {"commarea_hex": "E9C3F0F1", "untyped_length": 4}
    assert ec._java_untyped_commarea(case, {"name": "s"}, []) == {}


def test_the_java_template_reads_an_untyped_commarea():
    """#5859: the generated test builds the byte[] from `commarea_hex` and passes its length as EIBCALEN."""
    src = Path(ec.__file__).read_text(encoding="utf-8")
    assert 'sc.hasNonNull("commarea_hex")' in src
    assert "HexFormat.of().parseHex" in src
    assert 'sc.path("untyped_length")' in src


@pytest.mark.skipif(__import__("sys").platform == "win32" or not __import__("shutil").which("gcc"),
                    reason="needs gcc and a POSIX guard page")  # fmt: skip
def test_the_stub_stops_a_reference_past_a_stated_commarea_length(tmp_path):
    """#4270 (X23): with commarea.exact, GGCAREA copies the COMMAREA to the end of a page before an inaccessible one:
    the last byte is the program's, the next stops the run (98, "COMMAREA past EIBCALEN: not modelled"). Without it,
    the area is left where the driver has it."""
    import subprocess

    (tmp_path / "main.c").write_text(_AREA_MAIN, encoding="ascii")
    exe = tmp_path / "area"
    built = subprocess.run(["gcc", "-o", str(exe), str(tmp_path / "main.c"), str(ec.STUB / "ggcics.c")],  # noqa: S603,S607
                           capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    d = tmp_path / "d"
    d.mkdir()

    def run(*args: str) -> tuple[int, str]:
        p = subprocess.run([str(exe), *args], capture_output=True, text=True, env={"GGCICS_DIR": str(d)}, check=False)  # noqa: S603
        return p.returncode, p.stdout

    assert run("60", "99") == (0, "moved=0 first=x\nwrote\n")
    (d / "commarea.exact").write_text("60\n", encoding="ascii")
    assert run("60", "59") == (0, "moved=1 first=x\nwrote\n")
    assert run("60", "60") == (98, "moved=1 first=x\nCOMMAREA past EIBCALEN: not modelled\n")


def test_the_x23_stub_test_is_skipped_where_there_is_no_guard_page():
    """#6886: #6875 inserted tests between this test's `skipif` and its def, so it ran on Windows (the stub refuses a
    stated COMMAREA length there). The decorator must stay on the test it guards."""
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "test_the_stub_stops_a_reference_past_a_stated_commarea_length")  # fmt: skip
    assert any("skipif" in ast.unparse(d) and "win32" in ast.unparse(d) for d in fn.decorator_list)
