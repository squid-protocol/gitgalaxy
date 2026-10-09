package __PACKAGE__.cobolrt.standalone;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/**
 * DISPLAY for a project the generator gave no batch package (a CICS-only estate): the operands' texts, one line.
 * #4691: written in the record charset, not UTF-8, so a byte above X'7F' leaves as that one byte. #4698: the line
 * separator is a plain LF in every charset (a z/OS SYSOUT record has no newline byte; the capture frames records).
 */
public final class Sysout {
    private Sysout() {
    }

    public static void display(Object... operands) {
        write(join(operands), true);
    }

    public static void displayNoAdvancing(Object... operands) {
        write(join(operands), false);
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


    /** The bytes of the text in the charset, a character the charset has no byte for (the runtime's text view of a
     *  byte the charset leaves unmapped, such as U+0081 in windows-1252) as its one latin-1 byte (#4698). */
    private static byte[] encode(String text, Charset cs) {
        byte[] bytes = text.getBytes(cs);
        if (bytes.length == text.length() && !new String(bytes, cs).equals(text)) {
            for (int i = 0; i < bytes.length; i++) {
                char c = text.charAt(i);
                if (c < 256 && bytes[i] == '?' && c != '?') {
                    bytes[i] = (byte) c;
                }
            }
        }
        return bytes;
    }

    private static void write(String text, boolean endOfRecord) {
        byte[] data = encode(text, charset());
        byte[] bytes = data;
        if (endOfRecord) { // #4698: the record separator of the capture is a plain LF in every charset, not data
            bytes = java.util.Arrays.copyOf(data, data.length + 1);
            bytes[data.length] = '\n';
        }
        System.out.write(bytes, 0, bytes.length);
        System.out.flush();
    }
}
