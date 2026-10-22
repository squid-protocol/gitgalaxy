"""#4695: a det facade's handleTransaction answers the program's own DTO when its RETURN's COMMAREA LENGTH is past the DTO.

Since #4679 such a RETURN passes the COMMAREA as a byte[] in the region's EBCDIC (DetCics.commareaOut). The facade used to
answer that byte[] (CardDemo COCRDLIC, COCRDSLC, COCRDUPC, COACTVWC, COACTUPC: RETURN WS-COMMAREA LENGTH 2000), opaque to
a deployed caller. Now the service's wideAnswer reads the bytes through the DTO's layout (fromCommarea, #4449) in the port's
page; the task keeps the bytes (EIBCALEN, the next task's COMMAREA), and lastAnswerBytes() is unchanged. Only a program that
passes bytes (cx.passes_bytes) carries it, so no other port moves: the helper lives in the service, not in DetCics.
#5291: an XCTL with no COMMAREA also sets it (the target's RETURN may be wide): CardDemo COMEN01C and COADM01C.

Two layers: the generated source (every facade shape: typed, Object, Object with no own DTO, the byte-carrying overload,
void, handleLink, a program that passes no bytes) and the Java of wideAnswer itself (every answer class: text, spaces,
LOW-VALUES, non-text bytes, no layout, short bytes: null, left to the answer the facade had).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from gitgalaxy.tools.cobol_to_java.det import program as P
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

DET_CICS = Path(P.__file__).parent / "cobolrt" / "cics" / "DetCics.java"


def _stub(ret: str, req: str | None) -> str:
    arg = f", {req} request" if req else ""
    return (
        f"public class S {{\n    public {ret} handleTransaction(String transid{arg}) {{\n"
        '        region.run(task, "PROG", this::runTask);\n        return task.returned(' + ret + ".class);\n    }\n"
        f"    public {ret} handleTransaction(String transid{arg}, byte[] area) {{\n"
        '        region.run(task, "PROG", this::runTask);\n        return task.returned(' + ret + ".class);\n    }\n"
        "    public byte[] lastAnswerBytes() {\n        return null;\n    }\n}\n"
    )


def test_an_object_facade_with_its_own_dto_converts_wide_bytes_in_both_overloads():
    java = "\n".join(P.facades(_stub("Object", "CaDto"), True))
    assert java.count("wideAnswer(wide, CaDto.class)") == 2
    assert java.count("        return answer;") == 2  # any other answer is as it was
    assert java.count("lastAnswerBytes = task.returnedBytes();") == 1  # the bytes stay the task's, as they were
    assert java.count("private static <T> T wideAnswer(") == 1 and "@facade-helper" in java


def test_a_program_that_passes_no_bytes_is_unchanged():
    """Its facade and its service are as they were: nothing else of the estate's ports moves."""
    for ret, req in (("Object", "CaDto"), ("CaDto", "CaDto")):
        java = "\n".join(P.facades(_stub(ret, req)))
        assert "wideAnswer" not in java and java.count(f"return task.returned({ret}.class);") == 2


def test_a_typed_facade_converts_and_leaves_what_no_layout_reads_to_task_returned():
    java = "\n".join(P.facades(_stub("CaDto", "CaDto"), True))
    assert java.count("CaDto read = wideAnswer(wide, CaDto.class);") == 2
    assert java.count("return task.returned(CaDto.class);") == 2  # bytes no layout reads: refused by name, as before


@pytest.mark.parametrize("req", [None, "Object"])
def test_an_object_facade_with_no_dto_of_its_own_keeps_the_bytes(req):
    java = "\n".join(P.facades(_stub("Object", req), True))
    assert "wideAnswer" not in java
    assert java.count("return task.returned(Object.class);") == 2


def test_void_and_link_facades_are_as_they_were():
    java = "\n".join(
        P.facades("public void handleTransaction(String transid) {}\npublic CaDto handleLink(CaDto request) {}\n")
    )
    assert "wideAnswer" not in java
    java = "\n".join(
        P.facades('public CaDto handleLink(CaDto request) {\n region.run(task, "PROG", this::runTask);\n}\n')
    )
    assert "        return request;" in java and "wideAnswer" not in java


MAIN = """
import java.nio.charset.Charset;
import java.util.Arrays;

public class Main {
    static final Charset EBCDIC = Charset.forName("IBM037");
    static final Charset CS = Charset.forName("ISO-8859-1");

    static class DetCics {
%(commarea_in)s
    }

%(methods)s

    public static class Dto {
        final byte[] rec;
        Dto(byte[] rec) { this.rec = rec; }
        public static Dto fromCommarea(byte[] rec) {
            if (rec.length < 4) {
                throw new IllegalArgumentException(rec.length + " bytes do not fill Dto's 4-byte record");
            }
            return new Dto(Arrays.copyOf(rec, 4));
        }
    }

    public static class NoLayout { }

    static void say(String k, Object v) { System.out.println(k + "=" + v); }

    public static void main(String[] a) {
        Charset page = Charset.forName("ISO-8859-1");
        byte[] wide = new byte[40];
        Arrays.fill(wide, (byte) 0x40);  // EBCDIC spaces
        byte[] head = "AB12".getBytes(EBCDIC);
        System.arraycopy(head, 0, wide, 0, 4);
        for (int len : new int[] {4, 5, 40}) {  // exactly the record, past it, the 2000-byte shape
            Dto d = wideAnswer(Arrays.copyOf(wide, len), Dto.class);
            say("read " + len, Arrays.equals(d.rec, "AB12".getBytes(page)));
        }
        byte[] odd = Arrays.copyOf(wide, 12);
        odd[1] = 0x00;  // LOW-VALUES
        odd[2] = 0x40;  // a space
        Dto d = wideAnswer(odd, Dto.class);
        say("low-values", Arrays.equals(d.rec, new byte[] {'A', 0, ' ', '2'}));
        say("no-layout", wideAnswer(wide, NoLayout.class) == null);
        say("short", wideAnswer(Arrays.copyOf(wide, 3), Dto.class) == null);
    }
}
"""


def _jdk() -> Path | None:
    jdk = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if jdk and (Path(jdk) / "bin" / "javac").exists():
        return Path(jdk)
    javac = shutil.which("javac")
    return Path(javac).resolve().parent.parent if javac else None


def _commarea_in() -> str:
    """The real DetCics.commareaIn, cut from its source."""
    text = DET_CICS.read_text(encoding="utf-8")
    m = re.search(r"    public static byte\[\] commareaIn\(.*?\n    }\n", text, re.S)
    assert m
    return m.group(0)


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_commarea_as_reads_the_bytes_through_the_layout(tmp_path):
    jdk = _jdk()
    (tmp_path / "Main.java").write_text(
        MAIN % {"commarea_in": _commarea_in(), "methods": "\n".join(P.WIDE_ANSWER)}, encoding="utf-8"
    )
    javac_run(
        [str(jdk / "bin" / "javac"), "-encoding", "UTF-8", "-d", str(tmp_path / "c"), str(tmp_path / "Main.java")],
        check=True,
    )  # noqa: S603
    res = subprocess.run(
        [
            str(jdk / "bin" / "java"),
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(tmp_path / "c"),
            "Main",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )  # noqa: S603
    out = dict(line.split("=", 1) for line in res.stdout.splitlines() if "=" in line)
    assert len(out) == 6, res.stdout
    assert all(v == "true" for v in out.values()), out


# ---- #5291: an XCTL with no COMMAREA (CardDemo COMEN01C, COADM01C) ------------------------------------------------------
XCTL_DTO = """\
package com.x.dto.contract;

/** COBOL record DFHCOMMAREA (XCT.cbl), 5 bytes. */
public class XctDfhcommarea {

    // CA-HEAD: PIC X(3), offset 0, 3 bytes (xca.cpy)
    private String caHead;

    // CA-N: PIC 9(2), offset 3, 2 bytes (xca.cpy)
    private Integer caN;
}
"""
XCTL_STUB = (
    "package com.x.service;\nimport com.x.cics.CicsTask;\nimport com.x.dto.contract.XctDfhcommarea;\n"
    "public class XctService {\n"
    "    public {ret} handleTransaction(String transid, XctDfhcommarea request) {\n"
    '        region.run(task, "XCT", this::runTask);\n        return task.returned({ret}.class);\n    }\n'
    "    public XctDfhcommarea xctlNext(XctDfhcommarea request) { return request; }\n"
    "    public void runTask(CicsTask task) {}\n}\n"
)


def _xct_facade(tmp_path, command: str, ret: str) -> str:
    """The facade section of the port det translates for a program whose only transfer of control is `command`."""
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "XCT.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. XCT.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01 WS-CA.\n          COPY XCA.\n"
        "       LINKAGE SECTION.\n       01 DFHCOMMAREA.\n          COPY XCA.\n"
        "       PROCEDURE DIVISION USING DFHCOMMAREA.\n"
        f"           {command}\n           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    (tmp_path / "xca.cpy").write_text(
        "          03 CA-HEAD                 PIC X(3).\n          03 CA-N                    PIC 9(2).\n",
        encoding="utf-8",
    )
    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "XctDfhcommarea.java").write_text(XCTL_DTO, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    stub = XCTL_STUB.replace("{ret}", ret)
    r = P.translate(tmp_path / "XCT.cbl", [tmp_path], stub, "com.x", {}, tmp_path / "proj")
    assert r.stats["holes"] == [], r.stats
    return r.java


@pytest.mark.parametrize("ret", ["Object", "XctDfhcommarea"])
def test_an_xctl_with_no_commarea_reads_a_wide_answer_in_both_facade_shapes(tmp_path, ret):
    """The target is dynamic or unnamed by a COMMAREA, so its RETURN can pass wide bytes the facade must read."""
    java = _xct_facade(tmp_path, "EXEC CICS XCTL PROGRAM('OTHER') END-EXEC", ret)
    assert "wideAnswer(wide, XctDfhcommarea.class)" in java and "private static <T> T wideAnswer(" in java
    assert next(ln for ln in java.splitlines() if "task.xctl(" in ln).rstrip().endswith(", null);")


@pytest.mark.parametrize("ret", ["Object", "XctDfhcommarea"])
@pytest.mark.parametrize(
    "command",
    [
        "EXEC CICS XCTL PROGRAM('OTHER') COMMAREA(WS-CA) END-EXEC",  # a COMMAREA within its DTO
        "EXEC CICS LINK PROGRAM('OTHER') COMMAREA(WS-CA) END-EXEC",
        "CONTINUE",  # no transfer at all
    ],
)
def test_other_transfers_leave_the_facade_as_it_was(tmp_path, ret, command):
    java = _xct_facade(tmp_path, command, ret)
    assert "wideAnswer" not in java
