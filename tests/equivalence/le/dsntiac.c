/*
 * dsntiac.c -- Db2's SQLCA message formatter, CICS interface DSNTIAC, for the equivalence harness. GnuCOBOL has no Db2
 * runtime library; a program that CALLs "DSNTIAC" (CardDemo's COTRTLIC, 9999-FORMAT-DB2-MESSAGE) runs against this
 * instead. The twin of det/cobolrt/le/Dsntiac.java: the same lines, the same return codes, the same refusals.
 * oracle_assumptions.md (Q5) declares what is modelled.
 *
 *   CALL "DSNTIAC" USING DFHEIBLK, DFHCOMMAREA, SQLCA, message-area, line-length
 *
 * The message area is a halfword (big-endian: COMP) with the area's length, then lines of line-length bytes (IBM Db2
 * for z/OS Application Programming and SQL Guide, paraphrased and not re-fetched). Return codes: 0 formatted; 4 more
 * text than lines; 8 line length outside 72-240; 12 no whole line in the area; 24 an SQLCA that is not one. The
 * text is Db2's message catalogue, not documented byte for byte: only the SQLCODEs in MESSAGES have text, written
 * from the titles of IBM's DSNT messages without their message tokens; any other SQLCODE is refused (exit 98),
 * never answered with invented text. Nothing here is proven equal to z/OS. The SQLCA is the 136 bytes ggsql.c keeps
 * (COMP-5 fields little-endian).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* "SQLCODE|text": the same table, entry for entry, as the Java twin */
static const char *const MESSAGES[] = {
    "100|DSNT404I SQLCODE = 100, NOT FOUND: ROW NOT FOUND FOR FETCH, UPDATE, OR DELETE, OR THE RESULT OF A QUERY IS AN EMPTY TABLE",
    "-204|DSNT408I SQLCODE = -204, ERROR: THE NAME IS AN UNDEFINED NAME",
    "-305|DSNT408I SQLCODE = -305, ERROR: THE NULL VALUE CANNOT BE ASSIGNED TO OUTPUT HOST VARIABLE NUMBER, BECAUSE NO INDICATOR VARIABLE IS SPECIFIED",
    "-530|DSNT408I SQLCODE = -530, ERROR: THE INSERT OR UPDATE VALUE OF FOREIGN KEY IS INVALID",
    "-532|DSNT408I SQLCODE = -532, ERROR: THE RELATIONSHIP RESTRICTS THE DELETION OF ROW",
    "-803|DSNT408I SQLCODE = -803, ERROR: AN INSERTED OR UPDATED VALUE IS INVALID BECAUSE THE INDEX CONSTRAINS COLUMNS OF THE TABLE SO NO TWO ROWS CAN CONTAIN DUPLICATE VALUES IN THOSE COLUMNS",
    "-811|DSNT408I SQLCODE = -811, ERROR: THE RESULT OF AN EMBEDDED SELECT STATEMENT IS A TABLE OF MORE THAN ONE ROW",
    "-904|DSNT408I SQLCODE = -904, ERROR: UNSUCCESSFUL EXECUTION CAUSED BY AN UNAVAILABLE RESOURCE",
    "-911|DSNT408I SQLCODE = -911, ERROR: THE CURRENT UNIT OF WORK HAS BEEN ROLLED BACK DUE TO DEADLOCK OR TIMEOUT",
    "-913|DSNT408I SQLCODE = -913, ERROR: UNSUCCESSFUL EXECUTION CAUSED BY DEADLOCK OR TIMEOUT",
};

static int s32(const unsigned char *p) {
    return (int)((unsigned)p[0] | (unsigned)p[1] << 8 | (unsigned)p[2] << 16 | (unsigned)p[3] << 24);
}

static int s16(const unsigned char *p) {
    return (short)((p[0] << 8) | p[1]);
}

#define MAX_LINES 4096
#define MAX_WIDTH 240

static char lines[MAX_LINES][MAX_WIDTH + 1];
static int nlines;

static void add(const char *s, size_t n) {
    if (nlines >= MAX_LINES) {
        fprintf(stderr, "DSNTIAC: a message of more than %d lines is not modelled\n", MAX_LINES);
        exit(98);
    }
    memcpy(lines[nlines], s, n);
    lines[nlines++][n] = 0;
}

/* the text cut into lines of at most width, each at the last blank within it */
static void wrap(const char *text, int width) {
    while ((int)strlen(text) > width) {
        int cut = width;
        while (cut > 0 && text[cut] != ' ') {
            cut--;
        }
        if (cut <= 0) {
            cut = width;
        }
        add(text, (size_t)cut);
        text += cut;
        while (*text == ' ') {
            text++;
        }
    }
    add(text, strlen(text));
}

int DSNTIAC(unsigned char *eib, unsigned char *commarea, unsigned char *sqlca, unsigned char *area,
            unsigned char *linelen) {
    (void)eib;
    (void)commarea;
    int width = s16(linelen);
    if (width < 72 || width > 240) {
        return 8;
    }
    int alen = s16(area);
    if (alen - 2 < width) {
        return 12;
    }
    if (memcmp(sqlca, "SQLCA   ", 8) != 0 || s32(sqlca + 8) != 136) {
        return 24;
    }
    int code = s32(sqlca + 12);
    const char *head = NULL;
    for (size_t i = 0; i < sizeof MESSAGES / sizeof *MESSAGES; i++) {
        if (atoi(MESSAGES[i]) == code) {
            head = strchr(MESSAGES[i], '|') + 1;
        }
    }
    if (head == NULL) {
        fprintf(stderr, "DSNTIAC: Db2's message text for SQLCODE %d is not modelled\n", code);
        exit(98);
    }
    nlines = 0;
    wrap(head, width);
    char buf[512];
    snprintf(buf, sizeof buf, "DSNT418I SQLSTATE   = %.5s SQLSTATE RETURN CODE", sqlca + 131);
    wrap(buf, width);
    int e = 8;
    while (e > 0 && sqlca[88 + e - 1] == ' ') {
        e--;
    }
    snprintf(buf, sizeof buf, "DSNT415I SQLERRP    = %.*s SQL PROCEDURE DETECTING ERROR", e, sqlca + 88);
    wrap(buf, width);
    char dec[256] = "DSNT416I SQLERRD    =", hex[256] = "DSNT416I SQLERRD    =";
    for (int i = 0; i < 6; i++) {
        int v = s32(sqlca + 96 + 4 * i);
        snprintf(dec + strlen(dec), sizeof dec - strlen(dec), " %d", v);
        snprintf(hex + strlen(hex), sizeof hex - strlen(hex), " X'%08X'", (unsigned)v);
    }
    snprintf(buf, sizeof buf, "%s SQL DIAGNOSTIC INFORMATION", dec);
    wrap(buf, width);
    snprintf(buf, sizeof buf, "%s SQL DIAGNOSTIC INFORMATION", hex);
    wrap(buf, width);
    int room = (alen - 2) / width;
    for (int i = 0; i < room; i++) {
        unsigned char *at = area + 2 + (size_t)i * width;
        memset(at, ' ', (size_t)width);
        if (i < nlines) {
            memcpy(at, lines[i], strlen(lines[i]));
        }
    }
    return nlines > room ? 4 : 0;
}
