package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.Charset;

/** Numeric storage codecs: zoned, packed and binary. A signed zoned digit is overpunched `{A-I` / `}J-R`. */
final class Codec {
    static final String POSITIVE = "{ABCDEFGHI";
    static final String NEGATIVE = "}JKLMNOPQR";

    /** TRUNC(STD): a binary item holds at most its PICTURE's digits. GnuCOBOL under `-std=ibm` (the equivalence
     *  harness) does not: a binary item holds whatever its 2 / 4 / 8 bytes hold (TRUNC(BIN)), so that is the default. */
    static volatile boolean truncBinary = false;

    private Codec() {}

    /** A decimal as sign and magnitude, so that a negative zero survives a MOVE. */
    static final class Num {
        final BigInteger mag;
        final int scale;
        final boolean neg;

        Num(BigInteger mag, int scale, boolean neg) {
            this.mag = mag;
            this.scale = scale;
            this.neg = neg;
        }

        BigDecimal value() {
            BigDecimal v = new BigDecimal(mag, scale);
            return neg ? v.negate() : v;
        }

        static Num of(BigDecimal v) {
            return new Num(v.unscaledValue().abs(), v.scale(), v.signum() < 0);
        }
    }

    static char ch(byte b, Charset cs) {
        return new String(new byte[] {b}, cs).charAt(0);
    }

    static byte by(char c, Charset cs) {
        return String.valueOf(c).getBytes(cs)[0];
    }

    static byte space(Charset cs) {
        return by(' ', cs);
    }

    /** digit value and sign of a zoned byte: {digit, 1 if overpunched negative, 1 if overpunched positive}. */
    private static int[] zonedDigit(byte b, Charset cs, boolean overpunch) {
        char c = ch(b, cs);
        if (c >= '0' && c <= '9') return new int[] {c - '0', 0, 0};
        if (overpunch) {
            int p = POSITIVE.indexOf(c);
            if (p >= 0) return new int[] {p, 0, 1};
            int n = NEGATIVE.indexOf(c);
            if (n >= 0) return new int[] {n, 1, 0};
        }
        return new int[] {b & 0x0F, 0, 0};
    }

    static Num read(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                boolean neg = false;
                int start = f.off;
                int n = f.digits;
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.off : f.off + f.digits;
                    neg = ch(d[sp], cs) == '-';
                    if (f.signLeading) start = f.off + 1;
                }
                BigInteger v = BigInteger.ZERO;
                for (int i = 0; i < n; i++) {
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == n - 1);
                    int[] z = zonedDigit(d[start + i], cs, signPos);
                    if (signPos && z[1] == 1) neg = true;
                    v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(z[0]));
                }
                return new Num(v, f.scale, neg && f.signed);
            }
            case NUMERIC_PACKED: {
                BigInteger v = BigInteger.ZERO;
                for (int i = 0; i < f.len; i++) {
                    int b = d[f.off + i] & 0xFF;
                    v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b >> 4, 9)));
                    if (i < f.len - 1) v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b & 0x0F, 9)));
                }
                int sign = d[f.off + f.len - 1] & 0x0F;
                return new Num(v, f.scale, f.signed && (sign == 0x0D || sign == 0x0B));
            }
            case NUMERIC_BINARY: {
                byte[] b = new byte[f.len];
                for (int i = 0; i < f.len; i++) {
                    b[i] = f.nativeBin ? d[f.off + f.len - 1 - i] : d[f.off + i];
                }
                BigInteger v = f.signed ? new BigInteger(b) : new BigInteger(1, b);
                return new Num(v.abs(), f.scale, v.signum() < 0);
            }
            default:
                throw new IllegalArgumentException("not a numeric item: " + f.kind);
        }
    }

    /** The unscaled magnitude `m` (already at the field's scale) with sign `neg`, stored truncated to the digits. */
    static void write(Field f, BigInteger m, boolean neg, Charset cs) {
        byte[] d = f.st.bytes;
        BigInteger limit = BigInteger.TEN.pow(f.digits);
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                String s = m.mod(limit).toString();
                s = "0".repeat(f.digits - s.length()) + s;
                boolean negative = neg && f.signed;
                int start = f.off;
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.off : f.off + f.digits;
                    d[sp] = by(negative ? '-' : '+', cs);
                    if (f.signLeading) start = f.off + 1;
                }
                for (int i = 0; i < f.digits; i++) {
                    char c = s.charAt(i);
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == f.digits - 1);
                    if (signPos) c = (negative ? NEGATIVE : POSITIVE).charAt(c - '0');
                    d[start + i] = by(c, cs);
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
                    d[f.off + i] = (byte) ((hi << 4) | lo);
                }
                return;
            }
            case NUMERIC_BINARY: {
                BigInteger v = f.nativeBin || !truncBinary ? m : m.mod(limit);
                if (neg && f.signed) v = v.negate();
                byte[] b = v.toByteArray();
                byte fill = (byte) (v.signum() < 0 ? 0xFF : 0x00);
                for (int i = 0; i < f.len; i++) {
                    int from = b.length - f.len + i;
                    byte x = from >= 0 ? b[from] : fill;
                    d[f.nativeBin ? f.off + f.len - 1 - i : f.off + i] = x;
                }
                return;
            }
            default:
                throw new IllegalArgumentException("not a numeric item: " + f.kind);
        }
    }

    /** Whether `magnitude` (at the field's scale) fits the field without losing high-order digits. */
    static boolean fits(Field f, BigInteger magnitude, boolean neg) {
        if (f.kind == Field.Kind.NUMERIC_BINARY && (f.nativeBin || !truncBinary)) {
            int bits = f.len * 8;
            BigInteger v = neg && f.signed ? magnitude.negate() : magnitude;
            BigInteger lo = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).negate() : BigInteger.ZERO;
            BigInteger hi = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).subtract(BigInteger.ONE)
                    : BigInteger.ONE.shiftLeft(bits).subtract(BigInteger.ONE);
            return v.compareTo(lo) >= 0 && v.compareTo(hi) <= 0;
        }
        return magnitude.compareTo(BigInteger.TEN.pow(f.digits)) < 0;
    }
}
