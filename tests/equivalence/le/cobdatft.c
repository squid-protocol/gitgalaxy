/*
 * cobdatft.c -- CardDemo's assembler date routine COBDATFT (app/asm/COBDATFT.asm, Apache-2.0), for the equivalence
 * harness. GnuCOBOL cannot run S/370 assembler; a program that CALLs "COBDATFT" (CardDemo's CBACT01C) runs against
 * this instead, and a port is proven against what this returns. It is the assembler, instruction for instruction:
 * oracle_assumptions.md (A1) declares the translation.
 *
 *   CALL 'COBDATFT' USING CODATECN-REC          (app/cpy/CODATECN.cpy; the DSECT is app/maclib/COCDATFT.mac)
 *
 *   offset  0  COINTYPE  CL1    '1' input YYYYMMDD, '2' input YYYY-MM-DD
 *   offset  1  COINPDT   CL20   the input date
 *   offset 21  COOUTYPE  CL1    '1' output YYYY-MM-DD, '2' output YYYYMMDD
 *   offset 22  COOUTDT   CL20   the output date: only the bytes the MVCs below name are written; the rest keep
 *                               whatever the caller's storage held
 *   offset 42  COERMSG   CL38
 *
 * VALIDIN1 (type '1') is NOT modelled: its check `CLC COINPDT+4,=C'-'` has no explicit length, so it compares
 *   L'COINPDT = 20 bytes from COINPDT+4 against the 1-byte literal and the 19 bytes the literal pool holds after
 *   it -- what that comparison decides depends on the load module, not on the source. CBACT01C never takes it
 *   (it passes type '2'); a call that does is refused (exit 98).
 * VALIDIN2 (type '2'): COOUTYPE must not be '1' (the separator check is commented out in the source); then
 *   COOUTDT(4) = COINPDT(4), COOUTDT+4(2) = COINPDT+5(2), COOUTDT+6(2) = COINPDT+8(2).
 * Any other type, or the VALIDIN2 check failing, takes GOTOERR: MVC COERMSG,=C'INVALID INPUT' -- an MVC whose
 * length is COERMSG's, 38 bytes, from a 13-byte literal, so it copies 25 bytes from past the literal pool's end:
 * what the load module holds there. That is NOT modelled either. A call that would take an unmodelled path writes
 * "COBDATFT: ... is not modelled" to stderr and ends the run (exit 98), so no proof rests on a guess.
 * R15 is set to 0 (SR R15,R15): RETURN-CODE 0 on every path that returns.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void refuse(const char *what) {
    fprintf(stderr, "COBDATFT: %s is not modelled\n", what);
    exit(98);
}

int COBDATFT(unsigned char *rec) {
    unsigned char *intype = rec, *inp = rec + 1, *outtype = rec + 21, *out = rec + 22;
    if (*intype == '1') {
        refuse("input type '1' (VALIDIN1: a 20-byte CLC against a 1-byte literal)");
    } else if (*intype == '2') {
        if (*outtype == '1') {
            refuse("the error path (MVC of 38 bytes from a 13-byte literal)");
        }
        memcpy(out, inp, 4);
        memcpy(out + 4, inp + 5, 2);
        memcpy(out + 6, inp + 8, 2);
    } else {
        refuse("the error path (MVC of 38 bytes from a 13-byte literal)");
    }
    return 0;
}
