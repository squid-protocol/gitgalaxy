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
       SUPPRESSED = DFHRESP_SUPPRESSED, CCSIDERR = DFHRESP_CCSIDERR };

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
 * task and the programs it runs -- and (#5089) its own RUN / FETCH / FREE CHILD and the CHILD of its own children,
 * which concern only the tasks it started; any other event is a region resource's or a terminal's, whose order against its
 * parent's and its siblings' commands is not modelled. */
static void child_may(const char *line, int verb) {
    static const char *const ok[] = {"RETURN", "ABEND", "LINK", "XCTL", "RUN", "FETCH", "FREE-CHILD", "CHILD"};
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

/* #4892: an event of a model linked beside the stub (ggmq.c's MQI calls), in the task's own stream. */
void ggcics_event(const char *line, const char *data, int len) { event(line, data, len); }

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
static int uctranst_cvda = -1; /* the task's terminal's UCTRANST CVDA (450, 451, 452): stated by the run, or SET */
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
    if (len < 0 || stat(path, &st) != 0) return 0;
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

#include "ggcics_faults.c"  /* #5274: the faults family (faults.cfg planned conditions and ABENDs, DUPKEY, ABM0 map check, GGCSQLAB) */

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

/* #5042 (register X58): the SET(ptr) blocks (defined with the pointer lane, below) that a command ends or must not change */
static void blk_invalidate(const char *key);
static void file_set_end(const char *kind, const char *file); /* ends the SET(ptr) blocks of "READ file" / "BROWSE file" */
static void blk_invalidate_prefix(const char *prefix);
static int blk_held(const char *key);
static void *blk_set_new(const char *key, const void *data, size_t n, int sync);
static void blk_invalidate_sync(void);
static size_t blk_room(const void *p); /* #6839: bytes from p to the end of the live task-storage block holding it, else 0 */
static void file_set_end(const char *kind, const char *file) {
    char key[96];
    snprintf(key, sizeof key, "%s %s", kind, file);
    blk_invalidate(key);
}
static void container_key(char *out, size_t n, const char *chan, const char *name) {
    snprintf(out, n, "CONTAINER %s %s", chan, name);
}

static int has_hold(const char *file) {  /* #5092: a tokenless READ UPDATE holds a record of the file */
    for (int i = 0; i < MAX_FILES; i++) if (held[i].name[0] && strcmp(held[i].name, file) == 0) return 1;
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

/* #6839 row D: a variable-length file (files.cfg flag VAR: a RECORDFORMAT(V) KSDS the case states "variable"). IBM,
 * EXEC CICS WRITE / REWRITE: LENGTH is "the length of the data area where the record is written from" -- the
 * record's length for a variable-length file; READ INTO returns that length in LENGTH, LENGERR (RESP2 11) when it
 * is longer than LENGTH. The records stay in their reclen slots (padded as before); each one's own length is kept
 * in <path>.len, one "HEXKEY LENGTH" line per record written or seeded with a length of its own (none: reclen). */
static int is_var(const char *want) {
    char line[4096], name[64], p[3000], flags[64];
    int a, b, c, var = 0;
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    while (cfg && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%63s %2999s %d %d %d %63s", name, p, &a, &b, &c, flags) == 6 && strcmp(name, want) == 0) {
            var = flag_in(flags, "VAR");
            break;
        }
    }
    if (cfg) fclose(cfg);
    return var;
}

static void len_hex(const char *key, int klen, char *out) {
    static const char digits[] = "0123456789ABCDEF";
    for (int i = 0; i < klen; i++) {
        out[2 * i] = digits[(unsigned char)key[i] >> 4];
        out[2 * i + 1] = digits[(unsigned char)key[i] & 15];
    }
    out[2 * klen] = '\0';
}

/* The record's own length (its key's line in <path>.len), else `reclen`. */
static int len_get(const char *path, const char *key, int klen, int reclen) {
    char lp[3100], want[520], line[600], hex[520];
    int n, got = reclen;
    snprintf(lp, sizeof lp, "%s.len", path);
    len_hex(key, klen, want);
    FILE *f = fopen(lp, "r");
    while (f && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%519s %d", hex, &n) == 2 && strcmp(hex, want) == 0) got = n;
    }
    if (f) fclose(f);
    return got;
}

static void uow_save(const char *path);
static int non_recoverable(const char *path);

/* Record `len` as the record's own length (a WRITE / REWRITE). The .len file is backed out with its data file. */
static void len_set(const char *path, const char *key, int klen, int len) {
    char lp[3100], tmp[3200], want[520], line[600], hex[520];
    int n;
    snprintf(lp, sizeof lp, "%s.len", path);
    snprintf(tmp, sizeof tmp, "%s.len.new", path);
    FILE *touch = fopen(lp, "a");  /* exists before the unit of work saves it, so a backout empties what it adds */
    if (touch) fclose(touch);
    if (!non_recoverable(path)) uow_save(lp);
    len_hex(key, klen, want);
    FILE *in = fopen(lp, "r"), *out = fopen(tmp, "w");
    while (in && out && fgets(line, sizeof line, in)) {
        if (sscanf(line, "%519s %d", hex, &n) == 2 && strcmp(hex, want) != 0) fprintf(out, "%s %d\n", hex, n);
    }
    if (out) fprintf(out, "%s %d\n", want, len);
    if (in) fclose(in);
    if (out) fclose(out);
    rename(tmp, lp);
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

/* #6262, SPEC 6.2 WRITE / DELETE event: `rid=` the RIDFLD on entry as hex (left out: a DELETE of the held or the token's
 * record has none; `rlen` < 0), `generic=1` for DELETE GENERIC, `resp2=` where the command is not NORMAL, and for WRITE the
 * FROM bytes as issued. */
static void file_event(const char *verb, const char *file, const char *rid, int rlen, const gg_cics *c, const char *from,
                       int fromlen) {
    char ev[600], hex[2 * 100 + 1];
    int shown = rlen < 0 ? 0 : rlen < 100 ? rlen : 100;
    for (int i = 0; i < shown; i++) snprintf(hex + 2 * i, 3, "%02X", (unsigned char)rid[i]);
    hex[2 * shown] = '\0';
    int n = snprintf(ev, sizeof ev, "%s file=%s", verb, file);
    if (rlen >= 0) n += snprintf(ev + n, sizeof ev - (size_t)n, " rid=%s", hex);
    if (strcmp(verb, "DELETE") == 0 && strstr(c->flags, "GENERIC")) n += snprintf(ev + n, sizeof ev - (size_t)n, " generic=1");
    n += snprintf(ev + n, sizeof ev - (size_t)n, " resp=%d", c->resp);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
#ifndef _WIN32
    /* X23: recording the event is not a program reference. A WRITE that failed before reading FROM (DUPREC, FILENOTFOUND)
     * must not fault on a FROM that runs past EIBCALEN, so only the bytes before the guard page are recorded. */
    if (from && guard_size && from < guard_page && from + fromlen > guard_page) fromlen = (int)(guard_page - from);
#endif
    event(ev, from, from ? fromlen : 0);
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
        file_event("WRITE", want, ridfld, keylen, c, from, fromlen);
        return 0;
    }
    keyed_on_esds("WRITE", want);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
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
        if (rec && is_var(want)) len_set(path, rec + keyoff, klen, fromlen < reclen ? fromlen : reclen);  /* #6839 */
        free(rec);
        c->resp = NORMAL;
    }
    file_event("WRITE", want, ridfld, keylen, c, from, fromlen);
    return 0;
}

/* SPEC 6.2 REWRITE event: the file, RESP, RESP2 where the command is not NORMAL, and the FROM bytes as issued. */
static void rewrite_event(const gg_cics *c, const char *want, const char *from, int fromlen) {
    char ev[200];
    int n = snprintf(ev, sizeof ev, "REWRITE file=%s resp=%d", want, c->resp);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    event(ev, from, fromlen);
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
        rewrite_event(c, want, from, fromlen);
        return 0;
    }
    if (!have) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
    } else if (strstr(c->flags, "TOKEN") ? token_find(c->num, want) < 0 : !held_key(want, key, klen)) {
        c->resp = INVREQ;
        if (strstr(c->flags, "TOKEN")) c->resp2 = 47;
        else if (!has_hold(want)) c->resp2 = 30;  /* #5092: no READ UPDATE without a token before it (a held record of another key: unsaid, 0) */
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
            if (is_var(want)) len_set(path, key, klen, fromlen < reclen ? fromlen : reclen);  /* #6839 */
            free(rec);
            if (strstr(c->flags, "TOKEN")) tokens[token_find(c->num, want)].id = 0;
            else release(want);
            c->resp = NORMAL;
        }
    }
    if (c->resp == NORMAL) file_set_end("READ", want);  /* IBM: a READ SET pointer is valid until a corresponding REWRITE completes */
    rewrite_event(c, want, from, fromlen);
    return 0;
}

/* A Db2 case's SQL stub (tests/equivalence/db2/ggsql.c), when linked: its Db2 work belongs to the same unit of work.
 * A weak no-op DEFINITION, which ggsql.c's strong one overrides at link time. (A weak undefined REFERENCE checked
 * against NULL links on ELF but not on macOS, whose linker still requires it to resolve.) */
__attribute__((weak)) void ggsql_uow_end(int rollback) { (void)rollback; }
/* #4892 (W5): and the MQ model's (tests/equivalence/mq/ggmq.c), when a program CALLs MQI: the same weak default. */
__attribute__((weak)) void ggmq_uow_end(int rollback) { (void)rollback; }

static void td_uow_end(int rollback); /* #5168 */

/* The unit of work ends: committed (the saved copies dropped) or backed out (put back). */
static void uow_end(int rollback) {
    ggsql_uow_end(rollback);
    ggmq_uow_end(rollback);
    td_uow_end(rollback);
    char aside[3100];
    for (int i = 0; i < MAX_FILES; i++) {
        if (!uow_saved[i][0]) continue;
        snprintf(aside, sizeof aside, "%s.uow", uow_saved[i]);
        if (rollback) copy_file(aside, uow_saved[i]);
        remove(aside);
        uow_saved[i][0] = 0;
    }
    release(NULL);
    blk_invalidate_sync();  /* #5042: a READ UPDATE SET's, a browse SET's pointer */
}

static void browses_end(void); /* #4951 */

/* SYNCPOINT (flags empty: commit) / SYNCPOINT ROLLBACK (flags ROLLBACK: undo since the last SYNCPOINT). */
int GGCSYNC(gg_cics *c) {
    int rollback = strstr(c->flags, "ROLLBACK") != NULL, fresp, fresp2;
    /* #6271 (X71): a planned INVREQ (RESP2 200): the command is refused, no unit of work ends and nothing is recorded */
    if (injected(rollback ? "ROLLBACK" : "SYNCPOINT", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
    uow_end(rollback);
    browses_end(); /* #4951: a container browse token does not survive a sync point */
    c->resp = NORMAL;
    c->resp2 = 0;
    event(rollback ? "SYNCPOINT-ROLLBACK" : "SYNCPOINT", NULL, 0);
    return 0;
}

#include "ggcics_filecontrol.c"  /* #5274: the file-control family (READ, browse, DELETE, UNLOCK) */

/* RECEIVE MAP(name1) MAPSET(name2) INTO: the scenario's recorded map input. */
int GGCRECV(gg_cics *c, char *into, int intolen) {
    char map[9], mapset[9], path[4096], ev[128];
    /* #6271 (X26): after a SET the input arrives under the terminal's new UCTRANST. NOUCTRAN and TRANIDONLY (only the
     * transaction id is translated) leave the typed data as recorded; UCTRAN would upper-case it, which is not modelled. */
    if (uctranst_set && uctranst_cvda == 450)
        refuse("RECEIVE MAP after SET TERMINAL UCTRANST(UCTRAN): the upper-case translation of typed input is not modelled");
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    if (map_not_found(c, map, mapset)) return 0;
    int fresp, fresp2; /* #6271 (X71): a planned INVMPSZ / INVREQ: nothing is received, INTO is untouched */
    if (injected("RECEIVE-MAP", map, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
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

#include "ggcics_tempstorage.c"  /* #5274: the temporary storage family (READQ TS, WRITEQ TS) */

/* ---- the task's outputs ----------------------------------------------------------- */
/* SEND MAP: the symbolic map's bytes as the program left them (#4001: the harness resolves what
 * BMS sends from them and the BMS source); c->len is CURSOR's value, -1 when none was given. */
int GGCSMAP(gg_cics *c, char *from, int len) {
    char map[9], mapset[9], flags[41], ev[192];
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    trim(c->flags, 40, flags);
    if (map_not_found(c, map, mapset)) return 0;
    int fresp, fresp2; /* #6271 (X71): a planned INVMPSZ / TSIOERR / INVREQ: nothing is sent, the screen stays as it was */
    if (injected("SEND-MAP", map, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
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

/* the text itself: SEND TEXT's event, and CONVERSE's write (which plans no SEND TEXT fault: IBM's CONVERSE has its own conditions) */
static void send_text_event(gg_cics *c, char *from, int len) {
    char flags[41], ev[128];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-TEXT len=%d opts=%s", len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
    c->resp2 = 0;
}

int GGCSTXT(gg_cics *c, char *from, int len) {
    int fresp, fresp2; /* #6271 (X71): a planned TSIOERR / INVREQ / LENGERR: nothing is sent */
    if (injected("SEND-TEXT", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
    send_text_event(c, from, len);
    return 0;
}

/* CONVERSE FROM FROMLENGTH INTO ... (#5079, X63; IBM, EXEC CICS CONVERSE (default)), as CicsTask.converse: the data written to the
 * terminal (`from`, `fromlen` bytes), recorded as a plain SEND records it, then the terminal RECEIVE of the reply INTO `into` (GG-LEN the
 * most taken, GG-FLAGS NOTRUNCATE; on return GG-LEN the reply's length). A negative `fromlen` is LENGERR with nothing sent and nothing
 * read (GG-LEN -1: ASSUMED). Refused on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE). */
int GGCCONV(gg_cics *c, char *from, int fromlen, char *into) {
    char saved[40];
    int most = c->len;
    if (getenv("GGCICS_LU2") != NULL) refuse("CONVERSE on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE)");
    if (fromlen < 0) {
        c->resp = LENGERR;
        c->resp2 = 0;
        c->len = -1;
        return 0;
    }
    memcpy(saved, c->flags, sizeof saved);
    memset(c->flags, ' ', sizeof saved);
    memcpy(c->flags, "DATA", 4);
    send_text_event(c, from, fromlen);
    memcpy(c->flags, saved, sizeof saved);
    c->len = most;
    terminal_receive(c, into);
    return 0;
}

/* RETURN: at level 1 it ends the task, with TRANSID / COMMAREA for the next one; at a lower
 * level (#4004) it returns to the linking program, and the event shows the LINK COMMAREA as
 * that program now sees it (`len` -1: the LINK had none). */
static void return_event(const char *transid, char *commarea, int len);

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

#include "ggcics_conditions.c"  /* #5274: the conditions and abends family (the per-level handler state, GGCPENT, HANDLE CONDITION and ABEND, PUSH/POP HANDLE) */

#include "ggcics_transientdata.c"  /* #5274: the transient data family (READQ/WRITEQ/DELETEQ TD, SET/INQUIRE TDQUEUE) */

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

/* #6271 (X71): a plain RETURN TRANSID the program tests (GG-ITEM 2: it codes RESP) can fail on a planned INVREQ (1, 2, 4,
 * 200) / LENGERR (11, 26, 27) at the highest level; the task goes on and nothing is passed to the next one. A plain RETURN
 * that codes no RESP never consults the plan (its failure would be an abend IBM does not describe: not planned). */
int GGCRETN(gg_cics *c, char *commarea, int len) {
    char transid[9], ev[128];
    int fresp, fresp2;
    trim(c->name1, 8, transid);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (c->item == 2 && lvl == 0 && injected("RETURN", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        snprintf(ev, sizeof ev, "RETURN level=1 transid=%s resp=%d resp2=%d", transid, c->resp, c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    return_event(transid, commarea, len);
    return 0;
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
    int fresp, fresp2; /* #6271 (X71): a planned INVREQ (1, 2, 4, 200) / LENGERR (11, 26, 27): the program goes on */
    if (c->resp == NORMAL && injected("RETURN", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    }
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
    c->go_to = 0;
    if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    else if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; }
    else if (lvl + 1 >= MAX_LEVELS) { c->resp = INVREQ; }
    else if (injected("LINK", program, &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; }  /* #4648: as XCTL's */
    snprintf(ev, sizeof ev, "LINK target=%s len=%d area=%d resp=%d resp2=%d", program, len, has, c->resp, c->resp2);
    event(ev, has ? area : NULL, has && len > 0 && len <= 32763 ? len : 0);
    /* #6271 (X70): a planned abend (`LINK PROGRAM 1 -1 0 ABCODE`) went to the exit or ended the task: the callee never runs */
    if (c->resp != NORMAL || c->go_to != 0 || terminated) return 0;
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

#include "ggcics_containers.c"  /* #5274: the channels / containers family */

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
 * 1 (IBM lists no RESP2). Refused by name: a byte beyond 7-bit ASCII, a LENGTH past the field (flen). A field with
 * no digit left becomes all zeros (ASSUMED: IBM does not say). c->num is LENGTH. */
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
    /* no digit left: all zeros (IBM's rule read literally; ASSUMED, register X26) */
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
 * RESP2 23); an invalid CVDA is INVREQ RESP2 43. A SET is the task's view of its terminal from then on: a RECEIVE MAP after it reads the input under the new
 * value (#6271), an unformatted terminal RECEIVE after it is refused (IBM does not say when the change takes effect). c->num is the CVDA. */
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
    int fresp, fresp2; /* #6882 (X26): a planned TERMIDERR: the INQUIRE is not performed */
    if (injected("INQ-TERMINAL", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
    if (uctranst_terminal(c, 1)) {
        uctranst_init();
        c->num = uctranst_cvda;
    }
    return 0;
}

int GGCSETT(gg_cics *c) {
    int cvda = c->num;
    int fresp, fresp2; /* #6882 (X26): a planned TERMIDERR / INVREQ: the SET is not performed (uctranst_cvda and _set stay) */
    if (injected("SET-TERMINAL", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
    if (uctranst_terminal(c, 23)) {
        if (cvda != 450 && cvda != 451 && cvda != 452) { c->resp = INVREQ; c->resp2 = 43; return 0; }
        uctranst_cvda = cvda;
        uctranst_set = 1;
    }
    return 0;
}

/* ---- #4415 slice 2: INQUIRE ASSOCIATION (IBM CICS TS, INQUIRE ASSOCIATION; register X29) ----
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

#define GGCICS_TS_DELETEQ  /* the second part of the temporary storage family: DELETEQ TS */
#include "ggcics_tempstorage.c"
#undef GGCICS_TS_DELETEQ

#include "ggcics_taskcontrol.c"  /* #5274: the task / interval control family (START, RETRIEVE, RUN, DELAY, POST, CANCEL ...) */

#include "ggcics_enq.c"  /* #5274: the ENQ stub (GGCENQ) */

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

/* #5039 (X53): the value a GET hands out meets COMPAREMIN / COMPAREMAX (`has_*`: given): at or above the one, at or below the
 * other, either when COMPAREMAX is below COMPAREMIN. As CicsTask.counterInRange. */
static int counter_in_range(unsigned long long v, int has_min, unsigned long long cmin, int has_max, unsigned long long cmax) {
    int ge = !has_min || v >= cmin, le = !has_max || v <= cmax;
    return has_min && has_max && cmax < cmin ? (ge || le) : (ge && le);
}

/* GET with #5039 (X53)'s REDUCE ("the request succeeds with the current value set to the maximum plus 1": an INCREMENT that would
 * carry the counter past MAXIMUM + 1 leaves it there) and COMPAREMIN / COMPAREMAX (2: SUPPRESSED RESP2 103, the counter unchanged).
 * Refused, as CicsTask.getCounter: REDUCE with WRAP, REDUCE or a compare at a counter already at its limit, a negative compare
 * value of a fullword counter (`full`). */
static int counter_step_x(counter_row *r, unsigned long long incr, int wrap, int reduce, int has_min, unsigned long long cmin,
                          int has_max, unsigned long long cmax, int full, unsigned long long *out) {
    unsigned long long v = r->value, next;
    if (reduce && wrap) refuse("GET COUNTER with both REDUCE and WRAP");
    if (full && ((has_min && ((cmin >> 31) & 1)) || (has_max && ((cmax >> 31) & 1)))) refuse("GET COUNTER COMPAREMIN / COMPAREMAX below zero");
    if (!r->limited) {
        if (!counter_in_range(v, has_min, cmin, has_max, cmax)) return 2;
        if (incr > 4294967295ULL || v + incr > 4294967295ULL) refuse("GET COUNTER past 4294967295: the counter's maximum is not stated");
        *out = v;
        r->value = v + incr;
        return 0;
    }
    if (incr > r->max - r->min) refuse("GET COUNTER with an INCREMENT beyond the counter's range");
    if (r->max != ~0ULL && v > r->max) { /* at its limit: the counter is MAXIMUM + 1 */
        if (reduce) refuse("GET COUNTER REDUCE at a counter already at its limit");
        if (has_min || has_max) refuse("GET COUNTER COMPAREMIN / COMPAREMAX at a counter already at its limit");
        if (!wrap) return 1;
        *out = r->min;
        r->value = r->min + incr;
        return 0;
    }
    if (!counter_in_range(v, has_min, cmin, has_max, cmax)) return 2;
    next = v + incr;
    if (next < v) refuse("GET COUNTER past a doubleword");
    if (next > r->max && next - r->max > 1) {
        if (!reduce) refuse("GET COUNTER with an INCREMENT past MAXIMUM + 1");
        next = r->max + 1;
    }
    *out = v;
    r->value = next;
    return 0;
}

/* One GET of the counter at rows[at] (as CicsTask.getCounter(pool, name, increment, wrap)): the value it hands back in *out and
 * the counter `incr` more; 1 (SUPPRESSED RESP2 101, the counter unchanged) for a DEFINE DCOUNTER counter at its limit without
 * WRAP. #4770 (X45): such a counter has the limits it was given (unsigned doublewords): at its limit (MAXIMUM + 1) WRAP
 * "resets the current value ... equal to the minimum value" and the GET returns that; an INCREMENT beyond MAXIMUM - MINIMUM, or
 * past MAXIMUM + 1 (IBM's 406 / REDUCE boundaries are not stated), and a counter past a doubleword are refused. A counter with
 * no limits has none the run states: WRAP changes nothing and one past 4294967295 is refused, as before. */
static int counter_step(counter_row *r, unsigned long long incr, int wrap, unsigned long long *out) {
    return counter_step_x(r, incr, wrap, 0, 0, 0, 0, 0, 0, out);
}

static void put32(unsigned char *p, unsigned long long v) {
    for (int i = 3; i >= 0; i--) { p[i] = (unsigned char)(v & 255); v >>= 8; }
}

/* LENGERR RESP2 of a fullword (COUNTER) command whose counter holds v (#4770, X30; IBM, GET COUNTER and QUERY COUNTER): 0 when v fits
 * a signed fullword or the counter is at its limit (v past MAXIMUM: "LENGERR can't occur at counter-at-limit"); else 1 (no bit above
 * the low word: the sign bit), 2 (the high word is 1), 3 (above 1). The operation completes: VALUE is the low 32 bits. As
 * CicsTask.fullwordLengerr. */
static int counter_lengerr(const counter_row *r, unsigned long long v) {
    if (v <= 2147483647ULL) return 0;
    if (r->limited && r->max != ~0ULL && v > r->max) return 0;
    return (v >> 32) == 0 ? 1 : (v >> 32) == 1 ? 2 : 3;
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
        if ((c->resp2 = counter_lengerr(&rows[at], v))) c->resp = LENGERR;
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

/* GET COUNTER / DCOUNTER with REDUCE, COMPAREMIN, COMPAREMAX (#5039, register X53; IBM, EXEC CICS GET COUNTER and GET DCOUNTER):
 * as GGCGCNT / GGCGDCN with `reduce` and the bounds, each an area of the counter's width (length 0: not given). SUPPRESSED RESP2 103
 * when the value handed out is out of range. As CicsTask.getCounter(pool, name, increment, wrap, reduce, cmpMin, cmpMax, fullword). */
static int get_counter_x(gg_cics *c, int width, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
                         unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (width == 4 && inclen == 8 && be64(inc, 8) <= 4294967295ULL) {
        inc += 4;
        inclen = 4;
    }
    if (inclen > width || valuelen != width || cminlen > width || cmaxlen > width) refuse("GET COUNTER with a VALUE, INCREMENT or compare value that is not the counter's width");
    unsigned long long incr = be64(inc, inclen);
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
        int st = counter_step_x(&rows[at], incr, wrap, reduce, cminlen > 0, be64(cmin, cminlen), cmaxlen > 0, be64(cmax, cmaxlen), width == 4, &v);
        if (st) {
            c->resp = SUPPRESSED;
            c->resp2 = st == 1 ? 101 : 103;
            return 0;
        }
        unsigned long long got = v;
        for (int i = width - 1; i >= 0; i--) { value[i] = (unsigned char)(v & 255); v >>= 8; }
        counters_write(rows, n);
        if (width == 4 && (c->resp2 = counter_lengerr(&rows[at], got))) c->resp = LENGERR;
    }
    return 0;
}

int GGCGCNX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    return get_counter_x(c, 4, value, valuelen, inc, inclen, wrap, reduce, cmin, cminlen, cmax, cmaxlen);
}

int GGCGDCX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    return get_counter_x(c, 8, value, valuelen, inc, inclen, wrap, reduce, cmin, cminlen, cmax, cmaxlen);
}

/* REWIND COUNTER / DCOUNTER(qname) POOL(name1) INCREMENT(inc) (#5039, X53; IBM, EXEC CICS REWIND COUNTER and REWIND DCOUNTER): a
 * counter that has reached its limit (MAXIMUM + 1, where a GET leaves it) is reset to its minimum; SUPPRESSED RESP2 102 for one
 * that has not; INVREQ 406 for an INCREMENT beyond (maximum - minimum) + 1; 201 / 403 / 404. `inc` length 0: INCREMENT omitted (1).
 * Refused, as CicsTask.rewindCounter: an INCREMENT of zero or above 1 within the range, a counter with no limits. */
static int rewind_counter(gg_cics *c, int width, unsigned char *inc, int inclen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen > width) refuse("REWIND COUNTER with an INCREMENT that is not the counter's width");
    unsigned long long incr = inclen ? be64(inc, inclen) : 1;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (incr == 0) refuse("REWIND COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = counter_find(rows, n, pool, want);
    if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
        return 0;
    }
    counter_row *r = &rows[at];
    if (!r->limited) refuse("REWIND COUNTER of a counter whose limits the run does not state");
    unsigned long long range = r->max - r->min + 1; /* 0: a full doubleword, which no INCREMENT exceeds */
    if (range != 0 && incr > range) {
        c->resp = INVREQ;
        c->resp2 = 406;
        return 0;
    }
    if (incr != 1) refuse("REWIND COUNTER with an INCREMENT above 1");
    if (r->max == ~0ULL || r->value <= r->max) {
        c->resp = SUPPRESSED;
        c->resp2 = 102;
        return 0;
    }
    r->value = r->min;
    counters_write(rows, n);
    return 0;
}

int GGCRCNT(gg_cics *c, unsigned char *inc, int inclen) { return rewind_counter(c, 4, inc, inclen); }
int GGCRDCN(gg_cics *c, unsigned char *inc, int inclen) { return rewind_counter(c, 8, inc, inclen); }

/* UPDATE COUNTER / DCOUNTER(qname) POOL(name1) VALUE(val) (#5039, X53; IBM, EXEC CICS UPDATE COUNTER and UPDATE DCOUNTER): the new
 * current value; INVREQ 406 for a VALUE below MINIMUM or above MAXIMUM + 1; 201 / 403 / 404. Refused, as CicsTask.updateCounter: a
 * negative fullword VALUE, a counter with no limits. */
static int update_counter(gg_cics *c, int width, unsigned char *val, int vallen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (vallen != width) refuse("UPDATE COUNTER with a VALUE that is not the counter's width");
    unsigned long long value = be64(val, vallen);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (width == 4 && ((value >> 31) & 1)) refuse("UPDATE COUNTER with a VALUE below zero");
    int n = counters_read(rows), at = counter_find(rows, n, pool, want);
    if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
        return 0;
    }
    counter_row *r = &rows[at];
    if (!r->limited) refuse("UPDATE COUNTER of a counter whose limits the run does not state");
    if (value < r->min || (r->max != ~0ULL && value > r->max + 1)) {
        c->resp = INVREQ;
        c->resp2 = 406;
        return 0;
    }
    r->value = value;
    counters_write(rows, n);
    return 0;
}

int GGCUCNT(gg_cics *c, unsigned char *val, int vallen) { return update_counter(c, 4, val, vallen); }
int GGCUDCN(gg_cics *c, unsigned char *val, int vallen) { return update_counter(c, 8, val, vallen); }

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
 * no limits, and limits beyond a fullword, are refused; a value beyond a fullword is IBM's LENGERR (#4770, X30): RESP2 1 / 2 / 3, the
 * low 32 bits written. As CicsTask.queryCounter. */
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
        if ((lolen && rows[at].min > 2147483647ULL) || (hilen && rows[at].max > 2147483647ULL))
            refuse("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits are beyond a fullword");
        if ((c->resp2 = counter_lengerr(&rows[at], rows[at].value))) c->resp = LENGERR;
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

/* #5859 (X32): EXEC CICS VERIFY PASSWORD USERID(userid) PASSWORD(password). The region has no security manager, so the verdict
 * is the planned `VERIFY USERID NTH RESP 0` line a scenario states for the USERID (trailing blanks dropped), the way
 * CicsTask.verifyPassword reads it; none stated is refused by name. The password is not compared. Event, as the task logs it. */
int GGCVER(gg_cics *c, char *userid, int ulen) {
    char id[33], ev[96];
    int fresp, fresp2, n = ulen < 32 ? ulen : 32;
    c->resp = NORMAL;
    c->resp2 = 0;
    while (n > 0 && userid[n - 1] == ' ') n--;
    memcpy(id, userid, (size_t)n);
    id[n] = '\0';
    if (!injected("VERIFY", id, &fresp, &fresp2)) {
        snprintf(ev, sizeof ev, "VERIFY PASSWORD with no stated verdict for USERID '%s'", id);
        refuse(ev);
    }
    c->resp = fresp;
    c->resp2 = fresp2;
    snprintf(ev, sizeof ev, "VERIFY-PASSWORD userid=%s resp=%d", id, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* WRITE OPERATOR TEXT(from) of GG-LEN bytes: a message to the console, recorded with its text. A text IBM reformats
 * (DFHnnnn / DFHaannnn) or splits (over 113 characters) is refused. #5859 (X32), as CicsTask.writeOperator: GG-FLAGS
 * TEXTLENGTH says GG-LEN is the TEXTLENGTH value (IBM: 0-690, else INVREQ RESP2 1; the text is the first GG-LEN bytes of the
 * area, and one past the area is refused); GG-FLAGS ROUTES says `routes` holds GG-NUM route codes (each 1-28, else INVREQ
 * RESP2 3; GG-NUM below 1 or past the area is a case IBM leaves open, refused). The routes are no observable (the
 * console is not modelled) and EVENTUAL changes only when the operator acts. `area` is the text area's size, `routes_len`
 * the routes area's. */
int GGCWTO(gg_cics *c, char *from, int area, char *routes, int routes_len) {
    char ev[64];
    int n, k = 0, i;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(c->flags, "TEXTLENGTH")) {
        if (c->len < 0 || c->len > 690) {
            c->resp = INVREQ;
            c->resp2 = 1;
            return 0;
        }
        if (c->len > area) refuse("WRITE OPERATOR TEXTLENGTH past the text area");
    }
    if (strstr(c->flags, "ROUTES")) {
        if (c->num < 1 || c->num > routes_len) refuse("WRITE OPERATOR NUMROUTES IBM leaves open");
        for (i = 0; i < c->num; i++)
            if ((unsigned char)routes[i] < 1 || (unsigned char)routes[i] > 28) {
                c->resp = INVREQ;
                c->resp2 = 3;
                return 0;
            }
    }
    n = c->len;
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
static unsigned char **docs;
static int *doc_len;
static int *doc_dead; /* #4941: deleted by a WEB SEND DOCSTATUS(DOCDELETE) */
static int ndocs = 0, doc_cap = 0;
/* #6072: IBM sets no count of documents a task may create (storage alone limits it), so the tables grow; ZECS000 holds 501. */

static int doc_new(const unsigned char *data, int len, char *tok, int toklen) {
    char t[17];
    int i;
    if (ndocs >= doc_cap) {
        int cap = doc_cap ? doc_cap * 2 : 64;
        unsigned char **nd = realloc(docs, (size_t)cap * sizeof *docs);
        int *nl, *nx;
        if (!nd) refuse("DOCUMENT CREATE: out of storage");
        docs = nd;
        nl = realloc(doc_len, (size_t)cap * sizeof *doc_len);
        if (!nl) refuse("DOCUMENT CREATE: out of storage");
        doc_len = nl;
        nx = realloc(doc_dead, (size_t)cap * sizeof *doc_dead);
        if (!nx) refuse("DOCUMENT CREATE: out of storage");
        doc_dead = nx;
        memset(doc_dead + doc_cap, 0, (size_t)(cap - doc_cap) * sizeof *doc_dead);
        doc_cap = cap;
    }
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

#include "ggcics_web.c"  /* #5274: the web family, part 1 (WEB OPEN .. WRITE HTTPHEADER, EXTRACT TCPIP) */

/* ---- #4771 (register X47): storage CICS acquires for the task, addressed by a pointer. A block is registered when GETMAIN or
 * WEB RECEIVE SET hands it out (the pointer item `slot` then holds its address), so FREEMAIN can tell storage GETMAIN returned
 * from any other address. A freed block is kept (never reused), so a second FREEMAIN of it is recognised and refused. */
enum { BLK_GETMAIN = 0, BLK_RECEIVED = 1, BLK_FREED = 2 };
static struct { void *p; int kind; size_t n; char key[96]; int sync; } blks[8192];
static int nblks = 0;

/* #6839 (X47): a block lies in the low 2 GiB where the platform can place it (Linux MAP_32BIT). A POINTER is 8 bytes here, IBM's 4, and
 * a program that copies one through its 4-byte numeric view (ZECS001: MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X) keeps only the low half; a
 * heap address above 4 GiB then came back as an unmapped one (SIGSEGV at the next WEB CONVERSE FROM). Zero-filled, never unmapped. */
#if defined(_WIN32) && !defined(GGCICS_NO_LOW_BLOCKS)
/* windows.h is not included (its macros collide with this file's names): the one call declared as MinGW does. */
__declspec(dllimport) void *__stdcall VirtualAlloc(void *at, size_t n, unsigned long type, unsigned long prot);
#endif

/* Where the platform cannot place a block low (macOS arm64 reserves the low 4 GiB; its mmap with MAP_32BIT fails) the block comes
 * from calloc: GETMAIN still answers, only a 4-byte copy of the address is then not the address. GGCICS_NO_LOW_BLOCKS forces that. */
static void *blk_alloc(size_t n) {
#if defined(GGCICS_NO_LOW_BLOCKS)
    return calloc(n, 1);
#elif defined(_WIN32)
    static size_t cursor = 0x10000000U; /* zero-filled; the 64 KiB allocation granularity is the step */
    size_t step = 0x10000U, size = (n + step - 1) / step * step, at;
    void *p;
    if (size < 0x60000000U) {
        for (at = cursor; at + size < 0x7ff00000U; at += step) {
            p = VirtualAlloc((void *)at, n, 0x3000UL /* MEM_COMMIT | MEM_RESERVE */, 0x04UL /* PAGE_READWRITE */);
            if (p) { cursor = at + size; return p; }
        }
    }
    return calloc(n, 1);
#elif defined(MAP_32BIT)
    void *p = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
    return p == MAP_FAILED ? calloc(n, 1) : p;
#else
    return calloc(n, 1);
#endif
}

static void *blk_new(size_t n, int kind) {
    void *p;
    if (nblks >= 8192) refuse("more than 8192 blocks of task storage");
    p = blk_alloc(n ? n : 1);
    if (!p) refuse("GETMAIN length beyond the limit");
    blks[nblks].p = p;
    blks[nblks].kind = kind;
    blks[nblks].n = n;
    blks[nblks].key[0] = '\0';
    nblks++;
    return p;
}

/* #6839: the bytes from `p` to the end of the live GETMAIN / received block that holds it (0: no block does). A WEB command reads
 * its FROM / PATH / QUERY from the address, so a record SET onto a larger block may carry a length past its declared area (IBM). */
static size_t blk_room(const void *p) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind != BLK_FREED && (const char *)p >= (const char *)blks[i].p
            && (const char *)p < (const char *)blks[i].p + blks[i].n)
            return (size_t)((const char *)blks[i].p + blks[i].n - (const char *)p);
    }
    return 0;
}

/* #5042 (register X58): ends the validity of the SET(ptr) blocks of `key`. IBM says only that the pointer is then "no longer
 * valid"; the storage reads as zeros through any record already addressing it (ASSUMED), as CicsTask.invalidateSet. */
static void blk_invalidate(const char *key) {
    for (int i = 0; key && i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && strcmp(blks[i].key, key) == 0) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

/* A SYNCPOINT ends the blocks IBM says it does (READ UPDATE SET, READNEXT / READPREV SET); as CicsTask.invalidateSyncSet. */
static void blk_invalidate_sync(void) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && blks[i].sync) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

static void blk_invalidate_prefix(const char *prefix) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && strncmp(blks[i].key, prefix, strlen(prefix)) == 0) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

static int blk_held(const char *key) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && strcmp(blks[i].key, key) == 0) return 1;
    }
    return 0;
}

/* A SET(ptr) block of RECEIVE, RETRIEVE, READQ TS, GET CONTAINER or a file read, holding the n bytes of `data`: the earlier one
 * of the same `key` ends first (a NULL key: valid to the task's end). As CicsTask.acquireSet. */
static void *blk_set_new(const char *key, const void *data, size_t n, int sync) {
    void *p;
    if (n > 268435456U) refuse("SET(ptr) data beyond the limit");
    blk_invalidate(key);
    p = blk_new(n, BLK_RECEIVED);
    memcpy(p, data, n);
    if (key) snprintf(blks[nblks - 1].key, sizeof blks[0].key, "%s", key);
    blks[nblks - 1].sync = sync;
    return p;
}

/* GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(byte) (IBM CICS TS, EXEC CICS GETMAIN): GG-NUM the length, GG-FLAGS "SHORT" for the
 * LENGTH form; LENGERR RESP2 1 for FLENGTH below 1 / LENGTH zero (ptr set to zero). Refused: a length above the limit, a LENGTH
 * above 65520, an INITIMG that is not one byte. No INITIMG (#6876, imglen 0; IBM: "There is no default initialization", the contents
 * are undefined): LENGERR as above, any valid length refused by name, as CicsTask.getmain. */
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen) {
    char flags[41];
    long long n = c->num;
    trim(c->flags, 40, flags);
    if (imglen > 1) refuse("GETMAIN INITIMG is not one byte");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n < 1) { c->resp = LENGERR; c->resp2 = 1; *slot = NULL; return 0; }
    if (imglen == 0) refuse("GETMAIN without INITIMG acquired storage");
    if (n > 268435456LL || (strcmp(flags, "SHORT") == 0 && n > 65520)) refuse("GETMAIN length beyond the limit");
    *slot = blk_new((size_t)n, BLK_GETMAIN);
    memset(*slot, (unsigned char)img[0], (size_t)n);
    return 0;
}

/* LOAD PROGRAM(name1) [SET(ptr)] [LENGTH(halfword)] (#6876, X65; IBM, EXEC CICS LOAD): PGMIDERR RESP2 1 for a program the CSD does not
 * define (the pointer and LENGTH are not written); else the program is loaded by this task, the pointer takes the address of a
 * non-null image and LENGTH (GG-FLAGS LENGTH: the area is given) the image's length, a halfword written big-endian. IBM states no
 * image bytes or length, so a program that reads them is outside the proof. RELEASE PROGRAM(name1): PGMIDERR RESP2 1 for an undefined
 * program, INVREQ for one this task did not load, else NORMAL (IBM lists no other condition). */
#define LOADED_MAX 32
static char loaded[LOADED_MAX][9];
static char load_image[256];

int GGCLDPG(gg_cics *c, void **slot, unsigned char *len) {
    char program[9], flags[41];
    int i, free_at = -1;
    trim(c->name1, 8, program);
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; return 0; }
    for (i = 0; i < LOADED_MAX; i++) {
        if (strcmp(loaded[i], program) == 0) { free_at = i; break; }
        if (free_at < 0 && loaded[i][0] == 0) free_at = i;
    }
    if (free_at < 0) refuse("LOAD of more than 32 programs at once");
    snprintf(loaded[free_at], sizeof loaded[free_at], "%s", program);
    if (strstr(flags, "SET") != NULL) *slot = load_image;
    if (strstr(flags, "LENGTH") != NULL) { len[0] = (unsigned char)(sizeof load_image >> 8); len[1] = (unsigned char)(sizeof load_image & 255); }
    return 0;
}

int GGCRLPG(gg_cics *c) {
    char program[9];
    int i;
    trim(c->name1, 8, program);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; return 0; }
    for (i = 0; i < LOADED_MAX; i++)
        if (strcmp(loaded[i], program) == 0) { loaded[i][0] = 0; return 0; }
    c->resp = INVREQ;
    return 0;
}

/* The release both FREEMAIN forms share: the block that starts at `addr`, INVREQ RESP2 1 when none does. */
static int free_block_at(gg_cics *c, void *addr) {
    int i;
    c->resp = NORMAL;
    c->resp2 = 0;
    for (i = 0; i < nblks; i++) {
        if (blks[i].p == addr) {
            if (blks[i].kind != BLK_GETMAIN) refuse("FREEMAIN of storage already freed or received");
            blks[i].kind = BLK_FREED;
            return 0;
        }
    }
    c->resp = INVREQ;
    c->resp2 = 1;
    return 0;
}

/* GGCFREM: FREEMAIN DATAPOINTER(ptr): INVREQ RESP2 1 for an address GETMAIN did not return (a null pointer, a record's address). Refused:
 * storage already freed, a WEB RECEIVE SET body (IBM does not say whether FREEMAIN is allowed). */
int GGCFREM(gg_cics *c, void **slot) {
    return free_block_at(c, *slot);
}

/* GGCFRED: FREEMAIN DATA(record) (#6876, X47): `area` is the LINKAGE record, whose address is the storage a SET ADDRESS OF gave it.
 * As GGCFREM for that address; refused besides: a record with no address (IBM: undefined), an address inside a GETMAIN block that is
 * not its start (IBM does not say what releasing the middle of a block does), as CicsTask.freemainData. */
int GGCFRED(gg_cics *c, void *area) {
    int i;
    if (area == NULL) refuse("FREEMAIN DATA of a record no pointer addresses");
    for (i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_GETMAIN && (char *)area > (char *)blks[i].p && (char *)area < (char *)blks[i].p + blks[i].n)
            refuse("FREEMAIN DATA of an address inside a GETMAIN block");
    }
    return free_block_at(c, area);
}

/* ---- #5119 (register X56): an OS/VS COBOL address held in data (a chained storage area's fullword). `MOVE cell TO fullword` is
 * CALL 'GGCBLLP' USING cell fullword, `MOVE fullword TO cell` CALL 'GGCBLLG' USING fullword cell. A real address does not fit a
 * fullword here, so the fullword holds a token (ASSUMED): 0 for NULL, the n-th distinct address moved into data n * 65536 (at most
 * 1525: 8 digits), 4 bytes big-endian, numbered as CicsTask.bllToken. A block is never reused (blk_new), so one address is one block. */
static void *bll_tok[1525];
static int nbll_tok = 0;

int GGCBLLP(void **cell, unsigned char *data) {
    unsigned int v = 0;
    int i;
    if (*cell) {
        for (i = 0; i < nbll_tok && bll_tok[i] != *cell; i++) {
        }
        if (i == nbll_tok) {
            if (nbll_tok >= 1525) refuse("more than 1525 BLL addresses held in data");
            bll_tok[nbll_tok++] = *cell;
        }
        v = (unsigned int)(i + 1) * 65536U;
    }
    for (i = 3; i >= 0; i--) {
        data[i] = (unsigned char)(v & 0xFF);
        v >>= 8;
    }
    return 0;
}

int GGCBLLG(unsigned char *data, void **cell) {
    long long v = (long long)(signed char)data[0];
    int i;
    for (i = 1; i < 4; i++) v = (v << 8) | data[i];
    if (v == 0) {
        *cell = NULL;
        return 0;
    }
    if (v < 0 || v % 65536 != 0 || v / 65536 > nbll_tok) refuse("an address in data that no BLL cell gave");
    *cell = bll_tok[v / 65536 - 1];
    return 0;
}

/* #5079 slice 2b (X59): the TWA (TRANSACTION TWASIZE, $GGCICS_TWASIZE) is the task's: one zeroed block every program it LINKs to
 * addresses; the TCTUA (TYPETERM USERAREALEN, $GGCICS_USERAREALEN) is the terminal's, so its bytes live in the file $GGCICS_TCTUA that
 * each task reads when it first addresses the area and writes back as it ends. An area of size 0 or unstated is IBM's X'FF000000':
 * the pointer's first four bytes (little-endian 0xFF), so a program's PIC X(4) view of it compares equal. IBM does not state the
 * initial content: zeros, as the port. */
static char *twa_area, *tctua_area, *cwa_area;
static long tctua_len, cwa_len;

static long env_size(const char *name) {
    const char *v = getenv(name);
    long n = v ? atol(v) : 0;
    return n > 0 ? n : 0;
}

static void tctua_save(void) {
    const char *path = getenv("GGCICS_TCTUA");
    FILE *f = path && tctua_area ? fopen(path, "wb") : NULL;
    if (f) { fwrite(tctua_area, 1, (size_t)tctua_len, f); fclose(f); }
}

static void cwa_save(void) {
    const char *path = getenv("GGCICS_CWA");
    FILE *f = path && cwa_area ? fopen(path, "wb") : NULL;
    if (f) { fwrite(cwa_area, 1, (size_t)cwa_len, f); fclose(f); }
}

static void *system_area(const char *kind) {
    if (strcmp(kind, "CWA") == 0) {  /* #5079 slice 2b: SIT WRKAREA ($GGCICS_WRKAREA); one area for the region, so its bytes live in $GGCICS_CWA */
        long n = env_size("GGCICS_WRKAREA");
        const char *path = getenv("GGCICS_CWA");
        if (n == 0 || !path) return (void *)(size_t)0xFF;
        if (!cwa_area) {
            FILE *f = fopen(path, "rb");
            cwa_len = n;
            cwa_area = calloc((size_t)n, 1);
            if (f) { size_t got = fread(cwa_area, 1, (size_t)n, f); (void)got; fclose(f); }
            atexit(cwa_save);
        }
        return cwa_area;
    }
    if (strcmp(kind, "TWA") == 0) {
        long n = env_size("GGCICS_TWASIZE");
        if (n == 0) return (void *)(size_t)0xFF;
        if (!twa_area) twa_area = calloc((size_t)n, 1);
        return twa_area;
    }
    long n = env_size("GGCICS_USERAREALEN");
    const char *path = getenv("GGCICS_TCTUA");
    if (n == 0 || !path) return (void *)(size_t)0xFF;
    if (!tctua_area) {
        FILE *f = fopen(path, "rb");
        tctua_len = n;
        tctua_area = calloc((size_t)n, 1);
        if (f) { size_t got = fread(tctua_area, 1, (size_t)n, f); (void)got; fclose(f); }
        atexit(tctua_save);
    }
    return tctua_area;
}

/* GGCADDR: ADDRESS EIB(ptr) | COMMAREA(ptr) | CWA(ptr) | TWA(ptr) | TCTUA(ptr) (X59). `area` is the EIB or the program's DFHCOMMAREA; the pointer
 * takes its address (NORMAL: the command has no condition). GG-FLAGS COMMAREA with GG-NUM (EIBCALEN) 0: refused -- IBM sets X'FF000000',
 * which is no COBOL NULL, and a LINKAGE item the caller did not pass names no storage. GG-FLAGS CWA / TWA / TCTUA: the system area (`area`
 * is unused). */
int GGCADDR(gg_cics *c, void **slot, void *area) {
    char flags[41];
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(flags, "COMMAREA") != NULL && c->num == 0) refuse("ADDRESS COMMAREA with no COMMAREA");
    if (strstr(flags, "CWA") != NULL) { *slot = system_area("CWA"); return 0; }
    if (strstr(flags, "TCTUA") != NULL) { *slot = system_area("TCTUA"); return 0; }
    if (strstr(flags, "TWA") != NULL) { *slot = system_area("TWA"); return 0; }
    *slot = area;
    return 0;
}

#define GGCICS_WEB_PART2
#include "ggcics_web.c"  /* #5274: the web family, part 2 (WEB RECEIVE SET) */
#undef GGCICS_WEB_PART2

/* ---- #5042 (register X58): SET(ptr) on RECEIVE, RETRIEVE, READQ TS, GET CONTAINER and the file reads. Each answers as its INTO form
 * does (the same conditions and events), then, where data was delivered, puts a copy in a new block the pointer addresses
 * (blk_set_new; the key says what ends the pointer, as CicsTask.acquireSet). Where nothing was delivered the pointer is as it was
 * (ASSUMED: IBM does not say). */

/* RECEIVE SET(ptr) MAXLENGTH LENGTH (GG-LEN the most in, the length out): the block holds the bytes delivered; valid until the
 * next RECEIVE ("until the next receive command or the end of task"). */
int GGCRECP(gg_cics *c, void **slot) {
    memset(set_buf, 0, sizeof set_buf);
    int copied = terminal_receive(c, set_buf);
    if (copied >= 0) *slot = blk_set_new("RECEIVE", set_buf, (size_t)copied, 0);
    return 0;
}

/* RETRIEVE SET(ptr) LENGTH (flags as GGCRTRV's, INTO among them): the data of the START as one block, valid to the task's end
 * (IBM states no end: ASSUMED). The most is the stub's own 32768 bytes (GGCRTRV's buffer). */
int GGCRTRS(gg_cics *c, void **slot) {
    static char buf[32768];
    c->len = (int)sizeof buf;
    GGCRTRV(c, buf);
    if (c->resp == NORMAL) *slot = blk_set_new(NULL, buf, (size_t)c->len, 0);
    return 0;
}

/* READQ TS SET(ptr) LENGTH: the item as one block, valid until the next READQ TS. */
int GGCRDQS(gg_cics *c, void **slot) {
    static char buf[32768];
    c->len = (int)sizeof buf;
    GGCREADQ(c, buf);
    if (c->resp == NORMAL) *slot = blk_set_new("READQ", buf, (size_t)c->len, 0);
    return 0;
}

/* READ SET(ptr) [LENGTH] (flags as GGCREAD's; UPDATE / TOKEN among them): the record as one block, valid until the next READ of the
 * file, a corresponding REWRITE / DELETE / UNLOCK, or -- for a READ UPDATE -- a SYNCPOINT; GG-LEN the record's length.
 * The record goes through GGCREAD into the stub's own 32768 bytes (a longer record is refused there). */
int GGCRDST(gg_cics *c, char *ridfld, int keylen, void **slot) {
    static char buf[32768];
    char want[9], key[96];
    trim(c->name1, 8, want);
    c->len = (int)sizeof buf;
    set_form = 1;  /* #6262: the READ event is the SET form's */
    GGCREAD(c, ridfld, keylen, buf, (int)sizeof buf);
    set_form = 0;
    if (c->resp == NORMAL || c->resp == DUPKEY) {
        snprintf(key, sizeof key, "READ %s", want);
        *slot = blk_set_new(key, buf, (size_t)c->len, strstr(c->flags, "UPDATE") || strstr(c->flags, "TOKEN"));
    }
    return 0;
}

/* READNEXT (dir 1) / READPREV (dir -1) SET(ptr) (RIDFLD set to the key read): the record as one block, valid until the next
 * READNEXT / READPREV SET of the file's browse, its ENDBR or a SYNCPOINT. RBA browses are refused (as the translator does). */
static int browse_read_set(gg_cics *c, int dir, char *ridfld, int keylen, void **slot) {
    static char buf[32768];
    char want[9], path[3000], key[96];
    int reclen, keyoff, klen;
    trim(c->name1, 8, want);
    if (strstr(c->flags, "RBA")) refuse("READNEXT / READPREV SET in an RBA browse");
    set_form = 1;  /* #6262: the READNEXT / READPREV event is the SET form's */
    browse_read(c, dir, ridfld, keylen, buf, (int)sizeof buf);
    set_form = 0;
    if ((c->resp == NORMAL || c->resp == DUPKEY) && file_cfg(want, path, &reclen, &keyoff, &klen)) {
        snprintf(key, sizeof key, "BROWSE %s", want);
        *slot = blk_set_new(key, buf, (size_t)reclen, 1);
    }
    return 0;
}

int GGCRDNS(gg_cics *c, char *ridfld, int keylen, void **slot) {
    return browse_read_set(c, 1, ridfld, keylen, slot);
}

int GGCRDPS(gg_cics *c, char *ridfld, int keylen, void **slot) {
    return browse_read_set(c, -1, ridfld, keylen, slot);
}

/* GET CONTAINER SET(ptr) FLENGTH (GG-QNAME the container): a copy of the container's data as one block, valid until the next
 * GET CONTAINER SET of the container, its DELETE / MOVE or its channel's DELETE; FLENGTH (GG-LEN) the length of the data. */
int GGCGETS(gg_cics *c, void **slot) {
    char name[17], key[96];
    int ch;
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    ch = command_channel(c, 0, 4);
    if (!ch) return 0;
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (!k) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    {
        char flags[41];
        trim(c->flags, 40, flags);
        int into_ccsid = strstr(flags, "INTOCCSID") != NULL ? c->num : -1;
        if (k->bit && into_ccsid >= 0) refuse("GET CONTAINER SET INTOCCSID on a BIT container: the data is returned unconverted, and IBM does not say whether a block is then acquired");
        char *conv = malloc((size_t)k->len + 1);
        if (!conv) refuse("out of memory");
        memcpy(conv, k->data ? k->data : "", (size_t)k->len);
        if (!k->bit && !strstr(flags, "NOCONVERT")) ccsid_convert(conv, k->len, k->ccsid, into_ccsid >= 0 ? into_ccsid : REGION_CCSID, "GET CONTAINER");
        container_key(key, sizeof key, chans[ch - 1].name, name);
        *slot = blk_set_new(key, conv, (size_t)k->len, 0);
        free(conv);
        c->num = k->bit ? 0 : k->ccsid;
    }
    c->len = k->len;
    return 0;
}

#define GGCICS_WEB_PART3
#include "ggcics_web.c"  /* #5274: the web family, part 3 (WEB RETRIEVE, READ FORMFIELD / QUERYPARM, the browse forms) */
#undef GGCICS_WEB_PART3
