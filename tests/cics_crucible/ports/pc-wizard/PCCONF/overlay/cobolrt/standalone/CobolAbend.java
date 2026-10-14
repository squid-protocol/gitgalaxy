package com.gitgalaxy.modernized.cobolrt.standalone;

/** An abend (CEE3ABD) for a project the generator gave no batch package. */
public class CobolAbend extends RuntimeException {
    private static final long serialVersionUID = 1L;
    private final String code;

    public CobolAbend(String code, String message) {
        super(code + ": " + message);
        this.code = code;
    }

    // [rule RT-SYS-USER-ABEND]
    public static CobolAbend user(int abcode, String why) {
        return new CobolAbend(String.format(java.util.Locale.ROOT, "U%04d", abcode), why);
    }

    public String code() {
        return code;
    }
}
