// gitgalaxy-det-port: COBOL CBPAUP0C (CBPAUP0C.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.cobolrt.Accept;
import com.gitgalaxy.modernized.cobolrt.Funcs;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.cobolrt.dli.DetDli;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CBPAUP0C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 110, translated 110, holes 0.
 */
@Service
public class Cbpaup0cService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D5 = new BigDecimal("5");
    private static final BigDecimal D10 = new BigDecimal("10");
    private static final BigDecimal D1 = new BigDecimal("1");
    private static final BigDecimal D99999 = new BigDecimal("99999");
    private static final BigDecimal D16 = new BigDecimal("16");

    private static final byte[] IMAGE_s_WS_VARIABLES = Base64.getDecoder().decode(String.join("",
            "Q0JQQVVQMEMwMDAwMDAwMDAwMDAwMDAwAAAAAAAAMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAAAAAAAAAAAAAAAAAAAAABOTk5OICAgIFJNQUQwMDAw"));
    private static final byte[] IMAGE_s_WS_IMS_VARIABLES = Base64.getDecoder().decode(String.join("",
            "UFNCUEFVVEIAAiAgIA=="));
    private static final byte[] IMAGE_s_PRM_INFO = Base64.getDecoder().decode(String.join("",
            "MDAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_PENDING_AUTH_SUMMARY = Base64.getDecoder().decode(String.join("",
            "AAAAAAAMMDAwMDAwMDAwICAgICAgICAgICAAAAAAAAwAAAAAAAwAAAAAAAwAAAAAAAwAAAAAAAAAAAAMAAAAAAAMICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_PENDING_AUTH_DETAILS = Base64.getDecoder().decode(String.join("",
            "AAAMAAAAAAwgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDAwMDAAAAAAAAAMAAAAAAAADCAgICAgICAwMCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_IO_PCB_MASK = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_PGM_PCB_MASK = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_DIB = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private final Storage s_WS_VARIABLES = new Storage(IMAGE_s_WS_VARIABLES.length);
    private final Storage s_WS_IMS_VARIABLES = new Storage(IMAGE_s_WS_IMS_VARIABLES.length);
    private final Storage s_PRM_INFO = new Storage(IMAGE_s_PRM_INFO.length);
    private final Storage s_PENDING_AUTH_SUMMARY = new Storage(IMAGE_s_PENDING_AUTH_SUMMARY.length);
    private final Storage s_PENDING_AUTH_DETAILS = new Storage(IMAGE_s_PENDING_AUTH_DETAILS.length);
    private final Storage s_IO_PCB_MASK = new Storage(IMAGE_s_IO_PCB_MASK.length);
    private final Storage s_PGM_PCB_MASK = new Storage(IMAGE_s_PGM_PCB_MASK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);
    private final Storage s_DIB = new Storage(IMAGE_s_DIB.length);

    private final Field f3_CURRENT_DATE = Field.zoned(s_WS_VARIABLES, 8, 6, 0, false, false, false);
    private final Field f4_CURRENT_YYDDD = Field.zoned(s_WS_VARIABLES, 14, 5, 0, false, false, false);
    private final Field f6_WS_EXPIRY_DAYS = Field.binary(s_WS_VARIABLES, 24, 4, 0, true, false);
    private final Field f9_WS_CURR_APP_ID = Field.zoned(s_WS_VARIABLES, 30, 11, 0, false, false, false);
    private final Field f10_WS_NO_CHKP = Field.zoned(s_WS_VARIABLES, 41, 8, 0, false, false, false);
    private final Field f11_WS_AUTH_SMRY_PROC_CNT = Field.zoned(s_WS_VARIABLES, 49, 8, 0, false, false, false);
    private final Field f13_WS_NO_SUMRY_READ = Field.binary(s_WS_VARIABLES, 61, 8, 0, true, false);
    private final Field f14_WS_NO_SUMRY_DELETED = Field.binary(s_WS_VARIABLES, 65, 8, 0, true, false);
    private final Field f15_WS_NO_DTL_READ = Field.binary(s_WS_VARIABLES, 69, 8, 0, true, false);
    private final Field f16_WS_NO_DTL_DELETED = Field.binary(s_WS_VARIABLES, 73, 8, 0, true, false);
    private final Field f23_WK_CHKPT_ID = Field.group(s_WS_VARIABLES, 85, 8);
    private final Field f32_PRM_INFO = Field.group(s_PRM_INFO, 0, 17);
    private final Field f33_P_EXPIRY_DAYS = Field.zoned(s_PRM_INFO, 0, 2, 0, false, false, false);
    private final Field f35_P_CHKP_FREQ = Field.alphanumeric(s_PRM_INFO, 3, 5, false);
    private final Field f37_P_CHKP_DIS_FREQ = Field.alphanumeric(s_PRM_INFO, 9, 5, false);
    private final Field f39_P_DEBUG_FLAG = Field.alphanumeric(s_PRM_INFO, 15, 1, false);
    private final Field f41_PENDING_AUTH_SUMMARY = Field.group(s_PENDING_AUTH_SUMMARY, 0, 100);
    private final Field f42_PA_ACCT_ID = Field.packed(s_PENDING_AUTH_SUMMARY, 0, 11, 0, true);
    private final Field f50_PA_APPROVED_AUTH_CNT = Field.binary(s_PENDING_AUTH_SUMMARY, 50, 4, 0, true, false);
    private final Field f51_PA_DECLINED_AUTH_CNT = Field.binary(s_PENDING_AUTH_SUMMARY, 52, 4, 0, true, false);
    private final Field f52_PA_APPROVED_AUTH_AMT = Field.packed(s_PENDING_AUTH_SUMMARY, 54, 11, 2, true);
    private final Field f53_PA_DECLINED_AUTH_AMT = Field.packed(s_PENDING_AUTH_SUMMARY, 60, 11, 2, true);
    private final Field f55_PENDING_AUTH_DETAILS = Field.group(s_PENDING_AUTH_DETAILS, 0, 200);
    private final Field f57_PA_AUTH_DATE_9C = Field.packed(s_PENDING_AUTH_DETAILS, 0, 5, 0, true);
    private final Field f67_PA_AUTH_RESP_CODE = Field.alphanumeric(s_PENDING_AUTH_DETAILS, 62, 2, false);
    private final Field f70_PA_TRANSACTION_AMT = Field.packed(s_PENDING_AUTH_DETAILS, 74, 12, 2, true);
    private final Field f71_PA_APPROVED_AMT = Field.packed(s_PENDING_AUTH_DETAILS, 81, 12, 2, true);
    private final Field f85_IO_PCB_MASK = Field.alphanumeric(s_IO_PCB_MASK, 0, 1, false);
    private final Field f86_PGM_PCB_MASK = Field.alphanumeric(s_PGM_PCB_MASK, 0, 1, false);
    private final Field f87_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private final Field f90_DIBSTAT = Field.alphanumeric(s_DIB, 2, 2, false);
    private String f2_WS_PGMNAME;  // WS-PGMNAME PIC X(08)
    private BigDecimal f5_WS_AUTH_DATE;  // WS-AUTH-DATE PIC 9(05) DISPLAY
    private long f7_WS_DAY_DIFF;  // WS-DAY-DIFF PIC S9(4) BINARY
    private long f8_IDX;  // IDX PIC S9(4) BINARY
    private long f12_WS_TOT_REC_WRITTEN;  // WS-TOT-REC-WRITTEN PIC S9(8) BINARY
    private String f17_WS_ERR_FLG;  // WS-ERR-FLG PIC X(01)
    private String f18_WS_END_OF_AUTHDB_FLAG;  // WS-END-OF-AUTHDB-FLAG PIC X(01)
    private String f19_WS_MORE_AUTHS_FLAG;  // WS-MORE-AUTHS-FLAG PIC X(01)
    private String f20_WS_QUALIFY_DELETE_FLAG;  // WS-QUALIFY-DELETE-FLAG PIC X(01)
    private String f21_WS_INFILE_STATUS;  // WS-INFILE-STATUS PIC X(02)
    private String f22_WS_CUSTID_STATUS;  // WS-CUSTID-STATUS PIC X(02)
    private String f27_PSB_NAME;  // PSB-NAME PIC X(8)
    private long f29_PAUT_PCB_NUM;  // PAUT-PCB-NUM PIC S9(4) BINARY
    private String f30_IMS_RETURN_CODE;  // IMS-RETURN-CODE PIC X(02)
    private String f31_WS_IMS_PSB_SCHD_FLG;  // WS-IMS-PSB-SCHD-FLG PIC X(1)


    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Cbpaup0cService(DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_VARIABLES, 0, s_WS_VARIABLES.bytes, 0, IMAGE_s_WS_VARIABLES.length);
        System.arraycopy(IMAGE_s_WS_IMS_VARIABLES, 0, s_WS_IMS_VARIABLES.bytes, 0, IMAGE_s_WS_IMS_VARIABLES.length);
        System.arraycopy(IMAGE_s_PRM_INFO, 0, s_PRM_INFO.bytes, 0, IMAGE_s_PRM_INFO.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_SUMMARY, 0, s_PENDING_AUTH_SUMMARY.bytes, 0, IMAGE_s_PENDING_AUTH_SUMMARY.length);
        System.arraycopy(IMAGE_s_PENDING_AUTH_DETAILS, 0, s_PENDING_AUTH_DETAILS.bytes, 0, IMAGE_s_PENDING_AUTH_DETAILS.length);
        System.arraycopy(IMAGE_s_IO_PCB_MASK, 0, s_IO_PCB_MASK.bytes, 0, IMAGE_s_IO_PCB_MASK.length);
        System.arraycopy(IMAGE_s_PGM_PCB_MASK, 0, s_PGM_PCB_MASK.bytes, 0, IMAGE_s_PGM_PCB_MASK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        System.arraycopy(IMAGE_s_DIB, 0, s_DIB.bytes, 0, IMAGE_s_DIB.length);
        f2_WS_PGMNAME = "CBPAUP0C";
        f5_WS_AUTH_DATE = new BigDecimal("0");
        f7_WS_DAY_DIFF = 0L;
        f8_IDX = 0L;
        f12_WS_TOT_REC_WRITTEN = 0L;
        f17_WS_ERR_FLG = "N";
        f18_WS_END_OF_AUTHDB_FLAG = "N";
        f19_WS_MORE_AUTHS_FLAG = "N";
        f20_WS_QUALIFY_DELETE_FLAG = "N";
        f21_WS_INFILE_STATUS = "  ";
        f22_WS_CUSTID_STATUS = "  ";
        f27_PSB_NAME = "PSBPAUTB";
        f29_PAUT_PCB_NUM = 2L;
        f30_IMS_RETURN_CODE = "  ";
        f31_WS_IMS_PSB_SCHD_FLG = " ";
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 16);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f87_GG_RETURN_CODE, CS).intValue();
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
            DetDli.enterBmp(f85_IO_PCB_MASK, f86_PGM_PCB_MASK);
            try {
                perform(0, 16);
            } catch (Goback g) {
                // the program ended
            }
            DetDli.leave();  // the step ended: its databases, as it left them
            return Cobol.num(f87_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 17) {
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
            case 3: return p3();
            case 4: return p4();
            case 5: return p5();
            case 6: return p6();
            case 7: return p7();
            case 8: return p8();
            case 9: return p9();
            case 10: return p10();
            case 11: return p11();
            case 12: return p12();
            case 13: return p13();
            case 14: return p14();
            case 15: return p15();
            case 16: return p16();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // PERFORM 1000-INITIALIZE THRU 1000-EXIT
        perform(1, 2);
        // PERFORM 2000-FIND-NEXT-AUTH-SUMMARY THRU 2000-EXIT
        perform(3, 4);
        // PERFORM UNTIL ERR-FLG-ON OR END-OF-AUTHDB
        while (!((isErrFlgOn() || isEndOfAuthdb()))) {
            // PERFORM 3000-FIND-NEXT-AUTH-DTL THRU 3000-EXIT
            perform(5, 6);
            // PERFORM UNTIL NO-MORE-AUTHS
            while (!(isNoMoreAuths())) {
                // PERFORM 4000-CHECK-IF-EXPIRED THRU 4000-EXIT
                perform(7, 8);
                // IF QUALIFIED-FOR-DELETE
                if (isQualifiedForDelete()) {
                    // PERFORM 5000-DELETE-AUTH-DTL THRU 5000-EXIT
                    perform(9, 10);
                }
                // PERFORM 3000-FIND-NEXT-AUTH-DTL THRU 3000-EXIT
                perform(5, 6);
            }
            // IF PA-APPROVED-AUTH-CNT <= 0 AND PA-APPROVED-AUTH-CNT <= 0
            if ((Cobol.num(f50_PA_APPROVED_AUTH_CNT, CS).compareTo(D0) <= 0 && Cobol.num(f50_PA_APPROVED_AUTH_CNT, CS).compareTo(D0) <= 0)) {
                // PERFORM 6000-DELETE-AUTH-SUMMARY THRU 6000-EXIT
                perform(11, 12);
            }
            // IF WS-AUTH-SMRY-PROC-CNT > P-CHKP-FREQ
            if (Cobol.compare(f11_WS_AUTH_SMRY_PROC_CNT, f35_P_CHKP_FREQ, CS) > 0) {
                // PERFORM 9000-TAKE-CHECKPOINT THRU 9000-EXIT
                perform(13, 14);
                // MOVE 0 TO WS-AUTH-SMRY-PROC-CNT
                Cobol.move(D0, f11_WS_AUTH_SMRY_PROC_CNT, CS);
            }
            // PERFORM 2000-FIND-NEXT-AUTH-SUMMARY THRU 2000-EXIT
            perform(3, 4);
        }
        // PERFORM 9000-TAKE-CHECKPOINT THRU 9000-EXIT
        perform(13, 14);
        // DISPLAY ' '
        Sysout.display(" ");
        // DISPLAY '*-------------------------------------*'
        Sysout.display("*-------------------------------------*");
        // DISPLAY '# TOTAL SUMMARY READ :' WS-NO-SUMRY-READ
        Sysout.display("# TOTAL SUMMARY READ  :", Cobol.displayText(f13_WS_NO_SUMRY_READ, CS));
        // DISPLAY '# SUMMARY REC DELETED :' WS-NO-SUMRY-DELETED
        Sysout.display("# SUMMARY REC DELETED :", Cobol.displayText(f14_WS_NO_SUMRY_DELETED, CS));
        // DISPLAY '# TOTAL DETAILS READ :' WS-NO-DTL-READ
        Sysout.display("# TOTAL DETAILS READ  :", Cobol.displayText(f15_WS_NO_DTL_READ, CS));
        // DISPLAY '# DETAILS REC DELETED :' WS-NO-DTL-DELETED
        Sysout.display("# DETAILS REC DELETED :", Cobol.displayText(f16_WS_NO_DTL_DELETED, CS));
        // DISPLAY '*-------------------------------------*'
        Sysout.display("*-------------------------------------*");
        // DISPLAY ' '
        Sysout.display(" ");
        // GOBACK
        if (true) throw new Goback();
        return 1;
    }

    /** 1000-INITIALIZE. */
    private int p1() {
        // ACCEPT CURRENT-DATE FROM DATE
        Cobol.move(Accept.from(clock.currentDate(), "DATE"), f3_CURRENT_DATE, CS);
        // ACCEPT CURRENT-YYDDD FROM DAY
        Cobol.move(Accept.from(clock.currentDate(), "DAY"), f4_CURRENT_YYDDD, CS);
        // ACCEPT PRM-INFO FROM SYSIN
        Accept.sysin(f32_PRM_INFO, CS);
        // DISPLAY 'STARTING PROGRAM CBPAUP0C::'
        Sysout.display("STARTING PROGRAM CBPAUP0C::");
        // DISPLAY '*-------------------------------------*'
        Sysout.display("*-------------------------------------*");
        // DISPLAY 'CBPAUP0C PARM RECEIVED :' PRM-INFO
        Sysout.display("CBPAUP0C PARM RECEIVED :", Cobol.displayText(f32_PRM_INFO, CS));
        // DISPLAY 'TODAYS DATE :' CURRENT-YYDDD
        Sysout.display("TODAYS DATE            :", Cobol.displayText(f4_CURRENT_YYDDD, CS));
        // DISPLAY ' '
        Sysout.display(" ");
        // IF P-EXPIRY-DAYS IS NUMERIC
        if (Cobol.isNumeric(f33_P_EXPIRY_DAYS, CS)) {
            // MOVE P-EXPIRY-DAYS TO WS-EXPIRY-DAYS
            Cobol.move(f33_P_EXPIRY_DAYS, f6_WS_EXPIRY_DAYS, CS);
        } else {
            // MOVE 5 TO WS-EXPIRY-DAYS
            Cobol.move(D5, f6_WS_EXPIRY_DAYS, CS);
        }
        // IF P-CHKP-FREQ = SPACES OR 0 OR LOW-VALUES
        if (((Cobol.compareFigurative(f35_P_CHKP_FREQ, Figurative.SPACES, CS) == 0 || Cobol.compare(f35_P_CHKP_FREQ, "0", CS) == 0) || Cobol.compareFigurative(f35_P_CHKP_FREQ, Figurative.LOW_VALUES, CS) == 0)) {
            // MOVE 5 TO P-CHKP-FREQ
            Cobol.move(D5, f35_P_CHKP_FREQ, CS);
        }
        // IF P-CHKP-DIS-FREQ = SPACES OR 0 OR LOW-VALUES
        if (((Cobol.compareFigurative(f37_P_CHKP_DIS_FREQ, Figurative.SPACES, CS) == 0 || Cobol.compare(f37_P_CHKP_DIS_FREQ, "0", CS) == 0) || Cobol.compareFigurative(f37_P_CHKP_DIS_FREQ, Figurative.LOW_VALUES, CS) == 0)) {
            // MOVE 10 TO P-CHKP-DIS-FREQ
            Cobol.move(D10, f37_P_CHKP_DIS_FREQ, CS);
        }
        // IF P-DEBUG-FLAG NOT = 'Y'
        if (!(Cobol.compare(f39_P_DEBUG_FLAG, "Y", CS) == 0)) {
            // MOVE 'N' TO P-DEBUG-FLAG
            Cobol.move("N", f39_P_DEBUG_FLAG, CS);
        }
        return 2;
    }

    /** 1000-EXIT. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** 2000-FIND-NEXT-AUTH-SUMMARY. */
    private int p3() {
        // IF DEBUG-ON
        if (isDebugOn()) {
            // DISPLAY 'DEBUG: AUTH SMRY READ : ' WS-NO-SUMRY-READ
            Sysout.display("DEBUG: AUTH SMRY READ : ", Cobol.displayText(f13_WS_NO_SUMRY_READ, CS));
        }
        // EXEC DLI GN USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) INTO (PENDING-AUTH-SUMMARY) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.get("GN", BigDecimal.valueOf(f29_PAUT_PCB_NUM).intValue(), f41_PENDING_AUTH_SUMMARY, com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTSUM0")), f90_DIBSTAT, CS);
        // EVALUATE DIBSTAT
        if ((Cobol.compare(f90_DIBSTAT, "  ", CS) == 0)) {
            // SET NOT-END-OF-AUTHDB TO TRUE
            f18_WS_END_OF_AUTHDB_FLAG = "N";
            // ADD 1 TO WS-NO-SUMRY-READ
            BigDecimal t1 = D1;
            Cobol.store(f13_WS_NO_SUMRY_READ, Cobol.receiverNum(f13_WS_NO_SUMRY_READ, CS).add(t1), false, CS);
            // ADD 1 TO WS-AUTH-SMRY-PROC-CNT
            BigDecimal t3 = D1;
            Cobol.store(f11_WS_AUTH_SMRY_PROC_CNT, Cobol.receiverNum(f11_WS_AUTH_SMRY_PROC_CNT, CS).add(t3), false, CS);
            // MOVE PA-ACCT-ID TO WS-CURR-APP-ID
            Cobol.move(f42_PA_ACCT_ID, f9_WS_CURR_APP_ID, CS);
        } else if ((Cobol.compare(f90_DIBSTAT, "GB", CS) == 0)) {
            // SET END-OF-AUTHDB TO TRUE
            f18_WS_END_OF_AUTHDB_FLAG = "Y";
        } else if (true) {
            // DISPLAY 'AUTH SUMMARY READ FAILED :' DIBSTAT
            Sysout.display("AUTH SUMMARY READ FAILED  :", Cobol.displayText(f90_DIBSTAT, CS));
            // DISPLAY 'SUMMARY READ BEFORE ABEND :' WS-NO-SUMRY-READ
            Sysout.display("SUMMARY READ BEFORE ABEND :", Cobol.displayText(f13_WS_NO_SUMRY_READ, CS));
            // PERFORM 9999-ABEND
            perform(15, 15);
        }
        return 4;
    }

    /** 2000-EXIT. */
    private int p4() {
        // EXIT
        return 5;
    }

    /** 3000-FIND-NEXT-AUTH-DTL. */
    private int p5() {
        // IF DEBUG-ON
        if (isDebugOn()) {
            // DISPLAY 'DEBUG: AUTH DTL READ : ' WS-NO-DTL-READ
            Sysout.display("DEBUG: AUTH DTL READ : ", Cobol.displayText(f15_WS_NO_DTL_READ, CS));
        }
        // EXEC DLI GNP USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTDTL1) INTO (PENDING-AUTH-DETAILS) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.get("GNP", BigDecimal.valueOf(f29_PAUT_PCB_NUM).intValue(), f55_PENDING_AUTH_DETAILS, com.gitgalaxy.modernized.cobolrt.dli.DetDli.ssa("PAUTDTL1")), f90_DIBSTAT, CS);
        // EVALUATE DIBSTAT
        if ((Cobol.compare(f90_DIBSTAT, "  ", CS) == 0)) {
            // SET MORE-AUTHS TO TRUE
            f19_WS_MORE_AUTHS_FLAG = "Y";
            // ADD 1 TO WS-NO-DTL-READ
            BigDecimal t5 = D1;
            Cobol.store(f15_WS_NO_DTL_READ, Cobol.receiverNum(f15_WS_NO_DTL_READ, CS).add(t5), false, CS);
        } else if ((Cobol.compare(f90_DIBSTAT, "GE", CS) == 0) || (Cobol.compare(f90_DIBSTAT, "GB", CS) == 0)) {
            // SET NO-MORE-AUTHS TO TRUE
            f19_WS_MORE_AUTHS_FLAG = "N";
        } else if (true) {
            // DISPLAY 'AUTH DETAIL READ FAILED :' DIBSTAT
            Sysout.display("AUTH DETAIL READ FAILED  :", Cobol.displayText(f90_DIBSTAT, CS));
            // DISPLAY 'SUMMARY AUTH APP ID :' PA-ACCT-ID
            Sysout.display("SUMMARY AUTH APP ID      :", Cobol.displayText(f42_PA_ACCT_ID, CS));
            // DISPLAY 'DETAIL READ BEFORE ABEND :' WS-NO-DTL-READ
            Sysout.display("DETAIL READ BEFORE ABEND :", Cobol.displayText(f15_WS_NO_DTL_READ, CS));
            // PERFORM 9999-ABEND
            perform(15, 15);
        }
        return 6;
    }

    /** 3000-EXIT. */
    private int p6() {
        // EXIT
        return 7;
    }

    /** 4000-CHECK-IF-EXPIRED. */
    private int p7() {
        // COMPUTE WS-AUTH-DATE = 99999 - PA-AUTH-DATE-9C
        BigDecimal v7 = D99999.subtract(Cobol.num(f57_PA_AUTH_DATE_9C, CS));
        f5_WS_AUTH_DATE = Cobol.zoned(v7, 5, 0, false, false, CS);
        // COMPUTE WS-DAY-DIFF = CURRENT-YYDDD - WS-AUTH-DATE
        BigDecimal v8 = Cobol.num(f4_CURRENT_YYDDD, CS).subtract(f5_WS_AUTH_DATE);
        f7_WS_DAY_DIFF = Cobol.binary(v8, 4, true, false, CS);
        // IF WS-DAY-DIFF >= WS-EXPIRY-DAYS
        if (BigDecimal.valueOf(f7_WS_DAY_DIFF).compareTo(Cobol.num(f6_WS_EXPIRY_DAYS, CS)) >= 0) {
            // SET QUALIFIED-FOR-DELETE TO TRUE
            f20_WS_QUALIFY_DELETE_FLAG = "Y";
            // IF PA-AUTH-RESP-CODE = '00'
            if (Cobol.compare(f67_PA_AUTH_RESP_CODE, "00", CS) == 0) {
                // SUBTRACT 1 FROM PA-APPROVED-AUTH-CNT
                BigDecimal t9 = D1;
                Cobol.store(f50_PA_APPROVED_AUTH_CNT, Cobol.receiverNum(f50_PA_APPROVED_AUTH_CNT, CS).subtract(t9), false, CS);
                // SUBTRACT PA-APPROVED-AMT FROM PA-APPROVED-AUTH-AMT
                BigDecimal t11 = Cobol.num(f71_PA_APPROVED_AMT, CS);
                Cobol.store(f52_PA_APPROVED_AUTH_AMT, Cobol.receiverNum(f52_PA_APPROVED_AUTH_AMT, CS).subtract(t11), false, CS);
            } else {
                // SUBTRACT 1 FROM PA-DECLINED-AUTH-CNT
                BigDecimal t13 = D1;
                Cobol.store(f51_PA_DECLINED_AUTH_CNT, Cobol.receiverNum(f51_PA_DECLINED_AUTH_CNT, CS).subtract(t13), false, CS);
                // SUBTRACT PA-TRANSACTION-AMT FROM PA-DECLINED-AUTH-AMT
                BigDecimal t15 = Cobol.num(f70_PA_TRANSACTION_AMT, CS);
                Cobol.store(f53_PA_DECLINED_AUTH_AMT, Cobol.receiverNum(f53_PA_DECLINED_AUTH_AMT, CS).subtract(t15), false, CS);
            }
        } else {
            // SET NOT-QUALIFIED-FOR-DELETE TO TRUE
            f20_WS_QUALIFY_DELETE_FLAG = "N";
        }
        return 8;
    }

    /** 4000-EXIT. */
    private int p8() {
        // EXIT
        return 9;
    }

    /** 5000-DELETE-AUTH-DTL. */
    private int p9() {
        // IF DEBUG-ON
        if (isDebugOn()) {
            // DISPLAY 'DEBUG: AUTH DTL DLET : ' PA-ACCT-ID
            Sysout.display("DEBUG: AUTH DTL DLET : ", Cobol.displayText(f42_PA_ACCT_ID, CS));
        }
        // EXEC DLI DLET USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTDTL1) FROM (PENDING-AUTH-DETAILS) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.execChange("DLET", BigDecimal.valueOf(f29_PAUT_PCB_NUM).intValue(), f55_PENDING_AUTH_DETAILS, "PAUTDTL1"), f90_DIBSTAT, CS);
        // IF DIBSTAT = SPACES
        if (Cobol.compareFigurative(f90_DIBSTAT, Figurative.SPACES, CS) == 0) {
            // ADD 1 TO WS-NO-DTL-DELETED
            BigDecimal t17 = D1;
            Cobol.store(f16_WS_NO_DTL_DELETED, Cobol.receiverNum(f16_WS_NO_DTL_DELETED, CS).add(t17), false, CS);
        } else {
            // DISPLAY 'AUTH DETAIL DELETE FAILED :' DIBSTAT
            Sysout.display("AUTH DETAIL DELETE FAILED :", Cobol.displayText(f90_DIBSTAT, CS));
            // DISPLAY 'AUTH APP ID :' PA-ACCT-ID
            Sysout.display("AUTH APP ID               :", Cobol.displayText(f42_PA_ACCT_ID, CS));
            // PERFORM 9999-ABEND
            perform(15, 15);
        }
        return 10;
    }

    /** 5000-EXIT. */
    private int p10() {
        // EXIT
        return 11;
    }

    /** 6000-DELETE-AUTH-SUMMARY. */
    private int p11() {
        // IF DEBUG-ON
        if (isDebugOn()) {
            // DISPLAY 'DEBUG: AUTH SMRY DLET : ' PA-ACCT-ID
            Sysout.display("DEBUG: AUTH SMRY DLET : ", Cobol.displayText(f42_PA_ACCT_ID, CS));
        }
        // EXEC DLI DLET USING PCB(PAUT-PCB-NUM) SEGMENT (PAUTSUM0) FROM (PENDING-AUTH-SUMMARY) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.execChange("DLET", BigDecimal.valueOf(f29_PAUT_PCB_NUM).intValue(), f41_PENDING_AUTH_SUMMARY, "PAUTSUM0"), f90_DIBSTAT, CS);
        // IF DIBSTAT = SPACES
        if (Cobol.compareFigurative(f90_DIBSTAT, Figurative.SPACES, CS) == 0) {
            // ADD 1 TO WS-NO-SUMRY-DELETED
            BigDecimal t19 = D1;
            Cobol.store(f14_WS_NO_SUMRY_DELETED, Cobol.receiverNum(f14_WS_NO_SUMRY_DELETED, CS).add(t19), false, CS);
        } else {
            // DISPLAY 'AUTH SUMMARY DELETE FAILED :' DIBSTAT
            Sysout.display("AUTH SUMMARY DELETE FAILED :", Cobol.displayText(f90_DIBSTAT, CS));
            // DISPLAY 'AUTH APP ID :' PA-ACCT-ID
            Sysout.display("AUTH APP ID                :", Cobol.displayText(f42_PA_ACCT_ID, CS));
            // PERFORM 9999-ABEND
            perform(15, 15);
        }
        return 12;
    }

    /** 6000-EXIT. */
    private int p12() {
        // EXIT
        return 13;
    }

    /** 9000-TAKE-CHECKPOINT. */
    private int p13() {
        // EXEC DLI CHKP ID(WK-CHKPT-ID) END-EXEC
        Cobol.move(com.gitgalaxy.modernized.cobolrt.dli.DetDli.checkpoint(f23_WK_CHKPT_ID), f90_DIBSTAT, CS);
        // IF DIBSTAT = SPACES
        if (Cobol.compareFigurative(f90_DIBSTAT, Figurative.SPACES, CS) == 0) {
            // ADD 1 TO WS-NO-CHKP
            BigDecimal t21 = D1;
            Cobol.store(f10_WS_NO_CHKP, Cobol.receiverNum(f10_WS_NO_CHKP, CS).add(t21), false, CS);
            // IF WS-NO-CHKP >= P-CHKP-DIS-FREQ
            if (Cobol.compare(f10_WS_NO_CHKP, f37_P_CHKP_DIS_FREQ, CS) >= 0) {
                // MOVE 0 TO WS-NO-CHKP
                Cobol.move(D0, f10_WS_NO_CHKP, CS);
                // DISPLAY 'CHKP SUCCESS: AUTH COUNT - ' WS-NO-SUMRY-READ ', APP ID - ' WS-CURR-APP-ID
                Sysout.display("CHKP SUCCESS: AUTH COUNT - ", Cobol.displayText(f13_WS_NO_SUMRY_READ, CS), ", APP ID - ", Cobol.displayText(f9_WS_CURR_APP_ID, CS));
            }
        } else {
            // DISPLAY 'CHKP FAILED: DIBSTAT - ' DIBSTAT ', REC COUNT - ' WS-NO-SUMRY-READ ', APP ID - ' WS-CURR-APP-ID
            Sysout.display("CHKP FAILED: DIBSTAT - ", Cobol.displayText(f90_DIBSTAT, CS), ", REC COUNT - ", Cobol.displayText(f13_WS_NO_SUMRY_READ, CS), ", APP ID - ", Cobol.displayText(f9_WS_CURR_APP_ID, CS));
            // PERFORM 9999-ABEND
            perform(15, 15);
        }
        return 14;
    }

    /** 9000-EXIT. */
    private int p14() {
        // EXIT
        return 15;
    }

    /** 9999-ABEND. */
    private int p15() {
        // DISPLAY 'CBPAUP0C ABENDING ...'
        Sysout.display("CBPAUP0C ABENDING ...");
        // MOVE 16 TO RETURN-CODE
        Cobol.move(D16, f87_GG_RETURN_CODE, CS);
        // GOBACK
        if (true) throw new Goback();
        return 16;
    }

    /** 9999-EXIT. */
    private int p16() {
        // EXIT
        return 17;
    }

    /** 88 QUALIFIED-FOR-DELETE of WS-QUALIFY-DELETE-FLAG. */
    private boolean isQualifiedForDelete() { return f20_WS_QUALIFY_DELETE_FLAG.equals("Y"); }

    /** 88 NO-MORE-AUTHS of WS-MORE-AUTHS-FLAG. */
    private boolean isNoMoreAuths() { return f19_WS_MORE_AUTHS_FLAG.equals("N"); }

    /** 88 ERR-FLG-ON of WS-ERR-FLG. */
    private boolean isErrFlgOn() { return f17_WS_ERR_FLG.equals("Y"); }

    /** 88 END-OF-AUTHDB of WS-END-OF-AUTHDB-FLAG. */
    private boolean isEndOfAuthdb() { return f18_WS_END_OF_AUTHDB_FLAG.equals("Y"); }

    /** 88 DEBUG-ON of P-DEBUG-FLAG. */
    private boolean isDebugOn() { return Cobol.compare(f39_P_DEBUG_FLAG, "Y", CS) == 0; }

}
