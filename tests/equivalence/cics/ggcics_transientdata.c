/* #5274: the transient data family (READQ/WRITEQ/DELETEQ TD, SET/INQUIRE TDQUEUE) -- split out of ggcics.c, which includes it
 * where the block sat. */
/* ---- transient data (#5079, register X57) ---------------------------------------------------------------
 * An intrapartition queue is a first-in first-out file: <ts root>/td-<hex of the name>/NNNNNN.bin, the records from
 * `head` (the first one not yet read) on. tdqueues.cfg lists the CSD's queues, `NAME [TYPE]` (TYPE EXTRA: an
 * extrapartition queue; any other, or none: intrapartition); absent, every queue is defined and intrapartition. */
static void td_dir(const char *queue, char *dir, size_t size) {
    const char *root = getenv("GGCICS_TS");
    char hex[40];
    hex[0] = '\0';
    for (int i = 0; queue[i] && i < 16; i++) sprintf(hex + 2 * i, "%02X", (unsigned char)queue[i]);
    if (root) snprintf(dir, size, "%s/td-%s", root, hex);
    else snprintf(dir, size, "%s/ts/td-%s", dir_in(), hex);
}

/* 0: the CSD does not define the queue, 1: intrapartition (TYPE INTRA, or no TYPE column), 2: extrapartition, 3: any
 * other TYPE, or none stated ("-"): a queue READQ TD / DELETEQ TD do not model. */
static int td_kind(const char *queue) {
    char path[4096], line[256], name[32], type[32];
    snprintf(path, sizeof path, "%s/tdqueues.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    if (!cfg) return 1;
    int kind = 0;
    while (fgets(line, sizeof line, cfg)) {
        type[0] = '\0';
        if (sscanf(line, "%31s %31s", name, type) >= 1 && strcmp(name, queue) == 0)
            kind = !type[0] || strcmp(type, "INTRA") == 0 ? 1 : strcmp(type, "EXTRA") == 0 ? 2 : 3;
    }
    fclose(cfg);
    return kind;
}

static int td_head(const char *dir) {
    char path[4200];
    int head = 1;
    snprintf(path, sizeof path, "%s/head", dir);
    FILE *f = fopen(path, "r");
    if (f) { if (fscanf(f, "%d", &head) != 1) head = 1; fclose(f); }
    return head;
}

static int td_tail(const char *dir, int head) {
    struct stat st;
    char path[4200];
    int n = head;
    for (;;) {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, n);
        if (stat(path, &st) != 0) return n;
        n++;
    }
}

/* #5168: a queue's CSD attribute -- a KEY=VALUE word after NAME TYPE on its tdqueues.cfg line (RECOVSTATUS, TYPEFILE,
 * OPENTIME, INDIRECTNAME, TRIGGERLEVEL, TRANSID: the cases write only the ones the definition states). 1 and `out` when stated. */
static int td_attr(const char *queue, const char *key, char *out, size_t size) {
    char path[4096], line[256], name[32];
    int found = 0;
    size_t klen = strlen(key);
    snprintf(path, sizeof path, "%s/tdqueues.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    if (!cfg) return 0;
    while (fgets(line, sizeof line, cfg)) {
        char *w = strtok(line, " \t\r\n");
        if (!w) continue;
        snprintf(name, sizeof name, "%s", w);
        if (strcmp(name, queue) != 0) continue;
        found = 0;
        out[0] = '\0';
        strtok(NULL, " \t\r\n"); /* TYPE */
        while ((w = strtok(NULL, " \t\r\n")) != NULL) {
            if (strncmp(w, key, klen) == 0 && w[klen] == '=') { snprintf(out, size, "%s", w + klen + 1); found = 1; }
        }
    }
    fclose(cfg);
    return found;
}

/* The queue's own TYPE word ("" when none is stated or the CSD does not define it). */
static int td_type_word(const char *queue, char *type, size_t size) {
    char path[4096], line[256], name[32], t[32];
    int found = 0;
    type[0] = '\0';
    snprintf(path, sizeof path, "%s/tdqueues.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    if (!cfg) return 0;
    while (fgets(line, sizeof line, cfg)) {
        t[0] = '\0';
        if (sscanf(line, "%31s %31s", name, t) >= 1 && strcmp(name, queue) == 0) {
            found = 1;
            snprintf(type, size, "%s", t);
        }
    }
    fclose(cfg);
    return found;
}

/* #5168 (X61): an INDIRECT queue routes to the queue its INDIRECTNAME names ("the name of the transient data queue to which
 * this indirect queue routes data"; the target may itself be indirect). `target` is the queue that holds the records. Refused
 * by name: an INDIRECT queue with no INDIRECTNAME, one whose target the CSD does not define, a chain that loops. */
static void td_resolve(const char *queue, char *target) {
    char type[32], next[32];
    snprintf(target, 17, "%s", queue);
    for (int hops = 0;; hops++) {
        if (!td_type_word(target, type, sizeof type) || strcmp(type, "INDIRECT") != 0) return;
        if (!td_attr(target, "INDIRECTNAME", next, sizeof next)) refuse("an INDIRECT TD queue without INDIRECTNAME: not modelled");
        if (hops >= 8) refuse("a chain of INDIRECT TD queues that loops: not modelled");
        if (!td_type_word(next, type, sizeof type)) refuse("an INDIRECT TD queue whose target the CSD does not define: not modelled");
        snprintf(target, 17, "%s", next);
    }
}

/* #5168 round 3 (X61): the run-time open state a SET TDQUEUE OPENSTATUS left, in a file beside the queue's directory (so it
 * outlives the task, as the queue's records do): -1 none was set, 0 closed, 1 open. It overrides the CSD's OPENTIME. */
static int td_open_override(const char *queue) {
    char dir[4096], path[4200], word[16] = "";
    td_dir(queue, dir, sizeof dir);
    snprintf(path, sizeof path, "%s.open", dir);
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    if (fscanf(f, "%15s", word) != 1) word[0] = '\0';
    fclose(f);
    return strcmp(word, "OPEN") == 0 ? 1 : strcmp(word, "CLOSED") == 0 ? 0 : -1;
}

/* #5168 round 5 (X66): 1 when SET TDQUEUE ENABLESTATUS(DISABLED) left the queue disabled ("The queue cannot be accessed by
 * applications"); the state is in a file beside the queue's directory, so it outlives the task. ENABLED until a SET says otherwise. */
static int td_disabled(const char *queue) {
    char dir[4096], path[4200], word[16] = "";
    td_dir(queue, dir, sizeof dir);
    snprintf(path, sizeof path, "%s.enable", dir);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    if (fscanf(f, "%15s", word) != 1) word[0] = '\0';
    fclose(f);
    return strcmp(word, "DISABLED") == 0;
}

/* 1 when an extrapartition queue's data set is closed: the SET TDQUEUE state if there is one, else OPENTIME DEFERRED ("the data
 * set remains closed until you indicate that you want to open it"); INITIAL (or none stated: ASSUMED) is open. */
static int td_extra_closed(const char *queue) {
    char open[16];
    int set = td_open_override(queue);
    if (set >= 0) return !set;
    return td_attr(queue, "OPENTIME", open, sizeof open) && strcmp(open, "DEFERRED") == 0;
}

/* #5168 (X61): an extrapartition queue's state: 0 open for input, 1 open for output, 2 closed (td_extra_closed). Refused: a
 * TYPEFILE other than INPUT / OUTPUT (RDBACK, or none stated). */
static int td_extra_state(const char *queue) {
    char file[16];
    if (!td_attr(queue, "TYPEFILE", file, sizeof file) || (strcmp(file, "INPUT") != 0 && strcmp(file, "OUTPUT") != 0))
        refuse("READQ TD of an extrapartition queue with no TYPEFILE INPUT / OUTPUT: not modelled");
    if (td_extra_closed(queue)) return 2;
    return strcmp(file, "INPUT") == 0 ? 0 : 1;
}

/* #5168 round 7 (X66): a queue's TRIGGERLEVEL: what SET TDQUEUE TRIGGERLEVEL left (the file beside the queue's directory, so it
 * outlives the task), else the definition's, else 1 (IBM's default). */
static int td_trigger_level(const char *queue) {
    char dir[4096], path[4200], stated[40];
    int n;
    td_dir(queue, dir, sizeof dir);
    snprintf(path, sizeof path, "%s.trig", dir);
    FILE *f = fopen(path, "r");
    if (f) {
        int got = fscanf(f, "%d", &n);
        fclose(f);
        if (got == 1) return n;
    }
    return td_attr(queue, "TRIGGERLEVEL", stated, sizeof stated) ? atoi(stated) : 1;
}

/* #5168 (X61): automatic task initiation is not modelled: a WRITEQ TD that brings a queue with a TRANSID to its TRIGGERLEVEL
 * (default 1; 0 turns ATI off) would start that task. */
static void td_ati_check(const char *queue, int records_after) {
    char transid[16];
    int n;
    if (!td_attr(queue, "TRANSID", transid, sizeof transid)) return;
    n = td_trigger_level(queue);
    if (n > 0 && records_after >= n) refuse("WRITEQ TD to a queue that reaches its TRIGGERLEVEL: automatic task initiation is not modelled");
}

static void td_base(void) {
    const char *root = getenv("GGCICS_TS");
    char base[4096];
    if (root) snprintf(base, sizeof base, "%s", root);
    else snprintf(base, sizeof base, "%s/ts", dir_in());
    MKDIR(base);
}

static void td_clear(const char *dir) {
    char path[4200];
    int head = td_head(dir), tail = td_tail(dir, head);
    for (int i = head; i < tail; i++) {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, i);
        remove(path);
    }
    snprintf(path, sizeof path, "%s/head", dir);
    remove(path);
    RMDIR(dir);
}

static void td_copy_dir(const char *from, const char *to) {
    char a[4200], b[4200];
    int head = td_head(from), tail = td_tail(from, head);
    MKDIR(to);
    for (int i = head; i < tail; i++) {
        snprintf(a, sizeof a, "%s/%06d.bin", from, i);
        snprintf(b, sizeof b, "%s/%06d.bin", to, i);
        copy_file(a, b);
    }
    if (head != tail) {
        snprintf(b, sizeof b, "%s/head", to);
        FILE *f = fopen(b, "w");
        if (f) { fprintf(f, "%d\n", head); fclose(f); }
    }
}

/* #5168 (X61): RECOVSTATUS. LOGICAL: "restored to the state at the end of the last completed unit of work" -- the first read, write or
 * delete of the queue since the last SYNCPOINT saves it aside (<dir>.uow), SYNCPOINT drops the copy, SYNCPOINT ROLLBACK puts it back.
 * NO (and none stated: ASSUMED) commits at once, as X57. PHYSICAL ("the last READQ is backed out if its unit of work did not commit"):
 * a SYNCPOINT ROLLBACK after touching one is refused by name. */
#define MAX_TD_UOW 16
static char td_uow_q[MAX_TD_UOW][17];
static int td_uow_logical[MAX_TD_UOW], td_uow_n;

static void td_touch(const char *queue) {
    char rec[16], dir[4096], aside[4200];
    int logical;
    if (!td_attr(queue, "RECOVSTATUS", rec, sizeof rec)) return;
    logical = strcmp(rec, "LOGICAL") == 0;
    if (!logical && strcmp(rec, "PHYSICAL") != 0) return;
    for (int i = 0; i < td_uow_n; i++) if (strcmp(td_uow_q[i], queue) == 0) return;
    if (td_uow_n >= MAX_TD_UOW) refuse("a unit of work that touches more than 16 recoverable TD queues");
    snprintf(td_uow_q[td_uow_n], sizeof td_uow_q[0], "%s", queue);
    td_uow_logical[td_uow_n++] = logical;
    if (logical) {
        td_base();
        td_dir(queue, dir, sizeof dir);
        snprintf(aside, sizeof aside, "%s.uow", dir);
        td_clear(aside);
        td_copy_dir(dir, aside);
    }
}

static void td_uow_end(int rollback) {
    char dir[4096], aside[4200];
    for (int i = 0; i < td_uow_n; i++) {
        if (!td_uow_logical[i]) {
            if (rollback) refuse("SYNCPOINT ROLLBACK after a READQ / WRITEQ / DELETEQ TD of a PHYSICALLY recoverable queue: not modelled");
            continue;
        }
        td_dir(td_uow_q[i], dir, sizeof dir);
        snprintf(aside, sizeof aside, "%s.uow", dir);
        if (rollback) {
            td_clear(dir);
            td_copy_dir(aside, dir);
        }
        td_clear(aside);
    }
    td_uow_n = 0;
}

/* WRITEQ TD QUEUE(qname) FROM LENGTH(GG-LEN): one record on a transient-data queue -- recorded with its data and
 * compared (CardDemo's CORPT00C submits JCL through the JOBS queue), and appended to an intrapartition queue for a
 * READQ TD to read. QIDERR for a queue the CSD does not define (tdqueues.cfg; absent, every queue is defined). */
int GGCWRTD(gg_cics *c, char *from) {
    char queue[17], target[17], ev[96], dir[4096], path[4200];
    int fresp, fresp2, kind;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    td_resolve(queue, target); /* #5168: an INDIRECT queue holds its records on its target */
    kind = td_kind(target);
    if (injected("WRITEQ-TD", queue, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (!kind) {
        c->resp = QIDERR;
    } else if (td_disabled(target)) {
        c->resp = DFHRESP_DISABLED; /* #5168 round 5 (X66) */
    } else if (kind == 2) {
        /* #5168 (X61): IBM WRITEQ TD: INVREQ for an extrapartition queue opened for input, NOTOPEN for a closed one. A queue with no
         * TYPEFILE (or RDBACK) is still taken as open for output (ASSUMED), as before. */
        char file[16];
        if (td_extra_closed(target)) c->resp = DFHRESP_NOTOPEN;
        else if (td_attr(target, "TYPEFILE", file, sizeof file) && strcmp(file, "INPUT") == 0) c->resp = INVREQ;
    }
    if (c->resp == NORMAL && kind == 1) {
        td_base();
        td_dir(target, dir, sizeof dir);
        td_touch(target);
        td_ati_check(target, td_tail(dir, td_head(dir)) - td_head(dir) + 1);
        MKDIR(dir);
        snprintf(path, sizeof path, "%s/%06d.bin", dir, td_tail(dir, td_head(dir)));
        FILE *f = fopen(path, "wb");
        if (f) { if (c->len > 0) fwrite(from, 1, (size_t)c->len, f); fclose(f); }
    }
    snprintf(ev, sizeof ev, "WRITEQ-TD queue=%s len=%d resp=%d", queue, c->len, c->resp);
    event(ev, c->resp == NORMAL ? from : NULL, c->resp == NORMAL ? c->len : 0);
    return 0;
}

/* READQ TD QUEUE INTO LENGTH(c->len) (IBM, EXEC CICS READQ TD): a destructive read, first in first out. QIDERR when the
 * CSD does not define the queue; QZERO when it holds no record; LENGERR for a LENGTH below zero (nothing is read) or a
 * record longer than LENGTH (the record is read, so lost, and INTO gets its first LENGTH bytes; LENGTH 0: none); LENGTH
 * is set to the record's own length. An extrapartition queue, a record moved past INTO: refused (X57, X6). */
int GGCRDTD(gg_cics *c, char *into, int intolen) {
    char queue[17], hex[40], dir[4096], path[4200], ev[160], buf[32768];
    char target[17], rec[16], fl[40];
    int max = c->len, n = 0, copied = 0, shown = -1, kind, state = 0, fresp, fresp2, nosuspend;
    trim(c->qname, 16, queue);
    trim(c->flags, 40, fl); /* #5168 (X61): TDNOSUSPEND, read once and cleared (FETCH leaves NOSUSPEND in the same field) */
    nosuspend = strstr(fl, "TDNOSUSPEND") != NULL;
    c->flags[0] = '\0';
    hex[0] = '\0';
    for (int i = 0; queue[i]; i++) sprintf(hex + 2 * i, "%02X", (unsigned char)queue[i]);
    c->resp = NORMAL;
    c->resp2 = 0;
    td_resolve(queue, target); /* #5168 */
    kind = td_kind(target);
    if (kind == 3) refuse("READQ TD of a queue whose TYPE is not INTRA or EXTRA: not modelled");
    if (kind == 2) state = td_extra_state(target); /* #5168: closed NOTOPEN, open for output INVREQ; IOERR: planned only (faults.cfg READQ-TD) */
    if (!kind) {
        c->resp = QIDERR;
    } else if (td_disabled(target)) {
        c->resp = DFHRESP_DISABLED; /* #5168 round 5 (X66) */
    } else if (state == 2) {
        c->resp = DFHRESP_NOTOPEN;
    } else if (state == 1) {
        c->resp = INVREQ;
    } else if (max < 0) {
        c->resp = LENGERR;
    } else {
        td_touch(target);
        td_dir(target, dir, sizeof dir);
        int head = td_head(dir), tail = td_tail(dir, head);
        int busyable = kind == 1 && head == tail && td_attr(target, "RECOVSTATUS", rec, sizeof rec) && strcmp(rec, "LOGICAL") == 0;
        if ((kind == 2 || busyable) && injected("READQ-TD", queue, &fresp, &fresp2)) {
          if (busyable != (fresp == DFHRESP_QBUSY)) refuse("a planned READQ TD QBUSY is for a LOGICAL intrapartition queue with no record, IOERR for an extrapartition one");
          if (busyable) {
            /* #5168 (X61): a planned QBUSY on a LOGICAL intrapartition queue with no committed record; no RESP2 (IBM lists none) */
            if (!nosuspend) {
                snprintf(ev, sizeof ev, "READQ TD on a planned-busy queue without NOSUSPEND: %s (the task would be suspended)", queue);
                refuse(ev);
            }
            c->resp = fresp;
            c->resp2 = fresp2;
          } else {
            /* #5168 (X61): a planned IOERR on an open input queue; IBM: "the data record in error is skipped", so the record
             * is consumed and nothing reaches INTO. Counted for an open extrapartition queue only, as CicsTask counts it. */
            c->resp = fresp;
            c->resp2 = fresp2;
            if (head != tail) {
                snprintf(path, sizeof path, "%s/%06d.bin", dir, head);
                remove(path);
                snprintf(path, sizeof path, "%s/head", dir);
                FILE *f = fopen(path, "w");
                if (f) { fprintf(f, "%d\n", head + 1); fclose(f); }
            }
          }
        } else if (head == tail) {
            c->resp = DFHRESP_QZERO;
        } else {
            snprintf(path, sizeof path, "%s/%06d.bin", dir, head);
            FILE *f = fopen(path, "rb");
            if (f) { n = (int)fread(buf, 1, sizeof buf, f); fclose(f); }
            copied = n < max ? n : max;
            if (copied > intolen) refuse("READQ TD INTO LENGTH: a record moved past INTO");
            memcpy(into, buf, (size_t)copied);
            c->resp = n > max ? LENGERR : NORMAL;
            c->len = shown = n;
            remove(path);
            snprintf(path, sizeof path, "%s/head", dir);
            f = fopen(path, "w");
            if (f) { fprintf(f, "%d\n", head + 1); fclose(f); }
        }
    }
    snprintf(ev, sizeof ev, "READQ-TD queue=%s resp=%d len=%d copied=%d", hex, c->resp, shown, copied);
    event(ev, into, copied);
    return 0;
}

/* DELETEQ TD QUEUE (IBM, EXEC CICS DELETEQ TD): every record of an intrapartition queue; QIDERR when the CSD does not
 * define it, INVREQ (RESP2 0: IBM lists none) for an extrapartition queue. */
int GGCDLTD(gg_cics *c) {
    char queue[17], target[17], dir[4096], path[4200];
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    td_resolve(queue, target); /* #5168 */
    int kind = td_kind(target);
    if (!kind) { c->resp = QIDERR; return 0; }
    if (td_disabled(target)) { c->resp = DFHRESP_DISABLED; return 0; } /* #5168 round 5 (X66) */
    if (kind == 2) { c->resp = INVREQ; return 0; }
    if (kind == 3) refuse("DELETEQ TD of a queue whose TYPE is not INTRA or EXTRA: not modelled");
    td_touch(target);
    td_dir(target, dir, sizeof dir);
    int head = td_head(dir), tail = td_tail(dir, head);
    for (int i = head; i < tail; i++) {
        snprintf(path, sizeof path, "%s/%06d.bin", dir, i);
        remove(path);
    }
    snprintf(path, sizeof path, "%s/head", dir);
    remove(path);
    RMDIR(dir);
    return 0;
}

/* READQ TD SET(ptr) LENGTH (#5168, X61): the record as one block, valid until the next READQ TD ("until the next READQ TD or the end of
 * the task"); answers as the INTO form does (the same conditions and event). */
int GGCRDTS(gg_cics *c, void **slot) {
    static char buf[32768];
    c->len = (int)sizeof buf;
    GGCRDTD(c, buf, (int)sizeof buf);
    if (c->resp == NORMAL) *slot = blk_set_new("READQ TD", buf, (size_t)c->len, 0);
    return 0;
}

/* ---- #5168 round 3 (X61): SET / INQUIRE TDQUEUE OPENSTATUS (IBM CICS TS 6.x, SET TDQUEUE, INQUIRE TDQUEUE) ----
 * The queue is in GG-QNAME. CVDAs: OPEN 18, CLOSED 19, NOTAPPLIC 1; TYPE: INTRA 222, EXTRA 221, INDIRECT 122, REMOTE 4.
 * SET OPENSTATUS (extrapartition queues only; the data set "is to be opened / closed"): QIDERR RESP2 1 (the queue cannot be
 * found), INVREQ RESP2 9 for an intrapartition queue, RESP2 8 for an invalid CVDA. The state outlives the task (td_open_override)
 * and replaces OPENTIME. Setting the state a queue is already in is NORMAL (ASSUMED). Refused by name: an INDIRECT / REMOTE queue
 * (IBM names only intrapartition), an invalid CVDA on a queue that is not extrapartition (IBM does not order RESP2 8 / 9 / QIDERR),
 * OPEN with no TYPEFILE INPUT / OUTPUT (no direction to open it in), OPEN of an input queue that has been read (reopening
 * restarts the data set; the records are consumed), RESP2 16 (the DDNAME is taken as found). INQUIRE: QIDERR RESP2 1; OPENSTATUS
 * (GG-NUM) OPEN / CLOSED for an extrapartition queue, NOTAPPLIC ("the queue is not extrapartition") for the others; TYPE (GG-LEN);
 * GG-FLAGS says which are wanted, and a queue with no TYPE stated is refused for either. */
static int td_type_cvda(const char *queue, int kind, char *word, size_t size) {
    td_type_word(queue, word, size);
    if (kind == 1) return 222;
    if (kind == 2) return 221;
    if (strcmp(word, "INDIRECT") == 0) return 122;
    if (strcmp(word, "REMOTE") == 0) return 4;
    refuse("INQUIRE TDQUEUE of a queue with no TYPE stated");
    return 0;
}

int GGCSTDQ(gg_cics *c) {
    char queue[17], file[16], dir[4096], path[4200];
    int cvda = c->num, kind;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    kind = td_kind(queue);
    if (cvda != 18 && cvda != 19 && kind != 2)
        refuse("SET TDQUEUE OPENSTATUS with an invalid CVDA on a queue that is not extrapartition: IBM does not say which condition comes first");
    if (!kind) { c->resp = QIDERR; c->resp2 = 1; return 0; }
    if (kind == 1) { c->resp = INVREQ; c->resp2 = 9; return 0; }
    if (kind == 3) refuse("SET TDQUEUE OPENSTATUS of an INDIRECT or REMOTE queue");
    if (cvda != 18 && cvda != 19) { c->resp = INVREQ; c->resp2 = 8; return 0; }
    td_dir(queue, dir, sizeof dir);
    if (cvda == 18) {
        if (!td_attr(queue, "TYPEFILE", file, sizeof file) || (strcmp(file, "INPUT") != 0 && strcmp(file, "OUTPUT") != 0))
            refuse("SET TDQUEUE OPENSTATUS(OPEN) of an extrapartition queue with no TYPEFILE INPUT / OUTPUT");
        if (strcmp(file, "INPUT") == 0 && td_head(dir) != 1)
            refuse("SET TDQUEUE OPENSTATUS(OPEN) of an input queue that has been read: reopening restarts the data set");
    }
    td_base();
    snprintf(path, sizeof path, "%s.open", dir);
    FILE *f = fopen(path, "w");
    if (f) { fprintf(f, "%s\n", cvda == 18 ? "OPEN" : "CLOSED"); fclose(f); }
    return 0;
}

/* #5168 round 5 (X66): SET TDQUEUE ENABLESTATUS (IBM CICS TS 6.x, SET TDQUEUE). The queue is in GG-QNAME, the CVDA in GG-NUM:
 * ENABLED 23, DISABLED 24. QIDERR RESP2 1; INVREQ RESP2 10 for an invalid CVDA. Setting the state a queue is in is NORMAL (ASSUMED).
 * Refused by name: an invalid CVDA on a queue the CSD does not define (IBM does not order the two), an INDIRECT / REMOTE queue. */
int GGCSTDE(gg_cics *c) {
    char queue[17], dir[4096], path[4200];
    int cvda = c->num, kind, valid = cvda == 23 || cvda == 24;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    kind = td_kind(queue);
    if (!kind) {
        if (!valid) refuse("SET TDQUEUE ENABLESTATUS with an invalid CVDA on a queue the CSD does not define: IBM does not say which condition comes first");
        c->resp = QIDERR;
        c->resp2 = 1;
        return 0;
    }
    if (kind == 3) refuse("SET TDQUEUE ENABLESTATUS of an INDIRECT or REMOTE queue");
    if (!valid) { c->resp = INVREQ; c->resp2 = 10; return 0; }
    td_dir(queue, dir, sizeof dir);
    td_base();
    snprintf(path, sizeof path, "%s.enable", dir);
    FILE *f = fopen(path, "w");
    if (f) { fprintf(f, "%s\n", cvda == 24 ? "DISABLED" : "ENABLED"); fclose(f); }
    return 0;
}

/* #5168 round 7 (X66): SET TDQUEUE TRIGGERLEVEL (IBM CICS TS 6.x, SET TDQUEUE: intrapartition queues only). The queue is in GG-QNAME,
 * the level in GG-NUM; 0 turns automatic task initiation off. QIDERR RESP2 1. Not a unit-of-work resource: a rollback or an abend
 * keeps it. Refused by name: a queue that is not intrapartition (IBM names no condition), a level below zero. */
int GGCSTDT(gg_cics *c) {
    char queue[17], dir[4096], path[4200];
    int kind;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    kind = td_kind(queue);
    if (!kind) { c->resp = QIDERR; c->resp2 = 1; return 0; }
    if (kind != 1 || c->num < 0) refuse("SET TDQUEUE TRIGGERLEVEL of a queue that is not intrapartition, or below zero");
    td_dir(queue, dir, sizeof dir);
    td_base();
    snprintf(path, sizeof path, "%s.trig", dir);
    FILE *f = fopen(path, "w");
    if (f) { fprintf(f, "%d\n", (int)c->num); fclose(f); }
    return 0;
}

int GGCITDQ(gg_cics *c) {
    char queue[17], word[32];
    int kind;
    trim(c->qname, 16, queue);
    c->resp = NORMAL;
    c->resp2 = 0;
    kind = td_kind(queue);
    if (!kind) { c->resp = QIDERR; c->resp2 = 1; return 0; }
    /* #5168 round 6 (X66): TRIGGERLEVEL (hours), RECOVSTATUS (mins) and TRANSID (rtran). An intrapartition queue answers by its
     * definition: TRIGGERLEVEL (1 when none stated: IBM's default), TRANSID (blanks when none: ASSUMED), RECOVSTATUS LOGICAL 216 /
     * PHYSICAL 215 / NOTRECOVABLE 30 (none stated: X61 assumption 2); the others answer RECOVSTATUS NOTAPPLIC 1 ("the queue is not
     * intrapartition") and refuse TRIGGERLEVEL / TRANSID (IBM names no value). */
    if (strstr(c->flags, "TRIGGERLEVEL") || strstr(c->flags, "TRANSID") || strstr(c->flags, "RECOVSTATUS")) {
        char stated[40];
        if (kind != 1 && (strstr(c->flags, "TRIGGERLEVEL") || strstr(c->flags, "TRANSID"))) {
            td_type_cvda(queue, kind, word, sizeof word);
            refuse("INQUIRE TDQUEUE TRIGGERLEVEL / TRANSID of a queue that is not intrapartition");
        }
        if (kind != 1) td_type_cvda(queue, kind, word, sizeof word);
        if (strstr(c->flags, "TRIGGERLEVEL")) c->hours = td_trigger_level(queue);
        if (strstr(c->flags, "RECOVSTATUS")) {
            int got = kind == 1 && td_attr(queue, "RECOVSTATUS", stated, sizeof stated);
            c->mins = kind != 1 ? 1 : got && strcmp(stated, "LOGICAL") == 0 ? 216 : got && strcmp(stated, "PHYSICAL") == 0 ? 215 : 30;
        }
        if (strstr(c->flags, "TRANSID")) {
            memset(c->rtran, ' ', sizeof c->rtran);
            if (td_attr(queue, "TRANSID", stated, sizeof stated)) memcpy(c->rtran, stated, strlen(stated) < 4 ? strlen(stated) : 4);
        }
    }
    if (strstr(c->flags, "TYPE")) c->len = td_type_cvda(queue, kind, word, sizeof word);
    if (strstr(c->flags, "ENABLESTATUS")) c->item = td_disabled(queue) ? 24 : 23; /* #5168 round 5 (X66): its own state */
    if (strstr(c->flags, "OPENSTATUS")) {
        if (kind == 2) c->num = td_extra_closed(queue) ? 19 : 18;
        else {
            td_type_cvda(queue, kind, word, sizeof word);
            c->num = 1;
        }
    }
    return 0;
}
