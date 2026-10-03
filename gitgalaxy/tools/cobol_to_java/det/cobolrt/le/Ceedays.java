package __PACKAGE__.cobolrt.le;

import __PACKAGE__.cobolrt.Field;

/**
 * CEEDAYS -- convert a date to Lilian format (IBM z/OS Language Environment Programming Reference), as the
 * equivalence harness models it for the COBOL side (tests/equivalence/le/ceedays.c): the same conditions, the
 * same bytes, and the same refusals -- what that model does not model, this does not either.
 *
 *   CALL "CEEDAYS" USING input_char_date, picture_string, output_Lilian_date, fc
 */
public final class Ceedays {
    private Ceedays() {
    }

    public static void call(Field date, Field pic, Field lilian, Field fc) {
        byte[] db = date.storage().bytes;
        int d0 = date.offset();
        byte[] pb = pic.storage().bytes;
        int p0 = pic.offset();
        int dl = ((db[d0] & 0xff) << 8) | (db[d0 + 1] & 0xff);
        int pl = ((pb[p0] & 0xff) << 8) | (pb[p0 + 1] & 0xff);
        int d = d0 + 2;
        int p = p0 + 2;
        byte sep = pl == 10 ? pb[p + 4] : 0;
        if (!(pl == 10 && is(pb, p, "YYYY") && is(pb, p + 5, "MM") && is(pb, p + 8, "DD") && pb[p + 7] == sep
                && (sep == '-' || sep == '/' || sep == '.'))) {
            throw new UnsupportedOperationException("CEEDAYS: picture not modelled");
        }
        putLilian(lilian, 0);
        if (dl > 0 && db[d + dl - 1] == ' ') {
            throw new UnsupportedOperationException("CEEDAYS: a date with trailing blanks is not modelled");
        }
        if (dl < pl) {
            putFc(fc, 2507);
            return;
        }
        int y = digits(db, d, 4);
        int m = digits(db, d + 5, 2);
        int dd = digits(db, d + 8, 2);
        if (y < 0 || m < 0 || dd < 0 || db[d + 4] != sep || db[d + 7] != sep) {
            putFc(fc, 2520);
            return;
        }
        int[] mdays = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        if (m < 1 || m > 12) {
            throw new UnsupportedOperationException("CEEDAYS: a month outside 1-12 is not modelled");
        }
        if (dd < 1 || dd > mdays[m - 1] + (m == 2 && leap(y) ? 1 : 0)) {
            putFc(fc, 2508);
            return;
        }
        long days = civil(y, m, dd) - civil(1582, 10, 14);
        if (days < 1 || y > 9999) {
            putFc(fc, 2513);
            return;
        }
        putLilian(lilian, days);
        putFc(fc, 0);
    }

    private static boolean is(byte[] b, int at, String s) {
        for (int i = 0; i < s.length(); i++) {
            if (b[at + i] != (byte) s.charAt(i)) {
                return false;
            }
        }
        return true;
    }

    private static int digits(byte[] b, int at, int n) {
        int v = 0;
        for (int i = 0; i < n; i++) {
            int c = b[at + i] & 0xff;
            if (c < '0' || c > '9') {
                return -1;
            }
            v = v * 10 + (c - '0');
        }
        return v;
    }

    private static boolean leap(int y) {
        return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
    }

    private static long civil(int y, int m, int d) {
        y -= m <= 2 ? 1 : 0;
        long era = (y >= 0 ? y : y - 399) / 400;
        long yoe = y - era * 400;
        long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
        long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        return era * 146097 + doe;
    }

    private static void putLilian(Field out, long days) {
        byte[] b = out.storage().bytes;
        int o = out.offset();
        b[o] = (byte) (days >> 24);
        b[o + 1] = (byte) (days >> 16);
        b[o + 2] = (byte) (days >> 8);
        b[o + 3] = (byte) days;
    }

    private static void putFc(Field fc, int msgno) {
        byte[] b = fc.storage().bytes;
        int o = fc.offset();
        java.util.Arrays.fill(b, o, o + 12, (byte) 0);
        if (msgno == 0) {
            return;
        }
        b[o + 1] = 0x03;
        b[o + 2] = (byte) (msgno >> 8);
        b[o + 3] = (byte) msgno;
        b[o + 4] = 0x59;
        b[o + 5] = (byte) 0xC3;
        b[o + 6] = (byte) 0xC5;
        b[o + 7] = (byte) 0xC5;
    }
}
