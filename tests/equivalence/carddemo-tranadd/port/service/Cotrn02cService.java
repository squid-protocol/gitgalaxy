package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.call.CobolRef;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.Cotrn02cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cotrn2aScreen;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 578 tests NORMAL,NOTFND
 * READ at line 611 tests NORMAL,NOTFND
 * STARTBR at line 644 tests NORMAL,NOTFND
 * READPREV at line 675 tests ENDFILE,NORMAL
 * WRITE at line 713 tests DUPKEY,DUPREC,NORMAL
 * TODO: the RESP of RECEIVE at line 541 (paragraph RECEIVE-TRNADD-SCREEN) is never tested
 * Screens (#3619): Cotrn2aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cotrn02cService {

    private static final Logger log = LoggerFactory.getLogger(Cotrn02cService.class);

    private static final String WS_TRANID = "CT02";
    private static final String WS_PGMNAME = "COTRN02C";
    private static final String HIGH_16 = "\u00ff".repeat(16);   // HIGH-VALUES as CicsTask reads them (record charset)

    private final ObjectProvider<CsutldtcService> csutldtcService;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final TranRecordRepository tranRecordRepository;

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none).
     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its
     *  own record, so a port may pass either record -- the facade carries it as Object where a flow
     *  presents another class, and runTask reads it (task.commarea(..)). The flows:
     *  out: RETURN TRANSID(CPVS) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:254 -> app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Copaus0cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CPVD) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:202 -> a program the estate does not resolve, after an XCTL from app/cbl/COTRN02C.cbl (Copaus1cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CTLI) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTLIC.cbl:910 -> app/app-transaction-type-db2/cbl/COTRTLIC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CotrtlicCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CTTU) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTUPC.cbl:567 -> app/app-transaction-type-db2/cbl/COTRTUPC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CotrtupcCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CAUP) COMMAREA(WS-COMMAREA) at app/cbl/COACTUPC.cbl:1015 -> app/cbl/COACTUPC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CoactupcCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CAVW) COMMAREA(WS-COMMAREA) at app/cbl/COACTVWC.cbl:402 -> app/cbl/COACTVWC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CoactvwcCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CA00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COADM01C.cbl:111 -> app/cbl/COADM01C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CA00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COADM01C.cbl:280 -> app/cbl/COADM01C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CB00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COBIL00C.cbl:146 -> app/cbl/COBIL00C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cobil00cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CCLI) COMMAREA(WS-COMMAREA) at app/cbl/COCRDLIC.cbl:615 -> app/cbl/COCRDLIC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CocrdlicCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CCDL) COMMAREA(WS-COMMAREA) at app/cbl/COCRDSLC.cbl:402 -> app/cbl/COCRDSLC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CocrdslcCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CCUP) COMMAREA(WS-COMMAREA) at app/cbl/COCRDUPC.cbl:554 -> app/cbl/COCRDUPC.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CocrdupcCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CM00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COMEN01C.cbl:107 -> app/cbl/COMEN01C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CR00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/CORPT00C.cbl:199 -> app/cbl/CORPT00C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CR00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/CORPT00C.cbl:587 -> app/cbl/CORPT00C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CC00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COSGN00C.cbl:98 -> a program the estate does not resolve, after an XCTL from app/cbl/COTRN02C.cbl (no DTO besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CT00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN00C.cbl:138 -> app/cbl/COTRN00C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cotrn00cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CT01) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN01C.cbl:136 -> app/cbl/COTRN01C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cotrn01cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CU00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR00C.cbl:141 -> app/cbl/COUSR00C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cousr00cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CU01) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR01C.cbl:107 -> app/cbl/COUSR01C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (CarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CU02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR02C.cbl:135 -> app/cbl/COUSR02C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cousr02cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     *  out: RETURN TRANSID(CU03) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR03C.cbl:134 -> app/cbl/COUSR03C.cbl, after an XCTL from app/cbl/COTRN02C.cbl (Cousr03cCarddemoCommarea besides Cotrn02cCarddemoCommarea).
     */
    public Object handleTransaction(String transid, Cotrn02cCarddemoCommarea request) {
        log.info("Cotrn02c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COTRN02C", this::runTask);
        return task.returned(Object.class);
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it reaches. */
    public void runTask(CicsTask task) {
        log.info("Cotrn02c: runTask");
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Cotrn02cCarddemoCommarea handleLink(Cotrn02cCarddemoCommarea request) {
        log.info("Cotrn02c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COTRN02C", request);
        region.run(task, "COTRN02C", this::runTask);
        return request;
    }

    /** CALL 'CSUTLDTC' at app/cbl/COTRN02C.cbl:393, app/cbl/COTRN02C.cbl:413; the parameters are Csutldtc's USING items.
     *  Call targets open (6 public / 0 private estates); CALL USING open (5 public / 0 private estates). */
    public int callCsutldtc(CobolRef<String> lsDate, CobolRef<String> lsDateFormat, CobolRef<String> lsResult) {
        return csutldtcService.getObject().handleCall(lsDate, lsDateFormat, lsResult);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN02C.cbl:508, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves)).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically.
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL508(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as CICS file CCXREF at app/cbl/COTRN02C.cbl:611; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<CardXrefRecord> readCcxref(String key) {
        return cardXrefRecordRepository.findById(key);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as CICS file CXACAIX at app/cbl/COTRN02C.cbl:578; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardXrefRecord> readCxacaix(Long xrefAcctId) {
        return cardXrefRecordRepository.findByXrefAcctId(xrefAcctId);
    }

    /** AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS as CICS file TRANSACT at app/cbl/COTRN02C.cbl:644, 675, 704, 713; VSAM defines field testing: open (3 public / 0 private estates). */
    public TranRecord writeTransact(TranRecord record) {
        return tranRecordRepository.save(record);
    }

    public List<TranRecord> browseTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortGreaterThanEqualOrderByTranIdSortAsc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    public List<TranRecord> browseBackTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortLessThanEqualOrderByTranIdSortDesc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    // ------------------------------------------------------------------ helpers

    private static String sp(int n) {
        return " ".repeat(n);
    }

    private static String nul(int n) {
        return "\u0000".repeat(n);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String pad(String s, int n) {
        String v = s == null ? "" : s;
        return v.length() >= n ? v.substring(0, n) : v + sp(n - v.length());
    }

    private static boolean allOf(String s, char c) {
        if (s == null || s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != c) {
                return false;
            }
        }
        return true;
    }

    /** = SPACES OR LOW-VALUES */
    private static boolean blankOrLow(String s) {
        return allOf(s, ' ') || allOf(s, '\u0000');
    }

    /** IS NUMERIC on an alphanumeric item: every character a digit 0-9. */
    private static boolean numeric(String s) {
        if (s == null || s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    /** Alphanumeric equality through the code page's bytes (CobolCompare). */
    private static boolean eq(String a, String b) {
        try {
            return CobolCompare.eq(a, b);
        } catch (IllegalArgumentException e) {
            return false;   // a character the code page cannot encode equals no literal
        }
    }

    private static String digits(long v, int n) {
        return String.format(Locale.ROOT, "%0" + n + "d", v);
    }

    private static String edit(BigDecimal v) {
        return CobolEdit.format("+99999999.99", v, false, "$");   // PIC +99999999.99
    }

    private static Cotrn02cCarddemoCommarea copyOf(Cotrn02cCarddemoCommarea s) {
        Cotrn02cCarddemoCommarea c = new Cotrn02cCarddemoCommarea();
        c.setCdemoFromTranid(s.getCdemoFromTranid());
        c.setCdemoFromProgram(s.getCdemoFromProgram());
        c.setCdemoToTranid(s.getCdemoToTranid());
        c.setCdemoToProgram(s.getCdemoToProgram());
        c.setCdemoUserId(s.getCdemoUserId());
        c.setCdemoUserType(s.getCdemoUserType());
        c.setCdemoPgmContext(s.getCdemoPgmContext());
        c.setCdemoCustId(s.getCdemoCustId());
        c.setCdemoCustFname(s.getCdemoCustFname());
        c.setCdemoCustMname(s.getCdemoCustMname());
        c.setCdemoCustLname(s.getCdemoCustLname());
        c.setCdemoAcctId(s.getCdemoAcctId());
        c.setCdemoAcctStatus(s.getCdemoAcctStatus());
        c.setCdemoCardNum(s.getCdemoCardNum());
        c.setCdemoLastMap(s.getCdemoLastMap());
        c.setCdemoLastMapset(s.getCdemoLastMapset());
        c.setCdemoCt02TrnidFirst(s.getCdemoCt02TrnidFirst());
        c.setCdemoCt02TrnidLast(s.getCdemoCt02TrnidLast());
        c.setCdemoCt02PageNum(s.getCdemoCt02PageNum());
        c.setCdemoCt02NextPageFlg(s.getCdemoCt02NextPageFlg());
        c.setCdemoCt02TrnSelFlg(s.getCdemoCt02TrnSelFlg());
        c.setCdemoCt02TrnSelected(s.getCdemoCt02TrnSelected());
        return c;
    }

    /** CARDDEMO-COMMAREA as WORKING-STORAGE holds it before any MOVE (EIBCALEN = 0). */
    private static Cotrn02cCarddemoCommarea initialCommarea() {
        Cotrn02cCarddemoCommarea c = new Cotrn02cCarddemoCommarea();
        c.setCdemoFromTranid(sp(4));
        c.setCdemoFromProgram(sp(8));
        c.setCdemoToTranid(sp(4));
        c.setCdemoToProgram(sp(8));
        c.setCdemoUserId(sp(8));
        c.setCdemoUserType(sp(1));
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoCustFname(sp(25));
        c.setCdemoCustMname(sp(25));
        c.setCdemoCustLname(sp(25));
        c.setCdemoAcctId(0L);
        c.setCdemoAcctStatus(sp(1));
        c.setCdemoCardNum(0L);
        c.setCdemoLastMap(sp(7));
        c.setCdemoLastMapset(sp(7));
        c.setCdemoCt02TrnidFirst(sp(16));
        c.setCdemoCt02TrnidLast(sp(16));
        c.setCdemoCt02PageNum(0);
        c.setCdemoCt02NextPageFlg("N");
        c.setCdemoCt02TrnSelFlg(sp(1));
        c.setCdemoCt02TrnSelected(sp(16));
        return c;
    }

    private static Cotrn2aScreen blankScreen() {
        Cotrn2aScreen s = new Cotrn2aScreen();
        fill(s, true);
        return s;
    }

    /** All fields to spaces (storage initial) or LOW-VALUES (MOVE LOW-VALUES TO COTRN2AO). */
    private static void fill(Cotrn2aScreen s, boolean spaces) {
        java.util.function.IntFunction<String> f = spaces ? Cotrn02cService::sp : Cotrn02cService::nul;
        s.setTrnname(f.apply(4));
        s.setTitle01(f.apply(40));
        s.setCurdate(f.apply(8));
        s.setPgmname(f.apply(8));
        s.setTitle02(f.apply(40));
        s.setCurtime(f.apply(8));
        s.setActidin(f.apply(11));
        s.setCardnin(f.apply(16));
        s.setTtypcd(f.apply(2));
        s.setTcatcd(f.apply(4));
        s.setTrnsrc(f.apply(10));
        s.setTdesc(f.apply(60));
        s.setTrnamt(f.apply(12));
        s.setTorigdt(f.apply(10));
        s.setTprocdt(f.apply(10));
        s.setMid(f.apply(9));
        s.setMname(f.apply(30));
        s.setMcity(f.apply(25));
        s.setMzip(f.apply(10));
        s.setConfirm(f.apply(1));
        s.setErrmsg(f.apply(78));
    }

    /** A received field: nothing transmitted is LOW-VALUES, else the data padded to the field. */
    private static String rcv(String v, int n) {
        return v == null || v.isEmpty() ? nul(n) : pad(v, n);
    }

    private static TranRecord initialTran() {
        TranRecord t = new TranRecord();
        t.setTranId(sp(16));
        t.setTranTypeCd(sp(2));
        t.setTranCatCd(0);
        t.setTranSource(sp(10));
        t.setTranDesc(sp(100));
        t.setTranAmt(BigDecimal.ZERO.setScale(2));
        t.setTranMerchantId(0);
        t.setTranMerchantName(sp(50));
        t.setTranMerchantCity(sp(50));
        t.setTranMerchantZip(sp(10));
        t.setTranCardNum(sp(16));
        t.setTranOrigTs(sp(26));
        t.setTranProcTs(sp(26));
        return t;
    }

    // ------------------------------------------------------------------ the task

    /** One execution of the program: its WORKING-STORAGE and paragraphs. */
    private final class Run {
        private final CicsTask task;
        private final Cotrn2aScreen scr = blankScreen();           // COTRN2AI / COTRN2AO share storage
        private final Set<String> cursors = new LinkedHashSet<>(); // fields whose <f>L holds -1
        private Cotrn02cCarddemoCommarea ca;
        private boolean errFlg;                                    // WS-ERR-FLG
        private String message = sp(80);                           // WS-MESSAGE
        private boolean done;                                      // the task ended at a RETURN
        private boolean errmsgGreen;                               // ERRMSGC = DFHGREEN
        private CardXrefRecord xref = new CardXrefRecord();
        private TranRecord tran = initialTran();
        private BigDecimal wsTranAmtN = BigDecimal.ZERO.setScale(2);
        private String wsTranAmtE = edit(BigDecimal.ZERO);
        private long wsTranIdN;

        Run(CicsTask task) {
            this.task = task;
            xref.setXrefCardNum(sp(16));
            xref.setXrefCustId(0);
            xref.setXrefAcctId(0L);
        }

        /** MAIN-PARA */
        void mainPara() {
            errFlg = false;
            message = sp(80);
            scr.setErrmsg(sp(78));

            if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
                ca = initialCommarea();
                ca.setCdemoToProgram("COSGN00C");
                returnToPrevScreen();
                if (done) {
                    return;
                }
            } else {
                // DEFECT (kept): EIBCALEN shorter than the 218-byte record leaves the rest of the
                // COMMAREA as spaces in COBOL; the DTO is taken as received.
                ca = copyOf(task.commarea(Cotrn02cCarddemoCommarea.class));
                boolean reenter = ca.getCdemoPgmContext() != null && ca.getCdemoPgmContext() == 1;
                if (!reenter) {
                    ca.setCdemoPgmContext(1);
                    fill(scr, false);
                    cursors.add("ACTIDIN");
                    String sel = pad(ca.getCdemoCt02TrnSelected(), 16);
                    if (!blankOrLow(sel)) {
                        scr.setCardnin(sel);
                        processEnterKey();
                        if (done) {
                            return;
                        }
                    }
                    sendTrnaddScreen();
                    return;
                } else {
                    receiveTrnaddScreen();
                    String aid = task.aid();
                    if ("ENTER".equals(aid)) {
                        processEnterKey();
                    } else if ("PF3".equals(aid)) {
                        if (blankOrLow(pad(ca.getCdemoFromProgram(), 8))) {
                            ca.setCdemoToProgram("COMEN01C");
                        } else {
                            ca.setCdemoToProgram(ca.getCdemoFromProgram());
                        }
                        returnToPrevScreen();
                    } else if ("PF4".equals(aid)) {
                        clearCurrentScreen();
                    } else if ("PF5".equals(aid)) {
                        copyLastTranData();
                    } else {
                        errFlg = true;
                        message = "Invalid key pressed. Please see below...";   // CCDA-MSG-INVALID-KEY
                        sendTrnaddScreen();
                    }
                    if (done) {
                        return;
                    }
                }
            }
            // EXEC CICS RETURN TRANSID(WS-TRANID) COMMAREA(CARDDEMO-COMMAREA)
            task.returnTransid(WS_TRANID, ca);
            done = true;
        }

        /** PROCESS-ENTER-KEY */
        private void processEnterKey() {
            validateInputKeyFields();
            if (done) {
                return;
            }
            validateInputDataFields();
            if (done) {
                return;
            }
            String c = scr.getConfirm();
            if ("Y".equals(c) || "y".equals(c)) {
                addTransaction();
            } else if ("N".equals(c) || "n".equals(c) || blankOrLow(c)) {
                fail("Confirm to add this transaction...", "CONFIRM");
            } else {
                fail("Invalid value. Valid values are (Y/N)...", "CONFIRM");
            }
        }

        /** The repeated MOVE 'Y' TO WS-ERR-FLG / MOVE msg / MOVE -1 TO <f>L / PERFORM SEND-TRNADD-SCREEN. */
        private void fail(String msg, String cursorField) {
            errFlg = true;
            message = msg;
            cursors.add(cursorField);
            sendTrnaddScreen();
        }

        /** DISPLAY 'RESP:' WS-RESP-CD 'REAS:' WS-REAS-CD (WHEN OTHER arms). */
        private void displayResp(int resp, int resp2) {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(resp2), 9, 0, true));
        }

        /** VALIDATE-INPUT-KEY-FIELDS */
        private void validateInputKeyFields() {
            String act = scr.getActidin();
            String card = scr.getCardnin();
            if (!blankOrLow(act)) {
                if (!numeric(act)) {
                    fail("Account ID must be Numeric...", "ACTIDIN");
                    return;
                }
                long acctN = CobolRecords.numval(act, '.').abs().longValue() % 100_000_000_000L;
                xref.setXrefAcctId(acctN);
                scr.setActidin(digits(acctN, 11));
                readCxacaixFile();
                if (done) {
                    return;
                }
                scr.setCardnin(pad(xref.getXrefCardNum(), 16));
            } else if (!blankOrLow(card)) {
                if (!numeric(card)) {
                    fail("Card Number must be Numeric...", "CARDNIN");
                    return;
                }
                long cardN = CobolRecords.numval(card, '.').abs().longValue();
                xref.setXrefCardNum(digits(cardN, 16));
                scr.setCardnin(digits(cardN, 16));
                readCcxrefFile();
                if (done) {
                    return;
                }
                scr.setActidin(digits(xref.getXrefAcctId() == null ? 0 : xref.getXrefAcctId(), 11));
            } else {
                fail("Account or Card Number must be entered...", "ACTIDIN");
            }
        }

        /** VALIDATE-INPUT-DATA-FIELDS */
        private void validateInputDataFields() {
            if (errFlg) {
                // DEFECT (kept, unreachable): every error sends the screen and RETURNs, so ERR-FLG is
                // never on here. Fix: none needed; remove the dead block.
                scr.setTtypcd(sp(2));
                scr.setTcatcd(sp(4));
                scr.setTrnsrc(sp(10));
                scr.setTrnamt(sp(12));
                scr.setTdesc(sp(60));
                scr.setTorigdt(sp(10));
                scr.setTprocdt(sp(10));
                scr.setMid(sp(9));
                scr.setMname(sp(30));
                scr.setMcity(sp(25));
                scr.setMzip(sp(10));
            }

            if (blankOrLow(scr.getTtypcd())) { fail("Type CD can NOT be empty...", "TTYPCD"); return; }
            if (blankOrLow(scr.getTcatcd())) { fail("Category CD can NOT be empty...", "TCATCD"); return; }
            if (blankOrLow(scr.getTrnsrc())) { fail("Source can NOT be empty...", "TRNSRC"); return; }
            if (blankOrLow(scr.getTdesc())) { fail("Description can NOT be empty...", "TDESC"); return; }
            if (blankOrLow(scr.getTrnamt())) { fail("Amount can NOT be empty...", "TRNAMT"); return; }
            if (blankOrLow(scr.getTorigdt())) { fail("Orig Date can NOT be empty...", "TORIGDT"); return; }
            if (blankOrLow(scr.getTprocdt())) { fail("Proc Date can NOT be empty...", "TPROCDT"); return; }
            if (blankOrLow(scr.getMid())) { fail("Merchant ID can NOT be empty...", "MID"); return; }
            if (blankOrLow(scr.getMname())) { fail("Merchant Name can NOT be empty...", "MNAME"); return; }
            if (blankOrLow(scr.getMcity())) { fail("Merchant City can NOT be empty...", "MCITY"); return; }
            if (blankOrLow(scr.getMzip())) { fail("Merchant Zip can NOT be empty...", "MZIP"); return; }

            if (!numeric(scr.getTtypcd())) { fail("Type CD must be Numeric...", "TTYPCD"); return; }
            if (!numeric(scr.getTcatcd())) { fail("Category CD must be Numeric...", "TCATCD"); return; }

            String amt = scr.getTrnamt();
            if ((!eq(amt.substring(0, 1), "-") && !eq(amt.substring(0, 1), "+"))
                    || !numeric(amt.substring(1, 9))
                    || !eq(amt.substring(9, 10), ".")
                    || !numeric(amt.substring(10, 12))) {
                fail("Amount should be in format -99999999.99", "TRNAMT");
                return;
            }

            if (badDate(scr.getTorigdt())) {
                fail("Orig Date should be in format YYYY-MM-DD", "TORIGDT");
                return;
            }
            if (badDate(scr.getTprocdt())) {
                fail("Proc Date should be in format YYYY-MM-DD", "TPROCDT");
                return;
            }

            // COMPUTE WS-TRAN-AMT-N = FUNCTION NUMVAL-C(TRNAMTI)
            wsTranAmtN = amountOf(scr.getTrnamt());
            wsTranAmtE = edit(wsTranAmtN);
            scr.setTrnamt(wsTranAmtE);

            checkDate(scr.getTorigdt(), "Orig Date - Not a valid date...", "TORIGDT");
            if (done) {
                return;
            }
            checkDate(scr.getTprocdt(), "Proc Date - Not a valid date...", "TPROCDT");
            if (done) {
                return;
            }

            if (!numeric(scr.getMid())) {
                fail("Merchant ID must be Numeric...", "MID");
            }
        }

        private boolean badDate(String d) {
            return !numeric(d.substring(0, 4))
                    || !eq(d.substring(4, 5), "-")
                    || !numeric(d.substring(5, 7))
                    || !eq(d.substring(7, 8), "-")
                    || !numeric(d.substring(8, 10));
        }

        /** PIC S9(9)V99 target of NUMVAL-C: truncated, high-order digits lost. */
        private BigDecimal amountOf(String text) {
            BigDecimal v = CobolRecords.numval(text, '.').setScale(2, RoundingMode.DOWN);
            BigDecimal mod = BigDecimal.TEN.pow(9);
            BigDecimal ip = v.abs().setScale(0, RoundingMode.DOWN).remainder(mod);
            BigDecimal fp = v.abs().subtract(v.abs().setScale(0, RoundingMode.DOWN));
            BigDecimal r = ip.add(fp).setScale(2, RoundingMode.DOWN);
            return v.signum() < 0 ? r.negate() : r;
        }

        /** CALL 'CSUTLDTC' and test its result (lines 389-407 / 409-427). */
        private void checkDate(String date, String msg, String cursorField) {
            CobolRef<String> d = CobolRef.of(pad(date, 10));
            CobolRef<String> f = CobolRef.of(pad("YYYY-MM-DD", 10));   // WS-DATE-FORMAT
            CobolRef<String> r = CobolRef.of(sp(80));
            callCsutldtc(d, f, r);
            String res = pad(r.get(), 80);
            String sev = res.substring(0, 4);        // CSUTLDTC-RESULT-SEV-CD
            String num = res.substring(15, 19);      // CSUTLDTC-RESULT-MSG-NUM
            if (!eq(sev, "0000") && !eq(num, "2513")) {
                fail(msg, cursorField);
            }
        }

        /** ADD-TRANSACTION */
        private void addTransaction() {
            tran.setTranId(HIGH_16);
            startbrTransactFile();
            if (done) {
                return;
            }
            readprevTransactFile();
            if (done) {
                return;
            }
            endbrTransactFile();
            wsTranIdN = idDigits(tran.getTranId());                  // MOVE TRAN-ID TO WS-TRAN-ID-N
            wsTranIdN = (wsTranIdN + 1) % 10_000_000_000_000_000L;   // ADD 1 (PIC 9(16), high order lost)
            tran = initialTran();                                    // INITIALIZE TRAN-RECORD
            tran.setTranId(digits(wsTranIdN, 16));
            tran.setTranTypeCd(pad(scr.getTtypcd(), 2));
            tran.setTranCatCd(CobolRecords.numval(scr.getTcatcd(), '.').intValue());
            tran.setTranSource(pad(scr.getTrnsrc(), 10));
            tran.setTranDesc(pad(scr.getTdesc(), 100));
            wsTranAmtN = amountOf(scr.getTrnamt());
            tran.setTranAmt(wsTranAmtN);
            tran.setTranCardNum(pad(scr.getCardnin(), 16));
            tran.setTranMerchantId(CobolRecords.numval(scr.getMid(), '.').intValue());
            tran.setTranMerchantName(pad(scr.getMname(), 50));
            tran.setTranMerchantCity(pad(scr.getMcity(), 50));
            tran.setTranMerchantZip(pad(scr.getMzip(), 10));
            tran.setTranOrigTs(pad(scr.getTorigdt(), 26));
            tran.setTranProcTs(pad(scr.getTprocdt(), 26));
            writeTransactFile();
        }

        /** MOVE of an alphanumeric item to PIC 9(16): the digit nibble of each character. */
        private long idDigits(String s) {
            String v = pad(s, 16);
            long n = 0;
            for (int i = 0; i < 16; i++) {
                n = n * 10 + Math.floorMod(v.charAt(i) & 0x0F, 10);
            }
            return n;
        }

        /** COPY-LAST-TRAN-DATA */
        private void copyLastTranData() {
            validateInputKeyFields();
            if (done) {
                return;
            }
            tran.setTranId(HIGH_16);
            startbrTransactFile();
            if (done) {
                return;
            }
            readprevTransactFile();
            if (done) {
                return;
            }
            endbrTransactFile();
            if (!errFlg) {
                BigDecimal a = tran.getTranAmt() == null ? BigDecimal.ZERO : tran.getTranAmt();
                wsTranAmtE = edit(a);
                scr.setTtypcd(pad(tran.getTranTypeCd(), 2));
                scr.setTcatcd(digits(tran.getTranCatCd() == null ? 0 : tran.getTranCatCd(), 4));
                scr.setTrnsrc(pad(tran.getTranSource(), 10));
                scr.setTrnamt(wsTranAmtE);
                scr.setTdesc(pad(tran.getTranDesc(), 60));
                scr.setTorigdt(pad(tran.getTranOrigTs(), 10));
                scr.setTprocdt(pad(tran.getTranProcTs(), 10));
                scr.setMid(digits(tran.getTranMerchantId() == null ? 0 : tran.getTranMerchantId(), 9));
                scr.setMname(pad(tran.getTranMerchantName(), 30));
                scr.setMcity(pad(tran.getTranMerchantCity(), 25));
                scr.setMzip(pad(tran.getTranMerchantZip(), 10));
            }
            processEnterKey();
        }

        /** RETURN-TO-PREV-SCREEN */
        private void returnToPrevScreen() {
            String to = pad(ca.getCdemoToProgram(), 8);
            if (blankOrLow(to)) {
                ca.setCdemoToProgram("COSGN00C");
            }
            ca.setCdemoFromTranid(WS_TRANID);
            ca.setCdemoFromProgram(WS_PGMNAME);
            ca.setCdemoPgmContext(0);
            dispatchCdemoToProgramL508(task, pad(ca.getCdemoToProgram(), 8), ca);   // line 508
            if (task.ended()) {
                done = true;   // on PGMIDERR / LENGERR the program goes on (RESP not tested)
            }
        }

        /** SEND-TRNADD-SCREEN */
        private void sendTrnaddScreen() {
            populateHeaderInfo();
            scr.setErrmsg(pad(message, 78));
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            for (String f : cursors) {
                sub.cursor(f);
            }
            if (errmsgGreen) {
                sub.color("ERRMSG", 0xF4);   // DFHGREEN
            }
            task.sendMap(Cotrn2aScreen.MAP, Cotrn2aScreen.MAPSET, scr, sub, "ERASE", "CURSOR");
            task.returnTransid(WS_TRANID, ca);
            done = true;
        }

        /** RECEIVE-TRNADD-SCREEN (RESP is stored, never tested: MAPFAIL leaves COTRN2AI as it is) */
        private void receiveTrnaddScreen() {
            Optional<Cotrn2aScreen> in = task.receive(Cotrn2aScreen.MAP, Cotrn2aScreen.MAPSET, Cotrn2aScreen.class);
            if (in.isPresent()) {
                Cotrn2aScreen r = in.get();
                scr.setActidin(rcv(r.getActidin(), 11));
                scr.setCardnin(rcv(r.getCardnin(), 16));
                scr.setTtypcd(rcv(r.getTtypcd(), 2));
                scr.setTcatcd(rcv(r.getTcatcd(), 4));
                scr.setTrnsrc(rcv(r.getTrnsrc(), 10));
                scr.setTdesc(rcv(r.getTdesc(), 60));
                scr.setTrnamt(rcv(r.getTrnamt(), 12));
                scr.setTorigdt(rcv(r.getTorigdt(), 10));
                scr.setTprocdt(rcv(r.getTprocdt(), 10));
                scr.setMid(rcv(r.getMid(), 9));
                scr.setMname(rcv(r.getMname(), 30));
                scr.setMcity(rcv(r.getMcity(), 25));
                scr.setMzip(rcv(r.getMzip(), 10));
                scr.setConfirm(rcv(r.getConfirm(), 1));
                cursors.clear();
            }
        }

        /** POPULATE-HEADER-INFO */
        private void populateHeaderInfo() {
            LocalDateTime now = task.now();   // FUNCTION CURRENT-DATE
            scr.setTitle01(pad("      AWS Mainframe Modernization       ", 40));   // CCDA-TITLE01
            scr.setTitle02(pad("              CardDemo                  ", 40));   // CCDA-TITLE02
            scr.setTrnname(WS_TRANID);
            scr.setPgmname(WS_PGMNAME);
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
        }

        /** READ-CXACAIX-FILE */
        private void readCxacaixFile() {
            long key = xref.getXrefAcctId() == null ? 0L : xref.getXrefAcctId();
            CicsTask.FileRead<CardXrefRecord> r =
                    task.read("CXACAIX", () -> readCxacaix(key).stream().findFirst());
            if (r.resp() == 0) {
                // READ INTO: the program's own copy
                xref = CardXrefRecord.fromRecord(r.record().toRecord(CobolRecords.charset()), CobolRecords.charset());
            } else if (r.resp() == 13) {
                fail("Account ID NOT found...", "ACTIDIN");
            } else {
                displayResp(r.resp(), r.resp2());
                fail("Unable to lookup Acct in XREF AIX file...", "ACTIDIN");
            }
        }

        /** READ-CCXREF-FILE */
        private void readCcxrefFile() {
            String key = xref.getXrefCardNum();
            CicsTask.FileRead<CardXrefRecord> r = task.read("CCXREF", () -> readCcxref(key));
            if (r.resp() == 0) {
                xref = CardXrefRecord.fromRecord(r.record().toRecord(CobolRecords.charset()), CobolRecords.charset());
            } else if (r.resp() == 13) {
                fail("Card Number NOT found...", "CARDNIN");
            } else {
                displayResp(r.resp(), r.resp2());
                fail("Unable to lookup Card # in XREF file...", "CARDNIN");
            }
        }

        private NavigableSet<String> transactKeys() {
            TreeSet<String> keys = new TreeSet<>(Comparator.comparing(k -> CobolRecords.sortKey(k, "cp037")));
            tranRecordRepository.findAll().forEach(t -> keys.add(t.getTranId()));
            return keys;
        }

        /** STARTBR-TRANSACT-FILE */
        private void startbrTransactFile() {
            int resp = task.startbr("TRANSACT", tran.getTranId(), false, this::transactKeys);
            if (resp == 0) {
                return;
            }
            if (resp == 13) {
                fail("Transaction ID NOT found...", "ACTIDIN");
            } else {
                displayResp(resp, 0);
                fail("Unable to lookup Transaction...", "ACTIDIN");
            }
        }

        /** READPREV-TRANSACT-FILE */
        private void readprevTransactFile() {
            CicsTask.Browsed b = task.readprev("TRANSACT", tran.getTranId());
            if (b.resp() == 0) {
                tran.setTranId(b.key());   // RIDFLD is set to the key read
                Optional<TranRecord> rec = tranRecordRepository.findById(b.key());
                if (rec.isPresent()) {
                    tran = TranRecord.fromRecord(rec.get().toRecord(CobolRecords.charset()), CobolRecords.charset());
                }
            } else if (b.resp() == 20) {
                tran.setTranId("0".repeat(16));   // MOVE ZEROS TO TRAN-ID
            } else {
                displayResp(b.resp(), 0);
                fail("Unable to lookup Transaction...", "ACTIDIN");
            }
        }

        /** ENDBR-TRANSACT-FILE (no RESP option) */
        private void endbrTransactFile() {
            task.endbr("TRANSACT");
        }

        /** WRITE-TRANSACT-FILE */
        private void writeTransactFile() {
            final TranRecord toWrite = tran;
            int resp = task.write("TRANSACT", tranRecordRepository.existsById(toWrite.getTranId()),
                    () -> writeTransact(toWrite));
            if (resp == 0) {
                initializeAllFields();
                message = sp(80);
                errmsgGreen = true;   // MOVE DFHGREEN TO ERRMSGC
                String id = toWrite.getTranId();
                int sp = id.indexOf(' ');
                String tid = sp < 0 ? id : id.substring(0, sp);   // DELIMITED BY SPACE
                message = pad("Transaction added successfully. " + " Your Tran ID is " + tid + ".", 80);
                sendTrnaddScreen();
            } else if (resp == 14 || resp == 15) {   // DUPREC / DUPKEY
                fail("Tran ID already exist...", "ACTIDIN");
            } else {
                displayResp(resp, 0);
                fail("Unable to Add Transaction...", "ACTIDIN");
            }
        }

        /** CLEAR-CURRENT-SCREEN */
        private void clearCurrentScreen() {
            initializeAllFields();
            sendTrnaddScreen();
        }

        /** INITIALIZE-ALL-FIELDS */
        private void initializeAllFields() {
            cursors.add("ACTIDIN");
            scr.setActidin(sp(11));
            scr.setCardnin(sp(16));
            scr.setTtypcd(sp(2));
            scr.setTcatcd(sp(4));
            scr.setTrnsrc(sp(10));
            scr.setTrnamt(sp(12));
            scr.setTdesc(sp(60));
            scr.setTorigdt(sp(10));
            scr.setTprocdt(sp(10));
            scr.setMid(sp(9));
            scr.setMname(sp(30));
            scr.setMcity(sp(25));
            scr.setMzip(sp(10));
            scr.setConfirm(sp(1));
            message = sp(80);
        }
    }
}
