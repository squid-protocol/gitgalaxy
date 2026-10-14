package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEUTC -- get Universal Time Coordinated, the same service as CEEGMT. The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceeutc {
    private Ceeutc() {
    }

    public static void call(String now, Field lilian, Field seconds, Field fc, Charset cs) {
        LeTime.gmt(now, lilian, seconds, fc, cs);
    }
}
