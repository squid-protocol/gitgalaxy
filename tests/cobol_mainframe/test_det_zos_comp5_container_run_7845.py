"""#7845 (#7709, register C7): a COMP-5 group crosses a CICS channel container in z/OS order, run in Java. The parent's
area is PUT (`DetCics.containerData`), the container holds the bytes as the program held them, and the reader's area
(`DetCics.put`) reads the same values. Under `swapZosComp5(false)` the same values give the reversed (oracle) image."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PKG = "t"
# (digits, value, z/OS hex) for S9(4) / S9(9) / S9(18) COMP-5: 2, 4 and 8 bytes
ITEMS = [(4, "-2", "FFFE"), (9, "305419896", "12345678"), (18, "72623859790382856", "0102030405060708")]


def _rev(h: str) -> str:
    return "".join(reversed([h[i : i + 2] for i in range(0, len(h), 2)]))


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin/javac").is_file():
        return Path(home) / "bin"
    found = shutil.which("javac")
    return Path(found).parent if found else None


def _main() -> str:
    rows = ",".join(f'{{"{d}", "{v}", "{h}"}}' for d, v, h in ITEMS)
    return f"""package {PKG}.cics;
import {PKG}.cobolrt.*;
import {PKG}.cobolrt.cics.DetCics;
import java.math.BigDecimal;
public class Main {{
  static String hex(byte[] b) {{ StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02X", x & 0xFF)); return s.toString(); }}
  public static void main(String[] a) {{
    java.nio.charset.Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1;
    String[][] rows = {{{rows}}};
    for (boolean zos : new boolean[] {{true, false}}) {{
      boolean before = Cobol.swapZosComp5(zos);
      for (String[] r : rows) {{
        int d = Integer.parseInt(r[0]); int n = d <= 4 ? 2 : d <= 9 ? 4 : 8; int len = n + 2;
        Storage ps = new Storage(len);  // the parent's group: a text byte pair, then the COMP-5 item
        Field.alphanumeric(ps, 0, 2, false);
        System.arraycopy("AB".getBytes(cs), 0, ps.bytes, 0, 2);
        Field item = Field.binary(ps, 2, d, 0, true, true);
        Cobol.store(item, new BigDecimal(r[1]), false, cs);
        Field group = Field.group(ps, 0, len);
        CicsTask parent = new CicsTask("ZC01", "ENTER", null, null);
        CicsTask.ContainerResult put = parent.putContainer("CH", "C", DetCics.containerData(group, len), len, null, false);
        CicsTask.ContainerResult got = parent.getContainer("CH", "C", len);
        Storage cst = new Storage(len);  // the reader's own group, filled from the container
        Field into = Field.group(cst, 0, len);
        DetCics.put(into, got.data());
        Field read = Field.binary(cst, 2, d, 0, true, true);
        System.out.println(zos + " " + put.resp() + " " + got.resp() + " " + hex(got.data()) + " " + Cobol.num(read, cs).toPlainString());
      }}
      Cobol.swapZosComp5(before);
    }}
  }}
}}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK (javac)")
@pytest.mark.slow(
    reason="compiles the generated CicsTask and det runtime with javac (cold ~10-20 s on a loaded runner)"
)
def test_a_comp5_group_crosses_a_container_in_z_os_order_and_reads_back(tmp_path):
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
    (cics / "Main.java").write_text(_main(), encoding="utf-8")
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
    lines = run.stdout.splitlines()
    want = [
        f"{z} NORMAL NORMAL {'4142' + (h if z == 'true' else _rev(h))} {v}"
        for z in ("true", "false")
        for _, v, h in ITEMS
    ]
    assert lines == want, lines
