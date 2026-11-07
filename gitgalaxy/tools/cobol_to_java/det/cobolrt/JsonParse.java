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
 * value of the wrong type, no name matching any item) is a {@link Hole} unless the statement has ON EXCEPTION /
 * NOT ON EXCEPTION or names JSON-CODE / JSON-STATUS (the six-argument tryParse). The codes are IBM's (Programming Guide, Appendix D,
 * Table 109: 100 invalid text, 101 empty text, 102 text after the closing brace, 104 incompatible value, 106 no name
 * matched) and the JSON-STATUS bits are Table 108 (1 an item had no pair, 2 a pair had no item). A value that does not
 * fit (JSON-STATUS 128, 256: IBM stores it anyway, in a form the text does not state) is a Hole.
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

        abstract void accept(Object value, Ctx c);
    }

    /** What one statement collects: the JSON-STATUS bits and how many JSON pairs matched an item. */
    private static final class Ctx {
        int status;
        int matched;
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

    /** A fixed OCCURS table: a JSON array under the item's name, one element node per occurrence. */
    public static Node array(String name, Node... elements) {
        return new Array(name, List.of(elements));
    }

    /**
     * A table with OCCURS ... DEPENDING ON: the first `count` of the `elements` (one per occurrence up to the clause's
     * maximum). IBM: the object of the clause is not updated by JSON PARSE, and the pages do not say how many
     * occurrences a parse fills (ASSUMED: the ODO object's current value, as JSON GENERATE reads it). A count outside
     * `low` to the maximum is undefined by IBM: a {@link Hole}; so is an array of another length (the Array rule).
     */
    public static Node table(String name, int count, int low, String depending, Node... elements) {
        if (count < low || count > elements.length) {
            throw new Hole("JSON PARSE: " + depending + " holds " + count + ", outside " + low + " to " + elements.length
                    + " of the table " + name + "; IBM leaves it undefined");
        }
        return new Array(name, List.of(elements).subList(0, count));
    }

    /** A COMP-1 receiving a JSON number (a fixed-point or exponent form), converted to the item's precision. */
    public static Node floating(String name, Field f) {
        return new Floating(name, f);
    }

    /** A JSON number written with an exponent: a float receiver takes it, a fixed-point item does not (Hole). */
    private record Sci(BigDecimal value) {
    }

    /** The exception condition of IBM's definition (JSON-CODE nonzero): caught by tryParse, else a Hole. */
    private static final class JsonError extends Hole {
        /** IBM's JSON-CODE for this exception, or -1 when the Programming Guide does not state it for this shape. */
        final int code;

        JsonError(String what, int code) {
            super(what);
            this.code = code;
        }
    }

    /**
     * As parse, for a statement with ON EXCEPTION / NOT ON EXCEPTION: returns true when IBM raises the exception
     * condition (malformed text, not an object, a type mismatch, a string longer than its item, a number that does not
     * fit). Items stored before a type or size failure keep their values (assumed, X77); malformed text stores nothing.
     * What IBM leaves undefined or the model does not take stays a Hole.
     */
    // [rule RT-CBL-JSON-PARSE]
    public static boolean tryParse(Field src, Node root, Charset cs) {
        return tryParse(src, root, cs, new int[1], false, false) != 0;
    }

    /**
     * As the three-argument tryParse, returning IBM's JSON-CODE (0 after a success) and setting status[0] to JSON-STATUS. needCode: the
     * program reads JSON-CODE, so an exception whose code IBM does not state is a Hole; needStatus: the program reads
     * JSON-STATUS. IBM: after an exception it "might also contain a nonzero status value, representing one or more
     * non-exception conditions that occurred prior to the exception condition": the model stores the bits it collected
     * before the exception (a pair matching no item, a nested group that completed with an item unpaired). Malformed text
     * (100) and an unstated-code exception are a Hole under needStatus, since the model reads the whole text first and
     * cannot say which conditions IBM's left-to-right parse met before the error. Without the flags the exception is
     * still reported (return -1 for an unstated code).
     */
    // [rule RT-CBL-JSON-PARSE]
    public static int tryParse(Field src, Node root, Charset cs, int[] status, boolean needCode, boolean needStatus) {
        status[0] = 0;
        try {
            parse(src, root, cs, status);
            return 0;
        } catch (JsonError e) {
            if (needStatus && (e.code == 100 || e.code < 0)) {
                throw new Hole("JSON PARSE: JSON-STATUS after this exception is not modelled (" + e.getMessage() + ")");
            }
            if (e.code < 0 && needCode) {
                throw new Hole(e.getMessage());
            }
            return e.code;
        }
    }

    /** Parses the JSON text held in `src` (trailing spaces ignored) and stores its members into `root`'s items. */
    // [rule RT-CBL-JSON-PARSE]
    public static void parse(Field src, Node root, Charset cs) {
        parse(src, root, cs, new int[1]);
    }

    private static void parse(Field src, Node root, Charset cs, int[] status) {
        String t = Cobol.text(src, cs);
        for (int i = 0; i < t.length(); i++) {
            if (t.charAt(i) > 0x7F) {
                throw new Hole("JSON PARSE: a character beyond ASCII (U+" + Integer.toHexString(t.charAt(i)).toUpperCase()
                        + "); the UTF-8 to code page conversion is not modelled");
            }
        }
        Reader r = new Reader(t);
        r.ws();
        if (r.i >= t.length()) {
            throw new JsonError("JSON PARSE: the text is empty or only white space (JSON-CODE 101)", 101);
        }
        Object v = r.value();
        r.ws();
        if (v instanceof List) {
            throw new Hole("JSON PARSE: a top-level JSON array is not modelled; the Programming Guide states no JSON-CODE for it");
        }
        if (!(v instanceof Members)) {
            throw new JsonError("JSON PARSE: the text is not a JSON object; the Programming Guide states no JSON-CODE for it", -1);
        }
        if (r.i != t.length() && !t.substring(r.i).isBlank()) {
            throw new JsonError("JSON PARSE: text after the closing brace of the outermost object (JSON-CODE 102)", 102);
        }
        // the members of the text are the subordinates of the receiving group; the group's own name is not in the text
        Ctx c = new Ctx();
        try {
            ((Group) root).fill((Members) v, c);
            if (c.matched == 0) {
                throw new JsonError("JSON PARSE: no JSON name matched any data item (JSON-CODE 106)", 106);
            }
        } finally {
            status[0] = c.status; // the bits seen before an exception too (IBM, ON EXCEPTION)
        }
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

        void fill(Members m, Ctx c) {
            Set<String> seen = new HashSet<>();
            for (int i = 0; i < m.names.size(); i++) {
                if (!seen.add(m.names.get(i))) {
                    throw new Hole("JSON PARSE: the name " + m.names.get(i) + " occurs twice in one object; not modelled");
                }
            }
            Set<Node> hit = new HashSet<>();
            for (int i = 0; i < m.names.size(); i++) {
                boolean found = false;
                for (Node n : members) {
                    if (n.name.equals(m.names.get(i))) {
                        found = true;
                        hit.add(n);
                        c.matched++;
                        n.accept(m.values.get(i), c);
                    }
                }
                if (!found) {
                    c.status |= 2; // JSON-STATUS 2: a JSON pair matched no data item
                }
            }
            if (hit.size() < members.size()) {
                c.status |= 1; // JSON-STATUS 1: a data item had no matching pair and was not changed
            }
        }

        @Override
        void accept(Object value, Ctx c) {
            if (!(value instanceof Members)) {
                throw new JsonError("JSON PARSE: " + name + " is a group but the JSON value is not an object (JSON-CODE 104)", 104);
            }
            fill((Members) value, c);
        }
    }

    private static final class Array extends Node {
        final List<Node> elements;

        Array(String name, List<Node> elements) {
            super(name);
            this.elements = elements;
        }

        @Override
        void accept(Object value, Ctx c) {
            if (!(value instanceof List)) {
                throw new JsonError("JSON PARSE: " + name + " is a table but the JSON value is not an array (JSON-CODE 104)", 104);
            }
            List<?> a = (List<?>) value;
            if (a.size() != elements.size()) {
                // IBM's pages do not say what an array of another length does to a fixed OCCURS table
                throw new Hole("JSON PARSE: " + a.size() + " array elements for " + name + " of OCCURS " + elements.size()
                        + "; IBM does not state the result (not modelled)");
            }
            for (int k = 0; k < a.size(); k++) {
                elements.get(k).accept(a.get(k), c);
            }
        }
    }

    private static final class Text extends Node {
        final Field f;

        Text(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void accept(Object value, Ctx c) {
            if (!(value instanceof String)) {
                throw new JsonError("JSON PARSE: " + name + " takes a JSON string, the value is another type (JSON-CODE 104)", 104);
            }
            byte[] b = ((String) value).getBytes(StandardCharsets.US_ASCII);
            if (b.length > f.length()) {
                // JSON-STATUS 256: IBM stores the value anyway ("loss of information"); the stored form is not stated
                throw new Hole("JSON PARSE: " + b.length + " characters for " + name + " of " + f.length()
                        + "; IBM's assignment on a loss of information (JSON-STATUS 256) is not modelled");
            }
            byte[] out = new byte[f.length()];
            java.util.Arrays.fill(out, (byte) ' ');
            System.arraycopy(b, 0, out, 0, b.length);
            f.putRaw(out);
        }
    }

    private static final class Floating extends Node {
        final Field f;

        Floating(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void accept(Object value, Ctx c) {
            BigDecimal v;
            if (value instanceof Sci s) {
                v = s.value();
            } else if (value instanceof BigDecimal b) {
                v = b;
            } else {
                throw new JsonError("JSON PARSE: " + name + " takes a JSON number, the value is another type (JSON-CODE 104)", 104);
            }
            if (v.signum() != 0 && (v.precision() - v.scale() > 76 || v.precision() - v.scale() < -78)) {
                // JSON-STATUS 128 (loss of significance) for a value past the HFP range: the stored form is not stated
                throw new Hole("JSON PARSE: the number is outside the range of " + name + "; IBM's assignment on a SIZE ERROR (JSON-STATUS 128) is not modelled");
            }
            Cobol.store(f, v, false, StandardCharsets.ISO_8859_1);
        }
    }

    private static final class Num extends Node {
        final Field f;

        Num(String name, Field f) {
            super(name);
            this.f = f;
        }

        @Override
        void accept(Object value, Ctx c) {
            if (value instanceof Sci) {
                throw new Hole("JSON PARSE: an exponent for the fixed-point item " + name + "; not modelled");
            }
            if (!(value instanceof BigDecimal)) {
                throw new JsonError("JSON PARSE: " + name + " takes a JSON number, the value is another type (JSON-CODE 104)", 104);
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
                // JSON-STATUS 128: a SIZE ERROR; IBM stores the value anyway, in a form the text does not state
                throw new Hole("JSON PARSE: the number does not fit " + name + "; IBM's assignment on a SIZE ERROR (JSON-STATUS 128) is not modelled");
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
            return new JsonError("JSON PARSE: " + what + " at offset " + i + " (JSON-CODE 100)", 100);
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
            if (c == '[') {
                return array();
            }
            if (s.startsWith("true", i) || s.startsWith("false", i) || s.startsWith("null", i)) {
                throw new Hole("JSON PARSE: true, false or null at offset " + i + " is not modelled");
            }
            throw bad("a malformed value");
        }

        List<Object> array() {
            List<Object> a = new ArrayList<>();
            i++;
            ws();
            if (i < s.length() && s.charAt(i) == ']') {
                i++;
                return a;
            }
            while (true) {
                ws();
                a.add(value());
                ws();
                if (i < s.length() && s.charAt(i) == ',') {
                    i++;
                    continue;
                }
                if (i < s.length() && s.charAt(i) == ']') {
                    i++;
                    return a;
                }
                throw bad("a comma or closing bracket was expected");
            }
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

        Object number() {
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
                i++;
                if (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) {
                    i++;
                }
                int ex = i;
                while (i < s.length() && s.charAt(i) >= '0' && s.charAt(i) <= '9') {
                    i++;
                }
                if (i == ex || i - ex > 4) {
                    throw bad("a malformed exponent");
                }
                return new Sci(new BigDecimal(s.substring(start, i)));
            }
            return new BigDecimal(s.substring(start, i));
        }
    }
}
