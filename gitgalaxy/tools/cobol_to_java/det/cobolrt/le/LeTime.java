package __PACKAGE__.cobolrt.le;

import __PACKAGE__.cobolrt.Cobol;
import __PACKAGE__.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;

/**
 * The Language Environment date/time callable services CEEGMT / CEEUTC, CEEDATM, CEESECS, CEEDATE, CEEISEC, CEESECI,
 * CEEDYWK, CEEQCEN and CEESCEN (#4949, #5003), as the equivalence harness models them for the COBOL side (tests/equivalence/le/le_time.c): the
 * same conditions, the same bytes, and the same refusals -- what that model does not model, this does not either
 * ("NAME: ... is not modelled"). Register L6 says what IBM documents, what is assumed and what is refused.
 *
 * Lilian day 1 is 15 October 1582; Lilian second 86400 is 00:00:00 on that day (IBM: second 86,401 is 00:00:01 on
 * 15 October 1582). A float travels by value (Cobol.num / Cobol.store: HFP on z/OS, IEEE on the oracle, register C6).
 */
final class LeTime {
    private LeTime() {
    }

    static final long MAX_SECONDS = 265_621_680_000L; // exclusive: 24:00:00 on 31 December 9999 (IBM: 23:59:59.999)
    static final long MAX_DAY = 3_074_324L; // 31 December 9999
    private static final int[] MDAYS = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};

    static UnsupportedOperationException refuse(String service, String what) {
        return new UnsupportedOperationException(service + ": " + what + " is not modelled");
    }

    // [rule RT-LE-LILIAN]
    static boolean leap(long y) {
        return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
    }

    static int monthDays(long y, int m) {
        return MDAYS[m - 1] + (m == 2 && leap(y) ? 1 : 0);
    }

    static long civil(long y, int m, int d) {
        y -= m <= 2 ? 1 : 0;
        long era = (y >= 0 ? y : y - 399) / 400;
        long yoe = y - era * 400;
        long doy = (153L * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
        long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        return era * 146097 + doe;
    }

    static final long EPOCH = civil(1582, 10, 14);

    /** [year, month, day] of Lilian day n (1 = 15 October 1582). */
    static int[] ymd(long n) {
        long z = n + EPOCH;
        long era = (z >= 0 ? z : z - 146096) / 146097;
        long doe = z - era * 146097;
        long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
        long doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        long mp = (5 * doy + 2) / 153;
        int d = (int) (doy - (153 * mp + 2) / 5 + 1);
        int m = (int) (mp < 10 ? mp + 3 : mp - 9);
        long y = yoe + era * 400 + (m <= 2 ? 1 : 0);
        return new int[] {(int) y, m, d};
    }

    static void putInt(Field out, long v) {
        byte[] b = out.storage().bytes;
        int o = out.offset();
        b[o] = (byte) (v >> 24);
        b[o + 1] = (byte) (v >> 16);
        b[o + 2] = (byte) (v >> 8);
        b[o + 3] = (byte) v;
    }

    static int getInt(Field in) {
        byte[] b = in.storage().bytes;
        int o = in.offset();
        return ((b[o] & 0xff) << 24) | ((b[o + 1] & 0xff) << 16) | ((b[o + 2] & 0xff) << 8) | (b[o + 3] & 0xff);
    }

    /** The 12-byte feedback token: all zero for success, else severity 3, message number, case/severity/control, 'CEE'. */
    // [rule RT-LE-FEEDBACK-CODE]
    static void putFc(Field fc, int msgno) {
        byte[] b = fc.storage().bytes;
        int o = fc.offset();
        java.util.Arrays.fill(b, o, o + 12, (byte) 0);
        if (msgno != 0) {
            b[o + 1] = 0x03;
            b[o + 2] = (byte) (msgno >> 8);
            b[o + 3] = (byte) msgno;
            b[o + 4] = 0x59;
            b[o + 5] = (byte) 0xC3;
            b[o + 6] = (byte) 0xC5;
            b[o + 7] = (byte) 0xC5;
        }
    }

    // ------------------------------------------------------------------------------------------ pictures

    /** A picture's tokens: the tag ("YYYY", "YY", "MM", "DD", "DDD", "HH", "MI", "SS", "99", "999") or, for a literal
     *  character, null with the character in lit. Anything else -- a month or day name, AP, Z-suppression, eras, a
     *  lone Y / M / D / H / S / 9, a repeated token -- is refused. */
    record Tok(String tag, char lit) {
    }

    // [rule RT-LE-PICTURE-STRING]
    static java.util.List<Tok> picture(String service, Field pic) {
        byte[] pb = pic.storage().bytes;
        int p0 = pic.offset();
        int pl = ((pb[p0] & 0xff) << 8) | (pb[p0 + 1] & 0xff);
        if (pl == 0) {
            throw refuse(service, "a null picture (IBM takes the country default)");
        }
        String s = new String(pb, p0 + 2, pl, java.nio.charset.StandardCharsets.ISO_8859_1);
        String[] tags = {"YYYY", "YY", "DDD", "DD", "MM", "HH", "MI", "SS", "999", "99"};
        java.util.List<Tok> out = new java.util.ArrayList<>();
        java.util.Set<String> seen = new java.util.HashSet<>();
        for (int i = 0; i < s.length();) {
            String hit = null;
            for (String t : tags) {
                if (s.startsWith(t, i)) {
                    hit = t;
                    break;
                }
            }
            char c = s.charAt(i);
            if (hit != null) {
                if (!seen.add(hit.startsWith("YY") ? "Y" : hit.startsWith("DD") ? "D" : hit.startsWith("99") ? "9" : hit)) {
                    throw refuse(service, "picture '" + s + "' (a repeated token)");
                }
                out.add(new Tok(hit, (char) 0));
                i += hit.length();
            } else if ((c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z') || c == '9' || c == '<' || c == '>' || c == ' ' && s.isBlank()) {
                throw refuse(service, "picture '" + s + "'");
            } else {
                out.add(new Tok(null, c));
                i++;
            }
        }
        return out;
    }

    /** Format: the date part from lilian day n (never null), the time part from the seconds of the day and the
     *  milliseconds. */
    static String format(java.util.List<Tok> pic, long n, int hh, int mi, int ss, int ms) {
        int[] d = ymd(n);
        StringBuilder sb = new StringBuilder();
        for (Tok t : pic) {
            if (t.tag() == null) {
                sb.append(t.lit());
                continue;
            }
            switch (t.tag()) {
                case "YYYY" -> sb.append(String.format(java.util.Locale.ROOT, "%04d", d[0]));
                case "YY" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", d[0] % 100));
                case "MM" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", d[1]));
                case "DD" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", d[2]));
                case "DDD" -> sb.append(String.format(java.util.Locale.ROOT, "%03d", n - (civil(d[0], 1, 1) - EPOCH) + 1));
                case "HH" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", hh));
                case "MI" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", mi));
                case "SS" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", ss));
                case "99" -> sb.append(String.format(java.util.Locale.ROOT, "%02d", ms / 10));
                default -> sb.append(String.format(java.util.Locale.ROOT, "%03d", ms));
            }
        }
        return sb.toString();
    }

    /** A VSTRING result: halfword length, the text, nothing past it (register L6: the rest of the item is untouched). */
    // [rule RT-LE-VSTRING]
    static void putVstring(String service, Field out, String text, Charset cs) {
        byte[] t = text.getBytes(cs);
        if (out.length() < 2 + t.length) {
            throw refuse(service, "an output item shorter than the result (CEE2526 / CEE2527 truncation)");
        }
        byte[] b = out.storage().bytes;
        int o = out.offset();
        b[o] = (byte) (t.length >> 8);
        b[o + 1] = (byte) t.length;
        System.arraycopy(t, 0, b, o + 2, t.length);
    }

    static void clearVstring(Field out) {
        out.storage().bytes[out.offset()] = 0;
        out.storage().bytes[out.offset() + 1] = 0;
    }

    // ----------------------------------------------------------------------------------------- services

    /** CEEGMT / CEEUTC: the run's clock is GMT (the det runtime's CURRENT-DATE carries offset +0000). */
    // [rule RT-LE-CEEGMT]
    static void gmt(String now, Field lilian, Field seconds, Field fc, Charset cs) {
        long days = civil(Integer.parseInt(now.substring(0, 4)), Integer.parseInt(now.substring(4, 6)),
                Integer.parseInt(now.substring(6, 8))) - EPOCH;
        long whole = days * 86400L + Integer.parseInt(now.substring(8, 10)) * 3600L
                + Integer.parseInt(now.substring(10, 12)) * 60L + Integer.parseInt(now.substring(12, 14));
        putInt(lilian, days);
        Cobol.store(seconds, BigDecimal.valueOf(whole).add(BigDecimal.valueOf(Integer.parseInt(now.substring(14, 16)), 2)),
                false, cs);
        putFc(fc, 0);
    }

    /** The century window's start (years before the system date): the run's setting, 80 until CEESCEN changes it. */
    private static int centuryStart = 80;

    // [rule RT-LE-CEEQCEN]
    static void qcen(Field century, Field fc) {
        putInt(century, centuryStart);
        putFc(fc, 0);
    }

    /** CEESCEN: 0 to 100, else CEE2533 and the setting is unchanged. CEESECS reads it for a YY. */
    static void scen(Field century, Field fc) {
        int v = getInt(century);
        if (v < 0 || v > 100) {
            putFc(fc, 2533);
            return;
        }
        centuryStart = v;
        putFc(fc, 0);
    }

    // [rule RT-LE-CEEDATE]
    static void date(Field lilian, Field pic, Field out, Field fc, Charset cs) {
        java.util.List<Tok> p = picture("CEEDATE", pic);
        int n = getInt(lilian);
        if (n < 1 || n > MAX_DAY) {
            clearVstring(out);
            putFc(fc, 2512);
            return;
        }
        putVstring("CEEDATE", out, format(p, n, 0, 0, 0, 0), cs);
        putFc(fc, 0);
    }

    // [rule RT-LE-CEEDATM]
    static void datm(Field seconds, Field pic, Field out, Field fc, Charset cs) {
        java.util.List<Tok> p = picture("CEEDATM", pic);
        BigDecimal v = Cobol.num(seconds, cs);
        BigDecimal whole = v.setScale(0, java.math.RoundingMode.FLOOR);
        if (whole.compareTo(BigDecimal.valueOf(86400)) < 0 || whole.compareTo(BigDecimal.valueOf(MAX_SECONDS)) >= 0) {
            clearVstring(out);
            putFc(fc, 2505);
            return;
        }
        long w = whole.longValue();
        int ms = v.subtract(whole).multiply(BigDecimal.valueOf(1000)).setScale(0, java.math.RoundingMode.FLOOR).intValue();
        long sod = w % 86400;
        putVstring("CEEDATM", out, format(p, w / 86400, (int) (sod / 3600), (int) (sod / 60 % 60), (int) (sod % 60), ms), cs);
        putFc(fc, 0);
    }

    // [rule RT-LE-CEESECS]
    static void secs(String now, Field ts, Field pic, Field seconds, Field fc, Charset cs) {
        java.util.List<Tok> p = picture("CEESECS", pic);
        byte[] db = ts.storage().bytes;
        int d0 = ts.offset();
        int dl = ((db[d0] & 0xff) << 8) | (db[d0 + 1] & 0xff);
        int at = d0 + 2;
        if (dl > 0 && db[at] == ' ') {
            throw refuse("CEESECS", "a timestamp with leading blanks");
        }
        long[] v = {-1, -1, -1, 0, 0, 0, 0}; // year, month, day, hour, minute, second, milliseconds
        int pos = 0;
        for (int k = 0; k < p.size(); k++) {
            Tok t = p.get(k);
            char next = k + 1 < p.size() && p.get(k + 1).tag() == null ? p.get(k + 1).lit() : (char) 0;
            int w = t.tag() == null ? 1 : t.tag().length();
            if (t.tag() != null && t.tag().equals("DDD")) {
                throw refuse("CEESECS", "picture token DDD (a Julian day)");
            }
            if (pos + w > dl) {
                throw refuse("CEESECS", "a timestamp shorter than its picture");
            }
            if (t.tag() == null) {
                if (db[at + pos] != (byte) t.lit()) {
                    putFc(fc, 2525);
                    zero(seconds, cs);
                    return;
                }
                pos++;
                continue;
            }
            long val = 0;
            for (int i = 0; i < w; i++) {
                int c = db[at + pos + i] & 0xff;
                if (c < '0' || c > '9') {
                    if (next != 0 && c == next) {
                        throw refuse("CEESECS", "a field with its leading zeros omitted");
                    }
                    putFc(fc, 2525);
                    zero(seconds, cs);
                    return;
                }
                val = val * 10 + (c - '0');
            }
            pos += w;
            switch (t.tag()) {
                case "YYYY" -> v[0] = val;
                case "YY" -> { // the century window: [system year - start, + 99], the system year the run clock's
                    long base = Integer.parseInt(now.substring(0, 4)) - centuryStart;
                    v[0] = base + ((val - base) % 100 + 100) % 100;
                }
                case "MM" -> v[1] = val;
                case "DD" -> v[2] = val;
                case "HH" -> v[3] = val;
                case "MI" -> v[4] = val;
                case "SS" -> v[5] = val;
                case "99" -> v[6] = val * 10;
                default -> v[6] = val;
            }
        }
        if (v[0] < 0 || v[1] < 0 || v[2] < 0) {
            throw refuse("CEESECS", "a picture without a full date");
        }
        isec(v, seconds, fc, cs, 2508, 2521);
    }

    /** The shared check and conversion of CEESECS and CEEISEC; the day / year codes differ between them. */
    // [rule RT-LE-CEEISEC]
    private static void isec(long[] v, Field seconds, Field fc, Charset cs, int dayCode, int yearCode) {
        int bad = 0;
        int code = 0;
        if (v[0] < 1582 || v[0] > 9999) {
            bad++;
            code = yearCode;
        }
        if (v[1] < 1 || v[1] > 12) {
            bad++;
            code = 2517;
        }
        boolean ok = v[0] >= 1582 && v[0] <= 9999 && v[1] >= 1 && v[1] <= 12;
        if (v[2] < 1 || v[2] > (ok ? monthDays(v[0], (int) v[1]) : 31)) {
            bad++;
            code = dayCode;
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
            throw refuse("CEEISEC / CEESECS", "more than one invalid field (IBM does not say which condition comes first)");
        }
        long days = bad == 0 ? civil(v[0], (int) v[1], (int) v[2]) - EPOCH : 0;
        if (bad == 0 && days < 1) {
            bad = 1;
            code = 2513;
        }
        if (bad != 0) {
            zero(seconds, cs);
            putFc(fc, code);
            return;
        }
        Cobol.store(seconds, BigDecimal.valueOf(days * 86400L + v[3] * 3600 + v[4] * 60 + v[5]).add(BigDecimal.valueOf(v[6], 3)),
                false, cs);
        putFc(fc, 0);
    }

    static void isec(Field y, Field mo, Field d, Field h, Field mi, Field s, Field ms, Field seconds, Field fc, Charset cs) {
        long[] v = {getInt(y), getInt(mo), getInt(d), getInt(h), getInt(mi), getInt(s), getInt(ms)};
        isec(v, seconds, fc, cs, 2511, 2514);
    }

    // [rule RT-LE-CEESECI]
    static void seci(Field seconds, Field y, Field mo, Field d, Field h, Field mi, Field s, Field ms, Field fc, Charset cs) {
        BigDecimal v = Cobol.num(seconds, cs);
        BigDecimal whole = v.setScale(0, java.math.RoundingMode.FLOOR);
        if (whole.compareTo(BigDecimal.valueOf(86400)) < 0 || whole.compareTo(BigDecimal.valueOf(MAX_SECONDS)) >= 0) {
            for (Field f : new Field[] {y, mo, d, h, mi, s, ms}) {
                putInt(f, 0);
            }
            putFc(fc, 2505);
            return;
        }
        long w = whole.longValue();
        int[] date = ymd(w / 86400);
        long sod = w % 86400;
        putInt(y, date[0]);
        putInt(mo, date[1]);
        putInt(d, date[2]);
        putInt(h, sod / 3600);
        putInt(mi, sod / 60 % 60);
        putInt(s, sod % 60);
        putInt(ms, v.subtract(whole).multiply(BigDecimal.valueOf(1000)).setScale(0, java.math.RoundingMode.FLOOR).longValue());
        putFc(fc, 0);
    }

    // [rule RT-LE-CEEDYWK]
    static void dywk(Field lilian, Field out, Field fc) {
        long n = getInt(lilian);
        if (n < 1 || n > MAX_DAY) {
            putInt(out, 0);
            putFc(fc, 2512);
            return;
        }
        putInt(out, (n + 4) % 7 + 1);
        putFc(fc, 0);
    }

    private static void zero(Field seconds, Charset cs) {
        Cobol.store(seconds, BigDecimal.ZERO, false, cs);
    }
}
