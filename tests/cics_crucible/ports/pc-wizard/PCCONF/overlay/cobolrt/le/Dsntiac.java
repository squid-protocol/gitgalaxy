package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.List;

/**
 * DSNTIAC -- the CICS interface to Db2's SQLCA message formatter (DSNTIAR), as a stand-in the equivalence harness
 * shares with the COBOL side (tests/equivalence/le/dsntiac.c): the same lines, the same return codes, the same
 * refusals (oracle_assumptions.md Q5).
 *
 *   CALL 'DSNTIAC' USING DFHEIBLK, DFHCOMMAREA, SQLCA, message-area, line-length
 *
 * The message area is a halfword with the area's length, then lines of line-length bytes (IBM Db2 for z/OS
 * Application Programming and SQL Guide, paraphrased and not re-fetched). RETURN-CODE: 0 formatted; 4 more text than
 * lines (the rest dropped); 8 line length outside 72-240; 12 no whole line in the area; 24 an SQLCA that is not one.
 * The text is what is NOT documented byte for byte: Db2's message catalogue. Only the SQLCODEs in MESSAGES have
 * text here, written from the titles of IBM's DSNT messages without their message tokens; any other SQLCODE is
 * refused, never answered with invented text. The four header lines after the message (SQLSTATE, SQLERRP, SQLERRD
 * decimal and hexadecimal) follow the DSNT418I / DSNT415I / DSNT416I layout. Lines are padded with blanks, every longer
 * line is wrapped at the last blank within the line length. Nothing here is proven equal to z/OS.
 */
public final class Dsntiac {
    // "SQLCODE|text": the same table, entry for entry, as tests/equivalence/le/dsntiac.c
    private static final String[] MESSAGES = {
        "100|DSNT404I SQLCODE = 100, NOT FOUND: ROW NOT FOUND FOR FETCH, UPDATE, OR DELETE, OR THE RESULT OF A QUERY IS AN EMPTY TABLE",
        "-204|DSNT408I SQLCODE = -204, ERROR: THE NAME IS AN UNDEFINED NAME",
        "-305|DSNT408I SQLCODE = -305, ERROR: THE NULL VALUE CANNOT BE ASSIGNED TO OUTPUT HOST VARIABLE NUMBER, BECAUSE NO INDICATOR VARIABLE IS SPECIFIED",
        "-530|DSNT408I SQLCODE = -530, ERROR: THE INSERT OR UPDATE VALUE OF FOREIGN KEY IS INVALID",
        "-532|DSNT408I SQLCODE = -532, ERROR: THE RELATIONSHIP RESTRICTS THE DELETION OF ROW",
        "-803|DSNT408I SQLCODE = -803, ERROR: AN INSERTED OR UPDATED VALUE IS INVALID BECAUSE THE INDEX CONSTRAINS COLUMNS OF THE TABLE SO NO TWO ROWS CAN CONTAIN DUPLICATE VALUES IN THOSE COLUMNS",
        "-811|DSNT408I SQLCODE = -811, ERROR: THE RESULT OF AN EMBEDDED SELECT STATEMENT IS A TABLE OF MORE THAN ONE ROW",
        "-904|DSNT408I SQLCODE = -904, ERROR: UNSUCCESSFUL EXECUTION CAUSED BY AN UNAVAILABLE RESOURCE",
        "-911|DSNT408I SQLCODE = -911, ERROR: THE CURRENT UNIT OF WORK HAS BEEN ROLLED BACK DUE TO DEADLOCK OR TIMEOUT",
        "-913|DSNT408I SQLCODE = -913, ERROR: UNSUCCESSFUL EXECUTION CAUSED BY DEADLOCK OR TIMEOUT",
    };
    private static final int SQLCA_LENGTH = 136, SQLCODE = 12, SQLERRP = 88, SQLERRD = 96, SQLSTATE = 131;

    private Dsntiac() {
    }

    private static int s32(byte[] b, int o) {  // COMP-5: native, little-endian
        return (b[o] & 0xff) | ((b[o + 1] & 0xff) << 8) | ((b[o + 2] & 0xff) << 16) | ((b[o + 3] & 0xff) << 24);
    }

    private static int s16(Field f) {  // COMP: big-endian halfword
        byte[] b = f.storage().bytes;
        int o = f.offset();
        return (short) (((b[o] & 0xff) << 8) | (b[o + 1] & 0xff));
    }

    // [rule RT-LE-DSNTIAC]
    public static int call(Field eib, Field commarea, Field sqlca, Field area, Field lineLength, Charset cs) {
        if (lineLength.length() != 2 || area.length() < 2 || sqlca.length() < SQLCA_LENGTH) {
            throw new UnsupportedOperationException(
                    "DSNTIAC: an argument that is not a halfword line length, a message area or an SQLCA is not modelled");
        }
        byte[] c = sqlca.storage().bytes;
        int co = sqlca.offset();
        int width = s16(lineLength);
        if (width < 72 || width > 240) {
            return 8;
        }
        int areaLength = s16(area);
        if (areaLength - 2 < width) {
            return 12;
        }
        if (areaLength > area.length()) {
            throw new UnsupportedOperationException("DSNTIAC: a message area longer than its item is not modelled");
        }
        if (!new String(c, co, 8, cs).equals("SQLCA   ") || s32(c, co + 4) != SQLCA_LENGTH) {
            return 24;
        }
        int code = s32(c, co + SQLCODE);
        String head = null;
        for (String m : MESSAGES) {
            if (Integer.parseInt(m.substring(0, m.indexOf('|'))) == code) {
                head = m.substring(m.indexOf('|') + 1);
            }
        }
        if (head == null) {
            throw new UnsupportedOperationException(
                    "DSNTIAC: Db2's message text for SQLCODE " + code + " is not modelled (oracle_assumptions.md Q5)");
        }
        List<String> lines = new ArrayList<>();
        wrap(head, width, lines);
        wrap("DSNT418I SQLSTATE   = " + new String(c, co + SQLSTATE, 5, cs) + " SQLSTATE RETURN CODE", width, lines);
        wrap("DSNT415I SQLERRP    = " + new String(c, co + SQLERRP, 8, cs).stripTrailing()
                + " SQL PROCEDURE DETECTING ERROR", width, lines);
        StringBuilder dec = new StringBuilder("DSNT416I SQLERRD    =");
        StringBuilder hex = new StringBuilder("DSNT416I SQLERRD    =");
        for (int i = 0; i < 6; i++) {
            int v = s32(c, co + SQLERRD + 4 * i);
            dec.append(' ').append(v);
            hex.append(" X'").append(String.format(java.util.Locale.ROOT, "%08X", v)).append('\'');
        }
        wrap(dec + " SQL DIAGNOSTIC INFORMATION", width, lines);
        wrap(hex + " SQL DIAGNOSTIC INFORMATION", width, lines);
        int room = (areaLength - 2) / width;
        byte[] b = area.storage().bytes;
        int base = area.offset() + 2;
        for (int i = 0; i < room; i++) {
            byte[] t = (i < lines.size() ? lines.get(i) : "").getBytes(cs);
            byte[] pad = " ".getBytes(cs);
            for (int j = 0; j < width; j++) {
                b[base + i * width + j] = j < t.length ? t[j] : pad[0];
            }
        }
        return lines.size() > room ? 4 : 0;
    }

    /** `text` cut into lines of at most `width`, each at the last blank within it (a word longer than the line is cut). */
    private static void wrap(String text, int width, List<String> out) {
        String rest = text;
        while (rest.length() > width) {
            int cut = rest.lastIndexOf(' ', width);
            if (cut <= 0) {
                cut = width;
            }
            out.add(rest.substring(0, cut));
            rest = rest.substring(cut).stripLeading();
        }
        out.add(rest);
    }
}
