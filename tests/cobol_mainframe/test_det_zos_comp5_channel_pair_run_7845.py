"""#7845 (#7709, register C7): two translated programs pass a COMP-5 group through a CICS channel, run in Java. The parent
PUTs the group and LINKs with the channel; the child GETs it, adds one to each COMP-5 item and PUTs it back. Under
`zos_comp5` (the default) the container holds IBM's big-endian image before and after the child, and the child read the
values; with the switch off both programs hold the oracle's (little-endian) order. Synthetic programs only."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PKG = "t"
DATA = ["01 REC.", "   05 T PIC X(2).", "   05 H PIC S9(4) COMP-5.", "   05 W PIC S9(9) COMP-5.",
        "   05 D PIC S9(18) COMP-5.", "01 LEN PIC S9(8) COMP VALUE 16."]  # fmt: skip
PUT = "EXEC CICS PUT CONTAINER('C') CHANNEL('CH') FROM(REC)\n      FLENGTH(LEN) END-EXEC"
GET = "EXEC CICS GET CONTAINER('C') CHANNEL('CH') INTO(REC)\n      FLENGTH(LEN) END-EXEC"
PARENT = ["MOVE 'AB' TO T", "MOVE -2 TO H", "MOVE 305419896 TO W", "MOVE 72623859790382856 TO D", PUT,
          "EXEC CICS LINK PROGRAM('CHILD') CHANNEL('CH') END-EXEC"]  # fmt: skip
CHILD = [GET, "ADD 1 TO H", "ADD 1 TO W", "ADD 1 TO D", PUT]
# the group after the child: text, then H = -1, W = 305419897, D = 72623859790382857 (z/OS big-endian image)
ZOS = "4142" + "FFFF" + "12345679" + "0102030405060709"


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin/javac").is_file():
        return Path(home) / "bin"
    found = shutil.which("javac")
    return Path(found).parent if found else None


def _cbl(name: str, proc: list[str]) -> str:
    lines = ["IDENTIFICATION DIVISION.", f"PROGRAM-ID. {name}.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *DATA,
             "PROCEDURE DIVISION.", *[f"    {x}" for x in "\n".join(proc).split("\n")], "    EXEC CICS RETURN END-EXEC."]  # fmt: skip
    return "\n".join(f"       {x}" for x in lines) + "\n"


def _service(tmp_path: Path, name: str, proc: list[str], **kw) -> str:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / f"{name}.cbl").write_text(_cbl(name, proc))
    (tmp_path / "project").mkdir(exist_ok=True)
    stub = f"public class {name.title()}Service {{\n    public void runTask(CicsTask task) {{\n    }}\n}}\n"
    return P.translate(tmp_path / f"{name}.cbl", [], stub, PKG, None, tmp_path / "project", **kw).java


def _hex_main() -> str:
    return f"""package {PKG}.cics;
import {PKG}.service.*;
public class Main {{
  static String hex(byte[] b) {{ StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02X", x & 0xFF)); return s.toString(); }}
  public static void main(String[] a) {{
    {{
      CicsTask task = new CicsTask("ZC01", "ENTER", null, null).withClock(java.time.LocalDateTime.of(2026, 11, 6, 12, 0)).withPrograms(new CicsTask.Programs() {{
        public boolean defined(String p) {{ return p.equals("CHILD"); }}
        public void run(String p, CicsTask t) {{ new ChildService().runTask(t); }}
      }});
      new ParentService().runTask(task);
      CicsTask.ContainerResult got = task.getContainer("CH", "C", 16);
      System.out.println("true " + got.resp() + " " + hex(got.data()));
    }}
  }}
}}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK (javac)")
@pytest.mark.slow(reason="compiles the generated CicsTask, det runtime and two translated programs with javac")
def test_a_comp5_group_passes_through_a_channel_between_two_programs_in_z_os_order(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    for rel, text in P.runtime_files(PKG, batch=False).items():
        (src / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / PKG / rel).write_text(text, encoding="utf-8")
    cics = src / PKG / "cics"
    cics.mkdir(parents=True, exist_ok=True)
    (cics / "CicsTask.java").write_text(
        CICS_TASK_JAVA.replace("__PACKAGE__", PKG).replace("__ZONE__", "UTC"), encoding="utf-8"
    )
    (cics / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", PKG), encoding="utf-8")
    (cics / "Main.java").write_text(_hex_main(), encoding="utf-8")
    svc = src / PKG / "service"
    svc.mkdir(parents=True, exist_ok=True)
    for name, proc in (("Parent", PARENT), ("Child", CHILD)):
        (svc / f"{name}Service.java").write_text(_service(tmp_path, name, proc), encoding="utf-8")
    stereo = src / "org/springframework/stereotype"
    stereo.mkdir(parents=True)
    (stereo / "Service.java").write_text("package org.springframework.stereotype;\npublic @interface Service {\n}\n")
    rec = src / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    jdk = _jdk()
    classes = tmp_path / "classes"
    built = subprocess.run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(classes),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    run = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes),  # noqa: S603
                          f"{PKG}.cics.Main"], capture_output=True, text=True, encoding="utf-8", check=True)  # fmt: skip
    assert run.stdout.splitlines() == [f"true NORMAL {ZOS}"], run.stdout
