package __PACKAGE__.cobolrt.sql;

import __PACKAGE__.cobolrt.Cobol;
import __PACKAGE__.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.sql.SQLException;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.function.IntSupplier;
import java.util.function.Supplier;

/**
 * Embedded SQL for a det port: each EXEC SQL statement runs as the generated Db2 repository's method for it (one per
 * statement, the SQL as written), and this class does what Db2's precompiler and runtime do around it -- the host
 * variables' values from their bytes and back, and the SQLCA.
 *
 * Host variables, as the Db2 precompiler declares them for COBOL:
 *   PIC X(n)                      CHAR(n): all n bytes, trailing blanks included
 *   49 len S9(4) COMP + 49 X(n)   VARCHAR(n): the length's bytes
 *   numeric DISPLAY / COMP-3      DECIMAL(p,s);  binary  SMALLINT / INTEGER / BIGINT -- as BigDecimal
 * Into a host variable: a string padded with blanks or truncated (SQLWARN0 / SQLWARN1 'W', the indicator set to the
 * original length); a number whose integer part does not fit is SQLCODE -304 and nothing is assigned; NULL without an
 * indicator is -305. A searched UPDATE / DELETE that changes no row is +100; SELECT INTO with no row +100, with more
 * than one -811. Any other error is Db2's own SQLCODE and SQLSTATE, from the JDBC driver's SQLException.
 *
 * Plain Java: the repository's exceptions are recognised by their class names ("EmptyResultDataAccessException",
 * "IncorrectResultSizeDataAccessException") and their SQLException cause.
 */
public final class DetSql {
    private DetSql() {
    }

    // ---- the SQLCA (IBM's layout, the binary fields COMP-5) -------------------------------------------------
    private static final int SQLCODE = 12, SQLERRML = 16, SQLERRMC = 18, SQLERRP = 88, SQLERRD = 96, SQLWARN = 120,
            SQLSTATE = 131;

    private static void put(Field ca, int at, int length, String text, Charset cs) {
        byte[] b = text.getBytes(cs);
        for (int i = 0; i < length; i++) {
            ca.storage().bytes[ca.offset() + at + i] = i < b.length ? b[i] : (byte) ' ';
        }
    }

    private static void putInt(Field ca, int at, int bytes, long v) {  // COMP-5: native, little-endian
        for (int i = 0; i < bytes; i++) {
            ca.storage().bytes[ca.offset() + at + i] = (byte) (v >> (8 * i));
        }
    }

    /** The SQLCA as a statement leaves it before its outcome: SQLCODE 0, no warning. */
    public static void reset(Field ca, Charset cs) {
        put(ca, 0, 8, "SQLCA", cs);
        putInt(ca, 8, 4, 136);
        putInt(ca, SQLCODE, 4, 0);
        putInt(ca, SQLERRML, 2, 0);
        put(ca, SQLERRMC, 70, "", cs);
        put(ca, SQLERRP, 8, "", cs);
        for (int i = 0; i < 6; i++) {
            putInt(ca, SQLERRD + 4 * i, 4, 0);
        }
        put(ca, SQLWARN, 11, "", cs);
        put(ca, SQLSTATE, 5, "00000", cs);
    }

    private static void code(Field ca, int sqlcode, String state, Charset cs) {
        putInt(ca, SQLCODE, 4, sqlcode);
        put(ca, SQLSTATE, 5, state, cs);
    }

    private static void warn(Field ca, int which, Charset cs) {
        put(ca, SQLWARN, 1, "W", cs);
        put(ca, SQLWARN + which, 1, "W", cs);
    }

    /** A statement's exception as its SQLCODE: Db2's, from the driver's SQLException -- and, from IBM's JDBC
     *  driver (DB2Diagnosable.getSqlca, by reflection: no compile-time dependency), Db2's own SQLCA: the message
     *  tokens (SQLERRMC), SQLERRP, SQLERRD and the warnings, as the precompiled program has them. */
    private static void failed(Field ca, RuntimeException e, Charset cs) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t instanceof SQLException s && s.getErrorCode() != 0) {
                code(ca, s.getErrorCode(), s.getSQLState() == null ? "     " : s.getSQLState(), cs);
                db2Sqlca(ca, s, cs);
                return;
            }
        }
        throw e;  // not a database error: the port's own fault
    }

    private static void db2Sqlca(Field ca, SQLException s, Charset cs) {
        try {
            Object sqlca = s.getClass().getMethod("getSqlca").invoke(s);
            if (sqlca == null) {
                return;
            }
            Class<?> c = sqlca.getClass();
            String errmc = (String) c.getMethod("getSqlErrmc").invoke(sqlca);
            if (errmc != null) {
                byte[] b = errmc.getBytes(cs);
                putInt(ca, SQLERRML, 2, Math.min(b.length, 70));
                put(ca, SQLERRMC, 70, errmc, cs);
            }
            String errp = (String) c.getMethod("getSqlErrp").invoke(sqlca);
            if (errp != null) {
                put(ca, SQLERRP, 8, errp, cs);
            }
            int[] errd = (int[]) c.getMethod("getSqlErrd").invoke(sqlca);
            for (int i = 0; errd != null && i < Math.min(6, errd.length); i++) {
                putInt(ca, SQLERRD + 4 * i, 4, errd[i]);
            }
            char[] warn = (char[]) c.getMethod("getSqlWarn").invoke(sqlca);
            for (int i = 0; warn != null && i < Math.min(11, warn.length); i++) {
                put(ca, SQLWARN + i, 1, String.valueOf(warn[i]), cs);
            }
        } catch (ReflectiveOperationException | ClassCastException notIbm) {
            // another driver: the code and the state only
        }
    }

    private static boolean named(Throwable e, String simpleName) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t.getClass().getSimpleName().equals(simpleName)) {
                return true;
            }
        }
        return false;
    }

    // ---- host variables into the statement ---------------------------------------------------------------
    /** A PIC X(n) host variable: CHAR(n), its n bytes. */
    public static String charIn(Field f, Charset cs) {
        return Cobol.text(f, cs);
    }

    /** A VARCHAR host variable (the 49-level length and text): the length's bytes of the text. */
    public static String varcharIn(Field len, Field text, Charset cs) {
        int n = Cobol.num(len, cs).intValue();
        n = Math.max(0, Math.min(n, text.length()));
        return new String(text.storage().bytes, text.offset(), n, cs);
    }

    /** A numeric host variable: DECIMAL / SMALLINT / INTEGER / BIGINT, its value. */
    public static BigDecimal numIn(Field f, Charset cs) {
        return Cobol.num(f, cs);
    }

    /** A host variable with an indicator: NULL when the indicator is negative. */
    public static Object orNull(Object value, Field indicator, Charset cs) {
        return Cobol.num(indicator, cs).signum() < 0 ? null : value;
    }

    // ---- statements -----------------------------------------------------------------------------------------
    /** INSERT / UPDATE / DELETE: `searched` (an UPDATE or DELETE with a WHERE, or none) that changes no row is +100. */
    public static void update(Field ca, IntSupplier statement, boolean searched, Charset cs) {
        reset(ca, cs);
        try {
            int rows = statement.getAsInt();
            putInt(ca, SQLERRD + 8, 4, rows);
            if (rows == 0 && searched) {
                code(ca, 100, "02000", cs);
            }
        } catch (RuntimeException e) {
            failed(ca, e, cs);
        }
    }

    /** SELECT INTO: the one row, or null (+100 no row, -811 more than one, or Db2's error). */
    public static Map<String, Object> selectOne(Field ca, Supplier<Map<String, Object>> statement, Charset cs) {
        reset(ca, cs);
        try {
            return statement.get();
        } catch (RuntimeException e) {
            if (named(e, "EmptyResultDataAccessException")) {
                code(ca, 100, "02000", cs);
            } else if (named(e, "IncorrectResultSizeDataAccessException")) {
                code(ca, -811, "21000", cs);
            } else {
                failed(ca, e, cs);
            }
            return null;
        }
    }

    /** A row's columns, in order, into the host variables (`kinds`: X, V, N per host variable; `indicators` null
     *  where none): false when an assignment failed (-304 / -305 set; the rest not assigned). */
    public static boolean into(Field ca, Map<String, Object> row, String kinds, Field[] hosts, Field[] texts,
                               Field[] indicators, Charset cs) {
        Iterator<Object> values = row.values().iterator();
        for (int i = 0; i < hosts.length; i++) {
            Object v = values.hasNext() ? values.next() : null;
            Field ind = indicators == null ? null : indicators[i];
            if (v == null) {
                if (ind == null) {
                    code(ca, -305, "22002", cs);
                    return false;
                }
                Cobol.store(ind, BigDecimal.valueOf(-1), false, cs);
                continue;
            }
            char kind = kinds.charAt(i);
            if (kind == 'N') {
                BigDecimal n = v instanceof BigDecimal b ? b : new BigDecimal(v.toString());
                if (Cobol.storeChecked(hosts[i], n, false, cs)) {  // the integer part does not fit (the fraction is cut)
                    code(ca, -304, "22003", cs);
                    return false;
                }
                if (ind != null) {
                    Cobol.store(ind, BigDecimal.ZERO, false, cs);
                }
                continue;
            }
            String s = text(v);
            byte[] b = s.getBytes(cs);
            Field target = kind == 'V' ? texts[i] : hosts[i];
            int room = target.length();
            int k = Math.min(b.length, room);
            System.arraycopy(b, 0, target.storage().bytes, target.offset(), k);
            if (kind == 'X') {
                for (int j = k; j < room; j++) {
                    target.storage().bytes[target.offset() + j] = (byte) ' ';
                }
            } else {
                Cobol.store(hosts[i], BigDecimal.valueOf(k), false, cs);
            }
            if (b.length > room) {
                warn(ca, 1, cs);
            }
            if (ind != null) {
                Cobol.store(ind, BigDecimal.valueOf(b.length > room ? b.length : 0), false, cs);
            }
        }
        return true;
    }

    /** A column's value as Db2 renders it in character form. */
    private static String text(Object v) {
        if (v instanceof String s) {
            return s;
        }
        if (v instanceof java.sql.Date d) {
            return d.toLocalDate().toString();  // ISO: YYYY-MM-DD
        }
        if (v instanceof BigDecimal b) {
            return b.toPlainString();
        }
        if (v instanceof Number n) {
            return n.toString();
        }
        throw new UnsupportedOperationException("a " + v.getClass().getSimpleName() + " column into a string host "
            + "variable is not modelled");
    }

    // ---- cursors --------------------------------------------------------------------------------------------
    private static final Map<String, Iterator<Map<String, Object>>> OPEN = new HashMap<>();

    /** OPEN: the cursor's query run with the host variables' values now (-502 when it is open). */
    public static void open(Field ca, String cursor, Supplier<List<Map<String, Object>>> query, Charset cs) {
        reset(ca, cs);
        if (OPEN.containsKey(cursor)) {
            code(ca, -502, "24502", cs);
            return;
        }
        try {
            OPEN.put(cursor, query.get().iterator());
        } catch (RuntimeException e) {
            failed(ca, e, cs);
        }
    }

    /** FETCH: the next row, or null (+100 at the end, -501 when the cursor is not open). */
    public static Map<String, Object> fetch(Field ca, String cursor, Charset cs) {
        reset(ca, cs);
        Iterator<Map<String, Object>> rows = OPEN.get(cursor);
        if (rows == null) {
            code(ca, -501, "24501", cs);
            return null;
        }
        if (!rows.hasNext()) {
            code(ca, 100, "02000", cs);
            return null;
        }
        return rows.next();
    }

    /** CLOSE (-501 when it is not open). */
    public static void close(Field ca, String cursor, Charset cs) {
        reset(ca, cs);
        if (OPEN.remove(cursor) == null) {
            code(ca, -501, "24501", cs);
        }
    }

    /** A task's or a step's end: its cursors closed. */
    public static void closeAll() {
        OPEN.clear();
    }
}
