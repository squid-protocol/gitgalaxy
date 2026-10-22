/*
 * mvswait.c -- CardDemo's assembler wait routine MVSWAIT (app/asm/MVSWAIT.asm, Apache-2.0), for the equivalence
 * harness. GnuCOBOL cannot run S/370 assembler; a program that CALLs "MVSWAIT" (CardDemo's COBSWAIT) runs against
 * this instead. oracle_assumptions.md (A1) declares the translation.
 *
 *   CALL 'MVSWAIT' USING MVSWAIT-TIME           (a fullword: the delay, in hundredths of a second)
 *
 * The assembler loads the fullword, starts an interval timer (ASMWAIT BINLBL) and returns with R15 = 0 (SR R15,R15);
 * it writes nothing to the caller's storage. The wait is not observable in any compared output, so it is not slept:
 * RETURN-CODE 0 at once. The argument is passed by reference and its length is not known here, so the 4-byte
 * minimum the Java twin checks (Mvswait.call) cannot be checked on this side: a shorter item is a program defect
 * the COBOL compiler's own storage layout decides.
 */
int MVSWAIT(unsigned char *delay) {
    (void)delay;
    return 0;
}
