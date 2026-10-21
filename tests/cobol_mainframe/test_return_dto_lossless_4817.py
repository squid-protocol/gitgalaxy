"""#4817: a DTO-only answer of a RETURN COMMAREA never silently changes the bytes the RETURN passed.

IBM hands the next task the COMMAREA's bytes as they were. A DTO holds a number it decoded, so the DTO-only
handleTransaction (and the REST endpoint over it) refuses by name a RETURN whose bytes the DTO cannot hold; the
byte-carrying overload (returnedBytes) answers them. The whole input class: RETURN and RETURN IMMEDIATE, answered as
the DTO's class and as Object, bytes taken first or not, a LENGTH cut, FILLER, a DTO with no layout, no bytes beside.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile


def _jdk() -> Path | None:
    jdk = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if jdk and (Path(jdk) / "bin" / "javac").exists():
        return Path(jdk)
    javac = shutil.which("javac")
    return Path(javac).resolve().parent.parent if javac else None


MAIN = """
package com.squid.gitgalaxy.cics;

import java.nio.charset.StandardCharsets;

public class Main {
    /** A DTO with a layout: toCommarea answers the bytes it was built to write. */
    public static class Dto {
        final byte[] laid;
        Dto(String laid) { this.laid = laid.getBytes(StandardCharsets.US_ASCII); }
        public byte[] toCommarea() { return laid.clone(); }
    }

    /** A DTO with no layout. */
    public static class Bare { }

    static byte[] b(String s) { return s.getBytes(StandardCharsets.US_ASCII); }

    static String answer(String name, boolean immediate, Object dto, String passed, Integer length, boolean takeBytes,
                         Class<?> type) {
        CicsTask.Region region = new CicsTask.LocalRegion(null, "T001", null);
        CicsTask task = region.transaction("T1", null);
        if (immediate) {
            task.returnImmediate("T2", dto, length, b(passed));
        } else {
            task.returnTransid("T2", dto, length, b(passed));
        }
        if (takeBytes) {
            task.returnedBytes();
        }
        try {
            Object got = task.returned(type);
            return name + ": answered " + (got == dto);
        } catch (IllegalStateException e) {
            return name + ": refused " + e.getMessage().contains("#4817");
        }
    }

    public static void main(String[] args) {
        for (boolean imm : new boolean[] {false, true}) {
            String k = imm ? "imm " : "ret ";
            // a number of spaces and digits the DTO decoded to digits: refused, as the DTO's class and as Object
            System.out.println(answer(k + "lossy", imm, new Dto("1202"), "1 2 ", null, false, Dto.class));
            System.out.println(answer(k + "lossy-object", imm, new Dto("1202"), "1 2 ", null, false, Object.class));
            // the same, the bytes taken first (the byte-carrying handleTransaction): answered
            System.out.println(answer(k + "taken", imm, new Dto("1202"), "1 2 ", null, true, Dto.class));
            // the DTO holds every byte: answered
            System.out.println(answer(k + "clean", imm, new Dto("1234"), "1234", null, false, Dto.class));
            // FILLER and an unset field are spaces in the DTO's bytes, anything in the passed ones: answered
            System.out.println(answer(k + "filler", imm, new Dto("12  "), "12XY", null, false, Dto.class));
            // EBCDIC page spaces
            System.out.println(answer(k + "ebcdic-space", imm, new Dto("12@@"), "12XY", null, false, Dto.class));
            // a loss past LENGTH is not passed: answered; one inside it is refused
            System.out.println(answer(k + "cut-past", imm, new Dto("1299"), "1234", 2, false, Dto.class));
            System.out.println(answer(k + "cut-inside", imm, new Dto("1999"), "1234", 2, false, Dto.class));
            // a DTO with no layout: as it was
            System.out.println(answer(k + "bare", imm, new Bare(), "1234", null, false, Bare.class));
        }
        // a RETURN with no bytes beside the DTO (the 3-arg call): as it was
        CicsTask.Region region = new CicsTask.LocalRegion(null, "T001", null);
        CicsTask task = region.transaction("T1", null);
        Dto none = new Dto("1202");
        task.returnTransid("T2", none, null);
        System.out.println("nobytes: answered " + (task.returned(Dto.class) == none));
        // a task that RETURNed nothing
        System.out.println("nothing: " + (region.transaction("T3", null).returned(Dto.class) == null));
    }
}
"""

EXPECT = [
    "lossy: refused true",
    "lossy-object: refused true",
    "taken: answered true",
    "clean: answered true",
    "filler: answered true",
    "ebcdic-space: answered true",
    "cut-past: answered true",
    "cut-inside: refused true",
    "bare: answered true",
]


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_dto_only_answer_refuses_bytes_the_dto_cannot_hold(tmp_path):
    jdk = _jdk()
    src = tmp_path / "src" / "com" / "squid" / "gitgalaxy" / "cics"
    src.mkdir(parents=True)
    pkg = "package com.squid.gitgalaxy.cics;"
    (src / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("package __PACKAGE__.cics;", pkg).replace("__ZONE__", "UTC"), encoding="utf-8"
    )
    (src / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("package __PACKAGE__.cics;", pkg), encoding="utf-8")
    (src / "Main.java").write_text(MAIN, encoding="utf-8")
    javac_run(
        [
            str(jdk / "bin" / "javac"),
            "-encoding",
            "UTF-8",
            "-d",
            str(tmp_path / "classes"),
            *map(str, src.glob("*.java")),
        ],
        check=True,
    )  # noqa: S603
    res = subprocess.run(
        [
            str(jdk / "bin" / "java"),
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-cp",
            str(tmp_path / "classes"),
            "com.squid.gitgalaxy.cics.Main",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )  # noqa: S603
    lines = res.stdout.splitlines()
    for prefix in ("ret ", "imm "):
        assert [ln for ln in lines if ln.startswith(prefix)] == [prefix + e for e in EXPECT]
    assert "nobytes: answered true" in lines
    assert "nothing: true" in lines
