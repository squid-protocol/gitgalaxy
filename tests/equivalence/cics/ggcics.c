/*
 * #3754: the stub CICS runtime of the equivalence harness. A translated program
 * (tests/tools/equivalence_cics.py) CALLs these in place of each EXEC CICS
 * command; the harness driver CALLs GGCLOAD / GGCEND around the task.
 *
 * Inputs come from $GGCICS_DIR:
 *   commarea.in           the COMMAREA the task starts with (its length is EIBCALEN)
 *   receive_<MAP>.bin     what RECEIVE MAP(<MAP>) returns; absent means MAPFAIL
 *   terminal.in           what an unformatted terminal RECEIVE returns (#4005: the
 *                         step's text, typed on a cleared screen); absent means the
 *                         step transmitted no data
 *   retrieve_NNN.bin      the data of the START requests this task was started for, in
 *                         expiry order (#4006: what RETRIEVE returns; none: ENDDATA)
 *   requests.cfg          the unexpired interval-control requests: REQID EXPIRY (epoch
 *                         seconds, the virtual clock) per line (#4006: CANCEL's search)
 *   transactions.cfg      the transactions the CSD defines (START's TRANSIDERR)
 *   terminals.cfg         the region's terminals (START's TERMIDERR)
 * $GGCICS_NOW is the virtual time the task was dispatched at (YYYY-MM-DDTHH:MM:SS).
 * $GGCICS_TASKN is the task's number, EIBTASKN (#4270: GGCTASKN; unstated, 0).
 *   programs.cfg          the programs the CSD defines, one per line (#4004: a LINK to
 *                         any other is PGMIDERR); absent means every program is
 *                         defined
 * Temporary storage (#4002) lives in $GGCICS_TS (else $GGCICS_DIR/ts), shared by every
 * task of a scenario: one directory per queue, named by the queue name's hex, holding
 * its items as 000001.bin, 000002.bin, ... and `next`, the READQ NEXT position.
 *   files.cfg             one CICS file per line: NAME PATH RECLEN KEYOFF KEYLEN [NONE: RECOVERY(NONE)] --
 *                         generated from the engine's facts (CSD FILE -> DSNAME ->
 *                         IDCAMS KEYS, a PATH through its AIX)
 *   faults.cfg            #4023 follow-up: injected conditions, one per line: CMD FILE NTH
 *                         RESP [RESP2] -- the NTH (or `*`: every) CMD (READ, or INQUIRE with
 *                         the program's name as FILE) on FILE in
 *                         this task gets RESP / RESP2 (DFHRESP numbers) and does nothing
 *                         else; each one that fires is appended to $GGCICS_OUT/faults.txt
 *                         (`CMD FILE NTH RESP RESP2`). The Java side's CicsTask.read reads
 *                         the same plan. #4049: also XCTL (FILE: the program), WRITEQ-TS (the
 *                         queue), START (the TRANSID), RETRIEVE (FILE `-`) and CANCEL (the
 *                         REQID).
 * Outputs go to $GGCICS_OUT: events.txt, one line per command in order (`NNN VERB
 * pgm=<issuing program> key=value ...`), and NNN.bin, the bytes the command carried.
 *
 * #4004: a task is one process. The driver names its first program (GGCTASK) and CALLs
 * GGCRUN, the case's dispatcher (equivalence_cics.task_dispatcher): it runs the level's
 * program, then any program it XCTLs to. A LINK pushes a level and CALLs GGCRUN again with
 * the caller's own COMMAREA storage (by reference); GGCLRET pops it.
 *
 * Every entry point takes the GG-CICS block first (DFHEIBLK.cpy): the stub sets
 * GG-RESP / GG-RESP2 (the DFHRESP codes), the translator copied the names and
 * options into GG-NAME1 / GG-NAME2 / GG-FLAGS.
 */
#define _DEFAULT_SOURCE /* timegm, gmtime_r */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "ggcics_spec.h" /* #4270 spec PR 4: DFHRESP_* and condition_abcode, generated from gitgalaxy/standards/cics */
#ifdef _WIN32
#include <direct.h>
#define MKDIR(p) _mkdir(p) /* MinGW / MSVC: no mode argument */
/* nor timegm / gmtime_r: the C runtime's UTC equivalents */
#define timegm _mkgmtime
static struct tm *gg_gmtime_r(const time_t *when, struct tm *out) {
    struct tm *t = gmtime(when); /* one task, one thread: the shared buffer is copied out at once */
    if (!t) return NULL;
    *out = *t;
    return out;
}
#define gmtime_r gg_gmtime_r
#else
#define MKDIR(p) mkdir((p), 0777)
#endif

typedef struct {
    int resp;
    int resp2;
    char name1[8];
    char name2[8];
    char flags[40];
    int len; /* in-out: RECEIVE's / READQ's LENGTH (#4005) */
    char qname[16]; /* a TS queue's name (#4002) */
    int item;       /* in-out: ITEM (0 = NEXT) */
    int num;        /* out: NUMITEMS */
    int go_to;      /* out: the label index a condition / abend exit transfers to (#4003) */
    char chan[16];  /* #4270: a channel's name (in: CHANNEL; out: ASSIGN CHANNEL) */
    int hours, mins, secs;  /* #4270 slice 2: START AFTER / AT's HOURS, MINUTES, SECONDS (-1: not given) */
    char rtran[4], rterm[4], rqueue[8];  /* START / RETRIEVE RTRANSID, RTERMID, QUEUE (GG-FLAGS names which) */
} gg_cics;

/* the conditions the stub raises, by their short names; the numbers are the spec's (ggcics_spec.h) */
enum { NORMAL = DFHRESP_NORMAL, NOTFND = DFHRESP_NOTFND, LENGERR = DFHRESP_LENGERR, FILENOTFOUND = DFHRESP_FILENOTFOUND,
       MAPFAIL = DFHRESP_MAPFAIL, ITEMERR = DFHRESP_ITEMERR, QIDERR = DFHRESP_QIDERR, INVREQ = DFHRESP_INVREQ,
       PGMIDERR = DFHRESP_PGMIDERR, ENDDATA = DFHRESP_ENDDATA, DUPREC = DFHRESP_DUPREC, ENDFILE = DFHRESP_ENDFILE,
       CONTAINERERR = DFHRESP_CONTAINERERR, CHANNELERR = DFHRESP_CHANNELERR };

static int seq = 0;
static int ended = 0; /* a RETURN, XCTL or abend ended the task */

static void trim(const char *src, int len, char *dst) {
    while (len > 0 && (src[len - 1] == ' ' || src[len - 1] == '\0')) len--;
    memcpy(dst, src, len);
    dst[len] = '\0';
}

static const char *dir_in(void) { const char *d = getenv("GGCICS_DIR"); return d ? d : "."; }
static const char *dir_out(void) { const char *d = getenv("GGCICS_OUT"); return d ? d : "."; }

static const char *current_program(void);

/* One line of events.txt (the verb, then the issuing program); with `data`, its bytes as NNN.bin. */
static void event(const char *line, const char *data, int len) {
    char path[4096];
    const char *rest = strchr(line, ' ');
    int verb = rest ? (int)(rest - line) : (int)strlen(line);
    seq++;
    snprintf(path, sizeof path, "%s/events.txt", dir_out());
    FILE *f = fopen(path, "a");
    if (f) {
        fprintf(f, "%03d %.*s pgm=%s%s\n", seq, verb, line, current_program(), rest ? rest : "");
        fclose(f);
    }
    if (data && len > 0) {
        snprintf(path, sizeof path, "%s/%03d.bin", dir_out(), seq);
        f = fopen(path, "wb");
        if (f) { fwrite(data, 1, (size_t)len, f); fclose(f); }
    }
}

/* ---- the task's inputs ------------------------------------------------------------ */
int GGCLOAD(char *area, int maxlen) {
    char path[4096];
    snprintf(path, sizeof path, "%s/commarea.in", dir_in());
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    int n = (int)fread(area, 1, (size_t)maxlen, f);
    fclose(f);
    return n;
}

/* #4023 follow-up: the planned condition of this command on this file, if faults.cfg plans one. Every
 * command counts (per task: a task is one process), whether or not it faults. */
static int fault_counts[32];
static char fault_keys[32][40];
static int injected(const char *cmd, const char *file, int *resp, int *resp2) {
    char path[3000], line[256], pcmd[16], pfile[32], nth[16];
    int presp, presp2, n = 0, slot = -1, hit = 0;
    char key[40];
    snprintf(key, sizeof key, "%.15s %.16s", cmd, file);
    for (int i = 0; i < 32; i++) {
        if (fault_keys[i][0] == 0 || strcmp(fault_keys[i], key) == 0) { slot = i; break; }
    }
    if (slot < 0) return 0;
    if (fault_keys[slot][0] == 0) snprintf(fault_keys[slot], sizeof fault_keys[slot], "%s", key);
    n = ++fault_counts[slot];
    snprintf(path, sizeof path, "%s/faults.cfg", dir_in());
    FILE *f = fopen(path, "r");
    while (f && !hit && fgets(line, sizeof line, f)) {
        presp2 = 0;
        if (sscanf(line, "%15s %31s %15s %d %d", pcmd, pfile, nth, &presp, &presp2) < 4) continue;
        if (strcmp(pcmd, cmd) != 0 || strcmp(pfile, file) != 0) continue;
        if (nth[0] != '*' && atoi(nth) != n) continue;
        *resp = presp;
        *resp2 = presp2;
        hit = 1;
    }
    if (f) fclose(f);
    if (hit) {
        snprintf(path, sizeof path, "%s/faults.txt", dir_out());
        FILE *log = fopen(path, "a");
        if (log) { fprintf(log, "%s %s %d %d %d\n", cmd, file, n, *resp, *resp2); fclose(log); }
    }
    return hit;
}

/* ---- file updates (CardDemo's update programs) --------------------------------------------------------------
 * READ ... UPDATE holds the record it read (per file, until a REWRITE, another READ UPDATE or a SYNCPOINT);
 * REWRITE replaces the held record -- INVREQ without one, as CICS raises it; WRITE adds a record, DUPREC when its
 * key is already there. Each scenario has its own copy of the files, so what a task leaves is its own (and is
 * compared). A unit of work: the first change to a file since the last SYNCPOINT saves the file aside;
 * SYNCPOINT drops the copies (commit), SYNCPOINT ROLLBACK puts them back. */
#define MAX_FILES 16
static struct { char name[9]; char key[256]; int klen; } held[MAX_FILES];
static char uow_saved[MAX_FILES][3000];

static void hold(const char *file, const char *key, int klen) {
    for (int i = 0; i < MAX_FILES; i++) {
        if (held[i].name[0] == 0 || strcmp(held[i].name, file) == 0) {
            snprintf(held[i].name, sizeof held[i].name, "%s", file);
            memcpy(held[i].key, key, (size_t)(klen < 256 ? klen : 256));
            held[i].klen = klen < 256 ? klen : 256;
            return;
        }
    }
}

static int held_key(const char *file, const char *key, int klen) {
    for (int i = 0; i < MAX_FILES; i++) {
        if (held[i].name[0] && strcmp(held[i].name, file) == 0) {
            return held[i].klen == (klen < 256 ? klen : 256) && memcmp(held[i].key, key, (size_t)held[i].klen) == 0;
        }
    }
    return 0;
}

static void release(const char *file) {
    for (int i = 0; i < MAX_FILES; i++) {
        if (held[i].name[0] && (!file || strcmp(held[i].name, file) == 0)) held[i].name[0] = 0;
    }
}

static void copy_file(const char *from, const char *to) {
    FILE *a = fopen(from, "rb"), *b = fopen(to, "wb");
    char buf[8192];
    size_t n;
    while (a && b && (n = fread(buf, 1, sizeof buf, a)) > 0) fwrite(buf, 1, n, b);
    if (a) fclose(a);
    if (b) fclose(b);
}

/* files.cfg's sixth column: the file's flags, comma-separated -- NONE (the CSD defines it RECOVERY(NONE)) and ESDS
 * (an entry-sequenced data set: no key; each record is found by its relative byte address, #4213). */
static int flag_in(const char *flags, const char *flag) {
    size_t n = strlen(flag);
    for (const char *p = flags; (p = strstr(p, flag)) != NULL; p += n) {
        if ((p == flags || p[-1] == ',') && (p[n] == '\0' || p[n] == ',')) return 1;
    }
    return 0;
}

/* Whether the CSD defines the file at `path` RECOVERY(NONE) (files.cfg's sixth column): its changes are not backed out. */
static int non_recoverable(const char *path) {
    char line[4096], name[64], p[3000], rec[16];
    int a, b, c, none = 0;
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    while (cfg && !none && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%63s %2999s %d %d %d %15s", name, p, &a, &b, &c, rec) == 6 && strcmp(p, path) == 0)
            none = flag_in(rec, "NONE");
    }
    if (cfg) fclose(cfg);
    return none;
}

static void uow_save(const char *path) {
    char aside[3100];
    if (non_recoverable(path)) return;  /* CICS backs out recoverable files only */
    for (int i = 0; i < MAX_FILES; i++) {
        if (strcmp(uow_saved[i], path) == 0) return;
        if (uow_saved[i][0] == 0) {
            snprintf(uow_saved[i], sizeof uow_saved[i], "%s", path);
            snprintf(aside, sizeof aside, "%s.uow", path);
            copy_file(path, aside);
            return;
        }
    }
}

/* The file's files.cfg entry: its data path, record length, key offset and length; 0 when not defined. */
static int file_cfg(const char *want, char *path, int *reclen, int *keyoff, int *klen) {
    char line[4096], name[64];
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    int found = 0;
    while (cfg && !found && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%63s %2999s %d %d %d", name, path, reclen, keyoff, klen) == 5 && strcmp(name, want) == 0) {
            found = 1;
        }
    }
    if (cfg) fclose(cfg);
    return found;
}

/* Whether files.cfg defines the file `want` as an ESDS (#4213). */
static int is_esds(const char *want) {
    char line[4096], name[64], p[3000], flags[64];
    int a, b, c, esds = 0;
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    while (cfg && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%63s %2999s %d %d %d %63s", name, p, &a, &b, &c, flags) == 6 && strcmp(name, want) == 0) {
            esds = flag_in(flags, "ESDS");
            break;
        }
    }
    if (cfg) fclose(cfg);
    return esds;
}

/* What IBM does not document, or this model does not cover, stops the run: 98 and "<what>: not modelled"
 * (oracle_assumptions.md X5, X13), which the harness reports as a refusal by name -- never a guess. */
static void refuse(const char *what) {
    printf("%s: not modelled\n", what);
    fflush(stdout);
    exit(98);
}

/* A keyed command on an ESDS (#4213): an ESDS has no key; only its browse by RBA is modelled. */
static void keyed_on_esds(const char *verb, const char *want) {
    char why[120];
    if (!is_esds(want)) return;
    snprintf(why, sizeof why, "%s by key on %s, an ESDS", verb, want);
    refuse(why);
}

/* The record number (0-based) whose key is `key`, or -1. */
static long find_key(const char *path, int reclen, int keyoff, int klen, const char *key) {
    FILE *data = fopen(path, "rb");
    char *rec = malloc((size_t)reclen);
    long at = -1, i = 0;
    while (data && rec && fread(rec, 1, (size_t)reclen, data) == (size_t)reclen) {
        if (memcmp(rec + keyoff, key, (size_t)klen) == 0) { at = i; break; }
        i++;
    }
    if (data) fclose(data);
    free(rec);
    return at;
}

static void file_event(const char *verb, const char *file, const char *key, int klen, int resp) {
    char ev[400], k[201];
    int shown = klen < 200 ? klen : 200;
    memcpy(k, key, (size_t)shown);
    k[shown] = '\0';
    snprintf(ev, sizeof ev, "%s file=%s key=%s resp=%d", verb, file, k, resp);
    event(ev, NULL, 0);
}

/* WRITE FILE(name1) RIDFLD FROM: a new record; DUPREC when its key is there already. */
int GGCWRIT(gg_cics *c, char *ridfld, int keylen, char *from, int fromlen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (injected("WRITE", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event("WRITE", want, ridfld, keylen, c->resp);
        return 0;
    }
    keyed_on_esds("WRITE", want);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
    } else if (find_key(path, reclen, keyoff, klen < keylen ? klen : keylen, ridfld) >= 0) {
        c->resp = DUPREC;
    } else {
        uow_save(path);
        char *rec = malloc((size_t)reclen);
        memset(rec, ' ', (size_t)reclen);
        memcpy(rec, from, (size_t)(fromlen < reclen ? fromlen : reclen));
        FILE *data = fopen(path, "ab");
        if (data && rec) fwrite(rec, 1, (size_t)reclen, data);
        if (data) fclose(data);
        free(rec);
        c->resp = NORMAL;
    }
    file_event("WRITE", want, ridfld, keylen, c->resp);
    return 0;
}

/* REWRITE FILE(name1) FROM: replaces the record a READ UPDATE holds; INVREQ when none is held. */
int GGCREWR(gg_cics *c, char *from, int fromlen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int have = file_cfg(want, path, &reclen, &keyoff, &klen);
    const char *key = have ? from + keyoff : from;
    if (injected("REWRITE", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event("REWRITE", want, key, have ? klen : 0, c->resp);
        return 0;
    }
    if (!have) {
        c->resp = FILENOTFOUND;
    } else if (!held_key(want, key, klen)) {
        c->resp = INVREQ;
    } else {
        long at = find_key(path, reclen, keyoff, klen, key);
        if (at < 0) {
            c->resp = NOTFND;
        } else {
            uow_save(path);
            char *rec = malloc((size_t)reclen);
            memset(rec, ' ', (size_t)reclen);
            memcpy(rec, from, (size_t)(fromlen < reclen ? fromlen : reclen));
            FILE *data = fopen(path, "r+b");
            if (data && rec && fseek(data, at * (long)reclen, SEEK_SET) == 0) fwrite(rec, 1, (size_t)reclen, data);
            if (data) fclose(data);
            free(rec);
            release(want);
            c->resp = NORMAL;
        }
    }
    file_event("REWRITE", want, key, have ? klen : 0, c->resp);
    return 0;
}

/* A Db2 case's SQL stub (tests/equivalence/db2/ggsql.c), when linked: its Db2 work belongs to the same unit of work.
 * A weak no-op DEFINITION, which ggsql.c's strong one overrides at link time. (A weak undefined REFERENCE checked
 * against NULL links on ELF but not on macOS, whose linker still requires it to resolve.) */
__attribute__((weak)) void ggsql_uow_end(int rollback) { (void)rollback; }

/* The unit of work ends: committed (the saved copies dropped) or backed out (put back). */
static void uow_end(int rollback) {
    ggsql_uow_end(rollback);
    char aside[3100];
    for (int i = 0; i < MAX_FILES; i++) {
        if (!uow_saved[i][0]) continue;
        snprintf(aside, sizeof aside, "%s.uow", uow_saved[i]);
        if (rollback) copy_file(aside, uow_saved[i]);
        remove(aside);
        uow_saved[i][0] = 0;
    }
    release(NULL);
}

/* SYNCPOINT (flags empty: commit) / SYNCPOINT ROLLBACK (flags ROLLBACK: undo since the last SYNCPOINT). */
int GGCSYNC(gg_cics *c) {
    int rollback = strstr(c->flags, "ROLLBACK") != NULL;
    uow_end(rollback);
    c->resp = NORMAL;
    c->resp2 = 0;
    event(rollback ? "SYNCPOINT-ROLLBACK" : "SYNCPOINT", NULL, 0);
    return 0;
}

/* READ FILE(name1) RIDFLD INTO LENGTH(c->len): the first record whose key equals RIDFLD (IBM, EXEC CICS READ).
 * #4436: LENGTH is in-out -- in, the most the program takes (LENGTH OF INTO when the program gives none); the record
 * goes INTO, truncated to it with LENGERR (RESP2 11) when longer; out, the record's length (NORMAL and LENGERR).
 * Stops as not modelled: a negative LENGTH; a record moved past INTO (intolen: the storage after INTO, which GnuCOBOL
 * lays out unlike IBM's compiler, oracle_assumptions.md X6); LENGERR on READ UPDATE (IBM does not say whether the
 * record is then held). */
int GGCREAD(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    char want[9], line[4096], name[64], path[3000], ev[320];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp = FILENOTFOUND;
    c->resp2 = 0;
    if (injected("READ", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        char key[256];
        int shown = keylen < 200 ? keylen : 200;
        memcpy(key, ridfld, (size_t)shown);
        key[shown] = '\0';
        snprintf(ev, sizeof ev, "READ file=%s key=%s resp=%d", want, key, c->resp);
        event(ev, NULL, 0);
        return 0;
    }
    keyed_on_esds("READ", want);
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    if (cfg) {
        while (fgets(line, sizeof line, cfg)) {
            if (sscanf(line, "%63s %2999s %d %d %d", name, path, &reclen, &keyoff, &klen) != 5) continue;
            if (strcmp(name, want) != 0) continue;
            c->resp = NOTFND;
            FILE *data = fopen(path, "rb");
            char *rec = malloc((size_t)reclen);
            int cmp = keylen < klen ? keylen : klen;
            while (data && rec && fread(rec, 1, (size_t)reclen, data) == (size_t)reclen) {
                if (memcmp(rec + keyoff, ridfld, (size_t)cmp) == 0) {
                    int max = c->len, moved = reclen < max ? reclen : max;
                    if (max < 0) refuse("READ LENGTH (negative)");
                    if (moved > intolen) refuse("READ INTO LENGTH: a record moved past INTO");
                    if (reclen > max && strstr(c->flags, "UPDATE"))
                        refuse("READ UPDATE LENGERR (whether the record is held)");
                    memcpy(into, rec, (size_t)moved);
                    c->resp = reclen > max ? LENGERR : NORMAL;
                    c->resp2 = reclen > max ? 11 : 0;
                    c->len = reclen;
                    if (c->resp == NORMAL && strstr(c->flags, "UPDATE")) hold(want, rec + keyoff, klen);
                    break;
                }
            }
            if (data) fclose(data);
            free(rec);
            break;
        }
        fclose(cfg);
    }
    char key[256];
    int shown = keylen < 200 ? keylen : 200;
    memcpy(key, ridfld, (size_t)shown);
    key[shown] = '\0';
    snprintf(ev, sizeof ev, "READ file=%s key=%s resp=%d", want, key, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* ---- browse: STARTBR / READNEXT / READPREV / ENDBR (IBM CICS TS, EXEC CICS STARTBR ... ENDBR) ----------------
 * One browse per file (no REQID). Positions are found again from the keys on every command, so a record written
 * during the browse is seen. IBM's rules modelled:
 *   STARTBR    GTEQ (the default): the first key >= RIDFLD; EQUAL: that key only; NOTFND when none. A RIDFLD of
 *              all X'FF' positions at the end for a backwards browse. A second STARTBR on the file: INVREQ (33).
 *   READNEXT   the record STARTBR positioned on, then each next; RIDFLD is set to the key read. A RIDFLD the
 *              program changed, or a READNEXT after a READPREV, repositions: the first key >= RIDFLD (GTEQ).
 *              ENDFILE past the last record.
 *   READPREV   right after STARTBR the STARTBR key must exist (else NOTFND); after a READNEXT, or with RIDFLD
 *              changed, it repositions to RIDFLD and reads that record (so it reads again the record READNEXT
 *              just read) -- NOTFND when that key is not there, as documented for the STARTBR case; after an
 *              X'FF' STARTBR it reads the last record. ENDFILE before the first.
 *   ENDBR      INVREQ (35) when no browse is active.  */
static struct {
    char name[9];
    int active, equal, last, dir, have_last, rba;
    char start[256], lastkey[256];
    unsigned long rstart, rlast;  /* an RBA browse (#4213): the STARTBR's RBA, the last RBA read */
} br[MAX_FILES];

static int browse_slot(const char *file, int create) {
    for (int i = 0; i < MAX_FILES; i++) if (br[i].name[0] && strcmp(br[i].name, file) == 0) return i;
    if (!create) return -1;
    for (int i = 0; i < MAX_FILES; i++) {
        if (!br[i].name[0]) { memset(&br[i], 0, sizeof br[i]); snprintf(br[i].name, sizeof br[i].name, "%s", file); return i; }
    }
    return -1;
}

static int all_ff(const char *key, int len) {
    for (int i = 0; i < len; i++) if ((unsigned char)key[i] != 0xFF) return 0;
    return len > 0;
}

/* The file's records; `*n` of them, each `reclen` bytes (the caller frees). */
static char *load_records(const char *path, int reclen, long *n) {
    FILE *data = fopen(path, "rb");
    char *all = NULL;
    *n = 0;
    if (!data) return NULL;
    fseek(data, 0, SEEK_END);
    long size = ftell(data);
    fseek(data, 0, SEEK_SET);
    all = malloc((size_t)(size > 0 ? size : 1));
    if (all) *n = (long)fread(all, 1, (size_t)size, data) / reclen;
    fclose(data);
    return all;
}

/* The record whose key is the least key > `key` (strict), >= (or_equal), or the greatest < `key` (below); -1 when
 * none. With `exact`, only a record whose key equals `key`. */
static long pick(const char *all, long n, int reclen, int keyoff, int klen, const char *key, int mode) {
    long best = -1;
    for (long i = 0; i < n; i++) {
        int c = memcmp(all + i * reclen + keyoff, key, (size_t)klen);
        const char *bk = best >= 0 ? all + best * reclen + keyoff : NULL;
        if (mode == 0 && c == 0) return i;                                                      /* exact */
        if (mode == 1 && c >= 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) < 0)) best = i;  /* >= */
        if (mode == 2 && c > 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) < 0)) best = i;   /* > */
        if (mode == 3 && c < 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) > 0)) best = i;   /* < */
    }
    return best;
}

static long pick_last(const char *all, long n, int reclen, int keyoff, int klen) {
    long best = -1;
    for (long i = 0; i < n; i++) {
        if (best < 0 || memcmp(all + i * reclen + keyoff, all + best * reclen + keyoff, (size_t)klen) > 0) best = i;
    }
    return best;
}

/* ---- #4213: an ESDS browsed by relative byte address (STARTBR / READNEXT / READPREV ... RBA) ----------------------
 * IBM CICS TS, EXEC CICS STARTBR / READNEXT / READPREV, option RBA: "the record identification field specified in the
 * RIDFLD option contains a relative byte address"; "if you specify the RBA option, it applies to every READNEXT or
 * READPREV command in the browse, and causes CICS to return the relative byte address of each retrieved record".
 * EQUAL "is the default for a direct ESDS browse"; GTEQ "is not valid for directly browsing an ESDS" (refused by the
 * translator). "To position the browse at the last record in the file, ready for a backward browse, specify a RIDFLD
 * of X'FF' characters ... For a standard ESDS, specify the RBA option" (Sequential reading (browsing)); "when you set
 * RIDFLD to reposition a browse, the record identifier must be in the same form as on the previous STARTBR" (ibid.).
 * Modelled: an ESDS of fixed-length records in arrival order, a record's RBA its byte offset (oracle_assumptions.md
 * X13); RIDFLD a fullword, big-endian. The browse moves as the keyed one above does, in RBA order. Refused by name: an
 * RBA that addresses no record (IBM does not say whether VSAM answers NOTFND, INVREQ or ILLOGIC), RBA on a file that
 * is not an ESDS (a KSDS by RBA), a keyed browse of an ESDS, and a browse that mixes RBA and key commands. */
static unsigned long rba_get(const char *rid) {
    const unsigned char *u = (const unsigned char *)rid;
    return ((unsigned long)u[0] << 24) | ((unsigned long)u[1] << 16) | ((unsigned long)u[2] << 8) | u[3];
}

static void rba_put(char *rid, unsigned long v) {
    rid[0] = (char)((v >> 24) & 0xFF);
    rid[1] = (char)((v >> 16) & 0xFF);
    rid[2] = (char)((v >> 8) & 0xFF);
    rid[3] = (char)(v & 0xFF);
}

#define RBA_END 0xFFFFFFFFUL

/* The record (0-based) at `rba`; refused when no record starts there. */
static long rba_record(const char *verb, const char *want, unsigned long rba, int reclen, long n) {
    char why[120];
    if (rba % (unsigned long)reclen == 0 && rba / (unsigned long)reclen < (unsigned long)n) {
        return (long)(rba / (unsigned long)reclen);
    }
    snprintf(why, sizeof why, "%s RBA %lu on %s: no record starts there", verb, rba, want);
    refuse(why);
    return -1;
}

static void rba_event(const char *verb, const char *file, unsigned long rba, int resp) {
    char ev[120];
    snprintf(ev, sizeof ev, "%s file=%s rba=%lu resp=%d", verb, file, rba, resp);
    event(ev, NULL, 0);
}

/* STARTBR ... RBA: GG-FLAGS 'EQUAL RBA'. */
static int rba_startbr(gg_cics *c, const char *want, const char *path, int reclen, char *ridfld, int keylen) {
    char why[120];
    if (!is_esds(want)) {
        snprintf(why, sizeof why, "STARTBR RBA on %s, not an ESDS", want);
        refuse(why);
    }
    if (keylen < 4) refuse("an RBA RIDFLD shorter than a fullword");
    int s = browse_slot(want, 1);
    unsigned long rba = rba_get(ridfld);
    if (s >= 0 && br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 33;
    } else {
        long n;
        char *all = load_records(path, reclen, &n);
        free(all);
        if (rba != RBA_END) rba_record("STARTBR", want, rba, reclen, n);
        br[s].active = 1;
        br[s].dir = 0;
        br[s].have_last = 0;
        br[s].equal = 1;
        br[s].rba = 1;
        br[s].last = rba == RBA_END;
        br[s].rstart = rba;
        c->resp = NORMAL;
    }
    rba_event("STARTBR", want, rba, c->resp);
    return 0;
}

/* READNEXT (dir 1) / READPREV (dir -1) ... RBA: GG-FLAGS 'RBA'; the browse is an RBA browse. */
static int rba_read(gg_cics *c, int dir, const char *want, const char *path, int reclen, int s, char *ridfld,
                    int keylen, char *into, int intolen) {
    const char *verb = dir > 0 ? "READNEXT" : "READPREV";
    if (keylen < 4) refuse("an RBA RIDFLD shorter than a fullword");
    unsigned long rba = rba_get(ridfld), was = br[s].have_last ? br[s].rlast : br[s].rstart;
    int changed = rba != was;
    long n, at;
    char *all = load_records(path, reclen, &n);
    if (dir > 0) {
        if (br[s].dir == 0 && !br[s].last && !changed) at = rba_record(verb, want, rba, reclen, n);
        else if (br[s].dir == 1 && !changed) at = (long)(rba / (unsigned long)reclen) + 1;
        else if (rba == RBA_END) at = -1;
        else at = rba_record(verb, want, rba, reclen, n);
        if (at >= n) at = -1;
        c->resp = at < 0 ? ENDFILE : NORMAL;
        if (at < 0) c->resp2 = 90;
    } else {
        if (rba == RBA_END && (br[s].dir == 0 || changed)) at = n - 1;
        else if (br[s].dir == -1 && !changed) at = (long)(rba / (unsigned long)reclen) - 1;
        else at = rba_record(verb, want, rba, reclen, n);
        c->resp = at < 0 ? ENDFILE : NORMAL;
        if (at < 0) c->resp2 = 90;
    }
    if (at >= 0) {
        const char *rec = all + at * reclen;
        memcpy(into, rec, (size_t)(reclen < intolen ? reclen : intolen));
        rba = (unsigned long)at * (unsigned long)reclen;
        rba_put(ridfld, rba);
        br[s].rlast = rba;
        br[s].have_last = 1;
        br[s].dir = dir;
        if (reclen > intolen) { c->resp = LENGERR; c->resp2 = 11; }
    }
    free(all);
    rba_event(verb, want, rba, c->resp);
    return 0;
}

/* STARTBR FILE(name1) RIDFLD [GTEQ | EQUAL: GG-FLAGS 'EQUAL'] [RBA: GG-FLAGS 'RBA', #4213]. */
int GGCSTBR(gg_cics *c, char *ridfld, int keylen) {
    char want[9], path[3000], key[256];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (injected("STARTBR", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event("STARTBR", want, ridfld, keylen, c->resp);
        return 0;
    }
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        file_event("STARTBR", want, ridfld, keylen, c->resp);
        return 0;
    }
    if (strstr(c->flags, "RBA")) return rba_startbr(c, want, path, reclen, ridfld, keylen);
    keyed_on_esds("STARTBR", want);
    int s = browse_slot(want, 1);
    if (s >= 0 && br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 33;
    } else {
        int len = keylen < klen ? keylen : klen;
        memset(key, 0, sizeof key);
        memcpy(key, ridfld, (size_t)len);
        int equal = strstr(c->flags, "EQUAL") != NULL, last = all_ff(key, len);
        long n;
        char *all = load_records(path, reclen, &n);
        long at = last ? 0 : pick(all, n, reclen, keyoff, klen, key, equal ? 0 : 1);
        free(all);
        if (at < 0) {
            c->resp = NOTFND;
            c->resp2 = 80;
        } else {
            br[s].active = 1;
            br[s].rba = 0;
            br[s].equal = equal;
            br[s].last = last;
            br[s].dir = 0;
            br[s].have_last = 0;
            memcpy(br[s].start, key, sizeof key);
            c->resp = NORMAL;
        }
    }
    file_event("STARTBR", want, ridfld, keylen, c->resp);
    return 0;
}

/* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
static int browse_read(gg_cics *c, int dir, char *ridfld, int keylen, char *into, int intolen) {
    const char *verb = dir > 0 ? "READNEXT" : "READPREV";
    char want[9], path[3000], key[256];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (injected(verb, want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event(verb, want, ridfld, keylen, c->resp);
        return 0;
    }
    int s = browse_slot(want, 0);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
    } else if (s < 0 || !br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 34;
    } else if (br[s].rba != (strstr(c->flags, "RBA") != NULL)) {  /* IBM: the same form as the STARTBR's */
        char why[120];
        snprintf(why, sizeof why, "%s by %s in %s browse of %s", verb, br[s].rba ? "key" : "RBA",
                 br[s].rba ? "an RBA" : "a keyed", want);
        refuse(why);
    } else if (br[s].rba) {
        return rba_read(c, dir, want, path, reclen, s, ridfld, keylen, into, intolen);
    } else {
        int len = keylen < klen ? keylen : klen;
        memset(key, 0, sizeof key);
        memcpy(key, ridfld, (size_t)len);
        const char *was = br[s].have_last ? br[s].lastkey : br[s].start;
        int changed = memcmp(key, was, (size_t)klen) != 0;
        long n, at;
        char *all = load_records(path, reclen, &n);
        if (dir > 0) {
            if (br[s].dir == 0 && !br[s].last && !changed) at = pick(all, n, reclen, keyoff, klen, key, br[s].equal ? 0 : 1);
            else if (br[s].dir == 1 && !changed) at = pick(all, n, reclen, keyoff, klen, key, 2);
            else at = all_ff(key, klen) ? -1 : pick(all, n, reclen, keyoff, klen, key, br[s].equal ? 0 : 1);
            c->resp = at < 0 ? ENDFILE : NORMAL;
            if (at < 0) c->resp2 = 90;
        } else {
            if (all_ff(key, klen) && (br[s].dir == 0 || changed)) at = pick_last(all, n, reclen, keyoff, klen);
            else if (br[s].dir == -1 && !changed) at = pick(all, n, reclen, keyoff, klen, key, 3);
            else at = pick(all, n, reclen, keyoff, klen, key, 0);
            if (at >= 0) c->resp = NORMAL;
            else if (br[s].dir == -1 && !changed) { c->resp = ENDFILE; c->resp2 = 90; }
            else if (all_ff(key, klen)) { c->resp = ENDFILE; c->resp2 = 90; }
            else { c->resp = NOTFND; c->resp2 = 80; }
        }
        if (at >= 0) {
            const char *rec = all + at * reclen;
            memcpy(into, rec, (size_t)(reclen < intolen ? reclen : intolen));
            memcpy(ridfld, rec + keyoff, (size_t)len);
            memset(br[s].lastkey, 0, sizeof br[s].lastkey);
            memcpy(br[s].lastkey, rec + keyoff, (size_t)klen);
            br[s].have_last = 1;
            br[s].dir = dir;
            if (reclen > intolen) { c->resp = LENGERR; c->resp2 = 11; }
        }
        free(all);
    }
    file_event(verb, want, ridfld, keylen, c->resp);
    return 0;
}

int GGCRDNX(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    return browse_read(c, 1, ridfld, keylen, into, intolen);
}

int GGCRDPV(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    return browse_read(c, -1, ridfld, keylen, into, intolen);
}

/* ENDBR FILE(name1). */
int GGCENBR(gg_cics *c) {
    char want[9], ev[100];
    int fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int s = browse_slot(want, 0);
    if (injected("ENDBR", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (s < 0 || !br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 35;
    } else {
        br[s].active = 0;
        c->resp = NORMAL;
    }
    snprintf(ev, sizeof ev, "ENDBR file=%s resp=%d", want, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a READ UPDATE
 * holds -- INVREQ when none is held; NOTFND when the key is not there. */
int GGCDELT(gg_cics *c, char *ridfld, int keylen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int by_hold = strstr(c->flags, "HELD") != NULL;
    if (injected("DELETE", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event("DELETE", want, ridfld, by_hold ? 0 : keylen, c->resp);
        return 0;
    }
    keyed_on_esds("DELETE", want);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        file_event("DELETE", want, ridfld, by_hold ? 0 : keylen, c->resp);
        return 0;
    }
    char key[256];
    memset(key, 0, sizeof key);
    int s = -1;
    if (by_hold) {
        for (int i = 0; i < MAX_FILES; i++) if (held[i].name[0] && strcmp(held[i].name, want) == 0) { s = i; break; }
        if (s >= 0) memcpy(key, held[s].key, (size_t)held[s].klen);
    } else {
        memcpy(key, ridfld, (size_t)(keylen < klen ? keylen : klen));
    }
    long n;
    char *all = load_records(path, reclen, &n);
    long at = (by_hold && s < 0) ? -1 : pick(all, n, reclen, keyoff, keylen < klen && !by_hold ? keylen : klen, key, 0);
    if (by_hold && s < 0) {
        c->resp = INVREQ;
    } else if (at < 0) {
        c->resp = NOTFND;
        c->resp2 = 80;
    } else {
        uow_save(path);
        FILE *data = fopen(path, "wb");
        for (long i = 0; data && i < n; i++) if (i != at) fwrite(all + i * reclen, 1, (size_t)reclen, data);
        if (data) fclose(data);
        if (by_hold) release(want);
        c->resp = NORMAL;
    }
    free(all);
    file_event("DELETE", want, key, klen, c->resp);
    return 0;
}

/* RECEIVE MAP(name1) MAPSET(name2) INTO: the scenario's recorded map input. */
int GGCRECV(gg_cics *c, char *into, int intolen) {
    char map[9], mapset[9], path[4096], ev[128];
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    snprintf(path, sizeof path, "%s/receive_%s.bin", dir_in(), map);
    FILE *f = fopen(path, "rb");
    c->resp = MAPFAIL;
    c->resp2 = 0;
    if (f) {
        size_t n = fread(into, 1, (size_t)intolen, f);
        fclose(f);
        c->resp = n > 0 ? NORMAL : MAPFAIL;
    }
    snprintf(ev, sizeof ev, "RECEIVE-MAP map=%s mapset=%s resp=%d", map, mapset, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* RECEIVE INTO LENGTH (#4005): the terminal's input, unformatted. c->len is the most INTO
 * takes (MAXLENGTH, else LENGTH, else INTO's length; below zero, zero); on return it is the
 * LENGTH CICS sets. Longer data: under NOTRUNCATE (GG-FLAGS, #4413) the first c->len bytes,
 * NORMAL, LENGTH the length returned, and the rest kept for the next RECEIVE of the task;
 * else truncated, LENGERR, LENGTH the original length (IBM, EXEC CICS RECEIVE (3270
 * logical): "the data is truncated ... the data area specified in the LENGTH option is set
 * to the original length of data"). On an LUTYPE2 terminal (GGCICS_LU2=1: the case CSD's
 * TYPETERM DEVICE(LUTYPE2)) the RECEIVE returning the input's last byte raises EOC (RECEIVE
 * (LUTYPE2/LUTYPE3)); one leaving data retained there is undocumented and refused. The
 * operator's input is read once per task: a RECEIVE with nothing retained would wait for the
 * operator, which a scenario step cannot express, so it is recorded as RECEIVE-WAIT for the
 * driver to refuse. */
static int terminal_read = 0;
static char terminal_buf[32768];
static int terminal_at = 0, terminal_n = 0; /* the input not yet returned: terminal_buf[at..n) */
static char set_buf[32768];                  /* RECEIVE SET's data, valid until the next RECEIVE */

enum { EOC = DFHRESP_EOC };

static int terminal_receive(gg_cics *c, char *into) {
    char path[4096], ev[96], flags[41];
    int max = c->len < 0 ? 0 : c->len, notruncate, lu2 = getenv("GGCICS_LU2") != NULL;
    trim(c->flags, 40, flags);
    notruncate = strstr(flags, "NOTRUNCATE") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (terminal_at >= terminal_n && terminal_read) {
        c->len = 0;
        event("RECEIVE-WAIT", NULL, 0);
        return -1;
    }
    if (!terminal_read) {
        FILE *f;
        terminal_read = 1;
        snprintf(path, sizeof path, "%s/terminal.in", dir_in());
        f = fopen(path, "rb");
        if (f) {
            terminal_n = (int)fread(terminal_buf, 1, sizeof terminal_buf, f);
            fclose(f);
        }
        terminal_at = 0;
    }
    int n = terminal_n - terminal_at;
    int copied = n < max ? n : max;
    memcpy(into, terminal_buf + terminal_at, (size_t)copied);
    if (n > max && notruncate) {
        if (lu2) {
            c->len = 0;
            event("RECEIVE-REFUSED", NULL, 0); /* EOC on a partial RECEIVE is not documented */
            return -1;
        }
        terminal_at += copied;
        c->len = copied;
    } else {
        if (n > max) c->resp = LENGERR;
        else if (lu2) c->resp = EOC;
        terminal_at = terminal_n;
        c->len = n;
    }
    snprintf(ev, sizeof ev, "RECEIVE resp=%d len=%d copied=%d", c->resp, c->len, copied);
    event(ev, into, copied);
    return copied;
}

int GGCRECT(gg_cics *c, char *into) {
    terminal_receive(c, into);
    return 0;
}

/* RECEIVE SET(ADDRESS OF record) (#4413): the data in a buffer of the stub's, its address
 * into *ptr for the program's SET ADDRESS OF; the bytes past the data are X'00'. */
int GGCRECS(gg_cics *c, void **ptr) {
    memset(set_buf, 0, sizeof set_buf);
    terminal_receive(c, set_buf);
    *ptr = set_buf;
    return 0;
}

/* ---- temporary storage (#4002) ------------------------------------------------------ */
/* The queue's directory; `hex` gets the name (trailing blanks and nulls dropped) in hex. */
static void ts_dir(const gg_cics *c, char *dir, size_t size, char *hex) {
    const char *root = getenv("GGCICS_TS");
    char name[17];
    trim(c->qname, 16, name);
    hex[0] = '\0';
    for (int i = 0; name[i]; i++) sprintf(hex + 2 * i, "%02X", (unsigned char)name[i]);
    if (root) snprintf(dir, size, "%s/%s", root, hex);
    else snprintf(dir, size, "%s/ts/%s", dir_in(), hex);
}

/* How many items the queue holds; -1 when it does not exist (QIDERR). */
static int ts_count(const char *dir) {
    struct stat st;
    char path[4200];
    if (stat(dir, &st) != 0) return -1;
    int n = 0;
    for (;;) {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, n + 1);
        if (stat(path, &st) != 0) return n;
        n++;
    }
}

static int ts_next(const char *dir) {
    char path[4200];
    int n = 0;
    snprintf(path, sizeof path, "%s/next", dir);
    FILE *f = fopen(path, "r");
    if (f) { if (fscanf(f, "%d", &n) != 1) n = 0; fclose(f); }
    return n;
}

static void ts_set_next(const char *dir, int n) {
    char path[4200];
    snprintf(path, sizeof path, "%s/next", dir);
    FILE *f = fopen(path, "w");
    if (f) { fprintf(f, "%d\n", n); fclose(f); }
}

/* READQ TS QUEUE ITEM(c->item) | NEXT (c->item 0) INTO LENGTH(c->len) (IBM, EXEC CICS READQ TS):
 * QIDERR when the queue does not exist; ITEMERR for an item outside the queue, or NEXT past its
 * end; else the item goes INTO, truncated to LENGTH with LENGERR when longer, and LENGTH is set
 * to the item's length. NUMITEMS (c->num) is the queue's item count. NEXT reads the item after
 * the last one read by any task; this stub counts a read by ITEM as a read too. */
int GGCREADQ(gg_cics *c, char *into) {
    char dir[4096], hex[40], path[4200], ev[160], buf[32768], item[16];
    int max = c->len, n = 0, copied = 0, next = c->item == 0;
    ts_dir(c, dir, sizeof dir, hex);
    int count = ts_count(dir);
    int want = next ? (count < 0 ? 0 : ts_next(dir)) + 1 : c->item;
    c->resp2 = 0;
    c->num = 0;
    if (count < 0) {
        c->resp = QIDERR;
    } else if (want < 1 || want > count) {
        c->resp = ITEMERR;
    } else {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, want);
        FILE *f = fopen(path, "rb");
        if (f) { n = (int)fread(buf, 1, sizeof buf, f); fclose(f); }
        copied = n < max ? n : (max > 0 ? max : 0);
        memcpy(into, buf, (size_t)copied);
        c->resp = n > max ? LENGERR : NORMAL;
        c->len = n;
        c->num = count;
        ts_set_next(dir, want);
    }
    if (next) snprintf(item, sizeof item, "NEXT");
    else snprintf(item, sizeof item, "%d", c->item);
    snprintf(ev, sizeof ev, "READQ-TS queue=%s item=%s resp=%d len=%d copied=%d", hex, item, c->resp,
             (c->resp == NORMAL || c->resp == LENGERR) ? n : -1, copied);
    event(ev, into, copied);
    return 0;
}

/* WRITEQ TS QUEUE FROM LENGTH(c->len) [ITEM REWRITE] (IBM, EXEC CICS WRITEQ TS): a new queue is
 * created by its first write; the item is appended and its number returned in ITEM (c->item).
 * REWRITE replaces item c->item: QIDERR without the queue, ITEMERR outside it. LENGERR when
 * LENGTH is outside 1-32763. NUMITEMS (c->num) is the count after the write. */
int GGCWRTQ(gg_cics *c, char *from) {
    char dir[4096], hex[40], path[4200], ev[160], flags[41];
    int len = c->len;
    trim(c->flags, 40, flags);
    int rewrite = strstr(flags, "REWRITE") != NULL;
    ts_dir(c, dir, sizeof dir, hex);
    int count = ts_count(dir), item = 0, fresp, fresp2;
    char qname[17];
    trim(c->qname, 16, qname);
    c->resp2 = 0;
    if (injected("WRITEQ-TS", qname, &fresp, &fresp2)) {  /* #4049: a planned condition; nothing is written */
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (len < 1 || len > 32763) {
        c->resp = LENGERR;
    } else if (rewrite && count < 0) {
        c->resp = QIDERR;
    } else if (rewrite && (c->item < 1 || c->item > count)) {
        c->resp = ITEMERR;
    } else {
        if (count < 0) {
            char root[4096];
            const char *env = getenv("GGCICS_TS");
            if (env) snprintf(root, sizeof root, "%s", env);
            else snprintf(root, sizeof root, "%s/ts", dir_in());
            MKDIR(root);
            MKDIR(dir);
            count = 0;
        }
        item = rewrite ? c->item : count + 1;
        snprintf(path, sizeof path, "%s/%06d.bin", dir, item);
        FILE *f = fopen(path, "wb");
        if (f) { fwrite(from, 1, (size_t)len, f); fclose(f); }
        c->resp = NORMAL;
        c->item = item;
        c->num = rewrite ? count : count + 1;
    }
    snprintf(ev, sizeof ev, "WRITEQ-TS queue=%s item=%d resp=%d len=%d", hex, item, c->resp, len);
    event(ev, from, len > 0 && len <= 32763 ? len : 0);
    return 0;
}

/* ---- the task's outputs ----------------------------------------------------------- */
/* SEND MAP: the symbolic map's bytes as the program left them (#4001: the harness resolves what
 * BMS sends from them and the BMS source); c->len is CURSOR's value, -1 when none was given. */
int GGCSMAP(gg_cics *c, char *from, int len) {
    char map[9], mapset[9], flags[41], ev[192];
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-MAP map=%s mapset=%s len=%d cursor=%d opts=%s", map, mapset, len, c->len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
    return 0;
}

/* SEND CONTROL (#4413): its options (GG-FLAGS) and CURSOR's value (c->len, -1 when none). */
int GGCSCTL(gg_cics *c) {
    char flags[41], ev[128];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-CONTROL cursor=%d opts=%s", c->len, flags);
    event(ev, NULL, 0);
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

int GGCSTXT(gg_cics *c, char *from, int len) {
    char flags[41], ev[128];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-TEXT len=%d opts=%s", len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
    return 0;
}

/* RETURN: at level 1 it ends the task, with TRANSID / COMMAREA for the next one; at a lower
 * level (#4004) it returns to the linking program, and the event shows the LINK COMMAREA as
 * that program now sees it (`len` -1: the LINK had none). */
static void return_event(const char *transid, char *commarea, int len);

int GGCRETN(gg_cics *c, char *commarea, int len) {
    char transid[9];
    trim(c->name1, 8, transid);
    return_event(transid, commarea, len);
    return 0;
}

/* XCTL PROGRAM(name1) [COMMAREA LENGTH: GG-ITEM 1] (IBM, EXEC CICS XCTL): the program ends and
 * the target runs at the same level, with a copy of LENGTH bytes from the named area -- all of
 * them, even past the end of the item (#4008). It fails, and control stays in the issuing
 * program, with LENGERR RESP2 11 for a LENGTH outside 0-32763 and PGMIDERR RESP2 1 for a
 * program the CSD does not define. */
static void xctl_next(const char *program, char *commarea, int len);
static int program_defined(const char *program);

/* #4023 follow-up: INQUIRE PROGRAM(name1) -- NORMAL for a program the CSD defines, else PGMIDERR (or the condition
 * faults.cfg injects). It changes nothing a task can see but its RESP, so it records no event. */
int GGCINQP(gg_cics *c) {
    char program[9];
    int fresp, fresp2;
    trim(c->name1, 8, program);
    c->resp = program_defined(program) ? NORMAL : PGMIDERR;
    c->resp2 = 0;
    if (injected("INQUIRE", program, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    }
    return 0;
}

static int channel_named(const char *name, int create);
static void xctl_channel(int chan);

int GGCXCTL(gg_cics *c, char *commarea, int len) {
    char program[9], ev[128], flags[41], name[17];
    int has = c->item != 0, fresp, fresp2, chan = 0;
    trim(c->flags, 40, flags);
    if (strstr(flags, "CHANNEL")) { /* #4270: XCTL CHANNEL -- the target's current channel, made if absent */
        trim(c->chan, 16, name);
        chan = channel_named(name, 1);
    }
    trim(c->name1, 8, program);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    else if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; }
    else if (injected("XCTL", program, &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; }  /* #4049 */
    snprintf(ev, sizeof ev, "XCTL program=%s len=%d area=%d resp=%d resp2=%d", program, has ? len : 0, has,
             c->resp, c->resp2);
    event(ev, has ? commarea : NULL, has && len > 0 && len <= 65535 ? len : 0);
    if (c->resp != NORMAL) return 0;
    ended = 1;
    xctl_next(program, has ? commarea : NULL, has ? len : 0);
    xctl_channel(chan);
    return 0;
}

/* ---- conditions and abends (#4003) --------------------------------------------------- *
 * Each program level (a LINK level, #4004) has its own handler state: per condition
 * (DFHRESP code) the index of its HANDLE CONDITION label, IGNORE (-1) or the default (0);
 * its HANDLE ABEND LABEL exit; and a PUSH HANDLE stack of saved states. The translator
 * numbers the labels a program's HANDLE commands name, and after a command that raised a
 * condition issues GO TO <labels> DEPENDING ON GG-GOTO (IBM's translator does the same
 * after the HANDLE command, with DFHEIGDI): the transfer is a plain COBOL GO TO.
 */
#define MAX_LEVELS 32
#define MAX_PUSH 16
#define NCOND 130
enum { ERRCOND = DFHRESP_ERROR }; /* HANDLE CONDITION ERROR's slot */

typedef struct {
    short cond[NCOND]; /* >0 label index, -1 IGNORE, 0 default */
    short aid[40];     /* HANDLE AID (#4007): per key (aid_keys), its label index, 0 none, -1 deactivated (#4414) */
    int exit_label;    /* HANDLE ABEND LABEL index, 0 none */
    int exit_active;   /* deactivated when it gets control (IBM, abend recovery) */
    char exit_name[31];
} handlers;

enum { RUNNING = 0, DONE = 1, XCTLED = 2 };

typedef struct {
    char prog[9];
    char invoker[9];         /* the program that LINKed / XCTLed to this one (ASSIGN INVOKINGPROG); "" at the first */
    char next_invoker[9];    /* the invoker of the program pending at this level */
    handlers h;
    handlers pushed[MAX_PUSH];
    int npushed;
    int state;               /* RUNNING, DONE (RETURN, GOBACK) or XCTLED (#4004) */
    int pending;             /* a program is to run at this level: next / next_len / next_area */
    char next[9];
    int next_len, next_area_set;
    char *next_area;
    char *link_area;         /* the LINK COMMAREA: the linking program's own storage (NULL: none) */
    int link_len;
    /* #4270: the channel the level's program was passed (index + 1 into chans; 0: none), the channels in its
     * scope, and the names an XCTL left behind (naming one is refused: IBM does not document their scope) */
    int cur;
    int scope[32];
    int nscope;
    char dropped[32][17];
    int ndropped;
    int next_chan;           /* the channel an XCTL passes to the program pending at this level (index + 1) */
} level;

static level levels[MAX_LEVELS];
static void channel_pass(level *L, int passed); /* #4270 */
static int lvl = 0; /* the current level, 0 = level 1 */
static char task_abcode[5] = "    ";

static const char *current_program(void) { return levels[lvl].prog; }

/* The program's entry: the translator names it (GG-NAME1) for the level it runs at. It starts
 * with no handlers of its own: "The HANDLE CONDITION options are not inherited by the linked-to
 * program" (IBM, LINK), nor by the program XCTLed to. */
int GGCPENT(gg_cics *c) {
    level *L = &levels[lvl];
    trim(c->name1, 8, L->prog);
    memset(&L->h, 0, sizeof L->h);
    L->npushed = 0;
    L->state = RUNNING;
    return 0;
}

/* HANDLE CONDITION / IGNORE CONDITION: condition GG-NUM gets label GG-ITEM (0: the default
 * action again, -1: IGNORE). The last HANDLE or IGNORE for a condition wins (IBM, IGNORE
 * CONDITION: "until a HANDLE CONDITION command for the same condition is encountered"). */
int GGCHCND(gg_cics *c) {
    if (c->num > 0 && c->num < NCOND) levels[lvl].h.cond[c->num] = (short)c->item;
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* HANDLE ABEND LABEL (GG-NAME2 'LABEL', GG-ITEM its index, GG-FLAGS its name), CANCEL or
 * RESET (IBM, EXEC CICS HANDLE ABEND). */
int GGCHABN(gg_cics *c) {
    char how[9];
    handlers *h = &levels[lvl].h;
    trim(c->name2, 8, how);
    if (strcmp(how, "LABEL") == 0) {
        h->exit_label = c->item;
        h->exit_active = 1;
        trim(c->flags, 30, h->exit_name);
    } else if (strcmp(how, "CANCEL") == 0) {
        h->exit_active = 0;
    } else if (h->exit_label) { /* RESET: reactivate the exit cancelled, or taken */
        h->exit_active = 1;
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* PUSH HANDLE saves the level's HANDLE CONDITION, IGNORE CONDITION and HANDLE ABEND state and
 * suspends it; POP HANDLE restores the last one saved, INVREQ when none is (IBM, PUSH / POP). */
int GGCPUSH(gg_cics *c) {
    level *L = &levels[lvl];
    c->resp2 = 0;
    if (L->npushed >= MAX_PUSH) { c->resp = INVREQ; return 0; }
    L->pushed[L->npushed++] = L->h;
    memset(&L->h, 0, sizeof L->h);
    c->resp = NORMAL;
    return 0;
}

int GGCPOP(gg_cics *c) {
    level *L = &levels[lvl];
    c->resp2 = 0;
    if (L->npushed == 0) { c->resp = INVREQ; return 0; }
    L->h = L->pushed[--L->npushed];
    c->resp = NORMAL;
    return 0;
}

/* ---- HANDLE AID (#4007) ---------------------------------------------------------------- *
 * The keys HANDLE AID names, and the EIBAID byte each one sends (the harness's DFHAID.cpy:
 * tests/equivalence/cics, kept equal by a test). ANYKEY is any PA or PF key or CLEAR, not
 * ENTER (IBM, HANDLE AID). */
static const struct { const char *name; char eibaid; } aid_keys[] = {
    {"ANYKEY", 0}, {"ENTER", '\''}, {"CLEAR", '_'}, {"CLRPARTN", 0x6A}, {"LIGHTPEN", '='}, {"OPERID", 'W'},
    {"TRIGGER", '"'}, {"PA1", '%'}, {"PA2", '>'}, {"PA3", ','}, {"PF1", '1'}, {"PF2", '2'}, {"PF3", '3'},
    {"PF4", '4'}, {"PF5", '5'}, {"PF6", '6'}, {"PF7", '7'}, {"PF8", '8'}, {"PF9", '9'}, {"PF10", ':'},
    {"PF11", '#'}, {"PF12", '@'}, {"PF13", 'A'}, {"PF14", 'B'}, {"PF15", 'C'}, {"PF16", 'D'}, {"PF17", 'E'},
    {"PF18", 'F'}, {"PF19", 'G'}, {"PF20", 'H'}, {"PF21", 'I'}, {"PF22", '['}, {"PF23", '.'}, {"PF24", '<'},
};
#define NAIDS ((int)(sizeof aid_keys / sizeof aid_keys[0]))

/* HANDLE AID <key>(label): the key (GG-NAME1) gets label GG-ITEM; -1 deactivates it ("To ignore
 * an AID, issue a HANDLE AID command that specifies the associated option without a label"). */
int GGCHAID(gg_cics *c) {
    char key[9];
    trim(c->name1, 8, key);
    for (int i = 0; i < NAIDS; i++) {
        if (strcmp(aid_keys[i].name, key) == 0) levels[lvl].h.aid[i] = (short)c->item;
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* After an input command that completed normally, with neither RESP nor NOHANDLE: the label of
 * the key that was pressed (the EIBAID byte in GG-NAME1), else ANYKEY's for a PA / PF key or CLEAR,
 * else 0 -- "control returns to the application program at the instruction immediately following
 * the input command" (IBM, HANDLE AID). #4414: called first with the condition the command raised
 * (GG-RESP not 0): when a label applies to the key, which of the two CICS acts on first is not
 * documented, so it is recorded as AID-REFUSED for the driver to refuse, and control goes on. */
int GGCAID(gg_cics *c) {
    handlers *h = &levels[lvl].h;
    char aid = c->name1[0];
    c->go_to = 0;
    for (int i = 1; i < NAIDS; i++) {
        if (aid_keys[i].eibaid != aid) continue;
        if (h->aid[i] > 0) c->go_to = h->aid[i];
        else if (h->aid[0] > 0 && (aid_keys[i].name[0] == 'P' || strcmp(aid_keys[i].name, "CLEAR") == 0)) {
            /* #4414: a key deactivated (-1) while ANYKEY has a label: IBM does not say which applies */
            if (h->aid[i] < 0) { event("AID-REFUSED deactivated=1", NULL, 0); return 0; }
            c->go_to = h->aid[0];
        }
        break;
    }
    if (c->resp != NORMAL && c->go_to > 0) {
        char ev[64];
        snprintf(ev, sizeof ev, "AID-REFUSED resp=%d", c->resp);
        event(ev, NULL, 0);
        c->go_to = 0;
    }
    return 0;
}

/* The task abends with `code`: the first active HANDLE ABEND exit from this level upward gets
 * control ("CICS searches for an active abend exit, starting at the logical level of the
 * application program in which the abend occurred, and proceeding to successively higher
 * levels"), deactivated as it does; the levels below it are gone. At this level the program
 * GOes TO its label; above, it GOBACKs (GG-GOTO -1) until the LINK of that level (#4004).
 * With no exit (or CANCEL) the task terminates. */
static int unwind_to = -1, unwind_goto = 0, terminated = 0;

static void abend(gg_cics *c, const char *code, const char *cause, int cond, int cancel) {
    char ev[200], what[40] = "";
    int at = -1;
    memcpy(task_abcode, code, 4);
    if (cond) snprintf(what, sizeof what, " condition=%d", cond);
    for (int i = lvl; i >= 0 && !cancel; i--) {
        if (levels[i].h.exit_active) { at = i; break; }
    }
    if (at < 0) {
        snprintf(ev, sizeof ev, "ABEND abcode=%s cause=%s%s outcome=terminated", code, cause, what);
        uow_end(1); /* dynamic transaction backout: the terminated task's file changes are undone */
        ended = 1;
        terminated = 1;
        unwind_to = -1;
        c->go_to = -1;
    } else {
        handlers *h = &levels[at].h;
        h->exit_active = 0;
        snprintf(ev, sizeof ev, "ABEND abcode=%s cause=%s%s outcome=exit exit=%s.%s", code, cause, what,
                 levels[at].prog, h->exit_name);
        if (at == lvl) {
            c->go_to = h->exit_label;
        } else {
            unwind_to = at;
            unwind_goto = h->exit_label;
            c->go_to = -1;
        }
    }
    event(ev, NULL, 0);
}

/* EXEC CICS ABEND ABCODE(GG-NAME1) [CANCEL: GG-FLAGS]. */
int GGCABND(gg_cics *c) {
    char code[9], flags[41];
    trim(c->name1, 8, code);
    trim(c->flags, 40, flags);
    while (strlen(code) < 4) strcat(code, " ");
    abend(c, code, "command", 0, strstr(flags, "CANCEL") != NULL);
    return 0;
}

/* A command raised condition GG-RESP and the program gave neither RESP nor NOHANDLE: IGNOREd
 * (GG-GOTO 0, control continues), its HANDLE CONDITION label, else the ERROR label ("If no
 * HANDLE CONDITION command is active for a condition, but one is active for ERROR, control
 * passes to the label for ERROR"), else the default action: abend with its AEIx code. */
int GGCCOND(gg_cics *c) {
    handlers *h = &levels[lvl].h;
    int cond = c->resp;
    short st = cond > 0 && cond < NCOND ? h->cond[cond] : 0;
    c->go_to = 0;
    if (st == -1) return 0;
    if (st > 0) { c->go_to = st; return 0; }
    /* #4413: EOC's default action is to ignore it (IBM, RECEIVE (LUTYPE2/LUTYPE3)); ERROR takes
     * only a condition whose "default action ... terminates the task abnormally" (HANDLE CONDITION) */
    if (cond == EOC) return 0;
    if (h->cond[ERRCOND] > 0) { c->go_to = h->cond[ERRCOND]; return 0; }
    abend(c, condition_abcode(cond), "condition", cond, 0);
    return 0;
}

/* ASSIGN ABCODE: the task's current abend code, blanks when there has been none. */
int GGCASGN(gg_cics *c) {
    char want[9], line[256], key[16], value[16], path[4096];
    trim(c->name2, 8, want);
    memset(c->name1, ' ', 8);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strcmp(want, "INVOKING") == 0) { /* INVOKINGPROG (GG-NAME2 holds 8): who LINKed / XCTLed here; blanks at first */
        const char *p = levels[lvl].invoker;
        memcpy(c->name1, p, strlen(p) < 8 ? strlen(p) : 8);
        return 0;
    }
    if (strcmp(want, "PROGRAM") == 0) { /* ASSIGN PROGRAM: the program running at this level */
        const char *p = current_program();
        memcpy(c->name1, p, strlen(p) < 8 ? strlen(p) : 8);
        return 0;
    }
    /* #4270 slice 3: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD, from what the runner states for the task
     * ($GGCICS_STARTCODE: TD, S or SD; $GGCICS_USERID; $GGCICS_FACILITY: its terminal, empty for none;
     * $GGCICS_SCREEN: "rows cols"); unstated, the option is refused, never guessed. TERMCHK: INVREQ RESP2 5 for a
     * task with no terminal (IBM, ASSIGN: "The task is not associated with a terminal; or the task has no
     * principal facility"), before any FACILITY / SCRNHT / SCRNWD data area is written. */
    if (strcmp(want, "STARTCOD") == 0 || strcmp(want, "USERID") == 0 || strcmp(want, "FACILITY") == 0
        || strcmp(want, "TERMCHK") == 0 || strcmp(want, "SCRNHT") == 0 || strcmp(want, "SCRNWD") == 0) {
        const char *env = getenv(strcmp(want, "STARTCOD") == 0 ? "GGCICS_STARTCODE"
                                 : strcmp(want, "USERID") == 0 ? "GGCICS_USERID"
                                 : strncmp(want, "SCRN", 4) == 0 ? "GGCICS_SCREEN" : "GGCICS_FACILITY");
        int rows = 0, cols = 0;
        if (strcmp(want, "STARTCOD") == 0 && getenv("GGCICS_RUNCHILD"))
            refuse("ASSIGN STARTCODE in a RUN TRANSID child task: IBM lists no code for it");
        if (!env) {
            snprintf(line, sizeof line, "ASSIGN %s: not stated for this task", want);
            refuse(line);
            return 0;
        }
        if (strcmp(want, "TERMCHK") == 0) {
            if (!env[0]) { c->resp = INVREQ; c->resp2 = 5; }
            return 0;
        }
        if (strncmp(want, "SCRN", 4) == 0) {
            if (sscanf(env, "%d %d", &rows, &cols) != 2) refuse("ASSIGN SCRNHT / SCRNWD: $GGCICS_SCREEN");
            c->num = strcmp(want, "SCRNHT") == 0 ? rows : cols;
            return 0;
        }
        memcpy(c->name1, env, strlen(env) < 8 ? strlen(env) : 8);
        return 0;
    }
    if (strcmp(want, "APPLID") != 0 && strcmp(want, "SYSID") != 0) { /* ASSIGN ABCODE */
        memcpy(c->name1, task_abcode, 4);
        return 0;
    }
    /* ASSIGN APPLID / SYSID: the region's identity, as the case declares it (region.cfg: "APPLID x", "SYSID y") */
    snprintf(path, sizeof path, "%s/region.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    while (cfg && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%15s %15s", key, value) == 2 && strcmp(key, want) == 0) {
            memcpy(c->name1, value, strlen(value) < 8 ? strlen(value) : 8);
        }
    }
    if (cfg) fclose(cfg);
    return 0;
}

/* WRITEQ TD QUEUE(qname) FROM LENGTH(GG-LEN): one record on a transient-data queue -- recorded with its data and
 * compared (CardDemo's CORPT00C submits JCL through the JOBS queue). QIDERR for a queue the CSD does not define
 * (tdqueues.cfg; absent, every queue is defined). */
int GGCWRTD(gg_cics *c, char *from) {
    char queue[17], line[256], name[32], ev[96], path[4096];
    int fresp, fresp2, defined = 1;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    snprintf(path, sizeof path, "%s/tdqueues.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    if (cfg) {
        defined = 0;
        while (fgets(line, sizeof line, cfg)) if (sscanf(line, "%31s", name) == 1 && strcmp(name, queue) == 0) defined = 1;
        fclose(cfg);
    }
    if (injected("WRITEQ-TD", queue, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (!defined) {
        c->resp = QIDERR;
    }
    snprintf(ev, sizeof ev, "WRITEQ-TD queue=%s len=%d resp=%d", queue, c->len, c->resp);
    event(ev, c->resp == NORMAL ? from : NULL, c->resp == NORMAL ? c->len : 0);
    return 0;
}

/* ---- program levels: LINK, XCTL and the dispatcher (#4004) ---------------------------- */
static void return_event(const char *transid, char *commarea, int len) {
    char ev[96];
    level *L = &levels[lvl];
    L->state = DONE;
    if (lvl == 0) {
        snprintf(ev, sizeof ev, "RETURN level=1 transid=%s len=%d", transid, len);
        ended = 1;
        event(ev, commarea, len);
    } else {
        snprintf(ev, sizeof ev, "RETURN level=%d transid= len=%d", lvl + 1, L->link_area ? L->link_len : -1);
        event(ev, L->link_area, L->link_area ? L->link_len : 0);
    }
}

static void xctl_next(const char *program, char *commarea, int len) {
    level *L = &levels[lvl];
    snprintf(L->next_invoker, sizeof L->next_invoker, "%s", L->prog);  /* the XCTLing program */
    L->state = XCTLED;
    snprintf(L->next, sizeof L->next, "%s", program);
    L->next_len = commarea && len > 0 ? len : 0;
    L->next_area = NULL;
    if (L->next_len > 0) {
        L->next_area = malloc((size_t)L->next_len);
        if (L->next_area) memcpy(L->next_area, commarea, (size_t)L->next_len);
    }
    L->next_area_set = 1;
}

/* Whether the CSD defines `program` (programs.cfg; SPEC 2: program autoinstall is off). */
static int program_defined(const char *program) {
    char path[4096], line[64], name[64];
    int found = 0;
    snprintf(path, sizeof path, "%s/programs.cfg", dir_in());
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    while (!found && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s", name) == 1 && strcmp(name, program) == 0) found = 1;
    }
    fclose(f);
    return found;
}

/* #4270: EIBTASKN, the task's number, a fact of the run whoever runs the task states ($GGCICS_TASKN, as the
 * Java side's CicsTask.withTaskNumber; oracle_assumptions.md X21). The drivers CALL it after INITIALIZE DFHEIBLK
 * and MOVE GG-NUM TO EIBTASKN. IBM: "the task number assigned to the task by CICS", PIC S9(7) COMP-3: a value
 * that is not 0 to 9999999 is refused; unstated, 0 (the INITIALIZEd EIB's, as before). */
int GGCTASKN(gg_cics *c) {
    const char *env = getenv("GGCICS_TASKN");
    char *end = NULL;
    long n = 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (env) {
        n = strtol(env, &end, 10);
        if (!env[0] || *end || n < 0 || n > 9999999) refuse("EIBTASKN: $GGCICS_TASKN is not a task number");
    }
    c->num = (int)n;
    return 0;
}

/* The driver: the task's first program (GG-NAME1) and its COMMAREA length (GG-LEN). */
int GGCTASK(gg_cics *c) {
    lvl = 0;
    memset(&levels[0], 0, sizeof levels[0]);
    trim(c->name1, 8, levels[0].next);
    levels[0].next_len = c->len;
    levels[0].pending = 1;
    return 0;
}

/* GGCRUN asks what to run at this level: GG-ITEM 1 with the program (GG-NAME1), its EIBCALEN
 * (GG-LEN) and the COMMAREA's address (*area; NULL for none), or 0 when the level is done. */
int GGCNEXT(gg_cics *c, char **area) {
    level *L = &levels[lvl];
    c->item = 0;
    if (!L->pending || terminated || unwind_to >= 0) return 0;
    L->pending = 0;
    memset(c->name1, ' ', 8);
    memcpy(c->name1, L->next, strlen(L->next));
    c->len = L->next_len;
    if (L->next_area_set) *area = L->next_area;
    else if (L->next_len <= 0) *area = NULL; /* level 1 with EIBCALEN 0: no COMMAREA */
    if (L->state == XCTLED) { /* #4270: an XCTL's target: the channel it passed, the rest left behind */
        channel_pass(L, L->next_chan);
        L->next_chan = 0;
    }
    memcpy(L->prog, L->next, sizeof L->prog);
    memcpy(L->invoker, L->next_invoker, sizeof L->invoker);
    L->next_invoker[0] = 0;
    L->state = RUNNING;
    c->item = 1;
    return 0;
}

/* The level's program has returned to GGCRUN: after an XCTL its target runs next; after a
 * GOBACK with no RETURN, that GOBACK was the RETURN; after an abend, nothing. */
int GGCPEND(gg_cics *c) {
    level *L = &levels[lvl];
    (void)c;
    if (terminated || unwind_to >= 0) return 0;
    if (L->state == XCTLED) { L->pending = 1; return 0; }
    if (L->state == RUNNING) return_event("", NULL, 0);
    return 0;
}

/* GGCRUN has no program by that name: the case's translated programs do not include it. */
int GGCNOPG(gg_cics *c) {
    char program[9], ev[64];
    trim(c->name1, 8, program);
    snprintf(ev, sizeof ev, "NOPROGRAM target=%s", program);
    event(ev, NULL, 0);
    terminated = ended = 1;
    return 0;
}

/* LINK PROGRAM(name1) [COMMAREA(area) LENGTH(len): GG-ITEM 1] (IBM, EXEC CICS LINK):
 * LENGERR RESP2 11 for a length outside 0-32763, PGMIDERR RESP2 1 for a program the CSD does
 * not define; else a new level, whose program gets the caller's area itself (the COMMAREA is
 * passed by reference) and EIBCALEN = LENGTH (0 without COMMAREA). The event carries the
 * area's bytes as the command is issued. */
int GGCLINK(gg_cics *c, char *area) {
    char program[9], ev[128], flags[41], name[17];
    int has = c->item != 0, len = has ? c->len : 0, chan = 0;
    trim(c->name1, 8, program);
    trim(c->flags, 40, flags);
    if (strstr(flags, "CHANNEL")) { /* #4270: LINK CHANNEL -- made empty if absent ("a new empty channel is created") */
        trim(c->chan, 16, name);
        chan = channel_named(name, 1);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    else if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; }
    else if (lvl + 1 >= MAX_LEVELS) { c->resp = INVREQ; }
    snprintf(ev, sizeof ev, "LINK target=%s len=%d area=%d resp=%d resp2=%d", program, len, has, c->resp, c->resp2);
    event(ev, has ? area : NULL, has && len > 0 && len <= 32763 ? len : 0);
    if (c->resp != NORMAL) return 0;
    const char *linker = current_program();
    char by[9];
    snprintf(by, sizeof by, "%s", linker);
    lvl++;
    memset(&levels[lvl], 0, sizeof levels[lvl]);
    level *L = &levels[lvl];
    snprintf(L->next, sizeof L->next, "%s", program);
    snprintf(L->next_invoker, sizeof L->next_invoker, "%s", by);
    L->next_len = len;
    L->next_area = has ? area : NULL;
    L->next_area_set = 1;
    L->link_area = has ? area : NULL;
    L->link_len = len;
    L->pending = 1;
    channel_pass(L, chan); /* #4270: the callee's channel, the only one in its scope (0: none) */
    return 0;
}

/* Back in the linking program: the level is gone. After an abend whose exit is at this level,
 * GG-GOTO is the exit's label; at a level above, or with no exit, -1 (leave this program too). */
int GGCLRET(gg_cics *c) {
    if (lvl > 0) lvl--;
    c->resp = NORMAL;
    c->resp2 = 0;
    c->go_to = 0;
    if (terminated) {
        c->go_to = -1;
    } else if (unwind_to >= 0) {
        if (lvl <= unwind_to) {
            c->go_to = unwind_goto;
            unwind_to = -1;
        } else {
            c->go_to = -1;
        }
    }
    return 0;
}

/* ---- #4270: channels and containers ----------------------------------------------------- *
 * IBM CICS TS: PUT / GET / DELETE CONTAINER (CHANNEL), LINK / XCTL CHANNEL, ASSIGN CHANNEL,
 * "Scope of a channel". A container holds the program's bytes exactly: BIT is never converted,
 * and CHAR with no FROMCCSID / INTOCCSID is in the region's CCSID both ways (GET CONTAINER: "If
 * INTOCCSID and INTOCODEPAGE are not specified, the value for conversion defaults to the CCSID
 * of the region") -- the translator refuses the CCSID options. A channel is in the scope of the
 * level that made it and of a level it is passed to (LINK CHANNEL: "the called program"; XCTL
 * CHANNEL: the target). Containers are not events: a program shows what it got by what it does. */
#define MAX_CHANNELS 64
#define MAX_CONTAINERS 64
typedef struct { char name[17]; int bit; char *data; int len; int used; } gg_container;
typedef struct { char name[17]; gg_container c[MAX_CONTAINERS]; } gg_channel;
static gg_channel chans[MAX_CHANNELS];
static int nchans = 0;

/* A channel / container name without its trailing blanks; one that is empty, has an embedded
 * blank, or more than 16 characters is refused (IBM's "illegal character" rules are not modelled). */
static void cics_name(const char *src, char *dst, const char *what) {
    char msg[96];
    trim(src, 16, dst);
    if (!dst[0] || strchr(dst, ' ')) {
        snprintf(msg, sizeof msg, "%s name '%s'", what, dst);
        refuse(msg);
    }
}

/* The channel `name` in the current level's scope (index + 1), 0 when there is none; with
 * `create`, a new empty one when there is none. A name an XCTL left behind is refused. */
static int channel_named(const char *name, int create) {
    level *L = &levels[lvl];
    char msg[96];
    for (int i = 0; i < L->ndropped; i++) {
        if (strcmp(L->dropped[i], name) == 0) {
            snprintf(msg, sizeof msg, "channel %s after an XCTL that did not pass it", name);
            refuse(msg);
        }
    }
    for (int i = 0; i < L->nscope; i++) {
        if (strcmp(chans[L->scope[i] - 1].name, name) == 0) return L->scope[i];
    }
    if (!create) return 0;
    if (nchans >= MAX_CHANNELS || L->nscope >= 32) refuse("more channels than the stub holds");
    snprintf(chans[nchans].name, sizeof chans[nchans].name, "%s", name);
    nchans++;
    L->scope[L->nscope++] = nchans;
    return nchans;
}

/* A level's program starts with `passed` (index + 1; 0: none) as its current channel, the only
 * one in its scope; the names in scope before it (an XCTL's) are left behind. */
static void channel_pass(level *L, int passed) {
    L->ndropped = 0;
    for (int i = 0; i < L->nscope && L->ndropped < 32; i++) {
        if (L->scope[i] != passed) snprintf(L->dropped[L->ndropped++], 17, "%s", chans[L->scope[i] - 1].name);
    }
    L->cur = passed;
    L->nscope = 0;
    if (passed) L->scope[L->nscope++] = passed;
}

static void xctl_channel(int chan) { levels[lvl].next_chan = chan; }

/* The command's channel: GG-CHAN when GG-FLAGS says CHANNEL (`create`: PUT makes it), else the
 * current channel; 0 with RESP set when there is none. */
static int command_channel(gg_cics *c, int create, int no_current_resp2) {
    char flags[41], name[17];
    trim(c->flags, 40, flags);
    if (strstr(flags, "CHANNEL")) {
        cics_name(c->chan, name, "channel");
        int ch = channel_named(name, create);
        if (!ch) { c->resp = CHANNELERR; c->resp2 = 2; }
        return ch;
    }
    if (!levels[lvl].cur) { c->resp = INVREQ; c->resp2 = no_current_resp2; }
    return levels[lvl].cur;
}

static gg_container *container_named(gg_channel *ch, const char *name, int create) {
    gg_container *free_slot = NULL;
    for (int i = 0; i < MAX_CONTAINERS; i++) {
        if (ch->c[i].used && strcmp(ch->c[i].name, name) == 0) return &ch->c[i];
        if (!ch->c[i].used && !free_slot) free_slot = &ch->c[i];
    }
    if (!create) return NULL;
    if (!free_slot) refuse("more containers than the stub holds");
    memset(free_slot, 0, sizeof *free_slot);
    snprintf(free_slot->name, sizeof free_slot->name, "%s", name);
    free_slot->used = 1;
    return free_slot;
}

/* PUT CONTAINER(GG-QNAME) [CHANNEL: GG-CHAN] FROM FLENGTH(GG-LEN); GG-FLAGS: CHANNEL, BIT / CHAR,
 * APPEND. No channel and no current one: INVREQ RESP2 4, 1 when a data type was named. FLENGTH
 * below zero: LENGERR RESP2 1. A new container takes the type named, else BIT (naming the other
 * type for an existing one is refused, below). The data replaces the container's, or follows it. */
int GGCPUTC(gg_cics *c, char *from) {
    char flags[41], name[17];
    int bit, chr, ch;
    trim(c->flags, 40, flags);
    bit = strstr(flags, "BIT") != NULL;
    chr = strstr(flags, "CHAR") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    ch = command_channel(c, 1, bit || chr ? 1 : 4);
    if (!ch) return 0;
    if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    /* the other data type for an existing container: IBM says both that DATATYPE "applies only to new
     * containers" and that changing it is INVREQ RESP2 33 -- not settled, refused */
    if (k && (bit || chr) && k->bit != bit) refuse("PUT CONTAINER changing an existing container's data type");
    if (!k) {
        k = container_named(&chans[ch - 1], name, 1);
        k->bit = !chr;
    }
    if (strstr(flags, "APPEND")) {
        char *joined = realloc(k->data, (size_t)(k->len + c->len) + 1);
        if (!joined) refuse("out of memory");
        memcpy(joined + k->len, from, (size_t)c->len);
        k->data = joined;
        k->len += c->len;
    } else {
        free(k->data);
        k->data = malloc((size_t)c->len + 1);
        if (!k->data) refuse("out of memory");
        memcpy(k->data, from, (size_t)c->len);
        k->len = c->len;
    }
    return 0;
}

/* GET CONTAINER(GG-QNAME) [CHANNEL] INTO FLENGTH | NODATA (GG-FLAGS); GG-LEN in: the most INTO
 * takes; out: the container's length (NORMAL, LENGERR; else left as it came). CHANNELERR RESP2 2,
 * INVREQ RESP2 4, CONTAINERERR RESP2 10; longer data truncated, LENGERR RESP2 11. */
int GGCGETC(gg_cics *c, char *into) {
    char flags[41], name[17];
    int ch;
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    ch = command_channel(c, 0, 4);
    if (!ch) return 0;
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (!k) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    if (!strstr(flags, "NODATA")) {
        if (c->len < 0) refuse("GET CONTAINER FLENGTH below zero");
        int n = k->len < c->len ? k->len : c->len;
        memcpy(into, k->data, (size_t)n);
        if (k->len > c->len) { c->resp = LENGERR; c->resp2 = 11; }
    }
    c->len = k->len;
    return 0;
}

/* DELETE CONTAINER(GG-QNAME) [CHANNEL]: CHANNELERR RESP2 2, INVREQ RESP2 4, CONTAINERERR RESP2 10. */
int GGCDELC(gg_cics *c) {
    char name[17];
    int ch;
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    ch = command_channel(c, 0, 4);
    if (!ch) return 0;
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (!k) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    free(k->data);
    memset(k, 0, sizeof *k);
    return 0;
}

/* ASSIGN CHANNEL: the current channel's name into GG-CHAN, blanks when there is none. */
int GGCASCH(gg_cics *c) {
    memset(c->chan, ' ', 16);
    if (levels[lvl].cur) memcpy(c->chan, chans[levels[lvl].cur - 1].name, strlen(chans[levels[lvl].cur - 1].name));
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* ---- interval control (#4006) ---------------------------------------------------------- *
 * The virtual clock is $GGCICS_NOW; a task takes no time (SPEC 4). START records its request
 * as an event (with its expiry); the runner's scheduler keeps the requests and dispatches
 * them. RETRIEVE reads the data of the requests the task was started for. */
enum { TRANSIDERR = DFHRESP_TRANSIDERR, TERMIDERR = DFHRESP_TERMIDERR, IOERR = DFHRESP_IOERR,
       ENVDEFERR = DFHRESP_ENVDEFERR };

static time_t now_epoch(void) {
    const char *s = getenv("GGCICS_NOW");
    struct tm t;
    memset(&t, 0, sizeof t);
    if (!s || sscanf(s, "%d-%d-%dT%d:%d:%d", &t.tm_year, &t.tm_mon, &t.tm_mday, &t.tm_hour, &t.tm_min,
                     &t.tm_sec) != 6)
        return 0;
    t.tm_year -= 1900;
    t.tm_mon -= 1;
    return timegm(&t);
}

static void iso(time_t when, char *out, size_t size) {
    struct tm t;
    gmtime_r(&when, &t);
    strftime(out, size, "%Y-%m-%dT%H:%M:%S", &t);
}

static int listed(const char *file, const char *name) {
    char path[4096], line[64], word[64];
    int found = 0;
    snprintf(path, sizeof path, "%s/%s", dir_in(), file);
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    while (!found && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s", word) == 1 && strcmp(word, name) == 0) found = 1;
    }
    fclose(f);
    return found;
}

/* This task's own STARTs with a REQID, for a CANCEL in the same task. */
static struct { char reqid[17]; time_t expires; int cancelled; int data; } own[64];
static int nown = 0;

/* #4270: AFTER / AT's HOURS, MINUTES, SECONDS (-1: not given) as hhmmss, or -4 / -5 / -6 (INVREQ's RESP2,
 * negated) for the first one out of range (IBM, EXEC CICS START, AFTER: "A combination of at least two of
 * HOURS(0 - 99), MINUTES(0 - 59), and SECONDS(0 - 59)", or "one of HOURS(0 - 99), MINUTES(0 - 5999), or
 * SECONDS(0 - 359999)"). */
#define NOT_GIVEN (-999999999) /* the translator's GG-HOURS / GG-MINS / GG-SECS for an option not given */
static int hms(int h, int m, int s) {
    int given = (h != NOT_GIVEN) + (m != NOT_GIVEN) + (s != NOT_GIVEN), total;
    if (h != NOT_GIVEN && (h < 0 || h > 99)) return -4;
    if (m != NOT_GIVEN && (m < 0 || m > (given == 1 ? 5999 : 59))) return -5;
    if (s != NOT_GIVEN && (s < 0 || s > (given == 1 ? 359999 : 59))) return -6;
    total = (h != NOT_GIVEN ? h : 0) * 3600 + (m != NOT_GIVEN ? m : 0) * 60 + (s != NOT_GIVEN ? s : 0);
    return total / 3600 * 10000 + total / 60 % 60 * 100 + total % 60;
}

/* Whether the blank-separated GG-FLAGS words include `w`. */
static int flag_word(const char *flags, const char *w) {
    size_t n = strlen(w);
    for (const char *p = flags; (p = strstr(p, w)) != NULL; p += n) {
        if ((p == flags || p[-1] == ' ') && (p[n] == ' ' || p[n] == '\0')) return 1;
    }
    return 0;
}

/* `key=<hex>` for an event line, the value trimmed (#4270: RTRANSID / RTERMID / QUEUE). */
static void hexarg(char *out, size_t size, const char *key, const char *v, int n) {
    char t[17];
    size_t at;
    trim(v, n, t);
    at = (size_t)snprintf(out, size, " %s=", key);
    for (int i = 0; t[i] && at + 3 < size; i++) at += (size_t)snprintf(out + at, size - at, "%02X", (unsigned char)t[i]);
}

/* START TRANSID(name1) [TERMID(name2)] [REQID(qname)] INTERVAL(hhmmss) | TIME(hhmmss) (GG-NUM) | AFTER / AT
 * HOURS MINUTES SECONDS (GG-HOURS / GG-MINS / GG-SECS; GG-FLAGS says which) [FROM LENGTH: GG-ITEM 1] [PROTECT]
 * [RTRANSID RTERMID QUEUE: GG-RTRAN / GG-RTERM / GG-RQUEUE, flagged] (IBM, EXEC CICS START): the request expires at
 * now + INTERVAL (or AFTER), or at TIME (or AT) -- "If you specify a time with an hours component that is greater
 * than 23, you are specifying a time on a day following the current one"; a time of today not later than now but
 * within the preceding six hours expires at once ("If you specify a task to start at any time within the previous
 * six hours, it starts immediately"), an earlier one tomorrow (IBM, "Expiration times"). INVREQ RESP2 4 / 5 / 6 for
 * hours / minutes / seconds out of range, LENGERR for a LENGTH not greater than zero, TRANSIDERR for a transaction
 * the CSD does not define, TERMIDERR for a terminal other than the region's, IOERR for a REQID this task already
 * used with FROM, used again with FROM ("A START operation uses a REQID name that exists. This condition occurs only
 * when the FROM option is also used"); any other REQID that exists is refused. */
int GGCSTRT(gg_cics *c, char *from) {
    char transid[9], termid[9], reqid[17], flags[41], ev[512], expires[32] = "", hhmm[16] = "", named[128] = "";
    int has = c->item != 0, len = has ? c->len : 0, hhmmss = c->num, resp2 = 0;
    int is_time, protect, fresp, fresp2, reused = -1, after;
    time_t now = now_epoch(), at = now;
    trim(c->name1, 8, transid);
    trim(c->name2, 8, termid);
    trim(c->qname, 8, reqid);
    trim(c->flags, 40, flags);
    after = flag_word(flags, "AFTER") || flag_word(flags, "AT");
    is_time = flag_word(flags, "TIME") || flag_word(flags, "AT");
    protect = flag_word(flags, "PROTECT");
    if (after) {
        hhmmss = hms(c->hours, c->mins, c->secs);
        if (hhmmss < 0) resp2 = -hhmmss;
    } else if (hhmmss < 0 || hhmmss / 10000 > 99) {
        resp2 = 4;
    } else if (hhmmss / 100 % 100 > 59) {
        resp2 = 5;
    } else if (hhmmss % 100 > 59) {
        resp2 = 6;
    }
    int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
    if (reqid[0]) {
        char rq[256];
        for (int i = 0; i < nown && reused < 0; i++) {
            if (!own[i].cancelled && strcmp(own[i].reqid, reqid) == 0) reused = own[i].data;
        }
        if (reused < 0) {
            char path[4096], line[128], word[64];
            long ex;
            snprintf(path, sizeof path, "%s/requests.cfg", dir_in());
            FILE *f = fopen(path, "r");
            while (f && reused < 0 && fgets(line, sizeof line, f)) {
                if (sscanf(line, "%63s %ld", word, &ex) == 2 && strcmp(word, reqid) == 0 && ex > now) reused = 0;
            }
            if (f) fclose(f);
        }
        if (reused >= 0 && !(has && reused == 1)) {
            snprintf(rq, sizeof rq, "START REQID(%s) of a request that exists, %s", reqid,
                     has ? "not this task's own with FROM" : "without FROM");
            refuse(rq);
        }
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (resp2) {
        c->resp = INVREQ;
        c->resp2 = resp2;
    } else if (has && (len < 1 || len > 32763)) {
        c->resp = LENGERR;
    } else if (!listed("transactions.cfg", transid)) {
        c->resp = TRANSIDERR;
    } else if (termid[0] && !listed("terminals.cfg", termid)) {
        c->resp = TERMIDERR;
    } else if (injected("START", transid, &fresp, &fresp2)) {  /* #4049: a planned condition; nothing is started */
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (reused == 1) {
        c->resp = IOERR;
    } else if (is_time) {
        struct tm t;
        gmtime_r(&now, &t);
        t.tm_hour = 0;
        t.tm_min = 0;
        t.tm_sec = 0;
        at = timegm(&t) + hh * 3600 + mm * 60 + ss;
        if (hh <= 23 && at <= now) {
            if (now - at <= 6 * 3600) at = now;
            else at += 24 * 3600;
        }
    } else {
        at = now + hh * 3600 + mm * 60 + ss;
    }
    if (c->resp == NORMAL) {
        iso(at, expires, sizeof expires);
        if (reqid[0] && nown < 64) {
            snprintf(own[nown].reqid, sizeof own[nown].reqid, "%s", reqid);
            own[nown].expires = at;
            own[nown].data = has;
            own[nown++].cancelled = 0;
        }
    }
    if (hhmmss >= 0) snprintf(hhmm, sizeof hhmm, "%06d", hhmmss);
    if (flag_word(flags, "RTRANSID")) hexarg(named, sizeof named, "rtransid", c->rtran, 4);
    if (flag_word(flags, "RTERMID")) hexarg(named + strlen(named), sizeof named - strlen(named), "rtermid", c->rterm, 4);
    if (flag_word(flags, "QUEUE")) hexarg(named + strlen(named), sizeof named - strlen(named), "queue", c->rqueue, 8);
    snprintf(ev, sizeof ev, "START transid=%s termid=%s %s=%s reqid=%s protect=%d resp=%d resp2=%d expires=%s len=%d "
             "area=%d%s", transid, termid, is_time ? "time" : "interval", hhmm, reqid, protect, c->resp,
             c->resp == INVREQ ? resp2 : 0, expires, len, has, named);
    event(ev, has ? from : NULL, has && len > 0 && len <= 32763 ? len : 0);  /* FROM as given, whatever the outcome */
    return 0;
}

/* RETRIEVE [INTO LENGTH(c->len)] [RTRANSID RTERMID QUEUE] (GG-FLAGS: INTO and the options named; IBM, EXEC CICS
 * RETRIEVE): the next data record of the requests the task was started for, in expiry order -- retrieve_NNN.bin
 * its FROM data, retrieve_NNN.opt (#4270, when the START gave RTRANSID / RTERMID / QUEUE or no FROM) its other data
 * options. ENDDATA when none is left (also for a task no START started); ENVDEFERR when the command names RTRANSID
 * / RTERMID / QUEUE and the record's START did not give it ("occurs when a RETRIEVE command specifies an option not
 * specified by the corresponding START command"); else the data truncated with LENGERR when longer than LENGTH,
 * which is then set to the record's length, and the values asked for into GG-RTRAN / GG-RTERM / GG-RQUEUE. Refused:
 * INTO for a record with no FROM, and any RETRIEVE after an ENVDEFERR (IBM does not say whether either is
 * ENVDEFERR, or whether that record was used up). */
static int retrieved = 0, envdeferr = 0;

static int opt_value(const char *opts, const char *key, char *out, int n) {
    char pat[16];
    const char *p;
    snprintf(pat, sizeof pat, " %s=", key);
    p = strstr(opts, pat);
    if (!p) return 0;
    p += strlen(pat);
    memset(out, ' ', (size_t)n);
    for (int i = 0; i < n && p[0] && p[1] && p[0] != ' ' && p[0] != '\n'; i++, p += 2) {
        unsigned v;
        sscanf(p, "%2x", &v);
        out[i] = (char)v;
    }
    return 1;
}

int GGCRTRV(gg_cics *c, char *into) {
    char path[4096], ev[256], buf[32768], opts[256] = " from=1", flags[41], named[128] = "";
    char rtran[4], rterm[4], rqueue[8];
    int n = -1, max = c->len, copied = 0, fresp, fresp2, has_from = 1;
    int want_into, want_tran, want_term, want_queue;
    trim(c->flags, 40, flags);
    want_into = flag_word(flags, "INTO");
    want_tran = flag_word(flags, "RTRANSID");
    want_term = flag_word(flags, "RTERMID");
    want_queue = flag_word(flags, "QUEUE");
    if (getenv("GGCICS_RUNCHILD")) refuse("RETRIEVE in a RUN TRANSID child task: not documented");
    if (envdeferr) refuse("RETRIEVE after ENVDEFERR: whether the record is still there is not documented");
    snprintf(path, sizeof path, "%s/retrieve_%03d.bin", dir_in(), retrieved + 1);
    c->resp2 = 0;
    if (injected("RETRIEVE", "-", &fresp, &fresp2)) {  /* #4049: a planned condition; nothing is retrieved */
        c->resp = fresp;
        c->resp2 = fresp2;
        snprintf(ev, sizeof ev, "RETRIEVE resp=%d len=%d copied=%d", c->resp, -1, 0);
        event(ev, into, 0);
        return 0;
    }
    FILE *f = fopen(path, "rb");
    {
        char opath[4096];
        snprintf(opath, sizeof opath, "%s/retrieve_%03d.opt", dir_in(), retrieved + 1);
        FILE *o = fopen(opath, "r");
        if (o) {
            opts[0] = ' ';
            if (!fgets(opts + 1, sizeof opts - 1, o)) opts[1] = '\0';
            fclose(o);
            has_from = strstr(opts, " from=1") != NULL;
        } else if (!f) {
            has_from = -1;  /* no record */
        }
    }
    if (has_from < 0) {
        c->resp = ENDDATA;
    } else {
        int t = opt_value(opts, "rtransid", rtran, 4), m = opt_value(opts, "rtermid", rterm, 4);
        int q = opt_value(opts, "queue", rqueue, 8);
        if (want_into && !has_from) {
            if (f) fclose(f);
            refuse("RETRIEVE INTO the record of a START with no FROM: whether that is ENVDEFERR is not documented");
        }
        if ((want_tran && !t) || (want_term && !m) || (want_queue && !q)) {
            if (f) fclose(f);
            f = NULL;
            envdeferr = 1;
            c->resp = ENVDEFERR;
        } else {
            n = 0;
            if (f) {
                n = (int)fread(buf, 1, sizeof buf, f);
                fclose(f);
                f = NULL;
            }
            retrieved++;
            c->resp = NORMAL;
            if (want_into) {
                copied = n < max ? n : (max > 0 ? max : 0);
                memcpy(into, buf, (size_t)copied);
                c->resp = n > max ? LENGERR : NORMAL;
                c->len = n;
            }
            if (want_tran) {
                memcpy(c->rtran, rtran, 4);
                hexarg(named, sizeof named, "rtransid", rtran, 4);
            }
            if (want_term) {
                memcpy(c->rterm, rterm, 4);
                hexarg(named + strlen(named), sizeof named - strlen(named), "rtermid", rterm, 4);
            }
            if (want_queue) {
                memcpy(c->rqueue, rqueue, 8);
                hexarg(named + strlen(named), sizeof named - strlen(named), "queue", rqueue, 8);
            }
        }
    }
    if (f) fclose(f);
    if (c->resp != NORMAL && c->resp != LENGERR) n = -1;
    snprintf(ev, sizeof ev, "RETRIEVE resp=%d len=%d copied=%d into=%d%s", c->resp, n, copied, want_into, named);
    event(ev, into, copied);
    return 0;
}

/* #4270 slice 2: RUN TRANSID(name1) CHILD(child) (IBM, EXEC CICS RUN TRANSID): it "starts a task on the local
 * system ... The started task (child task) runs asynchronously with the starting task", and CICS places "the child
 * token that represents the child task" in CHILD's 16-character area. TRANSIDERR RESP2 1 for a transaction the CSD
 * does not define. The event is the runner's: its scheduler runs the child as a non-terminal task once this task has
 * ended. The token's bytes are the harness's own (IBM does not document them), as CicsTask.runTransid makes them. */
static int nchildren = 0;

int GGCRUNT(gg_cics *c, char *child) {
    char transid[9], ev[96], token[17];
    trim(c->name1, 8, transid);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!listed("transactions.cfg", transid)) {
        c->resp = TRANSIDERR;
        c->resp2 = 1;
    } else {
        snprintf(token, sizeof token, "GGCHILD%09d", ++nchildren);
        memcpy(child, token, 16);
    }
    snprintf(ev, sizeof ev, "RUN transid=%s resp=%d resp2=%d", transid, c->resp, c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* CANCEL REQID(qname) (IBM, EXEC CICS CANCEL): NORMAL for a request that has not expired, NOTFND
 * when none matches ("fails to match an unexpired interval control command"). */
int GGCCNCL(gg_cics *c) {
    char reqid[17], path[4096], line[128], word[64], ev[96];
    long expires;
    time_t now = now_epoch();
    int found = 0, fresp, fresp2;
    trim(c->qname, 8, reqid);
    if (injected("CANCEL", reqid, &fresp, &fresp2)) {  /* #4049: a planned condition; nothing is cancelled */
        c->resp = fresp;
        c->resp2 = fresp2;
        snprintf(ev, sizeof ev, "CANCEL reqid=%s resp=%d", reqid, c->resp);
        event(ev, NULL, 0);
        return 0;
    }
    for (int i = 0; i < nown && !found; i++) {
        if (!own[i].cancelled && strcmp(own[i].reqid, reqid) == 0 && own[i].expires > now) {
            own[i].cancelled = found = 1;
        }
    }
    snprintf(path, sizeof path, "%s/requests.cfg", dir_in());
    FILE *f = found ? NULL : fopen(path, "r");
    while (f && !found && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s %ld", word, &expires) == 2 && strcmp(word, reqid) == 0 && expires > now) found = 1;
    }
    if (f) fclose(f);
    c->resp = found ? NORMAL : NOTFND;
    c->resp2 = 0;
    snprintf(ev, sizeof ev, "CANCEL reqid=%s resp=%d", reqid, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* A LINKed program's result: the COMMAREA it leaves in its caller's storage, written as commarea.out when the task
 * ends (the driver calls this after the program, whether it RETURNed or GOBACKed). */
int GGCAOUT(const char *ca, int len) {
    char path[3000];
    snprintf(path, sizeof path, "%s/commarea.out", dir_out());
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    if (len > 0) fwrite(ca, 1, (size_t)len, f);
    fclose(f);
    return 0;
}

/* GET COUNTER(qname) POOL(name1) (IBM CICS TS, GET COUNTER): the named counter's current value in GG-NUM, then the
 * counter is one more. The region's counters are $GGCICS_DIR/counters.cfg ("POOL NAME VALUE", POOL "-" for none),
 * rewritten after each GET, so a later task of the scenario sees the next value; a counter not there is NOTFND. */
int GGCGCNT(gg_cics *c) {
    char want[17], pool[9], path[4096], line[256], p[64], n[64], ev[128];
    long v, got = -1;
    char lines[64][128];
    int nl = 0;
    trim(c->qname, 16, want);
    trim(c->name1, 8, pool);
    if (!pool[0]) strcpy(pool, "-");
    snprintf(path, sizeof path, "%s/counters.cfg", dir_in());
    FILE *f = fopen(path, "r");
    while (f && nl < 64 && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s %63s %ld", p, n, &v) != 3) continue;
        if (got < 0 && strcmp(p, pool) == 0 && strcmp(n, want) == 0) {
            got = v;
            v++;
        }
        snprintf(lines[nl++], sizeof lines[0], "%s %s %ld\n", p, n, v);
    }
    if (f) fclose(f);
    c->resp2 = 0;
    if (got < 0) {
        c->resp = NOTFND;
    } else {
        c->resp = NORMAL;
        c->num = (int)got;
        f = fopen(path, "w");
        for (int i = 0; f && i < nl; i++) fputs(lines[i], f);
        if (f) fclose(f);
    }
    snprintf(ev, sizeof ev, "GET-COUNTER pool=%s counter=%s resp=%d", pool, want, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* The program returned to the driver without a RETURN / XCTL / ABEND. */
int GGCEND(gg_cics *c) {
    (void)c;
    /* the task's program GOBACKed with no RETURN / XCTL / ABEND: at the highest level that GOBACK is the
     * RETURN (no TRANSID, no COMMAREA), as GGCPEND has it for a task run through GGCRUN */
    if (!ended) return_event("", NULL, 0);
    return 0;
}
