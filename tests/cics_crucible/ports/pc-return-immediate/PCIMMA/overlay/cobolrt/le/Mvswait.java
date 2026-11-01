package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;

/**
 * MVSWAIT -- CardDemo's assembler wait routine (app/asm/MVSWAIT.asm), as the equivalence harness models it for the
 * COBOL side (tests/equivalence/le/mvswait.c): the same effect, and the same refusal (oracle_assumptions.md A1).
 *
 *   CALL 'MVSWAIT' USING MVSWAIT-TIME          (a fullword: hundredths of a second to wait)
 *
 * The assembler loads the fullword, starts an interval timer (ASMWAIT) and returns with R15 = 0, writing nothing to
 * the caller's storage. The wait is not observable in any output a proof compares, so it is not slept: the call
 * returns at once with RETURN-CODE 0. An argument shorter than the fullword the assembler loads is refused.
 */
public final class Mvswait {
    private static final int FULLWORD = 4;

    private Mvswait() {
    }

    // [rule RT-LE-MVSWAIT]
    public static void call(Field delay) {
        if (delay.length() < FULLWORD) {
            throw new UnsupportedOperationException(
                    "MVSWAIT: an argument shorter than the fullword the assembler loads is not modelled");
        }
    }
}
