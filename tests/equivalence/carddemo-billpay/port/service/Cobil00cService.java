package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.Cobil00cCarddemoCommarea;
import com.gitgalaxy.modernized.dto.screen.Cobil0aScreen;
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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.NavigableSet;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 345 tests NORMAL,NOTFND
 * REWRITE at line 379 tests NORMAL,NOTFND
 * READ at line 410 tests NORMAL,NOTFND
 * STARTBR at line 443 tests NORMAL,NOTFND
 * READPREV at line 474 tests ENDFILE,NORMAL
 * WRITE at line 512 tests DUPKEY,DUPREC,NORMAL
 * The RESP of RECEIVE at line 308 (paragraph RECEIVE-BILLPAY-SCREEN) is never tested by the program.
 * Screens (#3619): Cobil0aScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class Cobil00cService {

    private static final Logger log = LoggerFactory.getLogger(Cobil00cService.class);

    private static final String WS_PGMNAME = "COBIL00C";
    private static final String WS_TRANID = "CB00";
    private static final String MAP = "COBIL0A";
    private static final String MAPSET = "COBIL00";
    private static final int DFHGREEN = 0xF4;
    private static final String HIGH_VALUES_16 = "\u00ff".repeat(16);

    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final TranRecordRepository tranRecordRepository;

    /** A CICS transaction entered the program. */
    public Cobil00cCarddemoCommarea handleTransaction(String transid, Cobil00cCarddemoCommarea request) {
        log.info("Cobil00c: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA and the paragraphs it performs. */
    public void runTask(CicsTask task) {
        new Run(task).main();
    }

    /** Another program LINKed / XCTLed to this one. */
    public Cobil00cCarddemoCommarea handleLink(Cobil00cCarddemoCommarea request) {
        log.info("Cobil00c: handleLink");
        return request;
    }

    /** EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COBIL00C.cbl:281, COMMAREA(CARDDEMO-COMMAREA): the target is data-driven (candidates the engine found: COMEN01C (moves), COSGN00C (moves)).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically.
     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the
     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition
     *  (NORMAL, PGMIDERR, ...).
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public String dispatchCdemoToProgramL281(CicsTask task, String program, Object commarea) {
        return task.xctl(program.stripTrailing(), commarea);
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

    // ------------------------------------------------------------------ helpers

    private static String fit(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    private static String low(int n) {
        return "\u0000".repeat(n);
    }

    /** IF x = SPACES OR LOW-VALUES */
    private static boolean spacesOrLow(String s) {
        if (s == null || s.isEmpty()) {
            return true;
        }
        return CobolCompare.eq(s, "") || CobolCompare.eq(s, CobolCompare.lowValues(s.length()));
    }

    /** MOVE alphanumeric TO PIC 9(n), as GnuCOBOL moves it: blanks skipped, digits right-justified, any
     *  other character makes the move invalid (null). */
    private static Long digitsKey(String text) {
        if (text == null) {
            return null;
        }
        StringBuilder d = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c >= '0' && c <= '9') {
                d.append(c);
            } else if (c != ' ') {
                return null;
            }
        }
        if (d.length() == 0) {
            return null;
        }
        return CobolRecords.numval(d.toString()).longValue();
    }

    /** Store into PIC S9(digits)V9(scale): truncate decimals, lose high-order digits. */
    private static BigDecimal store(BigDecimal v, int digits, int scale) {
        BigInteger u = v.setScale(scale, RoundingMode.DOWN).unscaledValue();
        BigInteger m = u.abs().mod(BigInteger.TEN.pow(digits));
        return new BigDecimal(u.signum() < 0 ? m.negate() : m, scale);
    }

    private static Cobil0aScreen lowScreen() {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(low(4));
        s.setTitle01(low(40));
        s.setCurdate(low(8));
        s.setPgmname(low(8));
        s.setTitle02(low(40));
        s.setCurtime(low(8));
        s.setActidin(low(11));
        s.setCurbal(low(14));
        s.setConfirm(low(1));
        s.setErrmsg(low(78));
        return s;
    }

    private static Cobil0aScreen spaceScreen() {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(fit("", 4));
        s.setTitle01(fit("", 40));
        s.setCurdate(fit("", 8));
        s.setPgmname(fit("", 8));
        s.setTitle02(fit("", 40));
        s.setCurtime(fit("", 8));
        s.setActidin(fit("", 11));
        s.setCurbal(fit("", 14));
        s.setConfirm(fit("", 1));
        s.setErrmsg(fit("", 78));
        return s;
    }

    /** What RECEIVE MAP leaves in COBIL0AI: a field not transmitted holds low-values. */
    private static Cobil0aScreen received(Cobil0aScreen r) {
        Cobil0aScreen s = new Cobil0aScreen();
        s.setTrnname(r.getTrnname() == null ? low(4) : fit(r.getTrnname(), 4));
        s.setTitle01(r.getTitle01() == null ? low(40) : fit(r.getTitle01(), 40));
        s.setCurdate(r.getCurdate() == null ? low(8) : fit(r.getCurdate(), 8));
        s.setPgmname(r.getPgmname() == null ? low(8) : fit(r.getPgmname(), 8));
        s.setTitle02(r.getTitle02() == null ? low(40) : fit(r.getTitle02(), 40));
        s.setCurtime(r.getCurtime() == null ? low(8) : fit(r.getCurtime(), 8));
        s.setActidin(r.getActidin() == null ? low(11) : fit(r.getActidin(), 11));
        s.setCurbal(r.getCurbal() == null ? low(14) : fit(r.getCurbal(), 14));
        s.setConfirm(r.getConfirm() == null ? low(1) : fit(r.getConfirm(), 1));
        s.setErrmsg(r.getErrmsg() == null ? low(78) : fit(r.getErrmsg(), 78));
        return s;
    }

    private static Cobil00cCarddemoCommarea blankCommarea() {
        Cobil00cCarddemoCommarea c = new Cobil00cCarddemoCommarea();
        c.setCdemoFromTranid(fit("", 4));
        c.setCdemoFromProgram(fit("", 8));
        c.setCdemoToTranid(fit("", 4));
        c.setCdemoToProgram(fit("", 8));
        c.setCdemoUserId(fit("", 8));
        c.setCdemoUserType(fit("", 1));
        c.setCdemoPgmContext(0);
        c.setCdemoCustId(0);
        c.setCdemoCustFname(fit("", 25));
        c.setCdemoCustMname(fit("", 25));
        c.setCdemoCustLname(fit("", 25));
        c.setCdemoAcctId(0L);
        c.setCdemoAcctStatus(fit("", 1));
        c.setCdemoCardNum(0L);
        c.setCdemoLastMap(fit("", 7));
        c.setCdemoLastMapset(fit("", 7));
        c.setCdemoCb00TrnidFirst(fit("", 16));
        c.setCdemoCb00TrnidLast(fit("", 16));
        c.setCdemoCb00PageNum(0);
        c.setCdemoCb00NextPageFlg("N");
        c.setCdemoCb00TrnSelFlg(fit("", 1));
        c.setCdemoCb00TrnSelected(fit("", 16));
        return c;
    }

    private static Cobil00cCarddemoCommarea copyCommarea(Cobil00cCarddemoCommarea s) {
        Cobil00cCarddemoCommarea c = new Cobil00cCarddemoCommarea();
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
        c.setCdemoCb00TrnidFirst(s.getCdemoCb00TrnidFirst());
        c.setCdemoCb00TrnidLast(s.getCdemoCb00TrnidLast());
        c.setCdemoCb00PageNum(s.getCdemoCb00PageNum());
        c.setCdemoCb00NextPageFlg(s.getCdemoCb00NextPageFlg());
        c.setCdemoCb00TrnSelFlg(s.getCdemoCb00TrnSelFlg());
        c.setCdemoCb00TrnSelected(s.getCdemoCb00TrnSelected());
        return c;
    }

    private static TranRecord blankTran() {
        TranRecord t = new TranRecord();
        t.setTranId(fit("", 16));
        t.setTranTypeCd(fit("", 2));
        t.setTranCatCd(0);
        t.setTranSource(fit("", 10));
        t.setTranDesc(fit("", 100));
        t.setTranAmt(BigDecimal.ZERO);
        t.setTranMerchantId(0);
        t.setTranMerchantName(fit("", 50));
        t.setTranMerchantCity(fit("", 50));
        t.setTranMerchantZip(fit("", 10));
        t.setTranCardNum(fit("", 16));
        t.setTranOrigTs(fit("", 26));
        t.setTranProcTs(fit("", 26));
        return t;
    }

    private Optional<AccountRecord> lookupAcct(Long key) {
        return key == null ? Optional.empty() : readAcctdat(key);
    }

    private Optional<CardXrefRecord> lookupXref(Long key) {
        if (key == null) {
            return Optional.empty();
        }
        return readCxacaix(key).stream()
                .min(Comparator.comparing((CardXrefRecord x) -> CobolRecords.sortKey(x.getXrefCardNum(), "cp037")));
    }

    private NavigableSet<String> transactKeys() {
        TreeSet<String> keys = new TreeSet<>(Comparator.comparing((String s) -> CobolRecords.sortKey(s, "cp037")));
        for (TranRecord t : tranRecordRepository.findAll()) {
            keys.add(t.getTranId());
        }
        return keys;
    }

    // ------------------------------------------------------------------ the task

    /** The program's WORKING-STORAGE for one task, and its paragraphs. */
    private final class Run {
        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();

        private Cobil0aScreen scr = spaceScreen();          // COBIL0AI / COBIL0AO share one area
        private final Set<String> cursorFields = new LinkedHashSet<>();  // fields whose <f>L is -1
        private Integer errmsgColor;                          // ERRMSGC
        private Cobil00cCarddemoCommarea ca = blankCommarea();

        private boolean errFlg;                               // WS-ERR-FLG
        private String message = fit("", 80);                 // WS-MESSAGE
        private boolean confPay;                              // WS-CONF-PAY-FLG
        private int resp;                                     // WS-RESP-CD
        private int reas;                                     // WS-REAS-CD
        private long tranIdNum;                               // WS-TRAN-ID-NUM

        private AccountRecord acct = new AccountRecord();     // ACCOUNT-RECORD
        private CardXrefRecord xref = new CardXrefRecord();   // CARD-XREF-RECORD
        private TranRecord tran = blankTran();                // TRAN-RECORD
        private Long acctKey;                                 // ACCT-ID / XREF-ACCT-ID as moved from ACTIDINI
        private boolean stopped;                              // the task was abended

        Run(CicsTask task) {
            this.task = task;
            acct.setAcctCurrBal(BigDecimal.ZERO);
            xref.setXrefCardNum(fit("", 16));
        }

        private BigDecimal bal() {
            return acct.getAcctCurrBal() == null ? BigDecimal.ZERO : acct.getAcctCurrBal();
        }

        private void fail(String text, String cursorField) {
            errFlg = true;
            message = fit(text, 80);
            cursorFields.add(cursorField);
            sendBillpayScreen();
        }

        private void displayResp() {
            Sysout.display("RESP:", Sysout.number(BigDecimal.valueOf(resp), 9, 0, true),
                    "REAS:", Sysout.number(BigDecimal.valueOf(reas), 9, 0, true));
        }

        // MAIN-PARA
        void main() {
            errFlg = false;                                   // SET ERR-FLG-OFF / USR-MODIFIED-NO
            message = fit("", 80);
            scr.setErrmsg(fit("", 78));

            if (!task.hasCommarea() || (task.eibcalen() != null && task.eibcalen() == 0)) {
                ca.setCdemoToProgram("COSGN00C");
                if (returnToPrevScreen()) {
                    return;
                }
            } else {
                ca = copyCommarea(task.commarea(Cobil00cCarddemoCommarea.class));
                Integer pc = ca.getCdemoPgmContext();
                boolean reenter = pc != null && pc == 1;
                if (!reenter) {
                    ca.setCdemoPgmContext(1);
                    scr = lowScreen();                         // MOVE LOW-VALUES TO COBIL0AO
                    cursorFields.clear();
                    errmsgColor = null;
                    cursorFields.add("ACTIDIN");               // MOVE -1 TO ACTIDINL
                    if (!spacesOrLow(ca.getCdemoCb00TrnSelected())) {
                        scr.setActidin(fit(ca.getCdemoCb00TrnSelected(), 11));
                        processEnterKey();
                        if (stopped) {
                            return;
                        }
                    }
                    sendBillpayScreen();
                } else {
                    receiveBillpayScreen();
                    String aid = task.aid();
                    if ("ENTER".equals(aid)) {
                        processEnterKey();
                        if (stopped) {
                            return;
                        }
                    } else if ("PF3".equals(aid)) {
                        if (spacesOrLow(ca.getCdemoFromProgram())) {
                            ca.setCdemoToProgram("COMEN01C");
                        } else {
                            ca.setCdemoToProgram(ca.getCdemoFromProgram());
                        }
                        if (returnToPrevScreen()) {
                            return;
                        }
                    } else if ("PF4".equals(aid)) {
                        clearCurrentScreen();
                    } else {
                        errFlg = true;
                        message = fit("Invalid key pressed. Please see below...", 80);  // CCDA-MSG-INVALID-KEY
                        sendBillpayScreen();
                    }
                }
            }
            task.returnTransid(WS_TRANID, copyCommarea(ca));
        }

        // PROCESS-ENTER-KEY
        void processEnterKey() {
            confPay = false;

            if (spacesOrLow(scr.getActidin())) {
                fail("Acct ID can NOT be empty...", "ACTIDIN");
            }

            if (!errFlg) {
                acctKey = digitsKey(scr.getActidin());         // MOVE ACTIDINI TO ACCT-ID XREF-ACCT-ID

                String cf = scr.getConfirm();
                if (CobolCompare.eq(cf, "Y") || CobolCompare.eq(cf, "y")) {
                    confPay = true;
                    readAcctdatFile();
                } else if (CobolCompare.eq(cf, "N") || CobolCompare.eq(cf, "n")) {
                    clearCurrentScreen();
                    errFlg = true;
                } else if (spacesOrLow(cf)) {
                    readAcctdatFile();
                } else {
                    fail("Invalid value. Valid values are (Y/N)...", "CONFIRM");
                }

                // runs even when the read above failed (ACCT-CURR-BAL keeps its previous value)
                scr.setCurbal(fit(CobolEdit.format("+9999999999.99", acct.getAcctCurrBal(), false, null), 14));
            }

            if (!errFlg) {
                if (bal().compareTo(BigDecimal.ZERO) <= 0 && !spacesOrLow(scr.getActidin())) {
                    fail("You have nothing to pay...", "ACTIDIN");
                }
            }

            if (!errFlg) {
                if (confPay) {
                    readCxacaixFile();
                    tran.setTranId(HIGH_VALUES_16);            // MOVE HIGH-VALUES TO TRAN-ID
                    startbrTransactFile();
                    readprevTransactFile();
                    endbrTransactFile();
                    if (stopped) {
                        return;
                    }
                    Long n = digitsKey(tran.getTranId());      // MOVE TRAN-ID TO WS-TRAN-ID-NUM
                    if (n != null) {
                        tranIdNum = n;
                    }
                    tranIdNum = (tranIdNum + 1) % 10_000_000_000_000_000L;   // ADD 1 TO WS-TRAN-ID-NUM
                    tran = blankTran();                        // INITIALIZE TRAN-RECORD
                    tran.setTranId(String.format(Locale.ROOT, "%016d", tranIdNum));
                    tran.setTranTypeCd("02");
                    tran.setTranCatCd(2);
                    tran.setTranSource(fit("POS TERM", 10));
                    tran.setTranDesc(fit("BILL PAYMENT - ONLINE", 100));
                    tran.setTranAmt(store(bal(), 9, 2));
                    tran.setTranCardNum(fit(xref.getXrefCardNum(), 16));
                    tran.setTranMerchantId(999999999);
                    tran.setTranMerchantName(fit("BILL PAYMENT", 50));
                    tran.setTranMerchantCity(fit("N/A", 50));
                    tran.setTranMerchantZip(fit("N/A", 10));
                    String ts = getCurrentTimestamp();
                    tran.setTranOrigTs(ts);
                    tran.setTranProcTs(ts);
                    writeTransactFile();
                    acct.setAcctCurrBal(store(bal().subtract(tran.getTranAmt()), 10, 2));
                    updateAcctdatFile();
                } else {
                    message = fit("Confirm to make a bill payment...", 80);
                    cursorFields.add("CONFIRM");
                }

                sendBillpayScreen();
            }
        }

        // GET-CURRENT-TIMESTAMP
        String getCurrentTimestamp() {
            long abs = task.asktime();
            String date = CicsTask.formatDate(abs, "YYYYMMDD", "-");
            String time = CicsTask.formatTime(abs, ":");
            return date + " " + time + "." + "000000";
        }

        // RETURN-TO-PREV-SCREEN: true when the XCTL took (the task has ended)
        boolean returnToPrevScreen() {
            // Defect kept: never true (the program always moves a target first); fix: drop the test.
            if (spacesOrLow(ca.getCdemoToProgram())) {
                ca.setCdemoToProgram("COSGN00C");
            }
            ca.setCdemoFromTranid(WS_TRANID);
            ca.setCdemoFromProgram(fit(WS_PGMNAME, 8));
            ca.setCdemoPgmContext(0);
            String r = dispatchCdemoToProgramL281(task, ca.getCdemoToProgram(), copyCommarea(ca));   // line 281
            return "NORMAL".equals(r);
        }

        // SEND-BILLPAY-SCREEN (with POPULATE-HEADER-INFO)
        void sendBillpayScreen() {
            LocalDateTime now = task.now();
            scr.setTitle01(fit("      AWS Mainframe Modernization", 40));
            scr.setTitle02(fit("              CardDemo", 40));
            scr.setTrnname(fit(WS_TRANID, 4));
            scr.setPgmname(fit(WS_PGMNAME, 8));
            scr.setCurdate(String.format(Locale.ROOT, "%02d/%02d/%02d",
                    now.getMonthValue(), now.getDayOfMonth(), now.getYear() % 100));
            scr.setCurtime(String.format(Locale.ROOT, "%02d:%02d:%02d",
                    now.getHour(), now.getMinute(), now.getSecond()));
            scr.setErrmsg(fit(message, 78));

            CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
            for (String f : cursorFields) {
                sub.cursor(f);
            }
            if (errmsgColor != null) {
                sub.color("ERRMSG", errmsgColor);
            }
            task.sendMap(MAP, MAPSET, Cobil0aScreen.fromValues(scr.screenValues()), sub, "ERASE", "CURSOR");
        }

        // RECEIVE-BILLPAY-SCREEN (RESP never tested by the program)
        void receiveBillpayScreen() {
            Optional<Cobil0aScreen> in = task.receive(MAP, MAPSET, Cobil0aScreen.class);
            resp = in.isPresent() ? 0 : 36;
            reas = 0;
            if (in.isPresent()) {
                scr = received(in.get());
                cursorFields.clear();
                errmsgColor = null;
            }
        }

        // READ-ACCTDAT-FILE
        void readAcctdatFile() {
            CicsTask.FileRead<AccountRecord> r = task.readForUpdate("ACCTDAT", () -> lookupAcct(acctKey));
            resp = r.resp();
            reas = r.resp2();
            if (resp == 0) {
                acct = AccountRecord.fromRecord(r.record().toRecord(cs), cs);
            } else if (resp == 13) {
                fail("Account ID NOT found...", "ACTIDIN");
            } else {
                displayResp();
                fail("Unable to lookup Account...", "ACTIDIN");
            }
        }

        // UPDATE-ACCTDAT-FILE
        void updateAcctdatFile() {
            AccountRecord copy = AccountRecord.fromRecord(acct.toRecord(cs), cs);
            resp = task.rewrite("ACCTDAT", () -> rewriteAcctdat(copy));
            reas = 0;
            if (resp == 0) {
                return;
            } else if (resp == 13) {
                fail("Account ID NOT found...", "ACTIDIN");
            } else {
                displayResp();
                fail("Unable to Update Account...", "ACTIDIN");
            }
        }

        // READ-CXACAIX-FILE
        void readCxacaixFile() {
            CicsTask.FileRead<CardXrefRecord> r = task.read("CXACAIX", () -> lookupXref(acctKey));
            resp = r.resp();
            reas = r.resp2();
            if (resp == 0) {
                xref = CardXrefRecord.fromRecord(r.record().toRecord(cs), cs);
            } else if (resp == 13) {
                fail("Account ID NOT found...", "ACTIDIN");
            } else {
                displayResp();
                fail("Unable to lookup XREF AIX file...", "ACTIDIN");
            }
        }

        // STARTBR-TRANSACT-FILE
        void startbrTransactFile() {
            resp = task.startbr("TRANSACT", tran.getTranId(), false, Cobil00cService.this::transactKeys);
            reas = 0;
            if (resp == 0) {
                return;
            } else if (resp == 13) {
                fail("Transaction ID NOT found...", "ACTIDIN");
            } else {
                displayResp();
                fail("Unable to lookup Transaction...", "ACTIDIN");
            }
        }

        // READPREV-TRANSACT-FILE
        void readprevTransactFile() {
            CicsTask.Browsed b = task.readprev("TRANSACT", tran.getTranId());
            resp = b.resp();
            reas = 0;
            if (resp == 0) {
                tran.setTranId(b.key());                       // RIDFLD is set to the key read
                Optional<TranRecord> found = tranRecordRepository.findById(b.key());
                if (found.isPresent()) {
                    tran = TranRecord.fromRecord(found.get().toRecord(cs), cs);   // INTO(TRAN-RECORD)
                }
            } else if (resp == 20) {
                tran.setTranId("0".repeat(16));                // MOVE ZEROS TO TRAN-ID
            } else {
                displayResp();
                fail("Unable to lookup Transaction...", "ACTIDIN");
            }
        }

        // ENDBR-TRANSACT-FILE: no RESP, so a condition takes CICS's default action (abend)
        void endbrTransactFile() {
            int e = task.endbr("TRANSACT");
            if (e != 0) {
                task.abendOnCondition(e == 13 ? "NOTFND" : "INVREQ");
                stopped = true;
            }
        }

        // WRITE-TRANSACT-FILE
        void writeTransactFile() {
            TranRecord rec = TranRecord.fromRecord(tran.toRecord(cs), cs);
            resp = task.write("TRANSACT", tranRecordRepository.existsById(rec.getTranId()), () -> writeTransact(rec));
            reas = 0;
            if (resp == 0) {
                initializeAllFields();
                message = fit("", 80);
                errmsgColor = DFHGREEN;
                String id = tran.getTranId();
                int sp = id.indexOf(' ');
                String idPart = sp < 0 ? id : id.substring(0, sp);   // DELIMITED BY SPACE
                message = fit("Payment successful. " + " Your Transaction ID is " + idPart + ".", 80);
                sendBillpayScreen();
            } else if (resp == 15 || resp == 14) {             // DUPKEY, DUPREC
                fail("Tran ID already exist...", "ACTIDIN");
            } else {
                displayResp();
                fail("Unable to Add Bill pay Transaction...", "ACTIDIN");
            }
        }

        // CLEAR-CURRENT-SCREEN
        void clearCurrentScreen() {
            initializeAllFields();
            sendBillpayScreen();
        }

        // INITIALIZE-ALL-FIELDS
        void initializeAllFields() {
            cursorFields.add("ACTIDIN");
            scr.setActidin(fit("", 11));
            scr.setCurbal(fit("", 14));
            scr.setConfirm(fit("", 1));
            message = fit("", 80);
        }
    }
}
