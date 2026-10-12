/*
 * ceeloct.c -- a model of the Language Environment callable service CEELOCT for the equivalence harness (#4884).
 * GnuCOBOL has no LE services; a program that CALLs "CEELOCT" (CBSA's CRECUST) runs against this instead, and a port
 * is proven against what this returns. The twin of det/cobolrt/le/Ceeloct.java.
 *
 *   CALL "CEELOCT" USING output_Lilian, output_seconds, output_Gregorian, fc
 *
 * (IBM z/OS Language Environment Programming Reference, "CEELOCT -- Get current local time"):
 *   output_Lilian      fullword binary: days since 14 October 1582 (15 October 1582 is day 1)
 *   output_seconds     double float: seconds since 00:00:00 on 14 October 1582, leap seconds not counted
 *   output_Gregorian   YYYYMMDDHHMISS999 (17 characters; IBM's documented field is longer: what the remaining bytes
 *                      hold is not documented, so only the 17 are written)
 *   fc                 the 12-byte feedback token, all zero on success
 * The local time is the run's pinned clock, $COB_CURRENT_DATE ("YYYY/MM/DD HH:MM:SS.CC", the case's clock, which the
 * runner also gives GnuCOBOL's FUNCTION CURRENT-DATE). Without it the model refuses (exit 98): no proof rests on the
 * wall clock. output_seconds is written as a native IEEE double (GnuCOBOL's COMP-2; the Java side holds the same
 * value in the item's own usage, register C6).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static long civil(int y, int m, int d) {
    y -= m <= 2;
    long era = (y >= 0 ? y : y - 399) / 400;
    long yoe = y - era * 400;
    long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe;
}

int CEELOCT(unsigned char *lilian, unsigned char *seconds, unsigned char *gregorian, unsigned char *fc) {
    const char *s = getenv("COB_CURRENT_DATE");
    int y, mo, d, hh, mi, ss, hs = 0;
    if (!s || sscanf(s, "%d/%d/%d %d:%d:%d.%d", &y, &mo, &d, &hh, &mi, &ss, &hs) < 6) {
        fprintf(stderr, "CEELOCT: no pinned clock ($COB_CURRENT_DATE) is not modelled\n");
        exit(98);
    }
    long days = civil(y, mo, d) - civil(1582, 10, 14);
    lilian[0] = (unsigned char)(days >> 24);
    lilian[1] = (unsigned char)(days >> 16);
    lilian[2] = (unsigned char)(days >> 8);
    lilian[3] = (unsigned char)days;
    double secs = (double)(days * 86400L + hh * 3600L + mi * 60L + ss) + hs / 100.0;
    memcpy(seconds, &secs, sizeof secs);
    char g[24];
    snprintf(g, sizeof g, "%04d%02d%02d%02d%02d%02d%03d", y, mo, d, hh, mi, ss, hs * 10);
    memcpy(gregorian, g, 17);
    memset(fc, 0, 12);
    return 0;
}
