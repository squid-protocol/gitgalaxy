/*
 * le_time.c -- models of the Language Environment date/time callable services CEEGMT / CEEUTC, CEEDATM, CEESECS,
 * CEEDATE, CEEISEC, CEESECI, CEEDYWK, CEEQCEN and CEESCEN for the equivalence harness (#4949). GnuCOBOL has no LE services; a program that
 * CALLs one (CBSA's BANKDATA: CEEGMT, CEEDATM) runs against this instead, and a port is proven against what this
 * returns. The twin of det/cobolrt/le/LeTime.java: the same conditions, the same bytes, the same refusals. Register
 * L6 (docs/language_status/register/L6.md) says what IBM documents, what is assumed and what is refused.
 *
 *   CALL "CEEGMT"  USING output_Lilian, output_seconds, fc          (CEEUTC: the same)
 *   CALL "CEEDATM" USING input_seconds, picture_string, output_timestamp, fc
 *   CALL "CEESECS" USING input_timestamp, picture_string, output_seconds, fc
 *   CALL "CEEDATE" USING input_Lilian_date, picture_string, output_char_date, fc
 *   CALL "CEEISEC" USING year, month, day, hours, minutes, seconds, milliseconds, output_seconds, fc
 *   CALL "CEESECI" USING input_seconds, year, month, day, hours, minutes, seconds, milliseconds, fc
 *   CALL "CEEDYWK" USING input_Lilian_date, day_number, fc          (1 Sunday .. 7 Saturday)
 *   CALL "CEEQCEN" USING century_start, fc
 *   CALL "CEESCEN" USING century_start, fc          (0 to 100, CEE2533 otherwise)
 *   CALL "CEEGMTO" USING offset_hours, offset_minutes, offset_seconds, fc      (CEEUTCO: the same)
 * (IBM z/OS Language Environment Programming Reference; the message list per service is the one IBM publishes for the
 * ILE CEE APIs, the same service definitions: register L6.) Lilian day 1 is 15 October 1582; Lilian second 86400 is
 * 00:00:00 on that day. Lilian dates are fullword binary, seconds a native IEEE double here (COMP-2; the Java side
 * holds the same value in the item's own usage, register C6), strings halfword-prefixed (VSTRING), the feedback code
 * 12 bytes: all zero on success, else severity 3, message number, 0x59, 'CEE' in EBCDIC.
 * CEEGMT reads the case's pinned clock, $COB_CURRENT_DATE ("YYYY/MM/DD HH:MM:SS.CC"), as GMT (the det runtime's
 * CURRENT-DATE carries offset +0000); without one the model refuses (exit 98). So does a CEESECS with a YY, whose
 * century window is anchored on that clock's year.
 * Pictures modelled: YYYY YY MM DD DDD HH MI SS 99 999 and literal punctuation. Anything else IBM documents (month and
 * day names, AP, Z-suppression, eras, a null picture) is refused: "NAME: ... is not modelled" on stderr, exit 98.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_SECONDS 265621680000.0
#define MAX_DAY 3074324L

static void refuse(const char *svc, const char *what) {
    fprintf(stderr, "%s: %s is not modelled\n", svc, what);
    exit(98);
}

static int leap(long y) {
    return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
}

static int monthdays(long y, int m) {
    static const int md[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return md[m - 1] + (m == 2 && leap(y));
}

static long civil(long y, int m, int d) {
    y -= m <= 2;
    long era = (y >= 0 ? y : y - 399) / 400;
    long yoe = y - era * 400;
    long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe;
}

#define EPOCH civil(1582, 10, 14)

static void ymd(long n, long *y, int *m, int *d) {
    long z = n + EPOCH;
    long era = (z >= 0 ? z : z - 146096) / 146097;
    long doe = z - era * 146097;
    long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    long doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    long mp = (5 * doy + 2) / 153;
    *d = (int)(doy - (153 * mp + 2) / 5 + 1);
    *m = (int)(mp < 10 ? mp + 3 : mp - 9);
    *y = yoe + era * 400 + (*m <= 2);
}

static void put_int(unsigned char *out, long v) {
    out[0] = (unsigned char)(v >> 24);
    out[1] = (unsigned char)(v >> 16);
    out[2] = (unsigned char)(v >> 8);
    out[3] = (unsigned char)v;
}

static long get_int(const unsigned char *in) {
    return (int)(((unsigned)in[0] << 24) | (in[1] << 16) | (in[2] << 8) | in[3]);
}

static void put_fc(unsigned char *fc, int msgno) {
    memset(fc, 0, 12);
    if (msgno) {
        fc[1] = 0x03;
        fc[2] = (unsigned char)(msgno >> 8);
        fc[3] = (unsigned char)(msgno & 0xff);
        fc[4] = 0x59;
        fc[5] = 0xC3;
        fc[6] = 0xC5;
        fc[7] = 0xC5;
    }
}

static void put_double(unsigned char *out, double v) {
    memcpy(out, &v, sizeof v);
}

static double get_double(const unsigned char *in) {
    double v;
    memcpy(&v, in, sizeof v);
    return v;
}

/* ---------------------------------------------------------------------------------------------- pictures */

typedef struct {
    char tag[5]; /* "" for a literal */
    char lit;
} tok;

static int picture(const char *svc, const unsigned char *pic, tok *out) {
    static const char *tags[] = {"YYYY", "YY", "DDD", "DD", "MM", "HH", "MI", "SS", "999", "99"};
    int pl = (pic[0] << 8) | pic[1];
    const char *s = (const char *)pic + 2;
    char what[300];
    if (pl == 0) {
        refuse(svc, "a null picture (IBM takes the country default)");
    }
    int blank = 1;
    for (int i = 0; i < pl; i++) {
        blank &= s[i] == ' ';
    }
    int n = 0;
    for (int i = 0; i < pl;) {
        const char *hit = NULL;
        for (int t = 0; t < 10 && !hit; t++) {
            if (i + (int)strlen(tags[t]) <= pl && memcmp(s + i, tags[t], strlen(tags[t])) == 0) {
                hit = tags[t];
            }
        }
        char c = s[i];
        if (hit) {
            /* a repeated token is refused: YYYY / YY, DDD / DD and 999 / 99 are one token each */
            int dup = 0;
            for (int k = 0; k < n; k++) {
                if (out[k].tag[0] && (strcmp(out[k].tag, hit) == 0 ||
                                      (strchr("YD9", hit[0]) && out[k].tag[0] == hit[0]))) {
                    dup = 1;
                }
            }
            if (dup) {
                snprintf(what, sizeof what, "picture '%.*s' (a repeated token)", pl, s);
                refuse(svc, what);
            }
            strcpy(out[n].tag, hit);
            out[n].lit = 0;
            n++;
            i += (int)strlen(hit);
        } else if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '9' || c == '<' || c == '>' ||
                   (c == ' ' && blank)) {
            snprintf(what, sizeof what, "picture '%.*s'", pl, s);
            refuse(svc, what);
        } else {
            out[n].tag[0] = 0;
            out[n].lit = c;
            n++;
            i++;
        }
    }
    return n;
}

static int format(const tok *p, int np, long n, int hh, int mi, int ss, int ms, char *buf) {
    long y;
    int m, d, w = 0;
    ymd(n, &y, &m, &d);
    for (int k = 0; k < np; k++) {
        const char *t = p[k].tag;
        if (!t[0]) {
            buf[w++] = p[k].lit;
        } else if (!strcmp(t, "YYYY")) {
            w += sprintf(buf + w, "%04ld", y);
        } else if (!strcmp(t, "YY")) {
            w += sprintf(buf + w, "%02ld", y % 100);
        } else if (!strcmp(t, "MM")) {
            w += sprintf(buf + w, "%02d", m);
        } else if (!strcmp(t, "DD")) {
            w += sprintf(buf + w, "%02d", d);
        } else if (!strcmp(t, "DDD")) {
            w += sprintf(buf + w, "%03ld", n - (civil(y, 1, 1) - EPOCH) + 1);
        } else if (!strcmp(t, "HH")) {
            w += sprintf(buf + w, "%02d", hh);
        } else if (!strcmp(t, "MI")) {
            w += sprintf(buf + w, "%02d", mi);
        } else if (!strcmp(t, "SS")) {
            w += sprintf(buf + w, "%02d", ss);
        } else if (!strcmp(t, "99")) {
            w += sprintf(buf + w, "%02d", ms / 10);
        } else {
            w += sprintf(buf + w, "%03d", ms);
        }
    }
    return w;
}

/* The declared size of a caller's output item: the harness reads the program's DATA DIVISION and gives
 * GG_LE_OUT_SIZES="CEEDATE=80,CEEDATM=80" (tests/tools/le_out_size.py); GnuCOBOL passes this routine a bare pointer.
 * -1: not stated (an item the harness could not size), so nothing is checked, as before. */
static long out_size(const char *svc) {
    const char *s = getenv("GG_LE_OUT_SIZES");
    size_t n = strlen(svc);
    while (s && *s) {
        if (!strncmp(s, svc, n) && s[n] == '=') {
            return atol(s + n + 1);
        }
        s = strchr(s, ',');
        if (s) {
            s++;
        }
    }
    return -1;
}

/* A VSTRING result: halfword length, the text, nothing past it. IBM cuts a result longer than its output item
 * (CEE2526 / CEE2527); that is refused by name here, as the Java side does (LeTime.putVstring), whenever the item's
 * size is stated, rather than written over the storage beside it. */
static void put_vstring(const char *svc, unsigned char *out, const char *text, int len) {
    long size = out_size(svc);
    if (size >= 0 && size < 2L + len) {
        refuse(svc, "an output item shorter than the result (CEE2526 / CEE2527 truncation)");
    }
    out[0] = (unsigned char)(len >> 8);
    out[1] = (unsigned char)len;
    memcpy(out + 2, text, (size_t)len);
}

static void clear_vstring(unsigned char *out) {
    out[0] = out[1] = 0;
}

/* ---------------------------------------------------------------------------------------------- services */

static void read_clock(const char *svc, int *y, int *mo, int *d, int *hh, int *mi, int *ss, int *hs) {
    const char *s = getenv("COB_CURRENT_DATE");
    *hs = 0;
    if (!s || sscanf(s, "%d/%d/%d %d:%d:%d.%d", y, mo, d, hh, mi, ss, hs) < 6) {
        fprintf(stderr, "%s: no pinned clock ($COB_CURRENT_DATE) is not modelled\n", svc);
        exit(98);
    }
}

/* The system year, for the century window (CEESECS YY): the pinned clock's. */
static long system_year(const char *svc) {
    int y, mo, d, hh, mi, ss, hs;
    read_clock(svc, &y, &mo, &d, &hh, &mi, &ss, &hs);
    return y;
}

static int gmt(unsigned char *lilian, unsigned char *seconds, unsigned char *fc) {
    int y, mo, d, hh, mi, ss, hs;
    read_clock("CEEGMT", &y, &mo, &d, &hh, &mi, &ss, &hs);
    long days = civil(y, mo, d) - EPOCH;
    put_int(lilian, days);
    put_double(seconds, (double)((long long)days * 86400LL + hh * 3600LL + mi * 60LL + ss) + hs / 100.0);
    put_fc(fc, 0);
    return 0;
}

int CEEGMT(unsigned char *lilian, unsigned char *seconds, unsigned char *fc) {
    return gmt(lilian, seconds, fc);
}

int CEEUTC(unsigned char *lilian, unsigned char *seconds, unsigned char *fc) {
    return gmt(lilian, seconds, fc);
}

/* CEEGMTO / CEEUTCO: the offset from GMT to local time. The pinned clock is GMT (+0000), so hours, minutes and seconds
 * are zero (register L6, assumption 1). */
static int gmto(unsigned char *hours, unsigned char *minutes, unsigned char *seconds, unsigned char *fc) {
    put_int(hours, 0);
    put_int(minutes, 0);
    put_double(seconds, 0.0);
    put_fc(fc, 0);
    return 0;
}

int CEEGMTO(unsigned char *hours, unsigned char *minutes, unsigned char *seconds, unsigned char *fc) {
    return gmto(hours, minutes, seconds, fc);
}

int CEEUTCO(unsigned char *hours, unsigned char *minutes, unsigned char *seconds, unsigned char *fc) {
    return gmto(hours, minutes, seconds, fc);
}

/* The century window's start, years before the system date: 80 (the ILE default) until CEESCEN sets it. CEESECS reads
 * it for a YY (the window is [system year - start, + 99]; the system year is the pinned clock's). */
static long century_start = 80;

int CEEQCEN(unsigned char *century, unsigned char *fc) {
    put_int(century, century_start);
    put_fc(fc, 0);
    return 0;
}

/* CEESCEN: 0 to 100; anything else is CEE2533 and the setting is unchanged. */
int CEESCEN(unsigned char *century, unsigned char *fc) {
    long v = get_int(century);
    if (v < 0 || v > 100) {
        put_fc(fc, 2533);
        return 0;
    }
    century_start = v;
    put_fc(fc, 0);
    return 0;
}

int CEEDATE(unsigned char *lilian, unsigned char *pic, unsigned char *out, unsigned char *fc) {
    tok p[64];
    char buf[512];
    int np = picture("CEEDATE", pic, p);
    long n = get_int(lilian);
    if (n < 1 || n > MAX_DAY) {
        clear_vstring(out);
        put_fc(fc, 2512);
        return 0;
    }
    put_vstring("CEEDATE", out, buf, format(p, np, n, 0, 0, 0, 0, buf));
    put_fc(fc, 0);
    return 0;
}

int CEEDATM(unsigned char *seconds, unsigned char *pic, unsigned char *out, unsigned char *fc) {
    tok p[64];
    char buf[512];
    int np = picture("CEEDATM", pic, p);
    double v = get_double(seconds), whole = floor(v);
    if (!(whole >= 86400.0 && whole < MAX_SECONDS)) {
        clear_vstring(out);
        put_fc(fc, 2505);
        return 0;
    }
    long long w = (long long)whole;
    int ms = (int)floor((v - whole) * 1000.0);
    long long sod = w % 86400LL;
    put_vstring("CEEDATM", out, buf, format(p, np, (long)(w / 86400LL), (int)(sod / 3600), (int)(sod / 60 % 60), (int)(sod % 60), ms, buf));
    put_fc(fc, 0);
    return 0;
}

/* The shared check and conversion of CEESECS and CEEISEC; the day / year codes differ between them. */
static void isec(const long *v, unsigned char *seconds, unsigned char *fc, int day_code, int year_code) {
    int bad = 0, code = 0;
    if (v[0] < 1582 || v[0] > 9999) {
        bad++;
        code = year_code;
    }
    if (v[1] < 1 || v[1] > 12) {
        bad++;
        code = 2517;
    }
    int ok = v[0] >= 1582 && v[0] <= 9999 && v[1] >= 1 && v[1] <= 12;
    if (v[2] < 1 || v[2] > (ok ? monthdays(v[0], (int)v[1]) : 31)) {
        bad++;
        code = day_code;
    }
    if (v[3] < 0 || v[3] > 23) {
        bad++;
        code = 2510;
    }
    if (v[4] < 0 || v[4] > 59) {
        bad++;
        code = 2516;
    }
    if (v[5] < 0 || v[5] > 59) {
        bad++;
        code = 2519;
    }
    if (v[6] < 0 || v[6] > 999) {
        bad++;
        code = 2515;
    }
    if (bad > 1) {
        refuse("CEEISEC / CEESECS", "more than one invalid field (IBM does not say which condition comes first)");
    }
    long days = bad == 0 ? civil(v[0], (int)v[1], (int)v[2]) - EPOCH : 0;
    if (bad == 0 && days < 1) {
        bad = 1;
        code = 2513;
    }
    if (bad) {
        put_double(seconds, 0.0);
        put_fc(fc, code);
        return;
    }
    put_double(seconds, (double)((long long)days * 86400LL + (long long)v[3] * 3600LL + (long long)v[4] * 60LL + v[5]) + v[6] / 1000.0);
    put_fc(fc, 0);
}

int CEEISEC(unsigned char *y, unsigned char *mo, unsigned char *d, unsigned char *h, unsigned char *mi,
            unsigned char *s, unsigned char *ms, unsigned char *seconds, unsigned char *fc) {
    long v[7] = {get_int(y), get_int(mo), get_int(d), get_int(h), get_int(mi), get_int(s), get_int(ms)};
    isec(v, seconds, fc, 2511, 2514);
    return 0;
}

/* CEESECI: Lilian seconds to integer fields, the inverse of CEEISEC; the range is CEEDATM's (CEE2505), the fraction is
 * floored to a thousandth. A failing call writes zeros. */
int CEESECI(unsigned char *seconds, unsigned char *y, unsigned char *mo, unsigned char *d, unsigned char *h,
            unsigned char *mi, unsigned char *s, unsigned char *ms, unsigned char *fc) {
    double v = get_double(seconds), whole = floor(v);
    if (!(whole >= 86400.0 && whole < MAX_SECONDS)) {
        put_int(y, 0);
        put_int(mo, 0);
        put_int(d, 0);
        put_int(h, 0);
        put_int(mi, 0);
        put_int(s, 0);
        put_int(ms, 0);
        put_fc(fc, 2505);
        return 0;
    }
    long long w = (long long)whole;
    long long sod = w % 86400LL;
    long yy;
    int mm, dd;
    ymd((long)(w / 86400LL), &yy, &mm, &dd);
    put_int(y, yy);
    put_int(mo, mm);
    put_int(d, dd);
    put_int(h, (long)(sod / 3600));
    put_int(mi, (long)(sod / 60 % 60));
    put_int(s, (long)(sod % 60));
    put_int(ms, (long)floor((v - whole) * 1000.0));
    put_fc(fc, 0);
    return 0;
}

/* CEEDYWK: the day of the week of a Lilian day, 1 (Sunday) to 7 (Saturday); day 1 (15 October 1582) was a Friday.
 * Outside 1 .. MAX_DAY the number is 0 and the code CEE2512. */
int CEEDYWK(unsigned char *lilian, unsigned char *out, unsigned char *fc) {
    long n = get_int(lilian);
    if (n < 1 || n > MAX_DAY) {
        put_int(out, 0);
        put_fc(fc, 2512);
        return 0;
    }
    put_int(out, (n + 4) % 7 + 1);
    put_fc(fc, 0);
    return 0;
}

int CEESECS(unsigned char *ts, unsigned char *pic, unsigned char *seconds, unsigned char *fc) {
    tok p[64];
    int np = picture("CEESECS", pic, p);
    int dl = (ts[0] << 8) | ts[1];
    const unsigned char *d = ts + 2;
    long v[7] = {-1, -1, -1, 0, 0, 0, 0};
    int pos = 0;
    if (dl > 0 && d[0] == ' ') {
        refuse("CEESECS", "a timestamp with leading blanks");
    }
    for (int k = 0; k < np; k++) {
        const char *t = p[k].tag;
        char next = k + 1 < np && !p[k + 1].tag[0] ? p[k + 1].lit : 0;
        int w = t[0] ? (int)strlen(t) : 1;
        if (!strcmp(t, "DDD")) {
            refuse("CEESECS", "picture token DDD (a Julian day)");
        }
        if (pos + w > dl) {
            refuse("CEESECS", "a timestamp shorter than its picture");
        }
        if (!t[0]) {
            if (d[pos] != (unsigned char)p[k].lit) {
                put_fc(fc, 2525);
                put_double(seconds, 0.0);
                return 0;
            }
            pos++;
            continue;
        }
        long val = 0;
        for (int i = 0; i < w; i++) {
            int c = d[pos + i];
            if (c < '0' || c > '9') {
                if (next && c == next) {
                    refuse("CEESECS", "a field with its leading zeros omitted");
                }
                put_fc(fc, 2525);
                put_double(seconds, 0.0);
                return 0;
            }
            val = val * 10 + (c - '0');
        }
        pos += w;
        if (!strcmp(t, "YYYY")) {
            v[0] = val;
        } else if (!strcmp(t, "YY")) {
            long base = system_year("CEESECS") - century_start; /* the window's first year */
            v[0] = base + ((val - base) % 100 + 100) % 100;
        } else if (!strcmp(t, "MM")) {
            v[1] = val;
        } else if (!strcmp(t, "DD")) {
            v[2] = val;
        } else if (!strcmp(t, "HH")) {
            v[3] = val;
        } else if (!strcmp(t, "MI")) {
            v[4] = val;
        } else if (!strcmp(t, "SS")) {
            v[5] = val;
        } else if (!strcmp(t, "99")) {
            v[6] = val * 10;
        } else {
            v[6] = val;
        }
    }
    if (v[0] < 0 || v[1] < 0 || v[2] < 0) {
        refuse("CEESECS", "a picture without a full date");
    }
    isec(v, seconds, fc, 2508, 2521);
    return 0;
}
