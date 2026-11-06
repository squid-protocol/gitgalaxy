package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * JSON GENERATE (Enterprise COBOL 6.3 Language Reference, "JSON GENERATE statement" and its Operation, Format
 * conversion, Trimming and JSON name formation pages), #7524. Modelled from IBM's definition alone: the oracle
 * (GnuCOBOL) has no JSON statement here to prove it against, so a port using it is oracle-unbacked (register X76).
 *
 * <p>The translator hands over the tree of the source group: its non-ignored elementary items (alphanumeric text or
 * fixed-point DISPLAY numbers) under their group names. The text is written to the receiver as UTF-8 bytes; only the
 * bytes generated change, the rest of the receiver keeps what it held. What IBM leaves to the exception condition
 * (the receiver too small) or leaves undefined (non-digit data in a numeric item) is a {@link Hole}, never a guess.
 */
public final class JsonGenerate {
    private JsonGenerate() {
    }

    /** One JSON member: a name and its value (a string, a number, or an object of members). */
    public abstract static class Node {
        final String name;

        Node(String name) {
            this.name = name;
        }

        abstract void render(StringBuilder out, Charset cs);
    }

    /** A group: `"name":{members}` (an object, its members in storage order). */
    public static Node group(String name, Node... members) {
        return new Group(name, List.of(members));
    }

    /** An alphanumeric / alphabetic elementary item: `"name":"text"`, trailing spaces trimmed, one space if all spaces. */
    public static Node text(String name, Field f) {
        return new Text(name, f);
    }

    /** A fixed-point DISPLAY number: `"name":-12.340`, leading zeros dropped, a plus sign never written. */
    public static Node number(String name, Field f) {
        return new Number(name, f);
    }

    /**
     * Writes `{root}` to `into` (the root's name is the source group's, or its NAME literal) and returns the
     * number of bytes generated (COUNT IN).
     */
    // [rule RT-CBL-JSON-GENERATE]
    public static int generate(Field into, Node root, Charset cs) {
        StringBuilder out = new StringBuilder("{");
        root.render(out, cs);
        out.append('}');
        byte[] b = out.toString().getBytes(StandardCharsets.US_ASCII);
        if (b.length > into.length()) {
            throw new Hole("JSON GENERATE: " + b.length + " bytes of JSON for a receiver of " + into.length()
                    + "; IBM raises the exception condition (receiver undefined, JSON-CODE nonzero), which is not modelled");
        }
        into.putRaw(b);
        return b.length;
    }

    private static void quote(StringBuilder out, String s) {
        out.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c > 0x7F) {
                throw new Hole("JSON GENERATE: a character beyond ASCII (U+" + Integer.toHexString(c).toUpperCase()
                        + "); the code page to UTF-8 conversion is not modelled");
            }
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\t' -> out.append("\\t");
                case '\n' -> out.append("\\n");
                case '\f' -> out.append("\\f");
                case '\r' -> out.append("\\r");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04X", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }

    private static final class Group extends Node {
        final List<Node> members;

        Group(String name, List<Node> members) {
            super(name);
            this.members = members;
        }

        @Override
        void render(StringBuilder out, Charset cs) {
            quote(out, name);
            out.append(":{");
            for (int i = 0; i < members.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                members.get(i).render(out, cs);
            }
            out.append('}');
        }
    }

    private static final class Text extends Node {
        final Field f;

        Text(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void render(StringBuilder out, Charset cs) {
            String v = Cobol.text(f, cs);
            int end = v.length();
            while (end > 0 && v.charAt(end - 1) == ' ') {
                end--;
            }
            quote(out, name);
            out.append(':');
            quote(out, end == 0 ? " " : v.substring(0, end));
        }
    }

    private static final class Number extends Node {
        final Field f;

        Number(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void render(StringBuilder out, Charset cs) {
            byte[] raw = f.raw();
            for (int i = 0; i < raw.length; i++) {
                boolean digit = raw[i] >= '0' && raw[i] <= '9';
                boolean punch = f.isSigned() && i == raw.length - 1 && "{ABCDEFGHI}JKLMNOPQR".indexOf((char) raw[i]) >= 0;
                if (!digit && !punch) {
                    throw new Hole("JSON GENERATE: non-digit data in numeric item " + name
                            + "; IBM documents no result (undefined by IBM, register C11)");
                }
            }
            BigDecimal v = Cobol.num(f, cs);
            if (v.signum() == 0 && f.isSigned() && "}JKLMNOPQR".indexOf((char) raw[raw.length - 1]) >= 0) {
                throw new Hole("JSON GENERATE: a negative zero in " + name + " is not modelled");
            }
            String digits = v.abs().setScale(f.scale()).toPlainString();
            int dot = digits.indexOf('.');
            int cut = 0;
            int intEnd = dot < 0 ? digits.length() : dot;
            while (cut < intEnd - 1 && digits.charAt(cut) == '0') {
                cut++;
            }
            quote(out, name);
            out.append(':');
            if (v.signum() < 0) {
                out.append('-');
            }
            out.append(digits.substring(cut));
        }
    }
}
