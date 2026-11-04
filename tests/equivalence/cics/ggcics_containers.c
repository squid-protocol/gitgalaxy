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
static int cics_defined_name(const char *n);
static int harness_channel; /* set while load_channel makes a channel the harness hands the task (DFHEP.EVENT): never refused */
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
    /* #5005 (X42): a channel LINK / XCTL / RETURN CHANNEL would make is never DFH... (DFHTRANSACTION, the transaction channel,
     * is not modelled; PUT and MOVE refuse such a name before they get here); one already in scope returned above */
    if (!harness_channel && cics_defined_name(name)) refuse("LINK / XCTL / RETURN CHANNEL naming a DFH... channel not in scope: the transaction channel (DFHTRANSACTION) and any other CICS-defined channel are not modelled");
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

/* #4270 (X17), #7589: the CCSIDs a CHAR container converts between -- the region's 037, 500, 1140 and 1208 (UTF-8) -- as CicsTask.convertContainer.
 * A container holds, per byte, the program's storage view of IBM's bytes: decode037(raw), so a raw EBCDIC 037 'A' (X'C1') sits as 0x41
 * (#4528). A conversion is raw -> strict decode by the source page -> code points -> strict encode by the target page -> raw, and the
 * length may change (1208 is multibyte). 500 permutes seven characters of 037's repertoire (the cent sign, the broken bar, the
 * exclamation mark, the not sign, the circumflex and the two square brackets); 1140 is 037 with the euro for the currency sign, so
 * the euro has no image in 037 or 500 and the currency sign none in 1140. Malformed UTF-8, or a character the target page lacks, is
 * refused: IBM does not say (IBM "Conversion CCSIDs for CICS TS", Table 38; register X17). */
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
/* the character (Latin-1 code point) the region's page 037 decodes each EBCDIC byte as */
static const unsigned char EBCDIC037[256] = {
    0x00, 0x01, 0x02, 0x03, 0x9C, 0x09, 0x86, 0x7F, 0x97, 0x8D, 0x8E, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x9D, 0x85, 0x08, 0x87, 0x18, 0x19, 0x92, 0x8F, 0x1C, 0x1D, 0x1E, 0x1F,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x0A, 0x17, 0x1B, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x05, 0x06, 0x07,
    0x90, 0x91, 0x16, 0x93, 0x94, 0x95, 0x96, 0x04, 0x98, 0x99, 0x9A, 0x9B, 0x14, 0x15, 0x9E, 0x1A,
    0x20, 0xA0, 0xE2, 0xE4, 0xE0, 0xE1, 0xE3, 0xE5, 0xE7, 0xF1, 0xA2, 0x2E, 0x3C, 0x28, 0x2B, 0x7C,
    0x26, 0xE9, 0xEA, 0xEB, 0xE8, 0xED, 0xEE, 0xEF, 0xEC, 0xDF, 0x21, 0x24, 0x2A, 0x29, 0x3B, 0xAC,
    0x2D, 0x2F, 0xC2, 0xC4, 0xC0, 0xC1, 0xC3, 0xC5, 0xC7, 0xD1, 0xA6, 0x2C, 0x25, 0x5F, 0x3E, 0x3F,
    0xF8, 0xC9, 0xCA, 0xCB, 0xC8, 0xCD, 0xCE, 0xCF, 0xCC, 0x60, 0x3A, 0x23, 0x40, 0x27, 0x3D, 0x22,
    0xD8, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0xAB, 0xBB, 0xF0, 0xFD, 0xFE, 0xB1,
    0xB0, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F, 0x70, 0x71, 0x72, 0xAA, 0xBA, 0xE6, 0xB8, 0xC6, 0xA4,
    0xB5, 0x7E, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0xA1, 0xBF, 0xD0, 0xDD, 0xDE, 0xAE,
    0x5E, 0xA3, 0xA5, 0xB7, 0xA9, 0xA7, 0xB6, 0xBC, 0xBD, 0xBE, 0x5B, 0x5D, 0xAF, 0xA8, 0xB4, 0xD7,
    0x7B, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0xAD, 0xF4, 0xF6, 0xF2, 0xF3, 0xF5,
    0x7D, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51, 0x52, 0xB9, 0xFB, 0xFC, 0xF9, 0xFA, 0xFF,
    0x5C, 0xF7, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0xB2, 0xD4, 0xD6, 0xD2, 0xD3, 0xD5,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0xB3, 0xDB, 0xDC, 0xD9, 0xDA, 0x9F,
};
static unsigned char ccsid_perm500(unsigned char b, int to500) {
    for (int j = 0; j < 7; j++) {
        if (to500 && b == ccsid_500_from[j]) return ccsid_500_to[j];
        if (!to500 && b == ccsid_500_to[j]) return ccsid_500_from[j];
    }
    return b;
}
static unsigned char enc037(unsigned char ch) { /* the EBCDIC 037 byte of a character */
    for (int j = 0; j < 256; j++) if (EBCDIC037[j] == ch) return (unsigned char)j;
    return 0;
}
/* strict UTF-8 (no overlong form, no surrogate, nothing past U+10FFFF): the bytes the sequence at s takes, 0 when malformed */
static int utf8_take(const unsigned char *s, int n, long *cp) {
    int need = s[0] < 0x80 ? 0 : s[0] >= 0xC2 && s[0] <= 0xDF ? 1 : s[0] >= 0xE0 && s[0] <= 0xEF ? 2 : s[0] >= 0xF0 && s[0] <= 0xF4 ? 3 : -1;
    if (need < 0 || need >= n) return need == 0 ? 1 : 0;
    long v = need == 0 ? s[0] : need == 1 ? s[0] & 0x1F : need == 2 ? s[0] & 0x0F : s[0] & 0x07;
    for (int i = 1; i <= need; i++) {
        if ((s[i] & 0xC0) != 0x80) return 0;
        v = (v << 6) | (s[i] & 0x3F);
    }
    if ((need == 2 && v < 0x800) || (need == 3 && (v < 0x10000 || v > 0x10FFFF)) || (v >= 0xD800 && v <= 0xDFFF)) return 0;
    *cp = v;
    return need + 1;
}
static int utf8_valid(const unsigned char *s, int n) {
    long cp;
    for (int i = 0; i < n;) { int k = utf8_take(s + i, n - i, &cp); if (!k) return 0; i += k; }
    return 1;
}
static int utf8_put(long cp, unsigned char *o) {
    if (cp < 0x80) { o[0] = (unsigned char)cp; return 1; }
    if (cp < 0x800) { o[0] = (unsigned char)(0xC0 | cp >> 6); o[1] = (unsigned char)(0x80 | (cp & 0x3F)); return 2; }
    if (cp < 0x10000) { o[0] = (unsigned char)(0xE0 | cp >> 12); o[1] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F)); o[2] = (unsigned char)(0x80 | (cp & 0x3F)); return 3; }
    o[0] = (unsigned char)(0xF0 | cp >> 18); o[1] = (unsigned char)(0x80 | ((cp >> 12) & 0x3F)); o[2] = (unsigned char)(0x80 | ((cp >> 6) & 0x3F)); o[3] = (unsigned char)(0x80 | (cp & 0x3F));
    return 4;
}
/* PUT FROMCCSID(1208): the program's bytes are read two ways -- A: the characters of UTF-8 text built from character literals (raw =
 * the 037 bytes of the program's characters), B: raw UTF-8 bytes from a hex literal (#4528) -- and the one that is valid UTF-8 is the
 * data; both valid and different is refused as ambiguous, neither as malformed. Returns the container's storage form. */
static char *ccsid_put_1208(const char *d, int len) {
    unsigned char *a = malloc((size_t)len + 1);
    char *out = malloc((size_t)len + 1);
    if (!a || !out) refuse("out of memory");
    for (int i = 0; i < len; i++) a[i] = enc037((unsigned char)d[i]);
    int va = utf8_valid(a, len), vb = utf8_valid((const unsigned char *)d, len);
    if (va && vb && memcmp(a, d, (size_t)len) != 0) refuse("PUT CONTAINER FROMCCSID(1208) data valid as UTF-8 both as the region's characters and as raw bytes: IBM does not say which the program holds (#4528)");
    if (!va && !vb) refuse("PUT CONTAINER FROMCCSID(1208) data that is not valid UTF-8: IBM leaves the conversion undefined");
    for (int i = 0; i < len; i++) out[i] = va ? d[i] : (char)EBCDIC037[(unsigned char)d[i]];
    free(a);
    return out;
}
/* convert len bytes of a container's storage; the result is malloc'd, *outlen its length */
static char *ccsid_convert_len(const char *d, int len, int from, int to, const char *what, int *outlen) {
    char *o = malloc((size_t)len * 4 + 8);
    int n = 0;
    if (!o) refuse("out of memory");
    ccsid_ok(from, what);
    ccsid_ok(to, what);
    if (from == to) { memcpy(o, d, (size_t)len); *outlen = len; return o; }
    unsigned char *raw = malloc((size_t)len + 1);
    if (!raw) refuse("out of memory");
    for (int i = 0; i < len; i++) raw[i] = from == 1208 ? enc037((unsigned char)d[i]) : (unsigned char)d[i];
    for (int i = 0; i < len;) {
        long cp;
        if (from == 1208) {
            int k = utf8_take(raw + i, len - i, &cp);
            if (!k) refuse("code-page conversion of malformed UTF-8 from CCSID 1208: IBM leaves it undefined");
            i += k;
        } else {
            unsigned char b = raw[i++];
            cp = from == 500 ? ccsid_perm500(b, 0) : b;  /* the character the source page reads at the byte the region's page reads as b */
            if (from == 1140 && b == 0xA4) cp = 0x20AC;
        }
        if (to == 1208) {
            unsigned char u[4];
            int k = utf8_put(cp, u);
            for (int j = 0; j < k; j++) o[n++] = (char)EBCDIC037[u[j]];
        } else {
            if (to == 1140 && cp == 0x20AC) cp = 0xA4;
            else if (cp > 0xFF || (to == 1140 && cp == 0xA4)) refuse("code-page conversion of a character the target CCSID lacks");
            o[n++] = (char)(to == 500 ? ccsid_perm500((unsigned char)cp, 1) : (unsigned char)cp);
        }
    }
    free(raw);
    *outlen = n;
    return o;
}
/* the in-place form (GET CONTAINER SET, ggcics_setforms.c): a conversion that changes the length is refused there */
static void ccsid_convert(char *d, int len, int from, int to, const char *what) {
    int n;
    char *o = ccsid_convert_len(d, len, from, to, what, &n);
    if (n != len) refuse("GET CONTAINER SET INTOCCSID of data whose converted length differs (a multibyte 1208 conversion): not modelled");
    memcpy(d, o, (size_t)len);
    free(o);
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
/* PUT CONTAINER (X42): the pipeline containers a burned program writes back (DFHREQUEST, DFH-BODY, DFH-DATA) run as ordinary ones;
 * any other DFH container, and any DFH channel, is refused by name. */
static int dfh_prefix(const char *n) {
    while (*n == ' ') n++;
    return toupper((unsigned char)n[0]) == 'D' && toupper((unsigned char)n[1]) == 'F' && toupper((unsigned char)n[2]) == 'H';
}
static void refuse_cics_defined_put(const char *container, const char *channel) {
    char t[17];
    int i = 0;
    while (*container == ' ') container++;
    for (; container[i] && container[i] != ' ' && i < 16; i++) t[i] = (char)toupper((unsigned char)container[i]);
    t[i] = 0;
    int pipeline = !strcmp(t, "DFHREQUEST") || !strcmp(t, "DFH-BODY") || !strcmp(t, "DFH-DATA");
    if ((!pipeline && dfh_prefix(t)) || (channel && dfh_prefix(channel)))
        refuse("PUT CONTAINER naming a CICS-defined (DFH...) container or channel: it may be read-only, and IBM lists none (INVREQ RESP2 30, CHANNELERR RESP2 3)");
}

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
    refuse_cics_defined_put(c->qname, strstr(flags, "CHANNEL") ? c->chan : NULL);
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
    /* PUT onto a container a GET CONTAINER SET pointer addresses (#7589, CAGCST): defined, the data is replaced. The held area is not
     * on IBM's list of what ends it, so it stays allocated with its old bytes (stale); a read through it is undefined by IBM and is the
     * case author's to avoid. */
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
    char *put;
    int plen = c->len;
    if (from_ccsid == 1208) put = ccsid_put_1208(from, c->len);
    else {
        put = malloc((size_t)c->len + 1);
        if (!put) refuse("out of memory");
        memcpy(put, from, (size_t)c->len);
    }
    if (!fresh && !k->bit) {
        char *conv = ccsid_convert_len(put, c->len, from_ccsid >= 0 ? from_ccsid : REGION_CCSID, k->ccsid, "PUT CONTAINER", &plen);
        free(put);
        put = conv;
    }
    if (prepend && !fresh) {
        char *joined = malloc((size_t)(k->len + plen) + 1);
        if (!joined) refuse("out of memory");
        memcpy(joined, put, (size_t)plen);
        if (k->len > 0) memcpy(joined + plen, k->data, (size_t)k->len);
        free(k->data);
        free(put);
        k->data = joined;
        k->len += plen;
    } else if (strstr(flags, "APPEND")) {
        char *joined = realloc(k->data, (size_t)(k->len + plen) + 1);
        if (!joined) refuse("out of memory");
        memcpy(joined + k->len, put, (size_t)plen);
        k->data = joined;
        k->len += plen;
        free(put);
    } else {
        free(k->data);
        k->data = put;
        k->len = plen;
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
    int clen = k->len; /* the length after conversion: 1208 is multibyte */
    char *conv;
    if (!k->bit && !strstr(flags, "NOCONVERT")) conv = ccsid_convert_len(k->data ? k->data : "", k->len, k->ccsid, into_ccsid >= 0 ? into_ccsid : REGION_CCSID, "GET CONTAINER", &clen);
    else {
        conv = malloc((size_t)k->len + 1);
        if (!conv) refuse("out of memory");
        memcpy(conv, k->data ? k->data : "", (size_t)k->len);
    }
    c->num = k->bit ? 0 : k->ccsid; /* GG-NUM out: the container's CCSID (CCSID(area)) */
    if (!strstr(flags, "NODATA")) {
        if (c->len < 0) refuse("GET CONTAINER FLENGTH below zero");
        int n = clen < c->len ? clen : c->len;
        memcpy(into, conv, (size_t)n);
        if (clen > c->len) { c->resp = LENGERR; c->resp2 = 11; }
    }
    free(conv);
    c->len = clen;
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
    harness_channel = 1;
    int ch = channel_named(as ? as : name, 1);
    harness_channel = 0;
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
