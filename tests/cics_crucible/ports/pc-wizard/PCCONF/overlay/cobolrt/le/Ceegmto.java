package com.gitgalaxy.modernized.cobolrt.le;

import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;

/** CEEGMTO / CEEUTCO -- the offset from GMT to local time (hours, minutes, seconds, fc). The det runtime's clock is GMT (CURRENT-DATE carries +0000), so the offset is zero (register L6, assumption 1); its C twin is tests/equivalence/le/le_time.c. */
public final class Ceegmto {
    private Ceegmto() {
    }

    // [rule RT-LE-CEEGMTO]
    public static void call(Field hours, Field minutes, Field seconds, Field fc, Charset cs) {
        LeTime.putInt(hours, 0);
        LeTime.putInt(minutes, 0);
        Cobol.store(seconds, BigDecimal.ZERO, false, cs);
        LeTime.putFc(fc, 0);
    }
}
