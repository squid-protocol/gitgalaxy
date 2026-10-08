package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.Charset;

/**
 * #4662 (oracle_assumptions.md C11): a zoned (USAGE DISPLAY) numeric item as GnuCOBOL 3.1.2 (`-std=ibm`, the oracle)
 * reads it, byte for byte, when a digit position holds a non-digit -- a space, a letter, a low-value, X'FF' -- and
 * the sign handling it applies to every zoned sender, digit-only data included. IBM documents no result for
 * non-digit data in a numeric item, so these are the oracle's rules (each one measured against cobc, see
 * tests/cobol_mainframe/test_det_nondigit_zoned.py), not z/OS's:
 *
 * <ul>
 *   <li>libcob's GET_SIGN ({@link #get}) turns the sign byte of a signed item into a digit and a sign before any
 *       numeric read: `{` and `A`-`I` are +0..+9, `}` and `J`-`R` are -0..-9, a digit is itself (positive), a space
 *       stays a space (positive), any other byte is the digit in its low nibble when that is 1-9, else 0 (positive:
 *       `!` is +1, X'FF' +0). PUT_SIGN ({@link #putSign}) writes the overpunch back afterwards -- so a read of a
 *       signed item rewrites a digit sign byte as `{`..`I` (`0123` becomes `012C`) and a space or any non-digit as
 *       `{` -- on a MOVE from it (whatever the receiver) and on an arithmetic operand, but not on a comparison; a
 *       separate sign is rewritten to `+` / `-` on a comparison too.</li>
 *   <li>Arithmetic (cob_decimal_set_display, {@link #operand}): a first byte X'FF' is +10^size and X'00' -10^size;
 *       otherwise leading bytes whose low nibble is 0 (zeros, spaces, low-values) are skipped, and the rest
 *       accumulate as `value * 10 + (byte - '0')` in an unsigned 64-bit integer that wraps: a space is -16, `A` 17,
 *       so PIC 9(6) of spaces is 2^64 - 16.</li>
 *   <li>A comparison ({@link #compareValue}) accumulates the same way in a signed 64-bit integer, without the
 *       skipping, and reads any sign byte that is no overpunch as 0.</li>
 *   <li>MOVE to a zoned item ({@link #toZoned}) copies the digit bytes, aligned on the decimal point (a space or
 *       X'00' becomes '0', any other byte stays) and writes the receiver's sign over its last or first byte (a
 *       digit overpunched, any other byte `{` / `}`).</li>
 *   <li>MOVE to a numeric-edited item ({@link #toEdited}) feeds the digit bytes to the edit PICTURE as they are:
 *       only a '0' is suppressed, so spaces stay spaces and Z(6)9 of 4 spaces is 7 spaces.</li>
 *   <li>MOVE to a packed item ({@link #toPacked}) makes a nibble pair `(hi * 16 + lo) mod 256` of the digits'
 *       values (byte - '0', a space 0).</li>
 * </ul>
 */
final class Zoned {
    private Zoned() {}

    private static final BigInteger TWO_64 = BigInteger.ONE.shiftLeft(64);

    /** A zoned item after libcob's GET_SIGN: the byte at each digit position (the sign byte converted to its digit
     *  char), the sign, and whether any digit position holds something that is not a digit. */
    static final class Raw {
        final int[] ch;
        final boolean neg;
        final boolean dirty;

        Raw(int[] ch, boolean neg, boolean dirty) {
            this.ch = ch;
            this.neg = neg;
            this.dirty = dirty;
        }
    }

    private static int start(Field f) {
        return f.signSeparate && f.signLeading ? f.off + 1 : f.off;
    }

    private static int signAt(Field f) {
        return f.signed && !f.signSeparate ? (f.signLeading ? 0 : f.digits - 1) : -1;
    }

    private static int sepAt(Field f) {
        return f.signSeparate ? (f.signLeading ? f.off : f.off + f.digits) : -1;
    }

    /** libcob's GET_SIGN on one sign byte: {digit char, 1 if negative}. `compare`: the comparison's reading, which
     *  takes a space and any byte that is no overpunch as 0. */
    private static int[] unpunch(int c, boolean compare) {
        if (c >= '0' && c <= '9') return new int[] {c, 0};
        if (c == '{') return new int[] {'0', 0};
        if (c >= 'A' && c <= 'I') return new int[] {'1' + (c - 'A'), 0};
        if (c == '}') return new int[] {'0', 1};
        if (c >= 'J' && c <= 'R') return new int[] {'1' + (c - 'J'), 1};
        if (compare) return new int[] {'0', 0};
        if (c == ' ') return new int[] {' ', 0};
        int n = c & 0x0F;
        return new int[] {n >= 1 && n <= 9 ? '0' + n : '0', 0};
    }

    /** The item's digit positions and sign as libcob reads them; nothing in the storage changes. */
    static Raw get(Field f, Charset cs) {
        return get(f, cs, false);
    }

    private static Raw get(Field f, Charset cs, boolean compare) {
        byte[] d = f.st.bytes;
        int n = f.digits;
        int s = start(f);
        int signAt = signAt(f);
        int[] ch = new int[n];
        boolean neg = false;
        boolean dirty = false;
        for (int i = 0; i < n; i++) {
            int c = Codec.ch(d[s + i], cs);
            if (i == signAt) {
                if (!(c >= '0' && c <= '9' || c == '{' || c == '}' || c >= 'A' && c <= 'R')) dirty = true;
                int[] u = unpunch(c, compare);
                c = u[0];
                neg = u[1] == 1;
            }
            ch[i] = c;
            if (c < '0' || c > '9') dirty = true;
        }
        if (f.signSeparate) neg = Codec.ch(d[sepAt(f)], cs) == '-';
        return new Raw(ch, neg, dirty);
    }

    /** PUT_SIGN: the sign written back over a signed item after a numeric read. */
    static void putSign(Field f, Raw r, Charset cs) {
        byte[] d = f.st.bytes;
        if (f.signSeparate) {
            d[sepAt(f)] = Codec.by(r.neg ? '-' : '+', cs);
            return;
        }
        int at = signAt(f);
        if (at < 0) return;
        int c = r.ch[at];
        char out = c >= '0' && c <= '9' ? (r.neg ? Codec.NEGATIVE : Codec.POSITIVE).charAt(c - '0')
                : r.neg ? '}' : '{';
        d[start(f) + at] = Codec.by(out, cs);
    }

    private static UnsupportedOperationException refuse(String what) {
        return new UnsupportedOperationException(what + " a zoned item holding a non-digit is not modelled "
                + "(IBM documents no result, register C11)");
    }

    private static BigDecimal scaled(BigInteger v, boolean neg, int scale) {
        return new BigDecimal(neg ? v.negate() : v, scale);
    }

    /** The value of a zoned item as an arithmetic operand (COMPUTE, ADD, ...), cob_decimal_set_display; PUT_SIGN
     *  follows. A digit-only item is read as ever. */
    static BigDecimal operand(Field f, Charset cs) {
        Raw r = get(f, cs);
        if (!r.dirty) {
            BigDecimal v = Codec.read(f, cs).value();
            putSign(f, r, cs);
            return v;
        }
        if (Codec.numprocPfd && !Codec.preferredSign(f, cs)) throw Codec.nonPreferredSign(f);
        int n = f.digits;
        int first = f.st.bytes[f.off] & 0xFF;
        if (first == 0xFF || first == 0) {  // HIGH-VALUES / LOW-VALUES: 10^size, positive or negative
            return scaled(BigInteger.TEN.pow(n), first == 0, f.scale);
        }
        int i = 0;
        while (n - i > 1 && (r.ch[i] & 0x0F) == 0) i++;
        if (n - i >= 19) throw refuse("arithmetic on 19 or more digits of");
        BigInteger v = BigInteger.ZERO;
        for (; i < n; i++) v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(r.ch[i] - '0'));
        v = v.mod(TWO_64);
        putSign(f, r, cs);
        return scaled(v, r.neg, f.scale);
    }

    /** The value of a zoned item cobc passes as an int (cob_get_int, for ADD / SUBTRACT of a field of at most 9
     *  digits to / from a zoned or packed item, cob_add_int): every digit position counts, nothing skipped, in a
     *  32-bit integer; PUT_SIGN follows. A digit-only item is read as ever. */
    static BigDecimal intOperand(Field f, Charset cs) {
        Raw r = get(f, cs);
        if (!r.dirty) {
            BigDecimal v = Codec.read(f, cs).value();
            putSign(f, r, cs);
            return v;
        }
        if (Codec.numprocPfd && !Codec.preferredSign(f, cs)) throw Codec.nonPreferredSign(f);
        int v = 0;
        for (int c : r.ch) v = v * 10 + (c - '0');
        putSign(f, r, cs);
        return scaled(BigInteger.valueOf(v), r.neg, f.scale);
    }

    /** The value of a zoned item in a comparison. cobc compares an unsigned or trailing-sign item without decimal
     *  places with cob_cmp_numdisp: every digit position counts, in a signed 64-bit integer, nothing skipped, a sign
     *  byte that is no overpunch (a space too) 0 and nothing written back. Any other item (a leading or separate
     *  sign) goes through the decimal as an arithmetic operand does (a separate sign is rewritten). A digit-only
     *  item is read as ever. */
    static BigDecimal compareValue(Field f, Charset cs) {
        boolean numdisp = !f.signSeparate && !(f.signed && f.signLeading) && f.scale == 0;
        Raw r = get(f, cs, numdisp);
        if (!r.dirty) {
            BigDecimal v = Codec.read(f, cs).value();
            if (!numdisp) putSign(f, r, cs);
            return v;
        }
        if (!numdisp) return operand(f, cs);
        if (Codec.numprocPfd && !Codec.preferredSign(f, cs)) throw Codec.nonPreferredSign(f);
        if (f.digits >= 19) throw refuse("comparing 19 or more digits of");
        long v = 0;
        for (int c : r.ch) v = v * 10 + (c - '0');
        return scaled(BigInteger.valueOf(v), r.neg, f.scale);
    }

    /** The sender's digit char (or -1 for a position it does not have) at the weight of receiver position `j`. */
    private static int aligned(Raw r, Field from, int rd, int rs, int j) {
        int i = from.digits - from.scale - (rd - rs) + j;
        return i >= 0 && i < from.digits ? r.ch[i] : -1;
    }

    /** MOVE of a zoned sender holding a non-digit to a zoned receiver (store_common_region): the digit bytes
     *  copied aligned on the decimal point. */
    static void toZoned(Field from, Raw r, Field to, Charset cs) {
        byte[] d = to.st.bytes;
        int s = start(to);
        for (int j = 0; j < to.digits; j++) {
            int c = aligned(r, from, to.digits, to.scale, j);
            d[s + j] = Codec.by(c < 0 || c == ' ' || c == 0 ? '0' : (char) c, cs);
        }
        if (!to.signed) return;
        boolean neg = r.neg;
        if (to.signSeparate) {
            d[sepAt(to)] = Codec.by(neg ? '-' : '+', cs);
            return;
        }
        int at = signAt(to);
        int c = Codec.ch(d[s + at], cs);
        char out = c >= '0' && c <= '9' ? (neg ? Codec.NEGATIVE : Codec.POSITIVE).charAt(c - '0') : neg ? '}' : '{';
        d[s + at] = Codec.by(out, cs);
    }

    /** MOVE of such a sender to a numeric-edited item: the bytes are the edit PICTURE's digits as they are. */
    static String toEdited(Field from, Raw r, Field to) {
        int[] shape = Editing.shape(to.pic);
        int n = shape[0] + shape[1];
        StringBuilder sb = new StringBuilder();
        for (int j = 0; j < n; j++) {
            int c = aligned(r, from, n, shape[1], j);
            sb.append(c < 0 ? '0' : (char) c);
        }
        return Editing.format(to.pic, BigDecimal.ZERO, false, null, sb.toString(), r.neg);
    }

    /** MOVE of such a sender to a packed item (cob_move_display_to_packed): a nibble pair is `(hi * 16 + lo) mod
     *  256` of the digits' values (byte - '0'; a space is 0), the last byte's low nibble the sign. */
    static void toPacked(Field from, Raw r, Field to) {
        byte[] d = to.st.bytes;
        int nibbles = to.len * 2;
        int[] v = new int[nibbles];
        int lead = nibbles - 1 - to.digits;  // a leading 0 nibble when the digit count is even
        for (int j = 0; j < to.digits; j++) {
            int c = aligned(r, from, to.digits, to.scale, j);
            v[lead + j] = c < 0 || c == ' ' ? 0 : c - '0';
        }
        v[nibbles - 1] = !to.signed ? 0x0F : r.neg ? 0x0D : 0x0C;
        for (int i = 0; i < to.len; i++) d[to.off + i] = (byte) ((v[2 * i] * 16 + v[2 * i + 1]) & 0xFF);
    }
}
