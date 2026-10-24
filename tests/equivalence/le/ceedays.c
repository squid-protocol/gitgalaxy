/*
 * ceedays.c -- a model of the Language Environment callable service CEEDAYS for the equivalence harness
 * (#4023 follow-up). GnuCOBOL has no LE services; a program that CALLs "CEEDAYS" (CardDemo's CSUTLDTC) runs
 * against this instead, and a port is proven against what this returns -- so it models only what IBM documents,
 * and refuses the rest rather than guess.
 *
 *   CALL "CEEDAYS" USING input_char_date, picture_string, output_Lilian_date, fc
 *
 * (IBM z/OS Language Environment Programming Reference, "CEEDAYS -- Convert date to Lilian format"):
 *   input_char_date, picture_string   halfword-prefixed character strings (VSTRING: 2-byte length, then text)
 *   output_Lilian_date                fullword binary: days since 14 October 1582 (15 October 1582 is day 1);
 *                                     0 when the date is not converted
 *   fc                                the 12-byte feedback token: severity, message number (halfwords), the
 *                                     case / severity / control byte, facility ID 'CEE' (EBCDIC), ISI -- all zero
 *                                     on success
 * The conditions modelled, with the message numbers IBM lists for CEEDAYS:
 *   CEE2EB (2507)  insufficient data: the date string is shorter than the picture string
 *   CEE2EC (2508)  the date value is not valid (a day outside its month, 29 February of a year that is not a
 *                  leap year in the Gregorian calendar)
 *   CEE2EH (2513)  the date is outside the supported range, 15 October 1582 to 31 December 9999
 *   CEE2EO (2520)  non-numeric data in a numeric position, or the date does not match the picture's separators
 * IBM documents (CEEDAYS, the callable service's description): "After a valid date is parsed, remaining characters are
 * ignored", so the date past the picture's span is never read; a date shorter than the picture's span is CEE2EB.
 * Pictures modelled (#4952, register L1): YYYY MM DD in any order, or YYYY DDD (Julian), each token once, adjacent
 * or joined by one separator character (- / .) used throughout. A picture LONGER than that span -- CardDemo's
 * 'YYYYMMDD  ' -- is read as its span and the rest is ASSUMED ignored ONLY WHEN IT IS ALL BLANKS (owner decision
 * 2026-10-14, register L1): IBM does not say how characters after the last token are read. A tail with any
 * non-blank byte is NOT modelled and refused by name. CBSA CRECUST's 'YYYYMMDD' is declared length 10 over 8 bytes:
 * its 2 extra bytes are the storage that follows the item, which IBM does not specify and z/OS would read as picture
 * text; the owner ruled them blank (2026-10-23, register L1: ASSUMED). This model cannot see where the item ends, so
 * a NUL tail byte (cobc's alignment padding after a 01 item) counts as that slack; Ceedays.java skips them by bound.
 * NOT modelled, and refused the same way: a numeric month outside 1-12 (2508 or 2517 -- IBM's documentation does
 * not settle it); a trailing blank on the part of the date the picture covers, all blanks included (#4049: whether CEEDAYS
 * ignores them -- 2507, insufficient data, once the date is shorter than the picture -- or reads a blank in a
 * numeric position as 2520 is not documented either; the test-strengthening loop found a port and this model
 * disagreeing on exactly that). Any other picture -- YY (a century window), month names, eras, a null or blank
 * picture, a blank separator -- is NOT modelled: the call writes "CEEDAYS: picture not modelled" to stderr and ends
 * the run (exit 98), so no proof ever rests on a guess.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int vlen(const unsigned char *v) {
    return (v[0] << 8) | v[1];
}

static void put_fc(unsigned char *fc, int msgno) {
    memset(fc, 0, 12);
    if (!msgno) {
        return;
    }
    fc[0] = 0x00; /* severity 3 */
    fc[1] = 0x03;
    fc[2] = (unsigned char)(msgno >> 8); /* message number */
    fc[3] = (unsigned char)(msgno & 0xff);
    fc[4] = 0x59;                         /* case 1, severity 3, control 1 */
    fc[5] = 0xC3;                         /* 'CEE' in EBCDIC */
    fc[6] = 0xC5;
    fc[7] = 0xC5;
}

static void put_lilian(unsigned char *out, long days) {
    out[0] = (unsigned char)((days >> 24) & 0xff);
    out[1] = (unsigned char)((days >> 16) & 0xff);
    out[2] = (unsigned char)((days >> 8) & 0xff);
    out[3] = (unsigned char)(days & 0xff);
}

static int leap(int y) {
    return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
}

/* Days from 0001-03-01-based civil count (proleptic Gregorian), for differences only. */
static long civil(int y, int m, int d) {
    y -= m <= 2;
    long era = (y >= 0 ? y : y - 399) / 400;
    long yoe = y - era * 400;
    long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe;
}

static int digits(const unsigned char *s, int n, int *out) {
    int v = 0;
    for (int i = 0; i < n; i++) {
        if (s[i] < '0' || s[i] > '9') {
            return 0;
        }
        v = v * 10 + (s[i] - '0');
    }
    *out = v;
    return 1;
}

/* The picture, as far as the tokens go: YYYY MM DD (any order) or YYYY DDD, adjacent or each pair joined by one
 * separator character, the same one throughout (- / .). Returns the length of that span, or 0 for a picture not
 * modelled. kind[] gets 'Y' (YYYY), 'M', 'D' (DD) or 'J' (DDD) in the order they appear. Only the picture's own
 * bytes up to the span are read here; the tail past the span is checked for blanks by the caller (see the header). */
static int pic_span(const unsigned char *p, int pl, char *kind, int *nt, char *sep) {
    int i = 0, have = 0, sepd = -1;
    *nt = 0;
    *sep = 0;
    while (i < pl) {
        if (*nt > 0) {
            int is_sep = p[i] == '-' || p[i] == '/' || p[i] == '.';
            if (sepd < 0) {
                sepd = is_sep;
                *sep = is_sep ? (char)p[i] : 0;
            }
            if (sepd) {
                if (!is_sep || (char)p[i] != *sep) {
                    return 0;
                }
                i++;
            }
        }
        char k;
        int w;
        /* A token is looked for only if it has not been seen: looking for one that has (a repeated token is refused
         * anyway) or for a longer one than the last token's width would read past the span -- and past the item, when
         * the picture's declared length overruns it (CRECUST). After MM or DD the last token is exact, never DDD. */
        if (!(have & (1 << ('Y' - 'A'))) && i + 4 <= pl && memcmp(p + i, "YYYY", 4) == 0) {
            k = 'Y', w = 4;
        } else if ((have & ~(1 << ('Y' - 'A'))) == 0 && i + 3 <= pl && memcmp(p + i, "DDD", 3) == 0) {
            k = 'J', w = 3;
        } else if (!(have & (1 << ('D' - 'A'))) && i + 2 <= pl && memcmp(p + i, "DD", 2) == 0) {
            k = 'D', w = 2;
        } else if (!(have & (1 << ('M' - 'A'))) && i + 2 <= pl && memcmp(p + i, "MM", 2) == 0) {
            k = 'M', w = 2;
        } else {
            return 0;
        }
        if (have & (1 << (k - 'A' + 0)) || *nt >= 3) {
            return 0; /* a repeated token */
        }
        have |= 1 << (k - 'A');
        kind[(*nt)++] = k;
        i += w;
        int ymd = (have & (1 << ('Y' - 'A'))) && (have & (1 << ('M' - 'A'))) && (have & (1 << ('D' - 'A')));
        int yj = (have & (1 << ('Y' - 'A'))) && (have & (1 << ('J' - 'A')));
        if (ymd && *nt == 3) {
            return i;
        }
        if (yj && *nt == 2) {
            return i;
        }
        if ((have & (1 << ('J' - 'A'))) && (have & ~((1 << ('Y' - 'A')) | (1 << ('J' - 'A'))))) {
            return 0; /* DDD with MM or DD */
        }
    }
    return 0;
}

int CEEDAYS(unsigned char *date, unsigned char *pic, unsigned char *lilian, unsigned char *fc) {
    int dl = vlen(date), pl = vlen(pic);
    const unsigned char *d = date + 2, *p = pic + 2;
    char kind[3], sep;
    int nt;
    int span = pic_span(p, pl, kind, &nt, &sep);
    if (!span) {
        fprintf(stderr, "CEEDAYS: picture not modelled: '%.*s'\n", pl, (const char *)p);
        exit(98);
    }
    for (int i = span; i < pl; i++) {
        /* NUL is cobc's alignment padding after a 01 item, which this function cannot see the end of: the slack past
         * CRECUST's 8-byte 'YYYYMMDD' (declared length 10), ruled blank by the owner 2026-10-23 (register L1) */
        if (p[i] != ' ' && p[i] != 0) {
            fprintf(stderr, "CEEDAYS: picture not modelled: a non-blank tail after '%.*s'\n", span,
                    (const char *)p);
            exit(98);
        }
    }
    put_lilian(lilian, 0);
    /* a trailing blank on the part of the date the picture covers: not modelled (#4049). A blank inside it is a
     * non-numeric position (2520); bytes past the span are never read. */
    int cover = dl < span ? dl : span;
    if (cover > 0 && d[cover - 1] == ' ') {
        fprintf(stderr, "CEEDAYS: a date with trailing blanks is not modelled (2507 or 2520?): '%.*s'\n", cover,
                (const char *)d);
        exit(98);
    }
    if (dl < span) {
        put_fc(fc, 2507);
        return 0;
    }
    int y = 0, m = 1, dd = 1, doy = 0, at = 0;
    for (int t = 0; t < nt; t++) {
        int w = kind[t] == 'Y' ? 4 : kind[t] == 'J' ? 3 : 2, v;
        if (t > 0 && sep) {
            if (d[at] != sep) {
                put_fc(fc, 2520);
                return 0;
            }
            at++;
        }
        if (!digits(d + at, w, &v)) {
            put_fc(fc, 2520);
            return 0;
        }
        at += w;
        if (kind[t] == 'Y') {
            y = v;
        } else if (kind[t] == 'M') {
            m = v;
        } else if (kind[t] == 'D') {
            dd = v;
        } else {
            doy = v;
        }
    }
    static const int mdays[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    long days;
    if (kind[1] == 'J' || kind[0] == 'J') {
        if (doy < 1 || doy > 365 + leap(y)) {
            put_fc(fc, 2508);
            return 0;
        }
        days = civil(y, 1, 1) + doy - 1 - civil(1582, 10, 14);
    } else {
        if (m < 1 || m > 12) {
            /* Not modelled: IBM's documentation leaves open whether a numeric month outside 1-12 is CEE2EC (2508,
             * date value not valid) or CEE2EL (2517, month not recognized) -- and CSUTLDTC itself tests for both. */
            fprintf(stderr, "CEEDAYS: a month outside 1-12 is not modelled (2508 or 2517?): '%.*s'\n", span,
                    (const char *)d);
            exit(98);
        }
        if (dd < 1 || dd > mdays[m - 1] + (m == 2 && leap(y))) {
            put_fc(fc, 2508);
            return 0;
        }
        days = civil(y, m, dd) - civil(1582, 10, 14);
    }
    if (days < 1 || y > 9999) {
        put_fc(fc, 2513);
        return 0;
    }
    put_lilian(lilian, days);
    put_fc(fc, 0);
    return 0;
}
