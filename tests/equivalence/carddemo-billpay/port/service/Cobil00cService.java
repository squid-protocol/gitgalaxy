package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea2;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cobil0aScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.TranRecord;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.TranRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.TreeSet;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 345 tests NORMAL,NOTFND
 * REWRITE at line 379 tests NORMAL,NOTFND
 * READ at line 410 tests NORMAL,NOTFND
 * STARTBR at line 443 tests NORMAL,NOTFND
 * READPREV at line 474 tests ENDFILE,NORMAL
 * WRITE at line 512 tests DUPKEY,DUPREC,NORMAL
 * TODO: the RESP of RECEIVE at line 308 (paragraph RECEIVE-BILLPAY-SCREEN) is never tested
 * Screens (#3619): Cobil0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cobil00cService {

    private static final Logger log = LoggerFactory.getLogger(Cobil00cService.class);

    private static final String WS_PGMNAME = "COBIL00C";
    private static final String WS_TRANID = "CB00";
    private static final int DFHGREEN = 0xF4;
    private static final String TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String TITLE02 = "              CardDemo                  ";
    private static final String MSG_INVALID_KEY = "Invalid key pressed. Please see below...";
    /** HIGH-VALUES as CicsTask reads a key (all 'ÿ'). */
    private static final String HIGH_KEY = "\u00ff".repeat(16);

    private final ObjectProvider<Comen01cService> comen01cService;
    private final ObjectProvider<Cosgn00cService> cosgn00cService;
    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final TranRecordRepository tranRecordRepository;

    /** The online logic of COBIL00C lives in runTask; there is no batch entry. */
    public void executeCobil00c(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COBIL00C");
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea2 handleTransaction(String transid, CarddemoCommarea2 request) {
        log.info("Cobil00c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of COBIL00C (transaction CB00): the whole PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        new Run(task).mainPara();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CarddemoCommarea2 handleLink(CarddemoCommarea2 request) {
        log.info("Cobil00c: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COBIL00C.cbl:281: the target is data-driven. Candidates: COMEN01C (moves), COSGN00C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL281(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COMEN01C":
                return comen01cService.getObject().handleLink((CarddemoCommarea) request);
            case "COSGN00C":
                cosgn00cService.getObject().handleLink();
                return null;
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COBIL00C.cbl:281: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS as CICS file ACCTDAT at app/cbl/COBIL00C.cbl:345, 379; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<AccountRecord> readAcctdat(Long key) {
        return accountRecordRepository.findById(key);
    }

    public AccountRecord rewriteAcctdat(AccountRecord record) {
        return accountRecordRepository.save(record);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as CICS file CXACAIX at app/cbl/COBIL00C.cbl:410; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardXrefRecord> readCxacaix(Long xrefAcctId) {
        return cardXrefRecordRepository.findByXrefAcctId(xrefAcctId);
    }

    /** AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS as CICS file TRANSACT at app/cbl/COBIL00C.cbl:443, 474, 503, 512; VSAM defines field testing: open (3 public / 0 private estates). */
    public TranRecord writeTransact(TranRecord record) {
        return tranRecordRepository.save(record);
    }

    public List<TranRecord> browseTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortGreaterThanEqualOrderByTranIdSortAsc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    public List<TranRecord> browseBackTransact(String from, int count) {
        return tranRecordRepository.findByTranIdSortLessThanEqualOrderByTranIdSortDesc(CobolRecords.sortKey(from, "cp037"), org.springframework.data.domain.PageRequest.of(0, count));
    }

    /** SEND MAP(COBIL0A) MAPSET(COBIL00) FROM(COBIL0AO) at app/cbl/COBIL00C.cbl:295 (#3619).
     *  The screen is filled and sent by runTask (SEND-BILLPAY-SCREEN). */
    public Cobil0aScreen renderCobil0a(Cobil0aScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(COBIL0A) MAPSET(COBIL00) INTO(COBIL0AI) at app/cbl/COBIL00C.cbl:308 (#3619).
     *  The screen is received and processed by runTask (RECEIVE-BILLPAY-SCREEN, PROCESS-ENTER-KEY). */
    public ScreenModel submitCobil0a(Cobil0aScreen input, String aid) {
        return renderCobil0a(input);
    }

    // ------------------------------------------------------------------ helpers

    private static String pad(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    private static boolean allOf(String s, char c) {
        if (s == null) {
            return true;
        }
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != c) {
                return false;
            }
        }
        return true;
    }

    private static boolean isSpaces(String s) {
        return allOf(s, ' ');
    }

    private static boolean isLow(String s) {
        return allOf(s, '\u0000');
    }

    /** MOVE alphanumeric TO unsigned numeric DISPLAY: the source's digits positionally, right aligned.
     *  Each character contributes its low nibble (a space is 0), so '123' + 8 spaces is 12300000000;
     *  a nibble above 9 (not a digit) is folded modulo 10 -- invalid data, no ruling in the source. */
    private static long numFromX(String s, int digits) {
        String t = s.length() > digits ? s.substring(s.length() - digits) : s;
        long v = 0;
        for (int i = 0; i < t.length(); i++) {
            v = v * 10 + ((t.charAt(i) & 0x0F) % 10);
        }
        return v;
    }

    /** MOVE / COMPUTE into a signed numeric with `intDigits`.`scale`: decimals truncated, high-order digits lost. */
    private static BigDecimal fitNum(BigDecimal v, int intDigits, int scale) {
        BigInteger u = v.setScale(scale, RoundingMode.DOWN).unscaledValue()
                .remainder(BigInteger.TEN.pow(intDigits + scale));
        return new BigDecimal(u, scale);
    }

    private static Cobil0aScreen filledScreen(char fill) {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(String.valueOf(fill).repeat(4));
        s.setTitle01(String.valueOf(fill).repeat(40));
        s.setCurdate(String.valueOf(fill).repeat(8));
        s.setPgmname(String.valueOf(fill).repeat(8));
        s.setTitle02(String.valueOf(fill).repeat(40));
        s.setCurtime(String.valueOf(fill).repeat(8));
        s.setActidin(String.valueOf(fill).repeat(11));
        s.setCurbal(String.valueOf(fill).repeat(14));
        s.setConfirm(String.valueOf(fill));
        s.setErrmsg(String.valueOf(fill).repeat(78));
        return s;
    }

    private static Cobil0aScreen copyScreen(Cobil0aScreen o) {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(o.getTrnname());
        s.setTitle01(o.getTitle01());
        s.setCurdate(o.getCurdate());
        s.setPgmname(o.getPgmname());
        s.setTitle02(o.getTitle02());
        s.setCurtime(o.getCurtime());
        s.setActidin(o.getActidin());
        s.setCurbal(o.getCurbal());
        s.setConfirm(o.getConfirm());
        s.setErrmsg(o.getErrmsg());
        return s;
    }

    /** A received screen as COBIL0AI holds it: a field the terminal did not send is low-values, short data is space padded. */
    private static Cobil0aScreen received(Cobil0aScreen in) {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(fieldIn(in.getTrnname(), 4));
        s.setTitle01(fieldIn(in.getTitle01(), 40));
        s.setCurdate(fieldIn(in.getCurdate(), 8));
        s.setPgmname(fieldIn(in.getPgmname(), 8));
        s.setTitle02(fieldIn(in.getTitle02(), 40));
        s.setCurtime(fieldIn(in.getCurtime(), 8));
        s.setActidin(fieldIn(in.getActidin(), 11));
        s.setCurbal(fieldIn(in.getCurbal(), 14));
        s.setConfirm(fieldIn(in.getConfirm(), 1));
        s.setErrmsg(fieldIn(in.getErrmsg(), 78));
        return s;
    }

    private static String fieldIn(String v, int n) {
        return v == null ? "\u0000".repeat(n) : pad(v, n);
    }

    private static CarddemoCommarea2 initialCommarea() {
        CarddemoCommarea2 c = new CarddemoCommarea2();
        return normalize(c);
    }

    /** MOVE DFHCOMMAREA(1:EIBCALEN) TO CARDDEMO-COMMAREA: the program's own copy of the COMMAREA. */
    private static CarddemoCommarea2 normalize(CarddemoCommarea2 s) {
        CarddemoCommarea2 c = new CarddemoCommarea2();
        c.setCdemoFromTranid(s.getCdemoFromTranid() == null ? pad("", 4) : s.getCdemoFromTranid());
        c.setCdemoFromProgram(s.getCdemoFromProgram() == null ? pad("", 8) : s.getCdemoFromProgram());
        c.setCdemoToTranid(s.getCdemoToTranid() == null ? pad("", 4) : s.getCdemoToTranid());
        c.setCdemoToProgram(s.getCdemoToProgram() == null ? pad("", 8) : s.getCdemoToProgram());
        c.setCdemoUserId(s.getCdemoUserId() == null ? pad("", 8) : s.getCdemoUserId());
        c.setCdemoUserType(s.getCdemoUserType() == null ? " " : s.getCdemoUserType());
        c.setCdemoPgmContext(s.getCdemoPgmContext() == null ? 0 : s.getCdemoPgmContext());
        c.setCdemoCustId(s.getCdemoCustId() == null ? 0 : s.getCdemoCustId());
        c.setCdemoCustFname(s.getCdemoCustFname() == null ? pad("", 25) : s.getCdemoCustFname());
        c.setCdemoCustMname(s.getCdemoCustMname() == null ? pad("", 25) : s.getCdemoCustMname());
        c.setCdemoCustLname(s.getCdemoCustLname() == null ? pad("", 25) : s.getCdemoCustLname());
        c.setCdemoAcctId(s.getCdemoAcctId() == null ? 0L : s.getCdemoAcctId());
        c.setCdemoAcctStatus(s.getCdemoAcctStatus() == null ? " " : s.getCdemoAcctStatus());
        c.setCdemoCardNum(s.getCdemoCardNum() == null ? 0L : s.getCdemoCardNum());
        c.setCdemoLastMap(s.getCdemoLastMap() == null ? pad("", 7) : s.getCdemoLastMap());
        c.setCdemoLastMapset(s.getCdemoLastMapset() == null ? pad("", 7) : s.getCdemoLastMapset());
        c.setCdemoCb00TrnidFirst(s.getCdemoCb00TrnidFirst() == null ? pad("", 16) : s.getCdemoCb00TrnidFirst());
        c.setCdemoCb00TrnidLast(s.getCdemoCb00TrnidLast() == null ? pad("", 16) : s.getCdemoCb00TrnidLast());
        c.setCdemoCb00PageNum(s.getCdemoCb00PageNum() == null ? 0 : s.getCdemoCb00PageNum());
        // CDEMO-CB00-NEXT-PAGE-FLG has VALUE 'N' in WORKING-STORAGE
        c.setCdemoCb00NextPageFlg(s.getCdemoCb00NextPageFlg() == null ? "N" : s.getCdemoCb00NextPageFlg());
        c.setCdemoCb00TrnSelFlg(s.getCdemoCb00TrnSelFlg() == null ? " " : s.getCdemoCb00TrnSelFlg());
        c.setCdemoCb00TrnSelected(s.getCdemoCb00TrnSelected() == null ? pad("", 16) : s.getCdemoCb00TrnSelected());
        return c;
    }

    private static AccountRecord initialAccount() {
        AccountRecord a = new AccountRecord();
        a.setAcctId(0L);
        a.setAcctActiveStatus(" ");
        a.setAcctCurrBal(new BigDecimal("0.00"));
        a.setAcctCreditLimit(new BigDecimal("0.00"));
        a.setAcctCashCreditLimit(new BigDecimal("0.00"));
        a.setAcctOpenDate(pad("", 10));
        a.setAcctExpiraionDate(pad("", 10));
        a.setAcctReissueDate(pad("", 10));
        a.setAcctCurrCycCredit(new BigDecimal("0.00"));
        a.setAcctCurrCycDebit(new BigDecimal("0.00"));
        a.setAcctAddrZip(pad("", 10));
        a.setAcctGroupId(pad("", 10));
        return a;
    }

    private static CardXrefRecord initialXref() {
        CardXrefRecord x = new CardXrefRecord();
        x.setXrefCardNum(pad("", 16));
        x.setXrefCustId(0);
        x.setXrefAcctId(0L);
        return x;
    }

    /** INITIALIZE TRAN-RECORD: alphanumerics to spaces, numerics to zeros. */
    private static TranRecord initialTran() {
        TranRecord t = new TranRecord();
        t.setTranId(pad("", 16));
        t.setTranTypeCd(pad("", 2));
        t.setTranCatCd(0);
        t.setTranSource(pad("", 10));
        t.setTranDesc(pad("", 100));
        t.setTranAmt(new BigDecimal("0.00"));
        t.setTranMerchantId(0);
        t.setTranMerchantName(pad("", 50));
        t.setTranMerchantCity(pad("", 50));
        t.setTranMerchantZip(pad("", 10));
        t.setTranCardNum(pad("", 16));
        t.setTranOrigTs(pad("", 26));
        t.setTranProcTs(pad("", 26));
        return t;
    }

    private Optional<CardXrefRecord> firstXref(Long acctId) {
        return readCxacaix(acctId).stream()
                .min(Comparator.comparing(x -> CobolRecords.sortKey(x.getXrefCardNum(), "cp037")));
    }

    private static String num9(int v) {
        return Sysout.number(BigDecimal.valueOf(v), 9, 0, true);
    }

    // ------------------------------------------------------------------ one task

    /** The task's working storage and the paragraphs of COBIL00C. */
    private final class Run {
        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();

        private CarddemoCommarea2 cc = initialCommarea();
        private Cobil0aScreen scr = filledScreen(' ');   // COBIL0AI / COBIL0AO share one storage
        private AccountRecord acct = initialAccount();
        private CardXrefRecord xref = initialXref();
        private TranRecord tran = initialTran();
        private String message = "";                    // WS-MESSAGE
        private boolean errFlg;                         // WS-ERR-FLG
        private boolean confPay;                        // WS-CONF-PAY-FLG
        private boolean actidCursor;                    // ACTIDINL = -1
        private boolean confirmCursor;                  // CONFIRML = -1
        private boolean errmsgGreen;                    // ERRMSGC = DFHGREEN
        private int respCd;                             // WS-RESP-CD
        private int reasCd;                             // WS-REAS-CD
        private boolean done;                           // the program left through XCTL

        Run(CicsTask task) {
            this.task = task;
        }

        // MAIN-PARA
        void mainPara() {
            errFlg = false;                                  // SET ERR-FLG-OFF
            message = "";                                    // MOVE SPACES TO WS-MESSAGE
            scr.setErrmsg(pad("", 78));                      // ... ERRMSGO OF COBIL0AO

            if (!task.hasCommarea()) {                       // IF EIBCALEN = 0
                cc.setCdemoToProgram("COSGN00C");
                returnToPrevScreen();
            } else {
                cc = normalize(task.commarea(CarddemoCommarea2.class));
                if (cc.getCdemoPgmContext() == null || cc.getCdemoPgmContext() != 1) {   // NOT CDEMO-PGM-REENTER
                    cc.setCdemoPgmContext(1);
                    scr = filledScreen('\u0000');            // MOVE LOW-VALUES TO COBIL0AO
                    errmsgGreen = false;
                    confirmCursor = false;
                    actidCursor = true;                      // MOVE -1 TO ACTIDINL
                    String sel = cc.getCdemoCb00TrnSelected();
                    // NOT = SPACES AND LOW-VALUES: not spaces and not low-values
                    if (!isSpaces(sel) && !isLow(sel)) {
                        scr.setActidin(pad(sel, 11));
                        processEnterKey();
                    }
                    sendBillpayScreen();
                } else {
                    receiveBillpayScreen();
                    String aid = task.aid();
                    if ("ENTER".equals(aid)) {
                        processEnterKey();
                    } else if ("PF3".equals(aid)) {
                        String from = cc.getCdemoFromProgram();
                        if (isSpaces(from) || isLow(from)) {
                            cc.setCdemoToProgram("COMEN01C");
                        } else {
                            cc.setCdemoToProgram(from);
                        }
                        returnToPrevScreen();
                    } else if ("PF4".equals(aid)) {
                        clearCurrentScreen();
                    } else {
                        errFlg = true;
                        message = MSG_INVALID_KEY;           // CCDA-MSG-INVALID-KEY
                        sendBillpayScreen();
                    }
                }
            }
            if (done) {
                return;
            }
            task.returnTransid(WS_TRANID, cc);               // EXEC CICS RETURN TRANSID COMMAREA
        }

        // PROCESS-ENTER-KEY
        void processEnterKey() {
            confPay = false;                                 // SET CONF-PAY-NO

            if (isSpaces(scr.getActidin()) || isLow(scr.getActidin())) {
                errFlg = true;
                message = "Acct ID can NOT be empty...";
                actidCursor = true;
                sendBillpayScreen();
            }

            if (!errFlg) {
                long id = numFromX(scr.getActidin(), 11);    // MOVE ACTIDINI TO ACCT-ID XREF-ACCT-ID
                acct.setAcctId(id);
                xref.setXrefAcctId(id);

                String conf = scr.getConfirm();
                if (CobolCompare.eq(conf, "Y") || CobolCompare.eq(conf, "y")) {
                    confPay = true;
                    readAcctdatFile();
                } else if (CobolCompare.eq(conf, "N") || CobolCompare.eq(conf, "n")) {
                    clearCurrentScreen();
                    errFlg = true;
                } else if (isSpaces(conf) || isLow(conf)) {
                    readAcctdatFile();
                } else {
                    errFlg = true;
                    message = "Invalid value. Valid values are (Y/N)...";
                    confirmCursor = true;
                    sendBillpayScreen();
                }

                // MOVE ACCT-CURR-BAL TO WS-CURR-BAL (PIC +9999999999.99), then to CURBALI -- runs even after an error above
                String curr = CobolEdit.format("+9999999999.99", acct.getAcctCurrBal(), false, null);
                scr.setCurbal(pad(curr, 14));
            }

            if (!errFlg) {
                if (acct.getAcctCurrBal().compareTo(BigDecimal.ZERO) <= 0
                        && !isSpaces(scr.getActidin()) && !isLow(scr.getActidin())) {
                    errFlg = true;
                    message = "You have nothing to pay...";
                    actidCursor = true;
                    sendBillpayScreen();
                }
            }

            if (!errFlg) {
                if (confPay) {
                    // The paragraphs below do not stop on an error flag set by an earlier one: as in the COBOL.
                    readCxacaixFile();
                    tran.setTranId(HIGH_KEY);                // MOVE HIGH-VALUES TO TRAN-ID
                    startbrTransactFile();
                    readprevTransactFile();
                    task.endbr("TRANSACT");                  // ENDBR-TRANSACT-FILE (no RESP)
                    long next = (numFromX(tran.getTranId(), 16) + 1) % 10_000_000_000_000_000L;  // ADD 1 TO WS-TRAN-ID-NUM
                    tran = initialTran();                    // INITIALIZE TRAN-RECORD
                    tran.setTranId(String.format(Locale.ROOT, "%016d", next));
                    tran.setTranTypeCd("02");
                    tran.setTranCatCd(2);
                    tran.setTranSource(pad("POS TERM", 10));
                    tran.setTranDesc(pad("BILL PAYMENT - ONLINE", 100));
                    // Defect kept: TRAN-AMT is S9(09)V99, ACCT-CURR-BAL S9(10)V99; a balance of 10^9 or more loses its
                    // high-order digit. Fix: widen TRAN-AMT.
                    tran.setTranAmt(fitNum(acct.getAcctCurrBal(), 9, 2));
                    tran.setTranCardNum(xref.getXrefCardNum());
                    tran.setTranMerchantId(999999999);
                    tran.setTranMerchantName(pad("BILL PAYMENT", 50));
                    tran.setTranMerchantCity(pad("N/A", 50));
                    tran.setTranMerchantZip(pad("N/A", 10));
                    String ts = getCurrentTimestamp();
                    tran.setTranOrigTs(ts);
                    tran.setTranProcTs(ts);
                    writeTransactFile();
                    // COMPUTE ACCT-CURR-BAL = ACCT-CURR-BAL - TRAN-AMT (no SIZE ERROR: high-order digits lost)
                    acct.setAcctCurrBal(fitNum(acct.getAcctCurrBal().subtract(tran.getTranAmt()), 10, 2));
                    updateAcctdatFile();
                } else {
                    message = "Confirm to make a bill payment...";
                    confirmCursor = true;
                }
                // Defect kept: on a successful payment the screen is sent here a second time (it was sent by
                // WRITE-TRANSACT-FILE already). Fix: send only once.
                sendBillpayScreen();
            }
        }

        // GET-CURRENT-TIMESTAMP
        String getCurrentTimestamp() {
            long abs = task.asktime();
            String date = CicsTask.formatDate(abs, "YYYYMMDD", "-");
            String time = CicsTask.formatTime(abs, ":");
            // INITIALIZE WS-TIMESTAMP; date (1:10), time (12:08), ZEROS to the microseconds
            return date + " " + time + ".000000";
        }

        // RETURN-TO-PREV-SCREEN
        void returnToPrevScreen() {
            String to = cc.getCdemoToProgram();
            if (isLow(to) || isSpaces(to)) {
                cc.setCdemoToProgram("COSGN00C");
            }
            cc.setCdemoFromTranid(WS_TRANID);
            cc.setCdemoFromProgram(WS_PGMNAME);
            cc.setCdemoPgmContext(0);
            String resp = task.xctl(cc.getCdemoToProgram().trim(), cc);
            if ("NORMAL".equals(resp)) {
                done = true;   // XCTL does not return; on LENGERR / PGMIDERR the program goes on
            }
        }

        // SEND-BILLPAY-SCREEN
        void sendBillpayScreen() {
            populateHeaderInfo();
            scr.setErrmsg(pad(message, 78));
            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            if (actidCursor) {
                sub.cursor("ACTIDIN");
            }
            if (confirmCursor) {
                sub.cursor("CONFIRM");
            }
            if (errmsgGreen) {
                sub.color("ERRMSG", DFHGREEN);
            }
            task.sendMap(Cobil0aScreen.MAP, Cobil0aScreen.MAPSET, copyScreen(scr), sub, "ERASE", "CURSOR");
        }

        // RECEIVE-BILLPAY-SCREEN
        void receiveBillpayScreen() {
            // RESP / RESP2 are not tested by the program (MAPFAIL leaves COBIL0AI as it was)
            Optional<Cobil0aScreen> in = task.receive(Cobil0aScreen.MAP, Cobil0aScreen.MAPSET, Cobil0aScreen.class);
            if (in.isPresent()) {
                scr = received(in.get());
                actidCursor = false;     // the L subfields now hold the received lengths
                confirmCursor = false;
            }
        }

        // POPULATE-HEADER-INFO
        void populateHeaderInfo() {
            LocalDateTime now = task.now();                  // FUNCTION CURRENT-DATE on the task's clock
            scr.setTitle01(TITLE01);
            scr.setTitle02(TITLE02);
            scr.setTrnname(WS_TRANID);
            scr.setPgmname(WS_PGMNAME);
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
        }

        // READ-ACCTDAT-FILE
        void readAcctdatFile() {
            CicsTask.FileRead<AccountRecord> r =
                    task.readForUpdate("ACCTDAT", () -> readAcctdat(acct.getAcctId()));
            respCd = r.resp();
            reasCd = r.resp2();
            if (respCd == 0) {
                acct = AccountRecord.fromRecord(r.record().toRecord(cs), cs);   // READ INTO: the program's own copy
            } else if (respCd == 13) {
                fail("Account ID NOT found...");
            } else {
                failOther("Unable to lookup Account...");
            }
        }

        // UPDATE-ACCTDAT-FILE
        void updateAcctdatFile() {
            respCd = task.rewrite("ACCTDAT", () -> rewriteAcctdat(AccountRecord.fromRecord(acct.toRecord(cs), cs)));
            reasCd = 0;
            if (respCd == 0) {
                return;
            } else if (respCd == 13) {
                fail("Account ID NOT found...");
            } else {
                failOther("Unable to Update Account...");
            }
        }

        // READ-CXACAIX-FILE
        void readCxacaixFile() {
            CicsTask.FileRead<CardXrefRecord> r =
                    task.read("CXACAIX", () -> firstXref(xref.getXrefAcctId()));
            respCd = r.resp();
            reasCd = r.resp2();
            if (respCd == 0) {
                xref = CardXrefRecord.fromRecord(r.record().toRecord(cs), cs);
            } else if (respCd == 13) {
                fail("Account ID NOT found...");
            } else {
                failOther("Unable to lookup XREF AIX file...");
            }
        }

        // STARTBR-TRANSACT-FILE
        void startbrTransactFile() {
            Comparator<String> byKey = Comparator.comparing(k -> CobolRecords.sortKey(k, "cp037"));
            respCd = task.startbr("TRANSACT", tran.getTranId(), false, () -> {
                TreeSet<String> keys = new TreeSet<>(byKey);
                tranRecordRepository.findAll().forEach(t -> keys.add(t.getTranId()));
                return keys;
            });
            reasCd = 0;
            if (respCd == 0) {
                return;
            } else if (respCd == 13) {
                fail("Transaction ID NOT found...");
            } else {
                failOther("Unable to lookup Transaction...");
            }
        }

        // READPREV-TRANSACT-FILE
        void readprevTransactFile() {
            CicsTask.Browsed b = task.readprev("TRANSACT", tran.getTranId());
            respCd = b.resp();
            reasCd = 0;
            if (respCd == 0) {
                Optional<TranRecord> rec = tranRecordRepository.findById(b.key());
                if (rec.isPresent()) {
                    tran = TranRecord.fromRecord(rec.get().toRecord(cs), cs);   // READPREV INTO TRAN-RECORD
                }
            } else if (respCd == 20) {
                tran.setTranId("0".repeat(16));              // MOVE ZEROS TO TRAN-ID
            } else {
                failOther("Unable to lookup Transaction...");
            }
        }

        // WRITE-TRANSACT-FILE
        void writeTransactFile() {
            respCd = task.write("TRANSACT", tranRecordRepository.existsById(tran.getTranId()),
                    () -> writeTransact(TranRecord.fromRecord(tran.toRecord(cs), cs)));
            reasCd = 0;
            if (respCd == 0) {
                initializeAllFields();
                message = "";
                errmsgGreen = true;                          // MOVE DFHGREEN TO ERRMSGC
                // STRING ... TRAN-ID DELIMITED BY SPACE: the id has no spaces
                String id = tran.getTranId();
                int sp = id.indexOf(' ');
                message = "Payment successful. " + " Your Transaction ID is " + (sp < 0 ? id : id.substring(0, sp)) + ".";
                sendBillpayScreen();
            } else if (respCd == 15 || respCd == 14) {       // DUPKEY, DUPREC
                fail("Tran ID already exist...");
            } else {
                failOther("Unable to Add Bill pay Transaction...");
            }
        }

        // CLEAR-CURRENT-SCREEN
        void clearCurrentScreen() {
            initializeAllFields();
            sendBillpayScreen();
        }

        // INITIALIZE-ALL-FIELDS
        void initializeAllFields() {
            actidCursor = true;                              // MOVE -1 TO ACTIDINL
            scr.setActidin(pad("", 11));
            scr.setCurbal(pad("", 14));
            scr.setConfirm(" ");
            message = "";
        }

        /** The common error arm: flag, message, cursor on the account field, send. */
        private void fail(String msg) {
            errFlg = true;
            message = msg;
            actidCursor = true;
            sendBillpayScreen();
        }

        /** WHEN OTHER: DISPLAY 'RESP:' WS-RESP-CD 'REAS:' WS-REAS-CD, then as fail. */
        private void failOther(String msg) {
            Sysout.display("RESP:", num9(respCd), "REAS:", num9(reasCd));
            fail(msg);
        }
    }
}
