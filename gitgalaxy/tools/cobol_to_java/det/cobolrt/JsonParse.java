package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * JSON PARSE ... INTO a group (Enterprise COBOL 6.3 Language Reference, "JSON PARSE statement" and its Operation,
 * Name matching and Format conversion pages), #7524. Modelled from IBM's definition alone: the oracle (GnuCOBOL) has no
 * JSON statement to prove it against, so a port using it is oracle-unbacked (register X77).
 *
 * <p>The translator hands over the tree of the receiving group. The JSON text must be one object whose members are
 * matched by name (case-sensitive) to the group's subordinate items; a name with no target is ignored and a target with
 * no member keeps its value. A string goes to an alphanumeric item (left-justified, space padded), a number to a
 * fixed-point DISPLAY item. What IBM answers with the exception condition (JSON-CODE, ON EXCEPTION: malformed text, a
 * value that does not fit or has the wrong type) is not modelled and is a {@link Hole}, never a guess.
 */
public final class JsonParse {
    private JsonParse() {
    }

    /** One receiving item: a JSON name and what it takes (members, text or a number). */
    public abstract static class Node {
        final String name;

        Node(String name) {
            this.name = name;
        }

        abstract void accept(Object value);
    }

    /** A group: members matched by name against a JSON object. */
    public static Node group(String name, Node... members) {
        return new Group(name, List.of(members));
    }

    /** An alphanumeric / alphabetic elementary item taking a JSON string. */
    public static Node text(String name, Field f) {
        return new Text(name, f);
    }

    /** A fixed-point DISPLAY number taking a JSON number. */
    public static Node number(String name, Field f) {
        return new Num(name, f);
    }

    /** Parses the JSON text held in `src` (trailing spaces ignored) and stores its members into `root`'s items. */
    // [rule RT-CBL-JSON-PARSE]
    public static void parse(Field src, Node root, Charset cs) {
        String t = Cobol.text(src, cs);
        for (int i = 0; i < t.length(); i++) {
            if (t.charAt(i) > 0x7F) {
                throw new Hole("JSON PARSE: a character beyond ASCII (U+" + Integer.toHexString(t.charAt(i)).toUpperCase()
                        + "); the UTF-8 to code page conversion is not modelled");
            }
        }
        Reader r = new Reader(t);
        r.ws();
        Object v = r.value();
        r.ws();
        if (r.i != t.length() && !t.substring(r.i).isBlank()) {
            throw new Hole("JSON PARSE: text after the JSON value; IBM raises the exception condition (JSON-CODE), not modelled");
        }
        if (!(v instanceof Members)) {
            throw new Hole("JSON PARSE: the text is not a JSON object; IBM raises the exception condition, not modelled");
        }
        // the members of the text are the subordinates of the receiving group; the group's own name is not in the text
        ((Group) root).fill((Members) v);
    }

    /** A parsed JSON object: names in text order. */
    private static final class Members {
        final List<String> names = new ArrayList<>();
        final List<Object> values = new ArrayList<>();
    }

    private static final class Group extends Node {
        final List<Node> members;

        Group(String name, List<Node> members) {
            super(name);
            this.members = members;
        }

        void fill(Members m) {
            Set<String> seen = new HashSet<>();
            for (int i = 0; i < m.names.size(); i++) {
                if (!seen.add(m.names.get(i))) {
                    throw new Hole("JSON PARSE: the name " + m.names.get(i) + " occurs twice in one object; not modelled");
                }
            }
            for (int i = 0; i < m.names.size(); i++) {
                for (Node n : members) {
                    if (n.name.equals(m.names.get(i))) {
                        n.accept(m.values.get(i));
                    }
                }
            }
        }

        @Override
        void accept(Object value) {
            if (!(value instanceof Members)) {
                throw new Hole("JSON PARSE: " + name + " is a group but the JSON value is not an object; IBM raises the exception condition, not modelled");
            }
            fill((Members) value);
        }
    }

    private static final class Text extends Node {
        final Field f;

        Text(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void accept(Object value) {
            if (!(value instanceof String)) {
                throw new Hole("JSON PARSE: " + name + " takes a JSON string; IBM raises the exception condition for another type, not modelled");
            }
            byte[] b = ((String) value).getBytes(StandardCharsets.US_ASCII);
            if (b.length > f.length()) {
                throw new Hole("JSON PARSE: " + b.length + " characters for " + name + " of " + f.length()
                        + "; IBM raises the exception condition, not modelled");
            }
            byte[] out = new byte[f.length()];
            java.util.Arrays.fill(out, (byte) ' ');
            System.arraycopy(b, 0, out, 0, b.length);
            f.putRaw(out);
        }
    }

    private static final class Num extends Node {
        final Field f;

        Num(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void accept(Object value) {
            if (!(value instanceof BigDecimal)) {
                throw new Hole("JSON PARSE: " + name + " takes a JSON number; IBM raises the exception condition for another type, not modelled");
            }
            BigDecimal v = (BigDecimal) value;
            if (v.scale() > f.scale() && v.stripTrailingZeros().scale() > f.scale()) {
                throw new Hole("JSON PARSE: " + name + " has " + f.scale() + " decimals, the JSON number more; IBM's truncation is not modelled");
            }
            v = v.setScale(f.scale(), java.math.RoundingMode.UNNECESSARY);
            if (v.signum() < 0 && !f.isSigned()) {
                throw new Hole("JSON PARSE: a negative number for the unsigned item " + name + "; not modelled");
            }
            if (v.precision() - v.scale() > f.digits() - f.scale() && v.signum() != 0) {
                throw new Hole("JSON PARSE: the number does not fit " + name + "; IBM raises the exception condition, not modelled");
            }
            Cobol.store(f, v, false, StandardCharsets.ISO_8859_1);
        }
    }

    /** A strict JSON reader (RFC 8259 shapes the statement takes: object, string, number); the rest is a Hole. */
    private static final class Reader {
        final String s;
        int i;

        Reader(String s) {
            this.s = s;
        }

        void ws() {
            while (i < s.length() && " \t\n\r".indexOf(s.charAt(i)) >= 0) {
                i++;
            }
        }

        Hole bad(String what) {
            return new Hole("JSON PARSE: " + what + " at offset " + i + "; IBM raises the exception condition (JSON-CODE), not modelled");
        }

        Object value() {
            if (i >= s.length()) {
                throw bad("no JSON value");
            }
            char c = s.charAt(i);
            if (c == '{') {
                return object();
            }
            if (c == '"') {
                return string();
            }
            if (c == '-' || (c >= '0' && c <= '9')) {
                return number();
            }
            throw bad("a JSON array, true, false, null or malformed value (not modelled)");
        }

        Members object() {
            Members m = new Members();
            i++;
            ws();
            if (i < s.length() && s.charAt(i) == '}') {
                i++;
                return m;
            }
            while (true) {
                ws();
                if (i >= s.length() || s.charAt(i) != '"') {
                    throw bad("a member name was expected");
                }
                String n = string();
                ws();
                if (i >= s.length() || s.charAt(i) != ':') {
                    throw bad("a colon was expected");
                }
                i++;
                ws();
                m.names.add(n);
                m.values.add(value());
                ws();
                if (i < s.length() && s.charAt(i) == ',') {
                    i++;
                    continue;
                }
                if (i < s.length() && s.charAt(i) == '}') {
                    i++;
                    return m;
                }
                throw bad("a comma or closing brace was expected");
            }
        }

        String string() {
            StringBuilder b = new StringBuilder();
            i++;
            while (true) {
                if (i >= s.length()) {
                    throw bad("an unterminated string");
                }
                char c = s.charAt(i++);
                if (c == '"') {
                    return b.toString();
                }
                if (c < 0x20) {
                    throw bad("a control character in a string");
                }
                if (c != '\\') {
                    b.append(c);
                    continue;
                }
                if (i >= s.length()) {
                    throw bad("an unterminated escape");
                }
                char e = s.charAt(i++);
                switch (e) {
                    case '"', '\\', '/' -> b.append(e);
                    case 'b' -> b.append('\b');
                    case 'f' -> b.append('\f');
                    case 'n' -> b.append('\n');
                    case 'r' -> b.append('\r');
                    case 't' -> b.append('\t');
                    case 'u' -> {
                        if (i + 4 > s.length()) {
                            throw bad("a short \\u escape");
                        }
                        int cp;
                        try {
                            cp = Integer.parseInt(s.substring(i, i + 4), 16);
                        } catch (NumberFormatException ex) {
                            throw bad("a malformed \\u escape");
                        }
                        i += 4;
                        if (cp > 0x7F) {
                            throw new Hole("JSON PARSE: a character beyond ASCII (U+" + Integer.toHexString(cp).toUpperCase()
                                    + "); the UTF-8 to code page conversion is not modelled");
                        }
                        b.append((char) cp);
                    }
                    default -> throw bad("an unknown escape");
                }
            }
        }

        BigDecimal number() {
            int start = i;
            if (s.charAt(i) == '-') {
                i++;
            }
            int digits = i;
            while (i < s.length() && s.charAt(i) >= '0' && s.charAt(i) <= '9') {
                i++;
            }
            if (i == digits || (s.charAt(digits) == '0' && i - digits > 1)) {
                throw bad("a malformed number");
            }
            if (i < s.length() && s.charAt(i) == '.') {
                i++;
                int fr = i;
                while (i < s.length() && s.charAt(i) >= '0' && s.charAt(i) <= '9') {
                    i++;
                }
                if (i == fr) {
                    throw bad("a malformed number");
                }
            }
            if (i < s.length() && (s.charAt(i) == 'e' || s.charAt(i) == 'E')) {
                throw bad("an exponent (floating-point conversion is not modelled)");
            }
            return new BigDecimal(s.substring(start, i));
        }
    }
}
