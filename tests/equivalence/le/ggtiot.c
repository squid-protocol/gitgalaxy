/*
 * ggtiot.c -- the z/OS control blocks a batch program walks (PSA -> TCB -> TIOT) for the equivalence harness
 * (#5856, register A2). GnuCOBOL has no PSA at address 0, so CardDemo's CBSTM03A (which SETs ADDRESS OF a record TO a
 * NULL pointer, then to the pointers it finds there) runs against these blocks instead; the det runtime's DetMvs.java
 * lays the same blocks from the same stated step, and the two are compared byte for byte (test_mvs_oracle_5856.py).
 *
 * IBM, z/OS MVS Data Areas: the PSA is at address 0 and PSATNEW (X'218') holds the TCB's address; TCBTIO (TCB + X'0C')
 * the TIOT's; the TIOT is a 24-byte header (TIOCNJOB, TIOCSTPN, TIOCJSTP) and one 20-byte entry per single-unit DD
 * (TIOELNGH 20, TIOEDDNM at +4, the UCB token TIOEFSRT at +17..19), ended by a fullword of zeros.
 *
 * The step is the environment variable GGMVS_STEP: JOB;STEP;PROCSTEP;DD:UCB,DD:NOUCB,... (the case's `mvs_step`; the
 * Java side reads the same text as the system property gitgalaxy.mvs.step). Only the bytes the walk reads are laid.
 * equivalence_mvs.py rewrites the program so it reaches these entry points (all by reference, so a COBOL POINTER is
 * passed as the address of its 8 bytes):
 *
 *   CALL "GGPSAPTR" USING ptr            a POINTER never set (NULL: IBM's address 0) is the PSA
 *   CALL "GGMVSCHK" USING ptr BY VALUE n  a record of n bytes SET ADDRESS OF ptr: refused past the block's end
 *   CALL "GGTIOTADV" / "GGTIOTSUB" USING ptr BY VALUE n    ptr moves n bytes on / back, within its block
 *
 * A pointer into no block laid here is not an MVS pointer and GGMVSCHK lets it be (the other pointer lanes); the Java
 * side refuses it, which this side cannot tell from a pointer of another kind. What is not modelled ends the run:
 * "GGTIOT: ... is not modelled" on stderr, exit 98 (equivalence.py MODEL_REFUSAL), so no proof rests on a guess.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PSATNEW 0x218
#define TCBTIO 0x0C
#define TIOT_HEADER 24
#define TIOT_ENTRY 20
#define POINTER 8 /* GnuCOBOL's on x86-64, register C9 */

static unsigned char *blk[3]; /* PSA, TCB, TIOT */
static long blklen[3];

static void refuse(const char *what) {
    fprintf(stderr, "GGTIOT: %s is not modelled\n", what);
    exit(98);
}

static void name(unsigned char *b, const char *s) {
    if (strlen(s) > 8) {
        refuse("a name longer than 8 characters in GGMVS_STEP");
    }
    memset(b, ' ', 8);
    memcpy(b, s, strlen(s));
}

static void put(unsigned char *b, void *p) {
    memcpy(b, &p, POINTER);
}

static void lay(void) {
    const char *step = getenv("GGMVS_STEP");
    if (blk[0]) {
        return;
    }
    if (!step || !*step) {
        refuse("z/OS control blocks (PSA / TCB / TIOT): no job step stated (GGMVS_STEP; register A2)");
    }
    char *copy = strdup(step);
    char *f[4];
    int n = 0;
    char *p = copy;
    for (; n < 3; n++) { /* exactly four ';'-separated fields, empty ones kept */
        char *semi = strchr(p, ';');
        if (!semi) {
            refuse("z/OS control blocks (PSA / TCB / TIOT): no job step stated (GGMVS_STEP; register A2)");
        }
        *semi = 0;
        f[n] = p;
        p = semi + 1;
    }
    f[3] = p;
    if (strchr(p, ';')) {
        refuse("z/OS control blocks (PSA / TCB / TIOT): no job step stated (GGMVS_STEP; register A2)");
    }
    int ndd = 0;
    char *dd[256];
    if (*f[3]) {
        for (char *t = f[3];; ) {
            char *comma = strchr(t, ',');
            if (comma) {
                *comma = 0;
            }
            if (ndd == 256) {
                refuse("more than 256 DDs in GGMVS_STEP");
            }
            dd[ndd++] = t;
            if (!comma) {
                break;
            }
            t = comma + 1;
        }
        while (ndd > 0 && !*dd[ndd - 1]) { /* a trailing comma ends the list (as the Java side's split does) */
            ndd--;
        }
    }
    blklen[0] = PSATNEW + POINTER;
    blklen[1] = TCBTIO + POINTER;
    blklen[2] = TIOT_HEADER + TIOT_ENTRY * ndd + 4;
    for (int i = 0; i < 3; i++) {
        blk[i] = calloc(1, (size_t)blklen[i]);
    }
    put(blk[0] + PSATNEW, blk[1]);
    put(blk[1] + TCBTIO, blk[2]);
    name(blk[2], f[0]);
    name(blk[2] + 8, f[1]);
    name(blk[2] + 16, f[2]);
    for (int i = 0; i < ndd; i++) {
        char *colon = strchr(dd[i], ':');
        unsigned char *e = blk[2] + TIOT_HEADER + TIOT_ENTRY * i;
        if (!colon || strchr(colon + 1, ':') || (strcmp(colon + 1, "UCB") && strcmp(colon + 1, "NOUCB"))) {
            refuse("a DD in GGMVS_STEP that is not NAME:UCB or NAME:NOUCB");
        }
        *colon = 0;
        e[0] = TIOT_ENTRY;
        name(e + 4, dd[i]);
        if (!strcmp(colon + 1, "UCB")) { /* a token, not an address: only "not zero" is stated */
            e[17] = (unsigned char)((i + 1) >> 16);
            e[18] = (unsigned char)((i + 1) >> 8);
            e[19] = (unsigned char)(i + 1);
        }
    }
    free(copy);
}

/* The block `p` addresses and its offset: -1 when none (a block's end is its own, so a walk may stop there). */
static int find(const unsigned char *p, long *off) {
    for (int pass = 0; pass < 2; pass++) {
        for (int i = 0; i < 3; i++) {
            long at = p - blk[i];
            if (p >= blk[i] && (pass ? at == blklen[i] : at < blklen[i])) {
                *off = at;
                return i;
            }
        }
    }
    return -1;
}

static unsigned char *get(unsigned char *ptr) {
    unsigned char *p;
    memcpy(&p, ptr, POINTER);
    return p ? p : blk[0]; /* NULL is IBM's address 0: the PSA */
}

/* CALL "GGPSAPTR" USING ptr */
int GGPSAPTR(unsigned char *ptr) {
    lay();
    put(ptr, blk[0]);
    return 0;
}

/* CALL "GGMVSCHK" USING ptr BY VALUE n */
int GGMVSCHK(unsigned char *ptr, int n) {
    long off;
    lay();
    int b = find(get(ptr), &off);
    if (b >= 0 && blklen[b] - off < n) {
        refuse("SET ADDRESS OF a record past the fields the stand-in lays (register A2)");
    }
    return 0;
}

static int move(unsigned char *ptr, long n) {
    long off;
    lay();
    int b = find(get(ptr), &off);
    if (b < 0) {
        refuse("pointer arithmetic on a pointer to no z/OS control block the stand-in lays (register A2)");
    }
    if (off + n < 0 || off + n > blklen[b]) {
        refuse("pointer arithmetic that leaves the control block the pointer addresses");
    }
    put(ptr, blk[b] + off + n);
    return 0;
}

/* CALL "GGTIOTADV" USING ptr BY VALUE n */
int GGTIOTADV(unsigned char *ptr, int n) {
    return move(ptr, n);
}

/* CALL "GGTIOTSUB" USING ptr BY VALUE n */
int GGTIOTSUB(unsigned char *ptr, int n) {
    return move(ptr, -(long)n);
}

/* For the tests: block i (0 PSA, 1 TCB, 2 TIOT), its bytes and length. */
const unsigned char *GGMVSBLK(int i, long *len) {
    lay();
    *len = blklen[i];
    return blk[i];
}
