/* #5274: the SET(pointer) forms of RECEIVE, CONVERSE, RETRIEVE and the file and queue reads -- split out of ggcics.c, which includes it here. */
/* RECEIVE SET(ptr) MAXLENGTH LENGTH (GG-LEN the most in, the length out): the block holds the bytes delivered; valid until the
 * next RECEIVE ("until the next receive command or the end of task"). */
int GGCRECP(gg_cics *c, void **slot) {
    memset(set_buf, 0, sizeof set_buf);
    int copied = terminal_receive(c, set_buf);
    if (copied >= 0) *slot = blk_set_new("RECEIVE", set_buf, (size_t)copied, 0);
    return 0;
}

/* CONVERSE FROM FROMLENGTH SET(ptr) TOLENGTH (#5079, X63 / X58): GGCCONV's write, then RECEIVE SET's read -- the reply as a new block the
 * pointer addresses (key "RECEIVE": it ends at the next RECEIVE SET or CONVERSE SET, ASSUMED). GG-LEN the most in, the length out; where
 * nothing was delivered (a negative FROMLENGTH, a second terminal read) the pointer is as it was. */
int GGCCONS(gg_cics *c, char *from, int fromlen, void **slot) {
    if (converse_write(c, from, fromlen) == 0) {
        memset(set_buf, 0, sizeof set_buf);
        int copied = terminal_receive(c, set_buf);
        if (copied >= 0) *slot = blk_set_new("RECEIVE", set_buf, (size_t)copied, 0);
    }
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
