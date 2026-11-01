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

#include "ggcics_filewrite.c"  /* #5274: WRITE and REWRITE of a file */

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

#include "ggcics_terminal.c"  /* #5274: the terminal: RECEIVE MAP, RECEIVE, SEND MAP / CONTROL / TEXT and CONVERSE */

#include "ggcics_program.c"  /* #5274: program control: INQUIRE PROGRAM, XCTL, RETURN, the task dispatcher, LINK and its return */

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

#include "ggcics_inquire.c"  /* #5274: BIF DEEDIT, INQUIRE / SET TERMINAL, INQUIRE ASSOCIATION and the COMMAREA written out */

#include "ggcics_counters.c"  /* #5274: the named counters: GET, DEFINE, DELETE, QUERY, REWIND and UPDATE, fullword and doubleword */

#include "ggcics_system.c"  /* #5274: INQUIRE URIMAP, VERIFY PASSWORD, WRITE OPERATOR and DOCUMENT */

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

#include "ggcics_storage.c"  /* #5274: the storage block: GETMAIN, FREEMAIN, LOAD, RELEASE, BLL cells and ADDRESS */

#include "ggcics_setforms.c"  /* #5274: the SET(pointer) forms of RECEIVE, CONVERSE, RETRIEVE and the file and queue reads */

#define GGCICS_WEB_PART3
#include "ggcics_web.c"  /* #5274: the web family, part 3 (WEB RETRIEVE, READ FORMFIELD / QUERYPARM, the browse forms) */
#undef GGCICS_WEB_PART3
