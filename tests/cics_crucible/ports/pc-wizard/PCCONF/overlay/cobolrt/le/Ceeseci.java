package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEESECI -- Lilian seconds to integers (input_seconds, year, month, day, hours, minutes, seconds, milliseconds, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceeseci {
    private Ceeseci() {
    }

    public static void call(Field seconds, Field y, Field mo, Field d, Field h, Field mi, Field s, Field ms, Field fc, Charset cs) {
        LeTime.seci(seconds, y, mo, d, h, mi, s, ms, fc, cs);
    }
}
