package com.ibm.jzos.fields;

/** The shim's one behaviour for byte conversion: refuse it, by name (see {@link CobolDatatypeFactory}). */
final class Unsupported {
    private Unsupported() {}

    static UnsupportedOperationException of(String what) {
        return new UnsupportedOperationException("JZOS shim: " + what + " is not modelled (the IBM WCA4Z adapter "
                + "passes values through setters, never record bytes)");
    }
}
