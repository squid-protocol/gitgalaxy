/* #4270, #4213, #5274: the file-control family of the stub -- READ, the browse (STARTBR / READNEXT / READPREV / ENDBR,
 * keyed and RBA), DELETE and UNLOCK -- split out of ggcics.c, which includes it where the block sat. */
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
 * KEYLENGTH not shorter than the key or below zero is INVREQ (RESP2 25 / 42, GGCREAD); zero is undocumented and stops the run. */
static long long read_search(gg_cics *c, const char *path, int reclen, int keyoff, int klen, const char *ridfld,
                             int keylen, char **all) {
    int gteq = strstr(c->flags, "GTEQ") != NULL, generic = strstr(c->flags, "GENERIC") != NULL;
    if (generic && keylen == 0) refuse("READ GENERIC KEYLENGTH not above zero (zero is undocumented)");
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

/* #6262: set while a READ / READNEXT / READPREV SET(ptr) wrapper runs; its event carries `set=1` and no `len=` (SPEC 6.2). */
static int set_form;

/* SPEC 6.2 READ event: `upd=1` for READ UPDATE, `len=` the LENGTH after the command, `resp2=` where the command is not
 * NORMAL, and the bytes that went INTO (NORMAL only: a LENGERR read asserts its RESP and length, not its data). */
static void read_event(const gg_cics *c, const char *want, const char *ridfld, int keylen, const char *into, int intolen) {
    char ev[400], key[256];
    int shown = keylen < 0 ? 0 : keylen < 200 ? keylen : 200;  /* #5092: a negative KEYLENGTH is INVREQ 42 */
    memcpy(key, ridfld, (size_t)shown);
    key[shown] = '\0';
    int n = snprintf(ev, sizeof ev, "READ file=%s key=%s resp=%d", want, key, c->resp);
    if (strstr(c->flags, "UPDATE") && n < (int)sizeof ev) n += snprintf(ev + n, sizeof ev - (size_t)n, " upd=1");
    if (set_form && n < (int)sizeof ev) n += snprintf(ev + n, sizeof ev - (size_t)n, " set=1");
    else if (c->resp == NORMAL || c->resp == LENGERR) n += snprintf(ev + n, sizeof ev - (size_t)n, " len=%d", c->len);
    if (c->resp != NORMAL && c->resp2 && n < (int)sizeof ev) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    int moved = c->resp == NORMAL ? (c->len < intolen ? c->len : intolen) : 0;
    event(ev, into, moved);
}

int GGCREAD(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    char want[9], line[4096], name[64], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp = FILENOTFOUND;
    c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
    if (strstr(c->flags, "UPDATE") && !strstr(c->flags, "TOKEN") && has_hold(want)) {
        c->resp = INVREQ;  /* #5092: a second READ UPDATE without a token, nothing released between */
        c->resp2 = 28;
        read_event(c, want, ridfld, keylen, into, 0);
        return 0;
    }
    if (injected("READ", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        read_event(c, want, ridfld, keylen, into, 0);
        return 0;
    }
    keyed_on_esds("READ", want);
    snprintf(line, sizeof line, "%s/files.cfg", dir_in());
    FILE *cfg = fopen(line, "r");
    if (cfg) {
        while (fgets(line, sizeof line, cfg)) {
            if (sscanf(line, "%63s %2999s %d %d %d", name, path, &reclen, &keyoff, &klen) != 5) continue;
            if (strcmp(name, want) != 0) continue;
            /* #5092 (X52), IBM, EXEC CICS READ: INVREQ RESP2 25 (GENERIC KEYLENGTH "greater than or equal to the length of a
             * full key"), 42 ("less than zero"), 26 (a KEYLENGTH without GENERIC that is not the key's length); GENERIC
             * always carries KEYLENGTH. Nothing is read or held. */
            int generic = strstr(c->flags, "GENERIC") != NULL, given = generic || strstr(c->flags, "KEYLENGTH") != NULL;
            int bad = !given ? 0 : generic ? (keylen < 0 ? 42 : keylen >= klen ? 25 : 0) : keylen != klen ? 26 : 0;
            if (bad) {
                c->resp = INVREQ;
                c->resp2 = bad;
                break;
            }
            c->resp = NOTFND;
            c->resp2 = 80;  /* IBM: NOTFND RESP2 80, "an attempt to retrieve a record based on the search argument ... is unsuccessful" */
            int search = strstr(c->flags, "GTEQ") || strstr(c->flags, "GENERIC");
            char *found = NULL;
            long long at = search ? read_search(c, path, reclen, keyoff, klen, ridfld, keylen, &found) : -1;
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
    dupkey_apply(c);
    read_event(c, want, ridfld, keylen, into, intolen);
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

/* #6262, SPEC 6.2 STARTBR / READNEXT / READPREV event: `rid=` the RIDFLD on entry as hex (a key may hold spaces or X'FF'),
 * STARTBR's `mode=` (GTEQ or EQUAL), `resp2=` where the command is not NORMAL, and for a browse read `len=` (the
 * record's) with the bytes that went INTO when it delivered the record (NORMAL or DUPKEY). `reclen` < 0: no record read. */
static void browse_event(const char *verb, const char *file, const char *rid, int klen, const gg_cics *c, int reclen,
                         const char *into, int intolen) {
    char ev[600], hex[2 * 100 + 1];
    int shown = klen < 0 ? 0 : klen < 100 ? klen : 100;
    for (int i = 0; i < shown; i++) snprintf(hex + 2 * i, 3, "%02X", (unsigned char)rid[i]);
    hex[2 * shown] = '\0';
    int n = snprintf(ev, sizeof ev, "%s file=%s rid=%s resp=%d", verb, file, hex, c->resp);
    if (strcmp(verb, "STARTBR") == 0)
        n += snprintf(ev + n, sizeof ev - (size_t)n, " mode=%s", strstr(c->flags, "EQUAL") ? "EQUAL" : "GTEQ");
    if (set_form) n += snprintf(ev + n, sizeof ev - (size_t)n, " set=1");
    else if (reclen >= 0 && (c->resp == NORMAL || c->resp == DUPKEY || c->resp == LENGERR))
        n += snprintf(ev + n, sizeof ev - (size_t)n, " len=%d", reclen);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    int ok = reclen >= 0 && (c->resp == NORMAL || c->resp == DUPKEY);
    event(ev, into, ok ? (reclen < intolen ? reclen : intolen) : 0);
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
        browse_event("STARTBR", want, ridfld, keylen, c, -1, NULL, 0);
        return 0;
    }
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
        browse_event("STARTBR", want, ridfld, keylen, c, -1, NULL, 0);
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
    browse_event("STARTBR", want, ridfld, keylen, c, -1, NULL, 0);
    return 0;
}

/* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
static int browse_read(gg_cics *c, int dir, char *ridfld, int keylen, char *into, int intolen) {
    const char *verb = dir > 0 ? "READNEXT" : "READPREV";
    char want[9], path[3000], key[256], entry[256];
    int reclen, keyoff, klen, fresp, fresp2, got = -1;
    memcpy(entry, ridfld, keylen < (int)sizeof entry ? (size_t)(keylen > 0 ? keylen : 0) : sizeof entry);  /* #6262: RIDFLD on entry */
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (injected(verb, want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        browse_event(verb, want, ridfld, keylen, c, -1, NULL, 0);
        return 0;
    }
    int s = browse_slot(want, 0);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
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
            got = reclen;
            if (reclen > intolen) { c->resp = LENGERR; c->resp2 = 11; }
        }
        free(all);
    }
    dupkey_apply(c);
    browse_event(verb, want, entry, keylen < (int)sizeof entry ? keylen : (int)sizeof entry, c, got, into, intolen);
    return 0;
}

int GGCRDNX(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    return browse_read(c, 1, ridfld, keylen, into, intolen);
}

int GGCRDPV(gg_cics *c, char *ridfld, int keylen, char *into, int intolen) {
    return browse_read(c, -1, ridfld, keylen, into, intolen);
}

/* ENDBR FILE(name1). #6262: a file the region does not define is FILENOTFOUND RESP2 1 (X75), as for the other browse
 * commands, not the INVREQ 35 of a defined file with no browse. */
int GGCENBR(gg_cics *c) {
    char want[9], ev[100], path[3000];
    int fresp, fresp2, n, reclen, keyoff, klen;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int s = browse_slot(want, 0);
    if (injected("ENDBR", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    } else if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;
    } else if (s < 0 || !br[s].active) {
        c->resp = INVREQ;
        c->resp2 = 35;
    } else {
        br[s].active = 0;
        c->resp = NORMAL;
        file_set_end("BROWSE", want);  /* IBM: "no longer valid after an ENDBR" */
    }
    n = snprintf(ev, sizeof ev, "ENDBR file=%s resp=%d", want, c->resp);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a READ UPDATE
 * holds -- INVREQ when none is held; NOTFND when the key is not there. #4771: GG-FLAGS 'GENERIC', every record whose key
 * starts with RIDFLD's first `keylen` bytes (NOTFND RESP2 80 when none). #5092 (X22), IBM, EXEC CICS DELETE, INVREQ RESP2:
 * 21 a DELETE of an ESDS, 22 a generic one of a non-KSDS (an ESDS here), 25 a GENERIC KEYLENGTH "greater than or equal to the
 * length of a full key", 42 one below zero, 26 a KEYLENGTH without GENERIC (GG-FLAGS 'KEYLENGTH') that is not the key's
 * length. Nothing is deleted or released. A GENERIC KEYLENGTH of zero is undocumented and stops the run. */
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
        file_event("DELETE", want, ridfld, by_hold ? -1 : keylen, c, NULL, 0);
        return 0;
    }
    int generic = strstr(c->flags, "GENERIC") != NULL;
    if (is_esds(want)) {  /* #5092: IBM INVREQ 21 (ESDS), 22 (generic delete of a non-KSDS); the key is not logged: an ESDS has none */
        c->resp = INVREQ;
        c->resp2 = generic ? 22 : 21;
        file_event("DELETE", want, ridfld, -1, c, NULL, 0);
        return 0;
    }
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
        file_event("DELETE", want, ridfld, by_hold ? -1 : keylen, c, NULL, 0);
        return 0;
    }
    int bad = 0;
    if (generic) bad = keylen < 0 ? 42 : keylen >= klen ? 25 : 0;
    else if (!by_hold && strstr(c->flags, "KEYLENGTH") && keylen != klen) bad = 26;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        file_event("DELETE", want, ridfld, keylen < 0 ? 0 : keylen < klen ? keylen : klen, c, NULL, 0);  /* KEYLENGTH may exceed RIDFLD: log at most the key's length */
        return 0;
    }
    if (generic && keylen == 0) refuse("DELETE GENERIC KEYLENGTH not above zero (zero is undocumented)");
    char key[256];
    memset(key, 0, sizeof key);
    int s = -1;
    if (by_tok) {
        int ti = token_find(c->num, want);
        if (ti < 0) {
            c->resp = INVREQ;
            c->resp2 = 47;
            file_event("DELETE", want, ridfld, -1, c, NULL, 0);
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
        if (c->resp == NORMAL) file_set_end("READ", want);
        file_event("DELETE", want, key, keylen, c, NULL, 0);
        return 0;
    }
    long long at = (by_hold && s < 0) ? -1 : pick(all, n, reclen, keyoff, keylen < klen && !by_hold ? keylen : klen, key, 0);
    if (by_hold && s < 0) {
        c->resp = INVREQ;
        c->resp2 = 31;  /* #5092: no RIDFLD and no READ UPDATE without a token before it */
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
    if (c->resp == NORMAL) file_set_end("READ", want);
    file_event("DELETE", want, key, by_hold ? -1 : keylen < klen ? keylen : klen, c, NULL, 0);
    return 0;
}

/* SPEC 6.2 UNLOCK event: the file, RESP, and RESP2 where the command is not NORMAL. */
static void unlock_event(const gg_cics *c, const char *want) {
    char ev[200];
    int n = snprintf(ev, sizeof ev, "UNLOCK file=%s resp=%d", want, c->resp);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    event(ev, NULL, 0);
}

/* UNLOCK FILE(name1) TOKEN(GG-NUM) (#5078, X52): releases the record a READ UPDATE TOKEN holds; INVREQ RESP2 47 for a
 * token matching none in use. #5079: without TOKEN (GG-FLAGS blank) it releases the file's tokenless hold; none held: no action, NORMAL (IBM). */
int GGCUNLK(gg_cics *c) {
    char want[9], path[3000];
    int reclen, keyoff, klen;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
        unlock_event(c, want);
        return 0;
    }
    if (!strstr(c->flags, "TOKEN")) {
        release(want);
        c->resp = NORMAL;
        file_set_end("READ", want);  /* IBM: until a corresponding UNLOCK completes */
        unlock_event(c, want);
        return 0;
    }
    int ti = token_find(c->num, want);
    if (ti < 0) {
        c->resp = INVREQ;
        c->resp2 = 47;
    } else {
        tokens[ti].id = 0;
        c->resp = NORMAL;
        file_set_end("READ", want);
    }
    unlock_event(c, want);
    return 0;
}
