// gitgalaxy-det-port: COBOL ABNDPROC (ABNDPROC.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.repository.vsam.WsAbndAreaRepository;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * ABNDPROC: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 13, translated 13, holes 0.
 */
@Service
public class AbndprocService {

    private static final Charset CS = CobolRecords.charset();
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_WS_CICS_WORK_AREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAA="));
    private static final byte[] IMAGE_s_WS_ABND_AREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAwwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKzAwMDAwMDAwKzAwMDAwMDAwKzAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_ABND_KEY_LEN = Base64.getDecoder().decode(String.join("",
            "AAAADA=="));
    private static final byte[] IMAGE_s_DB2_DATE_REFORMAT = Base64.getDecoder().decode(String.join("",
            "MDAwMCAwMCAwMA=="));
    private static final byte[] IMAGE_s_DATA_STORE_TYPE = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_WS_EIBTASKN12 = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_WS_SQLCODE_DISP = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAw"));
    private static final byte[] IMAGE_s_WS_U_TIME = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAw="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_ORIG_DATE_GRP_X = Base64.getDecoder().decode(String.join("",
            "ICAuICAuICAgIA=="));
    private static final byte[] IMAGE_s_WS_PASSED_DATA = Base64.getDecoder().decode(String.join("",
            "ICAgIDAwMDAwMCAgIA=="));
    private static final byte[] IMAGE_s_WS_SORT_DIV = Base64.getDecoder().decode(String.join("",
            "ICAgICAg"));
    private static final byte[] IMAGE_s_CUSTOMER_KY = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMDAwMDAwMDA="));
    private static final byte[] IMAGE_s_PROCTRAN_RIDFLD = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_SQLCODE_DISPLAY = Base64.getDecoder().decode(String.join("",
            "KzAwMDAwMDAw"));
    private static final byte[] IMAGE_s_MY_ABEND_CODE = Base64.getDecoder().decode(String.join("",
            "ICAgIA=="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "AAAAAAAAAAwwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKzAwMDAwMDAwKzAwMDAwMDAwKzAwMDAwMDAwICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_WS_CICS_WORK_AREA = new Storage(IMAGE_s_WS_CICS_WORK_AREA.length);
    private final Storage s_WS_ABND_AREA = new Storage(IMAGE_s_WS_ABND_AREA.length);
    private final Storage s_WS_ABND_KEY_LEN = new Storage(IMAGE_s_WS_ABND_KEY_LEN.length);
    private final Storage s_DB2_DATE_REFORMAT = new Storage(IMAGE_s_DB2_DATE_REFORMAT.length);
    private final Storage s_DATA_STORE_TYPE = new Storage(IMAGE_s_DATA_STORE_TYPE.length);
    private final Storage s_WS_EIBTASKN12 = new Storage(IMAGE_s_WS_EIBTASKN12.length);
    private final Storage s_WS_SQLCODE_DISP = new Storage(IMAGE_s_WS_SQLCODE_DISP.length);
    private final Storage s_WS_U_TIME = new Storage(IMAGE_s_WS_U_TIME.length);
    private final Storage s_WS_ORIG_DATE = new Storage(IMAGE_s_WS_ORIG_DATE.length);
    private final Storage s_WS_ORIG_DATE_GRP_X = new Storage(IMAGE_s_WS_ORIG_DATE_GRP_X.length);
    private final Storage s_WS_PASSED_DATA = new Storage(IMAGE_s_WS_PASSED_DATA.length);
    private final Storage s_WS_SORT_DIV = new Storage(IMAGE_s_WS_SORT_DIV.length);
    private final Storage s_CUSTOMER_KY = new Storage(IMAGE_s_CUSTOMER_KY.length);
    private final Storage s_PROCTRAN_RIDFLD = new Storage(IMAGE_s_PROCTRAN_RIDFLD.length);
    private final Storage s_SQLCODE_DISPLAY = new Storage(IMAGE_s_SQLCODE_DISPLAY.length);
    private final Storage s_MY_ABEND_CODE = new Storage(IMAGE_s_MY_ABEND_CODE.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private Field f100_EIBSYNRB;
    private Field f101_EIBNODAT;
    private Field f102_EIBRESP;
    private Field f103_EIBRESP2;
    private Field f104_EIBRLDBK;
    private Field f105_GG_RETURN_CODE;
    private Field f10_ABND_DATE;
    private Field f11_ABND_TIME;
    private Field f12_ABND_CODE;
    private Field f13_ABND_PROGRAM;
    private Field f14_ABND_RESPCODE;
    private Field f15_ABND_RESP2CODE;
    private Field f16_ABND_SQLCODE;
    private Field f17_ABND_FREEFORM;
    private Field f18_WS_ABND_KEY_LEN;
    private Field f19_DB2_DATE_REFORMAT;
    private Field f1_WS_CICS_WORK_AREA;
    private Field f20_DB2_DATE_REF_YR;
    private Field f21_FILLER;
    private Field f22_DB2_DATE_REF_MNTH;
    private Field f23_FILLER;
    private Field f24_DB2_DATE_REF_DAY;
    private Field f25_DATA_STORE_TYPE;
    private Field f26_WS_EIBTASKN12;
    private Field f27_WS_SQLCODE_DISP;
    private Field f28_WS_U_TIME;
    private Field f29_WS_ORIG_DATE;
    private Field f2_WS_CICS_RESP;
    private Field f30_WS_ORIG_DATE_GRP;
    private Field f31_WS_ORIG_DATE_DD;
    private Field f32_FILLER;
    private Field f33_WS_ORIG_DATE_MM;
    private Field f34_FILLER;
    private Field f35_WS_ORIG_DATE_YYYY;
    private Field f36_WS_ORIG_DATE_GRP_X;
    private Field f37_WS_ORIG_DATE_DD_X;
    private Field f38_FILLER;
    private Field f39_WS_ORIG_DATE_MM_X;
    private Field f3_WS_CICS_RESP2;
    private Field f40_FILLER;
    private Field f41_WS_ORIG_DATE_YYYY_X;
    private Field f42_WS_PASSED_DATA;
    private Field f43_WS_TEST_KEY;
    private Field f44_WS_SORT_CODE;
    private Field f45_WS_CUSTOMER_RANGE;
    private Field f46_WS_CUSTOMER_RANGE_TOP;
    private Field f47_WS_CUSTOMER_RANGE_MIDDLE;
    private Field f48_WS_CUSTOMER_RANGE_BOTTOM;
    private Field f49_WS_SORT_DIV;
    private Field f4_WS_ABND_AREA;
    private Field f50_WS_SORT_DIV1;
    private Field f51_WS_SORT_DIV2;
    private Field f52_WS_SORT_DIV3;
    private Field f53_CUSTOMER_KY;
    private Field f54_REQUIRED_SORT_CODE;
    private Field f55_REQUIRED_ACC_NUM;
    private Field f56_PROCTRAN_RIDFLD;
    private Field f57_SQLCODE_DISPLAY;
    private Field f58_MY_ABEND_CODE;
    private Field f59_DFHCOMMAREA;
    private Field f5_ABND_VSAM_KEY;
    private Field f60_COMM_VSAM_KEY;
    private Field f61_COMM_UTIME_KEY;
    private Field f62_COMM_TASKNO_KEY;
    private Field f63_COMM_APPLID;
    private Field f64_COMM_TRANID;
    private Field f65_COMM_DATE;
    private Field f66_COMM_TIME;
    private Field f67_COMM_CODE;
    private Field f68_COMM_PROGRAM;
    private Field f69_COMM_RESPCODE;
    private Field f6_ABND_UTIME_KEY;
    private Field f70_COMM_RESP2CODE;
    private Field f71_COMM_SQLCODE;
    private Field f72_COMM_FREEFORM;
    private Field f73_DFHEIBLK;
    private Field f74_EIBTIME;
    private Field f75_EIBDATE;
    private Field f76_EIBTRNID;
    private Field f77_EIBTASKN;
    private Field f78_EIBTRMID;
    private Field f79_DFHEIGDI;
    private Field f7_ABND_TASKNO_KEY;
    private Field f80_EIBCPOSN;
    private Field f81_EIBCALEN;
    private Field f82_EIBAID;
    private Field f83_EIBFN;
    private Field f84_EIBRCODE;
    private Field f85_EIBDS;
    private Field f86_EIBREQID;
    private Field f87_EIBRSRCE;
    private Field f88_EIBSYNC;
    private Field f89_EIBFREE;
    private Field f8_ABND_APPLID;
    private Field f90_EIBRECV;
    private Field f91_EIBSEND;
    private Field f92_EIBATT;
    private Field f93_EIBEOC;
    private Field f94_EIBFMH;
    private Field f95_EIBCOMPL;
    private Field f96_EIBSIG;
    private Field f97_EIBCONF;
    private Field f98_EIBERR;
    private Field f99_EIBERRCD;
    private Field f9_ABND_TRANID;

    private static WsAbndAreaKey id_WsAbndArea(byte[] rec) {
        Storage s = Storage.of(rec);
        WsAbndAreaKey k = new WsAbndAreaKey();
        k.setAbndUtimeKey(Cobol.num(Field.packed(s, 0, 15, 0, true), CS).longValue());
        k.setAbndTasknoKey(Cobol.num(Field.zoned(s, 8, 4, 0, false, false, false), CS).intValue());
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
            case "ABNDFILE" -> new DetCics.Store<WsAbndArea>(wsAbndAreaRepository::findAll, e -> e.toRecord(CS), b -> WsAbndArea.fromRecord(b, CS), e -> task.write("ABNDFILE", () -> wsAbndAreaRepository.save(e)), e -> task.write("ABNDFILE", () -> wsAbndAreaRepository.delete(e)), 0, 12, CS).withFindById(rec -> wsAbndAreaRepository.findById(id_WsAbndArea(rec)));
            default -> throw new Hole("CICS file " + n + ": no store in the generated project");
        });
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("GMOOH999", 5),
            java.util.Map.entry("GMOOH010", 4),
            java.util.Map.entry("GET-ME-OUT-OF-HERE", 3),
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

    private void in_AbndprocAbndinfoRec(AbndprocAbndinfoRec d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getAbndUtimeKey() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndUtimeKey().toString()), Field.packed(s, base + 0, 15, 0, true), CS);
        Cobol.move(d.getAbndTasknoKey() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndTasknoKey().toString()), Field.zoned(s, base + 8, 4, 0, false, false, false), CS);
        Cobol.move(d.getAbndApplid() == null ? "" : d.getAbndApplid(), Field.alphanumeric(s, base + 12, 8, false), CS);
        Cobol.move(d.getAbndTranid() == null ? "" : d.getAbndTranid(), Field.alphanumeric(s, base + 20, 4, false), CS);
        Cobol.move(d.getAbndDate() == null ? "" : d.getAbndDate(), Field.alphanumeric(s, base + 24, 10, false), CS);
        Cobol.move(d.getAbndTime() == null ? "" : d.getAbndTime(), Field.alphanumeric(s, base + 34, 8, false), CS);
        Cobol.move(d.getAbndCode() == null ? "" : d.getAbndCode(), Field.alphanumeric(s, base + 42, 4, false), CS);
        Cobol.move(d.getAbndProgram() == null ? "" : d.getAbndProgram(), Field.alphanumeric(s, base + 46, 8, false), CS);
        Cobol.move(d.getAbndRespcode() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndRespcode().toString()), Field.zoned(s, base + 54, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndResp2Code() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndResp2Code().toString()), Field.zoned(s, base + 63, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndSqlcode() == null ? BigDecimal.ZERO : new BigDecimal(d.getAbndSqlcode().toString()), Field.zoned(s, base + 72, 8, 0, true, true, true), CS);
        Cobol.move(d.getAbndFreeform() == null ? "" : d.getAbndFreeform(), Field.alphanumeric(s, base + 81, 600, false), CS);
    }

    private void fill_AbndprocAbndinfoRec(AbndprocAbndinfoRec d, Storage s, int base) {
        d.setAbndUtimeKey(Cobol.num(Field.packed(s, base + 0, 15, 0, true), CS).longValue());
        d.setAbndTasknoKey(Cobol.num(Field.zoned(s, base + 8, 4, 0, false, false, false), CS).intValue());
        d.setAbndApplid(Cobol.text(Field.alphanumeric(s, base + 12, 8, false), CS));
        d.setAbndTranid(Cobol.text(Field.alphanumeric(s, base + 20, 4, false), CS));
        d.setAbndDate(Cobol.text(Field.alphanumeric(s, base + 24, 10, false), CS));
        d.setAbndTime(Cobol.text(Field.alphanumeric(s, base + 34, 8, false), CS));
        d.setAbndCode(Cobol.text(Field.alphanumeric(s, base + 42, 4, false), CS));
        d.setAbndProgram(Cobol.text(Field.alphanumeric(s, base + 46, 8, false), CS));
        d.setAbndRespcode(Cobol.num(Field.zoned(s, base + 54, 8, 0, true, true, true), CS).intValue());
        d.setAbndResp2Code(Cobol.num(Field.zoned(s, base + 63, 8, 0, true, true, true), CS).intValue());
        d.setAbndSqlcode(Cobol.num(Field.zoned(s, base + 72, 8, 0, true, true, true), CS).intValue());
        d.setAbndFreeform(Cobol.text(Field.alphanumeric(s, base + 81, 600, false), CS));
    }

    private AbndprocAbndinfoRec out_AbndprocAbndinfoRec(Storage s, int base) {
        AbndprocAbndinfoRec d = new AbndprocAbndinfoRec();
        fill_AbndprocAbndinfoRec(d, s, base);
        return d;
    }


    private final WsAbndAreaRepository wsAbndAreaRepository;
    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public AbndprocService(WsAbndAreaRepository wsAbndAreaRepository, DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.wsAbndAreaRepository = wsAbndAreaRepository;
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
        fields0();
    }

    private void fields0() {
        f1_WS_CICS_WORK_AREA = Field.group(s_WS_CICS_WORK_AREA, 0, 8);
        f2_WS_CICS_RESP = Field.binary(s_WS_CICS_WORK_AREA, 0, 8, 0, true, false);
        f3_WS_CICS_RESP2 = Field.binary(s_WS_CICS_WORK_AREA, 4, 8, 0, true, false);
        f4_WS_ABND_AREA = Field.group(s_WS_ABND_AREA, 0, 681);
        f5_ABND_VSAM_KEY = Field.group(s_WS_ABND_AREA, 0, 12);
        f6_ABND_UTIME_KEY = Field.packed(s_WS_ABND_AREA, 0, 15, 0, true);
        f7_ABND_TASKNO_KEY = Field.zoned(s_WS_ABND_AREA, 8, 4, 0, false, false, false);
        f8_ABND_APPLID = Field.alphanumeric(s_WS_ABND_AREA, 12, 8, false);
        f9_ABND_TRANID = Field.alphanumeric(s_WS_ABND_AREA, 20, 4, false);
        f10_ABND_DATE = Field.alphanumeric(s_WS_ABND_AREA, 24, 10, false);
        f11_ABND_TIME = Field.alphanumeric(s_WS_ABND_AREA, 34, 8, false);
        f12_ABND_CODE = Field.alphanumeric(s_WS_ABND_AREA, 42, 4, false);
        f13_ABND_PROGRAM = Field.alphanumeric(s_WS_ABND_AREA, 46, 8, false);
        f14_ABND_RESPCODE = Field.zoned(s_WS_ABND_AREA, 54, 8, 0, true, true, true);
        f15_ABND_RESP2CODE = Field.zoned(s_WS_ABND_AREA, 63, 8, 0, true, true, true);
        f16_ABND_SQLCODE = Field.zoned(s_WS_ABND_AREA, 72, 8, 0, true, true, true);
        f17_ABND_FREEFORM = Field.alphanumeric(s_WS_ABND_AREA, 81, 600, false);
        f18_WS_ABND_KEY_LEN = Field.binary(s_WS_ABND_KEY_LEN, 0, 8, 0, true, false);
        f19_DB2_DATE_REFORMAT = Field.group(s_DB2_DATE_REFORMAT, 0, 10);
        f20_DB2_DATE_REF_YR = Field.zoned(s_DB2_DATE_REFORMAT, 0, 4, 0, false, false, false);
        f21_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 4, 1, false);
        f22_DB2_DATE_REF_MNTH = Field.zoned(s_DB2_DATE_REFORMAT, 5, 2, 0, false, false, false);
        f23_FILLER = Field.alphanumeric(s_DB2_DATE_REFORMAT, 7, 1, false);
        f24_DB2_DATE_REF_DAY = Field.zoned(s_DB2_DATE_REFORMAT, 8, 2, 0, false, false, false);
        f25_DATA_STORE_TYPE = Field.alphanumeric(s_DATA_STORE_TYPE, 0, 1, false);
        f26_WS_EIBTASKN12 = Field.zoned(s_WS_EIBTASKN12, 0, 12, 0, false, false, false);
        f27_WS_SQLCODE_DISP = Field.zoned(s_WS_SQLCODE_DISP, 0, 9, 0, false, false, false);
        f28_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);
        f29_WS_ORIG_DATE = Field.alphanumeric(s_WS_ORIG_DATE, 0, 10, false);
        f30_WS_ORIG_DATE_GRP = Field.group(s_WS_ORIG_DATE, 0, 10);
        f31_WS_ORIG_DATE_DD = Field.zoned(s_WS_ORIG_DATE, 0, 2, 0, false, false, false);
        f32_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 2, 1, false);
        f33_WS_ORIG_DATE_MM = Field.zoned(s_WS_ORIG_DATE, 3, 2, 0, false, false, false);
        f34_FILLER = Field.alphanumeric(s_WS_ORIG_DATE, 5, 1, false);
        f35_WS_ORIG_DATE_YYYY = Field.zoned(s_WS_ORIG_DATE, 6, 4, 0, false, false, false);
        f36_WS_ORIG_DATE_GRP_X = Field.group(s_WS_ORIG_DATE_GRP_X, 0, 10);
        f37_WS_ORIG_DATE_DD_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 0, 2, false);
        f38_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 2, 1, false);
        f39_WS_ORIG_DATE_MM_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 3, 2, false);
        f40_FILLER = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 5, 1, false);
        f41_WS_ORIG_DATE_YYYY_X = Field.alphanumeric(s_WS_ORIG_DATE_GRP_X, 6, 4, false);
        f42_WS_PASSED_DATA = Field.group(s_WS_PASSED_DATA, 0, 13);
        f43_WS_TEST_KEY = Field.alphanumeric(s_WS_PASSED_DATA, 0, 4, false);
        f44_WS_SORT_CODE = Field.zoned(s_WS_PASSED_DATA, 4, 6, 0, false, false, false);
        f45_WS_CUSTOMER_RANGE = Field.group(s_WS_PASSED_DATA, 10, 3);
        f46_WS_CUSTOMER_RANGE_TOP = Field.alphanumeric(s_WS_PASSED_DATA, 10, 1, false);
        f47_WS_CUSTOMER_RANGE_MIDDLE = Field.alphanumeric(s_WS_PASSED_DATA, 11, 1, false);
        f48_WS_CUSTOMER_RANGE_BOTTOM = Field.alphanumeric(s_WS_PASSED_DATA, 12, 1, false);
        f49_WS_SORT_DIV = Field.group(s_WS_SORT_DIV, 0, 6);
        f50_WS_SORT_DIV1 = Field.alphanumeric(s_WS_SORT_DIV, 0, 2, false);
        f51_WS_SORT_DIV2 = Field.alphanumeric(s_WS_SORT_DIV, 2, 2, false);
        f52_WS_SORT_DIV3 = Field.alphanumeric(s_WS_SORT_DIV, 4, 2, false);
        f53_CUSTOMER_KY = Field.group(s_CUSTOMER_KY, 0, 14);
        f54_REQUIRED_SORT_CODE = Field.zoned(s_CUSTOMER_KY, 0, 6, 0, false, false, false);
        f55_REQUIRED_ACC_NUM = Field.zoned(s_CUSTOMER_KY, 6, 8, 0, false, false, false);
        f56_PROCTRAN_RIDFLD = Field.binary(s_PROCTRAN_RIDFLD, 0, 8, 0, true, false);
        f57_SQLCODE_DISPLAY = Field.zoned(s_SQLCODE_DISPLAY, 0, 8, 0, true, true, true);
        f58_MY_ABEND_CODE = Field.alphanumeric(s_MY_ABEND_CODE, 0, 4, false);
        f59_DFHCOMMAREA = Field.group(s_DFHCOMMAREA, 0, 681);
        f60_COMM_VSAM_KEY = Field.group(s_DFHCOMMAREA, 0, 12);
        f61_COMM_UTIME_KEY = Field.packed(s_DFHCOMMAREA, 0, 15, 0, true);
        f62_COMM_TASKNO_KEY = Field.zoned(s_DFHCOMMAREA, 8, 4, 0, false, false, false);
        f63_COMM_APPLID = Field.alphanumeric(s_DFHCOMMAREA, 12, 8, false);
        f64_COMM_TRANID = Field.alphanumeric(s_DFHCOMMAREA, 20, 4, false);
        f65_COMM_DATE = Field.alphanumeric(s_DFHCOMMAREA, 24, 10, false);
        f66_COMM_TIME = Field.alphanumeric(s_DFHCOMMAREA, 34, 8, false);
        f67_COMM_CODE = Field.alphanumeric(s_DFHCOMMAREA, 42, 4, false);
        f68_COMM_PROGRAM = Field.alphanumeric(s_DFHCOMMAREA, 46, 8, false);
        f69_COMM_RESPCODE = Field.zoned(s_DFHCOMMAREA, 54, 8, 0, true, true, true);
        f70_COMM_RESP2CODE = Field.zoned(s_DFHCOMMAREA, 63, 8, 0, true, true, true);
        f71_COMM_SQLCODE = Field.zoned(s_DFHCOMMAREA, 72, 8, 0, true, true, true);
        f72_COMM_FREEFORM = Field.alphanumeric(s_DFHCOMMAREA, 81, 600, false);
        f73_DFHEIBLK = Field.group(s_DFHEIBLK, 0, 85);
        f74_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
        f75_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
        f76_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
        f77_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
        f78_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
        f79_DFHEIGDI = Field.binary(s_DFHEIBLK, 20, 4, 0, true, false);
        f80_EIBCPOSN = Field.binary(s_DFHEIBLK, 22, 4, 0, true, false);
        f81_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
        f82_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
        f83_EIBFN = Field.alphanumeric(s_DFHEIBLK, 27, 2, false);
        f84_EIBRCODE = Field.alphanumeric(s_DFHEIBLK, 29, 6, false);
        f85_EIBDS = Field.alphanumeric(s_DFHEIBLK, 35, 8, false);
        f86_EIBREQID = Field.alphanumeric(s_DFHEIBLK, 43, 8, false);
        f87_EIBRSRCE = Field.alphanumeric(s_DFHEIBLK, 51, 8, false);
        f88_EIBSYNC = Field.alphanumeric(s_DFHEIBLK, 59, 1, false);
        f89_EIBFREE = Field.alphanumeric(s_DFHEIBLK, 60, 1, false);
        f90_EIBRECV = Field.alphanumeric(s_DFHEIBLK, 61, 1, false);
        f91_EIBSEND = Field.alphanumeric(s_DFHEIBLK, 62, 1, false);
        f92_EIBATT = Field.alphanumeric(s_DFHEIBLK, 63, 1, false);
        f93_EIBEOC = Field.alphanumeric(s_DFHEIBLK, 64, 1, false);
        f94_EIBFMH = Field.alphanumeric(s_DFHEIBLK, 65, 1, false);
        f95_EIBCOMPL = Field.alphanumeric(s_DFHEIBLK, 66, 1, false);
        f96_EIBSIG = Field.alphanumeric(s_DFHEIBLK, 67, 1, false);
        f97_EIBCONF = Field.alphanumeric(s_DFHEIBLK, 68, 1, false);
        f98_EIBERR = Field.alphanumeric(s_DFHEIBLK, 69, 1, false);
        f99_EIBERRCD = Field.alphanumeric(s_DFHEIBLK, 70, 4, false);
        f100_EIBSYNRB = Field.alphanumeric(s_DFHEIBLK, 74, 1, false);
        f101_EIBNODAT = Field.alphanumeric(s_DFHEIBLK, 75, 1, false);
        f102_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
        f103_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
        f104_EIBRLDBK = Field.alphanumeric(s_DFHEIBLK, 84, 1, false);
        f105_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
        System.arraycopy(IMAGE_s_WS_ABND_AREA, 0, s_WS_ABND_AREA.bytes, 0, IMAGE_s_WS_ABND_AREA.length);
        System.arraycopy(IMAGE_s_WS_ABND_KEY_LEN, 0, s_WS_ABND_KEY_LEN.bytes, 0, IMAGE_s_WS_ABND_KEY_LEN.length);
        System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
        System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
        System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
        System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
        System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
        System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
        System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
        System.arraycopy(IMAGE_s_WS_SORT_DIV, 0, s_WS_SORT_DIV.bytes, 0, IMAGE_s_WS_SORT_DIV.length);
        System.arraycopy(IMAGE_s_CUSTOMER_KY, 0, s_CUSTOMER_KY.bytes, 0, IMAGE_s_CUSTOMER_KY.length);
        System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
        System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
        System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        performDepth = 0;
        try {
            perform(0, 5);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f105_GG_RETURN_CODE, CS).intValue();
    }

    public void executeAbndproc() {
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
            System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
            System.arraycopy(IMAGE_s_WS_ABND_AREA, 0, s_WS_ABND_AREA.bytes, 0, IMAGE_s_WS_ABND_AREA.length);
            System.arraycopy(IMAGE_s_WS_ABND_KEY_LEN, 0, s_WS_ABND_KEY_LEN.bytes, 0, IMAGE_s_WS_ABND_KEY_LEN.length);
            System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
            System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
            System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
            System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
            System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
            System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
            System.arraycopy(IMAGE_s_WS_SORT_DIV, 0, s_WS_SORT_DIV.bytes, 0, IMAGE_s_WS_SORT_DIV.length);
            System.arraycopy(IMAGE_s_CUSTOMER_KY, 0, s_CUSTOMER_KY.bytes, 0, IMAGE_s_CUSTOMER_KY.length);
            System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
            System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
            System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
            System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
            System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
            System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
            Cobol.move(task.transid(), f76_EIBTRNID, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f75_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f74_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof AbndprocAbndinfoRec x) {
                in_AbndprocAbndinfoRec(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_AbndprocAbndinfoRec(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 681);
            }
            Cobol.store(f81_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 5);
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

    public AbndprocAbndinfoRec handleLink(AbndprocAbndinfoRec request) {
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
            System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
            System.arraycopy(IMAGE_s_WS_ABND_AREA, 0, s_WS_ABND_AREA.bytes, 0, IMAGE_s_WS_ABND_AREA.length);
            System.arraycopy(IMAGE_s_WS_ABND_KEY_LEN, 0, s_WS_ABND_KEY_LEN.bytes, 0, IMAGE_s_WS_ABND_KEY_LEN.length);
            System.arraycopy(IMAGE_s_DB2_DATE_REFORMAT, 0, s_DB2_DATE_REFORMAT.bytes, 0, IMAGE_s_DB2_DATE_REFORMAT.length);
            System.arraycopy(IMAGE_s_DATA_STORE_TYPE, 0, s_DATA_STORE_TYPE.bytes, 0, IMAGE_s_DATA_STORE_TYPE.length);
            System.arraycopy(IMAGE_s_WS_EIBTASKN12, 0, s_WS_EIBTASKN12.bytes, 0, IMAGE_s_WS_EIBTASKN12.length);
            System.arraycopy(IMAGE_s_WS_SQLCODE_DISP, 0, s_WS_SQLCODE_DISP.bytes, 0, IMAGE_s_WS_SQLCODE_DISP.length);
            System.arraycopy(IMAGE_s_WS_U_TIME, 0, s_WS_U_TIME.bytes, 0, IMAGE_s_WS_U_TIME.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE, 0, s_WS_ORIG_DATE.bytes, 0, IMAGE_s_WS_ORIG_DATE.length);
            System.arraycopy(IMAGE_s_WS_ORIG_DATE_GRP_X, 0, s_WS_ORIG_DATE_GRP_X.bytes, 0, IMAGE_s_WS_ORIG_DATE_GRP_X.length);
            System.arraycopy(IMAGE_s_WS_PASSED_DATA, 0, s_WS_PASSED_DATA.bytes, 0, IMAGE_s_WS_PASSED_DATA.length);
            System.arraycopy(IMAGE_s_WS_SORT_DIV, 0, s_WS_SORT_DIV.bytes, 0, IMAGE_s_WS_SORT_DIV.length);
            System.arraycopy(IMAGE_s_CUSTOMER_KY, 0, s_CUSTOMER_KY.bytes, 0, IMAGE_s_CUSTOMER_KY.length);
            System.arraycopy(IMAGE_s_PROCTRAN_RIDFLD, 0, s_PROCTRAN_RIDFLD.bytes, 0, IMAGE_s_PROCTRAN_RIDFLD.length);
            System.arraycopy(IMAGE_s_SQLCODE_DISPLAY, 0, s_SQLCODE_DISPLAY.bytes, 0, IMAGE_s_SQLCODE_DISPLAY.length);
            System.arraycopy(IMAGE_s_MY_ABEND_CODE, 0, s_MY_ABEND_CODE.bytes, 0, IMAGE_s_MY_ABEND_CODE.length);
            System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
            System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
            System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
            byte[] parmText = (parm == null ? "" : parm).getBytes(CS);
            s_DFHCOMMAREA.bytes[0] = (byte) (parmText.length >> 8);
            s_DFHCOMMAREA.bytes[1] = (byte) parmText.length;
            System.arraycopy(parmText, 0, s_DFHCOMMAREA.bytes, 2, Math.min(parmText.length, s_DFHCOMMAREA.bytes.length - 2));
            try {
                perform(0, 5);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f105_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 6) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** PREMIERE. */
    private int p0() {

        return 1;
    }

    /** A010. */
    private int p1() {
        // MOVE DFHCOMMAREA TO WS-ABND-AREA
        Cobol.move(f59_DFHCOMMAREA, f4_WS_ABND_AREA, CS);
        // EXEC CICS WRITE FILE('ABNDFILE') FROM(WS-ABND-AREA) RIDFLD(ABND-VSAM-KEY) RESP(WS-CICS-RESP) RESP2(WS-CICS-RESP2) END-EXEC
        int resp1 = task.write("ABNDFILE".strip(), store("ABNDFILE".strip()).exists(DetCics.bytes(f5_ABND_VSAM_KEY)), () -> store("ABNDFILE".strip()).store(DetCics.bytes(f4_WS_ABND_AREA)));
        Cobol.store(f102_EIBRESP, BigDecimal.valueOf(resp1), false, CS);
        Cobol.store(f103_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f2_WS_CICS_RESP, BigDecimal.valueOf(resp1), false, CS);
        Cobol.store(f3_WS_CICS_RESP2, BigDecimal.valueOf(0), false, CS);
        // IF WS-CICS-RESP NOT = DFHRESP(NORMAL)
        if (!(Cobol.num(f2_WS_CICS_RESP, CS).compareTo(D0) == 0)) {
            // DISPLAY '*********************************************'
            Sysout.display("*********************************************");
            // DISPLAY '**** Unable to write to the file ABNDFILE !!!'
            Sysout.display("**** Unable to write to the file ABNDFILE !!!");
            // DISPLAY 'RESP=' WS-CICS-RESP ' RESP2=' WS-CICS-RESP2
            Sysout.display("RESP=", Cobol.displayText(f2_WS_CICS_RESP, CS), " RESP2=", Cobol.displayText(f3_WS_CICS_RESP2, CS));
            // DISPLAY '*********************************************'
            Sysout.display("*********************************************");
            // EXEC CICS RETURN END-EXEC
            caBack.run();
            task.returnTransid(null, null);
            if (true) throw new Goback();
        }
        // PERFORM GET-ME-OUT-OF-HERE
        perform(3, 5);
        return 2;
    }

    /** A999. */
    private int p2() {
        // EXIT
        return 3;
    }

    /** GET-ME-OUT-OF-HERE. */
    private int p3() {

        return 4;
    }

    /** GMOOH010. */
    private int p4() {
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        // GOBACK
        if (true) throw new Goback();
        return 5;
    }

    /** GMOOH999. */
    private int p5() {
        // EXIT
        return 6;
    }

}
