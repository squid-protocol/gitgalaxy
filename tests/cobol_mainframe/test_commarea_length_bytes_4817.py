"""#4817 / #4695: a RETURN or XCTL COMMAREA passes LENGTH bytes (a copy), whole input class on CicsTask's runtime.

IBM (EXEC CICS RETURN / XCTL, COMMAREA + LENGTH): the next task / the target is handed LENGTH bytes -- its EIBCALEN. The
bytes a det port passes beside its DTO are the record's whole span, so the runtime cuts them at LENGTH, as the DTO's reading
already is. A LINK passes its area by address and is not cut. LENGTH null / equal / past the area keep every byte (spaces in a
numeric field and bytes no DTO decodes too). #4695: a LENGTH past the DTO passes the COMMAREA as a byte[], which a facade's
`returned(Object.class)` answers by design and `returned(Dto.class)` refuses by name.
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

MAIN = """
package com.squid.gitgalaxy.cics;

import java.util.Arrays;
import java.util.Map;

public class Main {
    static final byte[] AREA = {' ', ' ', 0x00, (byte) 0xFF, 'Z', ' '};  // spaces, LOW-VALUES, a non-text byte

    static void say(String k, Object v) {
        System.out.println(k + "=" + v);
    }

    static String show(byte[] b) {
        return b == null ? "null" : Arrays.toString(b);
    }

    static byte[] head(int n) {
        return Arrays.copyOf(AREA, n);
    }

    /** XCTL from program A passing AREA / length: what program B takes as its DFHCOMMAREA bytes. */
    static byte[] xctl(Integer length) {
        byte[][] seen = {null};
        CicsTask task = new CicsTask("T001", "ENTER", null, null, Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask t) {
                if (p.equals("A")) {
                    t.xctl("B", "x", length, AREA.clone());
                } else {
                    seen[0] = t.linkArea();
                }
            }
        });
        task.run("A");
        return seen[0];
    }

    public static void main(String[] args) {
        CicsTask.Region region = new CicsTask.LocalRegion(null, "T001", null);
        Integer[] lengths = {null, 0, 2, 5, 6, 7, 40};
        for (Integer len : lengths) {
            int want = len == null ? AREA.length : Math.min(len, AREA.length);
            CicsTask r = region.transaction("T1", null);
            r.returnTransid("T2", "x", len, AREA.clone());
            say("return " + len, Arrays.equals(r.returnedBytes(), head(want)));
            CicsTask ri = new CicsTask("T001", "ENTER", null, null, Map.of()).withTermid("T001");
            ri.returnImmediate("T4", "x", len, AREA.clone());
            say("immediate " + len, Arrays.equals(ri.returnedBytes(), head(want)));
            say("xctl " + len, Arrays.equals(xctl(len), head(want)));
            // the next task is given exactly those bytes
            CicsTask next = region.transaction("T2", "x", r.returnedBytes());
            say("next " + len, Arrays.equals(next.linkArea(), head(want)));
        }
        // the bytes are a copy: the program's array changed afterwards does not change what was passed
        byte[] mine = AREA.clone();
        CicsTask c = region.transaction("T1", null);
        c.returnTransid("T2", "x", null, mine);
        mine[0] = 'Q';
        say("copy", c.returnedBytes()[0] == ' ');

        // #4695: a LENGTH past the DTO: the COMMAREA is the byte[]; Object answers it, a DTO is refused by name
        byte[] wide = {1, 2, 3, 4, 5};
        CicsTask w = region.transaction("T1", null);
        w.returnTransid("T2", wide, 5, null);
        say("object-answer", Arrays.equals((byte[]) w.returned(Object.class), wide));
        try {
            w.returned(Main.class);
            say("dto-refused", false);
        } catch (IllegalStateException e) {
            say("dto-refused", e.getMessage().contains("answer it as Object"));
        }
    }
}
"""


def _jdk() -> Path | None:
    jdk = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if jdk and (Path(jdk) / "bin" / "javac").exists():
        return Path(jdk)
    javac = shutil.which("javac")
    return Path(javac).resolve().parent.parent if javac else None


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_return_and_xctl_pass_length_bytes_and_the_byte_answer_is_by_design(tmp_path):
    jdk = _jdk()
    src = tmp_path / "src" / "com" / "squid" / "gitgalaxy" / "cics"
    src.mkdir(parents=True)
    (src / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("package __PACKAGE__.cics;", "package com.squid.gitgalaxy.cics;").replace(
            "__ZONE__", "UTC"
        )
    )
    (src / "CicsSpec.java").write_text(
        CICS_SPEC_JAVA.replace("package __PACKAGE__.cics;", "package com.squid.gitgalaxy.cics;")
    )
    (src / "Main.java").write_text(MAIN)
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
    out = dict(line.split("=", 1) for line in res.stdout.splitlines() if "=" in line)
    for key in ("return", "immediate", "xctl", "next"):
        for ln in ("null", "0", "2", "5", "6", "7", "40"):
            assert out[f"{key} {ln}"] == "true", (key, ln, res.stdout)
    assert out["copy"] == "true"
    assert out["object-answer"] == "true"
    assert out["dto-refused"] == "true"
