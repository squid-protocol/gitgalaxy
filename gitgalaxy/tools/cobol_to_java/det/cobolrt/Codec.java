package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.Charset;

/** Numeric storage codecs: zoned, packed and binary. A signed zoned digit is overpunched `{A-I` / `}J-R`. */
final class Codec {
    static final String POSITIVE = "{ABCDEFGHI";
    static final String NEGATIVE = "}JKLMNOPQR";

    static boolean truncBinary() {
        return CobolProfile.current().truncBinary();
    }

    static boolean zosComp5() {
        return CobolProfile.current().zosComp5();
    }

    /** Whether a COMP-5 item's bytes are held least significant first (the oracle's order, the default). */
    static boolean littleEndian(Field f) {
        return f.nativeBin && !zosComp5();
    }

    static boolean truncOpt() {
        return CobolProfile.current().truncOpt();
    }

    static boolean arithExtend() {
        return CobolProfile.current().arithExtend();
    }

    /** The stop of an intermediate past 30 digits under ARITH(EXTEND): `digits` is its digit count (a quotient's
     *  integer digits, its fraction being the 38 places cob_decimal_div keeps). */
    // [rule RT-NUM-ARITH-EXTEND-STOP]
    static BigDecimal arithExtendCheck(BigDecimal d, int digits) {
        if (arithExtend() && digits > 30) {
            throw new UnsupportedOperationException("ARITH(EXTEND): an intermediate result of " + digits
                    + " digits (past 30) is not modelled");
        }
        return d;
    }

    /** An add / subtract / multiply result under ARITH(EXTEND): past 30 digits it stops by name. */
    // [rule RT-NUM-ARITH-EXTEND-STOP]
    static BigDecimal arithExtendWide(BigDecimal r) {
        return arithExtendCheck(r, r.precision());
    }

    /** The named stop of a value past a binary receiver's PICTURE under TRUNC(OPT) (register C5, #4706). */
    // [rule RT-NUM-TRUNC-OPT-STOP]
    static UnsupportedOperationException truncOptUnpredictable(Field f, BigInteger magnitude, boolean neg) {
        return new UnsupportedOperationException("TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable ("
                + (neg && f.signed ? "-" : "") + new BigDecimal(magnitude, f.scale).toPlainString() + " into a "
                + (f.signed ? "signed " : "") + f.digits + "-digit binary item) is not modelled");
    }

    /** Whether storing `magnitude` (at the field's scale) in `f` meets the TRUNC(OPT) stop: a COMP / COMP-4 / BINARY
     *  item under TRUNC(OPT), the value past its PICTURE's digits. */
    static boolean pastPictureUnderOpt(Field f, BigInteger magnitude) {
        return truncOpt() && truncBinary() && f.kind == Field.Kind.NUMERIC_BINARY && !f.nativeBin
                && magnitude.compareTo(pow10(f.digits)) >= 0;
    }

    static boolean numprocPfd() {
        return CobolProfile.current().numprocPfd();
    }

    /** The refusal of a non-preferred sign under NUMPROC(PFD) (register C5). */
    // [rule RT-NUM-NUMPROC-PFD-SIGN]
    static UnsupportedOperationException nonPreferredSign(Field f) {
        return new UnsupportedOperationException("NUMPROC(PFD): a " + (f.signed ? "signed " : "unsigned ")
                + (f.kind == Field.Kind.NUMERIC_PACKED ? "packed" : "zoned")
                + " item with a non-preferred sign (IBM: the result depends on the generated code) is not modelled");
    }

    /** Whether a zoned item's sign byte, or a packed item's sign nibble, holds the preferred sign for the item and its
     *  value: C / D (a zero C) when signed, F when unsigned. SIGN SEPARATE items carry no sign nibble. */
    static boolean preferredSign(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        if (f.kind == Field.Kind.NUMERIC_PACKED) {
            int sign = d[f.at() + f.len - 1] & 0x0F;
            if (!f.signed) return sign == 0x0F;
            if (sign == 0x0C) return true;
            return sign == 0x0D && readAny(f, cs).mag.signum() != 0;
        }
        if (f.kind != Field.Kind.NUMERIC_DISPLAY || f.signSeparate) return true;
        char c = ch(d[f.signLeading ? f.at() : f.at() + f.digits - 1], cs);
        if (!f.signed) return c >= '0' && c <= '9';
        if (POSITIVE.indexOf(c) >= 0) return true;
        return NEGATIVE.indexOf(c) >= 0 && readAny(f, cs).mag.signum() != 0;
    }

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

    private static final long[] POW10_LONG = new long[19];
    private static final BigInteger[] POW10_BI = new BigInteger[39];
    static {
        POW10_LONG[0] = 1L;
        POW10_BI[0] = BigInteger.ONE;
        for (int i = 1; i < POW10_BI.length; i++) {
            POW10_BI[i] = POW10_BI[i - 1].multiply(BigInteger.TEN);
            if (i < POW10_LONG.length) POW10_LONG[i] = POW10_LONG[i - 1] * 10L;
        }
    }

    private static BigInteger pow10(int digits) {
        return digits < POW10_BI.length ? POW10_BI[digits] : BigInteger.TEN.pow(digits);
    }

    private static final class CharsetTable {
        final char[] decode = new char[256];
        final byte[] encode = new byte[256];
        final boolean[] hasEncode = new boolean[256];
        final boolean singleByte;

        CharsetTable(Charset cs) {
            this.singleByte = cs.newEncoder().maxBytesPerChar() == 1.0f;
            int limit = singleByte ? 256 : 128;
            for (int b = 0; b < limit; b++) {
                String s = new String(new byte[] {(byte) b}, cs);
                decode[b] = s.charAt(0);
            }
            for (int c = 0; c < limit; c++) {
                byte[] enc = String.valueOf((char) c).getBytes(cs);
                if (enc.length > 0) {
                    encode[c] = enc[0];
                    hasEncode[c] = true;
                }
            }
        }
    }

    private static final java.util.concurrent.ConcurrentHashMap<Charset, CharsetTable> CS_CACHE =
            new java.util.concurrent.ConcurrentHashMap<>();

    private static CharsetTable table(Charset cs) {
        return CS_CACHE.computeIfAbsent(cs, CharsetTable::new);
    }

    static char ch(byte b, Charset cs) {
        if (cs instanceof Lossless l) return l.decodeByte(b);
        CharsetTable t = table(cs);
        int idx = b & 0xFF;
        if (t.singleByte || idx < 128) return t.decode[idx];
        return new String(new byte[] {b}, cs).charAt(0);
    }

    static byte by(char c, Charset cs) {
        if (cs instanceof Lossless l) return l.encodeChar(c);
        CharsetTable t = table(cs);
        if (c < (t.singleByte ? 256 : 128) && t.hasEncode[c]) return t.encode[c];
        return String.valueOf(c).getBytes(cs)[0];
    }

    static byte space(Charset cs) {
        return by(' ', cs);
    }

    /** digit value and sign of a zoned byte: {digit, 1 if overpunched negative, 1 if overpunched positive}. */
    // [rule RT-NUM-ZONED-OVERPUNCH]
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
        if (numprocPfd() && !preferredSign(f, cs)) throw nonPreferredSign(f);
        return readAny(f, cs);
    }

    static BigDecimal readDecimal(Field f, Charset cs) {
        if (numprocPfd() && !preferredSign(f, cs)) throw nonPreferredSign(f);
        byte[] d = f.st.bytes;
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                if (f.digits <= 18) {
                    boolean neg = false;
                    int start = f.at();
                    int n = f.digits;
                    if (f.signSeparate) {
                        int sp = f.signLeading ? f.at() : f.at() + f.digits;
                        neg = ch(d[sp], cs) == '-';
                        if (f.signLeading) start = f.at() + 1;
                    }
                    long v = 0L;
                    for (int i = 0; i < n; i++) {
                        boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == n - 1);
                        byte rawByte = d[start + i];
                        char c = ch(rawByte, cs);
                        int digit;
                        if (c >= '0' && c <= '9') {
                            digit = c - '0';
                        } else if (signPos) {
                            if (c == '{') {
                                digit = 0;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c >= 'A' && c <= 'I') {
                                digit = c - 'A' + 1;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c == '}') {
                                digit = 0;
                                neg = true;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c >= 'J' && c <= 'R') {
                                digit = c - 'J' + 1;
                                neg = true;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else {
                                digit = rawByte & 0x0F;
                            }
                        } else {
                            digit = rawByte & 0x0F;
                        }
                        v = v * 10L + digit;
                    }
                    return BigDecimal.valueOf(neg && f.signed ? -v : v, f.scale);
                }
                break;
            }
            case NUMERIC_PACKED: {
                if (f.len <= 9) {
                    RuleTelemetry.hit("RT-NUM-PACKED-SIGN");
                    int at = f.at();
                    int len = f.len;
                    int sign = d[at + len - 1] & 0x0F;
                    boolean neg = f.signed && (sign == 0x0D || sign == 0x0B);
                    long v = 0L;
                    for (int i = 0; i < len; i++) {
                        int b = d[at + i] & 0xFF;
                        int hi = b >> 4;
                        v = v * 10L + (hi <= 9 ? hi : 9);
                        if (i < len - 1) {
                            int lo = b & 0x0F;
                            v = v * 10L + (lo <= 9 ? lo : 9);
                        }
                    }
                    return BigDecimal.valueOf(neg ? -v : v, f.scale);
                }
                break;
            }
            case NUMERIC_BINARY: {
                if (f.len <= 8) {
                    RuleTelemetry.hit("RT-NUM-BINARY-BYTE-ORDER");
                    int at = f.at();
                    int len = f.len;
                    boolean le = littleEndian(f);
                    long raw = 0L;
                    for (int i = 0; i < len; i++) {
                        int b = (le ? d[at + len - 1 - i] : d[at + i]) & 0xFF;
                        raw = (raw << 8) | b;
                    }
                    if (f.signed) {
                        if (len < 8) {
                            int shift = (8 - len) * 8;
                            raw = (raw << shift) >> shift;
                        }
                        return BigDecimal.valueOf(raw, f.scale);
                    }
                    if (len < 8 || raw >= 0) {
                        return BigDecimal.valueOf(raw, f.scale);
                    }
                }
                break;
            }
            default:
                break;
        }
        return readAny(f, cs).value();
    }

    // [rule RT-NUM-BINARY-BYTE-ORDER] [rule RT-NUM-PACKED-SIGN]
    private static Num readAny(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                boolean neg = false;
                int start = f.at();
                int n = f.digits;
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.at() : f.at() + f.digits;
                    neg = ch(d[sp], cs) == '-';
                    if (f.signLeading) start = f.at() + 1;
                }
                if (n <= 18) {
                    long v = 0L;
                    for (int i = 0; i < n; i++) {
                        boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == n - 1);
                        byte rawByte = d[start + i];
                        char c = ch(rawByte, cs);
                        int digit;
                        if (c >= '0' && c <= '9') {
                            digit = c - '0';
                        } else if (signPos) {
                            if (c == '{') {
                                digit = 0;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c >= 'A' && c <= 'I') {
                                digit = c - 'A' + 1;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c == '}') {
                                digit = 0;
                                neg = true;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else if (c >= 'J' && c <= 'R') {
                                digit = c - 'J' + 1;
                                neg = true;
                                RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                            } else {
                                digit = rawByte & 0x0F;
                            }
                        } else {
                            digit = rawByte & 0x0F;
                        }
                        v = v * 10L + digit;
                    }
                    return new Num(BigInteger.valueOf(v), f.scale, neg && f.signed);
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
                int at = f.at();
                int len = f.len;
                int sign = d[at + len - 1] & 0x0F;
                boolean neg = f.signed && (sign == 0x0D || sign == 0x0B);
                if (len <= 9) {
                    long v = 0L;
                    for (int i = 0; i < len; i++) {
                        int b = d[at + i] & 0xFF;
                        int hi = b >> 4;
                        v = v * 10L + (hi <= 9 ? hi : 9);
                        if (i < len - 1) {
                            int lo = b & 0x0F;
                            v = v * 10L + (lo <= 9 ? lo : 9);
                        }
                    }
                    return new Num(BigInteger.valueOf(v), f.scale, neg);
                }
                BigInteger v = BigInteger.ZERO;
                for (int i = 0; i < len; i++) {
                    int b = d[at + i] & 0xFF;
                    v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b >> 4, 9)));
                    if (i < len - 1) v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(Math.min(b & 0x0F, 9)));
                }
                return new Num(v, f.scale, neg);
            }
            case NUMERIC_FLOAT:
                return Num.of(Hfp.read(f));
            case NUMERIC_BINARY: {
                int at = f.at();
                int len = f.len;
                boolean le = littleEndian(f);
                if (len <= 8) {
                    long raw = 0L;
                    for (int i = 0; i < len; i++) {
                        int b = (le ? d[at + len - 1 - i] : d[at + i]) & 0xFF;
                        raw = (raw << 8) | b;
                    }
                    if (f.signed) {
                        if (len < 8) {
                            int shift = (8 - len) * 8;
                            raw = (raw << shift) >> shift;
                        }
                        if (raw == Long.MIN_VALUE) {
                            return new Num(BigInteger.valueOf(raw).abs(), f.scale, true);
                        }
                        return new Num(BigInteger.valueOf(raw < 0 ? -raw : raw), f.scale, raw < 0);
                    }
                    if (len < 8 || raw >= 0) {
                        return new Num(BigInteger.valueOf(raw), f.scale, false);
                    }
                }
                byte[] b = new byte[len];
                for (int i = 0; i < len; i++) {
                    b[i] = le ? d[at + len - 1 - i] : d[at + i];
                }
                BigInteger v = f.signed ? new BigInteger(b) : new BigInteger(1, b);
                return new Num(v.abs(), f.scale, v.signum() < 0);
            }
            default:
                throw new IllegalArgumentException("not a numeric item: " + f.kind);
        }
    }

    /** The unscaled magnitude `m` (already at the field's scale) with sign `neg`, stored truncated to the digits. */
    // [rule RT-NUM-TRUNC-BINARY]
    static void write(Field f, BigInteger m, boolean neg, Charset cs) {
        byte[] d = f.st.bytes;
        if (m.bitLength() <= 62 && f.digits <= 18) {
            long mv = m.longValue();
            switch (f.kind) {
                case NUMERIC_DISPLAY: {
                    long limit = POW10_LONG[f.digits];
                    if (mv >= limit) RuleTelemetry.hit("RT-NUM-TRUNC-BINARY");
                    long val = mv % limit;
                    boolean negative = neg && f.signed;
                    if (negative && !f.signSeparate) RuleTelemetry.hit("RT-NUM-ZONED-OVERPUNCH");
                    int start = f.at();
                    if (f.signSeparate) {
                        int sp = f.signLeading ? f.at() : f.at() + f.digits;
                        d[sp] = by(negative ? '-' : '+', cs);
                        if (f.signLeading) start = f.at() + 1;
                    }
                    for (int i = f.digits - 1; i >= 0; i--) {
                        int digit = (int) (val % 10L);
                        val /= 10L;
                        boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == f.digits - 1);
                        char c = signPos ? (negative ? NEGATIVE : POSITIVE).charAt(digit) : (char) ('0' + digit);
                        d[start + i] = by(c, cs);
                    }
                    return;
                }
                case NUMERIC_PACKED: {
                    if (f.len <= 9) {
                        RuleTelemetry.hit("RT-NUM-PACKED-SIGN");
                        long limit = POW10_LONG[f.digits];
                        if (mv >= limit) RuleTelemetry.hit("RT-NUM-TRUNC-BINARY");
                        long val = mv % limit;
                        int sign = !f.signed ? 0x0F : neg ? 0x0D : 0x0C;
                        int at = f.at();
                        int last = f.len - 1;
                        int hi = (int) (val % 10L);
                        val /= 10L;
                        d[at + last] = (byte) ((hi << 4) | sign);
                        for (int i = last - 1; i >= 0; i--) {
                            int lo = (int) (val % 10L);
                            val /= 10L;
                            int h = (int) (val % 10L);
                            val /= 10L;
                            d[at + i] = (byte) ((h << 4) | lo);
                        }
                        return;
                    }
                    break;
                }
                case NUMERIC_BINARY: {
                    if (f.len <= 8) {
                        RuleTelemetry.hit("RT-NUM-BINARY-BYTE-ORDER");
                        if (pastPictureUnderOpt(f, m)) throw truncOptUnpredictable(f, m, neg);
                        boolean doTrunc = !f.nativeBin && truncBinary() && f.digits <= 18;
                        if (doTrunc && mv >= POW10_LONG[f.digits]) RuleTelemetry.hit("RT-NUM-TRUNC-BINARY");
                        long v = f.nativeBin || !truncBinary() ? mv : mv % POW10_LONG[f.digits];
                        if (neg && f.signed) v = -v;
                        int at = f.at();
                        int len = f.len;
                        boolean le = littleEndian(f);
                        for (int i = len - 1; i >= 0; i--) {
                            d[le ? at + len - 1 - i : at + i] = (byte) v;
                            v >>= 8;
                        }
                        return;
                    }
                    break;
                }
                default:
                    break;
            }
        }
        BigInteger limit = pow10(f.digits);
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                String s = m.mod(limit).toString();
                s = "0".repeat(f.digits - s.length()) + s;
                boolean negative = neg && f.signed;
                int start = f.at();
                if (f.signSeparate) {
                    int sp = f.signLeading ? f.at() : f.at() + f.digits;
                    d[sp] = by(negative ? '-' : '+', cs);
                    if (f.signLeading) start = f.at() + 1;
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
                    d[f.at() + i] = (byte) ((hi << 4) | lo);
                }
                return;
            }
            case NUMERIC_FLOAT: // an integer (MOVE ZERO); Cobol.store and Cobol.move hand a float's value to Hfp whole
                Hfp.store(f, new BigDecimal(neg ? m.negate() : m));
                return;
            case NUMERIC_BINARY: {
                if (pastPictureUnderOpt(f, m)) throw truncOptUnpredictable(f, m, neg);
                BigInteger v = f.nativeBin || !truncBinary() ? m : m.mod(limit);
                if (neg && f.signed) v = v.negate();
                byte[] b = v.toByteArray();
                byte fill = (byte) (v.signum() < 0 ? 0xFF : 0x00);
                for (int i = 0; i < f.len; i++) {
                    int from = b.length - f.len + i;
                    byte x = from >= 0 ? b[from] : fill;
                    d[littleEndian(f) ? f.at() + f.len - 1 - i : f.at() + i] = x;
                }
                return;
            }
            default:
                throw new IllegalArgumentException("not a numeric item: " + f.kind);
        }
    }

    /** Whether `magnitude` (at the field's scale) fits the field without losing high-order digits. */
    // [rule RT-NUM-FITS]
    static boolean fits(Field f, BigInteger magnitude, boolean neg) {
        if (f.kind == Field.Kind.NUMERIC_BINARY && (f.nativeBin || !truncBinary())) {
            if (f.len <= 7 && magnitude.bitLength() <= 62) {
                long v = neg && f.signed ? -magnitude.longValue() : magnitude.longValue();
                int bits = f.len * 8;
                long lo = f.signed ? -(1L << (bits - 1)) : 0L;
                long hi = f.signed ? (1L << (bits - 1)) - 1L : (1L << bits) - 1L;
                return v >= lo && v <= hi;
            }
            int bits = f.len * 8;
            BigInteger v = neg && f.signed ? magnitude.negate() : magnitude;
            BigInteger lo = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).negate() : BigInteger.ZERO;
            BigInteger hi = f.signed ? BigInteger.ONE.shiftLeft(bits - 1).subtract(BigInteger.ONE)
                    : BigInteger.ONE.shiftLeft(bits).subtract(BigInteger.ONE);
            return v.compareTo(lo) >= 0 && v.compareTo(hi) <= 0;
        }
        if (f.digits <= 18 && magnitude.bitLength() <= 62) {
            return magnitude.longValue() < POW10_LONG[f.digits];
        }
        return magnitude.compareTo(pow10(f.digits)) < 0;
    }
}
