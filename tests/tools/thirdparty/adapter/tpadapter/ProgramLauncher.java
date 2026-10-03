package tpadapter;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.util.Arrays;
import java.util.Locale;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Runs one of a third-party port's program classes that has no main method of its own: the class is constructed
 * with its documented String arguments (file paths, a PARM) and its public execute() is called -- what the
 * port's own unit tests do. Nothing of the port is changed.
 *
 *   java -cp adapter:theirs ... tpadapter.ProgramLauncher LOCALE TZ LOGBACK-XML CLASS [constructor args...]
 *
 * Before the class loads: the JVM default locale and time zone of a harness environment (#3821), and logback
 * pointed at a message-only layout on stdout, so the port's log lines (its DISPLAY statements) read as a job log.
 * An exception whose message carries "ABCODE n" (the port's own 9999-ABEND-PROGRAM) is reported on stderr as
 * "USER ABEND Unnnn" and exit status 12; any other uncaught exception is printed and exits 16.
 */
public final class ProgramLauncher {
    private static final Pattern ABCODE = Pattern.compile("ABCODE\\s*(\\d+)");

    private ProgramLauncher() {
    }

    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.forLanguageTag(args[0]));
        TimeZone.setDefault(TimeZone.getTimeZone(args[1]));
        System.setProperty("logback.configurationFile", args[2]);
        String[] ctorArgs = Arrays.copyOfRange(args, 4, args.length);
        Class<?> type = Class.forName(args[3]);
        Constructor<?> ctor = null;
        for (Constructor<?> c : type.getConstructors()) {
            if (c.getParameterCount() == ctorArgs.length
                    && Arrays.stream(c.getParameterTypes()).allMatch(t -> t == String.class)) {
                ctor = c;
            }
        }
        if (ctor == null) {
            throw new IllegalArgumentException(type + ": no public constructor of " + ctorArgs.length + " Strings");
        }
        try {
            Object program = ctor.newInstance((Object[]) ctorArgs);
            type.getMethod("execute").invoke(program);
        } catch (InvocationTargetException e) {
            Throwable cause = e.getCause();
            Matcher m = ABCODE.matcher(String.valueOf(cause.getMessage()));
            System.out.flush();
            if (m.find()) {
                System.err.println("USER ABEND U" + m.group(1));
                System.exit(12);
            }
            cause.printStackTrace();
            System.exit(16);
        }
        System.out.flush();
    }
}
