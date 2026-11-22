package __PACKAGE__.cobolrt.job;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * An IDCAMS step for a job case (#8880 / #8881, part of #8878 / #4890): the commands a step's SYSIN holds, run against a
 * catalog of VSAM clusters and the step's sequential datasets, ending in the step's condition code. The Java side of
 * det/idcams_model.py, which is the oracle's model of the step (GnuCOBOL has no IDCAMS); the two must agree on every
 * deck, and a command or operand the model does not cover is refused by name ({@link Refused}) with the same text.
 *
 * <p>Reference: IBM z/OS DFSMS Access Method Services Commands (SC23-6846-60): "REPRO", "DELETE", "DEFINE CLUSTER",
 * "DEFINE ALTERNATEINDEX", "DEFINE PATH", "BLDINDEX", "SET", "IF-THEN-ELSE command sequence", "Condition codes",
 * "Modal commands", "Continuing commands and comments". The model:
 * <ul>
 * <li>Each command ends with a code (0 ok, 8 a problem the command could not finish, 12 a serious error); LASTCC is
 * the code of the last command run, MAXCC the highest so far (or what SET MAXCC put), and the step ends with MAXCC.
 * A failing command does not stop the commands after it.</li>
 * <li>DELETE of a missing entry is code 8, DEFINE of a name already cataloged is code 12 and changes nothing.</li>
 * <li>REPRO copies fixed-length records; a KSDS is read, and loaded from a sequential or ESDS source, in key order.</li>
 * <li>BLDINDEX builds an alternate index; reading the base through its path gives the base's records in alternate-key
 * order, records sharing a key in the order the base holds them (key order for a KSDS, arrival order for an ESDS).</li>
 * </ul>
 * The oracle is this model, not z/OS: docs/language_status/register/F6.md lists what it assumes.
 *
 * <p>{@code main} is the test driver: {@code Idcams spec-file}, a line protocol (see {@link #main}).
 */
public final class Idcams {
    private Idcams() {
    }

    /** A command or operand the model does not cover. */
    public static final class Refused extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public Refused(String message) {
            super(message);
        }
    }

    /** A catalog entry: a cluster, an alternate index or a path. */
    public abstract static class Entry {
        public final String name;

        Entry(String name) {
            this.name = name;
        }

        abstract Entry copy();
    }

    /** A VSAM cluster: a KSDS holds its records in key order, an ESDS in arrival order. */
    public static final class Cluster extends Entry {
        public final boolean indexed;
        public final int keyLen;
        public final int keyOff;
        public final int avg;
        public final int max;
        public List<byte[]> records = new ArrayList<>();

        public Cluster(String name, boolean indexed, int keyLen, int keyOff, int avg, int max) {
            super(name);
            this.indexed = indexed;
            this.keyLen = keyLen;
            this.keyOff = keyOff;
            this.avg = avg;
            this.max = max;
        }

        byte[] key(byte[] rec) {
            return slice(rec, keyOff, keyLen);
        }

        @Override
        Entry copy() {
            Cluster c = new Cluster(name, indexed, keyLen, keyOff, avg, max);
            c.records = new ArrayList<>(records);
            return c;
        }
    }

    /** An alternate index over the cluster {@code relate}; only whether BLDINDEX has built it is state. */
    public static final class Aix extends Entry {
        public final String relate;
        public final int keyLen;
        public final int keyOff;
        public final int avg;
        public final int max;
        public final boolean unique;
        public boolean upgrade = true;
        public boolean built;

        public Aix(String name, String relate, int keyLen, int keyOff, int avg, int max, boolean unique) {
            super(name);
            this.relate = relate;
            this.keyLen = keyLen;
            this.keyOff = keyOff;
            this.avg = avg;
            this.max = max;
            this.unique = unique;
        }

        @Override
        Entry copy() {
            Aix a = new Aix(name, relate, keyLen, keyOff, avg, max, unique);
            a.upgrade = upgrade;
            a.built = built;
            return a;
        }
    }

    /** A path: reading it reads the base cluster's records in the alternate index's key order. */
    public static final class PathEntry extends Entry {
        public final String aix;
        public final boolean update;

        public PathEntry(String name, String aix, boolean update) {
            super(name);
            this.aix = aix;
            this.update = update;
        }

        @Override
        Entry copy() {
            return this;
        }
    }

    /** A sequential dataset of fixed-length records (a DD of the step). */
    public static final class Sequential {
        public final int lrecl;
        public List<byte[]> records = new ArrayList<>();
        public final String disp;

        public Sequential(int lrecl, String disp) {
            this.lrecl = lrecl;
            this.disp = disp;
        }

        Sequential copy() {
            Sequential s = new Sequential(lrecl, disp);
            s.records = new ArrayList<>(records);
            return s;
        }
    }

    /** A DD of the step that names a cluster already in the catalog when the step starts. */
    public static final class Vsam {
        public final String name;

        public Vsam(String name) {
            this.name = name;
        }
    }

    /** What a step leaves: its return code (MAXCC at its end), the catalog and its sequential DDs. */
    public static final class Result {
        public int rc;
        public int lastcc;
        public int maxcc;
        public Map<String, Entry> catalog;
        public Map<String, Sequential> datasets;
        public List<String> log;
    }

    // ---------------------------------------------------------------------------------------------- parsing
    private static final Pattern COMMENT = Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL);
    private static final Pattern TOKEN = Pattern.compile(
        "(>=|<=|\\^=|\\u00AC=|=|>|<|\\(|\\)|[^\\s()=<>^,\\u00AC]+)");
    private static final Pattern NAME = Pattern.compile(
        "[A-Z#@$][A-Z0-9#@$-]{0,7}(?:\\.[A-Z#@$][A-Z0-9#@$-]{0,7})*");
    private static final Pattern DD = Pattern.compile("[A-Z#@$][A-Z0-9#@$]{0,7}");
    private static final int MAX_SET = 16;
    private static final int BASE_PTR = 4;
    private static final int AIX_HEADER = 5;
    private static final Set<String> HANDLED = Set.of("REPRO", "DELETE", "DEFINE", "SET", "IF", "BLDINDEX");
    private static final String CATALOG_WHY = "a catalog or VSAM effect the oracle has no model of";
    private static final String CONDCODE_WHY = "condition-code logic (MAXCC / LASTCC) the oracle has no model of";
    private static final Map<String, String> REFUSED_VERB = new HashMap<>();
    private static final Map<String, String> COMPARE = new HashMap<>();
    private static final Map<String, String> ALLOC = new HashMap<>();
    private static final Map<String, String> REPRO_KEY = new HashMap<>();
    private static final Map<String, Map<String, String[]>> FLAGS = new HashMap<>();
    private static final Map<String, Set<String>> VALUED = new HashMap<>();

    static {
        for (String v : new String[] {"ALTER", "BLDINDEX", "DEFINE", "DELETE", "EXPORT", "IMPORT", "LISTCAT", "LISTCRA",
            "EXAMINE", "DIAGNOSE", "VERIFY", "EXPORTRA", "IMPORTRA", "RESETCAT", "PARAM", "SHCDS", "DCOLLECT",
            "CREATE"}) {
            REFUSED_VERB.put(v, CATALOG_WHY);
        }
        REFUSED_VERB.put("PRINT", "a dump listing, not a data set the oracle compares");
        for (String v : new String[] {"SET", "IF", "THEN", "ELSE", "DO", "END", "CANCEL"}) {
            REFUSED_VERB.put(v, CONDCODE_WHY);
        }
        String[][] cmp = {{"=", "="}, {"EQ", "="}, {"^=", "!"}, {"NE", "!"}, {">", ">"}, {"GT", ">"}, {">=", "G"},
            {"GE", "G"}, {"<", "<"}, {"LT", "<"}, {"<=", "L"}, {"LE", "L"}, {"\u00AC=", "!"}};
        for (String[] c : cmp) {
            COMPARE.put(c[0], c[1]);
        }
        String[][] alloc = {{"VOLUMES", "VOLUMES"}, {"VOL", "VOLUMES"}, {"CYLINDERS", "CYLINDERS"},
            {"CYL", "CYLINDERS"}, {"TRACKS", "TRACKS"}, {"TRK", "TRACKS"}, {"RECORDS", "RECORDS"}, {"REC", "RECORDS"},
            {"MEGABYTES", "MEGABYTES"}, {"MB", "MEGABYTES"}, {"KILOBYTES", "KILOBYTES"}, {"KB", "KILOBYTES"},
            {"SHAREOPTIONS", "SHAREOPTIONS"}, {"SHR", "SHAREOPTIONS"}, {"FREESPACE", "FREESPACE"},
            {"FSPC", "FREESPACE"}, {"SPEED", "SPEED"}, {"RECOVERY", "RECOVERY"}, {"UNIQUE", "UNIQUE"},
            {"UNQ", "UNIQUE"}, {"SUBALLOCATION", "SUBALLOCATION"}, {"SUB", "SUBALLOCATION"}, {"ERASE", "ERASE"},
            {"NOERASE", "NOERASE"}};
        for (String[] a : alloc) {
            ALLOC.put(a[0], a[1]);
        }
        String[][] repro = {{"INFILE", "INFILE"}, {"IFILE", "INFILE"}, {"OUTFILE", "OUTFILE"}, {"OFILE", "OUTFILE"},
            {"INDATASET", "INDATASET"}, {"IDS", "INDATASET"}, {"OUTDATASET", "OUTDATASET"}, {"ODS", "OUTDATASET"}};
        for (String[] r : repro) {
            REPRO_KEY.put(r[0], r[1]);
        }
        String org = "organisation";
        String uniq = "key uniqueness";
        Map<String, String[]> cluster = new HashMap<>();
        cluster.put("INDEXED", new String[] {org, "INDEXED"});
        cluster.put("IXD", new String[] {org, "INDEXED"});
        cluster.put("NONINDEXED", new String[] {org, "NONINDEXED"});
        cluster.put("NIXD", new String[] {org, "NONINDEXED"});
        Map<String, String[]> aix = new HashMap<>();
        aix.put("UNIQUEKEY", new String[] {uniq, "UNIQUEKEY"});
        aix.put("UNQK", new String[] {uniq, "UNIQUEKEY"});
        aix.put("NONUNIQUEKEY", new String[] {uniq, "NONUNIQUEKEY"});
        aix.put("NUNQK", new String[] {uniq, "NONUNIQUEKEY"});
        aix.put("UPGRADE", new String[] {"upgrade", "UPGRADE"});
        aix.put("UPG", new String[] {"upgrade", "UPGRADE"});
        aix.put("NOUPGRADE", new String[] {"upgrade", "NOUPGRADE"});
        aix.put("NUPG", new String[] {"upgrade", "NOUPGRADE"});
        Map<String, String[]> path = new HashMap<>();
        path.put("UPDATE", new String[] {"update", "UPDATE"});
        path.put("UPD", new String[] {"update", "UPDATE"});
        path.put("NOUPDATE", new String[] {"update", "NOUPDATE"});
        path.put("NUPD", new String[] {"update", "NOUPDATE"});
        FLAGS.put("CLUSTER", cluster);
        FLAGS.put("ALTERNATEINDEX", aix);
        FLAGS.put("PATH", path);
        VALUED.put("CLUSTER", Set.of("NAME", "KEYS", "RECORDSIZE"));
        VALUED.put("ALTERNATEINDEX", Set.of("NAME", "RELATE", "KEYS", "RECORDSIZE"));
        VALUED.put("PATH", Set.of("NAME", "PATHENTRY"));
    }

    private static final class Op {
        final String name;
        List<Op> args;

        Op(String name) {
            this.name = name;
        }
    }

    private interface Stmt {
    }

    private record Cmd(String verb, List<Op> ops) implements Stmt {
    }

    private record SetMax(int value) implements Stmt {
    }

    private record If(String var, String cmp, long num, List<Stmt> then, List<Stmt> els) implements Stmt {
    }

    /** Each command of {@code sysin}, comments dropped and continuation lines joined (det/idcams.py _commands). */
    static List<String> commands(String sysin) {
        String text = COMMENT.matcher(sysin).replaceAll(" ");
        if (text.contains("/*") || text.contains("*/")) {
            throw new Refused("an unterminated comment");
        }
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        for (String raw : text.split("\r\n|\r|\n", -1)) {
            String line = (raw.length() > 72 ? raw.substring(0, 72) : raw).strip();
            if (line.isEmpty()) {
                continue;
            }
            char last = line.charAt(line.length() - 1);
            if (last == '-' || last == '+') {
                cur.append(line, 0, line.length() - 1).append(' ');
                continue;
            }
            out.add((cur + line).strip());
            cur.setLength(0);
        }
        if (!cur.toString().strip().isEmpty()) {
            out.add(cur.toString().strip());
        }
        return out;
    }

    private static List<String> toks(String line) {
        if (line.indexOf('\'') >= 0 || line.indexOf('"') >= 0) {
            throw new Refused("an IDCAMS quoted string");
        }
        List<String> out = new ArrayList<>();
        Matcher m = TOKEN.matcher(line);
        while (m.find()) {
            out.add(m.group());
        }
        return out;
    }

    private static String up(String s) {
        return s.toUpperCase(Locale.ROOT);
    }

    private static List<String> upAll(List<String> l) {
        List<String> out = new ArrayList<>();
        for (String s : l) {
            out.add(up(s));
        }
        return out;
    }

    /** Operands from {@code pos}; returns the list and the next position through {@code next[0]}. */
    private static List<Op> ops(List<String> toks, int pos, boolean nested, int[] next) {
        List<Op> out = new ArrayList<>();
        while (pos < toks.size()) {
            String t = toks.get(pos);
            if (t.equals(")")) {
                if (!nested) {
                    throw new Refused("an unbalanced ) in an IDCAMS command");
                }
                next[0] = pos + 1;
                return out;
            }
            if (t.equals("(")) {
                if (out.isEmpty() || out.get(out.size() - 1).args != null) {
                    throw new Refused("an IDCAMS ( with no keyword before it");
                }
                out.get(out.size() - 1).args = ops(toks, pos + 1, true, next);
                pos = next[0];
                continue;
            }
            out.add(new Op(up(t)));
            pos++;
        }
        if (nested) {
            throw new Refused("an unbalanced ( in an IDCAMS command");
        }
        next[0] = pos;
        return out;
    }

    private static long num(String text, String what) {
        if (text.isEmpty() || !text.chars().allMatch(c -> c >= '0' && c <= '9')) {
            throw new Refused(what + " value (" + head(text, 20) + ") is not a number");
        }
        try {
            return Long.parseLong(text);
        } catch (NumberFormatException e) {
            return Long.MAX_VALUE;
        }
    }

    private static String head(String s, int n) {
        return s.length() > n ? s.substring(0, n) : s;
    }

    /** One statement from line {@code i}; the next line index through {@code next[0]}. */
    private static Stmt parseOne(List<String> lines, int i, int[] next) {
        List<String> toks = toks(lines.get(i));
        String verb = up(toks.get(0));
        if (verb.equals("IF")) {
            return parseIf(lines, i, toks, next);
        }
        if (verb.equals("END") || verb.equals("ELSE") || verb.equals("THEN") || verb.equals("DO")) {
            throw new Refused("the IDCAMS " + verb + " with no IF-THEN before it");
        }
        if (verb.equals("SET")) {
            if (toks.size() != 4 || !toks.get(2).equals("=")) {
                throw new Refused("an IDCAMS SET that is not 'SET MAXCC = n'");
            }
            if (!up(toks.get(1)).equals("MAXCC")) {
                throw new Refused("the IDCAMS SET " + up(toks.get(1)) + " (only SET MAXCC is modelled)");
            }
            long value = num(toks.get(3), "the IDCAMS SET");
            if (value > MAX_SET) {
                throw new Refused("the IDCAMS SET value " + value + " (the model covers 0 to " + MAX_SET + ")");
            }
            next[0] = i + 1;
            return new SetMax((int) value);
        }
        if (!HANDLED.contains(verb)) {
            throw new Refused("the IDCAMS " + verb + " command ("
                + REFUSED_VERB.getOrDefault(verb, "a command the oracle has no model of") + ")");
        }
        List<Op> ops = ops(toks, 1, false, next);
        next[0] = i + 1;
        return new Cmd(verb, ops);
    }

    private static List<Stmt> parseBody(List<String> lines, int i, int[] next) {
        if (i >= lines.size()) {
            throw new Refused("an IDCAMS THEN / ELSE with no command after it");
        }
        if (upAll(toks(lines.get(i))).equals(List.of("DO"))) {
            List<Stmt> body = new ArrayList<>();
            i++;
            while (true) {
                if (i >= lines.size()) {
                    throw new Refused("an IDCAMS DO with no END");
                }
                if (upAll(toks(lines.get(i))).equals(List.of("END"))) {
                    next[0] = i + 1;
                    return body;
                }
                body.add(parseOne(lines, i, next));
                i = next[0];
            }
        }
        Stmt stmt = parseOne(lines, i, next);
        return new ArrayList<>(List.of(stmt));
    }

    private static Stmt parseIf(List<String> linesIn, int i, List<String> toks, int[] next) {
        List<String> up = upAll(toks);
        if (!up.contains("THEN")) {
            throw new Refused("an IDCAMS IF with no THEN");
        }
        int t = up.indexOf("THEN");
        List<String> cond = up.subList(1, t);
        if (cond.size() != 3 || !(cond.get(0).equals("LASTCC") || cond.get(0).equals("MAXCC"))
            || !COMPARE.containsKey(cond.get(1))) {
            throw new Refused("an IDCAMS IF condition that is not 'LASTCC|MAXCC op number'");
        }
        long n = num(cond.get(2), "the IDCAMS IF");
        List<String> lines = new ArrayList<>(linesIn);
        String rest = String.join(" ", toks.subList(t + 1, toks.size()));
        int j;
        if (!rest.isEmpty()) {
            lines.set(i, rest);
            j = i;
        } else {
            j = i + 1;
        }
        List<Stmt> then = parseBody(lines, j, next);
        j = next[0];
        List<Stmt> els = new ArrayList<>();
        if (j < lines.size()) {
            List<String> nxt = toks(lines.get(j));
            if (!nxt.isEmpty() && up(nxt.get(0)).equals("ELSE")) {
                String tail = String.join(" ", nxt.subList(1, nxt.size()));
                if (!tail.isEmpty()) {
                    lines.set(j, tail);
                }
                els = parseBody(lines, tail.isEmpty() ? j + 1 : j, next);
                j = next[0];
            }
        }
        next[0] = j;
        return new If(cond.get(0), COMPARE.get(cond.get(1)), n, then, els);
    }

    private static List<Stmt> parse(String sysin) {
        List<String> lines = commands(sysin);
        if (lines.isEmpty()) {
            throw new Refused("no IDCAMS command");
        }
        List<Stmt> out = new ArrayList<>();
        int[] next = {0};
        int i = 0;
        while (i < lines.size()) {
            out.add(parseOne(lines, i, next));
            i = next[0];
        }
        return out;
    }

    // ---------------------------------------------------------------------------------------------- bytes
    private static byte[] slice(byte[] rec, int off, int len) {
        int from = Math.min(off, rec.length);
        int to = Math.min(off + len, rec.length);
        return Arrays.copyOfRange(rec, from, to);
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xFF));
        }
        return sb.toString();
    }

    private static int cmpKey(byte[] a, byte[] b) {
        return Arrays.compareUnsigned(a, b);
    }

    // ---------------------------------------------------------------------------------------------- the step
    private static final class Step {
        final Map<String, Entry> catalog = new LinkedHashMap<>();
        final Map<String, Sequential> seqs = new LinkedHashMap<>();
        final Map<String, Entry> vsam = new LinkedHashMap<>();
        int lastcc;
        int maxcc;
        final List<String> log = new ArrayList<>();

        Step(Map<String, Entry> cat, Map<String, Object> dds) {
            for (Map.Entry<String, Entry> e : cat.entrySet()) {
                catalog.put(e.getKey(), e.getValue().copy());
            }
            for (Map.Entry<String, Object> e : dds.entrySet()) {
                if (e.getValue() instanceof Vsam v) {
                    if (!catalog.containsKey(v.name)) {
                        throw new Refused("DD " + e.getKey() + " names cluster " + v.name
                            + ", which is not in the catalog (a JCL allocation error)");
                    }
                    vsam.put(e.getKey(), catalog.get(v.name));
                } else {
                    Sequential d = (Sequential) e.getValue();
                    for (byte[] r : d.records) {
                        if (r.length != d.lrecl) {
                            throw new IllegalArgumentException("DD " + e.getKey() + ": a record is not " + d.lrecl
                                + " bytes");
                        }
                    }
                    seqs.put(e.getKey(), d.copy());
                }
            }
        }

        void end(int cc, String note) {
            lastcc = cc;
            maxcc = Math.max(maxcc, cc);
            log.add(note + ": condition code " + cc);
        }

        void run(List<Stmt> stmts) {
            for (Stmt s : stmts) {
                if (s instanceof SetMax m) {
                    maxcc = m.value();
                    log.add("SET MAXCC = " + m.value());
                } else if (s instanceof If f) {
                    long have = f.var().equals("LASTCC") ? lastcc : maxcc;
                    boolean hit = switch (f.cmp()) {
                        case "=" -> have == f.num();
                        case "!" -> have != f.num();
                        case ">" -> have > f.num();
                        case "G" -> have >= f.num();
                        case "<" -> have < f.num();
                        default -> have <= f.num();
                    };
                    run(hit ? f.then() : f.els());
                } else if (s instanceof Cmd c) {
                    switch (c.verb()) {
                        case "DELETE" -> delete(c.ops());
                        case "DEFINE" -> define(c.ops());
                        case "REPRO" -> repro(c.ops());
                        default -> bldindex(c.ops());
                    }
                }
            }
        }

        private boolean plainDeleteWord(String n) {
            return n.equals("CLUSTER") || n.equals("PURGE") || n.equals("NOPURGE") || n.equals("ERASE")
                || n.equals("NOERASE");
        }

        void delete(List<Op> ops) {
            if (ops.isEmpty() || ops.get(0).args != null || plainDeleteWord(ops.get(0).name)) {
                throw new Refused("the IDCAMS DELETE without one entry name (an entry list is not modelled)");
            }
            String name = entry(ops.get(0).name, "DELETE");
            for (Op op : ops.subList(1, ops.size())) {
                if (!plainDeleteWord(op.name) || op.args != null) {
                    throw new Refused("the IDCAMS DELETE " + op.name + " parameter");
                }
            }
            Entry ent = catalog.get(name);
            if (ent != null && !(ent instanceof Cluster)) {
                throw new Refused("the IDCAMS DELETE of " + name
                    + ", an alternate index or path (its dependents are not modelled)");
            }
            if (ent != null && hasAix(name)) {
                throw new Refused("the IDCAMS DELETE of " + name + ", a cluster with an alternate index related to it");
            }
            if (catalog.remove(name) == null) {
                end(8, "DELETE " + name + ": entry not found");
            } else {
                end(0, "DELETE " + name);
            }
        }

        private boolean hasAix(String base) {
            for (Entry e : catalog.values()) {
                if (e instanceof Aix a && a.relate.equals(base)) {
                    return true;
                }
            }
            return false;
        }

        private List<String> components(List<Op> ops, String kind) {
            List<String> names = new ArrayList<>();
            Set<String> seen = new HashSet<>();
            for (Op op : ops) {
                if (kind.equals("PATH") || !(op.name.equals("DATA") || op.name.equals("INDEX"))) {
                    throw new Refused("the IDCAMS DEFINE " + kind + " operand " + op.name + " outside " + kind
                        + "(...) (only DATA / INDEX with NAME(...) is modelled)");
                }
                if (!seen.add(op.name)) {
                    throw new Refused("the IDCAMS DEFINE " + kind + " " + op.name + " component stated twice");
                }
                List<Op> inner = op.args == null ? List.of() : op.args;
                if (inner.size() != 1 || !inner.get(0).name.equals("NAME") || inner.get(0).args == null
                    || inner.get(0).args.size() != 1) {
                    throw new Refused("the IDCAMS DEFINE " + kind + " " + op.name
                        + " component operand (only NAME(one name) is modelled)");
                }
                names.add(entry(inner.get(0).args.get(0).name, "DEFINE " + kind + " " + op.name + " NAME"));
            }
            return names;
        }

        private void scan(String kind, List<Op> args, Map<String, List<Op>> got, Map<String, String> flags) {
            for (Op op : args) {
                String key = ALLOC.getOrDefault(op.name, op.name);
                if (key.equals("RECSZ")) {
                    key = "RECORDSIZE";
                }
                String[] flag = FLAGS.get(kind).get(key);
                if (flag != null) {
                    if (flags.containsKey(flag[0]) || op.args != null) {
                        throw new Refused("the IDCAMS DEFINE " + kind + " " + flag[0] + " stated twice, or with a value");
                    }
                    flags.put(flag[0], flag[1]);
                } else if (VALUED.get(kind).contains(key) && op.args != null) {
                    if (got.containsKey(key)) {
                        throw new Refused("the IDCAMS DEFINE " + kind + " " + key + " parameter twice");
                    }
                    got.put(key, op.args);
                } else if (!kind.equals("PATH") && ALLOC.containsValue(key)) {
                    continue;
                } else {
                    throw new Refused("the IDCAMS DEFINE " + kind + " " + op.name + " parameter");
                }
            }
            if (!got.containsKey("NAME") || got.get("NAME").size() != 1) {
                throw new Refused("the IDCAMS DEFINE " + kind + " without a single NAME");
            }
        }

        void define(List<Op> ops) {
            String kind = ops.isEmpty() ? "" : (ops.get(0).name.equals("AIX") ? "ALTERNATEINDEX" : ops.get(0).name);
            if (!VALUED.containsKey(kind)) {
                throw new Refused("the IDCAMS DEFINE " + (ops.isEmpty() ? "(nothing)" : ops.get(0).name)
                    + " (only DEFINE CLUSTER, ALTERNATEINDEX and PATH are modelled)");
            }
            List<String> comps = components(ops.subList(1, ops.size()), kind);
            Map<String, List<Op>> got = new HashMap<>();
            Map<String, String> flags = new HashMap<>();
            scan(kind, ops.get(0).args == null ? List.of() : ops.get(0).args, got, flags);
            String name = entry(got.get("NAME").get(0).name, "DEFINE " + kind + " NAME");
            if (kind.equals("PATH")) {
                definePath(name, got, flags);
                return;
            }
            if (!got.containsKey("RECORDSIZE")) {
                throw new Refused("the IDCAMS DEFINE " + kind + " without RECORDSIZE (the default is not modelled)");
            }
            int[] rs = pair(got.get("RECORDSIZE"), "RECORDSIZE");
            int avg = rs[0];
            int mx = rs[1];
            if (!(0 < avg && avg <= mx)) {
                throw new Refused("the IDCAMS DEFINE " + kind + " RECORDSIZE(" + avg + " " + mx
                    + "): the model needs 0 < average <= maximum");
            }
            if (kind.equals("ALTERNATEINDEX")) {
                defineAix(name, got, flags, avg, mx, comps);
                return;
            }
            boolean indexed = flags.getOrDefault("organisation", "INDEXED").equals("INDEXED");
            int keyLen = 0;
            int keyOff = 0;
            if (indexed) {
                if (!got.containsKey("KEYS")) {
                    throw new Refused("the IDCAMS DEFINE CLUSTER INDEXED without KEYS (the default is not modelled)");
                }
                int[] k = pair(got.get("KEYS"), "KEYS");
                keyLen = k[0];
                keyOff = k[1];
                if (keyLen < 1 || keyOff + keyLen > avg) {
                    throw new Refused("the IDCAMS DEFINE CLUSTER KEYS(" + keyLen + " " + keyOff
                        + ") is not inside the shortest record (" + avg + ")");
                }
            } else if (got.containsKey("KEYS")) {
                throw new Refused("the IDCAMS DEFINE CLUSTER NONINDEXED with KEYS");
            }
            if (catalog.containsKey(name)) {
                end(12, "DEFINE CLUSTER " + name + ": duplicate data set name");
                return;
            }
            componentsFree(name, comps);
            catalog.put(name, new Cluster(name, indexed, keyLen, keyOff, avg, mx));
            end(0, "DEFINE CLUSTER " + name);
        }

        private void componentsFree(String name, List<String> comps) {
            boolean taken = new HashSet<>(comps).size() != comps.size() || comps.contains(name);
            for (String c : comps) {
                taken |= catalog.containsKey(c);
            }
            if (taken) {
                throw new Refused("the IDCAMS DEFINE " + name
                    + " component name is already an entry (its code is not stated)");
            }
        }

        private void defineAix(String name, Map<String, List<Op>> got, Map<String, String> flags, int avg, int mx,
                List<String> comps) {
            if (!got.containsKey("RELATE") || got.get("RELATE").size() != 1 || got.get("RELATE").get(0).args != null) {
                throw new Refused("the IDCAMS DEFINE ALTERNATEINDEX without a single RELATE");
            }
            String relate = entry(got.get("RELATE").get(0).name, "DEFINE ALTERNATEINDEX RELATE");
            if (!got.containsKey("KEYS")) {
                throw new Refused("the IDCAMS DEFINE ALTERNATEINDEX without KEYS (the default is not modelled)");
            }
            int[] k = pair(got.get("KEYS"), "KEYS");
            if ("NOUPGRADE".equals(flags.get("upgrade"))) {
                throw new Refused(
                    "the IDCAMS DEFINE ALTERNATEINDEX NOUPGRADE (an alternate index left stale by the base)");
            }
            if (catalog.containsKey(name)) {
                end(12, "DEFINE ALTERNATEINDEX " + name + ": duplicate data set name");
                return;
            }
            Entry base = catalog.get(relate);
            if (base == null) {
                throw new Refused("the IDCAMS DEFINE ALTERNATEINDEX RELATE(" + relate
                    + ") is not in the catalog (its code is not stated)");
            }
            if (!(base instanceof Cluster b)) {
                throw new Refused("the IDCAMS DEFINE ALTERNATEINDEX RELATE(" + relate + ") is not a cluster");
            }
            if (k[0] < 1 || k[1] + k[0] > b.avg) {
                throw new Refused("the IDCAMS DEFINE ALTERNATEINDEX KEYS(" + k[0] + " " + k[1]
                    + ") is not inside the base's shortest record (" + b.avg + ")");
            }
            componentsFree(name, comps);
            boolean unique = flags.getOrDefault("key uniqueness", "NONUNIQUEKEY").equals("UNIQUEKEY");
            catalog.put(name, new Aix(name, relate, k[0], k[1], avg, mx, unique));
            end(0, "DEFINE ALTERNATEINDEX " + name);
        }

        private void definePath(String name, Map<String, List<Op>> got, Map<String, String> flags) {
            if (!got.containsKey("PATHENTRY") || got.get("PATHENTRY").size() != 1
                || got.get("PATHENTRY").get(0).args != null) {
                throw new Refused("the IDCAMS DEFINE PATH without a single PATHENTRY");
            }
            String entry = entry(got.get("PATHENTRY").get(0).name, "DEFINE PATH PATHENTRY");
            if (catalog.containsKey(name)) {
                end(12, "DEFINE PATH " + name + ": duplicate data set name");
                return;
            }
            Entry target = catalog.get(entry);
            if (target == null) {
                throw new Refused("the IDCAMS DEFINE PATH PATHENTRY(" + entry
                    + ") is not in the catalog (its code is not stated)");
            }
            if (!(target instanceof Aix)) {
                throw new Refused("the IDCAMS DEFINE PATH PATHENTRY(" + entry
                    + ") is not an alternate index (a path over a cluster or another path is not modelled)");
            }
            catalog.put(name, new PathEntry(name, entry, flags.getOrDefault("update", "UPDATE").equals("UPDATE")));
            end(0, "DEFINE PATH " + name);
        }

        void bldindex(List<Op> ops) {
            Map<String, String> ends = new HashMap<>();
            for (Op op : ops) {
                String key = REPRO_KEY.get(op.name);
                if (key == null || op.args == null) {
                    throw new Refused("the IDCAMS BLDINDEX " + op.name + " parameter");
                }
                if (!key.endsWith("DATASET")) {
                    throw new Refused("the IDCAMS BLDINDEX " + key + " (the DD form is not modelled; name the data sets)");
                }
                if (ends.containsKey(key)) {
                    throw new Refused("the IDCAMS BLDINDEX names its " + key + " twice");
                }
                if (op.args.size() != 1 || op.args.get(0).args != null) {
                    throw new Refused("the IDCAMS BLDINDEX " + key + " value (one name, no password)");
                }
                ends.put(key, entry(op.args.get(0).name, "BLDINDEX " + key));
            }
            if (ends.size() != 2) {
                throw new Refused("the IDCAMS BLDINDEX without both INDATASET and OUTDATASET");
            }
            Entry b = catalog.get(ends.get("INDATASET"));
            Entry a = catalog.get(ends.get("OUTDATASET"));
            if (!(b instanceof Cluster base)) {
                throw new Refused("the IDCAMS BLDINDEX INDATASET(" + ends.get("INDATASET")
                    + ") is not a cluster in the catalog");
            }
            if (!(a instanceof Aix aix)) {
                throw new Refused("the IDCAMS BLDINDEX OUTDATASET(" + ends.get("OUTDATASET")
                    + ") is not an alternate index in the catalog");
            }
            if (!aix.relate.equals(base.name)) {
                throw new Refused("the IDCAMS BLDINDEX of " + aix.name + " from " + base.name
                    + ", which it is not related to");
            }
            if (aix.built) {
                throw new Refused("the IDCAMS BLDINDEX of " + aix.name
                    + ", which is already built (its code is not stated)");
            }
            if (base.records.isEmpty()) {
                throw new Refused("the IDCAMS BLDINDEX of an empty base cluster (its condition code is not modelled)");
            }
            int pointer = base.indexed ? base.keyLen : BASE_PTR;
            Map<String, Integer> groups = new HashMap<>();
            int busiest = 0;
            for (byte[] r : base.records) {
                int n = groups.merge(hex(slice(r, aix.keyOff, aix.keyLen)), 1, Integer::sum);
                busiest = Math.max(busiest, n);
            }
            if (aix.unique && busiest > 1) {
                throw new Refused("the IDCAMS BLDINDEX of a UNIQUEKEY alternate index over duplicate keys "
                    + "(IBM's outcome is not stated)");
            }
            int need = AIX_HEADER + aix.keyLen + pointer * busiest;
            if (need > aix.max) {
                throw new Refused("the IDCAMS BLDINDEX record for the busiest key needs " + need
                    + " bytes, over RECORDSIZE maximum " + aix.max + " (IBM's outcome is not stated)");
            }
            aix.built = true;
            end(0, "BLDINDEX " + aix.name + ": " + base.records.size() + " records, " + groups.size() + " keys");
        }

        /** A REPRO endpoint: a Sequential, or a Cluster as its records (a path reads as a Sequential). */
        private Object endpoint(String kind, String name, String side) {
            Entry ent;
            if (kind.endsWith("FILE")) {
                if (seqs.containsKey(name)) {
                    return seqs.get(name);
                }
                if (!vsam.containsKey(name)) {
                    throw new Refused("REPRO " + kind + "(" + name + ") is not a dataset of the step");
                }
                ent = vsam.get(name);
                if (catalog.get(ent.name) != ent) {
                    throw new Refused("REPRO " + kind + "(" + name
                        + "): its cluster was deleted in the step (the allocation is stale)");
                }
            } else {
                if (!catalog.containsKey(name)) {
                    throw new Refused("REPRO " + kind + "(" + name
                        + ") is not a cluster in the catalog (a cataloged sequential is not modelled)");
                }
                ent = catalog.get(name);
            }
            if (ent instanceof Aix) {
                throw new Refused("REPRO " + kind + "(" + name + ") is an alternate index (its records are not modelled)");
            }
            if (ent instanceof PathEntry p) {
                if (!side.equals("IN")) {
                    throw new Refused("REPRO " + kind + "(" + name + ") writes through a path (not modelled)");
                }
                return readPath(p);
            }
            if (side.equals("OUT") && hasAix(ent.name)) {
                throw new Refused("REPRO " + kind + "(" + name
                    + ") onto a base cluster with an alternate index (its upgrade is not modelled)");
            }
            return ent;
        }

        private Sequential readPath(PathEntry path) {
            List<byte[]> recs = pathRecords(catalog, path.name);
            Entry aix = catalog.get(path.aix);
            Entry base = catalog.get(((Aix) aix).relate);
            Sequential s = new Sequential(base instanceof Cluster c ? reclen(c) : 0, "OLD");
            s.records = recs;
            return s;
        }

        @SuppressWarnings("unchecked")
        void repro(List<Op> ops) {
            Map<String, String[]> ends = new HashMap<>();
            for (Op op : ops) {
                String key = REPRO_KEY.get(op.name);
                if (key == null || op.args == null) {
                    throw new Refused("the IDCAMS REPRO " + op.name + " parameter");
                }
                String side = key.startsWith("IN") ? "IN" : "OUT";
                if (ends.containsKey(side)) {
                    throw new Refused("the IDCAMS REPRO names its " + side.toLowerCase(Locale.ROOT) + "put twice");
                }
                if (op.args.size() != 1 || op.args.get(0).args != null || op.args.get(0).name.contains("/")) {
                    throw new Refused("the IDCAMS REPRO " + key + " value (one name, no password)");
                }
                String nm = op.args.get(0).name;
                boolean ok = key.endsWith("DATASET") ? NAME.matcher(nm).matches() : DD.matcher(nm).matches();
                if (!ok) {
                    throw new Refused("the IDCAMS REPRO " + key + " value (" + head(nm, 20) + ") is not a name");
                }
                ends.put(side, new String[] {key, nm});
            }
            if (ends.size() != 2) {
                throw new Refused("the IDCAMS REPRO without both an input and an output");
            }
            Object src = endpoint(ends.get("IN")[0], ends.get("IN")[1], "IN");
            Object dst = endpoint(ends.get("OUT")[0], ends.get("OUT")[1], "OUT");
            if (src == dst) {
                throw new Refused("the IDCAMS REPRO of a dataset onto itself");
            }
            List<byte[]> recs = new ArrayList<>(recordsOf(src));
            int n = reclen(src);
            int m = reclen(dst);
            if (n != m) {
                throw new Refused("the IDCAMS REPRO between record lengths " + n + " and " + m);
            }
            if (recs.isEmpty()) {
                throw new Refused("the IDCAMS REPRO of zero records (its condition code is not modelled)");
            }
            if (dst instanceof Sequential s) {
                if (!(s.disp.equals("OLD") || s.disp.equals("NEW"))) {
                    throw new Refused("the IDCAMS REPRO onto a DD with DISP=" + s.disp);
                }
                s.records = recs;
            } else {
                Cluster c = (Cluster) dst;
                if (c.indexed) {
                    if (!c.records.isEmpty()) {
                        throw new Refused(
                            "the IDCAMS REPRO onto a non-empty KSDS (insert mode and its duplicate-key codes)");
                    }
                    for (int i = 0; i + 1 < recs.size(); i++) {
                        if (cmpKey(c.key(recs.get(i)), c.key(recs.get(i + 1))) >= 0) {
                            throw new Refused(
                                "the IDCAMS REPRO into a KSDS from a source out of key order or with a duplicate key");
                        }
                    }
                    c.records = recs;
                } else {
                    List<byte[]> all = new ArrayList<>(c.records);
                    all.addAll(recs);
                    c.records = all;
                }
            }
            end(0, "REPRO " + recs.size() + " records");
        }
    }

    private static List<byte[]> recordsOf(Object d) {
        return d instanceof Sequential s ? s.records : ((Cluster) d).records;
    }

    private static int reclen(Object d) {
        if (d instanceof Sequential s) {
            return s.lrecl;
        }
        Cluster c = (Cluster) d;
        if (c.avg != c.max) {
            throw new Refused("the IDCAMS REPRO of variable-length records (cluster " + c.name + " RECORDSIZE(" + c.avg
                + " " + c.max + "))");
        }
        return c.max;
    }

    private static String entry(String text, String what) {
        if (text.contains("/") || !NAME.matcher(text).matches()) {
            throw new Refused("the IDCAMS " + what + " name (" + head(text, 20)
                + ") is not a plain data set name (no password)");
        }
        return text;
    }

    private static int[] pair(List<Op> args, String what) {
        if (args.size() != 2 || args.get(0).args != null || args.get(1).args != null) {
            throw new Refused("the IDCAMS " + what + " value is not two numbers");
        }
        return new int[] {(int) num(args.get(0).name, what), (int) num(args.get(1).name, what)};
    }

    /**
     * The records read through a path: the base cluster's records in alternate-key order, records sharing a key in
     * the order the base holds them, as BLDINDEX orders them. An index BLDINDEX has not built is refused.
     */
    public static List<byte[]> pathRecords(Map<String, Entry> catalog, String pathName) {
        if (!(catalog.get(pathName) instanceof PathEntry path)) {
            throw new Refused(pathName + " is not a path in the catalog");
        }
        Entry aix = catalog.get(path.aix);
        Entry base = aix instanceof Aix a ? catalog.get(a.relate) : null;
        if (!(aix instanceof Aix a) || !(base instanceof Cluster b)) {
            throw new Refused("the path " + pathName + " does not lead to an alternate index over a cluster");
        }
        if (!a.built) {
            throw new Refused("the path " + pathName + " reads " + a.name
                + ", which BLDINDEX has not built (reading it is not modelled)");
        }
        List<byte[]> out = new ArrayList<>(b.records);
        out.sort((x, y) -> cmpKey(slice(x, a.keyOff, a.keyLen), slice(y, a.keyOff, a.keyLen)));
        return out;
    }

    /**
     * Run the commands of {@code sysin}. {@code catalog} is the clusters that exist when the step starts and
     * {@code dds} the step's DDs (a {@link Sequential}, or a {@link Vsam} naming a catalog cluster). Neither
     * argument is changed: the step's effect is in the {@link Result}.
     */
    public static Result run(String sysin, Map<String, Entry> catalog, Map<String, Object> dds) {
        List<Stmt> stmts = parse(sysin);
        Step st = new Step(catalog, dds);
        st.run(stmts);
        Result r = new Result();
        r.rc = st.maxcc;
        r.lastcc = st.lastcc;
        r.maxcc = st.maxcc;
        r.catalog = st.catalog;
        r.datasets = st.seqs;
        r.log = st.log;
        return r;
    }

    // ---------------------------------------------------------------------------------------------- driver
    private static List<byte[]> hexRecords(String field) {
        List<byte[]> out = new ArrayList<>();
        if (field.equals("-")) {
            return out;
        }
        for (String h : field.split(",")) {
            byte[] b = new byte[h.length() / 2];
            for (int i = 0; i < b.length; i++) {
                b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
            }
            out.add(b);
        }
        return out;
    }

    private static String hexRecordsOut(List<byte[]> recs) {
        if (recs.isEmpty()) {
            return "-";
        }
        List<String> parts = new ArrayList<>();
        for (byte[] r : recs) {
            parts.add(hex(r));
        }
        return String.join(",", parts);
    }

    /**
     * The test driver. The spec file has one line per item, blank-separated fields:
     * {@code CLUSTER name indexed(1|0) keyLen keyOff avg max hexrecords|-}, {@code SEQ dd lrecl disp hexrecords|-},
     * {@code VSAM dd cluster}, and {@code STEP deck-file}: the steps run in order, each against the catalog the step
     * before left, with the DDs as stated. Per step it prints {@code RC rc lastcc maxcc} or {@code REFUSED message},
     * then {@code LOG}, {@code CAT}, {@code DS} and {@code PATH} lines. {@code RESET} starts a new scenario (an empty catalog
     * and no DDs) and prints {@code --}.
     */
    public static void main(String[] args) throws IOException {
        Map<String, Entry> catalog = new LinkedHashMap<>();
        Map<String, Object> dds = new LinkedHashMap<>();
        StringBuilder out = new StringBuilder();
        for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
            String[] f = line.trim().split(" +");
            if (f[0].isEmpty()) {
                continue;
            }
            switch (f[0]) {
                case "CLUSTER" -> {
                    Cluster c = new Cluster(f[1], f[2].equals("1"), Integer.parseInt(f[3]), Integer.parseInt(f[4]),
                        Integer.parseInt(f[5]), Integer.parseInt(f[6]));
                    c.records = hexRecords(f[7]);
                    catalog.put(f[1], c);
                }
                case "SEQ" -> {
                    Sequential s = new Sequential(Integer.parseInt(f[2]), f[3]);
                    s.records = hexRecords(f[4]);
                    dds.put(f[1], s);
                }
                case "VSAM" -> dds.put(f[1], new Vsam(f[2]));
                case "RESET" -> {
                    catalog = new LinkedHashMap<>();
                    dds = new LinkedHashMap<>();
                    out.append("--\n");
                }
                default -> {
                    String sysin = Files.readString(Path.of(f[1]), StandardCharsets.UTF_8);
                    try {
                        Result r = run(sysin, catalog, dds);
                        out.append("RC ").append(r.rc).append(' ').append(r.lastcc).append(' ').append(r.maxcc)
                            .append('\n');
                        for (String l : r.log) {
                            out.append("LOG ").append(l).append('\n');
                        }
                        for (Entry e : r.catalog.values()) {
                            out.append("CAT ").append(describe(e)).append('\n');
                        }
                        for (Map.Entry<String, Sequential> d : r.datasets.entrySet()) {
                            out.append("DS ").append(d.getKey()).append(' ').append(hexRecordsOut(d.getValue().records))
                                .append('\n');
                        }
                        for (Entry e : r.catalog.values()) {
                            if (e instanceof PathEntry) {
                                String v;
                                try {
                                    v = hexRecordsOut(pathRecords(r.catalog, e.name));
                                } catch (Refused x) {
                                    v = "REFUSED " + x.getMessage();
                                }
                                out.append("PATH ").append(e.name).append(' ').append(v).append('\n');
                            }
                        }
                        catalog = r.catalog;
                    } catch (Refused x) {
                        out.append("REFUSED ").append(x.getMessage()).append('\n');
                    }
                }
            }
        }
        System.out.write(out.toString().getBytes(StandardCharsets.UTF_8));
        System.out.flush();
    }

    private static String describe(Entry e) {
        if (e instanceof Cluster c) {
            return "CLUSTER " + c.name + " " + c.indexed + " " + c.keyLen + " " + c.keyOff + " " + c.avg + " " + c.max
                + " " + hexRecordsOut(c.records);
        }
        if (e instanceof Aix a) {
            return "AIX " + a.name + " " + a.relate + " " + a.keyLen + " " + a.keyOff + " " + a.avg + " " + a.max + " "
                + a.unique + " " + a.upgrade + " " + a.built;
        }
        PathEntry p = (PathEntry) e;
        return "PATH " + p.name + " " + p.aix + " " + p.update;
    }
}
