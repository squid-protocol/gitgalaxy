// Cobrix referee driver (#4377): parses each copybook named on stdin (one path per line) with
// Cobrix's CopybookParser and prints one JSON line per copybook with every field's offset/size.
// Compiled and run by tests/tools/referees/cobrix_adapter.py against a Cobrix build installed
// OUTSIDE this repository (see tests/tools/referees/README.md); nothing of Cobrix is vendored.
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import za.co.absa.cobrix.cobol.parser.Copybook;
import za.co.absa.cobrix.cobol.parser.CopybookParser;
import za.co.absa.cobrix.cobol.parser.ast.Group;
import za.co.absa.cobrix.cobol.parser.ast.Primitive;
import za.co.absa.cobrix.cobol.parser.ast.Statement;
import za.co.absa.cobrix.cobol.parser.policies.CommentPolicy;

public final class CobrixFacts {
    private static String q(String s) {
        if (s == null) return "null";
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    private static String opt(scala.Option<?> o) {
        return o.isDefined() ? q(String.valueOf(o.get())) : "null";
    }

    private static void walk(Statement st, String root, StringBuilder out, boolean[] first) {
        boolean group = st instanceof Group;
        if (!first[0]) out.append(',');
        first[0] = false;
        out.append("{\"root\":").append(q(root))
           .append(",\"name\":").append(q(st.originalName()))
           .append(",\"level\":").append(st.level())
           .append(",\"line\":").append(st.lineNumber())
           .append(",\"group\":").append(group)
           .append(",\"offset\":").append(st.binaryProperties().offset())
           .append(",\"size\":").append(st.binaryProperties().actualSize())
           .append(",\"data_size\":").append(st.binaryProperties().dataSize())
           .append(",\"occurs\":").append(opt(st.occurs()))
           .append(",\"occurs_to\":").append(opt(st.to()))
           .append(",\"depending_on\":").append(opt(st.dependingOn()))
           .append(",\"redefines\":").append(opt(st.redefines()))
           .append(",\"filler\":").append(st.isFiller());
        if (!group) {
            Primitive p = (Primitive) st;
            out.append(",\"pic\":").append(opt(p.dataType().originalPic()))
               .append(",\"type\":").append(q(p.dataType().getClass().getSimpleName()))
               .append(",\"datatype\":").append(q(p.dataType().toString()));
        }
        out.append('}');
        if (group) {
            scala.collection.mutable.ArrayBuffer<Statement> kids = ((Group) st).children();
            for (int i = 0; i < kids.size(); i++) walk(kids.apply(i), root, out, first);
        }
    }

    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String path;
        while ((path = in.readLine()) != null) {
            if (path.isBlank()) continue;
            long t0 = System.nanoTime();
            StringBuilder out = new StringBuilder();
            try {
                String text = new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.ISO_8859_1);
                Copybook cb = CopybookParser.parseSimple(text, false, false, new CommentPolicy(true, 6, 72), false, false);
                StringBuilder fields = new StringBuilder();
                boolean[] first = {true};
                scala.collection.mutable.ArrayBuffer<Statement> roots = cb.ast().children();
                for (int i = 0; i < roots.size(); i++) walk(roots.apply(i), roots.apply(i).originalName(), fields, first);
                out.append("{\"path\":").append(q(path)).append(",\"ok\":true,\"seconds\":")
                   .append((System.nanoTime() - t0) / 1e9).append(",\"fields\":[").append(fields).append("]}");
            } catch (Throwable e) {
                String msg = String.valueOf(e.getMessage());
                if (msg.length() > 300) msg = msg.substring(0, 300);
                out.setLength(0);
                out.append("{\"path\":").append(q(path)).append(",\"ok\":false,\"seconds\":")
                   .append((System.nanoTime() - t0) / 1e9).append(",\"error\":")
                   .append(q(e.getClass().getSimpleName() + ": " + msg)).append("}");
            }
            System.out.println(out);
            System.out.flush();
        }
    }
}
