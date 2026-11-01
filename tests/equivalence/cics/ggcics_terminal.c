/* #5274: the terminal: RECEIVE MAP, RECEIVE, SEND MAP / CONTROL / TEXT and CONVERSE -- split out of ggcics.c, which includes it here. */
/* RECEIVE MAP(name1) MAPSET(name2) INTO: the scenario's recorded map input. */
int GGCRECV(gg_cics *c, char *into, int intolen) {
    char map[9], mapset[9], path[4096], ev[128];
    /* #6271 (X26): after a SET the input arrives under the terminal's new UCTRANST. NOUCTRAN and TRANIDONLY (only the
     * transaction id is translated) leave the typed data as recorded; UCTRAN would upper-case it, which is not modelled. */
    if (uctranst_set && uctranst_cvda == 450)
        refuse("RECEIVE MAP after SET TERMINAL UCTRANST(UCTRAN): the upper-case translation of typed input is not modelled");
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    if (map_not_found(c, map, mapset)) return 0;
    int fresp, fresp2; /* #6271 (X71): a planned INVMPSZ / INVREQ: nothing is received, INTO is untouched */
    if (injected("RECEIVE-MAP", map, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
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
 * takes (MAXLENGTH, else LENGTH, else INTO's length; below zero, zero); on return it is the
 * LENGTH CICS sets. Longer data: under NOTRUNCATE (GG-FLAGS, #4413) the first c->len bytes,
 * NORMAL, LENGTH the length returned, and the rest kept for the next RECEIVE of the task;
 * else truncated, LENGERR, LENGTH the original length (IBM, EXEC CICS RECEIVE (3270
 * logical): "the data is truncated ... the data area specified in the LENGTH option is set
 * to the original length of data"). On an LUTYPE2 terminal (GGCICS_LU2=1: the case CSD's
 * TYPETERM DEVICE(LUTYPE2)) the RECEIVE returning the input's last byte raises EOC (RECEIVE
 * (LUTYPE2/LUTYPE3)); one leaving data retained there is undocumented and refused. The
 * operator's input is read once per task: a RECEIVE with nothing retained would wait for the
 * operator, which a scenario step cannot express, so it is recorded as RECEIVE-WAIT for the
 * driver to refuse. */
static int terminal_read = 0;
static char terminal_buf[32768];
static int terminal_at = 0, terminal_n = 0; /* the input not yet returned: terminal_buf[at..n) */
static char set_buf[32768];                  /* RECEIVE SET's data, valid until the next RECEIVE */

enum { EOC = DFHRESP_EOC };

static int terminal_receive(gg_cics *c, char *into) {
    char path[4096], ev[96], flags[41];
    if (uctranst_set) refuse("a terminal RECEIVE after SET TERMINAL UCTRANST");
    int max = c->len < 0 ? 0 : c->len, notruncate, lu2 = getenv("GGCICS_LU2") != NULL;
    trim(c->flags, 40, flags);
    notruncate = strstr(flags, "NOTRUNCATE") != NULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (terminal_at >= terminal_n && terminal_read) {
        c->len = 0;
        event("RECEIVE-WAIT", NULL, 0);
        return -1;
    }
    if (!terminal_read) {
        FILE *f;
        terminal_read = 1;
        snprintf(path, sizeof path, "%s/terminal.in", dir_in());
        f = fopen(path, "rb");
        if (f) {
            terminal_n = (int)fread(terminal_buf, 1, sizeof terminal_buf, f);
            fclose(f);
        }
        terminal_at = 0;
    }
    int n = terminal_n - terminal_at;
    int copied = n < max ? n : max;
    memcpy(into, terminal_buf + terminal_at, (size_t)copied);
    if (n > max && notruncate) {
        if (lu2) {
            c->len = 0;
            event("RECEIVE-REFUSED", NULL, 0); /* EOC on a partial RECEIVE is not documented */
            return -1;
        }
        terminal_at += copied;
        c->len = copied;
    } else {
        if (n > max) c->resp = LENGERR;
        else if (lu2) c->resp = EOC;
        terminal_at = terminal_n;
        c->len = n;
    }
    snprintf(ev, sizeof ev, "RECEIVE resp=%d len=%d copied=%d", c->resp, c->len, copied);
    event(ev, into, copied);
    return copied;
}

int GGCRECT(gg_cics *c, char *into) {
    terminal_receive(c, into);
    return 0;
}

/* RECEIVE SET(ADDRESS OF record) (#4413): the data in a buffer of the stub's, its address
 * into *ptr for the program's SET ADDRESS OF; the bytes past the data are X'00'. */
int GGCRECS(gg_cics *c, void **ptr) {
    memset(set_buf, 0, sizeof set_buf);
    terminal_receive(c, set_buf);
    *ptr = set_buf;
    return 0;
}

#include "ggcics_tempstorage.c"  /* #5274: the temporary storage family (READQ TS, WRITEQ TS) */

/* ---- the task's outputs ----------------------------------------------------------- */
/* SEND MAP: the symbolic map's bytes as the program left them (#4001: the harness resolves what
 * BMS sends from them and the BMS source); c->len is CURSOR's value, -1 when none was given. */
int GGCSMAP(gg_cics *c, char *from, int len) {
    char map[9], mapset[9], flags[41], ev[192];
    trim(c->name1, 8, map);
    trim(c->name2, 8, mapset);
    trim(c->flags, 40, flags);
    if (map_not_found(c, map, mapset)) return 0;
    int fresp, fresp2; /* #6271 (X71): a planned INVMPSZ / TSIOERR / INVREQ: nothing is sent, the screen stays as it was */
    if (injected("SEND-MAP", map, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
    snprintf(ev, sizeof ev, "SEND-MAP map=%s mapset=%s len=%d cursor=%d opts=%s", map, mapset, len, c->len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
    return 0;
}

/* SEND CONTROL (#4413): its options (GG-FLAGS) and CURSOR's value (c->len, -1 when none). */
int GGCSCTL(gg_cics *c) {
    char flags[41], ev[128];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-CONTROL cursor=%d opts=%s", c->len, flags);
    event(ev, NULL, 0);
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* the text itself: SEND TEXT's event, and CONVERSE's write (which plans no SEND TEXT fault: IBM's CONVERSE has its own conditions) */
static void send_text_event(gg_cics *c, char *from, int len) {
    char flags[41], ev[128];
    trim(c->flags, 40, flags);
    snprintf(ev, sizeof ev, "SEND-TEXT len=%d opts=%s", len, flags);
    event(ev, from, len);
    c->resp = NORMAL;
    c->resp2 = 0;
}

int GGCSTXT(gg_cics *c, char *from, int len) {
    int fresp, fresp2; /* #6271 (X71): a planned TSIOERR / INVREQ / LENGERR: nothing is sent */
    if (injected("SEND-TEXT", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        return 0;
    }
    send_text_event(c, from, len);
    return 0;
}

/* CONVERSE FROM FROMLENGTH INTO ... (#5079, X63; IBM, EXEC CICS CONVERSE (default)), as CicsTask.converse: the data written to the
 * terminal (`from`, `fromlen` bytes), recorded as a plain SEND records it, then the terminal RECEIVE of the reply INTO `into` (GG-LEN the
 * most taken, GG-FLAGS NOTRUNCATE; on return GG-LEN the reply's length). A negative `fromlen` is LENGERR with nothing sent and nothing
 * read (GG-LEN -1: ASSUMED). Refused on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE). */
/* CONVERSE's write half: 0 when the data was recorded, -1 (LENGERR, GG-LEN -1) for a negative length; the most taken is kept in GG-LEN. */
static int converse_write(gg_cics *c, char *from, int fromlen) {
    char saved[40];
    int most = c->len;
    if (getenv("GGCICS_LU2") != NULL) refuse("CONVERSE on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE)");
    if (fromlen < 0) {
        c->resp = LENGERR;
        c->resp2 = 0;
        c->len = -1;
        return -1;
    }
    memcpy(saved, c->flags, sizeof saved);
    memset(c->flags, ' ', sizeof saved);
    memcpy(c->flags, "DATA", 4);
    send_text_event(c, from, fromlen);
    memcpy(c->flags, saved, sizeof saved);
    c->len = most;
    return 0;
}

int GGCCONV(gg_cics *c, char *from, int fromlen, char *into) {
    if (converse_write(c, from, fromlen) == 0) terminal_receive(c, into);
    return 0;
}

/* RETURN: at level 1 it ends the task, with TRANSID / COMMAREA for the next one; at a lower
 * level (#4004) it returns to the linking program, and the event shows the LINK COMMAREA as
 * that program now sees it (`len` -1: the LINK had none). */
static void return_event(const char *transid, char *commarea, int len);

/* XCTL PROGRAM(name1) [COMMAREA LENGTH: GG-ITEM 1] (IBM, EXEC CICS XCTL): the program ends and
 * the target runs at the same level, with a copy of LENGTH bytes from the named area -- all of
 * them, even past the end of the item (#4008). It fails, and control stays in the issuing
 * program, with LENGERR RESP2 11 for a LENGTH outside 0-32763 and PGMIDERR RESP2 1 for a
 * program the CSD does not define. */
static void xctl_next(const char *program, char *commarea, int len);
static int program_defined(const char *program);
