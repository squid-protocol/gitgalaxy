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
 * NOT modelled, and refused the same way: a numeric month outside 1-12 (2508 or 2517 -- IBM's documentation does
 * not settle it); a date with trailing blanks, all blanks included (#4049: whether CEEDAYS ignores them -- 2507,
 * insufficient data, once the date is shorter than the picture -- or reads a blank in a numeric position as 2520
 * is not documented either; the test-strengthening loop found a port and this model disagreeing on exactly that). Pictures modelled: YYYY-MM-DD exactly (any other one-character separator in the same places: YYYY/MM/DD,
 * YYYY.MM.DD). Any other picture -- YYYYMMDD in a longer field, Julian DDD, month names, eras -- is NOT modelled:
 * the call writes "CEEDAYS: picture not modelled" to stderr and ends the run (exit 98), so no proof ever rests
 * on a guess.
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

int CEEDAYS(unsigned char *date, unsigned char *pic, unsigned char *lilian, unsigned char *fc) {
    int dl = vlen(date), pl = vlen(pic);
    const unsigned char *d = date + 2, *p = pic + 2;
    char sep = pl == 10 ? (char)p[4] : 0;
    if (!(pl == 10 && memcmp(p, "YYYY", 4) == 0 && memcmp(p + 5, "MM", 2) == 0 && memcmp(p + 8, "DD", 2) == 0 &&
          p[7] == sep && (sep == '-' || sep == '/' || sep == '.'))) {
        fprintf(stderr, "CEEDAYS: picture not modelled: '%.*s'\n", pl, (const char *)p);
        exit(98);
    }
    put_lilian(lilian, 0);
    if (dl > 0 && d[dl - 1] == ' ') {
        fprintf(stderr, "CEEDAYS: a date with trailing blanks is not modelled (2507 or 2520?): '%.*s'\n", dl,
                (const char *)d);
        exit(98);
    }
    if (dl < pl) {
        put_fc(fc, 2507);
        return 0;
    }
    int y, m, dd;
    if (!digits(d, 4, &y) || !digits(d + 5, 2, &m) || !digits(d + 8, 2, &dd) || d[4] != sep || d[7] != sep) {
        put_fc(fc, 2520);
        return 0;
    }
    static const int mdays[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (m < 1 || m > 12) {
        /* Not modelled: IBM's documentation leaves open whether a numeric month outside 1-12 is CEE2EC (2508,
         * date value not valid) or CEE2EL (2517, month not recognized) -- and CSUTLDTC itself tests for both. */
        fprintf(stderr, "CEEDAYS: a month outside 1-12 is not modelled (2508 or 2517?): '%.*s'\n", dl, (const char *)d);
        exit(98);
    }
    if (dd < 1 || dd > mdays[m - 1] + (m == 2 && leap(y))) {
        put_fc(fc, 2508);
        return 0;
    }
    long days = civil(y, m, dd) - civil(1582, 10, 14);
    if (days < 1 || y > 9999) {
        put_fc(fc, 2513);
        return 0;
    }
    put_lilian(lilian, days);
    put_fc(fc, 0);
    return 0;
}
