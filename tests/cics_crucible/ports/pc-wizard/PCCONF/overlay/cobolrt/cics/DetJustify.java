package com.gitgalaxy.modernized.cobolrt.cics;

import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.util.Arrays;

/** RECEIVE MAP into a field whose DFHMDF says JUSTIFY (#5082). A class of its own so that a port which has no such
 *  field does not carry it (and is not moved by it). */
public final class DetJustify {

    /** JUSTIFY=(LEFT|RIGHT[,BLANK|ZERO]) (IBM CICS TS, DFHMDF): the typed text (without its trailing blanks) placed at
     *  the left or right end of the field and the rest filled with blanks or zeros (LEFT leaves the fill after the
     *  text, RIGHT before it); <f>L is the length of the text typed, as for a field with no JUSTIFY. Text longer than
     *  the field is cut to it from the end the justification starts from. */
    // [rule RT-CICS-BMS-JUSTIFY]
    public static void place(Field input, Field len, String text, Charset cs, String justify) {
        boolean right = justify.contains("RIGHT");
        byte fill = (justify.contains("ZERO") ? "0" : " ").getBytes(cs)[0];
        String typed = text.stripTrailing();
        byte[] t = typed.getBytes(cs);
        byte[] area = new byte[input.length()];
        Arrays.fill(area, fill);
        int n = Math.min(t.length, area.length);
        if (right) {
            System.arraycopy(t, t.length - n, area, area.length - n, n);
        } else {
            System.arraycopy(t, 0, area, 0, n);
        }
        DetCics.put(input, area);
        if (len != null) {
            Cobol.store(len, BigDecimal.valueOf(typed.length()), false, cs);
        }
    }

    private DetJustify() {
    }
}
