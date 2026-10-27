#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's time support (ASKTIME / FORMATTIME, split out by #5274)
#
# PURPOSE:
# The time part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): formattimeCheck, asktime and the
# FORMATTIME renderers (formatDate, formatNumber, formatTime). The forge splices it into CicsTask where it always sat,
# so the class is byte-identical.
# ==============================================================================

TIME_JAVA = """\
    /** EXEC CICS FORMATTIME's condition (IBM): INVREQ (16) RESP2 1 when the ABSTIME value is less than zero ("or not in
     *  packed-decimal format": the port reads the field by its declared usage). {resp, resp2}. */
    public static int[] formattimeCheck(long abstime) {
        return abstime < 0 ? new int[] {16, 1} : new int[] {0, 0};
    }

    /** FORMATTIME with no RESP on an ABSTIME below zero: INVREQ's HANDLE CONDITION / default abend is not modelled (X28). */
    private static void refuseNegativeAbstime(long abstime) {
        if (abstime < 0) {
            throw new UnsupportedOperationException("FORMATTIME ABSTIME below zero without RESP: INVREQ's handling is not modelled");
        }
    }

    private static final LocalDateTime ABSTIME_EPOCH = LocalDateTime.of(1900, 1, 1, 0, 0);

    /** ASKTIME ABSTIME (IBM CICS TS): milliseconds since 00:00 on 1 January 1900, at the task's clock. */
    public long asktime() {
        return java.time.Duration.between(ABSTIME_EPOCH, now()).toMillis();
    }

    /** FORMATTIME ABSTIME(t) YYYYMMDD / MMDDYYYY / DDMMYYYY / YYMMDD / MMDDYY / DDMMYY: the date of t in that form,
     *  its parts joined by `datesep` ("" for no DATESEP; DATESEP with no value is "/"). */
    public static String formatDate(long abstime, String form, String datesep) {
        refuseNegativeAbstime(abstime);
        LocalDateTime t = ABSTIME_EPOCH.plus(java.time.Duration.ofMillis(abstime));
        String y4 = String.format(java.util.Locale.ROOT, "%04d", t.getYear()), y2 = y4.substring(2);
        String m = String.format(java.util.Locale.ROOT, "%02d", t.getMonthValue()), d = String.format(java.util.Locale.ROOT, "%02d", t.getDayOfMonth());
        String doy = String.format(java.util.Locale.ROOT, "%03d", t.getDayOfYear());
        List<String> parts = switch (form) {
            case "YYYYMMDD" -> List.of(y4, m, d);
            case "MMDDYYYY" -> List.of(m, d, y4);
            case "DDMMYYYY" -> List.of(d, m, y4);
            case "YYMMDD" -> List.of(y2, m, d);
            case "MMDDYY" -> List.of(m, d, y2);
            case "DDMMYY" -> List.of(d, m, y2);
            case "YYDDD" -> List.of(y2, doy);
            case "YYYYDDD" -> List.of(y4, doy);
            case "YYDDMM" -> List.of(y2, d, m);
            case "YYYYDDMM" -> List.of(y4, d, m);
            default -> throw new IllegalArgumentException("FORMATTIME " + form + " is not modelled");
        };
        return String.join(datesep, parts);
    }

    /** FORMATTIME ABSTIME(t) DAYCOUNT / DAYOFMONTH / DAYOFWEEK / MONTHOFYEAR / YEAR / MILLISECONDS: the binary integer IBM
     *  describes. DAYCOUNT "the number of days since 1 January 1900 (day 1)": 1 January 1900 is day 1. DAYOFWEEK: Sunday=0,
     *  Saturday=6. MILLISECONDS: the milliseconds in the current second, 0 - 999. */
    public static long formatNumber(long abstime, String form) {
        refuseNegativeAbstime(abstime);
        LocalDateTime t = ABSTIME_EPOCH.plus(java.time.Duration.ofMillis(abstime));
        return switch (form) {
            case "DAYCOUNT" -> abstime / 86_400_000L + 1;
            case "DAYOFMONTH" -> t.getDayOfMonth();
            case "DAYOFWEEK" -> t.getDayOfWeek().getValue() % 7;
            case "MONTHOFYEAR" -> t.getMonthValue();
            case "YEAR" -> t.getYear();
            case "MILLISECONDS" -> abstime % 1000;
            default -> throw new IllegalArgumentException("FORMATTIME " + form + " is not modelled");
        };
    }

    /** FORMATTIME ABSTIME(t) TIME: hhmmss of t, joined by `timesep` ("" for no TIMESEP; TIMESEP alone is ":"). */
    public static String formatTime(long abstime, String timesep) {
        refuseNegativeAbstime(abstime);
        LocalDateTime t = ABSTIME_EPOCH.plus(java.time.Duration.ofMillis(abstime));
        return String.join(timesep, String.format(java.util.Locale.ROOT, "%02d", t.getHour()), String.format(java.util.Locale.ROOT, "%02d", t.getMinute()),
                String.format(java.util.Locale.ROOT, "%02d", t.getSecond()));
    }

"""
