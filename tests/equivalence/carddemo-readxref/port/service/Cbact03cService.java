package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class Cbact03cService {

    private static final Logger log = LoggerFactory.getLogger(Cbact03cService.class);

    private static final String XREFFILE = "XREFFILE";

    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CobolFiles cobolFiles;

    /** The program's working storage for one run. */
    private static final class Run {
        String endOfFile = "N";                 // END-OF-FILE PIC X(01) VALUE 'N'
        CardXrefRecord cardXrefRecord;          // CARD-XREF-RECORD (READ INTO target: the program's own copy)
        Iterator<CardXrefRecord> cursor;        // the sequential cursor of XREFFILE-FILE
    }

    public void executeCbact03c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CBACT03C");
        runBatch(List.of(), null);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as BATCH SELECT XREFFILE-FILE at app/cbl/CBACT03C.cbl (SELECT XREFFILE-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    // FD-XREFFILE-REC (50 bytes) is mapped onto CARD-XREF-RECORD by CardXrefRecord.fromRecord / toRecord.
    // Sequential READ: in key order, XREF-CARD-NUM as cp037 bytes (#3945, #3822).
    public List<CardXrefRecord> readAllXreffileFile() {
        return cardXrefRecordRepository.findAll(org.springframework.data.domain.Sort.by("xrefCardNumSort"));
    }

    /** The batch entry (#3622): run by job READXREF step STEP05 (app/jcl/READXREF.jcl:22).
     *  DD XREFFILE (INPUT) -> AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS. */
    public int runBatch(List<Dd> dds, String parm) {
        Run run = new Run();

        // PROCEDURE DIVISION main line
        Sysout.display("START OF EXECUTION OF PROGRAM CBACT03C");
        xreffileOpen(run);                                   // PERFORM 0000-XREFFILE-OPEN

        while (!"Y".equals(run.endOfFile)) {                 // PERFORM UNTIL END-OF-FILE = 'Y'
            if ("N".equals(run.endOfFile)) {
                xreffileGetNext(run);                        // PERFORM 1000-XREFFILE-GET-NEXT
                if ("N".equals(run.endOfFile)) {
                    // DEFECT kept: 1000-XREFFILE-GET-NEXT already DISPLAYs the record, so every
                    // record is written twice. One-line fix: drop this DISPLAY (or the one in 1000).
                    displayRecord(run);                      // DISPLAY CARD-XREF-RECORD
                }
            }
        }

        xreffileClose();                                     // PERFORM 9000-XREFFILE-CLOSE

        Sysout.display("END OF EXECUTION OF PROGRAM CBACT03C");

        return 0;                                            // GOBACK (RETURN-CODE untouched)
    }

    /** DISPLAY CARD-XREF-RECORD: the group's 50 bytes (zoned digits, FILLER as spaces). */
    private void displayRecord(Run run) {
        Charset cs = CobolRecords.charset();
        Sysout.display(new String(run.cardXrefRecord.toRecord(cs), cs));
    }

    // 1000-XREFFILE-GET-NEXT
    private void xreffileGetNext(Run run) {
        Charset cs = CobolRecords.charset();
        CobolFiles.Read<CardXrefRecord> read = cobolFiles.readNext(XREFFILE, run.cursor);
        int applResult;
        if (CobolCompare.eq(read.status(), "00")) {
            // READ ... INTO: the program's own copy, never the repository's entity
            run.cardXrefRecord = CardXrefRecord.fromRecord(read.record().toRecord(cs), cs);
            applResult = 0;
            displayRecord(run);
        } else if (CobolCompare.eq(read.status(), "10")) {
            applResult = 16;
        } else {
            applResult = 12;
        }
        if (applResult == 0) {
            // CONTINUE
        } else if (applResult == 16) {
            run.endOfFile = "Y";
        } else {
            Sysout.display("ERROR READING XREFFILE");
            displayIoStatus(read.status());                  // MOVE XREFFILE-STATUS TO IO-STATUS
            abendProgram();
        }
    }

    // 0000-XREFFILE-OPEN
    private void xreffileOpen(Run run) {
        String status = cobolFiles.open(XREFFILE);
        int applResult = CobolCompare.eq(status, "00") ? 0 : 12;
        if (applResult == 0) {
            run.cursor = readAllXreffileFile().iterator();
        } else {
            Sysout.display("ERROR OPENING XREFFILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    // 9000-XREFFILE-CLOSE
    private void xreffileClose() {
        String status = cobolFiles.close(XREFFILE);
        int applResult = CobolCompare.eq(status, "00") ? 0 : 12;
        if (applResult != 0) {
            Sysout.display("ERROR CLOSING XREFFILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    // 9999-ABEND-PROGRAM
    private void abendProgram() {
        Sysout.display("ABENDING PROGRAM");
        // MOVE 0 TO TIMING; MOVE 999 TO ABCODE; CALL 'CEE3ABD' USING ABCODE, TIMING
        throw CobolAbend.user(999, "CBACT03C file error");
    }

    // 9910-DISPLAY-IO-STATUS
    private void displayIoStatus(String status) {
        String s = (status == null ? "" : status) + "  ";
        char stat1 = s.charAt(0);
        char stat2 = s.charAt(1);
        boolean numeric = stat1 >= '0' && stat1 <= '9' && stat2 >= '0' && stat2 <= '9';
        if (!numeric || stat1 == '9') {
            // TWO-BYTES-RIGHT receives IO-STAT2, so the binary item holds that byte's value
            int binary = String.valueOf(stat2).getBytes(CobolRecords.charset())[0] & 0xFF;
            Sysout.display("FILE STATUS IS: NNNN", stat1,
                    Sysout.number(BigDecimal.valueOf(binary), 3, 0, false));
        } else {
            Sysout.display("FILE STATUS IS: NNNN", "00" + stat1 + stat2);
        }
    }

}
