/* #5274: the conditions and abends family (the per-level handler state, GGCPENT, HANDLE CONDITION and ABEND, PUSH/POP HANDLE) -- split out of ggcics.c, which includes it
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
