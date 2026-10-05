package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.LgstsqDfhcommarea;
import com.gitgalaxy.modernized.dto.contract.Lgapvs01Dfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.WfPolicyInfo;
import com.gitgalaxy.modernized.entity.vsam.WfPolicyInfoKey;
import com.gitgalaxy.modernized.repository.vsam.WfPolicyInfoRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.util.Locale;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * WRITE at line 135 tests NORMAL
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Lgapvs01Service {

    private static final Logger log = LoggerFactory.getLogger(Lgapvs01Service.class);

    /** Offset of CA-POLICY-SPECIFIC inside CA-REQUEST-SPECIFIC (CA-POLICY-NUM 10 + CA-POLICY-COMMON 72). */
    private static final int SPEC = 82;

    private final ObjectProvider<LgstsqService> lgstsqService;
    private final WfPolicyInfoRepository wfPolicyInfoRepository;

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none). */
    public Lgapvs01Dfhcommarea handleTransaction(String transid, Lgapvs01Dfhcommarea request) {
        log.info("Lgapvs01: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "LGAPVS01", this::runTask);
        return task.returned(Lgapvs01Dfhcommarea.class);
    }

    /** One task of LGAPVS01 (VSAM KSDS policy record ADD). */
    public void runTask(CicsTask task) {
        log.info("Lgapvs01: runTask");
        if (!task.hasCommarea()) {
            // No DFHCOMMAREA: the original addresses storage that is not there (ASRA).
            task.abend("ASRA");
            return;
        }
        Lgapvs01Dfhcommarea ca = task.commarea(Lgapvs01Dfhcommarea.class);

        // MAINLINE: Move EIBCALEN To WS-Commarea-Len (never used afterwards)
        String spec = ca.getCaRequestSpecific() == null ? "" : ca.getCaRequestSpecific();

        // MAINLINE: Move CA-Request-ID(4:1) To WF-Request-ID
        String wfRequestId = fit(ca.getCaRequestId(), 3, 1);
        // MAINLINE: Move CA-Policy-Num To WF-Policy-Num (PIC 9(10) to X(10): the digits as held)
        String wfPolicyNum = fit(spec, 0, 10);
        // MAINLINE: Move CA-Customer-Num To WF-Customer-Num
        String wfCustomerNum = digits(ca.getCaCustomerNum(), 10);

        // MAINLINE: Evaluate WF-Request-ID (every redefinition of WF-Policy-Data covers all 43 bytes)
        String data;
        if (CobolCompare.eq(wfRequestId, "C")) {
            data = fit(spec, SPEC + 255, 8)        // CA-B-Postcode -> WF-B-Postcode
                    + fit(spec, SPEC + 843, 4)     // CA-B-Status -> WF-B-Status
                    + fit(spec, SPEC + 285, 31);   // CA-B-Customer -> WF-B-Customer (truncated)
        } else if (CobolCompare.eq(wfRequestId, "E")) {
            data = fit(spec, SPEC, 1)              // CA-E-WITH-PROFITS
                    + fit(spec, SPEC + 1, 1)       // CA-E-EQUITIES
                    + fit(spec, SPEC + 2, 1)       // CA-E-MANAGED-FUND
                    + fit(spec, SPEC + 3, 10)      // CA-E-FUND-NAME
                    + fit(spec, SPEC + 21, 30);    // CA-E-LIFE-ASSURED (X(31) -> X(30), truncated)
        } else if (CobolCompare.eq(wfRequestId, "H")) {
            data = fit(spec, SPEC, 15)             // CA-H-PROPERTY-TYPE
                    + fit(spec, SPEC + 15, 3)      // CA-H-BEDROOMS
                    + fit(spec, SPEC + 18, 8)      // CA-H-VALUE
                    + fit(spec, SPEC + 50, 8)      // CA-H-POSTCODE -> WF-H-POSTCODE
                    + fit(spec, SPEC + 26, 9);     // CA-H-HOUSE-NAME X(20) -> X(9), truncated
        } else if (CobolCompare.eq(wfRequestId, "M")) {
            data = fit(spec, SPEC, 15)             // CA-M-MAKE
                    + fit(spec, SPEC + 15, 15)     // CA-M-MODEL
                    + fit(spec, SPEC + 30, 6)      // CA-M-VALUE
                    + fit(spec, SPEC + 36, 7);     // CA-M-REGNUMBER
        } else {
            data = " ".repeat(43);                 // When Other: Move Spaces To WF-Policy-Data
        }

        // MAINLINE: Exec CICS Write File('KSDSPOLY') From(WF-Policy-Info) Ridfld(WF-Policy-Key) RESP(WS-RESP)
        WfPolicyInfoKey key = new WfPolicyInfoKey();
        key.setWfRequestId(wfRequestId);
        key.setWfCustomerNum(wfCustomerNum);
        key.setWfPolicyNum(wfPolicyNum);
        WfPolicyInfo rec = new WfPolicyInfo();
        rec.setId(key);
        rec.setWfPolicyData(data);
        int wsResp = task.write("KSDSPOLY", wfPolicyInfoRepository.existsById(key),
                () -> wfPolicyInfoRepository.save(rec));

        // MAINLINE: If WS-RESP Not = DFHRESP(NORMAL)
        if (wsResp != 0) {
            // Move EIBRESP2 To WS-RESP2: CicsTask.write exposes only RESP, so RESP2 is taken as 0.
            int wsResp2 = 0;
            ca.setCaReturnCode(80);                 // MOVE '80' TO CA-RETURN-CODE
            writeErrorMessage(task, ca, wsResp, wsResp2);   // PERFORM WRITE-ERROR-MESSAGE
            task.returnTransid(null, null);         // EXEC CICS RETURN END-EXEC
            return;
        }

        // A-EXIT: EXIT. GOBACK (a RETURN)
        task.returnTransid(null, null);
    }

    /** WRITE-ERROR-MESSAGE paragraph. */
    private void writeErrorMessage(CicsTask task, Lgapvs01Dfhcommarea ca, int wsResp, int wsResp2) {
        // EXEC CICS ASKTIME ABSTIME(WS-ABSTIME)
        long abstime = task.asktime();
        // EXEC CICS FORMATTIME ABSTIME MMDDYYYY(WS-DATE) TIME(WS-TIME): no DATESEP / TIMESEP
        String wsDate = CicsTask.formatDate(abstime, "MMDDYYYY", "");
        String wsTime = CicsTask.formatTime(abstime, "");

        String spec = ca.getCaRequestSpecific() == null ? "" : ca.getCaRequestSpecific();
        // MOVE WS-DATE TO EM-DATE / WS-TIME TO EM-TIME (truncated on the right)
        String emDate = fit(wsDate, 0, 8);
        String emTime = fit(wsTime, 0, 6);
        String emCusnum = digits(ca.getCaCustomerNum(), 10);   // Move CA-Customer-Num To EM-Cusnum
        String emPolnum = fit(spec, 0, 10);                     // Move CA-Policy-Num To EM-POLNUM
        // Move WS-RESP To EM-RespRC (PIC +9(5))
        String emResp = CobolEdit.format("+9(5)", BigDecimal.valueOf(wsResp), false, null);
        String emResp2 = CobolEdit.format("+9(5)", BigDecimal.valueOf(wsResp2), false, null);

        String errorMsg = emDate + " " + emTime + " LGAPVS01"
                + " PNUM=" + emPolnum
                + " CNUM=" + emCusnum
                + " Write file KSDSPOLY"
                + " RESP=" + emResp
                + " RESP2=" + emResp2;   // 101 bytes

        // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(ERROR-MSG) LENGTH(LENGTH OF ERROR-MSG)
        // TODO: layout mismatch kept from the source: LGSTSQ's commarea is CA-ERROR-MSG (90 data bytes);
        // the first 90 bytes of ERROR-MSG are mapped onto caData.
        LgstsqDfhcommarea first = new LgstsqDfhcommarea();
        first.setCaData(fit(errorMsg, 0, 90));
        task.link("LGSTSQ", first, 101);

        // IF EIBCALEN > 0
        Integer eibcalen = task.eibcalen();
        int len = eibcalen == null ? 32500 : eibcalen;
        if (len > 0) {
            String whole = commareaText(ca);
            LgstsqDfhcommarea msg = new LgstsqDfhcommarea();
            if (len < 91) {
                // MOVE DFHCOMMAREA(1:EIBCALEN) TO CA-DATA (space padded)
                msg.setCaData(fit(whole, 0, len) + " ".repeat(90 - len));
            } else {
                // MOVE DFHCOMMAREA(1:90) TO CA-DATA
                msg.setCaData(fit(whole, 0, 90));
            }
            // EXEC CICS LINK PROGRAM('LGSTSQ') COMMAREA(CA-ERROR-MSG) LENGTH(LENGTH OF CA-ERROR-MSG)
            task.link("LGSTSQ", msg, 99);
        }
    }

    /** DFHCOMMAREA as its bytes read: CA-REQUEST-ID, CA-RETURN-CODE, CA-CUSTOMER-NUM, CA-REQUEST-SPECIFIC. */
    private static String commareaText(Lgapvs01Dfhcommarea ca) {
        int rc = ca.getCaReturnCode() == null ? 0 : ca.getCaReturnCode();
        return fit(ca.getCaRequestId(), 0, 6)
                + String.format(Locale.ROOT, "%02d", Math.floorMod(rc, 100))
                + digits(ca.getCaCustomerNum(), 10)
                + fit(ca.getCaRequestSpecific(), 0, 32482);
    }

    /** `len` characters of `s` from `off`, space padded (MOVE to / from PIC X). */
    private static String fit(String s, int off, int len) {
        String v = s == null ? "" : s;
        StringBuilder out = new StringBuilder(len);
        for (int i = 0; i < len; i++) {
            int p = off + i;
            out.append(p < v.length() ? v.charAt(p) : ' ');
        }
        return out.toString();
    }

    /** A PIC 9(n) value as its n zoned digits (high-order digits lost, as COBOL stores it). */
    private static String digits(Long value, int n) {
        long v = value == null ? 0L : Math.abs(value);
        String s = Long.toString(v);
        return s.length() > n ? s.substring(s.length() - n) : "0".repeat(n - s.length()) + s;
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Lgapvs01Dfhcommarea handleLink(Lgapvs01Dfhcommarea request) {
        log.info("Lgapvs01: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGAPVS01", request);
        region.run(task, "LGAPVS01", this::runTask);
        return request;
    }

    /** EXEC CICS LINK PROGRAM(LGSTSQ) at base/src/lgapvs01.cbl:169, base/src/lgapvs01.cbl:176, base/src/lgapvs01.cbl:182.
     *  Call targets field testing: open (6 public / 0 private estates). */
    // TODO: this site passes ERROR-MSG; LGSTSQ receives CA-ERROR-MSG (base/src/lgacdb01.cbl) -- map one layout onto the other
    public LgstsqDfhcommarea linkLgstsq(LgstsqDfhcommarea request) {
        return lgstsqService.getObject().handleLink(request);
    }

    /** <USRHLQ>.GENAPP.KSDSPOLY as CICS file KSDSPOLY at base/src/lgapvs01.cbl:135; VSAM defines field testing: open (3 public / 0 private estates). */
    public WfPolicyInfo writeKsdspoly(WfPolicyInfo record) {
        // CICS WRITE adds a record: DUPREC when its key is already on file
        Optional<WfPolicyInfo> onFile = wfPolicyInfoRepository.findById(record.getId());
        if (onFile.isPresent()) {
            throw new org.springframework.dao.DuplicateKeyException(
                "DUPREC: CICS file KSDSPOLY already holds the key of this record");
        }
        return wfPolicyInfoRepository.save(record);
    }
}
