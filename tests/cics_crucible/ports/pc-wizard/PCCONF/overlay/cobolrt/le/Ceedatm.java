package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEDATM -- Lilian seconds to character timestamp (input_seconds, picture_string, output_timestamp, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceedatm {
    private Ceedatm() {
    }

    public static void call(Field seconds, Field pic, Field out, Field fc, Charset cs) {
        LeTime.datm(seconds, pic, out, fc, cs);
    }
}
