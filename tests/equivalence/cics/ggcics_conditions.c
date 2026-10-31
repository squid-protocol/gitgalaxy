/* #5274: the conditions and abends family (the per-level handler state, GGCPENT, HANDLE CONDITION and ABEND, PUSH/POP HANDLE, HANDLE AID, ASSIGN) -- split out of ggcics.c, which includes it
 * where the block sat. */
/* ---- conditions and abends (#4003) --------------------------------------------------- *
 * Each program level (a LINK level, #4004) has its own handler state: per condition
 * (DFHRESP code) the index of its HANDLE CONDITION label, IGNORE (-1) or the default (0);
 * its HANDLE ABEND LABEL exit; and a PUSH HANDLE stack of saved states. The translator
 * numbers the labels a program's HANDLE commands name, and after a command that raised a
 * condition issues GO TO <labels> DEPENDING ON GG-GOTO (IBM's translator does the same
 * after the HANDLE command, with DFHEIGDI): the transfer is a plain COBOL GO TO.
 */
#define MAX_LEVELS 32
#define MAX_PUSH 16
#define NCOND 130
enum { ERRCOND = DFHRESP_ERROR }; /* HANDLE CONDITION ERROR's slot */

typedef struct {
    short cond[NCOND]; /* >0 label index, -1 IGNORE, 0 default */
    short aid[40];     /* HANDLE AID (#4007): per key (aid_keys), its label index, 0 none, -1 deactivated (#4414) */
    int exit_label;    /* HANDLE ABEND LABEL index, 0 none */
    int exit_active;   /* deactivated when it gets control (IBM, abend recovery) */
    char exit_name[31];
} handlers;

enum { RUNNING = 0, DONE = 1, XCTLED = 2 };

typedef struct {
    char prog[9];
    char invoker[9];         /* the program that LINKed / XCTLed to this one (ASSIGN INVOKINGPROG); "" at the first */
    char next_invoker[9];    /* the invoker of the program pending at this level */
    handlers h;
    handlers pushed[MAX_PUSH];
    int npushed;
    int state;               /* RUNNING, DONE (RETURN, GOBACK) or XCTLED (#4004) */
    int pending;             /* a program is to run at this level: next / next_len / next_area */
    char next[9];
    int next_len, next_area_set;
    char *next_area;
    char *link_area;         /* the LINK COMMAREA: the linking program's own storage (NULL: none) */
    int link_len;
    /* #4270: the channel the level's program was passed (index + 1 into chans; 0: none), the channels in its
     * scope, and the names an XCTL left behind (naming one is refused: IBM does not document their scope) */
    int cur;
    int scope[32];
    int nscope;
    char dropped[32][17];
    int ndropped;
    int next_chan;           /* the channel an XCTL passes to the program pending at this level (index + 1) */
    int gen;                 /* #4951: which LINKed program this level runs (0: the task's first), the owner of its browses */
} level;

static level levels[MAX_LEVELS];
static int link_gen = 0; /* #4951: the last LINK's generation */
static void channel_pass(level *L, int passed); /* #4270 */
static int lvl = 0; /* the current level, 0 = level 1 */
static char task_abcode[5] = "    ";

static const char *current_program(void) { return levels[lvl].prog; }

/* The program's entry: the translator names it (GG-NAME1) for the level it runs at. It starts
 * with no handlers of its own: "The HANDLE CONDITION options are not inherited by the linked-to
 * program" (IBM, LINK), nor by the program XCTLed to. */
int GGCPENT(gg_cics *c) {
    level *L = &levels[lvl];
    trim(c->name1, 8, L->prog);
    memset(&L->h, 0, sizeof L->h);
    L->npushed = 0;
    L->state = RUNNING;
    return 0;
}

/* HANDLE CONDITION / IGNORE CONDITION: condition GG-NUM gets label GG-ITEM (0: the default
 * action again, -1: IGNORE). The last HANDLE or IGNORE for a condition wins (IBM, IGNORE
 * CONDITION: "until a HANDLE CONDITION command for the same condition is encountered"). */
int GGCHCND(gg_cics *c) {
    if (c->num > 0 && c->num < NCOND) levels[lvl].h.cond[c->num] = (short)c->item;
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* HANDLE ABEND LABEL (GG-NAME2 'LABEL', GG-ITEM its index, GG-FLAGS its name), CANCEL or
 * RESET (IBM, EXEC CICS HANDLE ABEND). */
int GGCHABN(gg_cics *c) {
    char how[9];
    handlers *h = &levels[lvl].h;
    trim(c->name2, 8, how);
    if (strcmp(how, "LABEL") == 0) {
        h->exit_label = c->item;
        h->exit_active = 1;
        trim(c->flags, 30, h->exit_name);
    } else if (strcmp(how, "CANCEL") == 0) {
        h->exit_active = 0;
    } else if (h->exit_label) { /* RESET: reactivate the exit cancelled, or taken */
        h->exit_active = 1;
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* PUSH HANDLE saves the level's HANDLE CONDITION, IGNORE CONDITION and HANDLE ABEND state and
 * suspends it; POP HANDLE restores the last one saved, INVREQ when none is (IBM, PUSH / POP). */
int GGCPUSH(gg_cics *c) {
    level *L = &levels[lvl];
    c->resp2 = 0;
    if (L->npushed >= MAX_PUSH) { c->resp = INVREQ; return 0; }
    L->pushed[L->npushed++] = L->h;
    memset(&L->h, 0, sizeof L->h);
    c->resp = NORMAL;
    return 0;
}

int GGCPOP(gg_cics *c) {
    level *L = &levels[lvl];
    c->resp2 = 0;
    if (L->npushed == 0) { c->resp = INVREQ; return 0; }
    L->h = L->pushed[--L->npushed];
    c->resp = NORMAL;
    return 0;
}

/* ---- HANDLE AID (#4007) ---------------------------------------------------------------- *
 * The keys HANDLE AID names, and the EIBAID byte each one sends (the harness's DFHAID.cpy:
 * tests/equivalence/cics, kept equal by a test). ANYKEY is any PA or PF key or CLEAR, not
 * ENTER (IBM, HANDLE AID). */
static const struct { const char *name; char eibaid; } aid_keys[] = {
    {"ANYKEY", 0}, {"ENTER", '\''}, {"CLEAR", '_'}, {"CLRPARTN", 0x6A}, {"LIGHTPEN", '='}, {"OPERID", 'W'},
    {"TRIGGER", '"'}, {"PA1", '%'}, {"PA2", '>'}, {"PA3", ','}, {"PF1", '1'}, {"PF2", '2'}, {"PF3", '3'},
    {"PF4", '4'}, {"PF5", '5'}, {"PF6", '6'}, {"PF7", '7'}, {"PF8", '8'}, {"PF9", '9'}, {"PF10", ':'},
    {"PF11", '#'}, {"PF12", '@'}, {"PF13", 'A'}, {"PF14", 'B'}, {"PF15", 'C'}, {"PF16", 'D'}, {"PF17", 'E'},
    {"PF18", 'F'}, {"PF19", 'G'}, {"PF20", 'H'}, {"PF21", 'I'}, {"PF22", '['}, {"PF23", '.'}, {"PF24", '<'},
};
#define NAIDS ((int)(sizeof aid_keys / sizeof aid_keys[0]))

/* HANDLE AID <key>(label): the key (GG-NAME1) gets label GG-ITEM; -1 deactivates it ("To ignore
 * an AID, issue a HANDLE AID command that specifies the associated option without a label"). */
int GGCHAID(gg_cics *c) {
    char key[9];
    trim(c->name1, 8, key);
    for (int i = 0; i < NAIDS; i++) {
        if (strcmp(aid_keys[i].name, key) == 0) levels[lvl].h.aid[i] = (short)c->item;
    }
    c->resp = NORMAL;
    c->resp2 = 0;
    return 0;
}

/* After an input command that completed normally, with neither RESP nor NOHANDLE: the label of
 * the key that was pressed (the EIBAID byte in GG-NAME1), else ANYKEY's for a PA / PF key or CLEAR,
 * else 0 -- "control returns to the application program at the instruction immediately following
 * the input command" (IBM, HANDLE AID). #4414: called first with the condition the command raised
 * (GG-RESP not 0): when a label applies to the key, which of the two CICS acts on first is not
 * documented, so it is recorded as AID-REFUSED for the driver to refuse, and control goes on. */
int GGCAID(gg_cics *c) {
    handlers *h = &levels[lvl].h;
    char aid = c->name1[0];
    c->go_to = 0;
    for (int i = 1; i < NAIDS; i++) {
        if (aid_keys[i].eibaid != aid) continue;
        if (h->aid[i] > 0) c->go_to = h->aid[i];
        else if (h->aid[0] > 0 && (aid_keys[i].name[0] == 'P' || strcmp(aid_keys[i].name, "CLEAR") == 0)) {
            /* #4414: a key deactivated (-1) while ANYKEY has a label: IBM does not say which applies */
            if (h->aid[i] < 0) { event("AID-REFUSED deactivated=1", NULL, 0); return 0; }
            c->go_to = h->aid[0];
        }
        break;
    }
    if (c->resp != NORMAL && c->go_to > 0) {
        char ev[64];
        snprintf(ev, sizeof ev, "AID-REFUSED resp=%d", c->resp);
        event(ev, NULL, 0);
        c->go_to = 0;
    }
    return 0;
}

/* The task abends with `code`: the first active HANDLE ABEND exit from this level upward gets
 * control ("CICS searches for an active abend exit, starting at the logical level of the
 * application program in which the abend occurred, and proceeding to successively higher
 * levels"), deactivated as it does; the levels below it are gone. At this level the program
 * GOes TO its label; above, it GOBACKs (GG-GOTO -1) until the LINK of that level (#4004).
 * With no exit (or CANCEL) the task terminates. */
static int unwind_to = -1, unwind_goto = 0, terminated = 0;

static void abend(gg_cics *c, const char *code, const char *cause, int cond, int cancel) {
    char ev[200], what[40] = "";
    int at = -1;
    memcpy(task_abcode, code, 4);
    if (cond) snprintf(what, sizeof what, " condition=%d", cond);
    for (int i = lvl; i >= 0 && !cancel; i--) {
        if (levels[i].h.exit_active) { at = i; break; }
    }
    if (at < 0) {
        snprintf(ev, sizeof ev, "ABEND abcode=%s cause=%s%s outcome=terminated", code, cause, what);
        uow_end(1); /* dynamic transaction backout: the terminated task's file changes are undone */
        ended = 1;
        terminated = 1;
        unwind_to = -1;
        c->go_to = -1;
    } else {
        handlers *h = &levels[at].h;
        h->exit_active = 0;
        snprintf(ev, sizeof ev, "ABEND abcode=%s cause=%s%s outcome=exit exit=%s.%s", code, cause, what,
                 levels[at].prog, h->exit_name);
        if (at == lvl) {
            c->go_to = h->exit_label;
        } else {
            unwind_to = at;
            unwind_goto = h->exit_label;
            c->go_to = -1;
        }
    }
    event(ev, NULL, 0);
}

/* EXEC CICS ABEND ABCODE(GG-NAME1) [CANCEL: GG-FLAGS]. */
int GGCABND(gg_cics *c) {
    char code[9], flags[41];
    trim(c->name1, 8, code);
    trim(c->flags, 40, flags);
    while (strlen(code) < 4) strcat(code, " ");
    abend(c, code, "command", 0, strstr(flags, "CANCEL") != NULL);
    return 0;
}

/* A command raised condition GG-RESP and the program gave neither RESP nor NOHANDLE: IGNOREd
 * (GG-GOTO 0, control continues), its HANDLE CONDITION label, else the ERROR label ("If no
 * HANDLE CONDITION command is active for a condition, but one is active for ERROR, control
 * passes to the label for ERROR"), else the default action: abend with its AEIx code. */
int GGCCOND(gg_cics *c) {
    handlers *h = &levels[lvl].h;
    int cond = c->resp;
    short st = cond > 0 && cond < NCOND ? h->cond[cond] : 0;
    c->go_to = 0;
    if (st == -1) return 0;
    if (st > 0) { c->go_to = st; return 0; }
    /* #4413: EOC's default action is to ignore it (IBM, RECEIVE (LUTYPE2/LUTYPE3)); ERROR takes
     * only a condition whose "default action ... terminates the task abnormally" (HANDLE CONDITION) */
    if (cond == EOC || cond == DFHRESP_EXPIRED) return 0; /* #5862 (X72): EXPIRED is ignored by default too */
    if (h->cond[ERRCOND] > 0) { c->go_to = h->cond[ERRCOND]; return 0; }
    abend(c, condition_abcode(cond), "condition", cond, 0);
    return 0;
}

/* ASSIGN ABCODE: the task's current abend code, blanks when there has been none. */
int GGCASGN(gg_cics *c) {
    char want[9], line[256], key[16], value[16], path[4096];
    trim(c->name2, 8, want);
    memset(c->name1, ' ', 8);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strcmp(want, "INVOKING") == 0) { /* INVOKINGPROG (GG-NAME2 holds 8): who LINKed / XCTLed here; blanks at first */
        const char *p = levels[lvl].invoker;
        memcpy(c->name1, p, strlen(p) < 8 ? strlen(p) : 8);
        return 0;
    }
    if (strcmp(want, "PROGRAM") == 0) { /* ASSIGN PROGRAM: the program running at this level */
        const char *p = current_program();
        memcpy(c->name1, p, strlen(p) < 8 ? strlen(p) : 8);
        return 0;
    }
    /* #4270 slice 3: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD, from what the runner states for the task
     * ($GGCICS_STARTCODE: TD, S or SD; $GGCICS_USERID; $GGCICS_FACILITY: its terminal, empty for none;
     * $GGCICS_SCREEN: "rows cols"); unstated, the option is refused, never guessed. TERMCHK: INVREQ RESP2 5 for a
     * task with no terminal (IBM, ASSIGN: "The task is not associated with a terminal; or the task has no
     * principal facility"), before any FACILITY / SCRNHT / SCRNWD data area is written. */
    if (strcmp(want, "STARTCOD") == 0 || strcmp(want, "USERID") == 0 || strcmp(want, "FACILITY") == 0
        || strcmp(want, "TERMCHK") == 0 || strcmp(want, "SCRNHT") == 0 || strcmp(want, "SCRNWD") == 0) {
        const char *env = getenv(strcmp(want, "STARTCOD") == 0 ? "GGCICS_STARTCODE"
                                 : strcmp(want, "USERID") == 0 ? "GGCICS_USERID"
                                 : strncmp(want, "SCRN", 4) == 0 ? "GGCICS_SCREEN" : "GGCICS_FACILITY");
        int rows = 0, cols = 0;
        if (strcmp(want, "STARTCOD") == 0 && getenv("GGCICS_RUNCHILD"))
            refuse("ASSIGN STARTCODE in a RUN TRANSID child task: IBM lists no code for it");
        if (!env) {
            snprintf(line, sizeof line, "ASSIGN %s: not stated for this task", want);
            refuse(line);
            return 0;
        }
        if (strcmp(want, "TERMCHK") == 0) {
            if (!env[0]) { c->resp = INVREQ; c->resp2 = 5; }
            return 0;
        }
        if (strncmp(want, "SCRN", 4) == 0) {
            if (sscanf(env, "%d %d", &rows, &cols) != 2) refuse("ASSIGN SCRNHT / SCRNWD: $GGCICS_SCREEN");
            c->num = strcmp(want, "SCRNHT") == 0 ? rows : cols;
            return 0;
        }
        memcpy(c->name1, env, strlen(env) < 8 ? strlen(env) : 8);
        return 0;
    }
    if (strcmp(want, "APPLID") != 0 && strcmp(want, "SYSID") != 0) { /* ASSIGN ABCODE */
        memcpy(c->name1, task_abcode, 4);
        return 0;
    }
    /* ASSIGN APPLID / SYSID: the region's identity, as the case declares it (region.cfg: "APPLID x", "SYSID y") */
    snprintf(path, sizeof path, "%s/region.cfg", dir_in());
    FILE *cfg = fopen(path, "r");
    while (cfg && fgets(line, sizeof line, cfg)) {
        if (sscanf(line, "%15s %15s", key, value) == 2 && strcmp(key, want) == 0) {
            memcpy(c->name1, value, strlen(value) < 8 ? strlen(value) : 8);
        }
    }
    if (cfg) fclose(cfg);
    return 0;
}
