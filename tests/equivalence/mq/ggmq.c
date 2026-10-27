/*
 * ggmq.c -- a model of the IBM MQ calls a CICS COBOL program makes (MQI: MQOPEN, MQGET, MQPUT, MQPUT1, MQCLOSE), for
 * the equivalence harness (#4892, register W1-W8). GnuCOBOL has no queue manager; a program that CALLs "MQGET" runs
 * against this instead, and a port is proven against what this returns. The twin of det/cobolrt/mq/QueueManager.java:
 * the two are kept to the same rules, and tests/cobol_mainframe/test_det_mq.py runs one table of calls through both.
 *
 * The queue manager's state is a stated fact of the case ($GGCICS_DIR/mq.cfg, written by tests/tools/equivalence_mq.py):
 *   QMGR <name> <ccsid>                      the queue manager the task is connected to (CICS: the region's)
 *   Q <name> <defpriority> <defpersistence>  each queue it holds (a local queue; any other name is unknown)
 *   M <name> <MQMD hex> <data hex | ->       each message on a queue at the task's start, in delivery order
 * IBM is the reference (IBM MQ documentation, "MQI calls" and the reason codes cited per check); what IBM leaves to the
 * installation or the moment is a register assumption, and every call, option or structure version not modelled stops
 * the run by name (exit 98, "... not modelled"), never guessed.
 *
 * The unit of work is the CICS task's (W5): a get or put under syncpoint is committed by SYNCPOINT and at the task's
 * normal end, and backed out by SYNCPOINT ROLLBACK or an abend that ends the task (ggcics.c's uow_end calls
 * ggmq_uow_end). Each call is an event in the task's stream (ggcics_event) and the queues the task leaves are
 * $GGCICS_OUT/mq.out.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void ggcics_event(const char *line, const char *data, int len); /* ggcics.c */

#define MDLEN 324  /* MQMD_LENGTH_1 */
#define MAXQ 64
#define MAXH 64

enum { AVAIL, PUT_PENDING, GET_PENDING, GONE };

typedef struct {
    int q, state, len;
    long seq;
    unsigned char md[MDLEN];
    unsigned char *data;
} msg_t;

static char qnames[MAXQ][49];
static int qprio[MAXQ], qpers[MAXQ], nq = 0;
static char qmgr[49] = "";
static int qmgr_ccsid = 37;
static msg_t *msgs = NULL;
static int nmsgs = 0, cap = 0;
static long seqc = 0, msgidc = 0;
static struct { int q, opts, open; } handles[MAXH];
static int nh = 0, loaded = 0;
/* the calls the case plans to fail (mq.cfg `FAULT VERB NTH REASON`): the nth call of that verb answers the reason, unperformed */
#define MAXF 32
static struct { char verb[16]; int nth, reason; } faults[MAXF];
static int nfaults = 0;
static struct { char verb[16]; int n; } counts[8];
static int ncounts = 0;

static void refuse(const char *call, const char *what) {
    fprintf(stderr, "%s: %s is not modelled\n", call, what);
    exit(98);
}

static int be32(const unsigned char *p) {
    return (int)((unsigned)p[0] << 24 | (unsigned)p[1] << 16 | (unsigned)p[2] << 8 | (unsigned)p[3]);
}

static void put32(unsigned char *p, int v) {
    p[0] = (unsigned char)((unsigned)v >> 24);
    p[1] = (unsigned char)((unsigned)v >> 16);
    p[2] = (unsigned char)((unsigned)v >> 8);
    p[3] = (unsigned char)v;
}

static int unhex(const char *h, unsigned char *out, int max) {
    int n = 0;
    if (strcmp(h, "-") == 0) return 0;
    for (; h[0] && h[1] && n < max; h += 2) {
        unsigned v;
        if (sscanf(h, "%2x", &v) != 1) break;
        out[n++] = (unsigned char)v;
    }
    return n;
}

static void hex(const unsigned char *p, int n, char *out) {
    static const char d[] = "0123456789ABCDEF";
    for (int i = 0; i < n; i++) {
        out[2 * i] = d[p[i] >> 4];
        out[2 * i + 1] = d[p[i] & 15];
    }
    out[2 * n] = '\0';
}

/* an MQCHAR48 name: trailing blanks and nulls dropped */
static void name48(const unsigned char *p, char *out) {
    int n = 48;
    while (n > 0 && (p[n - 1] == ' ' || p[n - 1] == '\0')) n--;
    memcpy(out, p, (size_t)n);
    out[n] = '\0';
}

static void pad(unsigned char *p, const char *s, int n) {
    int k = (int)strlen(s);
    memset(p, ' ', (size_t)n);
    memcpy(p, s, (size_t)(k < n ? k : n));
}

static int find_q(const char *name) {
    for (int i = 0; i < nq; i++)
        if (strcmp(qnames[i], name) == 0) return i;
    return -1;
}

static msg_t *add_msg(int q, const unsigned char *md, const unsigned char *data, int len, int state) {
    if (nmsgs == cap) {
        cap = cap ? cap * 2 : 16;
        msgs = realloc(msgs, (size_t)cap * sizeof *msgs);
        if (!msgs) refuse("MQ", "a queue manager out of memory");
    }
    msg_t *m = &msgs[nmsgs++];
    m->q = q;
    m->state = state;
    m->len = len;
    m->seq = ++seqc;
    memcpy(m->md, md, MDLEN);
    m->data = malloc(len > 0 ? (size_t)len : 1);
    if (len > 0) memcpy(m->data, data, (size_t)len);
    return m;
}

static void dump(void);

static void load(const char *call) {
    char path[4096], line[8192];
    if (loaded) return;
    const char *d = getenv("GGCICS_DIR");
    snprintf(path, sizeof path, "%s/mq.cfg", d ? d : ".");
    FILE *f = fopen(path, "r");
    if (!f) refuse(call, "a queue manager the case does not state (its \"mq\" section)");
    unsigned char md[MDLEN];
    static unsigned char data[65536];
    while (fgets(line, sizeof line, f)) {
        char a[64], b[64], c[1024], e[sizeof line];
        int x, y;
        if (sscanf(line, "QMGR %48s %d", a, &x) == 2) {
            strcpy(qmgr, a);
            qmgr_ccsid = x;
        } else if (sscanf(line, "Q %48s %d %d", a, &x, &y) == 3 && nq < MAXQ) {
            strcpy(qnames[nq], a);
            qprio[nq] = x;
            qpers[nq++] = y;
        } else if (sscanf(line, "FAULT %15s %d %d", a, &x, &y) == 3 && nfaults < MAXF) {
            strcpy(faults[nfaults].verb, a);
            faults[nfaults].nth = x;
            faults[nfaults++].reason = y;
        } else if (sscanf(line, "M %48s %1000s %8000s", b, c, e) == 3) {
            int q = find_q(b);
            if (q < 0 || unhex(c, md, MDLEN) != MDLEN) refuse(call, "a malformed mq.cfg message line");
            add_msg(q, md, data, unhex(e, data, (int)sizeof data), AVAIL);
        }
    }
    fclose(f);
    loaded = 1;
    atexit(dump);
}

/* the task's normal end commits its unit of work (W5); an abend that ended it was backed out already (uow_end(1)) */
void ggmq_uow_end(int rollback) {
    for (int i = 0; i < nmsgs; i++) {
        msg_t *m = &msgs[i];
        if (m->state == PUT_PENDING) m->state = rollback ? GONE : AVAIL;
        else if (m->state == GET_PENDING) {
            if (rollback) {
                m->state = AVAIL; /* IBM MQMD BackoutCount: "returned by MQGET as part of a unit of work, and backed out" */
                put32(m->md + 96, be32(m->md + 96) + 1);
            } else m->state = GONE;
        }
    }
}

/* delivery order: priority, then first in first out (MSGDLVSQ(PRIORITY), W3) */
static int before(const msg_t *a, const msg_t *b) {
    int pa = be32(a->md + 40), pb = be32(b->md + 40);
    return pa != pb ? pa > pb : a->seq < b->seq;
}

static void dump(void) {
    char path[4096];
    static char hx[2 * 65536 + 1], mdh[2 * MDLEN + 1];
    if (!loaded) return;
    ggmq_uow_end(0);
    const char *d = getenv("GGCICS_OUT");
    snprintf(path, sizeof path, "%s/mq.out", d ? d : ".");
    FILE *f = fopen(path, "w");
    if (!f) return;
    for (int q = 0; q < nq; q++) {
        fprintf(f, "Q %s\n", qnames[q]);
        int done[4096] = {0};
        for (;;) {
            int best = -1;
            for (int i = 0; i < nmsgs && i < 4096; i++)
                if (!done[i] && msgs[i].q == q && msgs[i].state == AVAIL && (best < 0 || before(&msgs[i], &msgs[best])))
                    best = i;
            if (best < 0) break;
            done[best] = 1;
            hex(msgs[best].md, MDLEN, mdh);
            hex(msgs[best].data, msgs[best].len, hx);
            fprintf(f, "M %s %s\n", mdh, msgs[best].len ? hx : "-");
        }
    }
    fclose(f);
}

static void hconn_ok(const char *call, const unsigned char *hconn) {
    if (be32(hconn) != 0) /* MQHC_DEF_HCONN: CICS needs no MQCONN, W6 */
        refuse(call, "an Hconn other than MQHC_DEF_HCONN (0) (MQCONN)");
}

/* one event: the call, the queue it names (as the program named it, or the handle's), CompCode and Reason */
static void ev(const char *verb, const char *queue, int cc, int rc, const char *extra, const unsigned char *data, int len) {
    char line[512];
    snprintf(line, sizeof line, "%s queue=%s cc=%d rc=%d%s", verb, queue, cc, rc, extra);
    ggcics_event(line, (const char *)data, len);
}

/* IBM: MQCC_WARNING for the two truncation reasons modelled, MQCC_FAILED for every other reason */
static int comp(int r) { return r == 0 ? 0 : (r == 2079 || r == 2080) ? 1 : 2; }

static void done(unsigned char *cc, unsigned char *rc, int r) {
    put32(cc, comp(r));
    put32(rc, r);
}

/* the reason the case plans for this call of `verb` (every call of it counts), or 0; the call is then not performed. The
 * twin of QueueManager.planned. */
static int planned(const char *verb) {
    int i, n = 0;
    for (i = 0; i < ncounts; i++)
        if (!strcmp(counts[i].verb, verb)) break;
    if (i == ncounts) {
        strcpy(counts[ncounts].verb, verb);
        counts[ncounts++].n = 0;
    }
    n = ++counts[i].n;
    for (i = 0; i < nfaults; i++)
        if (!strcmp(faults[i].verb, verb) && faults[i].nth == n) return faults[i].reason;
    return 0;
}

static const char *qname(int q) { return q >= 0 ? qnames[q] : ""; }

static int handle(const unsigned char *hobj) {
    int h = be32(hobj);
    return h >= 1 && h <= nh && handles[h - 1].open ? h - 1 : -1;
}

/* MQOD checks shared by MQOPEN and MQPUT1: the queue named, or -1 with rc 2085 */
static int resolve_od(const char *call, const unsigned char *od, char *name) {
    char qm[49];
    if (memcmp(od, "OD  ", 4) != 0) refuse(call, "an MQOD whose StrucId is not 'OD  ' (MQRC_OD_ERROR)");
    if (be32(od + 4) != 1) refuse(call, "an MQOD version other than 1");
    if (be32(od + 8) != 1) refuse(call, "an ObjectType other than MQOT_Q");
    name48(od + 12, name);
    name48(od + 60, qm);
    if (qm[0] && strcmp(qm, qmgr) != 0) refuse(call, "a queue on another queue manager (ObjectQMgrName)");
    return find_q(name);
}

#define OO_INPUT (1 | 2 | 4)
#define OO_OUTPUT 16
#define OO_SAVE_ALL 128
#define OO_PASS (256 | 512)
#define OO_MODELLED (OO_INPUT | OO_OUTPUT | OO_SAVE_ALL | OO_PASS | 8192)

/* MQOPEN (Hconn, ObjDesc, Options, Hobj, CompCode, Reason) */
int MQOPEN(unsigned char *hconn, unsigned char *od, unsigned char *options, unsigned char *hobj, unsigned char *cc,
           unsigned char *rc) {
    char name[49], extra[64];
    load("MQOPEN");
    hconn_ok("MQOPEN", hconn);
    int o = be32(options), fr = planned("MQOPEN");
    if (fr) {
        name48(od + 12, name);
        done(cc, rc, fr);
        snprintf(extra, sizeof extra, " options=%d hobj=0", o);
        ev("MQOPEN", name, comp(fr), fr, extra, NULL, 0);
        return 0;
    }
    if (o & ~OO_MODELLED) refuse("MQOPEN", "an option other than INPUT-*, OUTPUT, SAVE-ALL-CONTEXT, PASS-*-CONTEXT, FAIL-IF-QUIESCING");
    int q = resolve_od("MQOPEN", od, name);
    int inputs = !!(o & 1) + !!(o & 2) + !!(o & 4);
    int r = 0;
    /* IBM MQOPEN Options: one MQOO_INPUT_* at most; at least an input or output option here; SAVE_ALL_CONTEXT needs
     * an input option, PASS_*_CONTEXT needs MQOO_OUTPUT (MQRC_OPTIONS_ERROR 2046) */
    if (inputs > 1 || (!inputs && !(o & OO_OUTPUT)) || ((o & OO_SAVE_ALL) && !inputs) || ((o & OO_PASS) && !(o & OO_OUTPUT)))
        r = 2046;
    else if (q < 0)
        r = 2085; /* MQRC_UNKNOWN_OBJECT_NAME */
    if (!r && inputs)
        for (int i = 0; i < nh; i++)
            if (handles[i].open && handles[i].q == q && ((handles[i].opts | o) & 4) && (handles[i].opts & OO_INPUT))
                refuse("MQOPEN", "a queue opened for input twice with MQOO_INPUT_EXCLUSIVE (MQRC_OBJECT_IN_USE)");
    if (!r) {
        if (nh == MAXH) refuse("MQOPEN", "more than 64 object handles in a task");
        handles[nh].q = q;
        handles[nh].opts = o;
        handles[nh].open = 1;
        put32(hobj, ++nh); /* W4: handles are 1, 2, 3 ... in the order opened */
    }
    done(cc, rc, r);
    snprintf(extra, sizeof extra, " options=%d hobj=%d", o, r ? 0 : nh);
    ev("MQOPEN", name, comp(r), r, extra, NULL, 0);
    return 0;
}

/* MQCLOSE (Hconn, Hobj, Options, CompCode, Reason) */
int MQCLOSE(unsigned char *hconn, unsigned char *hobj, unsigned char *options, unsigned char *cc, unsigned char *rc) {
    load("MQCLOSE");
    hconn_ok("MQCLOSE", hconn);
    int fr = planned("MQCLOSE");
    if (fr) {
        int fh = handle(hobj);
        done(cc, rc, fr);
        ev("MQCLOSE", qname(fh >= 0 ? handles[fh].q : -1), comp(fr), fr, "", NULL, 0);
        return 0;
    }
    if (be32(options) != 0) refuse("MQCLOSE", "an option other than MQCO_NONE");
    int h = handle(hobj), q = h >= 0 ? handles[h].q : -1, r = h < 0 ? 2019 : 0; /* MQRC_HOBJ_ERROR */
    if (h >= 0) {
        handles[h].open = 0;
        put32(hobj, -1); /* MQHO_UNUSABLE_HOBJ */
    }
    done(cc, rc, r);
    ev("MQCLOSE", qname(q), comp(r), r, "", NULL, 0);
    return 0;
}

#define GMO_WAIT 1
#define GMO_SYNC 2
#define GMO_NOSYNC 4
#define GMO_TRUNC 64
#define GMO_CONVERT 16384
#define GMO_MODELLED (GMO_WAIT | GMO_SYNC | GMO_NOSYNC | GMO_TRUNC | 8192 | GMO_CONVERT)

static const unsigned char zero24[24];

/* MQGET (Hconn, Hobj, MsgDesc, GetMsgOpts, BufferLength, Buffer, DataLength, CompCode, Reason) */
int MQGET(unsigned char *hconn, unsigned char *hobj, unsigned char *md, unsigned char *gmo, unsigned char *buflen,
          unsigned char *buffer, unsigned char *datalen, unsigned char *cc, unsigned char *rc) {
    char extra[64];
    load("MQGET");
    hconn_ok("MQGET", hconn);
    int fr = planned("MQGET");
    if (fr) {
        int fh = handle(hobj);
        done(cc, rc, fr);
        ev("MQGET", qname(fh >= 0 ? handles[fh].q : -1), comp(fr), fr, " len=-1", buffer, 0);
        return 0;
    }
    if (memcmp(md, "MD  ", 4) != 0 || be32(md + 4) != 1) refuse("MQGET", "an MQMD other than version 1");
    if (memcmp(gmo, "GMO ", 4) != 0 || be32(gmo + 4) != 1) refuse("MQGET", "an MQGMO other than version 1");
    int o = be32(gmo + 8), h = handle(hobj), q = h >= 0 ? handles[h].q : -1, bl = be32(buflen), r = 0;
    if (o & ~GMO_MODELLED) refuse("MQGET", "an option other than WAIT, SYNCPOINT, NO-SYNCPOINT, ACCEPT-TRUNCATED-MSG, FAIL-IF-QUIESCING, CONVERT");
    msg_t *m = NULL;
    if (h < 0) r = 2019;                                  /* MQRC_HOBJ_ERROR */
    else if (!(handles[h].opts & OO_INPUT)) r = 2037;     /* MQRC_NOT_OPEN_FOR_INPUT */
    else if ((o & GMO_SYNC) && (o & GMO_NOSYNC)) r = 2046; /* MQRC_OPTIONS_ERROR */
    else if (bl < 0) r = 2005;                            /* MQRC_BUFFER_LENGTH_ERROR */
    else {
        /* a version-1 MQGMO matches on the MQMD's MsgId and CorrelId (IBM MQGMO MatchOptions) */
        if (memcmp(md + 48, zero24, 24) != 0 || memcmp(md + 72, zero24, 24) != 0)
            refuse("MQGET", "a get matching a MsgId or CorrelId (MQMI_NONE / MQCI_NONE expected)");
        for (int i = 0; i < nmsgs; i++)
            if (msgs[i].q == q && msgs[i].state == AVAIL && (!m || before(&msgs[i], m))) m = &msgs[i];
        if (!m) {
            if ((o & GMO_WAIT) && be32(gmo + 12) == -1) refuse("MQGET", "MQWI_UNLIMITED on a queue no producer fills (W2)");
            if ((o & GMO_WAIT) && be32(gmo + 12) < -1) refuse("MQGET", "a negative WaitInterval (MQRC_WAIT_INTERVAL_ERROR)");
            r = 2033; /* MQRC_NO_MSG_AVAILABLE: no other producer during the task, so a wait ends empty (W2) */
        }
    }
    int copied = 0;
    if (m) {
        if (o & GMO_CONVERT) { /* MQGMO_CONVERT: a no-op where the message already is as asked (W7) */
            int want = be32(md + 28);
            if ((want ? want : qmgr_ccsid) != be32(m->md + 28) || be32(md + 24) != be32(m->md + 24))
                refuse("MQGET", "MQGMO_CONVERT to another CCSID or encoding");
        }
        copied = m->len < bl ? m->len : bl;
        memcpy(md, m->md, MDLEN);
        if (copied) memcpy(buffer, m->data, (size_t)copied);
        put32(datalen, m->len);
        pad(gmo + 24, qnames[q], 48); /* ResolvedQName */
        if (m->len > bl && !(o & GMO_TRUNC)) {
            r = 2080; /* MQRC_TRUNCATED_MSG_FAILED: the message stays on the queue */
        } else {
            r = m->len > bl ? 2079 : 0; /* MQRC_TRUNCATED_MSG_ACCEPTED */
            /* on z/OS a get with neither SYNCPOINT option is in the unit of work (IBM MQGMO_SYNCPOINT) */
            m->state = (o & GMO_NOSYNC) ? GONE : GET_PENDING;
        }
    }
    done(cc, rc, r);
    snprintf(extra, sizeof extra, " len=%d", m ? m->len : -1);
    ev("MQGET", qname(q), comp(r), r, extra, buffer, copied);
    return 0;
}

#define PMO_SYNC 2
#define PMO_NOSYNC 4
#define PMO_DEFAULT 32
#define PMO_NOCONTEXT 16384
#define PMO_MODELLED (PMO_SYNC | PMO_NOSYNC | PMO_DEFAULT | 8192 | PMO_NOCONTEXT)

/* the clock's date and time (PutDate YYYYMMDD, PutTime HHMMSSTH): the run's pinned clock, taken as GMT (W8) */
static void put_clock(unsigned char *date, unsigned char *time) {
    const char *s = getenv("COB_CURRENT_DATE");
    int y, mo, d, hh, mi, ss, hs = 0;
    char b[24];
    if (!s || sscanf(s, "%d/%d/%d %d:%d:%d.%d", &y, &mo, &d, &hh, &mi, &ss, &hs) < 6)
        refuse("MQPUT", "a put with no pinned clock ($COB_CURRENT_DATE)");
    snprintf(b, sizeof b, "%04d%02d%02d", y, mo, d);
    memcpy(date, b, 8);
    snprintf(b, sizeof b, "%02d%02d%02d%02d", hh, mi, ss, hs);
    memcpy(time, b, 8);
}

/* the put both MQPUT and MQPUT1 make: rc, the message stored */
static int put(const char *call, int q, unsigned char *md, unsigned char *pmo, unsigned char *buflen,
               unsigned char *buffer) {
    char id[32];
    if (memcmp(md, "MD  ", 4) != 0 || be32(md + 4) != 1) refuse(call, "an MQMD other than version 1");
    if (memcmp(pmo, "PMO ", 4) != 0 || be32(pmo + 4) != 1) refuse(call, "an MQPMO other than version 1");
    int o = be32(pmo + 8), bl = be32(buflen);
    if (o & ~PMO_MODELLED) refuse(call, "an option other than SYNCPOINT, NO-SYNCPOINT, DEFAULT-CONTEXT, NO-CONTEXT, FAIL-IF-QUIESCING");
    if ((o & PMO_SYNC) && (o & PMO_NOSYNC)) return 2046;
    if ((o & PMO_DEFAULT) && (o & PMO_NOCONTEXT)) return 2046;
    if (bl < 0) return 2005;
    if (be32(md + 8) != 0) refuse(call, "Report options (MQRO_*)");
    int pri = be32(md + 40), per = be32(md + 44);
    if (pri < -1 || pri > 9) refuse(call, "a Priority outside -1..9 (MQRC_PRIORITY_ERROR)");
    if (per < 0 || per > 2) refuse(call, "a Persistence other than 0, 1, 2 (MQRC_PERSISTENCE_ERROR)");
    if (memcmp(md + 48, zero24, 24) == 0) { /* MQMI_NONE: the queue manager makes a unique MsgId (W4) */
        snprintf(id, sizeof id, "GGMQ%020ld", ++msgidc);
        memcpy(md + 48, id, 24);
    }
    if (o & PMO_NOCONTEXT) { /* IBM MQPMO_NO_CONTEXT: both kinds of context are blank */
        memset(md + 196, ' ', 12);
        memset(md + 208, 0, 32);
        memset(md + 240, ' ', 32);
        put32(md + 272, 0); /* MQAT_NO_CONTEXT */
        memset(md + 276, ' ', 28 + 8 + 8 + 4);
    } else { /* MQPMO_DEFAULT_CONTEXT (also when no context option is given) -- returned in the MQMD (W8) */
        memset(md + 196, ' ', 12);  /* UserIdentifier: the placeholder, W8 */
        memset(md + 208, 0, 32);    /* AccountingToken: the placeholder, W8 */
        memset(md + 240, ' ', 32);  /* ApplIdentityData: blank */
        put32(md + 272, 1);         /* PutApplType MQAT_CICS */
        memset(md + 276, ' ', 28);  /* PutApplName: the placeholder, W8 */
        put_clock(md + 304, md + 312);
        memset(md + 320, ' ', 4);   /* ApplOriginData: blank */
    }
    unsigned char stored[MDLEN];
    memcpy(stored, md, MDLEN);
    if (pri == -1) put32(stored + 40, qprio[q]);      /* MQPRI_PRIORITY_AS_Q_DEF */
    if (per == 2) put32(stored + 44, qpers[q]);       /* MQPER_PERSISTENCE_AS_Q_DEF */
    if (be32(md + 28) == 0) put32(stored + 28, qmgr_ccsid); /* MQCCSI_Q_MGR */
    put32(stored + 96, 0);                            /* BackoutCount */
    add_msg(q, stored, buffer, bl, (o & PMO_NOSYNC) ? AVAIL : PUT_PENDING); /* z/OS: in the unit of work by default */
    pad(pmo + 32, qnames[q], 48); /* ResolvedQName, ResolvedQMgrName */
    pad(pmo + 80, qmgr, 48);
    return 0;
}

static void put_event(const char *call, const char *queue, int r, const unsigned char *md, const unsigned char *buffer, int bl) {
    char extra[96], id[49];
    hex(md + 48, 24, id);
    snprintf(extra, sizeof extra, " msgid=%s", r ? "-" : id);
    ev(call, queue, comp(r), r, extra, buffer, r ? 0 : bl);
}

/* MQPUT (Hconn, Hobj, MsgDesc, PutMsgOpts, BufferLength, Buffer, CompCode, Reason) */
int MQPUT(unsigned char *hconn, unsigned char *hobj, unsigned char *md, unsigned char *pmo, unsigned char *buflen,
          unsigned char *buffer, unsigned char *cc, unsigned char *rc) {
    load("MQPUT");
    hconn_ok("MQPUT", hconn);
    int fr = planned("MQPUT");
    if (fr) {
        int fh = handle(hobj);
        done(cc, rc, fr);
        put_event("MQPUT", qname(fh >= 0 ? handles[fh].q : -1), fr, md, buffer, be32(buflen));
        return 0;
    }
    int h = handle(hobj), q = h >= 0 ? handles[h].q : -1, r;
    if (h < 0) r = 2019;                                   /* MQRC_HOBJ_ERROR */
    else if (!(handles[h].opts & OO_OUTPUT)) r = 2039;     /* MQRC_NOT_OPEN_FOR_OUTPUT */
    else r = put("MQPUT", q, md, pmo, buflen, buffer);
    done(cc, rc, r);
    put_event("MQPUT", qname(q), r, md, buffer, be32(buflen));
    return 0;
}

/* MQPUT1 (Hconn, ObjDesc, MsgDesc, PutMsgOpts, BufferLength, Buffer, CompCode, Reason): open, put, close */
int MQPUT1(unsigned char *hconn, unsigned char *od, unsigned char *md, unsigned char *pmo, unsigned char *buflen,
           unsigned char *buffer, unsigned char *cc, unsigned char *rc) {
    char name[49];
    load("MQPUT1");
    hconn_ok("MQPUT1", hconn);
    int fr = planned("MQPUT1");
    if (fr) {
        name48(od + 12, name);
        done(cc, rc, fr);
        put_event("MQPUT1", name, fr, md, buffer, be32(buflen));
        return 0;
    }
    int q = resolve_od("MQPUT1", od, name), r = q < 0 ? 2085 : put("MQPUT1", q, md, pmo, buflen, buffer);
    done(cc, rc, r);
    put_event("MQPUT1", name, r, md, buffer, be32(buflen));
    return 0;
}
