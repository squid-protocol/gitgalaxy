package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.entity.vsam.CardRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.repository.vsam.CardRecordRepository;
import java.nio.charset.Charset;
import java.util.Iterator;
import java.util.List;

@Service
@RequiredArgsConstructor
public class Cbact02cService {

    private static final Logger log = LoggerFactory.getLogger(Cbact02cService.class);

    private static final String CARDFILE = "CARDFILE";

    private final CardRecordRepository cardRecordRepository;
    private final CobolFiles cobolFiles;

    /** The program's working storage for one run. */
    private static final class State {
        String endOfFile = "N";               // END-OF-FILE
        CardRecord cardRecord;                // CARD-RECORD (READ INTO copy)
        Iterator<CardRecord> cursor;          // sequential position in CARDFILE-FILE
    }

    /** The program run as a batch step with no DD overrides and no PARM (#4342): runBatch's DD
     *  names resolved as the program declares them; returns the step's RETURN-CODE. */
    public int executeCbact02c() {
        return runBatch(List.of(), null);
    }

    /** AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS as BATCH SELECT CARDFILE-FILE at app/cbl/CBACT02C.cbl (SELECT CARDFILE-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    // The program reads FD-CARDFILE-REC (150 bytes) INTO CARD-RECORD (150 bytes): same layout, mapped by fromRecord / toRecord.
    // Sequential READ: in key order, CARD-NUM as cp037 bytes (#3945, #3822).
    public List<CardRecord> readAllCardfileFile() {
        return cardRecordRepository.findAll(org.springframework.data.domain.Sort.by("cardNumSort"));
    }

    /** The batch entry (#3622): run by job READCARD step STEP05 (app/jcl/READCARD.jcl:22).
     *  DD CARDFILE (INPUT) -> AWS.M2.CARDDEMO.CARDDATA.VSAM.KSDS. */
    public int runBatch(List<Dd> dds, String parm) {
        State s = new State();
        Charset cs = CobolRecords.charset();

        // PROCEDURE DIVISION main line
        Sysout.display("START OF EXECUTION OF PROGRAM CBACT02C");
        cardfileOpen(s);                                           // PERFORM 0000-CARDFILE-OPEN

        while (!"Y".equals(s.endOfFile)) {                         // PERFORM UNTIL END-OF-FILE = 'Y'
            if ("N".equals(s.endOfFile)) {
                cardfileGetNext(s, cs);                            // PERFORM 1000-CARDFILE-GET-NEXT
                if ("N".equals(s.endOfFile)) {
                    // DISPLAY CARD-RECORD: the group's 150 bytes (FILLER is not kept by the entity: spaces)
                    Sysout.display(new String(s.cardRecord.toRecord(cs), cs));
                }
            }
        }

        cardfileClose();                                           // PERFORM 9000-CARDFILE-CLOSE
        Sysout.display("END OF EXECUTION OF PROGRAM CBACT02C");
        return 0;                                                  // GOBACK; RETURN-CODE never set
    }

    /** 1000-CARDFILE-GET-NEXT. */
    private void cardfileGetNext(State s, Charset cs) {
        // READ CARDFILE-FILE INTO CARD-RECORD
        CobolFiles.Read<CardRecord> read = cobolFiles.readNext(CARDFILE, s.cursor);
        String status = read.status();
        int applResult;
        if ("00".equals(status)) {
            applResult = 0;
            // INTO: the program's own copy; a failed READ leaves the previous record in place
            s.cardRecord = CardRecord.fromRecord(read.record().toRecord(cs), cs);
        } else if ("10".equals(status)) {
            applResult = 16;
        } else {
            applResult = 12;
        }
        if (applResult == 0) {
            // CONTINUE
        } else if (applResult == 16) {
            s.endOfFile = "Y";
        } else {
            Sysout.display("ERROR READING CARDFILE");
            displayIoStatus(status);                               // MOVE CARDFILE-STATUS TO IO-STATUS
            abendProgram();
        }
    }

    /** 0000-CARDFILE-OPEN. */
    private void cardfileOpen(State s) {
        int applResult = 8;                                        // MOVE 8 TO APPL-RESULT
        String status = cobolFiles.open(CARDFILE);                 // OPEN INPUT CARDFILE-FILE
        if ("00".equals(status)) {
            applResult = 0;
            s.cursor = readAllCardfileFile().iterator();
        } else {
            applResult = 12;
        }
        if (applResult != 0) {
            Sysout.display("ERROR OPENING CARDFILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    /** 9000-CARDFILE-CLOSE. */
    private void cardfileClose() {
        int applResult = 8;                                        // ADD 8 TO ZERO GIVING APPL-RESULT
        String status = cobolFiles.close(CARDFILE);                // CLOSE CARDFILE-FILE
        if ("00".equals(status)) {
            applResult = 0;                                        // SUBTRACT APPL-RESULT FROM APPL-RESULT
        } else {
            applResult = 12;
        }
        if (applResult != 0) {
            Sysout.display("ERROR CLOSING CARDFILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    /** 9999-ABEND-PROGRAM: CALL 'CEE3ABD' USING ABCODE(999), TIMING(0). */
    private void abendProgram() {
        Sysout.display("ABENDING PROGRAM");
        throw CobolAbend.user(999, "CBACT02C file error");
    }

    /** 9910-DISPLAY-IO-STATUS; `status` is IO-STATUS (two bytes). */
    private void displayIoStatus(String status) {
        String io = (status + "  ").substring(0, 2);
        char stat1 = io.charAt(0);
        char stat2 = io.charAt(1);
        boolean numeric = isDigit(stat1) && isDigit(stat2);
        if (!numeric || stat1 == '9') {
            // MOVE IO-STAT2 TO TWO-BYTES-RIGHT: the binary halfword holds the byte's value
            int binary = String.valueOf(stat2).getBytes(CobolRecords.charset())[0] & 0xFF;
            Sysout.display("FILE STATUS IS: NNNN" + stat1 + Sysout.number(java.math.BigDecimal.valueOf(binary), 3, 0, false));
        } else {
            Sysout.display("FILE STATUS IS: NNNN" + "00" + io);
        }
    }

    private static boolean isDigit(char c) {
        return c >= '0' && c <= '9';
    }
}
