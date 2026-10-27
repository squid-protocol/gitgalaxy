package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.LgstsqDfhcommarea;
import com.gitgalaxy.modernized.dto.contract.Lgupvs01Dfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.WfPolicyInfo;
import com.gitgalaxy.modernized.entity.vsam.WfPolicyInfoKey;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.vsam.WfPolicyInfoRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 139 tests NORMAL
 * REWRITE at line 155 tests NORMAL
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Lgupvs01Service {

    private static final Logger log = LoggerFactory.getLogger(Lgupvs01Service.class);

    private final ObjectProvider<LgstsqService> lgstsqService;
    private final WfPolicyInfoRepository wfPolicyInfoRepository;

    // DFHCOMMAREA (lgcmarea.cpy) offsets: CA-REQUEST-ID 0, CA-CUSTOMER-NUM 8, CA-POLICY-NUM 18,
    // CA-POLICY-SPECIFIC 100 (the commercial / endowment / house / motor redefinitions start there)
    private static final int CA_LEN = 32500;
    private static final int CA_CUSTOMER_NUM = 8;
    private static final int CA_POLICY_NUM = 18;
    private static final int SPEC = 100;

    /** LGUPVS01: update a policy record in KSDSPOLY from the COMMAREA. */
    public void runTask(CicsTask task) {
        Charset cs = CobolRecords.charset();

        // No DFHCOMMAREA addressability: the original reads storage it was not given (ASRA).
        if (!task.hasCommarea()) {
            task.abend("ASRA");
            return;
        }
        Lgupvs01Dfhcommarea ca = task.commarea(Lgupvs01Dfhcommarea.class);

        // MAINLINE: Move EIBCALEN To WS-Commarea-Len (only used as the READ's LENGTH; not modelled by the task)
        byte[] rec = ca.toCommarea();

        // MAINLINE: Move CA-Request-ID(4:1) To WF-Request-ID, CA-Policy-Num / CA-Customer-Num to the key
        String requestId = CobolRecords.text(rec, 3, 1, cs);
        String policyNum = CobolRecords.text(rec, CA_POLICY_NUM, 10, cs);
        String customerNum = CobolRecords.text(rec, CA_CUSTOMER_NUM, 10, cs);

        // MAINLINE: Evaluate WF-Request-ID ... (WF-Policy-Data is fully covered by each arm)
        String policyData;
        if (CobolCompare.eq(requestId, "C")) {
            policyData = CobolRecords.text(rec, SPEC + 255, 8, cs)           // CA-B-Postcode -> WF-B-Postcode
                    + CobolRecords.text(rec, SPEC + 843, 4, cs)              // CA-B-Status -> WF-B-Status
                    + CobolRecords.text(rec, SPEC + 285, 31, cs);            // CA-B-Customer -> WF-B-Customer (31)
        } else if (CobolCompare.eq(requestId, "E")) {
            policyData = CobolRecords.text(rec, SPEC, 1, cs)                 // WITH-PROFITS
                    + CobolRecords.text(rec, SPEC + 1, 1, cs)                // EQUITIES
                    + CobolRecords.text(rec, SPEC + 2, 1, cs)                // MANAGED-FUND
                    + CobolRecords.text(rec, SPEC + 3, 10, cs)               // FUND-NAME
                    + CobolRecords.text(rec, SPEC + 21, 30, cs);             // LIFE-ASSURED (31 -> 30)
        } else if (CobolCompare.eq(requestId, "H")) {
            policyData = CobolRecords.text(rec, SPEC, 15, cs)                // PROPERTY-TYPE
                    + CobolRecords.text(rec, SPEC + 15, 3, cs)               // BEDROOMS
                    + CobolRecords.text(rec, SPEC + 18, 8, cs)               // VALUE
                    + CobolRecords.text(rec, SPEC + 50, 8, cs)               // POSTCODE
                    + CobolRecords.text(rec, SPEC + 26, 9, cs);              // HOUSE-NAME (20 -> 9)
        } else if (CobolCompare.eq(requestId, "M")) {
            policyData = CobolRecords.text(rec, SPEC, 15, cs)                // MAKE
                    + CobolRecords.text(rec, SPEC + 15, 15, cs)              // MODEL
                    + CobolRecords.text(rec, SPEC + 30, 6, cs)               // VALUE
                    + CobolRecords.text(rec, SPEC + 36, 7, cs);              // REGNUMBER
        } else {
            policyData = CobolRecords.fit("", 43, cs);                       // When Other: Move Spaces
        }

        WfPolicyInfoKey key = new WfPolicyInfoKey();
        key.setWfRequestId(requestId);
        key.setWfCustomerNum(customerNum);
        key.setWfPolicyNum(policyNum);

        // MAINLINE: Exec CICS Read File('KSDSPOLY') Update (INTO WS-FileIn is never used afterwards)
        CicsTask.FileRead<WfPolicyInfo> read = task.readForUpdate("KSDSPOLY", () -> readKsdspoly(key));
        if (read.resp() != 0) {
            int resp2 = read.resp2();                                        // Move EIBRESP2 To WS-RESP2
            ca.setCaReturnCode(81);                                          // MOVE '81' TO CA-RETURN-CODE
            writeErrorMessage(task, ca, read.resp(), resp2, cs);             // PERFORM WRITE-ERROR-MESSAGE
            task.abend("LGV3");                                              // EXEC CICS ABEND ABCODE('LGV3')
            return;                                                          // (EXEC CICS RETURN: unreachable)
        }

        // MAINLINE: Exec CICS ReWrite File('KSDSPOLY') From(WF-Policy-Info) Length(64)
        String recText = requestId + customerNum + policyNum + policyData;
        WfPolicyInfo updated = WfPolicyInfo.fromRecord(recText.getBytes(cs), cs);
        int resp = task.rewrite("KSDSPOLY", () -> rewriteKsdspoly(updated));
        if (resp != 0) {
            int resp2 = task.resp2();                                        // Move EIBRESP2 To WS-RESP2
            ca.setCaReturnCode(82);                                          // MOVE '82' TO CA-RETURN-CODE
            writeErrorMessage(task, ca, resp, resp2, cs);                    // PERFORM WRITE-ERROR-MESSAGE
            task.abend("LGV4");                                              // EXEC CICS ABEND ABCODE('LGV4')
            return;
        }

        // A-EXIT: GOBACK
        task.returnTransid(null, null);
    }

    /** WRITE-ERROR-MESSAGE paragraph. */
    private void writeErrorMessage(CicsTask task, Lgupvs01Dfhcommarea ca, int resp, int resp2, Charset cs) {
        // EXEC CICS ASKTIME / FORMATTIME MMDDYYYY(WS-DATE) TIME(WS-TIME)
        // WS-ABSTIME is PIC S9(8) COMP, so only the low 8 digits are kept
        long abstime = task.asktime() % 100_000_000L;
        String date = CicsTask.formatDate(abstime, "MMDDYYYY", "");   // 8 chars; EM-DATE is X(8)
        String time = CicsTask.formatTime(abstime, "");               // 6 chars; EM-TIME is X(6)

        byte[] rec = ca.toCommarea();
        String cusnum = CobolRecords.text(rec, CA_CUSTOMER_NUM, 10, cs);   // Move CA-Customer-Num To EM-Cusnum
        // EM-RESPRC / EM-RESP2RC are PIC +9(5)
        String respEdit = CobolEdit.format("+9(5)", BigDecimal.valueOf(resp), false, null);
        String resp2Edit = CobolEdit.format("+9(5)", BigDecimal.valueOf(resp2), false, null);

        // ERROR-MSG (101 bytes). EM-POLNUM is never moved to: it stays spaces (original defect, see notes).
        String errorMsg = date + " " + time + " LGUPVS01"
                + " PNUM=" + CobolRecords.fit("", 10, cs)
                + " CNUM=" + cusnum
                + " Re-write  KSDSPOLY "
                + " RESP=" + respEdit
                + " RESP2=" + resp2Edit;

        // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(ERROR-MSG) LENGTH(LENGTH OF ERROR-MSG)
        byte[] area = errorMsg.getBytes(cs);
        linkLgstsqArea(task, area, cs);
        if (task.ended()) {
            return;
        }

        // IF EIBCALEN > 0
        Integer calen = task.eibcalen();
        int len = calen == null ? CA_LEN : calen;
        if (len > 0) {
            byte[] now = ca.toCommarea();
            String caData;
            if (len < 91) {
                // MOVE DFHCOMMAREA(1:EIBCALEN) TO CA-DATA (padded with spaces)
                caData = CobolRecords.fit(CobolRecords.text(now, 0, Math.min(len, now.length), cs), 90, cs);
            } else {
                // MOVE DFHCOMMAREA(1:90) TO CA-DATA
                caData = CobolRecords.text(now, 0, 90, cs);
            }
            // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(CA-ERROR-MSG) LENGTH(LENGTH OF CA-ERROR-MSG)
            linkLgstsqArea(task, ("COMMAREA=" + caData).getBytes(cs), cs);
        }
    }

    /** One LINK to LGSTSQ with the caller's bytes (passed by address); LGSTSQ's COMMA-DATA is their first 90 bytes. */
    private void linkLgstsqArea(CicsTask task, byte[] area, Charset cs) {
        LgstsqDfhcommarea dto = new LgstsqDfhcommarea();
        dto.setCaData(CobolRecords.text(area, 0, Math.min(90, area.length), cs));
        task.link("LGSTSQ", dto, area.length, area);
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Lgupvs01Dfhcommarea handleLink(Lgupvs01Dfhcommarea request) {
        log.info("Lgupvs01: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGUPVS01", request);
        region.run(task, "LGUPVS01", this::runTask);
        return request;
    }

    /** #5053: handleLink with the raw bytes of the LINK's COMMAREA (passed by address: what the program
     *  leaves there the caller sees); lastLinkBytes() then answers the bytes it left. */
    public Lgupvs01Dfhcommarea handleLink(Lgupvs01Dfhcommarea request, byte[] area) {
        log.info("Lgupvs01: handleLink (bytes)");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGUPVS01", request, area);
        region.run(task, "LGUPVS01", this::runTask);
        byte[] left = task.linkAreaView();
        lastLinkBytes = task.linkAreaTaken() && left != null ? java.util.Arrays.copyOf(left, left.length) : null;
        return request;
    }

    // @facade-helper: the bytes the last byte-carrying handleLink's program left in the COMMAREA
    private byte[] lastLinkBytes;

    /** The bytes the last byte-carrying handleLink's program left in the LINK COMMAREA (a copy; null: it took
     *  none -- its DTO is the COMMAREA). @facade-helper */
    public byte[] lastLinkBytes() {
        return lastLinkBytes == null ? null : java.util.Arrays.copyOf(lastLinkBytes, lastLinkBytes.length);
    }

    /** EXEC CICS LINK PROGRAM(LGSTSQ) at base/src/lgupvs01.cbl:187, base/src/lgupvs01.cbl:194, base/src/lgupvs01.cbl:200.
     *  Call targets field testing: open (8 public / 0 private estates). */
    // TODO: this site passes ERROR-MSG; LGSTSQ receives CA-ERROR-MSG (base/src/lgacdb01.cbl) -- map one layout onto the other
    public LgstsqDfhcommarea linkLgstsq(LgstsqDfhcommarea request) {
        return lgstsqService.getObject().handleLink(request);
    }

    /** <USRHLQ>.GENAPP.KSDSPOLY as CICS file KSDSPOLY at base/src/lgupvs01.cbl:139, 155; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<WfPolicyInfo> readKsdspoly(WfPolicyInfoKey key) {
        return wfPolicyInfoRepository.findById(key);
    }

    public WfPolicyInfo rewriteKsdspoly(WfPolicyInfo record) {
        return wfPolicyInfoRepository.save(record);
    }

    /**
     * EXEC CICS ABEND ABCODE(LGV3) at base/src/lgupvs01.cbl:151 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgv3L151() {
        throw new CicsAbendException("LGV3", "LGUPVS01", "base/src/lgupvs01.cbl:151");
    }

    /**
     * EXEC CICS ABEND ABCODE(LGV4) at base/src/lgupvs01.cbl:164 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLgv4L164() {
        throw new CicsAbendException("LGV4", "LGUPVS01", "base/src/lgupvs01.cbl:164");
    }

}
