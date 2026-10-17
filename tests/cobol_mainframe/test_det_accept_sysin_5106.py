"""#5106: ACCEPT identifier FROM SYSIN in the det translator and runtime (CardDemo COBSWAIT's parameter card).

The input class: the translation (SYSIN wired, every other source still refused by name, the clock sources
unchanged) and the runtime (a card shorter than, equal to and longer than the target; a numeric target; CRLF; a
second ACCEPT reading the next record; no record left refused by name, never a silent blank).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PKG = "t"


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _program(accept: str) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. SYSINT.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01 PARM-VALUE PIC X(8).", "01 WAIT-TIME PIC 9(8) COMP.", "PROCEDURE DIVISION.", "MAIN-PARA.",
             f"    {accept}", "    MOVE PARM-VALUE TO WAIT-TIME", "    STOP RUN."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _translate(tmp_path: Path, src: str):
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "SYSINT.cbl").write_text(src)
    project = tmp_path / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp_path / "SYSINT.cbl", [], "public class SysintService {\n}\n", PKG, None, project)


def test_accept_from_sysin_is_the_runtime_call_and_imports_accept(tmp_path):
    r = _translate(tmp_path, _program("ACCEPT PARM-VALUE FROM SYSIN."))
    assert not r.stats["holes"], r.stats["holes"]
    assert "Accept.sysin(" in r.java
    assert f"import {PKG}.cobolrt.Accept;" in r.java


@pytest.mark.parametrize("source", ["CONSOLE", "ENVIRONMENT-NAME", "DATE", "DAY-OF-WEEK"])
def test_the_other_sources_are_unchanged(tmp_path, source):
    r = _translate(tmp_path, _program(f"ACCEPT PARM-VALUE FROM {source}."))
    if source in ("DATE",):
        assert not r.stats["holes"] and "Accept.from(" in r.java and "Accept.sysin(" not in r.java
    else:
        assert len(r.stats["holes"]) == 1 and f"ACCEPT FROM {source}" in r.stats["holes"][0], r.stats["holes"]


def _run(tmp_path: Path, stdin: bytes, accepts: int = 1) -> subprocess.CompletedProcess:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    for rel, text in P.runtime_files(PKG, batch=False).items():
        if not rel.startswith(("cobolrt/cics/", "cobolrt/sql/")):
            (src / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / PKG / rel).write_text(text)
    show = (
        'System.out.println("[" + t.cobolrt.Cobol.displayText(f, java.nio.charset.StandardCharsets.ISO_8859_1) + "]");'
    )
    body = (
        "java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1; "
        "t.cobolrt.Field f = t.cobolrt.Field.alphanumeric(t.cobolrt.Storage.of(new byte[8]), 0, 8, false); "
        + f"for (int i = 0; i < {accepts}; i++) {{ t.cobolrt.Accept.sysin(f, cs); {show} }}"
    )
    (src / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ {body} }} }}\n")
    jdk = _jdk()
    subprocess.run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    return subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp",  # noqa: S603
                           str(tmp_path / "classes"), "Main"], input=stdin, capture_output=True)  # fmt: skip


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize(
    "stdin, want",
    [
        (b"00000042\n", ["[00000042]"]),  # exactly the target
        (b"42\n", ["[42      ]"]),  # shorter: space-padded on the right
        (b"123456789012\n", ["[12345678]"]),  # longer: truncated on the right
        (b"00000007\r\n", ["[00000007]"]),  # CRLF line end dropped
        (b"AAAA\nBBBB\n", ["[AAAA    ]", "[BBBB    ]"]),  # one record per ACCEPT
        (b"LAST", ["[LAST    ]"]),  # no trailing newline
    ],
)  # fmt: skip
def test_the_runtime_reads_one_record_per_accept(tmp_path, stdin, want):
    run = _run(tmp_path, stdin, accepts=len(want))
    assert run.returncode == 0, run.stderr.decode()
    assert run.stdout.decode().split("\n")[: len(want)] == want


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_no_record_left_is_refused_by_name(tmp_path):
    run = _run(tmp_path, b"ONE\n", accepts=2)
    assert run.returncode != 0
    assert "ACCEPT FROM SYSIN: no record left" in run.stderr.decode()
