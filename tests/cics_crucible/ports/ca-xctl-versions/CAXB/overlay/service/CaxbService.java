package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CaxbDfhcommarea;
import com.gitgalaxy.modernized.entity.vsam.CobolEdit;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
@Transactional
@RequiredArgsConstructor
public class CaxbService {

    private static final Logger log = LoggerFactory.getLogger(CaxbService.class);

    /** LENGTH OF WS-V2 (copy/CAV2.cpy): 80 bytes. */
    private static final int V2_LENGTH = 80;

    // CAV2 layout: offset / length of each field in the 80-byte record.
    private static final int OFF_VERSION = 0, LEN_VERSION = 1;
    private static final int OFF_CUSTID = 1, LEN_CUSTID = 5;
    private static final int OFF_VISITS = 6, LEN_VISITS = 4;
    private static final int OFF_TIER = 10, LEN_TIER = 10;
    private static final int OFF_BALANCE = 20, LEN_BALANCE = 5;   // S9(7)V99 COMP-3: 9 digit nibbles + sign
    private static final int OFF_NOTE = 25, LEN_NOTE = 55;

    private static final int BALANCE_SCALE = 2;
    private static final int BALANCE_DIGITS = 9;

    /** WS-BYE PIC X(13) VALUE 'SESSION ENDED'. */
    private static final String WS_BYE = "SESSION ENDED";

    /** WS-BAL-ED PIC +9(7).99. */
    private static final String WS_BAL_ED_PIC = "+9(7).99";

    /** WS-REPORT PIC X(80). */
    private static final int REPORT_LENGTH = 80;

    /**
     * CAXB is a CICS program (transaction CA03); it has no batch step. The business logic lives in
     * runTask(CicsTask); this entry only records that it was called.
     */
    public void executeCaxb(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for CAXB");
        log.info("CAXB is a pseudo-conversational CICS program (transaction CA03); run it through runTask(CicsTask)");
    }

    /** A CICS transaction entered the program: one task on `request` (its whole record), ENTER pressed. */
    public CaxbDfhcommarea handleTransaction(String transid, CaxbDfhcommarea request) {
        log.info("Caxb: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", request, null, Map.of()).withProgram("CAXB");
        runTask(task);
        return returnedCommarea(task, request);
    }

    /** One pseudo-conversational task of this program (#3754): MAIN-PARA of src/CAXB.cbl. */
    public void runTask(CicsTask task) {
        log.info("Caxb: runTask");

        // MAIN-PARA (lines 25-29): IF EIBAID = DFHPF3 AND EIBTRNID = 'CA03'
        //   SEND TEXT FROM(WS-BYE) LENGTH(13) ERASE, then a plain RETURN (the task ends).
        if ("PF3".equals(task.aid()) && "CA03".equals(task.transid())) {
            task.sendText(WS_BYE, 13, "ERASE");
            task.returnTransid(null, null);
            return;
        }

        // MAIN-PARA (line 30): INITIALIZE WS-V2 -- alphanumerics to spaces, numerics to zero.
        CaxbDfhcommarea ws = new CaxbDfhcommarea();
        ws.setV2Version(alpha(null, LEN_VERSION));
        ws.setV2Custid(alpha(null, LEN_CUSTID));
        ws.setV2Visits(0);
        ws.setV2Tier(alpha(null, LEN_TIER));
        ws.setV2Balance(BigDecimal.ZERO.setScale(BALANCE_SCALE));
        ws.setV2Note(alpha(null, LEN_NOTE));

        // MAIN-PARA (lines 31-32): defaults for a version-1 caller.
        ws.setV2Tier(alpha("STANDARD", LEN_TIER));
        ws.setV2Note(alpha("UPGRADED FROM V1", LEN_NOTE));

        // MAIN-PARA (lines 33-40): the COMMAREA, trusted by EIBCALEN.
        int eibcalen = eibcalen(task);
        if (eibcalen > 0) {
            CaxbDfhcommarea ca = task.commarea(CaxbDfhcommarea.class);
            if (eibcalen < V2_LENGTH) {
                // MOVE DFHCOMMAREA(1:EIBCALEN) TO WS-V2(1:EIBCALEN): a byte overlay of the first EIBCALEN
                // bytes -- a field the length cuts through keeps its leading bytes from the COMMAREA and its
                // trailing bytes from WS-V2 as initialized above.
                overlay(ca, ws, eibcalen);
                // MOVE '2' TO V2-VERSION OF WS-V2
                ws.setV2Version(alpha("2", LEN_VERSION));
            } else {
                // MOVE DFHCOMMAREA(1:LENGTH OF WS-V2) TO WS-V2: every field taken as given.
                // DEFECT (kept): a caller passing 80 or more bytes that are not a version-2 record (CAXA's
                // XCTL LENGTH(80) of its 10-byte WS-V1, or its 32767-byte WS-BIG) is trusted blindly --
                // the caller's neighbouring storage becomes V2-TIER / V2-BALANCE / V2-NOTE and V2-VERSION
                // is neither checked nor set. Fix: IF V2-VERSION OF DFHCOMMAREA NOT = '2' treat the
                // COMMAREA as version 1 (take 10 bytes and default the rest).
                overlay(ca, ws, V2_LENGTH);
            }
        }

        // MAIN-PARA (line 41): ADD 1 TO V2-VISITS OF WS-V2 -- PIC 9(4), no SIZE ERROR: 9999 + 1 keeps 0000.
        // DEFECT (kept): the visit counter silently wraps from 9999 to 0000. Fix: add ON SIZE ERROR
        // (or widen V2-VISITS).
        int visits = ws.getV2Visits() == null ? 0 : Math.abs(ws.getV2Visits()) % 10000;
        ws.setV2Visits((visits + 1) % 10000);

        // MAIN-PARA (line 42): MOVE EIBCALEN TO WS-CALEN-D -- S9(4) COMP into unsigned PIC 9(4):
        // the sign is dropped and only the low-order four digits are kept.
        int wsCalenD = Math.abs(eibcalen) % 10000;

        // MAIN-PARA (line 43): MOVE V2-BALANCE OF WS-V2 TO WS-BAL-ED (PIC +9(7).99).
        BigDecimal balance = packedValue(ws.getV2Balance());
        ws.setV2Balance(balance);
        String wsBalEd = CobolEdit.format(WS_BAL_ED_PIC, balance, false, null);

        // MAIN-PARA (lines 44-51): STRING ... DELIMITED BY SIZE INTO WS-REPORT (VALUE SPACES, 80 bytes;
        // STRING does not pad, so the untouched tail stays spaces).
        StringBuilder sb = new StringBuilder();
        sb.append("V=").append(alpha(ws.getV2Version(), LEN_VERSION));
        sb.append(" C=").append(alpha(ws.getV2Custid(), LEN_CUSTID));
        sb.append(" N=").append(String.format(Locale.ROOT, "%04d", ws.getV2Visits()));
        sb.append(" T=").append(alpha(ws.getV2Tier(), LEN_TIER));
        sb.append(" B=").append(wsBalEd);
        sb.append(" L=").append(String.format(Locale.ROOT, "%04d", wsCalenD));
        sb.append(' ').append(alpha(ws.getV2Note(), LEN_NOTE), 0, 16);   // V2-NOTE OF WS-V2(1:16)
        String wsReport = alpha(sb.toString(), REPORT_LENGTH);          // STRING stops at the receiver's end

        // MAIN-PARA (lines 52-53): SEND TEXT FROM(WS-REPORT) LENGTH(80) ERASE
        task.sendText(wsReport, REPORT_LENGTH, "ERASE");

        // MAIN-PARA (lines 54-55): RETURN TRANSID('CA03') COMMAREA(WS-V2) LENGTH(80)
        task.returnTransid("CA03", ws, V2_LENGTH);
    }

    /** Another program LINKed / XCTLed to this one: one task on `request` (its whole record). */
    public CaxbDfhcommarea handleLink(CaxbDfhcommarea request) {
        log.info("Caxb: handleLink");
        CicsTask task = new CicsTask("CA03", "ENTER", request, null, Map.of()).withProgram("CAXB");
        runTask(task);
        return returnedCommarea(task, request);
    }

    // ------------------------------------------------------------------ helpers

    /** EIBCALEN: 0 without a COMMAREA, the whole record (80) when the task gives none (#4009). */
    private static int eibcalen(CicsTask task) {
        if (!task.hasCommarea()) {
            return 0;
        }
        Integer len = task.eibcalen();
        return len == null ? V2_LENGTH : len;
    }

    /**
     * WS-V2(1:len) = DFHCOMMAREA(1:len), len 1..80: each field receives the COMMAREA's bytes that fall
     * within the first `len` bytes and keeps its own for the rest.
     */
    private static void overlay(CaxbDfhcommarea ca, CaxbDfhcommarea ws, int len) {
        ws.setV2Version(overlayAlpha(ca.getV2Version(), ws.getV2Version(), OFF_VERSION, LEN_VERSION, len));
        ws.setV2Custid(overlayAlpha(ca.getV2Custid(), ws.getV2Custid(), OFF_CUSTID, LEN_CUSTID, len));
        ws.setV2Visits(overlayVisits(ca.getV2Visits(), ws.getV2Visits(), len));
        ws.setV2Tier(overlayAlpha(ca.getV2Tier(), ws.getV2Tier(), OFF_TIER, LEN_TIER, len));
        ws.setV2Balance(overlayBalance(ca.getV2Balance(), ws.getV2Balance(), len));
        ws.setV2Note(overlayAlpha(ca.getV2Note(), ws.getV2Note(), OFF_NOTE, LEN_NOTE, len));
    }

    /** Bytes of a field at `offset` (length `size`) that the first `len` bytes cover. */
    private static int covered(int offset, int size, int len) {
        return Math.max(0, Math.min(size, len - offset));
    }

    private static String overlayAlpha(String from, String to, int offset, int size, int len) {
        int k = covered(offset, size, len);
        String src = alpha(from, size);
        String dst = alpha(to, size);
        return src.substring(0, k) + dst.substring(k);
    }

    /** V2-VISITS PIC 9(4) unsigned DISPLAY: one digit character per byte. */
    private static Integer overlayVisits(Integer from, Integer to, int len) {
        int k = covered(OFF_VISITS, LEN_VISITS, len);
        String src = String.format(Locale.ROOT, "%04d", Math.abs(from == null ? 0 : from) % 10000);
        String dst = String.format(Locale.ROOT, "%04d", Math.abs(to == null ? 0 : to) % 10000);
        String digits = src.substring(0, k) + dst.substring(k);
        int v = 0;
        for (int i = 0; i < digits.length(); i++) {
            v = v * 10 + (digits.charAt(i) - '0');
        }
        return v;
    }

    /**
     * V2-BALANCE S9(7)V99 COMP-3: 5 bytes = 9 digit nibbles + a sign nibble. Byte j holds nibbles 2j and
     * 2j+1, so k of the 5 bytes carry the first 2k digits; the sign nibble travels only with the 5th byte.
     * WS-V2's balance at this point is +0 (INITIALIZE), so a partial overlay keeps its + sign.
     */
    private static BigDecimal overlayBalance(BigDecimal from, BigDecimal to, int len) {
        int k = covered(OFF_BALANCE, LEN_BALANCE, len);
        BigDecimal src = packedValue(from);
        BigDecimal dst = packedValue(to);
        if (k == LEN_BALANCE) {
            return src;
        }
        if (k == 0) {
            return dst;
        }
        String srcDigits = digits(src);
        String dstDigits = digits(dst);
        int n = Math.min(2 * k, BALANCE_DIGITS);
        String merged = srcDigits.substring(0, n) + dstDigits.substring(n);
        BigDecimal v = new BigDecimal(new BigInteger(merged, 10), BALANCE_SCALE);
        return dst.signum() < 0 ? v.negate() : v;
    }

    /** A value as S9(7)V99 holds it: scale 2 truncated, high-order digits beyond nine dropped. */
    private static BigDecimal packedValue(BigDecimal value) {
        BigDecimal v = value == null ? BigDecimal.ZERO : value;
        v = v.setScale(BALANCE_SCALE, RoundingMode.DOWN);
        BigInteger unscaled = v.unscaledValue();
        BigInteger kept = unscaled.abs().mod(BigInteger.TEN.pow(BALANCE_DIGITS));
        return new BigDecimal(unscaled.signum() < 0 ? kept.negate() : kept, BALANCE_SCALE);
    }

    private static String digits(BigDecimal packed) {
        return String.format(Locale.ROOT, "%09d", packed.unscaledValue().abs());
    }

    /** MOVE to PIC X(size): pad with spaces or truncate on the right. */
    private static String alpha(String value, int size) {
        String v = value == null ? "" : value;
        if (v.length() >= size) {
            return v.substring(0, size);
        }
        StringBuilder sb = new StringBuilder(size).append(v);
        while (sb.length() < size) {
            sb.append(' ');
        }
        return sb.toString();
    }

    /** The COMMAREA of the task's RETURN, if it returned one. */
    private static CaxbDfhcommarea returnedCommarea(CicsTask task, CaxbDfhcommarea fallback) {
        List<Map<String, Object>> events = task.events();
        for (int i = events.size() - 1; i >= 0; i--) {
            Map<String, Object> e = events.get(i);
            if ("RETURN".equals(e.get("event"))) {
                Object ca = e.get("commarea");
                return ca instanceof CaxbDfhcommarea c ? c : fallback;
            }
        }
        return fallback;
    }
}
