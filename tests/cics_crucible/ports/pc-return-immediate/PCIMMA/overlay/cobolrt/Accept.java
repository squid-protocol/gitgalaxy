package com.gitgalaxy.modernized.cobolrt;

/** ACCEPT identifier FROM the system date or time (#4893) or SYSIN (#5106): a class of its own, so a port that never ACCEPTs names it not. */
public final class Accept {
    private Accept() {
    }

    /** ACCEPT FROM DATE / DATE YYYYMMDD / DAY / DAY YYYYDDD / TIME: the run's clock -- `currentDate`, FUNCTION
     *  CURRENT-DATE's YYYYMMDDhhmmsshh -- as the unsigned integer item IBM describes (YYMMDD, YYYYMMDD, YYDDD, YYYYDDD,
     *  hhmmsshh), which the ACCEPT moves to its target as a MOVE of that item would. */
    // [rule RT-FUNC-ACCEPT-DATE]
    public static Field from(String currentDate, String what) {
        java.time.LocalDate d = java.time.LocalDate.of(Integer.parseInt(currentDate.substring(0, 4)),
                Integer.parseInt(currentDate.substring(4, 6)), Integer.parseInt(currentDate.substring(6, 8)));
        String doy = String.format(java.util.Locale.ROOT, "%03d", d.getDayOfYear());
        String digits;
        switch (what) {
            case "DATE": digits = currentDate.substring(2, 8); break;
            case "DATE YYYYMMDD": digits = currentDate.substring(0, 8); break;
            case "DAY": digits = currentDate.substring(2, 4) + doy; break;
            case "DAY YYYYDDD": digits = currentDate.substring(0, 4) + doy; break;
            case "TIME": digits = currentDate.substring(8, 16); break;
            default: throw new UnsupportedOperationException("ACCEPT FROM " + what + " is not modelled");
        }
        Storage s = Storage.of(digits.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
        return Field.zoned(s, 0, digits.length(), 0, false, false, false);
    }

    private static java.io.InputStream sysin;

    /** ACCEPT identifier FROM SYSIN (#5106, the batch input stream): the next record -- a line of standard input, its
     *  line end dropped, bytes kept as the record charset reads them -- moved to the target as an alphanumeric MOVE
     *  (a short card is space-padded, a long one truncated on the right). With no record left IBM leaves the
     *  target undefined: refused by name, never a silent blank. */
    // [rule RT-FUNC-ACCEPT-SYSIN]
    public static void sysin(Field to, java.nio.charset.Charset cs) {
        java.nio.charset.Charset rec = Cobol.recordCharset(cs);
        try {
            if (sysin == null) {
                sysin = new java.io.BufferedInputStream(System.in);
            }
            java.io.ByteArrayOutputStream line = new java.io.ByteArrayOutputStream();
            int c = sysin.read();
            if (c < 0) {
                throw new IllegalStateException("ACCEPT FROM SYSIN: no record left in the input stream");
            }
            while (c >= 0 && c != '\n') {
                line.write(c);
                c = sysin.read();
            }
            byte[] b = line.toByteArray();
            int n = b.length > 0 && b[b.length - 1] == '\r' ? b.length - 1 : b.length;
            Cobol.move(new String(b, 0, n, rec), to, rec);
        } catch (java.io.IOException e) {
            throw new IllegalStateException("ACCEPT FROM SYSIN: " + e.getMessage(), e);
        }
    }
}
