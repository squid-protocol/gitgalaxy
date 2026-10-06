package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.Cotrn01cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cotrn1aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.Optional;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 269 tests NORMAL,NOTFND
 * The RESP of RECEIVE at line 232 (paragraph RECEIVE-TRNVIEW-SCREEN) is never tested by the program.
 * Screens (#3619): Cotrn1aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cotrn01cService {

    private static final Logger log = LoggerFactory.getLogger(Cotrn01cService.class);

    private static final String WS_PGMNAME = "COTRN01C";
    private static final String WS_TRANID = "CT01";
    private static final String WS_TRANSACT_FILE = "TRANSACT";
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";
    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    private final TranRecordRepository tranRecordRepository;

    /** The program's working storage for one task. */
    private static final class Ctx {
        CicsTask task;
        Cotrn01cCarddemoCommarea commarea;
        Cotrn1aScreen screen;          // COTRN1AI / COTRN1AO share one storage area
        String message = x("", 80);    // WS-MESSAGE
        boolean errFlg;                // WS-ERR-FLG
        boolean cursor;                // TRNIDINL = -1
    }

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none).
     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its
     *  own record, so a port may pass either record -- the facade carries it as Object where a flow
     *  presents another class, and runTask reads it (task.commarea(..)). The flows:
     *  out: RETURN TRANSID(CPVS) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:254 -> app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Copaus0cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CPVD) COMMAREA(CARDDEMO-COMMAREA) at app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:202 -> app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Copaus1cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CTLI) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTLIC.cbl:910 -> app/app-transaction-type-db2/cbl/COTRTLIC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CotrtlicCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CTTU) COMMAREA(WS-COMMAREA) at app/app-transaction-type-db2/cbl/COTRTUPC.cbl:567 -> app/app-transaction-type-db2/cbl/COTRTUPC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CotrtupcCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CAUP) COMMAREA(WS-COMMAREA) at app/cbl/COACTUPC.cbl:1015 -> app/cbl/COACTUPC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CoactupcCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CAVW) COMMAREA(WS-COMMAREA) at app/cbl/COACTVWC.cbl:402 -> app/cbl/COACTVWC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CoactvwcCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CA00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COADM01C.cbl:111 -> app/cbl/COADM01C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CA00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COADM01C.cbl:280 -> app/cbl/COADM01C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CB00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COBIL00C.cbl:146 -> app/cbl/COBIL00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cobil00cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CCLI) COMMAREA(WS-COMMAREA) at app/cbl/COCRDLIC.cbl:615 -> app/cbl/COCRDLIC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CocrdlicCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CCDL) COMMAREA(WS-COMMAREA) at app/cbl/COCRDSLC.cbl:402 -> app/cbl/COCRDSLC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CocrdslcCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CCUP) COMMAREA(WS-COMMAREA) at app/cbl/COCRDUPC.cbl:554 -> app/cbl/COCRDUPC.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CocrdupcCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CM00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COMEN01C.cbl:107 -> app/cbl/COMEN01C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CR00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/CORPT00C.cbl:199 -> app/cbl/CORPT00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CR00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/CORPT00C.cbl:587 -> app/cbl/CORPT00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CC00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COSGN00C.cbl:98 -> app/cbl/COSGN00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CT00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN00C.cbl:138 -> app/cbl/COTRN00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cotrn00cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:156 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cotrn02cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CT02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COTRN02C.cbl:530 -> app/cbl/COTRN02C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cotrn02cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CU00) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR00C.cbl:141 -> app/cbl/COUSR00C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cousr00cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CU01) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR01C.cbl:107 -> app/cbl/COUSR01C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (CarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CU02) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR02C.cbl:135 -> app/cbl/COUSR02C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cousr02cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     *  out: RETURN TRANSID(CU03) COMMAREA(CARDDEMO-COMMAREA) at app/cbl/COUSR03C.cbl:134 -> app/cbl/COUSR03C.cbl, after an XCTL from app/cbl/COTRN01C.cbl (Cousr03cCarddemoCommarea besides Cotrn01cCarddemoCommarea).
     */
    public Object handleTransaction(String transid, Cotrn01cCarddemoCommarea request) {
        log.info("Cotrn01c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COTRN01C", this::runTask);
        return task.returned(Object.class);
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA. */
    public void runTask(CicsTask task) {
        Ctx c = new Ctx();
        c.task = task;
        c.screen = filled('\u0020');

        // MAIN-PARA: SET ERR-FLG-OFF / USR-MODIFIED-NO, MOVE SPACES TO WS-MESSAGE ERRMSGO
        c.errFlg = false;
        c.message = x("", 80);
        c.screen.setErrmsg(x("", 78));

        if (!task.hasCommarea()) {
            // EIBCALEN = 0: the commarea is the program's own (initial) working storage
            c.commarea = initialCommarea();
            c.commarea.setCdemoToProgram(x("COSGN00C", 8));
            returnToPrevScreen(c);
            return;
        }
        c.commarea = task.commarea(Cotrn01cCarddemoCommarea.class);
        Cotrn01cCarddemoCommarea cc = c.commarea;

        if (!pgmReenter(cc)) {
            cc.setCdemoPgmContext(1);                       // SET CDEMO-PGM-REENTER TO TRUE
            c.screen = filled('\u0000');                    // MOVE LOW-VALUES TO COTRN1AO
            c.cursor = true;                                // MOVE -1 TO TRNIDINL
            if (!blankOrLow(cc.getCdemoCt01TrnSelected(), 16)) {
                c.screen.setTrnidin(x(cc.getCdemoCt01TrnSelected(), 16));
                processEnterKey(c);
            }
            sendTrnviewScreen(c);
        } else {
            receiveTrnviewScreen(c);
            String aid = task.aid();
            if ("ENTER".equals(aid)) {
                processEnterKey(c);
            } else if ("PF3".equals(aid)) {
                if (blankOrLow(cc.getCdemoFromProgram(), 8)) {
                    cc.setCdemoToProgram(x("COMEN01C", 8));
                } else {
                    cc.setCdemoToProgram(x(cc.getCdemoFromProgram(), 8));
                }
                returnToPrevScreen(c);
                return;
            } else if ("PF4".equals(aid)) {
                clearCurrentScreen(c);
            } else if ("PF5".equals(aid)) {
                cc.setCdemoToProgram(x("COTRN00C", 8));
                returnToPrevScreen(c);
                return;
            } else {
                c.errFlg = true;
                c.message = x(CCDA_MSG_INVALID_KEY, 80);
                sendTrnviewScreen(c);
            }
        }

        task.returnTransid(WS_TRANID, cc);
    }

    /** PROCESS-ENTER-KEY. */
    private void processEnterKey(Ctx c) {
        if (blankOrLow(c.screen.getTrnidin(), 16)) {
            c.errFlg = true;
            c.message = x("Tran ID can NOT be empty...", 80);
            c.cursor = true;
            sendTrnviewScreen(c);
        } else {
            c.cursor = true;
        }

        TranRecord rec = null;
        if (!c.errFlg) {
            Cotrn1aScreen s = c.screen;
            s.setTrnid(x("", 16));
            s.setCardnum(x("", 16));
            s.setTtypcd(x("", 2));
            s.setTcatcd(x("", 4));
            s.setTrnsrc(x("", 10));
            s.setTrnamt(x("", 12));
            s.setTdesc(x("", 60));
            s.setTorigdt(x("", 10));
            s.setTprocdt(x("", 10));
            s.setMid(x("", 9));
            s.setMname(x("", 30));
            s.setMcity(x("", 25));
            s.setMzip(x("", 10));
            String tranId = x(s.getTrnidin(), 16);          // MOVE TRNIDINI TO TRAN-ID
            rec = readTransactFile(c, tranId);
        }

        if (!c.errFlg) {
            Cotrn1aScreen s = c.screen;
            BigDecimal amt = CobolRecords.decimal(rec.getTranAmt());
            String wsTranAmt = CobolEdit.format("+99999999.99", amt, false, null);   // WS-TRAN-AMT
            s.setTrnid(x(rec.getTranId(), 16));
            s.setCardnum(x(rec.getTranCardNum(), 16));
            s.setTtypcd(x(rec.getTranTypeCd(), 2));
            s.setTcatcd(x(Sysout.number(CobolRecords.decimal(rec.getTranCatCd()), 4, 0, false), 4));
            s.setTrnsrc(x(rec.getTranSource(), 10));
            s.setTrnamt(x(wsTranAmt, 12));
            s.setTdesc(x(rec.getTranDesc(), 60));
            s.setTorigdt(x(rec.getTranOrigTs(), 10));
            s.setTprocdt(x(rec.getTranProcTs(), 10));
            s.setMid(x(Sysout.number(CobolRecords.decimal(rec.getTranMerchantId()), 9, 0, false), 9));
            s.setMname(x(rec.getTranMerchantName(), 30));
            s.setMcity(x(rec.getTranMerchantCity(), 25));
            s.setMzip(x(rec.getTranMerchantZip(), 10));
            sendTrnviewScreen(c);
        }
    }

    /** RETURN-TO-PREV-SCREEN: XCTL never returns to the program. */
    private void returnToPrevScreen(Ctx c) {
        Cotrn01cCarddemoCommarea cc = c.commarea;
        if (blankOrLow(cc.getCdemoToProgram(), 8)) {
            cc.setCdemoToProgram(x("COSGN00C", 8));
        }
        cc.setCdemoFromTranid(x(WS_TRANID, 4));
        cc.setCdemoFromProgram(x(WS_PGMNAME, 8));
        cc.setCdemoPgmContext(0);
        String resp = dispatchCdemoToProgramL205(c.task, cc.getCdemoToProgram(), cc);   // line 205
        if (!"NORMAL".equals(resp)) {
            // no RESP on the XCTL: the condition takes CICS's default action
            c.task.abendOnCondition(resp);
        }
    }

    /** SEND-TRNVIEW-SCREEN. */
    private void sendTrnviewScreen(Ctx c) {
        populateHeaderInfo(c);
        c.screen.setErrmsg(x(c.message, 78));
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        if (c.cursor) {
            sub.cursor("TRNIDIN");
        }
        c.task.sendMap(Cotrn1aScreen.MAP, Cotrn1aScreen.MAPSET, copy(c.screen), sub, "ERASE", "CURSOR");
    }

    /** RECEIVE-TRNVIEW-SCREEN: RESP is never tested (defect kept; a MAPFAIL leaves the storage as it was). */
    private void receiveTrnviewScreen(Ctx c) {
        Optional<Cotrn1aScreen> in = c.task.receive(Cotrn1aScreen.MAP, Cotrn1aScreen.MAPSET, Cotrn1aScreen.class);
        if (in.isPresent()) {
            c.screen = copy(in.get());
            c.cursor = false;   // TRNIDINL now holds the received length, not -1
        }
    }

    /** POPULATE-HEADER-INFO. */
    private void populateHeaderInfo(Ctx c) {
        LocalDateTime now = c.task.now();                   // FUNCTION CURRENT-DATE
        Cotrn1aScreen s = c.screen;
        s.setTitle01(x(CCDA_TITLE01, 40));
        s.setTitle02(x(CCDA_TITLE02, 40));
        s.setTrnname(x(WS_TRANID, 4));
        s.setPgmname(x(WS_PGMNAME, 8));
        s.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d", now.getMonthValue(), now.getDayOfMonth(),
                now.getYear() % 100));
        s.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(), now.getSecond()));
    }

    /** READ-TRANSACT-FILE: returns the record, or null with the error flag set. */
    private TranRecord readTransactFile(Ctx c, String tranId) {
        CicsTask.FileRead<TranRecord> r = c.task.readForUpdate(WS_TRANSACT_FILE, () -> readTransact(tranId));
        int resp = r.resp();
        if (resp == 0) {
            return r.record();
        } else if (resp == 13) {
            c.errFlg = true;
            c.message = x("Transaction ID NOT found...", 80);
            c.cursor = true;
            sendTrnviewScreen(c);
        } else {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(r.resp2()), 9, 0, true));
            c.errFlg = true;
            c.message = x("Unable to lookup Transaction...", 80);
            c.cursor = true;
            sendTrnviewScreen(c);
        }
        return null;
    }

    /** CLEAR-CURRENT-SCREEN + INITIALIZE-ALL-FIELDS. */
    private void clearCurrentScreen(Ctx c) {
        c.cursor = true;
        Cotrn1aScreen s = c.screen;
        s.setTrnidin(x("", 16));
        s.setTrnid(x("", 16));
        s.setCardnum(x("", 16));
        s.setTtypcd(x("", 2));
        s.setTcatcd(x("", 4));
        s.setTrnsrc(x("", 10));
        s.setTrnamt(x("", 12));
        s.setTdesc(x("", 60));
        s.setTorigdt(x("", 10));
        s.setTprocdt(x("", 10));
        s.setMid(x("", 9));
        s.setMname(x("", 30));
        s.setMcity(x("", 25));
        s.setMzip(x("", 10));
        c.message = x("", 80);
        sendTrnviewScreen(c);
    }

    // ---- storage helpers ----

    private static String x(String v, int n) {
        return CobolRecords.fit(v, n, CobolRecords.charset());
    }

    private static boolean blankOrLow(String v, int n) {
        String s = x(v, n);
        return CobolCompare.eq(s, "") || CobolCompare.eq(s, "\u0000".repeat(n));
    }

    private static boolean pgmReenter(Cotrn01cCarddemoCommarea cc) {
        return cc.getCdemoPgmContext() != null && cc.getCdemoPgmContext() == 1;
    }

    private static Cotrn1aScreen filled(char ch) {
        String f = String.valueOf(ch);
        Cotrn1aScreen s = new Cotrn1aScreen();
        s.setTrnname(f.repeat(4));
        s.setTitle01(f.repeat(40));
        s.setCurdate(f.repeat(8));
        s.setPgmname(f.repeat(8));
        s.setTitle02(f.repeat(40));
        s.setCurtime(f.repeat(8));
        s.setTrnidin(f.repeat(16));
        s.setTrnid(f.repeat(16));
        s.setCardnum(f.repeat(16));
        s.setTtypcd(f.repeat(2));
        s.setTcatcd(f.repeat(4));
        s.setTrnsrc(f.repeat(10));
        s.setTdesc(f.repeat(60));
        s.setTrnamt(f.repeat(12));
        s.setTorigdt(f.repeat(10));
        s.setTprocdt(f.repeat(10));
        s.setMid(f.repeat(9));
        s.setMname(f.repeat(30));
        s.setMcity(f.repeat(25));
        s.setMzip(f.repeat(10));
        s.setErrmsg(f.repeat(78));
        return s;
    }

    /** A copy with every field at its PICTURE length (also what an event must hold: a snapshot). */
    private static Cotrn1aScreen copy(Cotrn1aScreen in) {
        Cotrn1aScreen s = new Cotrn1aScreen();
        s.setTrnname(x(in.getTrnname(), 4));
        s.setTitle01(x(in.getTitle01(), 40));
        s.setCurdate(x(in.getCurdate(), 8));
        s.setPgmname(x(in.getPgmname(), 8));
        s.setTitle02(x(in.getTitle02(), 40));
        s.setCurtime(x(in.getCurtime(), 8));
        s.setTrnidin(x(in.getTrnidin(), 16));
        s.setTrnid(x(in.getTrnid(), 16));
        s.setCardnum(x(in.getCardnum(), 16));
        s.setTtypcd(x(in.getTtypcd(), 2));
        s.setTcatcd(x(in.getTcatcd(), 4));
        s.setTrnsrc(x(in.getTrnsrc(), 10));
        s.setTdesc(x(in.getTdesc(), 60));
        s.setTrnamt(x(in.getTrnamt(), 12));
        s.setTorigdt(x(in.getTorigdt(), 10));
        s.setTprocdt(x(in.getTprocdt(), 10));
        s.setMid(x(in.getMid(), 9));
        s.setMname(x(in.getMname(), 30));
        s.setMcity(x(in.getMcity(), 25));
        s.setMzip(x(in.getMzip(), 10));
        s.setErrmsg(x(in.getErrmsg(), 78));
        return s;
    }

    /** CARDDEMO-COMMAREA as working storage holds it before any MOVE (X spaces, 9 zeros, NEXT-PAGE-FLG 'N'). */
    private static Cotrn01cCarddemoCommarea initialCommarea() {
        Cotrn01cCarddemoCommarea cc = new Cotrn01cCarddemoCommarea();
        cc.setCdemoFromTranid(x("", 4));
        cc.setCdemoFromProgram(x("", 8));
        cc.setCdemoToTranid(x("", 4));
        cc.setCdemoToProgram(x("", 8));
        cc.setCdemoUserId(x("", 8));
        cc.setCdemoUserType(x("", 1));
        cc.setCdemoPgmContext(0);
        cc.setCdemoCustId(0);
        cc.setCdemoCustFname(x("", 25));
        cc.setCdemoCustMname(x("", 25));
        cc.setCdemoCustLname(x("", 25));
        cc.setCdemoAcctId(0L);
        cc.setCdemoAcctStatus(x("", 1));
        cc.setCdemoCardNum(0L);
        cc.setCdemoLastMap(x("", 7));
        cc.setCdemoLastMapset(x("", 7));
        cc.setCdemoCt01TrnidFirst(x("", 16));
        cc.setCdemoCt01TrnidLast(x("", 16));
        cc.setCdemoCt01PageNum(0);
        cc.setCdemoCt01NextPageFlg("N");
        cc.setCdemoCt01TrnSelFlg(x("", 1));
        cc.setCdemoCt01TrnSelected(x("", 16));
        return cc;
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Cotrn01cCarddemoCommarea handleLink(Cotrn01cCarddemoCommarea request) {
        log.info("Cotrn01c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COTRN01C", request);
        region.run(task, "COTRN01C", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN01C.cbl:205, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves), COTRN00C (moves)).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically.
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL205(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS as CICS file TRANSACT at app/cbl/COTRN01C.cbl:269; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<TranRecord> readTransact(String key) {
        return tranRecordRepository.findById(key);
    }
}
