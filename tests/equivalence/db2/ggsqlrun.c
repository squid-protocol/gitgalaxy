/*
 * ggsqlrun.c -- a Db2 CICS case's database steps between scenarios, inside the COBOL side's container (the
 * scenarios of a CICS case run in one container): the tables reset to the seed before each, dumped after.
 *
 *   ggsqlrun -f FILE   run FILE's statements (';' ends one, outside quotes), then commit
 *   ggsqlrun -q SQL    run one query of one column and print each row's value, one a line ("NULL" for none)
 *
 * The connection is $GGSQL_CONN, as for ggsql.c; the dump query is the harness's (equivalence_db2.dump_query), so a
 * scenario's dump is the batch harness's form.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlcli1.h>

static SQLHENV env;
static SQLHDBC dbc;

static void fail(SQLSMALLINT kind, SQLHANDLE h, const char *what) {
    SQLCHAR state[6] = "", msg[1024] = "";
    SQLINTEGER native = 0;
    SQLSMALLINT len;
    SQLGetDiagRec(kind, h, 1, state, &native, msg, sizeof msg, &len);
    fprintf(stderr, "ggsqlrun: %s: %s %d %s\n", what, state, (int)native, msg);
    exit(1);
}

static int ok(SQLRETURN rc) {
    return rc == SQL_SUCCESS || rc == SQL_SUCCESS_WITH_INFO || rc == SQL_NO_DATA;
}

static void run(const char *sql) {
    SQLHSTMT h;
    SQLAllocHandle(SQL_HANDLE_STMT, dbc, &h);
    if (!ok(SQLExecDirect(h, (SQLCHAR *)sql, SQL_NTS))) fail(SQL_HANDLE_STMT, h, sql);
    SQLFreeHandle(SQL_HANDLE_STMT, h);
}

int main(int argc, char **argv) {
    const char *cs = getenv("GGSQL_CONN");
    if (argc != 3 || !cs) {
        fprintf(stderr, "usage: ggsqlrun -f FILE | -q SQL  (GGSQL_CONN set)\n");
        return 2;
    }
    SQLAllocHandle(SQL_HANDLE_ENV, SQL_NULL_HANDLE, &env);
    SQLSetEnvAttr(env, SQL_ATTR_ODBC_VERSION, (SQLPOINTER)SQL_OV_ODBC3, 0);
    SQLAllocHandle(SQL_HANDLE_DBC, env, &dbc);
    if (!ok(SQLDriverConnect(dbc, NULL, (SQLCHAR *)cs, SQL_NTS, NULL, 0, NULL, SQL_DRIVER_NOPROMPT)))
        fail(SQL_HANDLE_DBC, dbc, "connect");
    if (!strcmp(argv[1], "-f")) {
        FILE *f = fopen(argv[2], "r");
        static char buf[1 << 20], stmt[1 << 20];
        size_t n = f ? fread(buf, 1, sizeof buf - 1, f) : 0;
        int quote = 0, k = 0;
        if (!f) {
            fprintf(stderr, "ggsqlrun: %s: cannot open\n", argv[2]);
            return 1;
        }
        fclose(f);
        buf[n] = 0;
        for (size_t i = 0; i <= n; i++) {
            char ch = buf[i];
            if (ch == '\'') quote = !quote;
            if ((ch == ';' && !quote) || ch == 0) {
                stmt[k] = 0;
                char *s = stmt;
                while (*s == ' ' || *s == '\n' || *s == '\r' || *s == '\t') s++;
                if (*s) run(s);
                k = 0;
            } else {
                stmt[k++] = ch;
            }
        }
        SQLEndTran(SQL_HANDLE_DBC, dbc, SQL_COMMIT);
    } else {
        SQLHSTMT h;
        static char value[32768];
        SQLLEN got;
        SQLAllocHandle(SQL_HANDLE_STMT, dbc, &h);
        if (!ok(SQLExecDirect(h, (SQLCHAR *)argv[2], SQL_NTS))) fail(SQL_HANDLE_STMT, h, argv[2]);
        while (SQLFetch(h) == SQL_SUCCESS) {
            SQLGetData(h, 1, SQL_C_CHAR, value, sizeof value, &got);
            if (got == SQL_NULL_DATA) {
                printf("NULL\n");
            } else {  /* the value's own length: a CHAR column holding X'00' (LOW-VALUES) is not cut at its first NUL */
                size_t n = got >= 0 && (size_t)got < sizeof value ? (size_t)got : strlen(value);
                fwrite(value, 1, n, stdout);
                putchar('\n');
            }
        }
        SQLFreeHandle(SQL_HANDLE_STMT, h);
        SQLEndTran(SQL_HANDLE_DBC, dbc, SQL_COMMIT);
    }
    SQLDisconnect(dbc);
    return 0;
}
