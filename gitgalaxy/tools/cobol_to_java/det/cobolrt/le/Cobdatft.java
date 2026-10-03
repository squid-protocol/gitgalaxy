package __PACKAGE__.cobolrt.le;

import __PACKAGE__.cobolrt.Field;

/**
 * COBDATFT -- CardDemo's assembler date routine (app/asm/COBDATFT.asm), as the equivalence harness models it for
 * the COBOL side (tests/equivalence/le/cobdatft.c): the same bytes, and the same refusals -- what that model does
 * not model, this does not either (oracle_assumptions.md A1).
 *
 *   CALL 'COBDATFT' USING CODATECN-REC
 *
 * Input type '2' (YYYY-MM-DD) to output type '2' (YYYYMMDD) is modelled: COOUTDT(4) = COINPDT(4),
 * COOUTDT+4(2) = COINPDT+5(2), COOUTDT+6(2) = COINPDT+8(2); every other byte of the record is left as it was.
 * Input type '1' (its check is a 20-byte CLC against a 1-byte literal) and the error path (an MVC of 38 bytes from
 * a 13-byte literal) depend on the load module's literal pool, not on the source: refused.
 */
public final class Cobdatft {
    private static final int IN_TYPE = 0;
    private static final int IN_DATE = 1;
    private static final int OUT_TYPE = 21;
    private static final int OUT_DATE = 22;

    private Cobdatft() {
    }

    public static void call(Field rec) {
        byte[] b = rec.storage().bytes;
        int r = rec.offset();
        byte inType = b[r + IN_TYPE];
        if (inType == '1') {
            throw new UnsupportedOperationException(
                    "COBDATFT: input type '1' (VALIDIN1: a 20-byte CLC against a 1-byte literal) is not modelled");
        }
        if (inType != '2' || b[r + OUT_TYPE] == '1') {
            throw new UnsupportedOperationException(
                    "COBDATFT: the error path (MVC of 38 bytes from a 13-byte literal) is not modelled");
        }
        System.arraycopy(b, r + IN_DATE, b, r + OUT_DATE, 4);
        System.arraycopy(b, r + IN_DATE + 5, b, r + OUT_DATE + 4, 2);
        System.arraycopy(b, r + IN_DATE + 8, b, r + OUT_DATE + 6, 2);
    }
}
