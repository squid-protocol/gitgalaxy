// gitgalaxy-det-port: COBOL CSUTLDTC (CSUTLDTC.cbl), translated by rule, statement for statement
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.MainframeClock;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cobolrt.batch.DetFiles;
import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import com.gitgalaxy.modernized.cobolrt.Figurative;
import com.gitgalaxy.modernized.cobolrt.Funcs;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.call.CobolRef;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CSUTLDTC: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 27, translated 27, holes 0.
 */
@Service
public class CsutldtcService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_DATE_TO_TEST = Base64.getDecoder().decode(String.join("",
            "AAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_DATE_FORMAT = Base64.getDecoder().decode(String.join("",
            "AAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_OUTPUT_LILLIAN = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MESSAGE = Base64.getDecoder().decode(String.join("",
            "ICAgIE1lc2cgQ29kZTogICAgICAgICAgICAgICAgICAgICAgVHN0RGF0ZTogICAgICAgICAgICBNYXNrIHVzZWQ6ICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_FEEDBACK_CODE = Base64.getDecoder().decode(String.join("",
            "AAAAACAgICAAAAAA"));
    private static final byte[] IMAGE_s_LS_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_LS_DATE_FORMAT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_LS_RESULT = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_DATE_TO_TEST = new Storage(IMAGE_s_WS_DATE_TO_TEST.length);
    private final Storage s_WS_DATE_FORMAT = new Storage(IMAGE_s_WS_DATE_FORMAT.length);
    private final Storage s_OUTPUT_LILLIAN = new Storage(IMAGE_s_OUTPUT_LILLIAN.length);
    private final Storage s_WS_MESSAGE = new Storage(IMAGE_s_WS_MESSAGE.length);
    private final Storage s_FEEDBACK_CODE = new Storage(IMAGE_s_FEEDBACK_CODE.length);
    private final Storage s_LS_DATE = new Storage(IMAGE_s_LS_DATE.length);
    private final Storage s_LS_DATE_FORMAT = new Storage(IMAGE_s_LS_DATE_FORMAT.length);
    private final Storage s_LS_RESULT = new Storage(IMAGE_s_LS_RESULT.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_DATE_TO_TEST = Field.group(s_WS_DATE_TO_TEST, 0, 258);
    private final Field f2_VSTRING_LENGTH = Field.binary(s_WS_DATE_TO_TEST, 0, 4, 0, true, false);
    private final Field f3_VSTRING_TEXT = Field.group(s_WS_DATE_TO_TEST, 2, 256);
    private final Field f5_WS_DATE_FORMAT = Field.group(s_WS_DATE_FORMAT, 0, 258);
    private final Field f6_VSTRING_LENGTH = Field.binary(s_WS_DATE_FORMAT, 0, 4, 0, true, false);
    private final Field f7_VSTRING_TEXT = Field.group(s_WS_DATE_FORMAT, 2, 256);
    private final Field f9_OUTPUT_LILLIAN = Field.binary(s_OUTPUT_LILLIAN, 0, 9, 0, true, false);
    private final Field f10_WS_MESSAGE = Field.group(s_WS_MESSAGE, 0, 80);
    private final Field f12_WS_SEVERITY_N = Field.zoned(s_WS_MESSAGE, 0, 4, 0, false, false, false);
    private final Field f15_WS_MSG_NO_N = Field.zoned(s_WS_MESSAGE, 15, 4, 0, false, false, false);
    private final Field f17_WS_RESULT = Field.alphanumeric(s_WS_MESSAGE, 20, 15, false);
    private final Field f20_WS_DATE = Field.alphanumeric(s_WS_MESSAGE, 45, 10, false);
    private final Field f23_WS_DATE_FMT = Field.alphanumeric(s_WS_MESSAGE, 66, 10, false);
    private final Field f26_FEEDBACK_CODE = Field.group(s_FEEDBACK_CODE, 0, 12);
    private final Field f27_FEEDBACK_TOKEN_VALUE = Field.group(s_FEEDBACK_CODE, 0, 8);
    private final Field f29_SEVERITY = Field.binary(s_FEEDBACK_CODE, 0, 4, 0, true, false);
    private final Field f30_MSG_NO = Field.binary(s_FEEDBACK_CODE, 2, 4, 0, true, false);
    private final Field f37_LS_DATE = Field.alphanumeric(s_LS_DATE, 0, 10, false);
    private final Field f38_LS_DATE_FORMAT = Field.alphanumeric(s_LS_DATE_FORMAT, 0, 10, false);
    private final Field f39_LS_RESULT = Field.alphanumeric(s_LS_RESULT, 0, 80, false);
    private final Field f40_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);


    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public CsutldtcService(DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        initialState();
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_DATE_TO_TEST, 0, s_WS_DATE_TO_TEST.bytes, 0, IMAGE_s_WS_DATE_TO_TEST.length);
        System.arraycopy(IMAGE_s_WS_DATE_FORMAT, 0, s_WS_DATE_FORMAT.bytes, 0, IMAGE_s_WS_DATE_FORMAT.length);
        System.arraycopy(IMAGE_s_OUTPUT_LILLIAN, 0, s_OUTPUT_LILLIAN.bytes, 0, IMAGE_s_OUTPUT_LILLIAN.length);
        System.arraycopy(IMAGE_s_WS_MESSAGE, 0, s_WS_MESSAGE.bytes, 0, IMAGE_s_WS_MESSAGE.length);
        System.arraycopy(IMAGE_s_FEEDBACK_CODE, 0, s_FEEDBACK_CODE.bytes, 0, IMAGE_s_FEEDBACK_CODE.length);
        System.arraycopy(IMAGE_s_LS_DATE, 0, s_LS_DATE.bytes, 0, IMAGE_s_LS_DATE.length);
        System.arraycopy(IMAGE_s_LS_DATE_FORMAT, 0, s_LS_DATE_FORMAT.bytes, 0, IMAGE_s_LS_DATE_FORMAT.length);
        System.arraycopy(IMAGE_s_LS_RESULT, 0, s_LS_RESULT.bytes, 0, IMAGE_s_LS_RESULT.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 2);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f40_GG_RETURN_CODE, CS).intValue();
    }

    public int handleCall(CobolRef<String> arg1, CobolRef<String> arg2, CobolRef<String> arg3) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            Cobol.move(arg1.get() == null ? "" : arg1.get(), f37_LS_DATE, CS);
            Cobol.move(arg2.get() == null ? "" : arg2.get(), f38_LS_DATE_FORMAT, CS);
            Cobol.move(arg3.get() == null ? "" : arg3.get(), f39_LS_RESULT, CS);
            try {
                perform(0, 2);
            } catch (Goback g) {
                // GOBACK
            }
            arg1.set(Cobol.text(f37_LS_DATE, CS));
            arg2.set(Cobol.text(f38_LS_DATE_FORMAT, CS));
            arg3.set(Cobol.text(f39_LS_RESULT, CS));
            return Cobol.num(f40_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }


    /** GOBACK / STOP RUN. */
    private static final class Goback extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Goback() {
            super(null, null, false, false);
        }
    }

    private static Dd dd(List<Dd> dds, String name) {
        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElse(null);
    }

    /** The batch entry. */
    public int runBatch(List<Dd> dds, String parm) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            initialState();
            byte[] parmText = (parm == null ? "" : parm).getBytes(CS);
            s_LS_DATE.bytes[0] = (byte) (parmText.length >> 8);
            s_LS_DATE.bytes[1] = (byte) parmText.length;
            System.arraycopy(parmText, 0, s_LS_DATE.bytes, 2, Math.min(parmText.length, s_LS_DATE.bytes.length - 2));
            try {
                perform(0, 2);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f40_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    /** The active PERFORMs' last paragraphs, outermost first. */
    private int[] performThru = new int[64];
    private int performDepth = 0;

    /** Control reached the end of an outer active PERFORM's range: that PERFORM returns (`depth`). */
    private static final class PerformExit extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final int depth;

        PerformExit(int depth) {
            super(null, null, false, false);
            this.depth = depth;
        }
    }

    /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERFORM
     *  whose range ends there returns -- this one, or an outer one a GO TO reached the end of, abandoning
     *  the PERFORMs inside it (GnuCOBOL, as IBM: test_det_programs.py, GOTOOUT). */
    private void perform(int from, int thru) {
        int mine = performDepth;
        if (mine == performThru.length) {
            performThru = java.util.Arrays.copyOf(performThru, mine * 2);
        }
        performThru[performDepth++] = thru;
        try {
            int i = from;
            while (true) {
                int next = run(i);
                boolean jumped = (next & GOTO) != 0;
                next &= ~GOTO;
                if (!jumped) {
                    if (i == thru) {
                        return;
                    }
                    for (int d = mine - 1; d >= 0; d--) {
                        if (performThru[d] == i) {
                            throw new PerformExit(d);
                        }
                    }
                }
                if (next >= 3) {
                    throw new Goback();
                }
                i = next;
            }
        } catch (PerformExit e) {
            if (e.depth != mine) {
                throw e;
            }
        } finally {
            performDepth = mine;
        }
    }

    private int run(int i) {
        switch (i) {
            case 0: return p0();
            case 1: return p1();
            case 2: return p2();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** (MAIN). */
    private int p0() {
        // INITIALIZE WS-MESSAGE
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f10_WS_MESSAGE.storage(), f10_WS_MESSAGE.offset() + 0, 4, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f10_WS_MESSAGE.storage(), f10_WS_MESSAGE.offset() + 15, 4, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f10_WS_MESSAGE.storage(), f10_WS_MESSAGE.offset() + 20, 15, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f10_WS_MESSAGE.storage(), f10_WS_MESSAGE.offset() + 45, 10, false), CS);
        Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f10_WS_MESSAGE.storage(), f10_WS_MESSAGE.offset() + 66, 10, false), CS);
        // MOVE SPACES TO WS-DATE
        Cobol.moveFigurative(Figurative.SPACES, f20_WS_DATE, CS);
        // PERFORM A000-MAIN THRU A000-MAIN-EXIT
        perform(1, 2);
        // MOVE WS-MESSAGE TO LS-RESULT
        Cobol.move(f10_WS_MESSAGE, f39_LS_RESULT, CS);
        // MOVE WS-SEVERITY-N TO RETURN-CODE
        Cobol.move(f12_WS_SEVERITY_N, f40_GG_RETURN_CODE, CS);
        // EXIT PROGRAM
        if (true) throw new Goback();
        return 1;
    }

    /** A000-MAIN. */
    private int p1() {
        // MOVE LENGTH OF LS-DATE TO VSTRING-LENGTH OF WS-DATE-TO-TEST
        Cobol.move(BigDecimal.valueOf(10), f2_VSTRING_LENGTH, CS);
        // MOVE LS-DATE TO VSTRING-TEXT OF WS-DATE-TO-TEST WS-DATE
        Cobol.move(f37_LS_DATE, f3_VSTRING_TEXT, CS);
        Cobol.move(f37_LS_DATE, f20_WS_DATE, CS);
        // MOVE LENGTH OF LS-DATE-FORMAT TO VSTRING-LENGTH OF WS-DATE-FORMAT
        Cobol.move(BigDecimal.valueOf(10), f6_VSTRING_LENGTH, CS);
        // MOVE LS-DATE-FORMAT TO VSTRING-TEXT OF WS-DATE-FORMAT WS-DATE-FMT
        Cobol.move(f38_LS_DATE_FORMAT, f7_VSTRING_TEXT, CS);
        Cobol.move(f38_LS_DATE_FORMAT, f23_WS_DATE_FMT, CS);
        // MOVE 0 TO OUTPUT-LILLIAN
        Cobol.move(D0, f9_OUTPUT_LILLIAN, CS);
        // CALL "CEEDAYS" USING WS-DATE-TO-TEST, WS-DATE-FORMAT, OUTPUT-LILLIAN, FEEDBACK-CODE
        com.gitgalaxy.modernized.cobolrt.le.Ceedays.call(f1_WS_DATE_TO_TEST, f5_WS_DATE_FORMAT, f9_OUTPUT_LILLIAN, f26_FEEDBACK_CODE);
        // MOVE WS-DATE-TO-TEST TO WS-DATE
        Cobol.move(f1_WS_DATE_TO_TEST, f20_WS_DATE, CS);
        // MOVE SEVERITY OF FEEDBACK-CODE TO WS-SEVERITY-N
        Cobol.move(f29_SEVERITY, f12_WS_SEVERITY_N, CS);
        // MOVE MSG-NO OF FEEDBACK-CODE TO WS-MSG-NO-N
        Cobol.move(f30_MSG_NO, f15_WS_MSG_NO_N, CS);
        // EVALUATE TRUE
        if ((isFcInvalidDate())) {
            // MOVE 'Date is valid' TO WS-RESULT
            Cobol.move("Date is valid", f17_WS_RESULT, CS);
        } else if ((isFcInsufficientData())) {
            // MOVE 'Insufficient' TO WS-RESULT
            Cobol.move("Insufficient", f17_WS_RESULT, CS);
        } else if ((isFcBadDateValue())) {
            // MOVE 'Datevalue error' TO WS-RESULT
            Cobol.move("Datevalue error", f17_WS_RESULT, CS);
        } else if ((isFcInvalidEra())) {
            // MOVE 'Invalid Era ' TO WS-RESULT
            Cobol.move("Invalid Era    ", f17_WS_RESULT, CS);
        } else if ((isFcUnsuppRange())) {
            // MOVE 'Unsupp. Range ' TO WS-RESULT
            Cobol.move("Unsupp. Range  ", f17_WS_RESULT, CS);
        } else if ((isFcInvalidMonth())) {
            // MOVE 'Invalid month ' TO WS-RESULT
            Cobol.move("Invalid month  ", f17_WS_RESULT, CS);
        } else if ((isFcBadPicString())) {
            // MOVE 'Bad Pic String ' TO WS-RESULT
            Cobol.move("Bad Pic String ", f17_WS_RESULT, CS);
        } else if ((isFcNonNumericData())) {
            // MOVE 'Nonnumeric data' TO WS-RESULT
            Cobol.move("Nonnumeric data", f17_WS_RESULT, CS);
        } else if ((isFcYearInEraZero())) {
            // MOVE 'YearInEra is 0 ' TO WS-RESULT
            Cobol.move("YearInEra is 0 ", f17_WS_RESULT, CS);
        } else if (true) {
            // MOVE 'Date is invalid' TO WS-RESULT
            Cobol.move("Date is invalid", f17_WS_RESULT, CS);
        }
        return 2;
    }

    /** A000-MAIN-EXIT. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** 88 FC-INVALID-DATE of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcInvalidDate() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\000\000\000\000\000\000\000", CS) == 0; }

    /** 88 FC-INSUFFICIENT-DATA of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcInsufficientData() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\313Y\303\305\305", CS) == 0; }

    /** 88 FC-BAD-DATE-VALUE of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcBadDateValue() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\314Y\303\305\305", CS) == 0; }

    /** 88 FC-INVALID-ERA of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcInvalidEra() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\315Y\303\305\305", CS) == 0; }

    /** 88 FC-UNSUPP-RANGE of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcUnsuppRange() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\321Y\303\305\305", CS) == 0; }

    /** 88 FC-INVALID-MONTH of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcInvalidMonth() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\325Y\303\305\305", CS) == 0; }

    /** 88 FC-BAD-PIC-STRING of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcBadPicString() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\326Y\303\305\305", CS) == 0; }

    /** 88 FC-NON-NUMERIC-DATA of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcNonNumericData() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\330Y\303\305\305", CS) == 0; }

    /** 88 FC-YEAR-IN-ERA-ZERO of FEEDBACK-TOKEN-VALUE. */
    private boolean isFcYearInEraZero() { return Cobol.compare(f27_FEEDBACK_TOKEN_VALUE, "\000\003\011\331Y\303\305\305", CS) == 0; }

}
