// gitgalaxy-det-port: COBOL HXPRC (HXPRC.cbl), translated by rule, statement for statement
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
 * HXPRC: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 19, translated 19, holes 0.
 */
@Service
public class HxprcService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");

    private static final byte[] IMAGE_s_HXM4I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgIAAAICAgICAgICAgICAAACAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHBMSCA = Base64.getDecoder().decode(String.join("",
            "GRUMDfBAUGDITMFh8fiAAoIA/yhCQ0HAwcJGAD//APHy8/T19vcAAPHy9AQCBk3J0djZXehsAQUDBwABAgQIDwHw/w=="));
    private static final byte[] IMAGE_s_DFHAID = Base64.getDecoder().decode(String.join("",
            "ACdfaj1XWGgiJT4sMTIzNDU2Nzg5OiNAQUJDREVGR0hJWy48"));
    private static final byte[] IMAGE_s_WS_CA = Base64.getDecoder().decode(String.join("",
            "Uw=="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "IA=="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_HXM4I = new Storage(IMAGE_s_HXM4I.length);
    private final Storage s_DFHBMSCA = new Storage(IMAGE_s_DFHBMSCA.length);
    private final Storage s_DFHAID = new Storage(IMAGE_s_DFHAID.length);
    private final Storage s_WS_CA = new Storage(IMAGE_s_WS_CA.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f3_FAL = Field.binary(s_HXM4I, 12, 4, 0, true, false);
    private final Field f6_FAA = Field.alphanumeric(s_HXM4I, 14, 1, false);
    private final Field f9_FBL = Field.binary(s_HXM4I, 25, 4, 0, true, false);
    private final Field f12_FBA = Field.alphanumeric(s_HXM4I, 27, 1, false);
    private final Field f15_FCL = Field.binary(s_HXM4I, 38, 4, 0, true, false);
    private final Field f18_FCA = Field.alphanumeric(s_HXM4I, 40, 1, false);
    private final Field f21_HXM4O = Field.group(s_HXM4I, 0, 51);
    private final Field f24_FAC = Field.alphanumeric(s_HXM4I, 15, 1, false);
    private final Field f25_FAH = Field.alphanumeric(s_HXM4I, 16, 1, false);
    private final Field f26_FAO = Field.alphanumeric(s_HXM4I, 17, 8, false);
    private final Field f28_FBC = Field.alphanumeric(s_HXM4I, 28, 1, false);
    private final Field f29_FBH = Field.alphanumeric(s_HXM4I, 29, 1, false);
    private final Field f30_FBO = Field.alphanumeric(s_HXM4I, 30, 8, false);
    private final Field f32_FCC = Field.alphanumeric(s_HXM4I, 41, 1, false);
    private final Field f33_FCH = Field.alphanumeric(s_HXM4I, 42, 1, false);
    private final Field f34_FCO = Field.alphanumeric(s_HXM4I, 43, 8, false);
    private final Field f66_DFHDFCOL = Field.alphanumeric(s_DFHBMSCA, 30, 1, false);
    private final Field f69_DFHPINK = Field.alphanumeric(s_DFHBMSCA, 33, 1, false);
    private final Field f72_DFHYELLO = Field.alphanumeric(s_DFHBMSCA, 36, 1, false);
    private final Field f76_DFHBLINK = Field.alphanumeric(s_DFHBMSCA, 40, 1, false);
    private final Field f104_DFHNULL = Field.alphanumeric(s_DFHAID, 0, 1, false);
    private final Field f105_DFHENTER = Field.alphanumeric(s_DFHAID, 1, 1, false);
    private final Field f106_DFHCLEAR = Field.alphanumeric(s_DFHAID, 2, 1, false);
    private final Field f107_DFHCLRP = Field.alphanumeric(s_DFHAID, 3, 1, false);
    private final Field f108_DFHPEN = Field.alphanumeric(s_DFHAID, 4, 1, false);
    private final Field f109_DFHOPID = Field.alphanumeric(s_DFHAID, 5, 1, false);
    private final Field f110_DFHMSRE = Field.alphanumeric(s_DFHAID, 6, 1, false);
    private final Field f111_DFHSTRF = Field.alphanumeric(s_DFHAID, 7, 1, false);
    private final Field f112_DFHTRIG = Field.alphanumeric(s_DFHAID, 8, 1, false);
    private final Field f113_DFHPA1 = Field.alphanumeric(s_DFHAID, 9, 1, false);
    private final Field f114_DFHPA2 = Field.alphanumeric(s_DFHAID, 10, 1, false);
    private final Field f115_DFHPA3 = Field.alphanumeric(s_DFHAID, 11, 1, false);
    private final Field f116_DFHPF1 = Field.alphanumeric(s_DFHAID, 12, 1, false);
    private final Field f117_DFHPF2 = Field.alphanumeric(s_DFHAID, 13, 1, false);
    private final Field f118_DFHPF3 = Field.alphanumeric(s_DFHAID, 14, 1, false);
    private final Field f119_DFHPF4 = Field.alphanumeric(s_DFHAID, 15, 1, false);
    private final Field f120_DFHPF5 = Field.alphanumeric(s_DFHAID, 16, 1, false);
    private final Field f121_DFHPF6 = Field.alphanumeric(s_DFHAID, 17, 1, false);
    private final Field f122_DFHPF7 = Field.alphanumeric(s_DFHAID, 18, 1, false);
    private final Field f123_DFHPF8 = Field.alphanumeric(s_DFHAID, 19, 1, false);
    private final Field f124_DFHPF9 = Field.alphanumeric(s_DFHAID, 20, 1, false);
    private final Field f125_DFHPF10 = Field.alphanumeric(s_DFHAID, 21, 1, false);
    private final Field f126_DFHPF11 = Field.alphanumeric(s_DFHAID, 22, 1, false);
    private final Field f127_DFHPF12 = Field.alphanumeric(s_DFHAID, 23, 1, false);
    private final Field f128_DFHPF13 = Field.alphanumeric(s_DFHAID, 24, 1, false);
    private final Field f129_DFHPF14 = Field.alphanumeric(s_DFHAID, 25, 1, false);
    private final Field f130_DFHPF15 = Field.alphanumeric(s_DFHAID, 26, 1, false);
    private final Field f131_DFHPF16 = Field.alphanumeric(s_DFHAID, 27, 1, false);
    private final Field f132_DFHPF17 = Field.alphanumeric(s_DFHAID, 28, 1, false);
    private final Field f133_DFHPF18 = Field.alphanumeric(s_DFHAID, 29, 1, false);
    private final Field f134_DFHPF19 = Field.alphanumeric(s_DFHAID, 30, 1, false);
    private final Field f135_DFHPF20 = Field.alphanumeric(s_DFHAID, 31, 1, false);
    private final Field f136_DFHPF21 = Field.alphanumeric(s_DFHAID, 32, 1, false);
    private final Field f137_DFHPF22 = Field.alphanumeric(s_DFHAID, 33, 1, false);
    private final Field f138_DFHPF23 = Field.alphanumeric(s_DFHAID, 34, 1, false);
    private final Field f139_DFHPF24 = Field.alphanumeric(s_DFHAID, 35, 1, false);
    private final Field f140_WS_CA = Field.alphanumeric(s_WS_CA, 0, 1, false);
    private final Field f143_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f144_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f145_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f146_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f147_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f150_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f151_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
    private final Field f171_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f172_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f174_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
            java.util.Map.entry("DATAONLY-SEND", 2),
            java.util.Map.entry("OVERRIDE-SOME", 1),
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

    private void in_HxprcWsCa(HxprcWsCa d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getWsCa() == null ? "" : d.getWsCa(), Field.alphanumeric(s, base + 0, 1, false), CS);
    }

    private void fill_HxprcWsCa(HxprcWsCa d, Storage s, int base) {
        d.setWsCa(Cobol.text(Field.alphanumeric(s, base + 0, 1, false), CS));
    }

    private HxprcWsCa out_HxprcWsCa(Storage s, int base) {
        HxprcWsCa d = new HxprcWsCa();
        fill_HxprcWsCa(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }



    public HxprcService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_HXM4I, 0, s_HXM4I.bytes, 0, IMAGE_s_HXM4I.length);
        System.arraycopy(IMAGE_s_DFHBMSCA, 0, s_DFHBMSCA.bytes, 0, IMAGE_s_DFHBMSCA.length);
        System.arraycopy(IMAGE_s_DFHAID, 0, s_DFHAID.bytes, 0, IMAGE_s_DFHAID.length);
        System.arraycopy(IMAGE_s_WS_CA, 0, s_WS_CA.bytes, 0, IMAGE_s_WS_CA.length);
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
            perform(0, 2);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f174_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f145_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f147_EIBTRMID, CS);
            Cobol.store(f146_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f144_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f143_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                case "NULL" -> Cobol.move(f104_DFHNULL, f151_EIBAID, CS);
                case "ENTER" -> Cobol.move(f105_DFHENTER, f151_EIBAID, CS);
                case "CLEAR" -> Cobol.move(f106_DFHCLEAR, f151_EIBAID, CS);
                case "CLRP" -> Cobol.move(f107_DFHCLRP, f151_EIBAID, CS);
                case "PEN" -> Cobol.move(f108_DFHPEN, f151_EIBAID, CS);
                case "OPID" -> Cobol.move(f109_DFHOPID, f151_EIBAID, CS);
                case "MSRE" -> Cobol.move(f110_DFHMSRE, f151_EIBAID, CS);
                case "STRF" -> Cobol.move(f111_DFHSTRF, f151_EIBAID, CS);
                case "TRIG" -> Cobol.move(f112_DFHTRIG, f151_EIBAID, CS);
                case "PA1" -> Cobol.move(f113_DFHPA1, f151_EIBAID, CS);
                case "PA2" -> Cobol.move(f114_DFHPA2, f151_EIBAID, CS);
                case "PA3" -> Cobol.move(f115_DFHPA3, f151_EIBAID, CS);
                case "PF1" -> Cobol.move(f116_DFHPF1, f151_EIBAID, CS);
                case "PF2" -> Cobol.move(f117_DFHPF2, f151_EIBAID, CS);
                case "PF3" -> Cobol.move(f118_DFHPF3, f151_EIBAID, CS);
                case "PF4" -> Cobol.move(f119_DFHPF4, f151_EIBAID, CS);
                case "PF5" -> Cobol.move(f120_DFHPF5, f151_EIBAID, CS);
                case "PF6" -> Cobol.move(f121_DFHPF6, f151_EIBAID, CS);
                case "PF7" -> Cobol.move(f122_DFHPF7, f151_EIBAID, CS);
                case "PF8" -> Cobol.move(f123_DFHPF8, f151_EIBAID, CS);
                case "PF9" -> Cobol.move(f124_DFHPF9, f151_EIBAID, CS);
                case "PF10" -> Cobol.move(f125_DFHPF10, f151_EIBAID, CS);
                case "PF11" -> Cobol.move(f126_DFHPF11, f151_EIBAID, CS);
                case "PF12" -> Cobol.move(f127_DFHPF12, f151_EIBAID, CS);
                case "PF13" -> Cobol.move(f128_DFHPF13, f151_EIBAID, CS);
                case "PF14" -> Cobol.move(f129_DFHPF14, f151_EIBAID, CS);
                case "PF15" -> Cobol.move(f130_DFHPF15, f151_EIBAID, CS);
                case "PF16" -> Cobol.move(f131_DFHPF16, f151_EIBAID, CS);
                case "PF17" -> Cobol.move(f132_DFHPF17, f151_EIBAID, CS);
                case "PF18" -> Cobol.move(f133_DFHPF18, f151_EIBAID, CS);
                case "PF19" -> Cobol.move(f134_DFHPF19, f151_EIBAID, CS);
                case "PF20" -> Cobol.move(f135_DFHPF20, f151_EIBAID, CS);
                case "PF21" -> Cobol.move(f136_DFHPF21, f151_EIBAID, CS);
                case "PF22" -> Cobol.move(f137_DFHPF22, f151_EIBAID, CS);
                case "PF23" -> Cobol.move(f138_DFHPF23, f151_EIBAID, CS);
                case "PF24" -> Cobol.move(f139_DFHPF24, f151_EIBAID, CS);
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof HxprcWsCa x) {
                in_HxprcWsCa(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_HxprcWsCa(x, s_DFHCOMMAREA, 0);
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
            Cobol.store(f150_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 2);
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

    public HxprcWsCa handleTransaction(String transid, HxprcWsCa request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "HXPRC", this::runTask);
        return task.returned(HxprcWsCa.class);
    }

    public HxprcWsCa handleTransaction(String transid, HxprcWsCa request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "HXPRC", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(HxprcWsCa.class);
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
                if (next >= 3) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // MOVE LOW-VALUES TO HXM4O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f21_HXM4O, CS);
        // MOVE 'ALPHA' TO FAO
        Cobol.move("ALPHA", f26_FAO, CS);
        // MOVE 'BETA' TO FBO
        Cobol.move("BETA", f30_FBO, CS);
        // MOVE 'GAMMA' TO FCO
        Cobol.move("GAMMA", f34_FCO, CS);
        // IF EIBCALEN = 0
        if (Cobol.num(f150_EIBCALEN, CS).compareTo(D0) == 0) {
            // EXEC CICS SEND MAP('HXM4') MAPSET('HXSET4') FROM(HXM4O) ERASE END-EXEC
            java.util.Map<String, String> values1 = new java.util.LinkedHashMap<>();
            CicsTask.MapSubfields sub2 = new CicsTask.MapSubfields();
            values1.put("FA", Cobol.text(f26_FAO, CS));
            DetCics.subfields(sub2, "FA", f3_FAL, f6_FAA, f24_FAC, f25_FAH, CS);
            values1.put("FB", Cobol.text(f30_FBO, CS));
            DetCics.subfields(sub2, "FB", f9_FBL, f12_FBA, f28_FBC, f29_FBH, CS);
            values1.put("FC", Cobol.text(f34_FCO, CS));
            DetCics.subfields(sub2, "FC", f15_FCL, f18_FCA, f32_FCC, f33_FCH, CS);
            Hxm4Screen screen3 = Hxm4Screen.fromValues(values1);
            int[] planned4 = task.planned("SEND-MAP", "HXM4");
            if (planned4[0] == 0) task.sendMap("HXM4", "HXSET4", screen3, sub2, "ERASE");
            Cobol.store(f171_EIBRESP, BigDecimal.valueOf(planned4[0]), false, CS);
            Cobol.store(f172_EIBRESP2, BigDecimal.valueOf(planned4[1]), false, CS);
            if (planned4[0] != 0) {
                int to = condition(DetCics.condition(planned4[0]));
                if (to >= 0) return GOTO | to;
            }
        } else {
            // ELSE IF EIBAID = DFHPF1
            if (Cobol.compare(f151_EIBAID, f116_DFHPF1, CS) == 0) {
                // PERFORM OVERRIDE-SOME
                perform(1, 1);
            } else {
                // PERFORM DATAONLY-SEND
                perform(2, 2);
            }
        }
        // EXEC CICS RETURN TRANSID('HX04') COMMAREA(WS-CA) LENGTH(1) END-EXEC
        caBack.run();
        task.returnTransid("HX04".strip(), out_HxprcWsCa(f140_WS_CA.storage(), f140_WS_CA.offset()), 1, Cobol.commarea(f140_WS_CA, 1).bytes);
        if (true) throw new Goback();
        return 1;
    }

    /** OVERRIDE-SOME. */
    private int p1() {
        // MOVE DFHYELLO TO FAC
        Cobol.move(f72_DFHYELLO, f24_FAC, CS);
        // MOVE DFHDFCOL TO FBC
        Cobol.move(f66_DFHDFCOL, f28_FBC, CS);
        // MOVE DFHBLINK TO FCH
        Cobol.move(f76_DFHBLINK, f33_FCH, CS);
        // EXEC CICS SEND MAP('HXM4') MAPSET('HXSET4') FROM(HXM4O) END-EXEC
        java.util.Map<String, String> values5 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub6 = new CicsTask.MapSubfields();
        values5.put("FA", Cobol.text(f26_FAO, CS));
        DetCics.subfields(sub6, "FA", f3_FAL, f6_FAA, f24_FAC, f25_FAH, CS);
        values5.put("FB", Cobol.text(f30_FBO, CS));
        DetCics.subfields(sub6, "FB", f9_FBL, f12_FBA, f28_FBC, f29_FBH, CS);
        values5.put("FC", Cobol.text(f34_FCO, CS));
        DetCics.subfields(sub6, "FC", f15_FCL, f18_FCA, f32_FCC, f33_FCH, CS);
        Hxm4Screen screen7 = Hxm4Screen.fromValues(values5);
        int[] planned8 = task.planned("SEND-MAP", "HXM4");
        if (planned8[0] == 0) task.sendMap("HXM4", "HXSET4", screen7, sub6);
        Cobol.store(f171_EIBRESP, BigDecimal.valueOf(planned8[0]), false, CS);
        Cobol.store(f172_EIBRESP2, BigDecimal.valueOf(planned8[1]), false, CS);
        if (planned8[0] != 0) {
            int to = condition(DetCics.condition(planned8[0]));
            if (to >= 0) return GOTO | to;
        }
        return 2;
    }

    /** DATAONLY-SEND. */
    private int p2() {
        // MOVE LOW-VALUES TO HXM4O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f21_HXM4O, CS);
        // MOVE DFHPINK TO FAC
        Cobol.move(f69_DFHPINK, f24_FAC, CS);
        // MOVE DFHDFCOL TO FBC
        Cobol.move(f66_DFHDFCOL, f28_FBC, CS);
        // MOVE 'BETA' TO FBO
        Cobol.move("BETA", f30_FBO, CS);
        // EXEC CICS SEND MAP('HXM4') MAPSET('HXSET4') FROM(HXM4O) DATAONLY END-EXEC
        java.util.Map<String, String> values9 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub10 = new CicsTask.MapSubfields();
        values9.put("FA", Cobol.text(f26_FAO, CS));
        DetCics.subfields(sub10, "FA", f3_FAL, f6_FAA, f24_FAC, f25_FAH, CS);
        values9.put("FB", Cobol.text(f30_FBO, CS));
        DetCics.subfields(sub10, "FB", f9_FBL, f12_FBA, f28_FBC, f29_FBH, CS);
        values9.put("FC", Cobol.text(f34_FCO, CS));
        DetCics.subfields(sub10, "FC", f15_FCL, f18_FCA, f32_FCC, f33_FCH, CS);
        Hxm4Screen screen11 = Hxm4Screen.fromValues(values9);
        int[] planned12 = task.planned("SEND-MAP", "HXM4");
        if (planned12[0] == 0) task.sendMap("HXM4", "HXSET4", screen11, sub10, "DATAONLY");
        Cobol.store(f171_EIBRESP, BigDecimal.valueOf(planned12[0]), false, CS);
        Cobol.store(f172_EIBRESP2, BigDecimal.valueOf(planned12[1]), false, CS);
        if (planned12[0] != 0) {
            int to = condition(DetCics.condition(planned12[0]));
            if (to >= 0) return GOTO | to;
        }
        return 3;
    }

}
