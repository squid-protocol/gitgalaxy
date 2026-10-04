package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.PcdetlWsCa;
import com.gitgalaxy.modernized.dto.contract.PcmenuWsCa;
import com.gitgalaxy.modernized.dto.screen.PcmnScreen;
import com.gitgalaxy.modernized.dto.screen.ScreenModel;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * HANDLE AID mapping (field testing: field-tested (6 public / 0 private estates)):
 *   HANDLE AID at line 37: PF3 -> MENU-EXIT
 *   HANDLE AID at line 37: PF5 -> MENU-REFRESH
 *
 * Screens (#3619): PcmnScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class PcmenuService {

    private static final Logger log = LoggerFactory.getLogger(PcmenuService.class);

    private final ObjectProvider<PcdetlService> pcdetlService;

    /** WS-BYE PIC X(10) VALUE 'MENU ENDED'. */
    private static final String WS_BYE = "MENU ENDED";
    /** WS-NEXT PIC X(20) VALUE 'DETAIL ON NEXT ENTER'. */
    private static final String WS_NEXT = "DETAIL ON NEXT ENTER";
    /** LOW-VALUES in a PIC X(1) symbolic-map output field. */
    private static final String LOW_VALUE_1 = "\u0000";

    /** The program's WORKING-STORAGE: fresh for every task, as CICS gives each task its own copy. */
    private static final class WorkingStorage {
        // WS-CA (COPY PCMENUCA)
        int mnVisits;          // MN-VISITS PIC 9(4)
        String mnLast;         // MN-LAST   PIC X(4)
        String mnFlag;         // MN-FLAG   PIC XX
        // WS-MSG PIC X(40) VALUE SPACES
        String wsMsg = fit(null, 40);

        /** INITIALIZE WS-CA: numeric to zero, alphanumeric to spaces. */
        void initializeWsCa() {
            mnVisits = 0;
            mnLast = fit(null, 4);
            mnFlag = fit(null, 2);
        }

        /** MOVE DFHCOMMAREA TO WS-CA: the 10 bytes of the COMMAREA, field by field. */
        void moveCommarea(Object commarea) {
            if (commarea instanceof PcmenuWsCa ca) {
                mnVisits = visits(ca.getMnVisits());
                mnLast = fit(ca.getMnLast(), 4);
                mnFlag = fit(ca.getMnFlag(), 2);
            } else if (commarea instanceof PcdetlWsCa ca) {
                // RETURN TRANSID('PC11') from PCDETL (navigation fact src/PCDETL.cbl:35) passes the same
                // 10-byte layout (copy/PCMENUCA.cpy) under PCDETL's DTO.
                mnVisits = visits(ca.getMnVisits());
                mnLast = fit(ca.getMnLast(), 4);
                mnFlag = fit(ca.getMnFlag(), 2);
            } else {
                throw new IllegalStateException("PCMENU: unexpected COMMAREA type "
                        + (commarea == null ? "null" : commarea.getClass().getName()));
            }
        }

        PcmenuWsCa toPcmenuCa() {
            PcmenuWsCa ca = new PcmenuWsCa();
            ca.setMnVisits(mnVisits);
            ca.setMnLast(mnLast);
            ca.setMnFlag(mnFlag);
            return ca;
        }

        PcdetlWsCa toPcdetlCa() {
            PcdetlWsCa ca = new PcdetlWsCa();
            ca.setMnVisits(mnVisits);
            ca.setMnLast(mnLast);
            ca.setMnFlag(mnFlag);
            return ca;
        }
    }

    public void executePcmenu(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for PCMENU");
        // PCMENU is a pseudo-conversational CICS program (transaction PC11): it has no batch step.
        // Its whole PROCEDURE DIVISION is ported into runTask(CicsTask), one task per call (#3754).
        log.info("PCMENU runs online only: drive it through runTask(CicsTask)");
    }

    /** A CICS transaction entered the program: runs one task with ENTER on the given COMMAREA and
     *  returns the COMMAREA the task passed on RETURN TRANSID (the request itself when it passed none). */
    public PcmenuWsCa handleTransaction(String transid, PcmenuWsCa request) {
        log.info("Pcmenu: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", request, Map.of()).withProgram("PCMENU");
        runTask(task);
        List<Map<String, Object>> events = task.events();
        for (int i = events.size() - 1; i >= 0; i--) {
            Map<String, Object> e = events.get(i);
            if ("RETURN".equals(e.get("event")) && e.get("commarea") instanceof PcmenuWsCa ca) {
                return ca;
            }
        }
        return request;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Pcmenu: runTask");
        WorkingStorage ws = new WorkingStorage();
        String aid = task.aid();

        // ---- MAIN-PARA ----
        // IF EIBCALEN = 0 -- a new session whatever key was pressed (PF3 included)
        Integer eibcalen = task.eibcalen();
        if (!task.hasCommarea() || (eibcalen != null && eibcalen == 0)) {
            // INITIALIZE WS-CA / MOVE 1 TO MN-VISITS / MOVE 'WELCOME' TO WS-MSG
            ws.initializeWsCa();
            ws.mnVisits = 1;
            ws.wsMsg = fit("WELCOME", 40);
            // PERFORM SHOW-MENU: it ends with RETURN, so the task ends here.
            showMenu(task, ws);
            return;
        }
        // MOVE DFHCOMMAREA TO WS-CA
        // Kept: DFHCOMMAREA is PIC X(10) and is moved whole even when EIBCALEN < 10 (the bytes past
        // EIBCALEN are not the caller's). Fix: move only DFHCOMMAREA(1:EIBCALEN) after INITIALIZE WS-CA.
        ws.moveCommarea(task.commarea(Object.class));
        // ADD 1 TO MN-VISITS -- PIC 9(4) without ON SIZE ERROR: 9999 + 1 keeps its low-order digits, 0000.
        ws.mnVisits = (ws.mnVisits + 1) % 10000;
        // IF EIBAID = DFHCLEAR (tested before the RECEIVE: CLEAR sends no map data)
        if ("CLEAR".equals(aid)) {
            ws.wsMsg = fit("CLEARED", 40);
            showMenu(task, ws);          // PERFORM SHOW-MENU (ends the task)
            return;
        }
        // EXEC CICS HANDLE AID PF3(MENU-EXIT) PF5(MENU-REFRESH): armed for the RECEIVE below.
        // MOVE LOW-VALUES TO PCMNI
        // EXEC CICS RECEIVE MAP('PCMN') MAPSET('PCSET2') INTO(PCMNI)
        Optional<PcmnScreen> received = task.receive(PcmnScreen.MAP, PcmnScreen.MAPSET, PcmnScreen.class);
        // HANDLE AID takes precedence over the RECEIVE's condition (MAPFAIL): control goes to the label.
        if ("PF3".equals(aid)) {
            menuExit(task);              // GO TO MENU-EXIT
            return;
        }
        if ("PF5".equals(aid)) {
            menuRefresh(task, ws);       // GO TO MENU-REFRESH (falls through into SHOW-MENU)
            return;
        }
        if (received.isEmpty()) {
            // Kept: no HANDLE CONDITION / RESP for MAPFAIL, so a PA key (or any key sending no data)
            // abends AEI9 instead of showing 'KEY NOT ACTIVE'.
            // Fix: add RESP(WS-RESP) to the RECEIVE and treat MAPFAIL like a key not active.
            task.abendOnCondition("MAPFAIL");
            return;
        }
        PcmnScreen pcmni = received.get();
        // IF EIBAID NOT = DFHENTER
        if (!"ENTER".equals(aid)) {
            ws.wsMsg = fit("KEY NOT ACTIVE", 40);
            showMenu(task, ws);          // PERFORM SHOW-MENU (ends the task)
            return;
        }
        // EVALUATE OPTI (PIC X(1); LOW-VALUE when the field was not received)
        String opti = pcmni.getOpt() == null || pcmni.getOpt().isEmpty()
                ? LOW_VALUE_1 : pcmni.getOpt().substring(0, 1);
        switch (opti) {
            case "1" -> {
                // WHEN '1': MOVE 'PC11' TO MN-LAST
                ws.mnLast = fit("PC11", 4);
                // EXEC CICS XCTL PROGRAM('PCDETL') COMMAREA(WS-CA) LENGTH(10)
                String resp = task.xctl("PCDETL", ws.toPcdetlCa(), 10);
                if (!"NORMAL".equals(resp)) {
                    // No HANDLE CONDITION / RESP: CICS's default action abends the task.
                    task.abendOnCondition(resp);
                }
                return;
            }
            case "2" -> {
                // WHEN '2': MOVE 'PC11' TO MN-LAST
                ws.mnLast = fit("PC11", 4);
                // EXEC CICS SEND TEXT FROM(WS-NEXT) LENGTH(20) ERASE
                task.sendText(WS_NEXT, 20, "ERASE");
                // EXEC CICS RETURN TRANSID('PC12') COMMAREA(WS-CA) LENGTH(10)
                // PC12 runs PCDETL (navigation fact src/PCMENU.cbl:56), which reads PcdetlWsCa.
                task.returnTransid("PC12", ws.toPcdetlCa(), 10);
                return;
            }
            default -> {
                // WHEN OTHER
                ws.wsMsg = fit("INVALID OPTION", 40);
                showMenu(task, ws);      // PERFORM SHOW-MENU (ends the task)
                return;
            }
        }
        // END-EVALUATE. -- every branch ends the task, so the fall-through into MENU-EXIT never runs.
    }

    /** MENU-EXIT. */
    private void menuExit(CicsTask task) {
        // EXEC CICS SEND TEXT FROM(WS-BYE) LENGTH(10) ERASE
        task.sendText(WS_BYE, 10, "ERASE");
        // EXEC CICS RETURN
        task.returnTransid(null, null);
    }

    /** MENU-REFRESH. -- falls through into SHOW-MENU. */
    private void menuRefresh(CicsTask task, WorkingStorage ws) {
        // MOVE 'REFRESHED' TO WS-MSG.
        ws.wsMsg = fit("REFRESHED", 40);
        showMenu(task, ws);
    }

    /** SHOW-MENU. */
    private void showMenu(CicsTask task, WorkingStorage ws) {
        // MOVE LOW-VALUES TO PCMNO / MOVE MN-VISITS TO VISITSO / MOVE WS-MSG TO MSGO
        PcmnScreen pcmno = buildPcmno(ws.mnVisits, ws.wsMsg);
        // EXEC CICS SEND MAP('PCMN') MAPSET('PCSET2') FROM(PCMNO) ERASE
        // The length / attribute subfields hold LOW-VALUES: no cursor, the map's own attributes.
        CicsTask.MapSubfields subfields = new CicsTask.MapSubfields();
        task.sendMap(PcmnScreen.MAP, PcmnScreen.MAPSET, renderPcmn(pcmno), subfields, "ERASE");
        // EXEC CICS RETURN TRANSID('PC11') COMMAREA(WS-CA) LENGTH(10)
        task.returnTransid("PC11", ws.toPcmenuCa(), 10);
    }

    /** PCMNO as SHOW-MENU fills it. */
    private static PcmnScreen buildPcmno(int mnVisits, String wsMsg) {
        PcmnScreen screen = new PcmnScreen();
        // MOVE LOW-VALUES TO PCMNO: OPTO keeps LOW-VALUES (BMS sends no data for it).
        screen.setOpt(LOW_VALUE_1);
        // MOVE MN-VISITS TO VISITSO: PIC 9(4) unsigned DISPLAY into PIC X(4) -> its 4 digits.
        screen.setVisits(String.format(Locale.ROOT, "%04d", mnVisits % 10000));
        // MOVE WS-MSG TO MSGO: X(40) to X(40).
        screen.setMsg(fit(wsMsg, 40));
        return screen;
    }

    /** EXEC CICS XCTL PROGRAM(PCDETL) at src/PCMENU.cbl:49. XCTL transfers control: nothing after it runs in the caller.
     *  Call targets field testing: open (6 public / 0 private estates). */
    public PcdetlWsCa xctlPcdetl(PcdetlWsCa request) {
        return pcdetlService.getObject().handleLink(request);
    }

    /** SEND MAP(PCMN) MAPSET(PCSET2) FROM(PCMNO) at src/PCMENU.cbl:72 (#3619): the output fields held
     *  at the length of their symbolic-map O fields (VISITSO X(4), MSGO X(40)).
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public PcmnScreen renderPcmn(PcmnScreen screen) {
        if (screen == null) {
            return null;
        }
        if (screen.getVisits() != null) {
            screen.setVisits(fit(screen.getVisits(), 4));
        }
        if (screen.getMsg() != null) {
            screen.setMsg(fit(screen.getMsg(), 40));
        }
        return screen;
    }

    /** RECEIVE MAP(PCMN) MAPSET(PCSET2) INTO(PCMNI) at src/PCMENU.cbl:40 (#3619).
     *  `aid` is the key the user pressed (EIBAID): ENTER, PF1-PF24, CLEAR, PA1-PA3.
     *  The conversation's decisions are made in runTask; this view-model hook returns the screen as sent.
     *  BMS screen fields field testing: open (3 public / 0 private estates). */
    public ScreenModel submitPcmn(PcmnScreen input, String aid) {
        return renderPcmn(input);
    }

    /** MN-VISITS from a COMMAREA DTO: PIC 9(4) unsigned keeps 4 digits and no sign. */
    private static int visits(Integer value) {
        if (value == null) {
            return 0;
        }
        return Math.abs(value % 10000);
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String fit(String value, int length) {
        String s = value == null ? "" : value;
        if (s.length() >= length) {
            return s.substring(0, length);
        }
        StringBuilder sb = new StringBuilder(length).append(s);
        while (sb.length() < length) {
            sb.append(' ');
        }
        return sb.toString();
    }
}
