package com.gitgalaxy.modernized.service;

import java.util.Locale;
import java.util.Map;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.PcdetlWsCa;
import com.gitgalaxy.modernized.dto.screen.PcdtScreen;
import org.springframework.transaction.annotation.Transactional;

/**
 * PCDETL (src/PCDETL.cbl): the detail screen of the pc-aid-menu conversation.
 * It is reached by XCTL from PCMENU (the task is still PC11) or as transaction PC12.
 * It shows the COMMAREA and EIBTRNID, then RETURNs TRANSID('PC11') with no COMMAREA,
 * so the menu starts a new session.
 * Screens (#3619): PcdtScreen.
 */
@Service
@Transactional
@RequiredArgsConstructor
public class PcdetlService {

    private static final Logger log = LoggerFactory.getLogger(PcdetlService.class);

    /** SEND MAP('PCDT') MAPSET('PCSET2') at src/PCDETL.cbl:33. */
    private static final String MAP_PCDT = "PCDT";
    private static final String MAPSET_PCSET2 = "PCSET2";

    /** RETURN TRANSID('PC11') at src/PCDETL.cbl:35. */
    private static final String TRANSID_PC11 = "PC11";

    /** 01 WS-NOCTX PIC X(28) VALUE 'NO CONTEXT - START FROM PC11' (src/PCDETL.cbl:16-17). */
    private static final String WS_NOCTX = "NO CONTEXT - START FROM PC11";
    private static final int WS_NOCTX_LENGTH = 28;

    /** The literal moved to DMSGO at src/PCDETL.cbl:32. */
    private static final String MSG_ENTER_RETURNS = "ENTER RETURNS TO THE MENU";

    /** Symbolic map PCDTO output field widths (copy/PCSET2.cpy:54-60). */
    private static final int DVISITSO_LEN = 4;
    private static final int DLASTO_LEN = 4;
    private static final int DTRANO_LEN = 4;
    private static final int DMSGO_LEN = 40;

    /**
     * PCDETL has no batch entry. It is a CICS program only: entry transaction PC12, and the XCTL target of PCMENU.
     * Its whole PROCEDURE DIVISION is ported into {@link #runTask(CicsTask)}.
     */
    public void executePcdetl(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for PCDETL");
        log.info("PCDETL is a CICS program (transaction PC12); its logic runs through runTask(CicsTask)");
    }

    /**
     * A CICS transaction entered the program. This runs one task of PCDETL on the given COMMAREA
     * (null means a first entry, EIBCALEN = 0). The program ends with RETURN TRANSID('PC11') and NO COMMAREA,
     * so the next task receives no COMMAREA and this method returns null.
     */
    public PcdetlWsCa handleTransaction(String transid, PcdetlWsCa request) {
        log.info("Pcdetl: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", request, Map.of()).withProgram("PCDETL");
        runTask(task);
        // RETURN TRANSID('PC11') passes no COMMAREA (src/PCDETL.cbl:35)
        return null;
    }

    /**
     * Another program LINKed / XCTLed to this one. PCDETL only reads its COMMAREA
     * (MOVE DFHCOMMAREA TO WS-CA, src/PCDETL.cbl:27) and never writes DFHCOMMAREA back.
     * The caller's COMMAREA is therefore returned unchanged.
     */
    public PcdetlWsCa handleLink(PcdetlWsCa request) {
        log.info("Pcdetl: handleLink");
        return request;
    }

    /** One pseudo-conversational task of this program (#3754): the PROCEDURE DIVISION of src/PCDETL.cbl. */
    public void runTask(CicsTask task) {
        log.info("Pcdetl: runTask");

        // ---- MAIN-PARA (src/PCDETL.cbl:21) ----

        // IF EIBCALEN = 0 (src/PCDETL.cbl:22)
        Integer eibcalen = task.eibcalen();
        boolean noCommarea = !task.hasCommarea() || (eibcalen != null && eibcalen.intValue() == 0);
        if (noCommarea) {
            // EXEC CICS SEND TEXT FROM(WS-NOCTX) LENGTH(28) ERASE END-EXEC (src/PCDETL.cbl:23-24)
            task.sendText(moveAlnum(WS_NOCTX, WS_NOCTX_LENGTH), WS_NOCTX_LENGTH, "ERASE");
            // EXEC CICS RETURN END-EXEC (src/PCDETL.cbl:25): the task ends here
            task.returnTransid(null, null);
            return;
        }

        // MOVE DFHCOMMAREA TO WS-CA (src/PCDETL.cbl:27): all 10 bytes, whatever EIBCALEN is.
        // DEFECT kept: nothing checks that EIBCALEN >= 10, so a shorter COMMAREA makes the MOVE read past it.
        // Fix: IF EIBCALEN < LENGTH OF WS-CA, send WS-NOCTX and RETURN.
        PcdetlWsCa wsCa = task.commarea(PcdetlWsCa.class);

        // MOVE LOW-VALUES TO PCDTO ... MOVE 'ENTER RETURNS TO THE MENU' TO DMSGO (src/PCDETL.cbl:28-32)
        PcdtScreen pcdto = buildPcdto(wsCa, task.transid());

        // EXEC CICS SEND MAP('PCDT') MAPSET('PCSET2') FROM(PCDTO) ERASE END-EXEC (src/PCDETL.cbl:33-34)
        // No attribute, colour or length subfield is set: MOVE LOW-VALUES left them X'00' (no override).
        CicsTask.MapSubfields subfields = new CicsTask.MapSubfields();
        task.sendMap(MAP_PCDT, MAPSET_PCSET2, renderPcdt(pcdto), subfields, "ERASE");

        // EXEC CICS RETURN TRANSID('PC11') END-EXEC (src/PCDETL.cbl:35): no COMMAREA
        task.returnTransid(TRANSID_PC11, null);
    }

    /**
     * SEND MAP(PCDT) MAPSET(PCSET2) FROM(PCDTO) at src/PCDETL.cbl:33 (#3619).
     * These are the output fields of PCDTO as the symbolic map holds them. Each is an alphanumeric PIC X(n),
     * so each value is fitted to its width: padded with spaces or truncated on the right (COBOL MOVE).
     * A null field stays null: it is LOW-VALUES, and the map's own content is left.
     */
    public PcdtScreen renderPcdt(PcdtScreen screen) {
        if (screen == null) {
            return null;
        }
        if (screen.getDvisits() != null) {
            screen.setDvisits(moveAlnum(screen.getDvisits(), DVISITSO_LEN));
        }
        if (screen.getDlast() != null) {
            screen.setDlast(moveAlnum(screen.getDlast(), DLASTO_LEN));
        }
        if (screen.getDtran() != null) {
            screen.setDtran(moveAlnum(screen.getDtran(), DTRANO_LEN));
        }
        if (screen.getDmsg() != null) {
            screen.setDmsg(moveAlnum(screen.getDmsg(), DMSGO_LEN));
        }
        return screen;
    }

    /** MAIN-PARA, src/PCDETL.cbl:28-32: fills PCDTO from WS-CA and EIBTRNID. */
    private PcdtScreen buildPcdto(PcdetlWsCa wsCa, String eibtrnid) {
        // MOVE LOW-VALUES TO PCDTO (src/PCDETL.cbl:28): every O field is null (low-values)
        PcdtScreen pcdto = new PcdtScreen();

        // MOVE MN-VISITS TO DVISITSO (src/PCDETL.cbl:29): PIC 9(4) DISPLAY to PIC X(4).
        // An unsigned integer DISPLAY item moves as alphanumeric, so its four digit characters move as they are.
        pcdto.setDvisits(moveAlnum(visitsDigits(wsCa == null ? null : wsCa.getMnVisits()), DVISITSO_LEN));

        // MOVE MN-LAST TO DLASTO (src/PCDETL.cbl:30): PIC X(4) to PIC X(4)
        pcdto.setDlast(moveAlnum(wsCa == null ? null : wsCa.getMnLast(), DLASTO_LEN));

        // MOVE EIBTRNID TO DTRANO (src/PCDETL.cbl:31): PC11 after the XCTL from PCMENU, PC12 when entered
        pcdto.setDtran(moveAlnum(eibtrnid, DTRANO_LEN));

        // MOVE 'ENTER RETURNS TO THE MENU' TO DMSGO (src/PCDETL.cbl:32): padded with spaces to 40
        pcdto.setDmsg(moveAlnum(MSG_ENTER_RETURNS, DMSGO_LEN));

        return pcdto;
    }

    /**
     * The four characters of MN-VISITS PIC 9(4) as its storage holds them.
     * These are the zero-filled digits of the value modulo 10000 (the field keeps four unsigned digits).
     * A null value is shown as spaces. Null means the codec could not decode the bytes as digits, e.g. spaces.
     */
    private static String visitsDigits(Integer mnVisits) {
        if (mnVisits == null) {
            return "    ";
        }
        int v = Math.abs(mnVisits.intValue() % 10000);
        return String.format(Locale.ROOT, "%04d", v);
    }

    /** MOVE to an alphanumeric PIC X(len): pad with spaces or truncate on the right; null moves as spaces. */
    private static String moveAlnum(String value, int len) {
        String s = value == null ? "" : value;
        if (s.length() >= len) {
            return s.substring(0, len);
        }
        StringBuilder sb = new StringBuilder(len);
        sb.append(s);
        while (sb.length() < len) {
            sb.append(' ');
        }
        return sb.toString();
    }
}
