// gitgalaxy-det-port: COBOL DFSORTST (DFSORTST.cbl), translated by rule, statement for statement
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
import com.gitgalaxy.modernized.cobolrt.Sort;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Base64;
import java.util.List;
import org.springframework.stereotype.Service;

/**
 * DFSORTST: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;
 * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.
 * Statements: 2, translated 2, holes 0.
 */
@Service
public class DfsortstService {

    private static final Charset CS = Cobol.recordCharset(CobolRecords.charset());
    private static final int GOTO = 1 << 20;

    private static final byte[] IMAGE_s_I1_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_I2_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_O_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_S_REC = Base64.getDecoder().decode(String.join("",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg",
            "ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA="));
    private static final byte[] IMAGE_s_DFHEIBLK = Base64.getDecoder().decode(String.join("",
            "AAAADAAAAAwgICAgAAAADCAgICAAAAAAAAAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAAAAAAAAAAAIA=="));
    private static final byte[] IMAGE_s_GG_RETURN_CODE = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private static final byte[] IMAGE_s_GG_SORT_RETURN = Base64.getDecoder().decode(String.join("",
            "AAA="));
    private final Storage s_I1_REC = new Storage(IMAGE_s_I1_REC.length);
    private final Storage s_I2_REC = new Storage(IMAGE_s_I2_REC.length);
    private final Storage s_O_REC = new Storage(IMAGE_s_O_REC.length);
    private final Storage s_S_REC = new Storage(IMAGE_s_S_REC.length);
    private final Storage s_DFHEIBLK = new Storage(IMAGE_s_DFHEIBLK.length);
    private final Storage s_GG_RETURN_CODE = new Storage(IMAGE_s_GG_RETURN_CODE.length);
    private final Storage s_GG_SORT_RETURN = new Storage(IMAGE_s_GG_SORT_RETURN.length);

    private final Field f1_I1_REC = Field.alphanumeric(s_I1_REC, 0, 350, false);
    private final Field f2_I2_REC = Field.alphanumeric(s_I2_REC, 0, 350, false);
    private final Field f3_O_REC = Field.alphanumeric(s_O_REC, 0, 350, false);
    private final Field f11_EIBTIME = Field.packed(s_DFHEIBLK, 0, 7, 0, true);
    private final Field f12_EIBDATE = Field.packed(s_DFHEIBLK, 4, 7, 0, true);
    private final Field f13_EIBTRNID = Field.alphanumeric(s_DFHEIBLK, 8, 4, false);
    private final Field f14_EIBTASKN = Field.packed(s_DFHEIBLK, 12, 7, 0, true);
    private final Field f15_EIBTRMID = Field.alphanumeric(s_DFHEIBLK, 16, 4, false);
    private final Field f18_EIBCALEN = Field.binary(s_DFHEIBLK, 24, 4, 0, true, false);
    private final Field f42_GG_RETURN_CODE = Field.binary(s_GG_RETURN_CODE, 0, 4, 0, true, false);
    private final Field f43_GG_SORT_RETURN = Field.binary(s_GG_SORT_RETURN, 0, 4, 0, true, false);
    private String f8_W_EOF;  // W-EOF PIC X
    private String f9_W_REC;  // W-REC PIC X(350)

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
        if (CicsTask.undefinableFile(name)) {
            return DetCics.Store.undefined(CS);
        }
        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");
    }

    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(
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

    private DetFiles.DetFile I1_FILE;
    private DetFiles.DetFile I2_FILE;
    private DetFiles.DetFile O_FILE;
    private Sort sort_S_FILE;

    private final DatasetResolver datasets;
    private final CobolFiles files;
    private final MainframeClock clock;

    public DfsortstService(DatasetResolver datasets, CobolFiles files, MainframeClock clock) {
        this.datasets = datasets;
        this.files = files;
        this.clock = clock;
    }

    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */
    private void initialState() {
        System.arraycopy(IMAGE_s_I1_REC, 0, s_I1_REC.bytes, 0, IMAGE_s_I1_REC.length);
        System.arraycopy(IMAGE_s_I2_REC, 0, s_I2_REC.bytes, 0, IMAGE_s_I2_REC.length);
        System.arraycopy(IMAGE_s_O_REC, 0, s_O_REC.bytes, 0, IMAGE_s_O_REC.length);
        System.arraycopy(IMAGE_s_S_REC, 0, s_S_REC.bytes, 0, IMAGE_s_S_REC.length);
        System.arraycopy(IMAGE_s_DFHEIBLK, 0, s_DFHEIBLK.bytes, 0, IMAGE_s_DFHEIBLK.length);
        System.arraycopy(IMAGE_s_GG_RETURN_CODE, 0, s_GG_RETURN_CODE.bytes, 0, IMAGE_s_GG_RETURN_CODE.length);
        System.arraycopy(IMAGE_s_GG_SORT_RETURN, 0, s_GG_SORT_RETURN.bytes, 0, IMAGE_s_GG_SORT_RETURN.length);
        f8_W_EOF = " ";
        f9_W_REC = "                                                                                                                                                                                                                                                                                                                                                              ";
    }

    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its
     *  initial storage; RETURN-CODE. */
    public int runProgram() {
        initialState();
        performDepth = 0;
        try {
            perform(0, 0);
        } catch (Goback g) {
            // the program ended
        }
        return Cobol.num(f42_GG_RETURN_CODE, CS).intValue();
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
            Cobol.move(task.transid(), f13_EIBTRNID, CS);
            Cobol.move(task.termid() == null ? "" : task.termid(), f15_EIBTRMID, CS);
            Cobol.store(f14_EIBTASKN, BigDecimal.valueOf(task.taskNumber()), false, CS);
            java.time.LocalDateTime now = task.now();
            Cobol.store(f12_EIBDATE, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);
            Cobol.store(f11_EIBTIME, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);
            switch (task.aid() == null ? "" : task.aid()) {
                default -> { }
            }
            Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;
            int calen = 0;
            if (ca instanceof CarddemoCommarea) {
                calen = cx(task, 160);
            } else if (ca instanceof Cbstm03bLkM03bArea) {
                calen = cx(task, 1040);
            } else if (ca instanceof CoactupcWsThisProgcommarea) {
                calen = cx(task, 873);
            } else if (ca instanceof Copaua0cDfhcommarea) {
                calen = cx(task, 4096);
            }
            Cobol.store(f18_EIBCALEN, BigDecimal.valueOf(calen), false, CS);
            try {
                perform(0, 0);
            } catch (Goback g) {
                // RETURN / XCTL / an abend ended the program
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

    public Object handleTransaction(String transid, Object request) {
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.transaction(transid, request);
        region.run(task, "DFSORTST", this::runTask);
        return task.returned(Object.class);
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
            I1_FILE = new DetFiles.Sequential(files, "SORTIN1", () -> datasets.path(dd(dds, "SORTIN1")), s_I1_REC, 0, 350);
            I2_FILE = new DetFiles.Sequential(files, "SORTIN2", () -> datasets.path(dd(dds, "SORTIN2")), s_I2_REC, 0, 350);
            O_FILE = new DetFiles.Sequential(files, "SORTOUT", () -> datasets.path(dd(dds, "SORTOUT")), s_O_REC, 0, 350);
            try {
                perform(0, 0);
            } catch (Goback g) {
                // the program ended
            }
            return Cobol.num(f42_GG_RETURN_CODE, CS).intValue();
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
                if (next >= 1) {
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
            default: throw new IllegalStateException("paragraph " + i);
        }
    }

    /** MAIN-PARA. */
    private int p0() {
        // SORT S-FILE ON ASCENDING KEY K1 USING I1-FILE I2-FILE GIVING O-FILE
        sort_S_FILE = new Sort("S-FILE", 350, false, CS, Sort.Collating.ebcdic("EB", CS),
                new Sort.Key(r -> Field.alphanumeric(r, 0, 16, false), true));
        String st1 = I1_FILE.open("INPUT");
        Sort.expect(st1, "SORT USING I1-FILE: OPEN", "00");
        while (true) {
            st1 = I1_FILE.readNext();
            if (st1.equals("10")) {
                break;
            }
            Sort.expect(st1, "SORT USING I1-FILE: READ", "00");
            sort_S_FILE.add(f1_I1_REC);
        }
        st1 = I1_FILE.close();
        Sort.expect(st1, "SORT USING I1-FILE: CLOSE", "00");
        String st2 = I2_FILE.open("INPUT");
        Sort.expect(st2, "SORT USING I2-FILE: OPEN", "00");
        while (true) {
            st2 = I2_FILE.readNext();
            if (st2.equals("10")) {
                break;
            }
            Sort.expect(st2, "SORT USING I2-FILE: READ", "00");
            sort_S_FILE.add(f2_I2_REC);
        }
        st2 = I2_FILE.close();
        Sort.expect(st2, "SORT USING I2-FILE: CLOSE", "00");
        sort_S_FILE.sort();
        sort_S_FILE.rewind(350);
        String st3 = O_FILE.open("OUTPUT");
        Sort.expect(st3, "SORT GIVING O-FILE: OPEN", "00");
        for (byte[] r4 = sort_S_FILE.next(); r4 != null; r4 = sort_S_FILE.next()) {
            f3_O_REC.putRaw(r4);
            st3 = O_FILE.write(350);
            Sort.expect(st3, "SORT GIVING O-FILE: WRITE", "00");
        }
        st3 = O_FILE.close();
        Sort.expect(st3, "SORT GIVING O-FILE: CLOSE", "00");
        sort_S_FILE = null;
        Sort.finished(f43_GG_SORT_RETURN, CS);
        // GOBACK
        if (true) throw new Goback();
        return 1;
    }

}
