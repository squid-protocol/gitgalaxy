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

    // [rule RT-LE-CEEDAYS]
    public static void call(Field date, Field pic, Field lilian, Field fc) {
        byte[] db = date.storage().bytes;
        int d0 = date.offset();
        byte[] pb = pic.storage().bytes;
        int p0 = pic.offset();
        int dl = ((db[d0] & 0xff) << 8) | (db[d0 + 1] & 0xff);
        int pl = ((pb[p0] & 0xff) << 8) | (pb[p0 + 1] & 0xff);
        int d = d0 + 2;
        int p = p0 + 2;
        char[] kind = new char[3];
        int nt = 0;
        int sepd = -1;
        byte sep = 0;
        int i = 0;
        int have = 0;
        int span = 0;
        while (i < pl && span == 0) {
            if (nt > 0) {
                boolean isSep = pb[p + i] == '-' || pb[p + i] == '/' || pb[p + i] == '.';
                if (sepd < 0) {
                    sepd = isSep ? 1 : 0;
                    sep = isSep ? pb[p + i] : 0;
                }
                if (sepd == 1) {
                    if (!isSep || pb[p + i] != sep) {
                        break;
                    }
                    i++;
                }
            }
            char k;
            int w;
            // a token is looked for only if it has not been seen, and DDD only before MM / DD: looking further would
            // read past the span, and past the item when the picture's declared length overruns it (CRECUST)
            if ((have & (1 << ('Y' - 'A'))) == 0 && i + 4 <= pl && is(pb, p + i, "YYYY")) {
                k = 'Y';
                w = 4;
            } else if ((have & ~(1 << ('Y' - 'A'))) == 0 && i + 3 <= pl && is(pb, p + i, "DDD")) {
                k = 'J';
                w = 3;
            } else if ((have & (1 << ('D' - 'A'))) == 0 && i + 2 <= pl && is(pb, p + i, "DD")) {
                k = 'D';
                w = 2;
            } else if ((have & (1 << ('M' - 'A'))) == 0 && i + 2 <= pl && is(pb, p + i, "MM")) {
                k = 'M';
                w = 2;
            } else {
                break;
            }
            int bit = 1 << (k - 'A');
            if ((have & bit) != 0 || nt >= 3) {
                break;
            }
            have |= bit;
            kind[nt++] = k;
            i += w;
            int y = 1 << ('Y' - 'A');
            int m = 1 << ('M' - 'A');
            int dd = 1 << ('D' - 'A');
            int j = 1 << ('J' - 'A');
            if ((have & j) != 0 && (have & ~(y | j)) != 0) {
                break; // DDD with MM or DD
            }
            if (((have & y) != 0 && (have & m) != 0 && (have & dd) != 0) || ((have & y) != 0 && (have & j) != 0)) {
                span = i;
            }
        }
        if (span == 0) {
            throw new UnsupportedOperationException("CEEDAYS: picture not modelled");
        }
        // owner decisions (register L1): 2026-10-14 the picture's tail past the span is assumed ignored only when it is
        // all blanks, a non-blank byte is refused by name; 2026-10-23 a byte past the picture item (CRECUST's declared
        // length 10 over 8: storage IBM does not specify) is ASSUMED blank, so it is never read
        for (int t = span; t < pl; t++) {
            if (2 + t < pic.length() && pb[p + t] != ' ') {
                throw new UnsupportedOperationException(
                    "CEEDAYS: picture not modelled: a non-blank tail after the date tokens");
            }
        }
        putLilian(lilian, 0);
        int cover = Math.min(dl, span);
        if (cover > 0 && db[d + cover - 1] == ' ') {
            throw new UnsupportedOperationException("CEEDAYS: a date with trailing blanks is not modelled");
        }
        if (dl < span) {
            putFc(fc, 2507);
            return;
        }
        int y = 0;
        int m = 1;
        int dd = 1;
        int doy = 0;
        int at = 0;
        for (int t = 0; t < nt; t++) {
            int w = kind[t] == 'Y' ? 4 : kind[t] == 'J' ? 3 : 2;
            if (t > 0 && sep != 0) {
                if (db[d + at] != sep) {
                    putFc(fc, 2520);
                    return;
                }
                at++;
            }
            int v = digits(db, d + at, w);
            if (v < 0) {
                putFc(fc, 2520);
                return;
            }
            at += w;
            switch (kind[t]) {
                case 'Y' -> y = v;
                case 'M' -> m = v;
                case 'D' -> dd = v;
                default -> doy = v;
            }
        }
        int[] mdays = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        long days;
        if (kind[0] == 'J' || kind[1] == 'J') {
            if (doy < 1 || doy > 365 + (leap(y) ? 1 : 0)) {
                putFc(fc, 2508);
                return;
            }
            days = civil(y, 1, 1) + doy - 1 - civil(1582, 10, 14);
        } else {
            if (m < 1 || m > 12) {
                throw new UnsupportedOperationException("CEEDAYS: a month outside 1-12 is not modelled");
            }
            if (dd < 1 || dd > mdays[m - 1] + (m == 2 && leap(y) ? 1 : 0)) {
                putFc(fc, 2508);
                return;
            }
            days = civil(y, m, dd) - civil(1582, 10, 14);
        }
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
