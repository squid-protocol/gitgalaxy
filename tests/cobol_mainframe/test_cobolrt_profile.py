"""Tests for CobolProfile (#4714): explicit per-estate options profile and thread isolation."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"

DRIVER_JAVA = r"""package ggtest.cobolrt;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

public final class ProfileDriver {
    public static void main(String[] args) throws Exception {
        Charset cs = Cobol.recordCharset(StandardCharsets.ISO_8859_1);

        // 1. Fingerprint changes when options change
        CobolProfile pBin = CobolProfile.defaults();
        CobolProfile pStd = pBin.withTrunc(CobolProfile.TruncMode.STD)
                .withNumproc(CobolProfile.NumprocMode.PFD)
                .withArith(CobolProfile.ArithMode.EXTEND);
        if (pBin.fingerprint().equals(pStd.fingerprint())) {
            throw new AssertionError("fingerprints must differ");
        }

        // 2. Same logic under two profiles: TRUNC(BIN) vs TRUNC(STD)
        Storage sBin = new Storage(2);
        Field fBin = Field.binary(sBin, 0, 4, 0, true, false);
        CobolProfile.runWith(pBin, () -> Cobol.store(fBin, new BigDecimal("12345"), false, cs));
        if (Cobol.num(fBin, cs).intValue() != 12345) {
            throw new AssertionError("expected 12345 under TRUNC(BIN)");
        }
        CobolProfile.runWith(pStd, () -> Cobol.store(fBin, new BigDecimal("12345"), false, cs));
        if (Cobol.num(fBin, cs).intValue() != 2345) {
            throw new AssertionError("expected 2345 under TRUNC(STD)");
        }

        // 3. NUMPROC(PFD) refuses non-preferred packed sign 0x0F on signed item, NOPFD accepts it
        Storage sPack = new Storage(2);
        Field fSignedPack = Field.packed(sPack, 0, 3, 0, true);
        sPack.bytes[0] = 0x01;
        sPack.bytes[1] = 0x2F; // unsigned F nibble on a signed item
        BigDecimal nopfdVal = CobolProfile.runWith(pBin, () -> Cobol.num(fSignedPack, cs));
        if (nopfdVal.intValue() != 12) {
            throw new AssertionError("expected 12 under NUMPROC(NOPFD)");
        }
        boolean refused = false;
        try {
            CobolProfile.runWith(pStd, () -> Cobol.num(fSignedPack, cs));
        } catch (UnsupportedOperationException e) {
            refused = e.getMessage().contains("NUMPROC(PFD)");
        }
        if (!refused) {
            throw new AssertionError("expected NUMPROC(PFD) refusal");
        }

        // 4. Thread isolation: concurrent TRUNC(BIN) vs TRUNC(STD) never bleed across threads
        CountDownLatch start = new CountDownLatch(1);
        AtomicReference<Throwable> err = new AtomicReference<>();
        Thread t1 = new Thread(() -> {
            try {
                start.await();
                CobolProfile.runWith(pBin, () -> {
                    Storage s = new Storage(2);
                    Field f = Field.binary(s, 0, 4, 0, true, false);
                    for (int i = 0; i < 2000; i++) {
                        Cobol.store(f, new BigDecimal("12345"), false, cs);
                        if (Cobol.num(f, cs).intValue() != 12345) {
                            throw new AssertionError("thread 1 saw TRUNC(STD) bleed");
                        }
                    }
                });
            } catch (Throwable t) {
                err.compareAndSet(null, t);
            }
        });
        Thread t2 = new Thread(() -> {
            try {
                start.await();
                CobolProfile.runWith(pStd, () -> {
                    Storage s = new Storage(2);
                    Field f = Field.binary(s, 0, 4, 0, true, false);
                    for (int i = 0; i < 2000; i++) {
                        Cobol.store(f, new BigDecimal("12345"), false, cs);
                        if (Cobol.num(f, cs).intValue() != 2345) {
                            throw new AssertionError("thread 2 saw TRUNC(BIN) bleed");
                        }
                    }
                });
            } catch (Throwable t) {
                err.compareAndSet(null, t);
            }
        });
        t1.start();
        t2.start();
        start.countDown();
        t1.join();
        t2.join();
        if (err.get() != null) {
            throw new AssertionError(err.get());
        }
        System.out.println("PROFILE OK");
    }
}
"""


def test_cobol_profile_and_thread_isolation() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dst = tmp / "ggtest" / "cobolrt"
        for p in list(RT.glob("*.java")) + list((RT / "standalone").glob("*.java")):
            rel = p.relative_to(RT)
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(p.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest"), encoding="utf-8")
        (dst / "ProfileDriver.java").write_text(DRIVER_JAVA, encoding="utf-8")
        files = [str(p) for p in dst.rglob("*.java")]
        comp = subprocess.run(  # noqa: S603
            ["javac", "-encoding", "UTF-8", "-d", d, *files],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if comp.returncode != 0:
            raise AssertionError(f"javac failed:\n{comp.stderr}")
        run = subprocess.run(  # noqa: S603
            ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", d, "ggtest.cobolrt.ProfileDriver"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if run.returncode != 0:
            raise AssertionError(f"java failed:\n{run.stderr}\n{run.stdout}")
        if "PROFILE OK" not in run.stdout:
            raise AssertionError(run.stdout)


def test_det_translator_embeds_profile_and_fingerprint(tmp_path: Path) -> None:
    from gitgalaxy.tools.cobol_to_java.det import program as det_prog

    cbl = tmp_path / "OPT1.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. OPT1.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-N PIC S9(4) COMP VALUE 1.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n",
        encoding="utf-8",
    )
    stub = "package com.example.service;\npublic class Opt1Service {}\n"

    r_default = det_prog.translate(cbl, [], stub, "com.example")
    r_pfd = det_prog.translate(cbl, [], stub, "com.example", options=["TRUNC(BIN)", "NUMPROC(PFD)", "INTDATE(LILIAN)"])

    assert "public static final CobolProfile PROFILE = new CobolProfile(" in r_default.java
    assert "CobolProfile.TruncMode.STD" in r_default.java
    assert "CobolProfile.TruncMode.BIN" in r_pfd.java
    assert "CobolProfile.NumprocMode.PFD" in r_pfd.java
    assert r_default.stats["profile_fingerprint"] != r_pfd.stats["profile_fingerprint"]
    assert "INTDATE=LILIAN" in r_pfd.stats["profile_fingerprint"]
