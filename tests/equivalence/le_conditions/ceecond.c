/*
 * ceecond.c -- a model of Language Environment condition handling (CEEHDLR, CEEHDLU, CEESGL) written from IBM's
 * manuals, for the equivalence harness (#8062, register L8). GnuCOBOL has no LE runtime: this is the first slice of an
 * oracle a port's handler behaviour can be compared against. It is ASSUMED (IBM-documented), never z/OS-observed.
 *
 * Not yet linked into any program: tests/equivalence/le/ is linked into every batch, call and CICS program, this
 * directory is not. It is wired in only once a frame source for GnuCOBOL exists (L8, "Remaining slices"); until a
 * frame source is installed every entry point refuses (exit 98), so a stray link proves nothing.
 *
 * IBM references (z/OS 2.5):
 *   Programming Reference SA38-0683-50: "CEEHDLR--Register user-written condition handler", "CEEHDLU--Unregister
 *     user-written condition handler", "CEESGL--Signal a condition", "Invoking callable services" (fc), "ERRCOUNT".
 *   Programming Guide SA38-0682-50: "Handle cursor" / "Resume cursor", Table 34 "Default responses to unhandled
 *     conditions", "User-written condition handler interface" with Table 40 "Valid result codes", Figure 74
 *     "Language Environment condition token".
 *
 *   CALL "CEEHDLR" USING routine, token, fc      routine: a PROCEDURE-POINTER (its bytes hold the entry address)
 *   CALL "CEEHDLU" USING routine, fc
 *   CALL "CEESGL"  USING cond_rep, q_data_token, fc
 *   handler(c_ctok, token, result_code, new_condition)
 *
 * Modelled (IBM-documented):
 *   - handlers are queued per stack frame and driven LIFO; a frame's queue goes when the frame leaves the stack.
 *   - CEEHDLR: CEE000; CEE080 (sev 1, msg 256) when the routine is already registered for this frame, and it is
 *     registered again; CEE081 (sev 3, msg 257) for an entry that is not valid (here: a null entry, our reading).
 *   - CEEHDLU: CEE000; CEE07S (sev 1, msg 252) when the frame has no such registration.
 *   - CEESGL: the handlers of the signalling frame, then of each caller's frame; result_code preset to 20 (IBM: the
 *     default when a handler sets none); 10 resume at the resume cursor (after the CEESGL), 20 percolate to the next
 *     handler, 21 percolate to the first handler of the frame before; unhandled: with an fc and severity 0-3 the fc
 *     is CEE069 (sev 0, msg 201) and the program resumes after the call; without an fc, severity 0 or 1 is ignored.
 * Assumed (L8): the fc of a CEESGL whose condition a handler resumed is CEE000; COBOL's own handler between two
 *   frames percolates a condition CEESGL raised; the token bytes (case 1, control 1, facility "CEE" in EBCDIC, ISI
 *   zero, the L7 layout); ERRCOUNT is its default 0 (unlimited), so the error count never ends the enclave; of two
 *   registrations of one routine, CEEHDLU removes the later.
 * Refused by name (exit 98, "... not modelled"): no frame source; an omitted fc on a service that does not succeed
 *   (IBM: the condition is then signalled); result codes 30 / 31 / 32 (promote) and 60 (fix-up and resume) and any
 *   other value; a condition signalled, or a handler (un)registered, inside a handler; T_I_U (severity 4, or an
 *   unhandled severity 2 / 3 with no fc: the thread terminates); a case-1 token whose two severities disagree.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*gg_le_handler)(unsigned char *, unsigned char *, unsigned char *, unsigned char *);
/* The stack frames live now, innermost (the caller of the service) first; each pointer names one activation. */
typedef int (*gg_le_frames_fn)(void **chain, int max);

#define GG_LE_MAX 64

static gg_le_frames_fn frames_fn;
static struct reg {
    void *frame;
    gg_le_handler fn;
    unsigned char token[4];
} regs[GG_LE_MAX];
static int nregs, dispatching;

void gg_le_set_frames(gg_le_frames_fn fn) { frames_fn = fn; nregs = 0; dispatching = 0; }

static void refuse(const char *service, const char *what) {
    fprintf(stderr, "%s: %s is not modelled\n", service, what);
    fflush(stdout);
    exit(98);
}

/* A case-1 LE token (CEE000 is all zero): severity, message number, case 1 / severity / control 1, facility CEE (EBCDIC), ISI 0. */
static void token(unsigned char *fc, int sev, int msg) {
    static const unsigned char cee[3] = {0xC3, 0xC5, 0xC5};
    memset(fc, 0, 12);
    if (!sev && !msg) return; /* CEE000: all zero (as CEELOCT, L7) */
    fc[1] = (unsigned char)sev;
    fc[2] = (unsigned char)(msg >> 8);
    fc[3] = (unsigned char)(msg & 0xff);
    fc[4] = (unsigned char)(0x40 | (sev << 3) | 1);
    memcpy(fc + 5, cee, 3);
}

/* Write the outcome, or refuse when it is not CEE000 and the fc was omitted (IBM: the condition would be signalled). */
static void feedback(const char *service, unsigned char *fc, int sev, int msg) {
    if (fc) token(fc, sev, msg);
    else if (sev || msg) refuse(service, "signalling the service's own condition (an omitted fc)");
}

/* The live chain; registrations of frames no longer on it are dropped (IBM: unregistered when the frame goes). */
static int live(const char *service, void **chain) {
    if (!frames_fn) refuse(service, "the caller's stack frame (no frame source for this runtime)");
    int n = frames_fn(chain, GG_LE_MAX);
    if (n < 1) refuse(service, "a call with no stack frame");
    int kept = 0;
    for (int i = 0; i < nregs; i++) {
        int on = 0;
        for (int j = 0; j < n && !on; j++) on = regs[i].frame == chain[j];
        if (on) regs[kept++] = regs[i];
    }
    nregs = kept;
    return n;
}

int CEEHDLR(unsigned char *routine, unsigned char *tok, unsigned char *fc) {
    void *chain[GG_LE_MAX];
    if (dispatching) refuse("CEEHDLR", "registering a handler inside a handler");
    live("CEEHDLR", chain);
    gg_le_handler fn = NULL;
    if (routine) memcpy(&fn, routine, sizeof fn);
    if (!fn) {
        feedback("CEEHDLR", fc, 3, 257); /* CEE081 */
        return 0;
    }
    int again = 0;
    for (int i = 0; i < nregs; i++) again |= regs[i].frame == chain[0] && regs[i].fn == fn;
    if (nregs == GG_LE_MAX) refuse("CEEHDLR", "more than 64 registered handlers");
    regs[nregs].frame = chain[0];
    regs[nregs].fn = fn;
    memset(regs[nregs].token, 0, 4);
    if (tok) memcpy(regs[nregs].token, tok, 4);
    nregs++;
    feedback("CEEHDLR", fc, again ? 1 : 0, again ? 256 : 0); /* CEE080 / CEE000 */
    return 0;
}

int CEEHDLU(unsigned char *routine, unsigned char *fc) {
    void *chain[GG_LE_MAX];
    if (dispatching) refuse("CEEHDLU", "unregistering a handler inside a handler");
    live("CEEHDLU", chain);
    gg_le_handler fn = NULL;
    if (routine) memcpy(&fn, routine, sizeof fn);
    for (int i = nregs - 1; i >= 0; i--) {
        if (regs[i].frame != chain[0] || regs[i].fn != fn) continue;
        memmove(regs + i, regs + i + 1, (size_t)(nregs - i - 1) * sizeof regs[0]);
        nregs--;
        feedback("CEEHDLU", fc, 0, 0);
        return 0;
    }
    feedback("CEEHDLU", fc, 1, 252); /* CEE07S */
    return 0;
}

int CEESGL(unsigned char *cond, unsigned char *qdata, unsigned char *fc) {
    void *chain[GG_LE_MAX];
    (void)qdata; /* placed in the ISI for CEEGQDT, which is not modelled */
    if (dispatching) refuse("CEESGL", "a condition signalled inside a handler");
    int n = live("CEESGL", chain);
    if (!cond) refuse("CEESGL", "an omitted cond_rep");
    int sev = (cond[4] >> 3) & 7, kase = cond[4] >> 6;
    if (kase == 1 && ((cond[0] << 8) | cond[1]) != sev) refuse("CEESGL", "a case-1 token whose two severities differ");
    if (sev > 4) refuse("CEESGL", "a severity above 4");
    for (int f = 0; f < n; f++) {
        for (int i = nregs - 1; i >= 0; i--) {
            if (regs[i].frame != chain[f]) continue;
            unsigned char ctok[12], tok[4], newc[12], rc[4];
            int result = 20; /* IBM: percolate when the handler sets no result_code */
            memcpy(ctok, cond, 12);
            memcpy(tok, regs[i].token, 4);
            memset(newc, 0, sizeof newc);
            memcpy(rc, &result, 4);
            dispatching = 1;
            regs[i].fn(ctok, tok, rc, newc);
            dispatching = 0;
            memcpy(&result, rc, 4);
            if (result == 10) { /* resume at the resume cursor: after this CEESGL */
                feedback("CEESGL", fc, 0, 0);
                return 0;
            }
            if (result == 21) break; /* the first handler of the frame before */
            if (result != 20) {
                char what[96];
                snprintf(what, sizeof what, "handler result_code %d (only 10, 20 and 21 are)", result);
                refuse("CEESGL", what);
            }
        }
    }
    if (fc && sev <= 3) {
        token(fc, 0, 201); /* CEE069: an unhandled condition was returned in a feedback code */
        return 0;
    }
    if (!fc && sev <= 1) return 0; /* a safe condition, ignored */
    refuse("CEESGL", "an unhandled condition promoted to T_I_U (thread termination)");
    return 0;
}
