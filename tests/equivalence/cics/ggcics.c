/*
 * #3754: the stub CICS runtime of the equivalence harness. A translated program
 * (tests/tools/equivalence_cics.py) CALLs these in place of each EXEC CICS
 * command; the harness driver CALLs GGCLOAD / GGCEND around the task.
 *
 * Inputs come from $GGCICS_DIR:
 *   commarea.in           the COMMAREA the task starts with (its length is EIBCALEN)
 *   channel.cfg           #4270 (X24): the channel the task starts with (GGCCHIN): its name, then
 *                         `NAME BIT|CHAR HEX` per container ('-' for no bytes); GGCEND writes the
 *                         current channel's containers at task end to $GGCICS_OUT/containers.out
 *   commarea.exact        #4270 (X23): the COMMAREA is exactly that long (a scenario's stated
 *                         length, shorter than the record): GGCAREA puts it before a guard page
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
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "ggcics_spec.h" /* #4270 spec PR 4: DFHRESP_* and condition_abcode, generated from gitgalaxy/standards/cics */
#ifdef _WIN32
#include <direct.h>
#define MKDIR(p) _mkdir(p) /* MinGW / MSVC: no mode argument */
#define RMDIR(p) _rmdir(p) /* #4836: the C runtime's remove() deletes files only on Windows */
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
#define RMDIR(p) rmdir(p)
#include <signal.h>   /* #4270 (X23): GGCAREA's guard page */
#include <sys/mman.h>
#include <sys/wait.h> /* #4950: a RUN TRANSID child, run as a process of its own */
#include <unistd.h>
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
    char as[16], tochan[16];  /* #4951: MOVE CONTAINER's AS and TOCHANNEL */
} gg_cics;

/* the conditions the stub raises, by their short names; the numbers are the spec's (ggcics_spec.h) */
enum { NORMAL = DFHRESP_NORMAL, NOTFND = DFHRESP_NOTFND, LENGERR = DFHRESP_LENGERR, FILENOTFOUND = DFHRESP_FILENOTFOUND,
       MAPFAIL = DFHRESP_MAPFAIL, ITEMERR = DFHRESP_ITEMERR, QIDERR = DFHRESP_QIDERR, INVREQ = DFHRESP_INVREQ,
       PGMIDERR = DFHRESP_PGMIDERR, ENDDATA = DFHRESP_ENDDATA, DUPREC = DFHRESP_DUPREC, DUPKEY = DFHRESP_DUPKEY, ENDFILE = DFHRESP_ENDFILE, ILLOGIC = DFHRESP_ILLOGIC,
       END = DFHRESP_END, TOKENERR = DFHRESP_TOKENERR, CONTAINERERR = DFHRESP_CONTAINERERR, CHANNELERR = DFHRESP_CHANNELERR,
       SUPPRESSED = DFHRESP_SUPPRESSED };

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
static void refuse(const char *what);

/* #4950 (X18, R1): a RUN TRANSID child its parent's wait dispatched ($GGCICS_CHILDOF) records only the end of its
 * task and the programs it runs; any other event is a region resource's or a terminal's, whose order against its
 * parent's and its siblings' commands is not modelled. */
static void child_may(const char *line, int verb) {
    static const char *const ok[] = {"RETURN", "ABEND", "LINK", "XCTL"};
    char msg[160];
    if (!getenv("GGCICS_CHILDOF")) return;
    for (size_t i = 0; i < sizeof ok / sizeof ok[0]; i++)
        if ((int)strlen(ok[i]) == verb && strncmp(line, ok[i], (size_t)verb) == 0) return;
    snprintf(msg, sizeof msg, "a RUN TRANSID child's %.*s (a region resource or a terminal): its order against its "
             "parent's and its siblings' commands", verb, line);
    refuse(msg);
}

/* One line of events.txt (the verb, then the issuing program); with `data`, its bytes as NNN.bin. */
static void event(const char *line, const char *data, int len) {
    char path[4096];
    const char *rest = strchr(line, ' ');
    int verb = rest ? (int)(rest - line) : (int)strlen(line);
    child_may(line, verb);
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

/* #4270 (oracle_assumptions.md X23): a COMMAREA of a stated length (commarea.exact) is exactly that many bytes
 * -- the caller passed no more. GGCAREA copies it to the end of a page followed by an inaccessible one, so a
 * reference past EIBCALEN, read or write, faults at that statement: the run stops there as not modelled (on z/OS
 * the program sees whatever storage follows the area) and the task is judged up to it, as the det port refuses
 * the same reference (DetCics.PastFrom). Any other COMMAREA stays in the driver's own area (*area unchanged). */
static void refuse(const char *what);
static int uctranst_set = 0; /* #4415: a SET TERMINAL UCTRANST changed the task's terminal (X26) */
#ifndef _WIN32
static char *guard_page;
static size_t guard_size;
static void past_eibcalen(int sig, siginfo_t *info, void *ctx) {
    char *at = (char *)info->si_addr;
    (void)ctx;
    if (at >= guard_page && at < guard_page + guard_size) refuse("COMMAREA past EIBCALEN");
    signal(sig, SIG_DFL); /* any other fault is the stub's or the program's own: as it was */
    raise(sig);
}
#endif

int GGCAREA(char **area, int len) {
    char path[4096];
    struct stat st;
    snprintf(path, sizeof path, "%s/commarea.exact", dir_in());
    if (len <= 0 || stat(path, &st) != 0) return 0;
#ifdef _WIN32
    refuse("a stated COMMAREA length on this platform");
#else
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    size_t body = ((size_t)len + page - 1) / page * page;
    char *base = mmap(NULL, body + page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (base == MAP_FAILED || mprotect(base + body, page, PROT_NONE) != 0) refuse("a guarded COMMAREA");
    guard_page = base + body;
    guard_size = page;
    memcpy(guard_page - len, *area, (size_t)len);
    *area = guard_page - len;
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = past_eibcalen;
    sa.sa_flags = SA_SIGINFO;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
#endif
    return 0;
}

/* #4023 follow-up: the planned condition of this command on this file, if faults.cfg plans one. Every
 * command counts (per task: a task is one process), whether or not it faults. */
static int fault_counts[32];
static char fault_keys[32][40];
/* #4623: a planned DUPKEY is not a failure of the read. IBM retrieves the record through the non-unique alternate
 * index and answers DUPKEY (RESP2 140) because another record with the same key follows. So injected() holds it
 * back (the read runs) and dupkey_apply() turns the NORMAL of a read that found its record into it. */
static struct { int on, n, resp, resp2; char cmd[16], file[32]; } dupkey;
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
    dupkey.on = 0;
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
    if (hit && *resp == DFHRESP_DUPKEY) {
        dupkey.on = 1; dupkey.n = n; dupkey.resp = *resp; dupkey.resp2 = *resp2;
        snprintf(dupkey.cmd, sizeof dupkey.cmd, "%s", cmd);
        snprintf(dupkey.file, sizeof dupkey.file, "%s", file);
        return 0;
    }
    if (hit) {
        snprintf(path, sizeof path, "%s/faults.txt", dir_out());
        FILE *log = fopen(path, "a");
        if (log) { fprintf(log, "%s %s %d %d %d\n", cmd, file, n, *resp, *resp2); fclose(log); }
    }
    return hit;
}

static void dupkey_apply(gg_cics *c) {
    if (!dupkey.on) return;
    dupkey.on = 0;
    if (c->resp != NORMAL) return;  /* no record was retrieved: nothing for DUPKEY to qualify */
    c->resp = dupkey.resp;
    c->resp2 = dupkey.resp2;
    char path[3000];
    snprintf(path, sizeof path, "%s/faults.txt", dir_out());
    FILE *log = fopen(path, "a");
    if (log) { fprintf(log, "%s %s %d %d %d\n", dupkey.cmd, dupkey.file, dupkey.n, c->resp, c->resp2); fclose(log); }
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

/* #5078 (X52): READ UPDATE TOKEN(d) holds a record under a token of its own (IBM, EXEC CICS READ: "a unique identifier
 * for this READ UPDATE request ... for use in associating a subsequent REWRITE or DELETE (or UNLOCK) request with the
 * record returned"), however many are held, on any file. The ids count from 1 per task (their value is IBM's to choose:
 * ASSUMED). REWRITE / DELETE / UNLOCK TOKEN spend the token; one that matches no token in use (never issued, spent,
 * or another file's) is INVREQ RESP2 47 ("a token whose value cannot be matched against any token in use"). */
#define MAX_TOKENS 64
static struct { int id; char name[9]; char key[256]; int klen; } tokens[MAX_TOKENS];
static int next_token = 1;

static int token_hold(const char *file, const char *key, int klen) {
    for (int i = 0; i < MAX_TOKENS; i++) {
        if (tokens[i].id == 0) {
            tokens[i].id = next_token++;
            snprintf(tokens[i].name, sizeof tokens[i].name, "%s", file);
            memcpy(tokens[i].key, key, (size_t)(klen < 256 ? klen : 256));
            tokens[i].klen = klen < 256 ? klen : 256;
            return tokens[i].id;
        }
    }
    refuse("READ UPDATE TOKEN: more than 64 records held");
    return 0;
}

static int token_find(int id, const char *file) {
    for (int i = 0; id > 0 && i < MAX_TOKENS; i++) {
        if (tokens[i].id == id && (!file || strcmp(tokens[i].name, file) == 0)) return i;
    }
    return -1;
}

static void release(const char *file) {
    if (!file) for (int i = 0; i < MAX_TOKENS; i++) tokens[i].id = 0;  /* a SYNCPOINT ends every hold, tokens too */
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
static long long find_key(const char *path, int reclen, int keyoff, int klen, const char *key) {
    FILE *data = fopen(path, "rb");
    char *rec = malloc((size_t)reclen);
    long long at = -1, i = 0;
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
    } else if (strstr(c->flags, "TOKEN") ? token_find(c->num, want) < 0 : !held_key(want, key, klen)) {
        c->resp = INVREQ;
        if (strstr(c->flags, "TOKEN")) c->resp2 = 47;
    } else if (strstr(c->flags, "TOKEN") && (tokens[token_find(c->num, want)].klen != klen
                                              || memcmp(tokens[token_find(c->num, want)].key, key, (size_t)klen) != 0)) {
        refuse("REWRITE TOKEN FROM: a key other than the held record's");
    } else {
        long long at = find_key(path, reclen, keyoff, klen, key);
        if (at < 0) {
            c->resp = NOTFND;
        } else {
            uow_save(path);
            char *rec = malloc((size_t)reclen);
            memset(rec, ' ', (size_t)reclen);
            memcpy(rec, from, (size_t)(fromlen < reclen ? fromlen : reclen));
            FILE *data = fopen(path, "r+b");
            if (data && rec && fseek(data, (long)(at * reclen), SEEK_SET) == 0) fwrite(rec, 1, (size_t)reclen, data);
            if (data) fclose(data);
            free(rec);
            if (strstr(c->flags, "TOKEN")) tokens[token_find(c->num, want)].id = 0;
            else release(want);
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

static void browses_end(void); /* #4951 */

/* SYNCPOINT (flags empty: commit) / SYNCPOINT ROLLBACK (flags ROLLBACK: undo since the last SYNCPOINT). */
int GGCSYNC(gg_cics *c) {
    int rollback = strstr(c->flags, "ROLLBACK") != NULL;
    uow_end(rollback);
    browses_end(); /* #4951: a container browse token does not survive a sync point */
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
static char *load_records(const char *path, int reclen, long long *n);
/* #4270 READ GTEQ / GENERIC (GG-FLAGS 'GTEQ' / 'GENERIC'; oracle_assumptions.md X22), IBM, EXEC CICS READ: GENERIC --
 * "the search key is a generic key whose length is specified in the KEYLENGTH option" (keylen); GTEQ -- "if the search
 * for a record that has the same key (complete or generic) as that specified in the RIDFLD option is unsuccessful,
 * the first record that has a greater key is retrieved". Of the records whose key's first `cmp` bytes equal RIDFLD's
 * (or, GTEQ, are greater), the first in key order (the browse's byte order); -1 when none: NOTFND, RESP2 80. A GENERIC
 * KEYLENGTH not shorter than the key (INVREQ RESP2 25) or not above zero (42; zero undocumented) stops the run. */
static long long read_search(gg_cics *c, const char *path, int reclen, int keyoff, int klen, const char *ridfld,
                             int keylen, char **all) {
    int gteq = strstr(c->flags, "GTEQ") != NULL, generic = strstr(c->flags, "GENERIC") != NULL;
    if (generic && (keylen >= klen || keylen <= 0))
        refuse("READ GENERIC KEYLENGTH not shorter than the key or not above zero");
    int cmp = generic ? keylen : klen;
    long long n, best = -1;
    *all = load_records(path, reclen, &n);
    for (long long i = 0; *all && i < n; i++) {
        int d = memcmp(*all + i * reclen + keyoff, ridfld, (size_t)cmp);
        if (d < 0 || (d > 0 && !gteq)) continue;
        if (best < 0 || memcmp(*all + i * reclen + keyoff, *all + best * reclen + keyoff, (size_t)klen) < 0) best = i;
    }
    return best;
}

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
            int search = strstr(c->flags, "GTEQ") || strstr(c->flags, "GENERIC");
            char *found = NULL;
            long long at = search ? read_search(c, path, reclen, keyoff, klen, ridfld, keylen, &found) : -1;
            if (search && at < 0) c->resp2 = 80;
            FILE *data = search ? NULL : fopen(path, "rb");
            char *rec = malloc((size_t)reclen);
            if (search && at >= 0 && rec) memcpy(rec, found + at * reclen, (size_t)reclen);
            free(found);
            int cmp = keylen < klen ? keylen : klen;
            while (rec && ((search && at >= 0) || (data && fread(rec, 1, (size_t)reclen, data) == (size_t)reclen))) {
                if (search || memcmp(rec + keyoff, ridfld, (size_t)cmp) == 0) {
                    int max = c->len, moved = reclen < max ? reclen : max;
                    if (max < 0) refuse("READ LENGTH (negative)");
                    if (moved > intolen) refuse("READ INTO LENGTH: a record moved past INTO");
                    if (reclen > max && strstr(c->flags, "UPDATE"))
                        refuse("READ UPDATE LENGERR (whether the record is held)");
                    memcpy(into, rec, (size_t)moved);
                    c->resp = reclen > max ? LENGERR : NORMAL;
                    c->resp2 = reclen > max ? 11 : 0;
                    c->len = reclen;
                    if (c->resp == NORMAL && strstr(c->flags, "TOKEN")) c->num = token_hold(want, rec + keyoff, klen);
                    else if (c->resp == NORMAL && strstr(c->flags, "UPDATE")) hold(want, rec + keyoff, klen);
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
    dupkey_apply(c);
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
    unsigned long long rstart, rlast;  /* an RBA browse (#4213): the STARTBR's RBA, the last RBA read */
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
static char *load_records(const char *path, int reclen, long long *n) {
    FILE *data = fopen(path, "rb");
    char *all = NULL;
    *n = 0;
    if (!data) return NULL;
    fseek(data, 0, SEEK_END);
    long long size = ftell(data);
    fseek(data, 0, SEEK_SET);
    all = malloc((size_t)(size > 0 ? size : 1));
    if (all) *n = (long long)fread(all, 1, (size_t)size, data) / reclen;
    fclose(data);
    return all;
}

/* The record whose key is the least key > `key` (strict), >= (or_equal), or the greatest < `key` (below); -1 when
 * none. With `exact`, only a record whose key equals `key`. */
static long long pick(const char *all, long long n, int reclen, int keyoff, int klen, const char *key, int mode) {
    long long best = -1;
    for (long long i = 0; i < n; i++) {
        int c = memcmp(all + i * reclen + keyoff, key, (size_t)klen);
        const char *bk = best >= 0 ? all + best * reclen + keyoff : NULL;
        if (mode == 0 && c == 0) return i;                                                      /* exact */
        if (mode == 1 && c >= 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) < 0)) best = i;  /* >= */
        if (mode == 2 && c > 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) < 0)) best = i;   /* > */
        if (mode == 3 && c < 0 && (!bk || memcmp(all + i * reclen + keyoff, bk, (size_t)klen) > 0)) best = i;   /* < */
    }
    return best;
}

static long long pick_last(const char *all, long long n, int reclen, int keyoff, int klen) {
    long long best = -1;
    for (long long i = 0; i < n; i++) {
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
static unsigned long long rba_get(const char *rid) {
    const unsigned char *u = (const unsigned char *)rid;
    return ((unsigned long long)u[0] << 24) | ((unsigned long long)u[1] << 16) | ((unsigned long long)u[2] << 8) | u[3];
}

static void rba_put(char *rid, unsigned long long v) {
    rid[0] = (char)((v >> 24) & 0xFF);
    rid[1] = (char)((v >> 16) & 0xFF);
    rid[2] = (char)((v >> 8) & 0xFF);
    rid[3] = (char)(v & 0xFF);
}

#define RBA_END 0xFFFFFFFFULL

/* The record (0-based) at `rba`; refused when no record starts there. */
static long long rba_record(const char *verb, const char *want, unsigned long long rba, int reclen, long long n) {
    char why[120];
    if (rba % (unsigned long long)reclen == 0 && rba / (unsigned long long)reclen < (unsigned long long)n) {
        return (long long)(rba / (unsigned long long)reclen);
    }
    snprintf(why, sizeof why, "%s RBA %llu on %s: no record starts there", verb, rba, want);
    refuse(why);
    return -1;
}

static void rba_event(const char *verb, const char *file, unsigned long long rba, int resp) {
    char ev[120];
    snprintf(ev, sizeof ev, "%s file=%s rba=%llu resp=%d", verb, file, rba, resp);
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
    unsigned long long rba = rba_get(ridfld);
    if (s >= 0 && br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 33;
    } else {
        long long n;
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
    unsigned long long rba = rba_get(ridfld), was = br[s].have_last ? br[s].rlast : br[s].rstart;
    int changed = rba != was;
    long long n, at;
    char *all = load_records(path, reclen, &n);
    if (dir > 0) {
        if (br[s].dir == 0 && !br[s].last && !changed) at = rba_record(verb, want, rba, reclen, n);
        else if (br[s].dir == 1 && !changed) at = (long long)(rba / (unsigned long long)reclen) + 1;
        else if (rba == RBA_END) at = -1;
        else at = rba_record(verb, want, rba, reclen, n);
        if (at >= n) at = -1;
        c->resp = at < 0 ? ENDFILE : NORMAL;
        if (at < 0) c->resp2 = 90;
    } else {
        if (rba == RBA_END && (br[s].dir == 0 || changed)) at = n - 1;
        else if (br[s].dir == -1 && !changed) at = (long long)(rba / (unsigned long long)reclen) - 1;
        else at = rba_record(verb, want, rba, reclen, n);
        c->resp = at < 0 ? ENDFILE : NORMAL;
        if (at < 0) c->resp2 = 90;
    }
    if (at >= 0) {
        const char *rec = all + at * reclen;
        memcpy(into, rec, (size_t)(reclen < intolen ? reclen : intolen));
        rba = (unsigned long long)at * (unsigned long long)reclen;
        rba_put(ridfld, rba);
        br[s].rlast = rba;
        br[s].have_last = 1;
        br[s].dir = dir;
        if (reclen > intolen) { c->resp = LENGERR; c->resp2 = 11; }
    }
    free(all);
    dupkey_apply(c);
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
        long long n;
        char *all = load_records(path, reclen, &n);
        long long at = last ? 0 : pick(all, n, reclen, keyoff, klen, key, equal ? 0 : 1);
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
        long long n, at;
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
    dupkey_apply(c);
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
 * holds -- INVREQ when none is held; NOTFND when the key is not there. #4771: GG-FLAGS 'GENERIC', every record whose key
 * starts with RIDFLD's first `keylen` bytes (NOTFND RESP2 80 when none; a KEYLENGTH not shorter than the key, or not above
 * zero, refused: IBM's INVREQ 25 / 42, X22). */
int GGCDELT(gg_cics *c, char *ridfld, int keylen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int by_tok = strstr(c->flags, "TOKEN") != NULL;  /* #5078: the record a READ UPDATE TOKEN holds (GG-NUM) */
    int by_hold = strstr(c->flags, "HELD") != NULL || by_tok;
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
    if (strstr(c->flags, "GENERIC") && (keylen <= 0 || keylen >= klen)) refuse("DELETE GENERIC KEYLENGTH");
    char key[256];
    memset(key, 0, sizeof key);
    int s = -1;
    if (by_tok) {
        int ti = token_find(c->num, want);
        if (ti < 0) {
            c->resp = INVREQ;
            c->resp2 = 47;
            file_event("DELETE", want, ridfld, 0, c->resp);
            return 0;
        }
        memcpy(key, tokens[ti].key, (size_t)tokens[ti].klen);
        s = ti;
    } else if (by_hold) {
        for (int i = 0; i < MAX_FILES; i++) if (held[i].name[0] && strcmp(held[i].name, want) == 0) { s = i; break; }
        if (s >= 0) memcpy(key, held[s].key, (size_t)held[s].klen);
    } else {
        memcpy(key, ridfld, (size_t)(keylen < klen ? keylen : klen));
    }
    long long n;
    char *all = load_records(path, reclen, &n);
    if (strstr(c->flags, "GENERIC")) { /* #4771 (X22): every record whose key starts with the KEYLENGTH-byte generic key */
        long long gone = 0;
        uow_save(path);
        FILE *data = fopen(path, "wb");
        for (long long i = 0; data && i < n; i++) {
            if (memcmp(all + i * reclen + keyoff, key, (size_t)keylen) == 0) gone++;
            else fwrite(all + i * reclen, 1, (size_t)reclen, data);
        }
        if (data) fclose(data);
        c->resp = gone ? NORMAL : NOTFND;
        c->resp2 = gone ? 0 : 80;
        free(all);
        file_event("DELETE", want, key, keylen, c->resp);
        return 0;
    }
    long long at = (by_hold && s < 0) ? -1 : pick(all, n, reclen, keyoff, keylen < klen && !by_hold ? keylen : klen, key, 0);
    if (by_hold && s < 0) {
        c->resp = INVREQ;
    } else if (at < 0) {
        c->resp = NOTFND;
        c->resp2 = 80;
    } else {
        uow_save(path);
        FILE *data = fopen(path, "wb");
        for (long long i = 0; data && i < n; i++) if (i != at) fwrite(all + i * reclen, 1, (size_t)reclen, data);
        if (data) fclose(data);
        if (by_tok) tokens[s].id = 0;
        else if (by_hold) release(want);
        c->resp = NORMAL;
    }
    free(all);
    file_event("DELETE", want, key, klen, c->resp);
    return 0;
}

/* UNLOCK FILE(name1) TOKEN(GG-NUM) (#5078, X52): releases the record a READ UPDATE TOKEN holds; INVREQ RESP2 47 for a
 * token matching none in use. UNLOCK without TOKEN is not modelled (translate refuses it). */
int GGCUNLK(gg_cics *c) {
    char want[9], path[3000];
    int reclen, keyoff, klen;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        return 0;
    }
    int ti = token_find(c->num, want);
    if (ti < 0) {
        c->resp = INVREQ;
        c->resp2 = 47;
    } else {
        tokens[ti].id = 0;
        c->resp = NORMAL;
    }
    return 0;
}

/* #4270 (X31): SEND MAP / RECEIVE MAP for a map the mapset does not hold. IBM CICS TS, abend ABM0: "The map specified for
 * a basic mapping support (BMS) request could not be located"; "The transaction is abnormally terminated with a CICS
 * transaction dump". Neither command lists a condition for it, so RESP / HANDLE CONDITION do not see it (a HANDLE ABEND
 * exit does). The mapsets and their maps are a fact the run states, $GGCICS_MAPSETS = `MAPSET=MAP,MAP;MAPSET=MAP`
 * (the cics-crucible runner takes them from the case's maps); a mapset not stated is not checked. 1: the task
 * abended -- c->go_to says where to go on (an exit label at this level, else -1: leave the program). */
static void abend(gg_cics *c, const char *code, const char *cause, int cond, int cancel);

static int map_not_found(gg_cics *c, const char *map, const char *mapset) {
    const char *env = getenv("GGCICS_MAPSETS");
    size_t ml = strlen(mapset), nl = strlen(map);
    c->go_to = 0;
    for (const char *p = env; p && *p;) {
        const char *end = strchr(p, ';');
        size_t len = end ? (size_t)(end - p) : strlen(p);
        if (len > ml && strncmp(p, mapset, ml) == 0 && p[ml] == '=') {
            int held = 0;
            for (const char *q = p + ml + 1; q < p + len;) {
                const char *comma = memchr(q, ',', (size_t)(p + len - q));
                size_t n = comma ? (size_t)(comma - q) : (size_t)(p + len - q);
                if (n == nl && strncmp(q, map, nl) == 0) held = 1;
                q += n + 1;
            }
            if (held) return 0;
            abend(c, "ABM0", "system", 0, 0);
            return 1;
        }
        p = end ? end + 1 : NULL;
    }
    return 0;
}

/* RECEIVE MAP(name1) MAPSET(name2) INTO: the scenario's recorded map input. */
int GGCRECV(gg_cics *c, char *into, int intolen) {
    char map[9], mapset[9], path[4096], ev[128];
    if (uctranst_set) refuse("a terminal RECEIVE after SET TERMINAL UCTRANST");
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    if (map_not_found(c, map, mapset)) return 0;
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
    if (uctranst_set) refuse("a terminal RECEIVE after SET TERMINAL UCTRANST");
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
    if (map_not_found(c, map, mapset)) return 0;
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
    /* #4768 (X34): STATUS, the definition's CVDA -- ENABLED (23), the DEFINE PROGRAM default; no run states a DISABLED one */
    if (c->resp == NORMAL) c->num = 23;
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
    int gen;                 /* #4951: which LINKed program this level runs (0: the task's first), the owner of its browses */
} level;

static level levels[MAX_LEVELS];
static int link_gen = 0; /* #4951: the last LINK's generation */
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

/* RETURN TRANSID(name1) [COMMAREA LENGTH: GG-ITEM 1] IMMEDIATE (#4270, register X27; IBM, EXEC CICS RETURN): the next task
 * is attached at once, ahead of any terminal input, with the COMMAREA. INVREQ RESP2 1 for a task with no terminal
 * ($GGCICS_FACILITY empty; unstated: refused), INVREQ RESP2 2 below the highest level, LENGERR RESP2 11 for a length
 * outside 0-32763 -- the program then goes on. The two INVREQs together are not stated by IBM: refused. */
int GGCRETI(gg_cics *c, char *commarea, int len) {
    char transid[9], ev[128];
    const char *own = getenv("GGCICS_FACILITY");
    int has = c->item != 0, no_terminal;
    trim(c->name1, 8, transid);
    if (!own) refuse("RETURN IMMEDIATE: the task's terminal is not stated for this task");
    no_terminal = !own[0];
    if (no_terminal && lvl > 0)
        refuse("RETURN IMMEDIATE below the highest level in a task with no terminal: IBM lists INVREQ RESP2 1 and 2 "
               "for it and does not say which");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (lvl > 0) { c->resp = INVREQ; c->resp2 = 2; }
    else if (no_terminal) { c->resp = INVREQ; c->resp2 = 1; }
    else if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    if (c->resp != NORMAL) {
        snprintf(ev, sizeof ev, "RETURN level=%d transid=%s immediate=1 resp=%d resp2=%d", lvl + 1, transid, c->resp,
                 c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    levels[lvl].state = DONE;
    ended = 1;
    snprintf(ev, sizeof ev, "RETURN level=1 transid=%s len=%d immediate=1", transid, has ? len : 0);
    event(ev, has ? commarea : NULL, has && len > 0 ? len : 0);
    return 0;
}

static void xctl_next(const char *program, char *commarea, int len) {
    level *L = &levels[lvl];
    /* #4816 (X39): a LINKed program XCTLing with (part of) the area its caller passed: IBM does not say whether the
     * target then addresses that storage or a copy (XCTL COMMAREA: "the contents of the data-area are passed") */
    if (commarea && lvl > 0 && L->link_area && commarea >= L->link_area
        && commarea < L->link_area + L->link_len)
        refuse("XCTL passing the COMMAREA its LINK caller passed");
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
    long long n = 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (env) {
        n = strtoll(env, &end, 10);
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
    int has = c->item != 0, len = has ? c->len : 0, chan = 0, fresp, fresp2;
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
    else if (injected("LINK", program, &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; }  /* #4648: as XCTL's */
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
    L->gen = ++link_gen;
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
 * CHANNEL: the target). Containers are not events: a program shows what it got by what it does -- and
 * (#4270, X24) the containers a task leaves on its first program's current channel are compared at its end. */
#define MAX_CHANNELS 64
#define MAX_CONTAINERS 64
typedef struct { char name[17]; int bit; char *data; int len; int used; long long order; } gg_container; /* order: creation order (#4951) */
typedef struct { char name[17]; gg_container c[MAX_CONTAINERS]; int shape; } gg_channel; /* shape: containers added + removed (#4951) */
static gg_channel chans[MAX_CHANNELS];
static int nchans = 0;

/* A channel / container name without its trailing blanks; one that is empty, has an embedded
 * blank, or more than 16 characters is refused (IBM's "illegal character" rules are not modelled). */
/* #4950: the characters IBM's PUT CONTAINER page allows in a CONTAINER / CHANNEL name ("The acceptable characters are
 * A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - and _. Leading and embedded blank characters are not permitted").
 * RUN TRANSID's page (channel_chars) lists three more -- & < and the not sign -- which this one omits: a name holding
 * one is refused (the two pages disagree), as CicsTask.illegalName does */
static const char name_chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$@#/%?!:|\"=,;>.-_";

/* `src` without its trailing blanks into `dst`; 1 when it holds a character outside IBM's set (a leading or embedded
 * blank included), else 0. A blank name, or one holding only IBM's set and & < or the not sign, is refused. */
static int cics_name_check(const char *src, char *dst, const char *what) {
    char msg[160];
    int disputed = 0;
    trim(src, 16, dst);
    if (!dst[0]) {
        snprintf(msg, sizeof msg, "%s name '%s'", what, dst);
        refuse(msg);
    }
    for (const char *p = dst; *p; p++) {
        if (strchr(name_chars, *p)) continue;
        if (strchr("&<\xac", *p)) { disputed = 1; continue; }
        return 1;
    }
    if (disputed) {
        snprintf(msg, sizeof msg, "%s name '%s' holds & < or a not sign: IBM's RUN TRANSID page allows them, its PUT "
                 "CONTAINER page does not", what, dst);
        refuse(msg);
    }
    return 0;
}

/* The name of a command whose page says nothing of an illegal one: refused (PUT CONTAINER alone has CHANNELERR RESP2 1
 * / CONTAINERERR RESP2 18, GGCPUTC) */
static void cics_name(const char *src, char *dst, const char *what) {
    char msg[96];
    if (cics_name_check(src, dst, what)) {
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

static long long container_seq = 0;

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
    free_slot->order = ++container_seq;
    ch->shape++;
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
    int bad_name = cics_name_check(c->qname, name, "container");
    int bad_chan = 0;
    if (strstr(flags, "CHANNEL")) {
        char chn[17];
        bad_chan = cics_name_check(c->chan, chn, "channel");
    }
    if (bad_name || bad_chan) {
        /* IBM: CHANNELERR RESP2 1 (CHANNEL), CONTAINERERR RESP2 18 (CONTAINER) "contains an illegal character or
         * combination of characters"; which it raises first of two of them, or of one and another condition, is not
         * documented */
        if (bad_name && bad_chan) refuse("PUT CONTAINER with an illegal CONTAINER and CHANNEL name: which condition IBM raises first is not documented");
        if (c->len < 0) refuse("PUT CONTAINER with an illegal name and a negative FLENGTH: which condition IBM raises first is not documented");
        if (bad_chan) { c->resp = CHANNELERR; c->resp2 = 1; return 0; }
        if (strstr(flags, "CHANNEL")) {
            char chn[17];
            trim(c->chan, 16, chn);
            if (!channel_named(chn, 0)) refuse("PUT CONTAINER with an illegal CONTAINER name and a channel not in scope: which condition IBM raises first is not documented");
        } else if (!levels[lvl].cur) {
            refuse("PUT CONTAINER with an illegal CONTAINER name and no channel: which condition IBM raises first is not documented");
        }
        c->resp = CONTAINERERR; c->resp2 = 18;
        return 0;
    }
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
    chans[ch - 1].shape++;
    return 0;
}

/* ---- #5005: DELETE CHANNEL and QUERY CHANNEL (IBM CICS TS, EXEC CICS DELETE CHANNEL, QUERY CHANNEL); the same semantics as
 * CicsTask (register X44). The channel's name is GG-CHAN. */

/* DELETE CHANNEL: the channel and its containers go from the program's scope; CHANNELERR RESP2 2 for one not in scope. The
 * current channel is refused: IBM's RESP2 4 / 5 / 6 all fit a channel the program was passed, and it ranks none. */
int GGCDELH(gg_cics *c) {
    char name[17];
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->chan, name, "channel");
    int ch = channel_named(name, 0);
    if (!ch) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    if (ch == levels[lvl].cur) refuse("DELETE CHANNEL of the current channel");
    for (int i = 0; i < MAX_CONTAINERS; i++) {
        if (chans[ch - 1].c[i].used) free(chans[ch - 1].c[i].data);
        memset(&chans[ch - 1].c[i], 0, sizeof chans[ch - 1].c[i]);
    }
    chans[ch - 1].shape++;
    level *L = &levels[lvl];
    for (int i = 0; i < L->nscope; i++) {
        if (L->scope[i] == ch) {
            for (int j = i; j + 1 < L->nscope; j++) L->scope[j] = L->scope[j + 1];
            L->nscope--;
            break;
        }
    }
    return 0;
}

/* QUERY CHANNEL: the number of containers into GG-NUM; CHANNELERR RESP2 2 for a channel not in scope. */
int GGCQCHN(gg_cics *c) {
    char name[17];
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->chan, name, "channel");
    int ch = channel_named(name, 0);
    if (!ch) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    int n = 0;
    for (int i = 0; i < MAX_CONTAINERS; i++) if (chans[ch - 1].c[i].used) n++;
    c->num = n;
    return 0;
}

/* ---- #4951: MOVE CONTAINER and the container browse (IBM CICS TS, EXEC CICS MOVE CONTAINER (CHANNEL), STARTBROWSE /
 * GETNEXT / ENDBROWSE CONTAINER (CHANNEL)); the same semantics as CicsTask (register X42). */

/* MOVE CONTAINER(GG-QNAME) AS(GG-AS) [CHANNEL: GG-CHAN] [TOCHANNEL: GG-TOCHAN]; GG-FLAGS: CHANNEL, TOCHAN. INVREQ RESP2 4
 * (CHANNEL or TOCHANNEL omitted, no current channel), CHANNELERR 2, CONTAINERERR 10, in that order; a move that
 * raises a condition changes nothing and creates no channel. The container keeps its data type. */
int GGCMOVC(gg_cics *c) {
    char flags[41], name[17], target[17], cn[17] = "", tn[17] = "";
    int from, to;
    trim(c->flags, 40, flags);
    int has_from = strstr(flags, "CHANNEL") != NULL, has_to = strstr(flags, "TOCHAN") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    cics_name(c->as, target, "container");
    if (has_from) { cics_name(c->chan, cn, "channel"); from = channel_named(cn, 0); }
    else from = levels[lvl].cur;
    if (has_to) { cics_name(c->tochan, tn, "channel"); to = channel_named(tn, 0); }
    else to = levels[lvl].cur;
    if ((!has_from || !has_to) && !levels[lvl].cur) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    if (!from) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    gg_container *src = container_named(&chans[from - 1], name, 0);
    if (!src) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    gg_container *dst = to ? container_named(&chans[to - 1], target, 0) : NULL;
    if (to == from && strcmp(name, target) == 0) refuse("MOVE CONTAINER onto itself");
    if (dst && dst->bit != src->bit) refuse("MOVE CONTAINER onto a container of the other data type");
    if (!to) to = channel_named(tn, 1);
    if (!dst) {
        dst = container_named(&chans[to - 1], target, 1);
        dst->bit = src->bit;
    } else {
        free(dst->data);
    }
    dst->data = src->data;
    dst->len = src->len;
    src->data = NULL;
    memset(src, 0, sizeof *src);
    chans[from - 1].shape++;
    return 0;
}

#define MAX_BROWSES 64
typedef struct { int token; int owner; int chan; int shape; int n; int next; char names[MAX_CONTAINERS][17]; } gg_browse;
static gg_browse browses[MAX_BROWSES];
static int browse_tokens = 0;

static gg_browse *browse_of(int token) {
    for (int i = 0; i < MAX_BROWSES; i++) {
        if (browses[i].token == token && token != 0 && browses[i].owner == levels[lvl].gen) return &browses[i];
    }
    return NULL;
}

static void browses_end(void) { memset(browses, 0, sizeof browses); }

/* STARTBROWSE CONTAINER [CHANNEL: GG-CHAN, GG-FLAGS CHANNEL]: the token into GG-NUM (1, 2, 3 ... per task). CHANNELERR
 * RESP2 2; no CHANNEL and no current channel is refused (IBM: the BTS form). The containers come in creation order. */
int GGCSBRC(gg_cics *c) {
    char flags[41], cn[17];
    int ch;
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(flags, "CHANNEL")) {
        cics_name(c->chan, cn, "channel");
        ch = channel_named(cn, 0);
        if (!ch) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    } else {
        ch = levels[lvl].cur;
        if (!ch) refuse("STARTBROWSE CONTAINER with no channel");
    }
    gg_browse *b = NULL;
    for (int i = 0; i < MAX_BROWSES && !b; i++) if (!browses[i].token) b = &browses[i];
    if (!b) refuse("more container browses than the stub holds");
    memset(b, 0, sizeof *b);
    b->token = ++browse_tokens;
    b->owner = levels[lvl].gen;
    b->chan = ch;
    b->shape = chans[ch - 1].shape;
    long long last = 0; /* the names, in creation order: each time the oldest after the last taken */
    for (;;) {
        gg_container *best = NULL;
        for (int i = 0; i < MAX_CONTAINERS; i++) {
            gg_container *k = &chans[ch - 1].c[i];
            if (k->used && k->order > last && (!best || k->order < best->order)) best = k;
        }
        if (!best) break;
        last = best->order;
        snprintf(b->names[b->n++], 17, "%s", best->name);
    }
    c->num = b->token;
    return 0;
}

/* GETNEXT CONTAINER BROWSETOKEN(GG-NUM): the next name into GG-QNAME (16 characters). END RESP2 2 past the last (again
 * on a later GETNEXT), TOKENERR 3 for a token that is not a current one of this program's. A container added to or
 * removed from the browsed channel since the start is refused. */
int GGCGNXC(gg_cics *c) {
    c->resp = NORMAL;
    c->resp2 = 0;
    gg_browse *b = browse_of(c->num);
    if (!b) { c->resp = TOKENERR; c->resp2 = 3; return 0; }
    if (chans[b->chan - 1].shape != b->shape) refuse("GETNEXT CONTAINER: the browsed channel changed during the browse");
    if (b->next >= b->n) { c->resp = END; c->resp2 = 2; return 0; }
    memset(c->qname, ' ', 16);
    memcpy(c->qname, b->names[b->next], strlen(b->names[b->next]));
    b->next++;
    return 0;
}

/* ENDBROWSE CONTAINER BROWSETOKEN(GG-NUM): TOKENERR RESP2 3 for a token that is not a current one of this program's. */
int GGCEBRC(gg_cics *c) {
    c->resp = NORMAL;
    c->resp2 = 0;
    gg_browse *b = browse_of(c->num);
    if (!b) { c->resp = TOKENERR; c->resp2 = 3; return 0; }
    memset(b, 0, sizeof *b);
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

/* #4270 (oracle_assumptions.md X24): the channel a task starts with ($GGCICS_DIR/channel.cfg) -- what a RUN TRANSID
 * CHANNEL parent or a LINK CHANNEL caller passed -- made the first program's current channel, the only one in its
 * scope. No file: no current channel, as before. */
static int hexval(int ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    refuse("channel.cfg: a container's data is not hex");
    return 0;
}

static int channel_in; /* a channel.cfg was read: the task's containers are written at its end */

/* A channel.cfg-format file (its name line, then `NAME BIT|CHAR HEX` per container, '-' for no bytes) as a channel in
 * the current level's scope, named `as` (NULL: the file's own name); its index + 1, 0 when there is no file. */
static int load_channel(const char *path, const char *as) {
    char name[17], word[32], type[8];
    size_t size = 1 << 20;
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char *line = malloc(size);
    if (!line) refuse("out of memory");
    if (!fgets(line, (int)size, f) || sscanf(line, "%16s", name) != 1) refuse("channel.cfg: no channel name");
    int ch = channel_named(as ? as : name, 1);
    while (fgets(line, (int)size, f)) {
        char *hex = malloc(size);
        if (!hex) refuse("out of memory");
        if (sscanf(line, "%31s %7s %s", word, type, hex) != 3 || strlen(word) > 16) refuse("channel.cfg: a container line");
        gg_container *k = container_named(&chans[ch - 1], word, 1);
        k->bit = strcmp(type, "CHAR") != 0;
        size_t n = strcmp(hex, "-") == 0 ? 0 : strlen(hex) / 2;
        k->data = malloc(n + 1);
        if (!k->data) refuse("out of memory");
        for (size_t i = 0; i < n; i++) k->data[i] = (char)(hexval(hex[2 * i]) * 16 + hexval(hex[2 * i + 1]));
        k->len = (int)n;
        free(hex);
    }
    free(line);
    fclose(f);
    return ch;
}

/* A channel's containers to `path` in channel.cfg's format (#4950: a RUN / START CHANNEL's copy, a child's reply). */
static void save_channel(const gg_channel *ch, const char *path) {
    FILE *f = fopen(path, "w");
    if (!f) refuse("cannot write a channel's copy");
    fprintf(f, "%s\n", ch->name);
    for (int i = 0; i < MAX_CONTAINERS; i++) {
        if (!ch->c[i].used) continue;
        fprintf(f, "%s %s ", ch->c[i].name, ch->c[i].bit ? "BIT" : "CHAR");
        if (!ch->c[i].len) fprintf(f, "-");
        for (int j = 0; j < ch->c[i].len; j++) fprintf(f, "%02X", (unsigned char)ch->c[i].data[j]);
        fprintf(f, "\n");
    }
    fclose(f);
}

int GGCCHIN(gg_cics *c) {
    char path[4096];
    (void)c;
    snprintf(path, sizeof path, "%s/channel.cfg", dir_in());
    int ch = load_channel(path, NULL);
    if (!ch) return 0;
    levels[0].cur = ch;
    channel_in = 1;
    return 0;
}

/* #4270 (X24): the first program's current channel at task end, every container's bytes in hex -- only for a task
 * started with a channel (channel.cfg), whose first program keeps it as its current channel to the end. */
static void containers_out(void) {
    char path[3000];
    if (!channel_in) return;
    if (!levels[0].cur) refuse("the task's current channel gone at its end");
    gg_channel *ch = &chans[levels[0].cur - 1];
    snprintf(path, sizeof path, "%s/containers.out", dir_out());
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "CHANNEL %s\n", ch->name);
    for (int i = 0; i < MAX_CONTAINERS; i++) {
        if (!ch->c[i].used) continue;
        fprintf(f, "%s ", ch->c[i].name);
        for (int j = 0; j < ch->c[i].len; j++) fprintf(f, "%02X", (unsigned char)ch->c[i].data[j]);
        fprintf(f, "\n");
    }
    fclose(f);
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

/* ---- #4415 slice 1: EXEC CICS BIF DEEDIT (IBM CICS TS, "BIF DEEDIT"; register X26) ------------------------------
 * FIELD's first LENGTH bytes, as the region's EBCDIC page (CCSID 037; ASCII_TO_EBCDIC, python's cp037 for 7-bit ASCII)
 * holds them, edited in place: the characters other than the digits X'F0'-X'F9' are removed, the digits right-aligned
 * and padded on the left with zeros; a field that ends in a minus sign (X'60') or CR gets the negative zone X'D' in its
 * rightmost byte; a rightmost byte whose zone is X'A'-X'F' is returned unaltered ("This permits the application
 * program to operate on a zoned numeric field"); a 1-byte field is returned unaltered. LENGERR if LENGTH is less than
 * 1 (IBM lists no RESP2). Refused by name: a byte beyond 7-bit ASCII, a LENGTH past the field (flen), and a field with
 * no digit left (IBM does not say what it becomes). c->num is LENGTH. */
static const unsigned char ASCII_TO_EBCDIC[128] = {
    0x00, 0x01, 0x02, 0x03, 0x37, 0x2D, 0x2E, 0x2F, 0x16, 0x05, 0x25, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x3C, 0x3D, 0x32, 0x26, 0x18, 0x19, 0x3F, 0x27, 0x1C, 0x1D, 0x1E, 0x1F,
    0x40, 0x5A, 0x7F, 0x7B, 0x5B, 0x6C, 0x50, 0x7D, 0x4D, 0x5D, 0x5C, 0x4E, 0x6B, 0x60, 0x4B, 0x61,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0x7A, 0x5E, 0x4C, 0x7E, 0x6E, 0x6F,
    0x7C, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6,
    0xD7, 0xD8, 0xD9, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xBA, 0xE0, 0xBB, 0xB0, 0x6D,
    0x79, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96,
    0x97, 0x98, 0x99, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xC0, 0x4F, 0xD0, 0xA1, 0x07,
};

int GGCDEED(gg_cics *c, char *field, int flen) {
    int n = c->num, i, k = 0, end, kept = -1, negative, cr, last;
    unsigned char e[32768], digits[32768], out[32768];
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n < 1) { c->resp = LENGERR; return 0; }
    if (n > flen) refuse("BIF DEEDIT LENGTH past FIELD");
    if (n > (int)sizeof e) refuse("BIF DEEDIT LENGTH past 32768");
    for (i = 0; i < n; i++) {
        if ((unsigned char)field[i] >= 0x80) refuse("BIF DEEDIT of a byte beyond 7-bit ASCII");
        e[i] = ASCII_TO_EBCDIC[(unsigned char)field[i]];
    }
    if (n == 1) return 0;
    cr = e[n - 2] == 0xC3 && e[n - 1] == 0xD9;
    negative = e[n - 1] == 0x60 || cr;
    end = n;
    if (negative) end = n - (cr ? 2 : 1);
    else if ((e[n - 1] & 0xF0) >= 0xA0) { kept = e[n - 1]; end = n - 1; }
    for (i = 0; i < end; i++)
        if (e[i] >= 0xF0 && e[i] <= 0xF9) digits[k++] = e[i];
    if (k == 0 && kept < 0) refuse("BIF DEEDIT of a field with no digit left");
    memset(out, 0xF0, (size_t)n);
    last = n - 1;
    if (kept >= 0) { out[last] = (unsigned char)kept; last--; }
    for (i = k - 1; i >= 0; i--, last--) out[last] = digits[i];
    if (negative) out[n - 1] = (unsigned char)(0xD0 | (out[n - 1] & 0x0F));
    for (i = 0; i < n; i++) {
        int a, found = -1;
        for (a = 0; a < 128; a++)
            if (ASCII_TO_EBCDIC[a] == out[i]) { found = a; break; }
        if (found < 0) refuse("BIF DEEDIT result byte beyond 7-bit ASCII");
        field[i] = (char)found;
    }
    return 0;
}

/* ---- #4415 slice 1: INQUIRE / SET TERMINAL UCTRANST (IBM CICS TS, INQUIRE TERMINAL, SET TERMINAL; register X26) ----
 * The CVDAs UCTRAN 450, NOUCTRAN 451, TRANIDONLY 452. The task's terminal ($GGCICS_FACILITY) has the UCTRANST the runner
 * states ($GGCICS_UCTRANST: UCTRAN, NOUCTRAN or TRANIDONLY, from the TYPETERM's UCTRAN); unstated, or the UCTRANST of a
 * terminal other than the task's, refused. A terminal terminals.cfg does not list is TERMIDERR (INQUIRE RESP2 1, SET
 * RESP2 23); an invalid CVDA is INVREQ RESP2 43. A SET is the task's view of its terminal from then on, and a terminal
 * RECEIVE after it is refused (IBM does not say when the change takes effect). c->num is the CVDA. */
static int uctranst_cvda = -1;

static int uctranst_terminal(gg_cics *c, int resp2) {
    char term[9];
    const char *own = getenv("GGCICS_FACILITY");
    trim(c->name1, 8, term);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!listed("terminals.cfg", term)) { c->resp = TERMIDERR; c->resp2 = resp2; return 0; }
    if (!own || strcmp(own, term) != 0) refuse("UCTRANST of a terminal other than the task's");
    return 1;
}

static void uctranst_init(void) {
    const char *v = getenv("GGCICS_UCTRANST");
    if (uctranst_cvda >= 0) return;
    if (!v) refuse("INQUIRE TERMINAL UCTRANST: not stated for this task");
    uctranst_cvda = strcmp(v, "UCTRAN") == 0 ? 450 : strcmp(v, "NOUCTRAN") == 0 ? 451
                  : strcmp(v, "TRANIDONLY") == 0 ? 452 : 0;
    if (!uctranst_cvda) refuse("GGCICS_UCTRANST is not UCTRAN, NOUCTRAN or TRANIDONLY");
}

int GGCINQT(gg_cics *c) {
    if (uctranst_terminal(c, 1)) {
        uctranst_init();
        c->num = uctranst_cvda;
    }
    return 0;
}

int GGCSETT(gg_cics *c) {
    int cvda = c->num;
    if (uctranst_terminal(c, 23)) {
        if (cvda != 450 && cvda != 451 && cvda != 452) { c->resp = INVREQ; c->resp2 = 43; return 0; }
        uctranst_cvda = cvda;
        uctranst_set = 1;
    }
    return 0;
}

/* ---- #4415 slice 2: INQUIRE ASSOCIATION, DELETEQ TS (IBM CICS TS, INQUIRE ASSOCIATION, DELETEQ TS; register X29) ----
 * INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID ODUSERID ODFACILNAME ODNETWORKID ODFACILTYPE: the task's own origin data, the
 * five values the runner states in $GGCICS_ORIGIN as "applid,userid,facilname,networkid,faciltype" (the facility type
 * one of IBM's CVDA names); unstated, refused. GG-FLAGS names the option wanted: the 8-character values come back in
 * name1, ODFACILTYPE's CVDA in num. The task exists and no security is checked: neither TASKIDERR nor NOTAUTH. */
int GGCINQA(gg_cics *c) {
    static const struct { const char *name; int cvda; } types[] = {
        {"APPC", 124}, {"ASRUNTRAN", 1209}, {"BRIDGE", 935}, {"EVENT", 334}, {"IIOP", 1097}, {"IPECI", 936},
        {"IPIC", 1089}, {"JVMSERVER", 1193}, {"LU61", 125}, {"MRO", 938}, {"NODEJSAPP", 1215}, {"NONE", 496},
        {"RRSUR", 939}, {"RZINSTOR", 940}, {"SCHEDULER", 941}, {"SOCKET", 942}, {"START", 635}, {"STARTTERM", 943},
        {"TERMINAL", 213}, {"TRANDATA", 944}, {"WEB", 945}, {"XMRUNTRAN", 946}};
    const char *env = getenv("GGCICS_ORIGIN");
    char want[41], fields[5][64], buf[256];
    int n = 0;
    trim(c->flags, 40, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!env) refuse("INQUIRE ASSOCIATION: the origin data is not stated for this task");
    snprintf(buf, sizeof buf, "%s", env);
    for (char *tok = strtok(buf, ","); tok && n < 5; tok = strtok(NULL, ",")) snprintf(fields[n++], sizeof fields[0], "%s", tok);
    if (n != 5) refuse("INQUIRE ASSOCIATION: $GGCICS_ORIGIN is not applid,userid,facilname,networkid,faciltype");
    if (strcmp(want, "ODFACILTYPE") == 0) {
        c->num = 0;
        for (size_t i = 0; i < sizeof types / sizeof types[0]; i++)
            if (strcmp(types[i].name, fields[4]) == 0) c->num = types[i].cvda;
        if (!c->num) refuse("INQUIRE ASSOCIATION: $GGCICS_ORIGIN's facility type is not one of IBM's");
        return 0;
    }
    int at = strcmp(want, "ODAPPLID") == 0 ? 0 : strcmp(want, "ODUSERID") == 0 ? 1
           : strcmp(want, "ODFACILNAME") == 0 ? 2 : strcmp(want, "ODNETWORKID") == 0 ? 3 : -1;
    if (at < 0) refuse("INQUIRE ASSOCIATION: an option that is not modelled");
    memset(c->name1, ' ', 8);
    memcpy(c->name1, fields[at], strlen(fields[at]) < 8 ? strlen(fields[at]) : 8);
    return 0;
}

/* DELETEQ TS QUEUE (c->qname): the whole queue and its READQ NEXT position. QIDERR (44) when it does not exist; INVREQ
 * (16) for a name of binary zeros only (IBM: "the queue name is all binary zeroes"); IBM lists no RESP2 (0). */
int GGCDELQ(gg_cics *c) {
    char dir[4096], hex[40], path[4200];
    int last = -1, zeros = 1;
    for (int i = 0; i < 16; i++) if (c->qname[i] != ' ') last = i;
    for (int i = 0; i <= last; i++) if (c->qname[i] != '\0') zeros = 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (last >= 0 && zeros) { c->resp = INVREQ; return 0; }
    ts_dir(c, dir, sizeof dir, hex);
    int count = ts_count(dir);
    if (count < 0) { c->resp = QIDERR; return 0; }
    for (int i = 1; i <= count; i++) {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, i);
        remove(path);
    }
    snprintf(path, sizeof path, "%s/next", dir);
    remove(path);
    RMDIR(dir); /* an empty directory: remove() would leave it on Windows (#4836) */
    return 0;
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
static int handed_channel(const gg_cics *c, char *name);

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
    char chname[17] = "", chpath[4200];
    int chan_bad = 0, chan_ix = 0;
    if (flag_word(flags, "CHANNEL")) { /* #4950: START CHANNEL -- the started task's copy of the channel, made now */
        chan_bad = !handed_channel(c, chname);
        if (chan_bad && !listed("transactions.cfg", transid))
            refuse("START TRANSID of a transaction not defined, with an incorrect CHANNEL name");
        if (!chan_bad && !(chan_ix = channel_named(chname, 0))) refuse("START CHANNEL of a channel not in the program's scope");
    }
    if (reqid[0]) {
        char rq[256];
        for (int i = 0; i < nown && reused < 0; i++) {
            if (!own[i].cancelled && strcmp(own[i].reqid, reqid) == 0) reused = own[i].data;
        }
        if (reused < 0) {
            char path[4096], line[128], word[64];
            long long ex;
            snprintf(path, sizeof path, "%s/requests.cfg", dir_in());
            FILE *f = fopen(path, "r");
            while (f && reused < 0 && fgets(line, sizeof line, f)) {
                if (sscanf(line, "%63s %lld", word, &ex) == 2 && strcmp(word, reqid) == 0 && ex > now) reused = 0;
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
    if (chan_bad) {
        c->resp = CHANNELERR;
        c->resp2 = 1;
    } else if (resp2) {
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
    if (chan_ix && c->resp == NORMAL) { /* #4950: the copy, beside the event (NNN.channel), its name in `channel=` */
        snprintf(chpath, sizeof chpath, "%s/%03d.channel", dir_out(), seq + 1);
        save_channel(&chans[chan_ix - 1], chpath);
        snprintf(named + strlen(named), sizeof named - strlen(named), " channel=%s", chname);
    }
    snprintf(ev, sizeof ev, "START transid=%s termid=%s %s=%s reqid=%s protect=%d resp=%d resp2=%d expires=%s len=%d "
             "area=%d%s", transid, termid, is_time ? "time" : "interval", hhmm, reqid, protect, c->resp,
             c->resp == INVREQ || c->resp == CHANNELERR ? c->resp2 : 0, expires, len, has, named);
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
 * does not define. #4950 (X18): the child runs at this task's next wait (GGCDLAY, a GGCFETCH that waits) -- a task that
 * never waits ends with it not run -- as CicsTask.runTransid has it. The token's bytes are the harness's own (IBM does
 * not document them), the same on both sides. */
#define MAX_KIDS 64
typedef struct {
    char token[17], transid[9], abcode[5];
    int number, dispatched, fetched, freed, abended;
    long long completes;
} gg_kid;
static gg_kid kids[MAX_KIDS];
static int nchildren = 0, replies = 0;
static long long waited = 0; /* #4950 (X18): the scheduler's clock, milliseconds of waits */

/* #4950: the characters IBM allows in the name of a channel RUN TRANSID / START hands on (EXEC CICS RUN TRANSID,
 * CHANNEL: "The acceptable characters are A-Z a-z 0-9 $ @ # . / - _ % & ? ! : | " = \xac , ; < >. Leading and embedded
 * blank characters are not permitted"), as the spec's CHANNEL_NAME_CHARS and CicsTask.handedChannel */
static const char channel_chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$@#./-_%&?!:|\"=\xac,;<>";

/* GG-CHAN's name without its trailing blanks into `name`; 0 when it holds a character IBM does not allow (CHANNELERR
 * RESP2 1). An all-blank name is refused, as one starting DFH. */
static int handed_channel(const gg_cics *c, char *name) {
    char msg[64];
    trim(c->chan, 16, name);
    if (!name[0]) refuse("a CHANNEL() with a blank name");
    if (strncmp(name, "DFH", 3) == 0) {
        snprintf(msg, sizeof msg, "CHANNEL(%s), a channel named DFH", name);
        refuse(msg);
    }
    for (const char *p = name; *p; p++)
        if (!strchr(channel_chars, *p)) return 0;
    return 1;
}

static void kid_dir(int n, char *path, size_t size) { snprintf(path, size, "%s/child_%03d", dir_out(), n); }

/* Copies a configuration file of this task's into a child's directory, when there is one. */
static void copy_cfg(const char *file, const char *to) {
    char from[4096], dst[4200], buf[4096];
    size_t n;
    snprintf(from, sizeof from, "%s/%s", dir_in(), file);
    FILE *f = fopen(from, "rb");
    if (!f) return;
    snprintf(dst, sizeof dst, "%s/%s", to, file);
    FILE *g = fopen(dst, "wb");
    if (!g) refuse("cannot write a child's configuration");
    while ((n = fread(buf, 1, sizeof buf, f)) > 0) fwrite(buf, 1, n, g);
    fclose(f);
    fclose(g);
}

int GGCRUNT(gg_cics *c, char *child) {
    char transid[9], ev[96], token[17], name[17], dir[4096], path[4200];
    int bad = 0;
    trim(c->name1, 8, transid);
    if (getenv("GGCICS_CHILDOF")) refuse("RUN TRANSID in a RUN TRANSID child task (a grandchild)");
    if (strstr(c->flags, "CHANNEL")) bad = !handed_channel(c, name);
    c->resp = NORMAL;
    c->resp2 = 0;
    int undefined = !listed("transactions.cfg", transid);
    if (bad && undefined) refuse("RUN TRANSID of a transaction not defined, with an incorrect CHANNEL name");
    if (bad) {
        c->resp = CHANNELERR;
        c->resp2 = 1;
    } else if (undefined) {
        c->resp = TRANSIDERR;
        c->resp2 = 1;
    } else {
        if (nchildren >= MAX_KIDS) refuse("more RUN TRANSID children than the stub holds");
        gg_kid *k = &kids[nchildren++];
        memset(k, 0, sizeof *k);
        snprintf(token, sizeof token, "GGCHILD%09d", nchildren);
        memcpy(child, token, 16);
        memcpy(k->token, token, 17);
        snprintf(k->transid, sizeof k->transid, "%s", transid);
        k->number = nchildren;
        kid_dir(nchildren, dir, sizeof dir);
        MKDIR(dir);
        if (strstr(c->flags, "CHANNEL")) { /* the child's copy, made now ("if the channel does not exist, it is created") */
            snprintf(path, sizeof path, "%s/channel.cfg", dir);
            save_channel(&chans[channel_named(name, 1) - 1], path);
        }
    }
    snprintf(ev, sizeof ev, "RUN transid=%s resp=%d resp2=%d", transid, c->resp, c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* #4950: the child's program, from childprogs.cfg (`TRANSID PROGRAM` per line: the case's statement of what each
 * transaction a RUN may name runs); NULL when the case does not run it. */
static int child_program(const char *transid, char *program) {
    char path[4096], line[64], t[16], p[16];
    snprintf(path, sizeof path, "%s/childprogs.cfg", dir_in());
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%15s %15s", t, p) == 2 && strcmp(t, transid) == 0) {
            snprintf(program, 9, "%s", p);
            fclose(f);
            return 1;
        }
    }
    fclose(f);
    return 0;
}

/* #4950 (X18, ASSUMED): this task waits (a DELAY, or a FETCH that waits): the RUN children not yet dispatched run now,
 * in RUN order, each to its end before this task resumes (one quasi-reentrant TCB: a task keeps control until it
 * waits; a task takes no processor time, X4). A child is this program re-run as a non-terminal task in a directory of
 * its own: EIBTASKN this task's plus its RUN number, no COMMAREA, its current channel the copy RUN made. It completes at
 * its dispatch plus its own DELAYs. What it did is one CHILD event (its directory), compared as a whole. */
static void dispatch_children(void) {
#ifdef _WIN32
    for (int i = 0; i < nchildren; i++)
        if (!kids[i].dispatched && !kids[i].freed) refuse("a RUN TRANSID child on Windows (the stub runs it as a process)");
#else
    char dir[4096], path[4300], program[9], msg[96], line[128], status[16], code[8];
    for (int i = 0; i < nchildren; i++) {
        gg_kid *k = &kids[i];
        if (k->dispatched || k->freed) continue;
        k->dispatched = 1;
        if (!child_program(k->transid, program)) {
            snprintf(msg, sizeof msg, "child transaction %s: its program is not one the case runs", k->transid);
            refuse(msg);
        }
        kid_dir(k->number, dir, sizeof dir);
        snprintf(path, sizeof path, "%s/out", dir);
        MKDIR(path);
        copy_cfg("region.cfg", dir);
        copy_cfg("programs.cfg", dir);
        copy_cfg("transactions.cfg", dir);
        snprintf(path, sizeof path, "%s/eib.in", dir);
        FILE *f = fopen(path, "w");
        FILE *e = NULL;
        char eib[128] = "";
        if (getenv("EIBIN")) e = fopen(getenv("EIBIN"), "r");
        if (!f || !e || !fgets(eib, sizeof eib, e) || strlen(eib) < 30) refuse("a RUN TRANSID child: no EIB to start it from");
        fclose(e);
        /* TRANSID AID DATE TIME TERMID: the child's transaction, no AID (DFHNULL), its parent's date and time (X4) */
        fprintf(f, "%-4s %-8s %.15s     \n", k->transid, "DFHNULL", eib + 14);
        fclose(f);
        fflush(NULL);
        pid_t pid = fork();
        if (pid < 0) refuse("a RUN TRANSID child: fork failed");
        if (pid == 0) {
            char num[24], out[4300], eibin[4300], trace[4300];
            const char *taskn = getenv("GGCICS_TASKN");
            snprintf(num, sizeof num, "%ld", (taskn ? strtol(taskn, NULL, 10) : 0) + k->number);
            snprintf(out, sizeof out, "%s/out", dir);
            snprintf(eibin, sizeof eibin, "%s/eib.in", dir);
            snprintf(trace, sizeof trace, "%s/trace.txt", dir);
            setenv("GGCICS_DIR", dir, 1);
            setenv("GGCICS_OUT", out, 1);
            setenv("EIBIN", eibin, 1);
            setenv("GGCICS_TASKN", num, 1);
            setenv("GGCICS_RUNCHILD", "1", 1);
            setenv("GGCICS_CHILDOF", "1", 1);
            setenv("GGCICS_CHILDPROG", program, 1);
            if (getenv("COB_TRACE_FILE")) setenv("COB_TRACE_FILE", trace, 1); /* (its own: the parent's stays open) */
            const char *gone[] = {"GGCICS_FACILITY", "GGCICS_STARTCODE", "GGCICS_ORIGIN", "GGCICS_UCTRANST",
                                  "GGCICS_WEBREQ", "GGCICS_TCPIP", "GGCICS_HTTP", "GGCICS_LU2", "GGCICS_URIMAPS", "GGCICS_DOCTEMPLATES"};
            for (size_t j = 0; j < sizeof gone / sizeof gone[0]; j++) unsetenv(gone[j]);
            execl("/proc/self/exe", "task", (char *)NULL);
            _exit(97);
        }
        int st = 0;
        if (waitpid(pid, &st, 0) < 0 || !WIFEXITED(st)) {
            printf("RUN TRANSID child %s failed\n", k->token);
            exit(1);
        }
        if (WEXITSTATUS(st) == 98) exit(98); /* the child refused (its reason is in the shared log): so does the task */
        if (WEXITSTATUS(st) != 0) {
            printf("RUN TRANSID child %s failed (exit %d)\n", k->token, WEXITSTATUS(st));
            exit(1);
        }
        long long its = 0;
        snprintf(path, sizeof path, "%s/out/end.txt", dir);
        f = fopen(path, "r");
        if (!f || !fgets(line, sizeof line, f) || sscanf(line, "%15s %7s %lld", status, code, &its) != 3)
            refuse("a RUN TRANSID child that left no end state");
        fclose(f);
        if (strcmp(status, "RECOVERED") == 0)
            refuse("a RUN TRANSID child that went on after an abend (HANDLE ABEND): its completion status");
        k->abended = strcmp(status, "ABEND") == 0;
        snprintf(k->abcode, sizeof k->abcode, "%.4s", code);
        k->completes = waited + its;
        snprintf(msg, sizeof msg, "CHILD child=%s transid=%s dir=child_%03d", k->token, k->transid, k->number);
        event(msg, NULL, 0);
    }
#endif
}

/* #4950: in a child ($GGCICS_CHILDOF), at its end: end.txt (NORMAL | ABEND | RECOVERED, the abend code, its own
 * waits in ms) and reply.cfg, the current channel it leaves its parent (none: no file). */
static void child_end(void) {
    char path[4096];
    if (!getenv("GGCICS_CHILDOF")) return;
    snprintf(path, sizeof path, "%s/end.txt", dir_out());
    FILE *f = fopen(path, "w");
    if (!f) refuse("a RUN TRANSID child: cannot write its end");
    int abcode = strncmp(task_abcode, "    ", 4) != 0;
    fprintf(f, "%s %.4s %lld\n", terminated ? "ABEND" : abcode ? "RECOVERED" : "NORMAL", abcode ? task_abcode : "----",
            waited);
    fclose(f);
    if (levels[0].cur) {
        snprintf(path, sizeof path, "%s/reply.cfg", dir_out());
        save_channel(&chans[levels[0].cur - 1], path);
    }
}

/* #4950: the driver asks whether this process is a RUN TRANSID child: GG-ITEM 1 with its program in GG-NAME1. */
int GGCCHLD(gg_cics *c) {
    const char *p = getenv("GGCICS_CHILDOF") ? getenv("GGCICS_CHILDPROG") : NULL;
    c->item = 0;
    if (!p) return 0;
    memset(c->name1, ' ', 8);
    memcpy(c->name1, p, strlen(p) < 8 ? strlen(p) : 8);
    c->item = 1;
    return 0;
}

/* #4950: DELAY (IBM, EXEC CICS DELAY), as CicsTask.delay / delayMillis: GG-FLAGS INTERVAL (GG-NUM hhmmss), TIME, or
 * FOR (GG-HOURS / GG-MINS / GG-SECS / GG-LEN milliseconds, -999999999 when not given); none: INTERVAL(0). A task takes no
 * time (X4): NORMAL at once, after the RUN children the wait dispatches; the scheduler's clock moves by its length. A
 * TIME, or a value out of IBM's ranges, is refused in a task with RUN children or in a child. */
int GGCDLAY(gg_cics *c) {
    const int none = -999999999;
    long long ms = -1;
    char msg[96];
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(c->flags, "INTERVAL")) {
        long long v = c->num;
        if (v >= 0 && v / 10000 <= 99 && v / 100 % 100 <= 59 && v % 100 <= 59)
            ms = (v / 10000 * 3600 + v / 100 % 100 * 60 + v % 100) * 1000;
    } else if (strstr(c->flags, "FOR")) {
        long long h = c->hours, m = c->mins, s = c->secs, l = c->len;
        int given = (h != none) + (m != none) + (s != none) + (l != none), one = given == 1;
        if (!((h != none && (h < 0 || h > 99)) || (m != none && (m < 0 || m > (one ? 5999 : 59)))
              || (s != none && (s < 0 || s > (one ? 359999 : 59))) || (l != none && (l < 0 || l > (one ? 359999999 : 999)))))
            ms = ((h != none ? h : 0) * 3600 + (m != none ? m : 0) * 60 + (s != none ? s : 0)) * 1000 + (l != none ? l : 0);
    } else if (!strstr(c->flags, "TIME")) {
        ms = 0;
    }
    if (ms < 0) {
        if (nchildren || getenv("GGCICS_CHILDOF")) {
            snprintf(msg, sizeof msg, "DELAY %s in a task with RUN TRANSID children",
                     strstr(c->flags, "TIME") ? "TIME" : "out of range");
            refuse(msg);
        }
        return 0;
    }
    dispatch_children();
    waited += ms;
    return 0;
}

static int kid_of(const char *qname) {
    char token[17];
    memcpy(token, qname, 16);
    token[16] = 0;
    for (int i = 0; i < nchildren; i++)
        if (strcmp(kids[i].token, token) == 0) return i + 1;
    return 0;
}

/* #4884, #4950: FETCH ANY / FETCH CHILD(token) (IBM, EXEC CICS FETCH), as CicsTask.fetch: GG-FLAGS 'CHILD' with the
 * token in GG-QNAME (else FETCH ANY), NOSUSPEND, TIMEOUT (GG-NUM milliseconds) or neither (it waits), CHANNEL (the reply
 * channel asked for). On NORMAL: the token in GG-QNAME, the reply channel's name in GG-CHAN, the abend code in GG-NAME1
 * (GG-ITEM 1: the child abended) and COMPSTATUS's CVDA in GG-NUM (NORMAL 1016, ABEND 900). */
int GGCFETCH(gg_cics *c) {
    char ev[200], msg[96], path[4300], dir[4096], reply[17];
    int one = 0, any = 0, first = -1;
    int nosuspend = strstr(c->flags, "NOSUSPEND") != NULL, timed = strstr(c->flags, "TIMEOUT") != NULL;
    long long timeout = timed ? c->num : 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    c->item = 0;
    if (timed && (timeout < 0 || timeout > 4080000)) {
        snprintf(msg, sizeof msg, "FETCH TIMEOUT(%d) outside 0 to 4080000 milliseconds", (int)timeout);
        refuse(msg);
    }
    if (strstr(c->flags, "CHILD")) {
        one = kid_of(c->qname);
        if (!one || kids[one - 1].freed) { c->resp = INVREQ; c->resp2 = 50; goto done; }
        if (kids[one - 1].fetched) refuse("FETCH CHILD of a child already fetched");
    } else if (nchildren == 0) {
        c->resp = INVREQ;
        c->resp2 = 52;
        goto done;
    }
    if (!nosuspend) dispatch_children();
    for (int i = 0; i < nchildren; i++) {
        gg_kid *k = &kids[i];
        if (one ? i != one - 1 : k->fetched || k->freed) continue;
        any = 1;
        if (k->dispatched && (first < 0 || k->completes < kids[first].completes)) first = i;
    }
    if (!any) { c->resp = DFHRESP_NOTFND; c->resp2 = 1; goto done; }
    if (nosuspend) {
        if (first < 0 || kids[first].completes > waited) { c->resp = DFHRESP_NOTFINISHED; c->resp2 = 52; goto done; }
        if (kids[first].completes == waited) refuse("a FETCH whose answer turns on a child completing at the instant its parent resumed from a wait (a tie)");
    } else if (timed) {
        if (kids[first].completes == waited + timeout) refuse("a FETCH whose answer turns on a child completing at the instant its parent resumed from a wait (a tie)");
        if (kids[first].completes > waited + timeout) {
            waited += timeout;
            c->resp = DFHRESP_NOTFINISHED;
            c->resp2 = 53;
            goto done;
        }
    }
    if (kids[first].completes > waited) waited = kids[first].completes;
    gg_kid *k = &kids[first];
    k->fetched = 1;
    memcpy(c->qname, k->token, 16);
    c->num = k->abended ? 900 : 1016;
    if (k->abended) { memset(c->name1, ' ', 8); memcpy(c->name1, k->abcode, 4); c->item = 1; }
    reply[0] = 0;
    if (strstr(c->flags, "CHANNEL")) {
        kid_dir(k->number, dir, sizeof dir);
        snprintf(path, sizeof path, "%s/out/reply.cfg", dir);
        snprintf(reply, sizeof reply, "GGREPLY%09d", replies + 1);
        if (!load_channel(path, reply)) refuse("FETCH CHANNEL of a child that left no current channel");
        replies++;
        memset(c->chan, ' ', 16);
        memcpy(c->chan, reply, 16);
    }
    snprintf(ev, sizeof ev, "FETCH resp=%d resp2=%d child=%s compstatus=%s abcode=%s channel=%s", c->resp, c->resp2,
             k->token, k->abended ? "ABEND" : "NORMAL", k->abended ? k->abcode : "-", reply[0] ? reply : "-");
    event(ev, NULL, 0);
    return 0;
done:
    snprintf(ev, sizeof ev, "FETCH resp=%d resp2=%d", c->resp, c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* #4950: FREE CHILD(token in GG-QNAME) (IBM, EXEC CICS FREE CHILD), as CicsTask.freeChild: INVREQ 50 for a token that
 * is not a child's or was freed; freeing a child already fetched is refused. */
int GGCFREE(gg_cics *c) {
    char ev[64];
    int k = kid_of(c->qname);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!k || kids[k - 1].freed) {
        c->resp = INVREQ;
        c->resp2 = 50;
    } else if (kids[k - 1].fetched) {
        refuse("FREE CHILD of a child already fetched");
    } else {
        kids[k - 1].freed = 1;
    }
    snprintf(ev, sizeof ev, "FREE-CHILD resp=%d resp2=%d", c->resp, c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* CANCEL REQID(qname) (IBM, EXEC CICS CANCEL): NORMAL for a request that has not expired, NOTFND
 * when none matches ("fails to match an unexpired interval control command"). */
int GGCCNCL(gg_cics *c) {
    char reqid[17], path[4096], line[128], word[64], ev[96];
    long long expires;
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
        if (sscanf(line, "%63s %lld", word, &expires) == 2 && strcmp(word, reqid) == 0 && expires > now) found = 1;
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

/* The region's named counters (#4270, register X30): $GGCICS_DIR/counters.cfg, one "POOL NAME VALUE" per line (POOL "-" for
 * none), read whole for each counter command and rewritten by the ones that change it, so a later task of the scenario
 * sees the result. */
#define MAXCNT 64
/* #4770 (X45): `limited` rows (DEFINE DCOUNTER's) carry MINIMUM / MAXIMUM, unsigned doublewords; a row of three fields has limits
 * the run does not state. */
typedef struct { char pool[64], name[64]; unsigned long long value; int limited; unsigned long long min, max; } counter_row; /* #4836: long is 32-bit on Windows */

static int counters_read(counter_row *rows) {
    char path[4096], line[256];
    int n = 0;
    snprintf(path, sizeof path, "%s/counters.cfg", dir_in());
    FILE *f = fopen(path, "r");
    while (f && n < MAXCNT && fgets(line, sizeof line, f))
    {
        int got = sscanf(line, "%63s %63s %llu %llu %llu", rows[n].pool, rows[n].name, &rows[n].value, &rows[n].min, &rows[n].max);
        rows[n].limited = got == 5;
        if (got == 3 || got == 5) n++;
    }
    if (f) fclose(f);
    return n;
}

static void counters_write(const counter_row *rows, int n) {
    char path[4096];
    snprintf(path, sizeof path, "%s/counters.cfg", dir_in());
    FILE *f = fopen(path, "w");
    for (int i = 0; f && i < n; i++) {
        if (rows[i].limited)
            fprintf(f, "%s %s %llu %llu %llu\n", rows[i].pool, rows[i].name, rows[i].value, rows[i].min, rows[i].max);
        else
            fprintf(f, "%s %s %llu\n", rows[i].pool, rows[i].name, rows[i].value);
    }
    if (f) fclose(f);
}

static int counter_find(const counter_row *rows, int n, const char *pool, const char *name) {
    for (int i = 0; i < n; i++)
        if (strcmp(rows[i].pool, pool) == 0 && strcmp(rows[i].name, name) == 0) return i;
    return -1;
}

/* The INVREQ RESP2 IBM gives a name outside its rules (EXEC CICS DEFINE / GET COUNTER): 403 for the pool (A-Z 0-9 $ @ # _,
 * no embedded spaces), 404 for the counter (A-Z $ @ # first, then also 0-9 and _; no embedded spaces); 0 for a valid pair.
 * A counter name of blanks only is not covered by IBM's rules: refused. */
static int counter_name_resp2(const char *pool, const char *name) {
    for (const char *q = pool; *q; q++)
        if (!((*q >= 'A' && *q <= 'Z') || (*q >= '0' && *q <= '9') || *q == '$' || *q == '@' || *q == '#' || *q == '_'))
            return 403;
    if (!name[0]) refuse("a named counter with a blank name");
    for (const char *q = name; *q; q++) {
        int ok = (*q >= 'A' && *q <= 'Z') || *q == '$' || *q == '@' || *q == '#' ||
                 (q > name && ((*q >= '0' && *q <= '9') || *q == '_'));
        if (!ok) return 404;
    }
    return 0;
}

static void counter_names(gg_cics *c, char *want, char *pool, char *shown) {
    trim(c->qname, 16, want);
    trim(c->name1, 8, pool);
    strcpy(shown, pool);
    if (!pool[0]) strcpy(pool, "-");
}

/* One GET of the counter at rows[at] (as CicsTask.getCounter(pool, name, increment, wrap)): the value it hands back in *out and
 * the counter `incr` more; 1 (SUPPRESSED RESP2 101, the counter unchanged) for a DEFINE DCOUNTER counter at its limit without
 * WRAP. #4770 (X45): such a counter has the limits it was given (unsigned doublewords): at its limit (MAXIMUM + 1) WRAP
 * "resets the current value ... equal to the minimum value" and the GET returns that; an INCREMENT beyond MAXIMUM - MINIMUM, or
 * past MAXIMUM + 1 (IBM's 406 / REDUCE boundaries are not stated), and a counter past a doubleword are refused. A counter with
 * no limits has none the run states: WRAP changes nothing and one past 4294967295 is refused, as before. */
static int counter_step(counter_row *r, unsigned long long incr, int wrap, unsigned long long *out) {
    unsigned long long v = r->value, next;
    if (!r->limited) {
        if (incr > 4294967295ULL || v + incr > 4294967295ULL) refuse("GET COUNTER past 4294967295: the counter's maximum is not stated");
        *out = v;
        r->value = v + incr;
        return 0;
    }
    if (incr > r->max - r->min) refuse("GET COUNTER with an INCREMENT beyond the counter's range");
    if (r->max != ~0ULL && v > r->max) { /* at its limit: the counter is MAXIMUM + 1 */
        if (!wrap) return 1;
        *out = r->min;
        r->value = r->min + incr;
        return 0;
    }
    next = v + incr;
    if (next < v) refuse("GET COUNTER past a doubleword");
    if (next > r->max && next - r->max > 1) refuse("GET COUNTER with an INCREMENT past MAXIMUM + 1");
    *out = v;
    r->value = next;
    return 0;
}

static void put32(unsigned char *p, unsigned long long v) {
    for (int i = 3; i >= 0; i--) { p[i] = (unsigned char)(v & 255); v >>= 8; }
}

/* GET COUNTER(qname) POOL(name1) VALUE(value) INCREMENT(inc) [WRAP] (IBM CICS TS, GET COUNTER; X30, #5039, X50): the
 * value before the increment is written big-endian (signed fullword) into `value`, after which the counter is the
 * increment more; `wrap` is WRAP. See counter_step for the limits. As CicsTask.getCounter(pool, name, increment, wrap). */
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    unsigned long long incr = 0;
    int i;
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen == 8 && inc[0] == 0 && inc[1] == 0 && inc[2] == 0 && inc[3] == 0) {
        inc += 4;
        inclen = 4;
    }
    if (inclen > 4 || valuelen != 4) refuse("GET COUNTER with a VALUE or INCREMENT that is not a fullword");
    for (i = 0; i < inclen; i++) incr = incr * 256 + inc[i];
    if (incr == 0) refuse("GET COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        unsigned long long v;
        if (counter_step(&rows[at], incr, wrap, &v)) {
            c->resp = SUPPRESSED;
            c->resp2 = 101;
            return 0;
        }
        put32(value, v);
        counters_write(rows, n);
    }
    return 0;
}

/* GET DCOUNTER(qname) POOL(name1) VALUE(value) INCREMENT(inc) [WRAP] (IBM CICS TS, GET COUNTER and GET DCOUNTER; X30, X45): the
 * value before the increment is written big-endian (unsigned doubleword) into `value`, after which the counter is the
 * increment more; `wrap` is WRAP. See counter_step for the limits. As CicsTask.getCounter(pool, name, increment, wrap). */
int GGCGDCN(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    unsigned long long incr = 0;
    int i;
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen > 8 || valuelen != 8) refuse("GET DCOUNTER with a VALUE or INCREMENT that is not a doubleword");
    for (i = 0; i < inclen; i++) incr = incr * 256 + inc[i];
    if (incr == 0) refuse("GET COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        unsigned long long v;
        if (counter_step(&rows[at], incr, wrap, &v)) {
            c->resp = SUPPRESSED;
            c->resp2 = 101;
            return 0;
        }
        for (i = 7; i >= 0; i--) { value[i] = (unsigned char)(v & 255); v >>= 8; }
        counters_write(rows, n);
    }
    return 0;
}

static unsigned long long be64(const unsigned char *p, int len) {
    unsigned long long v = 0;
    for (int i = 0; i < len; i++) v = v * 256 + p[i];
    return v;
}

static void put64(unsigned char *p, unsigned long long v) {
    for (int i = 7; i >= 0; i--) { p[i] = (unsigned char)(v & 255); v >>= 8; }
}

/* DEFINE DCOUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4770, register X45; IBM, EXEC CICS DEFINE COUNTER and DEFINE
 * DCOUNTER): unsigned doublewords, each area passed with its length (0: omitted -- IBM's defaults MINIMUM zero, MAXIMUM a doubleword
 * of X'FF', VALUE zero). INVREQ 407 when MAXIMUM is below MINIMUM, 406 when VALUE is below MINIMUM or above MAXIMUM + 1 (checked
 * before 202, 403 / 404 first: the page gives no order), 202 for a duplicate. As CicsTask.defineDcounter. */
int GGCDDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows);
    if (vallen > 8 || lolen > 8 || hilen > 8) refuse("DEFINE DCOUNTER with a VALUE, MINIMUM or MAXIMUM that is not a doubleword");
    unsigned long long v = vallen ? be64(val, vallen) : 0, mn = lolen ? be64(lo, lolen) : 0, mx = hilen ? be64(hi, hilen) : ~0ULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (mx < mn) {
        c->resp = INVREQ;
        c->resp2 = 407;
    } else if (v < mn || (mx != ~0ULL && v > mx + 1)) {
        c->resp = INVREQ;
        c->resp2 = 406;
    } else if (counter_find(rows, n, pool, want) >= 0) {
        c->resp = INVREQ;
        c->resp2 = 202;
    } else if (n >= MAXCNT) {
        refuse("DEFINE COUNTER past the stub's 64 counters");
    } else {
        snprintf(rows[n].pool, sizeof rows[n].pool, "%s", pool);
        snprintf(rows[n].name, sizeof rows[n].name, "%s", want);
        rows[n].value = v;
        rows[n].limited = 1;
        rows[n].min = mn;
        rows[n].max = mx;
        counters_write(rows, n + 1);
    }
    return 0;
}

/* QUERY DCOUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4770, X45): the counter's value and limits, unsigned doublewords
 * written big-endian into the areas given (length 0: not asked for); the value is unchanged. MINIMUM / MAXIMUM of a counter with no
 * limits are refused. As CicsTask.queryDcounter. */
int GGCQDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    if ((vallen && vallen != 8) || (lolen && lolen != 8) || (hilen && hilen != 8))
        refuse("QUERY DCOUNTER with a VALUE, MINIMUM or MAXIMUM that is not a doubleword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        if ((lolen || hilen) && !rows[at].limited)
            refuse("QUERY DCOUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        if (vallen) put64(val, rows[at].value);
        if (lolen) put64(lo, rows[at].min);
        if (hilen) put64(hi, rows[at].max);
    }
    return 0;
}

/* QUERY COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (IBM CICS TS, EXEC CICS QUERY COUNTER; #4415 slice 2, X29; #5039, X50):
 * the named counter's value and limits, signed fullwords written big-endian into the areas given (length 0: not asked for);
 * the value is unchanged. A counter not there is INVREQ RESP2 201 "Named counter not found". MINIMUM / MAXIMUM of a counter with
 * no limits, and a value beyond a fullword (IBM's LENGERR), are refused. As CicsTask.queryCounter. */
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    if ((vallen && vallen != 4) || (lolen && lolen != 4) || (hilen && hilen != 4))
        refuse("QUERY COUNTER with a VALUE, MINIMUM or MAXIMUM that is not a fullword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        if ((lolen || hilen) && !rows[at].limited)
            refuse("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        if (rows[at].value > 2147483647ULL)
            refuse("QUERY COUNTER of a value beyond a fullword");
        if (vallen) put32(val, rows[at].value);
        if (lolen) put32(lo, rows[at].min);
        if (hilen) put32(hi, rows[at].max);
    }
    return 0;
}

/* DEFINE COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4270, register X30; #5039, X50; IBM, EXEC CICS DEFINE COUNTER):
 * fullwords, each area passed with its length (0: omitted -- IBM's defaults MINIMUM zero, MAXIMUM X'7FFFFFFF' = 2147483647,
 * VALUE zero). INVREQ 407 when MAXIMUM is below MINIMUM or beyond X'7FFFFFFF', 406 when VALUE is below MINIMUM or above MAXIMUM + 1,
 * 202 for a duplicate, 403 / 404 for a name outside IBM's rules (407 / 406 checked first: the page gives no order). A VALUE or
 * MINIMUM below zero is refused. As CicsTask.defineCounter. */
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows);
    if (vallen > 4 || lolen > 4 || hilen > 4) refuse("DEFINE COUNTER with a VALUE, MINIMUM or MAXIMUM that is not a fullword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (vallen && (val[0] & 0x80)) refuse("DEFINE COUNTER with a VALUE below zero");
    if (lolen && (lo[0] & 0x80)) refuse("DEFINE COUNTER with a MINIMUM below zero");
    unsigned long long v = vallen ? be64(val, vallen) : 0;
    unsigned long long mn = lolen ? be64(lo, lolen) : 0;
    unsigned long long mx = hilen ? be64(hi, hilen) : 2147483647ULL;
    if (mx < mn || mx > 2147483647ULL) {
        c->resp = INVREQ;
        c->resp2 = 407;
    } else if (v < mn || v > mx + 1) {
        c->resp = INVREQ;
        c->resp2 = 406;
    } else if (counter_find(rows, n, pool, want) >= 0) {
        c->resp = INVREQ;
        c->resp2 = 202;
    } else if (n >= MAXCNT) {
        refuse("DEFINE COUNTER past the stub's 64 counters");
    } else {
        snprintf(rows[n].pool, sizeof rows[n].pool, "%s", pool);
        snprintf(rows[n].name, sizeof rows[n].name, "%s", want);
        rows[n].value = v;
        rows[n].limited = 1;
        rows[n].min = mn;
        rows[n].max = mx;
        counters_write(rows, n + 1);
    }
    return 0;
}

/* DELETE COUNTER(qname) POOL(name1) (#4270, register X30; IBM, EXEC CICS DELETE COUNTER): the counter removed; INVREQ
 * RESP2 201 "Named counter not found" (the page lists no NOTFND), 403 for a pool outside IBM's rules. */
int GGCXCNT(gg_cics *c) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad == 403 ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad == 403) {
        c->resp = INVREQ;
        c->resp2 = 403;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        for (int i = at; i + 1 < n; i++) rows[i] = rows[i + 1];
        counters_write(rows, n - 1);
    }
    return 0;
}

/* ---- #4270 zECS: INQUIRE URIMAP's browse, WRITE OPERATOR (IBM CICS TS, INQUIRE URIMAP, "Browsing resource definitions",
 * WRITE OPERATOR; register X32) ----
 * The URIMAP definitions installed in the region, in the order it browses them, are a fact the runner states: the file
 * $GGCICS_URIMAPS names, one `NAME TRANSACTION PATH` per line ('-' for no transaction); unstated, refused. GG-FLAGS names
 * the browse step: START (ILLOGIC RESP2 1 when one is already in progress), NEXT (END RESP2 2 past the last; the
 * definition it returns is read by GGCURIP) or END. NEXT / END with no browse started are refused: IBM gives that ILLOGIC
 * no RESP2 of its own. #4768 (X34): DIRECT, the direct form INQUIRE URIMAP(name): the definition GG-NAME1 names, read by
 * GGCURIP as NEXT's; NOTFND RESP2 3 when it is not installed. */
static int urimap_at = -1; /* -1: no browse; else the next definition's index */
static char urimap_now[3][300];

static int urimap_get(int want, char fields[3][300]) {
    const char *env = getenv("GGCICS_URIMAPS");
    char line[1024];
    int n = 0, found = 0;
    if (!env) refuse("INQUIRE URIMAP: the installed URIMAP definitions are not stated for this task");
    FILE *f = fopen(env, "r");
    if (!f) refuse("INQUIRE URIMAP: the installed URIMAP definitions are not stated for this task");
    while (fgets(line, sizeof line, f)) {
        char a[300], b[300], p[300];
        if (sscanf(line, "%299s %299s %299s", a, b, p) != 3) continue;
        if (n == want && fields) {
            snprintf(fields[0], 300, "%s", a);
            snprintf(fields[1], 300, "%s", strcmp(b, "-") == 0 ? "" : b);
            snprintf(fields[2], 300, "%s", p);
            found = 1;
        }
        n++;
    }
    fclose(f);
    return fields ? found : n;
}

int GGCURIB(gg_cics *c) {
    char want[41];
    trim(c->flags, 40, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    urimap_get(-1, NULL); /* (refuses when the definitions are not stated) */
    if (strcmp(want, "DIRECT") == 0) { /* #4768 (X34): URIMAP(name1), NOTFND RESP2 3 when it is not installed */
        char name[9], fields[3][300];
        trim(c->name1, 8, name);
        for (int i = 0; urimap_get(i, fields); i++) {
            if (strcmp(fields[0], name) == 0) { memcpy(urimap_now, fields, sizeof urimap_now); return 0; }
        }
        c->resp = NOTFND;
        c->resp2 = 3;
        return 0;
    }
    if (strcmp(want, "START") == 0) {
        if (urimap_at >= 0) { c->resp = DFHRESP_ILLOGIC; c->resp2 = 1; return 0; }
        urimap_at = 0;
        return 0;
    }
    if (urimap_at < 0) refuse("INQUIRE URIMAP NEXT or END with no browse started");
    if (strcmp(want, "END") == 0) { urimap_at = -1; return 0; }
    if (!urimap_get(urimap_at, urimap_now)) { c->resp = DFHRESP_END; c->resp2 = 2; return 0; }
    urimap_at++;
    return 0;
}

/* The definition the last NEXT returned: GG-FLAGS names URIMAP (8 characters), PATH (255) or TRANSACTION (4); the value,
 * blank-padded, goes to the program's area -- at most its length (IBM states no padding for a short value: blanks). */
int GGCURIP(gg_cics *c, char *area, int len) {
    char want[41];
    int at = 0, width = 8, n; /* urimap_now: name, transaction, path */
    trim(c->flags, 40, want);
    if (strcmp(want, "PATH") == 0) { at = 2; width = 255; }
    else if (strcmp(want, "TRANSACTION") == 0) { at = 1; width = 4; }
    n = len < width ? len : width;
    for (int i = 0; i < n; i++) area[i] = ' ';
    for (int i = 0; i < n && urimap_now[at][i]; i++) area[i] = urimap_now[at][i];
    return 0;
}

/* WRITE OPERATOR TEXT(from) of GG-LEN bytes: a message to the console, recorded with its text. A text IBM reformats
 * (DFHnnnn / DFHaannnn) or splits (over 113 characters) is refused. */
int GGCWTO(gg_cics *c, char *from) {
    char ev[64];
    int n = c->len, k = 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    while (n > 0 && from[n - 1] == ' ') n--;
    if (c->len > 113) refuse("WRITE OPERATOR text IBM reformats");
    if (n >= 7 && strncmp(from, "DFH", 3) == 0) {
        k = 3;
        if (from[3] >= 'A' && from[3] <= 'Z' && from[4] >= 'A' && from[4] <= 'Z') k = 5;
        else if (from[3] >= 'a' && from[3] <= 'z' && from[4] >= 'a' && from[4] <= 'z') k = 5;
        if (n >= k + 4 && from[k] >= '0' && from[k] <= '9' && from[k + 1] >= '0' && from[k + 1] <= '9'
            && from[k + 2] >= '0' && from[k + 2] <= '9' && from[k + 3] >= '0' && from[k + 3] <= '9')
            refuse("WRITE OPERATOR text IBM reformats");
    }
    snprintf(ev, sizeof ev, "WRITE-OPERATOR len=%d resp=0", c->len);
    event(ev, from, c->len);
    return 0;
}

/* ---- #4769 zECS: the document handler's DOCUMENT CREATE and DOCUMENT RETRIEVE (IBM CICS TS, EXEC CICS DOCUMENT
 * CREATE, DOCUMENT RETRIEVE; register X33) ----
 * A document is the bytes the task built, named by a 16-byte DOCTOKEN ("GGDOC" and eleven digits); it lasts as long as
 * the task (one process here). The installed DOCTEMPLATEs are a fact the runner states: the file $GGCICS_DOCTEMPLATES
 * names, one `NAME TEXT-IN-HEX` per line (the text, hex, because it can hold line ends; '-' for an empty text); unstated, refused. */
#define GG_MAXDOCS 64
static unsigned char *docs[GG_MAXDOCS];
static int doc_len[GG_MAXDOCS];
static int doc_dead[GG_MAXDOCS]; /* #4941: deleted by a WEB SEND DOCSTATUS(DOCDELETE) */
static int ndocs = 0;

static int doc_new(const unsigned char *data, int len, char *tok, int toklen) {
    char t[17];
    int i;
    if (ndocs >= GG_MAXDOCS) refuse("DOCUMENT CREATE of more than 64 documents");
    docs[ndocs] = malloc(len > 0 ? (size_t)len : 1);
    memcpy(docs[ndocs], data, (size_t)(len > 0 ? len : 0));
    doc_len[ndocs] = len;
    ndocs++;
    snprintf(t, sizeof t, "GGDOC%011d", ndocs);
    for (i = 0; i < toklen && i < 16; i++) tok[i] = t[i];
    for (; i < toklen; i++) tok[i] = ' ';
    return 0;
}

/* The text the template `name` yields (malloc'd, `*len` bytes); NULL when it is not installed. */
static unsigned char *doctemplate(const char *name, int *len) {
    const char *env = getenv("GGCICS_DOCTEMPLATES");
    char line[65536], n[100], hex[65000];
    FILE *f;
    if (!env) refuse("DOCUMENT CREATE: the installed document templates are not stated for this task");
    f = fopen(env, "r");
    if (!f) refuse("DOCUMENT CREATE: the installed document templates are not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int hl, k;
        unsigned char *out;
        hex[0] = '\0';
        if (sscanf(line, "%99s %64999s", n, hex) < 1 || strcmp(n, name) != 0) continue;
        fclose(f);
        hl = strcmp(hex, "-") == 0 ? 0 : (int)strlen(hex);
        out = malloc((size_t)(hl / 2 + 1));
        for (k = 0; k + 1 < hl; k += 2) {
            unsigned int b;
            sscanf(hex + k, "%2x", &b);
            out[k / 2] = (unsigned char)b;
        }
        *len = hl / 2;
        return out;
    }
    fclose(f);
    return NULL;
}

/* Does `text` (`left` bytes) begin with `word`, in either case? */
static int doc_word(const unsigned char *text, int left, const char *word) {
    int n = (int)strlen(word), i;
    if (left < n) return 0;
    for (i = 0; i < n; i++)
        if (tolower(text[i]) != word[i]) return 0;
    return 1;
}

/* DOCUMENT CREATE DOCTOKEN(tok): GG-FLAGS names the source -- EMPTY; DATA (TEXT / BINARY: `src`, GG-LEN bytes, `srclen`
 * the area's own length; a negative GG-LEN is LENGERR RESP2 1, one past the area is refused); TEMPLATE (`src` is the
 * 48-byte name, `srclen` its length: NOTFND RESP2 3 when not installed). The token goes to `tok` (16 bytes, blank-padded)
 * on NORMAL only. */
int GGCDOCC(gg_cics *c, char *src, int srclen, char *tok, int toklen) {
    char flags[41];
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strcmp(flags, "DATA") == 0) {
        if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
        if (c->len > srclen) refuse("DOCUMENT CREATE LENGTH past the TEXT / BINARY area");
        return doc_new((unsigned char *)src, c->len, tok, toklen);
    }
    if (strcmp(flags, "TEMPLATE") == 0) {
        char name[100];
        int len = 0, i;
        unsigned char *text;
        trim(src, srclen < 99 ? srclen : 99, name);
        text = doctemplate(name, &len);
        if (!text) { c->resp = NOTFND; c->resp2 = 3; return 0; }
        for (i = 0; i < len; i++) {
            if (text[i] == '#' && (doc_word(text + i + 1, len - i - 1, "set") || doc_word(text + i + 1, len - i - 1, "include")
                                   || doc_word(text + i + 1, len - i - 1, "echo")))
                refuse("DOCUMENT CREATE TEMPLATE text with symbols or template commands");
            if (text[i] == '&' && i + 1 < len && isalpha(text[i + 1])) {
                int j = i + 1;
                while (j < len && (isalnum(text[j]) || text[j] == '.' || text[j] == '_' || text[j] == '-')) j++;
                if (j < len && text[j] == ';')
                    refuse("DOCUMENT CREATE TEMPLATE text with symbols or template commands");
            }
        }
        doc_new(text, len, tok, toklen);
        free(text);
        return 0;
    }
    return doc_new((unsigned char *)"", 0, tok, toklen);
}

/* DOCUMENT RETRIEVE DOCTOKEN(tok) INTO(into) MAXLENGTH(GG-LEN) DATAONLY: at most GG-LEN bytes go INTO (the rest of INTO
 * is left alone), GG-LEN is set to the document's length -- the length it needs when truncated, LENGERR RESP2 2. NOTFND
 * RESP2 1 for a token CICS did not give; LENGERR RESP2 1 for a negative MAXLENGTH (GG-LEN left alone). More bytes than
 * INTO holds are refused. */
int GGCDOCR(gg_cics *c, char *tok, int toklen, char *into, int intolen) {
    char want[100];
    int i, n, copied;
    c->resp = NORMAL;
    c->resp2 = 0;
    trim(tok, toklen < 99 ? toklen : 99, want);
    for (i = 0; i < ndocs; i++) {
        char t[17];
        snprintf(t, sizeof t, "GGDOC%011d", i + 1);
        if (strcmp(t, want) == 0) break;
    }
    if (i == ndocs || doc_dead[i]) { c->resp = NOTFND; c->resp2 = 1; return 0; }
    if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    n = doc_len[i];
    copied = n < c->len ? n : c->len;
    if (copied > intolen) refuse("DOCUMENT RETRIEVE MAXLENGTH beyond INTO");
    memcpy(into, docs[i], (size_t)copied);
    if (n > c->len) { c->resp = LENGERR; c->resp2 = 2; }
    c->len = n;
    return 0;
}

static void web_flush(void); /* #4941 */

/* The program returned to the driver without a RETURN / XCTL / ABEND. */
int GGCEND(gg_cics *c) {
    (void)c;
    /* the task's program GOBACKed with no RETURN / XCTL / ABEND: at the highest level that GOBACK is the
     * RETURN (no TRANSID, no COMMAREA), as GGCPEND has it for a task run through GGCRUN */
    if (!ended) return_event("", NULL, 0);
    web_flush(); /* #4941: an ACTION(EVENTUAL) WEB SEND goes out at the end of the task */
    containers_out();
    child_end(); /* #4950 */
    return 0;
}

/* ---- #4767 zECS: CICS web support as an HTTP client -- WEB OPEN, WEB CONVERSE, WEB CLOSE (IBM CICS TS, EXEC CICS WEB OPEN,
 * WEB CONVERSE, WEB CLOSE; register X35) ----
 * The server is not part of the region: the peers are a fact the runner states, the file $GGCICS_HTTP names (unstated, every
 * WEB command is refused). Per peer a line `P SCHEME HOSTHEX PORT URIMAP|- PATHHEX|-`, then its responses, one per request,
 * `X METHOD PATHHEX QUERYHEX|- STATUS STATUSTEXTHEX|- MEDIATYPEHEX|- BODYHEX|-` (hex: the bytes in the program's page; '-':
 * none). The exchange is in the program's characters: conversion changes nothing within the model. As CicsTask (the Java
 * side) answers. */
#define WEB_MAXX 256
#define WEB_MAXP 32
#define WEB_TXT 4096
typedef struct { char scheme[8], host[WEB_TXT], urimap[9], path[WEB_TXT]; int port, haspath; } web_peer;
typedef struct { int peer, status; char method[8], path[WEB_TXT], query[WEB_TXT], stext[WEB_TXT], media[WEB_TXT];
                 char *body; int bodylen; } web_x;
static web_peer web_peers[WEB_MAXP];
static web_x web_xs[WEB_MAXX];
static int web_npeers = -1, web_nxs = 0, web_answered[WEB_MAXX], web_seq = 0;
static struct { char token[9]; int peer, byurimap, open; } web_sess[64];
static int web_nsess = 0;

static int web_hexval(int ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    refuse("WEB: $GGCICS_HTTP holds a value that is not hex");
    return 0;
}

/* hex (or '-') -> bytes in dst (NUL-terminated as well), its length */
static int web_unhex(const char *hex, char *dst, int cap) {
    int n = strcmp(hex, "-") == 0 ? 0 : (int)strlen(hex) / 2;
    if (n >= cap) refuse("WEB: a stated value too long");
    for (int i = 0; i < n; i++) dst[i] = (char)(web_hexval(hex[2 * i]) * 16 + web_hexval(hex[2 * i + 1]));
    dst[n] = '\0';
    return n;
}

static void web_load(void) {
    const char *env = getenv("GGCICS_HTTP");
    static char line[70000];
    if (web_npeers >= 0) return;
    if (!env) refuse("WEB: the HTTP peers are not stated for this task");
    FILE *f = fopen(env, "r");
    if (!f) refuse("WEB: the HTTP peers are not stated for this task");
    web_npeers = 0;
    while (fgets(line, sizeof line, f)) {
        static char a[8][33000];
        if (strlen(line) > 32000) refuse("WEB: a stated response longer than 16000 bytes");
        int k = sscanf(line, "%32999s %32999s %32999s %32999s %32999s %32999s %32999s %32999s",
                       a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
        if (k == 6 && strcmp(a[0], "P") == 0 && web_npeers < WEB_MAXP) {
            web_peer *p = &web_peers[web_npeers++];
            snprintf(p->scheme, sizeof p->scheme, "%s", a[1]);
            web_unhex(a[2], p->host, WEB_TXT);
            p->port = atoi(a[3]);
            snprintf(p->urimap, sizeof p->urimap, "%s", strcmp(a[4], "-") == 0 ? "" : a[4]);
            p->haspath = strcmp(a[5], "-") != 0;
            web_unhex(a[5], p->path, WEB_TXT);
        } else if (k == 8 && strcmp(a[0], "X") == 0 && web_npeers > 0 && web_nxs < WEB_MAXX) {
            web_x *x = &web_xs[web_nxs++];
            x->peer = web_npeers - 1;
            snprintf(x->method, sizeof x->method, "%s", a[1]);
            web_unhex(a[2], x->path, WEB_TXT);
            web_unhex(a[3], x->query, WEB_TXT);
            x->status = atoi(a[4]);
            web_unhex(a[5], x->stext, WEB_TXT);
            web_unhex(a[6], x->media, WEB_TXT);
            x->body = malloc(strlen(a[7]) / 2 + 2);
            if (!x->body) refuse("out of memory");
            x->bodylen = web_unhex(a[7], x->body, (int)strlen(a[7]) / 2 + 2);
        }
    }
    fclose(f);
}

static void web_hex(const char *src, int n, char *dst) {
    if (n == 0) { strcpy(dst, "-"); return; }
    for (int i = 0; i < n; i++) sprintf(dst + 2 * i, "%02X", (unsigned char)src[i]);
}

static int web_same_host(const char *a, const char *b) { /* host names compare without case (ASSUMED, X35) */
    while (*a && *b && tolower((unsigned char)*a) == tolower((unsigned char)*b)) { a++; b++; }
    return *a == '\0' && *b == '\0';
}

static int web_session(const char *token) {
    for (int i = 0; i < web_nsess; i++)
        if (web_sess[i].open && memcmp(web_sess[i].token, token, 8) == 0) return i;
    return -1;
}

static void web_opened(gg_cics *c, char *token, int peer, int byurimap) {
    if (web_nsess >= 64) refuse("WEB OPEN: more than 64 sessions in one task");
    snprintf(web_sess[web_nsess].token, 9, "GGWS%04d", ++web_seq);
    web_sess[web_nsess].peer = peer;
    web_sess[web_nsess].byurimap = byurimap;
    web_sess[web_nsess].open = 1;
    memcpy(token, web_sess[web_nsess].token, 8);
    web_nsess++;
    c->resp = NORMAL;
    c->resp2 = 0;
}

/* WEB OPEN: GG-FLAGS URIMAP (the name in GG-NAME1) or HOST (GG-LEN HOSTLENGTH, GG-ITEM the SCHEME CVDA, GG-NUM the
 * PORTNUMBER when GG-FLAGS also names PORT). LENGERR 21, INVREQ 40 / 138; the SESSTOKEN written on NORMAL only. */
int GGCWOPN(gg_cics *c, char *token, char *host, int hostcap) {
    char flags[41], name[9], h[WEB_TXT];
    int conds = 0, port, n = c->len;
    const char *sch;
    web_load();
    trim(c->flags, 40, flags);
    if (strncmp(flags, "URIMAP", 6) == 0) {
        trim(c->name1, 8, name);
        for (int i = 0; i < web_npeers; i++)
            if (strcmp(web_peers[i].urimap, name) == 0) { web_opened(c, token, i, 1); return 0; }
        refuse("WEB OPEN of a peer the run does not state");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n <= 0) { c->resp = LENGERR; c->resp2 = 21; conds++; }
    else if (n > hostcap) refuse("WEB OPEN HOSTLENGTH beyond HOST");
    sch = c->item == 1096 ? "HTTP" : c->item == 1029 ? "HTTPS" : NULL;
    if (!sch) { c->resp = INVREQ; c->resp2 = 40; conds++; }
    port = strstr(flags, "PORT") ? c->num : (sch && strcmp(sch, "HTTPS") == 0 ? 443 : 80);
    if (strstr(flags, "PORT") && port > 65535) { c->resp = INVREQ; c->resp2 = 138; conds++; }
    else if (strstr(flags, "PORT") && port < 1) refuse("WEB OPEN PORTNUMBER below 1");
    if (conds > 1) refuse("WEB OPEN with more than one condition at once");
    if (conds == 1) return 0;
    if (n >= WEB_TXT) refuse("WEB OPEN HOSTLENGTH beyond HOST");
    memcpy(h, host, (size_t)n);
    h[n] = '\0';
    for (int i = 0; i < web_npeers; i++) {
        if (strcmp(web_peers[i].scheme, sch) == 0 && web_same_host(web_peers[i].host, h) && web_peers[i].port == port) {
            web_opened(c, token, i, 0);
            return 0;
        }
    }
    refuse("WEB OPEN of a peer the run does not state");
    return 0;
}

/* WEB CONVERSE: GG-NUM the METHOD CVDA (out: STATUSCODE), GG-HOURS PATHLENGTH, GG-MINS QUERYSTRLEN, GG-SECS FROMLENGTH,
 * GG-LEN MAXLENGTH (out: TOLENGTH), GG-ITEM STATUSLEN (-1: no STATUSTEXT); GG-FLAGS names PATH QUERY FROM MEDIA given.
 * The conditions IBM lists for what the program gives come back with nothing sent; a response longer than MAXLENGTH is
 * truncated (LENGERR 57). INTO, STATUSTEXT and MEDIATYPE are written here, when a response came back. */
int GGCWCNV(gg_cics *c, char *token, char *path, int pathcap, char *query, int querycap, char *from, int fromcap,
            char *media, int mediacap, char *into, int intocap, char *stext, int stextcap) {
    char flags[41], ev[WEB_TXT * 9 + 400], p[WEB_TXT], q[WEB_TXT], mt[57], hx[4][WEB_TXT * 2 + 2];
    int conds = 0, s, hasp, hasq, hasf, hasm, pl = c->hours, ql = c->mins, fl = c->secs, max = c->len, sl = c->item;
    int method = c->num, body = 0, x = -1, n, mtl = 0;
    const char *m = method == 748 ? "GET" : method == 750 ? "HEAD" : method == 292 ? "DELETE" : method == 636 ? "POST"
                  : method == 749 ? "PUT" : method == 1220 ? "PATCH" : NULL;
    web_load();
    trim(c->flags, 40, flags);
    hasp = strstr(flags, "PATH") != NULL;
    hasq = strstr(flags, "QUERY") != NULL;
    hasf = strstr(flags, "FROM") != NULL;
    hasm = strstr(flags, "MEDIA") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
#define WEB_COND(r, r2) do { c->resp = (r); c->resp2 = (r2); conds++; } while (0)
    s = web_session(token);
    if (s < 0) WEB_COND(DFHRESP_NOTOPEN, 27);
    if (method == 760 || method == 759) refuse("WEB CONVERSE METHOD TRACE / OPTIONS");
    if (m) body = strcmp(m, "POST") == 0 || strcmp(m, "PUT") == 0 || strcmp(m, "PATCH") == 0;
    if (!m) WEB_COND(INVREQ, 54);
    else if (hasf && !body) WEB_COND(INVREQ, 33);
    else if (!hasf && body) WEB_COND(INVREQ, 34);
    if (hasm) {
        mtl = mediacap < 56 ? mediacap : 56;
        memcpy(mt, media, (size_t)mtl);
        while (mtl > 0 && mt[mtl - 1] == ' ') mtl--;
        mt[mtl] = '\0';
    }
    if (hasf && !hasm) WEB_COND(INVREQ, 76);
    else if (hasf && mtl == 0) refuse("WEB CONVERSE body with a blank MEDIATYPE");
    if (hasp && pl <= 0) WEB_COND(LENGERR, 5);
    if (hasq && ql <= 0) WEB_COND(LENGERR, 8);
    if (max < 0) WEB_COND(LENGERR, 16);
    else if (max == 0) refuse("WEB CONVERSE MAXLENGTH 0");
    if (hasf && fl <= 0) WEB_COND(LENGERR, 50);
    if (sl == 0 || sl < -1) WEB_COND(LENGERR, 59);
    if ((hasp && pl > pathcap) || (hasq && ql > querycap) || (hasf && fl > fromcap))
        refuse("WEB CONVERSE length beyond its area");
#undef WEB_COND
    if (conds > 1) refuse("WEB CONVERSE with more than one condition at once");
    if (conds == 1) return 0;
    if (!hasp && !web_sess[s].byurimap) refuse("WEB CONVERSE with no PATH on a session opened by HOST");
    if (hasp) {
        if (pl >= WEB_TXT) refuse("WEB CONVERSE length beyond its area");
        memcpy(p, path, (size_t)pl);
        p[pl] = '\0';
    } else {
        snprintf(p, sizeof p, "%s", web_peers[web_sess[s].peer].path);
    }
    q[0] = '\0';
    if (hasq) {
        int skip = query[0] == '?';
        if (ql >= WEB_TXT) refuse("WEB CONVERSE length beyond its area");
        memcpy(q, query + skip, (size_t)(ql - skip));
        q[ql - skip] = '\0';
    }
    for (int i = 0; i < web_nxs && x < 0; i++) {
        if (!web_answered[i] && web_xs[i].peer == web_sess[s].peer && strcmp(web_xs[i].method, m) == 0
            && strcmp(web_xs[i].path, p) == 0 && strcmp(web_xs[i].query, q) == 0) x = i;
    }
    if (x < 0) refuse("WEB CONVERSE request the peer states no response to");
    if (sl > 0 && (int)strlen(web_xs[x].stext) > sl) refuse("WEB CONVERSE status text longer than STATUSLEN");
    web_answered[x] = 1;
    n = web_xs[x].bodylen;
    if (n > max) { n = max; c->resp = LENGERR; c->resp2 = 57; }
    web_hex(web_peers[web_sess[s].peer].host, (int)strlen(web_peers[web_sess[s].peer].host), hx[0]);
    web_hex(p, (int)strlen(p), hx[1]);
    web_hex(q, (int)strlen(q), hx[2]);
    web_hex(mt, hasf ? mtl : 0, hx[3]);
    snprintf(ev, sizeof ev, "WEB-CONVERSE host=%s method=%s path=%s query=%s media=%s body=%d resp=%d resp2=%d",
             hx[0], m, hx[1], hx[2], hx[3], hasf, c->resp, c->resp2);
    event(ev, hasf ? from : NULL, hasf ? fl : 0);
    if (n > intocap) refuse("WEB CONVERSE INTO beyond its area");
    memcpy(into, web_xs[x].body, (size_t)n);
    c->len = n;
    c->num = web_xs[x].status;
    if (sl > 0) {
        int tl = (int)strlen(web_xs[x].stext);
        if (tl > stextcap) refuse("WEB CONVERSE STATUSTEXT beyond its area");
        memcpy(stext, web_xs[x].stext, (size_t)tl);
    }
    if (hasm) {
        int ml = (int)strlen(web_xs[x].media), w = mediacap < 56 ? mediacap : 56;
        for (int i = 0; i < w; i++) media[i] = i < ml ? web_xs[x].media[i] : ' ';
    }
    return 0;
}

/* WEB CLOSE: NOTOPEN 27 for a token that is not an open session's. */
int GGCWCLS(gg_cics *c, char *token) {
    int s;
    web_load();
    s = web_session(token);
    c->resp = s < 0 ? DFHRESP_NOTOPEN : NORMAL;
    c->resp2 = s < 0 ? 27 : 0;
    if (s >= 0) web_sess[s].open = 0;
    return 0;
}

/* ---- #4767 zECS: WEB PARSE URL (IBM CICS TS, EXEC CICS WEB PARSE URL; register X36) -- pure, no peer ----
 * GG-LEN URLLENGTH, GG-HOURS HOSTLENGTH, GG-MINS PATHLENGTH, GG-SECS QUERYSTRLEN (each in; out: the piece's length),
 * GG-NUM PORTNUMBER (out); GG-FLAGS names SCHEME HOST PATH QUERY given. INVREQ 28 (no "scheme://", an empty scheme or
 * host, a port that is not 1-5 digits or above 65535: ASSUMED), INVREQ 65 (a "%" not followed by two of 0-9 A-F). Refused as
 * CicsTask.webParse refuses. The areas are written on NORMAL only. */
static int web_hexd(int ch) { return (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'F'); }

int GGCWPRS(gg_cics *c, char *url, int urlcap, char *scheme, int schemecap, char *host, int hostcap, char *path,
            int pathcap, char *query, int querycap) {
    char flags[41], u[WEB_TXT], sch[17], h[WEB_TXT], pa[WEB_TXT], q[WEB_TXT];
    int n = c->len, hl = c->hours, pl = c->mins, ql = c->secs, bad28 = 0, bad65 = 0, port = -1;
    int hs, hp, hq, hc;
    char *sep, *rest, *auth_end, *tail, *qm, *colon;
    int i, auth_len, sl;
    trim(c->flags, 40, flags);
    hc = strstr(flags, "SCHEME") != NULL;
    hs = strstr(flags, "HOST") != NULL;
    hp = strstr(flags, "PATH") != NULL;
    hq = strstr(flags, "QUERY") != NULL;
    if (n <= 0) refuse("WEB PARSE URL URLLENGTH not above zero");
    if (n > urlcap || n >= WEB_TXT) refuse("WEB PARSE URL length beyond its area");
    if ((hs && hl > hostcap) || (hp && pl > pathcap) || (hq && ql > querycap)) refuse("WEB PARSE URL length beyond its area");
    memcpy(u, url, (size_t)n);
    u[n] = '\0';
    for (i = 0; i < n; i++) {
        if (u[i] == '%') {
            int ok = i + 2 < n && web_hexd(u[i + 1]) && web_hexd(u[i + 2]);
            int lower = i + 2 < n && isxdigit((unsigned char)u[i + 1]) && isxdigit((unsigned char)u[i + 2]);
            if (!ok && lower) refuse("WEB PARSE URL lowercase hex digit in an escape");
            if (!ok) bad65 = 1;
        }
    }
    if (strchr(u, '#')) refuse("WEB PARSE URL fragment");
    sep = strstr(u, "://");
    sch[0] = '\0';
    if (!sep || sep == u) bad28 = 1;
    else {
        sl = (int)(sep - u);
        if (sl > 16) refuse("WEB PARSE URL scheme other than HTTP / HTTPS");
        for (i = 0; i < sl; i++) sch[i] = (char)toupper((unsigned char)u[i]);
        sch[sl] = '\0';
        if (strcmp(sch, "HTTP") != 0 && strcmp(sch, "HTTPS") != 0) refuse("WEB PARSE URL scheme other than HTTP / HTTPS");
    }
    h[0] = pa[0] = q[0] = '\0';
    if (!bad28) {
        rest = sep + 3;
        auth_end = rest + strcspn(rest, "/?");
        auth_len = (int)(auth_end - rest);
        for (i = 0; i < auth_len; i++)
            if (rest[i] == '@' || rest[i] == '[' || rest[i] == ']') refuse("WEB PARSE URL user-info or IPv6 host");
        colon = NULL;
        for (i = 0; i < auth_len; i++) if (rest[i] == ':') colon = rest + i;
        if (colon) {
            int plen = (int)(auth_end - colon) - 1, digits = 1;
            memcpy(h, rest, (size_t)(colon - rest));
            h[colon - rest] = '\0';
            if (plen == 0) refuse("WEB PARSE URL empty port");
            for (i = 0; i < plen; i++) if (colon[1 + i] < '0' || colon[1 + i] > '9') digits = 0;
            if (!digits || plen > 5) bad28 = 1;
            else {
                port = atoi(colon + 1);
                if (port > 65535) bad28 = 1;
                else if (port == 0) refuse("WEB PARSE URL port 0");
            }
        } else {
            memcpy(h, rest, (size_t)auth_len);
            h[auth_len] = '\0';
            port = strcmp(sch, "HTTPS") == 0 ? 443 : 80;
        }
        if (h[0] == '\0') bad28 = 1;
        tail = auth_end;
        qm = strchr(tail, '?');
        memcpy(pa, tail, qm ? (size_t)(qm - tail) : strlen(tail));
        pa[qm ? (size_t)(qm - tail) : strlen(tail)] = '\0';
        snprintf(q, sizeof q, "%s", qm ? qm + 1 : "");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad28 && bad65) refuse("WEB PARSE URL with more than one condition at once");
    if (bad28) { c->resp = INVREQ; c->resp2 = 28; return 0; }
    if (bad65) { c->resp = INVREQ; c->resp2 = 65; return 0; }
    if ((hs && (int)strlen(h) > hl) || (hp && (int)strlen(pa) > pl) || (hq && (int)strlen(q) > ql))
        refuse("WEB PARSE URL piece longer than its length");
    if (hc && (int)strlen(sch) > schemecap) refuse("WEB PARSE URL length beyond its area");
    if ((hp && pa[0] == '\0') || (hq && q[0] == '\0')) refuse("WEB PARSE URL PATH or QUERYSTRING the URL has none of");
    if (hc) { memset(scheme, ' ', (size_t)schemecap); memcpy(scheme, sch, strlen(sch)); }
    if (hs) { memcpy(host, h, strlen(h)); c->hours = (int)strlen(h); }
    if (hp) { memcpy(path, pa, strlen(pa)); c->mins = (int)strlen(pa); }
    if (hq) { memcpy(query, q, strlen(q)); c->secs = (int)strlen(q); }
    c->num = port;
    return 0;
}

/* ---- #4767 zECS: WEB SEND, the server side (IBM CICS TS, EXEC CICS WEB SEND; register X37) ----
 * The task serves one inbound request the runner states: the file $GGCICS_WEBREQ names (unstated, WEB SEND is refused; only that
 * a request is stated is read here: WEB RECEIVE / EXTRACT / READ HTTPHEADER are not modelled yet). GG-LEN FROMLENGTH, GG-ITEM
 * ACTION (0: not given), GG-NUM STATUSCODE (-1: not given), GG-HOURS STATUSLEN (-1: not given), GG-MINS the conversion (0, 1
 * SRVCONVERT, 2 NOSRVCONVERT); GG-FLAGS names MEDIA STEXT given. Recorded as WEB-SEND. As CicsTask.webSend answers. */
static int web_sent = 0;        /* an ACTION(IMMEDIATE) response was sent */
static int web_send_failed = 0; /* #4941: the last WEB SEND ended in a condition */
static int web_issued = 0;      /* a WEB SEND was accepted (IMMEDIATE or EVENTUAL) */
/* #4941 (X37): the ACTION(EVENTUAL) response held for the end of the task (its WEB-SEND event line and body), the document an
 * EVENTUAL DOCTOKEN send (not DOCDELETE) sent as it was sent, and the DOCTOKEN WEB RETRIEVE gave for it (a new document). */
static int web_held = 0, web_held_len = 0, web_held_doclen = 0, web_held_tok = 0;
static char web_held_ev[WEB_TXT * 4 + 200];
static unsigned char *web_held_body = NULL, *web_held_doc = NULL;

/* The task ended: an ACTION(EVENTUAL) response is sent now (recorded after the task's other events); a task that ended in an
 * abend with one held is refused (IBM does not say whether the response is sent). As CicsTask.events. */
static void web_flush(void) {
    if (!web_held) return;
    if (terminated) refuse("WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend");
    web_held = 0;
    event(web_held_ev, (const char *)web_held_body, web_held_len);
}

static int web_send_body(gg_cics *c, const char *from, int fl, char *media, int mediacap, char *stext, int stextcap,
                         int ofdoc, int doc_i, int docstatus) {
    char flags[41], mt[57], ev[WEB_TXT * 4 + 200], hx[2][WEB_TXT * 2 + 2];
    int eventual, action = c->item, status = c->num, sl = c->hours, conv = c->mins, mtl = 0, conds = 0, hasm, hast, i;
    trim(c->flags, 40, flags);
    hasm = strstr(flags, "MEDIA") != NULL;
    hast = strstr(flags, "STEXT") != NULL;
    if (status != -1 && (status < 100 || status > 599)) refuse("WEB SEND STATUSCODE outside 100-599");
    if (hasm) {
        mtl = mediacap < 56 ? mediacap : 56;
        memcpy(mt, media, (size_t)mtl);
        while (mtl > 0 && mt[mtl - 1] == ' ') mtl--;
        mt[mtl] = '\0';
        for (i = 0; i < mtl; i++) if ((unsigned char)mt[i] <= ' ' || (unsigned char)mt[i] > '~') mtl = -1;
        if (mtl < 0 || strchr(mt, '/') == NULL || mt[0] == '/' || mt[strlen(mt) - 1] == '/')
            refuse("WEB SEND MEDIATYPE blank or not type/subtype");
    }
    if (conv == 1) {
        int text = hasm && mtl >= 5 && tolower((unsigned char)mt[0]) == 't' && tolower((unsigned char)mt[1]) == 'e'
                   && tolower((unsigned char)mt[2]) == 'x' && tolower((unsigned char)mt[3]) == 't' && mt[4] == '/';
        if (!text) refuse("WEB SEND SRVCONVERT on a media type that is not text/*");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (ofdoc && doc_i < 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    if (action != 0 && action != 2 && action != 3) { c->resp = INVREQ; c->resp2 = 11; conds++; }
    if (ofdoc && docstatus != 0 && docstatus != 295 && docstatus != 296) { c->resp = INVREQ; c->resp2 = 143; conds++; }
    if ((status == 204 || status == 205 || status == 304) && fl > 0) { c->resp = INVREQ; c->resp2 = 72; conds++; }
    if (conds > 1) refuse("WEB SEND with more than one condition at once");
    if (conds == 1) { web_send_failed = 1; return 0; }
    eventual = action != 2; /* (an omitted ACTION is EVENTUAL for a send that is not chunked: IBM) */
    if (!eventual && web_held) refuse("WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send");
    web_send_failed = 0;
    web_issued = 1;
    web_hex(mt, hasm ? mtl : 0, hx[0]);
    if (hast) { int n = sl < 0 ? stextcap : sl; web_hex(stext, n, hx[1]); } else strcpy(hx[1], "-");
    snprintf(ev, sizeof ev, "WEB-SEND status=%d stext=%s media=%s action=%s resp=0 resp2=0",
             status == -1 ? 200 : status, hx[1], hx[0], eventual ? "EVENTUAL" : "IMMEDIATE");
    free(web_held_doc);
    web_held_doc = NULL;
    web_held_tok = 0;
    if (eventual) {
        free(web_held_body);
        web_held_body = malloc(fl > 0 ? (size_t)fl : 1);
        memcpy(web_held_body, from, (size_t)(fl > 0 ? fl : 0));
        web_held_len = fl;
        strcpy(web_held_ev, ev);
        web_held = 1; /* sent at the end of the task; a second send replaces it */
        if (ofdoc && docstatus != 295) {
            web_held_doc = malloc(fl > 0 ? (size_t)fl : 1);
            memcpy(web_held_doc, from, (size_t)(fl > 0 ? fl : 0));
            web_held_doclen = fl;
        }
    } else {
        web_sent = 1;
        event(ev, from, fl);
    }
    if (ofdoc && docstatus == 295) doc_dead[doc_i] = 1; /* DOCDELETE: deleted once its contents are saved for sending */
    return 0;
}

int GGCWSND(gg_cics *c, char *from, int fromcap, char *media, int mediacap, char *stext, int stextcap) {
    char flags[41];
    int fl = c->len, sl = c->hours, hast;
    const char *env = getenv("GGCICS_WEBREQ");
    FILE *f;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    fclose(f);
    if (web_sent) refuse("WEB SEND after a response was sent");
    trim(c->flags, 40, flags);
    hast = strstr(flags, "STEXT") != NULL;
    if (fl <= 0 || (hast && sl == 0) || sl < -1) refuse("WEB SEND FROMLENGTH or STATUSLEN not above zero");
    if (fl > fromcap || (hast && sl > stextcap)) refuse("WEB SEND length beyond its area");
    return web_send_body(c, from, fl, media, mediacap, stext, stextcap, 0, -1, 0);
}

/* WEB SEND DOCTOKEN(tok) (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response is the document the token names,
 * one the task created, as it is now; an empty document is no message body (ASSUMED), so a 204 may send one. GG-SECS is
 * DOCSTATUS's CVDA (0: not given; 295 DOCDELETE, 296 NODOCDELETE). As CicsTask.webSendDocument. */
int GGCWSDC(gg_cics *c, char *tok, int toklen, char *media, int mediacap, char *stext, int stextcap) {
    char flags[41], want[100];
    int sl = c->hours, hast, i;
    const char *env = getenv("GGCICS_WEBREQ");
    FILE *f;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    fclose(f);
    if (web_sent) refuse("WEB SEND after a response was sent");
    trim(c->flags, 40, flags);
    hast = strstr(flags, "STEXT") != NULL;
    trim(tok, toklen < 99 ? toklen : 99, want);
    for (i = 0; i < ndocs; i++) {
        char t[17];
        snprintf(t, sizeof t, "GGDOC%011d", i + 1);
        if (strcmp(t, want) == 0) break;
    }
    if ((hast && sl == 0) || sl < -1) refuse("WEB SEND FROMLENGTH or STATUSLEN not above zero");
    if (hast && sl > stextcap) refuse("WEB SEND length beyond its area");
    if (i == ndocs || doc_dead[i]) i = -1; /* NOTFND 1: not created, deleted or wrongly named (IBM lists one RESP2) */
    return web_send_body(c, i < 0 ? "" : (const char *)docs[i], i < 0 ? 0 : doc_len[i], media, mediacap, stext, stextcap, 1,
                         i, c->secs);
}

/* ---- #4767 zECS: the server reading the request it serves (IBM CICS TS, EXEC CICS WEB EXTRACT, WEB RECEIVE, WEB READ
 * HTTPHEADER, WEB WRITE HTTPHEADER; register X38) ----
 * The request is the file $GGCICS_WEBREQ names (unstated, each command is refused): `R SCHEME HOSTHEX PORT METHOD PATHHEX
 * QUERYHEX|-`, `V VERSIONHEX`, `B MEDIAHEX BODYHEX|-` (none: no body) and a `H NAMEHEX VALUEHEX|-` line per header. As
 * CicsTask.webExtract / webReceive / webReadHeader / webWriteHeader answer. */
#define WEB_MAXH 64
static struct { int loaded, hasbody, nh; char scheme[8], host[WEB_TXT], method[16], path[WEB_TXT], query[WEB_TXT],
                version[64], media[WEB_TXT], *body; int port, bodylen; char hname[WEB_MAXH][256];
                char *hval[WEB_MAXH]; } webreq;
static int web_received = 0;

static void webreq_load(void) {
    const char *env = getenv("GGCICS_WEBREQ");
    static char line[70000], a[8][33000];
    FILE *f;
    if (webreq.loaded) return;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int k = sscanf(line, "%32999s %32999s %32999s %32999s %32999s %32999s %32999s", a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
        if (k == 7 && strcmp(a[0], "R") == 0) {
            snprintf(webreq.scheme, sizeof webreq.scheme, "%s", a[1]);
            web_unhex(a[2], webreq.host, WEB_TXT);
            webreq.port = atoi(a[3]);
            snprintf(webreq.method, sizeof webreq.method, "%s", a[4]);
            web_unhex(a[5], webreq.path, WEB_TXT);
            web_unhex(a[6], webreq.query, WEB_TXT);
        } else if (k == 2 && strcmp(a[0], "V") == 0) {
            web_unhex(a[1], webreq.version, (int)sizeof webreq.version);
        } else if (k == 3 && strcmp(a[0], "B") == 0) {
            webreq.hasbody = 1;
            web_unhex(a[1], webreq.media, WEB_TXT);
            webreq.body = malloc(strlen(a[2]) / 2 + 2);
            if (!webreq.body) refuse("out of memory");
            webreq.bodylen = web_unhex(a[2], webreq.body, (int)strlen(a[2]) / 2 + 2);
        } else if (k == 3 && strcmp(a[0], "H") == 0 && webreq.nh < WEB_MAXH) {
            int n = web_unhex(a[1], webreq.hname[webreq.nh], 256);
            webreq.hname[webreq.nh][n] = '\0';
            webreq.hval[webreq.nh] = malloc(strlen(a[2]) / 2 + 2);
            if (!webreq.hval[webreq.nh]) refuse("out of memory");
            web_unhex(a[2], webreq.hval[webreq.nh], (int)strlen(a[2]) / 2 + 2);
            webreq.nh++;
        }
    }
    fclose(f);
    webreq.loaded = 1;
}

/* GG-LEN HOSTLENGTH, GG-HOURS METHODLENGTH, GG-MINS VERSIONLEN, GG-SECS PATHLENGTH, GG-ITEM QUERYSTRLEN (each in; out: the
 * piece's length); GG-FLAGS names HOST METHOD VERSION PATH QUERY given; out: GG-NUM the port, GG-NAME1 the scheme. */
int GGCWEXT(gg_cics *c, char *host, int hostcap, char *method, int methodcap, char *version, int versioncap, char *path,
            int pathcap, char *query, int querycap) {
    char flags[41];
    int hs, hm, hv, hp, hq, hl = c->len, ml = c->hours, vl = c->mins, pl = c->secs, ql = c->item, conds = 0;
    webreq_load();
    trim(c->flags, 40, flags);
    hs = strstr(flags, "HOST") != NULL;
    hm = strstr(flags, "METHOD") != NULL;
    hv = strstr(flags, "VERSION") != NULL;
    hp = strstr(flags, "PATH") != NULL;
    hq = strstr(flags, "QUERY") != NULL;
    if ((hs && hl > hostcap) || (hm && ml > methodcap) || (hv && vl > versioncap) || (hp && pl > pathcap)
        || (hq && ql > querycap)) refuse("WEB EXTRACT length beyond its area");
    if ((hm && ml <= 0) || (hq && ql <= 0)) refuse("WEB EXTRACT METHODLENGTH or QUERYSTRLEN not above zero");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (hs && hl <= 0) { c->resp = LENGERR; c->resp2 = 21; conds++; }
    if (hp && pl <= 0) { c->resp = LENGERR; c->resp2 = 5; conds++; }
    if (hv && vl <= 0) { c->resp = LENGERR; c->resp2 = 7; conds++; }
    if (conds > 1) refuse("WEB EXTRACT with more than one condition at once");
    if (conds == 1) return 0;
    if ((hs && (int)strlen(webreq.host) > hl) || (hm && (int)strlen(webreq.method) > ml)
        || (hv && (int)strlen(webreq.version) > vl) || (hp && (int)strlen(webreq.path) > pl)
        || (hq && (int)strlen(webreq.query) > ql)) refuse("WEB EXTRACT piece longer than its length");
    if (hs) { memcpy(host, webreq.host, strlen(webreq.host)); c->len = (int)strlen(webreq.host); }
    if (hm) { memcpy(method, webreq.method, strlen(webreq.method)); c->hours = (int)strlen(webreq.method); }
    if (hv) { memcpy(version, webreq.version, strlen(webreq.version)); c->mins = (int)strlen(webreq.version); }
    if (hp) { memcpy(path, webreq.path, strlen(webreq.path)); c->secs = (int)strlen(webreq.path); }
    if (hq) { memcpy(query, webreq.query, strlen(webreq.query)); c->item = (int)strlen(webreq.query); }
    c->num = webreq.port;
    memset(c->name1, ' ', sizeof c->name1);
    memcpy(c->name1, webreq.scheme, strlen(webreq.scheme));
    return 0;
}

/* ---- #4972: EXTRACT TCPIP, the connection the task was started on (IBM CICS TS, EXEC CICS EXTRACT TCPIP; register X38) ----
 * The connection is the file $GGCICS_TCPIP names (unstated, EXTRACT TCPIP is refused): `T CLIENTADDR CLIENTNAMEHEX|-
 * SERVERADDR SERVERNAMEHEX|- PORT SSLTYPE`, the names in hex ("-": the DNS knows none). As CicsTask.extractTcpip answers. */
static struct { int loaded, port, hascname, hassname; char caddr[64], saddr[64], ssl[16], cname[WEB_TXT],
                sname[WEB_TXT]; } tcpipc;

static void tcpip_load(void) {
    const char *env = getenv("GGCICS_TCPIP");
    static char line[70000], a[8][33000];
    FILE *f;
    if (tcpipc.loaded) return;
    if (!env || !(f = fopen(env, "r"))) refuse("the TCP/IP connection is not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int k = sscanf(line, "%32999s %32999s %32999s %32999s %32999s %32999s %32999s", a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
        if (k == 7 && strcmp(a[0], "T") == 0) {
            snprintf(tcpipc.caddr, sizeof tcpipc.caddr, "%s", a[1]);
            tcpipc.hascname = strcmp(a[2], "-") != 0;
            web_unhex(a[2], tcpipc.cname, WEB_TXT);
            snprintf(tcpipc.saddr, sizeof tcpipc.saddr, "%s", a[3]);
            tcpipc.hassname = strcmp(a[4], "-") != 0;
            web_unhex(a[4], tcpipc.sname, WEB_TXT);
            tcpipc.port = atoi(a[5]);
            snprintf(tcpipc.ssl, sizeof tcpipc.ssl, "%s", a[6]);
        }
    }
    fclose(f);
    tcpipc.loaded = 1;
}

/* An IPv4 address in dotted decimal as a number (-1: it is not one: four decimal parts 0-255, no leading zero). */
static long long ipv4_value(const char *s) { /* long long: `long` is 32 bits on Windows, and 192.x is above 2^31 */
    long long value = 0;
    int parts = 0;
    while (1) {
        int n = 0, digits = 0;
        if (*s == '0' && s[1] >= '0' && s[1] <= '9') return -1;
        while (*s >= '0' && *s <= '9') {
            n = n * 10 + (*s++ - '0');
            if (++digits > 3) return -1;
        }
        if (digits == 0 || n > 255) return -1;
        value = value * 256 + n;
        parts++;
        if (*s == '\0') break;
        if (*s++ != '.') return -1;
    }
    return parts == 4 ? value : -1;
}

/* GG-LEN CADDRLENGTH, GG-HOURS CNAMELENGTH, GG-MINS SADDRLENGTH, GG-SECS SNAMELENGTH (each in, 0 when the option is missing;
 * out: the piece's length); GG-FLAGS names A1 N1 A2 N2 (client address, client name, server address, server name given) and U1 U2 F1 F2 (a number asked
 * for). The numbers come from GGCTCPN. */
int GGCTCPX(gg_cics *c, char *caddr, int caddrcap, char *cname, int cnamecap, char *saddr, int saddrcap, char *sname,
            int snamecap) {
    char flags[81];
    int ca, cn, sa, sn, cnu, snu, cf, sf, cl = c->len, nl = c->hours, sl = c->mins, ml = c->secs;
    int badlength, toosmall;
    long long cnum, snum;
    tcpip_load();
    trim(c->flags, 40, flags);
    ca = strstr(flags, "A1") != NULL;
    cn = strstr(flags, "N1") != NULL;
    sa = strstr(flags, "A2") != NULL;
    sn = strstr(flags, "N2") != NULL;
    cnu = strstr(flags, "U1") != NULL;
    snu = strstr(flags, "U2") != NULL;
    cf = strstr(flags, "F1") != NULL;
    sf = strstr(flags, "F2") != NULL;
    if ((ca && cl > caddrcap) || (cn && nl > cnamecap) || (sa && sl > saddrcap) || (sn && ml > snamecap))
        refuse("EXTRACT TCPIP length beyond its area");
    cnum = ipv4_value(tcpipc.caddr);
    snum = ipv4_value(tcpipc.saddr);
    if (((ca || cnu || cf) && cnum < 0) || ((sa || snu || sf) && snum < 0) || (cnu && cnum > 2147483647LL)
        || (snu && snum > 2147483647LL)) refuse("EXTRACT TCPIP address");
    if (sn && !tcpipc.hassname) refuse("EXTRACT TCPIP");
    badlength = (ca && cl <= 0) || (cn && nl <= 0) || (sa && sl <= 0) || (sn && ml <= 0);
    toosmall = (ca && cl > 0 && (int)strlen(tcpipc.caddr) > cl) || (cn && nl > 0 && (int)strlen(tcpipc.cname) > nl)
               || (sa && sl > 0 && (int)strlen(tcpipc.saddr) > sl) || (sn && ml > 0 && (int)strlen(tcpipc.sname) > ml);
    if (badlength && toosmall) refuse("EXTRACT TCPIP with more than one condition at once");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (badlength) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    if (toosmall) refuse("EXTRACT TCPIP");
    if (ca) { memcpy(caddr, tcpipc.caddr, strlen(tcpipc.caddr)); c->len = (int)strlen(tcpipc.caddr); }
    if (cn) { memcpy(cname, tcpipc.cname, strlen(tcpipc.cname)); c->hours = (int)strlen(tcpipc.cname); }
    if (sa) { memcpy(saddr, tcpipc.saddr, strlen(tcpipc.saddr)); c->mins = (int)strlen(tcpipc.saddr); }
    if (sn) { memcpy(sname, tcpipc.sname, strlen(tcpipc.sname)); c->secs = (int)strlen(tcpipc.sname); }
    return 0;
}

/* GG-FLAGS names one of CNU SNU PORT SSL; out: GG-NUM (the SSL type as its CVDA). Only after a NORMAL GGCTCPX. */
int GGCTCPN(gg_cics *c) {
    char flags[41];
    tcpip_load();
    trim(c->flags, 40, flags);
    if (strcmp(flags, "CNU") == 0) c->num = (int)ipv4_value(tcpipc.caddr);
    else if (strcmp(flags, "SNU") == 0) c->num = (int)ipv4_value(tcpipc.saddr);
    else if (strcmp(flags, "PORT") == 0) c->num = tcpipc.port;
    else c->num = strcmp(tcpipc.ssl, "SSL") == 0 ? 1030 : strcmp(tcpipc.ssl, "NOSSL") == 0 ? 1031
                  : strcmp(tcpipc.ssl, "CLIENTAUTH") == 0 ? 1032 : 1205;
    return 0;
}

/* GG-NUM MAXLENGTH; GG-FLAGS names MEDIA given; out: GG-LEN the bytes returned. */
int GGCWRCV(gg_cics *c, char *into, int intocap, char *media, int mediacap) {
    char flags[41];
    int hm, maxl = c->num, n;
    webreq_load();
    trim(c->flags, 40, flags);
    hm = strstr(flags, "MEDIA") != NULL;
    if (!webreq.hasbody) refuse("WEB RECEIVE of a request with no body");
    if (web_received) refuse("a second WEB RECEIVE");
    if (maxl > intocap) refuse("WEB RECEIVE length beyond its area");
    if (hm && mediacap < 56) refuse("WEB RECEIVE length beyond its area");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (maxl <= 0) { c->resp = LENGERR; c->resp2 = 16; return 0; }
    web_received = 1;
    n = webreq.bodylen > maxl ? maxl : webreq.bodylen;
    if (webreq.bodylen > maxl) { c->resp = LENGERR; c->resp2 = 57; }
    memcpy(into, webreq.body, (size_t)n);
    c->len = n;
    if (hm) {
        if ((int)strlen(webreq.media) > 56) refuse("WEB RECEIVE length beyond its area");
        memset(media, ' ', 56);
        memcpy(media, webreq.media, strlen(webreq.media));
    }
    return 0;
}

/* GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in; out: the value's length); the value into `value`. */
int GGCWRDH(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int nl = c->len, vl = c->num, i, found = -1, nfound = 0, ci = 0, conds = 0;
    char n[257];
    webreq_load();
    if (nl <= 0 || nl > namecap || nl > 256) refuse("WEB READ HTTPHEADER NAMELENGTH not above zero or past its area");
    if (vl > valuecap) refuse("WEB READ HTTPHEADER length beyond its area");
    memcpy(n, name, (size_t)nl);
    n[nl] = '\0';
    for (i = 0; i < webreq.nh; i++) {
        if (strcmp(webreq.hname[i], n) == 0) { found = i; nfound++; }
        else if (strlen(webreq.hname[i]) == strlen(n)) {
            size_t j;
            int same = 1;
            for (j = 0; j < strlen(n); j++) if (tolower((unsigned char)webreq.hname[i][j]) != tolower((unsigned char)n[j])) same = 0;
            if (same) ci = 1;
        }
    }
    if (nfound == 0 && ci) refuse("WEB READ HTTPHEADER header name found only without case");
    if (nfound > 1) refuse("WEB READ HTTPHEADER two headers of the name");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (webreq.nh == 0) { c->resp = INVREQ; c->resp2 = 43; conds++; }
    else if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    if (vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (conds > 1) refuse("WEB READ HTTPHEADER with more than one condition at once");
    if (conds == 1) return 0;
    if ((int)strlen(webreq.hval[found]) > vl) refuse("WEB READ HTTPHEADER value longer than VALUELENGTH");
    memcpy(value, webreq.hval[found], strlen(webreq.hval[found]));
    c->num = (int)strlen(webreq.hval[found]);
    return 0;
}

/* GG-LEN NAMELENGTH, GG-NUM VALUELENGTH. Recorded as WEB-HEADER. */
int GGCWWRH(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int nl = c->len, vl = c->num, conds = 0, i;
    char hx[2][WEB_TXT * 2 + 2];
    webreq_load();
    if (web_sent || web_held) refuse("WEB WRITE HTTPHEADER after the response was sent");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (nl <= 0) { c->resp = LENGERR; c->resp2 = 35; conds++; }
    if (vl <= 0 || vl > 32000) { c->resp = LENGERR; c->resp2 = 55; conds++; }
    if (conds > 1) refuse("WEB WRITE HTTPHEADER with more than one condition at once");
    if (conds == 1) return 0;
    if (nl > namecap || vl > valuecap) refuse("WEB WRITE HTTPHEADER length beyond its area");
    if (nl >= WEB_TXT || vl >= WEB_TXT) refuse("WEB WRITE HTTPHEADER length beyond its area");
    for (i = 0; i < nl; i++)
        if (name[i] == ' ' || name[i] == ':') refuse("WEB WRITE HTTPHEADER name blank or holding a blank or a colon");
    web_hex(name, nl, hx[0]);
    web_hex(value, vl, hx[1]);
    {
        char ev[WEB_TXT * 4 + 100];
        snprintf(ev, sizeof ev, "WEB-HEADER name=%s value=%s resp=0 resp2=0", hx[0], hx[1]);
        event(ev, NULL, 0);
    }
    return 0;
}

/* ---- #4771 (register X47): storage CICS acquires for the task, addressed by a pointer. A block is registered when GETMAIN or
 * WEB RECEIVE SET hands it out (the pointer item `slot` then holds its address), so FREEMAIN can tell storage GETMAIN returned
 * from any other address. A freed block is kept (never reused), so a second FREEMAIN of it is recognised and refused. */
enum { BLK_GETMAIN = 0, BLK_RECEIVED = 1, BLK_FREED = 2 };
static struct { void *p; int kind; } blks[8192];
static int nblks = 0;

static void *blk_new(size_t n, int kind) {
    void *p;
    if (nblks >= 8192) refuse("more than 8192 blocks of task storage");
    p = calloc(n ? n : 1, 1);
    if (!p) refuse("GETMAIN length beyond the limit");
    blks[nblks].p = p;
    blks[nblks].kind = kind;
    nblks++;
    return p;
}

/* GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(byte) (IBM CICS TS, EXEC CICS GETMAIN): GG-NUM the length, GG-FLAGS "SHORT" for the
 * LENGTH form; LENGERR RESP2 1 for FLENGTH below 1 / LENGTH zero (ptr set to zero). Refused: a length above the limit, a LENGTH
 * above 65520, an INITIMG that is not one byte. */
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen) {
    char flags[41];
    long long n = c->num;
    trim(c->flags, 40, flags);
    if (imglen != 1) refuse("GETMAIN INITIMG is not one byte");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n < 1) { c->resp = LENGERR; c->resp2 = 1; *slot = NULL; return 0; }
    if (n > 268435456LL || (strcmp(flags, "SHORT") == 0 && n > 65520)) refuse("GETMAIN length beyond the limit");
    *slot = blk_new((size_t)n, BLK_GETMAIN);
    memset(*slot, (unsigned char)img[0], (size_t)n);
    return 0;
}

/* GGCFREM: FREEMAIN DATAPOINTER(ptr): INVREQ RESP2 1 for an address GETMAIN did not return (a null pointer, a record's address). Refused:
 * storage already freed, a WEB RECEIVE SET body (IBM does not say whether FREEMAIN is allowed). */
int GGCFREM(gg_cics *c, void **slot) {
    int i;
    c->resp = NORMAL;
    c->resp2 = 0;
    for (i = 0; i < nblks; i++) {
        if (blks[i].p == *slot) {
            if (blks[i].kind != BLK_GETMAIN) refuse("FREEMAIN of storage already freed or received");
            blks[i].kind = BLK_FREED;
            return 0;
        }
    }
    c->resp = INVREQ;
    c->resp2 = 1;
    return 0;
}

/* WEB RECEIVE SET(ptr) LENGTH(area) [MAXLENGTH(n)] [MEDIATYPE(area)] (X38, X47): the body as a new block the pointer addresses; GG-NUM
 * MAXLENGTH (2147483647 when not given); GG-FLAGS names MEDIA given; out: GG-LEN the bytes returned. LENGERR 16 leaves the pointer
 * as it was (ASSUMED); a body cut at MAXLENGTH is LENGERR 57 with the pointer set. */
int GGCWRCS(gg_cics *c, void **slot, char *media, int mediacap) {
    char flags[41];
    int hm, maxl = c->num, n;
    webreq_load();
    trim(c->flags, 40, flags);
    hm = strstr(flags, "MEDIA") != NULL;
    if (!webreq.hasbody) refuse("WEB RECEIVE of a request with no body");
    if (web_received) refuse("a second WEB RECEIVE");
    if (hm && mediacap < 56) refuse("WEB RECEIVE length beyond its area");
    if (webreq.bodylen > 268435456) refuse("WEB RECEIVE SET body beyond the limit");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (maxl <= 0) { c->resp = LENGERR; c->resp2 = 16; return 0; }
    web_received = 1;
    n = webreq.bodylen > maxl ? maxl : webreq.bodylen;
    if (webreq.bodylen > maxl) { c->resp = LENGERR; c->resp2 = 57; }
    *slot = blk_new((size_t)n, BLK_RECEIVED);
    memcpy(*slot, webreq.body, (size_t)n);
    c->len = n;
    if (hm) {
        if ((int)strlen(webreq.media) > 56) refuse("WEB RECEIVE length beyond its area");
        memset(media, ' ', 56);
        memcpy(media, webreq.media, strlen(webreq.media));
    }
    return 0;
}

/* WEB RETRIEVE DOCTOKEN(tok) (IBM CICS TS, EXEC CICS WEB RETRIEVE; register X41): NORMAL (the DOCTOKEN written to `tok`) for a
 * last WEB SEND that was a document send with ACTION(EVENTUAL) and no DOCDELETE -- the token names a copy of the document as it
 * was sent (ASSUMED: a new document of the task, the same token for every retrieve of that send); INVREQ RESP2 2 no WEB SEND
 * issued; NOTFND RESP2 1 the last WEB SEND was DOCDELETE or not an EVENTUAL document send. As CicsTask.webRetrieve. */
int GGCWRTV(gg_cics *c, char *tok, int toklen) {
    char t[17];
    int i;
    webreq_load();
    if (web_send_failed) refuse("WEB RETRIEVE after a WEB SEND that ended in a condition");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_issued) { c->resp = INVREQ; c->resp2 = 2; return 0; }
    if (!web_held_doc) { c->resp = NOTFND; c->resp2 = 1; return 0; }
    if (!web_held_tok) {
        doc_new(web_held_doc, web_held_doclen, t, 16);
        web_held_tok = ndocs;
    }
    snprintf(t, sizeof t, "GGDOC%011d", web_held_tok);
    for (i = 0; i < toklen && i < 16; i++) tok[i] = t[i];
    for (; i < toklen; i++) tok[i] = ' ';
    return 0;
}

/* ---- #4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (HTTPHEADER, FORMFIELD, QUERYPARM) ----
 * GG-ITEM names the kind (0 HTTPHEADER, 1 FORMFIELD, 2 QUERYPARM). FORMFIELD reads the name=value pairs of the body (a form,
 * application/x-www-form-urlencoded), QUERYPARM those of the query string (both unescaped: %XX only), HTTPHEADER the headers.
 * As CicsTask.webReadParam / webStartBrowse / webReadNext / webEndBrowse answer. */
static const char *const web_kinds[3] = {"HTTPHEADER", "FORMFIELD", "QUERYPARM"};
static int web_browse_on[3], web_browse_at[3], web_browse_end[3];
typedef struct { int n; char **name, **value; } web_pairs;

static void web_badform(int kind) {
    char m[80];
    snprintf(m, sizeof m, "WEB %s data outside the modelled name=value form", web_kinds[kind]);
    refuse(m);
}

static char *web_plain(int kind, const char *s, int len) {
    char *o = malloc((size_t)len + 1);
    int n = 0, i;
    if (!o) refuse("out of memory");
    for (i = 0; i < len; i++) {
        unsigned char ch = (unsigned char)s[i];
        if (ch == '+' || ch == ';' || ch <= ' ' || ch > '~') web_badform(kind);
        if (ch == '%') {
            int hi, lo;
            if (i + 2 >= len || !isxdigit((unsigned char)s[i + 1]) || !isxdigit((unsigned char)s[i + 2])) web_badform(kind);
            hi = web_hexval(s[i + 1]);
            lo = web_hexval(s[i + 2]);
            if (hi * 16 + lo < 32 || hi * 16 + lo > 126) web_badform(kind);
            o[n++] = (char)(hi * 16 + lo);
            i += 2;
        } else {
            o[n++] = (char)ch;
        }
    }
    o[n] = '\0';
    return o;
}

/* the pairs of the kind; 0 when the request has none */
static int web_getpairs(int kind, web_pairs *p) {
    const char *data, *piece;
    int i;
    p->n = 0;
    if (kind == 0) {
        p->name = malloc(sizeof(char *) * (size_t)(webreq.nh + 1));
        p->value = malloc(sizeof(char *) * (size_t)(webreq.nh + 1));
        for (i = 0; i < webreq.nh; i++) { p->name[i] = webreq.hname[i]; p->value[i] = webreq.hval[i]; }
        p->n = webreq.nh;
        return webreq.nh > 0;
    }
    data = kind == 2 ? webreq.query : (webreq.hasbody ? webreq.body : "");
    if (kind == 1 && data[0] != '\0' && strcasecmp(webreq.media, "application/x-www-form-urlencoded") != 0)
        refuse("WEB FORMFIELD body not application/x-www-form-urlencoded");
    if (data[0] == '\0') return 0;
    p->name = malloc(sizeof(char *) * (strlen(data) + 2));
    p->value = malloc(sizeof(char *) * (strlen(data) + 2));
    if (!p->name || !p->value) refuse("out of memory");
    for (piece = data;; ) {
        const char *amp = strchr(piece, '&'), *eq = memchr(piece, '=', amp ? (size_t)(amp - piece) : strlen(piece));
        const char *pct = memchr(piece, '%', eq ? (size_t)(eq - piece) : 0);
        size_t plen = amp ? (size_t)(amp - piece) : strlen(piece);
        if (!eq || eq == piece || pct) web_badform(kind);
        p->name[p->n] = web_plain(kind, piece, (int)(eq - piece));
        p->value[p->n] = web_plain(kind, eq + 1, (int)(plen - (size_t)(eq - piece) - 1));
        p->n++;
        if (!amp) break;
        piece = amp + 1;
    }
    return 1;
}

/* GG-ITEM kind, GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in; out: the value's whole length). */
int GGCWRDP(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int kind = c->item, nl = c->len, vl = c->num, conds = 0, i, hit = -1, nfound = 0;
    web_pairs p;
    char n[257], m[96];
    webreq_load();
    if (nl > namecap || vl > valuecap || nl > 256) {
        snprintf(m, sizeof m, "WEB READ %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_getpairs(kind, &p)) { c->resp = INVREQ; c->resp2 = 13; conds++; }
    else if (nl > 0) {
        memcpy(n, name, (size_t)nl);
        n[nl] = '\0';
        for (i = 0; i < p.n; i++) if (strcasecmp(p.name[i], n) == 0) { hit = i; nfound++; }
        if (nfound > 1) {
            snprintf(m, sizeof m, "WEB READ %s two pairs of the name", web_kinds[kind]);
            refuse(m);
        }
        if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    }
    if (nl <= 0 || vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB READ %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) return 0;
    {
        int n2 = (int)strlen(p.value[hit]), k = n2 > vl ? vl : n2;
        memcpy(value, p.value[hit], (size_t)k);
        if (n2 > vl) { c->resp = LENGERR; c->resp2 = 5; }
        c->num = n2;
    }
    return 0;
}

/* GG-ITEM kind; GG-FLAGS names NAME given; GG-LEN NAMELENGTH. */
int GGCWSBR(gg_cics *c, char *name, int namecap) {
    int kind = c->item, nl = c->len, conds = 0, i, start = 0, nfound = 0, named, at = -1;
    web_pairs p;
    char flags[41], n[257], m[96];
    webreq_load();
    trim(c->flags, 40, flags);
    named = strstr(flags, "NAME") != NULL;
    if (named && (nl > namecap || nl > 256)) {
        snprintf(m, sizeof m, "WEB STARTBROWSE %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (web_browse_on[kind]) { c->resp = ILLOGIC; c->resp2 = kind == 0 ? 10 : 5; conds++; }
    if (named && nl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (!web_getpairs(kind, &p)) { c->resp = INVREQ; c->resp2 = kind == 0 ? 43 : 13; conds++; }
    else if (named && nl > 0) {
        memcpy(n, name, (size_t)nl);
        n[nl] = '\0';
        for (i = 0; i < p.n; i++) if (strcasecmp(p.name[i], n) == 0) { at = i; nfound++; }
        if (nfound > 1) {
            snprintf(m, sizeof m, "WEB STARTBROWSE %s two pairs of the name", web_kinds[kind]);
            refuse(m);
        }
        if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
        else if (strcmp(p.name[at], n) != 0) {
            snprintf(m, sizeof m, "WEB STARTBROWSE %s name found only without case", web_kinds[kind]);
            refuse(m);
        } else start = at;
    }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB STARTBROWSE %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) return 0;
    web_browse_on[kind] = 1;
    web_browse_at[kind] = start;
    web_browse_end[kind] = 0;
    return 0;
}

/* GG-ITEM kind, GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in: the areas' sizes as the program gives them; out: the pair's whole lengths). */
int GGCWRNX(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int kind = c->item, nl = c->len, vl = c->num, conds = 0, end, cutn, cutv, k;
    web_pairs p;
    char m[96];
    webreq_load();
    if (nl > namecap || vl > valuecap) {
        snprintf(m, sizeof m, "WEB READNEXT %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_browse_on[kind]) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    web_getpairs(kind, &p);
    end = web_browse_at[kind] >= p.n;
    if (end && web_browse_end[kind]) {
        snprintf(m, sizeof m, "WEB READNEXT %s after ENDFILE", web_kinds[kind]);
        refuse(m);
    }
    if (nl <= 0 || vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (end) { c->resp = ENDFILE; c->resp2 = 0; conds++; }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB READNEXT %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) {
        if (end) web_browse_end[kind] = 1;
        return 0;
    }
    k = web_browse_at[kind];
    cutn = (int)strlen(p.name[k]) > nl;
    cutv = (int)strlen(p.value[k]) > vl;
    if (cutn && cutv) {
        snprintf(m, sizeof m, "WEB READNEXT %s name and value both truncated", web_kinds[kind]);
        refuse(m);
    }
    if ((cutn || cutv) && kind == 0) refuse("WEB READNEXT HTTPHEADER truncated");
    memcpy(name, p.name[k], cutn ? (size_t)nl : strlen(p.name[k]));
    memcpy(value, p.value[k], cutv ? (size_t)vl : strlen(p.value[k]));
    c->len = (int)strlen(p.name[k]);
    c->num = (int)strlen(p.value[k]);
    if (cutn || cutv) { c->resp = LENGERR; c->resp2 = cutn ? 4 : 5; }
    else web_browse_at[kind]++;
    return 0;
}

/* GG-ITEM kind. */
int GGCWEBR(gg_cics *c) {
    int kind = c->item;
    webreq_load();
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_browse_on[kind]) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    web_browse_on[kind] = 0;
    return 0;
}
