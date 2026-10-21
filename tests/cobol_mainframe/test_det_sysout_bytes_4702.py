"""#4702 (D2 re-check of #4698): what the det runtime writes for a DISPLAY and a hexadecimal literal under each record
charset, against the register's D2 text -- a hex literal is exactly its bytes, the SYSOUT record separator a plain LF
(0x0A) in every charset (never the charset's "\\n": 0x15 / 0x25 on EBCDIC), WITH NO ADVANCING no separator.

The runtime (batch Sysout and standalone Sysout, Cobol.hex) is compiled once and driven directly, one JVM per
charset: no GnuCOBOL, no Docker. The GnuCOBOL side of the high bytes is test_det_bytes_4690.py.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_det_programs import PKG, _batch_package, _java

pytestmark = pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")

SINGLE_BYTE = ["ISO-8859-1", "IBM037", "IBM1047", "windows-1252"]
MAIN = f"""import {PKG}.cobolrt.Cobol;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.Charset;

public class Main {{
    static String hex(byte[] b) {{
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format("%02X", x));
        return s.toString();
    }}

    public static void main(String[] a) throws Exception {{
        Charset cs = Cobol.recordCharset(Charset.forName(System.getProperty("gitgalaxy.data.charset")));
        PrintStream real = System.out;
        for (String mode : new String[] {{"batch", "standalone"}}) {{
            ByteArrayOutputStream cap = new ByteArrayOutputStream();
            System.setOut(new PrintStream(cap, true));
            if (mode.equals("batch")) {{
                {PKG}.batch.Sysout.display("AB", Cobol.hex("\\u0041\\u00C3\\u00A9\\u0015\\u0025", cs));
                {PKG}.batch.Sysout.displayNoAdvancing("C");
                {PKG}.batch.Sysout.display("D");
            }} else {{
                {PKG}.cobolrt.standalone.Sysout.display("AB", Cobol.hex("\\u0041\\u00C3\\u00A9\\u0015\\u0025", cs));
                {PKG}.cobolrt.standalone.Sysout.displayNoAdvancing("C");
                {PKG}.cobolrt.standalone.Sysout.display("D");
            }}
            System.setOut(real);
            real.println(mode + " " + hex(cap.toByteArray()));
        }}
        StringBuilder all = new StringBuilder("hex");
        for (int b = 0; b < 256; b++) {{
            try {{
                all.append(' ').append(hex(Cobol.hex(String.valueOf((char) b), cs).getBytes(cs)));
            }} catch (UnsupportedOperationException e) {{
                all.append(" REFUSED");
            }}
        }}
        real.println(all);
    }}
}}
"""


@functools.cache
def _classes() -> Path:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-sysout-4702-"))
    atexit.register(shutil.rmtree, base, True)
    src = base / "java"
    files = {
        k: v for k, v in P.runtime_files(PKG, batch=True).items() if not k.startswith(("cobolrt/cics/", "cobolrt/sql/"))
    }
    files["cobolrt/standalone/Sysout.java"] = (
        (P.RUNTIME / "standalone/Sysout.java").read_text(encoding="utf-8").replace("__PACKAGE__", PKG)
    )
    for rel, text in files.items():
        (src / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / PKG / rel).write_text(text)
    _batch_package(src)
    rec = src / PKG / "entity/vsam/CobolRecords.java"  # both Sysouts read the record charset; here, the property
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(
        f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset.Charset "
        'charset() {\n        return java.nio.charset.Charset.forName(System.getProperty("gitgalaxy.data.charset"));\n'
        "    }\n}\n"
    )
    (src / "Main.java").write_text(MAIN)
    jdk = _java()
    assert jdk is not None
    out = base / "classes"
    subprocess.run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(out),  # noqa: S603
                    *map(str, src.rglob("*.java"))], check=True)  # fmt: skip
    return out


@functools.cache
def _run(charset: str) -> dict[str, str]:
    jdk = _java()
    assert jdk is not None
    proc = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",  # noqa: S603
                           f"-Dgitgalaxy.data.charset={charset}", "-cp", str(_classes()), "Main"],
                          capture_output=True, text=True, encoding="utf-8", check=True)  # fmt: skip
    return {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in proc.stdout.splitlines()}


def _record_bytes(charset: str) -> bytes:
    """What `DISPLAY 'AB', X'41C3A9'`, `DISPLAY 'C' WITH NO ADVANCING`, `DISPLAY 'D'` write: the hex literal's five
    bytes as they are (valid UTF-8 too), one LF after the first and the last record, none after 'C'."""
    return "AB".encode(charset) + b"\x41\xc3\xa9\x15\x25" + b"\n" + "C".encode(charset) + "D".encode(charset) + b"\n"


@pytest.mark.parametrize("charset", [*SINGLE_BYTE, "UTF-8"])
@pytest.mark.parametrize("mode", ["batch", "standalone"])
def test_display_ends_a_record_in_one_plain_lf_and_a_hex_literal_is_its_bytes(charset, mode):
    """D2: the separator is the capture's framing (0x0A) and none follows WITH NO ADVANCING, never the charset's
    "\\n" (0x15 / 0x25 on EBCDIC); X'41C3A91525' is exactly those five bytes."""
    assert bytes.fromhex(_run(charset)[mode]) == _record_bytes(charset)


@pytest.mark.parametrize("charset", SINGLE_BYTE)
def test_every_byte_value_survives_as_a_hex_literal_in_a_single_byte_charset(charset):
    """D2: X'hh' is exactly byte hh -- the five bytes windows-1252 leaves unmapped (81 8D 8F 90 9D) included."""
    got = _run(charset)["hex"].split()
    assert got == [f"{b:02X}" for b in range(256)]


def test_a_hex_literal_in_a_multi_byte_record_charset_refuses_the_bytes_it_cannot_keep():
    """D2: UTF-8 holds X'00'..X'7F' as themselves; X'80'..X'FF' alone are not text in it, so the literal refuses by
    name rather than writing U+FFFD's bytes (EF BF BD) for them. No burned estate runs a multi-byte record charset."""
    got = _run("UTF-8")["hex"].split()
    assert got == [f"{b:02X}" for b in range(128)] + ["REFUSED"] * 128
