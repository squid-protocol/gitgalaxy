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

        /** `"name":value`. */
        void render(StringBuilder out, Charset cs) {
            quote(out, name);
            out.append(':');
            value(out, cs);
        }

        /** The value alone: what an element of a table is. */
        abstract void value(StringBuilder out, Charset cs);

        /** True when SUPPRESS ... WHEN leaves this member out (its value is one of the WHEN figuratives, or, for a group, all its members are). */
        boolean skip(Charset cs) {
            return false;
        }
    }

    /** A table (OCCURS): `"name":[element,...]`, each element a value without a name (an object for a group). */
    public static Node array(String name, Node... elements) {
        return new Array(name, List.of(elements));
    }

    /**
     * A table with OCCURS ... DEPENDING ON: the first `count` of the `elements` (one per occurrence up to the clause's
     * maximum), `[]` for none. A count outside `low` to the maximum is undefined by IBM: a {@link Hole}.
     */
    public static Node table(String name, int count, int low, String depending, Node... elements) {
        if (count < low || count > elements.length) {
            throw new Hole("JSON GENERATE: " + depending + " holds " + count + ", outside " + low + " to " + elements.length
                    + " of the table " + name + "; IBM leaves it undefined");
        }
        return new Array(name, List.of(elements).subList(0, count));
    }

    /**
     * NAME OF the source IS OMITTED (IBM: an anonymous JSON object, the top-level parent name not generated): the text is
     * the root group's `{members}` alone.
     */
    public static Node anonymous(Node root) {
        return new Anonymous(root);
    }

    private static final class Anonymous extends Node {
        final Node root;

        Anonymous(Node root) {
            super(root.name);
            this.root = root;
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            root.value(out, cs);
        }
    }

    /** A group: `"name":{members}` (an object, its members in storage order). */
    public static Node group(String name, Node... members) {
        return new Group(name, List.of(members));
    }

    /** An alphanumeric / alphabetic elementary item: `"name":"text"`, trailing spaces trimmed, one space if all spaces. */
    public static Node text(String name, Field f, String... when) {
        return new Text(name, f, when);
    }

    /** A fixed-point DISPLAY number: `"name":-12.340`, leading zeros dropped, a plus sign never written. */
    public static Node number(String name, Field f, String... when) {
        return new Number(name, f, when);
    }

    /**
     * CONVERTING item TO JSON BOOLEAN USING ... (IBM 6.4): `"name":true` when the item matches the condition-name or the
     * literal, `"name":false` for every other value.
     */
    public static Node bool(String name, boolean matches) {
        return new Bool(name, matches);
    }

    private static final class Bool extends Node {
        final boolean matches;

        Bool(String name, boolean matches) {
            super(name);
            this.matches = matches;
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            out.append(matches ? "true" : "false");
        }
    }

    /**
     * CONVERTING item TO NULL USING figurative (IBM 6.4, format 2): `"name":null` when the item equals the figurative,
     * else the member as `inner` generates it. `probe` is the item as a node whose WHEN is that figurative: its
     * {@link Node#skip} is the equality test (ZERO numeric for a number, the bytes for the others).
     */
    public static Node nullIf(Node inner, Node probe) {
        return new NullIf(inner, probe);
    }

    private static final class NullIf extends Node {
        final Node inner;
        final Node probe;

        NullIf(Node inner, Node probe) {
            super(inner.name);
            this.inner = inner;
            this.probe = probe;
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            if (probe.skip(cs)) {
                out.append("null");
            } else {
                inner.value(out, cs);
            }
        }
    }

    /**
     * Writes `{root}` to `into` (the root's name is the source group's, or its NAME literal) and returns the
     * number of bytes generated (COUNT IN). `when` on an item (ZERO, SPACE, LOW-VALUE, HIGH-VALUE) is SUPPRESS ... WHEN:
     * the item is left out when its value matches, and a group whose members are all left out goes with them; the
     * root group is always written (IBM: `{"A":{}}`).
     */
    // [rule RT-CBL-JSON-GENERATE]
    public static int generate(Field into, Node root, Charset cs) {
        int n = tryGenerate(into, root, cs);
        if (n < 0) {
            throw new Hole("JSON GENERATE: the JSON is longer than the receiver of " + into.length()
                    + " bytes; IBM raises the exception condition (receiver undefined, JSON-CODE nonzero), which is "
                    + "modelled only with ON EXCEPTION / NOT ON EXCEPTION");
        }
        return n;
    }

    /**
     * As generate, for a statement with ON EXCEPTION / NOT ON EXCEPTION: returns -1 (the exception condition, the
     * receiver untouched) when the JSON is longer than the receiver.
     */
    // [rule RT-CBL-JSON-GENERATE]
    public static int tryGenerate(Field into, Node root, Charset cs) {
        StringBuilder out = new StringBuilder();
        if (root instanceof Anonymous a) {
            a.value(out, cs);
        } else {
            out.append('{');
            root.render(out, cs);
            out.append('}');
        }
        byte[] b = out.toString().getBytes(StandardCharsets.US_ASCII);
        if (b.length > into.length()) {
            return -1;
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
        void value(StringBuilder out, Charset cs) {
            out.append('{');
            boolean first = true;
            for (Node m : members) {
                if (m.skip(cs)) {
                    continue;
                }
                if (!first) {
                    out.append(',');
                }
                first = false;
                m.render(out, cs);
            }
            out.append('}');
        }

        @Override
        boolean skip(Charset cs) {
            for (Node m : members) {
                if (!m.skip(cs)) {
                    return false;
                }
            }
            return true;
        }
    }

    /**
     * Whether `raw` is entirely the figurative `w` (SPACE, LOW-VALUE, HIGH-VALUE; the byte of SPACE is the code page's).
     */
    private static boolean allBytes(byte[] raw, String w, Charset cs) {
        byte b = switch (w) {
            case "SPACE" -> " ".getBytes(cs)[0];
            case "LOW-VALUE" -> (byte) 0x00;
            default -> (byte) 0xFF;
        };
        for (byte x : raw) {
            if (x != b) {
                return false;
            }
        }
        return true;
    }

    private static final class Array extends Node {
        final List<Node> elements;

        Array(String name, List<Node> elements) {
            super(name);
            this.elements = elements;
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            out.append('[');
            for (int i = 0; i < elements.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                elements.get(i).value(out, cs);
            }
            out.append(']');
        }
    }

    private static final class Text extends Node {
        final Field f;
        final String[] when;

        Text(String name, Field f, String[] when) {
            super(name);
            this.f = f;
            this.when = when;
        }

        /** ZERO on text is an alphanumeric comparison with ZEROS: every character a `0`. */
        @Override
        boolean skip(Charset cs) {
            for (String w : when) {
                if (w.equals("ZERO") ? Cobol.text(f, cs).chars().allMatch(c -> c == '0') : allBytes(f.raw(), w, cs)) {
                    return true;
                }
            }
            return false;
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            String v = Cobol.text(f, cs);
            int end = v.length();
            while (end > 0 && v.charAt(end - 1) == ' ') {
                end--;
            }
            quote(out, end == 0 ? " " : v.substring(0, end));
        }
    }

    private static final class Number extends Node {
        final Field f;
        final String[] when;

        Number(String name, Field f, String[] when) {
            super(name);
            this.f = f;
            this.when = when;
        }

        /** ZERO is a numeric comparison (invalid data and negative zero are the Holes of {@link #read}); the others
         *  compare the bytes of a DISPLAY integer. */
        @Override
        boolean skip(Charset cs) {
            for (String w : when) {
                if (w.equals("ZERO")) {
                    if (read(cs).signum() == 0) {
                        return true;
                    }
                } else if (allBytes(f.raw(), w, cs)) {
                    return true;
                }
            }
            return false;
        }

        /** The value, or a Hole where IBM documents no result (invalid data) or the model is silent (negative zero). */
        private BigDecimal read(Charset cs) {
            byte[] raw = f.raw();
            boolean negZero;
            if (f.kind() == Field.Kind.NUMERIC_DISPLAY) {
                for (int i = 0; i < raw.length; i++) {
                    boolean digit = raw[i] >= '0' && raw[i] <= '9';
                    boolean punch = f.isSigned() && i == raw.length - 1
                            && "{ABCDEFGHI}JKLMNOPQR".indexOf((char) raw[i]) >= 0;
                    if (!digit && !punch) {
                        throw invalid();
                    }
                }
                negZero = f.isSigned() && "}JKLMNOPQR".indexOf((char) raw[raw.length - 1]) >= 0;
            } else if (f.kind() == Field.Kind.NUMERIC_PACKED) {
                // a digit nibble above 9 or a sign nibble below A is no packed decimal: IBM documents no result
                for (int i = 0; i < raw.length; i++) {
                    int hi = (raw[i] >> 4) & 0x0F;
                    int lo = raw[i] & 0x0F;
                    boolean last = i == raw.length - 1;
                    if (hi > 9 || (last ? lo < 0x0A : lo > 9)) {
                        throw invalid();
                    }
                }
                int sign = raw[raw.length - 1] & 0x0F;
                negZero = f.isSigned() && (sign == 0x0B || sign == 0x0D);
            } else if (f.kind() == Field.Kind.NUMERIC_BINARY) {
                negZero = false;
            } else if (f.kind() == Field.Kind.NUMERIC_FLOAT) {
                if (f.len != 4) {
                    throw new Hole("JSON GENERATE: " + name + " is a COMP-2; IBM's conversion picture for it is illegal");
                }
                return Hfp.read(f);
            } else {
                throw new Hole("JSON GENERATE: " + name + " is not a DISPLAY, packed or binary number");
            }
            BigDecimal v = Cobol.num(f, cs);
            if (f.kind() == Field.Kind.NUMERIC_BINARY && !f.nativeBin
                    && v.abs().compareTo(BigDecimal.TEN.pow(f.digits() - f.scale())) >= 0) {
                throw new Hole("JSON GENERATE: binary item " + name + " holds a value past its PICTURE's digits; "
                        + "IBM's text for it depends on the TRUNC option and is not modelled");
            }
            if (v.signum() == 0 && negZero) {
                throw new Hole("JSON GENERATE: a negative zero in " + name + " is not modelled");
            }
            return v;
        }

        /**
         * IBM: a COMP-1 is converted as if moved to PICTURE -9.9(8)E+99 and trimmed: `-1.50000000E+00` (a sign only when
         * negative, one digit, the point, eight digits, E, the exponent's sign, two digits). ASSUMED: the mantissa is
         * rounded half away from zero (as Hfp.display, RT-HFP-DISPLAY); zero is a Hole (IBM's trimming of "0.0..." is
         * not stated).
         */
        private String floatText(BigDecimal v) {
            if (v.signum() == 0) {
                throw new Hole("JSON GENERATE: " + name + " holds zero; IBM's trimming of the float picture is not stated");
            }
            BigDecimal r = v.abs().round(new java.math.MathContext(9, java.math.RoundingMode.HALF_UP));
            int exp = r.precision() - r.scale() - 1;
            String d = r.unscaledValue().toString();
            d = d + "0".repeat(9 - d.length());
            String e = String.valueOf(Math.abs(exp));
            return (v.signum() < 0 ? "-" : "") + d.charAt(0) + "." + d.substring(1) + "E" + (exp < 0 ? "-" : "+")
                    + (e.length() < 2 ? "0" : "") + e;
        }

        private Hole invalid() {
            return new Hole("JSON GENERATE: non-digit data in numeric item " + name
                    + "; IBM documents no result (undefined by IBM, register C11)");
        }

        @Override
        void value(StringBuilder out, Charset cs) {
            BigDecimal v = read(cs);
            if (f.kind() == Field.Kind.NUMERIC_FLOAT) {
                out.append(floatText(v));
                return;
            }
            String digits = v.abs().setScale(f.scale()).toPlainString();
            int dot = digits.indexOf('.');
            int cut = 0;
            int intEnd = dot < 0 ? digits.length() : dot;
            while (cut < intEnd - 1 && digits.charAt(cut) == '0') {
                cut++;
            }
            if (v.signum() < 0) {
                out.append('-');
            }
            out.append(digits.substring(cut));
        }
    }
}
