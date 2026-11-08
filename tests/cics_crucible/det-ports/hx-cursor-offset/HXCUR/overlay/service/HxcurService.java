// gitgalaxy-det-port: COBOL HXCUR (HXCUR.cbl), translated by rule, statement for statement
package com.gitgalaxy.modernized.service;

import com.gitgalaxy.modernized.cobolrt.standalone.CobolAbend;
import com.gitgalaxy.modernized.cobolrt.standalone.Sysout;
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
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * HXCUR: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 20, translated 20, holes 0.
 */
@Service
public class HxcurService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D165 = new BigDecimal("165");
    private static final BigDecimal D81 = new BigDecimal("81");
    private static final BigDecimal D6 = new BigDecimal("6");
    private static final BigDecimal D8 = new BigDecimal("8");
    private final Cobol.Dc DC_1 = new Cobol.Dc("1");
    private final Cobol.Dc DC_80 = new Cobol.Dc("80");

    private static final byte[] IMAGE_s_HXM5I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgICAgAAAgICAgICAgICAAACAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHAID = Base64.getDecoder().decode(String.join("",
            "ACdfaj1XWGgiJT4sMTIzNDU2Nzg5OiNAQUJDREVGR0hJWy48"));
    private static final byte[] IMAGE_s_WS_CA = Base64.getDecoder().decode(String.join("",
            "Uw=="));
    private static final byte[] IMAGE_s_WS_POS = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_ROW = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_WS_COL = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_HXM5I = new Storage(IMAGE_s_HXM5I.length);
    private final Storage s_DFHAID = new Storage(IMAGE_s_DFHAID.length);
    private final Storage s_WS_CA = new Storage(IMAGE_s_WS_CA.length);
    private final Storage s_WS_POS = new Storage(IMAGE_s_WS_POS.length);
    private final Storage s_WS_ROW = new Storage(IMAGE_s_WS_ROW.length);
    private final Storage s_WS_COL = new Storage(IMAGE_s_WS_COL.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f3_MSGL = Field.binary(s_HXM5I, 12, 4, 0, true, false);
    private final Field f6_MSGA = Field.alphanumeric(s_HXM5I, 14, 1, false);
    private final Field f8_ACCTL = Field.binary(s_HXM5I, 27, 4, 0, true, false);
    private final Field f11_ACCTA = Field.alphanumeric(s_HXM5I, 29, 1, false);
    private final Field f13_NOTEL = Field.binary(s_HXM5I, 38, 4, 0, true, false);
    private final Field f16_NOTEA = Field.alphanumeric(s_HXM5I, 40, 1, false);
    private final Field f18_HXM5O = Field.group(s_HXM5I, 0, 49);
    private final Field f21_MSGO = Field.alphanumeric(s_HXM5I, 15, 12, false);
    private final Field f23_ACCTO = Field.alphanumeric(s_HXM5I, 30, 8, false);
    private final Field f25_NOTEO = Field.alphanumeric(s_HXM5I, 41, 8, false);
    private final Field f27_DFHNULL = Field.alphanumeric(s_DFHAID, 0, 1, false);
    private final Field f28_DFHENTER = Field.alphanumeric(s_DFHAID, 1, 1, false);
    private final Field f29_DFHCLEAR = Field.alphanumeric(s_DFHAID, 2, 1, false);
    private final Field f30_DFHCLRP = Field.alphanumeric(s_DFHAID, 3, 1, false);
    private final Field f31_DFHPEN = Field.alphanumeric(s_DFHAID, 4, 1, false);
    private final Field f32_DFHOPID = Field.alphanumeric(s_DFHAID, 5, 1, false);
    private final Field f33_DFHMSRE = Field.alphanumeric(s_DFHAID, 6, 1, false);
    private final Field f34_DFHSTRF = Field.alphanumeric(s_DFHAID, 7, 1, false);
    private final Field f35_DFHTRIG = Field.alphanumeric(s_DFHAID, 8, 1, false);
    private final Field f36_DFHPA1 = Field.alphanumeric(s_DFHAID, 9, 1, false);
    private final Field f37_DFHPA2 = Field.alphanumeric(s_DFHAID, 10, 1, false);
    private final Field f38_DFHPA3 = Field.alphanumeric(s_DFHAID, 11, 1, false);
    private final Field f39_DFHPF1 = Field.alphanumeric(s_DFHAID, 12, 1, false);
    private final Field f40_DFHPF2 = Field.alphanumeric(s_DFHAID, 13, 1, false);
    private final Field f41_DFHPF3 = Field.alphanumeric(s_DFHAID, 14, 1, false);
    private final Field f42_DFHPF4 = Field.alphanumeric(s_DFHAID, 15, 1, false);
    private final Field f43_DFHPF5 = Field.alphanumeric(s_DFHAID, 16, 1, false);
    private final Field f44_DFHPF6 = Field.alphanumeric(s_DFHAID, 17, 1, false);
    private final Field f45_DFHPF7 = Field.alphanumeric(s_DFHAID, 18, 1, false);
    private final Field f46_DFHPF8 = Field.alphanumeric(s_DFHAID, 19, 1, false);
    private final Field f47_DFHPF9 = Field.alphanumeric(s_DFHAID, 20, 1, false);
    private final Field f48_DFHPF10 = Field.alphanumeric(s_DFHAID, 21, 1, false);
    private final Field f49_DFHPF11 = Field.alphanumeric(s_DFHAID, 22, 1, false);
    private final Field f50_DFHPF12 = Field.alphanumeric(s_DFHAID, 23, 1, false);
    private final Field f51_DFHPF13 = Field.alphanumeric(s_DFHAID, 24, 1, false);
    private final Field f52_DFHPF14 = Field.alphanumeric(s_DFHAID, 25, 1, false);
    private final Field f53_DFHPF15 = Field.alphanumeric(s_DFHAID, 26, 1, false);
    private final Field f54_DFHPF16 = Field.alphanumeric(s_DFHAID, 27, 1, false);
    private final Field f55_DFHPF17 = Field.alphanumeric(s_DFHAID, 28, 1, false);
    private final Field f56_DFHPF18 = Field.alphanumeric(s_DFHAID, 29, 1, false);
    private final Field f57_DFHPF19 = Field.alphanumeric(s_DFHAID, 30, 1, false);
    private final Field f58_DFHPF20 = Field.alphanumeric(s_DFHAID, 31, 1, false);
    private final Field f59_DFHPF21 = Field.alphanumeric(s_DFHAID, 32, 1, false);
    private final Field f60_DFHPF22 = Field.alphanumeric(s_DFHAID, 33, 1, false);
    private final Field f61_DFHPF23 = Field.alphanumeric(s_DFHAID, 34, 1, false);
    private final Field f62_DFHPF24 = Field.alphanumeric(s_DFHAID, 35, 1, false);
    private final Field f63_WS_CA = Field.alphanumeric(s_WS_CA, 0, 1, false);
    private final Field f64_WS_POS = Field.binary(s_WS_POS, 0, 4, 0, true, false);
    private final Field f65_WS_ROW = Field.binary(s_WS_ROW, 0, 4, 0, true, false);
    private final Field f66_WS_COL = Field.binary(s_WS_COL, 0, 4, 0, true, false);
    private final Field f69_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f70_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f71_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f72_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f73_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f76_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f77_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
    private final Field f97_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f98_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f100_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
        if (CicsTask.undefinableFile(name) || task.undefinedInRegion(name)) {
            return DetCics.Store.undefined(CS);
        }
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("COMPUTED-OFFSET", 3),
            java.util.Map.entry("BEATS-IC", 2),
            java.util.Map.entry("FIXED-OFFSET", 1),
            java.util.Map.entry("MAIN-PARA", 0)
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

    private void in_HxcurWsCa(HxcurWsCa d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getWsCa() == null ? "" : d.getWsCa(), Field.alphanumeric(s, base + 0, 1, false), CS);
    }

    private void fill_HxcurWsCa(HxcurWsCa d, Storage s, int base) {
        d.setWsCa(Cobol.text(Field.alphanumeric(s, base + 0, 1, false), CS));
    }

    private HxcurWsCa out_HxcurWsCa(Storage s, int base) {
        HxcurWsCa d = new HxcurWsCa();
        fill_HxcurWsCa(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }



    public HxcurService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_HXM5I, 0, s_HXM5I.bytes, 0, IMAGE_s_HXM5I.length);
        System.arraycopy(IMAGE_s_DFHAID, 0, s_DFHAID.bytes, 0, IMAGE_s_DFHAID.length);
        System.arraycopy(IMAGE_s_WS_CA, 0, s_WS_CA.bytes, 0, IMAGE_s_WS_CA.length);
        System.arraycopy(IMAGE_s_WS_POS, 0, s_WS_POS.bytes, 0, IMAGE_s_WS_POS.length);
        System.arraycopy(IMAGE_s_WS_ROW, 0, s_WS_ROW.bytes, 0, IMAGE_s_WS_ROW.length);
        System.arraycopy(IMAGE_s_WS_COL, 0, s_WS_COL.bytes, 0, IMAGE_s_WS_COL.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        DC_1.reset();
        DC_80.reset();
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 3);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f100_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f71_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f73_EIBTRMID, CS);
            Cobol.store(f72_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f70_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f69_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                case "NULL" -> Cobol.move(f27_DFHNULL, f77_EIBAID, CS);
                case "ENTER" -> Cobol.move(f28_DFHENTER, f77_EIBAID, CS);
                case "CLEAR" -> Cobol.move(f29_DFHCLEAR, f77_EIBAID, CS);
                case "CLRP" -> Cobol.move(f30_DFHCLRP, f77_EIBAID, CS);
                case "PEN" -> Cobol.move(f31_DFHPEN, f77_EIBAID, CS);
                case "OPID" -> Cobol.move(f32_DFHOPID, f77_EIBAID, CS);
                case "MSRE" -> Cobol.move(f33_DFHMSRE, f77_EIBAID, CS);
                case "STRF" -> Cobol.move(f34_DFHSTRF, f77_EIBAID, CS);
                case "TRIG" -> Cobol.move(f35_DFHTRIG, f77_EIBAID, CS);
                case "PA1" -> Cobol.move(f36_DFHPA1, f77_EIBAID, CS);
                case "PA2" -> Cobol.move(f37_DFHPA2, f77_EIBAID, CS);
                case "PA3" -> Cobol.move(f38_DFHPA3, f77_EIBAID, CS);
                case "PF1" -> Cobol.move(f39_DFHPF1, f77_EIBAID, CS);
                case "PF2" -> Cobol.move(f40_DFHPF2, f77_EIBAID, CS);
                case "PF3" -> Cobol.move(f41_DFHPF3, f77_EIBAID, CS);
                case "PF4" -> Cobol.move(f42_DFHPF4, f77_EIBAID, CS);
                case "PF5" -> Cobol.move(f43_DFHPF5, f77_EIBAID, CS);
                case "PF6" -> Cobol.move(f44_DFHPF6, f77_EIBAID, CS);
                case "PF7" -> Cobol.move(f45_DFHPF7, f77_EIBAID, CS);
                case "PF8" -> Cobol.move(f46_DFHPF8, f77_EIBAID, CS);
                case "PF9" -> Cobol.move(f47_DFHPF9, f77_EIBAID, CS);
                case "PF10" -> Cobol.move(f48_DFHPF10, f77_EIBAID, CS);
                case "PF11" -> Cobol.move(f49_DFHPF11, f77_EIBAID, CS);
                case "PF12" -> Cobol.move(f50_DFHPF12, f77_EIBAID, CS);
                case "PF13" -> Cobol.move(f51_DFHPF13, f77_EIBAID, CS);
                case "PF14" -> Cobol.move(f52_DFHPF14, f77_EIBAID, CS);
                case "PF15" -> Cobol.move(f53_DFHPF15, f77_EIBAID, CS);
                case "PF16" -> Cobol.move(f54_DFHPF16, f77_EIBAID, CS);
                case "PF17" -> Cobol.move(f55_DFHPF17, f77_EIBAID, CS);
                case "PF18" -> Cobol.move(f56_DFHPF18, f77_EIBAID, CS);
                case "PF19" -> Cobol.move(f57_DFHPF19, f77_EIBAID, CS);
                case "PF20" -> Cobol.move(f58_DFHPF20, f77_EIBAID, CS);
                case "PF21" -> Cobol.move(f59_DFHPF21, f77_EIBAID, CS);
                case "PF22" -> Cobol.move(f60_DFHPF22, f77_EIBAID, CS);
                case "PF23" -> Cobol.move(f61_DFHPF23, f77_EIBAID, CS);
                case "PF24" -> Cobol.move(f62_DFHPF24, f77_EIBAID, CS);
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof HxcurWsCa x) {
                in_HxcurWsCa(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_HxcurWsCa(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 1);
            }
            s_DFHCOMMAREA.beyond = null;
            if (ca instanceof byte[] cb0) {
                byte[] cb = DetCics.commareaIn(cb0, CS);
                System.arraycopy(cb, 0, s_DFHCOMMAREA.bytes, 0, Math.min(cb.length, s_DFHCOMMAREA.bytes.length));
                if (cb.length > s_DFHCOMMAREA.bytes.length) {
                    s_DFHCOMMAREA.beyond = java.util.Arrays.copyOfRange(cb, s_DFHCOMMAREA.bytes.length, cb.length);
                }
                calen = cx(task, cb.length);
            }
            byte[] raw = task.linkArea();
            if (raw != null) {
                System.arraycopy(raw, 0, s_DFHCOMMAREA.bytes, 0, Math.min(raw.length, s_DFHCOMMAREA.bytes.length));
                int keep = s_DFHCOMMAREA.bytes.length;
                s_DFHCOMMAREA.beyond = raw.length > keep ? java.util.Arrays.copyOfRange(raw, keep, raw.length) : null;
                Runnable typed = caBack;
                caBack = () -> { System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, keep)); if (s_DFHCOMMAREA.beyond != null) { System.arraycopy(s_DFHCOMMAREA.beyond, 0, raw, keep, raw.length - keep); } typed.run(); };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f76_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 3);
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

    public HxcurWsCa handleTransaction(String transid, HxcurWsCa request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "HXCUR", this::runTask);
        return task.returned(HxcurWsCa.class);
    }

    public HxcurWsCa handleTransaction(String transid, HxcurWsCa request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "HXCUR", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(HxcurWsCa.class);
    }

    // @facade-helper: the bytes the last byte-carrying handleTransaction answered
    private byte[] lastAnswerBytes;

    /** The bytes the last byte-carrying handleTransaction's RETURN passed on (a copy; null: none).
     *  @facade-helper */
    public byte[] lastAnswerBytes() {
        return lastAnswerBytes == null ? null : java.util.Arrays.copyOf(lastAnswerBytes, lastAnswerBytes.length);
    }


    /** GOBACK / STOP RUN. */
    private static final class Goback extends RuntimeException {
        private static final long serialVersionUID = 1L;

        Goback() {
            super(null, null, false, false);
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
                if (next >= 4) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // MOVE LOW-VALUES TO HXM5O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f18_HXM5O, CS);
        // IF EIBCALEN = 0
        if (Cobol.num(f76_EIBCALEN, CS).compareTo(D0) == 0) {
            // MOVE 'READY' TO MSGO
            Cobol.move("READY", f21_MSGO, CS);
            // EXEC CICS SEND MAP('HXM5') MAPSET('HXSET5') FROM(HXM5O) ERASE END-EXEC
            java.util.Map<String, String> values1 = new java.util.LinkedHashMap<>();
            CicsTask.MapSubfields sub2 = new CicsTask.MapSubfields();
            values1.put("MSG", Cobol.text(f21_MSGO, CS));
            DetCics.subfields(sub2, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
            values1.put("ACCT", Cobol.text(f23_ACCTO, CS));
            DetCics.subfields(sub2, "ACCT", f8_ACCTL, f11_ACCTA, null, null, CS);
            values1.put("NOTE", Cobol.text(f25_NOTEO, CS));
            DetCics.subfields(sub2, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
            Hxm5Screen screen3 = Hxm5Screen.fromValues(values1);
            int[] planned4 = task.planned("SEND-MAP", "HXM5");
            if (planned4[0] == 0) task.sendMap("HXM5", "HXSET5", screen3, sub2, "ERASE");
            Cobol.store(f97_EIBRESP, BigDecimal.valueOf(planned4[0]), false, CS);
            Cobol.store(f98_EIBRESP2, BigDecimal.valueOf(planned4[1]), false, CS);
            if (planned4[0] != 0) {
                int to = condition(DetCics.condition(planned4[0]));
                if (to >= 0) return GOTO | to;
            }
        } else {
            // EVALUATE TRUE
            if ((Cobol.compare(f77_EIBAID, f39_DFHPF1, CS) == 0)) {
                // PERFORM FIXED-OFFSET
                perform(1, 1);
            } else if ((Cobol.compare(f77_EIBAID, f40_DFHPF2, CS) == 0)) {
                // PERFORM BEATS-IC
                perform(2, 2);
            } else if (true) {
                // PERFORM COMPUTED-OFFSET
                perform(3, 3);
            }
        }
        // EXEC CICS RETURN TRANSID('HX05') COMMAREA(WS-CA) LENGTH(1) END-EXEC
        caBack.run();
        task.returnTransid("HX05".strip(), out_HxcurWsCa(f63_WS_CA.storage(), f63_WS_CA.offset()), 1, Cobol.commarea(f63_WS_CA, 1).bytes);
        if (true) throw new Goback();
        return 1;
    }

    /** FIXED-OFFSET. */
    private int p1() {
        // MOVE 'DATAONLY 165' TO MSGO
        Cobol.move("DATAONLY 165", f21_MSGO, CS);
        // MOVE 165 TO WS-POS
        Cobol.move(D165, f64_WS_POS, CS);
        // EXEC CICS SEND MAP('HXM5') MAPSET('HXSET5') FROM(HXM5O) DATAONLY CURSOR(WS-POS) END-EXEC
        java.util.Map<String, String> values5 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub6 = new CicsTask.MapSubfields();
        values5.put("MSG", Cobol.text(f21_MSGO, CS));
        DetCics.subfields(sub6, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
        values5.put("ACCT", Cobol.text(f23_ACCTO, CS));
        DetCics.subfields(sub6, "ACCT", f8_ACCTL, f11_ACCTA, null, null, CS);
        values5.put("NOTE", Cobol.text(f25_NOTEO, CS));
        DetCics.subfields(sub6, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
        sub6.cursorAt(Cobol.num(f64_WS_POS, CS).intValue());
        Hxm5Screen screen7 = Hxm5Screen.fromValues(values5);
        int[] planned8 = task.planned("SEND-MAP", "HXM5");
        if (planned8[0] == 0) task.sendMap("HXM5", "HXSET5", screen7, sub6, "CURSOR", "DATAONLY");
        Cobol.store(f97_EIBRESP, BigDecimal.valueOf(planned8[0]), false, CS);
        Cobol.store(f98_EIBRESP2, BigDecimal.valueOf(planned8[1]), false, CS);
        if (planned8[0] != 0) {
            int to = condition(DetCics.condition(planned8[0]));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

    /** BEATS-IC. */
    private int p2() {
        // MOVE 'IC OVERRIDE' TO MSGO
        Cobol.move("IC OVERRIDE", f21_MSGO, CS);
        // MOVE 81 TO WS-POS
        Cobol.move(D81, f64_WS_POS, CS);
        // EXEC CICS SEND MAP('HXM5') MAPSET('HXSET5') FROM(HXM5O) CURSOR(WS-POS) END-EXEC
        java.util.Map<String, String> values9 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub10 = new CicsTask.MapSubfields();
        values9.put("MSG", Cobol.text(f21_MSGO, CS));
        DetCics.subfields(sub10, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
        values9.put("ACCT", Cobol.text(f23_ACCTO, CS));
        DetCics.subfields(sub10, "ACCT", f8_ACCTL, f11_ACCTA, null, null, CS);
        values9.put("NOTE", Cobol.text(f25_NOTEO, CS));
        DetCics.subfields(sub10, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
        sub10.cursorAt(Cobol.num(f64_WS_POS, CS).intValue());
        Hxm5Screen screen11 = Hxm5Screen.fromValues(values9);
        int[] planned12 = task.planned("SEND-MAP", "HXM5");
        if (planned12[0] == 0) task.sendMap("HXM5", "HXSET5", screen11, sub10, "CURSOR");
        Cobol.store(f97_EIBRESP, BigDecimal.valueOf(planned12[0]), false, CS);
        Cobol.store(f98_EIBRESP2, BigDecimal.valueOf(planned12[1]), false, CS);
        if (planned12[0] != 0) {
            int to = condition(DetCics.condition(planned12[0]));
            if (to >= 0) return GOTO | to;
        }
        return 3;
    }

    /** COMPUTED-OFFSET. */
    private int p3() {
        // MOVE 6 TO WS-ROW
        Cobol.move(D6, f65_WS_ROW, CS);
        // MOVE 8 TO WS-COL
        Cobol.move(D8, f66_WS_COL, CS);
        // COMPUTE WS-POS = (WS-ROW - 1) * 80 + (WS-COL - 1)
        BigDecimal v13 = Cobol.align(Cobol.multiply(Cobol.subtract(Cobol.num(f65_WS_ROW, CS), DC_1), DC_80), 0).add(Cobol.align(Cobol.subtract(Cobol.num(f66_WS_COL, CS), DC_1), 0));
        Cobol.store(f64_WS_POS, v13, false, CS);
        // MOVE 'ROW 6 COL 8' TO MSGO
        Cobol.move("ROW 6 COL 8", f21_MSGO, CS);
        // EXEC CICS SEND MAP('HXM5') MAPSET('HXSET5') FROM(HXM5O) DATAONLY CURSOR(WS-POS) END-EXEC
        java.util.Map<String, String> values14 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub15 = new CicsTask.MapSubfields();
        values14.put("MSG", Cobol.text(f21_MSGO, CS));
        DetCics.subfields(sub15, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
        values14.put("ACCT", Cobol.text(f23_ACCTO, CS));
        DetCics.subfields(sub15, "ACCT", f8_ACCTL, f11_ACCTA, null, null, CS);
        values14.put("NOTE", Cobol.text(f25_NOTEO, CS));
        DetCics.subfields(sub15, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
        sub15.cursorAt(Cobol.num(f64_WS_POS, CS).intValue());
        Hxm5Screen screen16 = Hxm5Screen.fromValues(values14);
        int[] planned17 = task.planned("SEND-MAP", "HXM5");
        if (planned17[0] == 0) task.sendMap("HXM5", "HXSET5", screen16, sub15, "CURSOR", "DATAONLY");
        Cobol.store(f97_EIBRESP, BigDecimal.valueOf(planned17[0]), false, CS);
        Cobol.store(f98_EIBRESP2, BigDecimal.valueOf(planned17[1]), false, CS);
        if (planned17[0] != 0) {
            int to = condition(DetCics.condition(planned17[0]));
            if (to >= 0) return GOTO | to;
        }
        return 4;
    }

}
