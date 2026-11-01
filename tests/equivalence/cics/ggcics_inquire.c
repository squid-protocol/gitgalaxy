/* #5274: BIF DEEDIT, INQUIRE / SET TERMINAL, INQUIRE ASSOCIATION and the COMMAREA written out -- split out of ggcics.c, which includes it here. */
int GGCDEED(gg_cics *c, char *field, int flen) {
    int n = c->num, i, k = 0, end, kept = -1, negative, cr, last;
    unsigned char e[32768], digits[32768], out[32768];
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n < 1) { c->resp = LENGERR; return 0; }
    if (n > flen) refuse("BIF DEEDIT LENGTH past FIELD");
    if (n > (int)sizeof e) refuse("BIF DEEDIT LENGTH past 32768");
    for (i = 0; i < n; i++) {
        if ((unsigned char)field[i] >= 0x80) refuse("BIF DEEDIT of a byte beyond 7-bit ASCII");
        e[i] = ASCII_TO_EBCDIC[(unsigned char)field[i]];
    }
    if (n == 1) return 0;
    cr = e[n - 2] == 0xC3 && e[n - 1] == 0xD9;
    negative = e[n - 1] == 0x60 || cr;
    end = n;
    if (negative) end = n - (cr ? 2 : 1);
    else if ((e[n - 1] & 0xF0) >= 0xA0) { kept = e[n - 1]; end = n - 1; }
    for (i = 0; i < end; i++)
        if (e[i] >= 0xF0 && e[i] <= 0xF9) digits[k++] = e[i];
    /* no digit left: all zeros (IBM's rule read literally; ASSUMED, register X26) */
    memset(out, 0xF0, (size_t)n);
    last = n - 1;
    if (kept >= 0) { out[last] = (unsigned char)kept; last--; }
    for (i = k - 1; i >= 0; i--, last--) out[last] = digits[i];
    if (negative) out[n - 1] = (unsigned char)(0xD0 | (out[n - 1] & 0x0F));
    for (i = 0; i < n; i++) {
        int a, found = -1;
        for (a = 0; a < 128; a++)
            if (ASCII_TO_EBCDIC[a] == out[i]) { found = a; break; }
        if (found < 0) refuse("BIF DEEDIT result byte beyond 7-bit ASCII");
        field[i] = (char)found;
    }
    return 0;
}

/* ---- #4415 slice 1: INQUIRE / SET TERMINAL UCTRANST (IBM CICS TS, INQUIRE TERMINAL, SET TERMINAL; register X26) ----
 * The CVDAs UCTRAN 450, NOUCTRAN 451, TRANIDONLY 452. The task's terminal ($GGCICS_FACILITY) has the UCTRANST the runner
 * states ($GGCICS_UCTRANST: UCTRAN, NOUCTRAN or TRANIDONLY, from the TYPETERM's UCTRAN); unstated, or the UCTRANST of a
 * terminal other than the task's, refused. A terminal terminals.cfg does not list is TERMIDERR (INQUIRE RESP2 1, SET
 * RESP2 23); an invalid CVDA is INVREQ RESP2 43. A SET is the task's view of its terminal from then on: a RECEIVE MAP after it reads the input under the new
 * value (#6271), an unformatted terminal RECEIVE after it is refused (IBM does not say when the change takes effect). c->num is the CVDA. */
static int uctranst_terminal(gg_cics *c, int resp2) {
    char term[9];
    const char *own = getenv("GGCICS_FACILITY");
    trim(c->name1, 8, term);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!listed("terminals.cfg", term)) { c->resp = TERMIDERR; c->resp2 = resp2; return 0; }
    if (!own || strcmp(own, term) != 0) refuse("UCTRANST of a terminal other than the task's");
    return 1;
}

static void uctranst_init(void) {
    const char *v = getenv("GGCICS_UCTRANST");
    if (uctranst_cvda >= 0) return;
    if (!v) refuse("INQUIRE TERMINAL UCTRANST: not stated for this task");
    uctranst_cvda = strcmp(v, "UCTRAN") == 0 ? 450 : strcmp(v, "NOUCTRAN") == 0 ? 451
                  : strcmp(v, "TRANIDONLY") == 0 ? 452 : 0;
    if (!uctranst_cvda) refuse("GGCICS_UCTRANST is not UCTRAN, NOUCTRAN or TRANIDONLY");
}

int GGCINQT(gg_cics *c) {
    int fresp, fresp2; /* #6882 (X26): a planned TERMIDERR: the INQUIRE is not performed */
    if (injected("INQ-TERMINAL", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
    if (uctranst_terminal(c, 1)) {
        uctranst_init();
        c->num = uctranst_cvda;
    }
    return 0;
}

int GGCSETT(gg_cics *c) {
    int cvda = c->num;
    int fresp, fresp2; /* #6882 (X26): a planned TERMIDERR / INVREQ: the SET is not performed (uctranst_cvda and _set stay) */
    if (injected("SET-TERMINAL", "-", &fresp, &fresp2)) { c->resp = fresp; c->resp2 = fresp2; return 0; }
    if (uctranst_terminal(c, 23)) {
        if (cvda != 450 && cvda != 451 && cvda != 452) { c->resp = INVREQ; c->resp2 = 43; return 0; }
        uctranst_cvda = cvda;
        uctranst_set = 1;
    }
    return 0;
}

/* ---- #4415 slice 2: INQUIRE ASSOCIATION (IBM CICS TS, INQUIRE ASSOCIATION; register X29) ----
 * INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID ODUSERID ODFACILNAME ODNETWORKID ODFACILTYPE: the task's own origin data, the
 * five values the runner states in $GGCICS_ORIGIN as "applid,userid,facilname,networkid,faciltype" (the facility type
 * one of IBM's CVDA names); unstated, refused. GG-FLAGS names the option wanted: the 8-character values come back in
 * name1, ODFACILTYPE's CVDA in num. The task exists and no security is checked: neither TASKIDERR nor NOTAUTH. */
int GGCINQA(gg_cics *c) {
    static const struct { const char *name; int cvda; } types[] = {
        {"APPC", 124}, {"ASRUNTRAN", 1209}, {"BRIDGE", 935}, {"EVENT", 334}, {"IIOP", 1097}, {"IPECI", 936},
        {"IPIC", 1089}, {"JVMSERVER", 1193}, {"LU61", 125}, {"MRO", 938}, {"NODEJSAPP", 1215}, {"NONE", 496},
        {"RRSUR", 939}, {"RZINSTOR", 940}, {"SCHEDULER", 941}, {"SOCKET", 942}, {"START", 635}, {"STARTTERM", 943},
        {"TERMINAL", 213}, {"TRANDATA", 944}, {"WEB", 945}, {"XMRUNTRAN", 946}};
    const char *env = getenv("GGCICS_ORIGIN");
    char want[41], fields[5][64], buf[256];
    int n = 0;
    trim(c->flags, 40, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!env) refuse("INQUIRE ASSOCIATION: the origin data is not stated for this task");
    snprintf(buf, sizeof buf, "%s", env);
    for (char *tok = strtok(buf, ","); tok && n < 5; tok = strtok(NULL, ",")) snprintf(fields[n++], sizeof fields[0], "%s", tok);
    if (n != 5) refuse("INQUIRE ASSOCIATION: $GGCICS_ORIGIN is not applid,userid,facilname,networkid,faciltype");
    if (strcmp(want, "ODFACILTYPE") == 0) {
        c->num = 0;
        for (size_t i = 0; i < sizeof types / sizeof types[0]; i++)
            if (strcmp(types[i].name, fields[4]) == 0) c->num = types[i].cvda;
        if (!c->num) refuse("INQUIRE ASSOCIATION: $GGCICS_ORIGIN's facility type is not one of IBM's");
        return 0;
    }
    int at = strcmp(want, "ODAPPLID") == 0 ? 0 : strcmp(want, "ODUSERID") == 0 ? 1
           : strcmp(want, "ODFACILNAME") == 0 ? 2 : strcmp(want, "ODNETWORKID") == 0 ? 3 : -1;
    if (at < 0) refuse("INQUIRE ASSOCIATION: an option that is not modelled");
    memset(c->name1, ' ', 8);
    memcpy(c->name1, fields[at], strlen(fields[at]) < 8 ? strlen(fields[at]) : 8);
    return 0;
}

#define GGCICS_TS_DELETEQ  /* the second part of the temporary storage family: DELETEQ TS */
#include "ggcics_tempstorage.c"
#undef GGCICS_TS_DELETEQ

#include "ggcics_taskcontrol.c"  /* #5274: the task / interval control family (START, RETRIEVE, RUN, DELAY, POST, CANCEL ...) */

#include "ggcics_enq.c"  /* #5274: the ENQ stub (GGCENQ) */

/* A LINKed program's result: the COMMAREA it leaves in its caller's storage, written as commarea.out when the task
 * ends (the driver calls this after the program, whether it RETURNed or GOBACKed). */
int GGCAOUT(const char *ca, int len) {
    char path[3000];
    snprintf(path, sizeof path, "%s/commarea.out", dir_out());
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    if (len > 0) fwrite(ca, 1, (size_t)len, f);
    fclose(f);
    return 0;
}

/* The region's named counters (#4270, register X30): $GGCICS_DIR/counters.cfg, one "POOL NAME VALUE" per line (POOL "-" for
 * none), read whole for each counter command and rewritten by the ones that change it, so a later task of the scenario
 * sees the result. */
#define MAXCNT 64
/* #4770 (X45): `limited` rows (DEFINE DCOUNTER's) carry MINIMUM / MAXIMUM, unsigned doublewords; a row of three fields has limits
 * the run does not state. */
typedef struct { char pool[64], name[64]; unsigned long long value; int limited; unsigned long long min, max; } counter_row; /* #4836: long is 32-bit on Windows */
