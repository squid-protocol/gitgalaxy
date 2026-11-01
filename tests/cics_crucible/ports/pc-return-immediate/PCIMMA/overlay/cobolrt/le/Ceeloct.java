package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;

/**
 * CEELOCT -- get the current local time (IBM z/OS Language Environment Programming Reference), as the equivalence
 * harness models it for the COBOL side (tests/equivalence/le/ceeloct.c): the same values from the same pinned clock.
 *
 *   CALL "CEELOCT" USING output_Lilian, output_seconds, output_Gregorian, fc
 *
 * The local time is the run's clock (FUNCTION CURRENT-DATE's text: YYYYMMDDHHMMSShh...). output_Lilian: days since
 * 14 October 1582 (15 October 1582 is day 1), a fullword binary; output_seconds: seconds since 00:00:00 on 14 October
 * 1582 (leap seconds not counted), stored in the item as its own usage holds it (COMP-2); output_Gregorian: the 17
 * characters YYYYMMDDHHMISS999 (milliseconds); fc: 12 zero bytes, the feedback code of success. No condition arises from
 * the clock the run gives, which is always valid. A scenario's fault plan (#6882) can still
 * plan IBM's one failure, CEE2F3 (severity 3, message 2531, "The local time was not available from the system"): the
 * generated call site then runs {@link #fail} instead of {@link #call}, and the three outputs are left as they were.
 */
public final class Ceeloct {
    private Ceeloct() {
    }

    // [rule RT-LE-CEELOCT]
    public static void call(String now, Field lilian, Field seconds, Field gregorian, Field fc, Charset cs) {
        int y = Integer.parseInt(now.substring(0, 4));
        int mo = Integer.parseInt(now.substring(4, 6));
        int d = Integer.parseInt(now.substring(6, 8));
        int hh = Integer.parseInt(now.substring(8, 10));
        int mi = Integer.parseInt(now.substring(10, 12));
        int ss = Integer.parseInt(now.substring(12, 14));
        int hs = Integer.parseInt(now.substring(14, 16));
        long days = civil(y, mo, d) - civil(1582, 10, 14);
        byte[] b = lilian.storage().bytes;
        int o = lilian.offset();
        b[o] = (byte) (days >> 24);
        b[o + 1] = (byte) (days >> 16);
        b[o + 2] = (byte) (days >> 8);
        b[o + 3] = (byte) days;
        long whole = days * 86400L + hh * 3600L + mi * 60L + ss;
        Cobol.store(seconds, BigDecimal.valueOf(whole).add(BigDecimal.valueOf(hs, 2)), false, cs);
        String g = String.format(java.util.Locale.ROOT, "%04d%02d%02d%02d%02d%02d%03d", y, mo, d, hh, mi, ss, hs * 10);
        byte[] gb = g.getBytes(cs);
        System.arraycopy(gb, 0, gregorian.storage().bytes, gregorian.offset(), gb.length);
        java.util.Arrays.fill(fc.storage().bytes, fc.offset(), fc.offset() + 12, (byte) 0);
    }

    // [rule RT-LE-CEELOCT]
    /** The feedback code of a failed CEELOCT: condition token CEE2F3 (severity 3, message number `msgno`, case 1, "CEE"). */
    public static void fail(Field fc, int msgno) {
        byte[] b = fc.storage().bytes;
        int o = fc.offset();
        java.util.Arrays.fill(b, o, o + 12, (byte) 0);
        b[o + 1] = 0x03;
        b[o + 2] = (byte) (msgno >> 8);
        b[o + 3] = (byte) msgno;
        b[o + 4] = 0x59;
        b[o + 5] = (byte) 0xC3;
        b[o + 6] = (byte) 0xC5;
        b[o + 7] = (byte) 0xC5;
    }

    private static long civil(int y, int m, int d) {
        y -= m <= 2 ? 1 : 0;
        long era = (y >= 0 ? y : y - 399) / 400;
        long yoe = y - era * 400;
        long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
        long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        return era * 146097 + doe;
    }
}
