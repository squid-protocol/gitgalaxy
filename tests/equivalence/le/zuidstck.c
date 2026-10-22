/*
 * zuidstck.c -- zECS's store-clock wrapper ZUIDSTCK as a stand-in for the equivalence harness (#5945, register X47).
 * The estate holds no source for the assembler module, so the 16 bytes it returns are a STATED INPUT of the run, never
 * the host clock. The twin of det/cobolrt/le/Zuidstck.java: the same bytes, the same refusal.
 *
 *   CALL "ZUIDSTCK" USING BY REFERENCE THE-TOD      (THE-TOD PIC X(16))
 *
 * The run states the bytes as $GGC_ZUIDSTCK_TOD, 32 hexadecimal digits (the case's "tod"). The 16 bytes are opaque: the
 * program keeps only THE-TOD(1:6) as a key prefix, and the STCK / STCKE layout is not modelled. An unstated or
 * malformed TOD is refused (exit 98), never answered with a clock reading. Nothing of IBM's or zECS's is shipped.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

int ZUIDSTCK(unsigned char *tod) {
    const char *s = getenv("GGC_ZUIDSTCK_TOD");
    unsigned char out[16];
    if (!s || strlen(s) != 32) goto refuse;
    for (int i = 0; i < 16; i++) {
        int hi = nibble(s[2 * i]), lo = nibble(s[2 * i + 1]);
        if (hi < 0 || lo < 0) goto refuse;
        out[i] = (unsigned char)(hi * 16 + lo);
    }
    memcpy(tod, out, 16);
    return 0;
refuse:
    fprintf(stderr, "ZUIDSTCK: a TOD the run does not state ($GGC_ZUIDSTCK_TOD, 32 hexadecimal digits) is not modelled\n");
    exit(98);
}
