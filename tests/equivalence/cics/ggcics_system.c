/* #5274: INQUIRE URIMAP, VERIFY PASSWORD, WRITE OPERATOR and DOCUMENT -- split out of ggcics.c, which includes it here. */
static int urimap_get(int want, char fields[3][300]) {
    const char *env = getenv("GGCICS_URIMAPS");
    char line[1024];
    int n = 0, found = 0;
    if (!env) refuse("INQUIRE URIMAP: the installed URIMAP definitions are not stated for this task");
    FILE *f = fopen(env, "r");
    if (!f) refuse("INQUIRE URIMAP: the installed URIMAP definitions are not stated for this task");
    while (fgets(line, sizeof line, f)) {
        char a[300], b[300], p[300];
        if (sscanf(line, "%299s %299s %299s", a, b, p) != 3) continue;
        if (n == want && fields) {
            snprintf(fields[0], 300, "%s", a);
            snprintf(fields[1], 300, "%s", strcmp(b, "-") == 0 ? "" : b);
            snprintf(fields[2], 300, "%s", p);
            found = 1;
        }
        n++;
    }
    fclose(f);
    return fields ? found : n;
}

int GGCURIB(gg_cics *c) {
    char want[41];
    trim(c->flags, 40, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    urimap_get(-1, NULL); /* (refuses when the definitions are not stated) */
    if (strcmp(want, "DIRECT") == 0) { /* #4768 (X34): URIMAP(name1), NOTFND RESP2 3 when it is not installed */
        char name[9], fields[3][300];
        trim(c->name1, 8, name);
        for (int i = 0; urimap_get(i, fields); i++) {
            if (strcmp(fields[0], name) == 0) { memcpy(urimap_now, fields, sizeof urimap_now); return 0; }
        }
        c->resp = NOTFND;
        c->resp2 = 3;
        return 0;
    }
    if (strcmp(want, "START") == 0) {
        if (urimap_at >= 0) { c->resp = DFHRESP_ILLOGIC; c->resp2 = 1; return 0; }
        urimap_at = 0;
        return 0;
    }
    if (urimap_at < 0) refuse("INQUIRE URIMAP NEXT or END with no browse started");
    if (strcmp(want, "END") == 0) { urimap_at = -1; return 0; }
    if (!urimap_get(urimap_at, urimap_now)) { c->resp = DFHRESP_END; c->resp2 = 2; return 0; }
    urimap_at++;
    return 0;
}

/* The definition the last NEXT returned: GG-FLAGS names URIMAP (8 characters), PATH (255) or TRANSACTION (4); the value,
 * blank-padded, goes to the program's area -- at most its length (IBM states no padding for a short value: blanks). */
int GGCURIP(gg_cics *c, char *area, int len) {
    char want[41];
    int at = 0, width = 8, n; /* urimap_now: name, transaction, path */
    trim(c->flags, 40, want);
    if (strcmp(want, "PATH") == 0) { at = 2; width = 255; }
    else if (strcmp(want, "TRANSACTION") == 0) { at = 1; width = 4; }
    n = len < width ? len : width;
    for (int i = 0; i < n; i++) area[i] = ' ';
    for (int i = 0; i < n && urimap_now[at][i]; i++) area[i] = urimap_now[at][i];
    return 0;
}

/* #5859 (X32): EXEC CICS VERIFY PASSWORD USERID(userid) PASSWORD(password). The region has no security manager, so the verdict
 * is the planned `VERIFY USERID NTH RESP 0` line a scenario states for the USERID (trailing blanks dropped), the way
 * CicsTask.verifyPassword reads it; none stated is refused by name. The password is not compared. Event, as the task logs it. */
int GGCVER(gg_cics *c, char *userid, int ulen) {
    char id[33], ev[96];
    int fresp, fresp2, n = ulen < 32 ? ulen : 32;
    c->resp = NORMAL;
    c->resp2 = 0;
    while (n > 0 && userid[n - 1] == ' ') n--;
    memcpy(id, userid, (size_t)n);
    id[n] = '\0';
    if (!injected("VERIFY", id, &fresp, &fresp2)) {
        snprintf(ev, sizeof ev, "VERIFY PASSWORD with no stated verdict for USERID '%s'", id);
        refuse(ev);
    }
    c->resp = fresp;
    c->resp2 = fresp2;
    snprintf(ev, sizeof ev, "VERIFY-PASSWORD userid=%s resp=%d", id, c->resp);
    event(ev, NULL, 0);
    return 0;
}

/* WRITE OPERATOR TEXT(from) of GG-LEN bytes: a message to the console, recorded with its text. A text IBM reformats
 * (DFHnnnn / DFHaannnn) or splits (over 113 characters) is refused. #5859 (X32), as CicsTask.writeOperator: GG-FLAGS
 * TEXTLENGTH says GG-LEN is the TEXTLENGTH value (IBM: 0-690, else INVREQ RESP2 1; the text is the first GG-LEN bytes of the
 * area, and one past the area is refused); GG-FLAGS ROUTES says `routes` holds GG-NUM route codes (each 1-28, else INVREQ
 * RESP2 3; GG-NUM below 1 or past the area is a case IBM leaves open, refused). The routes are no observable (the
 * console is not modelled) and EVENTUAL changes only when the operator acts. `area` is the text area's size, `routes_len`
 * the routes area's. */
int GGCWTO(gg_cics *c, char *from, int area, char *routes, int routes_len) {
    char ev[64];
    int n, k = 0, i;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(c->flags, "TEXTLENGTH")) {
        if (c->len < 0 || c->len > 690) {
            c->resp = INVREQ;
            c->resp2 = 1;
            return 0;
        }
        if (c->len > area) refuse("WRITE OPERATOR TEXTLENGTH past the text area");
    }
    if (strstr(c->flags, "ROUTES")) {
        if (c->num < 1 || c->num > routes_len) refuse("WRITE OPERATOR NUMROUTES IBM leaves open");
        for (i = 0; i < c->num; i++)
            if ((unsigned char)routes[i] < 1 || (unsigned char)routes[i] > 28) {
                c->resp = INVREQ;
                c->resp2 = 3;
                return 0;
            }
    }
    n = c->len;
    while (n > 0 && from[n - 1] == ' ') n--;
    if (c->len > 113) refuse("WRITE OPERATOR text IBM reformats");
    if (n >= 7 && strncmp(from, "DFH", 3) == 0) {
        k = 3;
        if (from[3] >= 'A' && from[3] <= 'Z' && from[4] >= 'A' && from[4] <= 'Z') k = 5;
        else if (from[3] >= 'a' && from[3] <= 'z' && from[4] >= 'a' && from[4] <= 'z') k = 5;
        if (n >= k + 4 && from[k] >= '0' && from[k] <= '9' && from[k + 1] >= '0' && from[k + 1] <= '9'
            && from[k + 2] >= '0' && from[k + 2] <= '9' && from[k + 3] >= '0' && from[k + 3] <= '9')
            refuse("WRITE OPERATOR text IBM reformats");
    }
    snprintf(ev, sizeof ev, "WRITE-OPERATOR len=%d resp=0", c->len);
    event(ev, from, c->len);
    return 0;
}

/* ---- #4769 zECS: the document handler's DOCUMENT CREATE and DOCUMENT RETRIEVE (IBM CICS TS, EXEC CICS DOCUMENT
 * CREATE, DOCUMENT RETRIEVE; register X33) ----
 * A document is the bytes the task built, named by a 16-byte DOCTOKEN ("GGDOC" and eleven digits); it lasts as long as
 * the task (one process here). The installed DOCTEMPLATEs are a fact the runner states: the file $GGCICS_DOCTEMPLATES
 * names, one `NAME TEXT-IN-HEX` per line (the text, hex, because it can hold line ends; '-' for an empty text); unstated, refused. */
static unsigned char **docs;
static int *doc_len;
static int *doc_dead; /* #4941: deleted by a WEB SEND DOCSTATUS(DOCDELETE) */
static int ndocs = 0, doc_cap = 0;
/* #6072: IBM sets no count of documents a task may create (storage alone limits it), so the tables grow; ZECS000 holds 501. */

static int doc_new(const unsigned char *data, int len, char *tok, int toklen) {
    char t[17];
    int i;
    if (ndocs >= doc_cap) {
        int cap = doc_cap ? doc_cap * 2 : 64;
        unsigned char **nd = realloc(docs, (size_t)cap * sizeof *docs);
        int *nl, *nx;
        if (!nd) refuse("DOCUMENT CREATE: out of storage");
        docs = nd;
        nl = realloc(doc_len, (size_t)cap * sizeof *doc_len);
        if (!nl) refuse("DOCUMENT CREATE: out of storage");
        doc_len = nl;
        nx = realloc(doc_dead, (size_t)cap * sizeof *doc_dead);
        if (!nx) refuse("DOCUMENT CREATE: out of storage");
        doc_dead = nx;
        memset(doc_dead + doc_cap, 0, (size_t)(cap - doc_cap) * sizeof *doc_dead);
        doc_cap = cap;
    }
    docs[ndocs] = malloc(len > 0 ? (size_t)len : 1);
    memcpy(docs[ndocs], data, (size_t)(len > 0 ? len : 0));
    doc_len[ndocs] = len;
    ndocs++;
    snprintf(t, sizeof t, "GGDOC%011d", ndocs);
    for (i = 0; i < toklen && i < 16; i++) tok[i] = t[i];
    for (; i < toklen; i++) tok[i] = ' ';
    return 0;
}

/* The text the template `name` yields (malloc'd, `*len` bytes); NULL when it is not installed. */
static unsigned char *doctemplate(const char *name, int *len) {
    const char *env = getenv("GGCICS_DOCTEMPLATES");
    char line[65536], n[100], hex[65000];
    FILE *f;
    if (!env) refuse("DOCUMENT CREATE: the installed document templates are not stated for this task");
    f = fopen(env, "r");
    if (!f) refuse("DOCUMENT CREATE: the installed document templates are not stated for this task");
    while (fgets(line, sizeof line, f)) {
        int hl, k;
        unsigned char *out;
        hex[0] = '\0';
        if (sscanf(line, "%99s %64999s", n, hex) < 1 || strcmp(n, name) != 0) continue;
        fclose(f);
        hl = strcmp(hex, "-") == 0 ? 0 : (int)strlen(hex);
        out = malloc((size_t)(hl / 2 + 1));
        for (k = 0; k + 1 < hl; k += 2) {
            unsigned int b;
            sscanf(hex + k, "%2x", &b);
            out[k / 2] = (unsigned char)b;
        }
        *len = hl / 2;
        return out;
    }
    fclose(f);
    return NULL;
}

/* Does `text` (`left` bytes) begin with `word`, in either case? */
static int doc_word(const unsigned char *text, int left, const char *word) {
    int n = (int)strlen(word), i;
    if (left < n) return 0;
    for (i = 0; i < n; i++)
        if (tolower(text[i]) != word[i]) return 0;
    return 1;
}

/* DOCUMENT CREATE DOCTOKEN(tok): GG-FLAGS names the source -- EMPTY; DATA (TEXT / BINARY: `src`, GG-LEN bytes, `srclen`
 * the area's own length; a negative GG-LEN is LENGERR RESP2 1, one past the area is refused); TEMPLATE (`src` is the
 * 48-byte name, `srclen` its length: NOTFND RESP2 3 when not installed). The token goes to `tok` (16 bytes, blank-padded)
 * on NORMAL only. */
int GGCDOCC(gg_cics *c, char *src, int srclen, char *tok, int toklen) {
    char flags[41];
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strcmp(flags, "DATA") == 0) {
        if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
        if (c->len > srclen) refuse("DOCUMENT CREATE LENGTH past the TEXT / BINARY area");
        return doc_new((unsigned char *)src, c->len, tok, toklen);
    }
    if (strcmp(flags, "TEMPLATE") == 0) {
        char name[100];
        int len = 0, i;
        unsigned char *text;
        trim(src, srclen < 99 ? srclen : 99, name);
        text = doctemplate(name, &len);
        if (!text) { c->resp = NOTFND; c->resp2 = 3; return 0; }
        for (i = 0; i < len; i++) {
            if (text[i] == '#' && (doc_word(text + i + 1, len - i - 1, "set") || doc_word(text + i + 1, len - i - 1, "include")
                                   || doc_word(text + i + 1, len - i - 1, "echo")))
                refuse("DOCUMENT CREATE TEMPLATE text with symbols or template commands");
            if (text[i] == '&' && i + 1 < len && isalpha(text[i + 1])) {
                int j = i + 1;
                while (j < len && (isalnum(text[j]) || text[j] == '.' || text[j] == '_' || text[j] == '-')) j++;
                if (j < len && text[j] == ';')
                    refuse("DOCUMENT CREATE TEMPLATE text with symbols or template commands");
            }
        }
        doc_new(text, len, tok, toklen);
        free(text);
        return 0;
    }
    return doc_new((unsigned char *)"", 0, tok, toklen);
}

/* DOCUMENT RETRIEVE DOCTOKEN(tok) INTO(into) MAXLENGTH(GG-LEN) DATAONLY: at most GG-LEN bytes go INTO (the rest of INTO
 * is left alone), GG-LEN is set to the document's length -- the length it needs when truncated, LENGERR RESP2 2. NOTFND
 * RESP2 1 for a token CICS did not give; LENGERR RESP2 1 for a negative MAXLENGTH (GG-LEN left alone). More bytes than
 * INTO holds are refused. */
int GGCDOCR(gg_cics *c, char *tok, int toklen, char *into, int intolen) {
    char want[100];
    int i, n, copied;
    c->resp = NORMAL;
    c->resp2 = 0;
    trim(tok, toklen < 99 ? toklen : 99, want);
    for (i = 0; i < ndocs; i++) {
        char t[17];
        snprintf(t, sizeof t, "GGDOC%011d", i + 1);
        if (strcmp(t, want) == 0) break;
    }
    if (i == ndocs || doc_dead[i]) { c->resp = NOTFND; c->resp2 = 1; return 0; }
    if (c->len < 0) { c->resp = LENGERR; c->resp2 = 1; return 0; }
    n = doc_len[i];
    copied = n < c->len ? n : c->len;
    if (copied > intolen) refuse("DOCUMENT RETRIEVE MAXLENGTH beyond INTO");
    memcpy(into, docs[i], (size_t)copied);
    if (n > c->len) { c->resp = LENGERR; c->resp2 = 2; }
    c->len = n;
    return 0;
}

static void web_flush(void); /* #4941 */
