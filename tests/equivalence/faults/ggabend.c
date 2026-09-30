/*
 * ggabend.c -- the equivalence harness's stand-in for the Language Environment abend service (#4023 follow-up).
 *
 * A program abends with `CALL 'CEE3ABD' USING ABCODE, TIMING` (ABCODE PIC S9(9) BINARY: the user abend code).
 * On z/OS the step ends ABEND Unnnn with no return code. GnuCOBOL has no CEE3ABD: this one writes the abend,
 * `U%04d` (the code modulo 4096, as a user completion code is), to the file GG_ABEND names, and ends the
 * process -- libcob's exit handlers close the files, as the step's end would. The Java side's CobolAbend
 * carries the same code, and the harness compares the two.
 */
#include <stdio.h>
#include <stdlib.h>

static void record_abend(int code) {
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
