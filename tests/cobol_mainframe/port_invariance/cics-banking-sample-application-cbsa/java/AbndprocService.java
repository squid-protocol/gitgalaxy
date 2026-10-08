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

    private final Field f2_WS_CICS_RESP = Field.binary(s_WS_CICS_WORK_AREA, 0, 8, 0, true, false);
    private final Field f3_WS_CICS_RESP2 = Field.binary(s_WS_CICS_WORK_AREA, 4, 8, 0, true, false);
    private final Field f4_WS_ABND_AREA = Field.group(s_WS_ABND_AREA, 0, 681);
    private final Field f5_ABND_VSAM_KEY = Field.group(s_WS_ABND_AREA, 0, 12);
    private final Field f59_DFHCOMMAREA = Field.group(s_DFHCOMMAREA, 0, 681);
    private final Field f74_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f75_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f76_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f77_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f78_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f81_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f102_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f103_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f105_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private long f18_WS_ABND_KEY_LEN;  // WS-ABND-KEY-LEN PIC S9(8) BINARY

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

    private void in_AbndprocDfhcommarea(AbndprocDfhcommarea d, Storage s, int base) {
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

    private void fill_AbndprocDfhcommarea(AbndprocDfhcommarea d, Storage s, int base) {
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

    private AbndprocDfhcommarea out_AbndprocDfhcommarea(Storage s, int base) {
        AbndprocDfhcommarea d = new AbndprocDfhcommarea();
        fill_AbndprocDfhcommarea(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
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
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_WS_CICS_WORK_AREA, 0, s_WS_CICS_WORK_AREA.bytes, 0, IMAGE_s_WS_CICS_WORK_AREA.length);
        System.arraycopy(IMAGE_s_WS_ABND_AREA, 0, s_WS_ABND_AREA.bytes, 0, IMAGE_s_WS_ABND_AREA.length);
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
        f18_WS_ABND_KEY_LEN = 12L;
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 5);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f105_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f76_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f78_EIBTRMID, CS);
            Cobol.store(f77_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f75_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f74_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof AbndprocDfhcommarea x) {
                in_AbndprocDfhcommarea(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_AbndprocDfhcommarea(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 681);
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
            Cobol.store(f81_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 5);
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

    public AbndprocDfhcommarea handleLink(AbndprocDfhcommarea request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("ABNDPROC", request);
        region.run(task, "ABNDPROC", this::runTask);
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
