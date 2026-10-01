package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class Cbcus01cService {

    private static final Logger log = LoggerFactory.getLogger(Cbcus01cService.class);

    private static final String DD = "CUSTFILE";

    private final CustomerRecordRepository customerRecordRepository;
    private final CobolFiles cobolFiles;

    public void executeCbcus01c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CBCUS01C");
        runBatch(List.of(), null);
    }

    /** AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS as BATCH SELECT CUSTFILE-FILE at app/cbl/CBCUS01C.cbl (SELECT CUSTFILE-FILE); VSAM defines field testing: open (3 public / 0 private estates). */
    // The program's FD-CUSTFILE-REC (500 bytes) is read INTO CUSTOMER-RECORD (500 bytes): the entity codec
    // (fromRecord / toRecord) maps one onto the other; FILLER is not kept and displays as spaces.
    // Sequential READ: in key order (CUST-ID, #3945).
    public List<CustomerRecord> readAllCustfileFile() {
        return customerRecordRepository.findAll(org.springframework.data.domain.Sort.by("custId"));
    }

    /** Working storage of the program that the paragraphs share. */
    private static final class State {
        String endOfFile = "N";            // END-OF-FILE
        CustomerRecord customer = null;    // CUSTOMER-RECORD (READ INTO copy)
        Iterator<CustomerRecord> cursor;   // the file's position
    }

    /** The batch entry (#3622): run by job READCUST step STEP05 (app/jcl/READCUST.jcl:21).
     *  `dds` are the step's DD statements (DatasetResolver maps each to its file); `parm` the
     *  text its EXEC PARM= passes (null without one) -- a PROCEDURE DIVISION USING area's data.
     *  DD CUSTFILE (INPUT) -> AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS.
     *  JCL job flow field testing: open (5 public / 0 private estates). */
    public int runBatch(List<Dd> dds, String parm) {
        State s = new State();
        // PROCEDURE DIVISION main line
        Sysout.display("START OF EXECUTION OF PROGRAM CBCUS01C");
        custfileOpen(s);                                   // PERFORM 0000-CUSTFILE-OPEN

        while (!"Y".equals(s.endOfFile)) {                 // PERFORM UNTIL END-OF-FILE = 'Y'
            if ("N".equals(s.endOfFile)) {
                custfileGetNext(s);                        // PERFORM 1000-CUSTFILE-GET-NEXT
                if ("N".equals(s.endOfFile)) {
                    // Defect kept: the record was already DISPLAYed in 1000-CUSTFILE-GET-NEXT, so every
                    // record prints twice. Fix: drop this DISPLAY (or the one in the paragraph).
                    Sysout.display(customerText(s));
                }
            }
            // Defect kept: if END-OF-FILE were ever neither 'N' nor 'Y' the loop would spin; unreachable.
        }

        custfileClose();                                   // PERFORM 9000-CUSTFILE-CLOSE
        Sysout.display("END OF EXECUTION OF PROGRAM CBCUS01C");
        return 0;                                          // GOBACK, RETURN-CODE untouched
    }

    /** 1000-CUSTFILE-GET-NEXT */
    private void custfileGetNext(State s) {
        CobolFiles.Read<CustomerRecord> read = cobolFiles.readNext(DD, s.cursor);
        String status = read.status();                     // CUSTFILE-STATUS
        int applResult;                                    // APPL-RESULT
        if ("00".equals(status)) {
            // READ ... INTO: the program's own copy of the record
            s.customer = CustomerRecord.fromRecord(read.record().toRecord(CobolRecords.charset()), CobolRecords.charset());
            applResult = 0;
            Sysout.display(customerText(s));
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
            Sysout.display("ERROR READING CUSTOMER FILE");
            displayIoStatus(status);                       // MOVE CUSTFILE-STATUS TO IO-STATUS; PERFORM Z-DISPLAY-IO-STATUS
            abendProgram();                                // PERFORM Z-ABEND-PROGRAM
        }
    }

    /** 0000-CUSTFILE-OPEN */
    private void custfileOpen(State s) {
        String status = cobolFiles.open(DD);
        if ("00".equals(status)) {
            s.cursor = readAllCustfileFile().iterator();
        } else {
            Sysout.display("ERROR OPENING CUSTFILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    /** 9000-CUSTFILE-CLOSE */
    private void custfileClose() {
        String status = cobolFiles.close(DD);
        if (!"00".equals(status)) {
            Sysout.display("ERROR CLOSING CUSTOMER FILE");
            displayIoStatus(status);
            abendProgram();
        }
    }

    /** Z-ABEND-PROGRAM: CALL 'CEE3ABD' USING ABCODE (999), TIMING (0). */
    private void abendProgram() {
        Sysout.display("ABENDING PROGRAM");
        throw CobolAbend.user(999, "CBCUS01C file error");
    }

    /** Z-DISPLAY-IO-STATUS */
    private void displayIoStatus(String status) {
        String io = (status == null ? "" : status) + "  ";
        char stat1 = io.charAt(0);                         // IO-STAT1
        char stat2 = io.charAt(1);                         // IO-STAT2
        boolean numeric = stat1 >= '0' && stat1 <= '9' && stat2 >= '0' && stat2 <= '9';
        if (!numeric || stat1 == '9') {
            // TWO-BYTES-BINARY = 0 with the right byte set to IO-STAT2: its binary value is that byte
            Charset cs = CobolRecords.charset();
            int right = String.valueOf(stat2).getBytes(cs)[0] & 0xFF;
            Sysout.display("FILE STATUS IS: NNNN" + stat1 + Sysout.number(BigDecimal.valueOf(right), 3, 0, false));
        } else {
            Sysout.display("FILE STATUS IS: NNNN" + "00" + stat1 + stat2);
        }
    }

    /** DISPLAY CUSTOMER-RECORD: the group's 500 bytes (zoned digits as stored, FILLER spaces). */
    private String customerText(State s) {
        Charset cs = CobolRecords.charset();
        CustomerRecord c = s.customer;
        return new String(c.toRecord(cs), cs);
    }

}
