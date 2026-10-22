"""#5053: the LINK / XCTL COMMAREA's bytes in the CICS crucible. A facade's handleLink had no byte overload, so the
crucible compared a LINKed program's COMMAREA (and the caller_commarea its RETURN gives back) through the DTO alone: a
facade that stopped carrying the bytes (a numeric DISPLAY field holding spaces, which a DTO reads as a number) was never
seen. The forge now emits handleLink(T request, byte[] area) beside the unchanged DTO form, with lastLinkBytes() (the
bytes the program left there); the det stub rebuilds both; the crucible drives the byte form and compares by its bytes."""

from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import test_facade_layout_4449 as base  # noqa: E402

from gitgalaxy.tools.cobol_to_java import proof_reach  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile


def _services() -> dict[str, str]:
    forge, _ = base._link_pair()
    return {k: "\n".join(forge.service_extras(p)["methods"]) for k, p in forge.programs.items()}


def test_the_facade_keeps_handleLink_and_adds_the_bytes_overload():
    s = _services()["PCCONF"]
    assert s.count("public PcconfWsState handleLink(PcconfWsState request) {") == 1  # the harness reads this one
    assert s.count("public PcconfWsState handleLink(PcconfWsState request, byte[] area) {") == 1
    assert 'region.linked("' in s and ", request, area);" in s
    assert "lastLinkBytes = task.linkAreaTaken() && left != null" in s
    assert "private byte[] lastLinkBytes;" in s and "public byte[] lastLinkBytes() {" in s
    assert "// @facade-helper" in s and "@facade-helper */" in s
    # the harness's contract regex (det/cics.py target_contract) reads the DTO form only
    assert re.findall(r"handleLink\((\w+) request\)", s) == ["PcconfWsState"]


def test_a_link_without_a_commarea_has_no_bytes_overload():
    """handleLink(byte[]) would only collide with the DTO form's arity in the crucible's lookup: no area, no bytes."""
    forge, _ = base._link_pair()
    prog = forge.programs["PCCONF"]
    prog_types = forge.link_types(prog)
    assert prog_types[0]
    src = Path(forge.service_extras.__code__.co_filename).read_text(encoding="utf-8")
    assert "if req else [])" in src and "link_bytes_overload" in src


def test_det_facades_rebuild_the_bytes_overload_and_its_helper():
    from gitgalaxy.tools.cobol_to_java.det.program import facades

    out = "\n".join(facades(_services()["PCCONF"]))
    assert out.count("handleLink(") == 2
    assert out.count(", request, area);") == 1 and out.count("region.linked(") == 2
    assert "lastLinkBytes = task.linkAreaTaken() && left != null" in out
    assert "// @facade-helper" in out and "public byte[] lastLinkBytes() {" in out
    assert "lastLinkBytes" in proof_reach.DET_HELPERS
    from gitgalaxy.tools.cobol_to_java.det.gen import METHODS_TAKEN

    assert "lastLinkBytes" in METHODS_TAKEN


def test_the_crucible_java_drives_the_link_byte_overload_and_reads_lastLinkBytes():
    src = runner._JAVA_TEST
    assert 'facade(service, "handleLink", 1, false)' in src and 'facade(service, "handleLink", 2, true)' in src
    assert 'm.getName().equals("lastLinkBytes")' in src and "has no lastLinkBytes()" in src
    assert "is not the bytes its task left in the LINK COMMAREA" in src
    assert (
        'e.put("area_bytes"' in src and "public CicsTask linked(String program, Object commarea, byte[] bytes)" in src
    )


def _ebcdic_area(text: str, layout=None):
    shapes = {}
    return cc.FieldArea({}, 4, b"\x40" * 4, 4)


def test_the_callers_commarea_is_compared_by_the_bytes_the_program_left():
    """A DISPLAY byte through the runtime page, a binary one as it is; bounded by the LINK's LENGTH, not the whole area."""
    layout = [
        {"name": "A-TXT", "offset": 0, "bytes": 2, "pic": "X(2)", "class": "X", "usage": None},
        {"name": "A-BIN", "offset": 2, "bytes": 2, "pic": "S9(4)", "class": "9", "usage": "COMP"},
    ]
    dto = cc.FieldArea({"A-TXT": "1 ", "A-BIN": 0}, 4, b"\xf1\x40\x00\x00", 4)
    left = base64.b64encode(b"1 \x00\x2a" + b"TAIL").decode()  # runtime page (ASCII), then bytes past the LINK's LENGTH
    got = runner._with_answered_bytes(dto, left, runner.RUNTIME_PAGE, layout)
    assert got.data == b"\xf1\x40\x00\x2a" and got.known == 4  # '1' is X'F1' in CCSID 037, the COMP bytes as they are
    # no answer: the DTO's bytes (a program that took none)
    assert runner._with_answered_bytes(dto, None, runner.RUNTIME_PAGE, layout) is dto
    whole = runner._with_answered_bytes(cc.FieldArea({}, cc.FULL, b"", 0), left, runner.RUNTIME_PAGE, None)
    assert len(whole.data) == 8  # a whole-record DTO has no LENGTH to cut at


def test_bytes_that_diverge_from_the_expected_log_fail():
    layout = [{"name": "A-TXT", "offset": 0, "bytes": 4, "pic": "X(4)", "class": "X", "usage": None}]
    dto = cc.FieldArea({"A-TXT": "    "}, 4, b"\x40" * 4, 4)
    spaces = runner._with_answered_bytes(dto, base64.b64encode(b"    ").decode(), runner.RUNTIME_PAGE, layout)
    other = runner._with_answered_bytes(dto, base64.b64encode(b"0000").decode(), runner.RUNTIME_PAGE, layout)
    assert spaces.data == b"\x40" * 4 and other.data == b"\xf0" * 4 and spaces.data != other.data


MAIN = """package com.acme.cics;

public class Main {
    static byte[] seen;

    public static void main(String[] a) {
        CicsTask task = new CicsTask("T001", "ENTER", null, null, java.util.Map.of());
        byte[] area = "    ".getBytes();
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask t) {
                byte[] v = t.linkAreaView();
                System.out.println(p + " view=" + (v == null ? "none" : v == area ? "same" : "copy") + " caller="
                        + t.linkAreaOfCaller() + " taken=" + t.linkAreaTaken());
                if (p.equals("FIRST") && v != null) {
                    t.linkArea()[0] = 'D';
                    t.xctl("SECOND", new Object(), 4, v);
                    return;
                }
                t.returnTransid(null, null);
            }
        });
        task.withProgram("CALLER");
        task.link("FIRST", new Object(), 4, area);
        System.out.println("area=" + new String(area));
        task.link("SECOND", new Object(), 4);
        CicsTask.Region region = new CicsTask.Region() {
            public CicsTask transaction(String transid, Object commarea) {
                return null;
            }

            public CicsTask linked(String program, Object commarea) {
                return new CicsTask("CSMI", null, commarea, null, java.util.Map.of());
            }

            public void run(CicsTask t, String program, java.util.function.Consumer<CicsTask> self) {
                self.accept(t);
            }
        };
        CicsTask t = region.linked("X", new Object(), area);
        System.out.println("region view=" + (t.linkAreaView() == area ? "same" : "copy") + " taken=" + t.linkAreaTaken());
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_the_runtime_hands_a_link_its_area_by_address_and_an_xctl_target_a_copy(tmp_path):
    root = tmp_path / "src" / "com" / "acme" / "cics"
    root.mkdir(parents=True)
    (root / "CicsTask.java").write_text(CICS_TASK_JAVA.replace("__PACKAGE__", "com.acme").replace("__ZONE__", "UTC"),
                                        encoding="utf-8")  # fmt: skip
    (root / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "com.acme"), encoding="utf-8")
    (root / "Main.java").write_text(MAIN, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, root.glob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "com.acme.cics.Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "FIRST view=same caller=true taken=false",  # the caller's own storage, not yet taken
        "SECOND view=copy caller=false taken=false",  # an XCTL target: a copy of the bytes XCTL passed
        "area=D   ",  # what the first program wrote there, the caller sees
        "SECOND view=none caller=false taken=false",  # a LINK without bytes: none to carry
        "region view=same taken=false",  # Region.linked(.., bytes): by address
    ]
