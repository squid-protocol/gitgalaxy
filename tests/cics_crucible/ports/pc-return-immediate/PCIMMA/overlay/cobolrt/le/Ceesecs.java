package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEESECS -- character timestamp to Lilian seconds (input_timestamp, picture_string, output_seconds, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceesecs {
    private Ceesecs() {
    }

    public static void call(Field ts, Field pic, Field seconds, Field fc, Charset cs) {
        LeTime.secs(ts, pic, seconds, fc, cs);
    }
}
