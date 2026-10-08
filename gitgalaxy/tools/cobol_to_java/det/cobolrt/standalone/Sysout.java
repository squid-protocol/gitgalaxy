package __PACKAGE__.cobolrt.standalone;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/**
 * DISPLAY for a project the generator gave no batch package (a CICS-only estate): the operands' texts, one line.
 * #4691: written in the record charset, not UTF-8, so a byte above X'7F' leaves as that one byte.
 */
public final class Sysout {
    private Sysout() {
    }

    public static void display(Object... operands) {
        write(join(operands) + "\n");
    }

    public static void displayNoAdvancing(Object... operands) {
        write(join(operands));
    }

    private static String join(Object... operands) {
        StringBuilder b = new StringBuilder();
        for (Object o : operands) {
            b.append(o);
        }
        return b.toString();
    }

    /** The record charset, CobolRecords.charset() when the project has it (looked up, so this class stands alone). */
    private static Charset charset() {
        try {
            return (Charset) Class.forName("__PACKAGE__.entity.vsam.CobolRecords").getMethod("charset").invoke(null);
        } catch (ReflectiveOperationException | ClassCastException e) {
            return StandardCharsets.ISO_8859_1;
        }
    }

    private static void write(String text) {
        byte[] bytes = text.getBytes(charset());
        System.out.write(bytes, 0, bytes.length);
        System.out.flush();
    }
}
