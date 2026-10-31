/* #5274: ggcics.c's channels / containers family (#4270, #4951, #5005), split out of the stub; ggcics.c includes
 * it where it always sat, so the two are one translation unit and nothing here is compiled on its own. */

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
typedef struct { char name[17]; int bit; int ccsid; char *data; int len; int used; long long order; } gg_container; /* order: creation order (#4951); ccsid: a CHAR container's CCSID (#4270, X17), 0 for BIT */
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

/* #4270 (X17): the CCSIDs a CHAR container converts between -- the region's 037, 500 and 1140, and 1208 (UTF-8) for ASCII bytes only -- as CicsTask.convertContainer:
 * a program's byte is read as the region's page (037), and a conversion is the character-to-character map between the pages.
 * 500 permutes seven characters of 037's repertoire (the cent sign, the broken bar, the exclamation mark, the not sign, the
 * circumflex and the two square brackets); 1140 is 037 with the euro for the currency sign, so that character has no image in
 * 037 or 500 and nothing converts to or from it; a 1208 byte or character beyond ASCII (multibyte) is refused. */
#define REGION_CCSID 37
static void ccsid_ok(int ccsid, const char *what) {
    char msg[96];
    if (ccsid != 37 && ccsid != 500 && ccsid != 1140 && ccsid != 1208) {
        snprintf(msg, sizeof msg, "%s(%d): only the CCSIDs 37, 500, 1140 and 1208 are modelled", what, ccsid);
        refuse(msg);
    }
}
static const unsigned char ccsid_500_from[7] = {0xA2, 0x7C, 0x21, 0xAC, 0x5E, 0x5B, 0x5D}; /* in 037 ... */
static const unsigned char ccsid_500_to[7]   = {0x5E, 0x5D, 0x7C, 0x5B, 0xAC, 0xA2, 0x21}; /* ... as 500 reads them */
/* CCSID 1208 (UTF-8) data is ASCII here, one byte a character: the region's page decodes an EBCDIC byte below X'80' as these characters */
static const unsigned char EBCDIC037_LOW[128] = {
    0x00, 0x01, 0x02, 0x03, 0x9C, 0x09, 0x86, 0x7F, 0x97, 0x8D, 0x8E, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x9D, 0x85, 0x08, 0x87, 0x18, 0x19, 0x92, 0x8F, 0x1C, 0x1D, 0x1E, 0x1F,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x0A, 0x17, 0x1B, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x05, 0x06, 0x07,
    0x90, 0x91, 0x16, 0x93, 0x94, 0x95, 0x96, 0x04, 0x98, 0x99, 0x9A, 0x9B, 0x14, 0x15, 0x9E, 0x1A,
    0x20, 0xA0, 0xE2, 0xE4, 0xE0, 0xE1, 0xE3, 0xE5, 0xE7, 0xF1, 0xA2, 0x2E, 0x3C, 0x28, 0x2B, 0x7C,
    0x26, 0xE9, 0xEA, 0xEB, 0xE8, 0xED, 0xEE, 0xEF, 0xEC, 0xDF, 0x21, 0x24, 0x2A, 0x29, 0x3B, 0xAC,
    0x2D, 0x2F, 0xC2, 0xC4, 0xC0, 0xC1, 0xC3, 0xC5, 0xC7, 0xD1, 0xA6, 0x2C, 0x25, 0x5F, 0x3E, 0x3F,
    0xF8, 0xC9, 0xCA, 0xCB, 0xC8, 0xCD, 0xCE, 0xCF, 0xCC, 0x60, 0x3A, 0x23, 0x40, 0x27, 0x3D, 0x22,
};
static unsigned char ccsid_perm500(unsigned char b, int to500) {
    for (int j = 0; j < 7; j++) {
        if (to500 && b == ccsid_500_from[j]) return ccsid_500_to[j];
        if (!to500 && b == ccsid_500_to[j]) return ccsid_500_from[j];
    }
    return b;
}
static void ccsid_convert(char *d, int len, int from, int to, const char *what) {
    if (from == to) return;
    ccsid_ok(from, what);
    ccsid_ok(to, what);
    for (int i = 0; i < len; i++) {
        unsigned char b = (unsigned char)d[i], ch = b;
        if (from == 1208) {
            int real = -1;  /* the byte the region's page encodes b as, when it is below X'80' */
            for (int j = 0; j < 128; j++) if (EBCDIC037_LOW[j] == b) { real = j; break; }
            if (real < 0) refuse("code-page conversion of a CCSID 1208 byte beyond ASCII (a multibyte character)");
            ch = (unsigned char)real;
        } else if (from == 500) {
            ch = ccsid_perm500(b, 0);  /* the character CCSID 500 reads at the byte the region's page reads as b */
        }
        if (to == 1208) {
            if (ch >= 0x80) refuse("code-page conversion to CCSID 1208 of a character beyond ASCII (a multibyte sequence)");
            d[i] = (char)EBCDIC037_LOW[ch];
            continue;
        }
        if (ch == 0xA4 && (from == 1140 || to == 1140)) refuse("code-page conversion of a character the target CCSID lacks");
        d[i] = (char)(to == 500 ? ccsid_perm500(ch, 1) : ch);
    }
}

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
    int bit, chr, ch, from_ccsid;
    trim(c->flags, 40, flags);
    bit = strstr(flags, "BIT") != NULL;
    chr = strstr(flags, "CHAR") != NULL;
    from_ccsid = strstr(flags, "FROMCCSID") != NULL ? c->num : -1; /* GG-NUM: the CCSID of FROM's data (#4270, X17) */
    c->resp = NORMAL;
    c->resp2 = 0;
    int fresp, fresp2; /* #6882 (X17): a planned condition: the PUT is not performed */
    if (injected("PUT-CONTAINER", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
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
    if (from_ccsid >= 0 && (bit || chr) && !strstr(flags, "CHANNEL") && !levels[lvl].cur) refuse("PUT CONTAINER FROMCCSID with a data type and no channel: INVREQ RESP2 1 and RESP2 2 both fit, and IBM ranks neither");
    ch = command_channel(c, 1, from_ccsid >= 0 ? 2 : bit || chr ? 1 : 4);
    if (!ch) return 0;
    if (from_ccsid >= 0) {
        ccsid_ok(from_ccsid, "PUT CONTAINER FROMCCSID");
        if (c->len < 0) refuse("PUT CONTAINER FROMCCSID with a negative FLENGTH: which condition IBM raises first is not documented");
        if (bit) { c->resp = INVREQ; c->resp2 = 34; return 0; }
    }
    if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (k) {
        char key[96];
        container_key(key, sizeof key, chans[ch - 1].name, name);
        if (blk_held(key)) refuse("PUT CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the pointer then sees");
    }
    /* the other data type for an existing container: IBM says both that DATATYPE "applies only to new
     * containers" and that changing it is INVREQ RESP2 33 -- not settled, refused */
    if (k && (bit || chr) && k->bit != bit) refuse("PUT CONTAINER changing an existing container's data type");
    if (k && k->bit && from_ccsid >= 0) refuse("PUT CONTAINER FROMCCSID onto an existing BIT container: IBM does not say");
    chr = chr || from_ccsid >= 0;
    int prepend = strstr(flags, "PREPEND") != NULL; /* #5005 (X17): BIT containers only */
    if (prepend && (chr || (k && !k->bit))) refuse("PUT CONTAINER PREPEND on a CHAR container: IBM counts a CHAR container's data in its code page");
    int fresh = k == NULL;
    if (!k) {
        k = container_named(&chans[ch - 1], name, 1);
        k->bit = !chr;
        k->ccsid = chr ? (from_ccsid >= 0 ? from_ccsid : REGION_CCSID) : 0;
    }
    char *put = malloc((size_t)c->len + 1);
    if (!put) refuse("out of memory");
    memcpy(put, from, (size_t)c->len);
    if (!fresh && !k->bit) ccsid_convert(put, c->len, from_ccsid >= 0 ? from_ccsid : REGION_CCSID, k->ccsid, "PUT CONTAINER");
    if (prepend && !fresh) {
        char *joined = malloc((size_t)(k->len + c->len) + 1);
        if (!joined) refuse("out of memory");
        memcpy(joined, put, (size_t)c->len);
        if (k->len > 0) memcpy(joined + c->len, k->data, (size_t)k->len);
        free(k->data);
        free(put);
        k->data = joined;
        k->len += c->len;
    } else if (strstr(flags, "APPEND")) {
        char *joined = realloc(k->data, (size_t)(k->len + c->len) + 1);
        if (!joined) refuse("out of memory");
        memcpy(joined + k->len, put, (size_t)c->len);
        k->data = joined;
        k->len += c->len;
        free(put);
    } else {
        free(k->data);
        k->data = put;
        k->len = c->len;
    }
    return 0;
}

/* GET CONTAINER(GG-QNAME) [CHANNEL] INTO FLENGTH [BYTEOFFSET: GG-NUM] | NODATA (GG-FLAGS); GG-LEN in: the most INTO
 * takes; out: the container's length (NORMAL, LENGERR; else left as it came). CHANNELERR RESP2 2,
 * INVREQ RESP2 4, CONTAINERERR RESP2 10; longer data truncated, LENGERR RESP2 11. */
int GGCGETC(gg_cics *c, char *into) {
    char flags[41], name[17];
    int ch;
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    int fresp, fresp2; /* #6882 (X17): a planned condition: nothing is read */
    if (injected("GET-CONTAINER", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
    cics_name(c->qname, name, "container");
    int into_ccsid = strstr(flags, "INTOCCSID") != NULL ? c->num : -1; /* GG-NUM in: INTOCCSID / INTOCODEPAGE (#4270, X17) */
    ch = command_channel(c, 0, into_ccsid >= 0 ? 2 : 4);
    if (!ch) return 0;
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (!k) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    if (k->bit && into_ccsid >= 0) {
        /* IBM: CCSIDERR RESP2 3, "the data was returned without any code page conversion"; FLENGTH is not stated */
        if (!strstr(flags, "NODATA")) {
            if (c->len < 0) refuse("GET CONTAINER FLENGTH below zero");
            if (k->len > c->len) refuse("GET CONTAINER INTOCCSID on a BIT container longer than INTO: whether LENGERR or CCSIDERR wins is not documented");
            memcpy(into, k->data ? k->data : "", (size_t)k->len);
        }
        c->num = 0;
        c->resp = CCSIDERR; c->resp2 = 3;
        return 0;
    }
    if (strstr(flags, "BYTEOFFSET")) {
        /* #5005 (X17), as CicsTask.getContainerAt: from the offset (below zero: zero); at or past the end LENGERR RESP2 12 with
         * FLENGTH and INTO left alone (ASSUMED); FLENGTH set to the length returned */
        if (!k->bit) refuse("GET CONTAINER BYTEOFFSET on a CHAR container: IBM counts the offset in the requested code page");
        if (c->len < 0) refuse("GET CONTAINER FLENGTH below zero");
        int at = c->num < 0 ? 0 : c->num, left = k->len - at;
        if (at >= k->len) { c->resp = LENGERR; c->resp2 = 12; return 0; }
        if (left > c->len) refuse("GET CONTAINER BYTEOFFSET with an FLENGTH below the data left: whether FLENGTH then holds the length returned or the container's is not documented");
        memcpy(into, k->data + at, (size_t)left);
        c->len = left;
        return 0;
    }
    char *conv = malloc((size_t)k->len + 1);
    if (!conv) refuse("out of memory");
    memcpy(conv, k->data ? k->data : "", (size_t)k->len);
    if (!k->bit && !strstr(flags, "NOCONVERT")) ccsid_convert(conv, k->len, k->ccsid, into_ccsid >= 0 ? into_ccsid : REGION_CCSID, "GET CONTAINER");
    c->num = k->bit ? 0 : k->ccsid; /* GG-NUM out: the container's CCSID (CCSID(area)) */
    if (!strstr(flags, "NODATA")) {
        if (c->len < 0) refuse("GET CONTAINER FLENGTH below zero");
        int n = k->len < c->len ? k->len : c->len;
        memcpy(into, conv, (size_t)n);
        if (k->len > c->len) { c->resp = LENGERR; c->resp2 = 11; }
    }
    free(conv);
    c->len = k->len;
    return 0;
}

/* IBM's MOVE CONTAINER (INVREQ RESP2 30 / 31, CHANNELERR 3), DELETE CHANNEL (CHANNELERR 3) and DELETE CONTAINER (INVREQ 30, CHANNELERR 3) pages name CICS-defined
 * read-only containers and channels and list none: a name beginning DFH may be one, so the command is refused by name (X42 / X44). */
static int cics_defined_name(const char *n) {
    while (*n == ' ') n++;
    return toupper((unsigned char)n[0]) == 'D' && toupper((unsigned char)n[1]) == 'F' && toupper((unsigned char)n[2]) == 'H';
}

/* DELETE CONTAINER(GG-QNAME) [CHANNEL]: CHANNELERR RESP2 2, INVREQ RESP2 4, CONTAINERERR RESP2 10. */
int GGCDELC(gg_cics *c) {
    char name[17];
    int ch;
    c->resp = NORMAL;
    c->resp2 = 0;
    cics_name(c->qname, name, "container");
    {
        char flags[41], cn[17] = "";
        trim(c->flags, 40, flags);
        if (strstr(flags, "CHANNEL")) cics_name(c->chan, cn, "channel");
        if (cics_defined_name(name) || cics_defined_name(cn))
            refuse("DELETE CONTAINER naming a CICS-defined (DFH...) container or channel: it may be read-only, and IBM lists none (INVREQ RESP2 30, CHANNELERR RESP2 3)");
    }
    ch = command_channel(c, 0, 4);
    if (!ch) return 0;
    gg_container *k = container_named(&chans[ch - 1], name, 0);
    if (!k) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    {
        char key[96];
        container_key(key, sizeof key, chans[ch - 1].name, name);
        blk_invalidate(key);  /* IBM: GET CONTAINER SET's data area is kept until "deleted by a DELETE CONTAINER" */
    }
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
    if (cics_defined_name(name)) refuse("DELETE CHANNEL naming a CICS-defined (DFH...) container or channel: it may be read-only, and IBM lists none (INVREQ RESP2 30 / 31, CHANNELERR RESP2 3)");
    int ch = channel_named(name, 0);
    if (!ch) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    if (ch == levels[lvl].cur) refuse("DELETE CHANNEL of the current channel");
    {
        char key[96];
        container_key(key, sizeof key, chans[ch - 1].name, "");
        blk_invalidate_prefix(key);  /* IBM: until "deleted by a DELETE CHANNEL command" */
    }
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
    if (cics_defined_name(name) || cics_defined_name(target) || cics_defined_name(cn) || cics_defined_name(tn))
        refuse("MOVE CONTAINER naming a CICS-defined (DFH...) container or channel: it may be read-only, and IBM lists none (INVREQ RESP2 30 / 31, CHANNELERR RESP2 3)");
    if ((!has_from || !has_to) && !levels[lvl].cur) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    if (!from) { c->resp = CHANNELERR; c->resp2 = 2; return 0; }
    gg_container *src = container_named(&chans[from - 1], name, 0);
    if (!src) { c->resp = CONTAINERERR; c->resp2 = 10; return 0; }
    gg_container *dst = to ? container_named(&chans[to - 1], target, 0) : NULL;
    if (to == from && strcmp(name, target) == 0) refuse("MOVE CONTAINER onto itself");
    if (dst && dst->bit != src->bit) refuse("MOVE CONTAINER onto a container of the other data type");
    if (dst && dst->ccsid != src->ccsid) refuse("MOVE CONTAINER onto a container of another CCSID");
    if (dst) {
        char key[96];
        container_key(key, sizeof key, chans[to - 1].name, target);
        if (blk_held(key)) refuse("MOVE CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the pointer then sees");
    }
    {
        char key[96];
        container_key(key, sizeof key, chans[from - 1].name, name);
        blk_invalidate(key);  /* IBM: until "moved by a MOVE CONTAINER command" */
    }
    if (!to) to = channel_named(tn, 1);
    if (!dst) {
        dst = container_named(&chans[to - 1], target, 1);
        dst->bit = src->bit;
        dst->ccsid = src->ccsid;
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
    char name[17], word[32], type[16];
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
        if (sscanf(line, "%31s %15s %s", word, type, hex) != 3 || strlen(word) > 16) refuse("channel.cfg: a container line");
        gg_container *k = container_named(&chans[ch - 1], word, 1);
        k->bit = strncmp(type, "CHAR", 4) != 0;
        k->ccsid = k->bit ? 0 : (type[4] == ':' ? atoi(type + 5) : REGION_CCSID); /* CHAR:n, a CCSID other than the region's */
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
        fprintf(f, "%s ", ch->c[i].name);
        if (ch->c[i].bit) fprintf(f, "BIT ");
        else if (ch->c[i].ccsid == REGION_CCSID) fprintf(f, "CHAR ");
        else fprintf(f, "CHAR:%d ", ch->c[i].ccsid);
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

/* RETURN TRANSID(name1) CHANNEL(chan) (#5005, register X17; IBM, EXEC CICS RETURN): the channel (made empty when absent)
 * is "made available to the next program" as its current channel, and the task ends -- its containers saved to
 * $GGCICS_OUT/return_channel.cfg for the runner to hand the next task. Below the highest logical level it fails, INVREQ
 * RESP2 2, and returns to the program (the event then names the level). As CicsTask.returnChannel. */
int GGCRETC(gg_cics *c, char *unused, int len) {
    char transid[9], name[17], ev[192], path[3000];
    (void)unused;
    (void)len;
    trim(c->name1, 8, transid);
    trim(c->chan, 16, name);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (lvl > 0) {
        c->resp = INVREQ;
        c->resp2 = 2;
        snprintf(ev, sizeof ev, "RETURN level=%d transid=%s channel=%s resp=%d resp2=%d", lvl + 1, transid, name,
                 c->resp, c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    int ch = channel_named(name, 1);
    snprintf(path, sizeof path, "%s/return_channel.cfg", dir_out());
    save_channel(&chans[ch - 1], path);
    levels[lvl].state = DONE;
    ended = 1;
    snprintf(ev, sizeof ev, "RETURN level=1 transid=%s len=0 channel=%s", transid, name);
    event(ev, NULL, 0);
    return 0;
}
