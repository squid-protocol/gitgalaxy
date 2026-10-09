/*
 * ggabend.c -- the equivalence harness's stand-in for the Language Environment abend service (#4023 follow-up).
 *
 * A program abends with `CALL 'CEE3ABD' USING ABCODE, TIMING` (ABCODE PIC S9(9) BINARY: the user abend code).
 * On z/OS the step ends ABEND Unnnn with no return code. GnuCOBOL has no CEE3ABD: this one writes the abend,
 * `U%04d` (the code modulo 4096, as a user completion code is), to the file GG_ABEND names, and ends the
 * process -- libcob's exit handlers close the files, as the step's end would. The Java side's CobolAbend
 * carries the same code, and the harness compares the two.
 *
 * #4269: an abend backs out the step's Db2 unit of work (the work since its last COMMIT), as Db2 for z/OS does when
 * a DSN / CAF batch program ends abnormally -- ggsql.c's ggsql_uow_end, when the program is a Db2 one (a weak
 * reference: linked without ggsql.c, there is no unit of work to end).
 */
#include <stdio.h>
#include <stdlib.h>

extern void ggsql_uow_end(int rollback) __attribute__((weak));

static void record_abend(int code) {
    if (ggsql_uow_end) ggsql_uow_end(1);
    const char *path = getenv("GG_ABEND");
    FILE *f = path ? fopen(path, "w") : NULL;
    if (f) {
        fprintf(f, "U%04d\n", code % 4096);
        fclose(f);
    }
    fflush(NULL);
    exit(254);
}

/* ABCODE is big-endian binary, as -std=ibm stores it. */
static int binary4(const unsigned char *p) {
    return (int)(((unsigned)p[0] << 24) | ((unsigned)p[1] << 16) | ((unsigned)p[2] << 8) | (unsigned)p[3]);
}

int CEE3ABD(unsigned char *abcode, unsigned char *timing) {
    (void)timing;
    record_abend(binary4(abcode));
    return 0;
}
