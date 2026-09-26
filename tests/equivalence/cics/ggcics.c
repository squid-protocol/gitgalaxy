/*
 * #3754: the stub CICS runtime of the equivalence harness. A translated program
 * (tests/tools/equivalence_cics.py) CALLs these in place of each EXEC CICS
 * command; the harness driver CALLs GGCLOAD / GGCEND around the task.
 *
 * Inputs come from $GGCICS_DIR:
 *   commarea.in           the COMMAREA the task starts with (its length is EIBCALEN)
 *   receive_<MAP>.bin     what RECEIVE MAP(<MAP>) returns; absent means MAPFAIL
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

typedef struct {
    int resp;
    int resp2;
    char name1[8];
    char name2[8];
    char flags[40];
} gg_cics;

enum { NORMAL = 0, NOTFND = 13, LENGERR = 22, FILENOTFOUND = 12, MAPFAIL = 36 };

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
