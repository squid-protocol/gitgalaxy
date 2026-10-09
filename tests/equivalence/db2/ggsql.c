/*
 * ggsql.c -- the COBOL side of a Db2 equivalence case: each EXEC SQL the harness precompiles
 * (tests/tools/equivalence_sql.py) becomes CALL 'GGSQL' USING GG-SQL-ID SQLCA host-variable ..., and this stub runs
 * the statement on a real Db2 through IBM's CLI driver -- the database the Java side reaches over JDBC.
 *
 * Host variables are converted as the Db2 precompiler declares them for COBOL (Db2 for z/OS Application Programming
 * and SQL Guide, "Compatibility of SQL and COBOL data types"):
 *   X  PIC X(n)                          CHAR(n): sent as all n bytes, trailing blanks included
 *   V  49 len PIC S9(4) COMP + 49 PIC X  VARCHAR(n): the length's bytes
 *   Z  PIC S9(p)V9(s) DISPLAY            DECIMAL(p,s) (zoned, sign overpunched as -fsign=EBCDIC writes ASCII)
 *   P  PIC S9(p)V9(s) COMP-3             DECIMAL(p,s)
 *   B  PIC S9(4|9|18) COMP / BINARY      SMALLINT / INTEGER / BIGINT (big-endian, as -std=ibm stores it)
 *   N  the same, COMP-5                  native byte order
 * Output (SELECT INTO, FETCH): a string longer than a fixed-length host variable is truncated (SQLWARN1 = 'W', the
 * indicator, if any, set to the original length), a shorter one padded with blanks; a VARCHAR host variable gets
 * the length and the bytes; a number whose integer part does not fit is SQLCODE -304 and nothing is assigned; a NULL
 * without an indicator variable is SQLCODE -305. SQLCODE, SQLSTATE, the warnings and SQLERRD(3) come from Db2.
 * SQLERRMC's message tokens, the warnings and SQLERRD are Db2's own SQLCA (SQLGetSQLCA); -304 / -305 / -811, which
 * this stub raises while assigning the result, carry no tokens.
 *
 * The statements come from $GGSQL_STMTS, written by the precompiler:
 *   S <id> <kind> <nin> <nout> <cursor|-> <program> <line> [H]
 *                                              kind: EXEC SELECT1 OPEN FETCH CLOSE COMMIT ROLLBACK; program and line
 *                                              (#4173): the EXEC SQL's own line in its program's source; H (#4269):
 *                                              an OPEN of a cursor declared WITH HOLD
 *   I <arg> <type> <len> <digits> <scale> <signed> <indicator-arg|-1>      one per input marker, in order
 *   O <arg> <type> <len> <digits> <scale> <signed> <indicator-arg|-1>      one per output column, in order
 *   Q <sql, the host variables replaced by ?>
 * <arg> numbers the CALL's arguments after GG-SQL-ID and SQLCA. The connection is $GGSQL_CONN (a CLI connection
 * string); autocommit is off, COMMIT / ROLLBACK are the program's own, and a run that ends normally commits (as a
 * batch step or a CICS task does; an abend backs the work out -- ggabend.c calls ggsql_uow_end). A form this stub
 * does not model ends the run (exit 98, "not modelled").
 *
 * #4269 -- cursors at the end of a unit of work, as Db2 for z/OS closes them (SQL Reference, COMMIT / ROLLBACK
 * statements): COMMIT closes every cursor not declared WITH HOLD, ROLLBACK every cursor; a FETCH or CLOSE of one
 * after that is -501. (IBM's CLI keeps a cursor open across a commit by default, SQL_ATTR_CURSOR_HOLD; a ROLLBACK
 * closes it at the server but leaves the CLI handle: this stub closes and frees the handles itself.)
 *
 * #4173 -- SQL faults. $GGSQL_FAULTS names a plan, one fault per line:
 *   <program> <line> <nth|*> <sqlcode> <sqlstate>
 * The nth execution of the statement at that line of that program (every one, for *) does not reach Db2: its SQLCA
 * is the one sqlca_reset leaves, with that SQLCODE and SQLSTATE -- no message tokens (SQLERRML 0), SQLERRD 0, no
 * warning (docs/language_status/oracle_assumptions.md M2) -- and nothing else changes: no row, no host variable,
 * a cursor's state as it was. Each fault that fires is appended to $GGSQL_FAULTS_LOG as
 *   SQL <program> <line> <n> <sqlcode>
 * the line the det port's DetSql writes for the same fault. $GGSQL_TRACE, when set, gets `<program> <line>` for
 * each statement executed (the harness's fault enumeration reads it).
 */
#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlcli1.h>
#include <sqlca.h>

#define MAXARGS 64
#define MAXSTMT 512
#define MAXHV 64

typedef struct {
    int arg, len, digits, scale, sign, ind;
    char type;
} hv;

typedef struct {
    int id, nin, nout, line, runs, hold;
    char kind[12], cursor[64], program[16];
    hv in[MAXHV], out[MAXHV];
    char *sql;
    SQLHSTMT h;
} stmt;

static stmt stmts[MAXSTMT];
static int nstmts = -1;
static SQLHENV env;
static SQLHDBC dbc;
static int connected;

static void at_end(void);

static void die(const char *what, const char *detail) {
    fprintf(stderr, "GGSQL: %s not modelled: %s\n", what, detail ? detail : "");
    fflush(stderr);
    exit(98);
}

static void load(void) {
    const char *path = getenv("GGSQL_STMTS");
    FILE *f = path ? fopen(path, "r") : NULL;
    char line[65536];
    stmt *cur = NULL;
    nstmts = 0;
    if (!f) die("statement table", path);
    while (fgets(line, sizeof line, f)) {
        line[strcspn(line, "\n")] = 0;
        if (line[0] == 'S') {
            cur = &stmts[nstmts++];
            memset(cur, 0, sizeof *cur);
            strcpy(cur->program, "-");
            char held[4] = "";
            sscanf(line + 2, "%d %11s %d %d %63s %15s %d %3s", &cur->id, cur->kind, &cur->nin, &cur->nout,
                   cur->cursor, cur->program, &cur->line, held);
            cur->hold = !strcmp(held, "H");
            cur->nin = 0, cur->nout = 0;
        } else if ((line[0] == 'I' || line[0] == 'O') && cur) {
            hv *v = line[0] == 'I' ? &cur->in[cur->nin++] : &cur->out[cur->nout++];
            sscanf(line + 2, "%d %c %d %d %d %d %d", &v->arg, &v->type, &v->len, &v->digits, &v->scale, &v->sign,
                   &v->ind);
        } else if (line[0] == 'Q' && cur) {
            cur->sql = strdup(line + 2);
        }
    }
    fclose(f);
}

static stmt *find(int id) {
    for (int i = 0; i < nstmts; i++)
        if (stmts[i].id == id) return &stmts[i];
    return NULL;
}

static stmt *find_cursor(const char *name, const char *kind) {
    for (int i = 0; i < nstmts; i++)
        if (!strcmp(stmts[i].cursor, name) && !strcmp(stmts[i].kind, kind)) return &stmts[i];
    return NULL;
}

/* ---- the SQLCA (COMP-5 fields: native) --------------------------------------------------------------- */
typedef struct {
    char sqlcaid[8];
    int sqlcabc, sqlcode;
    short sqlerrml;
    char sqlerrmc[70], sqlerrp[8];
    int sqlerrd[6];
    char sqlwarn[11], sqlstate[5];
} __attribute__((packed)) sqlca_t;

static void sqlca_reset(sqlca_t *c) {
    memcpy(c->sqlcaid, "SQLCA   ", 8);
    c->sqlcabc = 136;
    c->sqlcode = 0;
    c->sqlerrml = 0;
    memset(c->sqlerrmc, ' ', 70);
    memset(c->sqlerrp, ' ', 8);
    memset(c->sqlerrd, 0, sizeof c->sqlerrd);
    memset(c->sqlwarn, ' ', 11);
    memcpy(c->sqlstate, "00000", 5);
}

static void diag(sqlca_t *c, SQLSMALLINT kind, SQLHANDLE h, SQLRETURN rc) {
    SQLCHAR state[6] = "00000", msg[1024];
    SQLINTEGER native = 0;
    SQLSMALLINT len;
    if (rc == SQL_SUCCESS) return;
    /* Db2's own SQLCA, as the precompiled program would have it: the code, the state, the message tokens
       (SQLERRMC), the warnings and SQLERRD -- the COBOL SQLCA's layout is the C one */
    if (kind == SQL_HANDLE_STMT && rc != SQL_INVALID_HANDLE) {
        struct sqlca got;
        memset(&got, 0, sizeof got);
        if (SQLGetSQLCA(env, dbc, (SQLHSTMT)h, &got) == SQL_SUCCESS && got.sqlcode != 0) {
            memcpy(c, &got, sizeof(sqlca_t));  /* the same 136 bytes */
            memcpy(c->sqlcaid, "SQLCA   ", 8);
            c->sqlcabc = 136;
            return;
        }
    }
    if (rc == SQL_NO_DATA) {
        c->sqlcode = 100;
        memcpy(c->sqlstate, "02000", 5);
        return;
    }
    if (SQLGetDiagRec(kind, h, 1, state, &native, msg, sizeof msg, &len) == SQL_SUCCESS) {
        /* #4270 (Q10): -99999 is the CLI's own error, not Db2's (GenApp LGAPDB01's INSERT COMMERCIAL of a blank
           CA-LASTCHANGED as REQUESTDATE: 22007 in the client). What Db2 for z/OS answers is not known here, and the
           Java side's JDBC driver reports a client code of its own (-4220): refused by name, never compared */
        if (rc == SQL_ERROR && native == -99999) die("statement", "the CLI failed it in the client (no Db2 SQLCODE)");
        c->sqlcode = native;
        memcpy(c->sqlstate, state, 5);
        if (rc == SQL_SUCCESS_WITH_INFO && native == 0) c->sqlcode = 0;  /* a driver note, no Db2 warning */
        if (rc == SQL_SUCCESS_WITH_INFO && native > 0) c->sqlwarn[0] = 'W';
    } else if (rc == SQL_ERROR) {
        c->sqlcode = -99999;
        memcpy(c->sqlstate, "HY000", 5);
    }
}

static void connect_once(void) {
    const char *cs = getenv("GGSQL_CONN");
    SQLRETURN rc;
    if (connected) return;
    if (!cs) die("connection", "GGSQL_CONN is not set");
    SQLAllocHandle(SQL_HANDLE_ENV, SQL_NULL_HANDLE, &env);
    SQLSetEnvAttr(env, SQL_ATTR_ODBC_VERSION, (SQLPOINTER)SQL_OV_ODBC3, 0);
    SQLAllocHandle(SQL_HANDLE_DBC, env, &dbc);
    rc = SQLDriverConnect(dbc, NULL, (SQLCHAR *)cs, SQL_NTS, NULL, 0, NULL, SQL_DRIVER_NOPROMPT);
    if (rc != SQL_SUCCESS && rc != SQL_SUCCESS_WITH_INFO) {
        SQLCHAR state[6], msg[1024];
        SQLINTEGER native;
        SQLSMALLINT len;
        SQLGetDiagRec(SQL_HANDLE_DBC, dbc, 1, state, &native, msg, sizeof msg, &len);
        fprintf(stderr, "GGSQL: cannot connect (%s %d): %s\n", state, (int)native, msg);
        exit(97);
    }
    SQLSetConnectAttr(dbc, SQL_ATTR_AUTOCOMMIT, (SQLPOINTER)SQL_AUTOCOMMIT_OFF, 0);
    connected = 1;
    /* after the connect: exit handlers run last-registered first, and the driver registers its own cleanup while
       connecting -- the commit must run before it */
    atexit(at_end);
}

/* A CICS task's unit of work ends (ggcics.c: SYNCPOINT, SYNCPOINT ROLLBACK, an abend's backout): Db2's with it. */
void ggsql_uow_end(int rollback) {
    if (connected) SQLEndTran(SQL_HANDLE_DBC, dbc, rollback ? SQL_ROLLBACK : SQL_COMMIT);
}

static void at_end(void) {  /* a run that ends normally commits */
    if (!connected) return;
    SQLEndTran(SQL_HANDLE_DBC, dbc, SQL_COMMIT);
    SQLDisconnect(dbc);
}

/* ---- host variable <-> text ------------------------------------------------------------------------------ */
static const char POS[] = "{ABCDEFGHI", NEG[] = "}JKLMNOPQR";

static int be(const unsigned char *p, int n, int sign, long long *v) {
    unsigned long long u = 0;
    for (int i = 0; i < n; i++) u = (u << 8) | p[i];
    if (sign && n < 8 && (p[0] & 0x80)) u |= ~0ULL << (8 * n);
    *v = (long long)u;
    return 0;
}

static int le(const unsigned char *p, int n, int sign, long long *v) {
    unsigned long long u = 0;
    for (int i = n - 1; i >= 0; i--) u = (u << 8) | p[i];
    if (sign && n < 8 && (p[n - 1] & 0x80)) u |= ~0ULL << (8 * n);
    *v = (long long)u;
    return 0;
}

/* a numeric host variable's value as decimal text ("-123.45"); 0 when its bytes are no number */
static int num_text(const hv *v, const unsigned char *p, char *out) {
    char digits[64];
    int nd = 0, neg = 0;
    if (v->type == 'Z') {
        for (int i = 0; i < v->len; i++) {
            unsigned char ch = p[i];
            if (isdigit(ch)) digits[nd++] = ch;
            else if (i == v->len - 1 && strchr(POS, ch) && ch) digits[nd++] = '0' + (int)(strchr(POS, ch) - POS);
            else if (i == v->len - 1 && strchr(NEG, ch) && ch) digits[nd++] = '0' + (int)(strchr(NEG, ch) - NEG), neg = 1;
            else return 0;
        }
    } else if (v->type == 'P') {
        for (int i = 0; i < v->len; i++) {
            int hi = p[i] >> 4, lo = p[i] & 15;
            if (hi > 9) return 0;
            digits[nd++] = '0' + hi;
            if (i < v->len - 1) {
                if (lo > 9) return 0;
                digits[nd++] = '0' + lo;
            } else {
                if (lo < 10) return 0;
                neg = lo == 0xD || lo == 0xB;
            }
        }
    } else {
        long long x;
        (v->type == 'B' ? be : le)(p, v->len, v->sign, &x);
        neg = x < 0;
        nd = sprintf(digits, "%llu", (unsigned long long)(x < 0 ? -x : x));
        while (nd <= v->scale) memmove(digits + 1, digits, nd++), digits[0] = '0';
    }
    digits[nd] = 0;
    int whole = nd - v->scale;
    char *o = out;
    if (neg) *o++ = '-';
    memcpy(o, digits, whole), o += whole;
    if (v->scale) *o++ = '.', memcpy(o, digits + whole, v->scale), o += v->scale;
    *o = 0;
    return 1;
}

/* decimal text into a numeric host variable; -304 when the integer part does not fit, 0 when stored */
static int num_store(const hv *v, unsigned char *p, const char *text) {
    char ip[64] = "", fp[64] = "";
    int neg = 0;
    const char *t = text;
    while (*t == ' ') t++;
    if (*t == '-') neg = 1, t++;
    else if (*t == '+') t++;
    int ni = 0, nf = 0;
    while (isdigit((unsigned char)*t)) ip[ni++] = *t++;
    if (*t == '.') {
        t++;
        while (isdigit((unsigned char)*t)) fp[nf++] = *t++;
    }
    if (*t && *t != ' ') return -302;  /* not a number (an exponent, a non-numeric string) */
    char *ipz = ip;
    while (*ipz == '0' && ipz[1]) ipz++;  /* leading zeros */
    int whole = v->digits - v->scale;
    if (v->type == 'B' || v->type == 'N') whole = v->len == 2 ? 5 : v->len == 4 ? 10 : 19;
    if ((int)strlen(ipz) > whole && strcmp(ipz, "0")) return -304;
    char digits[64];
    int nd = 0;
    int lead = whole - (int)strlen(ipz);
    if (strcmp(ipz, "0") == 0 && whole > 0) lead = whole - 1;
    for (int i = 0; i < lead; i++) digits[nd++] = '0';
    for (char *c = ipz; *c; c++) digits[nd++] = *c;
    for (int i = 0; i < v->scale; i++) digits[nd++] = i < nf ? fp[i] : '0';  /* fraction truncated */
    digits[nd] = 0;
    int zero = 1;
    for (int i = 0; i < nd; i++) zero &= digits[i] == '0';
    if (zero) neg = 0;
    if (v->type == 'Z') {
        int n = v->len;
        memcpy(p, digits + nd - n, n);
        if (v->sign) p[n - 1] = (neg ? NEG : POS)[digits[nd - 1] - '0'];
    } else if (v->type == 'P') {
        int n = v->len, need = 2 * n - 1;
        char d[64];
        memset(d, '0', need);
        memcpy(d + need - nd, digits, nd > need ? need : nd);
        for (int i = 0; i < n; i++) {
            int hi = d[2 * i] - '0';
            int lo = i < n - 1 ? d[2 * i + 1] - '0' : (v->sign ? (neg ? 0xD : 0xC) : 0xF);
            p[i] = (unsigned char)(hi << 4 | lo);
        }
    } else {
        long long x = strtoll(digits, NULL, 10);
        if (neg) x = -x;
        if (v->len == 2 && (x > 32767 || x < -32768)) return -304;
        if (v->len == 4 && (x > 2147483647LL || x < -2147483648LL)) return -304;
        for (int i = 0; i < v->len; i++) {
            unsigned char b = (unsigned char)((unsigned long long)x >> (8 * i));
            p[v->type == 'B' ? v->len - 1 - i : i] = b;
        }
    }
    return 0;
}

static short ind_get(unsigned char **a, int idx) {
    if (idx < 0) return 0;
    return (short)((a[idx][0] << 8) | a[idx][1]);  /* PIC S9(4) COMP, big-endian */
}

static void ind_set(unsigned char **a, int idx, short v) {
    if (idx < 0) return;
    a[idx][0] = (unsigned char)(v >> 8);
    a[idx][1] = (unsigned char)v;
}

/* ---- binding ---------------------------------------------------------------------------------------- */
static char inbuf[MAXHV][512];
static SQLLEN inlen[MAXHV];

static void bind_inputs(stmt *s, unsigned char **a) {
    for (int i = 0; i < s->nin; i++) {
        hv *v = &s->in[i];
        unsigned char *p = a[v->arg];
        SQLSMALLINT sqltype;
        SQLULEN size;
        SQLSMALLINT dec = 0;
        if (ind_get(a, v->ind) < 0) {
            inlen[i] = SQL_NULL_DATA;
        }
        if (v->type == 'X') {
            memcpy(inbuf[i], p, v->len);
            inlen[i] = inlen[i] == SQL_NULL_DATA ? SQL_NULL_DATA : v->len;
            sqltype = SQL_CHAR, size = v->len;
        } else if (v->type == 'V') {
            int n = (p[0] << 8) | p[1];
            if (n < 0 || n > v->len) n = v->len;  /* Db2 rejects a length beyond the declared: -311 */
            memcpy(inbuf[i], p + 2, n);
            inlen[i] = inlen[i] == SQL_NULL_DATA ? SQL_NULL_DATA : n;
            sqltype = SQL_VARCHAR, size = v->len;
        } else {
            if (!num_text(v, p, inbuf[i])) die("a numeric host variable whose bytes are no number", s->sql);
            inlen[i] = inlen[i] == SQL_NULL_DATA ? SQL_NULL_DATA : (SQLLEN)strlen(inbuf[i]);
            if (v->type == 'B' || v->type == 'N')
                sqltype = v->len == 2 ? SQL_SMALLINT : v->len == 4 ? SQL_INTEGER : SQL_BIGINT, size = 0;
            else
                sqltype = SQL_DECIMAL, size = v->digits, dec = (SQLSMALLINT)v->scale;
        }
        SQLBindParameter(s->h, (SQLUSMALLINT)(i + 1), SQL_PARAM_INPUT, SQL_C_CHAR, sqltype, size, dec, inbuf[i],
                         sizeof inbuf[i], &inlen[i]);
    }
}

static int fetch_into(stmt *s, unsigned char **a, sqlca_t *c) {
    char buf[4096];
    SQLLEN got;
    SQLSMALLINT ncols = 0;
    SQLNumResultCols(s->h, &ncols);
    for (int i = 0; i < s->nout; i++) {
        hv *v = &s->out[i];
        if (i >= ncols) {  /* more host variables than columns: those left as they are, SQLWARN3 (Db2: a warning) */
            c->sqlwarn[0] = 'W', c->sqlwarn[3] = 'W';
            break;
        }
        unsigned char *p = a[v->arg];
        SQLRETURN rc = SQLGetData(s->h, (SQLUSMALLINT)(i + 1), SQL_C_CHAR, buf, sizeof buf, &got);
        if (rc != SQL_SUCCESS && rc != SQL_SUCCESS_WITH_INFO) {
            diag(c, SQL_HANDLE_STMT, s->h, rc);
            return 0;
        }
        if (got == SQL_NULL_DATA) {
            if (v->ind < 0) {
                c->sqlcode = -305;
                memcpy(c->sqlstate, "22002", 5);
                return 0;
            }
            ind_set(a, v->ind, -1);
            continue;
        }
        int n = (int)got;
        if (v->type == 'X') {
            int k = n < v->len ? n : v->len;
            memcpy(p, buf, k);
            memset(p + k, ' ', v->len - k);
            if (n > v->len) c->sqlwarn[0] = 'W', c->sqlwarn[1] = 'W';
            ind_set(a, v->ind, (short)(n > v->len ? n : 0));
        } else if (v->type == 'V') {
            int k = n < v->len ? n : v->len;
            p[0] = (unsigned char)(k >> 8), p[1] = (unsigned char)k;
            memcpy(p + 2, buf, k);
            if (n > v->len) c->sqlwarn[0] = 'W', c->sqlwarn[1] = 'W';
            ind_set(a, v->ind, (short)(n > v->len ? n : 0));
        } else {
            int r = num_store(v, p, buf);
            if (r) {
                c->sqlcode = r;
                memcpy(c->sqlstate, r == -304 ? "22003" : "22018", 5);
                return 0;
            }
            ind_set(a, v->ind, 0);
        }
    }
    return 1;
}

/* ---- #4173: SQL faults -------------------------------------------------------------------------------- */
/* The planned fault of this execution (the statement's nth), if $GGSQL_FAULTS plans one: 1, the SQLCA set. */
static int injected(stmt *s, sqlca_t *c) {
    const char *trace = getenv("GGSQL_TRACE"), *plan = getenv("GGSQL_FAULTS");
    stmt *k = s;  /* executions counted per key (program, line), as DetSql counts them: a member INCLUDEd twice */
    for (int i = 0; i < nstmts; i++)
        if (!strcmp(stmts[i].program, s->program) && stmts[i].line == s->line) { k = &stmts[i]; break; }
    int n = ++k->runs;
    if (trace && *trace) {
        FILE *t = fopen(trace, "a");
        if (t) { fprintf(t, "%s %d\n", s->program, s->line); fclose(t); }
    }
    FILE *f = plan && *plan ? fopen(plan, "r") : NULL;
    char prog[16], nth[16], state[8], line[256];
    int ln, code, hit = 0;
    while (f && !hit && fgets(line, sizeof line, f)) {
        if (sscanf(line, "%15s %d %15s %d %7s", prog, &ln, nth, &code, state) != 5) continue;
        if (strcmp(prog, s->program) || ln != s->line) continue;
        if (nth[0] != '*' && atoi(nth) != n) continue;
        c->sqlcode = code;
        memcpy(c->sqlstate, state, 5);
        hit = 1;
    }
    if (f) fclose(f);
    if (hit) {
        const char *log = getenv("GGSQL_FAULTS_LOG");
        FILE *l = log && *log ? fopen(log, "a") : NULL;
        if (l) { fprintf(l, "SQL %s %d %d %d\n", s->program, s->line, n, code); fclose(l); }
    }
    return hit;
}

/* One statement on Db2: the SQLCA and the host variables as the precompiled program sees them. */
static void run(stmt *s, sqlca_t *c, unsigned char **a) {
    SQLRETURN rc;
    if (!strcmp(s->kind, "COMMIT") || !strcmp(s->kind, "ROLLBACK")) {
        int commit = !strcmp(s->kind, "COMMIT");
        rc = SQLEndTran(SQL_HANDLE_DBC, dbc, commit ? SQL_COMMIT : SQL_ROLLBACK);
        diag(c, SQL_HANDLE_DBC, dbc, rc);
        if (c->sqlcode < 0) return;
        for (int i = 0; i < nstmts; i++) {  /* #4269: the cursors the unit of work's end closes */
            stmt *o = &stmts[i];
            if (strcmp(o->kind, "OPEN") || !o->h || (commit && o->hold)) continue;
            SQLCloseCursor(o->h);
            SQLFreeHandle(SQL_HANDLE_STMT, o->h);
            o->h = 0;
        }
        return;
    }
    if (!strcmp(s->kind, "FETCH") || !strcmp(s->kind, "CLOSE")) {
        stmt *o = find_cursor(s->cursor, "OPEN");
        if (!o || !o->h) {
            c->sqlcode = -501;  /* the cursor is not open */
            memcpy(c->sqlstate, "24501", 5);
            return;
        }
        if (!strcmp(s->kind, "CLOSE")) {
            rc = SQLCloseCursor(o->h);
            SQLFreeHandle(SQL_HANDLE_STMT, o->h);
            o->h = 0;
            return;
        }
        rc = SQLFetch(o->h);
        if (rc == SQL_NO_DATA) {
            diag(c, SQL_HANDLE_STMT, o->h, rc);
            return;
        }
        if (rc != SQL_SUCCESS && rc != SQL_SUCCESS_WITH_INFO) {
            diag(c, SQL_HANDLE_STMT, o->h, rc);
            return;
        }
        o->nout = s->nout;
        memcpy(o->out, s->out, sizeof s->out);
        fetch_into(o, a, c);
        return;
    }
    if (!strcmp(s->kind, "OPEN")) {
        if (s->h) {  /* already open */
            c->sqlcode = -502;
            memcpy(c->sqlstate, "24502", 5);
            return;
        }
    }
    SQLAllocHandle(SQL_HANDLE_STMT, dbc, &s->h);
    /* a cursor has the program's name, so its positioned UPDATE / DELETE (WHERE CURRENT OF name) finds it */
    if (!strcmp(s->kind, "OPEN")) SQLSetCursorName(s->h, (SQLCHAR *)s->cursor, SQL_NTS);
    rc = SQLPrepare(s->h, (SQLCHAR *)s->sql, SQL_NTS);
    if (rc != SQL_SUCCESS && rc != SQL_SUCCESS_WITH_INFO) {
        diag(c, SQL_HANDLE_STMT, s->h, rc);
        SQLFreeHandle(SQL_HANDLE_STMT, s->h);
        s->h = 0;
        return;
    }
    for (int i = 0; i < s->nin; i++) inlen[i] = 0;
    bind_inputs(s, a);
    rc = SQLExecute(s->h);
    diag(c, SQL_HANDLE_STMT, s->h, rc);
    if (c->sqlcode < 0 || (rc != SQL_SUCCESS && rc != SQL_SUCCESS_WITH_INFO && rc != SQL_NO_DATA)) {
        SQLFreeHandle(SQL_HANDLE_STMT, s->h);
        s->h = 0;
        return;
    }
    if (!strcmp(s->kind, "OPEN")) return;  /* the cursor stays open on s->h */
    if (!strcmp(s->kind, "SELECT1")) {  /* SELECT INTO: exactly one row (-811 for more) */
        rc = SQLFetch(s->h);
        if (rc == SQL_NO_DATA) {
            diag(c, SQL_HANDLE_STMT, s->h, rc);
        } else if (fetch_into(s, a, c)) {
            if (SQLFetch(s->h) != SQL_NO_DATA) {
                c->sqlcode = -811;
                memcpy(c->sqlstate, "21000", 5);
            }
        }
    } else if (rc != SQL_NO_DATA) {
        SQLLEN rows = 0;
        SQLRowCount(s->h, &rows);
        if (rows >= 0) c->sqlerrd[2] = (int)rows;  /* (CLI's -1: no row count -- a SAVEPOINT; SQLERRD(3) stays 0) */
    }
    SQLFreeHandle(SQL_HANDLE_STMT, s->h);
    s->h = 0;
}

/* #4507: each statement's outcome appended to $GGSQL_OUTCOMES, when set, as
 *   <kind> <cursor|-> <verb> <sqlcode> <sqlstate> <sqlerrd3> <injected 0|1>
 * (verb: the SQL's first word; FETCH / CLOSE: the cursor's). equivalence_db2.cobol_outcomes reads it, to compare
 * with what the Java side's JDBC got (EquivalenceDb2Config). */
static void outcome(const stmt *s, const sqlca_t *c, int fault) {
    const char *path = getenv("GGSQL_OUTCOMES");
    if (!path || !*path) return;
    const stmt *q = s;
    if (!strcmp(s->kind, "FETCH") || !strcmp(s->kind, "CLOSE")) {
        const stmt *o = find_cursor(s->cursor, "OPEN");
        if (o) q = o;
    }
    char verb[16] = "-";
    if (q->sql) {
        const char *p = q->sql;
        while (*p == ' ' || *p == '(') p++;
        int n = 0;
        while (p[n] && p[n] != ' ' && p[n] != '(' && n < 15) verb[n] = (char)toupper((unsigned char)p[n]), n++;
        verb[n ? n : 1] = 0;
    }
    FILE *f = fopen(path, "a");
    if (!f) return;
    fprintf(f, "%s %s %s %d %.5s %d %d\n", s->kind, s->cursor[0] ? s->cursor : "-", verb, c->sqlcode, c->sqlstate,
            c->sqlerrd[2], fault);
    fclose(f);
}

/* ---- the entry ---------------------------------------------------------------------------------------- */
/* #4270 (CardDemo COPAUS2C's 26-column INSERT): 32 host-variable arguments, as equivalence_sql.MAX_ARGS. */
int GGSQL(unsigned char *id, unsigned char *ca,
          unsigned char *h0, unsigned char *h1, unsigned char *h2, unsigned char *h3, unsigned char *h4,
          unsigned char *h5, unsigned char *h6, unsigned char *h7, unsigned char *h8, unsigned char *h9,
          unsigned char *h10, unsigned char *h11, unsigned char *h12, unsigned char *h13, unsigned char *h14,
          unsigned char *h15, unsigned char *h16, unsigned char *h17, unsigned char *h18, unsigned char *h19,
          unsigned char *h20, unsigned char *h21, unsigned char *h22, unsigned char *h23, unsigned char *h24,
          unsigned char *h25, unsigned char *h26, unsigned char *h27, unsigned char *h28, unsigned char *h29,
          unsigned char *h30, unsigned char *h31) {
    unsigned char *a[32] = {h0, h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h16, h17, h18, h19,
                            h20, h21, h22, h23, h24, h25, h26, h27, h28, h29, h30, h31};
    sqlca_t *c = (sqlca_t *)ca;
    int sid = 0;
    for (int i = 0; i < 4; i++) sid = sid * 10 + (id[i] - '0');  /* GG-SQL-ID PIC 9(4) */
    if (nstmts < 0) load();
    stmt *s = find(sid);
    if (!s) die("statement", "an unknown GG-SQL-ID");
    connect_once();
    sqlca_reset(c);
    if (injected(s, c)) {  /* #4173: a planned SQL fault -- the statement never reaches Db2 */
        outcome(s, c, 1);
        return 0;
    }
    run(s, c, a);
    outcome(s, c, 0);
    return 0;
}
