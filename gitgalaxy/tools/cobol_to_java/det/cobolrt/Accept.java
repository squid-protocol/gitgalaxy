package __PACKAGE__.cobolrt;

/** ACCEPT identifier FROM the system date or time (#4893): a class of its own, so a port that never ACCEPTs names it not. */
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
}
