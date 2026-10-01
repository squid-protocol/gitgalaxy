package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.call.CobolRef;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CarddemoCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactupcCommarea;
import com.gitgalaxy.modernized.dto.contract.CoactupcWsThisProgcommarea;
import com.gitgalaxy.modernized.dto.screen.CactupaScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenField;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import com.gitgalaxy.modernized.entity.vsam.AccountRecord;
import com.gitgalaxy.modernized.entity.vsam.CardXrefRecord;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.entity.vsam.CustomerRecord;
import com.gitgalaxy.modernized.exception.*;
import com.gitgalaxy.modernized.repository.vsam.AccountRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CardXrefRecordRepository;
import com.gitgalaxy.modernized.repository.vsam.CustomerRecordRepository;
import com.gitgalaxy.modernized.util.CobolCompare;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * READ at line 3654 tests NORMAL,NOTFND
 * READ at line 3703 tests NORMAL,NOTFND
 * READ at line 3753 tests NORMAL,NOTFND
 * READ at line 3894 tests NORMAL
 * READ at line 3921 tests NORMAL
 * REWRITE at line 4065 tests NORMAL
 * REWRITE at line 4085 tests NORMAL
 * TODO: the RESP of RECEIVE at line 1040 (paragraph 1100-RECEIVE-MAP) is never tested
 * TODO: the RESP of SEND at line 3594 (paragraph 3400-SEND-SCREEN) is never tested
 * TODO: the RESP of SEND at line 4211 (paragraph ABEND-ROUTINE) is never tested
 * Screens (#3619): CactupaScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CoactupcService {

    private static final Logger log = LoggerFactory.getLogger(CoactupcService.class);

    /** CSUTLDTC is a stateless program with no collaborators: the CALL in EDIT-DATE-LE runs it as it is. */
    private static final CsutldtcService CSUTLDTC = new CsutldtcService();

    private final ObjectProvider<Comen01cService> comen01cService;
    private final AccountRecordRepository accountRecordRepository;
    private final CardXrefRecordRepository cardXrefRecordRepository;
    private final CustomerRecordRepository customerRecordRepository;

    // ---- DFHBMSCA / literals ---------------------------------------------------------------------------
    private static final int DFHBMPRF = 0x61;
    private static final int DFHBMFSE = 0xC1;
    private static final int DFHBMASB = 0xF8;
    private static final int DFHBMDAR = 0x4C;
    private static final int DFHRED = 0xF2;
    private static final int DFHDFCOL = 0x00;
    private static final char LV = '\0';

    private static final String LIT_THISPGM = "COACTUPC";
    private static final String LIT_THISTRANID = "CAUP";
    private static final String LIT_THISMAPSET = "COACTUP";   // 'COACTUP ' moved to the X(7) CCARD-NEXT-MAPSET
    private static final String LIT_THISMAP = "CACTUPA";
    private static final String LIT_MENUPGM = "COMEN01C";
    private static final String LIT_MENUTRANID = "CM00";
    private static final String LIT_CCLISTMAPSET = "COCRDLI";
    private static final String CCDA_TITLE01 = "      AWS Mainframe Modernization       ";
    private static final String CCDA_TITLE02 = "              CardDemo                  ";

    // WS-INFO-MSG / WS-RETURN-MSG 88-level values
    private static final String MSG_FOUND_ACCOUNT_DATA = "Details of selected account shown above";
    private static final String MSG_PROMPT_FOR_SEARCH_KEYS = "Enter or update id of account to update";
    private static final String MSG_PROMPT_FOR_CHANGES = "Update account details presented above.";
    private static final String MSG_PROMPT_FOR_CONFIRMATION = "Changes validated.Press F5 to save";
    private static final String MSG_CONFIRM_UPDATE_SUCCESS = "Changes committed to database";
    private static final String MSG_INFORM_FAILURE = "Changes unsuccessful. Please try again";
    private static final String MSG_PROMPT_FOR_ACCT = "Account number not provided";
    private static final String MSG_NO_SEARCH_CRITERIA = "No input received";
    private static final String MSG_NO_CHANGES_DETECTED = "No change detected with respect to values fetched.";
    private static final String MSG_DID_NOT_FIND_ACCT_IN_ACCTDAT = "Did not find this account in account master file";
    private static final String MSG_DID_NOT_FIND_CUST_IN_CUSTDAT = "Did not find associated customer in master file";
    private static final String MSG_COULD_NOT_LOCK_ACCT = "Could not lock account record for update";
    private static final String MSG_COULD_NOT_LOCK_CUST = "Could not lock customer record for update";
    private static final String MSG_DATA_WAS_CHANGED = "Record changed by some one else. Please review";
    private static final String MSG_LOCKED_BUT_UPDATE_FAILED = "Update of record failed";

    // ---- CSLKPCDY lookups --------------------------------------------------------------------------------
    private static Set<String> setOf(String blankSeparated) {
        return new HashSet<>(Arrays.asList(blankSeparated.trim().split("\\s+")));
    }

    /** VALID-GENERAL-PURP-CODE */
    private static final Set<String> GENERAL_PURPOSE_AREA_CODES = setOf(
            "201 202 203 204 205 206 207 208 209 210 212 213 214 215 216 217 218 219 220 223 224 225 226 228 229 231 "
          + "234 236 239 240 242 246 248 249 250 251 252 253 254 256 260 262 264 267 268 269 270 272 276 279 281 284 289 "
          + "301 302 303 304 305 306 307 308 309 310 312 313 314 315 316 317 318 319 320 321 323 325 326 330 331 332 334 "
          + "336 337 339 340 341 343 345 346 347 351 352 360 361 364 365 367 368 380 385 386 "
          + "401 402 403 404 405 406 407 408 409 410 412 413 414 415 416 417 418 419 423 424 425 430 431 432 434 435 437 "
          + "438 440 441 442 443 445 447 448 450 458 463 464 469 470 473 474 475 478 479 480 484 "
          + "501 502 503 504 505 506 507 508 509 510 512 513 514 515 516 517 518 519 520 530 531 534 539 540 541 548 551 "
          + "559 561 562 563 564 567 570 571 572 573 574 575 579 580 581 582 585 586 587 "
          + "601 602 603 604 605 606 607 608 609 610 612 613 614 615 616 617 618 619 620 623 626 628 629 630 631 636 639 "
          + "640 641 646 647 649 650 651 656 657 658 659 660 661 662 664 667 669 670 671 672 678 680 681 682 683 684 689 "
          + "701 702 703 704 705 706 707 708 709 712 713 714 715 716 717 718 719 720 721 724 725 726 727 731 732 734 737 "
          + "740 742 743 747 753 754 757 758 760 762 763 765 767 769 770 771 772 773 774 775 778 779 780 781 782 784 785 "
          + "786 787 "
          + "801 802 803 804 805 806 807 808 809 810 812 813 814 815 816 817 818 819 820 825 826 828 829 830 831 832 838 "
          + "839 840 843 845 847 848 849 850 854 856 857 858 859 860 862 863 864 865 867 868 869 870 872 873 876 878 "
          + "901 902 903 904 905 906 907 908 909 910 912 913 914 915 916 917 918 919 920 925 928 929 930 931 934 936 937 "
          + "938 939 940 941 943 945 947 948 949 951 952 954 956 959 970 971 972 973 978 979 980 983 984 985 986 989");

    /** VALID-US-STATE-CODE */
    private static final Set<String> US_STATE_CODES = setOf(
            "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
          + "OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC AS GU MP PR VI");

    /** VALID-US-STATE-ZIP-CD2-COMBO */
    private static final Set<String> US_STATE_ZIP_COMBOS = setOf(
            "AA34 AE90 AE91 AE92 AE93 AE94 AE95 AE96 AE97 AE98 AK99 AL35 AL36 AP96 AR71 AR72 AS96 AZ85 AZ86 CA90 CA91 "
          + "CA92 CA93 CA94 CA95 CA96 CO80 CO81 CT60 CT61 CT62 CT63 CT64 CT65 CT66 CT67 CT68 CT69 DC20 DC56 DC88 DE19 "
          + "FL32 FL33 FL34 FM96 GA30 GA31 GA39 GU96 HI96 IA50 IA51 IA52 ID83 IL60 IL61 IL62 IN46 IN47 KS66 KS67 KY40 "
          + "KY41 KY42 LA70 LA71 MA10 MA11 MA12 MA13 MA14 MA15 MA16 MA17 MA18 MA19 MA20 MA21 MA22 MA23 MA24 MA25 MA26 "
          + "MA27 MA55 MD20 MD21 ME39 ME40 ME41 ME42 ME43 ME44 ME45 ME46 ME47 ME48 ME49 MH96 MI48 MI49 MN55 MN56 MO63 "
          + "MO64 MO65 MO72 MP96 MS38 MS39 MT59 NC27 NC28 ND58 NE68 NE69 NH30 NH31 NH32 NH33 NH34 NH35 NH36 NH37 NH38 "
          + "NJ70 NJ71 NJ72 NJ73 NJ74 NJ75 NJ76 NJ77 NJ78 NJ79 NJ80 NJ81 NJ82 NJ83 NJ84 NJ85 NJ86 NJ87 NJ88 NJ89 NM87 "
          + "NM88 NV88 NV89 NY50 NY54 NY63 NY10 NY11 NY12 NY13 NY14 OH43 OH44 OH45 OK73 OK74 OR97 PA15 PA16 PA17 PA18 "
          + "PA19 PR60 PR61 PR62 PR63 PR64 PR65 PR66 PR67 PR68 PR69 PR70 PR71 PR72 PR73 PR74 PR75 PR76 PR77 PR78 PR79 "
          + "PR90 PR91 PR92 PR93 PR94 PR95 PR96 PR97 PR98 PW96 RI28 RI29 SC29 SD57 TN37 TN38 TX73 TX75 TX76 TX77 TX78 "
          + "TX79 TX88 UT84 VA20 VA22 VA23 VA24 VI80 VI82 VI83 VI84 VI85 VT50 VT51 VT52 VT53 VT54 VT56 VT57 VT58 VT59 "
          + "WA98 WA99 WI53 WI54 WV24 WV25 WV26 WY82 WY83");

    // ---- screen field widths (symbolic map CACTUPA) -----------------------------------------------------
    private static final Map<String, Integer> FIELD_LENGTH = new LinkedHashMap<>();

    static {
        for (ScreenField f : CactupaScreen.LAYOUT) {
            if (f.name() != null) {
                FIELD_LENGTH.put(f.name(), f.length());
            }
        }
    }

    // ---- WS-NON-KEY-FLAGS layout (one flag byte each; LOW-VALUES = valid, '0' = not ok, 'B' = blank) ----------
    private static final int NK_ACCT_STATUS = 0;
    private static final int NK_CRED_LIMIT = 1;
    private static final int NK_CASH_LIMIT = 2;
    private static final int NK_CURR_BAL = 3;
    private static final int NK_CYC_CREDIT = 4;
    private static final int NK_CYC_DEBIT = 5;
    private static final int NK_DOB = 6;        // year, month, day
    private static final int NK_FICO = 9;
    private static final int NK_OPEN = 10;      // year, month, day
    private static final int NK_EXPIRY = 13;
    private static final int NK_REISSUE = 16;
    private static final int NK_FIRST = 19;
    private static final int NK_MIDDLE = 20;
    private static final int NK_LAST = 21;
    private static final int NK_ADDR1 = 22;
    private static final int NK_ADDR2 = 23;
    private static final int NK_CITY = 24;
    private static final int NK_STATE = 25;
    private static final int NK_ZIP = 26;
    private static final int NK_COUNTRY = 27;
    private static final int NK_PHONE1 = 28;    // A, B, C
    private static final int NK_PHONE2 = 31;
    private static final int NK_EFT = 34;
    private static final int NK_PRI = 35;
    private static final int NK_LEN = 36;

    public void executeCoactupc(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for COACTUPC");
        // COACTUPC is a pseudo-conversational CICS transaction: its logic is runTask(CicsTask), one task per call.
    }

    /** A CICS transaction entered the program. TODO: [AI AGENT] implement from the program's business rules. */
    public CoactupcCommarea handleTransaction(String transid, CoactupcCommarea request) {
        log.info("Coactupc: handleTransaction");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): paragraph 0000-MAIN and everything it performs. */
    public void runTask(CicsTask task) {
        log.info("Coactupc: runTask");
        new Run(task).main();
    }

    /** Another program LINKed / XCTLed to this one. TODO: [AI AGENT] implement from the program's business rules. */
    public CoactupcCommarea handleLink(CoactupcCommarea request) {
        log.info("Coactupc: handleLink");
        return request;
    }

    /** XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COACTUPC.cbl:956: the target is data-driven. Candidates: COMEN01C (moves).
     *  Also MOVEd from CDEMO-FROM-PROGRAM, whose content is not known statically: those names reach the default branch.
     *  Dynamic call targets field testing: open (5 public / 0 private estates). */
    public Object dispatchCdemoToProgramL956(String program, Object request) {
        switch (program.trim().toUpperCase(Locale.ROOT)) {
            case "COMEN01C":
                return comen01cService.getObject().handleLink((CarddemoCommarea) request);
            default:
                throw new IllegalArgumentException("XCTL PROGRAM(CDEMO-TO-PROGRAM) at app/cbl/COACTUPC.cbl:956: no known target " + program);
        }
    }

    /** AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS as CICS file ACCTDAT at app/cbl/COACTUPC.cbl:3703, 3894, 4065; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<AccountRecord> readAcctdat(Long key) {
        return accountRecordRepository.findById(key);
    }

    public AccountRecord rewriteAcctdat(AccountRecord record) {
        return accountRecordRepository.save(record);
    }

    /** AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS as CICS file CXACAIX at app/cbl/COACTUPC.cbl:3654; VSAM defines field testing: open (3 public / 0 private estates). */
    public List<CardXrefRecord> readCxacaix(Long xrefAcctId) {
        return cardXrefRecordRepository.findByXrefAcctId(xrefAcctId);
    }

    /** AWS.M2.CARDDEMO.CUSTDATA.VSAM.KSDS as CICS file CUSTDAT at app/cbl/COACTUPC.cbl:3753, 3921, 4085; VSAM defines field testing: open (3 public / 0 private estates). */
    public Optional<CustomerRecord> readCustdat(Integer key) {
        return customerRecordRepository.findById(key);
    }

    public CustomerRecord rewriteCustdat(CustomerRecord record) {
        return customerRecordRepository.save(record);
    }

    /**
     * EXEC CICS SYNCPOINT at app/cbl/COACTUPC.cbl:952 (paragraph 0000-MAIN).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * commits the work so far and starts a new unit of work; in Spring, split the work at this point into separate @Transactional calls (TransactionTemplate).
     * The task's SYNCPOINT is task.syncpoint() in runTask (0000-MAIN, PF3 branch): the unit of work is the task's.
     */
    public void commitPointL952() {
        log.info("EXEC CICS SYNCPOINT at line 952");
    }

    /**
     * EXEC CICS SYNCPOINT ROLLBACK at app/cbl/COACTUPC.cbl:4099 (paragraph 9600-WRITE-PROCESSING): rolls the unit of work back.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     */
    public void rollbackL4099() {
        throw new UnitOfWorkRollbackException("COACTUPC", "app/cbl/COACTUPC.cbl:4099");
    }

    /**
     * EXEC CICS HANDLE ABEND at app/cbl/COACTUPC.cbl:862 (paragraph 0000-MAIN) routes abends to ABEND-ROUTINE.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * runTask does the routing itself (task.handleAbend / abendOnCondition -> Run.abendRoutine, which has the task
     * to SEND on); this hook only shows what ABEND-ROUTINE would put in ABEND-DATA for the abend it is handed.
     */
    public void onAbendL862(CicsAbendException e) {
        log.info("HANDLE ABEND LABEL ABEND-ROUTINE at line 862: {}", abendData(fit("", 4), fit("", 50), fit("", 72)), e);
    }

    /**
     * EXEC CICS HANDLE ABEND at app/cbl/COACTUPC.cbl:4218 (paragraph ABEND-ROUTINE) routes abends to None.
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * It is HANDLE ABEND CANCEL (no label): no exit is active while ABEND-ROUTINE ends the task with ABEND 9999.
     */
    public void onAbendL4218(CicsAbendException e) {
        log.info("HANDLE ABEND CANCEL at line 4218: the task ends with ABCODE 9999", e);
    }

    /**
     * EXEC CICS ABEND ABCODE(9999) at app/cbl/COACTUPC.cbl:4222 (paragraph paragraph).
     * Units of work and handlers field testing: field-tested (6 public / 0 private estates).
     * Note: resolved at run time if an identifier.
     */
    public void abendLegacy9999L4222() {
        throw new CicsAbendException("9999", "COACTUPC", "app/cbl/COACTUPC.cbl:4222");
    }

    /** SEND MAP(CACTUPA) MAPSET(COACTUP) FROM(CACTUPAO) at app/cbl/COACTUPC.cbl:3594 (#3619).
     *  Run.sendMap builds CACTUPAO (3100 .. 3390) and SENDs it through the task.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public CactupaScreen renderCactupa(CactupaScreen screen) {
        return screen;
    }

    /** RECEIVE MAP(CACTUPA) MAPSET(COACTUP) INTO(CACTUPAI) at app/cbl/COACTUPC.cbl:1040 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  The task is runTask: Run.receiveMap reads CACTUPAI after the RECEIVE.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitCactupa(CactupaScreen input, String aid) {
        return renderCactupa(input);
    }

    // =====================================================================================================
    // COBOL storage helpers
    // =====================================================================================================

    /** MOVE to PIC X(n): padded with spaces or truncated on the right. */
    private static String fit(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    /**
     * A COMMAREA item PIC X(n) that a PIC 9(n) item redefines (an id, the SSN, the FICO score), as the DTO hands it
     * over: a number the DTO carries without its leading zeros ("24") is the zero filled digits it was stored as.
     */
    private static String numX(String v, int n) {
        if (v != null && !v.isEmpty() && v.length() < n && isNumeric(v)) {
            return "0".repeat(n - v.length()) + v;
        }
        return fit(v, n);
    }

    private static String sp(int n) {
        return " ".repeat(n);
    }

    private static String lv(int n) {
        return String.valueOf(LV).repeat(n);
    }

    private static boolean isAll(String s, char c) {
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) != c) {
                return false;
            }
        }
        return true;
    }

    /** IF x EQUAL LOW-VALUES OR x EQUAL SPACES */
    private static boolean lvOrSpaces(String s) {
        return isAll(s, LV) || isAll(s, ' ');
    }

    /** FUNCTION TRIM: leading and trailing spaces only. */
    private static String trim(String s) {
        int b = 0;
        int e = s.length();
        while (b < e && s.charAt(b) == ' ') {
            b++;
        }
        while (e > b && s.charAt(e - 1) == ' ') {
            e--;
        }
        return s.substring(b, e);
    }

    private static String stripTrailing(String s) {
        int e = s.length();
        while (e > 0 && s.charAt(e - 1) == ' ') {
            e--;
        }
        return s.substring(0, e);
    }

    /** IF x = '*' OR x = SPACES */
    private static boolean starOrSpaces(String v) {
        String t = stripTrailing(v);
        return t.isEmpty() || t.equals("*");
    }

    /** IS NUMERIC on an alphanumeric item: every character a digit. */
    private static boolean isNumeric(String s) {
        if (s.isEmpty()) {
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

    /** The value of an unsigned PIC 9(n) DISPLAY item laid over `s`: each byte's low nibble is its digit. */
    private static long numView(String s) {
        long v = 0;
        for (int i = 0; i < s.length(); i++) {
            v = v * 10 + (s.charAt(i) & 0x0F);
        }
        return v;
    }

    /** MOVE of a number to PIC 9(n): its low-order n digits, zero filled. */
    private static String digits(long value, int n) {
        String s = Long.toString(Math.abs(value));
        return s.length() > n ? s.substring(s.length() - n) : "0".repeat(n - s.length()) + s;
    }

    /** (pos:len) with a 1-based pos. */
    private static String sub(String s, int pos, int len) {
        return s.substring(pos - 1, pos - 1 + len);
    }

    /** MOVE v TO s(pos:len). */
    private static String put(String s, int pos, int len, String v) {
        return s.substring(0, pos - 1) + fit(v, len) + s.substring(pos - 1 + len);
    }

    /** MOVE alphanumeric TO unsigned PIC 9(size) DISPLAY (GnuCOBOL's cob_move_alphanum_to_display, no decimals). */
    private static String moveAlnumToNumeric(String src, int size) {
        char[] out = new char[size];
        Arrays.fill(out, '0');
        int s1 = 0;
        int e1 = src.length();
        while (s1 < e1 && Character.isWhitespace(src.charAt(s1))) {
            s1++;
        }
        if (s1 < e1 && (src.charAt(s1) == '+' || src.charAt(s1) == '-')) {
            s1++;
        }
        int count = 0;
        for (int p = s1; p < e1 && src.charAt(p) != '.'; p++) {
            if (src.charAt(p) >= '0' && src.charAt(p) <= '9') {
                count++;
            }
        }
        int s2;
        if (count < size) {
            s2 = size - count;
        } else {
            s2 = 0;
            for (; count > size; s1++) {
                if (src.charAt(s1) >= '0' && src.charAt(s1) <= '9') {
                    count--;
                }
            }
        }
        int points = 0;
        for (; s1 < e1 && s2 < size; s1++) {
            char c = src.charAt(s1);
            if (c >= '0' && c <= '9') {
                out[s2++] = c;
            } else if (c == '.') {
                if (points++ > 0) {
                    return fit(src, size);
                }
            } else if (!(Character.isWhitespace(c) || c == ',')) {
                return fit(src, size);
            }
        }
        return new String(out);
    }

    /** FUNCTION TEST-NUMVAL / TEST-NUMVAL-C: 0 when valid, else the position of the first bad character. */
    private static int testNumval(String s, boolean currencyForm) {
        int size = s.length();
        int n = 0;
        boolean plusMinus = false;
        for (; n < size; n++) {
            char c = s.charAt(n);
            boolean stop = false;
            if (c >= '0' && c <= '9') {
                stop = true;
            } else if (c == ' ') {
                continue;
            } else if (c == '+' || c == '-') {
                if (plusMinus) {
                    return n + 1;
                }
                plusMinus = true;
                continue;
            } else if (c == '.') {
                stop = true;
            } else if (c == '$' && currencyForm) {
                continue;                                 // the default currency symbol before the number
            } else {
                return n + 1;
            }
            if (stop) {
                break;
            }
        }
        if (n == size) {
            return n + 1;
        }
        int digits = 0;
        boolean decSeen = false;
        boolean spaceSeen = false;
        for (; n < size; n++) {
            char c = s.charAt(n);
            if (c >= '0' && c <= '9') {
                if (++digits > 38 || spaceSeen) {
                    return n + 1;
                }
            } else if (c == ',' || c == '.') {
                if (decSeen || spaceSeen) {
                    return n + 1;
                }
                if (c == '.') {
                    decSeen = true;
                } else if (!currencyForm) {
                    return n + 1;
                }
            } else if (c == ' ') {
                spaceSeen = true;
            } else if (c == '+' || c == '-') {
                if (plusMinus) {
                    return n + 1;
                }
                plusMinus = true;
            } else if (c == 'C' || c == 'D') {
                if (plusMinus) {
                    return n + 1;
                }
                char next = c == 'C' ? 'R' : 'B';
                if (n < size - 1 && s.charAt(n + 1) == next) {
                    plusMinus = true;
                    n++;
                } else {
                    return n + 2;
                }
            } else {
                return n + 1;
            }
        }
        if (digits == 0) {
            return n + 1;
        }
        return 0;
    }

    /** FUNCTION NUMVAL / NUMVAL-C of a text TEST-NUMVAL(-C) accepted (commas of NUMVAL-C dropped). */
    private static BigDecimal numval(String s) {
        return CobolRecords.numval(s.replace(",", "").replace("$", ""), '.');
    }

    private String zoned12(BigDecimal v) {
        byte[] b = new byte[12];
        CobolRecords.putZoned(b, 0, 12, 2, true, v, CobolRecords.charset());
        return new String(b, CobolRecords.charset());
    }

    /** The S9(10)V99 DISPLAY value laid over an X(12) item. */
    private BigDecimal z12(String s) {
        byte[] b = fit(s, 12).getBytes(CobolRecords.charset());
        BigDecimal v = CobolRecords.zoned(b, 0, 12, 2, CobolRecords.charset());
        return v == null ? BigDecimal.ZERO : v;
    }

    /** MOVE a S9(10)V99 value to +ZZZ,ZZZ,ZZZ.99 (WS-EDIT-CURRENCY-9-2-F). */
    private static String currencyEdited(BigDecimal v) {
        BigDecimal scaled = v.setScale(2, RoundingMode.DOWN);
        BigDecimal mag = scaled.abs().remainder(new BigDecimal("1000000000"));
        BigDecimal signed = scaled.signum() < 0 ? mag.negate() : mag;
        return CobolEdit.format("+ZZZ,ZZZ,ZZZ.99", signed, false, null);
    }

    private static boolean same(String a, String b) {
        return CobolCompare.eq(a, b);
    }

    private static String abendData(String code, String reason, String msg) {
        return fit(code, 4) + fit(LIT_THISPGM, 8) + fit(reason, 50) + fit(msg, 72);
    }

    // =====================================================================================================
    // The task
    // =====================================================================================================

    private final class Run {
        private final CicsTask task;
        private final Charset cs = CobolRecords.charset();
        private boolean ended;
        private Map<String, String> in = Map.of();

        // CARDDEMO-COMMAREA (COCOM01Y)
        private String cdFromTranid = sp(4);
        private String cdFromProgram = sp(8);
        private String cdToTranid = sp(4);
        private String cdToProgram = sp(8);
        private String cdUserId = sp(8);
        private String cdUserType = sp(1);
        private int cdPgmContext = 0;
        private int cdCustId = 0;
        private String cdCustFname = sp(25);
        private String cdCustMname = sp(25);
        private String cdCustLname = sp(25);
        private long cdAcctId = 0;
        private String cdAcctStatus = sp(1);
        private long cdCardNum = 0;
        private String cdLastMap = sp(7);
        private String cdLastMapset = sp(7);

        // WS-THIS-PROGCOMMAREA
        private String action = LV + "";
        private String oAcctIdX, oStatus, oBal, oCredit, oCash, oOpen, oExp, oReis, oCyCr, oCyDb, oGrp;
        private String oCustIdX, oFirst, oMid, oLast, oAd1, oAd2, oAd3, oState, oCtry, oZip, oPh1, oPh2;
        private String oSsnX, oGovt, oDob, oEft, oPri, oFico;
        private String nAcctIdX, nStatus, nBal, nCredit, nCash, nOpen, nExp, nReis, nCyCr, nCyDb, nGrp;
        private String nCustIdX, nFirst, nMid, nLast, nAd1, nAd2, nAd3, nState, nCtry, nZip, nPh1, nPh2;
        private String nSsn1, nSsn2, nSsn3, nGovt, nDob, nEft, nPri, nFico;

        // CC-WORK-AREA
        private String ccAid = sp(5);
        private String ccAcctId = sp(11);

        // WS-MISC-STORAGE
        private Misc m = new Misc();

        // ACCOUNT-RECORD / CARD-XREF-RECORD / CUSTOMER-RECORD: the program's own copies (never reset)
        private AccountRecord acct = blankAccount();
        private CardXrefRecord xref = blankXref();
        private CustomerRecord cust = blankCustomer();

        // CACTUPAO and the subfields of CACTUPAI / CACTUPAO
        private final Map<String, String> out = new LinkedHashMap<>();
        private CicsTask.MapSubfields sub = new CicsTask.MapSubfields();

        Run(CicsTask task) {
            this.task = task;
            initProg();
        }

        /** WS-MISC-STORAGE after INITIALIZE: alphanumerics spaces, numerics zero. */
        private final class Misc {
            String tranid = sp(4);
            String editVarName = sp(25);
            String editSignedX = sp(15);
            char signedFlag = ' ';
            String editAlnum = sp(256);
            int editAlnumLen = 0;
            char alphaFlag = ' ';
            char alnumFlag = ' ';
            char mandFlag = ' ';
            char yesNo = ' ';
            String phoneNum = sp(15);
            char[] phoneFlgs = {' ', ' ', ' '};
            String ssnPart1 = sp(3);
            char[] ssnFlgs = {' ', ' ', ' '};
            String dateCcyymmdd = sp(8);
            char[] dateFlgs = {' ', ' ', ' '};
            char dataChanged = ' ';
            char inputFlag = ' ';
            char acctFlag = ' ';
            char custFlag = ' ';
            char[] nk = filledFlags();
            String creditX = sp(15);
            String cashX = sp(15);
            String balX = sp(15);
            String cycCrX = sp(15);
            String cycDbX = sp(15);
            String infoMsg = sp(40);
            String returnMsg = sp(75);
            char acctReadFlag = ' ';
            char custReadFlag = ' ';
            int respCd = 0;
            int reasCd = 0;
            String errorOpname = sp(8);
            String errorFile = sp(9);
            String errorResp = sp(10);
            String errorResp2 = sp(10);
            String ridAcctIdX = sp(11);
            String ridCustIdX = sp(9);
            String abendCode = sp(4);
            String abendReason = sp(50);
            String abendMsg = sp(72);
        }

        private char[] filledFlags() {
            char[] f = new char[NK_LEN];
            Arrays.fill(f, ' ');
            return f;
        }

        // ---------------------------------------------------------------------------------------------
        // state helpers
        // ---------------------------------------------------------------------------------------------

        private AccountRecord blankAccount() {
            AccountRecord a = new AccountRecord();
            a.setAcctId(0L);
            a.setAcctActiveStatus(" ");
            a.setAcctCurrBal(BigDecimal.ZERO);
            a.setAcctCreditLimit(BigDecimal.ZERO);
            a.setAcctCashCreditLimit(BigDecimal.ZERO);
            a.setAcctOpenDate(sp(10));
            a.setAcctExpiraionDate(sp(10));
            a.setAcctReissueDate(sp(10));
            a.setAcctCurrCycCredit(BigDecimal.ZERO);
            a.setAcctCurrCycDebit(BigDecimal.ZERO);
            a.setAcctAddrZip(sp(10));
            a.setAcctGroupId(sp(10));
            return a;
        }

        private CardXrefRecord blankXref() {
            CardXrefRecord x = new CardXrefRecord();
            x.setXrefCardNum(sp(16));
            x.setXrefCustId(0);
            x.setXrefAcctId(0L);
            return x;
        }

        private CustomerRecord blankCustomer() {
            CustomerRecord c = new CustomerRecord();
            c.setCustId(0);
            c.setCustFirstName(sp(25));
            c.setCustMiddleName(sp(25));
            c.setCustLastName(sp(25));
            c.setCustAddrLine1(sp(50));
            c.setCustAddrLine2(sp(50));
            c.setCustAddrLine3(sp(50));
            c.setCustAddrStateCd(sp(2));
            c.setCustAddrCountryCd(sp(3));
            c.setCustAddrZip(sp(10));
            c.setCustPhoneNum1(sp(15));
            c.setCustPhoneNum2(sp(15));
            c.setCustSsn(0);
            c.setCustGovtIssuedId(sp(20));
            c.setCustDobYyyyMmDd(sp(10));
            c.setCustEftAccountId(sp(10));
            c.setCustPriCardHolderInd(" ");
            c.setCustFicoCreditScore(0);
            return c;
        }

        /** INITIALIZE WS-THIS-PROGCOMMAREA (an alphanumeric item is spaces: its VALUE LOW-VALUES is not used). */
        private void initProg() {
            action = sp(1);
            initOld();
            initNew();
        }

        /** INITIALIZE ACUP-OLD-DETAILS */
        private void initOld() {
            oAcctIdX = sp(11);
            oStatus = sp(1);
            oBal = sp(12);
            oCredit = sp(12);
            oCash = sp(12);
            oOpen = sp(8);
            oExp = sp(8);
            oReis = sp(8);
            oCyCr = sp(12);
            oCyDb = sp(12);
            oGrp = sp(10);
            oCustIdX = sp(9);
            oFirst = sp(25);
            oMid = sp(25);
            oLast = sp(25);
            oAd1 = sp(50);
            oAd2 = sp(50);
            oAd3 = sp(50);
            oState = sp(2);
            oCtry = sp(3);
            oZip = sp(10);
            oPh1 = sp(15);
            oPh2 = sp(15);
            oSsnX = sp(9);
            oGovt = sp(20);
            oDob = sp(8);
            oEft = sp(10);
            oPri = sp(1);
            oFico = sp(3);
        }

        /** INITIALIZE ACUP-NEW-DETAILS */
        private void initNew() {
            nAcctIdX = sp(11);
            nStatus = sp(1);
            nBal = sp(12);
            nCredit = sp(12);
            nCash = sp(12);
            nOpen = sp(8);
            nExp = sp(8);
            nReis = sp(8);
            nCyCr = sp(12);
            nCyDb = sp(12);
            nGrp = sp(10);
            nCustIdX = sp(9);
            nFirst = sp(25);
            nMid = sp(25);
            nLast = sp(25);
            nAd1 = sp(50);
            nAd2 = sp(50);
            nAd3 = sp(50);
            nState = sp(2);
            nCtry = sp(3);
            nZip = sp(10);
            nPh1 = sp(15);
            nPh2 = sp(15);
            nSsn1 = sp(3);
            nSsn2 = sp(2);
            nSsn3 = sp(4);
            nGovt = sp(20);
            nDob = sp(8);
            nEft = sp(10);
            nPri = sp(1);
            nFico = sp(3);
        }

        private String nSsnX() {
            return nSsn1 + nSsn2 + nSsn3;
        }

        /** MOVE DFHCOMMAREA(...) TO CARDDEMO-COMMAREA / WS-THIS-PROGCOMMAREA */
        private void loadCommarea(CoactupcCommarea ca) {
            CarddemoCommarea c = ca == null ? null : ca.getCarddemoCommarea();
            if (c != null) {
                cdFromTranid = fit(c.getCdemoFromTranid(), 4);
                cdFromProgram = fit(c.getCdemoFromProgram(), 8);
                cdToTranid = fit(c.getCdemoToTranid(), 4);
                cdToProgram = fit(c.getCdemoToProgram(), 8);
                cdUserId = fit(c.getCdemoUserId(), 8);
                cdUserType = fit(c.getCdemoUserType(), 1);
                cdPgmContext = c.getCdemoPgmContext() == null ? 0 : c.getCdemoPgmContext();
                cdCustId = c.getCdemoCustId() == null ? 0 : c.getCdemoCustId();
                cdCustFname = fit(c.getCdemoCustFname(), 25);
                cdCustMname = fit(c.getCdemoCustMname(), 25);
                cdCustLname = fit(c.getCdemoCustLname(), 25);
                cdAcctId = c.getCdemoAcctId() == null ? 0 : c.getCdemoAcctId();
                cdAcctStatus = fit(c.getCdemoAcctStatus(), 1);
                cdCardNum = c.getCdemoCardNum() == null ? 0 : c.getCdemoCardNum();
                cdLastMap = fit(c.getCdemoLastMap(), 7);
                cdLastMapset = fit(c.getCdemoLastMapset(), 7);
            }
            CoactupcWsThisProgcommarea w = ca == null ? null : ca.getWsThisProgcommarea();
            if (w == null) {
                // the bytes past the caller's COMMAREA: not supplied
                initProg();
                action = LV + "";
                return;
            }
            action = fit(w.getAcupChangeAction(), 1);
            oAcctIdX = numX(w.getAcupOldAcctIdX(), 11);
            oStatus = fit(w.getAcupOldActiveStatus(), 1);
            oBal = fit(w.getAcupOldCurrBal(), 12);
            oCredit = fit(w.getAcupOldCreditLimit(), 12);
            oCash = fit(w.getAcupOldCashCreditLimit(), 12);
            oOpen = fit(w.getAcupOldOpenDate(), 8);
            oExp = fit(w.getAcupOldExpiraionDate(), 8);
            oReis = fit(w.getAcupOldReissueDate(), 8);
            oCyCr = fit(w.getAcupOldCurrCycCredit(), 12);
            oCyDb = fit(w.getAcupOldCurrCycDebit(), 12);
            oGrp = fit(w.getAcupOldGroupId(), 10);
            oCustIdX = numX(w.getAcupOldCustIdX(), 9);
            oFirst = fit(w.getAcupOldCustFirstName(), 25);
            oMid = fit(w.getAcupOldCustMiddleName(), 25);
            oLast = fit(w.getAcupOldCustLastName(), 25);
            oAd1 = fit(w.getAcupOldCustAddrLine1(), 50);
            oAd2 = fit(w.getAcupOldCustAddrLine2(), 50);
            oAd3 = fit(w.getAcupOldCustAddrLine3(), 50);
            oState = fit(w.getAcupOldCustAddrStateCd(), 2);
            oCtry = fit(w.getAcupOldCustAddrCountryCd(), 3);
            oZip = fit(w.getAcupOldCustAddrZip(), 10);
            oPh1 = fit(w.getAcupOldCustPhoneNum1(), 15);
            oPh2 = fit(w.getAcupOldCustPhoneNum2(), 15);
            oSsnX = numX(w.getAcupOldCustSsnX(), 9);
            oGovt = fit(w.getAcupOldCustGovtIssuedId(), 20);
            oDob = fit(w.getAcupOldCustDobYyyyMmDd(), 8);
            oEft = fit(w.getAcupOldCustEftAccountId(), 10);
            oPri = fit(w.getAcupOldCustPriHolderInd(), 1);
            oFico = numX(w.getAcupOldCustFicoScoreX(), 3);
            nAcctIdX = numX(w.getAcupNewAcctIdX(), 11);
            nStatus = fit(w.getAcupNewActiveStatus(), 1);
            nBal = fit(w.getAcupNewCurrBal(), 12);
            nCredit = fit(w.getAcupNewCreditLimit(), 12);
            nCash = fit(w.getAcupNewCashCreditLimit(), 12);
            nOpen = fit(w.getAcupNewOpenDate(), 8);
            nExp = fit(w.getAcupNewExpiraionDate(), 8);
            nReis = fit(w.getAcupNewReissueDate(), 8);
            nCyCr = fit(w.getAcupNewCurrCycCredit(), 12);
            nCyDb = fit(w.getAcupNewCurrCycDebit(), 12);
            nGrp = fit(w.getAcupNewGroupId(), 10);
            nCustIdX = numX(w.getAcupNewCustIdX(), 9);
            nFirst = fit(w.getAcupNewCustFirstName(), 25);
            nMid = fit(w.getAcupNewCustMiddleName(), 25);
            nLast = fit(w.getAcupNewCustLastName(), 25);
            nAd1 = fit(w.getAcupNewCustAddrLine1(), 50);
            nAd2 = fit(w.getAcupNewCustAddrLine2(), 50);
            nAd3 = fit(w.getAcupNewCustAddrLine3(), 50);
            nState = fit(w.getAcupNewCustAddrStateCd(), 2);
            nCtry = fit(w.getAcupNewCustAddrCountryCd(), 3);
            nZip = fit(w.getAcupNewCustAddrZip(), 10);
            nPh1 = fit(w.getAcupNewCustPhoneNum1(), 15);
            nPh2 = fit(w.getAcupNewCustPhoneNum2(), 15);
            nSsn1 = numX(w.getAcupNewCustSsn1(), 3);
            nSsn2 = numX(w.getAcupNewCustSsn2(), 2);
            nSsn3 = numX(w.getAcupNewCustSsn3(), 4);
            nGovt = fit(w.getAcupNewCustGovtIssuedId(), 20);
            nDob = fit(w.getAcupNewCustDobYyyyMmDd(), 8);
            nEft = fit(w.getAcupNewCustEftAccountId(), 10);
            nPri = fit(w.getAcupNewCustPriHolderInd(), 1);
            nFico = numX(w.getAcupNewCustFicoScoreX(), 3);
        }

        private CarddemoCommarea carddemoDto() {
            CarddemoCommarea c = new CarddemoCommarea();
            c.setCdemoFromTranid(fit(cdFromTranid, 4));
            c.setCdemoFromProgram(fit(cdFromProgram, 8));
            c.setCdemoToTranid(fit(cdToTranid, 4));
            c.setCdemoToProgram(fit(cdToProgram, 8));
            c.setCdemoUserId(fit(cdUserId, 8));
            c.setCdemoUserType(fit(cdUserType, 1));
            c.setCdemoPgmContext(cdPgmContext);
            c.setCdemoCustId(cdCustId);
            c.setCdemoCustFname(fit(cdCustFname, 25));
            c.setCdemoCustMname(fit(cdCustMname, 25));
            c.setCdemoCustLname(fit(cdCustLname, 25));
            c.setCdemoAcctId(cdAcctId);
            c.setCdemoAcctStatus(fit(cdAcctStatus, 1));
            c.setCdemoCardNum(cdCardNum);
            c.setCdemoLastMap(fit(cdLastMap, 7));
            c.setCdemoLastMapset(fit(cdLastMapset, 7));
            return c;
        }

        private CoactupcWsThisProgcommarea progDto() {
            CoactupcWsThisProgcommarea w = new CoactupcWsThisProgcommarea();
            w.setAcupChangeAction(fit(action, 1));
            w.setAcupOldAcctIdX(oAcctIdX);
            w.setAcupOldActiveStatus(oStatus);
            w.setAcupOldCurrBal(oBal);
            w.setAcupOldCreditLimit(oCredit);
            w.setAcupOldCashCreditLimit(oCash);
            w.setAcupOldOpenDate(oOpen);
            w.setAcupOldExpiraionDate(oExp);
            w.setAcupOldReissueDate(oReis);
            w.setAcupOldCurrCycCredit(oCyCr);
            w.setAcupOldCurrCycDebit(oCyDb);
            w.setAcupOldGroupId(oGrp);
            w.setAcupOldCustIdX(oCustIdX);
            w.setAcupOldCustFirstName(oFirst);
            w.setAcupOldCustMiddleName(oMid);
            w.setAcupOldCustLastName(oLast);
            w.setAcupOldCustAddrLine1(oAd1);
            w.setAcupOldCustAddrLine2(oAd2);
            w.setAcupOldCustAddrLine3(oAd3);
            w.setAcupOldCustAddrStateCd(oState);
            w.setAcupOldCustAddrCountryCd(oCtry);
            w.setAcupOldCustAddrZip(oZip);
            w.setAcupOldCustPhoneNum1(oPh1);
            w.setAcupOldCustPhoneNum2(oPh2);
            w.setAcupOldCustSsnX(oSsnX);
            w.setAcupOldCustGovtIssuedId(oGovt);
            w.setAcupOldCustDobYyyyMmDd(oDob);
            w.setAcupOldCustEftAccountId(oEft);
            w.setAcupOldCustPriHolderInd(oPri);
            w.setAcupOldCustFicoScoreX(oFico);
            w.setAcupNewAcctIdX(nAcctIdX);
            w.setAcupNewActiveStatus(nStatus);
            w.setAcupNewCurrBal(nBal);
            w.setAcupNewCreditLimit(nCredit);
            w.setAcupNewCashCreditLimit(nCash);
            w.setAcupNewOpenDate(nOpen);
            w.setAcupNewExpiraionDate(nExp);
            w.setAcupNewReissueDate(nReis);
            w.setAcupNewCurrCycCredit(nCyCr);
            w.setAcupNewCurrCycDebit(nCyDb);
            w.setAcupNewGroupId(nGrp);
            w.setAcupNewCustIdX(nCustIdX);
            w.setAcupNewCustFirstName(nFirst);
            w.setAcupNewCustMiddleName(nMid);
            w.setAcupNewCustLastName(nLast);
            w.setAcupNewCustAddrLine1(nAd1);
            w.setAcupNewCustAddrLine2(nAd2);
            w.setAcupNewCustAddrLine3(nAd3);
            w.setAcupNewCustAddrStateCd(nState);
            w.setAcupNewCustAddrCountryCd(nCtry);
            w.setAcupNewCustAddrZip(nZip);
            w.setAcupNewCustPhoneNum1(nPh1);
            w.setAcupNewCustPhoneNum2(nPh2);
            w.setAcupNewCustSsn1(nSsn1);
            w.setAcupNewCustSsn2(nSsn2);
            w.setAcupNewCustSsn3(nSsn3);
            w.setAcupNewCustGovtIssuedId(nGovt);
            w.setAcupNewCustDobYyyyMmDd(nDob);
            w.setAcupNewCustEftAccountId(nEft);
            w.setAcupNewCustPriHolderInd(nPri);
            w.setAcupNewCustFicoScoreX(nFico);
            return w;
        }

        // 88-levels of ACUP-CHANGE-ACTION
        private boolean notFetched() {
            return action.charAt(0) == LV || action.charAt(0) == ' ';
        }

        private boolean act(String values) {
            return values.indexOf(action.charAt(0)) >= 0;
        }

        private boolean showDetails() {
            return act("S");
        }

        private boolean changesMade() {
            return act("ENCLF");
        }

        private boolean changesNotOk() {
            return act("E");
        }

        private boolean changesOkNotConfirmed() {
            return act("N");
        }

        private boolean changesOkayedAndDone() {
            return act("C");
        }

        private boolean changesFailed() {
            return act("LF");
        }

        // 88-levels of CCARD-AID
        private boolean aid(String v) {
            return ccAid.equals(v);
        }

        // 88-levels of WS-RETURN-MSG / WS-INFO-MSG
        private boolean msgOff() {
            return isAll(m.returnMsg, ' ');
        }

        private boolean retMsgIs(String v) {
            return m.returnMsg.equals(fit(v, 75));
        }

        private boolean infoMsgIs(String v) {
            return m.infoMsg.equals(fit(v, 40));
        }

        private boolean noInfoMessage() {
            return lvOrSpaces(m.infoMsg);
        }

        private boolean inputError() {
            return m.inputFlag == '1';
        }

        private void setInputError() {
            m.inputFlag = '1';
        }

        /** IF WS-RETURN-MSG-OFF STRING ... INTO WS-RETURN-MSG */
        private void err(String text) {
            if (msgOff()) {
                m.returnMsg = fit(text, 75);
            }
        }

        private String varName() {
            return trim(m.editVarName);
        }

        private void setVarName(String name) {
            m.editVarName = fit(name, 25);
        }

        // =============================================================================================
        // 0000-MAIN
        // =============================================================================================
        void main() {
            // EXEC CICS HANDLE ABEND LABEL(ABEND-ROUTINE)
            task.handleAbend("ABEND-ROUTINE");

            // INITIALIZE CC-WORK-AREA WS-MISC-STORAGE WS-COMMAREA: every item starts at its initial value (above).
            m.tranid = fit(LIT_THISTRANID, 4);
            m.returnMsg = sp(75);

            // DEFECT KEPT: CDEMO-FROM-PROGRAM = LIT-MENUPGM is tested here, before CARDDEMO-COMMAREA has been loaded
            // from DFHCOMMAREA, so it is always the initial spaces and the OR is never true (the same condition is
            // tested again, with the loaded value, in the EVALUATE below). One-line fix: move the IF below the MOVEs.
            if (!task.hasCommarea()
                    || (same(cdFromProgram, LIT_MENUPGM) && cdPgmContext != 1)) {
                cdFromTranid = sp(4);
                cdFromProgram = sp(8);
                cdToTranid = sp(4);
                cdToProgram = sp(8);
                cdUserId = sp(8);
                cdUserType = sp(1);
                cdCustId = 0;
                cdCustFname = sp(25);
                cdCustMname = sp(25);
                cdCustLname = sp(25);
                cdAcctId = 0;
                cdAcctStatus = sp(1);
                cdCardNum = 0;
                cdLastMap = sp(7);
                cdLastMapset = sp(7);
                initProg();
                cdPgmContext = 0;                 // SET CDEMO-PGM-ENTER TO TRUE
                action = LV + "";                 // SET ACUP-DETAILS-NOT-FETCHED TO TRUE
            } else {
                loadCommarea(task.commarea(CoactupcCommarea.class));
            }

            // PERFORM YYYY-STORE-PFKEY THRU YYYY-STORE-PFKEY-EXIT
            storePfkey();

            // SET PFK-INVALID TO TRUE ... IF PFK-INVALID SET CCARD-AID-ENTER TO TRUE
            boolean pfkValid = aid("ENTER") || aid("PFK03")
                    || (aid("PFK05") && changesOkNotConfirmed())
                    || (aid("PFK12") && !notFetched());
            if (!pfkValid) {
                ccAid = "ENTER";
            }

            // EVALUATE TRUE
            if (aid("PFK03")) {
                // WHEN CCARD-AID-PFK03
                if (lvOrSpaces(cdFromTranid)) {
                    cdToTranid = fit(LIT_MENUTRANID, 4);
                } else {
                    cdToTranid = cdFromTranid;
                }
                if (lvOrSpaces(cdFromProgram)) {
                    cdToProgram = fit(LIT_MENUPGM, 8);
                } else {
                    cdToProgram = cdFromProgram;
                }
                cdFromTranid = fit(LIT_THISTRANID, 4);
                cdFromProgram = fit(LIT_THISPGM, 8);
                cdUserType = "U";                         // SET CDEMO-USRTYP-USER
                cdPgmContext = 0;                         // SET CDEMO-PGM-ENTER
                cdLastMapset = fit(LIT_THISMAPSET, 7);
                cdLastMap = fit(LIT_THISMAP, 7);

                task.syncpoint();                         // EXEC CICS SYNCPOINT (commitPointL952)
                String resp = task.xctl(trim(cdToProgram), carddemoDto());   // EXEC CICS XCTL PROGRAM(CDEMO-TO-PROGRAM)
                if (!"NORMAL".equals(resp)) {
                    // no RESP clause: the condition takes CICS's default action
                    String label = task.abendOnCondition(resp);
                    if (label != null) {
                        abendRoutine();
                    }
                }
                return;
            } else if ((notFetched() && cdPgmContext == 0)
                    || (same(cdFromProgram, LIT_MENUPGM) && cdPgmContext != 1)) {
                // WHEN ACUP-DETAILS-NOT-FETCHED AND CDEMO-PGM-ENTER / WHEN CDEMO-FROM-PROGRAM = LIT-MENUPGM AND NOT CDEMO-PGM-REENTER
                initProg();
                sendMap();
                cdPgmContext = 1;                         // SET CDEMO-PGM-REENTER
                action = LV + "";                         // SET ACUP-DETAILS-NOT-FETCHED
                commonReturn();
                return;
            } else if (changesOkayedAndDone() || changesFailed()) {
                // WHEN ACUP-CHANGES-OKAYED-AND-DONE / WHEN ACUP-CHANGES-FAILED
                initProg();
                m = new Misc();                           // INITIALIZE WS-MISC-STORAGE
                cdAcctId = 0;                             // INITIALIZE CDEMO-ACCT-ID
                cdPgmContext = 0;
                sendMap();
                cdPgmContext = 1;
                action = LV + "";
                commonReturn();
                return;
            } else {
                // WHEN OTHER
                processInputs();
                decideAction();
                if (ended) {
                    return;
                }
                sendMap();
                commonReturn();
            }
        }

        // COMMON-RETURN
        private void commonReturn() {
            // MOVE WS-RETURN-MSG TO CCARD-ERROR-MSG (CC-WORK-AREA is not part of the COMMAREA)
            CoactupcCommarea ca = new CoactupcCommarea();
            ca.setCarddemoCommarea(carddemoDto());
            ca.setWsThisProgcommarea(progDto());
            task.returnTransid(LIT_THISTRANID, ca, 2000);   // LENGTH(LENGTH OF WS-COMMAREA)
        }

        // YYYY-STORE-PFKEY (CSSTRPFY)
        private void storePfkey() {
            String a = task.aid() == null ? "" : task.aid().trim().toUpperCase(Locale.ROOT);
            switch (a) {
                case "ENTER" -> ccAid = "ENTER";
                case "CLEAR" -> ccAid = "CLEAR";
                case "PA1" -> ccAid = "PA1  ";
                case "PA2" -> ccAid = "PA2  ";
                default -> {
                    if (a.startsWith("PF") && isNumeric(a.substring(2))) {
                        int k = Integer.parseInt(a.substring(2));
                        if (k >= 1 && k <= 24) {
                            ccAid = "PFK" + digits((k - 1) % 12 + 1, 2);
                        }
                    }
                }
            }
        }

        // =============================================================================================
        // 1000-PROCESS-INPUTS
        // =============================================================================================
        private void processInputs() {
            receiveMap();
            editMapInputs();
            // MOVE WS-RETURN-MSG TO CCARD-ERROR-MSG, LIT-THISPGM TO CCARD-NEXT-PROG, LIT-THISMAPSET / LIT-THISMAP
            // TO CCARD-NEXT-MAPSET / CCARD-NEXT-MAP: CC-WORK-AREA fields nothing reads afterwards.
        }

        private String fld(String name, int len) {
            return fit(in.get(name), len);
        }

        /** IF f = '*' OR f = SPACES MOVE LOW-VALUES TO target ELSE MOVE f TO target */
        private String pick(String name, int srcLen, int tgtLen) {
            String v = fld(name, srcLen);
            return starOrSpaces(v) ? lv(tgtLen) : fit(v, tgtLen);
        }

        // 1100-RECEIVE-MAP
        private void receiveMap() {
            // EXEC CICS RECEIVE MAP(LIT-THISMAP) MAPSET(LIT-THISMAPSET) INTO(CACTUPAI) RESP(WS-RESP-CD)
            Optional<CactupaScreen> screen = task.receive(LIT_THISMAP, LIT_THISMAPSET, CactupaScreen.class);
            in = screen.isPresent() ? screen.get().screenValues() : Map.of();

            initNew();                                    // INITIALIZE ACUP-NEW-DETAILS

            String id = fld("ACCTSID", 11);
            if (starOrSpaces(id)) {
                ccAcctId = lv(11);
                nAcctIdX = lv(11);
            } else {
                ccAcctId = id;
                nAcctIdX = id;
            }

            if (notFetched()) {
                return;                                   // GO TO 1100-RECEIVE-MAP-EXIT
            }

            nStatus = pick("ACSTTUS", 1, 1);

            // Credit limit
            String v = fld("ACRDLIM", 15);
            if (starOrSpaces(v)) {
                m.creditX = lv(15);
            } else {
                m.creditX = v;
                if (testNumval(m.creditX, true) == 0) {
                    nCredit = zoned12(numval(v));
                }
            }
            // Cash limit
            v = fld("ACSHLIM", 15);
            if (starOrSpaces(v)) {
                m.cashX = lv(15);
            } else {
                m.cashX = v;
                if (testNumval(m.cashX, true) == 0) {
                    nCash = zoned12(numval(v));
                }
            }
            // Current balance
            v = fld("ACURBAL", 15);
            if (starOrSpaces(v)) {
                m.balX = lv(15);
            } else {
                m.balX = v;
                if (testNumval(m.balX, true) == 0) {
                    nBal = zoned12(numval(m.balX));
                }
            }
            // Current cycle credit
            v = fld("ACRCYCR", 15);
            if (starOrSpaces(v)) {
                m.cycCrX = lv(15);
            } else {
                m.cycCrX = v;
                if (testNumval(m.cycCrX, true) == 0) {
                    nCyCr = zoned12(numval(v));
                }
            }
            // Current cycle debit
            v = fld("ACRCYDB", 15);
            if (starOrSpaces(v)) {
                m.cycDbX = lv(15);
            } else {
                m.cycDbX = v;
                if (testNumval(m.cycDbX, true) == 0) {
                    nCyDb = zoned12(numval(v));
                }
            }

            // Open / expiry / reissue dates
            nOpen = put(nOpen, 1, 4, pick("OPNYEAR", 4, 4));
            nOpen = put(nOpen, 5, 2, pick("OPNMON", 2, 2));
            nOpen = put(nOpen, 7, 2, pick("OPNDAY", 2, 2));
            nExp = put(nExp, 1, 4, pick("EXPYEAR", 4, 4));
            nExp = put(nExp, 5, 2, pick("EXPMON", 2, 2));
            nExp = put(nExp, 7, 2, pick("EXPDAY", 2, 2));
            nReis = put(nReis, 1, 4, pick("RISYEAR", 4, 4));
            nReis = put(nReis, 5, 2, pick("RISMON", 2, 2));
            nReis = put(nReis, 7, 2, pick("RISDAY", 2, 2));

            nGrp = pick("AADDGRP", 10, 10);

            // Customer master data
            nCustIdX = pick("ACSTNUM", 9, 9);
            nSsn1 = pick("ACTSSN1", 3, 3);
            nSsn2 = pick("ACTSSN2", 2, 2);
            nSsn3 = pick("ACTSSN3", 4, 4);
            nDob = put(nDob, 1, 4, pick("DOBYEAR", 4, 4));
            nDob = put(nDob, 5, 2, pick("DOBMON", 2, 2));
            nDob = put(nDob, 7, 2, pick("DOBDAY", 2, 2));
            nFico = pick("ACSTFCO", 3, 3);
            nFirst = pick("ACSFNAM", 25, 25);
            nMid = pick("ACSMNAM", 25, 25);
            nLast = pick("ACSLNAM", 25, 25);
            nAd1 = pick("ACSADL1", 50, 50);
            nAd2 = pick("ACSADL2", 50, 50);
            nAd3 = pick("ACSCITY", 50, 50);
            nState = pick("ACSSTTE", 2, 2);
            nCtry = pick("ACSCTRY", 3, 3);
            nZip = pick("ACSZIPC", 5, 10);
            nPh1 = put(nPh1, 2, 3, pick("ACSPH1A", 3, 3));
            nPh1 = put(nPh1, 6, 3, pick("ACSPH1B", 3, 3));
            nPh1 = put(nPh1, 10, 4, pick("ACSPH1C", 4, 4));
            nPh2 = put(nPh2, 2, 3, pick("ACSPH2A", 3, 3));
            nPh2 = put(nPh2, 6, 3, pick("ACSPH2B", 3, 3));
            nPh2 = put(nPh2, 10, 4, pick("ACSPH2C", 4, 4));
            nGovt = pick("ACSGOVT", 20, 20);
            nEft = pick("ACSEFTC", 10, 10);
            nPri = pick("ACSPFLG", 1, 1);
        }

        // =============================================================================================
        // 1200-EDIT-MAP-INPUTS
        // =============================================================================================
        private void editMapInputs() {
            m.inputFlag = '0';                            // SET INPUT-OK TO TRUE

            if (notFetched()) {
                // VALIDATE THE SEARCH KEYS
                editAccount();
                // MOVE LOW-VALUES TO ACUP-OLD-ACCT-DATA
                oAcctIdX = lv(11);
                oStatus = lv(1);
                oBal = lv(12);
                oCredit = lv(12);
                oCash = lv(12);
                oOpen = lv(8);
                oExp = lv(8);
                oReis = lv(8);
                oCyCr = lv(12);
                oCyDb = lv(12);
                oGrp = lv(10);
                if (m.acctFlag == ' ') {                  // FLG-ACCTFILTER-BLANK
                    m.returnMsg = fit(MSG_NO_SEARCH_CRITERIA, 75);   // SET NO-SEARCH-CRITERIA-RECEIVED
                }
                return;                                   // GO TO 1200-EDIT-MAP-INPUTS-EXIT
            }

            // SEARCH KEYS ALREADY VALIDATED AND DATA FETCHED
            m.infoMsg = fit(MSG_FOUND_ACCOUNT_DATA, 40);  // SET FOUND-ACCOUNT-DATA
            m.acctReadFlag = '1';                         // SET FOUND-ACCT-IN-MASTER
            m.acctFlag = '1';                             // SET FLG-ACCTFILTER-ISVALID
            m.custReadFlag = '1';                         // SET FOUND-CUST-IN-MASTER
            m.custFlag = '1';                             // SET FLG-CUSTFILTER-ISVALID

            compareOldNew();

            if (m.dataChanged == '0' || changesOkNotConfirmed() || changesOkayedAndDone()) {
                Arrays.fill(m.nk, LV);                    // MOVE LOW-VALUES TO WS-NON-KEY-FLAGS
                return;
            }

            action = "E";                                 // SET ACUP-CHANGES-NOT-OK

            setVarName("Account Status");
            m.yesNo = nStatus.charAt(0);
            editYesNo();
            m.nk[NK_ACCT_STATUS] = m.yesNo;

            setVarName("Open Date");
            m.dateCcyymmdd = nOpen;
            editDateCcyymmdd();
            System.arraycopy(m.dateFlgs, 0, m.nk, NK_OPEN, 3);

            setVarName("Credit Limit");
            m.editSignedX = m.creditX;
            editSigned9v2();
            m.nk[NK_CRED_LIMIT] = m.signedFlag;

            setVarName("Expiry Date");
            m.dateCcyymmdd = nExp;
            editDateCcyymmdd();
            System.arraycopy(m.dateFlgs, 0, m.nk, NK_EXPIRY, 3);

            setVarName("Cash Credit Limit");
            m.editSignedX = m.cashX;
            editSigned9v2();
            m.nk[NK_CASH_LIMIT] = m.signedFlag;

            setVarName("Reissue Date");
            m.dateCcyymmdd = nReis;
            editDateCcyymmdd();
            System.arraycopy(m.dateFlgs, 0, m.nk, NK_REISSUE, 3);

            setVarName("Current Balance");
            m.editSignedX = m.balX;
            editSigned9v2();
            m.nk[NK_CURR_BAL] = m.signedFlag;

            setVarName("Current Cycle Credit Limit");
            m.editSignedX = m.cycCrX;
            editSigned9v2();
            m.nk[NK_CYC_CREDIT] = m.signedFlag;

            setVarName("Current Cycle Debit Limit");
            m.editSignedX = m.cycDbX;
            editSigned9v2();
            m.nk[NK_CYC_DEBIT] = m.signedFlag;

            setVarName("SSN");
            editUsSsn();

            setVarName("Date of Birth");
            m.dateCcyymmdd = nDob;
            editDateCcyymmdd();
            System.arraycopy(m.dateFlgs, 0, m.nk, NK_DOB, 3);
            if (allValid(m.nk, NK_DOB)) {
                editDateOfBirth();
                System.arraycopy(m.dateFlgs, 0, m.nk, NK_DOB, 3);
            }

            setVarName("FICO Score");
            setAlnum(nFico, 3);
            editNumReqd();
            m.nk[NK_FICO] = m.alnumFlag;
            if (m.nk[NK_FICO] == LV) {
                editFicoScore();
            }

            setVarName("First Name");
            setAlnum(nFirst, 25);
            editAlphaReqd();
            m.nk[NK_FIRST] = m.alphaFlag;

            setVarName("Middle Name");
            setAlnum(nMid, 25);
            editAlphaOpt();
            m.nk[NK_MIDDLE] = m.alphaFlag;

            setVarName("Last Name");
            setAlnum(nLast, 25);
            editAlphaReqd();
            m.nk[NK_LAST] = m.alphaFlag;

            setVarName("Address Line 1");
            setAlnum(nAd1, 50);
            editMandatory();
            m.nk[NK_ADDR1] = m.mandFlag;

            setVarName("State");
            setAlnum(nState, 2);
            editAlphaReqd();
            m.nk[NK_STATE] = m.alphaFlag;
            if (m.alphaFlag == LV) {                      // IF FLG-ALPHA-ISVALID
                editUsStateCd();
            }

            setVarName("Zip");
            setAlnum(nZip, 5);
            editNumReqd();
            m.nk[NK_ZIP] = m.alnumFlag;

            // Address Line 2 is optional
            setVarName("City");
            setAlnum(nAd3, 50);
            editAlphaReqd();
            m.nk[NK_CITY] = m.alphaFlag;

            setVarName("Country");
            setAlnum(nCtry, 3);
            editAlphaReqd();
            m.nk[NK_COUNTRY] = m.alphaFlag;

            setVarName("Phone Number 1");
            m.phoneNum = nPh1;
            editUsPhoneNum();
            System.arraycopy(m.phoneFlgs, 0, m.nk, NK_PHONE1, 3);

            setVarName("Phone Number 2");
            m.phoneNum = nPh2;
            editUsPhoneNum();
            System.arraycopy(m.phoneFlgs, 0, m.nk, NK_PHONE2, 3);

            setVarName("EFT Account Id");
            setAlnum(nEft, 10);
            editNumReqd();
            m.nk[NK_EFT] = m.alnumFlag;

            setVarName("Primary Card Holder");
            m.yesNo = nPri.charAt(0);
            editYesNo();
            m.nk[NK_PRI] = m.yesNo;

            // Cross field edits begin here
            if (m.nk[NK_STATE] == LV && m.nk[NK_ZIP] == LV) {
                editUsStateZipCd();
            }

            if (!inputError()) {
                action = "N";                             // SET ACUP-CHANGES-OK-NOT-CONFIRMED
            }
        }

        private boolean allValid(char[] flags, int at) {
            return flags[at] == LV && flags[at + 1] == LV && flags[at + 2] == LV;
        }

        /** MOVE x TO WS-EDIT-ALPHANUM-ONLY, MOVE len TO WS-EDIT-ALPHANUM-LENGTH */
        private void setAlnum(String value, int len) {
            m.editAlnum = fit(value, 256);
            m.editAlnumLen = len;
        }

        private String alnumPart() {
            return m.editAlnum.substring(0, m.editAlnumLen);
        }

        // 1205-COMPARE-OLD-NEW
        private void compareOldNew() {
            m.dataChanged = '0';                          // SET NO-CHANGES-FOUND
            if (same(nAcctIdX, oAcctIdX)
                    && same(nStatus.toUpperCase(Locale.ROOT), oStatus.toUpperCase(Locale.ROOT))
                    && same(nBal, oBal)
                    && same(nCredit, oCredit)
                    && same(nCash, oCash)
                    && same(nOpen, oOpen)
                    && same(nExp, oExp)
                    && same(nReis, oReis)
                    && same(nCyCr, oCyCr)
                    && same(nCyDb, oCyDb)
                    && sameTrimUpper(nGrp, oGrp)) {
                // CONTINUE
            } else {
                m.dataChanged = '1';                      // SET CHANGE-HAS-OCCURRED
                return;
            }

            if (sameTrimUpper(nCustIdX, oCustIdX)
                    && sameTrimUpper(nFirst, oFirst)
                    && sameTrimUpper(nMid, oMid)
                    && sameTrimUpper(nLast, oLast)
                    && sameTrimUpper(nAd1, oAd1)
                    && sameTrimUpper(nAd2, oAd2)
                    && sameTrimUpper(nAd3, oAd3)
                    && sameTrimUpper(nState, oState)
                    && sameTrimUpper(nCtry, oCtry)
                    && sameTrimUpper(nZip, oZip)
                    && same(sub(nPh1, 2, 3), sub(oPh1, 2, 3))
                    && same(sub(nPh1, 6, 3), sub(oPh1, 6, 3))
                    && same(sub(nPh1, 10, 4), sub(oPh1, 10, 4))
                    && same(sub(nPh2, 2, 3), sub(oPh2, 2, 3))
                    && same(sub(nPh2, 6, 3), sub(oPh2, 6, 3))
                    && same(sub(nPh2, 10, 4), sub(oPh2, 10, 4))
                    && same(nSsnX(), oSsnX)
                    && sameTrimUpper(nGovt, oGovt)
                    && same(nDob, oDob)
                    && same(nEft, oEft)
                    && sameTrimUpper(nPri, oPri)
                    && same(nFico, oFico)) {
                m.returnMsg = fit(MSG_NO_CHANGES_DETECTED, 75);   // SET NO-CHANGES-DETECTED
            } else {
                m.dataChanged = '1';
            }
        }

        /** FUNCTION UPPER-CASE (FUNCTION TRIM (a)) = FUNCTION UPPER-CASE (FUNCTION TRIM (b)) */
        private boolean sameTrimUpper(String a, String b) {
            return same(trim(a).toUpperCase(Locale.ROOT), trim(b).toUpperCase(Locale.ROOT));
        }

        // 1210-EDIT-ACCOUNT
        private void editAccount() {
            m.acctFlag = '0';                             // SET FLG-ACCTFILTER-NOT-OK

            if (lvOrSpaces(ccAcctId)) {
                setInputError();
                m.acctFlag = ' ';                         // SET FLG-ACCTFILTER-BLANK
                if (msgOff()) {
                    m.returnMsg = fit(MSG_PROMPT_FOR_ACCT, 75);
                }
                cdAcctId = 0;
                nAcctIdX = "0".repeat(11);                // MOVE ZEROES TO CDEMO-ACCT-ID ACUP-NEW-ACCT-ID
                return;
            }

            nAcctIdX = moveAlnumToNumeric(ccAcctId, 11);  // MOVE CC-ACCT-ID TO ACUP-NEW-ACCT-ID
            if (!isNumeric(ccAcctId) || numView(ccAcctId) == 0) {
                setInputError();
                err("Account Number if supplied must be a 11 digit Non-Zero Number");
                cdAcctId = 0;
                return;
            }
            cdAcctId = Long.parseLong(ccAcctId);          // MOVE CC-ACCT-ID TO CDEMO-ACCT-ID
            m.acctFlag = '1';                             // SET FLG-ACCTFILTER-ISVALID
        }

        // 1215-EDIT-MANDATORY
        private void editMandatory() {
            m.mandFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                setInputError();
                m.mandFlag = 'B';
                err(varName() + " must be supplied.");
                return;
            }
            m.mandFlag = LV;
        }

        // 1220-EDIT-YESNO
        private void editYesNo() {
            char c = m.yesNo;
            if (c == LV || c == ' ' || c == '0') {
                setInputError();
                m.yesNo = 'B';                            // SET FLG-YES-NO-BLANK
                err(varName() + " must be supplied.");
                return;
            }
            if (c == 'Y' || c == 'N') {
                return;                                   // FLG-YES-NO-ISVALID
            }
            setInputError();
            m.yesNo = '0';                                // SET FLG-YES-NO-NOT-OK
            err(varName() + " must be Y or N.");
        }

        /** INSPECT WS-EDIT-ALPHANUM-ONLY(1:len) CONVERTING letters TO SPACES */
        private void convertLettersToSpaces() {
            StringBuilder sb = new StringBuilder(alnumPart());
            for (int i = 0; i < sb.length(); i++) {
                char c = sb.charAt(i);
                if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')) {
                    sb.setCharAt(i, ' ');
                }
            }
            m.editAlnum = sb + m.editAlnum.substring(m.editAlnumLen);
        }

        /** INSPECT WS-EDIT-ALPHANUM-ONLY(1:len) CONVERTING letters and digits TO SPACES */
        private void convertLettersDigitsToSpaces() {
            StringBuilder sb = new StringBuilder(alnumPart());
            for (int i = 0; i < sb.length(); i++) {
                char c = sb.charAt(i);
                if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
                    sb.setCharAt(i, ' ');
                }
            }
            m.editAlnum = sb + m.editAlnum.substring(m.editAlnumLen);
        }

        // 1225-EDIT-ALPHA-REQD
        private void editAlphaReqd() {
            m.alphaFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                setInputError();
                m.alphaFlag = 'B';
                err(varName() + " must be supplied.");
                return;
            }
            convertLettersToSpaces();
            if (trim(alnumPart()).isEmpty()) {
                // CONTINUE
            } else {
                setInputError();
                m.alphaFlag = '0';
                err(varName() + " can have alphabets only.");
                return;
            }
            m.alphaFlag = LV;
        }

        // 1230-EDIT-ALPHANUM-REQD (no paragraph PERFORMs it; ported for completeness)
        @SuppressWarnings("unused")
        private void editAlphanumReqd() {
            m.alnumFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                setInputError();
                m.alnumFlag = 'B';
                err(varName() + " must be supplied.");
                return;
            }
            convertLettersDigitsToSpaces();
            if (!trim(alnumPart()).isEmpty()) {
                setInputError();
                m.alnumFlag = '0';
                err(varName() + " can have numbers or alphabets only.");
                return;
            }
            m.alnumFlag = LV;
        }

        // 1235-EDIT-ALPHA-OPT
        private void editAlphaOpt() {
            m.alphaFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                m.alphaFlag = LV;
                return;
            }
            convertLettersToSpaces();
            if (!trim(alnumPart()).isEmpty()) {
                setInputError();
                m.alphaFlag = '0';
                err(varName() + " can have alphabets only.");
                return;
            }
            m.alphaFlag = LV;
        }

        // 1240-EDIT-ALPHANUM-OPT (no paragraph PERFORMs it; ported for completeness)
        @SuppressWarnings("unused")
        private void editAlphanumOpt() {
            m.alnumFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                m.alnumFlag = LV;
                return;
            }
            convertLettersDigitsToSpaces();
            if (!trim(alnumPart()).isEmpty()) {
                setInputError();
                m.alnumFlag = '0';
                err(varName() + " can have numbers or alphabets only.");
                return;
            }
            m.alnumFlag = LV;
        }

        // 1245-EDIT-NUM-REQD
        private void editNumReqd() {
            m.alnumFlag = '0';
            String s = alnumPart();
            if (lvOrSpaces(s) || trim(s).isEmpty()) {
                setInputError();
                m.alnumFlag = 'B';
                err(varName() + " must be supplied.");
                return;
            }
            if (!isNumeric(s)) {
                setInputError();
                m.alnumFlag = '0';
                err(varName() + " must be all numeric.");
                return;
            }
            if (isAll(s, '0')) {                          // FUNCTION NUMVAL(...) = 0
                setInputError();
                m.alnumFlag = '0';
                err(varName() + " must not be zero.");
                return;
            }
            m.alnumFlag = LV;
        }

        // 1250-EDIT-SIGNED-9V2
        private void editSigned9v2() {
            m.signedFlag = '0';
            if (lvOrSpaces(m.editSignedX)) {
                setInputError();
                m.signedFlag = 'B';
                err(varName() + " must be supplied.");
                return;
            }
            if (testNumval(m.editSignedX, true) == 0) {
                // CONTINUE
            } else {
                setInputError();
                m.signedFlag = '0';
                err(varName() + " is not valid");
                return;
            }
            m.signedFlag = LV;
        }

        // 1260-EDIT-US-PHONE-NUM (with EDIT-AREA-CODE, EDIT-US-PHONE-PREFIX, EDIT-US-PHONE-LINENUM)
        private void editUsPhoneNum() {
            m.phoneFlgs = new char[] {'0', '0', '0'};     // SET WS-EDIT-US-PHONE-IS-INVALID
            String a = sub(m.phoneNum, 2, 3);
            String b = sub(m.phoneNum, 6, 3);
            String c = sub(m.phoneNum, 10, 4);
            // DEFECT KEPT: the third condition tests NUMA against SPACES (not LOW-VALUES) and NUMC against LOW-VALUES only.
            // One-line fix: AND (NUMC EQUAL SPACES OR NUMC EQUAL LOW-VALUES).
            if (lvOrSpaces(a) && lvOrSpaces(b) && (isAll(a, ' ') || isAll(c, LV))) {
                m.phoneFlgs = new char[] {LV, LV, LV};    // SET WS-EDIT-US-PHONE-IS-VALID
                return;                                   // GO TO EDIT-US-PHONE-EXIT
            }

            // EDIT-AREA-CODE
            area:
            {
                if (lvOrSpaces(a)) {
                    setInputError();
                    m.phoneFlgs[0] = 'B';
                    err(varName() + ": Area code must be supplied.");
                    break area;
                }
                if (!isNumeric(a)) {
                    setInputError();
                    m.phoneFlgs[0] = '0';
                    err(varName() + ": Area code must be A 3 digit number.");
                    break area;
                }
                if (numView(a) == 0) {
                    setInputError();
                    m.phoneFlgs[0] = '0';
                    err(varName() + ": Area code cannot be zero");
                    break area;
                }
                if (!GENERAL_PURPOSE_AREA_CODES.contains(fit(trim(a), 3))) {
                    setInputError();
                    m.phoneFlgs[0] = '0';
                    err(varName() + ": Not valid North America general purpose area code");
                    break area;
                }
                m.phoneFlgs[0] = LV;
            }

            // EDIT-US-PHONE-PREFIX
            prefix:
            {
                if (lvOrSpaces(b)) {
                    setInputError();
                    m.phoneFlgs[1] = 'B';
                    err(varName() + ": Prefix code must be supplied.");
                    break prefix;
                }
                if (!isNumeric(b)) {
                    setInputError();
                    m.phoneFlgs[1] = '0';
                    err(varName() + ": Prefix code must be A 3 digit number.");
                    break prefix;
                }
                if (numView(b) == 0) {
                    setInputError();
                    m.phoneFlgs[1] = '0';
                    err(varName() + ": Prefix code cannot be zero");
                    break prefix;
                }
                m.phoneFlgs[1] = LV;
            }

            // EDIT-US-PHONE-LINENUM
            if (lvOrSpaces(c)) {
                setInputError();
                m.phoneFlgs[2] = 'B';
                err(varName() + ": Line number code must be supplied.");
                return;
            }
            if (!isNumeric(c)) {
                setInputError();
                m.phoneFlgs[2] = '0';
                err(varName() + ": Line number code must be A 4 digit number.");
                return;
            }
            if (numView(c) == 0) {
                setInputError();
                m.phoneFlgs[2] = '0';
                err(varName() + ": Line number code cannot be zero");
                return;
            }
            m.phoneFlgs[2] = LV;
        }

        // 1265-EDIT-US-SSN
        private void editUsSsn() {
            setVarName("SSN: First 3 chars");
            setAlnum(nSsn1, 3);
            editNumReqd();
            m.ssnFlgs[0] = m.alnumFlag;

            if (m.ssnFlgs[0] == LV) {
                m.ssnPart1 = nSsn1;
                long p1 = numView(m.ssnPart1);
                if (p1 == 0 || p1 == 666 || (p1 >= 900 && p1 <= 999)) {   // INVALID-SSN-PART1
                    setInputError();
                    m.ssnFlgs[0] = '0';
                    err(varName() + ": should not be 000, 666, or between 900 and 999");
                }
            }

            setVarName("SSN 4th & 5th chars");
            setAlnum(nSsn2, 2);
            editNumReqd();
            m.ssnFlgs[1] = m.alnumFlag;

            setVarName("SSN Last 4 chars");
            setAlnum(nSsn3, 4);
            editNumReqd();
            m.ssnFlgs[2] = m.alnumFlag;
        }

        // 1270-EDIT-US-STATE-CD
        private void editUsStateCd() {
            if (US_STATE_CODES.contains(nState)) {        // VALID-US-STATE-CODE
                return;
            }
            setInputError();
            m.nk[NK_STATE] = '0';                         // SET FLG-STATE-NOT-OK
            err(varName() + ": is not a valid state code");
        }

        // 1275-EDIT-FICO-SCORE
        private void editFicoScore() {
            long score = numView(nFico);
            if (score >= 300 && score <= 850) {           // FICO-RANGE-IS-VALID
                return;
            }
            setInputError();
            m.nk[NK_FICO] = '0';                          // SET FLG-FICO-SCORE-NOT-OK
            err(varName() + ": should be between 300 and 850");
        }

        // 1280-EDIT-US-STATE-ZIP-CD
        private void editUsStateZipCd() {
            String key = nState + sub(nZip, 1, 2);
            if (US_STATE_ZIP_COMBOS.contains(key)) {      // VALID-US-STATE-ZIP-CD2-COMBO
                return;
            }
            setInputError();
            m.nk[NK_STATE] = '0';
            m.nk[NK_ZIP] = '0';
            err("Invalid zip code for state");
        }

        // ---- CSUTLDPY: EDIT-DATE-CCYYMMDD THRU EDIT-DATE-CCYYMMDD-EXIT ---------------------------------
        // The paragraphs run one after the other (a GO TO ...-EXIT only skips to the next paragraph).
        private void editDateCcyymmdd() {
            String d = m.dateCcyymmdd;
            m.dateFlgs = new char[] {'0', '0', '0'};      // EDIT-DATE-CCYYMMDD: SET WS-EDIT-DATE-IS-INVALID

            // EDIT-YEAR-CCYY
            String ccyy = sub(d, 1, 4);
            m.dateFlgs[0] = '0';
            if (lvOrSpaces(ccyy)) {
                setInputError();
                m.dateFlgs[0] = 'B';
                err(varName() + " : Year must be supplied.");
            } else if (!isNumeric(ccyy)) {
                setInputError();
                m.dateFlgs[0] = '0';
                err(varName() + " must be 4 digit number.");
            } else if (!(numView(sub(d, 1, 2)) == 20 || numView(sub(d, 1, 2)) == 19)) {   // THIS-CENTURY / LAST-CENTURY
                setInputError();
                m.dateFlgs[0] = '0';
                err(varName() + " : Century is not valid.");
            } else {
                m.dateFlgs[0] = LV;
            }

            // EDIT-MONTH
            String mm = sub(d, 5, 2);
            m.dateFlgs[1] = '0';
            if (lvOrSpaces(mm)) {
                setInputError();
                m.dateFlgs[1] = 'B';
                err(varName() + " : Month must be supplied.");
            } else {
                long mmN = numView(mm);
                if (mmN < 1 || mmN > 12) {                // NOT WS-VALID-MONTH
                    setInputError();
                    m.dateFlgs[1] = '0';
                    err(varName() + ": Month must be a number between 1 and 12.");
                } else if (testNumval(mm, false) == 0) {
                    d = put(d, 5, 2, digits(numval(mm).longValue(), 2));   // COMPUTE WS-EDIT-DATE-MM-N = NUMVAL(MM)
                    m.dateFlgs[1] = LV;
                } else {
                    setInputError();
                    m.dateFlgs[1] = '0';
                    err(varName() + ": Month must be a number between 1 and 12.");
                }
            }

            // EDIT-DAY
            String dd = sub(d, 7, 2);
            m.dateFlgs[2] = LV;
            if (lvOrSpaces(dd)) {
                setInputError();
                m.dateFlgs[2] = 'B';
                err(varName() + " : Day must be supplied.");
            } else if (testNumval(dd, false) == 0) {
                d = put(d, 7, 2, digits(numval(dd).longValue(), 2));        // COMPUTE WS-EDIT-DATE-DD-N = NUMVAL(DD)
                long ddN = numView(sub(d, 7, 2));
                if (ddN < 1 || ddN > 31) {                // NOT WS-VALID-DAY
                    setInputError();
                    m.dateFlgs[2] = '0';
                    err(varName() + ":day must be a number between 1 and 31.");
                } else {
                    m.dateFlgs[2] = LV;
                }
            } else {
                setInputError();
                m.dateFlgs[2] = '0';
                err(varName() + ":day must be a number between 1 and 31.");
            }
            m.dateCcyymmdd = d;

            // EDIT-DAY-MONTH-YEAR
            long month = numView(sub(d, 5, 2));
            long day = numView(sub(d, 7, 2));
            boolean day31Month = month == 1 || month == 3 || month == 5 || month == 7 || month == 8 || month == 10
                    || month == 12;
            if (!day31Month && day == 31) {
                setInputError();
                m.dateFlgs[2] = '0';
                m.dateFlgs[1] = '0';
                err(varName() + ":Cannot have 31 days in this month.");
                return;                                   // GO TO EDIT-DATE-CCYYMMDD-EXIT
            }
            if (month == 2 && day == 30) {
                setInputError();
                m.dateFlgs[2] = '0';
                m.dateFlgs[1] = '0';
                err(varName() + ":Cannot have 30 days in this month.");
                return;
            }
            if (month == 2 && day == 29) {
                int divBy = numView(sub(d, 3, 2)) == 0 ? 400 : 4;
                long ccyyN = numView(sub(d, 1, 4));
                long remainder = ccyyN - (ccyyN / divBy) * divBy;   // DIVIDE ... GIVING WS-DIVIDEND REMAINDER WS-REMAINDER
                if (remainder != 0) {
                    setInputError();
                    m.dateFlgs[2] = '0';
                    m.dateFlgs[1] = '0';
                    m.dateFlgs[0] = '0';
                    err(varName() + ":Not a leap year.Cannot have 29 days in this month.");
                    return;
                }
            }
            if (!allValid(m.dateFlgs, 0)) {               // IF WS-EDIT-DATE-IS-VALID CONTINUE ELSE GO TO EXIT
                return;
            }

            // EDIT-DATE-LE: CALL 'CSUTLDTC' USING WS-EDIT-DATE-CCYYMMDD, WS-DATE-FORMAT, WS-DATE-VALIDATION-RESULT
            CobolRef<String> lsDate = CobolRef.of(fit(d, 10));           // LS-DATE X(10): the 8-character date
            CobolRef<String> lsFormat = CobolRef.of(fit("YYYYMMDD", 8) + sp(2));
            CobolRef<String> lsResult = CobolRef.of(sp(80));
            CSUTLDTC.handleCall(lsDate, lsFormat, lsResult);
            String result = fit(lsResult.get(), 80);
            String severity = sub(result, 1, 4);
            String msgNo = sub(result, 16, 4);
            if (numView(severity) == 0) {
                // CONTINUE
            } else {
                setInputError();
                m.dateFlgs[2] = '0';
                m.dateFlgs[1] = '0';
                m.dateFlgs[0] = '0';
                err(varName() + " validation error Sev code: " + severity + " Message code: " + msgNo);
                // GO TO EDIT-DATE-LE-EXIT
                // DEFECT KEPT: EDIT-DATE-LE-EXIT falls into SET WS-EDIT-DATE-IS-VALID below, so a date CSUTLDTC
                // rejected comes back with all its flags valid (only INPUT-ERROR and the message show the failure).
                // One-line fix: GO TO EDIT-DATE-CCYYMMDD-EXIT instead of EDIT-DATE-LE-EXIT.
                m.dateFlgs = new char[] {LV, LV, LV};
                return;
            }
            if (!inputError()) {
                m.dateFlgs[2] = LV;                       // SET FLG-DAY-ISVALID
            }
            m.dateFlgs = new char[] {LV, LV, LV};         // SET WS-EDIT-DATE-IS-VALID TO TRUE
        }

        // EDIT-DATE-OF-BIRTH
        private void editDateOfBirth() {
            LocalDate today = task.now().toLocalDate();   // MOVE FUNCTION CURRENT-DATE TO WS-CURRENT-DATE-YYYYMMDD
            long edit = integerOfDate(m.dateCcyymmdd);
            long current = ChronoUnit.DAYS.between(LocalDate.of(1600, 12, 31), today);
            if (current > edit) {
                // CONTINUE
            } else {
                setInputError();
                m.dateFlgs[2] = '0';
                m.dateFlgs[1] = '0';
                m.dateFlgs[0] = '0';
                err(varName() + ":cannot be in the future ");
            }
        }

        /** FUNCTION INTEGER-OF-DATE of a PIC 9(8) CCYYMMDD value: days from 1600-12-31 (ANSI), 0 for an invalid date. */
        private long integerOfDate(String ccyymmdd) {
            long v = numView(ccyymmdd);
            int year = (int) (v / 10000);
            int month = (int) (v / 100 % 100);
            int day = (int) (v % 100);
            if (year < 1601 || year > 9999) {
                return 0;
            }
            try {
                return ChronoUnit.DAYS.between(LocalDate.of(1600, 12, 31), LocalDate.of(year, month, day));
            } catch (DateTimeException e) {
                return 0;
            }
        }

        // =============================================================================================
        // 2000-DECIDE-ACTION
        // =============================================================================================
        private void decideAction() {
            if (notFetched() || aid("PFK12")) {
                // WHEN ACUP-DETAILS-NOT-FETCHED / WHEN CCARD-AID-PFK12
                if (m.acctFlag == '1') {                  // FLG-ACCTFILTER-ISVALID
                    m.returnMsg = sp(75);                 // SET WS-RETURN-MSG-OFF
                    readAcct();
                    if (m.custReadFlag == '1') {          // FOUND-CUST-IN-MASTER
                        action = "S";                     // SET ACUP-SHOW-DETAILS
                    }
                }
            } else if (showDetails()) {
                if (inputError() || retMsgIs(MSG_NO_CHANGES_DETECTED)) {
                    // CONTINUE
                } else {
                    action = "N";                         // SET ACUP-CHANGES-OK-NOT-CONFIRMED
                }
            } else if (changesNotOk()) {
                // CONTINUE
            } else if (changesOkNotConfirmed() && aid("PFK05")) {
                writeProcessing();
                if (retMsgIs(MSG_COULD_NOT_LOCK_ACCT)) {
                    action = "L";                         // SET ACUP-CHANGES-OKAYED-LOCK-ERROR
                } else if (retMsgIs(MSG_LOCKED_BUT_UPDATE_FAILED)) {
                    action = "F";                         // SET ACUP-CHANGES-OKAYED-BUT-FAILED
                } else if (retMsgIs(MSG_DATA_WAS_CHANGED)) {
                    action = "S";                         // SET ACUP-SHOW-DETAILS
                } else {
                    // DEFECT KEPT: COULD-NOT-LOCK-CUST-FOR-UPDATE is not tested, so a customer record that could not
                    // be locked ends as a success. One-line fix: add WHEN COULD-NOT-LOCK-CUST-FOR-UPDATE SET
                    // ACUP-CHANGES-OKAYED-LOCK-ERROR.
                    action = "C";                         // SET ACUP-CHANGES-OKAYED-AND-DONE
                }
            } else if (changesOkNotConfirmed()) {
                // CONTINUE
            } else if (changesOkayedAndDone()) {
                action = "S";
                if (lvOrSpaces(cdFromTranid)) {
                    cdAcctId = 0;
                    cdCardNum = 0;
                    cdAcctStatus = lv(1);
                }
            } else {
                // WHEN OTHER
                m.abendCode = fit("0001", 4);
                m.abendReason = sp(50);
                m.abendMsg = fit("UNEXPECTED DATA SCENARIO", 72);
                abendRoutine();
            }
        }

        // =============================================================================================
        // 3000-SEND-MAP
        // =============================================================================================
        private void sendMap() {
            screenInit();
            setupScreenVars();
            setupInfoMsg();
            setupScreenAttrs();
            setupInfoMsgAttrs();
            sendScreen();
        }

        private void set(String field, String value) {
            out.put(field, fit(value, FIELD_LENGTH.get(field)));
        }

        // 3100-SCREEN-INIT
        private void screenInit() {
            out.clear();
            sub = new CicsTask.MapSubfields();
            for (Map.Entry<String, Integer> e : FIELD_LENGTH.entrySet()) {
                out.put(e.getKey(), lv(e.getValue()));    // MOVE LOW-VALUES TO CACTUPAO
            }
            LocalDateTime now = task.now();
            set("TITLE01", CCDA_TITLE01);
            set("TITLE02", CCDA_TITLE02);
            set("TRNNAME", LIT_THISTRANID);
            set("PGMNAME", LIT_THISPGM);
            set("CURDATE", digits(now.getMonthValue(), 2) + "/" + digits(now.getDayOfMonth(), 2) + "/"
                    + digits(now.getYear() % 100, 2));
            set("CURTIME", digits(now.getHour(), 2) + ":" + digits(now.getMinute(), 2) + ":" + digits(now.getSecond(), 2));
        }

        // 3200-SETUP-SCREEN-VARS
        private void setupScreenVars() {
            if (cdPgmContext == 0) {                      // CDEMO-PGM-ENTER
                return;
            }
            if (numView(ccAcctId) == 0 && m.acctFlag == '1') {
                out.put("ACCTSID", lv(FIELD_LENGTH.get("ACCTSID")));
            } else {
                set("ACCTSID", ccAcctId);
            }
            if (notFetched() || numView(ccAcctId) == 0) {
                // 3201-SHOW-INITIAL-VALUES: MOVE LOW-VALUES to the fields 3100 already cleared
                showInitialValues();
            } else if (showDetails()) {
                showOriginalValues();
            } else if (changesMade()) {
                showUpdatedValues();
            } else {
                showOriginalValues();
            }
        }

        // 3201-SHOW-INITIAL-VALUES
        private void showInitialValues() {
            for (String f : new String[] {"ACSTTUS", "ACRDLIM", "ACURBAL", "ACSHLIM", "ACRCYCR", "ACRCYDB", "OPNYEAR",
                "OPNMON", "OPNDAY", "EXPYEAR", "EXPMON", "EXPDAY", "RISYEAR", "RISMON", "RISDAY", "AADDGRP", "ACSTNUM",
                "ACTSSN1", "ACTSSN2", "ACTSSN3", "ACSTFCO", "DOBYEAR", "DOBMON", "DOBDAY", "ACSFNAM", "ACSMNAM",
                "ACSLNAM", "ACSADL1", "ACSADL2", "ACSCITY", "ACSSTTE", "ACSZIPC", "ACSCTRY", "ACSPH1A", "ACSPH1B",
                "ACSPH1C", "ACSPH2A", "ACSPH2B", "ACSPH2C", "ACSGOVT", "ACSEFTC", "ACSPFLG"}) {
                out.put(f, lv(FIELD_LENGTH.get(f)));
            }
        }

        // 3202-SHOW-ORIGINAL-VALUES
        private void showOriginalValues() {
            Arrays.fill(m.nk, LV);                        // MOVE LOW-VALUES TO WS-NON-KEY-FLAGS
            m.infoMsg = fit(MSG_PROMPT_FOR_CHANGES, 40);  // SET PROMPT-FOR-CHANGES

            if (m.acctReadFlag == '1' || m.custReadFlag == '1') {
                set("ACSTTUS", oStatus);
                set("ACURBAL", currencyEdited(z12(oBal)));
                set("ACRDLIM", currencyEdited(z12(oCredit)));
                set("ACSHLIM", currencyEdited(z12(oCash)));
                set("ACRCYCR", currencyEdited(z12(oCyCr)));
                set("ACRCYDB", currencyEdited(z12(oCyDb)));
                set("OPNYEAR", sub(oOpen, 1, 4));
                set("OPNMON", sub(oOpen, 5, 2));
                set("OPNDAY", sub(oOpen, 7, 2));
                set("EXPYEAR", sub(oExp, 1, 4));
                set("EXPMON", sub(oExp, 5, 2));
                set("EXPDAY", sub(oExp, 7, 2));
                set("RISYEAR", sub(oReis, 1, 4));
                set("RISMON", sub(oReis, 5, 2));
                set("RISDAY", sub(oReis, 7, 2));
                set("AADDGRP", oGrp);
            }
            if (m.custReadFlag == '1') {
                set("ACSTNUM", oCustIdX);
                set("ACTSSN1", sub(oSsnX, 1, 3));
                set("ACTSSN2", sub(oSsnX, 4, 2));
                set("ACTSSN3", sub(oSsnX, 6, 4));
                set("ACSTFCO", oFico);
                set("DOBYEAR", sub(oDob, 1, 4));
                set("DOBMON", sub(oDob, 5, 2));
                set("DOBDAY", sub(oDob, 7, 2));
                set("ACSFNAM", oFirst);
                set("ACSMNAM", oMid);
                set("ACSLNAM", oLast);
                set("ACSADL1", oAd1);
                set("ACSADL2", oAd2);
                set("ACSCITY", oAd3);
                set("ACSSTTE", oState);
                set("ACSZIPC", oZip);
                set("ACSCTRY", oCtry);
                set("ACSPH1A", sub(oPh1, 2, 3));
                set("ACSPH1B", sub(oPh1, 6, 3));
                set("ACSPH1C", sub(oPh1, 10, 4));
                set("ACSPH2A", sub(oPh2, 2, 3));
                set("ACSPH2B", sub(oPh2, 6, 3));
                set("ACSPH2C", sub(oPh2, 10, 4));
                set("ACSGOVT", oGovt);
                set("ACSEFTC", oEft);
                set("ACSPFLG", oPri);
            }
        }

        // 3203-SHOW-UPDATED-VALUES
        private void showUpdatedValues() {
            set("ACSTTUS", nStatus);
            set("ACRDLIM", m.nk[NK_CRED_LIMIT] == LV ? currencyEdited(z12(nCredit)) : m.creditX);
            set("ACSHLIM", m.nk[NK_CASH_LIMIT] == LV ? currencyEdited(z12(nCash)) : m.cashX);
            set("ACURBAL", m.nk[NK_CURR_BAL] == LV ? currencyEdited(z12(nBal)) : m.balX);
            set("ACRCYCR", m.nk[NK_CYC_CREDIT] == LV ? currencyEdited(z12(nCyCr)) : m.cycCrX);
            set("ACRCYDB", m.nk[NK_CYC_DEBIT] == LV ? currencyEdited(z12(nCyDb)) : m.cycDbX);
            set("OPNYEAR", sub(nOpen, 1, 4));
            set("OPNMON", sub(nOpen, 5, 2));
            set("OPNDAY", sub(nOpen, 7, 2));
            set("EXPYEAR", sub(nExp, 1, 4));
            set("EXPMON", sub(nExp, 5, 2));
            set("EXPDAY", sub(nExp, 7, 2));
            set("RISYEAR", sub(nReis, 1, 4));
            set("RISMON", sub(nReis, 5, 2));
            set("RISDAY", sub(nReis, 7, 2));
            set("AADDGRP", nGrp);
            set("ACSTNUM", nCustIdX);
            set("ACTSSN1", nSsn1);
            set("ACTSSN2", nSsn2);
            set("ACTSSN3", nSsn3);
            set("ACSTFCO", nFico);
            set("DOBYEAR", sub(nDob, 1, 4));
            set("DOBMON", sub(nDob, 5, 2));
            set("DOBDAY", sub(nDob, 7, 2));
            set("ACSFNAM", nFirst);
            set("ACSMNAM", nMid);
            set("ACSLNAM", nLast);
            set("ACSADL1", nAd1);
            set("ACSADL2", nAd2);
            set("ACSCITY", nAd3);
            set("ACSSTTE", nState);
            set("ACSZIPC", nZip);
            set("ACSCTRY", nCtry);
            set("ACSPH1A", sub(nPh1, 2, 3));
            set("ACSPH1B", sub(nPh1, 6, 3));
            set("ACSPH1C", sub(nPh1, 10, 4));
            set("ACSPH2A", sub(nPh2, 2, 3));
            set("ACSPH2B", sub(nPh2, 6, 3));
            set("ACSPH2C", sub(nPh2, 10, 4));
            set("ACSGOVT", nGovt);
            set("ACSEFTC", nEft);
            set("ACSPFLG", nPri);
        }

        // 3250-SETUP-INFOMSG
        private void setupInfoMsg() {
            if (cdPgmContext == 0) {                      // CDEMO-PGM-ENTER
                m.infoMsg = fit(MSG_PROMPT_FOR_SEARCH_KEYS, 40);
            } else if (notFetched()) {
                m.infoMsg = fit(MSG_PROMPT_FOR_SEARCH_KEYS, 40);
            } else if (showDetails()) {
                m.infoMsg = fit(MSG_PROMPT_FOR_CHANGES, 40);
            } else if (changesNotOk()) {
                m.infoMsg = fit(MSG_PROMPT_FOR_CHANGES, 40);
            } else if (changesOkNotConfirmed()) {
                m.infoMsg = fit(MSG_PROMPT_FOR_CONFIRMATION, 40);
            } else if (changesOkayedAndDone()) {
                m.infoMsg = fit(MSG_CONFIRM_UPDATE_SUCCESS, 40);
            } else if (act("L")) {
                m.infoMsg = fit(MSG_INFORM_FAILURE, 40);
            } else if (act("F")) {
                m.infoMsg = fit(MSG_INFORM_FAILURE, 40);
            } else if (noInfoMessage()) {
                m.infoMsg = fit(MSG_PROMPT_FOR_SEARCH_KEYS, 40);
            }
            set("INFOMSG", m.infoMsg);
            set("ERRMSG", m.returnMsg);
        }

        // 3300-SETUP-SCREEN-ATTRS
        private void setupScreenAttrs() {
            protectAllAttrs();                            // 3310-PROTECT-ALL-ATTRS

            if (notFetched()) {
                sub.attr("ACCTSID", DFHBMFSE);
            } else if (showDetails() || changesNotOk()) {
                unprotectFewAttrs();                      // 3320-UNPROTECT-FEW-ATTRS
            } else if (changesOkNotConfirmed() || changesOkayedAndDone()) {
                // CONTINUE
            } else {
                sub.attr("ACCTSID", DFHBMFSE);
            }

            // POSITION CURSOR - ORDER BASED ON SCREEN LOCATION
            char[] nk = m.nk;
            if (infoMsgIs(MSG_FOUND_ACCOUNT_DATA) || retMsgIs(MSG_NO_CHANGES_DETECTED)) {
                sub.cursor("ACSTTUS");
            } else if (m.acctFlag == '0' || m.acctFlag == ' ') {
                sub.cursor("ACCTSID");
            } else if (bad(nk[NK_ACCT_STATUS])) {
                sub.cursor("ACSTTUS");
            } else if (bad(nk[NK_OPEN])) {
                sub.cursor("OPNYEAR");
            } else if (bad(nk[NK_OPEN + 1])) {
                sub.cursor("OPNMON");
            } else if (bad(nk[NK_OPEN + 2])) {
                sub.cursor("OPNDAY");
            } else if (bad(nk[NK_CRED_LIMIT])) {
                sub.cursor("ACRDLIM");
            } else if (bad(nk[NK_EXPIRY])) {
                sub.cursor("EXPYEAR");
            } else if (bad(nk[NK_EXPIRY + 1])) {
                sub.cursor("EXPMON");
            } else if (bad(nk[NK_EXPIRY + 2])) {
                sub.cursor("EXPDAY");
            } else if (bad(nk[NK_CASH_LIMIT])) {
                sub.cursor("ACSHLIM");
            } else if (bad(nk[NK_REISSUE])) {
                sub.cursor("RISYEAR");
            } else if (bad(nk[NK_REISSUE + 1])) {
                sub.cursor("RISMON");
            } else if (bad(nk[NK_REISSUE + 2])) {
                sub.cursor("RISDAY");
            } else if (bad(nk[NK_CURR_BAL])) {
                sub.cursor("ACURBAL");
            } else if (bad(nk[NK_CYC_CREDIT])) {
                sub.cursor("ACRCYCR");
            } else if (bad(nk[NK_CYC_DEBIT])) {
                sub.cursor("ACRCYDB");
            } else if (bad(m.ssnFlgs[0])) {
                sub.cursor("ACTSSN1");
            } else if (bad(m.ssnFlgs[1])) {
                sub.cursor("ACTSSN2");
            } else if (bad(m.ssnFlgs[2])) {
                sub.cursor("ACTSSN3");
            } else if (bad(nk[NK_DOB])) {
                sub.cursor("DOBYEAR");
            } else if (bad(nk[NK_DOB + 1])) {
                sub.cursor("DOBMON");
            } else if (bad(nk[NK_DOB + 2])) {
                sub.cursor("DOBDAY");
            } else if (bad(nk[NK_FICO])) {
                sub.cursor("ACSTFCO");
            } else if (bad(nk[NK_FIRST])) {
                sub.cursor("ACSFNAM");
            } else if (nk[NK_MIDDLE] == '0') {            // the middle name tests NOT-OK only
                sub.cursor("ACSMNAM");
            } else if (bad(nk[NK_LAST])) {
                sub.cursor("ACSLNAM");
            } else if (bad(nk[NK_ADDR1])) {
                sub.cursor("ACSADL1");
            } else if (bad(nk[NK_STATE])) {
                sub.cursor("ACSSTTE");
            } else if (bad(nk[NK_ZIP])) {
                sub.cursor("ACSZIPC");
            } else if (bad(nk[NK_CITY])) {
                sub.cursor("ACSCITY");
            } else if (bad(nk[NK_COUNTRY])) {
                sub.cursor("ACSCTRY");
            } else if (bad(nk[NK_PHONE1])) {
                sub.cursor("ACSPH1A");
            } else if (bad(nk[NK_PHONE1 + 1])) {
                sub.cursor("ACSPH1B");
            } else if (bad(nk[NK_PHONE1 + 2])) {
                sub.cursor("ACSPH1C");
            } else if (bad(nk[NK_PHONE2])) {
                sub.cursor("ACSPH2A");
            } else if (bad(nk[NK_PHONE2 + 1])) {
                sub.cursor("ACSPH2B");
            } else if (bad(nk[NK_PHONE2 + 2])) {
                sub.cursor("ACSPH2C");
            } else if (bad(nk[NK_EFT])) {
                sub.cursor("ACSEFTC");
            } else if (bad(nk[NK_PRI])) {
                sub.cursor("ACSPFLG");
            } else {
                sub.cursor("ACCTSID");
            }

            // SETUP COLOR
            if (same(cdLastMapset, LIT_CCLISTMAPSET)) {
                sub.color("ACCTSID", DFHDFCOL);
            }
            if (m.acctFlag == '0') {                      // FLG-ACCTFILTER-NOT-OK
                sub.color("ACCTSID", DFHRED);
            }
            if (m.acctFlag == ' ' && cdPgmContext == 1) { // FLG-ACCTFILTER-BLANK AND CDEMO-PGM-REENTER
                set("ACCTSID", "*");
                sub.color("ACCTSID", DFHRED);
            }

            if (notFetched() || m.acctFlag == ' ' || m.acctFlag == '0') {
                return;                                   // GO TO 3300-SETUP-SCREEN-ATTRS-EXIT
            }

            // COPY CSSETATY REPLACING ... for each remaining field
            flagAttr(nk[NK_ACCT_STATUS], "ACSTTUS");
            flagAttr(nk[NK_OPEN], "OPNYEAR");
            flagAttr(nk[NK_OPEN + 1], "OPNMON");
            flagAttr(nk[NK_OPEN + 2], "OPNDAY");
            flagAttr(nk[NK_CRED_LIMIT], "ACRDLIM");
            flagAttr(nk[NK_EXPIRY], "EXPYEAR");
            flagAttr(nk[NK_EXPIRY + 1], "EXPMON");
            flagAttr(nk[NK_EXPIRY + 2], "EXPDAY");
            flagAttr(nk[NK_CASH_LIMIT], "ACSHLIM");
            flagAttr(nk[NK_REISSUE], "RISYEAR");
            flagAttr(nk[NK_REISSUE + 1], "RISMON");
            flagAttr(nk[NK_REISSUE + 2], "RISDAY");
            flagAttr(nk[NK_CURR_BAL], "ACURBAL");
            flagAttr(nk[NK_CYC_CREDIT], "ACRCYCR");
            flagAttr(nk[NK_CYC_DEBIT], "ACRCYDB");
            flagAttr(m.ssnFlgs[0], "ACTSSN1");
            flagAttr(m.ssnFlgs[1], "ACTSSN2");
            flagAttr(m.ssnFlgs[2], "ACTSSN3");
            flagAttr(nk[NK_DOB], "DOBYEAR");
            flagAttr(nk[NK_DOB + 1], "DOBMON");
            flagAttr(nk[NK_DOB + 2], "DOBDAY");
            flagAttr(nk[NK_FICO], "ACSTFCO");
            flagAttr(nk[NK_FIRST], "ACSFNAM");
            flagAttr(nk[NK_MIDDLE], "ACSMNAM");
            flagAttr(nk[NK_LAST], "ACSLNAM");
            flagAttr(nk[NK_ADDR1], "ACSADL1");
            flagAttr(nk[NK_STATE], "ACSSTTE");
            flagAttr(nk[NK_ADDR2], "ACSADL2");
            flagAttr(nk[NK_ZIP], "ACSZIPC");
            flagAttr(nk[NK_CITY], "ACSCITY");
            flagAttr(nk[NK_COUNTRY], "ACSCTRY");
            flagAttr(nk[NK_PHONE1], "ACSPH1A");
            flagAttr(nk[NK_PHONE1 + 1], "ACSPH1B");
            flagAttr(nk[NK_PHONE1 + 2], "ACSPH1C");
            flagAttr(nk[NK_PHONE2], "ACSPH2A");
            flagAttr(nk[NK_PHONE2 + 1], "ACSPH2B");
            flagAttr(nk[NK_PHONE2 + 2], "ACSPH2C");
            flagAttr(nk[NK_PRI], "ACSPFLG");
            flagAttr(nk[NK_EFT], "ACSEFTC");
        }

        /** FLG-x-NOT-OK OR FLG-x-BLANK */
        private boolean bad(char flag) {
            return flag == '0' || flag == 'B';
        }

        /** CSSETATY: red if in error and a '*' if blank, once the screen has been shown. */
        private void flagAttr(char flag, String field) {
            if (bad(flag) && cdPgmContext == 1) {
                sub.color(field, DFHRED);
                if (flag == 'B') {
                    set(field, "*");
                }
            }
        }

        private static final String[] ALL_FIELDS = {"ACCTSID", "ACSTTUS", "ACRDLIM", "ACSHLIM", "ACURBAL", "ACRCYCR",
            "ACRCYDB", "OPNYEAR", "OPNMON", "OPNDAY", "EXPYEAR", "EXPMON", "EXPDAY", "RISYEAR", "RISMON", "RISDAY",
            "AADDGRP", "ACSTNUM", "ACTSSN1", "ACTSSN2", "ACTSSN3", "ACSTFCO", "DOBYEAR", "DOBMON", "DOBDAY", "ACSFNAM",
            "ACSMNAM", "ACSLNAM", "ACSADL1", "ACSADL2", "ACSCITY", "ACSSTTE", "ACSZIPC", "ACSCTRY", "ACSPH1A",
            "ACSPH1B", "ACSPH1C", "ACSPH2A", "ACSPH2B", "ACSPH2C", "ACSGOVT", "ACSEFTC", "ACSPFLG", "INFOMSG"};

        // 3310-PROTECT-ALL-ATTRS
        private void protectAllAttrs() {
            for (String f : ALL_FIELDS) {
                sub.attr(f, DFHBMPRF);
            }
        }

        // 3320-UNPROTECT-FEW-ATTRS
        private void unprotectFewAttrs() {
            for (String f : new String[] {"ACSTTUS", "ACRDLIM", "ACSHLIM", "ACURBAL", "ACRCYCR", "ACRCYDB", "OPNYEAR",
                "OPNMON", "OPNDAY", "EXPYEAR", "EXPMON", "EXPDAY", "RISYEAR", "RISMON", "RISDAY", "DOBYEAR", "DOBMON",
                "DOBDAY", "AADDGRP"}) {
                sub.attr(f, DFHBMFSE);
            }
            sub.attr("ACSTNUM", DFHBMPRF);
            for (String f : new String[] {"ACTSSN1", "ACTSSN2", "ACTSSN3", "ACSTFCO", "ACSFNAM", "ACSMNAM", "ACSLNAM",
                "ACSADL1", "ACSADL2", "ACSCITY", "ACSSTTE", "ACSZIPC"}) {
                sub.attr(f, DFHBMFSE);
            }
            sub.attr("ACSCTRY", DFHBMPRF);
            for (String f : new String[] {"ACSPH1A", "ACSPH1B", "ACSPH1C", "ACSPH2A", "ACSPH2B", "ACSPH2C", "ACSGOVT",
                "ACSEFTC", "ACSPFLG"}) {
                sub.attr(f, DFHBMFSE);
            }
            sub.attr("INFOMSG", DFHBMPRF);
        }

        // 3390-SETUP-INFOMSG-ATTRS
        private void setupInfoMsgAttrs() {
            if (noInfoMessage()) {
                sub.attr("INFOMSG", DFHBMDAR);
            } else {
                sub.attr("INFOMSG", DFHBMASB);
            }
            if (changesMade() && !changesOkayedAndDone()) {
                sub.attr("FKEY12", DFHBMASB);
            }
            if (infoMsgIs(MSG_PROMPT_FOR_CONFIRMATION)) {
                sub.attr("FKEY05", DFHBMASB);
                sub.attr("FKEY12", DFHBMASB);
            }
        }

        // 3400-SEND-SCREEN
        private void sendScreen() {
            // MOVE LIT-THISMAPSET TO CCARD-NEXT-MAPSET, LIT-THISMAP TO CCARD-NEXT-MAP
            CactupaScreen screen = CactupaScreen.fromValues(out);
            task.sendMap(LIT_THISMAP, LIT_THISMAPSET, screen, sub, "CURSOR", "ERASE", "FREEKB");
        }

        // =============================================================================================
        // 9000-READ-ACCT and the file paragraphs
        // =============================================================================================
        private void readAcct() {
            initOld();                                    // INITIALIZE ACUP-OLD-DETAILS
            m.infoMsg = sp(40);                           // SET WS-NO-INFO-MESSAGE
            String key = moveAlnumToNumeric(ccAcctId, 11);
            oAcctIdX = key;                               // MOVE CC-ACCT-ID TO ACUP-OLD-ACCT-ID WS-CARD-RID-ACCT-ID
            m.ridAcctIdX = key;

            getCardXrefByAcct();
            if (m.acctFlag == '0') {                      // FLG-ACCTFILTER-NOT-OK
                return;
            }

            getAcctDataByAcct();
            // DEFECT KEPT: DID-NOT-FIND-ACCT-IN-ACCTDAT is a WS-RETURN-MSG value that 9300 no longer sets (its SET is
            // commented out), so this exit is never taken and a missing account record falls through to the customer
            // read and 9500 with the previous (blank) ACCOUNT-RECORD. One-line fix: test FLG-ACCTFILTER-NOT-OK here.
            if (retMsgIs(MSG_DID_NOT_FIND_ACCT_IN_ACCTDAT)) {
                return;
            }

            m.ridCustIdX = digits(cdCustId, 9);           // MOVE CDEMO-CUST-ID TO WS-CARD-RID-CUST-ID
            getCustDataByCust();
            // DEFECT KEPT: the same for DID-NOT-FIND-CUST-IN-CUSTDAT (9400's SET is commented out).
            if (retMsgIs(MSG_DID_NOT_FIND_CUST_IN_CUSTDAT)) {
                return;
            }

            storeFetchedData();
        }

        private Optional<Long> keyOf(String digits) {
            return isNumeric(digits) && digits.length() <= 18 ? Optional.of(Long.parseLong(digits)) : Optional.empty();
        }

        /** MOVE WS-RESP-CD TO ERROR-RESP: a binary S9(9) to X(10), its 9 digits left-justified. */
        private String respText(int v) {
            return fit(digits(v, 9), 10);
        }

        private String fileErrorMessage() {
            return "File Error: " + m.errorOpname + " on " + m.errorFile + " returned RESP " + m.errorResp
                    + ",RESP2 " + m.errorResp2 + sp(5);
        }

        // 9200-GETCARDXREF-BYACCT
        private void getCardXrefByAcct() {
            Optional<Long> key = keyOf(m.ridAcctIdX);
            CicsTask.FileRead<CardXrefRecord> r = task.read("CXACAIX", () -> key.flatMap(k -> readCxacaix(k).stream()
                    .min(Comparator.comparing(x -> CobolRecords.sortKey(x.getXrefCardNum(), "cp037")))));
            m.respCd = r.resp();
            m.reasCd = r.resp2();
            if (m.respCd == 0) {                          // DFHRESP(NORMAL)
                xref = CardXrefRecord.fromRecord(r.record().toRecord(cs), cs);
                cdCustId = xref.getXrefCustId() == null ? 0 : xref.getXrefCustId();
                cdCardNum = Long.parseLong(moveAlnumToNumeric(xref.getXrefCardNum(), 16));
            } else if (m.respCd == 13) {                  // DFHRESP(NOTFND)
                setInputError();
                m.acctFlag = '0';
                if (msgOff()) {
                    m.errorResp = respText(m.respCd);
                    m.errorResp2 = respText(m.reasCd);
                    m.returnMsg = fit("Account:" + m.ridAcctIdX + " not found in" + " Cross ref file.  Resp:"
                            + m.errorResp + " Reas:" + m.errorResp2, 75);
                }
            } else {
                setInputError();
                m.acctFlag = '0';
                m.errorOpname = fit("READ", 8);
                m.errorFile = fit("CXACAIX", 9);
                m.errorResp = respText(m.respCd);
                m.errorResp2 = respText(m.reasCd);
                m.returnMsg = fit(fileErrorMessage(), 75);
            }
        }

        // 9300-GETACCTDATA-BYACCT
        private void getAcctDataByAcct() {
            Optional<Long> key = keyOf(m.ridAcctIdX);
            CicsTask.FileRead<AccountRecord> r = task.read("ACCTDAT", () -> key.flatMap(this::findAccount));
            m.respCd = r.resp();
            m.reasCd = r.resp2();
            if (m.respCd == 0) {
                acct = AccountRecord.fromRecord(r.record().toRecord(cs), cs);
                m.acctReadFlag = '1';                     // SET FOUND-ACCT-IN-MASTER
            } else if (m.respCd == 13) {
                setInputError();
                m.acctFlag = '0';
                if (msgOff()) {
                    m.errorResp = respText(m.respCd);
                    m.errorResp2 = respText(m.reasCd);
                    m.returnMsg = fit("Account:" + m.ridAcctIdX + " not found in" + " Acct Master file.Resp:"
                            + m.errorResp + " Reas:" + m.errorResp2, 75);
                }
            } else {
                setInputError();
                m.acctFlag = '0';
                m.errorOpname = fit("READ", 8);
                m.errorFile = fit("ACCTDAT", 9);
                m.errorResp = respText(m.respCd);
                m.errorResp2 = respText(m.reasCd);
                m.returnMsg = fit(fileErrorMessage(), 75);
            }
        }

        private Optional<AccountRecord> findAccount(Long key) {
            return readAcctdat(key);
        }

        private Optional<CustomerRecord> findCustomer(Long key) {
            return key > Integer.MAX_VALUE ? Optional.empty() : readCustdat((int) (long) key);
        }

        // 9400-GETCUSTDATA-BYCUST
        private void getCustDataByCust() {
            Optional<Long> key = keyOf(m.ridCustIdX);
            CicsTask.FileRead<CustomerRecord> r = task.read("CUSTDAT", () -> key.flatMap(this::findCustomer));
            m.respCd = r.resp();
            m.reasCd = r.resp2();
            if (m.respCd == 0) {
                cust = CustomerRecord.fromRecord(r.record().toRecord(cs), cs);
                m.custReadFlag = '1';                     // SET FOUND-CUST-IN-MASTER
            } else if (m.respCd == 13) {
                setInputError();
                m.custFlag = '0';
                m.errorResp = respText(m.respCd);
                m.errorResp2 = respText(m.reasCd);
                if (msgOff()) {
                    m.returnMsg = fit("CustId:" + m.ridCustIdX + " not found" + " in customer master.Resp: "
                            + m.errorResp + " REAS:" + m.errorResp2, 75);
                }
            } else {
                setInputError();
                m.custFlag = '0';
                m.errorOpname = fit("READ", 8);
                m.errorFile = fit("CUSTDAT", 9);
                m.errorResp = respText(m.respCd);
                m.errorResp2 = respText(m.reasCd);
                m.returnMsg = fit(fileErrorMessage(), 75);
            }
        }

        private long num(Number n) {
            return n == null ? 0 : n.longValue();
        }

        // 9500-STORE-FETCHED-DATA
        private void storeFetchedData() {
            // Store context in the COMMAREA
            cdAcctId = num(acct.getAcctId());
            cdCustId = (int) num(cust.getCustId());
            cdCustFname = fit(cust.getCustFirstName(), 25);
            cdCustMname = fit(cust.getCustMiddleName(), 25);
            cdCustLname = fit(cust.getCustLastName(), 25);
            cdAcctStatus = fit(acct.getAcctActiveStatus(), 1);
            cdCardNum = Long.parseLong(moveAlnumToNumeric(xref.getXrefCardNum(), 16));

            initOld();                                    // INITIALIZE ACUP-OLD-DETAILS
            oAcctIdX = digits(num(acct.getAcctId()), 11);
            oStatus = fit(acct.getAcctActiveStatus(), 1);
            oBal = zoned12(dec(acct.getAcctCurrBal()));
            oCredit = zoned12(dec(acct.getAcctCreditLimit()));
            oCash = zoned12(dec(acct.getAcctCashCreditLimit()));
            oCyCr = zoned12(dec(acct.getAcctCurrCycCredit()));
            oCyDb = zoned12(dec(acct.getAcctCurrCycDebit()));
            String od = fit(acct.getAcctOpenDate(), 10);
            oOpen = sub(od, 1, 4) + sub(od, 6, 2) + sub(od, 9, 2);
            String ed = fit(acct.getAcctExpiraionDate(), 10);
            oExp = sub(ed, 1, 4) + sub(ed, 6, 2) + sub(ed, 9, 2);
            String rd = fit(acct.getAcctReissueDate(), 10);
            oReis = sub(rd, 1, 4) + sub(rd, 6, 2) + sub(rd, 9, 2);
            oGrp = fit(acct.getAcctGroupId(), 10);

            oCustIdX = digits(num(cust.getCustId()), 9);
            oSsnX = digits(num(cust.getCustSsn()), 9);
            String dob = fit(cust.getCustDobYyyyMmDd(), 10);
            oDob = sub(dob, 1, 4) + sub(dob, 6, 2) + sub(dob, 9, 2);
            oFico = digits(num(cust.getCustFicoCreditScore()), 3);
            oFirst = fit(cust.getCustFirstName(), 25);
            oMid = fit(cust.getCustMiddleName(), 25);
            oLast = fit(cust.getCustLastName(), 25);
            oAd1 = fit(cust.getCustAddrLine1(), 50);
            oAd2 = fit(cust.getCustAddrLine2(), 50);
            oAd3 = fit(cust.getCustAddrLine3(), 50);
            oState = fit(cust.getCustAddrStateCd(), 2);
            oCtry = fit(cust.getCustAddrCountryCd(), 3);
            oZip = fit(cust.getCustAddrZip(), 10);
            oPh1 = fit(cust.getCustPhoneNum1(), 15);
            oPh2 = fit(cust.getCustPhoneNum2(), 15);
            oGovt = fit(cust.getCustGovtIssuedId(), 20);
            oEft = fit(cust.getCustEftAccountId(), 10);
            oPri = fit(cust.getCustPriCardHolderInd(), 1);
        }

        private BigDecimal dec(BigDecimal v) {
            return v == null ? BigDecimal.ZERO : v;
        }

        // =============================================================================================
        // 9600-WRITE-PROCESSING
        // =============================================================================================
        private void writeProcessing() {
            m.ridAcctIdX = moveAlnumToNumeric(ccAcctId, 11);   // MOVE CC-ACCT-ID TO WS-CARD-RID-ACCT-ID

            // Read the account file for update
            Optional<Long> akey = keyOf(m.ridAcctIdX);
            CicsTask.FileRead<AccountRecord> ar = task.readForUpdate("ACCTDAT", () -> akey.flatMap(this::findAccount));
            m.respCd = ar.resp();
            m.reasCd = ar.resp2();
            if (m.respCd == 0) {
                acct = AccountRecord.fromRecord(ar.record().toRecord(cs), cs);
            } else {
                setInputError();
                if (msgOff()) {
                    m.returnMsg = fit(MSG_COULD_NOT_LOCK_ACCT, 75);
                }
                return;
            }

            // Read the customer file for update
            m.ridCustIdX = digits(cdCustId, 9);
            Optional<Long> ckey = keyOf(m.ridCustIdX);
            CicsTask.FileRead<CustomerRecord> cr = task.readForUpdate("CUSTDAT", () -> ckey.flatMap(this::findCustomer));
            m.respCd = cr.resp();
            m.reasCd = cr.resp2();
            if (m.respCd == 0) {
                cust = CustomerRecord.fromRecord(cr.record().toRecord(cs), cs);
            } else {
                setInputError();
                if (msgOff()) {
                    m.returnMsg = fit(MSG_COULD_NOT_LOCK_CUST, 75);
                }
                return;
            }

            // Did someone change the record while we were out ?
            checkChangeInRec();
            if (retMsgIs(MSG_DATA_WAS_CHANGED)) {
                return;
            }

            // Prepare the update: INITIALIZE ACCT-UPDATE-RECORD (RECLN 300)
            byte[] arec = CobolRecords.blank(300, cs);
            CobolRecords.putZoned(arec, 0, 11, 0, false, new BigDecimal(numView(nAcctIdX)), cs);       // ACCT-UPDATE-ID
            CobolRecords.putText(arec, 11, 1, nStatus, cs);                                             // ACTIVE-STATUS
            CobolRecords.putZoned(arec, 12, 12, 2, true, z12(nBal), cs);                                // CURR-BAL
            CobolRecords.putZoned(arec, 24, 12, 2, true, z12(nCredit), cs);                             // CREDIT-LIMIT
            CobolRecords.putZoned(arec, 36, 12, 2, true, z12(nCash), cs);                               // CASH-CREDIT-LIMIT
            CobolRecords.putText(arec, 48, 10, sub(nOpen, 1, 4) + "-" + sub(nOpen, 5, 2) + "-" + sub(nOpen, 7, 2), cs);
            CobolRecords.putText(arec, 58, 10, sub(nExp, 1, 4) + "-" + sub(nExp, 5, 2) + "-" + sub(nExp, 7, 2), cs);
            CobolRecords.putText(arec, 68, 10, sub(nReis, 1, 4) + "-" + sub(nReis, 5, 2) + "-" + sub(nReis, 7, 2), cs);
            CobolRecords.putZoned(arec, 78, 12, 2, true, z12(nCyCr), cs);                               // CURR-CYC-CREDIT
            CobolRecords.putZoned(arec, 90, 12, 2, true, z12(nCyDb), cs);                               // CURR-CYC-DEBIT
            // DEFECT KEPT: ACCT-UPDATE-RECORD has no ACCT-ADDR-ZIP, so its GROUP-ID lands on the ACCOUNT-RECORD's
            // ACCT-ADDR-ZIP bytes (102-111) and ACCT-GROUP-ID (112-121) is rewritten as spaces.
            // One-line fix: add 15 ACCT-UPDATE-ADDR-ZIP PIC X(10) before GROUP-ID (and move ACCT-ADDR-ZIP to it).
            CobolRecords.putText(arec, 102, 10, nGrp, cs);                                              // GROUP-ID

            // INITIALIZE CUST-UPDATE-RECORD (RECLN 500)
            byte[] crec = CobolRecords.blank(500, cs);
            CobolRecords.putZoned(crec, 0, 9, 0, false, new BigDecimal(numView(nCustIdX)), cs);
            CobolRecords.putText(crec, 9, 25, nFirst, cs);
            CobolRecords.putText(crec, 34, 25, nMid, cs);
            CobolRecords.putText(crec, 59, 25, nLast, cs);
            CobolRecords.putText(crec, 84, 50, nAd1, cs);
            CobolRecords.putText(crec, 134, 50, nAd2, cs);
            CobolRecords.putText(crec, 184, 50, nAd3, cs);
            CobolRecords.putText(crec, 234, 2, nState, cs);
            CobolRecords.putText(crec, 236, 3, nCtry, cs);
            CobolRecords.putText(crec, 239, 10, nZip, cs);
            CobolRecords.putText(crec, 249, 15,
                    "(" + sub(nPh1, 2, 3) + ")" + sub(nPh1, 6, 3) + "-" + sub(nPh1, 10, 4), cs);
            CobolRecords.putText(crec, 264, 15,
                    "(" + sub(nPh2, 2, 3) + ")" + sub(nPh2, 6, 3) + "-" + sub(nPh2, 10, 4), cs);
            CobolRecords.putZoned(crec, 279, 9, 0, false, new BigDecimal(numView(nSsnX())), cs);
            CobolRecords.putText(crec, 288, 20, nGovt, cs);
            CobolRecords.putText(crec, 308, 10, sub(nDob, 1, 4) + "-" + sub(nDob, 5, 2) + "-" + sub(nDob, 7, 2), cs);
            CobolRecords.putText(crec, 318, 10, nEft, cs);
            CobolRecords.putText(crec, 328, 1, nPri, cs);
            CobolRecords.putZoned(crec, 329, 3, 0, false, new BigDecimal(numView(nFico)), cs);

            // Update account: EXEC CICS REWRITE FILE(LIT-ACCTFILENAME) FROM(ACCT-UPDATE-RECORD)
            int resp = task.rewrite("ACCTDAT", () -> rewriteAcctdat(AccountRecord.fromRecord(arec, cs)));
            m.respCd = resp;
            if (resp != 0) {
                m.returnMsg = fit(MSG_LOCKED_BUT_UPDATE_FAILED, 75);   // SET LOCKED-BUT-UPDATE-FAILED
                return;
            }

            // Update customer: EXEC CICS REWRITE FILE(LIT-CUSTFILENAME) FROM(CUST-UPDATE-RECORD)
            resp = task.rewrite("CUSTDAT", () -> rewriteCustdat(CustomerRecord.fromRecord(crec, cs)));
            m.respCd = resp;
            if (resp != 0) {
                m.returnMsg = fit(MSG_LOCKED_BUT_UPDATE_FAILED, 75);
                task.rollback();                          // EXEC CICS SYNCPOINT ROLLBACK (rollbackL4099)
            }
        }

        // 9700-CHECK-CHANGE-IN-REC
        private void checkChangeInRec() {
            String od = fit(acct.getAcctOpenDate(), 10);
            String ed = fit(acct.getAcctExpiraionDate(), 10);
            String rd = fit(acct.getAcctReissueDate(), 10);
            boolean acctSame = same(fit(acct.getAcctActiveStatus(), 1), oStatus)
                    && dec(acct.getAcctCurrBal()).compareTo(z12(oBal)) == 0
                    && dec(acct.getAcctCreditLimit()).compareTo(z12(oCredit)) == 0
                    && dec(acct.getAcctCashCreditLimit()).compareTo(z12(oCash)) == 0
                    && dec(acct.getAcctCurrCycCredit()).compareTo(z12(oCyCr)) == 0
                    && dec(acct.getAcctCurrCycDebit()).compareTo(z12(oCyDb)) == 0
                    && same(sub(od, 1, 4), sub(oOpen, 1, 4))
                    && same(sub(od, 6, 2), sub(oOpen, 5, 2))
                    && same(sub(od, 9, 2), sub(oOpen, 7, 2))
                    && same(sub(ed, 1, 4), sub(oExp, 1, 4))
                    && same(sub(ed, 6, 2), sub(oExp, 5, 2))
                    && same(sub(ed, 9, 2), sub(oExp, 7, 2))
                    && same(sub(rd, 1, 4), sub(oReis, 1, 4))
                    && same(sub(rd, 6, 2), sub(oReis, 5, 2))
                    && same(sub(rd, 9, 2), sub(oReis, 7, 2))
                    && same(fit(acct.getAcctGroupId(), 10).toLowerCase(Locale.ROOT), oGrp.toLowerCase(Locale.ROOT));
            if (!acctSame) {
                m.returnMsg = fit(MSG_DATA_WAS_CHANGED, 75);   // SET DATA-WAS-CHANGED-BEFORE-UPDATE
                return;
            }

            String dob = fit(cust.getCustDobYyyyMmDd(), 10);
            boolean custSame = upperSame(cust.getCustFirstName(), oFirst, 25)
                    && upperSame(cust.getCustMiddleName(), oMid, 25)
                    && upperSame(cust.getCustLastName(), oLast, 25)
                    && upperSame(cust.getCustAddrLine1(), oAd1, 50)
                    && upperSame(cust.getCustAddrLine2(), oAd2, 50)
                    && upperSame(cust.getCustAddrLine3(), oAd3, 50)
                    && upperSame(cust.getCustAddrStateCd(), oState, 2)
                    && upperSame(cust.getCustAddrCountryCd(), oCtry, 3)
                    && same(fit(cust.getCustAddrZip(), 10), oZip)
                    && same(fit(cust.getCustPhoneNum1(), 15), oPh1)
                    && same(fit(cust.getCustPhoneNum2(), 15), oPh2)
                    && num(cust.getCustSsn()) == numView(oSsnX)
                    && upperSame(cust.getCustGovtIssuedId(), oGovt, 20)
                    && same(sub(dob, 1, 4), sub(oDob, 1, 4))
                    && same(sub(dob, 6, 2), sub(oDob, 5, 2))
                    && same(sub(dob, 9, 2), sub(oDob, 7, 2))
                    && same(fit(cust.getCustEftAccountId(), 10), oEft)
                    && same(fit(cust.getCustPriCardHolderInd(), 1), oPri)
                    && num(cust.getCustFicoCreditScore()) == numView(oFico);
            if (!custSame) {
                m.returnMsg = fit(MSG_DATA_WAS_CHANGED, 75);
            }
        }

        private boolean upperSame(String a, String b, int len) {
            return same(fit(a, len).toUpperCase(Locale.ROOT), fit(b, len).toUpperCase(Locale.ROOT));
        }

        // =============================================================================================
        // ABEND-ROUTINE
        // =============================================================================================
        private void abendRoutine() {
            if (isAll(m.abendMsg, LV)) {
                m.abendMsg = fit("UNEXPECTED ABEND OCCURRED.", 72);
            }
            // MOVE LIT-THISPGM TO ABEND-CULPRIT; EXEC CICS SEND FROM(ABEND-DATA) LENGTH(LENGTH OF ABEND-DATA) NOHANDLE ERASE
            String abendData = abendData(m.abendCode, m.abendReason, m.abendMsg);
            task.sendText(abendData, abendData.length(), "NOHANDLE", "ERASE");
            task.handleAbendCancel();                     // EXEC CICS HANDLE ABEND CANCEL
            task.abend("9999");                           // EXEC CICS ABEND ABCODE('9999')
            ended = true;
        }
    }
}
