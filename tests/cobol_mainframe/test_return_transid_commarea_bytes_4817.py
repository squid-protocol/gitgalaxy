"""#4817: RETURN TRANSID COMMAREA carries its bytes to the next task.

IBM: RETURN TRANSID COMMAREA passes the bytes to the next task (a copy); every byte arrives as it was.
A level-1 RETURN passes the bytes beside the DTO (like #4806 XCTL). Bytes the DTO cannot decode are preserved.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA, CICS_SPEC_JAVA
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile


def _jdk() -> Path | None:
    """Requires JDK 17 to compile and run the Java test."""
    jdk = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if not jdk or not (Path(jdk) / "bin" / "javac").exists():
        import shutil

        return Path(shutil.which("javac")).parent.parent if shutil.which("javac") else None
    return Path(jdk)


TASK_MAIN = """
package com.squid.gitgalaxy.cics;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;

public class Main {
    public static void main(String[] args) {
        CicsTask.Region region = new CicsTask.LocalRegion(null, "T001", null);

        // spaces in a numeric field which DTO would decode incorrectly
        byte[] original = "    ".getBytes(StandardCharsets.US_ASCII);
        Object commarea = new String(original, StandardCharsets.US_ASCII); // dummy DTO

        // 1. Task returns TRANSID with COMMAREA and its bytes
        CicsTask task1 = region.transaction("T1", null);
        task1.returnTransid("T2", commarea, 4, original);
        byte[] passedBytes = task1.returnedBytes();

        // 2. Next task receives the bytes
        CicsTask task2 = region.transaction("T2", commarea, passedBytes);
        byte[] nextArea = task2.linkArea();

        System.out.println("T2 received bytes matching: " + Arrays.equals(original, nextArea));

        // 3. Old 2-arg path
        CicsTask task3 = region.transaction("T3", commarea);
        System.out.println("T3 received bytes null: " + (task3.linkArea() == null));

        // 4. Return Immediate
        CicsTask task4 = region.transaction("T4", null);
        task4.returnImmediate("T5", commarea, 4, original);
        CicsTask task5 = region.transaction("T5", commarea, task4.returnedBytes());
        System.out.println("T5 received bytes matching: " + Arrays.equals(original, task5.linkArea()));
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_return_transid_passes_the_commarea_bytes_to_the_next_task(tmp_path):
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
    (src / "Main.java").write_text(TASK_MAIN)

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
    )

    assert "T2 received bytes matching: true" in res.stdout
    assert "T3 received bytes null: true" in res.stdout
    assert "T5 received bytes matching: true" in res.stdout
