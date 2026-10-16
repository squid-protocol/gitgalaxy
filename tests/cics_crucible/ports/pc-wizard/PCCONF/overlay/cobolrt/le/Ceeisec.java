package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEISEC -- integers to Lilian seconds (year, month, day, hours, minutes, seconds, milliseconds, output_seconds, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceeisec {
    private Ceeisec() {
    }

    public static void call(Field y, Field mo, Field d, Field h, Field mi, Field s, Field ms, Field seconds, Field fc, Charset cs) {
        LeTime.isec(y, mo, d, h, mi, s, ms, seconds, fc, cs);
    }
}
