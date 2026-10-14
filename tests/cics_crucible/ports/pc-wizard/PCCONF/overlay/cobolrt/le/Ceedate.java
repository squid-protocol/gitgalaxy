package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Field;
import java.nio.charset.Charset;

/** CEEDATE -- Lilian date to character (input_Lilian_date, picture_string, output_char_date, fc). The model is LeTime (register L6); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceedate {
    private Ceedate() {
    }

    public static void call(Field lilian, Field pic, Field out, Field fc, Charset cs) {
        LeTime.date(lilian, pic, out, fc, cs);
    }
}
