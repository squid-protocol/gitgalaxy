/* #4270, #5079, #4950, #5274: the task / interval control family of the stub -- START, RETRIEVE, RUN TRANSID and its child
 * tasks (FETCH, FREE), DELAY, POST, WAIT EVENT and CANCEL -- split out of ggcics.c, which includes it where the block sat. */
/* This task's own STARTs with a REQID, for a CANCEL in the same task. */
static struct { char reqid[17]; time_t expires; int cancelled; int data; } own[64];
static int nown = 0;

/* ---- #5079 (register X63): POST and WAIT EVENT, as CicsTask.post / waitEvent. The timer-event control area is a 4-byte block of
 * task storage (blk_set_new), posted (first byte X'40', third X'80') by a WAIT EVENT, which runs the stated clock to the expiry, or by
 * a CANCEL of the POST. A task has one live POST: a later POST, a local START or a DELAY ends it (IBM, POST), and a WAIT EVENT on
 * an area so ended is refused. */
static struct { void *area; int released; } post_areas[64];
static int npost_areas = 0, post_seq = 0;
static void *post_live = NULL;
static time_t post_at = 0;
static char post_reqid[17] = "";

static void post_release(void) {
    if (!post_live) return;
    for (int i = 0; i < npost_areas; i++) if (post_areas[i].area == post_live) post_areas[i].released = 1;
    for (int i = 0; i < nown; i++) if (strcmp(own[i].reqid, post_reqid) == 0) own[i].cancelled = 1;
    post_live = NULL;
    post_reqid[0] = '\0';
}

static void post_area(void *area) {
    unsigned char *b = (unsigned char *)area;
    b[0] = 0x40;
    b[2] = 0x80;
}

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
        post_release();  /* #5079 (X63): IBM, POST: a local START ends the POST's area */
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
#define MAX_RUN_DEPTH 3 /* #5089: generations below a task RUN children go (CicsTask.MAX_RUN_DEPTH) */
/* #5089: 0 for a task, its parent's + 1 for a RUN child ($GGCICS_DEPTH, set by the parent's dispatch) */
static int run_depth(void) {
    const char *d = getenv("GGCICS_DEPTH");
    return d ? atoi(d) : 0;
}
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
    if (run_depth() >= MAX_RUN_DEPTH) /* #5089 (X18): a child may RUN children of its own, to a stated depth */
        refuse("RUN TRANSID in a RUN TRANSID child task 3 levels below a task (a great-great-grandchild): the depth the "
               "harness models ends here");
    int fresp, fresp2;
    if (injected("RUN-TRANSID", "-", &fresp, &fresp2)) { /* #6882 (X18): a planned condition; no child is started */
        c->resp = fresp;
        c->resp2 = fresp2;
        snprintf(ev, sizeof ev, "RUN transid=%s resp=%d resp2=%d", transid, c->resp, c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
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

#ifndef _WIN32
/* #6967 (X18): the lines of this task's faults.cfg for a RUN child of `transid` (`@TRANSID CMD NAME NTH RESP RESP2
 * [ABCODE]`) become the child's own faults.cfg, the prefix off: the child counts its commands as a task of its own, as
 * CicsTask.childFaults. */
static void child_faults(const char *transid, const char *to) {
    char path[4200], line[256], tag[16];
    snprintf(path, sizeof path, "%s/faults.cfg", dir_in());
    FILE *f = fopen(path, "r");
    if (!f) return;
    snprintf(tag, sizeof tag, "@%s ", transid);
    size_t n = strlen(tag);
    FILE *g = NULL;
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, tag, n) != 0) continue;
        if (!g) {
            snprintf(path, sizeof path, "%s/faults.cfg", to);
            if (!(g = fopen(path, "w"))) refuse("cannot write a child's configuration");
        }
        fputs(line + n, g);
    }
    fclose(f);
    if (g) fclose(g);
}

/* #6967 (X18): the faults that fired in a child (its directory's out/faults.txt), appended to this task's at the
 * child's end, each line `@TRANSID ` first, as CicsTask.childFired. */
static void child_fired(const char *transid, const char *dir) {
    char path[4300], line[256];
    snprintf(path, sizeof path, "%s/out/faults.txt", dir);
    FILE *f = fopen(path, "r");
    if (!f) return;
    snprintf(path, sizeof path, "%s/faults.txt", dir_out());
    FILE *g = fopen(path, "a");
    if (!g) refuse("cannot write the fault log");
    while (fgets(line, sizeof line, f)) fprintf(g, "@%s %s", transid, line);
    fclose(f);
    fclose(g);
}
#endif

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
        copy_cfg("childprogs.cfg", dir); /* #5089: the child's own children run the case's programs too */
        child_faults(k->transid, dir);
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
            snprintf(num, sizeof num, "%d", run_depth() + 1);
            setenv("GGCICS_DEPTH", num, 1);
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
        child_fired(k->transid, dir);
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
    int fresp, fresp2; /* #6271 (X72): a planned EXPIRED / INVREQ: the delay is not performed (no children dispatched, no clock move) */
    if (injected("DELAY", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
    post_release();  /* #5079 (X63): IBM, POST: a subsequent DELAY ends the POST's area */
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

/* POST INTERVAL(hhmmss) | TIME(hhmmss) (GG-NUM) | AFTER / AT HOURS MINUTES SECONDS (GG-HOURS / GG-MINS / GG-SECS; GG-FLAGS says
 * which) [REQID(qname)] SET(ptr) (IBM, EXEC CICS POST): the 4-byte timer-event control area, binary zeros until posted. INVREQ
 * RESP2 4 / 5 / 6 for hours / minutes / seconds out of range; EXPIRED for a TIME already past (no area, the pointer as it was). A
 * POST with no REQID runs under POSTnnnn (ASSUMED: IBM "generates one"), returned in GG-NAME1 for EIBREQID. */
int GGCPOST(gg_cics *c, void **slot) {
    char flags[41], reqid[17];
    int hhmmss = c->num, resp2 = 0, after, is_time;
    time_t now = now_epoch(), at;
    trim(c->flags, 40, flags);
    trim(c->qname, 8, reqid);
    after = flag_word(flags, "AFTER") || flag_word(flags, "AT");
    is_time = flag_word(flags, "TIME") || flag_word(flags, "AT");
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
    c->resp = NORMAL;
    c->resp2 = 0;
    if (resp2) {
        c->resp = INVREQ;
        c->resp2 = resp2;
        return 0;
    }
    int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
    if (is_time) {
        struct tm t;
        gmtime_r(&now, &t);
        t.tm_hour = 0;
        t.tm_min = 0;
        t.tm_sec = 0;
        at = timegm(&t) + hh * 3600 + mm * 60 + ss;
        if (hh <= 23 && at < now) {
            c->resp = DFHRESP_EXPIRED;
            return 0;
        }
    } else {
        at = now + hh * 3600 + mm * 60 + ss;
    }
    if (!reqid[0]) snprintf(reqid, sizeof reqid, "POST%04d", ++post_seq);
    if (npost_areas >= 64 || nown >= 64) refuse("more than 64 POSTs in a task");
    post_release();
    post_live = blk_set_new(NULL, "\0\0\0\0", 4, 0);
    post_areas[npost_areas].area = post_live;
    post_areas[npost_areas++].released = 0;
    post_at = at;
    snprintf(post_reqid, sizeof post_reqid, "%s", reqid);
    snprintf(own[nown].reqid, sizeof own[nown].reqid, "%s", reqid);
    own[nown].expires = at;
    own[nown].data = 0;
    own[nown++].cancelled = 0;
    memset(c->name1, ' ', 8);
    memcpy(c->name1, reqid, strlen(reqid) < 8 ? strlen(reqid) : 8);
    *slot = post_live;
    return 0;
}

/* WAIT EVENT ECADDR(ptr) (IBM, EXEC CICS WAIT EVENT), as CicsTask.waitEvent: INVREQ RESP2 2 for a null pointer. An area not yet
 * posted is posted at its expiry -- the RUN children not yet run are dispatched, the scheduler's clock runs to it (a task takes no
 * time, X4); one already posted returns at once (ASSUMED). Refused: an address that is no POST's area, an area a later POST,
 * CANCEL, local START or DELAY ended (IBM: "unpredictable"). */
int GGCWEVT(gg_cics *c, void **slot) {
    void *area = *slot;
    int i;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (area == NULL) {
        c->resp = INVREQ;
        c->resp2 = 2;
        return 0;
    }
    for (i = 0; i < npost_areas && post_areas[i].area != area; i++) {}
    if (i == npost_areas) refuse("WAIT EVENT on an address that is no POST's timer-event control area");
    if (post_areas[i].released) refuse("WAIT EVENT on a timer-event control area a later POST, CANCEL, START or DELAY ended");
    if (((unsigned char *)area)[0] != 0x40) {
        long long ms = (long long)(post_at - now_epoch()) * 1000;
        dispatch_children();
        waited += ms > 0 ? ms : 0;
        post_area(area);
        for (int k = 0; k < nown; k++) if (strcmp(own[k].reqid, post_reqid) == 0) own[k].cancelled = 1;
    }
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
 * (GG-ITEM 1: the child abended) and COMPSTATUS's CVDA in GG-NUM (NORMAL 1016, ABEND 900; SECERROR 1214 when the scenario
 * plans a FETCH-STATUS, #6967). */
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
    int fresp, fresp2;
    if (!strstr(c->flags, "CHILD") && injected("FETCH-ANY", "-", &fresp, &fresp2)) { /* #6882 (X18): nothing is fetched */
        c->resp = fresp;
        c->resp2 = fresp2;
        goto done;
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
    const char *compst = k->abended ? "ABEND" : "NORMAL";
    int sresp, sresp2;
    if (injected("FETCH-STATUS", "-", &sresp, &sresp2)) { /* #6967 (X18): the child failed a security check */
        if (k->abended) refuse("a planned SECERROR COMPSTATUS for a child that abended (IBM does not say which status wins)");
        c->num = sresp;
        compst = "SECERROR";
    }
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
             k->token, compst, k->abended ? k->abcode : "-", reply[0] ? reply : "-");
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
    if (found && post_live && strcmp(reqid, post_reqid) == 0) {  /* #5079 (X63): a CANCEL of the POST posts its area */
        post_area(post_live);
        post_release();
    }
    c->resp = found ? NORMAL : NOTFND;
    c->resp2 = 0;
    snprintf(ev, sizeof ev, "CANCEL reqid=%s resp=%d", reqid, c->resp);
    event(ev, NULL, 0);
    return 0;
}
