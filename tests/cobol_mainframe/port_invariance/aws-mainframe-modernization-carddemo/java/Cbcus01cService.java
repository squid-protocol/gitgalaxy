// gitgalaxy-det-port: COBOL CBCUS01C (CBCUS01C.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CBCUS01C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 64, translated 64, holes 0.
 */
@Service
public class Cbcus01cService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D8 = new BigDecimal("8");
    private static final BigDecimal D12 = new BigDecimal("12");
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_FD_CUSTFILE_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_CUSTOMER_RECORD = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_CUSTFILE_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_IO_STATUS = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_TWO_BYTES_BINARY = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_IO_STATUS_04 = Base64.getDecoder().decode(String.join("",
            "MDAwMA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_FD_CUSTFILE_REC = new Storage(IMAGE_s_FD_CUSTFILE_REC.length);
    private final Storage s_CUSTOMER_RECORD = new Storage(IMAGE_s_CUSTOMER_RECORD.length);
    private final Storage s_CUSTFILE_STATUS = new Storage(IMAGE_s_CUSTFILE_STATUS.length);
    private final Storage s_IO_STATUS = new Storage(IMAGE_s_IO_STATUS.length);
    private final Storage s_TWO_BYTES_BINARY = new Storage(IMAGE_s_TWO_BYTES_BINARY.length);
    private final Storage s_IO_STATUS_04 = new Storage(IMAGE_s_IO_STATUS_04.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_FD_CUSTFILE_REC = Field.group(s_FD_CUSTFILE_REC, 0, 500);
    private final Field f4_CUSTOMER_RECORD = Field.group(s_CUSTOMER_RECORD, 0, 500);
    private final Field f24_CUSTFILE_STATUS = Field.group(s_CUSTFILE_STATUS, 0, 2);
    private final Field f27_IO_STATUS = Field.group(s_IO_STATUS, 0, 2);
    private final Field f28_IO_STAT1 = Field.alphanumeric(s_IO_STATUS, 0, 1, false);
    private final Field f29_IO_STAT2 = Field.alphanumeric(s_IO_STATUS, 1, 1, false);
    private final Field f30_TWO_BYTES_BINARY = Field.binary(s_TWO_BYTES_BINARY, 0, 4, 0, false, false);
    private final Field f33_TWO_BYTES_RIGHT = Field.alphanumeric(s_TWO_BYTES_BINARY, 1, 1, false);
    private final Field f34_IO_STATUS_04 = Field.group(s_IO_STATUS_04, 0, 4);
    private final Field f36_IO_STATUS_0403 = Field.zoned(s_IO_STATUS_04, 1, 3, 0, false, false, false);
    private final Field f41_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private long f37_APPL_RESULT;  // APPL-RESULT PIC S9(9) BINARY
    private String f38_END_OF_FILE;  // END-OF-FILE PIC X(01)
    private long f39_ABCODE;  // ABCODE PIC S9(9) BINARY
    private long f40_TIMING;  // TIMING PIC S9(9) BINARY

    private static Integer id_CustomerRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.num(Field.zoned(s, 0, 9, 0, false, false, false), CS).intValue();
    }

    private DetFiles.DetFile CUSTFILE_FILE;

    private final CustomerRecordRepository customerRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Cbcus01cService(CustomerRecordRepository customerRecordRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.customerRecordRepository = customerRecordRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_FD_CUSTFILE_REC, 0, s_FD_CUSTFILE_REC.bytes, 0, IMAGE_s_FD_CUSTFILE_REC.length);
        System.arraycopy(IMAGE_s_CUSTOMER_RECORD, 0, s_CUSTOMER_RECORD.bytes, 0, IMAGE_s_CUSTOMER_RECORD.length);
        System.arraycopy(IMAGE_s_CUSTFILE_STATUS, 0, s_CUSTFILE_STATUS.bytes, 0, IMAGE_s_CUSTFILE_STATUS.length);
        System.arraycopy(IMAGE_s_IO_STATUS, 0, s_IO_STATUS.bytes, 0, IMAGE_s_IO_STATUS.length);
        System.arraycopy(IMAGE_s_TWO_BYTES_BINARY, 0, s_TWO_BYTES_BINARY.bytes, 0, IMAGE_s_TWO_BYTES_BINARY.length);
        System.arraycopy(IMAGE_s_IO_STATUS_04, 0, s_IO_STATUS_04.bytes, 0, IMAGE_s_IO_STATUS_04.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        f37_APPL_RESULT = 0L;
        f38_END_OF_FILE = "N";
        f39_ABCODE = 0L;
        f40_TIMING = 0L;
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 5);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f41_GG_RETURN_CODE, CS).intValue();
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
            CUSTFILE_FILE = new DetFiles.Indexed<CustomerRecord>(files, "CUSTFILE", s_FD_CUSTFILE_REC, 0, 500, 0, 9, customerRecordRepository::findAll, e -> e.toRecord(CS), b -> CustomerRecord.fromRecord(b, CS), customerRecordRepository::save, CS).withFindById(rec -> customerRecordRepository.findById(id_CustomerRecord(rec)));
            try {
                perform(0, 5);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f41_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 6) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** (MAIN). */
    private int p0() {
        // DISPLAY 'START OF EXECUTION OF PROGRAM CBCUS01C'
        Sysout.display("START OF EXECUTION OF PROGRAM CBCUS01C");
        // PERFORM 0000-CUSTFILE-OPEN
        perform(2, 2);
        // PERFORM UNTIL END-OF-FILE = 'Y'
        while (!(f38_END_OF_FILE.equals("Y"))) {
            // IF END-OF-FILE = 'N'
            if (f38_END_OF_FILE.equals("N")) {
                // PERFORM 1000-CUSTFILE-GET-NEXT
                perform(1, 1);
                // IF END-OF-FILE = 'N'
                if (f38_END_OF_FILE.equals("N")) {
                    // DISPLAY CUSTOMER-RECORD
                    Sysout.display(Cobol.displayText(f4_CUSTOMER_RECORD, CS));
                }
            }
        }
        // PERFORM 9000-CUSTFILE-CLOSE
        perform(3, 3);
        // DISPLAY 'END OF EXECUTION OF PROGRAM CBCUS01C'
        Sysout.display("END OF EXECUTION OF PROGRAM CBCUS01C");
        // GOBACK
        if (true) throw new Goback();
        return 1;
    }

    /** 1000-CUSTFILE-GET-NEXT. */
    private int p1() {
        // READ CUSTFILE-FILE INTO CUSTOMER-RECORD
        String st1 = CUSTFILE_FILE.readNext();
        Cobol.move(st1, f24_CUSTFILE_STATUS, CS);
        if (st1.startsWith("0")) {
            Cobol.move(f1_FD_CUSTFILE_REC, f4_CUSTOMER_RECORD, CS);
        }
        // IF CUSTFILE-STATUS = '00'
        if (Cobol.compare(f24_CUSTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            f37_APPL_RESULT = 0L;
            // DISPLAY CUSTOMER-RECORD
            Sysout.display(Cobol.displayText(f4_CUSTOMER_RECORD, CS));
        } else {
            // ELSE IF CUSTFILE-STATUS = '10'
            if (Cobol.compare(f24_CUSTFILE_STATUS, "10", CS) == 0) {
                // MOVE 16 TO APPL-RESULT
                f37_APPL_RESULT = 16L;
            } else {
                // MOVE 12 TO APPL-RESULT
                f37_APPL_RESULT = 12L;
            }
        }
        // IF APPL-AOK
        if (isApplAok()) {
            // CONTINUE
        } else {
            // ELSE IF APPL-EOF
            if (isApplEof()) {
                // MOVE 'Y' TO END-OF-FILE
                f38_END_OF_FILE = "Y";
            } else {
                // DISPLAY 'ERROR READING CUSTOMER FILE'
                Sysout.display("ERROR READING CUSTOMER FILE");
                // MOVE CUSTFILE-STATUS TO IO-STATUS
                Cobol.move(f24_CUSTFILE_STATUS, f27_IO_STATUS, CS);
                // PERFORM Z-DISPLAY-IO-STATUS
                perform(5, 5);
                // PERFORM Z-ABEND-PROGRAM
                perform(4, 4);
            }
        }
        // EXIT
        return 2;
    }

    /** 0000-CUSTFILE-OPEN. */
    private int p2() {
        // MOVE 8 TO APPL-RESULT
        f37_APPL_RESULT = 8L;
        // OPEN INPUT CUSTFILE-FILE
        String st2 = CUSTFILE_FILE.open("INPUT");
        Cobol.move(st2, f24_CUSTFILE_STATUS, CS);
        // IF CUSTFILE-STATUS = '00'
        if (Cobol.compare(f24_CUSTFILE_STATUS, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            f37_APPL_RESULT = 0L;
        } else {
            // MOVE 12 TO APPL-RESULT
            f37_APPL_RESULT = 12L;
        }
        // IF APPL-AOK
        if (isApplAok()) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING CUSTFILE'
            Sysout.display("ERROR OPENING CUSTFILE");
            // MOVE CUSTFILE-STATUS TO IO-STATUS
            Cobol.move(f24_CUSTFILE_STATUS, f27_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(5, 5);
            // PERFORM Z-ABEND-PROGRAM
            perform(4, 4);
        }
        // EXIT
        return 3;
    }

    /** 9000-CUSTFILE-CLOSE. */
    private int p3() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v3 = D8.add(BigDecimal.ZERO);
        f37_APPL_RESULT = Cobol.binary(v3, 9, true, false, CS);
        // CLOSE CUSTFILE-FILE
        String st4 = CUSTFILE_FILE.close();
        Cobol.move(st4, f24_CUSTFILE_STATUS, CS);
        // IF CUSTFILE-STATUS = '00'
        if (Cobol.compare(f24_CUSTFILE_STATUS, "00", CS) == 0) {
            // SUBTRACT APPL-RESULT FROM APPL-RESULT
            BigDecimal t5 = BigDecimal.valueOf(f37_APPL_RESULT);
            f37_APPL_RESULT = Cobol.binary(BigDecimal.valueOf(f37_APPL_RESULT).subtract(t5), 9, true, false, CS);
        } else {
            // ADD 12 TO ZERO GIVING APPL-RESULT
            BigDecimal v7 = D12.add(BigDecimal.ZERO);
            f37_APPL_RESULT = Cobol.binary(v7, 9, true, false, CS);
        }
        // IF APPL-AOK
        if (isApplAok()) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CUSTOMER FILE'
            Sysout.display("ERROR CLOSING CUSTOMER FILE");
            // MOVE CUSTFILE-STATUS TO IO-STATUS
            Cobol.move(f24_CUSTFILE_STATUS, f27_IO_STATUS, CS);
            // PERFORM Z-DISPLAY-IO-STATUS
            perform(5, 5);
            // PERFORM Z-ABEND-PROGRAM
            perform(4, 4);
        }
        // EXIT
        return 4;
    }

    /** Z-ABEND-PROGRAM. */
    private int p4() {
        // DISPLAY 'ABENDING PROGRAM'
        Sysout.display("ABENDING PROGRAM");
        // MOVE 0 TO TIMING
        f40_TIMING = 0L;
        // MOVE 999 TO ABCODE
        f39_ABCODE = 999L;
        // CALL 'CEE3ABD' USING ABCODE, TIMING
        if (true) throw CobolAbend.user(BigDecimal.valueOf(f39_ABCODE).intValue(), "CEE3ABD");
        return 5;
    }

    /** Z-DISPLAY-IO-STATUS. */
    private int p5() {
        // IF IO-STATUS NOT NUMERIC OR IO-STAT1 = '9'
        if ((!(Cobol.isNumeric(f27_IO_STATUS, CS)) || Cobol.compare(f28_IO_STAT1, "9", CS) == 0)) {
            // MOVE IO-STAT1 TO IO-STATUS-04(1:1)
            Cobol.move(f28_IO_STAT1, f34_IO_STATUS_04.ref(1, Integer.valueOf(1)), CS);
            // MOVE 0 TO TWO-BYTES-BINARY
            Cobol.move(D0, f30_TWO_BYTES_BINARY, CS);
            // MOVE IO-STAT2 TO TWO-BYTES-RIGHT
            Cobol.move(f29_IO_STAT2, f33_TWO_BYTES_RIGHT, CS);
            // MOVE TWO-BYTES-BINARY TO IO-STATUS-0403
            Cobol.move(f30_TWO_BYTES_BINARY, f36_IO_STATUS_0403, CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(f34_IO_STATUS_04, CS));
        } else {
            // MOVE '0000' TO IO-STATUS-04
            Cobol.move("0000", f34_IO_STATUS_04, CS);
            // MOVE IO-STATUS TO IO-STATUS-04(3:2)
            Cobol.move(f27_IO_STATUS, f34_IO_STATUS_04.ref(3, Integer.valueOf(2)), CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(f34_IO_STATUS_04, CS));
        }
        // EXIT
        return 6;
    }

    /** 88 APPL-AOK of APPL-RESULT. */
    private boolean isApplAok() { return f37_APPL_RESULT == 0L; }

    /** 88 APPL-EOF of APPL-RESULT. */
    private boolean isApplEof() { return f37_APPL_RESULT == 16L; }

}
