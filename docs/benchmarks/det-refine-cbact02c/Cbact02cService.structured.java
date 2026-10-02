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
import com.gitgalaxy.modernized.entity.vsam.CardRecord;
import com.gitgalaxy.modernized.repository.vsam.CardRecordRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * CBACT02C: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 63, translated 63, holes 0.
 */
@Service
public class Cbact02cService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D16 = new BigDecimal("16");
    private static final BigDecimal D12 = new BigDecimal("12");
    private static final BigDecimal D8 = new BigDecimal("8");
    private static final BigDecimal D999 = new BigDecimal("999");

    private static final byte[] IMAGE_s_FD_CARDFILE_REC = Base64.getDecoder().decode(String.join("", "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_CARD_RECORD = Base64.getDecoder().decode(String.join("", "ICAgICAgICAgICAgICAgIDAwMDAwMDAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_CARDFILE_STATUS = Base64.getDecoder().decode(String.join("", "ICA="));
    private static final byte[] IMAGE_s_IO_STATUS = Base64.getDecoder().decode(String.join("", "ICA="));
    private static final byte[] IMAGE_s_TWO_BYTES_BINARY = Base64.getDecoder().decode(String.join("", "AAA="));
    private static final byte[] IMAGE_s_IO_STATUS_04 = Base64.getDecoder().decode(String.join("", "MDAwMA=="));
    private static final byte[] IMAGE_s_APPL_RESULT = Base64.getDecoder().decode(String.join("", "AAAAAA=="));
    private static final byte[] IMAGE_s_END_OF_FILE = Base64.getDecoder().decode(String.join("", "Tg=="));
    private static final byte[] IMAGE_s_ABCODE = Base64.getDecoder().decode(String.join("", "AAAAAA=="));
    private static final byte[] IMAGE_s_TIMING = Base64.getDecoder().decode(String.join("", "AAAAAA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("", "AAA="));
    private final Storage s_FD_CARDFILE_REC = new Storage(IMAGE_s_FD_CARDFILE_REC.length);
    private final Storage s_CARD_RECORD = new Storage(IMAGE_s_CARD_RECORD.length);
    private final Storage s_CARDFILE_STATUS = new Storage(IMAGE_s_CARDFILE_STATUS.length);
    private final Storage s_IO_STATUS = new Storage(IMAGE_s_IO_STATUS.length);
    private final Storage s_TWO_BYTES_BINARY = new Storage(IMAGE_s_TWO_BYTES_BINARY.length);
    private final Storage s_IO_STATUS_04 = new Storage(IMAGE_s_IO_STATUS_04.length);
    private final Storage s_APPL_RESULT = new Storage(IMAGE_s_APPL_RESULT.length);
    private final Storage s_END_OF_FILE = new Storage(IMAGE_s_END_OF_FILE.length);
    private final Storage s_ABCODE = new Storage(IMAGE_s_ABCODE.length);
    private final Storage s_TIMING = new Storage(IMAGE_s_TIMING.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private Field abcode;
    private Field applResult;
    private Field cardAcctId;
    private Field cardActiveStatus;
    private Field cardCvvCd;
    private Field cardEmbossedName;
    private Field cardExpiraionDate;
    private Field cardNum;
    private Field cardRecord;
    private Field cardfileStat1;
    private Field cardfileStat2;
    private Field cardfileStatus;
    private Field endOfFile;
    private Field fdCardData;
    private Field fdCardNum;
    private Field fdCardfileRec;
    private Field filler11;
    private Field ggReturnCode;
    private Field ioStat1;
    private Field ioStat2;
    private Field ioStatus;
    private Field ioStatus04;
    private Field ioStatus0401;
    private Field ioStatus0403;
    private Field timing;
    private Field twoBytesAlpha;
    private Field twoBytesBinary;
    private Field twoBytesLeft;
    private Field twoBytesRight;

    private static String id_CardRecord(byte[] rec) {
        Storage s = Storage.of(rec);
        return Cobol.text(Field.alphanumeric(s, 0, 16, false), CS);
    }

    private DetFiles.DetFile CARDFILE_FILE;

    private final CardRecordRepository cardRecordRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public Cbact02cService(CardRecordRepository cardRecordRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.cardRecordRepository = cardRecordRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        fields0();
    }

    private void fields0() {
        fdCardfileRec = Field.group(s_FD_CARDFILE_REC, 0, 150);
        fdCardNum = Field.alphanumeric(s_FD_CARDFILE_REC, 0, 16, false);
        fdCardData = Field.alphanumeric(s_FD_CARDFILE_REC, 16, 134, false);
        cardRecord = Field.group(s_CARD_RECORD, 0, 150);
        cardNum = Field.alphanumeric(s_CARD_RECORD, 0, 16, false);
        cardAcctId = Field.zoned(s_CARD_RECORD, 16, 11, 0, false, false, false);
        cardCvvCd = Field.zoned(s_CARD_RECORD, 27, 3, 0, false, false, false);
        cardEmbossedName = Field.alphanumeric(s_CARD_RECORD, 30, 50, false);
        cardExpiraionDate = Field.alphanumeric(s_CARD_RECORD, 80, 10, false);
        cardActiveStatus = Field.alphanumeric(s_CARD_RECORD, 90, 1, false);
        filler11 = Field.alphanumeric(s_CARD_RECORD, 91, 59, false);
        cardfileStatus = Field.group(s_CARDFILE_STATUS, 0, 2);
        cardfileStat1 = Field.alphanumeric(s_CARDFILE_STATUS, 0, 1, false);
        cardfileStat2 = Field.alphanumeric(s_CARDFILE_STATUS, 1, 1, false);
        ioStatus = Field.group(s_IO_STATUS, 0, 2);
        ioStat1 = Field.alphanumeric(s_IO_STATUS, 0, 1, false);
        ioStat2 = Field.alphanumeric(s_IO_STATUS, 1, 1, false);
        twoBytesBinary = Field.binary(s_TWO_BYTES_BINARY, 0, 4, 0, false, false);
        twoBytesAlpha = Field.group(s_TWO_BYTES_BINARY, 0, 2);
        twoBytesLeft = Field.alphanumeric(s_TWO_BYTES_BINARY, 0, 1, false);
        twoBytesRight = Field.alphanumeric(s_TWO_BYTES_BINARY, 1, 1, false);
        ioStatus04 = Field.group(s_IO_STATUS_04, 0, 4);
        ioStatus0401 = Field.zoned(s_IO_STATUS_04, 0, 1, 0, false, false, false);
        ioStatus0403 = Field.zoned(s_IO_STATUS_04, 1, 3, 0, false, false, false);
        applResult = Field.binary(s_APPL_RESULT, 0, 9, 0, true, false);
        endOfFile = Field.alphanumeric(s_END_OF_FILE, 0, 1, false);
        abcode = Field.binary(s_ABCODE, 0, 9, 0, true, false);
        timing = Field.binary(s_TIMING, 0, 9, 0, true, false);
        ggReturnCode = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        System.arraycopy(IMAGE_s_FD_CARDFILE_REC, 0, s_FD_CARDFILE_REC.bytes, 0, IMAGE_s_FD_CARDFILE_REC.length);
        System.arraycopy(IMAGE_s_CARD_RECORD, 0, s_CARD_RECORD.bytes, 0, IMAGE_s_CARD_RECORD.length);
        System.arraycopy(IMAGE_s_CARDFILE_STATUS, 0, s_CARDFILE_STATUS.bytes, 0, IMAGE_s_CARDFILE_STATUS.length);
        System.arraycopy(IMAGE_s_IO_STATUS, 0, s_IO_STATUS.bytes, 0, IMAGE_s_IO_STATUS.length);
        System.arraycopy(IMAGE_s_TWO_BYTES_BINARY, 0, s_TWO_BYTES_BINARY.bytes, 0, IMAGE_s_TWO_BYTES_BINARY.length);
        System.arraycopy(IMAGE_s_IO_STATUS_04, 0, s_IO_STATUS_04.bytes, 0, IMAGE_s_IO_STATUS_04.length);
        System.arraycopy(IMAGE_s_APPL_RESULT, 0, s_APPL_RESULT.bytes, 0, IMAGE_s_APPL_RESULT.length);
        System.arraycopy(IMAGE_s_END_OF_FILE, 0, s_END_OF_FILE.bytes, 0, IMAGE_s_END_OF_FILE.length);
        System.arraycopy(IMAGE_s_ABCODE, 0, s_ABCODE.bytes, 0, IMAGE_s_ABCODE.length);
        System.arraycopy(IMAGE_s_TIMING, 0, s_TIMING.bytes, 0, IMAGE_s_TIMING.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        try {
            runAll();
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(ggReturnCode, CS).intValue();
    }

    public void executeCbact02c() {
        runBatch(List.of(), null);
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
        System.arraycopy(IMAGE_s_FD_CARDFILE_REC, 0, s_FD_CARDFILE_REC.bytes, 0, IMAGE_s_FD_CARDFILE_REC.length);
        System.arraycopy(IMAGE_s_CARD_RECORD, 0, s_CARD_RECORD.bytes, 0, IMAGE_s_CARD_RECORD.length);
        System.arraycopy(IMAGE_s_CARDFILE_STATUS, 0, s_CARDFILE_STATUS.bytes, 0, IMAGE_s_CARDFILE_STATUS.length);
        System.arraycopy(IMAGE_s_IO_STATUS, 0, s_IO_STATUS.bytes, 0, IMAGE_s_IO_STATUS.length);
        System.arraycopy(IMAGE_s_TWO_BYTES_BINARY, 0, s_TWO_BYTES_BINARY.bytes, 0, IMAGE_s_TWO_BYTES_BINARY.length);
        System.arraycopy(IMAGE_s_IO_STATUS_04, 0, s_IO_STATUS_04.bytes, 0, IMAGE_s_IO_STATUS_04.length);
        System.arraycopy(IMAGE_s_APPL_RESULT, 0, s_APPL_RESULT.bytes, 0, IMAGE_s_APPL_RESULT.length);
        System.arraycopy(IMAGE_s_END_OF_FILE, 0, s_END_OF_FILE.bytes, 0, IMAGE_s_END_OF_FILE.length);
        System.arraycopy(IMAGE_s_ABCODE, 0, s_ABCODE.bytes, 0, IMAGE_s_ABCODE.length);
        System.arraycopy(IMAGE_s_TIMING, 0, s_TIMING.bytes, 0, IMAGE_s_TIMING.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        CARDFILE_FILE = new DetFiles.Indexed<CardRecord>(files, "CARDFILE", s_FD_CARDFILE_REC, 0, 150, 0, 16, cardRecordRepository::findAll, e -> e.toRecord(CS), b -> CardRecord.fromRecord(b, CS), cardRecordRepository::save, CS).withFindById(rec -> cardRecordRepository.findById(id_CardRecord(rec)));
        try {
            runAll();
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(ggReturnCode, CS).intValue();
    }

    /** The PROCEDURE DIVISION: its paragraphs in order (each falls into the next). */
    private void runAll() {
        main();
        p1000CardfileGetNext();
        p0000CardfileOpen();
        p9000CardfileClose();
        p9999AbendProgram();
        p9910DisplayIoStatus();
    }

    /** (MAIN). */
    private void main() {
        // DISPLAY 'START OF EXECUTION OF PROGRAM CBACT02C'
        Sysout.display("START OF EXECUTION OF PROGRAM CBACT02C");
        // PERFORM 0000-CARDFILE-OPEN
        p0000CardfileOpen();
        // PERFORM UNTIL END-OF-FILE = 'Y'
        while (!(Cobol.compare(endOfFile, "Y", CS) == 0)) {
            // IF END-OF-FILE = 'N'
            if (Cobol.compare(endOfFile, "N", CS) == 0) {
                // PERFORM 1000-CARDFILE-GET-NEXT
                p1000CardfileGetNext();
                // IF END-OF-FILE = 'N'
                if (Cobol.compare(endOfFile, "N", CS) == 0) {
                    // DISPLAY CARD-RECORD
                    Sysout.display(Cobol.displayText(cardRecord, CS));
                }
            }
        }
        // PERFORM 9000-CARDFILE-CLOSE
        p9000CardfileClose();
        // DISPLAY 'END OF EXECUTION OF PROGRAM CBACT02C'
        Sysout.display("END OF EXECUTION OF PROGRAM CBACT02C");
        // GOBACK
        if (true) throw new Goback();
    }

    /** 1000-CARDFILE-GET-NEXT. */
    private void p1000CardfileGetNext() {
        // READ CARDFILE-FILE INTO CARD-RECORD
        String st1 = CARDFILE_FILE.readNext();
        Cobol.move(st1, cardfileStatus, CS);
        if (st1.startsWith("0")) {
            Cobol.move(fdCardfileRec, cardRecord, CS);
        }
        // IF CARDFILE-STATUS = '00'
        if (Cobol.compare(cardfileStatus, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, applResult, CS);
        } else {
            // ELSE IF CARDFILE-STATUS = '10'
            if (Cobol.compare(cardfileStatus, "10", CS) == 0) {
                // MOVE 16 TO APPL-RESULT
                Cobol.move(D16, applResult, CS);
            } else {
                // MOVE 12 TO APPL-RESULT
                Cobol.move(D12, applResult, CS);
            }
        }
        // IF APPL-AOK
        if (Cobol.compare(applResult, D0, CS) == 0) {
            // CONTINUE
        } else {
            // ELSE IF APPL-EOF
            if (Cobol.compare(applResult, D16, CS) == 0) {
                // MOVE 'Y' TO END-OF-FILE
                Cobol.move("Y", endOfFile, CS);
            } else {
                // DISPLAY 'ERROR READING CARDFILE'
                Sysout.display("ERROR READING CARDFILE");
                // MOVE CARDFILE-STATUS TO IO-STATUS
                Cobol.move(cardfileStatus, ioStatus, CS);
                // PERFORM 9910-DISPLAY-IO-STATUS
                p9910DisplayIoStatus();
                // PERFORM 9999-ABEND-PROGRAM
                p9999AbendProgram();
            }
        }
        // EXIT
    }

    /** 0000-CARDFILE-OPEN. */
    private void p0000CardfileOpen() {
        // MOVE 8 TO APPL-RESULT
        Cobol.move(D8, applResult, CS);
        // OPEN INPUT CARDFILE-FILE
        String st2 = CARDFILE_FILE.open("INPUT");
        Cobol.move(st2, cardfileStatus, CS);
        // IF CARDFILE-STATUS = '00'
        if (Cobol.compare(cardfileStatus, "00", CS) == 0) {
            // MOVE 0 TO APPL-RESULT
            Cobol.move(D0, applResult, CS);
        } else {
            // MOVE 12 TO APPL-RESULT
            Cobol.move(D12, applResult, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(applResult, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR OPENING CARDFILE'
            Sysout.display("ERROR OPENING CARDFILE");
            // MOVE CARDFILE-STATUS TO IO-STATUS
            Cobol.move(cardfileStatus, ioStatus, CS);
            // PERFORM 9910-DISPLAY-IO-STATUS
            p9910DisplayIoStatus();
            // PERFORM 9999-ABEND-PROGRAM
            p9999AbendProgram();
        }
        // EXIT
    }

    /** 9000-CARDFILE-CLOSE. */
    private void p9000CardfileClose() {
        // ADD 8 TO ZERO GIVING APPL-RESULT
        BigDecimal v3 = D8.add(BigDecimal.ZERO);
        Cobol.store(applResult, v3, false, CS);
        // CLOSE CARDFILE-FILE
        String st4 = CARDFILE_FILE.close();
        Cobol.move(st4, cardfileStatus, CS);
        // IF CARDFILE-STATUS = '00'
        if (Cobol.compare(cardfileStatus, "00", CS) == 0) {
            // SUBTRACT APPL-RESULT FROM APPL-RESULT
            BigDecimal t5 = Cobol.num(applResult, CS);
            Cobol.store(applResult, Cobol.num(applResult, CS).subtract(t5), false, CS);
        } else {
            // ADD 12 TO ZERO GIVING APPL-RESULT
            BigDecimal v7 = D12.add(BigDecimal.ZERO);
            Cobol.store(applResult, v7, false, CS);
        }
        // IF APPL-AOK
        if (Cobol.compare(applResult, D0, CS) == 0) {
            // CONTINUE
        } else {
            // DISPLAY 'ERROR CLOSING CARDFILE'
            Sysout.display("ERROR CLOSING CARDFILE");
            // MOVE CARDFILE-STATUS TO IO-STATUS
            Cobol.move(cardfileStatus, ioStatus, CS);
            // PERFORM 9910-DISPLAY-IO-STATUS
            p9910DisplayIoStatus();
            // PERFORM 9999-ABEND-PROGRAM
            p9999AbendProgram();
        }
        // EXIT
    }

    /** 9999-ABEND-PROGRAM. */
    private void p9999AbendProgram() {
        // DISPLAY 'ABENDING PROGRAM'
        Sysout.display("ABENDING PROGRAM");
        // MOVE 0 TO TIMING
        Cobol.move(D0, timing, CS);
        // MOVE 999 TO ABCODE
        Cobol.move(D999, abcode, CS);
        // CALL 'CEE3ABD' USING ABCODE, TIMING
        if (true) throw CobolAbend.user(Cobol.num(abcode, CS).intValue(), "CEE3ABD");
    }

    /** 9910-DISPLAY-IO-STATUS. */
    private void p9910DisplayIoStatus() {
        // IF IO-STATUS NOT NUMERIC OR IO-STAT1 = '9'
        if ((!(Cobol.isNumeric(ioStatus, CS)) || Cobol.compare(ioStat1, "9", CS) == 0)) {
            // MOVE IO-STAT1 TO IO-STATUS-04(1:1)
            Cobol.move(ioStat1, ioStatus04.ref(1, Integer.valueOf(1)), CS);
            // MOVE 0 TO TWO-BYTES-BINARY
            Cobol.move(D0, twoBytesBinary, CS);
            // MOVE IO-STAT2 TO TWO-BYTES-RIGHT
            Cobol.move(ioStat2, twoBytesRight, CS);
            // MOVE TWO-BYTES-BINARY TO IO-STATUS-0403
            Cobol.move(twoBytesBinary, ioStatus0403, CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(ioStatus04, CS));
        } else {
            // MOVE '0000' TO IO-STATUS-04
            Cobol.move("0000", ioStatus04, CS);
            // MOVE IO-STATUS TO IO-STATUS-04(3:2)
            Cobol.move(ioStatus, ioStatus04.ref(3, Integer.valueOf(2)), CS);
            // DISPLAY 'FILE STATUS IS: NNNN' IO-STATUS-04
            Sysout.display("FILE STATUS IS: NNNN", Cobol.displayText(ioStatus04, CS));
        }
        // EXIT
    }

}
