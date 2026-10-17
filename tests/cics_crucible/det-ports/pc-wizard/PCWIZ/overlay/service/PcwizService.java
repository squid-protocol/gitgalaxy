// gitgalaxy-det-port: COBOL PCWIZ (PCWIZ.cbl), translated by rule, statement for statement
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
 * PCWIZ: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 39, translated 39, holes 0.
 */
@Service
public class PcwizService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;
    private static final BigDecimal D0 = new BigDecimal("0");
    private static final BigDecimal D1 = new BigDecimal("1");
    private static final BigDecimal D2 = new BigDecimal("2");
    private final Cobol.Dc DC_100 = new Cobol.Dc("100");

    private static final byte[] IMAGE_s_PCM1I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgICAgICAgAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_PCM2I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgICAgICAgAAAgICAgICAgIAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_PCM3I = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgAAAgICAgICAgICAgICAgICAgAAAgICAgICAgICAgIAAAICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHAID = Base64.getDecoder().decode(String.join("",
            "ACdfaj1XWGgiJT4sMTIzNDU2Nzg5OiNAQUJDREVGR0hJWy48"));
    private static final byte[] IMAGE_s_WS_STATE = Base64.getDecoder().decode(String.join("",
            "MCAgICAgICAgICAgICAgIAAAAAwAACAgICAgICAg"));
    private static final byte[] IMAGE_s_WS_RESP = Base64.getDecoder().decode(String.join("",
            "AAAAAA=="));
    private static final byte[] IMAGE_s_WS_MSG = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA=="));
    private static final byte[] IMAGE_s_WS_AMT_DIGITS = Base64.getDecoder().decode(String.join("",
            "MDAwMDAwMA=="));
    private static final byte[] IMAGE_s_WS_BYE = Base64.getDecoder().decode(String.join("",
            "V0laQVJEIENBTkNFTExFRA=="));
    private static final byte[] IMAGE_s_DFHCOMMAREA = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg"));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_PCM1I = new Storage(IMAGE_s_PCM1I.length);
    private final Storage s_PCM2I = new Storage(IMAGE_s_PCM2I.length);
    private final Storage s_PCM3I = new Storage(IMAGE_s_PCM3I.length);
    private final Storage s_DFHAID = new Storage(IMAGE_s_DFHAID.length);
    private final Storage s_WS_STATE = new Storage(IMAGE_s_WS_STATE.length);
    private final Storage s_WS_RESP = new Storage(IMAGE_s_WS_RESP.length);
    private final Storage s_WS_MSG = new Storage(IMAGE_s_WS_MSG.length);
    private final Storage s_WS_AMT_DIGITS = new Storage(IMAGE_s_WS_AMT_DIGITS.length);
    private final Storage s_WS_BYE = new Storage(IMAGE_s_WS_BYE.length);
    private final Storage s_DFHCOMMAREA = new Storage(IMAGE_s_DFHCOMMAREA.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);

    private final Field f1_PCM1I = Field.group(s_PCM1I, 0, 73);
    private final Field f3_NAMEL = Field.binary(s_PCM1I, 12, 4, 0, true, false);
    private final Field f6_NAMEA = Field.alphanumeric(s_PCM1I, 14, 1, false);
    private final Field f7_NAMEI = Field.alphanumeric(s_PCM1I, 15, 15, false);
    private final Field f8_MSG1L = Field.binary(s_PCM1I, 30, 4, 0, true, false);
    private final Field f11_MSG1A = Field.alphanumeric(s_PCM1I, 32, 1, false);
    private final Field f12_MSG1I = Field.alphanumeric(s_PCM1I, 33, 40, false);
    private final Field f13_PCM1O = Field.group(s_PCM1I, 0, 73);
    private final Field f16_NAMEO = Field.alphanumeric(s_PCM1I, 15, 15, false);
    private final Field f18_MSG1O = Field.alphanumeric(s_PCM1I, 33, 40, false);
    private final Field f21_NAMEOUTL = Field.binary(s_PCM2I, 12, 4, 0, true, false);
    private final Field f24_NAMEOUTA = Field.alphanumeric(s_PCM2I, 14, 1, false);
    private final Field f26_AMTL = Field.binary(s_PCM2I, 30, 4, 0, true, false);
    private final Field f29_AMTA = Field.alphanumeric(s_PCM2I, 32, 1, false);
    private final Field f31_MSG2L = Field.binary(s_PCM2I, 40, 4, 0, true, false);
    private final Field f34_MSG2A = Field.alphanumeric(s_PCM2I, 42, 1, false);
    private final Field f36_PCM2O = Field.group(s_PCM2I, 0, 83);
    private final Field f39_NAMEOUTO = Field.alphanumeric(s_PCM2I, 15, 15, false);
    private final Field f41_AMTO = Field.alphanumeric(s_PCM2I, 33, 7, false);
    private final Field f43_MSG2O = Field.alphanumeric(s_PCM2I, 43, 40, false);
    private final Field f70_DFHNULL = Field.alphanumeric(s_DFHAID, 0, 1, false);
    private final Field f71_DFHENTER = Field.alphanumeric(s_DFHAID, 1, 1, false);
    private final Field f72_DFHCLEAR = Field.alphanumeric(s_DFHAID, 2, 1, false);
    private final Field f73_DFHCLRP = Field.alphanumeric(s_DFHAID, 3, 1, false);
    private final Field f74_DFHPEN = Field.alphanumeric(s_DFHAID, 4, 1, false);
    private final Field f75_DFHOPID = Field.alphanumeric(s_DFHAID, 5, 1, false);
    private final Field f76_DFHMSRE = Field.alphanumeric(s_DFHAID, 6, 1, false);
    private final Field f77_DFHSTRF = Field.alphanumeric(s_DFHAID, 7, 1, false);
    private final Field f78_DFHTRIG = Field.alphanumeric(s_DFHAID, 8, 1, false);
    private final Field f79_DFHPA1 = Field.alphanumeric(s_DFHAID, 9, 1, false);
    private final Field f80_DFHPA2 = Field.alphanumeric(s_DFHAID, 10, 1, false);
    private final Field f81_DFHPA3 = Field.alphanumeric(s_DFHAID, 11, 1, false);
    private final Field f82_DFHPF1 = Field.alphanumeric(s_DFHAID, 12, 1, false);
    private final Field f83_DFHPF2 = Field.alphanumeric(s_DFHAID, 13, 1, false);
    private final Field f84_DFHPF3 = Field.alphanumeric(s_DFHAID, 14, 1, false);
    private final Field f85_DFHPF4 = Field.alphanumeric(s_DFHAID, 15, 1, false);
    private final Field f86_DFHPF5 = Field.alphanumeric(s_DFHAID, 16, 1, false);
    private final Field f87_DFHPF6 = Field.alphanumeric(s_DFHAID, 17, 1, false);
    private final Field f88_DFHPF7 = Field.alphanumeric(s_DFHAID, 18, 1, false);
    private final Field f89_DFHPF8 = Field.alphanumeric(s_DFHAID, 19, 1, false);
    private final Field f90_DFHPF9 = Field.alphanumeric(s_DFHAID, 20, 1, false);
    private final Field f91_DFHPF10 = Field.alphanumeric(s_DFHAID, 21, 1, false);
    private final Field f92_DFHPF11 = Field.alphanumeric(s_DFHAID, 22, 1, false);
    private final Field f93_DFHPF12 = Field.alphanumeric(s_DFHAID, 23, 1, false);
    private final Field f94_DFHPF13 = Field.alphanumeric(s_DFHAID, 24, 1, false);
    private final Field f95_DFHPF14 = Field.alphanumeric(s_DFHAID, 25, 1, false);
    private final Field f96_DFHPF15 = Field.alphanumeric(s_DFHAID, 26, 1, false);
    private final Field f97_DFHPF16 = Field.alphanumeric(s_DFHAID, 27, 1, false);
    private final Field f98_DFHPF17 = Field.alphanumeric(s_DFHAID, 28, 1, false);
    private final Field f99_DFHPF18 = Field.alphanumeric(s_DFHAID, 29, 1, false);
    private final Field f100_DFHPF19 = Field.alphanumeric(s_DFHAID, 30, 1, false);
    private final Field f101_DFHPF20 = Field.alphanumeric(s_DFHAID, 31, 1, false);
    private final Field f102_DFHPF21 = Field.alphanumeric(s_DFHAID, 32, 1, false);
    private final Field f103_DFHPF22 = Field.alphanumeric(s_DFHAID, 33, 1, false);
    private final Field f104_DFHPF23 = Field.alphanumeric(s_DFHAID, 34, 1, false);
    private final Field f105_DFHPF24 = Field.alphanumeric(s_DFHAID, 35, 1, false);
    private final Field f106_WS_STATE = Field.group(s_WS_STATE, 0, 30);
    private final Field f107_PC_STEP = Field.zoned(s_WS_STATE, 0, 1, 0, false, false, false);
    private final Field f108_PC_NAME = Field.alphanumeric(s_WS_STATE, 1, 15, false);
    private final Field f109_PC_AMOUNT = Field.packed(s_WS_STATE, 16, 7, 2, true);
    private final Field f110_PC_ERRORS = Field.binary(s_WS_STATE, 20, 4, 0, true, false);
    private final Field f111_PC_BACK = Field.alphanumeric(s_WS_STATE, 22, 1, false);
    private final Field f113_WS_RESP = Field.binary(s_WS_RESP, 0, 8, 0, true, false);
    private final Field f114_WS_MSG = Field.alphanumeric(s_WS_MSG, 0, 40, false);
    private final Field f115_WS_AMT_DIGITS = Field.zoned(s_WS_AMT_DIGITS, 0, 7, 0, false, false, false);
    private final Field f116_WS_BYE = Field.alphanumeric(s_WS_BYE, 0, 16, false);
    private final Field f117_DFHCOMMAREA = Field.alphanumeric(s_DFHCOMMAREA, 0, 30, false);
    private final Field f119_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f120_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f121_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f122_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f123_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f126_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f127_EIBAID = Field.alphanumeric(s_DFHEIBLK, 26, 1, false);
    private final Field f147_EIBRESP = Field.binary(s_DFHEIBLK, 76, 8, 0, true, false);
    private final Field f148_EIBRESP2 = Field.binary(s_DFHEIBLK, 80, 8, 0, true, false);
    private final Field f150_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);

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
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
            java.util.Map.entry("CANCEL-WIZARD", 4),
            java.util.Map.entry("SEND-STEP2", 3),
            java.util.Map.entry("SEND-STEP1", 2),
            java.util.Map.entry("TAKE-NAME", 1),
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

    private void in_PcwizWsState(PcwizWsState d, Storage s, int base) {
        if (d == null) {
            return;
        }
        Cobol.move(d.getPcStep() == null ? BigDecimal.ZERO : new BigDecimal(d.getPcStep().toString()), Field.zoned(s, base + 0, 1, 0, false, false, false), CS);
        Cobol.move(d.getPcName() == null ? "" : d.getPcName(), Field.alphanumeric(s, base + 1, 15, false), CS);
        Cobol.move(d.getPcAmount() == null ? BigDecimal.ZERO : new BigDecimal(d.getPcAmount().toString()), Field.packed(s, base + 16, 7, 2, true), CS);
        Cobol.move(d.getPcErrors() == null ? BigDecimal.ZERO : new BigDecimal(d.getPcErrors().toString()), Field.binary(s, base + 20, 4, 0, true, false), CS);
        Cobol.move(d.getPcBack() == null ? "" : d.getPcBack(), Field.alphanumeric(s, base + 22, 1, false), CS);
        Cobol.move(d.getPcSpare() == null ? "" : d.getPcSpare(), Field.alphanumeric(s, base + 23, 7, false), CS);
    }

    private void fill_PcwizWsState(PcwizWsState d, Storage s, int base) {
        d.setPcStep(Cobol.num(Field.zoned(s, base + 0, 1, 0, false, false, false), CS).intValue());
        d.setPcName(Cobol.text(Field.alphanumeric(s, base + 1, 15, false), CS));
        d.setPcAmount(Cobol.num(Field.packed(s, base + 16, 7, 2, true), CS));
        d.setPcErrors(Cobol.num(Field.binary(s, base + 20, 4, 0, true, false), CS).intValue());
        d.setPcBack(Cobol.text(Field.alphanumeric(s, base + 22, 1, false), CS));
        d.setPcSpare(Cobol.text(Field.alphanumeric(s, base + 23, 7, false), CS));
    }

    private PcwizWsState out_PcwizWsState(Storage s, int base) {
        PcwizWsState d = new PcwizWsState();
        fill_PcwizWsState(d, s, base);
        return d;
    }

    /** #4270 (X23): DFHCOMMAREA's whole record again, with what the task left in its EIBCALEN bytes. */
    private void caWhole(byte[] whole) {
        if (s_DFHCOMMAREA.bytes != whole) {
            System.arraycopy(s_DFHCOMMAREA.bytes, 0, whole, 0, s_DFHCOMMAREA.bytes.length);
            s_DFHCOMMAREA.bytes = whole;
        }
    }



    public PcwizService() {
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_PCM1I, 0, s_PCM1I.bytes, 0, IMAGE_s_PCM1I.length);
        System.arraycopy(IMAGE_s_PCM2I, 0, s_PCM2I.bytes, 0, IMAGE_s_PCM2I.length);
        System.arraycopy(IMAGE_s_PCM3I, 0, s_PCM3I.bytes, 0, IMAGE_s_PCM3I.length);
        System.arraycopy(IMAGE_s_DFHAID, 0, s_DFHAID.bytes, 0, IMAGE_s_DFHAID.length);
        System.arraycopy(IMAGE_s_WS_STATE, 0, s_WS_STATE.bytes, 0, IMAGE_s_WS_STATE.length);
        System.arraycopy(IMAGE_s_WS_RESP, 0, s_WS_RESP.bytes, 0, IMAGE_s_WS_RESP.length);
        System.arraycopy(IMAGE_s_WS_MSG, 0, s_WS_MSG.bytes, 0, IMAGE_s_WS_MSG.length);
        System.arraycopy(IMAGE_s_WS_AMT_DIGITS, 0, s_WS_AMT_DIGITS.bytes, 0, IMAGE_s_WS_AMT_DIGITS.length);
        System.arraycopy(IMAGE_s_WS_BYE, 0, s_WS_BYE.bytes, 0, IMAGE_s_WS_BYE.length);
        System.arraycopy(IMAGE_s_DFHCOMMAREA, 0, s_DFHCOMMAREA.bytes, 0, IMAGE_s_DFHCOMMAREA.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        DC_100.reset();
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 4);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f150_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f121_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f123_EIBTRMID, CS);
            Cobol.store(f122_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f120_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f119_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                case "NULL" -> Cobol.move(f70_DFHNULL, f127_EIBAID, CS);
                case "ENTER" -> Cobol.move(f71_DFHENTER, f127_EIBAID, CS);
                case "CLEAR" -> Cobol.move(f72_DFHCLEAR, f127_EIBAID, CS);
                case "CLRP" -> Cobol.move(f73_DFHCLRP, f127_EIBAID, CS);
                case "PEN" -> Cobol.move(f74_DFHPEN, f127_EIBAID, CS);
                case "OPID" -> Cobol.move(f75_DFHOPID, f127_EIBAID, CS);
                case "MSRE" -> Cobol.move(f76_DFHMSRE, f127_EIBAID, CS);
                case "STRF" -> Cobol.move(f77_DFHSTRF, f127_EIBAID, CS);
                case "TRIG" -> Cobol.move(f78_DFHTRIG, f127_EIBAID, CS);
                case "PA1" -> Cobol.move(f79_DFHPA1, f127_EIBAID, CS);
                case "PA2" -> Cobol.move(f80_DFHPA2, f127_EIBAID, CS);
                case "PA3" -> Cobol.move(f81_DFHPA3, f127_EIBAID, CS);
                case "PF1" -> Cobol.move(f82_DFHPF1, f127_EIBAID, CS);
                case "PF2" -> Cobol.move(f83_DFHPF2, f127_EIBAID, CS);
                case "PF3" -> Cobol.move(f84_DFHPF3, f127_EIBAID, CS);
                case "PF4" -> Cobol.move(f85_DFHPF4, f127_EIBAID, CS);
                case "PF5" -> Cobol.move(f86_DFHPF5, f127_EIBAID, CS);
                case "PF6" -> Cobol.move(f87_DFHPF6, f127_EIBAID, CS);
                case "PF7" -> Cobol.move(f88_DFHPF7, f127_EIBAID, CS);
                case "PF8" -> Cobol.move(f89_DFHPF8, f127_EIBAID, CS);
                case "PF9" -> Cobol.move(f90_DFHPF9, f127_EIBAID, CS);
                case "PF10" -> Cobol.move(f91_DFHPF10, f127_EIBAID, CS);
                case "PF11" -> Cobol.move(f92_DFHPF11, f127_EIBAID, CS);
                case "PF12" -> Cobol.move(f93_DFHPF12, f127_EIBAID, CS);
                case "PF13" -> Cobol.move(f94_DFHPF13, f127_EIBAID, CS);
                case "PF14" -> Cobol.move(f95_DFHPF14, f127_EIBAID, CS);
                case "PF15" -> Cobol.move(f96_DFHPF15, f127_EIBAID, CS);
                case "PF16" -> Cobol.move(f97_DFHPF16, f127_EIBAID, CS);
                case "PF17" -> Cobol.move(f98_DFHPF17, f127_EIBAID, CS);
                case "PF18" -> Cobol.move(f99_DFHPF18, f127_EIBAID, CS);
                case "PF19" -> Cobol.move(f100_DFHPF19, f127_EIBAID, CS);
                case "PF20" -> Cobol.move(f101_DFHPF20, f127_EIBAID, CS);
                case "PF21" -> Cobol.move(f102_DFHPF21, f127_EIBAID, CS);
                case "PF22" -> Cobol.move(f103_DFHPF22, f127_EIBAID, CS);
                case "PF23" -> Cobol.move(f104_DFHPF23, f127_EIBAID, CS);
                case "PF24" -> Cobol.move(f105_DFHPF24, f127_EIBAID, CS);
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof PcwizWsState x) {
                in_PcwizWsState(x, s_DFHCOMMAREA, 0);
                caBack = () -> fill_PcwizWsState(x, s_DFHCOMMAREA, 0);
                calen = cx(task, 30);
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
                caBack = () -> { typed.run(); System.arraycopy(s_DFHCOMMAREA.bytes, 0, raw, 0, Math.min(raw.length, keep)); if (s_DFHCOMMAREA.beyond != null) { System.arraycopy(s_DFHCOMMAREA.beyond, 0, raw, keep, raw.length - keep); } };
            }
            byte[] caWhole = null;
            if (task.exactCommarea() && calen < s_DFHCOMMAREA.bytes.length) {
                caWhole = s_DFHCOMMAREA.bytes;
                s_DFHCOMMAREA.bytes = java.util.Arrays.copyOf(caWhole, calen);
                Runnable typed = caBack;
                byte[] whole = caWhole;
                caBack = () -> { caWhole(whole); typed.run(); };
            }
            Cobol.store(f126_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                try {
                    perform(0, 4);
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

    public PcwizWsState handleTransaction(String transid, PcwizWsState request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "PCWIZ", this::runTask);
        return task.returned(PcwizWsState.class);
    }

    public PcwizWsState handleTransaction(String transid, PcwizWsState request, byte[] area) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "PCWIZ", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(PcwizWsState.class);
    }

    public PcwizWsState handleLink(PcwizWsState request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("PCWIZ", request);
        region.run(task, "PCWIZ", this::runTask);
        return request;
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
                if (next >= 5) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // IF EIBCALEN = 0
        if (Cobol.num(f126_EIBCALEN, CS).compareTo(D0) == 0) {
            // INITIALIZE WS-STATE
            Cobol.moveFigurative(Figurative.ZEROS, Field.zoned(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 0, 1, 0, false, false, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 1, 15, false), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.packed(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 16, 7, 2, true), CS);
            Cobol.moveFigurative(Figurative.ZEROS, Field.binary(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 20, 4, 0, true, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 22, 1, false), CS);
            Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f106_WS_STATE.storage(), f106_WS_STATE.offset() + 23, 7, false), CS);
            // MOVE 1 TO PC-STEP
            Cobol.move(D1, f107_PC_STEP, CS);
            // MOVE 'TYPE YOUR NAME' TO WS-MSG
            Cobol.move("TYPE YOUR NAME", f114_WS_MSG, CS);
            // PERFORM SEND-STEP1
            perform(2, 2);
        }
        // MOVE DFHCOMMAREA TO WS-STATE
        Cobol.move(f117_DFHCOMMAREA, f106_WS_STATE, CS);
        // EVALUATE TRUE
        if ((Cobol.compare(f127_EIBAID, f84_DFHPF3, CS) == 0)) {
            // PERFORM CANCEL-WIZARD
            perform(4, 4);
        } else if ((Cobol.compare(f111_PC_BACK, "Y", CS) == 0)) {
            // MOVE 'N' TO PC-BACK
            Cobol.move("N", f111_PC_BACK, CS);
            // MOVE 2 TO PC-STEP
            Cobol.move(D2, f107_PC_STEP, CS);
            // MOVE 'CHANGE THE AMOUNT' TO WS-MSG
            Cobol.move("CHANGE THE AMOUNT", f114_WS_MSG, CS);
            // PERFORM SEND-STEP2
            perform(3, 3);
        } else if ((Cobol.compare(f127_EIBAID, f72_DFHCLEAR, CS) == 0)) {
            // MOVE 'SCREEN RESTORED' TO WS-MSG
            Cobol.move("SCREEN RESTORED", f114_WS_MSG, CS);
            // PERFORM SEND-STEP1
            perform(2, 2);
        } else if (true) {
            // PERFORM TAKE-NAME
            perform(1, 1);
        }
        return 1;
    }

    /** TAKE-NAME. */
    private int p1() {
        // MOVE LOW-VALUES TO PCM1I
        Cobol.moveFigurative(Figurative.LOW_VALUES, f1_PCM1I, CS);
        // EXEC CICS RECEIVE MAP('PCM1') MAPSET('PCSET') INTO(PCM1I) RESP(WS-RESP) END-EXEC
        java.util.Optional<Pcm1Screen> received1 = task.receive("PCM1", "PCSET", Pcm1Screen.class);
        int resp3 = received1.isPresent() ? 0 : 36;
        if (received1.isPresent()) {
            java.util.Arrays.fill(f1_PCM1I.storage().bytes, f1_PCM1I.offset(), f1_PCM1I.offset() + f1_PCM1I.length(), (byte) 0);
            java.util.Map<String, String> typed2 = received1.get().screenValues();
            if (typed2.get("NAME") != null) {
                com.gitgalaxy.modernized.cobolrt.cics.DetJustify.place(f7_NAMEI, f3_NAMEL, typed2.get("NAME"), CS, "LEFT,BLANK");
            }
            if (typed2.get("MSG1") != null) {
                DetCics.typed(f12_MSG1I, f8_MSG1L, typed2.get("MSG1"), CS);
            }
        }
        Cobol.store(f147_EIBRESP, BigDecimal.valueOf(resp3), false, CS);
        Cobol.store(f148_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f113_WS_RESP, BigDecimal.valueOf(resp3), false, CS);
        // IF WS-RESP NOT = DFHRESP(NORMAL) OR NAMEL = 0
        if ((!(Cobol.num(f113_WS_RESP, CS).compareTo(D0) == 0) || Cobol.num(f3_NAMEL, CS).compareTo(D0) == 0)) {
            // ADD 1 TO PC-ERRORS
            BigDecimal t4 = D1;
            Cobol.store(f110_PC_ERRORS, Cobol.receiverNum(f110_PC_ERRORS, CS).add(t4), false, CS);
            // MOVE 'NAME IS REQUIRED' TO WS-MSG
            Cobol.move("NAME IS REQUIRED", f114_WS_MSG, CS);
            // PERFORM SEND-STEP1
            perform(2, 2);
        }
        // MOVE NAMEI TO PC-NAME
        Cobol.move(f7_NAMEI, f108_PC_NAME, CS);
        // MOVE 2 TO PC-STEP
        Cobol.move(D2, f107_PC_STEP, CS);
        // MOVE 'TYPE THE AMOUNT IN CENTS' TO WS-MSG
        Cobol.move("TYPE THE AMOUNT IN CENTS", f114_WS_MSG, CS);
        // PERFORM SEND-STEP2
        perform(3, 3);
        return 2;
    }

    /** SEND-STEP1. */
    private int p2() {
        // MOVE LOW-VALUES TO PCM1O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f13_PCM1O, CS);
        // MOVE WS-MSG TO MSG1O
        Cobol.move(f114_WS_MSG, f18_MSG1O, CS);
        // EXEC CICS SEND MAP('PCM1') MAPSET('PCSET') FROM(PCM1O) ERASE END-EXEC
        java.util.Map<String, String> values6 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub7 = new CicsTask.MapSubfields();
        values6.put("NAME", Cobol.text(f16_NAMEO, CS));
        DetCics.subfields(sub7, "NAME", f3_NAMEL, f6_NAMEA, null, null, CS);
        values6.put("MSG1", Cobol.text(f18_MSG1O, CS));
        DetCics.subfields(sub7, "MSG1", f8_MSG1L, f11_MSG1A, null, null, CS);
        Pcm1Screen screen8 = Pcm1Screen.fromValues(values6);
        task.sendMap("PCM1", "PCSET", screen8, sub7, "ERASE");
        Cobol.store(f147_EIBRESP, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f148_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (0 != 0) {
            int to = condition(DetCics.condition(0));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN TRANSID('PC02') COMMAREA(WS-STATE) LENGTH(30) END-EXEC
        caBack.run();
        task.returnTransid("PC02".strip(), out_PcwizWsState(f106_WS_STATE.storage(), f106_WS_STATE.offset()), 30, Cobol.commarea(f106_WS_STATE, 30).bytes);
        if (true) throw new Goback();
        return 3;
    }

    /** SEND-STEP2. */
    private int p3() {
        // MOVE LOW-VALUES TO PCM2O
        Cobol.moveFigurative(Figurative.LOW_VALUES, f36_PCM2O, CS);
        // MOVE PC-NAME TO NAMEOUTO
        Cobol.move(f108_PC_NAME, f39_NAMEOUTO, CS);
        // IF PC-AMOUNT > 0
        if (Cobol.num(f109_PC_AMOUNT, CS).compareTo(D0) > 0) {
            // COMPUTE WS-AMT-DIGITS = PC-AMOUNT * 100
            BigDecimal v9 = Cobol.multiply(Cobol.num(f109_PC_AMOUNT, CS), DC_100);
            Cobol.store(f115_WS_AMT_DIGITS, v9, false, CS);
            // MOVE WS-AMT-DIGITS TO AMTO
            Cobol.move(f115_WS_AMT_DIGITS, f41_AMTO, CS);
        }
        // MOVE WS-MSG TO MSG2O
        Cobol.move(f114_WS_MSG, f43_MSG2O, CS);
        // EXEC CICS SEND MAP('PCM2') MAPSET('PCSET') FROM(PCM2O) ERASE END-EXEC
        java.util.Map<String, String> values10 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub11 = new CicsTask.MapSubfields();
        values10.put("NAMEOUT", Cobol.text(f39_NAMEOUTO, CS));
        DetCics.subfields(sub11, "NAMEOUT", f21_NAMEOUTL, f24_NAMEOUTA, null, null, CS);
        values10.put("AMT", Cobol.text(f41_AMTO, CS));
        DetCics.subfields(sub11, "AMT", f26_AMTL, f29_AMTA, null, null, CS);
        values10.put("MSG2", Cobol.text(f43_MSG2O, CS));
        DetCics.subfields(sub11, "MSG2", f31_MSG2L, f34_MSG2A, null, null, CS);
        Pcm2Screen screen12 = Pcm2Screen.fromValues(values10);
        task.sendMap("PCM2", "PCSET", screen12, sub11, "ERASE");
        Cobol.store(f147_EIBRESP, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f148_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (0 != 0) {
            int to = condition(DetCics.condition(0));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN TRANSID('PC03') COMMAREA(WS-STATE) LENGTH(30) END-EXEC
        caBack.run();
        task.returnTransid("PC03".strip(), out_PcwizWsState(f106_WS_STATE.storage(), f106_WS_STATE.offset()), 30, Cobol.commarea(f106_WS_STATE, 30).bytes);
        if (true) throw new Goback();
        return 4;
    }

    /** CANCEL-WIZARD. */
    private int p4() {
        // EXEC CICS SEND TEXT FROM(WS-BYE) LENGTH(16) ERASE END-EXEC
        String text13 = Cobol.text(f116_WS_BYE, CS);
        task.sendText(text13.substring(0, Math.min(text13.length(), 16)), 16, "ERASE");
        Cobol.store(f147_EIBRESP, BigDecimal.valueOf(0), false, CS);
        Cobol.store(f148_EIBRESP2, BigDecimal.valueOf(0), false, CS);
        if (0 != 0) {
            int to = condition(DetCics.condition(0));
            if (to >= 0) return GOTO | to;
        }
        // EXEC CICS RETURN END-EXEC
        caBack.run();
        task.returnTransid(null, null);
        if (true) throw new Goback();
        return 5;
    }

}
