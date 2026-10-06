"""#4271: NUMPROC on both sides of a proof (oracle_assumptions.md C5), and floating-point items refused (C6).

- NUMPROC(MIG): Enterprise COBOL 5 and 6 no longer support it; "the compilation will get the default setting for
  NUMPROC ... the IBM default, which is NUMPROC(NOPFD)" (Enterprise COBOL for z/OS 6.4 Migration Guide, GC27-8715-03,
  Table 18). The harness compiles it as NOPFD for a case that states such a compiler, and refuses it otherwise.
- NUMPROC(PFD): "the compiler assumes that the sign in your data is one of three preferred signs" -- C signed positive
  or zero, D signed negative, F unsigned -- "and uses whatever sign it is given" (6.4 Programming Guide, SC27-8714-03,
  "Sign representation of zoned and packed-decimal data"). With preferred signs it computes as NOPFD; the det runtime
  refuses to read any other sign, and the harness proves a PFD program only through a det port.
- COMP-1 / COMP-2: IBM hexadecimal floating point on z/OS, and IBM evaluates a whole expression in floating point when
  any operand or receiver is one (Programming Guide, Appendix A); the translator computes such a statement in HFP
  (#4271 slice 1: test_det_hfp.py) and refuses by name what the oracle cannot decide.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_common as common  # noqa: E402

PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
V6 = {"product": "Enterprise COBOL", "version": "6.1", "evidence": "IGY.V6R1M0.SIGYCOMP"}


# ---- the oracle (equivalence_common) ---------------------------------------------------------------------------


def test_numproc_mig_compiles_as_the_default_under_enterprise_cobol_5_and_later():
    src = "   CBL NUMPROC(MIG),FLAG(I,W),RENT\n" + PLAIN  # IBM DBB EPSMPMT's card, from column 4
    text, flags = common.compile_options({"compiler": V6}, src)
    assert text == "\n" + PLAIN and flags == ["-fbinary-truncate"]  # NOPFD: GnuCOBOL's own sign processing
    assert common.numproc({"compiler": V6}, src) == "NOPFD"
    assert common.numproc({"compiler": {**V6, "version": "5.2"}}, src) == "NOPFD"


@pytest.mark.parametrize(
    "compiler", [None, {**V6, "version": "4.2"}, {**V6, "product": "VS COBOL II"}, {"version": "6"}]
)
def test_numproc_mig_is_refused_without_a_later_compiler(compiler):
    case = {"compiler": compiler} if compiler else {}
    with pytest.raises(common.UnsupportedOption, match=r"NUMPROC\(MIG\)"):
        common.compile_options(case, "       CBL NUMPROC(MIG)\n" + PLAIN)
    with pytest.raises(common.UnsupportedOption, match=r"NUMPROC\(MIG\)"):
        common.compile_options({**case, "compiler_options": ["NUMPROC(MIG)"]}, PLAIN)


def test_numproc_pfd_compiles_and_needs_a_det_port(tmp_path):
    src = "       PROCESS NUMPROC(PFD)\n" + PLAIN
    assert common.compile_options({}, src) == ("\n" + PLAIN, ["-fbinary-truncate"])
    model = tmp_path / "model" / "service"
    model.mkdir(parents=True)
    (model / "PService.java").write_text("package x;\npublic class PService {}\n", encoding="utf-8")
    det = tmp_path / "det" / "service"
    det.mkdir(parents=True)
    (det / "PService.java").write_text("// gitgalaxy-det-port: COBOL P ...\npackage x;\n", encoding="utf-8")
    for port in (tmp_path / "model", None, tmp_path / "absent"):
        with pytest.raises(common.UnsupportedOption, match=r"NUMPROC\(PFD\)"):
            common.numproc_guard({}, src, port)
    common.numproc_guard({}, src, tmp_path / "det")
    common.numproc_guard({}, PLAIN, tmp_path / "model")  # NOPFD: any port
    common.numproc_guard({"compiler_options": ["NUMPROC(PFD)"]}, "       CBL NUMPROC(NOPFD)\n" + PLAIN, None)


# ---- the translator --------------------------------------------------------------------------------------------


def test_each_entry_runs_with_its_programs_numproc(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "T.cbl"
    src.write_text(PLAIN, encoding="ascii")
    assert P.numproc_pfd(src) is False
    assert P.numproc_pfd(src, ["NUMPROC(PFD)"]) is True
    src.write_text("   CBL NUMPROC(MIG)\n" + PLAIN, encoding="ascii")
    assert P.numproc_pfd(src, ["NUMPROC(PFD)"]) is False  # the card wins; MIG compiles as IBM's default
    src.write_text("       PROCESS NUMPROC(PFD)\n" + PLAIN, encoding="ascii")
    assert P.numproc_pfd(src) is True
    java = "class S {\n    public void runTask(CicsTask task) {\n        x();\n    }\n}\n"
    out = P.with_trunc(java, True, True)
    assert "boolean pfdBefore = Cobol.swapNumprocPfd(true);  // NUMPROC(PFD)" in out
    assert "Cobol.swapNumprocPfd(pfdBefore);" in out.split("finally")[1]
    assert "Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)" in P.with_trunc(java, True)


def test_a_floating_point_statement_is_computed_in_hfp(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser
    from gitgalaxy.tools.cobol_to_java.det import program as P

    cbl = tmp_path / "FLT.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FLT.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01 F COMP-1.\n       01 N PIC 9(3)V99 VALUE 1.5.\n"
        "       PROCEDURE DIVISION.\n           COMPUTE F = N / 3\n           COMPUTE N = F * 2\n"
        "           GOBACK.\n",
        encoding="ascii",
    )
    (tmp_path / "project").mkdir()
    r = P.translate(cbl, [], "public class FltService {\n}\n", "p", None, tmp_path / "project")
    assert not r.stats["holes"], r.stats["holes"]
    assert "Hfp.divide(Hfp.of(Cobol.num(f2_N, CS)), Hfp.of(D3), true)" in r.java  # long: a literal operand
    assert "Hfp.multiply(Cobol.num(f1_F, CS), Hfp.of(D2), true)" in r.java
    assert "Field.hfp(" in r.java and "import p.cobolrt.Hfp;" in r.java


# ---- the runtime -----------------------------------------------------------------------------------------------


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


RUNTIME_PROBE = r"""
import p.cobolrt.*;
import java.nio.charset.*;
public class Probe {
    static final Charset CS = StandardCharsets.ISO_8859_1;
    static Field zoned(String text, boolean signed) {
        Storage s = new Storage(text.length());
        System.arraycopy(text.getBytes(CS), 0, s.bytes, 0, text.length());
        return Field.zoned(s, 0, text.length(), 0, signed, false, false);
    }
    static Field packed(int[] bytes, int digits, boolean signed) {
        Storage s = new Storage(bytes.length);
        for (int i = 0; i < bytes.length; i++) s.bytes[i] = (byte) bytes[i];
        return Field.packed(s, 0, digits, 0, signed);
    }
    static String read(Field f) {
        try { return Cobol.num(f, CS).toPlainString(); } catch (UnsupportedOperationException e) { return "REFUSED"; }
    }
    static String numeric(Field f) {
        try { return String.valueOf(Cobol.isNumeric(f, CS)); } catch (UnsupportedOperationException e) { return "REFUSED"; }
    }
    public static void main(String[] a) {
        Field[] fs = {
            zoned("12C", true), zoned("12L", true), zoned("123", true), zoned("12}", true), zoned("00}", true),
            zoned("123", false), zoned("12C", false),
            packed(new int[] {0x12, 0x3C}, 3, true), packed(new int[] {0x12, 0x3D}, 3, true),
            packed(new int[] {0x12, 0x3F}, 3, true), packed(new int[] {0x00, 0x0D}, 3, true),
            packed(new int[] {0x12, 0x3F}, 3, false), packed(new int[] {0x12, 0x3C}, 3, false),
        };
        for (boolean pfd : new boolean[] {false, true}) {
            boolean before = Cobol.swapNumprocPfd(pfd);
            StringBuilder out = new StringBuilder(pfd ? "PFD" : "NOPFD");
            for (Field f : fs) out.append(' ').append(read(f)).append('/').append(numeric(f));
            System.out.println(out);
            if (Cobol.swapNumprocPfd(before) != pfd) throw new IllegalStateException("swap");
        }
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_reads_preferred_signs_and_refuses_the_rest_under_pfd(tmp_path):
    rt = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
    out = tmp_path / "src/p/cobolrt"
    out.mkdir(parents=True)
    for f in rt.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    (tmp_path / "src/Probe.java").write_text(RUNTIME_PROBE)
    jdk = _jdk()
    files = [str(f) for f in (tmp_path / "src").rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"), *files], check=True)  # noqa: S603
    lines = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "Probe"], capture_output=True,  # noqa: S603
                           text=True, check=True).stdout.split("\n")  # fmt: skip
    nopfd = lines[0].split()[1:]
    pfd = lines[1].split()[1:]
    # NOPFD (IBM's default): every sign is read, as GnuCOBOL reads it
    assert nopfd == ["123/true", "-123/true", "123/true", "-120/true", "0/true", "123/true", "123/false",
                     "123/true", "-123/true", "123/true", "0/true", "123/true", "123/false"]  # fmt: skip
    # PFD: C, D (not on zero) signed and F unsigned are read; F signed, an overpunch unsigned, a negative zero,
    # packed F signed and C unsigned are refused; the class test refuses only F signed (Table 7)
    assert pfd == ["123/true", "-123/true", "REFUSED/REFUSED", "-120/true", "REFUSED/true", "123/true",
                   "REFUSED/false", "123/true", "-123/true", "REFUSED/REFUSED", "REFUSED/true", "123/true",
                   "REFUSED/false"]  # fmt: skip
