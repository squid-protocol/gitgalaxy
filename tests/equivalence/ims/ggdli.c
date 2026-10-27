/*
 * ggdli.c -- the IMS DL/I database model of the equivalence harness (#4893): what a batch DL/I program (IMS calls its
 * ENTRY 'DLITCBL' with its PCBs; it issues CALL 'CBLTDLI') runs against under GnuCOBOL, which has no IMS. Its Java twin
 * is the det runtime's cobolrt/dli/DetDli.java: the same rules, the same refusals. Register family I
 * (docs/language_status/register/I*.md) states every rule, every assumption and every refusal; the reference is IBM's
 * IMS Application Programming (DL/I calls, SSAs, the DB PCB mask, current position) and IMS Messages and Codes (DL/I
 * status codes).
 *
 *   CALL 'GGDLINIT' USING pcb-1 ... pcb-n      the harness's driver, before it enters the program: binds each DB PCB of
 *                                              the PSB (psb.cfg, in order) to the area passed, and fills its mask
 *   CALL 'CBLTDLI'  USING function pcb io-area [ssa-1 ... ssa-15]   (CEETDLI, #5233: the same list)
 *   CALL 'GGDLIEND'                            the driver, after the program returns: writes each database
 *   CALL 'GGDLIBMP' USING io-pcb pcb-1 ... pcb-n   the driver of a BMP (#5857): IMS passes the I/O PCB first (PSB
 *                                              CMPAT=YES); the DB PCBs are bound as GGDLINIT does, the PSB scheduled
 *
 * Inputs ($GGDLI_DIR, written by tests/tools/equivalence_ims.py from the case's DBD / PSB sources and seed):
 *   dbd.cfg    DBD <name> / SEGM <dbd> <name> <parent name or 0> <bytes> /
 *              FIELD <dbd> <segment> <field> <start> <bytes> <type C|X|P> <S sequence field | - search field>
 *   psb.cfg    PCB <dbd> <procopt> <keylen>, one line per DB PCB in PSB order; GSAM <dbd> <procopt> <record length>
 *              for a GSAM PCB (#5233), in the same order (the program's USING lists them as the PSB does)
 *   seed.<dbd> the database in hierarchic sequence: per segment, its 8-byte name and its BYTES of data
 * Output ($GGDLI_OUT/<dbd>.out): each database at the end, in the seed's format; each GSAM database (#5233) the records
 * inserted through its PCB, one record length each, in order.
 * A GSAM PCB (register I5, #5233) is a load-mode output file: ISRT with no SSA appends one fixed-length record (the
 * DBD's RECORD length, taken from the I/O area), status blank. Any other function answers AM (IBM: the call is not
 * compatible with the PCB's processing option, here load); an ISRT with an SSA stops the run by name.
 *
 * Modelled (IMS Messages and Codes, "DL/I status codes"): GU GHU GN GHN GNP GHNP ISRT REPL DLET through a DB PCB, with
 * unqualified SSAs and SSAs qualified by one field (EQ GT LT GE LE NE and their symbolic forms) on a C / X field (a
 * byte comparison) or a P field whose operands both carry the same positive sign (where IMS's packed and logical
 * comparisons agree); status blank, GA, GK, GE, GB, GP, II, DJ, DA, AC, AJ, AK, AD, AM. A DB PCB with PROCOPT L / LS (#5233, load_isrt) takes only ISRT, in hierarchic and key order: LB, LC, LD, LE. Command codes F, L, -, C, D and P (on a GU) are
 * modelled (#5233, check_codes). Anything else -- the other command codes, the # operator, another function, a call
 * whose answer depends on what this model leaves open (register I5)
 * -- writes "CBLTDLI: ... is not modelled" to stderr and ends the run (exit 98): no proof rests on a guess.
 * Each call returns 0 (RETURN-CODE 0, register I1).
 * A case's fault run may plan a DL/I status on a call (GGDLI_FAULTS, see planned_dli, #5857).
 */
extern int cob_get_num_params(void); /* libcob: the argument count of the current CALL */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXSEG 64
#define MAXFLD 256
#define MAXPCB 32
#define MAXDB 16
#define MAXSSA 15

typedef struct {
    char name[9];
    int db, parent, bytes, level, key; /* key: the sequence field (index into flds), or -1 */
} Segm;
typedef struct {
    char name[9];
    int seg, start, bytes;
    char type;
} Fld;
typedef struct Node {
    int seg;
    unsigned char *data;
    struct Node *parent, *first, *next;
} Node;
enum { POS_START, POS_AT, POS_UNKNOWN };
enum { PAR_NONE, PAR_AT, PAR_UNKNOWN };
typedef struct {
    int db, keylen, sensegs;
    char procopt[5];
    unsigned char *mask;
    int pos;          /* POS_START: before the first segment; POS_AT: on `at`; POS_UNKNOWN: left open (register I3) */
    Node *at;
    int par;          /* parentage: PAR_AT on `parent` */
    Node *parentage;
    Node *hold;       /* the segment a get-hold call returned, until the next call on this PCB */
    Node *holdpath[MAXSSA]; /* #5233: the segments a D-coded get-hold returned, in I/O area order (nhp 0: only the held one) */
    int holdskip[MAXSSA];   /* command code N, per holdpath entry */
    int nhp;
    int load;         /* #5233: PROCOPT L / LS on a DB PCB (load mode): ISRT only, in hierarchic and key order */
    Node *loadlast;   /* the segment the last successful load ISRT inserted */
    int gsam;         /* #5233: a GSAM PCB (load mode): db is -1, `out` collects the records ISRT appended */
    int reclen;
    char dbname[9];
    unsigned char *out;
    size_t outlen;
    int prevknown;    /* `at` is the previous segment for GA / GK */
} Pcb;
typedef struct {
    char name[9];
    Node root; /* a virtual node: its children are the root segments */
} Db;

static Segm segs[MAXSEG];
static Fld flds[MAXFLD];
static Db dbs[MAXDB];
static Pcb pcbs[MAXPCB];
static int nseg, nfld, ndb, npcb, loaded, refused;
static int bmp; /* 1 in a BMP entered by GGDLIBMP: PCB numbers of an EXEC DLI count the I/O PCB (#5857) */

static void refuse(const char *what) {
    fprintf(stderr, "CBLTDLI: %s is not modelled\n", what);
    refused = 1; /* a refused run writes no database (the atexit dump of an EXEC DLI task) */
    exit(98);
}

static void name8(char *out, const unsigned char *in) {
    memcpy(out, in, 8);
    out[8] = 0;
    for (int i = 7; i >= 0 && out[i] == ' '; i--) out[i] = 0;
}

static int find_seg(int db, const char *name) {
    for (int i = 0; i < nseg; i++)
        if (segs[i].db == db && !strcmp(segs[i].name, name)) return i;
    return -1;
}

static int find_fld(int seg, const char *name) {
    for (int i = 0; i < nfld; i++)
        if (flds[i].seg == seg && !strcmp(flds[i].name, name)) return i;
    return -1;
}

static FILE *open_in(const char *file) {
    const char *dir = getenv("GGDLI_DIR");
    if (!dir) dir = getenv("GGCICS_DIR"); /* a CICS task: the scenario's directory holds the stated databases */
    char path[4096];
    if (!dir) refuse("a run with no database stated (GGDLI_DIR)");
    snprintf(path, sizeof path, "%s/%s", dir, file);
    return fopen(path, "rb");
}

static int key_cmp(const Node *a, const unsigned char *kb) {
    const Fld *k = &flds[segs[a->seg].key];
    return memcmp(a->data + k->start - 1, kb, k->bytes);
}

/* A child in its place: after the twins of earlier segment types (DBD order), among its own twins in key order. */
static void link_child(Node *parent, Node *n) {
    Node **p = &parent->first;
    const Fld *k = &flds[segs[n->seg].key];
    while (*p && ((*p)->seg < n->seg || ((*p)->seg == n->seg && key_cmp(*p, n->data + k->start - 1) < 0)))
        p = &(*p)->next;
    n->next = *p;
    *p = n;
    n->parent = parent;
}

static void load_db(int d) {
    char file[64];
    snprintf(file, sizeof file, "seed.%s", dbs[d].name);
    FILE *f = open_in(file);
    if (!f) return; /* no seed: an empty database */
    Node *last[MAXSEG] = {0};
    unsigned char nm[8];
    while (fread(nm, 1, 8, f) == 8) {
        char name[9];
        name8(name, nm);
        int s = find_seg(d, name);
        if (s < 0) refuse("a seed segment the DBD does not define");
        Node *n = calloc(1, sizeof *n);
        n->seg = s;
        n->data = malloc(segs[s].bytes);
        if (fread(n->data, 1, segs[s].bytes, f) != (size_t)segs[s].bytes) refuse("a truncated seed");
        Node *parent = segs[s].parent < 0 ? &dbs[d].root : last[segs[s].parent];
        if (!parent) refuse("a seed segment before its parent");
        /* the seed must already be in hierarchic sequence: appended, it lands last among its parent's children */
        Node *t = parent->first, *prev = NULL;
        while (t) {
            prev = t;
            t = t->next;
        }
        if (prev && (prev->seg > s || (prev->seg == s && key_cmp(prev, n->data + flds[segs[s].key].start - 1) >= 0)))
            refuse("a seed not in hierarchic sequence (twins in byte order of their keys)");
        n->parent = parent;
        if (prev)
            prev->next = n;
        else
            parent->first = n;
        last[s] = n;
        for (int c = 0; c < nseg; c++)
            if (segs[c].db == d && segs[c].level > segs[s].level) last[c] = NULL;
    }
    fclose(f);
}

static void load(void) {
    if (loaded) return;
    loaded = 1;
    FILE *f = open_in("dbd.cfg");
    if (!f) refuse("a run with no dbd.cfg");
    char line[512], a[64], b[64], c[64], e[64], g[8], h[8];
    int x, y;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "DBD %63s", a) == 1) {
            snprintf(dbs[ndb].name, 9, "%.8s", a);
            dbs[ndb].root.seg = -1;
            ndb++;
        } else if (sscanf(line, "SEGM %63s %63s %63s %d", a, b, c, &x) == 4) {
            Segm *s = &segs[nseg];
            s->db = ndb - 1;
            snprintf(s->name, 9, "%.8s", b);
            s->bytes = x;
            s->key = -1;
            s->parent = strcmp(c, "0") ? find_seg(ndb - 1, c) : -1;
            s->level = s->parent < 0 ? 1 : segs[s->parent].level + 1;
            nseg++;
        } else if (sscanf(line, "FIELD %63s %63s %63s %d %d %7s %7s", a, b, e, &x, &y, g, h) == 7) {
            Fld *fl = &flds[nfld];
            fl->seg = find_seg(ndb - 1, b);
            snprintf(fl->name, 9, "%.8s", e);
            fl->start = x;
            fl->bytes = y;
            fl->type = g[0];
            if (h[0] == 'S') segs[fl->seg].key = nfld;
            nfld++;
        }
    }
    fclose(f);
    for (int s = 0; s < nseg; s++)
        if (segs[s].key < 0) refuse("a segment with no sequence field");
    for (int d = 0; d < ndb; d++) load_db(d);
}

static void put_fullword(unsigned char *p, int v) {
    p[0] = (unsigned char)(v >> 24);
    p[1] = (unsigned char)(v >> 16);
    p[2] = (unsigned char)(v >> 8);
    p[3] = (unsigned char)v;
}

typedef unsigned char *P;

/* The PSB's DB PCBs (psb.cfg, in order) into pcbs[], masks unbound; a PSB read again starts afresh (EXEC DLI SCHD). */
static void read_psb(void) {
    FILE *f = open_in("psb.cfg");
    if (!f) refuse("a run with no psb.cfg");
    char line[256], a[64], b[64], kind[8];
    int k;
    npcb = 0;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%7s %63s %63s %d", kind, a, b, &k) != 4) continue;
        int gsam = !strcmp(kind, "GSAM");
        if (!gsam && strcmp(kind, "PCB")) continue;
        if (npcb == 16) refuse("a PSB of more than 16 DB PCBs");
        Pcb *p = &pcbs[npcb];
        memset(p, 0, sizeof *p);
        p->db = -1;
        snprintf(p->procopt, 5, "%.4s", b);
        if (gsam) {
            for (int i = 0; i < npcb; i++)
                if (!strcmp(pcbs[i].dbname, a)) refuse("two GSAM PCBs on one database");
            p->gsam = 1;
            p->reclen = k;
            snprintf(p->dbname, 9, "%.8s", a);
            npcb++;
            continue;
        }
        for (int d = 0; d < ndb; d++)
            if (!strcmp(dbs[d].name, a)) p->db = d;
        p->keylen = k;
        p->load = !strcmp(p->procopt, "L") || !strcmp(p->procopt, "LS");
        for (int s = 0; s < nseg; s++)
            if (segs[s].db == p->db) p->sensegs++;
        npcb++;
    }
    fclose(f);
}

/* The mask of a PCB with no position: DBD name, level 00, status blank, PROCOPT, sensitive segments, empty key feedback */
static void init_mask(Pcb *p) {
    memset(p->mask, ' ', 36);
    const char *nm = p->gsam ? p->dbname : dbs[p->db].name;
    memcpy(p->mask, nm, strlen(nm));
    if (!p->gsam) memcpy(p->mask + 8, "00", 2); /* a GSAM PCB has no segment level: blank (ASSUMED, register I5) */
    memcpy(p->mask + 12, p->procopt, strlen(p->procopt));
    put_fullword(p->mask + 16, 0);
    put_fullword(p->mask + 28, 0);
    put_fullword(p->mask + 32, p->sensegs);
    memset(p->mask + 36, 0, p->keylen);
    p->pos = POS_START;
    p->par = PAR_NONE;
}

int GGDLINIT(P a0, P a1, P a2, P a3, P a4, P a5, P a6, P a7, P a8, P a9, P a10, P a11, P a12, P a13, P a14, P a15) {
    P areas[16] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15};
    load();
    read_psb();
    if (cob_get_num_params() != npcb) refuse("an entry whose USING does not list one area per PCB of the PSB");
    for (int i = 0; i < npcb; i++) {
        pcbs[i].mask = areas[i];
        init_mask(&pcbs[i]);
    }
    return 0;
}

/* A BMP's driver (#5857, the twin of DetDli.enterBmp): areas[0] is the I/O PCB, the rest the DB PCBs in PSB order. */
static int scheduled;
int GGDLIBMP(P a0, P a1, P a2, P a3, P a4, P a5, P a6, P a7, P a8, P a9, P a10, P a11, P a12, P a13, P a14, P a15) {
    P areas[16] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15};
    load();
    read_psb();
    if (cob_get_num_params() != npcb + 1) refuse("a BMP whose USING does not list the I/O PCB and one area per PCB of the PSB");
    for (int i = 0; i < npcb; i++) {
        pcbs[i].mask = areas[i + 1];
        init_mask(&pcbs[i]);
    }
    bmp = 1;
    scheduled = 1;
    return 0;
}

static void dump_node(FILE *f, const Node *n) {
    for (const Node *c = n->first; c; c = c->next) {
        char nm[8];
        memset(nm, ' ', 8);
        memcpy(nm, segs[c->seg].name, strlen(segs[c->seg].name));
        fwrite(nm, 1, 8, f);
        fwrite(c->data, 1, segs[c->seg].bytes, f);
        dump_node(f, c);
    }
}

static void write_dbs(void) {
    const char *out = getenv("GGDLI_OUT");
    if (!out) out = getenv("GGCICS_OUT");
    if (!out) return;
    load();
    for (int d = 0; d < ndb; d++) {
        char path[4096];
        snprintf(path, sizeof path, "%s/%s.out", out, dbs[d].name);
        FILE *f = fopen(path, "wb");
        if (!f) refuse("an unwritable GGDLI_OUT");
        dump_node(f, &dbs[d].root);
        fclose(f);
    }
    for (int i = 0; i < npcb; i++) { /* #5233: each GSAM database, the records its PCB took */
        if (!pcbs[i].gsam) continue;
        char path[4096];
        snprintf(path, sizeof path, "%s/%s.out", out, pcbs[i].dbname);
        FILE *f = fopen(path, "wb");
        if (!f) refuse("an unwritable GGDLI_OUT");
        if (pcbs[i].outlen) fwrite(pcbs[i].out, 1, pcbs[i].outlen, f);
        fclose(f);
    }
}

static int scheduled_once;
static void write_dbs_unless_refused(void) {
    if (!refused) write_dbs();
}

int GGDLIEND(void) {
    write_dbs();
    return 0;
}

/* ---- the database's hierarchic sequence ---------------------------------------------------------------------- */
static Node *next_in_seq(Node *n) {
    if (n->first) return n->first;
    while (n) {
        if (n->next) return n->next;
        n = n->parent;
    }
    return NULL;
}

static Node *db_first(int d) { return dbs[d].root.first; }

static int descends(const Node *n, const Node *anc) {
    for (const Node *p = n->parent; p; p = p->parent)
        if (p == anc) return 1;
    return 0;
}

static Node *last_in_subtree(Node *n) {
    while (n->first) {
        Node *c = n->first;
        while (c->next) c = c->next;
        n = c;
    }
    return n;
}

/* segment type t is `anc` or below it */
static int descends_type(int t, int anc) {
    for (; t >= 0; t = segs[t].parent)
        if (t == anc) return 1;
    return 0;
}

static Node *ancestor_of_type(Node *n, int seg) {
    for (; n && n->parent; n = n->parent)
        if (n->seg == seg) return n;
    return NULL;
}

/* ---- SSAs ------------------------------------------------------------------------------------------------------ */
#define MAX_TERMS 16
typedef struct {
    int fld, op; /* op 0 EQ 1 GT 2 LT 3 GE 4 LE 5 NE */
    const unsigned char *value;
    int or_; /* #5233: joined to the statement before by OR (else AND); unused on the first */
} Term;
typedef struct {
    int first, last, par, path, enq, up, vee, norepl; /* command codes F, L, P, D, Q, U, V and N (#5233) */
    Node *anchor; /* U / V: the node at this level on the current position (set per call by get) */
    const unsigned char *cat; /* command code C (#5233): the concatenated key in the parentheses, else NULL */
    int seg, fld, op; /* fld -1: unqualified; the first statement (terms[0]) is mirrored here */
    const unsigned char *value;
    int nterms;
    Term terms[MAX_TERMS];
} Ssa;

static const char *OPS[][3] = {{"EQ", " =", "= "}, {"GT", " >", "> "}, {"LT", " <", "< "},
                               {"GE", ">=", "=>"}, {"LE", "<=", "=<"}, {"NE", "\xac=", "=\xac"}};

/* The bytes of a concatenated key down to a segment type (#5233, command code C). */
static int cat_length(int seg) {
    int len = 0;
    for (int t = seg; t >= 0; t = segs[t].parent) {
        if (segs[t].key < 0) refuse("the command code C on a segment with no sequence field");
        len += flds[segs[t].key].bytes;
    }
    return len;
}

/* Command code C (#5233): the concatenated key becomes one SSA per level, qualified EQ on that level's key. */
static int expand_cat(Ssa *s, int k) {
    if (k != 1 || !s[0].cat) return k;
    int path[MAXSSA], depth = 0;
    for (int t = s[0].seg; t >= 0; t = segs[t].parent) {
        if (depth == MAXSSA) refuse("more than 15 SSAs");
        path[depth++] = t;
    }
    Ssa src = s[0];
    const unsigned char *at = src.cat;
    for (int i = 0; i < depth; i++) {
        Ssa *x = &s[i];
        int t = path[depth - 1 - i];
        x->first = x->last = x->par = x->path = x->enq = x->up = x->vee = x->norepl = 0; /* every flag: s[1..] is stale stack from the call before */
        x->cat = NULL;
        x->seg = t;
        x->fld = segs[t].key;
        x->op = 0;
        x->value = at;
        x->nterms = 1;
        x->terms[0].fld = x->fld;
        x->terms[0].op = 0;
        x->terms[0].value = at;
        x->terms[0].or_ = 0;
        at += flds[x->fld].bytes;
    }
    s[depth - 1].par = src.par;
    s[depth - 1].first = src.first;
    return depth;
}

/* The SSAs of a call: 0, or the status code that rejects them. */
static const char *parse_ssas(int db, unsigned char **raw, int n, Ssa *out) {
    for (int i = 0; i < n; i++) {
        char nm[9];
        name8(nm, raw[i]);
        out[i].seg = find_seg(db, nm);
        out[i].fld = -1;
        out[i].first = out[i].last = out[i].par = out[i].path = out[i].enq = out[i].up = out[i].vee = out[i].norepl = 0;
        out[i].cat = NULL;
        if (out[i].seg < 0) return "AC";
        unsigned char q = raw[i][8];
        if (q == ' ') continue;
        const unsigned char *at = raw[i] + 9;
        if (q == '*') {
            /* #5233: command codes, each one of A-Z 0-9 or '-', then '(' or a blank; F, L, P, C, D, N, Q, U, V and - are modelled */
            while ((*at >= 'A' && *at <= 'Z') || (*at >= '0' && *at <= '9') || *at == '-') {
                if (*at == 'F')
                    out[i].first = 1;
                else if (*at == 'L')
                    out[i].last = 1;
                else if (*at == 'P')
                    out[i].par = 1;
                else if (*at == 'D')
                    out[i].path = 1;
                else if (*at == 'N')
                    out[i].norepl = 1;
                else if (*at == 'Q')
                    out[i].enq = 1; /* #5233: enqueue; no effect with one program, checked in check_codes */
                else if (*at == 'U')
                    out[i].up = 1;
                else if (*at == 'V')
                    out[i].vee = 1;
                else if (*at == 'C')
                    out[i].cat = at; /* the key itself is placed below */
                else if (*at != '-') {
                    char what[40];
                    snprintf(what, sizeof what, "the command code %c", *at);
                    refuse(what);
                }
                at++;
            }
            if (*at != ' ' && *at != '(') return "AJ";
            if (*at == ' ' && out[i].cat) return "AJ";
            if (*at == ' ') continue;
            at++;
            if (out[i].cat) {
                /* #5233: command code C, SEG*C(concatenated key): the keys from the root down to this segment */
                int len = cat_length(out[i].seg);
                if (at[len] != ')') return "AJ";
                out[i].cat = at;
                continue;
            }
        } else if (q != '(')
            return "AJ";
        out[i].nterms = 0;
        for (;;) {
            Term *m = &out[i].terms[out[i].nterms];
            name8(nm, at);
            m->fld = find_fld(out[i].seg, nm);
            if (m->fld < 0) return "AK";
            m->op = -1;
            for (int o = 0; o < 6; o++)
                for (int v = 0; v < 3; v++)
                    if (!memcmp(at + 8, OPS[o][v], 2)) m->op = o;
            if (m->op < 0) return "AJ";
            m->value = at + 10;
            unsigned char end = at[10 + flds[m->fld].bytes];
            char t = flds[m->fld].type;
            int bool_op = end == '&' || end == '*' || end == '+' || end == '|';
            if (t != 'C' && t != 'X' && t != 'P' && (end == ')' || bool_op))
                refuse("a qualification on a field of a type other than C, X or P");
            out[i].nterms++;
            if (end == ')') break;
            if (end == '#') refuse("a boolean SSA with the independent AND operator (#)");
            if (!bool_op) return "AJ";
            if (out[i].nterms == MAX_TERMS) refuse("a boolean SSA of more than 16 qualification statements");
            out[i].terms[out[i].nterms].or_ = end == '+' || end == '|';
            at += 11 + flds[m->fld].bytes;
        }
        out[i].fld = out[i].terms[0].fld;
        out[i].op = out[i].terms[0].op;
        out[i].value = out[i].terms[0].value;
    }
    return 0;
}

/* Command codes (#5233): Q on a get (no effect: one program, so no other program to wait for); F and L on a GU / GHU or an ISRT (a unique sequence field: no effect on ISRT, and F none on GU,
 * which starts from the first twin); L only as the last, unqualified SSA. Anything else is refused. */
static void check_codes(const char *fn, const Ssa *s, int k) {
    int gu = !strncmp(fn, "GU", 2) || !strncmp(fn, "GHU", 3), is = !strncmp(fn, "ISRT", 4);
    int ps = 0;
    for (int i = 0; i < k; i++) {
        if (s[i].cat && (!gu || k != 1 || s[i].last)) refuse("the command code C other than alone on a GU, without L");
        if (s[i].path && fn[0] != 'G' && !is) { /* D on an ISRT is the path insert (#5233) */
            char what[40];
            snprintf(what, sizeof what, "the command code D on a %.4s", fn);
            refuse(what);
        }
        if (s[i].path && s[i].cat) refuse("the command code D beside C");
        if (s[i].norepl && (fn[0] != 'G' || fn[1] != 'H' || !s[i].path)) {
            char what[64];
            snprintf(what, sizeof what, "the command code N other than with D on a get-hold call (%.4s)", fn);
            refuse(what);
        }
        if (s[i].enq && fn[0] != 'G') { /* #5233: Q (enqueue) is modelled on the gets, where it changes nothing */
            char what[40];
            snprintf(what, sizeof what, "the command code Q on a %.4s", fn);
            refuse(what);
        }
        if ((s[i].up || s[i].vee) && (fn[0] != 'G' || s[i].cat)) {
            char what[48];
            snprintf(what, sizeof what, "the command code %c%s%.4s", s[i].up ? 'U' : 'V', s[i].cat ? " beside C" : " on a ", s[i].cat ? "" : fn);
            refuse(what);
        }
        if (s[i].par && (!gu || ++ps > 1)) {
            char what[40];
            if (gu)
                refuse("the command code P on more than one SSA");
            snprintf(what, sizeof what, "the command code P on a %.4s", fn);
            refuse(what);
        }
        if (s[i].first && !gu && !is) {
            char what[40];
            snprintf(what, sizeof what, "the command code F on a %.4s", fn);
            refuse(what);
        }
        if (s[i].last && (!(gu || is) || i != k - 1 || s[i].fld >= 0))
            refuse("the command code L other than on the last, unqualified SSA of a GU or ISRT");
    }
}

static int packed_sign(const unsigned char *p, int n) {
    for (int i = 0; i < n; i++) {
        if ((p[i] >> 4) > 9) return -1;
        if (i < n - 1 && (p[i] & 15) > 9) return -1;
    }
    return p[n - 1] & 15;
}

static int term_holds(const Node *n, const Term *m) {
    const Fld *f = &flds[m->fld];
    const unsigned char *a = n->data + f->start - 1;
    if (f->type == 'P') {
        int sa = packed_sign(a, f->bytes), sb = packed_sign(m->value, f->bytes);
        if (sa < 0 || sb < 0 || sa != sb || (sa != 0xC && sa != 0xF))
            refuse("a P-field qualification on operands that are not both valid with one positive sign");
    }
    int c = memcmp(a, m->value, f->bytes);
    switch (m->op) {
    case 0: return c == 0;
    case 1: return c > 0;
    case 2: return c < 0;
    case 3: return c >= 0;
    case 4: return c <= 0;
    default: return c != 0;
    }
}

/* IBM: statements joined by AND form a set, and the SSA holds when any set does. Every statement is evaluated (no
   short circuit) so a refusal does not depend on the data. */
static int qualifies(const Node *n, const Ssa *s) {
    if (s->fld < 0) return 1;
    int any = 0, set = term_holds(n, &s->terms[0]);
    for (int k = 1; k < s->nterms; k++) {
        if (s->terms[k].or_) {
            any |= set;
            set = 1;
        }
        set &= term_holds(n, &s->terms[k]);
    }
    return any | set;
}

/* n (of the last SSA's type) satisfies every SSA: each one's segment type is n or an ancestor of n */
static int satisfies(Node *n, const Ssa *s, int k) {
    if (k == 0) return 1;
    if (n->seg != s[k - 1].seg) return 0;
    for (int i = 0; i < k; i++) {
        Node *a = ancestor_of_type(n, s[i].seg);
        if (!a || !qualifies(a, &s[i])) return 0;
        if (s[i].anchor && a != s[i].anchor) return 0; /* #5233: U / V */
    }
    return 1;
}

/* SSAs in hierarchic order, each the child of the one before: 0, "AC", or a refusal */
static const char *chain(const Ssa *s, int k) {
    for (int i = 1; i < k; i++) {
        int p = segs[s[i].seg].parent;
        if (p == s[i - 1].seg) continue;
        while (p >= 0 && p != s[i - 1].seg) p = segs[p].parent;
        if (p < 0) return "AC";
        refuse("SSAs that leave out an intermediate level");
    }
    return 0;
}

/* ---- the PCB mask ---------------------------------------------------------------------------------------------- */
static void status(Pcb *p, const char *st) { memcpy(p->mask + 10, st, 2); }

/* #5857: DL/I status faults, the twin of DetDli.planned. GGDLI_FAULTS names a plan file, one fault per line:
 *     <FUNCTION> <NTH> <STATUS>        e.g.  GNP 3 AM        (NTH `*`: every call)
 * FUNCTION is GU GN GNP ISRT REPL or DLET (a get-hold counts as its get), CHKP, or (#5233) SCHD; every call of it counts, whether or
 * not it faults. The planned call is NOT performed: the PCB (DIBSTAT for CHKP) answers the status. Each fault that
 * fires is appended to GGDLI_FAULTS_LOG as `DLI <FUNCTION> <NTH> <STATUS>`. */
static const char *planned_dli(const char *fn) {
    static struct { char fn[5]; int nth; char st[3]; int seen; } plan[32];
    static int np = -1;
    if (np < 0) {
        np = 0;
        const char *path = getenv("GGDLI_FAULTS");
        FILE *f = path ? fopen(path, "r") : NULL;
        char nth[16];
        while (f && np < 32 && fscanf(f, "%4s %15s %2s", plan[np].fn, nth, plan[np].st) == 3) {
            plan[np].nth = nth[0] == '*' ? 0 : atoi(nth);
            plan[np].seen = 0;
            np++;
        }
        if (f) fclose(f);
    }
    if (!np) return NULL;
    char key[5];
    memcpy(key, fn, 4);
    key[4] = 0;
    for (int i = 3; i >= 0 && key[i] == ' '; i--) key[i] = 0;
    if (key[0] == 'G' && key[1] == 'H') memmove(key + 1, key + 2, strlen(key + 2) + 1);
    const char *hit = NULL;
    for (int i = 0; i < np; i++) {
        if (strcmp(plan[i].fn, key)) continue;
        plan[i].seen++;
        if (!hit && (plan[i].nth == 0 || plan[i].nth == plan[i].seen)) {
            hit = plan[i].st;
            const char *log = getenv("GGDLI_FAULTS_LOG");
            FILE *l = log ? fopen(log, "a") : NULL;
            if (l) {
                fprintf(l, "DLI %s %d %s\n", key, plan[i].seen, plan[i].st);
                fclose(l);
            }
        }
    }
    return hit;
}

static void feedback(Pcb *p, Node *n) {
    char lv[3];
    Node *path[MAXSEG];
    int depth = 0, len = 0;
    if (!n || !n->parent) {
        memcpy(p->mask + 8, "00", 2);
        memset(p->mask + 20, ' ', 8);
        put_fullword(p->mask + 28, 0);
        return;
    }
    snprintf(lv, sizeof lv, "%02d", segs[n->seg].level);
    memcpy(p->mask + 8, lv, 2);
    memset(p->mask + 20, ' ', 8);
    memcpy(p->mask + 20, segs[n->seg].name, strlen(segs[n->seg].name));
    for (Node *a = n; a && a->parent; a = a->parent) path[depth++] = a;
    for (int i = depth - 1; i >= 0; i--) {
        const Fld *k = &flds[segs[path[i]->seg].key];
        if (len + k->bytes > p->keylen) refuse("a concatenated key longer than the PCB's KEYLEN");
        memcpy(p->mask + 36 + len, path[i]->data + k->start - 1, k->bytes);
        len += k->bytes;
    }
    put_fullword(p->mask + 28, len);
}

static int allows(const Pcb *p, char what) {
    return strchr(p->procopt, 'A') != NULL || strchr(p->procopt, what) != NULL;
}

static Pcb *find_pcb(unsigned char *mask) {
    for (int i = 0; i < npcb; i++)
        if (pcbs[i].mask == mask) return &pcbs[i];
    refuse("a PCB the program was not passed");
    return NULL;
}

/* GU / GN / GNP and their holds */
static void get(Pcb *p, const char *fn, unsigned char *io, Ssa *s, int k, int hold) {
    if (!allows(p, 'G')) {
        status(p, "AM");
        return;
    }
    if (hold && strchr(p->procopt, 'O')) refuse("a get-hold call under PROCOPT O");
    const char *bad = chain(s, k);
    if (bad) {
        status(p, bad);
        return;
    }
    Node *n = NULL, *from = NULL, *bound = NULL;
    int gu = fn[1] == 'U' || fn[2] == 'U', gnp = !gu && strstr(fn, "NP") != NULL;
    /* #5233: command codes U and V take the current position as qualification: U at its own level, V at its level and
     * every level above; the node there is the position's ancestor-or-self of that type */
    int vee = -1;
    for (int i = 0; i < k; i++)
        if (s[i].vee) vee = i;
    for (int i = 0; i < k; i++) {
        s[i].anchor = NULL;
        if (s[i].up || i <= vee) {
            if (p->pos != POS_AT) refuse(i <= vee ? "the command code V with no established position" : "the command code U with no established position");
            s[i].anchor = ancestor_of_type(p->at, s[i].seg);
            if (!s[i].anchor) refuse(i <= vee ? "the command code V at a level the current position is not on" : "the command code U at a level the current position is not on");
        }
    }
    if (gu) {
        if (k && segs[s[0].seg].parent >= 0) refuse("a GU whose SSAs leave out the root level");
        from = db_first(p->db);
    } else {
        if (gnp) {
            if (p->par == PAR_NONE) {
                status(p, "GP");
                return;
            }
            if (p->par == PAR_UNKNOWN) refuse("a GNP after a call that leaves parentage open");
            bound = p->parentage;
            if (k) {
                int q = segs[s[0].seg].parent;
                if (!descends_type(q, bound->seg)) refuse("a GNP whose SSAs name a segment outside its parent");
            }
        }
        if (p->pos == POS_UNKNOWN) refuse("a GN / GNP after a call that leaves position open");
        if (bound && (p->pos != POS_AT || (p->at != bound && !descends(p->at, bound))))
            refuse("a GNP whose position is outside its parent");
        from = p->pos == POS_START ? db_first(p->db) : next_in_seq(p->at);
    }
    for (Node *c = from; c; c = next_in_seq(c)) {
        if (bound && !descends(c, bound)) break;
        if (k ? satisfies(c, s, k) : 1) {
            n = c;
            break;
        }
    }
    if (n && gu && k && s[k - 1].last) { /* #5233: the last twin of the type under the parent the path found */
        Node *l = n;
        for (Node *c = n->next; c; c = c->next)
            if (c->seg == n->seg) l = c;
        n = l;
    }
    if (!n) {
        int qualified = 0;
        for (int i = 0; i < k; i++) qualified |= s[i].fld >= 0;
        if (gu) {
            Node *best = NULL;
            for (int j = k - 1; j >= 1 && !best; j--)
                for (Node *c = from; c; c = next_in_seq(c))
                    if (satisfies(c, s, j)) {
                        best = c;
                        break;
                    }
            status(p, "GE");
            feedback(p, best);
            p->pos = POS_UNKNOWN;
            p->par = PAR_UNKNOWN;
        } else if (gnp) {
            if (qualified) {
                /* #5233 (register I5): GE, the parent's feedback, parentage as it was; where IMS leaves position after a
                 * qualified search that finds nothing is not stated, so it is unknown and the next GN / GNP stops by name */
                status(p, "GE");
                feedback(p, bound);
                p->pos = POS_UNKNOWN;
                return;
            }
            status(p, "GE");
            feedback(p, bound);
            p->pos = POS_AT;
            p->at = last_in_subtree(bound);
            p->prevknown = 0;
        } else {
            if (qualified) refuse("a qualified GN that finds nothing (GE or GB: IMS's sequence-field search)");
            status(p, "GB");
            p->pos = POS_START;
            p->prevknown = 0;
        }
        return;
    }
    const char *st = "  ";
    if (!gu && k == 0 && p->prevknown && p->pos == POS_AT) {
        if (segs[n->seg].level < segs[p->at->seg].level)
            st = "GA";
        else if (segs[n->seg].level == segs[p->at->seg].level && n->seg != p->at->seg)
            st = "GK";
    }
    /* #5233: command code D, a path call: each D-coded SSA's segment (the found one's ancestor of that type), in
     * hierarchic order, then the found segment itself; D on the last SSA adds nothing */
    unsigned char *at = io;
    int np = 0;
    for (int i = 0; i < k - 1; i++)
        if (s[i].path) {
            Node *a = ancestor_of_type(n, s[i].seg);
            np++;
            memcpy(at, a->data, segs[a->seg].bytes);
            at += segs[a->seg].bytes;
        }
    memcpy(at, n->data, segs[n->seg].bytes);
    status(p, st);
    feedback(p, n);
    p->pos = POS_AT;
    p->at = n;
    p->prevknown = 1;
    if (!gnp) {
        p->par = PAR_AT;
        p->parentage = n;
        for (int i = 0; i < k; i++) /* #5233: command code P sets parentage at the level of its SSA (a GU only) */
            if (s[i].par) p->parentage = ancestor_of_type(n, s[i].seg);
    }
    if (hold) {
        p->hold = n;
        if (np > 0 || s[k - 1].norepl) { /* #5233: a path get-hold: REPL replaces each segment returned, but those coded N */
            int j = 0;
            for (int i = 0; i < k - 1; i++)
                if (s[i].path) {
                    p->holdpath[j] = ancestor_of_type(n, s[i].seg);
                    p->holdskip[j++] = s[i].norepl;
                }
            p->holdpath[j] = n;
            p->holdskip[j++] = s[k - 1].norepl;
            p->nhp = j;
        }
    }
}

/* Path ISRT (#5233, command code D on an SSA before the last): twin of DetDli.pathIsrt. The I/O area holds each D-coded segment and
 * then the last, in hierarchic order; a level is found by the sequence field in its slice (D-coded) or by its SSA, and a missing
 * D-coded one is inserted from its slice. A D-coded segment that exists is kept as is (a GU with a concatenated key resets every flag of the SSAs it expands: stale stack made it a path call). The area's size is the program's job here. */
static void path_isrt(Pcb *p, unsigned char *io, Ssa *s, int k) {
    if (segs[s[0].seg].parent >= 0) refuse("an ISRT whose SSAs leave out the root level");
    unsigned char *at = io;
    Node *parent = &dbs[p->db].root;
    for (int i = 0; i < k; i++) {
        int t = s[i].seg, coded = i == k - 1 || s[i].path;
        const Fld *key = &flds[segs[t].key];
        Node *found = NULL;
        for (Node *c = parent->first; c; c = c->next)
            if (c->seg == t && (coded ? key_cmp(c, at + key->start - 1) == 0 : satisfies(c, s, i + 1))) {
                found = c;
                break;
            }
        if (i == k - 1) {
            if (found) {
                status(p, "II");
                feedback(p, parent->parent ? parent : NULL);
                p->pos = POS_UNKNOWN;
                p->par = PAR_UNKNOWN;
                return;
            }
            Node *n = calloc(1, sizeof *n);
            n->seg = t;
            n->data = malloc(segs[t].bytes);
            memcpy(n->data, at, segs[t].bytes);
            link_child(parent, n);
            status(p, "  ");
            feedback(p, n);
            p->pos = POS_AT;
            p->at = n;
            p->prevknown = 0;
            p->par = PAR_UNKNOWN;
            return;
        }
        if (!found && !coded) {
            status(p, "GE");
            feedback(p, parent->parent ? parent : NULL);
            p->pos = POS_UNKNOWN;
            p->par = PAR_UNKNOWN;
            return;
        }
        if (!found) {
            Node *n = calloc(1, sizeof *n);
            n->seg = t;
            n->data = malloc(segs[t].bytes);
            memcpy(n->data, at, segs[t].bytes);
            n->parent = parent; /* so the SSA's qualification can be read before the segment is linked */
            if (!satisfies(n, s, i + 1)) refuse("a path ISRT whose segment does not satisfy its own SSA");
            link_child(parent, n);
            found = n;
        } else if (!satisfies(found, s, i + 1)) {
            refuse("a path ISRT whose existing segment does not satisfy its own SSA");
        }
        if (coded) at += segs[t].bytes;
        parent = found;
    }
}

/* ISRT: the last SSA names the type inserted (unqualified); the SSAs before it locate the parent, from the root, or
 * there are none and current position does */
static void load_isrt(Pcb *p, unsigned char *io, Ssa *s, int k) {
    if (k > 1) refuse("a load-mode ISRT with SSAs before the last");
    int t = s[0].seg;
    Node *root = &dbs[p->db].root;
    if (!p->loadlast && root->first) refuse("load mode into a database that already holds segments");
    Node *parent = segs[t].parent < 0 ? root : ancestor_of_type(p->loadlast, segs[t].parent);
    if (!parent) {
        status(p, "LD");
        return;
    }
    const Fld *key = &flds[segs[t].key];
    Node *last = parent->first;
    while (last && last->next) last = last->next;
    if (last) {
        const char *bad = NULL;
        if (last->seg > t)
            bad = "LE";
        else if (last->seg == t) {
            int c = key_cmp(last, io + key->start - 1);
            bad = c == 0 ? "LB" : c > 0 ? "LC" : NULL;
        }
        if (bad) {
            status(p, bad);
            return;
        }
    }
    Node *n = calloc(1, sizeof *n);
    n->seg = t;
    n->data = malloc(segs[t].bytes);
    memcpy(n->data, io, segs[t].bytes);
    link_child(parent, n);
    p->loadlast = n;
    status(p, "  ");
    feedback(p, n);
    p->pos = POS_AT;
    p->at = n;
    p->prevknown = 0;
    p->par = PAR_UNKNOWN;
}

static void isrt(Pcb *p, unsigned char *io, Ssa *s, int k) {
    if (!p->load && !allows(p, 'I')) {
        status(p, "AM");
        return;
    }
    if (k == 0) refuse("an ISRT with no SSA");
    if (s[k - 1].fld >= 0) refuse("an ISRT whose last SSA is qualified");
    const char *bad = chain(s, k);
    if (bad) {
        status(p, bad);
        return;
    }
    if (p->load) {
        load_isrt(p, io, s, k);
        return;
    }
    for (int i = 0; i < k - 1; i++)
        if (s[i].path) {
            path_isrt(p, io, s, k);
            return;
        }
    int t = s[k - 1].seg;
    Node *parent;
    if (segs[t].parent < 0) {
        if (k > 1) refuse("an ISRT of a root with SSAs before it");
        parent = &dbs[p->db].root;
    } else if (k == 1) {
        if (p->pos != POS_AT) refuse("an ISRT that relies on a position left open");
        parent = ancestor_of_type(p->at, segs[t].parent);
        if (!parent) refuse("an ISRT whose parent is not on the current position's path");
    } else {
        if (segs[s[0].seg].parent >= 0) refuse("an ISRT whose SSAs leave out the root level");
        parent = NULL;
        for (Node *c = db_first(p->db); c; c = next_in_seq(c))
            if (satisfies(c, s, k - 1)) {
                parent = c;
                break;
            }
        if (!parent) {
            Node *best = NULL;
            for (int j = k - 2; j >= 1 && !best; j--)
                for (Node *c = db_first(p->db); c; c = next_in_seq(c))
                    if (satisfies(c, s, j)) {
                        best = c;
                        break;
                    }
            status(p, "GE");
            feedback(p, best);
            p->pos = POS_UNKNOWN;
            p->par = PAR_UNKNOWN;
            return;
        }
    }
    const Fld *key = &flds[segs[t].key];
    for (Node *c = parent->first; c; c = c->next)
        if (c->seg == t && key_cmp(c, io + key->start - 1) == 0) {
            status(p, "II");
            feedback(p, parent->parent ? parent : NULL);
            p->pos = POS_UNKNOWN;
            p->par = PAR_UNKNOWN;
            return;
        }
    Node *n = calloc(1, sizeof *n);
    n->seg = t;
    n->data = malloc(segs[t].bytes);
    memcpy(n->data, io, segs[t].bytes);
    link_child(parent, n);
    status(p, "  ");
    feedback(p, n);
    p->pos = POS_AT;
    p->at = n;
    p->prevknown = 0;
    p->par = PAR_UNKNOWN;
}

/* REPL / DLET: on the segment the previous call on this PCB held */
static void change(Pcb *p, int dlet, unsigned char *io, Node *held, int k, Node **path, const int *skip, int npath) {
    if (!allows(p, dlet ? 'D' : 'R')) {
        status(p, "AM");
        return;
    }
    if (k) refuse(dlet ? "a DLET with SSAs" : "a REPL with SSAs");
    if (!held) {
        status(p, "DJ");
        return;
    }
    if (npath) { /* #5233: REPL after a D-coded get-hold: each segment from its slice of the area, except those coded N */
        if (dlet) refuse("a DLET after a path call (command code D)");
        unsigned char *at = io;
        for (int i = 0; i < npath; i++) {
            const Fld *pk = &flds[segs[path[i]->seg].key];
            if (!skip[i] && key_cmp(path[i], at + pk->start - 1) != 0) {
                status(p, "DA");
                return;
            }
            at += segs[path[i]->seg].bytes;
        }
        status(p, "  ");
        at = io;
        for (int i = 0; i < npath; i++) {
            if (!skip[i]) memcpy(path[i]->data, at, segs[path[i]->seg].bytes);
            at += segs[path[i]->seg].bytes;
        }
        return;
    }
    const Fld *key = &flds[segs[held->seg].key];
    if (key_cmp(held, io + key->start - 1) != 0) {
        status(p, "DA");
        return;
    }
    status(p, "  ");
    if (!dlet) {
        memcpy(held->data, io, segs[held->seg].bytes);
        return;
    }
    /* position: on the segment before the deleted one in hierarchic sequence (the next call goes on after it) */
    Node *prev = NULL;
    for (Node *c = db_first(p->db); c && c != held; c = next_in_seq(c)) prev = c;
    Node **link = &held->parent->first;
    while (*link != held) link = &(*link)->next;
    *link = held->next;
    for (int i = 0; i < npcb; i++) { /* another PCB on the deleted segments has its position left open */
        Pcb *o = &pcbs[i];
        if (o != p && o->db == p->db && o->pos == POS_AT && (o->at == held || descends(o->at, held)))
            o->pos = POS_UNKNOWN;
        if (o->par == PAR_AT && (o->parentage == held || descends(o->parentage, held))) o->par = PAR_UNKNOWN;
    }
    p->pos = prev ? POS_AT : POS_START;
    p->at = prev;
    p->prevknown = 0;
}

/* One DL/I call: args[0] function, args[1] the PCB mask, args[2] the I/O area, args[3..n-1] the SSAs */
/* #5233: a GSAM PCB in load mode. ISRT with no SSA appends reclen bytes of the I/O area as one record; every other
 * function is not compatible with the load processing option (AM); an SSA on a GSAM call stops the run by name. */
static void gsam_call(Pcb *p, const char *fn, P *args, int n) {
    if (strcmp(fn, "ISRT")) {
        status(p, "AM");
        return;
    }
    if (n != 3) refuse("a GSAM ISRT with an SSA, or with no I/O area");
    p->out = realloc(p->out, p->outlen + p->reclen);
    if (!p->out) refuse("memory for a GSAM record");
    memcpy(p->out + p->outlen, args[2], p->reclen);
    p->outlen += p->reclen;
    status(p, "  ");
}

static int do_call(P *args, int n) {
    load();
    if (n < 2) refuse("a call with fewer than a function and a PCB");
    Pcb *p = find_pcb(args[1]);
    char fn[5];
    memcpy(fn, args[0], 4);
    fn[4] = 0;
    Node *held = p->hold;
    p->hold = NULL;
    Node *hpath[MAXSSA];
    int hskip[MAXSSA], nhpath = p->nhp;
    memcpy(hpath, p->holdpath, sizeof hpath);
    memcpy(hskip, p->holdskip, sizeof hskip);
    p->nhp = 0;
    static const char *KNOWN[] = {"GU  ", "GHU ", "GN  ", "GHN ", "GNP ", "GHNP", "ISRT", "REPL", "DLET", NULL};
    static const char *OTHER[] = {"CHKP", "XRST", "ROLB", "ROLL", "ROLS", "SETS", "SETU", "SYNC", "LOG ", "STAT", "GSCD",
                                  "FLD ", "POS ", "INIT", "INQY", "SNAP", "PCB ", "TERM", "GMSG", "ICMD", "RCMD", "CMD ",
                                  "GCMD", "AUTH", "CHNG", "PURG", "DEQ ", "SETO", "APSB", "DPSB", "GSTA", NULL};
    int known = 0;
    for (int i = 0; KNOWN[i]; i++) known |= !strcmp(fn, KNOWN[i]);
    const char *fault = known ? planned_dli(fn) : NULL;
    if (fault) {
        status(p, fault);
        return 0;
    }
    if (!known) {
        for (int i = 0; OTHER[i]; i++)
            if (!strcmp(fn, OTHER[i])) refuse("a DL/I call other than GU GHU GN GHN GNP GHNP ISRT REPL DLET");
        status(p, "AD");
        return 0;
    }
    if (p->gsam) {
        gsam_call(p, fn, args, n);
        return 0;
    }
    if (n < 3) refuse("a database call with no I/O area");
    int k = n - 3;
    if (k > MAXSSA) refuse("more than 15 SSAs");
    Ssa s[MAXSSA];
    const char *bad = parse_ssas(p->db, args + 3, k, s);
    if (bad) {
        status(p, bad);
        return 0;
    }
    check_codes(fn, s, k);
    k = expand_cat(s, k);
    if (fn[0] == 'G')
        get(p, fn, args[2], s, k, fn[1] == 'H');
    else if (!strcmp(fn, "ISRT"))
        isrt(p, args[2], s, k);
    else
        change(p, fn[0] == 'D', args[2], held, k, hpath, hskip, nhpath);
    return 0;
}

int CBLTDLI(P a0, P a1, P a2, P a3, P a4, P a5, P a6, P a7, P a8, P a9, P a10, P a11, P a12, P a13, P a14, P a15,
            P a16, P a17) {
    P args[18] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a16, a17};
    return do_call(args, cob_get_num_params());
}

/* #5233: CALL 'CEETDLI' (Language Environment's interface) takes the same USING list as CBLTDLI. */
int CEETDLI(P a0, P a1, P a2, P a3, P a4, P a5, P a6, P a7, P a8, P a9, P a10, P a11, P a12, P a13, P a14, P a15,
            P a16, P a17) {
    P args[18] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a16, a17};
    return do_call(args, cob_get_num_params());
}

/* ---- EXEC DLI under CICS (#5278, register I5) -----------------------------------------------------------------
 * The harness lowers each EXEC DLI command to one of these (the Java twin is DetDli.schedule / terminate / get / execIsrt /
 * execChange). The databases are read from $GGDLI_DIR, else $GGCICS_DIR, and written at exit to $GGDLI_OUT, else
 * $GGCICS_OUT. DIBSTAT (2 bytes) is the first argument of each.
 *   CALL 'GGDLISCHD' USING dibstat BY VALUE nodhabend      EXEC DLI SCHD PSB(..) [NODHABEND]
 *   CALL 'GGDLITERM' USING dibstat                         EXEC DLI TERM
 *   CALL 'GGDLIX'    USING dibstat verb BY VALUE pcb-number io BY VALUE seglength spec-1 value-1 BY VALUE length-1 [spec-2 ...]
 *                          verb: GU GN GNP ISRT REPL DLET (4 bytes); spec: segment(8) field(8) operator(2), the field
 *                          blank for an unqualified SSA; a REPL / DLET names its segment in spec-1 only. */
static int by_value(P a) { return (int)(long)a; }

static void set_dibstat(P dibstat, const char *st) { memcpy(dibstat, st, 2); }

int GGDLISCHD(P dibstat, P nodhabend) {
    if (bmp) refuse("an EXEC DLI SCHD in a BMP");
    const char *fault = planned_dli("SCHD"); /* #5233: not performed, DIBSTAT answers the status */
    if (fault && !(!strcmp(fault, "TC") && !scheduled)) {
        set_dibstat(dibstat, fault);
        return 0;
    }
    /* A planned TC says the task already holds the PSB: schedule it (a TERM after it is valid), DIBSTAT TC. */
    if (scheduled) {
        if (!by_value(nodhabend)) refuse("a SCHD of a PSB already scheduled, without NODHABEND (the task would abend)");
        set_dibstat(dibstat, "TC");
        return 0;
    }
    load();
    read_psb();
    for (int i = 0; i < npcb; i++) {
        pcbs[i].mask = calloc(1, 36 + pcbs[i].keylen);
        init_mask(&pcbs[i]);
    }
    if (!scheduled_once) {
        scheduled_once = 1;
        atexit(write_dbs_unless_refused);
    }
    scheduled = 1;
    set_dibstat(dibstat, fault ? fault : "  ");
    return 0;
}

int GGDLITERM(P dibstat) {
    if (bmp) refuse("an EXEC DLI TERM in a BMP");
    if (!scheduled) refuse("a TERM with no PSB scheduled");
    scheduled = 0;
    npcb = 0;
    set_dibstat(dibstat, "  ");
    return 0;
}

int GGDLIX(P dibstat, P verb, P pcbnum, P io, P seglen, P s1, P v1, P l1, P s2, P v2, P l2, P s3, P v3, P l3) {
    int n = cob_get_num_params();
    if (!scheduled) refuse("an EXEC DLI command with no PSB scheduled");
    int num = by_value(pcbnum) - bmp;
    if (bmp && num < 1) refuse("an EXEC DLI database command on PCB(1), the I/O PCB");
    if (num < 1 || num > npcb) refuse("a PCB number the scheduled PSB does not have");
    Pcb *p = &pcbs[num - 1];
    char fn[5];
    memcpy(fn, verb, 4);
    fn[4] = 0;
    int upd = strchr(p->procopt, 'A') || strchr(p->procopt, 'R') || strchr(p->procopt, 'D');
    if (!strcmp(fn, "GU  ")) memcpy(fn, upd ? "GHU " : "GU  ", 4);
    else if (!strcmp(fn, "GN  ")) memcpy(fn, upd ? "GHN " : "GN  ", 4);
    else if (!strcmp(fn, "GNP ")) memcpy(fn, upd ? "GHNP" : "GNP ", 4);
    P specs[3] = {s1, s2, s3}, vals[3] = {v1, v2, v3}, lens[3] = {l1, l2, l3};
    int k = (n - 5) / 3;
    unsigned char *ssa[3];
    for (int i = 0; i < k; i++) {
        int vl = by_value(lens[i]);
        int q = specs[i][8] != ' ' || specs[i][9] != ' ';
        ssa[i] = calloc(1, 20 + vl + 1);
        memset(ssa[i], ' ', 20 + vl);
        memcpy(ssa[i], specs[i], 8);
        if (q && (!strcmp(fn, "REPL") || !strcmp(fn, "DLET"))) refuse("a REPL / DLET with a WHERE");
        if (q) {
            ssa[i][8] = '(';
            memcpy(ssa[i] + 9, specs[i] + 8, 8);
            memcpy(ssa[i] + 17, specs[i] + 16, 2);
            memcpy(ssa[i] + 19, vals[i], vl);
            ssa[i][19 + vl] = ')';
        }
    }
    int change = !strcmp(fn, "REPL") || !strcmp(fn, "DLET");
    if (change) {
        char nm[9];
        name8(nm, specs[0]);
        if (p->hold && strcmp(segs[p->hold->seg].name, nm))
            refuse("an EXEC DLI REPL / DLET whose SEGMENT is not the held segment's type");
        k = 0;
    }
    if (!strcmp(fn, "ISRT") && by_value(seglen) >= 0 && k > 0) {
        Ssa parsed[3];
        if (!parse_ssas(p->db, ssa, k, parsed) && segs[parsed[k - 1].seg].bytes != by_value(seglen))
            refuse("an ISRT whose SEGLENGTH is not the segment's fixed length");
    }
    P args[6] = {(P)fn, p->mask, io, k > 0 ? ssa[0] : NULL, k > 1 ? ssa[1] : NULL, k > 2 ? ssa[2] : NULL};
    do_call(args, 3 + k);
    memcpy(dibstat, p->mask + 10, 2);
    return 0;
}

/* EXEC DLI CHKP ID(area) in a BMP (#5857, the twin of DetDli.checkpoint): DIBSTAT blank, every database position
 * released (the next GN starts at the beginning). The ID is 8 bytes. ASSUMPTION (register I5, no IBM text cited). */
int GGDLICHKP(P dibstat, P id, P idlen) {
    if (!bmp) refuse("an EXEC DLI CHKP outside a BMP entered by USING its I/O PCB");
    if (by_value(idlen) != 8) refuse("a CHKP ID that is not 8 bytes");
    const char *fault = planned_dli("CHKP");
    if (fault) {
        set_dibstat(dibstat, fault);
        return 0;
    }
    for (int i = 0; i < npcb; i++) {
        Pcb *p = &pcbs[i];
        p->pos = POS_START;
        p->at = NULL;
        p->par = PAR_NONE;
        p->parentage = NULL;
        p->hold = NULL;
        p->prevknown = 0;
    }
    set_dibstat(dibstat, "  ");
    return 0;
}
