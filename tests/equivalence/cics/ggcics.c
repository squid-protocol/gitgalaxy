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
 *   terminal.read         present when an earlier program of the task already read it
 * Temporary storage (#4002) lives in $GGCICS_TS (else $GGCICS_DIR/ts), shared by every
 * task of a scenario: one directory per queue, named by the queue name's hex, holding
 * its items as 000001.bin, 000002.bin, ... and `next`, the READQ NEXT position.
 *   files.cfg             one CICS file per line: NAME PATH RECLEN KEYOFF KEYLEN --
 *                         generated from the engine's facts (CSD FILE -> DSNAME ->
 *                         IDCAMS KEYS, a PATH through its AIX)
 * Outputs go to $GGCICS_OUT: events.txt, one line per command in order, and
 * NNN.bin, the bytes a SEND / RETURN / XCTL carried.
 *
 * Every entry point takes the GG-CICS block first (DFHEIBLK.cpy): the stub sets
 * GG-RESP / GG-RESP2 (the DFHRESP codes), the translator copied the names and
 * options into GG-NAME1 / GG-NAME2 / GG-FLAGS.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

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
} gg_cics;

enum { NORMAL = 0, NOTFND = 13, LENGERR = 22, FILENOTFOUND = 12, MAPFAIL = 36, ITEMERR = 26, QIDERR = 44 };

static int seq = 0;
static int ended = 0; /* a RETURN, XCTL or abend ended the task */

static void trim(const char *src, int len, char *dst) {
    while (len > 0 && (src[len - 1] == ' ' || src[len - 1] == '\0')) len--;
    memcpy(dst, src, len);
    dst[len] = '\0';
}

static const char *dir_in(void) { const char *d = getenv("GGCICS_DIR"); return d ? d : "."; }
static const char *dir_out(void) { const char *d = getenv("GGCICS_OUT"); return d ? d : "."; }

/* One line of events.txt; with `data`, its bytes as NNN.bin. */
static void event(const char *line, const char *data, int len) {
    char path[4096];
    seq++;
    snprintf(path, sizeof path, "%s/events.txt", dir_out());
    FILE *f = fopen(path, "a");
    if (f) {
        fprintf(f, "%03d %s\n", seq, line);
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

/* READ FILE(name1) RIDFLD INTO: the first record whose key equals RIDFLD. */
int GGCREAD(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    char want[9], line[4096], name[64], path[3000], ev[320];
    int reclen, keyoff, klen;
    trim(c->name1, 8, want);
    c->resp = FILENOTFOUND;
    c->resp2 = 0;
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
                    memcpy(into, rec, (size_t)(reclen < intolen ? reclen : intolen));
                    c->resp = reclen > intolen ? LENGERR : NORMAL;
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
 * takes; on return it is the data's length. Longer data is truncated to c->len and raises
 * LENGERR, with c->len set to the full length (IBM, RECEIVE (3270 logical): "the data is
 * truncated ... the length data area is set to the original length of the data"). The
 * input is read once per task: a second RECEIVE would wait for the operator, which a
 * scenario step cannot express, so it is recorded as RECEIVE-WAIT for the driver to refuse. */
static int terminal_read = 0;

int GGCRECT(gg_cics *c, char *into) {
    char path[4096], ev[96], buf[32768];
    int n = 0, max = c->len;
    snprintf(path, sizeof path, "%s/terminal.read", dir_in());
    FILE *f = fopen(path, "rb");
    if (f) { fclose(f); terminal_read = 1; }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (terminal_read) {
        c->len = 0;
        event("RECEIVE-WAIT", NULL, 0);
        return 0;
    }
    terminal_read = 1;
    snprintf(path, sizeof path, "%s/terminal.in", dir_in());
    f = fopen(path, "rb");
    if (f) {
        n = (int)fread(buf, 1, sizeof buf, f);
        fclose(f);
    }
    int copied = n < max ? n : (max > 0 ? max : 0);
    memcpy(into, buf, (size_t)copied);
    if (n > max) c->resp = LENGERR;
    c->len = n;
    snprintf(ev, sizeof ev, "RECEIVE resp=%d len=%d copied=%d", c->resp, n, copied);
    event(ev, into, copied);
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
    int count = ts_count(dir), item = 0;
    c->resp2 = 0;
    if (len < 1 || len > 32763) {
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
            mkdir(root, 0777);
            mkdir(dir, 0777);
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
int GGCSMAP(gg_cics *c, char *from, int len) {
    char map[9], mapset[9], flags[41], ev[160];
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-MAP map=%s mapset=%s len=%d opts=%s", map, mapset, len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
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

int GGCRETN(gg_cics *c, char *commarea, int len) {
    char transid[9], ev[96];
    trim(c->name1, 8, transid);
    snprintf(ev, sizeof ev, "RETURN transid=%s len=%d", transid, len);
    ended = 1;
    event(ev, commarea, len);
    return 0;
}

int GGCXCTL(gg_cics *c, char *commarea, int len) {
    char program[9], ev[96];
    trim(c->name1, 8, program);
    snprintf(ev, sizeof ev, "XCTL program=%s len=%d", program, len);
    ended = 1;
    event(ev, commarea, len);
    return 0;
}

int GGCABND(gg_cics *c) {
    char code[9], ev[64];
    trim(c->name1, 8, code);
    snprintf(ev, sizeof ev, "ABEND abcode=%s", code);
    ended = 1;
    event(ev, NULL, 0);
    return 0;
}

/* HANDLE ABEND LABEL / CANCEL / PROGRAM: recorded; an abend path is not driven. */
int GGCHABN(gg_cics *c) {
    char flags[41], ev[96];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "HANDLE-ABEND %s", flags);
    event(ev, NULL, 0);
    return 0;
}

/* A command raised a condition the program neither tests (RESP) nor ignores (NOHANDLE):
 * CICS abends the task (AEIx). The translator ends the program after this. */
int GGCUNHD(gg_cics *c) {
    char ev[64];
    snprintf(ev, sizeof ev, "ABEND unhandled-resp=%d", c->resp);
    ended = 1;
    event(ev, NULL, 0);
    return 0;
}

/* The program returned to the driver without a RETURN / XCTL / ABEND. */
int GGCEND(gg_cics *c) {
    (void)c;
    if (!ended) event("END", NULL, 0);
    return 0;
}
