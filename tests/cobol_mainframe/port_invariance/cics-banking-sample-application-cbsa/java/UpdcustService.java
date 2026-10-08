// gitgalaxy-det-port: COBOL UPDCUST (UPDCUST.cbl), translated by rule, statement for statement
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.batch.CobolAbend;
import com.gitgalaxy.modernized.batch.CobolFiles;
import com.gitgalaxy.modernized.batch.DatasetResolver;
import com.gitgalaxy.modernized.batch.Dd;
import com.gitgalaxy.modernized.batch.MainframeClock;
import com.gitgalaxy.modernized.batch.Sysout;
import com.gitgalaxy.modernized.cobolrt.batch.DetFiles;
import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import com.gitgalaxy.modernized.cobolrt.Figurative;
import com.gitgalaxy.modernized.cobolrt.Funcs;
import com.gitgalaxy.modernized.cobolrt.Hole;
import com.gitgalaxy.modernized.cobolrt.Storage;
import com.gitgalaxy.modernized.entity.vsam.CobolRecords;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.cobolrt.cics.DetCics;
import com.gitgalaxy.modernized.dto.screen.*;
import com.gitgalaxy.modernized.dto.contract.*;
import com.gitgalaxy.modernized.entity.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.*;
import com.gitgalaxy.modernized.repository.vsam.OutputDataRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * UPDCUST: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 64, translated 64, holes 0.
 */
@Service
public class UpdcustService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_SORTCODE = Base64.getDecoder().decode(String.join("",
            "OTg3NjU0"));
    private static final byte[] IMAGE_s_WS_CICS_WORK_AREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_DB2_DATE_REFORMAT = Base64.getDecoder().decode(String.join("",
            "MDAwMCAwMCAwMA=="));
    private static final byte[] IMAGE_s_WS_CUST_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMDAwMDAwMDAwMDAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMA=="));
    private static final byte[] IMAGE_s_WS_EIBTASKN12 = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_WS_SQLCODE_DISP = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_DESIRED_CUST_KEY = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDAwMA=="));
    private static final byte[] IMAGE_s_WS_CUST_REC_LEN = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_U_TIME = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAw="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE_GRP_X = Base64.getDecoder().decode(String.join("",
            "ICAuICAuICAgIA=="));
    private static final byte[] IMAGE_s_REJ_REASON = Base64.getDecoder().decode(String.join("",
            "ICA="));
    private static final byte[] IMAGE_s_WS_PASSED_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMCAgIA=="));
    private static final byte[] IMAGE_s_WS_SORT_DIV = Base64.getDecoder().decode(String.join("",
            "ICAgICAg"));
    private static final byte[] IMAGE_s_CUSTOMER_KY = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_STORM_DRAIN_CONDITION = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_WS_UNSTR_TITLE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_TITLE_VALID = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_TIME_DATA = Base64.getDecoder().decode(String.join("",
            "MDAwMDAw"));
    private static final byte[] IMAGE_s_WS_ABEND_PGM = Base64.getDecoder().decode(String.join("",
            "QUJORFBST0M="));
    private static final byte[] IMAGE_s_ABNDINFO_REC = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAwwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKzAwMDAwMDAwKzAwMDAwMDAwKzAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgMDAwMDAwMDAwMDAwMDAwMDAwMCAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_SORTCODE = new Storage(IMAGE_s_SORTCODE.length);
    private final Storage s_WS_CICS_WORK_AREA = new Storage(IMAGE_s_WS_CICS_WORK_AREA.length);
    private final Storage s_DB2_DATE_REFORMAT = new Storage(IMAGE_s_DB2_DATE_REFORMAT.length);
    private final Storage s_WS_CUST_DATA = new Storage(IMAGE_s_WS_CUST_DATA.length);
    private final Storage s_WS_EIBTASKN12 = new Storage(IMAGE_s_WS_EIBTASKN12.length);
    private final Storage s_WS_SQLCODE_DISP = new Storage(IMAGE_s_WS_SQLCODE_DISP.length);
    private final Storage s_DESIRED_CUST_KEY = new Storage(IMAGE_s_DESIRED_CUST_KEY.length);
    private final Storage s_WS_CUST_REC_LEN = new Storage(IMAGE_s_WS_CUST_REC_LEN.length);
    private final Storage s_WS_U_TIME = new Storage(IMAGE_s_WS_U_TIME.length);
    private final Storage s_WS_ORIG_DATE = new Storage(IMAGE_s_WS_ORIG_DATE.length);
    private final Storage s_WS_ORIG_DATE_GRP_X = new Storage(IMAGE_s_WS_ORIG_DATE_GRP_X.length);
    private final Storage s_REJ_REASON = new Storage(IMAGE_s_REJ_REASON.length);
    private final Storage s_WS_PASSED_DATA = new Storage(IMAGE_s_WS_PASSED_DATA.length);
    private final Storage s_WS_SORT_DIV = new Storage(IMAGE_s_WS_SORT_DIV.length);
    private final Storage s_CUSTOMER_KY = new Storage(IMAGE_s_CUSTOMER_KY.length);
    private final Storage s_STORM_DRAIN_CONDITION = new Storage(IMAGE_s_STORM_DRAIN_CONDITION.length);
    private final Storage s_WS_UNSTR_TITLE = new Storage(IMAGE_s_WS_UNSTR_TITLE.length);
    private final Storage s_WS_TITLE_VALID = new Storage(IMAGE_s_WS_TITLE_VALID.length);
    private final Storage s_WS_TIME_DATA = new Storage(IMAGE_s_WS_TIME_DATA.length);
    private final Storage s_WS_ABEND_PGM = new Storage(IMAGE_s_WS_ABEND_PGM.length);
    private final Storage s_ABNDINFO_REC = new Storage(IMAGE_s_ABNDINFO_REC.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_SORTCODE = Field.zoned(s_SORTCODE, 0, 6, 0, false, false, false);
    private final Field f12_WS_CUST_DATA = Field.group(s_WS_CUST_DATA, 0, 259);
    private final Field f14_CUSTOMER_EYECATCHER = Field.alphanumeric(s_WS_CUST_DATA, 0, 4, false);
    private final Field f16_CUSTOMER_SORTCODE = Field.zoned(s_WS_CUST_DATA, 4, 6, 0, false, false, false);
    private final Field f17_CUSTOMER_NUMBER = Field.zoned(s_WS_CUST_DATA, 10, 10, 0, false, false, false);
    private final Field f18_CUSTOMER_NAME = Field.alphanumeric(s_WS_CUST_DATA, 20, 60, false);
    private final Field f19_CUSTOMER_ADDRESS = Field.alphanumeric(s_WS_CUST_DATA, 80, 160, false);
    private final Field f20_CUSTOMER_DATE_OF_BIRTH = Field.zoned(s_WS_CUST_DATA, 240, 8, 0, false, false, false);
    private final Field f25_CUSTOMER_CREDIT_SCORE = Field.zoned(s_WS_CUST_DATA, 248, 3, 0, false, false, false);
    private final Field f26_CUSTOMER_CS_REVIEW_DATE = Field.zoned(s_WS_CUST_DATA, 251, 8, 0, false, false, false);
    private final Field f33_DESIRED_CUST_KEY = Field.group(s_DESIRED_CUST_KEY, 0, 16);
    private final Field f34_DESIRED_SORT_CODE = Field.zoned(s_DESIRED_CUST_KEY, 0, 6, 0, false, false, false);
    private final Field f35_DESIRED_CUSTNO = Field.zoned(s_DESIRED_CUST_KEY, 6, 10, 0, false, false, false);
    private final Field f36_WS_CUST_REC_LEN = Field.binary(s_WS_CUST_REC_LEN, 0, 4, 0, true, false);
    private final Field f37_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);
    private final Field f38_WS_ORIG_DATE = Field.alphanumeric(s_WS_ORIG_DATE, 0, 10, false);
    private final Field f67_WS_UNSTR_TITLE = Field.alphanumeric(s_WS_UNSTR_TITLE, 0, 9, false);
    private final Field f68_WS_TITLE_VALID = Field.alphanumeric(s_WS_TITLE_VALID, 0, 1, false);
    private final Field f70_WS_TIME_NOW = Field.zoned(s_WS_TIME_DATA, 0, 6, 0, false, false, false);
    private final Field f91_COMM_EYE = Field.alphanumeric(s_DFHCOMMAREA, 0, 4, false);
    private final Field f92_COMM_SCODE = Field.alphanumeric(s_DFHCOMMAREA, 4, 6, false);
    private final Field f93_COMM_CUSTNO = Field.alphanumeric(s_DFHCOMMAREA, 10, 10, false);
    private final Field f94_COMM_NAME = Field.alphanumeric(s_DFHCOMMAREA, 20, 60, false);
    private final Field f95_COMM_ADDR = Field.alphanumeric(s_DFHCOMMAREA, 80, 160, false);
    private final Field f96_COMM_DOB = Field.zoned(s_DFHCOMMAREA, 240, 8, 0, false, false, false);
    private final Field f101_COMM_CREDIT_SCORE = Field.zoned(s_DFHCOMMAREA, 248, 3, 0, false, false, false);
    private final Field f102_COMM_CS_REVIEW_DATE = Field.zoned(s_DFHCOMMAREA, 251, 8, 0, false, false, false);
    private final Field f107_COMM_UPD_SUCCESS = Field.alphanumeric(s_DFHCOMMAREA, 259, 1, false);
    private final Field f108_COMM_UPD_FAIL_CD = Field.alphanumeric(s_DFHCOMMAREA, 260, 1, false);
    private final Field f110_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f111_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f112_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f113_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f114_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f117_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f138_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f139_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f141_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private BigDecimal f2_SYSIDERR_RETRY;  // SYSIDERR-RETRY PIC 999 DISPLAY
    private long f4_WS_CICS_RESP;  // WS-CICS-RESP PIC S9(8) BINARY
    private long f5_WS_CICS_RESP2;  // WS-CICS-RESP2 PIC S9(8) BINARY

    private static OutputDataKey id_OutputData(byte[] rec) {
        Storage s = Storage.of(rec);
        OutputDataKey k = new OutputDataKey();
        k.setCustomerSortcode(Cobol.num(Field.zoned(s, 4, 6, 0, false, false, false), CS).intValue());
        k.setCustomerNumber(Cobol.num(Field.zoned(s, 10, 10, 0, false, false, false), CS).longValue());
        return k;
    }

    private CicsTask task;
    private final java.util.Map<String, Integer> handlers = new java.util.HashMap<>();
    private final java.util.Map<String, DetCics.Store<?>> stores = new java.util.HashMap<>();
    private final java.util.Map<String, byte[]> heldKey = new java.util.HashMap<>();
    /** Writes the COMMAREA's bytes back into the object the task carries (a LINKed program's is its caller's). */
    private Runnable caBack = () -> { };

    /** The program ends because of an abend: a LINKed program's COMMAREA writes stay its caller's. */
    private Goback abended() {
        if (task.level() > 1) {
            caBack.run();
        }
        return new Goback();
    }

    @SuppressWarnings("unchecked")
    private <E> DetCics.Store<E> store(String name) {
        return (DetCics.Store<E>) stores.computeIfAbsent(name, n -> switch (n) {
            case "CUSTOMER" -> new DetCics.Store<OutputData>(outputDataRepository::findAll, e -> e.toRecord(CS), b -> OutputData.fromRecord(b, CS), e -> task.write("CUSTOMER", () -> outputDataRepository.save(e)), e -> task.write("CUSTOMER", () -> outputDataRepository.delete(e)), 4, 16, CS).withFindById(rec -> outputDataRepository.findById(id_OutputData(rec)));
            default -> throw new Hole("CICS file " + n + ": no store in the generated project");
        });
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("PTD999", 11),
            java.util.Map.entry("PTD010", 10),
            java.util.Map.entry("POPULATE-TIME-DATE", 9),
            java.util.Map.entry("GMOOH999", 8),
            java.util.Map.entry("GMOOH010", 7),
            java.util.Map.entry("GET-ME-OUT-OF-HERE", 6),
            java.util.Map.entry("UCV999", 5),
            java.util.Map.entry("UCV010", 4),
            java.util.Map.entry("UPDATE-CUSTOMER-VSAM", 3),
            java.util.Map.entry("A999", 2),
            java.util.Map.entry("A010", 1),
            java.util.Map.entry("PREMIERE", 0)
    );

    private static int paragraph(String name) {
        Integer i = PARAGRAPHS.get(name);
        if (i == null) {
            throw new IllegalStateException("no paragraph " + name);
        }
        return i;
    }

    /** A condition the command did not return in RESP: its HANDLE CONDITION label, or -1 (go on) when IGNOREd
     *  (#4414); else CICS's default action -- -1 for one whose default is to ignore it (#4413: EOC); else the
     *  ERROR label (#4502: IBM, HANDLE CONDITION: "if the default action for such a condition terminates the
     *  task abnormally, and the condition ERROR has been specified, the action for ERROR is taken"); else an
     *  abend, to this program's HANDLE ABEND exit or ending the task. */
    private int condition(String cond) {
        Integer h = handlers.get(cond);
        if (h != null) {
            return h;
        }
        if (DetCics.ignoredByDefault(cond)) {
            return -1;
        }
        Integer error = handlers.get("ERROR");
        if (error != null) {
            return error;
        }
        String label = task.abendOnCondition(cond);
        if (label == null) {
            throw abended();
        }
        return paragraph(label);
    }

    private static int cx(CicsTask task, int whole) {
        return task.eibcalen() == null ? whole : task.eibcalen();
    }

    private void in_UpdcustDfhcommarea(UpdcustDfhcommarea d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getCommEye() == null ? "" : d.getCommEye(), Field.alphanumeric(s, base + 0, 4, false), CS);
        Cobol.move(d.getCommScode() == null ? "" : d.getCommScode(), Field.alphanumeric(s, base + 4, 6, false), CS);
        Cobol.move(d.getCommCustno() == null ? "" : d.getCommCustno(), Field.alphanumeric(s, base + 10, 10, false), CS);
        Cobol.move(d.getCommName() == null ? "" : d.getCommName(), Field.alphanumeric(s, base + 20, 60, false), CS);
        Cobol.move(d.getCommAddr() == null ? "" : d.getCommAddr(), Field.alphanumeric(s, base + 80, 160, false), CS);
        Cobol.move(d.getCommDob() == null ? BigDecimal.ZERO : new BigDecimal(d.getCommDob().toString()), Field.zoned(s, base + 240, 8, 0, false, false, false), CS);
        Cobol.move(d.getCommCreditScore() == null ? BigDecimal.ZERO : new BigDecimal(d.getCommCreditScore().toString()), Field.zoned(s, base + 248, 3, 0, false, false, false), CS);
        Cobol.move(d.getCommCsReviewDate() == null ? BigDecimal.ZERO : new BigDecimal(d.getCommCsReviewDate().toString()), Field.zoned(s, base + 251, 8, 0, false, false, false), CS);
        Cobol.move(d.getCommUpdSuccess() == null ? "" : d.getCommUpdSuccess(), Field.alphanumeric(s, base + 259, 1, false), CS);
        Cobol.move(d.getCommUpdFailCd() == null ? "" : d.getCommUpdFailCd(), Field.alphanumeric(s, base + 260, 1, false), CS);
    }

    private void fill_UpdcustDfhcommarea(UpdcustDfhcommarea d, Storage s, int base) {
        d.setCommEye(Cobol.text(Field.alphanumeric(s, base + 0, 4, false), CS));
        d.setCommScode(Cobol.text(Field.alphanumeric(s, base + 4, 6, false), CS));
        d.setCommCustno(Cobol.text(Field.alphanumeric(s, base + 10, 10, false), CS));
        d.setCommName(Cobol.text(Field.alphanumeric(s, base + 20, 60, false), CS));
        d.setCommAddr(Cobol.text(Field.alphanumeric(s, base + 80, 160, false), CS));
        d.setCommDob(Cobol.num(Field.zoned(s, base + 240, 8, 0, false, false, false), CS).intValue());
        d.setCommCreditScore(Cobol.num(Field.zoned(s, base + 248, 3, 0, false, false, false), CS).intValue());
        d.setCommCsReviewDate(Cobol.num(Field.zoned(s, base + 251, 8, 0, false, false, false), CS).intValue());
        d.setCommUpdSuccess(Cobol.text(Field.alphanumeric(s, base + 259, 1, false), CS));
        d.setCommUpdFailCd(Cobol.text(Field.alphanumeric(s, base + 260, 1, false), CS));
    }

    private UpdcustDfhcommarea out_UpdcustDfhcommarea(Storage s, int base) {
        UpdcustDfhcommarea d = new UpdcustDfhcommarea();
        fill_UpdcustDfhcommarea(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }


    private final OutputDataRepository outputDataRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public UpdcustService(OutputDataRepository outputDataRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.outputDataRepository = outputDataRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
        System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
        System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
        System.arraycopy(IMAGE_s_WS_CUST_DATA, 0, s_WS_CUST_DATA.bytes, 0, IMAGE_s_WS_CUST_DATA.length);
        System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
        System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
        System.arraycopy(IMAGE_s_DESIRED_CUST_KEY, 0, s_DESIRED_CUST_KEY.bytes, 0, IMAGE_s_DESIRED_CUST_KEY.length);
        System.arraycopy(IMAGE_s_WS_CUST_REC_LEN, 0, s_WS_CUST_REC_LEN.bytes, 0, IMAGE_s_WS_CUST_REC_LEN.length);
        System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
        System.arraycopy(IMAGE_s_REJ_REASON, 0, s_REJ_REASON.bytes, 0, IMAGE_s_REJ_REASON.length);
        System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
        System.arraycopy(IMAGE_s_WS_SORT_DIV, 0, s_WS_SORT_DIV.bytes, 0, IMAGE_s_WS_SORT_DIV.length);
        System.arraycopy(IMAGE_s_CUSTOMER_KY, 0, s_CUSTOMER_KY.bytes, 0, IMAGE_s_CUSTOMER_KY.length);
        System.arraycopy(IMAGE_s_STORM_DRAIN_CONDITION, 0, s_STORM_DRAIN_CONDITION.bytes, 0, IMAGE_s_STORM_DRAIN_CONDITION.length);
        System.arraycopy(IMAGE_s_WS_UNSTR_TITLE, 0, s_WS_UNSTR_TITLE.bytes, 0, IMAGE_s_WS_UNSTR_TITLE.length);
        System.arraycopy(IMAGE_s_WS_TITLE_VALID, 0, s_WS_TITLE_VALID.bytes, 0, IMAGE_s_WS_TITLE_VALID.length);
        System.arraycopy(IMAGE_s_WS_TIME_DATA, 0, s_WS_TIME_DATA.bytes, 0, IMAGE_s_WS_TIME_DATA.length);
        System.arraycopy(IMAGE_s_WS_ABEND_PGM, 0, s_WS_ABEND_PGM.bytes, 0, IMAGE_s_WS_ABEND_PGM.length);
        System.arraycopy(IMAGE_s_ABNDINFO_REC, 0, s_ABNDINFO_REC.bytes, 0, IMAGE_s_ABNDINFO_REC.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        f2_SYSIDERR_RETRY = new BigDecimal("0");
        f4_WS_CICS_RESP = 0L;
        f5_WS_CICS_RESP2 = 0L;
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 11);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f141_GG_RETURN_CODE, CS).intValue();
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            this.task = task;
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            initialState();
            Cobol.move(task.transid(), f112_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f114_EIBTRMID, CS);
            Cobol.store(f113_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f111_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f110_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof UpdcustDfhcommarea x) {
                in_UpdcustDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_UpdcustDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 261);
            }
            byte[] raw = task.linkArea();
            if (raw != null) {
                System.arraycopy(raw, 0, s_DFHCOMMAREA.bytes, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length));
                Runnable typed = caBack;
                caBack = () -> { typed.run(); System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length)); };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f117_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 11);
                } catch (Goback g) {
                    // RETURN / XCTL / an abend ended the program
                }
            } catch (IndexOutOfBoundsException e) {
                if (caWhole == null) {
                    throw e;
                }
                throw new DetCics.PastFrom("COMMAREA past EIBCALEN (" + calen + " bytes): not modelled");
            } finally {
                if (caWhole != null) {
                    caWhole(caWhole);
                }
            }
            if (!task.ended()) {
                caBack.run();
                task.returnTransid(null, null);  // a GOBACK is a RETURN
            }
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    public UpdcustDfhcommarea handleLink(UpdcustDfhcommarea request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("UPDCUST", request);
        region.run(task, "UPDCUST", this::runTask);
        return request;
    }


    /** GOBACK / STOP RUN. */
    private static final class Goback extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Goback() {
            super(null, null, false, false);
        }
    }

    private static Dd dd(List<Dd> dds, String name) {
        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElse(null);
    }

    /** The batch entry. */
    public int runBatch(List<Dd> dds, String parm) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        boolean pfdBefore = Cobol.swapNumprocPfd(false);  // NUMPROC(NOPFD)
        try {
            initialState();
            try {
                perform(0, 11);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f141_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
            Cobol.swapNumprocPfd(pfdBefore);
        }
    }

    /** The active PERFORMs' last paragraphs, outermost first. */
    private int[] performThru = new int[64];
    private int performDepth = 0;

    /** Control reached the end of an outer active PERFORM's range: that PERFORM returns (`depth`). */
    private static final class PerformExit extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final int depth;

        PerformExit(int depth) {
            super(null, null, false, false);
            this.depth = depth;
        }
    }

    /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERFORM
     *  whose range ends there returns -- this one, or an outer one a GO TO reached the end of, abandoning
     *  the PERFORMs inside it (GnuCOBOL, as IBM: test_det_programs.py, GOTOOUT). */
    private void perform(int from, int thru) {
        int mine = performDepth;
        if (mine == performThru.length) {
            performThru = java.util.Arrays.copyOf(performThru, mine * 2);
        }
        performThru[performDepth++] = thru;
        try {
            int i = from;
            while (true) {
                int next = run(i);
                boolean jumped = (next & GOTO) != 0;
                next &= ~GOTO;
                if (!jumped) {
                    if (i == thru) {
                        return;
                    }
                    for (int d = mine - 1; d >= 0; d--) {
                        if (performThru[d] == i) {
                            throw new PerformExit(d);
                        }
                    }
                }
                if (next >= 12) {
                    throw new Goback();
                }
                i = next;
            }
        } catch (PerformExit e) {
            if (e.depth != mine) {
                throw e;
            }
        } finally {
            performDepth = mine;
        }
    }

    private int run(int i) {
        switch (i) {
            case 0: return p0();
            case 1: return p1();
            case 2: return p2();
            case 3: return p3();
            case 4: return p4();
            case 5: return p5();
            case 6: return p6();
            case 7: return p7();
            case 8: return p8();
            case 9: return p9();
            case 10: return p10();
            case 11: return p11();
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** PREMIERE. */
    private int p0() {

        return 1;
    }

    /** A010. */
    private int p1() {
        // MOVE SORTCODE TO COMM-SCODE DESIRED-SORT-CODE
        Cobol.move(f1_SORTCODE, f92_COMM_SCODE, CS);
        Cobol.move(f1_SORTCODE, f34_DESIRED_SORT_CODE, CS);
        // MOVE SPACES TO WS-UNSTR-TITLE
        Cobol.moveFigurative(Figurative.SPACES, f67_WS_UNSTR_TITLE, CS);
        // UNSTRING COMM-NAME DELIMITED BY SPACE INTO WS-UNSTR-TITLE
        Cobol.unstring(f94_COMM_NAME, null, null, java.util.List.of(Cobol.Delim.of(" ", false, CS)), CS, Cobol.Into.of(f67_WS_UNSTR_TITLE));
        // MOVE ' ' TO WS-TITLE-VALID
        Cobol.move(" ", f68_WS_TITLE_VALID, CS);
        // EVALUATE WS-UNSTR-TITLE
        if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Professor", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Mr       ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Mrs      ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Miss     ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Ms       ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Dr       ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Drs      ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Lord     ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Sir      ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "Lady     ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if ((Cobol.compare(f67_WS_UNSTR_TITLE, "         ", CS) == 0)) {
            // MOVE 'Y' TO WS-TITLE-VALID
            Cobol.move("Y", f68_WS_TITLE_VALID, CS);
        } else if (true) {
            // MOVE 'N' TO WS-TITLE-VALID
            Cobol.move("N", f68_WS_TITLE_VALID, CS);
        }
        // IF WS-TITLE-VALID = 'N'
        if (Cobol.compare(f68_WS_TITLE_VALID, "N", CS) == 0) {
            // MOVE 'N' TO COMM-UPD-SUCCESS
            Cobol.move("N", f107_COMM_UPD_SUCCESS, CS);
            // MOVE 'T' TO COMM-UPD-FAIL-CD
            Cobol.move("T", f108_COMM_UPD_FAIL_CD, CS);
            // GOBACK
            if (true) throw new Goback();
        }
        // PERFORM UPDATE-CUSTOMER-VSAM
        perform(3, 5);
        // PERFORM GET-ME-OUT-OF-HERE
        perform(6, 8);
        return 2;
    }

    /** A999. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** UPDATE-CUSTOMER-VSAM. */
    private int p3() {

        return 4;
    }

    /** UCV010. */
    private int p4() {
        // MOVE COMM-CUSTNO TO DESIRED-CUSTNO
        Cobol.move(f93_COMM_CUSTNO, f35_DESIRED_CUSTNO, CS);
        // EXEC CICS READ FILE('CUSTOMER') RIDFLD(DESIRED-CUST-KEY) INTO(WS-CUST-DATA) UPDATE RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
        byte[] rec2 = DetCics.bytes(f33_DESIRED_CUST_KEY);
        CicsTask.FileRead<byte[]> read1 = task.readForUpdate("CUSTOMER".strip(), () -> store("CUSTOMER".strip()).find(rec2));
        if (read1.record() != null) {
            DetCics.put(f12_WS_CUST_DATA, read1.record());
            heldKey.put("CUSTOMER".strip(), rec2);
        }
        Cobol.store(f138_EIBRESP, BigDecimal.valueOf(read1.resp()), false, CS);
        Cobol.store(f139_EIBRESP2, BigDecimal.valueOf(read1.resp2()), false, CS);
        f4_WS_CICS_RESP = Cobol.binary(BigDecimal.valueOf(read1.resp()), 8, true, false, CS);
        f5_WS_CICS_RESP2 = Cobol.binary(BigDecimal.valueOf(read1.resp2()), 8, true, false, CS);
        // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
        if (!(f4_WS_CICS_RESP == 0L)) {
            // MOVE 'N' TO COMM-UPD-SUCCESS
            Cobol.move("N", f107_COMM_UPD_SUCCESS, CS);
            // IF WS-CICS-RESP = DFHRESP(NOTFND)
            if (f4_WS_CICS_RESP == 13L) {
                // MOVE '1' TO COMM-UPD-FAIL-CD
                Cobol.move("1", f108_COMM_UPD_FAIL_CD, CS);
            } else {
                // MOVE '2' TO COMM-UPD-FAIL-CD
                Cobol.move("2", f108_COMM_UPD_FAIL_CD, CS);
            }
            // GO TO UCV999
            if (true) return GOTO | 5;
        }
        // IF (COMM-NAME = SPACES OR COMM-NAME(1:1) = ' ') AND (COMM-ADDR = SPACES OR COMM-ADDR(1:1) = ' ')
        if (((Cobol.compareFigurative(f94_COMM_NAME, Figurative.SPACES, CS) == 0 || Cobol.compare(f94_COMM_NAME.ref(1, Integer.valueOf(1)), " ", CS) == 0) && (Cobol.compareFigurative(f95_COMM_ADDR, Figurative.SPACES, CS) == 0 || Cobol.compare(f95_COMM_ADDR.ref(1, Integer.valueOf(1)), " ", CS) == 0))) {
            // MOVE 'N' TO COMM-UPD-SUCCESS
            Cobol.move("N", f107_COMM_UPD_SUCCESS, CS);
            // MOVE '4' TO COMM-UPD-FAIL-CD
            Cobol.move("4", f108_COMM_UPD_FAIL_CD, CS);
            // GO TO UCV999
            if (true) return GOTO | 5;
        }
        // IF (COMM-NAME = SPACES OR COMM-NAME(1:1) = ' ') AND (COMM-ADDR NOT = SPACES OR COMM-ADDR(1:1) NOT = ' ')
        if (((Cobol.compareFigurative(f94_COMM_NAME, Figurative.SPACES, CS) == 0 || Cobol.compare(f94_COMM_NAME.ref(1, Integer.valueOf(1)), " ", CS) == 0) && (!(Cobol.compareFigurative(f95_COMM_ADDR, Figurative.SPACES, CS) == 0) || !(Cobol.compare(f95_COMM_ADDR.ref(1, Integer.valueOf(1)), " ", CS) == 0)))) {
            // MOVE COMM-ADDR TO CUSTOMER-ADDRESS OF WS-CUST-DATA
            Cobol.move(f95_COMM_ADDR, f19_CUSTOMER_ADDRESS, CS);
        }
        // IF (COMM-ADDR = SPACES OR COMM-ADDR(1:1) = ' ') AND (COMM-NAME NOT = SPACES OR COMM-NAME(1:1) NOT = ' ')
        if (((Cobol.compareFigurative(f95_COMM_ADDR, Figurative.SPACES, CS) == 0 || Cobol.compare(f95_COMM_ADDR.ref(1, Integer.valueOf(1)), " ", CS) == 0) && (!(Cobol.compareFigurative(f94_COMM_NAME, Figurative.SPACES, CS) == 0) || !(Cobol.compare(f94_COMM_NAME.ref(1, Integer.valueOf(1)), " ", CS) == 0)))) {
            // MOVE COMM-NAME TO CUSTOMER-NAME OF WS-CUST-DATA
            Cobol.move(f94_COMM_NAME, f18_CUSTOMER_NAME, CS);
        }
        // IF COMM-ADDR(1:1) NOT = ' ' AND COMM-NAME(1:1) NOT = ' '
        if ((!(Cobol.compare(f95_COMM_ADDR.ref(1, Integer.valueOf(1)), " ", CS) == 0) && !(Cobol.compare(f94_COMM_NAME.ref(1, Integer.valueOf(1)), " ", CS) == 0))) {
            // MOVE COMM-ADDR TO CUSTOMER-ADDRESS OF WS-CUST-DATA
            Cobol.move(f95_COMM_ADDR, f19_CUSTOMER_ADDRESS, CS);
            // MOVE COMM-NAME TO CUSTOMER-NAME OF WS-CUST-DATA
            Cobol.move(f94_COMM_NAME, f18_CUSTOMER_NAME, CS);
        }
        // COMPUTE WS-CUST-REC-LEN = LENGTH OF WS-CUST-DATA
        BigDecimal v3 = BigDecimal.valueOf(259);
        Cobol.store(f36_WS_CUST_REC_LEN, v3, false, CS);
        // EXEC CICS REWRITE FILE ('CUSTOMER') FROM (WS-CUST-DATA) LENGTH(WS-CUST-REC-LEN) RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
        int resp4 = task.rewrite("CUSTOMER".strip(), () -> store("CUSTOMER".strip()).store(DetCics.bytes(f12_WS_CUST_DATA, Cobol.num(f36_WS_CUST_REC_LEN, CS).intValue())));
        Cobol.store(f138_EIBRESP, BigDecimal.valueOf(resp4), false, CS);
        Cobol.store(f139_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        f4_WS_CICS_RESP = Cobol.binary(BigDecimal.valueOf(resp4), 8, true, false, CS);
        f5_WS_CICS_RESP2 = Cobol.binary(BigDecimal.valueOf(0), 8, true, false, CS);
        // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
        if (!(f4_WS_CICS_RESP == 0L)) {
            // MOVE 'N' TO COMM-UPD-SUCCESS
            Cobol.move("N", f107_COMM_UPD_SUCCESS, CS);
            // MOVE '3' TO COMM-UPD-FAIL-CD
            Cobol.move("3", f108_COMM_UPD_FAIL_CD, CS);
            // GO TO UCV999
            if (true) return GOTO | 5;
        }
        // MOVE CUSTOMER-EYECATCHER OF WS-CUST-DATA TO COMM-EYE
        Cobol.move(f14_CUSTOMER_EYECATCHER, f91_COMM_EYE, CS);
        // MOVE CUSTOMER-SORTCODE OF WS-CUST-DATA TO COMM-SCODE
        Cobol.move(f16_CUSTOMER_SORTCODE, f92_COMM_SCODE, CS);
        // MOVE CUSTOMER-NUMBER OF WS-CUST-DATA TO COMM-CUSTNO
        Cobol.move(f17_CUSTOMER_NUMBER, f93_COMM_CUSTNO, CS);
        // MOVE CUSTOMER-NAME OF WS-CUST-DATA TO COMM-NAME
        Cobol.move(f18_CUSTOMER_NAME, f94_COMM_NAME, CS);
        // MOVE CUSTOMER-ADDRESS OF WS-CUST-DATA TO COMM-ADDR
        Cobol.move(f19_CUSTOMER_ADDRESS, f95_COMM_ADDR, CS);
        // MOVE CUSTOMER-DATE-OF-BIRTH OF WS-CUST-DATA TO COMM-DOB
        Cobol.move(f20_CUSTOMER_DATE_OF_BIRTH, f96_COMM_DOB, CS);
        // MOVE CUSTOMER-CREDIT-SCORE OF WS-CUST-DATA TO COMM-CREDIT-SCORE
        Cobol.move(f25_CUSTOMER_CREDIT_SCORE, f101_COMM_CREDIT_SCORE, CS);
        // MOVE CUSTOMER-CS-REVIEW-DATE OF WS-CUST-DATA TO COMM-CS-REVIEW-DATE
        Cobol.move(f26_CUSTOMER_CS_REVIEW_DATE, f102_COMM_CS_REVIEW_DATE, CS);
        // MOVE 'Y' TO COMM-UPD-SUCCESS
        Cobol.move("Y", f107_COMM_UPD_SUCCESS, CS);
        return 5;
    }

    /** UCV999. */
    private int p5() {
        // EXIT
        return 6;
    }

    /** GET-ME-OUT-OF-HERE. */
    private int p6() {

        return 7;
    }

    /** GMOOH010. */
    private int p7() {
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 8;
    }

    /** GMOOH999. */
    private int p8() {
        // EXIT
        return 9;
    }

    /** POPULATE-TIME-DATE. */
    private int p9() {

        return 10;
    }

    /** PTD010. */
    private int p10() {
        // EXEC CICS ASKTIME ABSTIME(WS-U-TIME) END-EXEC
        Cobol.store(f37_WS_U_TIME, BigDecimal.valueOf(task.asktime()), false, CS);
        // EXEC CICS FORMATTIME ABSTIME(WS-U-TIME) DDMMYYYY(WS-ORIG-DATE) TIME(WS-TIME-NOW) DATESEP END-EXEC
        Cobol.move(CicsTask.formatDate(Cobol.num(f37_WS_U_TIME, CS).longValue(), "DDMMYYYY", "/"), f38_WS_ORIG_DATE, CS);
        Cobol.move(CicsTask.formatTime(Cobol.num(f37_WS_U_TIME, CS).longValue(), ""), f70_WS_TIME_NOW, CS);
        return 11;
    }

    /** PTD999. */
    private int p11() {
        // EXIT
        return 12;
    }

}
