// gitgalaxy-det-port: COBOL COBTUPDT (COBTUPDT.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.cobolrt.sql.DetSql;
import com.gitgalaxy.modernized.repository.db2.TransactionTypeRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * COBTUPDT: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 58, translated 58, holes 0.
 */
@Service
public class CobtupdtService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D100 = new BigDecimal("100");
    private static final BigDecimal D4 = new BigDecimal("4");

    private static final byte[] IMAGE_s_WS_INPUT_VARS = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_SQLCA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAAAAAAAAAAAAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DCLTRANSACTION_TYPE = Base64.getDecoder().decode(String.join("",
            "ICAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_FLAGS = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WORKING_VARIABLES = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_MISC_VARS = Base64.getDecoder().decode(String.join("",
            "ICAgICA="));
    private static final byte[] IMAGE_s_WS_INF_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_WS_INPUT_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_INPUT_VARS = new Storage(IMAGE_s_WS_INPUT_VARS.length);
    private final Storage s_SQLCA = new Storage(IMAGE_s_SQLCA.length);
    private final Storage s_DCLTRANSACTION_TYPE = new Storage(IMAGE_s_DCLTRANSACTION_TYPE.length);
    private final Storage s_FLAGS = new Storage(IMAGE_s_FLAGS.length);
    private final Storage s_WORKING_VARIABLES = new Storage(IMAGE_s_WORKING_VARIABLES.length);
    private final Storage s_WS_MISC_VARS = new Storage(IMAGE_s_WS_MISC_VARS.length);
    private final Storage s_WS_INF_STATUS = new Storage(IMAGE_s_WS_INF_STATUS.length);
    private final Storage s_WS_INPUT_REC = new Storage(IMAGE_s_WS_INPUT_REC.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_WS_INPUT_VARS = Field.group(s_WS_INPUT_VARS, 0, 53);
    private final Field f5_SQLCA = Field.group(s_SQLCA, 0, 136);
    private final Field f8_SQLCODE = Field.binary(s_SQLCA, 12, 9, 0, true, true);
    private final Field f35_WS_RETURN_MSG = Field.alphanumeric(s_WORKING_VARIABLES, 0, 80, false);
    private final Field f37_WS_VAR_SQLCODE = Field.numericEdited(s_WS_MISC_VARS, 0, 5, "----9", false);
    private final Field f38_WS_INF_STATUS = Field.group(s_WS_INF_STATUS, 0, 2);
    private final Field f41_WS_INPUT_REC = Field.group(s_WS_INPUT_REC, 0, 53);
    private final Field f42_INPUT_REC_TYPE = Field.alphanumeric(s_WS_INPUT_REC, 0, 1, false);
    private final Field f43_INPUT_REC_NUMBER = Field.alphanumeric(s_WS_INPUT_REC, 1, 2, false);
    private final Field f44_INPUT_REC_DESC = Field.alphanumeric(s_WS_INPUT_REC, 3, 50, false);
    private final Field f45_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private String f28_DCL_TR_TYPE;  // DCL-TR-TYPE PIC X(2)
    private long f30_DCL_TR_DESCRIPTION_LEN;  // DCL-TR-DESCRIPTION-LEN PIC S9(4) BINARY
    private String f31_DCL_TR_DESCRIPTION_TEXT;  // DCL-TR-DESCRIPTION-TEXT PIC X(50)
    private String f33_LASTREC;  // LASTREC PIC X(1)

    private DetFiles.DetFile TR_RECORD;

    private final TransactionTypeRepository transactionTypeRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public CobtupdtService(TransactionTypeRepository transactionTypeRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.transactionTypeRepository = transactionTypeRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_INPUT_VARS, 0, s_WS_INPUT_VARS.bytes, 0, IMAGE_s_WS_INPUT_VARS.length);
        System.arraycopy(IMAGE_s_SQLCA, 0, s_SQLCA.bytes, 0, IMAGE_s_SQLCA.length);
        System.arraycopy(IMAGE_s_DCLTRANSACTION_TYPE, 0, s_DCLTRANSACTION_TYPE.bytes, 0, IMAGE_s_DCLTRANSACTION_TYPE.length);
        System.arraycopy(IMAGE_s_FLAGS, 0, s_FLAGS.bytes, 0, IMAGE_s_FLAGS.length);
        System.arraycopy(IMAGE_s_WORKING_VARIABLES, 0, s_WORKING_VARIABLES.bytes, 0, IMAGE_s_WORKING_VARIABLES.length);
        System.arraycopy(IMAGE_s_WS_MISC_VARS, 0, s_WS_MISC_VARS.bytes, 0, IMAGE_s_WS_MISC_VARS.length);
        System.arraycopy(IMAGE_s_WS_INF_STATUS, 0, s_WS_INF_STATUS.bytes, 0, IMAGE_s_WS_INF_STATUS.length);
        System.arraycopy(IMAGE_s_WS_INPUT_REC, 0, s_WS_INPUT_REC.bytes, 0, IMAGE_s_WS_INPUT_REC.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        f28_DCL_TR_TYPE = "  ";
        f30_DCL_TR_DESCRIPTION_LEN = 0L;
        f31_DCL_TR_DESCRIPTION_TEXT = "                                                  ";
        f33_LASTREC = " ";
        Cobol.moveFigurative(Figurative.ZEROS, f37_WS_VAR_SQLCODE, CS);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 8);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f45_GG_RETURN_CODE, CS).intValue();
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
            DetSql.closeAll();  // a step's cursors are its own
            initialState();
            TR_RECORD = new DetFiles.Sequential(files, "INPFILE", () -> datasets.path(dd(dds, "INPFILE")), s_WS_INPUT_VARS, 0, 53);
            try {
                perform(0, 8);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f45_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 9) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** 0001-OPEN-FILES. */
    private int p0() {
        // OPEN INPUT TR-RECORD
        String st1 = TR_RECORD.open("INPUT");
        Cobol.move(st1, f38_WS_INF_STATUS, CS);
        // IF WS-INF-STATUS = '00' THEN
        if (Cobol.compare(f38_WS_INF_STATUS, "00", CS) == 0) {
            // DISPLAY 'OPEN FILE OK'
            Sysout.display("OPEN FILE OK");
        } else {
            // DISPLAY 'OPEN FILE NOT OK'
            Sysout.display("OPEN FILE NOT OK");
        }
        // EXIT
        return 1;
    }

    /** 1001-READ-NEXT-RECORDS. */
    private int p1() {
        // PERFORM 1002-READ-RECORDS
        perform(2, 2);
        // PERFORM UNTIL LASTREC = 'Y'
        while (!(f33_LASTREC.equals("Y"))) {
            // PERFORM 1003-TREAT-RECORD
            perform(3, 3);
            // PERFORM 1002-READ-RECORDS
            perform(2, 2);
        }
        // PERFORM 2001-CLOSE-STOP
        perform(8, 8);
        // EXIT
        // STOP RUN
        if (true) throw new Goback();
        return 2;
    }

    /** 1002-READ-RECORDS. */
    private int p2() {
        // READ TR-RECORD NEXT RECORD INTO WS-INPUT-REC
        String st2 = TR_RECORD.readNext();
        Cobol.move(st2, f38_WS_INF_STATUS, CS);
        if (st2.startsWith("0")) {
            Cobol.move(f1_WS_INPUT_VARS, f41_WS_INPUT_REC, CS);
        }
        if (st2.equals("10")) {
            // MOVE 'Y' TO LASTREC
            f33_LASTREC = "Y";
        }
        // IF LASTREC NOT EQUAL TO 'Y' THEN
        if (!(f33_LASTREC.equals("Y"))) {
            // DISPLAY 'PROCESSING ' WS-INPUT-REC
            Sysout.display("PROCESSING   ", Cobol.displayText(f41_WS_INPUT_REC, CS));
        }
        // EXIT
        return 3;
    }

    /** 1003-TREAT-RECORD. */
    private int p3() {
        // EVALUATE INPUT-REC-TYPE
        if ((Cobol.compare(f42_INPUT_REC_TYPE, "A", CS) == 0)) {
            // DISPLAY 'ADDING RECORD'
            Sysout.display("ADDING RECORD");
            // PERFORM 10031-INSERT-DB
            perform(4, 4);
        } else if ((Cobol.compare(f42_INPUT_REC_TYPE, "U", CS) == 0)) {
            // DISPLAY 'UPDATING RECORD'
            Sysout.display("UPDATING RECORD");
            // PERFORM 10032-UPDATE-DB
            perform(5, 5);
        } else if ((Cobol.compare(f42_INPUT_REC_TYPE, "D", CS) == 0)) {
            // DISPLAY 'DELETING RECORD'
            Sysout.display("DELETING RECORD");
            // PERFORM 10033-DELETE-DB
            perform(6, 6);
        } else if ((Cobol.compare(f42_INPUT_REC_TYPE, "*", CS) == 0)) {
            // DISPLAY 'IGNORING COMMENTED LINE'
            Sysout.display("IGNORING COMMENTED LINE");
        } else if (true) {
            // STRING 'ERROR: TYPE NOT VALID' DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("ERROR: TYPE NOT VALID", CS));
            // PERFORM 9999-ABEND
            perform(7, 7);
        }
        // EXIT
        return 4;
    }

    /** 10031-INSERT-DB. */
    private int p4() {
        // EXEC SQL INSERT INTO CARDDEMO.TRANSACTION_TYPE ( TR_TYPE, TR_DESCRIPTION ) VALUES ( :INPUT-REC-NUMBER, :INPUT-REC-DESC ) END-EXEC
        java.util.Map<String, Object> sqlParams3 = new java.util.HashMap<>();
        sqlParams3.put("inputRecNumber", DetSql.charIn(f43_INPUT_REC_NUMBER, CS));
        sqlParams3.put("inputRecDesc", DetSql.charIn(f44_INPUT_REC_DESC, CS));
        DetSql.update(f5_SQLCA, "COBTUPDT:137", () -> transactionTypeRepository.insertL137Cobtupdt(sqlParams3), false, CS);
        // MOVE SQLCODE TO WS-VAR-SQLCODE
        Cobol.move(f8_SQLCODE, f37_WS_VAR_SQLCODE, CS);
        // EVALUATE TRUE
        if ((Cobol.num(f8_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0)) {
            // DISPLAY 'RECORD INSERTED SUCCESSFULLY'
            Sysout.display("RECORD INSERTED SUCCESSFULLY");
        } else if ((Cobol.num(f8_SQLCODE, CS).compareTo(D0) < 0)) {
            // STRING 'Error accessing:' ' TRANSACTION_TYPE table. SQLCODE:' WS-VAR-SQLCODE DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("Error accessing:", CS), Cobol.StringPart.size(" TRANSACTION_TYPE table. SQLCODE:", CS), Cobol.StringPart.size(f37_WS_VAR_SQLCODE));
            // PERFORM 9999-ABEND
            perform(7, 7);
        }
        // EXIT
        return 5;
    }

    /** 10032-UPDATE-DB. */
    private int p5() {
        // EXEC SQL UPDATE CARDDEMO.TRANSACTION_TYPE SET TR_DESCRIPTION = :INPUT-REC-DESC WHERE TR_TYPE = :INPUT-REC-NUMBER END-EXEC
        java.util.Map<String, Object> sqlParams4 = new java.util.HashMap<>();
        sqlParams4.put("inputRecDesc", DetSql.charIn(f44_INPUT_REC_DESC, CS));
        sqlParams4.put("inputRecNumber", DetSql.charIn(f43_INPUT_REC_NUMBER, CS));
        DetSql.update(f5_SQLCA, "COBTUPDT:171", () -> transactionTypeRepository.updateL171Cobtupdt(sqlParams4), true, CS);
        // MOVE SQLCODE TO WS-VAR-SQLCODE
        Cobol.move(f8_SQLCODE, f37_WS_VAR_SQLCODE, CS);
        // EVALUATE TRUE
        if ((Cobol.num(f8_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0)) {
            // DISPLAY 'RECORD UPDATED SUCCESSFULLY'
            Sysout.display("RECORD UPDATED SUCCESSFULLY");
        } else if ((Cobol.num(f8_SQLCODE, CS).compareTo(D100) == 0)) {
            // STRING 'No records found.' DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("No records found.", CS));
            // PERFORM 9999-ABEND
            perform(7, 7);
        } else if ((Cobol.num(f8_SQLCODE, CS).compareTo(D0) < 0)) {
            // STRING 'Error accessing:' ' TRANSACTION_TYPE table. SQLCODE:' WS-VAR-SQLCODE DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("Error accessing:", CS), Cobol.StringPart.size(" TRANSACTION_TYPE table. SQLCODE:", CS), Cobol.StringPart.size(f37_WS_VAR_SQLCODE));
            // PERFORM 9999-ABEND
            perform(7, 7);
        }
        // EXIT
        return 6;
    }

    /** 10033-DELETE-DB. */
    private int p6() {
        // EXEC SQL DELETE FROM CARDDEMO.TRANSACTION_TYPE WHERE TR_TYPE = :INPUT-REC-NUMBER END-EXEC
        java.util.Map<String, Object> sqlParams5 = new java.util.HashMap<>();
        sqlParams5.put("inputRecNumber", DetSql.charIn(f43_INPUT_REC_NUMBER, CS));
        DetSql.update(f5_SQLCA, "COBTUPDT:201", () -> transactionTypeRepository.deleteL201Cobtupdt(sqlParams5), true, CS);
        // MOVE SQLCODE TO WS-VAR-SQLCODE
        Cobol.move(f8_SQLCODE, f37_WS_VAR_SQLCODE, CS);
        // EVALUATE TRUE
        if ((Cobol.num(f8_SQLCODE, CS).compareTo(BigDecimal.ZERO) == 0)) {
            // DISPLAY 'RECORD DELETED SUCCESSFULLY'
            Sysout.display("RECORD DELETED SUCCESSFULLY");
        } else if ((Cobol.num(f8_SQLCODE, CS).compareTo(D100) == 0)) {
            // STRING 'No records found.' DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("No records found.", CS));
            // PERFORM 9999-ABEND
            perform(7, 7);
        } else if ((Cobol.num(f8_SQLCODE, CS).compareTo(D0) < 0)) {
            // STRING 'Error accessing:' ' TRANSACTION_TYPE table. SQLCODE:' WS-VAR-SQLCODE DELIMITED BY SIZE INTO WS-RETURN-MSG
            Cobol.string(f35_WS_RETURN_MSG, null, CS, Cobol.StringPart.size("Error accessing:", CS), Cobol.StringPart.size(" TRANSACTION_TYPE table. SQLCODE:", CS), Cobol.StringPart.size(f37_WS_VAR_SQLCODE));
            // PERFORM 9999-ABEND
            perform(7, 7);
        }
        // EXIT
        return 7;
    }

    /** 9999-ABEND. */
    private int p7() {
        // DISPLAY WS-RETURN-MSG
        Sysout.display(Cobol.displayText(f35_WS_RETURN_MSG, CS));
        // MOVE 4 TO RETURN-CODE
        Cobol.move(D4, f45_GG_RETURN_CODE, CS);
        // EXIT
        return 8;
    }

    /** 2001-CLOSE-STOP. */
    private int p8() {
        // CLOSE TR-RECORD
        String st6 = TR_RECORD.close();
        Cobol.move(st6, f38_WS_INF_STATUS, CS);
        // EXIT
        return 9;
    }

}
