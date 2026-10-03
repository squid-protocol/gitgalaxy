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
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D13 = new BigDecimal("13");

    private static final byte[] IMAGE_s_SORTCODE = Base64.getDecoder().decode(String.join("",
            "OTg3NjU0"));
    private static final byte[] IMAGE_s_SYSIDERR_RETRY = Base64.getDecoder().decode(String.join("",
            "MDAw"));
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
    private final Storage s_SYSIDERR_RETRY = new Storage(IMAGE_s_SYSIDERR_RETRY.length);
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

    private Field f100_COMM_BIRTH_YEAR;
    private Field f101_COMM_CREDIT_SCORE;
    private Field f102_COMM_CS_REVIEW_DATE;
    private Field f103_COMM_CS_GROUP;
    private Field f104_COMM_CS_DAY;
    private Field f105_COMM_CS_MONTH;
    private Field f106_COMM_CS_YEAR;
    private Field f107_COMM_UPD_SUCCESS;
    private Field f108_COMM_UPD_FAIL_CD;
    private Field f109_DFHEIBLK;
    private Field f10_FILLER;
    private Field f110_EIBTIME;
    private Field f111_EIBDATE;
    private Field f112_EIBTRNID;
    private Field f113_EIBTASKN;
    private Field f114_EIBTRMID;
    private Field f115_DFHEIGDI;
    private Field f116_EIBCPOSN;
    private Field f117_EIBCALEN;
    private Field f118_EIBAID;
    private Field f119_EIBFN;
    private Field f11_DB2_DATE_REF_DAY;
    private Field f120_EIBRCODE;
    private Field f121_EIBDS;
    private Field f122_EIBREQID;
    private Field f123_EIBRSRCE;
    private Field f124_EIBSYNC;
    private Field f125_EIBFREE;
    private Field f126_EIBRECV;
    private Field f127_EIBSEND;
    private Field f128_EIBATT;
    private Field f129_EIBEOC;
    private Field f12_WS_CUST_DATA;
    private Field f130_EIBFMH;
    private Field f131_EIBCOMPL;
    private Field f132_EIBSIG;
    private Field f133_EIBCONF;
    private Field f134_EIBERR;
    private Field f135_EIBERRCD;
    private Field f136_EIBSYNRB;
    private Field f137_EIBNODAT;
    private Field f138_EIBRESP;
    private Field f139_EIBRESP2;
    private Field f13_CUSTOMER_RECORD;
    private Field f140_EIBRLDBK;
    private Field f141_GG_RETURN_CODE;
    private Field f14_CUSTOMER_EYECATCHER;
    private Field f15_CUSTOMER_KEY;
    private Field f16_CUSTOMER_SORTCODE;
    private Field f17_CUSTOMER_NUMBER;
    private Field f18_CUSTOMER_NAME;
    private Field f19_CUSTOMER_ADDRESS;
    private Field f1_SORTCODE;
    private Field f20_CUSTOMER_DATE_OF_BIRTH;
    private Field f21_CUSTOMER_DOB_GROUP;
    private Field f22_CUSTOMER_BIRTH_DAY;
    private Field f23_CUSTOMER_BIRTH_MONTH;
    private Field f24_CUSTOMER_BIRTH_YEAR;
    private Field f25_CUSTOMER_CREDIT_SCORE;
    private Field f26_CUSTOMER_CS_REVIEW_DATE;
    private Field f27_CUSTOMER_CS_GROUP;
    private Field f28_CUSTOMER_CS_REVIEW_DAY;
    private Field f29_CUSTOMER_CS_REVIEW_MONTH;
    private Field f2_SYSIDERR_RETRY;
    private Field f30_CUSTOMER_CS_REVIEW_YEAR;
    private Field f31_WS_EIBTASKN12;
    private Field f32_WS_SQLCODE_DISP;
    private Field f33_DESIRED_CUST_KEY;
    private Field f34_DESIRED_SORT_CODE;
    private Field f35_DESIRED_CUSTNO;
    private Field f36_WS_CUST_REC_LEN;
    private Field f37_WS_U_TIME;
    private Field f38_WS_ORIG_DATE;
    private Field f39_WS_ORIG_DATE_GRP;
    private Field f3_WS_CICS_WORK_AREA;
    private Field f40_WS_ORIG_DATE_DD;
    private Field f41_FILLER;
    private Field f42_WS_ORIG_DATE_MM;
    private Field f43_FILLER;
    private Field f44_WS_ORIG_DATE_YYYY;
    private Field f45_WS_ORIG_DATE_GRP_X;
    private Field f46_WS_ORIG_DATE_DD_X;
    private Field f47_FILLER;
    private Field f48_WS_ORIG_DATE_MM_X;
    private Field f49_FILLER;
    private Field f4_WS_CICS_RESP;
    private Field f50_WS_ORIG_DATE_YYYY_X;
    private Field f51_REJ_REASON;
    private Field f52_WS_PASSED_DATA;
    private Field f53_WS_TEST_KEY;
    private Field f54_WS_SORT_CODE;
    private Field f55_WS_CUSTOMER_RANGE;
    private Field f56_WS_CUSTOMER_RANGE_TOP;
    private Field f57_WS_CUSTOMER_RANGE_MIDDLE;
    private Field f58_WS_CUSTOMER_RANGE_BOTTOM;
    private Field f59_WS_SORT_DIV;
    private Field f5_WS_CICS_RESP2;
    private Field f60_WS_SORT_DIV1;
    private Field f61_WS_SORT_DIV2;
    private Field f62_WS_SORT_DIV3;
    private Field f63_CUSTOMER_KY;
    private Field f64_REQUIRED_SORT_CODE;
    private Field f65_REQUIRED_ACC_NUM;
    private Field f66_STORM_DRAIN_CONDITION;
    private Field f67_WS_UNSTR_TITLE;
    private Field f68_WS_TITLE_VALID;
    private Field f69_WS_TIME_DATA;
    private Field f6_DB2_DATE_REFORMAT;
    private Field f70_WS_TIME_NOW;
    private Field f71_WS_TIME_NOW_GRP;
    private Field f72_WS_TIME_NOW_GRP_HH;
    private Field f73_WS_TIME_NOW_GRP_MM;
    private Field f74_WS_TIME_NOW_GRP_SS;
    private Field f75_WS_ABEND_PGM;
    private Field f76_ABNDINFO_REC;
    private Field f77_ABND_VSAM_KEY;
    private Field f78_ABND_UTIME_KEY;
    private Field f79_ABND_TASKNO_KEY;
    private Field f7_DB2_DATE_REF_YR;
    private Field f80_ABND_APPLID;
    private Field f81_ABND_TRANID;
    private Field f82_ABND_DATE;
    private Field f83_ABND_TIME;
    private Field f84_ABND_CODE;
    private Field f85_ABND_PROGRAM;
    private Field f86_ABND_RESPCODE;
    private Field f87_ABND_RESP2CODE;
    private Field f88_ABND_SQLCODE;
    private Field f89_ABND_FREEFORM;
    private Field f8_FILLER;
    private Field f90_DFHCOMMAREA;
    private Field f91_COMM_EYE;
    private Field f92_COMM_SCODE;
    private Field f93_COMM_CUSTNO;
    private Field f94_COMM_NAME;
    private Field f95_COMM_ADDR;
    private Field f96_COMM_DOB;
    private Field f97_COMM_DOB_GROUP;
    private Field f98_COMM_BIRTH_DAY;
    private Field f99_COMM_BIRTH_MONTH;
    private Field f9_DB2_DATE_REF_MNTH;

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

    /** A condition the command neither returned in RESP nor ignored: its HANDLE CONDITION label, or CICS's
     *  default action -- an abend, to this program's HANDLE ABEND exit or ending the task. */
    private int condition(String cond) {
        Integer h = handlers.get(cond);
        if (h != null) {
            return h;
        }
        String label = task.abendOnCondition(cond);
        if (label == null) {
            throw new Goback();
        }
        return paragraph(label);
    }

    private static int cx(CicsTask task, int whole) {
        return task.eibcalen() == null ? whole : task.eibcalen();
    }

    private void in_UpdcustUpdcustCommarea(UpdcustUpdcustCommarea d, Storage s, int base) {
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

    private void fill_UpdcustUpdcustCommarea(UpdcustUpdcustCommarea d, Storage s, int base) {
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

    private UpdcustUpdcustCommarea out_UpdcustUpdcustCommarea(Storage s, int base) {
        UpdcustUpdcustCommarea d = new UpdcustUpdcustCommarea();
        fill_UpdcustUpdcustCommarea(d, s, base);
        return d;
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
        fields0();
    }

    private void fields0() {
        f1_SORTCODE = Field.zoned(s_SORTCODE, 0, 6, 0, false, false, false);
        f2_SYSIDERR_RETRY = Field.zoned(s_SYSIDERR_RETRY, 0, 3, 0, false, false, false);
        f3_WS_CICS_WORK_AREA = Field.group(s_WS_CICS_WORK_AREA, 0, 8);
        f4_WS_CICS_RESP = Field.binary(s_WS_CICS_WORK_AREA, 0, 8, 0, true, false);
        f5_WS_CICS_RESP2 = Field.binary(s_WS_CICS_WORK_AREA, 4, 8, 0, true, false);
        f6_DB2_DATE_REFORMAT = Field.group(s_DB2_DATE_REFORMAT, 0, 10);
        f7_DB2_DATE_REF_YR = Field.zoned(s_DB2_DATE_REFORMAT, 0, 4, 0, false, false, false);
        f8_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 4, 1, false);
        f9_DB2_DATE_REF_MNTH = Field.zoned(s_DB2_DATE_REFORMAT, 5, 2, 0, false, false, false);
        f10_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 7, 1, false);
        f11_DB2_DATE_REF_DAY = Field.zoned(s_DB2_DATE_REFORMAT, 8, 2, 0, false, false, false);
        f12_WS_CUST_DATA = Field.group(s_WS_CUST_DATA, 0, 259);
        f13_CUSTOMER_RECORD = Field.group(s_WS_CUST_DATA, 0, 259);
        f14_CUSTOMER_EYECATCHER = Field.alphanumeric(s_WS_CUST_DATA, 0, 4, false);
        f15_CUSTOMER_KEY = Field.group(s_WS_CUST_DATA, 4, 16);
        f16_CUSTOMER_SORTCODE = Field.zoned(s_WS_CUST_DATA, 4, 6, 0, false, false, false);
        f17_CUSTOMER_NUMBER = Field.zoned(s_WS_CUST_DATA, 10, 10, 0, false, false, false);
        f18_CUSTOMER_NAME = Field.alphanumeric(s_WS_CUST_DATA, 20, 60, false);
        f19_CUSTOMER_ADDRESS = Field.alphanumeric(s_WS_CUST_DATA, 80, 160, false);
        f20_CUSTOMER_DATE_OF_BIRTH = Field.zoned(s_WS_CUST_DATA, 240, 8, 0, false, false, false);
        f21_CUSTOMER_DOB_GROUP = Field.group(s_WS_CUST_DATA, 240, 8);
        f22_CUSTOMER_BIRTH_DAY = Field.zoned(s_WS_CUST_DATA, 240, 2, 0, false, false, false);
        f23_CUSTOMER_BIRTH_MONTH = Field.zoned(s_WS_CUST_DATA, 242, 2, 0, false, false, false);
        f24_CUSTOMER_BIRTH_YEAR = Field.zoned(s_WS_CUST_DATA, 244, 4, 0, false, false, false);
        f25_CUSTOMER_CREDIT_SCORE = Field.zoned(s_WS_CUST_DATA, 248, 3, 0, false, false, false);
        f26_CUSTOMER_CS_REVIEW_DATE = Field.zoned(s_WS_CUST_DATA, 251, 8, 0, false, false, false);
        f27_CUSTOMER_CS_GROUP = Field.group(s_WS_CUST_DATA, 251, 8);
        f28_CUSTOMER_CS_REVIEW_DAY = Field.zoned(s_WS_CUST_DATA, 251, 2, 0, false, false, false);
        f29_CUSTOMER_CS_REVIEW_MONTH = Field.zoned(s_WS_CUST_DATA, 253, 2, 0, false, false, false);
        f30_CUSTOMER_CS_REVIEW_YEAR = Field.zoned(s_WS_CUST_DATA, 255, 4, 0, false, false, false);
        f31_WS_EIBTASKN12 = Field.zoned(s_WS_EIBTASKN12, 0, 12, 0, false, false, false);
        f32_WS_SQLCODE_DISP = Field.zoned(s_WS_SQLCODE_DISP, 0, 9, 0, false, false, false);
        f33_DESIRED_CUST_KEY = Field.group(s_DESIRED_CUST_KEY, 0, 16);
        f34_DESIRED_SORT_CODE = Field.zoned(s_DESIRED_CUST_KEY, 0, 6, 0, false, false, false);
        f35_DESIRED_CUSTNO = Field.zoned(s_DESIRED_CUST_KEY, 6, 10, 0, false, false, false);
        f36_WS_CUST_REC_LEN = Field.binary(s_WS_CUST_REC_LEN, 0, 4, 0, true, false);
        f37_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);
        f38_WS_ORIG_DATE = Field.alphanumeric(s_WS_ORIG_DATE, 0, 10, false);
        f39_WS_ORIG_DATE_GRP = Field.group(s_WS_ORIG_DATE, 0, 10);
        f40_WS_ORIG_DATE_DD = Field.zoned(s_WS_ORIG_DATE, 0, 2, 0, false, false, false);
        f41_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 2, 1, false);
        f42_WS_ORIG_DATE_MM = Field.zoned(s_WS_ORIG_DATE, 3, 2, 0, false, false, false);
        f43_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 5, 1, false);
        f44_WS_ORIG_DATE_YYYY = Field.zoned(s_WS_ORIG_DATE, 6, 4, 0, false, false, false);
        f45_WS_ORIG_DATE_GRP_X = Field.group(s_WS_ORIG_DATE_GRP_X, 0, 10);
        f46_WS_ORIG_DATE_DD_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 0, 2, false);
        f47_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 2, 1, false);
        f48_WS_ORIG_DATE_MM_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 3, 2, false);
        f49_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 5, 1, false);
        f50_WS_ORIG_DATE_YYYY_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 6, 4, false);
        f51_REJ_REASON = Field.alphanumeric(s_REJ_REASON, 0, 2, false);
        f52_WS_PASSED_DATA = Field.group(s_WS_PASSED_DATA, 0, 13);
        f53_WS_TEST_KEY = Field.alphanumeric(s_WS_PASSED_DATA, 0, 4, false);
        f54_WS_SORT_CODE = Field.zoned(s_WS_PASSED_DATA, 4, 6, 0, false, false, false);
        f55_WS_CUSTOMER_RANGE = Field.group(s_WS_PASSED_DATA, 10, 3);
        f56_WS_CUSTOMER_RANGE_TOP = Field.alphanumeric(s_WS_PASSED_DATA, 10, 1, false);
        f57_WS_CUSTOMER_RANGE_MIDDLE = Field.alphanumeric(s_WS_PASSED_DATA, 11, 1, false);
        f58_WS_CUSTOMER_RANGE_BOTTOM = Field.alphanumeric(s_WS_PASSED_DATA, 12, 1, false);
        f59_WS_SORT_DIV = Field.group(s_WS_SORT_DIV, 0, 6);
        f60_WS_SORT_DIV1 = Field.alphanumeric(s_WS_SORT_DIV, 0, 2, false);
        f61_WS_SORT_DIV2 = Field.alphanumeric(s_WS_SORT_DIV, 2, 2, false);
        f62_WS_SORT_DIV3 = Field.alphanumeric(s_WS_SORT_DIV, 4, 2, false);
        f63_CUSTOMER_KY = Field.group(s_CUSTOMER_KY, 0, 14);
        f64_REQUIRED_SORT_CODE = Field.zoned(s_CUSTOMER_KY, 0, 6, 0, false, false, false);
        f65_REQUIRED_ACC_NUM = Field.zoned(s_CUSTOMER_KY, 6, 8, 0, false, false, false);
        f66_STORM_DRAIN_CONDITION = Field.alphanumeric(s_STORM_DRAIN_CONDITION, 0, 20, false);
        f67_WS_UNSTR_TITLE = Field.alphanumeric(s_WS_UNSTR_TITLE, 0, 9, false);
        f68_WS_TITLE_VALID = Field.alphanumeric(s_WS_TITLE_VALID, 0, 1, false);
        f69_WS_TIME_DATA = Field.group(s_WS_TIME_DATA, 0, 6);
        f70_WS_TIME_NOW = Field.zoned(s_WS_TIME_DATA, 0, 6, 0, false, false, false);
        f71_WS_TIME_NOW_GRP = Field.group(s_WS_TIME_DATA, 0, 6);
        f72_WS_TIME_NOW_GRP_HH = Field.zoned(s_WS_TIME_DATA, 0, 2, 0, false, false, false);
        f73_WS_TIME_NOW_GRP_MM = Field.zoned(s_WS_TIME_DATA, 2, 2, 0, false, false, false);
        f74_WS_TIME_NOW_GRP_SS = Field.zoned(s_WS_TIME_DATA, 4, 2, 0, false, false, false);
        f75_WS_ABEND_PGM = Field.alphanumeric(s_WS_ABEND_PGM, 0, 8, false);
        f76_ABNDINFO_REC = Field.group(s_ABNDINFO_REC, 0, 681);
        f77_ABND_VSAM_KEY = Field.group(s_ABNDINFO_REC, 0, 12);
        f78_ABND_UTIME_KEY = Field.packed(s_ABNDINFO_REC, 0, 15, 0, true);
        f79_ABND_TASKNO_KEY = Field.zoned(s_ABNDINFO_REC, 8, 4, 0, false, false, false);
        f80_ABND_APPLID = Field.alphanumeric(s_ABNDINFO_REC, 12, 8, false);
        f81_ABND_TRANID = Field.alphanumeric(s_ABNDINFO_REC, 20, 4, false);
        f82_ABND_DATE = Field.alphanumeric(s_ABNDINFO_REC, 24, 10, false);
        f83_ABND_TIME = Field.alphanumeric(s_ABNDINFO_REC, 34, 8, false);
        f84_ABND_CODE = Field.alphanumeric(s_ABNDINFO_REC, 42, 4, false);
        f85_ABND_PROGRAM = Field.alphanumeric(s_ABNDINFO_REC, 46, 8, false);
        f86_ABND_RESPCODE = Field.zoned(s_ABNDINFO_REC, 54, 8, 0, true, true, true);
        f87_ABND_RESP2CODE = Field.zoned(s_ABNDINFO_REC, 63, 8, 0, true, true, true);
        f88_ABND_SQLCODE = Field.zoned(s_ABNDINFO_REC, 72, 8, 0, true, true, true);
        f89_ABND_FREEFORM = Field.alphanumeric(s_ABNDINFO_REC, 81, 600, false);
        f90_DFHCOMMAREA = Field.group(s_DFHCOMMAREA, 0, 261);
        f91_COMM_EYE = Field.alphanumeric(s_DFHCOMMAREA, 0, 4, false);
        f92_COMM_SCODE = Field.alphanumeric(s_DFHCOMMAREA, 4, 6, false);
        f93_COMM_CUSTNO = Field.alphanumeric(s_DFHCOMMAREA, 10, 10, false);
        f94_COMM_NAME = Field.alphanumeric(s_DFHCOMMAREA, 20, 60, false);
        f95_COMM_ADDR = Field.alphanumeric(s_DFHCOMMAREA, 80, 160, false);
        f96_COMM_DOB = Field.zoned(s_DFHCOMMAREA, 240, 8, 0, false, false, false);
        f97_COMM_DOB_GROUP = Field.group(s_DFHCOMMAREA, 240, 8);
        f98_COMM_BIRTH_DAY = Field.zoned(s_DFHCOMMAREA, 240, 2, 0, false, false, false);
        f99_COMM_BIRTH_MONTH = Field.zoned(s_DFHCOMMAREA, 242, 2, 0, false, false, false);
        f100_COMM_BIRTH_YEAR = Field.zoned(s_DFHCOMMAREA, 244, 4, 0, false, false, false);
        f101_COMM_CREDIT_SCORE = Field.zoned(s_DFHCOMMAREA, 248, 3, 0, false, false, false);
        f102_COMM_CS_REVIEW_DATE = Field.zoned(s_DFHCOMMAREA, 251, 8, 0, false, false, false);
        f103_COMM_CS_GROUP = Field.group(s_DFHCOMMAREA, 251, 8);
        f104_COMM_CS_DAY = Field.zoned(s_DFHCOMMAREA, 251, 2, 0, false, false, false);
        f105_COMM_CS_MONTH = Field.zoned(s_DFHCOMMAREA, 253, 2, 0, false, false, false);
        f106_COMM_CS_YEAR = Field.zoned(s_DFHCOMMAREA, 255, 4, 0, false, false, false);
        f107_COMM_UPD_SUCCESS = Field.alphanumeric(s_DFHCOMMAREA, 259, 1, false);
        f108_COMM_UPD_FAIL_CD = Field.alphanumeric(s_DFHCOMMAREA, 260, 1, false);
        f109_DFHEIBLK = Field.group(s_DFHEIBLK, 0, 85);
        f110_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
        f111_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
        f112_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
        f113_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
        f114_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
        f115_DFHEIGDI = Field.binary(s_DFHEIBLK, 20, 4, 0, true, false);
        f116_EIBCPOSN = Field.binary(s_DFHEIBLK, 22, 4, 0, true, false);
        f117_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
        f118_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
        f119_EIBFN = Field.alphanumeric(s_DFHEIBLK, 27, 2, false);
        f120_EIBRCODE = Field.alphanumeric(s_DFHEIBLK, 29, 6, false);
        f121_EIBDS = Field.alphanumeric(s_DFHEIBLK, 35, 8, false);
        f122_EIBREQID = Field.alphanumeric(s_DFHEIBLK, 43, 8, false);
        f123_EIBRSRCE = Field.alphanumeric(s_DFHEIBLK, 51, 8, false);
        f124_EIBSYNC = Field.alphanumeric(s_DFHEIBLK, 59, 1, false);
        f125_EIBFREE = Field.alphanumeric(s_DFHEIBLK, 60, 1, false);
        f126_EIBRECV = Field.alphanumeric(s_DFHEIBLK, 61, 1, false);
        f127_EIBSEND = Field.alphanumeric(s_DFHEIBLK, 62, 1, false);
        f128_EIBATT = Field.alphanumeric(s_DFHEIBLK, 63, 1, false);
        f129_EIBEOC = Field.alphanumeric(s_DFHEIBLK, 64, 1, false);
        f130_EIBFMH = Field.alphanumeric(s_DFHEIBLK, 65, 1, false);
        f131_EIBCOMPL = Field.alphanumeric(s_DFHEIBLK, 66, 1, false);
        f132_EIBSIG = Field.alphanumeric(s_DFHEIBLK, 67, 1, false);
        f133_EIBCONF = Field.alphanumeric(s_DFHEIBLK, 68, 1, false);
        f134_EIBERR = Field.alphanumeric(s_DFHEIBLK, 69, 1, false);
        f135_EIBERRCD = Field.alphanumeric(s_DFHEIBLK, 70, 4, false);
        f136_EIBSYNRB = Field.alphanumeric(s_DFHEIBLK, 74, 1, false);
        f137_EIBNODAT = Field.alphanumeric(s_DFHEIBLK, 75, 1, false);
        f138_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
        f139_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
        f140_EIBRLDBK = Field.alphanumeric(s_DFHEIBLK, 84, 1, false);
        f141_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
        System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
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
        performDepth = 0;
        try {
            perform(0, 11);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f141_GG_RETURN_CODE, CS).intValue();
    }

    public void executeUpdcust() {
        runBatch(List.of(), null);
    }

    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
    public void runTask(CicsTask task) {
        boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)
        try {
            this.task = task;
            caBack = () -> { };
            handlers.clear();
            heldKey.clear();
            System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
            System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
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
            Cobol.move(task.transid(), f112_EIBTRNID, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f111_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f110_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof UpdcustUpdcustCommarea x) {
                in_UpdcustUpdcustCommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_UpdcustUpdcustCommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 261);
            }
            Cobol.store(f117_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 11);
            } catch (Goback g) {
                // RETURN / XCTL / an abend ended the program
            }
            if (!task.ended()) {
                caBack.run();
                task.returnTransid(null, null);  // a GOBACK is a RETURN
            }
        } finally {
            Cobol.swapTruncBinary(truncBefore);
        }
    }

    public UpdcustUpdcustCommarea handleLink(UpdcustUpdcustCommarea request) {
        throw new UnsupportedOperationException("handleLink: this port runs as runTask");
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
        try {
            System.arraycopy(IMAGE_s_SORTCODE, 0, s_SORTCODE.bytes, 0, IMAGE_s_SORTCODE.length);
            System.arraycopy(IMAGE_s_SYSIDERR_RETRY, 0, s_SYSIDERR_RETRY.bytes, 0, IMAGE_s_SYSIDERR_RETRY.length);
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
            try {
                perform(0, 11);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f141_GG_RETURN_CODE, CS).intValue();
        } finally {
            Cobol.swapTruncBinary(truncBefore);
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
        Cobol.store(f4_WS_CICS_RESP, BigDecimal.valueOf(read1.resp()), false, CS);
        Cobol.store(f5_WS_CICS_RESP2, BigDecimal.valueOf(read1.resp2()), false, CS);
        // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
        if (!(Cobol.num(f4_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
            // MOVE 'N' TO COMM-UPD-SUCCESS
            Cobol.move("N", f107_COMM_UPD_SUCCESS, CS);
            // IF WS-CICS-RESP = DFHRESP(NOTFND)
            if (Cobol.num(f4_WS_CICS_RESP, CS).compareTo(D13) == 0) {
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
        Cobol.store(f4_WS_CICS_RESP, BigDecimal.valueOf(resp4), false, CS);
        Cobol.store(f5_WS_CICS_RESP2, BigDecimal.valueOf(0), false, CS);
        // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
        if (!(Cobol.num(f4_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
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
