package com.gitgalaxy.modernized.service;

import java.time.DateTimeException;
import java.time.LocalDate;
import java.util.Locale;
import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.call.CobolRef;

@Service
@RequiredArgsConstructor
public class CsutldtcService {

    private static final Logger log = LoggerFactory.getLogger(CsutldtcService.class);

    /** Feedback of a CEEDAYS call: SEVERITY and MSG-NO of FEEDBACK-CODE (CASE-1-CONDITION-ID). */
    private record Feedback(int severity, int msgNo) {
    }

    private static final Feedback FC_INVALID_DATE = new Feedback(0, 0);       // success token: all zero
    private static final Feedback FC_INSUFFICIENT_DATA = new Feedback(3, 0x09CB);
    private static final Feedback FC_BAD_DATE_VALUE = new Feedback(3, 0x09CC);
    private static final Feedback FC_UNSUPP_RANGE = new Feedback(3, 0x09D1);
    private static final Feedback FC_INVALID_MONTH = new Feedback(3, 0x09D5);
    private static final Feedback FC_BAD_PIC_STRING = new Feedback(3, 0x09D6);
    private static final Feedback FC_NON_NUMERIC_DATA = new Feedback(3, 0x09D8);

    public void executeCsutldtc(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CSUTLDTC");
        // The program is only entered by CALL (handleCall); without parameters it runs on blank items.
        CobolRef<String> result = CobolRef.of(" ".repeat(80));
        int rc = handleCall(CobolRef.of(" ".repeat(10)), CobolRef.of(" ".repeat(10)), result);
        log.info("Csutldtc: return code {} result {}", rc, result.get());
    }

    /** PROCEDURE DIVISION USING LS-DATE, LS-DATE-FORMAT, LS-RESULT; returns RETURN-CODE. */
    public int handleCall(CobolRef<String> lsDate, CobolRef<String> lsDateFormat, CobolRef<String> lsResult) {
        log.info("Csutldtc: handleCall");
        String date = fit(lsDate.get(), 10);
        String format = fit(lsDateFormat.get(), 10);

        // Main line: INITIALIZE WS-MESSAGE (fillers keep their VALUEs), MOVE SPACES TO WS-DATE
        // PERFORM A000-MAIN THRU A000-MAIN-EXIT
        // A000-MAIN: MOVE LS-DATE TO VSTRING-TEXT / WS-DATE, MOVE LS-DATE-FORMAT TO ... / WS-DATE-FMT,
        // CALL "CEEDAYS"
        Feedback fb = ceedays(date, format);

        // A000-MAIN: MOVE WS-DATE-TO-TEST TO WS-DATE
        // DEFECT KEPT: WS-DATE-TO-TEST is the whole group (2-byte length + text = 12 bytes), not its
        // VSTRING-TEXT, so the move into X(10) stores X'000A' and the first 8 characters of the date.
        // One-line fix: MOVE VSTRING-TEXT OF WS-DATE-TO-TEST TO WS-DATE.
        String wsDate = fit("\u0000\n" + date, 10);

        // A000-MAIN: MOVE SEVERITY / MSG-NO OF FEEDBACK-CODE TO WS-SEVERITY-N / WS-MSG-NO-N (PIC 9(4))
        int severityN = Math.abs(fb.severity()) % 10000;
        int msgNoN = Math.abs(fb.msgNo()) % 10000;

        // A000-MAIN: EVALUATE TRUE ... WS-RESULT (X(15))
        String wsResult;
        if (fb.equals(FC_INVALID_DATE)) {
            wsResult = "Date is valid";
        } else if (fb.equals(FC_INSUFFICIENT_DATA)) {
            wsResult = "Insufficient";
        } else if (fb.equals(FC_BAD_DATE_VALUE)) {
            wsResult = "Datevalue error";
        } else if (fb.msgNo() == 0x09CD && fb.severity() == 3) {
            wsResult = "Invalid Era    ";
        } else if (fb.equals(FC_UNSUPP_RANGE)) {
            wsResult = "Unsupp. Range  ";
        } else if (fb.equals(FC_INVALID_MONTH)) {
            wsResult = "Invalid month  ";
        } else if (fb.equals(FC_BAD_PIC_STRING)) {
            wsResult = "Bad Pic String ";
        } else if (fb.equals(FC_NON_NUMERIC_DATA)) {
            wsResult = "Nonnumeric data";
        } else if (fb.msgNo() == 0x09D9 && fb.severity() == 3) {
            wsResult = "YearInEra is 0 ";
        } else {
            wsResult = "Date is invalid";
        }

        // WS-MESSAGE layout: SEVERITY 4, FILLER 11 'Mesg Code:', MSG-NO 4, FILLER 1, WS-RESULT 15, FILLER 1,
        // FILLER 9 'TstDate:', WS-DATE 10, FILLER 1, FILLER 10 'Mask used:', WS-DATE-FMT 10, FILLER 1, FILLER 3
        String message = String.format(Locale.ROOT, "%04d", severityN)
                + fit("Mesg Code:", 11)
                + String.format(Locale.ROOT, "%04d", msgNoN)
                + " "
                + fit(wsResult, 15)
                + " "
                + fit("TstDate:", 9)
                + wsDate
                + " "
                + "Mask used:"
                + format
                + " "
                + "   ";

        // Main line: MOVE WS-MESSAGE TO LS-RESULT, MOVE WS-SEVERITY-N TO RETURN-CODE, EXIT PROGRAM
        lsResult.set(fit(message, 80));
        return severityN;
    }

    /**
     * Stand-in for CALL "CEEDAYS" (not in the estate): validates the date against the picture string.
     * Supported picture tokens: YYYY, MM, DD plus literal separators (trailing blanks ignored). Other tokens
     * (YY, MMM, JJJ, eras ...) are answered as a bad picture string -- the estate's callers use YYYYMMDD and
     * YYYY-MM-DD only. A date character where the picture has a separator is answered as non-numeric data
     * (as the original run reports it), not as a bad date value.
     */
    private Feedback ceedays(String date, String format) {
        String d = stripTrailing(date);
        String f = stripTrailing(format).toUpperCase(Locale.ROOT);
        if (f.isEmpty()) {
            return FC_BAD_PIC_STRING;
        }
        if (d.isEmpty()) {
            return FC_INSUFFICIENT_DATA;
        }
        int pos = 0;
        int year = -1;
        int month = -1;
        int day = -1;
        int i = 0;
        while (i < f.length()) {
            String tok;
            if (f.startsWith("YYYY", i)) {
                tok = "YYYY";
            } else if (f.startsWith("MM", i) && !f.startsWith("MMM", i)) {
                tok = "MM";
            } else if (f.startsWith("DD", i)) {
                tok = "DD";
            } else if (Character.isLetter(f.charAt(i))) {
                return FC_BAD_PIC_STRING;
            } else {
                tok = null;
            }
            if (tok == null) {
                if (pos >= d.length()) {
                    return FC_INSUFFICIENT_DATA;
                }
                if (d.charAt(pos) != f.charAt(i)) {
                    return FC_NON_NUMERIC_DATA;
                }
                pos++;
                i++;
                continue;
            }
            int n = tok.length();
            if (pos + n > d.length()) {
                return FC_INSUFFICIENT_DATA;
            }
            int v = 0;
            for (int k = 0; k < n; k++) {
                char c = d.charAt(pos + k);
                if (c < '0' || c > '9') {
                    return FC_NON_NUMERIC_DATA;
                }
                v = v * 10 + (c - '0');
            }
            if (tok.equals("YYYY")) {
                if (year >= 0) {
                    return FC_BAD_PIC_STRING;
                }
                year = v;
            } else if (tok.equals("MM")) {
                if (month >= 0) {
                    return FC_BAD_PIC_STRING;
                }
                month = v;
            } else {
                if (day >= 0) {
                    return FC_BAD_PIC_STRING;
                }
                day = v;
            }
            pos += n;
            i += n;
        }
        if (year < 0 || month < 0 || day < 0) {
            return FC_BAD_PIC_STRING;
        }
        if (pos < d.length()) {
            return FC_BAD_DATE_VALUE;
        }
        if (month < 1 || month > 12) {
            return FC_INVALID_MONTH;
        }
        LocalDate date1;
        try {
            date1 = LocalDate.of(year, month, day);
        } catch (DateTimeException e) {
            return year < 1 ? FC_UNSUPP_RANGE : FC_BAD_DATE_VALUE;
        }
        // Lilian day 1 is 1582-10-15; the range ends at 9999-12-31
        if (date1.isBefore(LocalDate.of(1582, 10, 15))) {
            return FC_UNSUPP_RANGE;
        }
        return FC_INVALID_DATE;
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String fit(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    private static String stripTrailing(String s) {
        int e = s.length();
        while (e > 0 && s.charAt(e - 1) == ' ') {
            e--;
        }
        return s.substring(0, e);
    }

}
