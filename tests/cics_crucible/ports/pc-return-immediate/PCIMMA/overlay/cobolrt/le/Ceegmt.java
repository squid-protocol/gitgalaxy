package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEGMT -- get current Greenwich Mean Time (output_Lilian, output_seconds, fc); CEEUTC is its alias. The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceegmt {
    private Ceegmt() {
    }

    public static void call(String now, Field lilian, Field seconds, Field fc, Charset cs) {
        LeTime.gmt(now, lilian, seconds, fc, cs);
    }
}
