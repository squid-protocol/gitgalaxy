package __PACKAGE__.cobolrt;

import java.util.Objects;
import java.util.function.Supplier;

/**
 * Explicit per-estate / per-program compiler and runtime options profile (#4714, #4704).
 *
 * <p>Replaces global {@code static volatile} option flags with an immutable profile bound to the current thread
 * ({@link #current()}, {@link #swap(CobolProfile)}, {@link #runWith(CobolProfile, Runnable)}). Two threads running
 * programs compiled with different options (e.g. {@code TRUNC(STD)} + {@code NUMPROC(PFD)} vs {@code TRUNC(BIN)} +
 * {@code NUMPROC(NOPFD)}) never interfere with each other.
 */
public final class CobolProfile {
    public enum TruncMode { BIN, STD, OPT }

    public enum NumprocMode { NOPFD, PFD, MIG }

    public enum ArithMode { COMPAT, EXTEND }

    private static final CobolProfile DEFAULTS = new CobolProfile(
            TruncMode.BIN, NumprocMode.NOPFD, ArithMode.COMPAT, false, false, false, "IBM037");

    private static final CobolProfile ZOS_DEFAULTS = new CobolProfile(
            TruncMode.STD, NumprocMode.NOPFD, ArithMode.COMPAT, true, false, false, "IBM037");

    private static final ThreadLocal<CobolProfile> CURRENT = ThreadLocal.withInitial(() -> DEFAULTS);

    private final TruncMode trunc;
    private final NumprocMode numproc;
    private final ArithMode arith;
    private final boolean zosComp5;
    private final boolean intdateLilian;
    private final boolean decimalComma;
    private final String codepage;

    public CobolProfile(
            TruncMode trunc,
            NumprocMode numproc,
            ArithMode arith,
            boolean zosComp5,
            boolean intdateLilian,
            boolean decimalComma,
            String codepage) {
        this.trunc = Objects.requireNonNull(trunc, "trunc");
        this.numproc = Objects.requireNonNull(numproc, "numproc");
        this.arith = Objects.requireNonNull(arith, "arith");
        this.zosComp5 = zosComp5;
        this.intdateLilian = intdateLilian;
        this.decimalComma = decimalComma;
        this.codepage = Objects.requireNonNull(codepage, "codepage");
    }

    /** Oracle / equivalence-harness defaults: TRUNC(BIN), NUMPROC(NOPFD), ARITH(COMPAT), little-endian COMP-5. */
    public static CobolProfile defaults() {
        return DEFAULTS;
    }

    /** IBM Enterprise COBOL for z/OS defaults: TRUNC(STD), NUMPROC(NOPFD), ARITH(COMPAT), big-endian COMP-5. */
    public static CobolProfile zosDefaults() {
        return ZOS_DEFAULTS;
    }

    /** The active profile on the current thread. */
    public static CobolProfile current() {
        return CURRENT.get();
    }

    /** Replaces the current thread's active profile and returns the previous one. */
    public static CobolProfile swap(CobolProfile next) {
        Objects.requireNonNull(next, "next");
        CobolProfile before = CURRENT.get();
        CURRENT.set(next);
        return before;
    }

    /** Runs {@code body} under {@code profile} and restores the prior profile in a {@code finally} block. */
    public static void runWith(CobolProfile profile, Runnable body) {
        CobolProfile before = swap(profile);
        try {
            body.run();
        } finally {
            CURRENT.set(before);
        }
    }

    /** Runs {@code body} under {@code profile} and restores the prior profile in a {@code finally} block. */
    public static <T> T runWith(CobolProfile profile, Supplier<T> body) {
        CobolProfile before = swap(profile);
        try {
            return body.get();
        } finally {
            CURRENT.set(before);
        }
    }

    public TruncMode trunc() {
        return trunc;
    }

    public NumprocMode numproc() {
        return numproc;
    }

    public ArithMode arith() {
        return arith;
    }

    public boolean zosComp5() {
        return zosComp5;
    }

    public boolean intdateLilian() {
        return intdateLilian;
    }

    public boolean decimalComma() {
        return decimalComma;
    }

    public String codepage() {
        return codepage;
    }

    public boolean truncBinary() {
        return trunc == TruncMode.STD || trunc == TruncMode.OPT;
    }

    public boolean truncOpt() {
        return trunc == TruncMode.OPT;
    }

    public boolean numprocPfd() {
        return numproc == NumprocMode.PFD;
    }

    public boolean arithExtend() {
        return arith == ArithMode.EXTEND;
    }

    public CobolProfile withTrunc(TruncMode next) {
        return new CobolProfile(next, numproc, arith, zosComp5, intdateLilian, decimalComma, codepage);
    }

    public CobolProfile withNumproc(NumprocMode next) {
        return new CobolProfile(trunc, next, arith, zosComp5, intdateLilian, decimalComma, codepage);
    }

    public CobolProfile withArith(ArithMode next) {
        return new CobolProfile(trunc, numproc, next, zosComp5, intdateLilian, decimalComma, codepage);
    }

    public CobolProfile withZosComp5(boolean next) {
        return new CobolProfile(trunc, numproc, arith, next, intdateLilian, decimalComma, codepage);
    }

    public CobolProfile withIntdateLilian(boolean next) {
        return new CobolProfile(trunc, numproc, arith, zosComp5, next, decimalComma, codepage);
    }

    public CobolProfile withDecimalComma(boolean next) {
        return new CobolProfile(trunc, numproc, arith, zosComp5, intdateLilian, next, codepage);
    }

    public CobolProfile withCodepage(String next) {
        return new CobolProfile(trunc, numproc, arith, zosComp5, intdateLilian, decimalComma, next);
    }

    /** Canonical fingerprint of all option dimensions (for evidence-staleness tracking). */
    public String fingerprint() {
        return "TRUNC=" + trunc
                + ";NUMPROC=" + numproc
                + ";ARITH=" + arith
                + ";ZOS_COMP5=" + zosComp5
                + ";INTDATE=" + (intdateLilian ? "LILIAN" : "ANSI")
                + ";DECIMAL_POINT=" + (decimalComma ? "COMMA" : "PERIOD")
                + ";CODEPAGE=" + codepage;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof CobolProfile p)) return false;
        return zosComp5 == p.zosComp5
                && intdateLilian == p.intdateLilian
                && decimalComma == p.decimalComma
                && trunc == p.trunc
                && numproc == p.numproc
                && arith == p.arith
                && codepage.equals(p.codepage);
    }

    @Override
    public int hashCode() {
        return Objects.hash(trunc, numproc, arith, zosComp5, intdateLilian, decimalComma, codepage);
    }

    @Override
    public String toString() {
        return "CobolProfile[" + fingerprint() + "]";
    }
}
