"""CPU-time microbenchmark and A/B parity harness for cobolrt (#4717, #8423).

Measures per-thread CPU time (ThreadMXBean.getCurrentThreadCpuTime) after JIT warmup,
taking the fastest of 3 rounds so measurements are independent of wall-clock runner load.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"

BENCH_JAVA = r"""package ggtest.cobolrt;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Random;

public final class CobolrtBench {
    private static final ThreadMXBean TMX = ManagementFactory.getThreadMXBean();

    private static long cpuNanos() {
        return TMX.isCurrentThreadCpuTimeSupported() ? TMX.getCurrentThreadCpuTime() : System.nanoTime();
    }

    @FunctionalInterface
    interface BenchOp {
        long run(int iters);
    }

    private static double measureNsPerOp(String name, int warmup, int iters, int rounds, BenchOp op) {
        long sink = 0;
        for (int w = 0; w < 3; w++) {
            sink ^= op.run(warmup);
        }
        long bestNs = Long.MAX_VALUE;
        for (int r = 0; r < rounds; r++) {
            long t0 = cpuNanos();
            sink ^= op.run(iters);
            long dt = cpuNanos() - t0;
            if (dt < bestNs) bestNs = dt;
        }
        double nsPerOp = (double) bestNs / iters;
        System.out.printf("BENCH %-26s %8.1f ns/op  (best of %d x %d, sink=%d)%n",
                name, nsPerOp, rounds, iters, sink & 0xFF);
        return nsPerOp;
    }

    public static void runBench(int iters) {
        Charset ebcdic = Cobol.recordCharset(Charset.forName("IBM037"));
        Charset latin1 = Cobol.recordCharset(StandardCharsets.ISO_8859_1);

        Storage sPack = new Storage(6);
        Field fPack = Field.packed(sPack, 0, 11, 2, true);
        Cobol.store(fPack, new BigDecimal("12345.67"), false, ebcdic);

        Storage sZonedE = new Storage(11);
        Field fZonedE = Field.zoned(sZonedE, 0, 11, 2, true, false, false);
        Cobol.store(fZonedE, new BigDecimal("12345.67"), false, ebcdic);

        Storage sZonedA = new Storage(11);
        Field fZonedA = Field.zoned(sZonedA, 0, 11, 2, true, false, false);
        Cobol.store(fZonedA, new BigDecimal("12345.67"), false, latin1);

        Storage sBin = new Storage(4);
        Field fBin = Field.binary(sBin, 0, 9, 0, true, false);
        Cobol.store(fBin, new BigDecimal("12345"), false, ebcdic);

        BigDecimal delta = new BigDecimal("1.05");
        BigDecimal deltaInt = new BigDecimal("1");
        int warmup = Math.min(20_000, Math.max(1_000, iters / 10));

        measureNsPerOp("packed_add_store", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                BigDecimal v = Cobol.num(fPack, ebcdic);
                BigDecimal r = Cobol.add(v, delta);
                Cobol.store(fPack, r, false, ebcdic);
                acc += sPack.bytes[5] & 0xFF;
            }
            return acc;
        });

        measureNsPerOp("zoned_ebcdic_add_store", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                BigDecimal v = Cobol.num(fZonedE, ebcdic);
                BigDecimal r = Cobol.add(v, delta);
                Cobol.store(fZonedE, r, false, ebcdic);
                acc += sZonedE.bytes[10] & 0xFF;
            }
            return acc;
        });

        measureNsPerOp("zoned_ascii_add_store", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                BigDecimal v = Cobol.num(fZonedA, latin1);
                BigDecimal r = Cobol.add(v, delta);
                Cobol.store(fZonedA, r, false, latin1);
                acc += sZonedA.bytes[10] & 0xFF;
            }
            return acc;
        });

        measureNsPerOp("binary_add_store", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                BigDecimal v = Cobol.num(fBin, ebcdic);
                BigDecimal r = Cobol.add(v, deltaInt);
                Cobol.store(fBin, r, false, ebcdic);
                acc += sBin.bytes[3] & 0xFF;
            }
            return acc;
        });

        measureNsPerOp("move_zoned_to_packed", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                Cobol.move(fZonedE, fPack, ebcdic);
                acc += sPack.bytes[5] & 0xFF;
            }
            return acc;
        });

        measureNsPerOp("move_packed_to_zoned", warmup, iters, 3, n -> {
            long acc = 0;
            for (int i = 0; i < n; i++) {
                Cobol.move(fPack, fZonedE, ebcdic);
                acc += sZonedE.bytes[10] & 0xFF;
            }
            return acc;
        });
    }

    // Reference BigInteger-only Codec implementation for A/B parity verification
    private static char refCh(byte b, Charset cs) {
        return new String(new byte[] {b}, cs).charAt(0);
    }

    private static byte refBy(char c, Charset cs) {
        return String.valueOf(c).getBytes(cs)[0];
    }

    private static int[] refZonedDigit(byte b, Charset cs, boolean overpunch) {
        char c = refCh(b, cs);
        if (c >= '0' && c <= '9') return new int[] {c - '0', 0, 0};
        if (overpunch) {
            int p = Codec.POSITIVE.indexOf(c);
            if (p >= 0) return new int[] {p, 0, 1};
            int n = Codec.NEGATIVE.indexOf(c);
            if (n >= 0) return new int[] {n, 1, 0};
        }
        return new int[] {b & 0x0F, 0, 0};
    }

    private static Codec.Num refReadAny(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                boolean neg = false;
                int start = f.at();
                int n = f.digits;
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.at() : f.at() + f.digits;
                    neg = refCh(d[sp], cs) == '-';
                    if (f.signLeading) start = f.at() + 1;
                }
                BigInteger v = BigInteger.ZERO;
                for (int i = 0; i < n; i++) {
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == n - 1);
                    int[] z = refZonedDigit(d[start + i], cs, signPos);
                    if (signPos && z[1] == 1) neg = true;
                    v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(z[0]));
                }
                return new Codec.Num(v, f.scale, neg && f.signed);
            }
            case NUMERIC_PACKED: {
                BigInteger v = BigInteger.ZERO;
                for (int i = 0; i < f.len; i++) {
                    int b = d[f.at() + i] & 0xFF;
                    v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b >> 4, 9)));
                    if (i < f.len - 1) v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b & 0x0F, 9)));
                }
                int sign = d[f.at() + f.len - 1] & 0x0F;
                return new Codec.Num(v, f.scale, f.signed && (sign == 0x0D || sign == 0x0B));
            }
            case NUMERIC_BINARY: {
                byte[] b = new byte[f.len];
                for (int i = 0; i < f.len; i++) {
                    b[i] = Codec.littleEndian(f) ? d[f.at() + f.len - 1 - i] : d[f.at() + i];
                }
                BigInteger v = f.signed ? new BigInteger(b) : new BigInteger(1, b);
                return new Codec.Num(v.abs(), f.scale, v.signum() < 0);
            }
            default:
                throw new IllegalArgumentException();
        }
    }

    private static void refWrite(Field f, BigInteger m, boolean neg, Charset cs) {
        byte[] d = f.st.bytes;
        BigInteger limit = BigInteger.TEN.pow(f.digits);
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                String s = m.mod(limit).toString();
                s = "0".repeat(f.digits - s.length()) + s;
                boolean negative = neg && f.signed;
                int start = f.at();
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.at() : f.at() + f.digits;
                    d[sp] = refBy(negative ? '-' : '+', cs);
                    if (f.signLeading) start = f.at() + 1;
                }
                for (int i = 0; i < f.digits; i++) {
                    char c = s.charAt(i);
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == f.digits - 1);
                    if (signPos) c = (negative ? Codec.NEGATIVE : Codec.POSITIVE).charAt(c - '0');
                    d[start + i] = refBy(c, cs);
                }
                return;
            }
            case NUMERIC_PACKED: {
                String s = m.mod(limit).toString();
                int n = f.len * 2 - 1;
                s = "0".repeat(n - s.length()) + s;
                int sign = !f.signed ? 0x0F : neg ? 0x0D : 0x0C;
                for (int i = 0; i < f.len; i++) {
                    int hi = s.charAt(2 * i) - '0';
                    int lo = i < f.len - 1 ? s.charAt(2 * i + 1) - '0' : sign;
                    d[f.at() + i] = (byte) ((hi << 4) | lo);
                }
                return;
            }
            case NUMERIC_BINARY: {
                if (Codec.pastPictureUnderOpt(f, m)) throw Codec.truncOptUnpredictable(f, m, neg);
                BigInteger v = f.nativeBin || !Codec.truncBinary() ? m : m.mod(limit);
                if (neg && f.signed) v = v.negate();
                byte[] b = v.toByteArray();
                byte fill = (byte) (v.signum() < 0 ? 0xFF : 0x00);
                for (int i = 0; i < f.len; i++) {
                    int from = b.length - f.len + i;
                    byte x = from >= 0 ? b[from] : fill;
                    d[Codec.littleEndian(f) ? f.at() + f.len - 1 - i : f.at() + i] = x;
                }
                return;
            }
            default:
                throw new IllegalArgumentException();
        }
    }

    private static boolean refFits(Field f, BigInteger magnitude, boolean neg) {
        if (f.kind == Field.Kind.NUMERIC_BINARY && (f.nativeBin || !Codec.truncBinary())) {
            int bits = f.len * 8;
            BigInteger v = neg && f.signed ? magnitude.negate() : magnitude;
            BigInteger lo = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).negate() : BigInteger.ZERO;
            BigInteger hi = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).subtract(BigInteger.ONE)
                    : BigInteger.ONE.shiftLeft(bits).subtract(BigInteger.ONE);
            return v.compareTo(lo) >= 0 && v.compareTo(hi) <= 0;
        }
        return magnitude.compareTo(BigInteger.TEN.pow(f.digits)) < 0;
    }

    public static void runParity(int fuzzCount) {
        Charset[] charsets = {
            Cobol.recordCharset(Charset.forName("IBM037")),
            Cobol.recordCharset(StandardCharsets.ISO_8859_1),
            StandardCharsets.UTF_8
        };
        Random rng = new Random(42L);
        int checked = 0;

        for (Charset cs : charsets) {
            for (int b = 0; b < 256; b++) {
                if (cs == StandardCharsets.UTF_8 && b >= 128) continue;
                byte bb = (byte) b;
                char c = Codec.ch(bb, cs);
                char rc = refCh(bb, cs);
                if (c != rc) {
                    throw new AssertionError("ch mismatch for " + cs + " byte " + b + ": " + (int) c + " vs " + (int) rc);
                }
                if (c != '\uFFFD' && Codec.by(c, cs) != refBy(c, cs)) {
                    throw new AssertionError("by mismatch for " + cs + " char " + (int) c);
                }
            }
        }

        for (int i = 0; i < fuzzCount; i++) {
            Charset cs = charsets[rng.nextInt(2)]; // IBM037 or ISO-8859-1 lossless
            boolean truncBin = rng.nextBoolean();
            boolean zosComp5 = rng.nextBoolean();
            CobolProfile.swap(new CobolProfile(
                    truncBin ? CobolProfile.TruncMode.STD : CobolProfile.TruncMode.BIN,
                    CobolProfile.NumprocMode.NOPFD,
                    CobolProfile.ArithMode.COMPAT,
                    zosComp5, false, false, "IBM037"));

            int kind = rng.nextInt(3);
            int digits = 1 + rng.nextInt(22);
            int scale = rng.nextInt(Math.min(digits + 1, 7));
            boolean signed = rng.nextBoolean();
            boolean signLeading = rng.nextBoolean();
            boolean signSeparate = rng.nextBoolean();
            boolean nativeBin = rng.nextBoolean();

            Storage st1;
            Storage st2;
            Field f1;
            Field f2;
            if (kind == 0) {
                int len = digits + (signed && signSeparate ? 1 : 0);
                st1 = new Storage(len);
                st2 = new Storage(len);
                f1 = Field.zoned(st1, 0, digits, scale, signed, signLeading, signSeparate);
                f2 = Field.zoned(st2, 0, digits, scale, signed, signLeading, signSeparate);
            } else if (kind == 1) {
                st1 = new Storage(digits / 2 + 1);
                st2 = new Storage(digits / 2 + 1);
                f1 = Field.packed(st1, 0, digits, scale, signed);
                f2 = Field.packed(st2, 0, digits, scale, signed);
            } else {
                digits = 1 + rng.nextInt(18);
                int len = digits <= 4 ? 2 : digits <= 9 ? 4 : 8;
                st1 = new Storage(len);
                st2 = new Storage(len);
                f1 = Field.binary(st1, 0, digits, scale, signed, nativeBin);
                f2 = Field.binary(st2, 0, digits, scale, signed, nativeBin);
            }

            // Test write + read + fits on edge & random BigIntegers
            BigInteger mag = switch (i % 6) {
                case 0 -> BigInteger.ZERO;
                case 1 -> BigInteger.ONE;
                case 2 -> BigInteger.TEN.pow(Math.min(digits, 18)).subtract(BigInteger.ONE);
                case 3 -> BigInteger.TEN.pow(Math.min(digits, 18));
                case 4 -> new BigInteger(63, rng);
                default -> new BigInteger(75, rng);
            };
            boolean neg = rng.nextBoolean();

            Codec.write(f1, mag, neg, cs);
            refWrite(f2, mag, neg, cs);
            if (!Arrays.equals(st1.bytes, st2.bytes)) {
                throw new AssertionError("write bytes mismatch at i=" + i + " kind=" + f1.kind
                        + " digits=" + digits + " signed=" + signed + " mag=" + mag + " neg=" + neg);
            }

            Codec.Num n1 = Codec.read(f1, cs);
            Codec.Num n2 = refReadAny(f2, cs);
            if (!n1.mag.equals(n2.mag) || n1.scale != n2.scale || n1.neg != n2.neg) {
                throw new AssertionError("read mismatch at i=" + i + " kind=" + f1.kind
                        + " got=(" + n1.mag + "," + n1.neg + ") ref=(" + n2.mag + "," + n2.neg + ")");
            }
            BigDecimal d1 = Codec.readDecimal(f1, cs);
            BigDecimal d2 = n2.value();
            if (d1.compareTo(d2) != 0 || d1.scale() != d2.scale()) {
                throw new AssertionError("readDecimal mismatch at i=" + i + " kind=" + f1.kind
                        + " got=" + d1 + " ref=" + d2);
            }

            if (Codec.fits(f1, mag, neg) != refFits(f2, mag, neg)) {
                throw new AssertionError("fits mismatch at i=" + i + " kind=" + f1.kind
                        + " digits=" + digits + " mag=" + mag + " neg=" + neg);
            }
            checked++;
        }
        CobolProfile.swap(CobolProfile.defaults());
        System.out.println("PARITY OK: " + checked + " fuzzed cases + charset tables");
    }

    public static void main(String[] args) {
        String mode = args.length > 0 ? args[0] : "both";
        int iters = args.length > 1 ? Integer.parseInt(args[1]) : 200_000;
        int fuzz = args.length > 2 ? Integer.parseInt(args[2]) : 5_000;
        if ("parity".equals(mode) || "both".equals(mode)) {
            runParity(fuzz);
        }
        if ("bench".equals(mode) || "both".equals(mode)) {
            runBench(iters);
        }
    }
}
"""


def run(mode: str = "both", iters: int = 200_000, fuzz: int = 5_000) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        dst = tmp / "ggtest" / "cobolrt"
        for p in list(RT.glob("*.java")) + list((RT / "standalone").glob("*.java")):
            rel = p.relative_to(RT)
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(p.read_text().replace("__PACKAGE__", "ggtest"))
        (dst / "CobolrtBench.java").write_text(BENCH_JAVA)
        files = [str(p) for p in dst.rglob("*.java")]
        comp = subprocess.run(["javac", "-d", d, *files], capture_output=True, text=True)  # noqa: S603, S607
        if comp.returncode != 0:
            raise RuntimeError(f"javac failed:\n{comp.stderr}")
        return subprocess.run(  # noqa: S603
            ["java", "-cp", d, "ggtest.cobolrt.CobolrtBench", mode, str(iters), str(fuzz)],  # noqa: S607
            capture_output=True,
            text=True,
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CPU-time benchmark and A/B parity harness for cobolrt")
    ap.add_argument("--mode", choices=("parity", "bench", "both"), default="both")
    ap.add_argument("--iters", type=int, default=200_000)
    ap.add_argument("--fuzz", type=int, default=5_000)
    args = ap.parse_args(argv)
    res = run(args.mode, args.iters, args.fuzz)
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, end="", file=sys.stderr)
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
