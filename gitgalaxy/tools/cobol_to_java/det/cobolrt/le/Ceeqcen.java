package __PACKAGE__.cobolrt.le;

import __PACKAGE__.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEQCEN -- query the century window (century_start, fc); set is CEESCEN -- set it (century_start, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceeqcen {
    private Ceeqcen() {
    }

    public static void call(Field century, Field fc, Charset cs) {
        LeTime.qcen(century, fc);
    }

    public static void set(Field century, Field fc, Charset cs) {
        LeTime.scen(century, fc);
    }
}
