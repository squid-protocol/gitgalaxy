package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cotrn00cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.Cotrn01cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cotrn0aScreen;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.TreeSet;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * STARTBR at line 593 tests NORMAL,NOTFND
 * READNEXT at line 626 tests ENDFILE,NORMAL
 * READPREV at line 660 tests ENDFILE,NORMAL
 * The RESP of RECEIVE at line 556 (paragraph RECEIVE-TRNLST-SCREEN) is never tested by the program.
 * Screens (#3619): Cotrn0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cotrn00cService {

    private static final Logger log = LoggerFactory.getLogger(Cotrn00cService.class);

    private static final String PGMNAME = "COTRN00C";
    private static final String TRANID = "CT00";
    private static final String FILE = "TRANSACT";
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...         ";

    /** Field name -> length, from the BMS layout (the symbolic map's data fields). */
    private static final Map<String, Integer> LEN = new HashMap<>();

    static {
        for (var f : Cotrn0aScreen.LAYOUT) {
            if (f.name() != null) {
                LEN.put(f.name(), f.length());
            }
        }
    }

    private final TranRecordRepository tranRecordRepository;

    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),
     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through runTask. Returns the COMMAREA its RETURN passes on (null: none). */
    public Cotrn00cCarddemoCommarea handleTransaction(String transid, Cotrn00cCarddemoCommarea request) {
        log.info("Cotrn00c: handleTransaction");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "COTRN00C", this::runTask);
        return task.returned(Cotrn00cCarddemoCommarea.class);
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        log.info("Cotrn00c: runTask");
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public Cotrn00cCarddemoCommarea handleLink(Cotrn00cCarddemoCommarea request) {
        log.info("Cotrn00c: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("COTRN00C", request);
        region.run(task, "COTRN00C", this::runTask);
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN00C.cbl:192, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves), COTRN01C (moves)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL192(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COTRN00C.cbl:518, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves), COTRN01C (moves)).
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL518(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
    }

    /** AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS as CICS file TRANSACT at app/cbl/COTRN00C.cbl:593, 626, 660, 694; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<TranRecord> browseTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortGreaterThanEqualOrderByTranIdSortAsc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    public List<TranRecord> browseBackTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortLessThanEqualOrderByTranIdSortDesc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    /** One task's WORKING-STORAGE and the paragraphs of the program. */
    private final class Run {
        // CARDDEMO-COMMAREA offsets (COCOM01Y + CDEMO-CT00-INFO), 218 bytes
        private static final int FROM_TRANID = 0;
        private static final int FROM_PROGRAM = 4;
        private static final int TO_TRANID = 12;
        private static final int TO_PROGRAM = 16;
        private static final int USER_ID = 24;
        private static final int USER_TYPE = 32;
        private static final int PGM_CONTEXT = 33;
        private static final int CUST_ID = 34;
        private static final int CUST_FNAME = 43;
        private static final int CUST_MNAME = 68;
        private static final int CUST_LNAME = 93;
        private static final int ACCT_ID = 118;
        private static final int ACCT_STATUS = 129;
        private static final int CARD_NUM = 130;
        private static final int LAST_MAP = 146;
        private static final int LAST_MAPSET = 153;
        private static final int TRNID_FIRST = 160;
        private static final int TRNID_LAST = 176;
        private static final int PAGE_NUM = 192;
        private static final int NEXT_PAGE_FLG = 200;
        private static final int TRN_SEL_FLG = 201;
        private static final int TRN_SELECTED = 202;
        private static final int CA_LEN = 218;

        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();
        private final byte[] ca = CobolRecords.blank(CA_LEN, cs);      // CARDDEMO-COMMAREA
        private final Map<String, String> scr = new LinkedHashMap<>();  // COTRN0AI / COTRN0AO share storage
        private TranRecord rec = blankTran();                           // TRAN-RECORD (TRAN-ID is its first 16 bytes)

        private boolean err;          // WS-ERR-FLG
        private boolean eof;          // WS-TRANSACT-EOF
        private boolean eraseYes = true;   // WS-SEND-ERASE-FLG
        private boolean cursorL;      // TRNIDINL OF COTRN0AI = -1
        private boolean done;         // the task ended (XCTL / ABEND): stop at once
        private String message = spaces(80);   // WS-MESSAGE
        private int resp;             // WS-RESP-CD
        private int reas;             // WS-REAS-CD
        private int idx;              // WS-IDX

        Run(CicsTask task) {
            this.task = task;
            for (Map.Entry<String, Integer> e : LEN.entrySet()) {
                scr.put(e.getKey(), spaces(e.getValue()));
            }
            // numeric items with no VALUE start as zeros
            numPut(PGM_CONTEXT, 1, 0);
            numPut(CUST_ID, 9, 0);
            numPut(ACCT_ID, 11, 0);
            numPut(CARD_NUM, 16, 0);
            numPut(PAGE_NUM, 8, 0);
        }

        // ---------------------------------------------------------------- MAIN-PARA
        void mainPara() {
            err = false;                       // SET ERR-FLG-OFF
            eof = false;                       // SET TRANSACT-NOT-EOF
            put(NEXT_PAGE_FLG, 1, "N");        // SET NEXT-PAGE-NO
            eraseYes = true;                   // SET SEND-ERASE-YES
            message = spaces(80);
            scr.put("ERRMSG", spaces(78));
            cursorL = true;                    // MOVE -1 TO TRNIDINL

            Integer len = task.eibcalen();
            if (!task.hasCommarea() || (len != null && len == 0)) {   // IF EIBCALEN = 0
                put(TO_PROGRAM, 8, "COSGN00C");
                returnToPrevScreen();
                return;
            }
            loadCommarea(task.commarea(Object.class));   // MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA
            if (!(contextOf() == 1)) {                   // IF NOT CDEMO-PGM-REENTER
                put(PGM_CONTEXT, 1, "1");                // SET CDEMO-PGM-REENTER
                lowValuesScreen();                       // MOVE LOW-VALUES TO COTRN0AO
                processEnterKey();
                if (done) {
                    return;
                }
                sendTrnlstScreen();
            } else {
                receiveTrnlstScreen();
                String aid = task.aid();
                if ("ENTER".equals(aid)) {
                    processEnterKey();
                } else if ("PF3".equals(aid)) {
                    put(TO_PROGRAM, 8, "COMEN01C");
                    returnToPrevScreen();
                } else if ("PF7".equals(aid)) {
                    processPf7Key();
                } else if ("PF8".equals(aid)) {
                    processPf8Key();
                } else {
                    err = true;
                    cursorL = true;
                    message = fit(MSG_INVALID_KEY, 80);
                    sendTrnlstScreen();
                }
            }
            if (done) {
                return;
            }
            task.returnTransid(TRANID, commareaDto());   // EXEC CICS RETURN TRANSID COMMAREA
        }

        // ---------------------------------------------------------------- PROCESS-ENTER-KEY
        void processEnterKey() {
            boolean picked = false;
            for (int i = 1; i <= 10 && !picked; i++) {
                String sel = scr.get(selName(i));
                if (!isSpaces(sel) && !isLow(sel)) {
                    put(TRN_SEL_FLG, 1, sel);
                    put(TRN_SELECTED, 16, scr.get(trnidName(i)));
                    picked = true;
                }
            }
            if (!picked) {
                put(TRN_SEL_FLG, 1, " ");
                put(TRN_SELECTED, 16, " ");
            }
            String flg = txt(TRN_SEL_FLG, 1);
            String selected = txt(TRN_SELECTED, 16);
            if (!isSpaces(flg) && !isLow(flg) && !isSpaces(selected) && !isLow(selected)) {
                if (CobolCompare.eq(flg, "S") || CobolCompare.eq(flg, "s")) {
                    put(TO_PROGRAM, 8, "COTRN01C");
                    put(FROM_TRANID, 4, TRANID);
                    put(FROM_PROGRAM, 8, PGMNAME);
                    put(PGM_CONTEXT, 1, "0");
                    xctl(dispatchCdemoToProgramL192(task, txt(TO_PROGRAM, 8), commareaDto()));   // XCTL, line 192
                    return;
                } else {
                    message = fit("Invalid selection. Valid value is S", 80);
                    cursorL = true;
                }
            }

            String in = scr.get("TRNIDIN");
            if (isSpaces(in) || isLow(in)) {
                rec.setTranId(lowValues(16));
            } else if (isNumeric(in)) {
                rec.setTranId(fit(in, 16));
            } else {
                err = true;
                message = fit("Tran ID must be Numeric ...", 80);
                cursorL = true;
                sendTrnlstScreen();
                // DEFECT kept: execution carries on into the page-forward below with TRAN-ID unchanged.
            }

            cursorL = true;
            numPut(PAGE_NUM, 8, 0);
            processPageForward();
            if (done) {
                return;
            }
            if (!err) {
                scr.put("TRNIDIN", spaces(16));
            }
        }

        // ---------------------------------------------------------------- PROCESS-PF7-KEY
        void processPf7Key() {
            String first = txt(TRNID_FIRST, 16);
            if (isSpaces(first) || isLow(first)) {
                rec.setTranId(lowValues(16));
            } else {
                rec.setTranId(first);
            }
            put(NEXT_PAGE_FLG, 1, "Y");
            cursorL = true;
            if (page() > 1) {
                processPageBackward();
            } else {
                message = fit("You are already at the top of the page...", 80);
                eraseYes = false;
                sendTrnlstScreen();
            }
        }

        // ---------------------------------------------------------------- PROCESS-PF8-KEY
        void processPf8Key() {
            String last = txt(TRNID_LAST, 16);
            if (isSpaces(last) || isLow(last)) {
                rec.setTranId(highValues(16));
            } else {
                rec.setTranId(last);
            }
            cursorL = true;
            if (CobolCompare.eq(txt(NEXT_PAGE_FLG, 1), "Y")) {
                processPageForward();
            } else {
                message = fit("You are already at the bottom of the page...", 80);
                eraseYes = false;
                sendTrnlstScreen();
            }
        }

        // ---------------------------------------------------------------- PROCESS-PAGE-FORWARD
        void processPageForward() {
            startbrTransact();
            if (err) {
                return;
            }
            String aid = task.aid();
            if (!"ENTER".equals(aid) && !"PF7".equals(aid) && !"PF3".equals(aid)) {
                readnextTransact();
            }
            if (!eof && !err) {
                for (idx = 1; idx <= 10; idx++) {
                    initializeTranData();
                }
            }
            idx = 1;
            while (!(idx >= 11 || eof || err)) {
                readnextTransact();
                if (!eof && !err) {
                    populateTranData();
                    idx = idx + 1;
                }
            }
            if (!eof && !err) {
                setPage(page() + 1);
                readnextTransact();
                if (!eof && !err) {
                    put(NEXT_PAGE_FLG, 1, "Y");
                } else {
                    put(NEXT_PAGE_FLG, 1, "N");
                }
            } else {
                put(NEXT_PAGE_FLG, 1, "N");
                if (idx > 1) {
                    setPage(page() + 1);
                }
            }
            endbrTransact();
            if (done) {
                return;
            }
            mv("PAGENUM", Sysout.number(BigDecimal.valueOf(page()), 8, 0, false));
            scr.put("TRNIDIN", spaces(16));
            sendTrnlstScreen();
        }

        // ---------------------------------------------------------------- PROCESS-PAGE-BACKWARD
        void processPageBackward() {
            startbrTransact();
            if (err) {
                return;
            }
            String aid = task.aid();
            if (!"ENTER".equals(aid) && !"PF8".equals(aid)) {
                readprevTransact();
            }
            if (!eof && !err) {
                for (idx = 1; idx <= 10; idx++) {
                    initializeTranData();
                }
            }
            idx = 10;
            while (!(idx <= 0 || eof || err)) {
                readprevTransact();
                if (!eof && !err) {
                    populateTranData();
                    idx = idx - 1;
                }
            }
            if (!eof && !err) {
                readprevTransact();
                if (CobolCompare.eq(txt(NEXT_PAGE_FLG, 1), "Y")) {
                    if (!eof && !err && page() > 1) {
                        setPage(page() - 1);
                    } else {
                        setPage(1);
                    }
                }
            }
            endbrTransact();
            if (done) {
                return;
            }
            mv("PAGENUM", Sysout.number(BigDecimal.valueOf(page()), 8, 0, false));
            sendTrnlstScreen();
        }

        // ---------------------------------------------------------------- POPULATE-TRAN-DATA
        void populateTranData() {
            String amt = CobolEdit.format("+99999999.99", rec.getTranAmt(), false, null);   // WS-TRAN-AMT
            String ts = fit(rec.getTranOrigTs(), 26);                                       // WS-TIMESTAMP
            String yy = ts.substring(2, 4);
            String mm = ts.substring(5, 7);
            String dd = ts.substring(8, 10);
            String tranDate = fit(mm + "/" + dd + "/" + yy, 8);                             // WS-TRAN-DATE
            if (idx >= 1 && idx <= 10) {
                mv(trnidName(idx), rec.getTranId());
                if (idx == 1) {
                    put(TRNID_FIRST, 16, rec.getTranId());
                }
                mv(tdateName(idx), tranDate);
                mv(tdescName(idx), rec.getTranDesc());
                mv(tamtName(idx), amt);
                if (idx == 10) {
                    put(TRNID_LAST, 16, rec.getTranId());
                }
            }
        }

        // ---------------------------------------------------------------- INITIALIZE-TRAN-DATA
        void initializeTranData() {
            if (idx >= 1 && idx <= 10) {
                mv(trnidName(idx), " ");
                mv(tdateName(idx), " ");
                mv(tdescName(idx), " ");
                mv(tamtName(idx), " ");
            }
        }

        // ---------------------------------------------------------------- RETURN-TO-PREV-SCREEN
        void returnToPrevScreen() {
            String to = txt(TO_PROGRAM, 8);
            if (isLow(to) || isSpaces(to)) {
                put(TO_PROGRAM, 8, "COSGN00C");
            }
            put(FROM_TRANID, 4, TRANID);
            put(FROM_PROGRAM, 8, PGMNAME);
            numPut(PGM_CONTEXT, 1, 0);
            xctl(dispatchCdemoToProgramL518(task, txt(TO_PROGRAM, 8), commareaDto()));   // XCTL, line 518
        }

        /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) COMMAREA(CARDDEMO-COMMAREA): never returns when it works;
         *  without RESP a failure takes CICS's default action, an abend. */
        void xctl(String r) {
            if (!"NORMAL".equals(r)) {
                task.abendOnCondition(r);
            }
            done = true;
        }

        // ---------------------------------------------------------------- SEND-TRNLST-SCREEN
        void sendTrnlstScreen() {
            populateHeaderInfo();
            scr.put("ERRMSG", fit(message, 78));   // MOVE WS-MESSAGE TO ERRMSGO
            Cotrn0aScreen screen = Cotrn0aScreen.fromValues(scr);
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            if (cursorL) {
                sub.cursor("TRNIDIN");
            }
            if (eraseYes) {
                task.sendMap("COTRN0A", "COTRN00", screen, sub, "ERASE", "CURSOR");
            } else {
                task.sendMap("COTRN0A", "COTRN00", screen, sub, "CURSOR");
            }
        }

        // ---------------------------------------------------------------- RECEIVE-TRNLST-SCREEN
        void receiveTrnlstScreen() {
            Optional<Cotrn0aScreen> in = task.receive("COTRN0A", "COTRN00", Cotrn0aScreen.class);
            // DEFECT kept: the RESP of the RECEIVE is never tested. On MAPFAIL COTRN0AI is left as it was.
            resp = in.isPresent() ? 0 : 36;
            reas = 0;
            if (in.isPresent()) {
                Map<String, String> v = in.get().screenValues();
                for (Map.Entry<String, String> e : v.entrySet()) {
                    // a field the terminal did not send leaves its storage as it was
                    if (e.getValue() != null && LEN.containsKey(e.getKey())) {
                        mv(e.getKey(), e.getValue());
                    }
                }
            }
        }

        // ---------------------------------------------------------------- POPULATE-HEADER-INFO
        void populateHeaderInfo() {
            LocalDateTime now = task.now();   // FUNCTION CURRENT-DATE
            String yy = String.format(Locale.ROOT, "%04d", now.getYear()).substring(2);
            mv("TITLE01", TITLE01);
            mv("TITLE02", TITLE02);
            mv("TRNNAME", TRANID);
            mv("PGMNAME", PGMNAME);
            mv("CURDATE", String.format(Locale.ROOT, "%02d/%02d/%s", now.getMonthValue(), now.getDayOfMonth(), yy));
            mv("CURTIME", String.format(Locale.ROOT, "%02d:%02d:%02d", now.getHour(), now.getMinute(), now.getSecond()));
        }

        // ---------------------------------------------------------------- STARTBR-TRANSACT-FILE
        void startbrTransact() {
            resp = task.startbr(FILE, rec.getTranId(), false, this::tranKeys);
            reas = 0;   // RESP2 is not given by the task
            if (resp == 0) {
                // CONTINUE
            } else if (resp == 13) {
                eof = true;
                message = fit("You are at the top of the page...", 80);
                cursorL = true;
                sendTrnlstScreen();
            } else {
                unableToLookup();
            }
        }

        // ---------------------------------------------------------------- READNEXT-TRANSACT-FILE
        void readnextTransact() {
            CicsTask.Browsed b = task.readnext(FILE, rec.getTranId());
            resp = b.resp();
            reas = 0;
            if (resp == 0) {
                loadRecord(b.key());
            } else if (resp == 20) {
                eof = true;
                message = fit("You have reached the bottom of the page...", 80);
                cursorL = true;
                sendTrnlstScreen();
            } else {
                unableToLookup();
            }
        }

        // ---------------------------------------------------------------- READPREV-TRANSACT-FILE
        void readprevTransact() {
            CicsTask.Browsed b = task.readprev(FILE, rec.getTranId());
            resp = b.resp();
            reas = 0;
            if (resp == 0) {
                loadRecord(b.key());
            } else if (resp == 20) {
                eof = true;
                message = fit("You have reached the top of the page...", 80);
                cursorL = true;
                sendTrnlstScreen();
            } else {
                unableToLookup();
            }
        }

        // ---------------------------------------------------------------- ENDBR-TRANSACT-FILE
        void endbrTransact() {
            int rc = task.endbr(FILE);
            if (rc != 0) {
                // DEFECT kept: ENDBR has no RESP, so a failure (e.g. no browse after a NOTFND STARTBR) abends the task.
                task.abendOnCondition(rc == 13 ? "NOTFND" : "INVREQ");
                done = true;
            }
        }

        // ---------------------------------------------------------------- helpers
        private void unableToLookup() {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reas), 9, 0, true));
            err = true;
            message = fit("Unable to lookup transaction...", 80);
            cursorL = true;
            sendTrnlstScreen();
        }

        /** The record is the program's own copy (READ INTO); RIDFLD (TRAN-ID) becomes the key read. */
        private void loadRecord(String key) {
            Optional<TranRecord> found = tranRecordRepository.findById(key);
            if (found.isPresent()) {
                rec = TranRecord.fromRecord(found.get().toRecord(cs), cs);
            }
            rec.setTranId(key);
        }

        /** The file's keys in the code page's byte order, as VSAM orders them. */
        private NavigableSet<String> tranKeys() {
            TreeSet<String> keys = new TreeSet<>(Comparator.comparing((String k) -> CobolRecords.sortKey(k, "cp037")));
            for (TranRecord t : tranRecordRepository.findAll()) {
                keys.add(t.getTranId());
            }
            return keys;
        }

        private TranRecord blankTran() {
            TranRecord t = new TranRecord();
            t.setTranId(spaces(16));
            t.setTranTypeCd(spaces(2));
            t.setTranCatCd(0);
            t.setTranSource(spaces(10));
            t.setTranDesc(spaces(100));
            t.setTranAmt(BigDecimal.ZERO.setScale(2));
            t.setTranMerchantId(0);
            t.setTranMerchantName(spaces(50));
            t.setTranMerchantCity(spaces(50));
            t.setTranMerchantZip(spaces(10));
            t.setTranCardNum(spaces(16));
            t.setTranOrigTs(spaces(26));
            t.setTranProcTs(spaces(26));
            return t;
        }

        private void lowValuesScreen() {
            for (Map.Entry<String, Integer> e : LEN.entrySet()) {
                scr.put(e.getKey(), lowValues(e.getValue()));
            }
            cursorL = false;   // TRNIDINL is wiped too
        }

        private void mv(String field, String value) {
            scr.put(field, fit(value, LEN.get(field)));
        }

        private String fit(String value, int width) {
            return CobolRecords.fit(value, width, cs);
        }

        private String txt(int off, int len) {
            return CobolRecords.text(ca, off, len, cs);
        }

        private void put(int off, int len, String value) {
            CobolRecords.putText(ca, off, len, value, cs);
        }

        private void numPut(int off, int digits, long value) {
            CobolRecords.putZoned(ca, off, digits, 0, false, BigDecimal.valueOf(value), cs);
        }

        private long page() {
            BigDecimal b = CobolRecords.zoned(ca, PAGE_NUM, 8, 0, cs);
            return b == null ? 0 : b.longValue();
        }

        private void setPage(long v) {
            numPut(PAGE_NUM, 8, v);   // 9(08): high-order digits are lost
        }

        private int contextOf() {
            BigDecimal b = CobolRecords.zoned(ca, PGM_CONTEXT, 1, 0, cs);
            return b == null ? -1 : b.intValue();
        }

        private String spaces(int n) {
            return " ".repeat(n);
        }

        private String lowValues(int n) {
            byte[] b = new byte[n];
            return new String(b, cs);
        }

        private String highValues(int n) {
            byte[] b = new byte[n];
            Arrays.fill(b, (byte) 0xFF);
            return new String(b, cs);
        }

        private boolean isSpaces(String s) {
            return CobolCompare.eq(s, "");
        }

        private boolean isLow(String s) {
            return CobolCompare.eq(s, CobolCompare.lowValues(s == null ? 0 : s.length()));
        }

        private boolean isNumeric(String s) {
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

        private String selName(int i) {
            return String.format(Locale.ROOT, "SEL%04d", i);
        }

        private String trnidName(int i) {
            return String.format(Locale.ROOT, "TRNID%02d", i);
        }

        private String tdateName(int i) {
            return String.format(Locale.ROOT, "TDATE%02d", i);
        }

        private String tdescName(int i) {
            return String.format(Locale.ROOT, "TDESC%02d", i);
        }

        private String tamtName(int i) {
            return String.format(Locale.ROOT, "TAMT%03d", i);
        }

        /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: bytes past the received length are spaces. */
        private void loadCommarea(Object o) {
            int dtoLen;
            if (o instanceof Cotrn00cCarddemoCommarea c) {
                general(c.getCdemoFromTranid(), c.getCdemoFromProgram(), c.getCdemoToTranid(), c.getCdemoToProgram(),
                        c.getCdemoUserId(), c.getCdemoUserType(), c.getCdemoPgmContext(), c.getCdemoCustId(),
                        c.getCdemoCustFname(), c.getCdemoCustMname(), c.getCdemoCustLname(), c.getCdemoAcctId(),
                        c.getCdemoAcctStatus(), c.getCdemoCardNum(), c.getCdemoLastMap(), c.getCdemoLastMapset());
                put(TRNID_FIRST, 16, c.getCdemoCt00TrnidFirst());
                put(TRNID_LAST, 16, c.getCdemoCt00TrnidLast());
                CobolRecords.putZoned(ca, PAGE_NUM, 8, 0, false, CobolRecords.decimal(c.getCdemoCt00PageNum()), cs);
                put(NEXT_PAGE_FLG, 1, c.getCdemoCt00NextPageFlg());
                put(TRN_SEL_FLG, 1, c.getCdemoCt00TrnSelFlg());
                put(TRN_SELECTED, 16, c.getCdemoCt00TrnSelected());
                dtoLen = CA_LEN;
            } else if (o instanceof Cotrn01cCarddemoCommarea c) {
                general(c.getCdemoFromTranid(), c.getCdemoFromProgram(), c.getCdemoToTranid(), c.getCdemoToProgram(),
                        c.getCdemoUserId(), c.getCdemoUserType(), c.getCdemoPgmContext(), c.getCdemoCustId(),
                        c.getCdemoCustFname(), c.getCdemoCustMname(), c.getCdemoCustLname(), c.getCdemoAcctId(),
                        c.getCdemoAcctStatus(), c.getCdemoCardNum(), c.getCdemoLastMap(), c.getCdemoLastMapset());
                put(TRNID_FIRST, 16, c.getCdemoCt01TrnidFirst());
                put(TRNID_LAST, 16, c.getCdemoCt01TrnidLast());
                CobolRecords.putZoned(ca, PAGE_NUM, 8, 0, false, CobolRecords.decimal(c.getCdemoCt01PageNum()), cs);
                put(NEXT_PAGE_FLG, 1, c.getCdemoCt01NextPageFlg());
                put(TRN_SEL_FLG, 1, c.getCdemoCt01TrnSelFlg());
                put(TRN_SELECTED, 16, c.getCdemoCt01TrnSelected());
                dtoLen = CA_LEN;
            } else if (o instanceof CarddemoCommarea c) {
                general(c.getCdemoFromTranid(), c.getCdemoFromProgram(), c.getCdemoToTranid(), c.getCdemoToProgram(),
                        c.getCdemoUserId(), c.getCdemoUserType(), c.getCdemoPgmContext(), c.getCdemoCustId(),
                        c.getCdemoCustFname(), c.getCdemoCustMname(), c.getCdemoCustLname(), c.getCdemoAcctId(),
                        c.getCdemoAcctStatus(), c.getCdemoCardNum(), c.getCdemoLastMap(), c.getCdemoLastMapset());
                dtoLen = 160;
            } else {
                throw new IllegalStateException("COMMAREA of an unknown layout: " + o);
            }
            Integer e = task.eibcalen();
            int eff = Math.min(e == null ? dtoLen : e, dtoLen);
            byte space = " ".getBytes(cs)[0];
            for (int i = Math.max(eff, 0); i < CA_LEN; i++) {
                ca[i] = space;
            }
        }

        private void general(String ft, String fp, String tt, String tp, String uid, String ut, Integer ctx,
                             Integer cust, String fn, String mn, String ln, Long acct, String ast, Long card,
                             String lm, String lms) {
            put(FROM_TRANID, 4, ft);
            put(FROM_PROGRAM, 8, fp);
            put(TO_TRANID, 4, tt);
            put(TO_PROGRAM, 8, tp);
            put(USER_ID, 8, uid);
            put(USER_TYPE, 1, ut);
            CobolRecords.putZoned(ca, PGM_CONTEXT, 1, 0, false, CobolRecords.decimal(ctx), cs);
            CobolRecords.putZoned(ca, CUST_ID, 9, 0, false, CobolRecords.decimal(cust), cs);
            put(CUST_FNAME, 25, fn);
            put(CUST_MNAME, 25, mn);
            put(CUST_LNAME, 25, ln);
            CobolRecords.putZoned(ca, ACCT_ID, 11, 0, false, CobolRecords.decimal(acct), cs);
            put(ACCT_STATUS, 1, ast);
            CobolRecords.putZoned(ca, CARD_NUM, 16, 0, false, CobolRecords.decimal(card), cs);
            put(LAST_MAP, 7, lm);
            put(LAST_MAPSET, 7, lms);
        }

        private Cotrn00cCarddemoCommarea commareaDto() {
            Cotrn00cCarddemoCommarea d = new Cotrn00cCarddemoCommarea();
            d.setCdemoFromTranid(txt(FROM_TRANID, 4));
            d.setCdemoFromProgram(txt(FROM_PROGRAM, 8));
            d.setCdemoToTranid(txt(TO_TRANID, 4));
            d.setCdemoToProgram(txt(TO_PROGRAM, 8));
            d.setCdemoUserId(txt(USER_ID, 8));
            d.setCdemoUserType(txt(USER_TYPE, 1));
            d.setCdemoPgmContext(CobolRecords.toInteger(CobolRecords.zoned(ca, PGM_CONTEXT, 1, 0, cs)));
            d.setCdemoCustId(CobolRecords.toInteger(CobolRecords.zoned(ca, CUST_ID, 9, 0, cs)));
            d.setCdemoCustFname(txt(CUST_FNAME, 25));
            d.setCdemoCustMname(txt(CUST_MNAME, 25));
            d.setCdemoCustLname(txt(CUST_LNAME, 25));
            d.setCdemoAcctId(CobolRecords.toLong(CobolRecords.zoned(ca, ACCT_ID, 11, 0, cs)));
            d.setCdemoAcctStatus(txt(ACCT_STATUS, 1));
            d.setCdemoCardNum(CobolRecords.toLong(CobolRecords.zoned(ca, CARD_NUM, 16, 0, cs)));
            d.setCdemoLastMap(txt(LAST_MAP, 7));
            d.setCdemoLastMapset(txt(LAST_MAPSET, 7));
            d.setCdemoCt00TrnidFirst(txt(TRNID_FIRST, 16));
            d.setCdemoCt00TrnidLast(txt(TRNID_LAST, 16));
            d.setCdemoCt00PageNum(CobolRecords.toInteger(CobolRecords.zoned(ca, PAGE_NUM, 8, 0, cs)));
            d.setCdemoCt00NextPageFlg(txt(NEXT_PAGE_FLG, 1));
            d.setCdemoCt00TrnSelFlg(txt(TRN_SEL_FLG, 1));
            d.setCdemoCt00TrnSelected(txt(TRN_SELECTED, 16));
            return d;
        }
    }
}
