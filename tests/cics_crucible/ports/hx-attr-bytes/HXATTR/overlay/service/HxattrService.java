package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.HxattrWsCa;
import com.gitgalaxy.modernized.dto.screen.Hxm1Screen;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * RECEIVE at line 74 tests NORMAL
 * Screens (#3619): Hxm1Screen.
 *
 * Port of src/HXATTR.cbl (CICS transaction HX01), a pseudo-conversational program on map HXM1 of
 * mapset HXSET1:
 * first entry (EIBCALEN = 0) sends the map with attribute bytes set by several (partly wrong) routes;
 * CLEAR resends the bare map (MAPONLY); any other key receives the map and echoes it back (DATAONLY).
 */
@Service
@Transactional
@RequiredArgsConstructor
public class HxattrService {

    private static final Logger log = LoggerFactory.getLogger(HxattrService.class);

    private static final String PROGRAM = "HXATTR";
    private static final String TRANSID = "HX01";
    private static final String MAP = "HXM1";
    private static final String MAPSET = "HXSET1";

    // DFHBMSCA constants used by the program (EBCDIC byte values)
    private static final int DFHBMPRO = 0x60;   // '-' protected
    private static final int DFHBMPRF = 0x61;   // '/' protected + MDT
    private static final int DFHBMUNP = 0x40;   // ' ' unprotected
    private static final int DFHBMEOF = 0x80;   // input flag: field erased (EOF)

    // Symbolic map HXM1I / HXM1O (copy/HXSET1.cpy): the named fields in map order and their data lengths
    private static final List<String> FIELDS =
            List.of("STAT", "BRITE", "NAME", "SECRET", "RAW", "BLINKY", "TWIDDLE", "LEFTOVR", "NULATR", "FSETF");
    private static final int STAT_LEN = 12;
    private static final int BRITE_LEN = 12;
    private static final int NAME_LEN = 10;
    private static final int SECRET_LEN = 8;
    private static final int RAW_LEN = 8;
    private static final int BLINKY_LEN = 8;
    private static final int TWIDDLE_LEN = 8;
    private static final int LEFTOVR_LEN = 8;
    private static final int NULATR_LEN = 8;
    private static final int FSETF_LEN = 8;

    /** A CICS transaction entered the program with a COMMAREA and no terminal input: the task is run through
     *  runTask with ENTER, and the COMMAREA the program passes on its RETURN (null when none) is returned. */
    public HxattrWsCa handleTransaction(String transid, HxattrWsCa request) {
        log.info("Hxattr: handleTransaction");
        CicsTask task = new CicsTask(transid, "ENTER", request, Map.of());
        runTask(task);
        HxattrWsCa passed = null;
        for (Map<String, Object> e : task.events()) {
            if ("RETURN".equals(e.get("event")) && e.get("commarea") instanceof HxattrWsCa ca) {
                passed = ca;
            }
        }
        return passed;
    }

    /** One pseudo-conversational task of this program (#3754). */
    public void runTask(CicsTask task) {
        log.info("Hxattr: runTask");
        // MAIN-PARA
        if (eibcalen(task) == 0) {
            firstScreen(task);
        } else {
            if ("CLEAR".equals(task.aid())) {          // EIBAID = DFHCLEAR
                resetScreen(task);
            } else {
                echoScreen(task);
            }
        }
        if (task.ended()) {
            // FIRST-SCREEN and RESET-SCREEN end the task with their own RETURN TRANSID: the RETURN below
            // (line 38) is only reached from ECHO-SCREEN.
            return;
        }
        // EXEC CICS RETURN END-EXEC (line 38)
        // DEFECT kept: after ECHO-SCREEN the task ends with a plain RETURN (no TRANSID), so the
        // pseudo-conversation ends and the next key the operator presses does not start HX01.
        // Fix: EXEC CICS RETURN TRANSID('HX01') COMMAREA(WS-CA) LENGTH(1) at the end of ECHO-SCREEN.
        task.returnTransid(null, null);
    }

    // ------------------------------------------------------------------------------------------------
    // Paragraphs
    // ------------------------------------------------------------------------------------------------

    /** FIRST-SCREEN (lines 39-71). */
    private void firstScreen(CicsTask task) {
        Hxm1Screen hxm1o = new Hxm1Screen();
        Map<String, Integer> attrs = new LinkedHashMap<>();
        fillFirstScreen(hxm1o, attrs);
        // EXEC CICS SEND MAP('HXM1') MAPSET('HXSET1') FROM(HXM1O) ERASE
        task.sendMap(MAP, MAPSET, hxm1o, subfields(attrs), "ERASE");
        // EXEC CICS RETURN TRANSID('HX01') COMMAREA(WS-CA) LENGTH(1)
        task.returnTransid(TRANSID, newWsCa(), 1);
    }

    /** FIRST-SCREEN's moves into HXM1O (lines 40-65); `attrs` receives the A subfields. */
    private void fillFirstScreen(Hxm1Screen hxm1o, Map<String, Integer> attrs) {
        // MOVE LOW-VALUES TO HXM1O
        lowValues(hxm1o, attrs);

        // a DFHBMSCA name: protected, normal
        attrs.put("STAT", DFHBMPRO);                                   // MOVE DFHBMPRO TO STATA
        hxm1o.setStat(move("PROTECTED", STAT_LEN));                    // MOVE 'PROTECTED' TO STATO

        // a literal: protected + bright (the value of DFHPROTI)
        attrs.put("BRITE", 0xE8);                                      // MOVE X'E8' TO BRITEA
        String brite = move("IGNORED", BRITE_LEN);                     // MOVE 'IGNORED' TO BRITEO
        // MOVE LOW-VALUE TO BRITEO(1:1)
        // DEFECT kept: an output field whose first byte is X'00' is not sent by BMS, so 'IGNORED' never
        // shows and the map's INITIAL 'INITIAL-TEXT' stays. Fix: drop the MOVE LOW-VALUE TO BRITEO(1:1).
        hxm1o.setBrite('\u0000' + brite.substring(1));

        // a literal: unprotected, nondisplay, MDT on (DFHUNNOD)
        // DEFECT kept: with the MDT on, 'PASSWORD' comes back as input on every key even if untouched.
        // Fix: MOVE DFHBMDAR (X'4C', MDT off) TO SECRETA.
        attrs.put("SECRET", 0x4D);                                     // MOVE X'4D' TO SECRETA
        hxm1o.setSecret(move("PASSWORD", SECRET_LEN));                 // MOVE 'PASSWORD' TO SECRETO

        // a raw byte that is not an EBCDIC graphic
        // DEFECT kept: X'3C' is not a valid attribute byte value. Fix: move a DFHBMSCA constant.
        attrs.put("RAW", 0x3C);                                        // MOVE X'3C' TO RAWA
        hxm1o.setRaw(move("HIDDEN", RAW_LEN));                         // MOVE 'HIDDEN' TO RAWO

        // meant as "blink": F1 in the ATTRIBUTE byte is ASKIP + MDT
        // DEFECT kept: X'F1' is DFHBMASF (autoskip + MDT), not blink; BLINKY returns as input on every key.
        // Fix: MOVE DFHBMASK TO BLINKYA (blink needs extended highlighting, DSATTS=HILIGHT and DFHBLINK).
        attrs.put("BLINKY", 0xF1);                                     // MOVE X'F1' TO BLINKYA
        hxm1o.setBlinky(move("BLINK?", BLINKY_LEN));                   // MOVE 'BLINK?' TO BLINKYO

        // bit arithmetic: DFHBMUNP (X'40') plus 1 to set the MDT bit
        // WS-BITS (WS-BITS-NUM PIC S9(4) COMP VALUE 0, redefined as WS-BITS-HIGH / WS-BITS-LOW): working
        // storage is fresh in every task, so it starts at X'0000'.
        byte[] wsBits = new byte[2];
        wsBits[1] = (byte) DFHBMUNP;                                   // MOVE DFHBMUNP TO WS-BITS-LOW
        int wsBitsNum = (short) (((wsBits[0] & 0xFF) << 8) | (wsBits[1] & 0xFF));   // X'0040' = 64
        wsBitsNum = (wsBitsNum + 1) % 10000;                           // ADD 1 TO WS-BITS-NUM (PIC S9(4)): 65
        wsBits[0] = (byte) (wsBitsNum >> 8);
        wsBits[1] = (byte) wsBitsNum;                                  // X'0041'
        // DEFECT kept: X'40' + 1 = X'41', not the DFHBMSCA value X'C1' (DFHBMFSE, unprotected + MDT).
        // Fix: MOVE DFHBMFSE TO TWIDDLEA.
        attrs.put("TWIDDLE", wsBits[1] & 0xFF);                        // MOVE WS-BITS-LOW TO TWIDDLEA
        hxm1o.setTwiddle(move("TWIDDLED", TWIDDLE_LEN));               // MOVE 'TWIDDLED' TO TWIDDLEO

        // a left-over input flag (field erased) used as an attribute
        // DEFECT kept: DFHBMEOF (X'80') is an input flag, not an attribute. Fix: MOVE DFHBMUNP TO LEFTOVRA.
        attrs.put("LEFTOVR", DFHBMEOF);                                // MOVE DFHBMEOF TO LEFTOVRA

        // null attribute, program data
        hxm1o.setNulatr(move("PROGDATA", NULATR_LEN));                 // MOVE 'PROGDATA' TO NULATRO
    }

    /** ECHO-SCREEN (lines 72-85). */
    private void echoScreen(CicsTask task) {
        Hxm1Screen hxm1i = new Hxm1Screen();
        Map<String, Integer> attrs = new LinkedHashMap<>();
        // MOVE LOW-VALUES TO HXM1I, then
        // EXEC CICS RECEIVE MAP('HXM1') MAPSET('HXSET1') INTO(HXM1I) RESP(WS-RESP)
        // (the RECEIVE is issued inside fillEchoScreen, after the MOVE, as the program orders them)
        fillEchoScreen(hxm1i, attrs, null, task);
        // EXEC CICS SEND MAP('HXM1') MAPSET('HXSET1') FROM(HXM1O) DATAONLY
        task.sendMap(MAP, MAPSET, hxm1i, subfields(attrs), "DATAONLY");
    }

    private void fillEchoScreen(Hxm1Screen hxm1i, Map<String, Integer> attrs, Optional<Hxm1Screen> received) {
        fillEchoScreen(hxm1i, attrs, received, null);
    }

    /** ECHO-SCREEN's moves (lines 73-82): HXM1O redefines HXM1I, so the echo sends back what was received. */
    private void fillEchoScreen(Hxm1Screen hxm1i, Map<String, Integer> attrs, Optional<Hxm1Screen> received,
            CicsTask task) {
        // MOVE LOW-VALUES TO HXM1I
        lowValues(hxm1i, attrs);
        Optional<Hxm1Screen> in = task != null ? task.receive(MAP, MAPSET, Hxm1Screen.class) : received;
        boolean normal = in.isPresent();                               // WS-RESP = DFHRESP(NORMAL); else MAPFAIL
        if (normal) {
            receiveInto(in.get(), hxm1i);                              // INTO(HXM1I); MAPFAIL moves nothing
        }
        // MOVE DFHBMPRF TO STATA
        attrs.put("STAT", DFHBMPRF);
        if (normal) {
            hxm1i.setStat(move("RECEIVED", STAT_LEN));                 // MOVE 'RECEIVED' TO STATO
        } else {
            hxm1i.setStat(move("NO INPUT", STAT_LEN));                 // MOVE 'NO INPUT' TO STATO
        }
    }

    /** RESET-SCREEN (lines 86-91). */
    private void resetScreen(CicsTask task) {
        // EXEC CICS SEND MAP('HXM1') MAPSET('HXSET1') MAPONLY ERASE
        task.sendMap(MAP, MAPSET, null, new CicsTask.MapSubfields(), "MAPONLY", "ERASE");
        // EXEC CICS RETURN TRANSID('HX01') COMMAREA(WS-CA) LENGTH(1)
        task.returnTransid(TRANSID, newWsCa(), 1);
    }

    // ------------------------------------------------------------------------------------------------
    // Storage helpers
    // ------------------------------------------------------------------------------------------------

    /** EIBCALEN: 0 without a COMMAREA; the length passed, or the whole record (1 byte) when not given. */
    private static int eibcalen(CicsTask task) {
        if (!task.hasCommarea()) {
            return 0;
        }
        Integer len = task.eibcalen();
        return len == null ? 1 : len;
    }

    /** 01 WS-CA PIC X VALUE 'S': fresh working storage in every task. */
    private static HxattrWsCa newWsCa() {
        HxattrWsCa wsCa = new HxattrWsCa();
        wsCa.setWsCa("S");
        return wsCa;
    }

    /** MOVE LOW-VALUES to the symbolic map: every data subfield X'00', every attribute byte X'00'. */
    private static void lowValues(Hxm1Screen map, Map<String, Integer> attrs) {
        map.setStat(low(STAT_LEN));
        map.setBrite(low(BRITE_LEN));
        map.setName(low(NAME_LEN));
        map.setSecret(low(SECRET_LEN));
        map.setRaw(low(RAW_LEN));
        map.setBlinky(low(BLINKY_LEN));
        map.setTwiddle(low(TWIDDLE_LEN));
        map.setLeftovr(low(LEFTOVR_LEN));
        map.setNulatr(low(NULATR_LEN));
        map.setFsetf(low(FSETF_LEN));
        attrs.clear();
        for (String f : FIELDS) {
            attrs.put(f, 0x00);
        }
    }

    /** RECEIVE MAP INTO(HXM1I): each received field's data, padded with blanks (JUSTIFY=(LEFT,BLANK)); a field
     *  not received (null or empty) keeps its low values. */
    private static void receiveInto(Hxm1Screen from, Hxm1Screen into) {
        into.setStat(received(from.getStat(), into.getStat(), STAT_LEN));
        into.setBrite(received(from.getBrite(), into.getBrite(), BRITE_LEN));
        into.setName(received(from.getName(), into.getName(), NAME_LEN));
        into.setSecret(received(from.getSecret(), into.getSecret(), SECRET_LEN));
        into.setRaw(received(from.getRaw(), into.getRaw(), RAW_LEN));
        into.setBlinky(received(from.getBlinky(), into.getBlinky(), BLINKY_LEN));
        into.setTwiddle(received(from.getTwiddle(), into.getTwiddle(), TWIDDLE_LEN));
        into.setLeftovr(received(from.getLeftovr(), into.getLeftovr(), LEFTOVR_LEN));
        into.setNulatr(received(from.getNulatr(), into.getNulatr(), NULATR_LEN));
        into.setFsetf(received(from.getFsetf(), into.getFsetf(), FSETF_LEN));
    }

    private static String received(String value, String current, int len) {
        if (value == null || value.isEmpty()) {
            return current;
        }
        return move(value, len);
    }

    /** MOVE to PIC X(len): pad with spaces or truncate on the right. */
    private static String move(String value, int len) {
        String v = value == null ? "" : value;
        return v.length() >= len ? v.substring(0, len) : v + " ".repeat(len - v.length());
    }

    /** LOW-VALUES for PIC X(len). */
    private static String low(int len) {
        return String.valueOf(new char[len]);
    }

    /** The A subfields of HXM1O at the SEND: every attribute byte that is not X'00' (X'00' leaves the map's
     *  own attribute). No L subfield holds -1, so no cursor is asked for. */
    private static CicsTask.MapSubfields subfields(Map<String, Integer> attrs) {
        CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
        for (String f : FIELDS) {
            int a = attrs.getOrDefault(f, 0x00);
            if (a != 0x00) {
                sub.attr(f, a);
            }
        }
        return sub;
    }
}
