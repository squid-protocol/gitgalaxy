/* #5274: WRITE and REWRITE of a file -- split out of ggcics.c, which includes it here. */
/* WRITE FILE(name1) RIDFLD FROM: a new record; DUPREC when its key is there already. */
int GGCWRIT(gg_cics *c, char *ridfld, int keylen, char *from, int fromlen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    if (injected("WRITE", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        file_event("WRITE", want, ridfld, keylen, c, from, fromlen);
        return 0;
    }
    keyed_on_esds("WRITE", want);
    if (!file_cfg(want, path, &reclen, &keyoff, &klen)) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
    } else if (find_key(path, reclen, keyoff, klen < keylen ? klen : keylen, ridfld) >= 0) {
        c->resp = DUPREC;
    } else {
        uow_save(path);
        char *rec = malloc((size_t)reclen);
        memset(rec, ' ', (size_t)reclen);
        memcpy(rec, from, (size_t)(fromlen < reclen ? fromlen : reclen));
        FILE *data = fopen(path, "ab");
        if (data && rec) fwrite(rec, 1, (size_t)reclen, data);
        if (data) fclose(data);
        if (rec && is_var(want)) len_set(path, rec + keyoff, klen, fromlen < reclen ? fromlen : reclen);  /* #6839 */
        free(rec);
        c->resp = NORMAL;
    }
    file_event("WRITE", want, ridfld, keylen, c, from, fromlen);
    return 0;
}

/* SPEC 6.2 REWRITE event: the file, RESP, RESP2 where the command is not NORMAL, and the FROM bytes as issued. */
static void rewrite_event(const gg_cics *c, const char *want, const char *from, int fromlen) {
    char ev[200];
    int n = snprintf(ev, sizeof ev, "REWRITE file=%s resp=%d", want, c->resp);
    if (c->resp != NORMAL && c->resp2) snprintf(ev + n, sizeof ev - (size_t)n, " resp2=%d", c->resp2);
    event(ev, from, fromlen);
}

/* REWRITE FILE(name1) FROM: replaces the record a READ UPDATE holds; INVREQ when none is held. */
int GGCREWR(gg_cics *c, char *from, int fromlen) {
    char want[9], path[3000];
    int reclen, keyoff, klen, fresp, fresp2;
    trim(c->name1, 8, want);
    c->resp2 = 0;
    int have = file_cfg(want, path, &reclen, &keyoff, &klen);
    const char *key = have ? from + keyoff : from;
    if (injected("REWRITE", want, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        rewrite_event(c, want, from, fromlen);
        return 0;
    }
    if (!have) {
        c->resp = FILENOTFOUND;
        c->resp2 = 1;  /* IBM: RESP2 1, the file is not defined to CICS (X75) */
    } else if (strstr(c->flags, "TOKEN") ? token_find(c->num, want) < 0 : !held_key(want, key, klen)) {
        c->resp = INVREQ;
        if (strstr(c->flags, "TOKEN")) c->resp2 = 47;
        else if (!has_hold(want)) c->resp2 = 30;  /* #5092: no READ UPDATE without a token before it (a held record of another key: unsaid, 0) */
    } else if (strstr(c->flags, "TOKEN") && (tokens[token_find(c->num, want)].klen != klen
                                              || memcmp(tokens[token_find(c->num, want)].key, key, (size_t)klen) != 0)) {
        refuse("REWRITE TOKEN FROM: a key other than the held record's");
    } else {
        long long at = find_key(path, reclen, keyoff, klen, key);
        if (at < 0) {
            c->resp = NOTFND;
        } else {
            uow_save(path);
            char *rec = malloc((size_t)reclen);
            memset(rec, ' ', (size_t)reclen);
            memcpy(rec, from, (size_t)(fromlen < reclen ? fromlen : reclen));
            FILE *data = fopen(path, "r+b");
            if (data && rec && fseek(data, (long)(at * reclen), SEEK_SET) == 0) fwrite(rec, 1, (size_t)reclen, data);
            if (data) fclose(data);
            if (is_var(want)) len_set(path, key, klen, fromlen < reclen ? fromlen : reclen);  /* #6839 */
            free(rec);
            if (strstr(c->flags, "TOKEN")) tokens[token_find(c->num, want)].id = 0;
            else release(want);
            c->resp = NORMAL;
        }
    }
    if (c->resp == NORMAL) file_set_end("READ", want);  /* IBM: a READ SET pointer is valid until a corresponding REWRITE completes */
    rewrite_event(c, want, from, fromlen);
    return 0;
}

/* A Db2 case's SQL stub (tests/equivalence/db2/ggsql.c), when linked: its Db2 work belongs to the same unit of work.
 * A weak no-op DEFINITION, which ggsql.c's strong one overrides at link time. (A weak undefined REFERENCE checked
 * against NULL links on ELF but not on macOS, whose linker still requires it to resolve.) */
__attribute__((weak)) void ggsql_uow_end(int rollback) { (void)rollback; }
/* #4892 (W5): and the MQ model's (tests/equivalence/mq/ggmq.c), when a program CALLs MQI: the same weak default. */
__attribute__((weak)) void ggmq_uow_end(int rollback) { (void)rollback; }

static void td_uow_end(int rollback); /* #5168 */
