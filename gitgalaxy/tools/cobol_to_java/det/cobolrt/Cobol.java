package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * COBOL data semantics over byte storage (IBM Enterprise COBOL, as GnuCOBOL implements it under
 * `-std=ibm -fsign=EBCDIC`; every rule here is checked against GnuCOBOL by tests/cobol_mainframe/test_cobolrt.py).
 *
 * <p>Every text conversion takes the record charset. Statements STRING, UNSTRING and INSPECT are the methods
 * {@link #string}, {@link #unstring} and {@link #inspect}; their operands are built with {@link StringPart},
 * {@link Delim}, {@link Into} and {@link Clause}.
 */
public final class Cobol {
    private Cobol() {}

    // ------------------------------------------------------------------------------------------ categories

    private static final int GROUP = 0;
    private static final int ALNUM = 1;
    private static final int NUMERIC = 2;
    private static final int NUM_EDITED = 3;
    private static final int ALNUM_EDITED = 4;

    private static int cat(Field f) {
        switch (f.kind) {
            case GROUP: return GROUP;
            case ALPHANUMERIC:
            case ALPHABETIC: return ALNUM;
            case NUMERIC_EDITED: return NUM_EDITED;
            case ALPHANUMERIC_EDITED: return ALNUM_EDITED;
            default: return NUMERIC;
        }
    }

    private static Field temp(byte[] b) {
        Storage s = new Storage(b.length);
        System.arraycopy(b, 0, s.bytes, 0, b.length);
        return Field.alphanumeric(s, 0, b.length, false);
    }

    /** A numeric literal as the DISPLAY item it is. */
    private static Field literalField(BigDecimal v) {
        if (v.scale() < 0) v = v.setScale(0);
        int digits = Math.max(Math.max(v.unscaledValue().abs().toString().length(), v.scale()), 1);
        // a literal written without a sign is unsigned: MOVE 23 TO a group gives "23", not an overpunched "2C"
        return Field.zoned(new Storage(digits), 0, digits, v.scale(), v.signum() < 0, false, false);
    }

    /** TRUNC(STD) for binary items (high-order digits beyond the PICTURE lost; size error beyond the PICTURE).
     *  Default false: as GnuCOBOL `-std=ibm` behaves, a binary item holds what its bytes hold. */
    public static void setTruncBinary(boolean on) {
        Codec.truncBinary = on;
    }

    /** TRUNC for a program's run (#4102): `on` in effect, the setting before returned (the caller restores it). */
    public static boolean swapTruncBinary(boolean on) {
        boolean before = Codec.truncBinary;
        Codec.truncBinary = on;
        return before;
    }

    /** NUMPROC for a program's run (#4271): `pfd` true for NUMPROC(PFD) -- a zoned or packed value read with a sign
     *  that is not preferred is refused by name (Codec.numprocPfd) --, false for IBM's default NUMPROC(NOPFD) (and
     *  NUMPROC(MIG), which Enterprise COBOL 5 and later compile as the default). The setting before is returned. */
    public static boolean swapNumprocPfd(boolean pfd) {
        boolean before = Codec.numprocPfd;
        Codec.numprocPfd = pfd;
        return before;
    }

    // ------------------------------------------------------------------------------------------ ARITHMETIC
    // ------------------------------------------------------------------------------- size error (#4655)
    /** libcob's invalid intermediate (COB_DECIMAL_NAN, oracle_assumptions C14): a decimal whose scale is -32768. A
     *  zero divisor (cob_decimal_div) makes one of the dividend; an operation with one makes one of its left
     *  operand's value; storing one (cob_decimal_get_field) leaves the receiver unchanged with a size error. It is
     *  an ordinary number to everything else: cob_decimal_align truncates it to 0 (Cobol.align does the same with
     *  its scale) and cob_decimal_cmp compares its value scaled by 10^32768. */
    public static final int NAN_SCALE = -32768;

    public static boolean isNan(BigDecimal d) {
        return d.scale() == NAN_SCALE;
    }

    private static BigDecimal nan(BigDecimal d) {
        return new BigDecimal(d.unscaledValue(), NAN_SCALE);
    }

    /** The statement's size-error state (libcob's EC-SIZE exception code): set by a zero divisor, 0 ** 0 or an
     *  exponent without a finite result even when no invalid value reaches a receiver (an aligned NaN is 0, a
     *  function's argument divided by zero is 0); cleared where a statement with ON SIZE ERROR starts. */
    private static final ThreadLocal<boolean[]> SIZE_EC = ThreadLocal.withInitial(() -> new boolean[1]);

    public static void sizeClear() {
        SIZE_EC.get()[0] = false;
    }

    public static boolean sizeRaised() {
        return SIZE_EC.get()[0];
    }

    private static void raiseSize() {
        SIZE_EC.get()[0] = true;
    }

    /** cob_decimal_add of two intermediates where either may be libcob's NaN (#4655): NaN in, NaN out. */
    public static BigDecimal add(BigDecimal a, BigDecimal b) {
        return isNan(a) ? a : isNan(b) ? nan(a) : a.add(b);
    }

    /** cob_decimal_sub, as {@link #add(BigDecimal, BigDecimal)}. */
    public static BigDecimal subtract(BigDecimal a, BigDecimal b) {
        return isNan(a) ? a : isNan(b) ? nan(a) : a.subtract(b);
    }

    /** cob_decimal_mul, as {@link #add(BigDecimal, BigDecimal)}. */
    public static BigDecimal multiply(BigDecimal a, BigDecimal b) {
        return isNan(a) ? a : isNan(b) ? nan(a) : a.multiply(b);
    }

    /** Unary minus where the operand may be NaN: cobc's 0 - x, so a NaN's value is 0. */
    public static BigDecimal negate(BigDecimal a) {
        return isNan(a) ? nan(BigDecimal.ZERO) : a.negate();
    }

    /** An intermediate quotient as GnuCOBOL forms it (cob_decimal_div): the scale a.scale - b.scale, the dividend
     *  shifted 38 digits more (and as many again as that scale is below zero), then divided and truncated -- so the
     *  quotient keeps 38 + max(a.scale - b.scale, 0) decimal places; a zero dividend is 0 of scale 0. The
     *  receiver's own truncation or ROUNDED then applies in store. A zero divisor makes the dividend NaN and raises
     *  the size error (#4655); a NaN operand gives NaN. */
    public static BigDecimal divide(BigDecimal a, BigDecimal b) {
        if (isNan(a)) {
            return a;
        }
        if (isNan(b)) {
            return nan(a);
        }
        if (b.signum() == 0) {
            raiseSize();
            return nan(a);
        }
        if (a.signum() == 0) {
            return BigDecimal.ZERO;
        }
        return a.divide(b, 38 + Math.max(a.scale() - b.scale(), 0), java.math.RoundingMode.DOWN);
    }

    /** DIVIDE ... REMAINDER (cob_div_quotient, cob_div_remainder): the dividend less the divisor times the quotient
     *  `q` truncated to the first GIVING receiver's `scale` places -- not to its PICTURE's high-order digits, so a
     *  quotient too big for its receiver still gives the true remainder. A NaN quotient (a zero divisor) gives NaN:
     *  the remainder receiver unchanged (#4655). */
    public static BigDecimal remainder(BigDecimal a, BigDecimal q, BigDecimal b, int scale) {
        if (isNan(q)) {
            return q;
        }
        return a.subtract(q.setScale(scale, RoundingMode.DOWN).multiply(b));
    }

    /** A division in an intrinsic function's argument (cob_intr_binop): a zero divisor gives 0, with the size
     *  error raised -- never NaN (#4655). */
    public static BigDecimal divideIntr(BigDecimal a, BigDecimal b) {
        if (b.signum() == 0) {
            raiseSize();
            return BigDecimal.ZERO;
        }
        return divide(a, b);
    }

    /** ARITHMETIC-OSVS (#4287, oracle_assumptions C2): an intermediate result truncated to `scale` decimal places, as
     *  libcob's cob_decimal_align does it where cobc -std=ibm emits it (the translator decides where, det/osvs.py).
     *  With more places than `scale` the low-order ones are dropped (toward zero); with fewer, libcob shifts the
     *  other way: the value loses as many low-order digits as it lacks places (579 aligned to 2 places is 500). */
    public static BigDecimal align(BigDecimal d, int scale) {
        if (d.scale() > scale) {
            return d.setScale(scale, java.math.RoundingMode.DOWN);
        }
        if (d.scale() < scale) {
            int k = scale - d.scale();
            return new BigDecimal(d.unscaledValue().divide(java.math.BigInteger.TEN.pow(k)), d.scale() - k);
        }
        return d;
    }

    /** A numeric literal on the right of an operation in a decimal expression: libcob's decimal constant (cobc's
     *  dc_N, one per distinct literal of the program, set once when the program starts). libcob changes its scale
     *  in place: an ADD or SUBTRACT from an intermediate with more decimal places raises it to theirs
     *  (align_decimal), an exponent loses its trailing zeros (cob_decimal_pow) -- and every later use of the same
     *  literal sees the changed scale (oracle_assumptions C2, #4287). */
    public static final class Dc {
        private final BigDecimal initial;
        BigDecimal v;

        public Dc(String literal) {
            initial = new BigDecimal(literal);
            v = initial;
        }

        /** The program starts again (its initial state): the literal as written. */
        public void reset() {
            v = initial;
        }
    }

    /** cob_decimal_add with a decimal constant (Dc). */
    public static BigDecimal add(BigDecimal a, Dc c) {
        if (isNan(a)) {
            return a;
        }
        if (a.scale() > c.v.scale()) {
            c.v = c.v.setScale(a.scale());
        }
        return a.add(c.v);
    }

    /** cob_decimal_sub with a decimal constant (Dc). */
    public static BigDecimal subtract(BigDecimal a, Dc c) {
        if (isNan(a)) {
            return a;
        }
        if (a.scale() > c.v.scale()) {
            c.v = c.v.setScale(a.scale());
        }
        return a.subtract(c.v);
    }

    /** cob_decimal_mul with a decimal constant (Dc): the constant as it is now. */
    public static BigDecimal multiply(BigDecimal a, Dc c) {
        return isNan(a) ? a : a.multiply(c.v);
    }

    /** cob_decimal_div with a decimal constant (Dc): the constant as it is now. */
    public static BigDecimal divide(BigDecimal a, Dc c) {
        return divide(a, c.v);
    }

    /** cob_decimal_pow with a decimal constant exponent (Dc, never negative: the translator refuses one): trimmed in
     *  place once the base is not zero. */
    public static BigDecimal power(BigDecimal a, Dc c) {
        if (isNan(a)) {
            return a;
        }
        if (c.v.signum() != 0 && a.signum() != 0) {
            c.v = trim(c.v);
        }
        return power(a, c.v);
    }

    /** cob_trim_decimal: trailing zeros dropped while the scale is above zero; zero is 0 of scale 0. */
    private static BigDecimal trim(BigDecimal d) {
        if (d.signum() == 0) {
            return BigDecimal.ZERO;
        }
        while (d.scale() > 0) {
            java.math.BigInteger[] qr = d.unscaledValue().divideAndRemainder(java.math.BigInteger.TEN);
            if (qr[1].signum() != 0) {
                break;
            }
            d = new BigDecimal(qr[0], d.scale() - 1);
        }
        return d;
    }

    /** A ** b as cob_decimal_pow forms it: a whole exponent exactly (base and result trimmed of trailing zeros, a
     *  negative one through cob_decimal_div), else through double. 0 ** 0 is 1 with the size error raised; an
     *  exponent through double without a finite result (a negative base, an overflow) is NaN with the size error
     *  raised, as libcob's (#4655); a NaN operand gives NaN. */
    public static BigDecimal power(BigDecimal a, BigDecimal b) {
        if (isNan(a)) {
            return a;
        }
        if (isNan(b)) {
            return nan(a);
        }
        boolean whole = b.stripTrailingZeros().scale() <= 0;
        if (b.signum() == 0) {
            if (a.signum() == 0) {
                raiseSize();
            }
            return BigDecimal.ONE;
        }
        if (a.signum() == 0) {
            return BigDecimal.ZERO;
        }
        if (whole && b.signum() > 0 && b.compareTo(BigDecimal.valueOf(999)) <= 0) {
            int n = b.intValueExact();
            return n == 1 ? trim(a) : trim(trim(a).pow(n));
        }
        if (whole && b.signum() < 0) {
            return trim(divide(BigDecimal.ONE, trim(trim(a).pow(-b.intValueExact()))));
        }
        double r = Math.pow(a.doubleValue(), b.doubleValue());
        if (Double.isNaN(r) || Double.isInfinite(r)) {
            raiseSize();
            return nan(a);
        }
        return new BigDecimal(r);
    }

    // ------------------------------------------------------------------------------------------------ MOVE

    public static void move(Field from, Field to, Charset cs) {
        if (cat(to) == GROUP) {
            padCopy(from.raw(), to, false, cs);
            return;
        }
        int fc = cat(from);
        if (from.kind == Field.Kind.NUMERIC_FLOAT || to.kind == Field.Kind.NUMERIC_FLOAT) {
            moveFloat(from, fc, to, cs);
            return;
        }
        switch (cat(to)) {
            case ALNUM:
                padCopy(sourceText(from, fc, cs), to, to.justRight, cs);
                break;
            case ALNUM_EDITED:
                insertEdit(to, sourceText(from, fc, cs), cs);
                break;
            case NUMERIC:
                if (to.kind == Field.Kind.NUMERIC_BINARY && from.kind == Field.Kind.NUMERIC_DISPLAY
                        && nonDigitToBinary(from, to, cs)) {
                    break;
                }
                boolean zoned = to.kind == Field.Kind.NUMERIC_DISPLAY && fc != NUMERIC && fc != NUM_EDITED;
                store(to, zoned ? alnumToDisplay(from.raw(), to, cs) : source(from, fc, to.decimalComma, cs), cs);
                break;
            default:
                edit(to, source(from, fc, to.decimalComma, cs), cs);
        }
    }

    private static final BigInteger TWO_64 = BigInteger.ONE.shiftLeft(64);

    /** A zoned sender holding a byte that is not a digit (a space, a letter) in a digit position, MOVEd to a binary
     *  item, as the oracle computes it (#4652, register C11; GnuCOBOL 3.1.2 cob_move_display_to_binary): each byte
     *  counts as its character minus '0' -- a space -16, 'A' 17 --, the sender's digits aligned on the receiver's
     *  decimal places and accumulated in an unsigned 64-bit integer (wrapping), the receiver's digits kept under
     *  TRUNC(STD) (not for COMP-5), then the sender's sign applied when the receiver is signed. PIC 9(10) of spaces
     *  into S9(9) COMP is 931773840 under TRUNC(STD), -597908592 under TRUNC(BIN). IBM documents no result for such
     *  data. A space where a signed sender's sign is counts -16 and positive; the oracle then rewrites a positive
     *  sender's sign byte as an overpunch -- a space '{', a digit 4 'D' -- (a separate space sign '+'), as here. Any other non-sign there is refused by name. False,
     *  nothing done, when every digit position holds a digit (the ordinary MOVE). */
    private static boolean nonDigitToBinary(Field from, Field to, Charset cs) {
        byte[] d = from.st.bytes;
        int n = from.digits;
        int start = from.signSeparate && from.signLeading ? from.off + 1 : from.off;
        int signAt = from.signed && !from.signSeparate ? (from.signLeading ? 0 : n - 1) : -1;
        int sepAt = from.signSeparate ? (from.signLeading ? from.off : from.off + n) : -1;
        int[] digit = new int[n];
        boolean neg = false;
        boolean nonDigit = false;
        for (int i = 0; i < n; i++) {
            char c = Codec.ch(d[start + i], cs);
            if (i == signAt && (c < '0' || c > '9') && c != ' ') {
                int p = Codec.POSITIVE.indexOf(c);
                int q = Codec.NEGATIVE.indexOf(c);
                if (p < 0 && q < 0) throw nonDigitSign();
                neg = q >= 0;
                c = (char) ('0' + (p >= 0 ? p : q));
            }
            if (c < '0' || c > '9') nonDigit = true;
            digit[i] = c - '0';
        }
        if (!nonDigit) return false;
        if (sepAt >= 0) {
            char s = Codec.ch(d[sepAt], cs);
            if (s != '+' && s != '-' && s != ' ') throw nonDigitSign();
            neg = s == '-';
        }
        if (Codec.numprocPfd && !Codec.preferredSign(from, cs)) throw Codec.nonPreferredSign(from);
        BigInteger v = BigInteger.ZERO;
        for (int i = 0; i < n - from.scale + to.scale; i++) {
            v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(i < n ? digit[i] : 0));
        }
        v = v.mod(TWO_64);
        if (Codec.truncBinary && !to.nativeBin) v = v.mod(BigInteger.TEN.pow(to.digits));
        Codec.write(to, v, neg, cs);
        if (signAt >= 0 && !neg) d[start + signAt] = Codec.by(Codec.POSITIVE.charAt(Math.max(digit[signAt], 0)), cs);
        if (sepAt >= 0 && Codec.ch(d[sepAt], cs) == ' ') d[sepAt] = Codec.by('+', cs);
        return true;
    }

    private static UnsupportedOperationException nonDigitSign() {
        return new UnsupportedOperationException("MOVE to a binary item of a signed zoned item whose sign byte is "
                + "neither a digit, a sign nor a space (IBM documents no result, register C11) is not modelled");
    }

    /** A MOVE with a COMP-1 / COMP-2 sender or receiver (#4271, Hfp): a number into a float converted to its
     *  precision; a float into a fixed-point or numeric-edited item rounded in the receiver's low-order position (9 /
     *  18 significant digits at most). Any other MOVE of a float (its bytes) is refused by name -- the translator
     *  refuses it first. */
    private static void moveFloat(Field from, int fc, Field to, Charset cs) {
        if (to.kind == Field.Kind.NUMERIC_FLOAT && (fc == NUMERIC || fc == NUM_EDITED)) {
            Hfp.store(to, source(from, fc, cs).value());
            return;
        }
        if (from.kind == Field.Kind.NUMERIC_FLOAT && (cat(to) == NUMERIC || cat(to) == NUM_EDITED)) {
            BigDecimal v = Hfp.toFixed(Hfp.read(from), to.scale, from.len == 4 ? 9 : 18);
            if (cat(to) == NUMERIC) Codec.write(to, v.unscaledValue().abs(), v.signum() < 0, cs);
            else edit(to, Codec.Num.of(v), cs);
            return;
        }
        throw new UnsupportedOperationException("MOVE of a COMP-1 / COMP-2 item's bytes (IBM hexadecimal floating "
                + "point, register C6) is not modelled");
    }

    public static void move(String nonnumericLiteral, Field to, Charset cs) {
        move(temp(nonnumericLiteral.getBytes(cs)), to, cs);
    }

    public static void move(BigDecimal numericLiteral, Field to, Charset cs) {
        move(fill(literalField(numericLiteral), numericLiteral, cs), to, cs);
    }

    private static Field fill(Field f, BigDecimal v, Charset cs) {
        if (v.scale() < 0) v = v.setScale(0);
        Codec.write(f, v.unscaledValue().abs(), v.signum() < 0, cs);
        return f;
    }

    public static void moveFigurative(Figurative fig, Field to, Charset cs) {
        byte b = figByte(fig, cs);
        switch (cat(to)) {
            case NUMERIC:
                if (to.kind == Field.Kind.NUMERIC_FLOAT && fig != Figurative.ZEROS) {
                    throw new UnsupportedOperationException("MOVE " + fig + " to a COMP-1 / COMP-2 item (its bytes, "
                            + "register C6) is not modelled");
                }
                if (fig == Figurative.ZEROS) {
                    Codec.write(to, BigInteger.ZERO, false, cs);
                } else {
                    Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
                }
                break;
            case NUM_EDITED:
                if (fig == Figurative.ZEROS) {
                    edit(to, new Codec.Num(BigInteger.ZERO, 0, false), cs);
                } else {
                    Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
                }
                break;
            default:
                Arrays.fill(to.st.bytes, to.off, to.off + to.len, b);
        }
    }

    private static byte figByte(Figurative f, Charset cs) {
        switch (f) {
            case SPACES: return Codec.space(cs);
            case ZEROS: return Codec.by('0', cs);
            case LOW_VALUES: return 0;
            case HIGH_VALUES: return (byte) 0xFF;
            default: return Codec.by('"', cs);
        }
    }

    /** MOVE ALL literal: the literal repeated to the receiver's size. */
    public static void moveAll(String allLiteral, Field to, Charset cs) {
        byte[] lit = allLiteral.getBytes(cs);
        if (lit.length == 0) return;
        byte[] b = new byte[to.len];
        for (int i = 0; i < b.length; i++) b[i] = lit[i % lit.length];
        switch (cat(to)) {
            case NUMERIC:
            case NUM_EDITED:
                // GnuCOBOL: the pattern ends at the right edge (ALL "12" to PIC 9(5) is 21212)
                for (int k = 0; k < b.length; k++) b[b.length - 1 - k] = lit[lit.length - 1 - k % lit.length];
                move(temp(b), to, cs);
                break;
            default:
                System.arraycopy(b, 0, to.st.bytes, to.off, b.length);
        }
    }

    /** The sending item as the bytes an alphanumeric receiver gets. */
    private static byte[] sourceText(Field from, int fc, Charset cs) {
        if (fc != NUMERIC) return from.raw();
        if (from.kind == Field.Kind.NUMERIC_FLOAT) {
            throw new UnsupportedOperationException("a COMP-1 / COMP-2 item as text (register C6) is not modelled");
        }
        if (from.kind == Field.Kind.NUMERIC_DISPLAY) {
            // GnuCOBOL (as IBM for an integer): the digit bytes as they are -- invalid data included -- the
            // overpunched sign turned back into its digit, a separate sign dropped, no decimal point
            byte[] raw = from.raw();
            int start = from.signSeparate && from.signLeading ? 1 : 0;
            int end = from.signSeparate && !from.signLeading ? raw.length - 1 : raw.length;
            byte[] out = java.util.Arrays.copyOfRange(raw, start, end);
            if (from.signed && !from.signSeparate && out.length > 0) {
                int at = from.signLeading ? 0 : out.length - 1;
                out[at] = unpunch(out[at], cs);
            }
            return from.scale < 0 ? pZeros(out, from, cs) : out;
        }
        Codec.Num n = Codec.read(from, cs);
        String s = n.mag.toString();
        // a left-P binary / packed item (PIC VPP99 COMP): GnuCOBOL writes its Ps as leading digits too (#4670)
        int width = Math.max(from.digits, from.scale);
        if (s.length() < width) s = "0".repeat(width - s.length()) + s;
        return pZeros(s.getBytes(cs), from, cs);
    }

    /** #4670: a right-P item (PIC 99PP) as text: its digits, then a zero for each P (MOVE 1300 into it, then into a
     *  PIC X(6): "1300  "), as GnuCOBOL moves it. */
    private static byte[] pZeros(byte[] digits, Field from, Charset cs) {
        if (from.scale >= 0) return digits;
        byte[] out = java.util.Arrays.copyOf(digits, digits.length - from.scale);
        java.util.Arrays.fill(out, digits.length, out.length, Codec.by('0', cs));
        return out;
    }

    /** An overpunched sign byte ({ A-I: +0..9, } J-R: -0..9 as -fsign=EBCDIC writes them) as its digit; any other
     *  byte as it is. */
    private static byte unpunch(byte b, Charset cs) {
        String c = new String(new byte[] {b}, cs);
        int i = "{ABCDEFGHI".indexOf(c);
        if (i < 0) {
            i = "}JKLMNOPQR".indexOf(c);
        }
        return i < 0 ? b : String.valueOf(i).getBytes(cs)[0];
    }

    /** The sending item's value as a number: numeric, de-edited, or an alphanumeric read as GnuCOBOL does. */
    private static Codec.Num source(Field from, int fc, Charset cs) {
        return source(from, fc, false, cs);
    }

    /** As source(from, fc, cs); `decimalComma` (#4462: the receiver's program declares DECIMAL-POINT IS COMMA): an
     *  alphanumeric sender's `,` is its decimal point and `.` is ignored, as libcob reads it. */
    private static Codec.Num source(Field from, int fc, boolean decimalComma, Charset cs) {
        switch (fc) {
            case NUMERIC: return Codec.read(from, cs);
            case NUM_EDITED: return deedit(from, cs);
            default: return parseAlnum(from.raw(), cs, decimalComma);
        }
    }

    private static Codec.Num deedit(Field f, Charset cs) {
        String s = new String(f.raw(), cs);
        BigInteger v = BigInteger.ZERO;
        boolean neg = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                v = v.multiply(BigInteger.TEN).add(BigInteger.valueOf(c - '0'));
            } else if (c == '-') {
                neg = true;
            } else if ((c == 'C' && i + 1 < s.length() && s.charAt(i + 1) == 'R')
                    || (c == 'D' && i + 1 < s.length() && s.charAt(i + 1) == 'B')) {
                neg = true;
            }
        }
        return new Codec.Num(v, f.scale, neg);
    }

    /**
     * An alphanumeric item MOVEd into a zoned (USAGE DISPLAY) numeric one, as libcob 3 (cob_move_alphanum_to_display) does it, byte for byte:
     * leading spaces and one sign character are skipped; the digits before the first '.' fix where the number is
     * aligned (high-order ones that do not fit are skipped); then characters are copied while the receiver has room --
     * digits are kept, one '.' starts the decimals, spaces and ',' are ignored, and any other character met before the
     * receiver is full (a second '.', a letter, a sign inside the number) leaves the receiver ZERO and positive. No
     * validation: a field of letters is 0, never an error. Characters after the receiver is full are never looked at. (A packed or binary receiver reads the whole text instead: any stray
     * character anywhere makes it zero -- parseAlnum.)
     */
    private static Codec.Num alnumToDisplay(byte[] raw, Field to, Charset cs) {
        int total = to.digits;
        int scale = to.scale;
        if (scale < 0 || scale > total) return parseAlnum(raw, cs, to.decimalComma);
        char dp = to.decimalComma ? ',' : '.';  // #4462: DECIMAL-POINT IS COMMA swaps the point and the separator
        char sep = to.decimalComma ? '.' : ',';
        String s = new String(raw, cs);
        int n = s.length();
        int i = 0;
        while (i < n && Character.isWhitespace(s.charAt(i))) i++;
        boolean neg = false;
        if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-')) neg = s.charAt(i++) == '-';
        int count = 0;
        for (int j = i; j < n && s.charAt(j) != dp; j++) {
            if (s.charAt(j) >= '0' && s.charAt(j) <= '9') count++;
        }
        int size = total - scale;
        char[] out = new char[total];
        Arrays.fill(out, '0');
        int pos = 0;
        if (count < size) {
            pos = size - count;
        } else {
            for (int c = count; c > size; c--) {
                while (i < n && !(s.charAt(i) >= '0' && s.charAt(i) <= '9')) i++;
                i++;
            }
        }
        boolean point = false;
        for (; i < n && pos < total; i++) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                out[pos++] = c;
            } else if (c == dp && !point) {
                point = true;
            } else if (!(Character.isWhitespace(c) || c == sep)) {
                return new Codec.Num(BigInteger.ZERO, scale, false);
            }
        }
        return new Codec.Num(total == 0 ? BigInteger.ZERO : new BigInteger(new String(out)), scale, neg);
    }

    /** `decimalComma` (#4462: DECIMAL-POINT IS COMMA): `,` is the decimal point and `.` the ignored separator. */
    private static Codec.Num parseAlnum(byte[] raw, Charset cs, boolean decimalComma) {
        char dp = decimalComma ? ',' : '.';
        char sep = decimalComma ? '.' : ',';
        String s = new String(raw, cs);
        int i = 0;
        int n = s.length();
        while (i < n && Character.isWhitespace(s.charAt(i))) i++;
        boolean neg = false;
        if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-')) neg = s.charAt(i++) == '-';
        StringBuilder digits = new StringBuilder();
        int frac = 0;
        boolean point = false;
        for (; i < n; i++) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                digits.append(c);
                if (point) frac++;
            } else if (c == dp && !point) {
                point = true;
            } else if (!(Character.isWhitespace(c) || c == sep)) {
                return new Codec.Num(BigInteger.ZERO, 0, false);
            }
        }
        return new Codec.Num(digits.length() == 0 ? BigInteger.ZERO : new BigInteger(digits.toString()), frac, neg);
    }

    private static void padCopy(byte[] src, Field to, boolean right, Charset cs) {
        byte sp = Codec.space(cs);
        byte[] d = to.st.bytes;
        int n = to.len;
        if (!right) {
            for (int i = 0; i < n; i++) d[to.off + i] = i < src.length ? src[i] : sp;
        } else {
            for (int i = 0; i < n; i++) {
                int from = src.length - n + i;
                d[to.off + i] = from >= 0 ? src[from] : sp;
            }
        }
    }

    private static void insertEdit(Field to, byte[] src, Charset cs) {
        String pic = Editing.expandPic(to.pic);
        byte sp = Codec.space(cs);
        int k = 0;
        for (int i = 0; i < to.len; i++) {
            char c = i < pic.length() ? pic.charAt(i) : 'X';
            byte b;
            if (c == 'B') b = sp;
            else if (c == '0') b = Codec.by('0', cs);
            else if (c == '/') b = Codec.by('/', cs);
            else b = k < src.length ? src[k++] : sp;
            to.st.bytes[to.off + i] = b;
        }
    }

    /** Stores `n` into a numeric item: aligned on the decimal point, extra decimals and high digits dropped. */
    private static void store(Field to, Codec.Num n, Charset cs) {
        if (to.kind == Field.Kind.NUMERIC_FLOAT) {
            Hfp.store(to, n.value());
            return;
        }
        BigInteger m = new BigDecimal(n.mag, n.scale).setScale(to.scale, RoundingMode.DOWN).unscaledValue();
        Codec.write(to, m, n.neg, cs);
    }

    private static void edit(Field to, Codec.Num n, Charset cs) {
        BigDecimal v = new BigDecimal(n.mag, n.scale).setScale(to.scale, RoundingMode.DOWN);
        if (n.neg) v = v.negate();
        String s;
        if (to.blankWhenZero && v.signum() == 0) s = " ".repeat(to.len);
        else s = Editing.format(to.pic, v, to.decimalComma, null);
        padCopy(s.getBytes(cs), to, false, cs);
    }

    // ------------------------------------------------------------------------------------------------ values

    /** A numeric item's value (numeric-edited: de-edited). */
    public static BigDecimal num(Field f, Charset cs) {
        switch (cat(f)) {
            case NUMERIC: return Codec.read(f, cs).value();
            case NUM_EDITED: return deedit(f, cs).value();
            default: return parseAlnum(f.raw(), cs, f.decimalComma).value();
        }
    }

    /** The item's bytes as text. */
    public static String text(Field f, Charset cs) {
        return new String(f.st.bytes, f.off, f.len, cs);
    }

    /** A typed alphanumeric item's text back into its bytes (det-port typed groups): exactly its length, which a
     *  lifted String always has. */
    public static void putText(Field f, String s, Charset cs) {
        byte[] b = s.getBytes(cs);
        System.arraycopy(b, 0, f.st.bytes, f.off, Math.min(b.length, f.len));
    }

    // -------------------------------------------------------------------------------------- arithmetic store

    /** No ON SIZE ERROR: low-order digits beyond the scale dropped (or rounded half away from zero), high-order
     *  digits beyond the PICTURE lost; libcob's NaN (a zero divisor) leaves `to` unchanged (#4655). */
    public static void store(Field to, BigDecimal value, boolean rounded, Charset cs) {
        if (isNan(value)) {
            return;
        }
        if (to.kind == Field.Kind.NUMERIC_FLOAT) { // a float receiver: the value converted to its precision (Hfp)
            Hfp.store(to, value);
            return;
        }
        BigDecimal v = value.setScale(to.scale, rounded ? RoundingMode.HALF_UP : RoundingMode.DOWN);
        if (cat(to) == NUM_EDITED) {
            edit(to, Codec.Num.of(v), cs);
        } else {
            Codec.write(to, v.unscaledValue().abs(), v.signum() < 0, cs);
        }
    }

    /** ADD / SUBTRACT ... TO / FROM an unsigned binary item where cobc 3.1.2 compiles native integer arithmetic
     *  (#4684, oracle_assumptions C4; the translator marks where: gen.native_add). IBM is the reference: an unsigned
     *  receiver takes the absolute value of the result (1 - 3 is 2), truncated at its bytes under COMP-5 or
     *  TRUNC(BIN) and to its PICTURE under TRUNC(STD) -- exactly {@link #store}. The oracle wraps there instead (1 - 3
     *  is 65534 in a halfword): a declared oracle-vs-IBM difference, not modelled. */
    public static void storeNative(Field to, BigDecimal value, Charset cs) {
        store(to, value, false, cs);
    }

    /** ON SIZE ERROR: true, `to` unchanged, when the value does not fit or is libcob's NaN (#4655). */
    public static boolean storeChecked(Field to, BigDecimal value, boolean rounded, Charset cs) {
        if (isNan(value)) {
            return true;
        }
        if (to.kind == Field.Kind.NUMERIC_FLOAT) { // an exponent overflow is refused by name in Hfp, never a size error
            store(to, value, rounded, cs);
            return false;
        }
        BigDecimal v = value.setScale(to.scale, rounded ? RoundingMode.HALF_UP : RoundingMode.DOWN);
        BigInteger m = v.unscaledValue().abs();
        if (cat(to) == NUM_EDITED ? m.compareTo(BigInteger.TEN.pow(to.digits)) >= 0 : !Codec.fits(to, m, v.signum() < 0)) {
            return true;
        }
        store(to, value, rounded, cs);
        return false;
    }

    /** A Db2 value assigned to a host variable (#4579): as {@link #storeChecked}, but a binary host variable (COMP,
     *  COMP-4, BINARY, COMP-5) takes any value its 2 / 4 / 8 bytes hold whatever TRUNC says -- the PICTURE's digits do
     *  not limit it. Db2 for z/OS declares the host variable by its data type (the precompiler maps S9(4) COMP to
     *  SMALLINT, S9(9) COMP to INTEGER, S9(18) COMP to BIGINT) and raises SQLCODE -304 only for a value outside that
     *  type (IBM Db2 for z/OS SQL Reference, "Assignments and comparisons": numeric assignment, SQLSTATE 22003); the
     *  COBOL side's num_store (tests/equivalence/db2/ggsql.c) does the same. A true return means -304. */
    public static boolean storeHostChecked(Field to, BigDecimal value, boolean rounded, Charset cs) {
        if (to.kind != Field.Kind.NUMERIC_BINARY) {
            return storeChecked(to, value, rounded, cs);
        }
        boolean before = Codec.truncBinary;
        Codec.truncBinary = false;  // the byte-width range for the check and the store; the caller's TRUNC restored
        try {
            return storeChecked(to, value, rounded, cs);
        } finally {
            Codec.truncBinary = before;
        }
    }

    // ---------------------------------------------------------------------------------------------- compare

    private static int cmpBytes(byte[] a, byte[] b, Charset cs) {
        byte sp = Codec.space(cs);
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {
            int x = (i < a.length ? a[i] : sp) & 0xFF;
            int y = (i < b.length ? b[i] : sp) & 0xFF;
            if (x != y) return x < y ? -1 : 1;
        }
        return 0;
    }

    /** Nonnumeric operands' bytes: in the data's byte order, or under the PROGRAM COLLATING SEQUENCE's alphabet when
     *  `coll` is one (#4539; null: byte order). */
    private static int cmpBytes(byte[] a, byte[] b, Charset cs, Sort.Collating coll) {
        return coll == null ? cmpBytes(a, b, cs) : coll.relation(a, b, cs);
    }

    public static int compare(Field a, Field b, Charset cs) {
        return compare(a, b, cs, null);
    }

    /** As {@link #compare(Field, Field, Charset)}; a nonnumeric comparison under `coll` (PROGRAM COLLATING
     *  SEQUENCE), a numeric one by value whatever the sequence. */
    public static int compare(Field a, Field b, Charset cs, Sort.Collating coll) {
        if (cat(a) == NUMERIC && cat(b) == NUMERIC) {
            if (a.kind == Field.Kind.NUMERIC_FLOAT || b.kind == Field.Kind.NUMERIC_FLOAT) {
                return Integer.signum(floatOperand(a, cs).compareTo(floatOperand(b, cs)));
            }
            return Integer.signum(num(a, cs).compareTo(num(b, cs)));
        }
        return cmpBytes(operand(a, b, cs), operand(b, a, cs), cs, coll);
    }

    /** `f`'s bytes as a nonnumeric comparand against `other` (#4665): a numeric item against an elementary
     *  nonnumeric one (alphanumeric, alphabetic, edited) is its digits as characters (IBM Enterprise COBOL 6.4
     *  Language Reference, "Comparison of numeric and alphanumeric operands": as if moved to an alphanumeric item of
     *  as many characters as its digits; GnuCOBOL likewise): a zoned item's bytes, its overpunched sign digit
     *  unpunched; a packed or binary item's value in its PICTURE's digits, unsigned. A sign-separate or P-scaled item
     *  the generator refuses (register C13). Anything else (a group): its bytes. */
    private static byte[] operand(Field f, Field other, Charset cs) {
        if (cat(f) != NUMERIC || cat(other) == NUMERIC || cat(other) == GROUP || f.kind == Field.Kind.NUMERIC_FLOAT) {
            return f.raw();
        }
        return digitsText(f, cs);
    }

    /** A numeric item's digits as characters, unsigned (see {@link #operand}). */
    private static byte[] digitsText(Field f, Charset cs) {
        if (f.kind == Field.Kind.NUMERIC_DISPLAY) {
            byte[] b = f.raw();
            if (f.signed && !f.signSeparate) {
                int i = f.signLeading ? 0 : f.digits - 1;
                char c = Codec.ch(b[i], cs);
                int d = Codec.POSITIVE.indexOf(c) >= 0 ? Codec.POSITIVE.indexOf(c) : Codec.NEGATIVE.indexOf(c);
                if (d >= 0) b[i] = String.valueOf((char) ('0' + d)).getBytes(cs)[0];
            }
            return b;
        }
        String s = num(f, cs).setScale(f.scale, java.math.RoundingMode.DOWN).unscaledValue().abs().toString();
        s = s.length() >= f.digits ? s.substring(s.length() - f.digits) : "0".repeat(f.digits - s.length()) + s;
        return s.getBytes(cs);
    }

    // ------------------------------------------------------------------------------- typed (lifted) items
    /** An alphanumeric item held as a Java String of its length (det-port B3): `s` moved into it -- truncated on
     *  the right, or padded with spaces (COBOL's alphanumeric MOVE). */
    public static String fit(String s, int length) {
        if (s.length() >= length) {
            return s.substring(0, length);
        }
        return s + " ".repeat(length - s.length());
    }

    /** An arithmetic result stored in a binary item of `digits` (signed or not) and read back -- exactly what
     *  `store` leaves in such an item (truncation, ROUNDED, the byte width's wrap-around), through a scratch item. */
    public static long binary(BigDecimal value, int digits, boolean signed, boolean rounded, Charset cs) {
        return binary(value, digits, signed, rounded, false, cs);
    }

    /** As {@link #binary(BigDecimal, int, boolean, boolean, Charset)}; `comp5` for a COMP-5 item, which keeps its
     *  bytes whatever TRUNC says (#4684). */
    public static long binary(BigDecimal value, int digits, boolean signed, boolean rounded, boolean comp5,
                              Charset cs) {
        int bytes = digits <= 4 ? 2 : digits <= 9 ? 4 : 8;
        Field t = Field.binary(new Storage(bytes), 0, digits, 0, signed, comp5);
        store(t, value, rounded, cs);
        return num(t, cs).longValue();
    }

    /** As {@link #binary}, for the statements {@link #storeNative} marks (#4684, C4): IBM's absolute value; `comp5`
     *  for a COMP-5 item, which no TRUNC truncates. */
    public static long binaryNative(BigDecimal value, int digits, boolean signed, boolean comp5, Charset cs) {
        return binary(value, digits, signed, false, comp5, cs);
    }

    /** A numeric value stored in a zoned DISPLAY item (PIC S9(digits)V9(scale), sign overpunched) and read back:
     *  what `store` leaves there (high-order truncation, the scale, ROUNDED, an unsigned item's sign dropped). */
    public static BigDecimal zoned(BigDecimal value, int digits, int scale, boolean signed, boolean rounded,
                                   Charset cs) {
        Field t = Field.zoned(new Storage(digits), 0, digits, scale, signed, false, false);
        store(t, value, rounded, cs);
        return num(t, cs);
    }

    /** As zoned, for a packed-decimal (COMP-3) item. */
    public static BigDecimal packed(BigDecimal value, int digits, int scale, boolean signed, boolean rounded,
                                    Charset cs) {
        Field t = Field.packed(new Storage(digits / 2 + 1), 0, digits, scale, signed);
        store(t, value, rounded, cs);
        return num(t, cs);
    }

    /** The text a MOVE of `from` into an alphanumeric item of `length` bytes leaves there (any sender: COBOL's MOVE
     *  rules, through a scratch item). */
    public static String moveText(Field from, int length, Charset cs) {
        Field t = Field.alphanumeric(new Storage(length), 0, length, false);
        move(from, t, cs);
        return text(t, cs);
    }

    /** Two alphanumeric values compared as COBOL compares them: the shorter padded with spaces, byte by byte in the
     *  record charset (its collating sequence -- not Java's char order when the charset is EBCDIC). */
    public static int compareText(String a, String b, Charset cs) {
        return compareText(a, b, cs, null);
    }

    /** As {@link #compareText(String, String, Charset)}, under `coll` (PROGRAM COLLATING SEQUENCE; null: byte
     *  order). */
    public static int compareText(String a, String b, Charset cs, Sort.Collating coll) {
        if (coll != null) {
            return coll.relation(a.getBytes(cs), b.getBytes(cs), cs);
        }
        byte[] x = a.getBytes(cs);
        byte[] y = b.getBytes(cs);
        byte sp = " ".getBytes(cs)[0];
        int n = Math.max(x.length, y.length);
        for (int i = 0; i < n; i++) {
            int u = (i < x.length ? x[i] : sp) & 0xFF;
            int v = (i < y.length ? y[i] : sp) & 0xFF;
            if (u != v) {
                return u < v ? -1 : 1;
            }
        }
        return 0;
    }

    /** Two texts compared as nonnumeric operands (a function's result, a literal): the shorter padded with
     *  spaces, character by character in their code (the record charset's byte order for a single-byte one). */
    public static int compareText(String a, String b) {
        int n = Math.max(a.length(), b.length());
        for (int i = 0; i < n; i++) {
            char x = i < a.length() ? a.charAt(i) : ' ';
            char y = i < b.length() ? b.charAt(i) : ' ';
            if (x != y) {
                return x < y ? -1 : 1;
            }
        }
        return 0;
    }

    public static int compare(Field a, String nonnumericLiteral, Charset cs) {
        return compare(a, nonnumericLiteral, cs, null);
    }

    public static int compare(Field a, String nonnumericLiteral, Charset cs, Sort.Collating coll) {
        return cmpBytes(a.raw(), nonnumericLiteral.getBytes(cs), cs, coll);
    }

    public static int compare(Field a, BigDecimal numericLiteral, Charset cs) {
        return compare(a, numericLiteral, cs, null);
    }

    public static int compare(Field a, BigDecimal numericLiteral, Charset cs, Sort.Collating coll) {
        if (cat(a) != NUMERIC) {
            // GnuCOBOL: an alphanumeric or edited item (#4665) against a numeric literal is a text comparison with the
            // literal's digits (the generator passes the literal as written, through the String overload)
            return cmpBytes(a.raw(), numericLiteral.unscaledValue().abs().toString().getBytes(cs), cs, coll);
        }
        if (a.kind == Field.Kind.NUMERIC_FLOAT) return Integer.signum(num(a, cs).compareTo(Hfp.of(numericLiteral)));
        return Integer.signum(num(a, cs).compareTo(numericLiteral));
    }

    /** A comparand of a floating-point comparison (IBM: "in floating-point arithmetic if either comparand is a
     *  floating-point value"): a float as it is, a fixed-point item converted to long HFP. */
    private static BigDecimal floatOperand(Field f, Charset cs) {
        return f.kind == Field.Kind.NUMERIC_FLOAT ? num(f, cs) : Hfp.of(num(f, cs));
    }

    /** `a` against an ALL literal (#4557; IBM Enterprise COBOL 6.4 Language Reference, "Figurative constants": ALL
     *  literal, "Comparison of alphanumeric operands"): the literal repeated -- or cut -- to the length of the other
     *  operand, then compared byte by byte (no padding is left to do). A numeric item is compared as the
     *  nonnumeric operand it is against a nonnumeric literal. */
    public static int compareAll(Field a, String allLiteral, Charset cs) {
        return compareAll(a, allLiteral, cs, null);
    }

    /** As {@link #compareAll(Field, String, Charset)}, under `coll` (PROGRAM COLLATING SEQUENCE; null: byte order). */
    public static int compareAll(Field a, String allLiteral, Charset cs, Sort.Collating coll) {
        return cmpBytes(a.raw(), repeat(allLiteral, a.len, cs), cs, coll);
    }

    /** `n` bytes of `allLiteral` repeated from its first character (a space for an empty one). */
    private static byte[] repeat(String allLiteral, int n, Charset cs) {
        byte[] lit = allLiteral.isEmpty() ? " ".getBytes(cs) : allLiteral.getBytes(cs);
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) b[i] = lit[i % lit.length];
        return b;
    }

    public static int compareFigurative(Field a, Figurative f, Charset cs) {
        return compareFigurative(a, f, cs, null);
    }

    public static int compareFigurative(Field a, Figurative f, Charset cs, Sort.Collating coll) {
        if (f == Figurative.ZEROS && cat(a) == NUMERIC) return Integer.signum(num(a, cs).signum());
        byte[] b = new byte[a.len];
        Arrays.fill(b, figByte(f, cs));
        return cmpBytes(a.raw(), b, cs, coll);
    }

    // ----------------------------------------------------------------------------------------- class tests

    /** Whether a signed zoned or packed item's sign is X'F' (an unsigned-form sign in a signed item). */
    private static boolean isNumericSignF(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        if (f.kind == Field.Kind.NUMERIC_PACKED) return (d[f.off + f.len - 1] & 0x0F) == 0x0F;
        if (f.kind != Field.Kind.NUMERIC_DISPLAY) return false;
        char c = Codec.ch(d[f.signLeading ? f.off : f.off + f.digits - 1], cs);
        return c >= '0' && c <= '9';
    }

    public static boolean isNumeric(Field f, Charset cs) {
        byte[] d = f.st.bytes;
        if (Codec.numprocPfd && f.signed && !f.signSeparate && isNumericSignF(f, cs)) {
            // NUMPROC(PFD)'s class test takes C, D and "+0" for a signed item, NOPFD's C, D and F (Programming Guide
            // SC27-8714-03, Table 7, NUMCLS(PRIM)): an F-signed value's answer is not settled -- refused (C5)
            throw Codec.nonPreferredSign(f);
        }
        switch (f.kind) {
            case NUMERIC_DISPLAY: {
                int start = f.off;
                if (f.signSeparate) {
                    char sc = Codec.ch(d[f.signLeading ? f.off : f.off + f.digits], cs);
                    if (sc != '+' && sc != '-') return false;
                    if (f.signLeading) start++;
                }
                for (int i = 0; i < f.digits; i++) {
                    char c = Codec.ch(d[start + i], cs);
                    boolean signPos = f.signed && !f.signSeparate && (f.signLeading ? i == 0 : i == f.digits - 1);
                    boolean ok = c >= '0' && c <= '9'
                            || signPos && (Codec.POSITIVE.indexOf(c) >= 0 || Codec.NEGATIVE.indexOf(c) >= 0);
                    if (!ok) return false;
                }
                return true;
            }
            case NUMERIC_PACKED: {
                for (int i = 0; i < f.len; i++) {
                    int b = d[f.off + i] & 0xFF;
                    if ((b >> 4) > 9) return false;
                    if (i < f.len - 1 && (b & 0x0F) > 9) return false;
                }
                int sign = d[f.off + f.len - 1] & 0x0F;
                return f.signed ? sign >= 0x0A : sign == 0x0F;
            }
            case NUMERIC_BINARY:
                return true;
            case NUMERIC_EDITED:
                return false;
            default: {
                if (f.len == 0) return false;
                for (int i = 0; i < f.len; i++) {
                    char c = Codec.ch(d[f.off + i], cs);
                    if (c < '0' || c > '9') return false;
                }
                return true;
            }
        }
    }

    private static boolean letters(Field f, Charset cs, boolean upper, boolean lower) {
        if (f.len == 0) return false;
        for (int i = 0; i < f.len; i++) {
            char c = Codec.ch(f.st.bytes[f.off + i], cs);
            boolean ok = c == ' ' || (upper && c >= 'A' && c <= 'Z') || (lower && c >= 'a' && c <= 'z');
            if (!ok) return false;
        }
        return true;
    }

    public static boolean isAlphabetic(Field f, Charset cs) {
        return letters(f, cs, true, true);
    }

    public static boolean isAlphabeticUpper(Field f, Charset cs) {
        return letters(f, cs, true, false);
    }

    public static boolean isAlphabeticLower(Field f, Charset cs) {
        return letters(f, cs, false, true);
    }

    // ------------------------------------------------------------------------------------------------ DISPLAY

    /**
     * The operand as IBM DISPLAY writes it (the model tests/equivalence/faults/ggdisplay.c applies to GnuCOBOL):
     * a signed zoned item with an embedded sign as its bytes, the sign overpunched; a binary or packed item as
     * zoned digits of its PICTURE (scale: no decimal point; signed: the last digit overpunched); an unsigned or
     * SIGN SEPARATE zoned item, a group, an alphanumeric or an edited item as libcob writes it.
     */
    public static String displayText(Field f, Charset cs) {
        switch (f.kind) {
            case NUMERIC_FLOAT: // IBM: as external floating point -.9(8)E-99 (COMP-1) / -.9(17)E-99 (COMP-2)
                return Hfp.display(Hfp.read(f), f.len == 8);
            case NUMERIC_PACKED:
            case NUMERIC_BINARY: {
                Codec.Num n = Codec.read(f, cs);
                Storage s = new Storage(f.digits);
                Field z = Field.zoned(s, 0, f.digits, f.scale, f.signed, false, false);
                store(z, n, cs);
                return new String(s.bytes, cs);
            }
            default:
                return text(f, cs);
        }
    }

    // ------------------------------------------------------------------------------------------------ STRING

    /** One sending item of a STRING statement. */
    public static final class StringPart {
        final byte[] src;
        final byte[] delim; // null: DELIMITED BY SIZE

        private StringPart(byte[] src, byte[] delim) {
            this.src = src;
            this.delim = delim;
        }

        public static StringPart size(Field src) {
            return new StringPart(src.raw(), null);
        }

        public static StringPart size(String lit, Charset cs) {
            return new StringPart(lit.getBytes(cs), null);
        }

        public static StringPart delimited(Field src, Field delim) {
            return new StringPart(src.raw(), delim.raw());
        }

        public static StringPart delimited(Field src, String delim, Charset cs) {
            return new StringPart(src.raw(), delim.getBytes(cs));
        }

        public static StringPart delimited(String src, Field delim, Charset cs) {
            return new StringPart(src.getBytes(cs), delim.raw());
        }

        public static StringPart delimited(String src, String delim, Charset cs) {
            return new StringPart(src.getBytes(cs), delim.getBytes(cs));
        }
    }

    private static int indexOf(byte[] hay, int from, int to, byte[] pat) {
        for (int i = from; i + pat.length <= to; i++) {
            if (matches(hay, i, pat)) return i;
        }
        return -1;
    }

    private static boolean matches(byte[] hay, int at, byte[] pat) {
        if (at < 0 || at + pat.length > hay.length) return false;
        for (int j = 0; j < pat.length; j++) if (hay[at + j] != pat[j]) return false;
        return true;
    }

    /**
     * STRING parts... INTO into [WITH POINTER pointer]. Bytes are transferred in order; the receiving item is not
     * padded (only the bytes written change). `pointer` may be null (start at 1). Returns true on OVERFLOW (the
     * pointer is outside the receiver, or the data did not fit; what fits is transferred).
     */
    public static boolean string(Field into, Field pointer, Charset cs, StringPart... parts) {
        int off = 0;
        if (pointer != null) {
            BigDecimal p = num(pointer, cs);
            if (p.compareTo(BigDecimal.ONE) < 0 || p.compareTo(BigDecimal.valueOf(into.len)) > 0) return true;
            off = p.intValue() - 1;
        }
        boolean overflow = false;
        outer:
        for (StringPart part : parts) {
            int n = part.src.length;
            if (part.delim != null && part.delim.length > 0) {
                int at = indexOf(part.src, 0, part.src.length, part.delim);
                if (at >= 0) n = at;
            }
            int room = into.len - off;
            if (n > room) {
                System.arraycopy(part.src, 0, into.st.bytes, into.off + off, room);
                off = into.len;
                overflow = true;
                break outer;
            }
            System.arraycopy(part.src, 0, into.st.bytes, into.off + off, n);
            off += n;
        }
        if (pointer != null) store(pointer, BigDecimal.valueOf(off + 1), false, cs);
        return overflow;
    }

    // ---------------------------------------------------------------------------------------------- UNSTRING

    /** One DELIMITED BY operand of UNSTRING: a literal or an item, with ALL. */
    public static final class Delim {
        final byte[] bytes;
        final boolean all;

        private Delim(byte[] bytes, boolean all) {
            this.bytes = bytes;
            this.all = all;
        }

        public static Delim of(String lit, boolean all, Charset cs) {
            return new Delim(lit.getBytes(cs), all);
        }

        public static Delim of(Field f, boolean all) {
            return new Delim(f.raw(), all);
        }
    }

    /** One INTO operand of UNSTRING, with its optional DELIMITER IN and COUNT IN items. */
    public static final class Into {
        final Field target;
        Field delimiterIn;
        Field countIn;

        private Into(Field target) {
            this.target = target;
        }

        public static Into of(Field target) {
            return new Into(target);
        }

        public Into delimiterIn(Field f) {
            this.delimiterIn = f;
            return this;
        }

        public Into countIn(Field f) {
            this.countIn = f;
            return this;
        }
    }

    /**
     * UNSTRING src [DELIMITED BY delims] INTO intos... [WITH POINTER pointer] [TALLYING IN tallying]. `delims`
     * may be empty (the rest of the source goes to the first INTO); `pointer` and `tallying` may be null. The
     * tallying item is incremented by the number of receiving items filled. Returns true on OVERFLOW (the
     * pointer is outside the source, or source characters remain after the last INTO).
     */
    public static boolean unstring(Field src, Field pointer, Field tallying, List<Delim> delims, Charset cs,
                                   Into... intos) {
        byte[] data = src.raw();
        int off = 0;
        if (pointer != null) {
            BigDecimal p = num(pointer, cs);
            if (p.compareTo(BigDecimal.ONE) < 0 || p.compareTo(BigDecimal.valueOf(data.length)) > 0) return true;
            off = p.intValue() - 1;
        }
        int filled = 0;
        byte sp = Codec.space(cs);
        for (Into in : intos) {
            if (off >= data.length) break;
            int end = data.length;
            int dlen = 0;
            Delim hit = null;
            scan:
            for (int i = off; i < data.length; i++) {
                for (Delim d : delims) {
                    if (d.bytes.length > 0 && matches(data, i, d.bytes)) {
                        end = i;
                        dlen = d.bytes.length;
                        hit = d;
                        break scan;
                    }
                }
            }
            if (delims.isEmpty()) end = Math.min(data.length, off + in.target.len); // no DELIMITED BY: by size
            byte[] piece = Arrays.copyOfRange(data, off, end);
            move(temp(piece), in.target, cs);
            if (in.countIn != null) store(in.countIn, BigDecimal.valueOf(piece.length), false, cs);
            if (in.delimiterIn != null) {
                if (hit != null) move(temp(hit.bytes), in.delimiterIn, cs);
                else padCopy(new byte[0], in.delimiterIn, false, cs);
            }
            off = end + dlen;
            if (hit != null && hit.all) {
                while (matches(data, off, hit.bytes)) off += hit.bytes.length;
            }
            filled++;
        }
        if (pointer != null) store(pointer, BigDecimal.valueOf(off + 1), false, cs);
        if (tallying != null) store(tallying, num(tallying, cs).add(BigDecimal.valueOf(filled)), false, cs);
        return off < data.length;
    }

    // ----------------------------------------------------------------------------------------------- INSPECT

    public enum Mode { CHARACTERS, ALL, LEADING, FIRST }

    /** One TALLYING, REPLACING or CONVERTING phrase of INSPECT, with its BEFORE / AFTER INITIAL. */
    public static final class Clause {
        final Field counter; // tallying
        final Mode mode;
        final byte[] pattern; // null: CHARACTERS
        final byte[] by; // replacing
        final byte[] from; // converting
        final byte[] to;
        byte[] before;
        byte[] after;

        private Clause(Field counter, Mode mode, byte[] pattern, byte[] by, byte[] from, byte[] to) {
            this.counter = counter;
            this.mode = mode;
            this.pattern = pattern;
            this.by = by;
            this.from = from;
            this.to = to;
        }

        /** TALLYING counter FOR CHARACTERS | ALL pattern | LEADING pattern (pattern null for CHARACTERS). */
        public static Clause tally(Field counter, Mode mode, String pattern, Charset cs) {
            return new Clause(counter, mode, pattern == null ? null : pattern.getBytes(cs), null, null, null);
        }

        public static Clause tally(Field counter, Mode mode, Field pattern) {
            return new Clause(counter, mode, pattern == null ? null : pattern.raw(), null, null, null);
        }

        /** REPLACING CHARACTERS BY by | ALL / LEADING / FIRST pattern BY by. */
        public static Clause replace(Mode mode, String pattern, String by, Charset cs) {
            return new Clause(null, mode, pattern == null ? null : pattern.getBytes(cs), by.getBytes(cs), null, null);
        }

        public static Clause replace(Mode mode, Field pattern, Field by) {
            return new Clause(null, mode, pattern == null ? null : pattern.raw(), by.raw(), null, null);
        }

        /** CONVERTING from TO to. */
        public static Clause converting(String from, String to, Charset cs) {
            return new Clause(null, Mode.ALL, null, null, from.getBytes(cs), to.getBytes(cs));
        }

        public static Clause converting(Field from, Field to) {
            return new Clause(null, Mode.ALL, null, null, from.raw(), to.raw());
        }

        public Clause before(String s, Charset cs) {
            before = s.getBytes(cs);
            return this;
        }

        public Clause before(Field f) {
            before = f.raw();
            return this;
        }

        public Clause after(String s, Charset cs) {
            after = s.getBytes(cs);
            return this;
        }

        public Clause after(Field f) {
            after = f.raw();
            return this;
        }
    }

    /**
     * INSPECT target with its phrases in the order written. The phrases act on the original text; within the
     * TALLYING phrase, or the REPLACING phrase, the earlier clause takes the characters (libcob's mark array); the
     * two phrases are separate passes, as cobc emits them.
     */
    public static void inspect(Field target, Charset cs, Clause... clauses) {
        byte[] data = target.raw();
        int n = data.length;
        boolean[] mark = new boolean[n];
        byte[] out = data.clone();
        long[] counts = new long[clauses.length];
        int phase = -1;
        for (int ci = 0; ci < clauses.length; ci++) {
            Clause c = clauses[ci];
            // cobc emits TALLYING and REPLACING as separate passes: a new phase starts with fresh marks
            int ph = c.from != null ? 2 : c.by != null ? 1 : 0;
            if (ph != phase) {
                Arrays.fill(mark, false);
                phase = ph;
            }
            int start = 0;
            int end = n;
            if (c.before != null) {
                int at = indexOf(data, 0, n, c.before);
                if (at >= 0) end = at;
            }
            if (c.after != null) {
                int at = indexOf(data, 0, n, c.after);
                start = at >= 0 ? at + c.after.length : n;
            }
            if (c.from != null) {
                for (int i = start; i < end; i++) {
                    for (int j = 0; j < c.from.length; j++) {
                        if (data[i] == c.from[j]) {
                            out[i] = c.to[j];
                            break;
                        }
                    }
                }
                continue;
            }
            boolean replacing = c.by != null;
            if (c.pattern == null) {
                for (int i = start; i < end; i++) {
                    if (mark[i]) continue;
                    mark[i] = true;
                    counts[ci]++;
                    if (replacing) out[i] = c.by[0];
                }
                continue;
            }
            int pl = c.pattern.length;
            for (int i = start; i + pl <= end; i++) {
                if (!matches(data, i, c.pattern)) {
                    if (c.mode == Mode.LEADING) break;
                    continue;
                }
                boolean taken = false;
                for (int j = 0; j < pl; j++) if (mark[i + j]) taken = true;
                if (taken) continue;
                for (int j = 0; j < pl; j++) mark[i + j] = true;
                counts[ci]++;
                if (replacing) System.arraycopy(c.by, 0, out, i, Math.min(pl, c.by.length));
                i += pl - 1;
                if (c.mode == Mode.FIRST) break;
            }
        }
        System.arraycopy(out, 0, target.st.bytes, target.off, n);
        for (int ci = 0; ci < clauses.length; ci++) {
            Clause c = clauses[ci];
            if (c.counter != null) {
                store(c.counter, num(c.counter, cs).add(BigDecimal.valueOf(counts[ci])), false, cs);
            }
        }
    }

    /** #4181: a LINK's COMMAREA as the target's DTO of `size` bytes reads it. The COMMAREA is passed by reference, so
     *  the target sees the caller's storage from the area's first byte -- here up to the end of the caller's record
     *  (its 01 item's storage), never past it: z/OS would show the target whatever storage follows the record, which
     *  this port does not lay out, so those bytes are LOW-VALUES (docs/language_status/oracle_assumptions.md X10). */
    public static Storage commarea(Field f, int size) {
        Storage w = new Storage(size);
        int n = Math.max(0, Math.min(size, f.storage().bytes.length - f.offset()));
        System.arraycopy(f.storage().bytes, f.offset(), w.bytes, 0, n);
        beyond(f, w.bytes, n, false);
        return w;
    }

    /** #4679: the bytes of `area` from `n` on that lie past `f`'s record, from or (`back`) into the opaque bytes a
     *  longer COMMAREA brought past it (Storage.beyond); none there: left as they are (LOW-VALUES). */
    public static void beyond(Field f, byte[] area, int n, boolean back) {
        byte[] b = f.storage().beyond;
        if (b == null) {
            return;
        }
        int past = f.offset() + n - f.storage().bytes.length;  // where byte n of the area sits in `beyond`
        int k = Math.max(0, Math.min(area.length - n, b.length - past));
        if (past < 0 || k == 0) {
            return;
        }
        if (back) {
            System.arraycopy(area, n, b, past, k);
        } else {
            System.arraycopy(b, past, area, n, k);
        }
    }

    /** #4181: what the LINKed program left in the COMMAREA, back into the caller's storage -- up to the end of the
     *  caller's record, as commarea read it. */
    public static void commareaBack(Storage w, Field f) {
        int n = Math.max(0, Math.min(w.bytes.length, f.storage().bytes.length - f.offset()));
        System.arraycopy(w.bytes, 0, f.storage().bytes, f.offset(), n);
        beyond(f, w.bytes, n, true);
    }
}
