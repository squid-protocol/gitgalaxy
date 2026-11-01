package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;

/**
 * ZUIDSTCK -- zECS's assembler store-clock wrapper (ZECS001 4000-GET-COUNTER), as a stand-in whose 16 bytes are a
 * STATED INPUT of the run, never the host clock (register X47, #5945):
 *
 *   CALL ZUIDSTCK USING BY REFERENCE THE-TOD      (THE-TOD PIC X(16))
 *
 * The run states the bytes as $GGC_ZUIDSTCK_TOD, 32 hexadecimal digits. The 16 bytes are opaque: the program keeps only
 * THE-TOD(1:6) as a key prefix and never reads them as a time, so the STCK / STCKE layout (IBM z/Architecture
 * Principles of Operation, STORE CLOCK EXTENDED: a 16-byte value) is context, not a claim. An unstated or malformed TOD
 * is refused, never answered with a clock reading. The oracle's twin is tests/equivalence/le/zuidstck.c.
 */
public final class Zuidstck {
    private Zuidstck() {
    }

    private static String stated;

    /** The harness states a run's TOD per task (all tasks share one JVM): it wins over the environment; null clears it. */
    public static void state(String hex) {
        stated = hex;
    }

    // [rule RT-LE-ZUIDSTCK]
    public static void call(Field tod) {
        String hex = stated != null ? stated : System.getenv("GGC_ZUIDSTCK_TOD");
        if (hex == null || !hex.matches("[0-9A-Fa-f]{32}")) {
            throw new UnsupportedOperationException(
                "ZUIDSTCK: a TOD the run does not state ($GGC_ZUIDSTCK_TOD, 32 hexadecimal digits) is not modelled");
        }
        if (tod.length() != 16) {
            throw new UnsupportedOperationException("ZUIDSTCK: a 16-byte TOD item expected (got " + tod.length() + ")");
        }
        byte[] b = tod.storage().bytes;
        int o = tod.offset();
        for (int i = 0; i < 16; i++) {
            b[o + i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
    }
}
