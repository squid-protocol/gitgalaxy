/* #5274: program control: INQUIRE PROGRAM, XCTL, RETURN, the task dispatcher, LINK and its return -- split out of ggcics.c, which includes it here. */
/* #4023 follow-up: INQUIRE PROGRAM(name1) -- NORMAL for a program the CSD defines, else PGMIDERR (or the condition
 * faults.cfg injects). It changes nothing a task can see but its RESP, so it records no event. */
int GGCINQP(gg_cics *c) {
    char program[9];
    int fresp, fresp2;
    trim(c->name1, 8, program);
    c->resp = program_defined(program) ? NORMAL : PGMIDERR;
    c->resp2 = 0;
    if (injected("INQUIRE", program, &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    }
    /* #4768 (X34): STATUS, the definition's CVDA -- ENABLED (23), the DEFINE PROGRAM default; no run states a DISABLED one */
    if (c->resp == NORMAL) c->num = 23;
    return 0;
}

static int channel_named(const char *name, int create);
static void xctl_channel(int chan);

int GGCXCTL(gg_cics *c, char *commarea, int len) {
    char program[9], ev[128], flags[41], name[17];
    int has = c->item != 0, fresp, fresp2, chan = 0;
    trim(c->flags, 40, flags);
    if (strstr(flags, "CHANNEL")) { /* #4270: XCTL CHANNEL -- the target's current channel, made if absent */
        trim(c->chan, 16, name);
        chan = channel_named(name, 1);
    }
    trim(c->name1, 8, program);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    else if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; }
    else if (injected("XCTL", program, &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; }  /* #4049 */
    snprintf(ev, sizeof ev, "XCTL program=%s len=%d area=%d resp=%d resp2=%d", program, has ? len : 0, has,
             c->resp, c->resp2);
    event(ev, has ? commarea : NULL, has && len > 0 && len <= 65535 ? len : 0);
    if (c->resp != NORMAL) return 0;
    ended = 1;
    xctl_next(program, has ? commarea : NULL, has ? len : 0);
    xctl_channel(chan);
    return 0;
}

#include "ggcics_conditions.c"  /* #5274: the conditions and abends family (the per-level handler state, GGCPENT, HANDLE CONDITION and ABEND, PUSH/POP HANDLE) */

#include "ggcics_transientdata.c"  /* #5274: the transient data family (READQ/WRITEQ/DELETEQ TD, SET/INQUIRE TDQUEUE) */

/* ---- program levels: LINK, XCTL and the dispatcher (#4004) ---------------------------- */
static void return_event(const char *transid, char *commarea, int len) {
    char ev[96];
    level *L = &levels[lvl];
    L->state = DONE;
    if (lvl == 0) {
        snprintf(ev, sizeof ev, "RETURN level=1 transid=%s len=%d", transid, len);
        ended = 1;
        event(ev, commarea, len);
    } else {
        snprintf(ev, sizeof ev, "RETURN level=%d transid= len=%d", lvl + 1, L->link_area ? L->link_len : -1);
        event(ev, L->link_area, L->link_area ? L->link_len : 0);
    }
}

/* #6271 (X71): a plain RETURN TRANSID the program tests (GG-ITEM 2: it codes RESP) can fail on a planned INVREQ (1, 2, 4,
 * 200) / LENGERR (11, 26, 27) at the highest level; the task goes on and nothing is passed to the next one. A plain RETURN
 * that codes no RESP never consults the plan (its failure would be an abend IBM does not describe: not planned). */
int GGCRETN(gg_cics *c, char *commarea, int len) {
    char transid[9], ev[128];
    int fresp, fresp2;
    trim(c->name1, 8, transid);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (c->item == 2 && lvl == 0 && injected("RETURN", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
        snprintf(ev, sizeof ev, "RETURN level=1 transid=%s resp=%d resp2=%d", transid, c->resp, c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    return_event(transid, commarea, len);
    return 0;
}

/* RETURN TRANSID(name1) [COMMAREA LENGTH: GG-ITEM 1] IMMEDIATE (#4270, register X27; IBM, EXEC CICS RETURN): the next task
 * is attached at once, ahead of any terminal input, with the COMMAREA. INVREQ RESP2 1 for a task with no terminal
 * ($GGCICS_FACILITY empty; unstated: refused), INVREQ RESP2 2 below the highest level, LENGERR RESP2 11 for a length
 * outside 0-32763 -- the program then goes on. The two INVREQs together are not stated by IBM: refused. */
int GGCRETI(gg_cics *c, char *commarea, int len) {
    char transid[9], ev[128];
    const char *own = getenv("GGCICS_FACILITY");
    int has = c->item != 0, no_terminal;
    trim(c->name1, 8, transid);
    if (!own) refuse("RETURN IMMEDIATE: the task's terminal is not stated for this task");
    no_terminal = !own[0];
    if (no_terminal && lvl > 0)
        refuse("RETURN IMMEDIATE below the highest level in a task with no terminal: IBM lists INVREQ RESP2 1 and 2 "
               "for it and does not say which");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (lvl > 0) { c->resp = INVREQ; c->resp2 = 2; }
    else if (no_terminal) { c->resp = INVREQ; c->resp2 = 1; }
    else if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    int fresp, fresp2; /* #6271 (X71): a planned INVREQ (1, 2, 4, 200) / LENGERR (11, 26, 27): the program goes on */
    if (c->resp == NORMAL && injected("RETURN", "-", &fresp, &fresp2)) {
        c->resp = fresp;
        c->resp2 = fresp2;
    }
    if (c->resp != NORMAL) {
        snprintf(ev, sizeof ev, "RETURN level=%d transid=%s immediate=1 resp=%d resp2=%d", lvl + 1, transid, c->resp,
                 c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    levels[lvl].state = DONE;
    ended = 1;
    snprintf(ev, sizeof ev, "RETURN level=1 transid=%s len=%d immediate=1", transid, has ? len : 0);
    event(ev, has ? commarea : NULL, has && len > 0 ? len : 0);
    return 0;
}

static void xctl_next(const char *program, char *commarea, int len) {
    level *L = &levels[lvl];
    /* #4816 (X39): a LINKed program XCTLing with (part of) the area its caller passed: IBM does not say whether the
     * target then addresses that storage or a copy (XCTL COMMAREA: "the contents of the data-area are passed") */
    if (commarea && lvl > 0 && L->link_area && commarea >= L->link_area
        && commarea < L->link_area + L->link_len)
        refuse("XCTL passing the COMMAREA its LINK caller passed");
    snprintf(L->next_invoker, sizeof L->next_invoker, "%s", L->prog);  /* the XCTLing program */
    L->state = XCTLED;
    snprintf(L->next, sizeof L->next, "%s", program);
    L->next_len = commarea && len > 0 ? len : 0;
    L->next_area = NULL;
    if (L->next_len > 0) {
        L->next_area = malloc((size_t)L->next_len);
        if (L->next_area) memcpy(L->next_area, commarea, (size_t)L->next_len);
    }
    L->next_area_set = 1;
}

/* Whether the CSD defines `program` (programs.cfg; SPEC 2: program autoinstall is off). */
static int program_defined(const char *program) {
    char path[4096], line[64], name[64];
    int found = 0;
    snprintf(path, sizeof path, "%s/programs.cfg", dir_in());
    FILE *f = fopen(path, "r");
    if (!f) return 1;
    while (!found && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s", name) == 1 && strcmp(name, program) == 0) found = 1;
    }
    fclose(f);
    return found;
}

/* #4270: EIBTASKN, the task's number, a fact of the run whoever runs the task states ($GGCICS_TASKN, as the
 * Java side's CicsTask.withTaskNumber; oracle_assumptions.md X21). The drivers CALL it after INITIALIZE DFHEIBLK
 * and MOVE GG-NUM TO EIBTASKN. IBM: "the task number assigned to the task by CICS", PIC S9(7) COMP-3: a value
 * that is not 0 to 9999999 is refused; unstated, 0 (the INITIALIZEd EIB's, as before). */
int GGCTASKN(gg_cics *c) {
    const char *env = getenv("GGCICS_TASKN");
    char *end = NULL;
    long long n = 0;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (env) {
        n = strtoll(env, &end, 10);
        if (!env[0] || *end || n < 0 || n > 9999999) refuse("EIBTASKN: $GGCICS_TASKN is not a task number");
    }
    c->num = (int)n;
    return 0;
}

/* The driver: the task's first program (GG-NAME1) and its COMMAREA length (GG-LEN). */
int GGCTASK(gg_cics *c) {
    lvl = 0;
    memset(&levels[0], 0, sizeof levels[0]);
    trim(c->name1, 8, levels[0].next);
    levels[0].next_len = c->len;
    levels[0].pending = 1;
    return 0;
}

/* GGCRUN asks what to run at this level: GG-ITEM 1 with the program (GG-NAME1), its EIBCALEN
 * (GG-LEN) and the COMMAREA's address (*area; NULL for none), or 0 when the level is done. */
int GGCNEXT(gg_cics *c, char **area) {
    level *L = &levels[lvl];
    c->item = 0;
    if (!L->pending || terminated || unwind_to >= 0) return 0;
    L->pending = 0;
    memset(c->name1, ' ', 8);
    memcpy(c->name1, L->next, strlen(L->next));
    c->len = L->next_len;
    if (L->next_area_set) *area = L->next_area;
    else if (L->next_len <= 0) *area = NULL; /* level 1 with EIBCALEN 0: no COMMAREA */
    if (L->state == XCTLED) { /* #4270: an XCTL's target: the channel it passed, the rest left behind */
        channel_pass(L, L->next_chan);
        L->next_chan = 0;
    }
    memcpy(L->prog, L->next, sizeof L->prog);
    memcpy(L->invoker, L->next_invoker, sizeof L->invoker);
    L->next_invoker[0] = 0;
    L->state = RUNNING;
    c->item = 1;
    return 0;
}

/* The level's program has returned to GGCRUN: after an XCTL its target runs next; after a
 * GOBACK with no RETURN, that GOBACK was the RETURN; after an abend, nothing. */
int GGCPEND(gg_cics *c) {
    level *L = &levels[lvl];
    (void)c;
    if (terminated || unwind_to >= 0) return 0;
    if (L->state == XCTLED) { L->pending = 1; return 0; }
    if (L->state == RUNNING) return_event("", NULL, 0);
    return 0;
}

/* GGCRUN has no program by that name: the case's translated programs do not include it. */
int GGCNOPG(gg_cics *c) {
    char program[9], ev[64];
    trim(c->name1, 8, program);
    snprintf(ev, sizeof ev, "NOPROGRAM target=%s", program);
    event(ev, NULL, 0);
    terminated = ended = 1;
    return 0;
}

/* LINK PROGRAM(name1) [COMMAREA(area) LENGTH(len): GG-ITEM 1] (IBM, EXEC CICS LINK):
 * LENGERR RESP2 11 for a length outside 0-32763, PGMIDERR RESP2 1 for a program the CSD does
 * not define; else a new level, whose program gets the caller's area itself (the COMMAREA is
 * passed by reference) and EIBCALEN = LENGTH (0 without COMMAREA). The event carries the
 * area's bytes as the command is issued. */
int GGCLINK(gg_cics *c, char *area) {
    char program[9], ev[128], flags[41], name[17];
    int has = c->item != 0, len = has ? c->len : 0, chan = 0, fresp, fresp2;
    trim(c->name1, 8, program);
    trim(c->flags, 40, flags);
    if (strstr(flags, "CHANNEL")) { /* #4270: LINK CHANNEL -- made empty if absent ("a new empty channel is created") */
        trim(c->chan, 16, name);
        chan = channel_named(name, 1);
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    c->go_to = 0;
    if (has && (len < 0 || len > 32763)) { c->resp = LENGERR; c->resp2 = 11; }
    else if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; }
    else if (lvl + 1 >= MAX_LEVELS) { c->resp = INVREQ; }
    else if (injected("LINK", program, &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; }  /* #4648: as XCTL's */
    snprintf(ev, sizeof ev, "LINK target=%s len=%d area=%d resp=%d resp2=%d", program, len, has, c->resp, c->resp2);
    event(ev, has ? area : NULL, has && len > 0 && len <= 32763 ? len : 0);
    /* #6271 (X70): a planned abend (`LINK PROGRAM 1 -1 0 ABCODE`) went to the exit or ended the task: the callee never runs */
    if (c->resp != NORMAL || c->go_to != 0 || terminated) return 0;
    const char *linker = current_program();
    char by[9];
    snprintf(by, sizeof by, "%s", linker);
    lvl++;
    memset(&levels[lvl], 0, sizeof levels[lvl]);
    level *L = &levels[lvl];
    snprintf(L->next, sizeof L->next, "%s", program);
    snprintf(L->next_invoker, sizeof L->next_invoker, "%s", by);
    L->next_len = len;
    L->next_area = has ? area : NULL;
    L->next_area_set = 1;
    L->link_area = has ? area : NULL;
    L->link_len = len;
    L->pending = 1;
    L->gen = ++link_gen;
    channel_pass(L, chan); /* #4270: the callee's channel, the only one in its scope (0: none) */
    return 0;
}

/* Back in the linking program: the level is gone. After an abend whose exit is at this level,
 * GG-GOTO is the exit's label; at a level above, or with no exit, -1 (leave this program too). */
int GGCLRET(gg_cics *c) {
    if (lvl > 0) lvl--;
    c->resp = NORMAL;
    c->resp2 = 0;
    c->go_to = 0;
    if (terminated) {
        c->go_to = -1;
    } else if (unwind_to >= 0) {
        if (lvl <= unwind_to) {
            c->go_to = unwind_goto;
            unwind_to = -1;
        } else {
            c->go_to = -1;
        }
    }
    return 0;
}

#include "ggcics_containers.c"  /* #5274: the channels / containers family */

/* ---- interval control (#4006) ---------------------------------------------------------- *
 * The virtual clock is $GGCICS_NOW; a task takes no time (SPEC 4). START records its request
 * as an event (with its expiry); the runner's scheduler keeps the requests and dispatches
 * them. RETRIEVE reads the data of the requests the task was started for. */
enum { TRANSIDERR = DFHRESP_TRANSIDERR, TERMIDERR = DFHRESP_TERMIDERR, IOERR = DFHRESP_IOERR,
       ENVDEFERR = DFHRESP_ENVDEFERR };
