package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEDYWK -- the day of the week of a Lilian date (input_Lilian_date, day_number, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceedywk {
    private Ceedywk() {
    }

    public static void call(Field lilian, Field out, Field fc) {
        LeTime.dywk(lilian, out, fc);
    }
}
