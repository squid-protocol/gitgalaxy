package com.gitgalaxy.modernized.cobolrt.sql;

import com.gitgalaxy.modernized.cobolrt.Cobol;
import com.gitgalaxy.modernized.cobolrt.Field;
import java.math.BigDecimal;
import java.nio.charset.Charset;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.function.IntSupplier;
import java.util.function.ToIntFunction;
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
 *
 * #4173 -- SQL faults. Each statement's call carries its key, "PROGRAM:LINE" (the program and the line of its EXEC
 * SQL in that program's source). A fault plan -- withFaults, or the file the system property gitgalaxy.sqlfaults.plan
 * names -- has one fault per line, `PROGRAM LINE NTH|* SQLCODE SQLSTATE [TOKEN [SQLERRD3]]`: the nth execution of that
 * statement does not run; its SQLCA is reset's with that SQLCODE and SQLSTATE (and, when declared, one message token
 * as SQLERRMC with its SQLERRML, and SQLERRD(3): #5561), and nothing else changes. Each fault that fires is
 * appended to the log (gitgalaxy.sqlfaults.log) as `SQL PROGRAM LINE N SQLCODE` -- the line the equivalence harness's
 * COBOL side (tests/equivalence/db2/ggsql.c) writes for the same fault.
 *
 * #4269 -- the unit of work. EXEC SQL COMMIT / ROLLBACK end the Db2 unit of work the program runs in. That unit is
 * the runner's (unitOfWork): for a batch step, one Db2 transaction from the step's start, committed at its normal end
 * and backed out when it abends, as Db2 for z/OS does for a DSN / CAF batch program. COMMIT commits it and closes
 * every cursor not declared WITH HOLD (a held one stays open, with no current row until its next FETCH); ROLLBACK
 * backs it out and closes every cursor (IBM Db2 for z/OS SQL Reference, COMMIT and ROLLBACK statements). With no
 * unit of work given, each statement was committed as it ran: COMMIT has nothing more to commit, and ROLLBACK cannot
 * undo it -- it is refused (UnsupportedOperationException), never answered. SAVEPOINT, ROLLBACK TO SAVEPOINT and
 * RELEASE SAVEPOINT run as written on the unit's connection (savepoint), Db2 answering them.
 */
public final class DetSql {
    private DetSql() {
    }

    // ---- #4173: SQL faults ------------------------------------------------------------------------------------
    private static final List<String[]> FAULTS = new ArrayList<>();
    private static final Map<String, Integer> RUNS = new HashMap<>();
    private static java.nio.file.Path faultLog;

    static {
        String plan = System.getProperty("gitgalaxy.sqlfaults.plan", "");
        String log = System.getProperty("gitgalaxy.sqlfaults.log", "");
        if (!plan.isEmpty()) {
            try {
                withFaults(java.nio.file.Files.readAllLines(java.nio.file.Path.of(plan)),
                        log.isEmpty() ? null : java.nio.file.Path.of(log));
            } catch (java.io.IOException e) {
                throw new java.io.UncheckedIOException(e);
            }
        }
    }

    /** The fault plan from here on (one fault per line, `PROGRAM LINE NTH|* SQLCODE SQLSTATE [TOKEN [SQLERRD3]]`),
     *  each statement's executions counted afresh, each fault that fires appended to `log` (null: not logged). */
    // [rule RT-SQL-FAULT-INJECTION]
    public static void withFaults(List<String> plan, java.nio.file.Path log) {
        FAULTS.clear();
        RUNS.clear();
        for (String line : plan) {
            String[] f = line.trim().split("\\s+");
            if (f.length >= 5 && f.length <= 7) {
                FAULTS.add(f);
            }
        }
        faultLog = log;
    }

    /** The planned fault of this execution of the statement at `at` ("PROGRAM:LINE"), if any: true, the SQLCA set. */
    private static boolean injected(Field ca, String at, Charset cs) {
        if (at == null) {
            return false;
        }
        int n = RUNS.merge(at, 1, Integer::sum);
        int colon = at.lastIndexOf(':');
        String program = at.substring(0, colon), line = at.substring(colon + 1);
        for (String[] f : FAULTS) {
            if (f[0].equals(program) && f[1].equals(line) && ("*".equals(f[2]) || Integer.parseInt(f[2]) == n)) {
                code(ca, Integer.parseInt(f[3]), f[4], cs);
                if (f.length > 5) {  // #5561: the declared message token and reason code
                    String token = "-".equals(f[5]) ? "" : f[5].length() > 70 ? f[5].substring(0, 70) : f[5];  // `-`: none
                    putInt(ca, SQLERRML, 2, token.length());
                    put(ca, SQLERRMC, 70, token, cs);
                    putInt(ca, SQLERRD + 8, 4, f.length > 6 ? Integer.parseInt(f[6]) : 0);
                }
                if (faultLog != null) {
                    try {
                        java.nio.file.Files.writeString(faultLog, "SQL " + program + " " + line + " " + n + " " + f[3]
                                + System.lineSeparator(), java.nio.file.StandardOpenOption.CREATE,
                                java.nio.file.StandardOpenOption.APPEND);
                    } catch (java.io.IOException e) {
                        throw new java.io.UncheckedIOException(e);
                    }
                }
                return true;
            }
        }
        return false;
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
    // [rule RT-SQL-SQLCA]
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

    /** IBM JCC's client-side "invalid conversion" error code, which Db2 itself never returns to a program. */
    private static final int JCC_BAD_CONVERSION = -4220;

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
                if (s.getErrorCode() == JCC_BAD_CONVERSION) {
                    // #4658: the JDBC driver refused the host variable's bytes on the client (a date column bound to
                    // an unset, non-date PIC X) before Db2 saw them; the embedded-SQL program, on z/OS as on Db2 LUW,
                    // gets the server's verdict: -180, SQLSTATE 22007 (the string is not a valid datetime value).
                    code(ca, -180, "22007", cs);
                    return;
                }
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
    // [rule RT-SQL-HOST-VARIABLE-IN]
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
    // [rule RT-SQL-SEARCHED-NOT-FOUND]
    public static void update(Field ca, IntSupplier statement, boolean searched, Charset cs) {
        update(ca, null, statement, searched, cs);
    }

    /** update, the statement at `at` ("PROGRAM:LINE"; #4173: a planned SQL fault there instead of the statement). */
    public static void update(Field ca, String at, IntSupplier statement, boolean searched, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
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

    /** INSERT ... VALUES (:A1, :A2) FOR n ROWS [ATOMIC] (#4269; IBM Db2 for z/OS SQL Reference, INSERT): the single-row
     *  statement run for element 1..n of every column's host variable table (`hosts[column][row]`, `indicators` null
     *  where none), SQLERRD(3) the rows inserted. ATOMIC (the default): a row that fails is Db2's error with the whole
     *  statement undone -- nothing inserted, SQLERRD(3) 0. The undo of the rows before the failing one is a savepoint
     *  (INSERT_ROWS_SAVEPOINT) set on the unit of work's connection before row 1 and rolled back to; with no unit of
     *  work a failure after row 1 is refused (the rows were committed as they ran). n above the host variable
     *  tables (`capacity`) or below 1 is refused. */
    // [rule RT-SQL-INSERT-ROWS]
    public static void insertRows(Field ca, String at, long n, int capacity, String kinds, String[] names,
                                  Field[][] hosts, Field[][] indicators, ToIntFunction<Map<String, Object>> statement,
                                  Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (n < 1 || n > capacity) {
            throw new UnsupportedOperationException("EXEC SQL INSERT at " + at + ": FOR " + n
                    + " ROWS with host variable tables of " + capacity);
        }
        int done = 0;
        boolean undoable = n > 1 && unitOfWork != null;
        if (undoable) {
            try {
                unitOfWork.execute("SAVEPOINT " + INSERT_ROWS_SAVEPOINT + " ON ROLLBACK RETAIN CURSORS");
            } catch (RuntimeException e) {
                failed(ca, e, cs);
                return;
            }
        }
        for (int j = 0; j < n; j++) {
            Map<String, Object> params = new HashMap<>();
            for (int c = 0; c < hosts.length; c++) {
                Object v = kinds.charAt(c) == 'N' ? numIn(hosts[c][j], cs) : charIn(hosts[c][j], cs);
                if (indicators != null && indicators[c] != null) {
                    v = orNull(v, indicators[c][j], cs);
                }
                params.put(names[c], v);
            }
            try {
                done += statement.applyAsInt(params);
            } catch (RuntimeException e) {
                if (done == 0 && !undoable) {
                    failed(ca, e, cs);
                    return;
                }
                if (undoable) {
                    try {
                        unitOfWork.execute("ROLLBACK TO SAVEPOINT " + INSERT_ROWS_SAVEPOINT);
                        unitOfWork.execute("RELEASE SAVEPOINT " + INSERT_ROWS_SAVEPOINT);
                    } catch (RuntimeException undo) {
                        throw new UnsupportedOperationException("EXEC SQL INSERT at " + at + ": row " + (j + 1)
                                + " of " + n + " failed and ATOMIC's undo failed too", undo);
                    }
                    failed(ca, e, cs);
                    return;
                }
                throw new UnsupportedOperationException("EXEC SQL INSERT at " + at + ": row " + (j + 1) + " of " + n
                        + " failed after " + done + " were inserted; ATOMIC's undo is not modelled", e);
            }
        }
        if (undoable) {
            try {
                unitOfWork.execute("RELEASE SAVEPOINT " + INSERT_ROWS_SAVEPOINT);
            } catch (RuntimeException e) {
                failed(ca, e, cs);
                return;
            }
        }
        putInt(ca, SQLERRD + 8, 4, done);
    }

    /** The savepoint ATOMIC's undo of INSERT ... FOR n ROWS rolls back to (a name a program's own savepoint won't use). */
    private static final String INSERT_ROWS_SAVEPOINT = "GGINSROWS_UNDO";

    /** SELECT INTO: the one row, or null (+100 no row, -811 more than one, or Db2's error). */
    // [rule RT-SQL-SELECT-INTO]
    public static Map<String, Object> selectOne(Field ca, Supplier<Map<String, Object>> statement, Charset cs) {
        return selectOne(ca, null, statement, cs);
    }

    /** selectOne, the statement at `at` (#4173: a planned SQL fault there: null, the SQLCA set). */
    public static Map<String, Object> selectOne(Field ca, String at, Supplier<Map<String, Object>> statement,
                                                Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return null;
        }
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
    // [rule RT-SQL-HOST-VARIABLE-OUT]
    public static boolean into(Field ca, Map<String, Object> row, String kinds, Field[] hosts, Field[] texts,
                               Field[] indicators, Charset cs) {
        Iterator<Object> values = row.entrySet().stream()  // GG_RID: the row id a positioned statement uses, no column
                .filter(e -> !"GG_RID".equalsIgnoreCase(e.getKey())).map(Map.Entry::getValue).iterator();
        for (int i = 0; i < hosts.length; i++) {
            if (!values.hasNext()) {  // more host variables than columns: those left as they are, SQLWARN3 'W'
                warn(ca, 3, cs);
                break;
            }
            Object v = values.next();
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
                if (Cobol.storeHostChecked(hosts[i], n, false, cs)) {  // the integer part does not fit (the fraction is cut)
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
        if (v instanceof java.sql.Timestamp t) {  // Db2's character form (ISO date format): 2011-08-22-12.13.01.000000
            return t.toLocalDateTime().format(java.time.format.DateTimeFormatter.ofPattern("uuuu-MM-dd-HH.mm.ss.SSSSSS"));
        }
        if (v instanceof java.sql.Time t) {  // ISO: HH.MM.SS
            return t.toLocalTime().format(java.time.format.DateTimeFormatter.ofPattern("HH.mm.ss"));
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

    // ---- #4269: the unit of work ------------------------------------------------------------------------------
    /** The Db2 unit of work a program's statements run in: its runner's (a batch step's transaction). */
    public interface UnitOfWork {
        /** Commit the work done since the last commit point; the unit goes on. */
        void commit();

        /** Back out the work done since the last commit point; the unit goes on. */
        void rollback();

        /** Run a statement as written on the unit's connection (a savepoint statement); Db2's error as thrown. */
        default void execute(String sql) {
            throw new UnsupportedOperationException("this unit of work runs no statement: " + sql);
        }
    }

    private static UnitOfWork unitOfWork;

    /** The unit of work the statements run in from here on (null: none -- each statement commits as it runs);
     *  the one it replaces. */
    public static UnitOfWork unitOfWork(UnitOfWork u) {
        UnitOfWork was = unitOfWork;
        unitOfWork = u;
        return was;
    }

    /** EXEC SQL COMMIT [WORK] at `at`: the unit of work committed (Db2's SQLCODE if it fails); every cursor not
     *  declared WITH HOLD closed, a held one left with no current row. */
    // [rule RT-SQL-UNIT-OF-WORK]
    public static void commit(Field ca, String at, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (unitOfWork != null) {
            try {
                unitOfWork.commit();
            } catch (RuntimeException e) {
                failed(ca, e, cs);
                return;
            }
        }
        OPEN.keySet().removeIf(c -> !HOLD.contains(c));
        POS.keySet().retainAll(OPEN.keySet());
        CURRENT.clear();
    }

    /** EXEC SQL ROLLBACK [WORK] at `at`: the unit of work backed out, every cursor closed. Refused with no unit of
     *  work: the statements were committed as they ran, and a port never pretends to undo them. */
    public static void rollback(Field ca, String at, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (unitOfWork == null) {
            throw new UnsupportedOperationException("EXEC SQL ROLLBACK at " + at + ": no unit of work -- each "
                    + "statement was committed as it ran (the runner gives the step one: DetSql.unitOfWork)");
        }
        try {
            unitOfWork.rollback();
        } catch (RuntimeException e) {
            failed(ca, e, cs);
            return;
        }
        OPEN.clear();
        POS.clear();
        CURRENT.clear();
    }

    /** EXEC SQL SAVEPOINT / ROLLBACK TO SAVEPOINT / RELEASE SAVEPOINT at `at`: `sql` as written, on the unit of
     *  work's connection, Db2 answering (-880: no such savepoint). The cursors are not touched: a savepoint is set ON
     *  ROLLBACK RETAIN CURSORS. Refused with no unit of work, as ROLLBACK is. */
    // [rule RT-SQL-SAVEPOINT]
    public static void savepoint(Field ca, String at, String sql, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (unitOfWork == null) {
            throw new UnsupportedOperationException("EXEC SQL " + sql + " at " + at + ": no unit of work -- each "
                    + "statement was committed as it ran (the runner gives the step one: DetSql.unitOfWork)");
        }
        try {
            unitOfWork.execute(sql);
        } catch (RuntimeException e) {
            failed(ca, e, cs);
        }
    }

    // ---- cursors --------------------------------------------------------------------------------------------
    // #4269: an open cursor is its result rows (read at OPEN) and a position: 0 before the first row, 1..n on a row,
    // n + 1 after the last. FETCH [NEXT] steps it forward; a scroll cursor's orientations (fetchScroll) move it.
    private static final Map<String, List<Map<String, Object>>> OPEN = new HashMap<>();
    private static final Map<String, Integer> POS = new HashMap<>();
    private static final Map<String, Map<String, Object>> CURRENT = new HashMap<>();  // the row FETCH last returned
    private static final java.util.Set<String> HOLD = new java.util.HashSet<>();  // #4269: open cursors WITH HOLD

    /** OPEN: the cursor's query run with the host variables' values now (-502 when it is open). */
    // [rule RT-SQL-CURSOR]
    public static void open(Field ca, String cursor, Supplier<List<Map<String, Object>>> query, Charset cs) {
        open(ca, null, cursor, query, cs);
    }

    /** open, the OPEN at `at` (#4173: a planned SQL fault there: the cursor not opened, the SQLCA set). */
    public static void open(Field ca, String at, String cursor, Supplier<List<Map<String, Object>>> query,
                            Charset cs) {
        open(ca, at, cursor, false, query, cs);
    }

    /** open, of a cursor declared WITH HOLD when `hold` (#4269: a COMMIT leaves it open). */
    public static void open(Field ca, String at, String cursor, boolean hold,
                            Supplier<List<Map<String, Object>>> query, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (OPEN.containsKey(cursor)) {
            code(ca, -502, "24502", cs);
            return;
        }
        try {
            OPEN.put(cursor, query.get());
            POS.put(cursor, 0);
            if (hold) {
                HOLD.add(cursor);
            } else {
                HOLD.remove(cursor);
            }
        } catch (RuntimeException e) {
            failed(ca, e, cs);
        }
    }

    /** FETCH: the next row, or null (+100 at the end, -501 when the cursor is not open). */
    public static Map<String, Object> fetch(Field ca, String cursor, Charset cs) {
        return fetch(ca, null, cursor, cs);
    }

    /** fetch, the FETCH at `at` (#4173: a planned SQL fault there: null, the cursor where it was, the SQLCA set). */
    public static Map<String, Object> fetch(Field ca, String at, String cursor, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return null;
        }
        List<Map<String, Object>> rows = OPEN.get(cursor);
        if (rows == null) {
            code(ca, -501, "24501", cs);
            return null;
        }
        return moveTo(ca, cursor, rows, POS.get(cursor) + 1, cs);
    }

    /** FETCH [NEXT] ROWSET FROM cursor FOR n ROWS (#4269; IBM Db2 for z/OS SQL Reference, FETCH): up to n next rows of
     *  the cursor, SQLERRD(3) the number read. A rowset that reaches the end of the data holds fewer than n rows (or
     *  none) and is SQLCODE +100 with SQLERRD(3) set (register Q4); n above the host variable tables (`capacity`) or
     *  below 1 is refused. */
    // [rule RT-SQL-ROWSET-FETCH]
    public static List<Map<String, Object>> fetchRowset(Field ca, String at, String cursor, long n, int capacity,
                                                        Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return List.of();
        }
        List<Map<String, Object>> rows = OPEN.get(cursor);
        if (rows == null) {
            code(ca, -501, "24501", cs);
            return List.of();
        }
        if (n < 1 || n > capacity) {
            throw new UnsupportedOperationException("EXEC SQL FETCH ROWSET at " + at + ": FOR " + n
                    + " ROWS with host variable tables of " + capacity);
        }
        List<Map<String, Object>> got = new ArrayList<>();
        while (got.size() < n) {
            Map<String, Object> row = moveTo(ca, cursor, rows, POS.get(cursor) + 1, cs);
            if (row == null) {
                break;
            }
            got.add(row);
        }
        putInt(ca, SQLERRD + 8, 4, got.size());
        return got;
    }

    /** The rowset's rows into the host variable tables: row j into element j of every column's table
     *  (`hosts[column][row]`, `indicators` null where none): the first row that fails to assign (-304 / -305) stops. */
    public static void intoRows(Field ca, List<Map<String, Object>> rows, String kinds, Field[][] hosts,
                                Field[][] indicators, Charset cs) {
        for (int j = 0; j < rows.size(); j++) {
            Field[] h = new Field[hosts.length];
            Field[] ind = indicators == null ? null : new Field[hosts.length];
            for (int c = 0; c < hosts.length; c++) {
                h[c] = hosts[c][j];
                if (ind != null) {
                    ind[c] = indicators[c] == null ? null : indicators[c][j];
                }
            }
            if (!into(ca, rows.get(j), kinds, h, new Field[hosts.length], ind, cs)) {
                return;
            }
        }
    }

    /** FETCH of a scroll cursor with an orientation (#4269; IBM Db2 for z/OS SQL Reference, FETCH): `orientation` is
     *  PRIOR, FIRST, LAST, CURRENT, ABSOLUTE (n a row number, a negative one counted from the last row) or RELATIVE
     *  (n rows from the current position). The cursor is insensitive: its rows are those OPEN read. A move off either
     *  end is +100 and leaves the cursor before the first row or after the last; FETCH CURRENT with no current row
     *  is refused (Db2 for z/OS answers +231, Db2 for LUW +100: not the same answer on both). */
    // [rule RT-SQL-SCROLL-FETCH]
    public static Map<String, Object> fetchScroll(Field ca, String at, String cursor, String orientation, long n,
                                                  Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return null;
        }
        List<Map<String, Object>> rows = OPEN.get(cursor);
        if (rows == null) {
            code(ca, -501, "24501", cs);
            return null;
        }
        long size = rows.size();
        long pos = POS.get(cursor);
        long target;
        switch (orientation) {
            case "NEXT": target = pos + 1; break;
            case "PRIOR": target = pos - 1; break;
            case "FIRST": target = 1; break;
            case "LAST": target = size; break;
            case "CURRENT":
                if (pos < 1 || pos > size) {
                    throw new UnsupportedOperationException("EXEC SQL FETCH CURRENT at " + at + ": the cursor has no "
                            + "current row (Db2 for z/OS +231, Db2 for LUW +100: not modelled)");
                }
                target = pos;
                break;
            case "ABSOLUTE": target = n > 0 ? n : n < 0 ? size + n + 1 : 0; break;
            case "RELATIVE": target = pos + n; break;
            default: throw new UnsupportedOperationException("EXEC SQL FETCH " + orientation + " not modelled");
        }
        return moveTo(ca, cursor, rows, Math.max(0, Math.min(target, size + 1)), cs);
    }

    /** FETCH BEFORE | AFTER of a scroll cursor (#4269; IBM Db2 for z/OS SQL Reference, FETCH): the cursor is parked before
     *  its first row (position 0) or after its last (n + 1); SQLCODE 0, no row returned, no host variable touched. The
     *  cursor then has no current row. -501 when it is not open. */
    // [rule RT-SQL-SCROLL-POSITION]
    public static void positionScroll(Field ca, String at, String cursor, String where, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        List<Map<String, Object>> rows = OPEN.get(cursor);
        if (rows == null) {
            code(ca, -501, "24501", cs);
            return;
        }
        switch (where) {
            case "BEFORE": POS.put(cursor, 0); break;
            case "AFTER": POS.put(cursor, rows.size() + 1); break;
            default: throw new UnsupportedOperationException("EXEC SQL FETCH " + where + " not modelled");
        }
        CURRENT.remove(cursor);
    }

    /** The cursor positioned at `target` (0 .. n + 1): its row, or null and +100 when that is off either end. */
    private static Map<String, Object> moveTo(Field ca, String cursor, List<Map<String, Object>> rows, long target,
                                              Charset cs) {
        int size = rows.size();
        int pos = (int) Math.max(0, Math.min(target, size + 1));
        POS.put(cursor, pos);
        if (pos < 1 || pos > size) {
            CURRENT.remove(cursor);  // before the first row or after the last: no current row
            code(ca, 100, "02000", cs);
            return null;
        }
        Map<String, Object> row = rows.get(pos - 1);
        CURRENT.put(cursor, row);
        return row;
    }

    /** A positioned UPDATE / DELETE (WHERE CURRENT OF cursor): the generated method, given the current row's id
     *  (GG_RID, which the cursor's query returns). -501 when the cursor is not open, -508 when it has no current row
     *  (before its first FETCH, or after +100). */
    // [rule RT-SQL-POSITIONED-UPDATE]
    public static void updateCurrent(Field ca, String cursor, java.util.function.Function<Object, Integer> statement,
                                     Charset cs) {
        updateCurrent(ca, null, cursor, statement, cs);
    }

    /** updateCurrent, the statement at `at` (#4173: a planned SQL fault there instead, the SQLCA set). */
    public static void updateCurrent(Field ca, String at, String cursor,
                                     java.util.function.Function<Object, Integer> statement, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        if (!OPEN.containsKey(cursor)) {
            code(ca, -501, "24501", cs);
            return;
        }
        Map<String, Object> row = CURRENT.get(cursor);
        if (row == null) {
            code(ca, -508, "24504", cs);
            return;
        }
        update(ca, () -> statement.apply(row.get("GG_RID")), false, cs);
    }

    /** CLOSE (-501 when it is not open). */
    public static void close(Field ca, String cursor, Charset cs) {
        close(ca, null, cursor, cs);
    }

    /** close, the CLOSE at `at` (#4173: a planned SQL fault there: the cursor left open, the SQLCA set). */
    public static void close(Field ca, String at, String cursor, Charset cs) {
        reset(ca, cs);
        if (injected(ca, at, cs)) {
            return;
        }
        CURRENT.remove(cursor);
        POS.remove(cursor);
        if (OPEN.remove(cursor) == null) {
            code(ca, -501, "24501", cs);
        }
    }

    /** A task's or a step's end: its cursors closed. */
    public static void closeAll() {
        OPEN.clear();
        POS.clear();
        CURRENT.clear();
        HOLD.clear();
    }
}
