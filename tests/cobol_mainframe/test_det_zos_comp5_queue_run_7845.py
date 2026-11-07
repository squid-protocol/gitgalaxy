"""#7845 (#7709, register C7), siblings of the container: a COMP-5 group through the byte paths of TS and TD queues and
START FROM / RETRIEVE INTO, run in Java on the runtime those commands generate (DetCics.toRegion / fromRegion around
CicsTask's queue). Those paths move the bytes between the program's page (CS) and the region's (REGION, cp037), unlike a
container, which copies them. Pinned: with the same page the queue holds IBM's big-endian image; with a different one it
holds that image transcoded byte by byte (not IBM's raw bytes -- a boundary, C7.md), and in both the reader gets the same
values back. Synthetic group only."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PKG = "t"
ITEMS = [(4, "-2", "FFFE"), (9, "305419896", "12345678"), (18, "72623859790382856", "0102030405060708")]
PAGES = {"same": "ISO_8859_1", "cp037": "IBM037"}  # the region's page; the program's is ISO-8859-1


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin/javac").is_file():
        return Path(home) / "bin"
    found = shutil.which("javac")
    return Path(found).parent if found else None


def _main() -> str:
    rows = ",".join(f'{{"{d}", "{v}"}}' for d, v, _ in ITEMS)
    pages = ",".join(f'"{p}"' for p in PAGES.values())
    return f"""package {PKG}.cics;
import {PKG}.cobolrt.*;
import {PKG}.cobolrt.cics.DetCics;
import java.math.BigDecimal;
import java.nio.charset.Charset;
public class Main {{
  static String hex(byte[] b) {{ StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02X", x & 0xFF)); return s.toString(); }}
  static String read(byte[] got, int len, int d, Charset cs) {{
    Storage cst = new Storage(len);  // the reader's own group
    DetCics.put(Field.group(cst, 0, len), got);
    return Cobol.num(Field.binary(cst, 2, d, 0, true, true), cs).toPlainString();
  }}
  public static void main(String[] a) {{
    Charset cs = java.nio.charset.StandardCharsets.ISO_8859_1;
    String[][] rows = {{{rows}}};
    for (String pg : new String[] {{{pages}}}) {{
      Charset region = Charset.forName(pg);
      for (String[] r : rows) {{
        int d = Integer.parseInt(r[0]); int n = d <= 4 ? 2 : d <= 9 ? 4 : 8; int len = n + 2;
        boolean before = Cobol.swapZosComp5(true);
        Storage ps = new Storage(len);
        System.arraycopy("AB".getBytes(cs), 0, ps.bytes, 0, 2);
        Cobol.store(Field.binary(ps, 2, d, 0, true, true), new BigDecimal(r[1]), false, cs);
        Field group = Field.group(ps, 0, len);
        CicsTask task = new CicsTask("ZC01", "ENTER", null, null);
        // WRITEQ TS FROM / READQ TS INTO, as cics_queues.ts_queue generates them
        byte[] stored = DetCics.toRegion(DetCics.bytes(group, group.length()), cs, region);
        task.writeqTs("Q", stored);
        CicsTask.TsResult ts = task.readqTsNext("Q", len);
        System.out.println("TS " + pg + " " + d + " " + hex(ts.data()) + " " + read(DetCics.fromRegion(ts.data(), region, cs), len, d, cs));
        // WRITEQ TD / READQ TD: the record is the program's own text (a String in CS)
        task.writeqTd("QTD1", new String(DetCics.bytes(group, group.length()), cs));
        CicsTask.TdResult td = task.readqTd("QTD1", len);
        System.out.println("TD " + pg + " " + d + " " + hex(td.data().getBytes(cs)) + " " + read(td.data().getBytes(cs), len, d, cs));
        // START FROM / RETRIEVE INTO: the data the started task is handed, through the same pages
        byte[] sent = DetCics.toRegion(DetCics.startData(group, len), cs, region);
        System.out.println("ST " + pg + " " + d + " " + hex(sent) + " " + read(DetCics.fromRegion(sent, region, cs), len, d, cs));
        Cobol.swapZosComp5(before);
      }}
    }}
  }}
}}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK (javac)")
@pytest.mark.slow(
    reason="compiles the generated CicsTask and det runtime with javac (cold ~10-20 s on a loaded runner)"
)
def test_a_comp5_group_through_queues_and_start_keeps_its_values_and_its_page_image(tmp_path):
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
    want = []
    for page in PAGES:
        for kind in ("TS", "TD", "ST"):
            for d, v, h in ITEMS:
                raw = bytes.fromhex("4142" + h)  # IBM's image: the text pair, then the big-endian item
                image = raw if page == "same" or kind == "TD" else raw.decode("latin-1").encode("cp037")
                want.append(f"{kind} {PAGES[page]} {d} {image.hex().upper()} {v}")
    got = sorted(run.stdout.splitlines())
    assert got == sorted(want), run.stdout
    assert len(got) == 18
