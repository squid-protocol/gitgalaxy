/* #5274: the web family (WEB OPEN / CONVERSE / CLOSE / PARSE / SEND / EXTRACT / RECEIVE / RETRIEVE, the header and form-field
 * reads and browses, EXTRACT TCPIP) -- split out of ggcics.c, which includes it in three parts where the blocks sat (the
 * storage block GETMAIN / FREEMAIN / BLL sits between them, and WEB RECEIVE SET needs blk_set_new). */
#if !defined(GGCICS_WEB_PART2) && !defined(GGCICS_WEB_PART3) /* the first part: WEB OPEN .. WRITE HTTPHEADER, EXTRACT TCPIP */
/* ---- #4767 zECS: CICS web support as an HTTP client -- WEB OPEN, WEB CONVERSE, WEB CLOSE (IBM CICS TS, EXEC CICS WEB OPEN,
 * WEB CONVERSE, WEB CLOSE; register X35) ----
 * The server is not part of the region: the peers are a fact the runner states, the file $GGCICS_HTTP names (unstated, every
 * WEB command is refused). Per peer a line `P SCHEME HOSTHEX PORT URIMAP|- PATHHEX|-`, then its responses, one per request,
 * `X METHOD PATHHEX QUERYHEX|- STATUS STATUSTEXTHEX|- MEDIATYPEHEX|- BODYHEX|-` (hex: the bytes in the program's page; '-':
 * none). The exchange is in the program's characters: conversion changes nothing within the model. As CicsTask (the Java
 * side) answers. */
#define WEB_MAXP 32
#define WEB_TXT 4096
/* #6072: the stated request and connection files (webreq_load, tcpip_load) take a line of WEBIN_LINE bytes and each token of
 * WEBIN_TOK: a body of 32000 bytes or more is 64000 hex characters, which a 33000-byte token split into several. */
#define WEBIN_LINE 270000
#define WEBIN_TOK_FMT "%269999s"
typedef struct { char scheme[8], host[WEB_TXT], urimap[9], path[WEB_TXT]; int port, haspath; } web_peer;
typedef struct { int peer, status; char method[8], path[WEB_TXT], query[WEB_TXT], stext[WEB_TXT], media[WEB_TXT];
                 char *body; int bodylen; } web_x;
static web_peer web_peers[WEB_MAXP];
/* #6072: IBM sets no count of sessions a task may open or of responses a peer may give (ZECS000 opens one per record and
 * never closes: 501), so these tables grow; only the token's four digits (GGWSnnnn, 8 bytes) bound the sessions. */
#define WEB_MAXSESS 9999
static web_x *web_xs;
static int *web_answered;
static struct { char token[9]; int peer, byurimap, open; } *web_sess;
static int web_npeers = -1, web_nxs = 0, web_xcap = 0, web_seq = 0, web_nsess = 0, web_scap = 0;

static void *web_grow(void *tab, int *cap, size_t each, int need) {
    int ncap = *cap ? *cap : 64;
    void *t;
    while (ncap < need) ncap *= 2;
    t = realloc(tab, (size_t)ncap * each);
    if (!t) refuse("WEB: out of storage");
    memset((char *)t + (size_t)*cap * each, 0, (size_t)(ncap - *cap) * each);
    *cap = ncap;
    return t;
}

static int web_hexval(int ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    refuse("WEB: $GGCICS_HTTP holds a value that is not hex");
    return 0;
}

/* hex (or '-') -> bytes in dst (NUL-terminated as well), its length */
static int web_unhex(const char *hex, char *dst, int cap) {
    int n = strcmp(hex, "-") == 0 ? 0 : (int)strlen(hex) / 2;
    if (n >= cap) refuse("WEB: a stated value too long");
    for (int i = 0; i < n; i++) dst[i] = (char)(web_hexval(hex[2 * i]) * 16 + web_hexval(hex[2 * i + 1]));
    dst[n] = '\0';
    return n;
}

static void web_load(void) {
    const char *env = getenv("GGCICS_HTTP");
    static char line[70000];
    if (web_npeers >= 0) return;
    if (!env) refuse("WEB: the HTTP peers are not stated for this task");
    FILE *f = fopen(env, "r");
    if (!f) refuse("WEB: the HTTP peers are not stated for this task");
    web_npeers = 0;
    while (fgets(line, sizeof line, f)) {
        static char a[8][33000];
        if (strlen(line) > 32000) refuse("WEB: a stated response longer than 16000 bytes");
        int k = sscanf(line, "%32999s %32999s %32999s %32999s %32999s %32999s %32999s %32999s",
                       a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
        if (k == 6 && strcmp(a[0], "P") == 0) {
            if (web_npeers >= WEB_MAXP) refuse("WEB: more than 32 HTTP peers stated");
            web_peer *p = &web_peers[web_npeers++];
            snprintf(p->scheme, sizeof p->scheme, "%s", a[1]);
            web_unhex(a[2], p->host, WEB_TXT);
            p->port = atoi(a[3]);
            snprintf(p->urimap, sizeof p->urimap, "%s", strcmp(a[4], "-") == 0 ? "" : a[4]);
            p->haspath = strcmp(a[5], "-") != 0;
            web_unhex(a[5], p->path, WEB_TXT);
        } else if (k == 8 && strcmp(a[0], "X") == 0 && web_npeers > 0) {
            web_x *x;
            if (web_nxs >= web_xcap) {
                int old = web_xcap;
                web_xs = web_grow(web_xs, &web_xcap, sizeof *web_xs, web_nxs + 1);
                web_xcap = old;
                web_answered = web_grow(web_answered, &web_xcap, sizeof *web_answered, web_nxs + 1);
            }
            x = &web_xs[web_nxs++];
            x->peer = web_npeers - 1;
            snprintf(x->method, sizeof x->method, "%s", a[1]);
            web_unhex(a[2], x->path, WEB_TXT);
            web_unhex(a[3], x->query, WEB_TXT);
            x->status = atoi(a[4]);
            web_unhex(a[5], x->stext, WEB_TXT);
            web_unhex(a[6], x->media, WEB_TXT);
            x->body = malloc(strlen(a[7]) / 2 + 2);
            if (!x->body) refuse("out of memory");
            x->bodylen = web_unhex(a[7], x->body, (int)strlen(a[7]) / 2 + 2);
        }
    }
    fclose(f);
}

static void web_hex(const char *src, int n, char *dst) {
    if (n == 0) { strcpy(dst, "-"); return; }
    for (int i = 0; i < n; i++) sprintf(dst + 2 * i, "%02X", (unsigned char)src[i]);
}

static int web_same_host(const char *a, const char *b) { /* host names compare without case (ASSUMED, X35) */
    while (*a && *b && tolower((unsigned char)*a) == tolower((unsigned char)*b)) { a++; b++; }
    return *a == '\0' && *b == '\0';
}

static int web_session(const char *token) {
    for (int i = 0; i < web_nsess; i++)
        if (web_sess[i].open && memcmp(web_sess[i].token, token, 8) == 0) return i;
    return -1;
}

static void web_opened(gg_cics *c, char *token, int peer, int byurimap) {
    if (web_nsess >= WEB_MAXSESS) refuse("WEB OPEN: more than 9999 sessions in one task");
    if (web_nsess >= web_scap) web_sess = web_grow(web_sess, &web_scap, sizeof *web_sess, web_nsess + 1);
    snprintf(web_sess[web_nsess].token, 9, "GGWS%04d", ++web_seq);
    web_sess[web_nsess].peer = peer;
    web_sess[web_nsess].byurimap = byurimap;
    web_sess[web_nsess].open = 1;
    memcpy(token, web_sess[web_nsess].token, 8);
    web_nsess++;
    c->resp = NORMAL;
    c->resp2 = 0;
}

/* WEB OPEN: GG-FLAGS URIMAP (the name in GG-NAME1) or HOST (GG-LEN HOSTLENGTH, GG-ITEM the SCHEME CVDA, GG-NUM the
 * PORTNUMBER when GG-FLAGS also names PORT). LENGERR 21, INVREQ 40 / 138; the SESSTOKEN written on NORMAL only. */
static int web_open(gg_cics *c, char *token, char *host, int hostcap) {
    char flags[41], name[9], h[WEB_TXT];
    int conds = 0, port, n = c->len;
    const char *sch;
    web_load();
    trim(c->flags, 40, flags);
    if (strncmp(flags, "URIMAP", 6) == 0) {
        trim(c->name1, 8, name);
        for (int i = 0; i < web_npeers; i++)
            if (strcmp(web_peers[i].urimap, name) == 0) { web_opened(c, token, i, 1); return 0; }
        refuse("WEB OPEN of a peer the run does not state");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n <= 0) { c->resp = LENGERR; c->resp2 = 21; conds++; }
    else if (n > hostcap) refuse("WEB OPEN HOSTLENGTH beyond HOST");
    sch = c->item == 1096 ? "HTTP" : c->item == 1029 ? "HTTPS" : NULL;
    if (!sch) { c->resp = INVREQ; c->resp2 = 40; conds++; }
    port = strstr(flags, "PORT") ? c->num : (sch && strcmp(sch, "HTTPS") == 0 ? 443 : 80);
    if (strstr(flags, "PORT") && port > 65535) { c->resp = INVREQ; c->resp2 = 138; conds++; }
    else if (strstr(flags, "PORT") && port < 1) refuse("WEB OPEN PORTNUMBER below 1");
    if (conds > 1) refuse("WEB OPEN with more than one condition at once");
    if (conds == 1) return 0;
    if (n >= WEB_TXT) refuse("WEB OPEN HOSTLENGTH beyond HOST");
    memcpy(h, host, (size_t)n);
    h[n] = '\0';
    for (int i = 0; i < web_npeers; i++) {
        if (strcmp(web_peers[i].scheme, sch) == 0 && web_same_host(web_peers[i].host, h) && web_peers[i].port == port) {
            web_opened(c, token, i, 0);
            return 0;
        }
    }
    refuse("WEB OPEN of a peer the run does not state");
    return 0;
}

/* The WEB-OPEN event of SPEC 6.2 (host and scheme as the connection names them, '-' when the command gave none; RESP2 as
 * recorded): a refusal inside web_open records nothing, as CicsTask.webOpenHost / webOpenUrimap. */
int GGCWOPN(gg_cics *c, char *token, char *host, int hostcap) {
    char flags[41], hx[WEB_TXT * 2 + 2], ev[WEB_TXT * 2 + 120];
    const char *sch = c->item == 1096 ? "HTTP" : c->item == 1029 ? "HTTPS" : "-";
    int n = c->len;
    const char *h = host;
    web_load();
    trim(c->flags, 40, flags);
    web_open(c, token, host, hostcap);
    if (strncmp(flags, "URIMAP", 6) == 0) {
        n = 0;
        sch = "-";
        if (c->resp == NORMAL) {
            h = web_peers[web_sess[web_nsess - 1].peer].host;
            n = (int)strlen(h);
            sch = web_peers[web_sess[web_nsess - 1].peer].scheme;
        }
    } else if (n <= 0 || n > hostcap) {
        n = 0;
    }
    web_hex(h, n, hx);
    snprintf(ev, sizeof ev, "WEB-OPEN host=%s scheme=%s resp=%d resp2=%d", hx, sch, c->resp, c->resp2);
    event(ev, NULL, 0);
    return 0;
}

/* WEB CONVERSE: GG-NUM the METHOD CVDA (out: STATUSCODE), GG-HOURS PATHLENGTH, GG-MINS QUERYSTRLEN, GG-SECS FROMLENGTH,
 * GG-LEN MAXLENGTH (out: TOLENGTH), GG-ITEM STATUSLEN (-1: no STATUSTEXT); GG-FLAGS names PATH QUERY FROM MEDIA given.
 * The conditions IBM lists for what the program gives come back with nothing sent; a response longer than MAXLENGTH is
 * truncated (LENGERR 57). INTO, STATUSTEXT and MEDIATYPE are written here, when a response came back. */
int GGCWCNV(gg_cics *c, char *token, char *path, int pathcap, char *query, int querycap, char *from, int fromcap,
            char *media, int mediacap, char *into, int intocap, char *stext, int stextcap) {
    char flags[41], ev[WEB_TXT * 9 + 400], p[WEB_TXT], q[WEB_TXT], mt[57], hx[4][WEB_TXT * 2 + 2];
    int conds = 0, s, hasp, hasq, hasf, hasm, pl = c->hours, ql = c->mins, fl = c->secs, max = c->len, sl = c->item;
    int method = c->num, body = 0, x = -1, n, mtl = 0;
    const char *m = method == 748 ? "GET" : method == 750 ? "HEAD" : method == 292 ? "DELETE" : method == 636 ? "POST"
                  : method == 749 ? "PUT" : method == 1220 ? "PATCH" : NULL;
    web_load();
    trim(c->flags, 40, flags);
    hasp = strstr(flags, "PATH") != NULL;
    hasq = strstr(flags, "QUERY") != NULL;
    hasf = strstr(flags, "FROM") != NULL;
    hasm = strstr(flags, "MEDIA") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
#define WEB_COND(r, r2) do { c->resp = (r); c->resp2 = (r2); conds++; } while (0)
    s = web_session(token);
    if (s < 0) WEB_COND(DFHRESP_NOTOPEN, 27);
    if (method == 760 || method == 759) refuse("WEB CONVERSE METHOD TRACE / OPTIONS");
    if (m) body = strcmp(m, "POST") == 0 || strcmp(m, "PUT") == 0 || strcmp(m, "PATCH") == 0;
    if (!m) WEB_COND(INVREQ, 54);
    else if (hasf && !body) WEB_COND(INVREQ, 33);
    else if (!hasf && body) WEB_COND(INVREQ, 34);
    if (hasm) {
        mtl = mediacap < 56 ? mediacap : 56;
        memcpy(mt, media, (size_t)mtl);
        while (mtl > 0 && mt[mtl - 1] == ' ') mtl--;
        mt[mtl] = '\0';
    }
    if (hasf && !hasm) WEB_COND(INVREQ, 76);
    else if (hasf && mtl == 0) refuse("WEB CONVERSE body with a blank MEDIATYPE");
    if (hasp && pl <= 0) WEB_COND(LENGERR, 5);
    if (hasq && ql <= 0) WEB_COND(LENGERR, 8);
    if (max < 0) WEB_COND(LENGERR, 16);
    else if (max == 0) refuse("WEB CONVERSE MAXLENGTH 0");
    if (hasf && fl <= 0) WEB_COND(LENGERR, 50);
    if (sl == 0 || sl < -1) WEB_COND(LENGERR, 59);
    if ((hasp && pl > pathcap) || (hasq && ql > querycap) || (hasf && fl > fromcap))
        refuse("WEB CONVERSE length beyond its area");
#undef WEB_COND
    if (conds > 1) refuse("WEB CONVERSE with more than one condition at once");
    if (conds == 1) return 0;
    if (!hasp && !web_sess[s].byurimap) refuse("WEB CONVERSE with no PATH on a session opened by HOST");
    if (hasp) {
        if (pl >= WEB_TXT) refuse("WEB CONVERSE length beyond its area");
        memcpy(p, path, (size_t)pl);
        p[pl] = '\0';
    } else {
        snprintf(p, sizeof p, "%s", web_peers[web_sess[s].peer].path);
    }
    q[0] = '\0';
    if (hasq) {
        int skip = query[0] == '?';
        if (ql >= WEB_TXT) refuse("WEB CONVERSE length beyond its area");
        memcpy(q, query + skip, (size_t)(ql - skip));
        q[ql - skip] = '\0';
    }
    for (int i = 0; i < web_nxs && x < 0; i++) {
        if (!web_answered[i] && web_xs[i].peer == web_sess[s].peer && strcmp(web_xs[i].method, m) == 0
            && strcmp(web_xs[i].path, p) == 0 && strcmp(web_xs[i].query, q) == 0) x = i;
    }
    if (x < 0) refuse("WEB CONVERSE request the peer states no response to");
    if (sl > 0 && (int)strlen(web_xs[x].stext) > sl) refuse("WEB CONVERSE status text longer than STATUSLEN");
    web_answered[x] = 1;
    n = web_xs[x].bodylen;
    if (n > max) { n = max; c->resp = LENGERR; c->resp2 = 57; }
    web_hex(web_peers[web_sess[s].peer].host, (int)strlen(web_peers[web_sess[s].peer].host), hx[0]);
    web_hex(p, (int)strlen(p), hx[1]);
    web_hex(q, (int)strlen(q), hx[2]);
    web_hex(mt, hasf ? mtl : 0, hx[3]);
    snprintf(ev, sizeof ev, "WEB-CONVERSE host=%s method=%s path=%s query=%s media=%s body=%d resp=%d resp2=%d",
             hx[0], m, hx[1], hx[2], hx[3], hasf, c->resp, c->resp2);
    {   /* #4767: the response the peer gave (status, TOLENGTH, the bytes INTO gets, hex; '-' none), for the crucible's event */
        size_t el = strlen(ev);
        char *big = malloc(el + 2 * (size_t)n + 64);
        if (!big) refuse("WEB CONVERSE out of memory recording the response");
        memcpy(big, ev, el);
        el += (size_t)sprintf(big + el, " status=%d tolen=%d into=", web_xs[x].status, n);
        web_hex(web_xs[x].body, n, big + el);
        event(big, hasf ? from : NULL, hasf ? fl : 0);
        free(big);
    }
    if (n > intocap) refuse("WEB CONVERSE INTO beyond its area");
    memcpy(into, web_xs[x].body, (size_t)n);
    c->len = n;
    c->num = web_xs[x].status;
    if (sl > 0) {
        int tl = (int)strlen(web_xs[x].stext);
        if (tl > stextcap) refuse("WEB CONVERSE STATUSTEXT beyond its area");
        memcpy(stext, web_xs[x].stext, (size_t)tl);
    }
    if (hasm) {
        int ml = (int)strlen(web_xs[x].media), w = mediacap < 56 ? mediacap : 56;
        for (int i = 0; i < w; i++) media[i] = i < ml ? web_xs[x].media[i] : ' ';
    }
    return 0;
}

/* WEB CLOSE: NOTOPEN 27 for a token that is not an open session's. */
int GGCWCLS(gg_cics *c, char *token) {
    int s;
    web_load();
    s = web_session(token);
    c->resp = s < 0 ? DFHRESP_NOTOPEN : NORMAL;
    c->resp2 = s < 0 ? 27 : 0;
    if (s >= 0) web_sess[s].open = 0;
    {
        char ev[80];
        snprintf(ev, sizeof ev, "WEB-CLOSE resp=%d resp2=%d", c->resp, c->resp2);
        event(ev, NULL, 0);
    }
    return 0;
}

/* ---- #4767 zECS: WEB PARSE URL (IBM CICS TS, EXEC CICS WEB PARSE URL; register X36) -- pure, no peer ----
 * GG-LEN URLLENGTH, GG-HOURS HOSTLENGTH, GG-MINS PATHLENGTH, GG-SECS QUERYSTRLEN (each in; out: the piece's length),
 * GG-NUM PORTNUMBER (out); GG-FLAGS names SCHEME HOST PATH QUERY given. INVREQ 28 (no "scheme://", an empty scheme or
 * host, a port that is not 1-5 digits or above 65535: ASSUMED), INVREQ 65 (a "%" not followed by two of 0-9 A-F), LENGERR
 * (RESP2 29 host, 30 path, 8 query string longer than its length; areas and lengths left alone: ASSUMED). An IPv6 host is
 * written in brackets and returned without them. Refused as CicsTask.webParse refuses. The areas are written on NORMAL only. */
#define WEB_IPV6 "WEB PARSE URL IPv6 host that is not [hex:colons] or [hex:colons]:port"
static int web_hexd(int ch) { return (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'F'); }

int GGCWPRS(gg_cics *c, char *url, int urlcap, char *scheme, int schemecap, char *host, int hostcap, char *path,
            int pathcap, char *query, int querycap) {
    char flags[41], u[WEB_TXT], sch[17], h[WEB_TXT], pa[WEB_TXT], q[WEB_TXT];
    int n = c->len, hl = c->hours, pl = c->mins, ql = c->secs, bad28 = 0, bad65 = 0, port = -1;
    int hs, hp, hq, hc;
    char *sep, *rest, *auth_end, *tail, *qm, *colon;
    int i, auth_len, sl;
    trim(c->flags, 40, flags);
    hc = strstr(flags, "SCHEME") != NULL;
    hs = strstr(flags, "HOST") != NULL;
    hp = strstr(flags, "PATH") != NULL;
    hq = strstr(flags, "QUERY") != NULL;
    if (n <= 0) refuse("WEB PARSE URL URLLENGTH not above zero");
    if (n > urlcap || n >= WEB_TXT) refuse("WEB PARSE URL length beyond its area");
    if ((hs && hl > hostcap) || (hp && pl > pathcap) || (hq && ql > querycap)) refuse("WEB PARSE URL length beyond its area");
    memcpy(u, url, (size_t)n);
    u[n] = '\0';
    for (i = 0; i < n; i++) {
        if (u[i] == '%') {
            int ok = i + 2 < n && web_hexd(u[i + 1]) && web_hexd(u[i + 2]);
            int lower = i + 2 < n && isxdigit((unsigned char)u[i + 1]) && isxdigit((unsigned char)u[i + 2]);
            if (!ok && lower) refuse("WEB PARSE URL lowercase hex digit in an escape");
            if (!ok) bad65 = 1;
        }
    }
    if (strchr(u, '#')) refuse("WEB PARSE URL fragment");
    sep = strstr(u, "://");
    sch[0] = '\0';
    if (!sep || sep == u) bad28 = 1;
    else {
        sl = (int)(sep - u);
        if (sl > 16) refuse("WEB PARSE URL scheme other than HTTP / HTTPS");
        for (i = 0; i < sl; i++) sch[i] = (char)toupper((unsigned char)u[i]);
        sch[sl] = '\0';
        if (strcmp(sch, "HTTP") != 0 && strcmp(sch, "HTTPS") != 0) refuse("WEB PARSE URL scheme other than HTTP / HTTPS");
    }
    h[0] = pa[0] = q[0] = '\0';
    if (!bad28) {
        rest = sep + 3;
        auth_end = rest + strcspn(rest, "/?");
        auth_len = (int)(auth_end - rest);
        for (i = 0; i < auth_len; i++) if (rest[i] == '@') refuse("WEB PARSE URL user-info");
        colon = NULL;
        if (auth_len > 0 && rest[0] == '[') {
            char *close = memchr(rest, ']', (size_t)auth_len);
            int cl = close ? (int)(close - rest) : 0;
            int shaped = cl >= 2 && (cl + 1 == auth_len || rest[cl + 1] == ':') && !memchr(rest + 1, '[', (size_t)(auth_len - 1))
                         && !(cl + 1 < auth_len && memchr(rest + cl + 1, ']', (size_t)(auth_len - cl - 1)));
            for (i = 1; shaped && i < cl; i++) if (!isxdigit((unsigned char)rest[i]) && rest[i] != ':' && rest[i] != '.') shaped = 0;
            if (!shaped) refuse(WEB_IPV6);
            memcpy(h, rest + 1, (size_t)(cl - 1));
            h[cl - 1] = '\0';
            if (cl + 1 < auth_len) colon = rest + cl + 1;
        } else {
            for (i = 0; i < auth_len; i++) if (rest[i] == '[' || rest[i] == ']') refuse(WEB_IPV6);
            for (i = 0; i < auth_len; i++) if (rest[i] == ':') colon = rest + i;
            memcpy(h, rest, (size_t)(colon ? colon - rest : auth_len));
            h[colon ? colon - rest : auth_len] = '\0';
        }
        if (colon) {
            int plen = (int)(auth_end - colon) - 1, digits = 1;
            if (plen == 0) refuse("WEB PARSE URL empty port");
            for (i = 0; i < plen; i++) if (colon[1 + i] < '0' || colon[1 + i] > '9') digits = 0;
            if (!digits || plen > 5) bad28 = 1;
            else {
                port = atoi(colon + 1);
                if (port > 65535) bad28 = 1;
                else if (port == 0) refuse("WEB PARSE URL port 0");
            }
        } else port = strcmp(sch, "HTTPS") == 0 ? 443 : 80;
        if (h[0] == '\0') bad28 = 1;
        tail = auth_end;
        qm = strchr(tail, '?');
        memcpy(pa, tail, qm ? (size_t)(qm - tail) : strlen(tail));
        pa[qm ? (size_t)(qm - tail) : strlen(tail)] = '\0';
        snprintf(q, sizeof q, "%s", qm ? qm + 1 : "");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    {
        int host_long = hs && (int)strlen(h) > hl, path_long = hp && (int)strlen(pa) > pl, query_long = hq && (int)strlen(q) > ql;
        if (bad28 + bad65 + host_long + path_long + query_long > 1) refuse("WEB PARSE URL with more than one condition at once");
        if (bad28) { c->resp = INVREQ; c->resp2 = 28; return 0; }
        if (bad65) { c->resp = INVREQ; c->resp2 = 65; return 0; }
        if (hc && (int)strlen(sch) > schemecap) refuse("WEB PARSE URL length beyond its area");
        if ((hp && pa[0] == '\0') || (hq && q[0] == '\0')) refuse("WEB PARSE URL PATH or QUERYSTRING the URL has none of");
        if (host_long || path_long || query_long) { c->resp = LENGERR; c->resp2 = host_long ? 29 : path_long ? 30 : 8; return 0; }
    }
    if (hc) { memset(scheme, ' ', (size_t)schemecap); memcpy(scheme, sch, strlen(sch)); }
    if (hs) { memcpy(host, h, strlen(h)); c->hours = (int)strlen(h); }
    if (hp) { memcpy(path, pa, strlen(pa)); c->mins = (int)strlen(pa); }
    if (hq) { memcpy(query, q, strlen(q)); c->secs = (int)strlen(q); }
    c->num = port;
    return 0;
}

/* ---- #4767 zECS: WEB SEND, the server side (IBM CICS TS, EXEC CICS WEB SEND; register X37) ----
 * The task serves one inbound request the runner states: the file $GGCICS_WEBREQ names (unstated, WEB SEND is refused; only that
 * a request is stated is read here: WEB RECEIVE / EXTRACT / READ HTTPHEADER are not modelled yet). GG-LEN FROMLENGTH, GG-ITEM
 * ACTION (0: not given), GG-NUM STATUSCODE (-1: not given), GG-HOURS STATUSLEN (-1: not given), GG-MINS the conversion (0, 1
 * SRVCONVERT, 2 NOSRVCONVERT); GG-FLAGS names MEDIA STEXT given. Recorded as WEB-SEND. As CicsTask.webSend answers. */
static int web_sent = 0;        /* an ACTION(IMMEDIATE) response was sent */
static int web_send_failed = 0; /* #4941: the last WEB SEND ended in a condition */
static int web_issued = 0;      /* a WEB SEND was accepted (IMMEDIATE or EVENTUAL) */
/* #4941 (X37): the ACTION(EVENTUAL) response held for the end of the task (its WEB-SEND event line and body), the document an
 * EVENTUAL DOCTOKEN send (not DOCDELETE) sent as it was sent, and the DOCTOKEN WEB RETRIEVE gave for it (a new document). */
static int web_held = 0, web_held_len = 0, web_held_doclen = 0, web_held_tok = 0;
static char web_held_ev[WEB_TXT * 4 + 200];
static unsigned char *web_held_body = NULL, *web_held_doc = NULL;

/* The task ended: an ACTION(EVENTUAL) response is sent now (recorded after the task's other events); a task that ended in an
 * abend with one held is refused (IBM does not say whether the response is sent). As CicsTask.events. */
static void web_flush(void) {
    if (!web_held) return;
    if (terminated) refuse("WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend");
    web_held = 0;
    event(web_held_ev, (const char *)web_held_body, web_held_len);
}

static int web_send_body(gg_cics *c, const char *from, int fl, char *media, int mediacap, char *stext, int stextcap,
                         int ofdoc, int doc_i, int docstatus, int pre, int pre2) {
    char flags[41], mt[57], ev[WEB_TXT * 4 + 200], hx[2][WEB_TXT * 2 + 2];
    int eventual, action = c->item, status = c->num, sl = c->hours, conv = c->mins, mtl = 0, conds = 0, hasm, hast, i;
    trim(c->flags, 40, flags);
    hasm = strstr(flags, "MEDIA") != NULL;
    hast = strstr(flags, "STEXT") != NULL;
    if (status != -1 && (status < 100 || status > 599)) refuse("WEB SEND STATUSCODE outside 100-599");
    if (hasm) {
        mtl = mediacap < 56 ? mediacap : 56;
        memcpy(mt, media, (size_t)mtl);
        while (mtl > 0 && mt[mtl - 1] == ' ') mtl--;
        mt[mtl] = '\0';
        for (i = 0; i < mtl; i++) if ((unsigned char)mt[i] <= ' ' || (unsigned char)mt[i] > '~') mtl = -1;
        if (mtl < 0 || strchr(mt, '/') == NULL || mt[0] == '/' || mt[strlen(mt) - 1] == '/')
            refuse("WEB SEND MEDIATYPE blank or not type/subtype");
    }
    if (conv == 1) {
        int text = hasm && mtl >= 5 && tolower((unsigned char)mt[0]) == 't' && tolower((unsigned char)mt[1]) == 'e'
                   && tolower((unsigned char)mt[2]) == 'x' && tolower((unsigned char)mt[3]) == 't' && mt[4] == '/';
        if (!text) refuse("WEB SEND SRVCONVERT on a media type that is not text/*");
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (pre) { c->resp = pre; c->resp2 = pre2; conds++; } /* a container send's own conditions */
    if (ofdoc && doc_i < 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    if (action != 0 && action != 2 && action != 3) { c->resp = INVREQ; c->resp2 = 11; conds++; }
    if (ofdoc && docstatus != 0 && docstatus != 295 && docstatus != 296) { c->resp = INVREQ; c->resp2 = 143; conds++; }
    if ((status == 204 || status == 205 || status == 304) && fl > 0) { c->resp = INVREQ; c->resp2 = 72; conds++; }
    if (conds > 1) refuse("WEB SEND with more than one condition at once");
    if (conds == 1) { web_send_failed = 1; return 0; }
    eventual = action != 2; /* (an omitted ACTION is EVENTUAL for a send that is not chunked: IBM) */
    if (!eventual && web_held) refuse("WEB SEND ACTION(IMMEDIATE) after an ACTION(EVENTUAL) send");
    web_send_failed = 0;
    web_issued = 1;
    web_hex(mt, hasm ? mtl : 0, hx[0]);
    if (hast) { int n = sl < 0 ? stextcap : sl; web_hex(stext, n, hx[1]); } else strcpy(hx[1], "-");
    snprintf(ev, sizeof ev, "WEB-SEND status=%d stext=%s media=%s action=%s resp=0 resp2=0",
             status == -1 ? 200 : status, hx[1], hx[0], eventual ? "EVENTUAL" : "IMMEDIATE");
    free(web_held_doc);
    web_held_doc = NULL;
    web_held_tok = 0;
    if (eventual) {
        free(web_held_body);
        web_held_body = malloc(fl > 0 ? (size_t)fl : 1);
        memcpy(web_held_body, from, (size_t)(fl > 0 ? fl : 0));
        web_held_len = fl;
        strcpy(web_held_ev, ev);
        web_held = 1; /* sent at the end of the task; a second send replaces it */
        if (ofdoc && docstatus != 295) {
            web_held_doc = malloc(fl > 0 ? (size_t)fl : 1);
            memcpy(web_held_doc, from, (size_t)(fl > 0 ? fl : 0));
            web_held_doclen = fl;
        }
    } else {
        web_sent = 1;
        event(ev, from, fl);
    }
    if (ofdoc && docstatus == 295) doc_dead[doc_i] = 1; /* DOCDELETE: deleted once its contents are saved for sending */
    return 0;
}

int GGCWSND(gg_cics *c, char *from, int fromcap, char *media, int mediacap, char *stext, int stextcap) {
    char flags[41];
    int fl = c->len, sl = c->hours, hast;
    const char *env = getenv("GGCICS_WEBREQ");
    FILE *f;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    fclose(f);
    if (web_sent) refuse("WEB SEND after a response was sent");
    trim(c->flags, 40, flags);
    hast = strstr(flags, "STEXT") != NULL;
    if (fl <= 0 || (hast && sl == 0) || sl < -1) refuse("WEB SEND FROMLENGTH or STATUSLEN not above zero");
    if (fl > fromcap || (hast && sl > stextcap)) refuse("WEB SEND length beyond its area");
    return web_send_body(c, from, fl, media, mediacap, stext, stextcap, 0, -1, 0, 0, 0);
}

/* WEB SEND DOCTOKEN(tok) (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response is the document the token names,
 * one the task created, as it is now; an empty document is no message body (ASSUMED), so a 204 may send one. GG-SECS is
 * DOCSTATUS's CVDA (0: not given; 295 DOCDELETE, 296 NODOCDELETE). As CicsTask.webSendDocument. */
int GGCWSDC(gg_cics *c, char *tok, int toklen, char *media, int mediacap, char *stext, int stextcap) {
    char flags[41], want[100];
    int sl = c->hours, hast, i;
    const char *env = getenv("GGCICS_WEBREQ");
    FILE *f;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    fclose(f);
    if (web_sent) refuse("WEB SEND after a response was sent");
    trim(c->flags, 40, flags);
    hast = strstr(flags, "STEXT") != NULL;
    trim(tok, toklen < 99 ? toklen : 99, want);
    for (i = 0; i < ndocs; i++) {
        char t[17];
        snprintf(t, sizeof t, "GGDOC%011d", i + 1);
        if (strcmp(t, want) == 0) break;
    }
    if ((hast && sl == 0) || sl < -1) refuse("WEB SEND FROMLENGTH or STATUSLEN not above zero");
    if (hast && sl > stextcap) refuse("WEB SEND length beyond its area");
    if (i == ndocs || doc_dead[i]) i = -1; /* NOTFND 1: not created, deleted or wrongly named (IBM lists one RESP2) */
    return web_send_body(c, i < 0 ? "" : (const char *)docs[i], i < 0 ? 0 : doc_len[i], media, mediacap, stext, stextcap, 1,
                         i, c->secs, 0, 0);
}

/* WEB SEND CONTAINER(GG-QNAME) [CHANNEL(GG-CHAN)] (IBM CICS TS, EXEC CICS WEB SEND, server; register X37): the response body is
 * the container's data as it is now. CONTAINERERR RESP2 2, CHANNELERR RESP2 2, INVREQ RESP2 145 (no CHANNEL, no current
 * channel), INVREQ RESP2 150 (conversion of a BIT container); an empty container and a BIT container sent as it is are refused.
 * As CicsTask.webSendContainer. */
int GGCWSCT(gg_cics *c, char *media, int mediacap, char *stext, int stextcap) {
    char flags[41], name[17];
    int sl = c->hours, hast, ch, pre = 0, pre2 = 0;
    gg_container *k = NULL;
    const char *env = getenv("GGCICS_WEBREQ");
    FILE *f;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    fclose(f);
    if (web_sent) refuse("WEB SEND after a response was sent");
    trim(c->flags, 40, flags);
    hast = strstr(flags, "STEXT") != NULL;
    if ((hast && sl == 0) || sl < -1) refuse("WEB SEND FROMLENGTH or STATUSLEN not above zero");
    if (hast && sl > stextcap) refuse("WEB SEND length beyond its area");
    cics_name(c->qname, name, "container");
    ch = command_channel(c, 0, 145);
    if (!ch) { pre = c->resp; pre2 = c->resp2; }
    else if (!(k = container_named(&chans[ch - 1], name, 0))) { pre = CONTAINERERR; pre2 = 2; }
    else if (c->mins != 0 && k->bit) { pre = INVREQ; pre2 = 150; }
    else if (k->len == 0) refuse("WEB SEND of an empty container");
    else if (k->bit) refuse("WEB SEND of a DATATYPE BIT container");
    else if (k->ccsid != REGION_CCSID) refuse("WEB SEND of a container in a CCSID other than the region's");
    return web_send_body(c, pre ? "" : k->data, pre ? 0 : k->len, media, mediacap, stext, stextcap, 0, -1, 0, pre, pre2);
}

/* ---- #4767 zECS: the server reading the request it serves (IBM CICS TS, EXEC CICS WEB EXTRACT, WEB RECEIVE, WEB READ
 * HTTPHEADER, WEB WRITE HTTPHEADER; register X38) ----
 * The request is the file $GGCICS_WEBREQ names (unstated, each command is refused): `R SCHEME HOSTHEX PORT METHOD PATHHEX
 * QUERYHEX|-`, `V VERSIONHEX`, `B MEDIAHEX BODYHEX|-` (none: no body) and a `H NAMEHEX VALUEHEX|-` line per header. As
 * CicsTask.webExtract / webReceive / webReadHeader / webWriteHeader answer. */
#define WEB_MAXH 64
static struct { int loaded, hasbody, nh; char scheme[8], host[WEB_TXT], method[16], path[WEB_TXT], query[WEB_TXT],
                version[64], media[WEB_TXT], *body; int port, bodylen; char hname[WEB_MAXH][256];
                char *hval[WEB_MAXH]; } webreq;
static int web_received = 0; /* 0 none, 1 a receive not NOSRVCONVERT, 2 NOSRVCONVERT, 3 the SRVCONVERT pass after it (ASSUMED, X38) */

static void webreq_load(void) {
    const char *env = getenv("GGCICS_WEBREQ");
    static char line[WEBIN_LINE], a[8][WEBIN_LINE];
    FILE *f;
    if (webreq.loaded) return;
    if (!env || !(f = fopen(env, "r"))) refuse("the HTTP request is not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int k;
        if (!strchr(line, '\n') && !feof(f)) refuse("the HTTP request has a line longer than the stub reads");
        k = sscanf(line, WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " "
                         WEBIN_TOK_FMT " " WEBIN_TOK_FMT, a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
        if (k == 7 && strcmp(a[0], "R") == 0) {
            snprintf(webreq.scheme, sizeof webreq.scheme, "%s", a[1]);
            web_unhex(a[2], webreq.host, WEB_TXT);
            webreq.port = atoi(a[3]);
            snprintf(webreq.method, sizeof webreq.method, "%s", a[4]);
            web_unhex(a[5], webreq.path, WEB_TXT);
            web_unhex(a[6], webreq.query, WEB_TXT);
        } else if (k == 2 && strcmp(a[0], "V") == 0) {
            web_unhex(a[1], webreq.version, (int)sizeof webreq.version);
        } else if (k == 3 && strcmp(a[0], "B") == 0) {
            webreq.hasbody = 1;
            web_unhex(a[1], webreq.media, WEB_TXT);
            webreq.body = malloc(strlen(a[2]) / 2 + 2);
            if (!webreq.body) refuse("out of memory");
            webreq.bodylen = web_unhex(a[2], webreq.body, (int)strlen(a[2]) / 2 + 2);
        } else if (k == 3 && strcmp(a[0], "H") == 0 && webreq.nh < WEB_MAXH) {
            int n = web_unhex(a[1], webreq.hname[webreq.nh], 256);
            webreq.hname[webreq.nh][n] = '\0';
            webreq.hval[webreq.nh] = malloc(strlen(a[2]) / 2 + 2);
            if (!webreq.hval[webreq.nh]) refuse("out of memory");
            web_unhex(a[2], webreq.hval[webreq.nh], (int)strlen(a[2]) / 2 + 2);
            webreq.nh++;
        }
    }
    fclose(f);
    webreq.loaded = 1;
}

/* GG-LEN HOSTLENGTH, GG-HOURS METHODLENGTH, GG-MINS VERSIONLEN, GG-SECS PATHLENGTH, GG-ITEM QUERYSTRLEN (each in; out: the
 * piece's length); GG-FLAGS names HOST METHOD VERSION PATH QUERY given; out: GG-NUM the port, GG-NAME1 the scheme. */
int GGCWEXT(gg_cics *c, char *host, int hostcap, char *method, int methodcap, char *version, int versioncap, char *path,
            int pathcap, char *query, int querycap) {
    char flags[41];
    int hs, hm, hv, hp, hq, hl = c->len, ml = c->hours, vl = c->mins, pl = c->secs, ql = c->item, conds = 0;
    webreq_load();
    trim(c->flags, 40, flags);
    hs = strstr(flags, "HOST") != NULL;
    hm = strstr(flags, "METHOD") != NULL;
    hv = strstr(flags, "VERSION") != NULL;
    hp = strstr(flags, "PATH") != NULL;
    hq = strstr(flags, "QUERY") != NULL;
    if ((hs && hl > hostcap) || (hm && ml > methodcap) || (hv && vl > versioncap) || (hp && pl > pathcap)
        || (hq && ql > querycap)) refuse("WEB EXTRACT length beyond its area");
    if ((hm && ml <= 0) || (hq && ql <= 0)) refuse("WEB EXTRACT METHODLENGTH or QUERYSTRLEN not above zero");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (hs && hl <= 0) { c->resp = LENGERR; c->resp2 = 21; conds++; }
    if (hp && pl <= 0) { c->resp = LENGERR; c->resp2 = 5; conds++; }
    if (hv && vl <= 0) { c->resp = LENGERR; c->resp2 = 7; conds++; }
    if (conds > 1) refuse("WEB EXTRACT with more than one condition at once");
    if (conds == 1) return 0;
    if ((hs && (int)strlen(webreq.host) > hl) || (hm && (int)strlen(webreq.method) > ml)
        || (hv && (int)strlen(webreq.version) > vl) || (hp && (int)strlen(webreq.path) > pl)
        || (hq && (int)strlen(webreq.query) > ql)) refuse("WEB EXTRACT piece longer than its length");
    if (hs) { memcpy(host, webreq.host, strlen(webreq.host)); c->len = (int)strlen(webreq.host); }
    if (hm) { memcpy(method, webreq.method, strlen(webreq.method)); c->hours = (int)strlen(webreq.method); }
    if (hv) { memcpy(version, webreq.version, strlen(webreq.version)); c->mins = (int)strlen(webreq.version); }
    if (hp) { memcpy(path, webreq.path, strlen(webreq.path)); c->secs = (int)strlen(webreq.path); }
    if (hq) { memcpy(query, webreq.query, strlen(webreq.query)); c->item = (int)strlen(webreq.query); }
    c->num = webreq.port;
    memset(c->name1, ' ', sizeof c->name1);
    memcpy(c->name1, webreq.scheme, strlen(webreq.scheme));
    return 0;
}

/* ---- #4972: EXTRACT TCPIP, the connection the task was started on (IBM CICS TS, EXEC CICS EXTRACT TCPIP; register X38) ----
 * The connection is the file $GGCICS_TCPIP names (unstated, EXTRACT TCPIP is refused): `T CLIENTADDR CLIENTNAMEHEX|-
 * SERVERADDR SERVERNAMEHEX|- PORT SSLTYPE`, the names in hex ("-": the DNS knows none). As CicsTask.extractTcpip answers. */
static struct { int loaded, port, hascname, hassname; char caddr[64], saddr[64], ssl[16], cname[WEB_TXT],
                sname[WEB_TXT]; } tcpipc;

static void tcpip_load(void) {
    const char *env = getenv("GGCICS_TCPIP");
    static char line[WEBIN_LINE], a[8][WEBIN_LINE];
    FILE *f;
    if (tcpipc.loaded) return;
    if (!env || !(f = fopen(env, "r"))) refuse("the TCP/IP connection is not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int k;
        if (!strchr(line, '\n') && !feof(f)) refuse("the TCP/IP connection has a line longer than the stub reads");
        k = sscanf(line, WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " " WEBIN_TOK_FMT " "
                         WEBIN_TOK_FMT " " WEBIN_TOK_FMT, a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
        if (k == 7 && strcmp(a[0], "T") == 0) {
            snprintf(tcpipc.caddr, sizeof tcpipc.caddr, "%s", a[1]);
            tcpipc.hascname = strcmp(a[2], "-") != 0;
            web_unhex(a[2], tcpipc.cname, WEB_TXT);
            snprintf(tcpipc.saddr, sizeof tcpipc.saddr, "%s", a[3]);
            tcpipc.hassname = strcmp(a[4], "-") != 0;
            web_unhex(a[4], tcpipc.sname, WEB_TXT);
            tcpipc.port = atoi(a[5]);
            snprintf(tcpipc.ssl, sizeof tcpipc.ssl, "%s", a[6]);
        }
    }
    fclose(f);
    tcpipc.loaded = 1;
}

/* An IPv4 address in dotted decimal as a number (-1: it is not one: four decimal parts 0-255, no leading zero). */
static long long ipv4_value(const char *s) { /* long long: `long` is 32 bits on Windows, and 192.x is above 2^31 */
    long long value = 0;
    int parts = 0;
    while (1) {
        int n = 0, digits = 0;
        if (*s == '0' && s[1] >= '0' && s[1] <= '9') return -1;
        while (*s >= '0' && *s <= '9') {
            n = n * 10 + (*s++ - '0');
            if (++digits > 3) return -1;
        }
        if (digits == 0 || n > 255) return -1;
        value = value * 256 + n;
        parts++;
        if (*s == '\0') break;
        if (*s++ != '.') return -1;
    }
    return parts == 4 ? value : -1;
}

/* GG-LEN CADDRLENGTH, GG-HOURS CNAMELENGTH, GG-MINS SADDRLENGTH, GG-SECS SNAMELENGTH (each in, 0 when the option is missing;
 * out: the piece's length); GG-FLAGS names A1 N1 A2 N2 (client address, client name, server address, server name given) and U1 U2 F1 F2 (a number asked
 * for). The numbers come from GGCTCPN. */
int GGCTCPX(gg_cics *c, char *caddr, int caddrcap, char *cname, int cnamecap, char *saddr, int saddrcap, char *sname,
            int snamecap) {
    char flags[81];
    int ca, cn, sa, sn, cnu, snu, cf, sf, cl = c->len, nl = c->hours, sl = c->mins, ml = c->secs;
    int badlength, toosmall;
    long long cnum, snum;
    tcpip_load();
    trim(c->flags, 40, flags);
    ca = strstr(flags, "A1") != NULL;
    cn = strstr(flags, "N1") != NULL;
    sa = strstr(flags, "A2") != NULL;
    sn = strstr(flags, "N2") != NULL;
    cnu = strstr(flags, "U1") != NULL;
    snu = strstr(flags, "U2") != NULL;
    cf = strstr(flags, "F1") != NULL;
    sf = strstr(flags, "F2") != NULL;
    if ((ca && cl > caddrcap) || (cn && nl > cnamecap) || (sa && sl > saddrcap) || (sn && ml > snamecap))
        refuse("EXTRACT TCPIP length beyond its area");
    cnum = ipv4_value(tcpipc.caddr);
    snum = ipv4_value(tcpipc.saddr);
    if (((ca || cnu || cf) && cnum < 0) || ((sa || snu || sf) && snum < 0) || (cnu && cnum > 2147483647LL)
        || (snu && snum > 2147483647LL)) refuse("EXTRACT TCPIP address");
    if (sn && !tcpipc.hassname) refuse("EXTRACT TCPIP");
    badlength = (ca && cl <= 0) || (cn && nl <= 0) || (sa && sl <= 0) || (sn && ml <= 0);
    toosmall = (ca && cl > 0 && (int)strlen(tcpipc.caddr) > cl) || (cn && nl > 0 && (int)strlen(tcpipc.cname) > nl)
               || (sa && sl > 0 && (int)strlen(tcpipc.saddr) > sl) || (sn && ml > 0 && (int)strlen(tcpipc.sname) > ml);
    if (badlength && toosmall) refuse("EXTRACT TCPIP with more than one condition at once");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (badlength) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    if (toosmall) refuse("EXTRACT TCPIP");
    if (ca) { memcpy(caddr, tcpipc.caddr, strlen(tcpipc.caddr)); c->len = (int)strlen(tcpipc.caddr); }
    if (cn) { memcpy(cname, tcpipc.cname, strlen(tcpipc.cname)); c->hours = (int)strlen(tcpipc.cname); }
    if (sa) { memcpy(saddr, tcpipc.saddr, strlen(tcpipc.saddr)); c->mins = (int)strlen(tcpipc.saddr); }
    if (sn) { memcpy(sname, tcpipc.sname, strlen(tcpipc.sname)); c->secs = (int)strlen(tcpipc.sname); }
    return 0;
}

/* GG-FLAGS names one of CNU SNU PORT SSL; out: GG-NUM (the SSL type as its CVDA). Only after a NORMAL GGCTCPX. */
int GGCTCPN(gg_cics *c) {
    char flags[41];
    tcpip_load();
    trim(c->flags, 40, flags);
    if (strcmp(flags, "CNU") == 0) c->num = (int)ipv4_value(tcpipc.caddr);
    else if (strcmp(flags, "SNU") == 0) c->num = (int)ipv4_value(tcpipc.saddr);
    else if (strcmp(flags, "PORT") == 0) c->num = tcpipc.port;
    else c->num = strcmp(tcpipc.ssl, "SSL") == 0 ? 1030 : strcmp(tcpipc.ssl, "NOSSL") == 0 ? 1031
                  : strcmp(tcpipc.ssl, "CLIENTAUTH") == 0 ? 1032 : 1205;
    return 0;
}

/* #4767 (X38): the WEB-RECEIVE event: the request's media type (hex; "-": none) and the bytes returned as the event's data, RESP
 * and RESP2 as the command ended (LENGERR 16: nothing returned). As CicsTask.webReceive records it. */
static void web_receive_event(const gg_cics *c, const char *body, int n) {
    char ev[WEB_TXT * 2 + 100], hx[WEB_TXT * 2 + 2];
    if (c->resp2 == 16 || (int)strlen(webreq.media) >= WEB_TXT) strcpy(hx, "-"); else web_hex(webreq.media, (int)strlen(webreq.media), hx);
    snprintf(ev, sizeof ev, "WEB-RECEIVE media=%s resp=%d resp2=%d", hx, c->resp == LENGERR ? 22 : 0, c->resp2);
    event(ev, body, n);
}

/* GG-NUM MAXLENGTH; GG-FLAGS names MEDIA given; out: GG-LEN the bytes returned. */
int GGCWRCV(gg_cics *c, char *into, int intocap, char *media, int mediacap) {
    char flags[41];
    int hm, maxl = c->num, n;
    webreq_load();
    trim(c->flags, 40, flags);
    hm = strstr(flags, "MEDIA") != NULL;
    if (!webreq.hasbody) refuse("WEB RECEIVE of a request with no body");
    if (web_received && !(web_received == 2 && strstr(flags, "CONV") && !strstr(flags, "RAW"))) refuse("a second WEB RECEIVE");
    if (maxl > intocap) refuse("WEB RECEIVE length beyond its area");
    if (hm && mediacap < 56) refuse("WEB RECEIVE length beyond its area");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (maxl <= 0) { c->resp = LENGERR; c->resp2 = 16; web_receive_event(c, NULL, 0); return 0; }
    web_received = web_received == 2 ? 3 : strstr(flags, "RAW") ? 2 : 1;
    n = webreq.bodylen > maxl ? maxl : webreq.bodylen;
    if (webreq.bodylen > maxl) { c->resp = LENGERR; c->resp2 = 57; }
    memcpy(into, webreq.body, (size_t)n);
    c->len = n;
    web_receive_event(c, webreq.body, n);
    if (hm) {
        if ((int)strlen(webreq.media) > 56) refuse("WEB RECEIVE length beyond its area");
        memset(media, ' ', 56);
        memcpy(media, webreq.media, strlen(webreq.media));
    }
    return 0;
}

/* GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in; out: the value's length); the value into `value`. */
int GGCWRDH(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int nl = c->len, vl = c->num, i, found = -1, nfound = 0, ci = 0, conds = 0;
    char n[257];
    webreq_load();
    if (nl <= 0 || nl > namecap || nl > 256) refuse("WEB READ HTTPHEADER NAMELENGTH not above zero or past its area");
    if (vl > valuecap) refuse("WEB READ HTTPHEADER length beyond its area");
    memcpy(n, name, (size_t)nl);
    n[nl] = '\0';
    for (i = 0; i < webreq.nh; i++) {
        if (strcmp(webreq.hname[i], n) == 0) { found = i; nfound++; }
        else if (strlen(webreq.hname[i]) == strlen(n)) {
            size_t j;
            int same = 1;
            for (j = 0; j < strlen(n); j++) if (tolower((unsigned char)webreq.hname[i][j]) != tolower((unsigned char)n[j])) same = 0;
            if (same) ci = 1;
        }
    }
    if (nfound == 0 && ci) refuse("WEB READ HTTPHEADER header name found only without case");
    if (nfound > 1) refuse("WEB READ HTTPHEADER two headers of the name");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (webreq.nh == 0) { c->resp = INVREQ; c->resp2 = 43; conds++; }
    else if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    if (vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (conds > 1) refuse("WEB READ HTTPHEADER with more than one condition at once");
    if (conds == 1) return 0;
    if ((int)strlen(webreq.hval[found]) > vl) refuse("WEB READ HTTPHEADER value longer than VALUELENGTH");
    memcpy(value, webreq.hval[found], strlen(webreq.hval[found]));
    c->num = (int)strlen(webreq.hval[found]);
    return 0;
}

/* GG-LEN NAMELENGTH, GG-NUM VALUELENGTH. Recorded as WEB-HEADER. */
int GGCWWRH(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int nl = c->len, vl = c->num, conds = 0, i;
    char hx[2][WEB_TXT * 2 + 2];
    webreq_load();
    if (web_sent || web_held) refuse("WEB WRITE HTTPHEADER after the response was sent");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (nl <= 0) { c->resp = LENGERR; c->resp2 = 35; conds++; }
    if (vl <= 0 || vl > 32000) { c->resp = LENGERR; c->resp2 = 55; conds++; }
    if (conds > 1) refuse("WEB WRITE HTTPHEADER with more than one condition at once");
    if (conds == 1) return 0;
    if (nl > namecap || vl > valuecap) refuse("WEB WRITE HTTPHEADER length beyond its area");
    if (nl >= WEB_TXT || vl >= WEB_TXT) refuse("WEB WRITE HTTPHEADER length beyond its area");
    for (i = 0; i < nl; i++)
        if (name[i] == ' ' || name[i] == ':') refuse("WEB WRITE HTTPHEADER name blank or holding a blank or a colon");
    web_hex(name, nl, hx[0]);
    web_hex(value, vl, hx[1]);
    {
        char ev[WEB_TXT * 4 + 100];
        snprintf(ev, sizeof ev, "WEB-HEADER name=%s value=%s resp=0 resp2=0", hx[0], hx[1]);
        event(ev, NULL, 0);
    }
    return 0;
}
#elif defined(GGCICS_WEB_PART2) /* the second part: WEB RECEIVE SET */
/* WEB RECEIVE SET(ptr) LENGTH(area) [MAXLENGTH(n)] [MEDIATYPE(area)] (X38, X47): the body as a new block the pointer addresses; GG-NUM
 * MAXLENGTH (2147483647 when not given); GG-FLAGS names MEDIA given; out: GG-LEN the bytes returned. LENGERR 16 leaves the pointer
 * as it was (ASSUMED); a body cut at MAXLENGTH is LENGERR 57 with the pointer set. */
int GGCWRCS(gg_cics *c, void **slot, char *media, int mediacap) {
    char flags[41];
    int hm, maxl = c->num, n;
    webreq_load();
    trim(c->flags, 40, flags);
    hm = strstr(flags, "MEDIA") != NULL;
    if (!webreq.hasbody) refuse("WEB RECEIVE of a request with no body");
    if (web_received && !(web_received == 2 && strstr(flags, "CONV") && !strstr(flags, "RAW"))) refuse("a second WEB RECEIVE");
    if (hm && mediacap < 56) refuse("WEB RECEIVE length beyond its area");
    if (webreq.bodylen > 268435456) refuse("WEB RECEIVE SET body beyond the limit");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (maxl <= 0) { c->resp = LENGERR; c->resp2 = 16; web_receive_event(c, NULL, 0); return 0; }
    web_received = web_received == 2 ? 3 : strstr(flags, "RAW") ? 2 : 1;
    n = webreq.bodylen > maxl ? maxl : webreq.bodylen;
    if (webreq.bodylen > maxl) { c->resp = LENGERR; c->resp2 = 57; }
    *slot = blk_new((size_t)n, BLK_RECEIVED);
    memcpy(*slot, webreq.body, (size_t)n);
    c->len = n;
    web_receive_event(c, webreq.body, n);
    if (hm) {
        if ((int)strlen(webreq.media) > 56) refuse("WEB RECEIVE length beyond its area");
        memset(media, ' ', 56);
        memcpy(media, webreq.media, strlen(webreq.media));
    }
    return 0;
}
#else /* the third part: WEB RETRIEVE, READ FORMFIELD / QUERYPARM and the browse forms */
/* WEB RETRIEVE DOCTOKEN(tok) (IBM CICS TS, EXEC CICS WEB RETRIEVE; register X41): NORMAL (the DOCTOKEN written to `tok`) for a
 * last WEB SEND that was a document send with ACTION(EVENTUAL) and no DOCDELETE -- the token names a copy of the document as it
 * was sent (ASSUMED: a new document of the task, the same token for every retrieve of that send); INVREQ RESP2 2 no WEB SEND
 * issued; NOTFND RESP2 1 the last WEB SEND was DOCDELETE or not an EVENTUAL document send. As CicsTask.webRetrieve. */
int GGCWRTV(gg_cics *c, char *tok, int toklen) {
    char t[17];
    int i;
    webreq_load();
    if (web_send_failed) refuse("WEB RETRIEVE after a WEB SEND that ended in a condition");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_issued) { c->resp = INVREQ; c->resp2 = 2; return 0; }
    if (!web_held_doc) { c->resp = NOTFND; c->resp2 = 1; return 0; }
    if (!web_held_tok) {
        doc_new(web_held_doc, web_held_doclen, t, 16);
        web_held_tok = ndocs;
    }
    snprintf(t, sizeof t, "GGDOC%011d", web_held_tok);
    for (i = 0; i < toklen && i < 16; i++) tok[i] = t[i];
    for (; i < toklen; i++) tok[i] = ' ';
    return 0;
}

/* ---- #4940 (register X38): WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (HTTPHEADER, FORMFIELD, QUERYPARM) ----
 * GG-ITEM names the kind (0 HTTPHEADER, 1 FORMFIELD, 2 QUERYPARM). FORMFIELD reads the name=value pairs of the body (a form,
 * application/x-www-form-urlencoded), QUERYPARM those of the query string (both unescaped: %XX only), HTTPHEADER the headers.
 * As CicsTask.webReadParam / webStartBrowse / webReadNext / webEndBrowse answer. */
static const char *const web_kinds[3] = {"HTTPHEADER", "FORMFIELD", "QUERYPARM"};
static int web_browse_on[3], web_browse_at[3], web_browse_end[3];
typedef struct { int n; char **name, **value; } web_pairs;

static void web_badform(int kind) {
    char m[80];
    snprintf(m, sizeof m, "WEB %s data outside the modelled name=value form", web_kinds[kind]);
    refuse(m);
}

static char *web_plain(int kind, const char *s, int len) {
    char *o = malloc((size_t)len + 1);
    int n = 0, i;
    if (!o) refuse("out of memory");
    for (i = 0; i < len; i++) {
        unsigned char ch = (unsigned char)s[i];
        if (ch == '+' || ch == ';' || ch <= ' ' || ch > '~') web_badform(kind);
        if (ch == '%') {
            int hi, lo;
            if (i + 2 >= len || !isxdigit((unsigned char)s[i + 1]) || !isxdigit((unsigned char)s[i + 2])) web_badform(kind);
            hi = web_hexval(s[i + 1]);
            lo = web_hexval(s[i + 2]);
            if (hi * 16 + lo < 32 || hi * 16 + lo > 126) web_badform(kind);
            o[n++] = (char)(hi * 16 + lo);
            i += 2;
        } else {
            o[n++] = (char)ch;
        }
    }
    o[n] = '\0';
    return o;
}

/* the pairs of the kind; 0 when the request has none */
static int web_getpairs(int kind, web_pairs *p) {
    const char *data, *piece;
    int i;
    p->n = 0;
    if (kind == 0) {
        p->name = malloc(sizeof(char *) * (size_t)(webreq.nh + 1));
        p->value = malloc(sizeof(char *) * (size_t)(webreq.nh + 1));
        for (i = 0; i < webreq.nh; i++) { p->name[i] = webreq.hname[i]; p->value[i] = webreq.hval[i]; }
        p->n = webreq.nh;
        return webreq.nh > 0;
    }
    data = kind == 2 ? webreq.query : (webreq.hasbody ? webreq.body : "");
    if (kind == 1 && data[0] != '\0' && strcasecmp(webreq.media, "application/x-www-form-urlencoded") != 0)
        refuse("WEB FORMFIELD body not application/x-www-form-urlencoded");
    if (data[0] == '\0') return 0;
    p->name = malloc(sizeof(char *) * (strlen(data) + 2));
    p->value = malloc(sizeof(char *) * (strlen(data) + 2));
    if (!p->name || !p->value) refuse("out of memory");
    for (piece = data;; ) {
        const char *amp = strchr(piece, '&'), *eq = memchr(piece, '=', amp ? (size_t)(amp - piece) : strlen(piece));
        const char *pct = memchr(piece, '%', eq ? (size_t)(eq - piece) : 0);
        size_t plen = amp ? (size_t)(amp - piece) : strlen(piece);
        if (!eq || eq == piece || pct) web_badform(kind);
        p->name[p->n] = web_plain(kind, piece, (int)(eq - piece));
        p->value[p->n] = web_plain(kind, eq + 1, (int)(plen - (size_t)(eq - piece) - 1));
        p->n++;
        if (!amp) break;
        piece = amp + 1;
    }
    return 1;
}

/* GG-ITEM kind, GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in; out: the value's whole length). */
int GGCWRDP(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int kind = c->item, nl = c->len, vl = c->num, conds = 0, i, hit = -1, nfound = 0;
    web_pairs p;
    char n[257], m[96];
    webreq_load();
    if (nl > namecap || vl > valuecap || nl > 256) {
        snprintf(m, sizeof m, "WEB READ %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_getpairs(kind, &p)) { c->resp = INVREQ; c->resp2 = 13; conds++; }
    else if (nl > 0) {
        memcpy(n, name, (size_t)nl);
        n[nl] = '\0';
        for (i = 0; i < p.n; i++) if (strcasecmp(p.name[i], n) == 0) { hit = i; nfound++; }
        if (nfound > 1) {
            snprintf(m, sizeof m, "WEB READ %s two pairs of the name", web_kinds[kind]);
            refuse(m);
        }
        if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
    }
    if (nl <= 0 || vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB READ %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) return 0;
    {
        int n2 = (int)strlen(p.value[hit]), k = n2 > vl ? vl : n2;
        memcpy(value, p.value[hit], (size_t)k);
        if (n2 > vl) { c->resp = LENGERR; c->resp2 = 5; }
        c->num = n2;
    }
    return 0;
}

/* GG-ITEM kind; GG-FLAGS names NAME given; GG-LEN NAMELENGTH. */
int GGCWSBR(gg_cics *c, char *name, int namecap) {
    int kind = c->item, nl = c->len, conds = 0, i, start = 0, nfound = 0, named, at = -1;
    web_pairs p;
    char flags[41], n[257], m[96];
    webreq_load();
    trim(c->flags, 40, flags);
    named = strstr(flags, "NAME") != NULL;
    if (named && (nl > namecap || nl > 256)) {
        snprintf(m, sizeof m, "WEB STARTBROWSE %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (web_browse_on[kind]) { c->resp = ILLOGIC; c->resp2 = kind == 0 ? 10 : 5; conds++; }
    if (named && nl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (!web_getpairs(kind, &p)) { c->resp = INVREQ; c->resp2 = kind == 0 ? 43 : 13; conds++; }
    else if (named && nl > 0) {
        memcpy(n, name, (size_t)nl);
        n[nl] = '\0';
        for (i = 0; i < p.n; i++) if (strcasecmp(p.name[i], n) == 0) { at = i; nfound++; }
        if (nfound > 1) {
            snprintf(m, sizeof m, "WEB STARTBROWSE %s two pairs of the name", web_kinds[kind]);
            refuse(m);
        }
        if (nfound == 0) { c->resp = NOTFND; c->resp2 = 1; conds++; }
        else if (strcmp(p.name[at], n) != 0) {
            snprintf(m, sizeof m, "WEB STARTBROWSE %s name found only without case", web_kinds[kind]);
            refuse(m);
        } else start = at;
    }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB STARTBROWSE %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) return 0;
    web_browse_on[kind] = 1;
    web_browse_at[kind] = start;
    web_browse_end[kind] = 0;
    return 0;
}

/* GG-ITEM kind, GG-LEN NAMELENGTH, GG-NUM VALUELENGTH (in: the areas' sizes as the program gives them; out: the pair's whole lengths). */
int GGCWRNX(gg_cics *c, char *name, int namecap, char *value, int valuecap) {
    int kind = c->item, nl = c->len, vl = c->num, conds = 0, end, cutn, cutv, k;
    web_pairs p;
    char m[96];
    webreq_load();
    if (nl > namecap || vl > valuecap) {
        snprintf(m, sizeof m, "WEB READNEXT %s length beyond its area", web_kinds[kind]);
        refuse(m);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_browse_on[kind]) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    web_getpairs(kind, &p);
    end = web_browse_at[kind] >= p.n;
    if (end && web_browse_end[kind]) {
        snprintf(m, sizeof m, "WEB READNEXT %s after ENDFILE", web_kinds[kind]);
        refuse(m);
    }
    if (nl <= 0 || vl <= 0) { c->resp = LENGERR; c->resp2 = 1; conds++; }
    if (end) { c->resp = ENDFILE; c->resp2 = 0; conds++; }
    if (conds > 1) {
        snprintf(m, sizeof m, "WEB READNEXT %s with more than one condition at once", web_kinds[kind]);
        refuse(m);
    }
    if (conds == 1) {
        if (end) web_browse_end[kind] = 1;
        return 0;
    }
    k = web_browse_at[kind];
    cutn = (int)strlen(p.name[k]) > nl;
    cutv = (int)strlen(p.value[k]) > vl;
    if (cutn && cutv) {
        snprintf(m, sizeof m, "WEB READNEXT %s name and value both truncated", web_kinds[kind]);
        refuse(m);
    }
    if ((cutn || cutv) && kind == 0) refuse("WEB READNEXT HTTPHEADER truncated");
    memcpy(name, p.name[k], cutn ? (size_t)nl : strlen(p.name[k]));
    memcpy(value, p.value[k], cutv ? (size_t)vl : strlen(p.value[k]));
    c->len = (int)strlen(p.name[k]);
    c->num = (int)strlen(p.value[k]);
    if (cutn || cutv) { c->resp = LENGERR; c->resp2 = cutn ? 4 : 5; }
    else web_browse_at[kind]++;
    return 0;
}

/* GG-ITEM kind. */
int GGCWEBR(gg_cics *c) {
    int kind = c->item;
    webreq_load();
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!web_browse_on[kind]) { c->resp = INVREQ; c->resp2 = 4; return 0; }
    web_browse_on[kind] = 0;
    return 0;
}
#endif
