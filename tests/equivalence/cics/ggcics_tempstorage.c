/* #5274: the temporary storage family (READQ TS, WRITEQ TS, DELETEQ TS) -- split out of ggcics.c, which includes it
 * where the block sat. */
#ifndef GGCICS_TS_DELETEQ  /* the first part: READQ / WRITEQ TS */
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
#else  /* ggcics.c includes the file a second time, where DELETEQ TS sat */

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
#endif
