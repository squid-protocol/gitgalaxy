package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.CasubDfhcommarea;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Port of CALINK (src/CALINK.cbl): LINKs to CASUB with a 100-byte request header (copy/CAHDR.cpy)
 * in one of four modes typed after the transid, then SENDs a one-line report and RETURNs.
 *
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * the RESP of the LINK at line 52 (paragraph MAIN-PARA) is captured into WS-RESP / WS-RESP2 and
 * only reported; no branch ever tests it (kept as in the original, see MAIN-PARA below).
 */
@Service
@Transactional
@RequiredArgsConstructor
public class CalinkService {

    private static final Logger log = LoggerFactory.getLogger(CalinkService.class);

    private final ObjectProvider<CasubService> casubService;

    /** A CICS transaction entered the program. */
    public void handleTransaction(String transid) {
        log.info("Calink: handleTransaction {}", transid);
    }

    /** One pseudo-conversational task of this program (#3754): the PROCEDURE DIVISION (MAIN-PARA). */
    public void runTask(CicsTask task) {
        log.info("Calink: runTask");
        WorkingStorage ws = new WorkingStorage();

        // MAIN-PARA, line 33: EXEC CICS RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN) END-EXEC
        // No RESP option: an unhandled condition (LENGERR for more than 20 bytes typed) takes CICS's
        // default action, an abend of the task (AEIV).
        CicsTask.Received received = task.receiveText(ws.inlen);
        if (!"NORMAL".equals(received.resp())) {
            task.abendOnCondition(received.resp());
            return;
        }
        ws.inlen = (short) received.length();          // WS-INLEN PIC S9(4) COMP: set to the length received
        ws.input = overlay(ws.input, received.data()); // RECEIVE INTO moves only the bytes received

        // MAIN-PARA, line 35: MOVE WS-INPUT(6:1) TO WS-MODE
        ws.mode = ws.input.substring(5, 6);

        // MAIN-PARA, line 36: INITIALIZE WS-CA100 (alphanumerics to spaces, CA-SEEN-LEN to zero)
        ws.caEye = pic("", 4);
        ws.caVersion = pic("", 1);
        ws.caRc = pic("", 2);
        ws.caSeenLen = 0;
        ws.caRequest = pic("", 20);
        ws.caReply = pic("", 20);
        ws.caSpare = pic("", 51);

        // MAIN-PARA, lines 37-39
        ws.caEye = pic("CAHD", 4);       // MOVE 'CAHD' TO CA-EYE
        ws.caVersion = pic("1", 1);      // MOVE '1' TO CA-VERSION
        ws.caRequest = pic("PING", 20);  // MOVE 'PING' TO CA-REQUEST

        // MAIN-PARA, lines 40-55: EVALUATE WS-MODE
        int mark = task.events().size();
        switch (ws.mode) {
            case "S" -> {
                // WHEN 'S', line 42: LINK PROGRAM('CASUB') COMMAREA(WS-CA100) LENGTH(100), no RESP
                String resp = linkWithCommarea(task, ws, "CASUB", 100);
                if (terminatedSince(task, mark)) {
                    return;
                }
                if (!"NORMAL".equals(resp)) {
                    task.abendOnCondition(resp);   // no RESP: CICS's default action abends the task
                    return;
                }
            }
            case "L" -> {
                // WHEN 'L', line 46: LINK PROGRAM('CASUB') COMMAREA(WS-CA100) LENGTH(500), no RESP.
                // DEFECT (kept): LENGTH(500) on a 100-byte WS-CA100 hands CASUB the next 400 bytes of this
                // program's storage (WS-AFTER) as its CA-EXT-FLAG / CA-EXT-DATA.
                // Fix: LENGTH(LENGTH OF WS-CA100), or pass a 500-byte area.
                String resp = linkWithCommarea(task, ws, "CASUB", 500);
                if (terminatedSince(task, mark)) {
                    return;
                }
                if (!"NORMAL".equals(resp)) {
                    task.abendOnCondition(resp);
                    return;
                }
            }
            case "Z" -> {
                // WHEN 'Z', line 50: LINK PROGRAM('CASUB') with no COMMAREA (callee's EIBCALEN = 0), no RESP
                String resp = task.link("CASUB");
                if (terminatedSince(task, mark)) {
                    return;
                }
                if (!"NORMAL".equals(resp)) {
                    task.abendOnCondition(resp);
                    return;
                }
            }
            default -> {
                // WHEN OTHER, line 52: LINK PROGRAM('CAGONE') COMMAREA(WS-CA100) LENGTH(100)
                //                      RESP(WS-RESP) RESP2(WS-RESP2)
                // Reached by mode 'P' and by any other character, a blank mode (nothing typed after the
                // transid) and lower-case 's' / 'l' / 'z' included.
                // DEFECT (kept): WS-RESP is never tested; a PGMIDERR is only shown in the report and the
                // program goes on with the header it built itself.
                // Fix: IF WS-RESP NOT = DFHRESP(NORMAL) handle the failed LINK before using the COMMAREA.
                String resp = linkWithCommarea(task, ws, "CAGONE", 100);
                if (terminatedSince(task, mark)) {
                    return;
                }
                ws.resp = dfhresp(resp);
                ws.resp2 = dfhresp2(resp);
            }
        }

        // MAIN-PARA, line 56: MOVE CA-SEEN-LEN TO WS-SEEN-D
        // S9(4) COMP to PIC 9(4): the sign is dropped and only the low-order 4 digits are kept.
        int seenD = Math.abs(ws.caSeenLen) % 10000;
        // MAIN-PARA, lines 57-58: MOVE WS-RESP TO WS-RESP-D, MOVE WS-RESP2 TO WS-RESP2-D
        // S9(8) COMP to PIC 99: unsigned, low-order 2 digits.
        int respD = (int) (Math.abs((long) ws.resp) % 100);
        int resp2D = (int) (Math.abs((long) ws.resp2) % 100);

        // MAIN-PARA, lines 59-63: STRING ... DELIMITED BY SIZE INTO WS-REPORT
        // 70 bytes are moved into the 80-byte WS-REPORT, whose remaining bytes keep their VALUE SPACES.
        StringBuilder sb = new StringBuilder();
        sb.append("MODE=").append(ws.mode)
                .append(" RC=").append(ws.caRc)
                .append(" SEEN=").append(String.format(Locale.ROOT, "%04d", seenD))
                .append(" REPLY=").append(ws.caReply, 0, 4)
                .append(" AFTER=").append(ws.afterFlag)
                .append(' ').append(ws.afterData, 0, 17)
                .append(" RESP=").append(String.format(Locale.ROOT, "%02d", respD))
                .append('/').append(String.format(Locale.ROOT, "%02d", resp2D));
        ws.report = overlay(ws.report, sb.toString());

        // MAIN-PARA, lines 64-65: EXEC CICS SEND TEXT FROM(WS-REPORT) LENGTH(80) ERASE END-EXEC
        task.sendText(ws.report, 80, "ERASE");

        // MAIN-PARA, line 66: EXEC CICS RETURN END-EXEC
        task.returnTransid(null, null);
    }

    /** EXEC CICS LINK PROGRAM(CASUB) at src/CALINK.cbl:42, src/CALINK.cbl:46, src/CALINK.cbl:50.
     *  Call targets field testing: open (6 public / 0 private estates).
     *  Generated direct call; the CICS port goes through CicsTask.link so the callee runs at the next level. */
    public CasubDfhcommarea linkCasub(CasubDfhcommarea request) {
        return casubService.getObject().handleLink(request);
    }

    // ---------------------------------------------------------------------------------------------------

    /**
     * LINK ... COMMAREA(WS-CA100) LENGTH(length). A local LINK passes the address of WS-CA100 itself, so
     * CASUB's 500-byte DFHCOMMAREA lies over WS-BLOCK: its first 100 bytes are WS-CA100 and its
     * CA-EXT-FLAG / CA-EXT-DATA are this program's WS-AFTER-FLAG / WS-AFTER-DATA, whatever LENGTH says
     * (LENGTH only sets the callee's EIBCALEN). The DTO is built from that storage, passed by reference,
     * and whatever the callee changed in it is copied back.
     */
    private static String linkWithCommarea(CicsTask task, WorkingStorage ws, String program, int length) {
        CasubDfhcommarea ca = new CasubDfhcommarea();
        ca.setCaEye(ws.caEye);
        ca.setCaVersion(ws.caVersion);
        ca.setCaRc(ws.caRc);
        ca.setCaSeenLen((int) ws.caSeenLen);
        ca.setCaRequest(ws.caRequest);
        ca.setCaReply(ws.caReply);
        ca.setCaSpare(ws.caSpare);
        ca.setCaExtFlag(ws.afterFlag);
        ca.setCaExtData(ws.afterData);

        String resp = task.link(program, ca, length);

        ws.caEye = pic(ca.getCaEye(), 4);
        ws.caVersion = pic(ca.getCaVersion(), 1);
        ws.caRc = pic(ca.getCaRc(), 2);
        ws.caSeenLen = ca.getCaSeenLen() == null ? 0 : (short) ca.getCaSeenLen().intValue(); // a halfword
        ws.caRequest = pic(ca.getCaRequest(), 20);
        ws.caReply = pic(ca.getCaReply(), 20);
        ws.caSpare = pic(ca.getCaSpare(), 51);
        ws.afterFlag = pic(ca.getCaExtFlag(), 1);
        ws.afterData = pic(ca.getCaExtData(), 399);
        return resp;
    }

    /** Whether a program LINKed to terminated the task with an abend no exit took (the task ends there). */
    private static boolean terminatedSince(CicsTask task, int mark) {
        List<Map<String, Object>> events = task.events();
        for (int i = mark; i < events.size(); i++) {
            Map<String, Object> e = events.get(i);
            if ("ABEND".equals(e.get("event")) && "terminated".equals(e.get("outcome"))) {
                return true;
            }
        }
        return false;
    }

    /** DFHRESP value of the conditions a LINK raises. */
    private static int dfhresp(String resp) {
        return switch (resp) {
            case "NORMAL" -> 0;
            case "INVREQ" -> 16;
            case "LENGERR" -> 22;
            case "PGMIDERR" -> 27;
            default -> throw new IllegalStateException("LINK condition with no DFHRESP value known: " + resp);
        };
    }

    /** RESP2 of the conditions a LINK raises (IBM EXEC CICS LINK: LENGERR 11, PGMIDERR 1). */
    private static int dfhresp2(String resp) {
        return switch (resp) {
            case "NORMAL" -> 0;
            case "LENGERR" -> 11;
            case "PGMIDERR" -> 1;
            default -> throw new IllegalStateException("LINK condition with no RESP2 value known: " + resp);
        };
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String pic(String value, int length) {
        String v = value == null ? "" : value;
        if (v.length() >= length) {
            return v.substring(0, length);
        }
        StringBuilder sb = new StringBuilder(length).append(v);
        while (sb.length() < length) {
            sb.append(' ');
        }
        return sb.toString();
    }

    /** Moves `data` over the leading bytes of `field`, keeping the rest of the field as it was. */
    private static String overlay(String field, String data) {
        String d = data == null ? "" : data;
        if (d.length() >= field.length()) {
            return d.substring(0, field.length());
        }
        return d + field.substring(d.length());
    }

    /** CALINK's WORKING-STORAGE, fresh for every task, with its VALUE clauses. */
    private static final class WorkingStorage {
        String input = pic("", 20);        // WS-INPUT    PIC X(20) VALUE SPACES
        short inlen = 20;                  // WS-INLEN    PIC S9(4) COMP VALUE 20
        String mode = " ";                 // WS-MODE     PIC X VALUE SPACE
        int resp = 0;                      // WS-RESP     PIC S9(8) COMP VALUE 0
        int resp2 = 0;                     // WS-RESP2    PIC S9(8) COMP VALUE 0
        String report = pic("", 80);       // WS-REPORT   PIC X(80) VALUE SPACES
        // WS-BLOCK / WS-CA100 (copy/CAHDR.cpy): no VALUE clauses, set by INITIALIZE before use
        String caEye = pic("", 4);
        String caVersion = pic("", 1);
        String caRc = pic("", 2);
        short caSeenLen = 0;
        String caRequest = pic("", 20);
        String caReply = pic("", 20);
        String caSpare = pic("", 51);
        // WS-BLOCK / WS-AFTER
        String afterFlag = "N";                       // WS-AFTER-FLAG PIC X VALUE 'N'
        String afterData = pic("CALLER-OWNED", 399);  // WS-AFTER-DATA PIC X(399) VALUE 'CALLER-OWNED'
    }
}
