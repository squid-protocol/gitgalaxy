// gitgalaxy-det-port: COBOL HXRST (HXRST.cbl), translated by rule, statement for statement
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
 * HXRST: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 25, translated 25, holes 0.
 */
@Service
public class HxrstService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_HXM3I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgICAgAAAgICAgICAgICAAACAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_DFHBMSCA = Base64.getDecoder().decode(String.join("",
            "GRUMDfBAUGDITMFh8fiAAoIA/yhCQ0HAwcJGAD//APHy8/T19vcAAPHy9AQCBk3J0djZXehsAQUDBwABAgQIDwHw/w=="));
    private static final byte[] IMAGE_s_DFHAID = Base64.getDecoder().decode(String.join("",
            "ACdfaj1XWGgiJT4sMTIzNDU2Nzg5OiNAQUJDREVGR0hJWy48"));
    private static final byte[] IMAGE_s_WS_CA = Base64.getDecoder().decode(String.join("",
            "Uw=="));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_HXM3I = new Storage(IMAGE_s_HXM3I.length);
    private final Storage s_DFHBMSCA = new Storage(IMAGE_s_DFHBMSCA.length);
    private final Storage s_DFHAID = new Storage(IMAGE_s_DFHAID.length);
    private final Storage s_WS_CA = new Storage(IMAGE_s_WS_CA.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_HXM3I = Field.group(s_HXM3I, 0, 49);
    private final Field f3_MSGL = Field.binary(s_HXM3I, 12, 4, 0, true, false);
    private final Field f6_MSGA = Field.alphanumeric(s_HXM3I, 14, 1, false);
    private final Field f7_MSGI = Field.alphanumeric(s_HXM3I, 15, 12, false);
    private final Field f8_NAMEL = Field.binary(s_HXM3I, 27, 4, 0, true, false);
    private final Field f11_NAMEA = Field.alphanumeric(s_HXM3I, 29, 1, false);
    private final Field f12_NAMEI = Field.alphanumeric(s_HXM3I, 30, 8, false);
    private final Field f13_NOTEL = Field.binary(s_HXM3I, 38, 4, 0, true, false);
    private final Field f16_NOTEA = Field.alphanumeric(s_HXM3I, 40, 1, false);
    private final Field f17_NOTEI = Field.alphanumeric(s_HXM3I, 41, 8, false);
    private final Field f18_HXM3O = Field.group(s_HXM3I, 0, 49);
    private final Field f21_MSGO = Field.alphanumeric(s_HXM3I, 15, 12, false);
    private final Field f23_NAMEO = Field.alphanumeric(s_HXM3I, 30, 8, false);
    private final Field f25_NOTEO = Field.alphanumeric(s_HXM3I, 41, 8, false);
    private final Field f34_DFHBMPRO = Field.alphanumeric(s_DFHBMSCA, 7, 1, false);
    private final Field f37_DFHBMFSE = Field.alphanumeric(s_DFHBMSCA, 10, 1, false);
    private final Field f95_DFHNULL = Field.alphanumeric(s_DFHAID, 0, 1, false);
    private final Field f96_DFHENTER = Field.alphanumeric(s_DFHAID, 1, 1, false);
    private final Field f97_DFHCLEAR = Field.alphanumeric(s_DFHAID, 2, 1, false);
    private final Field f98_DFHCLRP = Field.alphanumeric(s_DFHAID, 3, 1, false);
    private final Field f99_DFHPEN = Field.alphanumeric(s_DFHAID, 4, 1, false);
    private final Field f100_DFHOPID = Field.alphanumeric(s_DFHAID, 5, 1, false);
    private final Field f101_DFHMSRE = Field.alphanumeric(s_DFHAID, 6, 1, false);
    private final Field f102_DFHSTRF = Field.alphanumeric(s_DFHAID, 7, 1, false);
    private final Field f103_DFHTRIG = Field.alphanumeric(s_DFHAID, 8, 1, false);
    private final Field f104_DFHPA1 = Field.alphanumeric(s_DFHAID, 9, 1, false);
    private final Field f105_DFHPA2 = Field.alphanumeric(s_DFHAID, 10, 1, false);
    private final Field f106_DFHPA3 = Field.alphanumeric(s_DFHAID, 11, 1, false);
    private final Field f107_DFHPF1 = Field.alphanumeric(s_DFHAID, 12, 1, false);
    private final Field f108_DFHPF2 = Field.alphanumeric(s_DFHAID, 13, 1, false);
    private final Field f109_DFHPF3 = Field.alphanumeric(s_DFHAID, 14, 1, false);
    private final Field f110_DFHPF4 = Field.alphanumeric(s_DFHAID, 15, 1, false);
    private final Field f111_DFHPF5 = Field.alphanumeric(s_DFHAID, 16, 1, false);
    private final Field f112_DFHPF6 = Field.alphanumeric(s_DFHAID, 17, 1, false);
    private final Field f113_DFHPF7 = Field.alphanumeric(s_DFHAID, 18, 1, false);
    private final Field f114_DFHPF8 = Field.alphanumeric(s_DFHAID, 19, 1, false);
    private final Field f115_DFHPF9 = Field.alphanumeric(s_DFHAID, 20, 1, false);
    private final Field f116_DFHPF10 = Field.alphanumeric(s_DFHAID, 21, 1, false);
    private final Field f117_DFHPF11 = Field.alphanumeric(s_DFHAID, 22, 1, false);
    private final Field f118_DFHPF12 = Field.alphanumeric(s_DFHAID, 23, 1, false);
    private final Field f119_DFHPF13 = Field.alphanumeric(s_DFHAID, 24, 1, false);
    private final Field f120_DFHPF14 = Field.alphanumeric(s_DFHAID, 25, 1, false);
    private final Field f121_DFHPF15 = Field.alphanumeric(s_DFHAID, 26, 1, false);
    private final Field f122_DFHPF16 = Field.alphanumeric(s_DFHAID, 27, 1, false);
    private final Field f123_DFHPF17 = Field.alphanumeric(s_DFHAID, 28, 1, false);
    private final Field f124_DFHPF18 = Field.alphanumeric(s_DFHAID, 29, 1, false);
    private final Field f125_DFHPF19 = Field.alphanumeric(s_DFHAID, 30, 1, false);
    private final Field f126_DFHPF20 = Field.alphanumeric(s_DFHAID, 31, 1, false);
    private final Field f127_DFHPF21 = Field.alphanumeric(s_DFHAID, 32, 1, false);
    private final Field f128_DFHPF22 = Field.alphanumeric(s_DFHAID, 33, 1, false);
    private final Field f129_DFHPF23 = Field.alphanumeric(s_DFHAID, 34, 1, false);
    private final Field f130_DFHPF24 = Field.alphanumeric(s_DFHAID, 35, 1, false);
    private final Field f131_WS_CA = Field.alphanumeric(s_WS_CA, 0, 1, false);
    private final Field f132_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f135_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f136_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f137_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f138_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f139_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f142_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f143_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
    private final Field f163_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f164_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f166_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("ERASE-SCREEN", 3),
            java.util.Map.entry("ECHO-SCREEN", 2),
            java.util.Map.entry("FIRST-SCREEN", 1),
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

    private void in_HxrstWsCa(HxrstWsCa d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getWsCa() == null ? "" : d.getWsCa(), Field.alphanumeric(s, base + 0, 1, false), CS);
    }

    private void fill_HxrstWsCa(HxrstWsCa d, Storage s, int base) {
        d.setWsCa(Cobol.text(Field.alphanumeric(s, base + 0, 1, false), CS));
    }

    private HxrstWsCa out_HxrstWsCa(Storage s, int base) {
        HxrstWsCa d = new HxrstWsCa();
        fill_HxrstWsCa(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }



    public HxrstService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_HXM3I, 0, s_HXM3I.bytes, 0, IMAGE_s_HXM3I.length);
        System.arraycopy(IMAGE_s_DFHBMSCA, 0, s_DFHBMSCA.bytes, 0, IMAGE_s_DFHBMSCA.length);
        System.arraycopy(IMAGE_s_DFHAID, 0, s_DFHAID.bytes, 0, IMAGE_s_DFHAID.length);
        System.arraycopy(IMAGE_s_WS_CA, 0, s_WS_CA.bytes, 0, IMAGE_s_WS_CA.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
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
        return Cobol.num(f166_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f137_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f139_EIBTRMID, CS);
            Cobol.store(f138_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f136_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f135_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                case "NULL" -> Cobol.move(f95_DFHNULL, f143_EIBAID, CS);
                case "ENTER" -> Cobol.move(f96_DFHENTER, f143_EIBAID, CS);
                case "CLEAR" -> Cobol.move(f97_DFHCLEAR, f143_EIBAID, CS);
                case "CLRP" -> Cobol.move(f98_DFHCLRP, f143_EIBAID, CS);
                case "PEN" -> Cobol.move(f99_DFHPEN, f143_EIBAID, CS);
                case "OPID" -> Cobol.move(f100_DFHOPID, f143_EIBAID, CS);
                case "MSRE" -> Cobol.move(f101_DFHMSRE, f143_EIBAID, CS);
                case "STRF" -> Cobol.move(f102_DFHSTRF, f143_EIBAID, CS);
                case "TRIG" -> Cobol.move(f103_DFHTRIG, f143_EIBAID, CS);
                case "PA1" -> Cobol.move(f104_DFHPA1, f143_EIBAID, CS);
                case "PA2" -> Cobol.move(f105_DFHPA2, f143_EIBAID, CS);
                case "PA3" -> Cobol.move(f106_DFHPA3, f143_EIBAID, CS);
                case "PF1" -> Cobol.move(f107_DFHPF1, f143_EIBAID, CS);
                case "PF2" -> Cobol.move(f108_DFHPF2, f143_EIBAID, CS);
                case "PF3" -> Cobol.move(f109_DFHPF3, f143_EIBAID, CS);
                case "PF4" -> Cobol.move(f110_DFHPF4, f143_EIBAID, CS);
                case "PF5" -> Cobol.move(f111_DFHPF5, f143_EIBAID, CS);
                case "PF6" -> Cobol.move(f112_DFHPF6, f143_EIBAID, CS);
                case "PF7" -> Cobol.move(f113_DFHPF7, f143_EIBAID, CS);
                case "PF8" -> Cobol.move(f114_DFHPF8, f143_EIBAID, CS);
                case "PF9" -> Cobol.move(f115_DFHPF9, f143_EIBAID, CS);
                case "PF10" -> Cobol.move(f116_DFHPF10, f143_EIBAID, CS);
                case "PF11" -> Cobol.move(f117_DFHPF11, f143_EIBAID, CS);
                case "PF12" -> Cobol.move(f118_DFHPF12, f143_EIBAID, CS);
                case "PF13" -> Cobol.move(f119_DFHPF13, f143_EIBAID, CS);
                case "PF14" -> Cobol.move(f120_DFHPF14, f143_EIBAID, CS);
                case "PF15" -> Cobol.move(f121_DFHPF15, f143_EIBAID, CS);
                case "PF16" -> Cobol.move(f122_DFHPF16, f143_EIBAID, CS);
                case "PF17" -> Cobol.move(f123_DFHPF17, f143_EIBAID, CS);
                case "PF18" -> Cobol.move(f124_DFHPF18, f143_EIBAID, CS);
                case "PF19" -> Cobol.move(f125_DFHPF19, f143_EIBAID, CS);
                case "PF20" -> Cobol.move(f126_DFHPF20, f143_EIBAID, CS);
                case "PF21" -> Cobol.move(f127_DFHPF21, f143_EIBAID, CS);
                case "PF22" -> Cobol.move(f128_DFHPF22, f143_EIBAID, CS);
                case "PF23" -> Cobol.move(f129_DFHPF23, f143_EIBAID, CS);
                case "PF24" -> Cobol.move(f130_DFHPF24, f143_EIBAID, CS);
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof HxrstWsCa x) {
                in_HxrstWsCa(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_HxrstWsCa(x, s_DFHCOMMAREA, 0);
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
            Cobol.store(f142_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
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

    public HxrstWsCa handleTransaction(String transid, HxrstWsCa request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "HXRST", this::runTask);
        return task.returned(HxrstWsCa.class);
    }

    public HxrstWsCa handleTransaction(String transid, HxrstWsCa request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "HXRST", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(HxrstWsCa.class);
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
        // IF EIBCALEN = 0
        if (Cobol.num(f142_EIBCALEN, CS).compareTo(D0) == 0) {
            // PERFORM FIRST-SCREEN
            perform(1, 1);
        } else {
            // MOVE LOW-VALUES TO HXM3I
            Cobol.moveFigurative(Figurative.LOW_VALUES, f1_HXM3I, CS);
            // EXEC CICS RECEIVE MAP('HXM3') MAPSET('HXSET3') INTO(HXM3I) RESP(WS-RESP) END-EXEC
            int[] planned4 = task.planned("RECEIVE-MAP", "HXM3");
            java.util.Optional<Hxm3Screen> received1 = planned4[0] != 0 ? java.util.Optional.empty() : task.receive("HXM3", "HXSET3", Hxm3Screen.class);
            int resp3 = planned4[0] != 0 ? planned4[0] : received1.isPresent() ? 0 : 36;
            if (received1.isPresent()) {
                java.util.Arrays.fill(f1_HXM3I.storage().bytes, f1_HXM3I.offset(), f1_HXM3I.offset() + f1_HXM3I.length(), (byte) 0);
                java.util.Map<String, String> typed2 = received1.get().screenValues();
                if (typed2.get("MSG") != null) {
                    DetCics.typed(f7_MSGI, f3_MSGL, typed2.get("MSG"), CS);
                }
                if (typed2.get("NAME") != null) {
                    com.gitgalaxy.modernized.cobolrt.cics.DetJustify.place(f12_NAMEI, f8_NAMEL, typed2.get("NAME"), CS, "LEFT,BLANK");
                }
                if (typed2.get("NOTE") != null) {
                    com.gitgalaxy.modernized.cobolrt.cics.DetJustify.place(f17_NOTEI, f13_NOTEL, typed2.get("NOTE"), CS, "LEFT,BLANK");
                }
            }
            Cobol.store(f163_EIBRESP, BigDecimal.valueOf(resp3), false, CS);
            Cobol.store(f164_EIBRESP2, BigDecimal.valueOf(0), false, CS);
            Cobol.store(f132_WS_RESP, BigDecimal.valueOf(resp3), false, CS);
            // IF EIBAID = DFHPF2
            if (Cobol.compare(f143_EIBAID, f108_DFHPF2, CS) == 0) {
                // PERFORM ERASE-SCREEN
                perform(3, 3);
            } else {
                // PERFORM ECHO-SCREEN
                perform(2, 2);
            }
        }
        // EXEC CICS RETURN TRANSID('HX03') COMMAREA(WS-CA) LENGTH(1) END-EXEC
        caBack.run();
        task.returnTransid("HX03".strip(), out_HxrstWsCa(f131_WS_CA.storage(), f131_WS_CA.offset()), 1, Cobol.commarea(f131_WS_CA, 1).bytes);
        if (true) throw new Goback();
        return 1;
    }

    /** FIRST-SCREEN. */
    private int p1() {
        // MOVE LOW-VALUES TO HXM3O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f18_HXM3O, CS);
        // MOVE DFHBMPRO TO MSGA
        Cobol.move(f34_DFHBMPRO, f6_MSGA, CS);
        // MOVE 'READY' TO MSGO
        Cobol.move("READY", f21_MSGO, CS);
        // MOVE DFHBMFSE TO NOTEA
        Cobol.move(f37_DFHBMFSE, f16_NOTEA, CS);
        // MOVE 'KEEP' TO NOTEO
        Cobol.move("KEEP", f25_NOTEO, CS);
        // EXEC CICS SEND MAP('HXM3') MAPSET('HXSET3') FROM(HXM3O) ERASE END-EXEC
        java.util.Map<String, String> values5 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub6 = new CicsTask.MapSubfields();
        values5.put("MSG", Cobol.text(f21_MSGO, CS));
        DetCics.subfields(sub6, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
        values5.put("NAME", Cobol.text(f23_NAMEO, CS));
        DetCics.subfields(sub6, "NAME", f8_NAMEL, f11_NAMEA, null, null, CS);
        values5.put("NOTE", Cobol.text(f25_NOTEO, CS));
        DetCics.subfields(sub6, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
        Hxm3Screen screen7 = Hxm3Screen.fromValues(values5);
        int[] planned8 = task.planned("SEND-MAP", "HXM3");
        if (planned8[0] == 0) task.sendMap("HXM3", "HXSET3", screen7, sub6, "ERASE");
        Cobol.store(f163_EIBRESP, BigDecimal.valueOf(planned8[0]), false, CS);
        Cobol.store(f164_EIBRESP2, BigDecimal.valueOf(planned8[1]), false, CS);
        if (planned8[0] != 0) {
            int to = condition(DetCics.condition(planned8[0]));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

    /** ECHO-SCREEN. */
    private int p2() {
        // MOVE DFHBMPRO TO MSGA
        Cobol.move(f34_DFHBMPRO, f6_MSGA, CS);
        // IF WS-RESP = DFHRESP(NORMAL)
        if (Cobol.num(f132_WS_RESP, CS).compareTo(D0) == 0) {
            // MOVE 'RECEIVED' TO MSGO
            Cobol.move("RECEIVED", f21_MSGO, CS);
        } else {
            // MOVE 'NO INPUT' TO MSGO
            Cobol.move("NO INPUT", f21_MSGO, CS);
        }
        // IF EIBAID = DFHPF1
        if (Cobol.compare(f143_EIBAID, f107_DFHPF1, CS) == 0) {
            // EXEC CICS SEND MAP('HXM3') MAPSET('HXSET3') FROM(HXM3O) DATAONLY FRSET END-EXEC
            java.util.Map<String, String> values9 = new java.util.LinkedHashMap<>();
            CicsTask.MapSubfields sub10 = new CicsTask.MapSubfields();
            values9.put("MSG", Cobol.text(f21_MSGO, CS));
            DetCics.subfields(sub10, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
            values9.put("NAME", Cobol.text(f23_NAMEO, CS));
            DetCics.subfields(sub10, "NAME", f8_NAMEL, f11_NAMEA, null, null, CS);
            values9.put("NOTE", Cobol.text(f25_NOTEO, CS));
            DetCics.subfields(sub10, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
            Hxm3Screen screen11 = Hxm3Screen.fromValues(values9);
            int[] planned12 = task.planned("SEND-MAP", "HXM3");
            if (planned12[0] == 0) task.sendMap("HXM3", "HXSET3", screen11, sub10, "FRSET", "DATAONLY");
            Cobol.store(f163_EIBRESP, BigDecimal.valueOf(planned12[0]), false, CS);
            Cobol.store(f164_EIBRESP2, BigDecimal.valueOf(planned12[1]), false, CS);
            if (planned12[0] != 0) {
                int to = condition(DetCics.condition(planned12[0]));
                if (to >= 0) return GOTO | to;
            }
        } else {
            // EXEC CICS SEND MAP('HXM3') MAPSET('HXSET3') FROM(HXM3O) DATAONLY END-EXEC
            java.util.Map<String, String> values13 = new java.util.LinkedHashMap<>();
            CicsTask.MapSubfields sub14 = new CicsTask.MapSubfields();
            values13.put("MSG", Cobol.text(f21_MSGO, CS));
            DetCics.subfields(sub14, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
            values13.put("NAME", Cobol.text(f23_NAMEO, CS));
            DetCics.subfields(sub14, "NAME", f8_NAMEL, f11_NAMEA, null, null, CS);
            values13.put("NOTE", Cobol.text(f25_NOTEO, CS));
            DetCics.subfields(sub14, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
            Hxm3Screen screen15 = Hxm3Screen.fromValues(values13);
            int[] planned16 = task.planned("SEND-MAP", "HXM3");
            if (planned16[0] == 0) task.sendMap("HXM3", "HXSET3", screen15, sub14, "DATAONLY");
            Cobol.store(f163_EIBRESP, BigDecimal.valueOf(planned16[0]), false, CS);
            Cobol.store(f164_EIBRESP2, BigDecimal.valueOf(planned16[1]), false, CS);
            if (planned16[0] != 0) {
                int to = condition(DetCics.condition(planned16[0]));
                if (to >= 0) return GOTO | to;
            }
        }
        return 3;
    }

    /** ERASE-SCREEN. */
    private int p3() {
        // MOVE LOW-VALUES TO HXM3O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f18_HXM3O, CS);
        // MOVE DFHBMPRO TO MSGA
        Cobol.move(f34_DFHBMPRO, f6_MSGA, CS);
        // MOVE 'ERASED' TO MSGO
        Cobol.move("ERASED", f21_MSGO, CS);
        // EXEC CICS SEND MAP('HXM3') MAPSET('HXSET3') FROM(HXM3O) DATAONLY ERASEAUP END-EXEC
        java.util.Map<String, String> values17 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub18 = new CicsTask.MapSubfields();
        values17.put("MSG", Cobol.text(f21_MSGO, CS));
        DetCics.subfields(sub18, "MSG", f3_MSGL, f6_MSGA, null, null, CS);
        values17.put("NAME", Cobol.text(f23_NAMEO, CS));
        DetCics.subfields(sub18, "NAME", f8_NAMEL, f11_NAMEA, null, null, CS);
        values17.put("NOTE", Cobol.text(f25_NOTEO, CS));
        DetCics.subfields(sub18, "NOTE", f13_NOTEL, f16_NOTEA, null, null, CS);
        Hxm3Screen screen19 = Hxm3Screen.fromValues(values17);
        int[] planned20 = task.planned("SEND-MAP", "HXM3");
        if (planned20[0] == 0) task.sendMap("HXM3", "HXSET3", screen19, sub18, "ERASEAUP", "DATAONLY");
        Cobol.store(f163_EIBRESP, BigDecimal.valueOf(planned20[0]), false, CS);
        Cobol.store(f164_EIBRESP2, BigDecimal.valueOf(planned20[1]), false, CS);
        if (planned20[0] != 0) {
            int to = condition(DetCics.condition(planned20[0]));
            if (to >= 0) return GOTO | to;
        }
        return 4;
    }

}
