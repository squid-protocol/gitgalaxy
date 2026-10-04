package devinadapter;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Runs a third-party port's own entry point under one of the harness's JVM environments (#3821): the default
 * locale and time zone are set first -- as the harness's generated test does for our ports -- and nothing else.
 *
 *   java -cp adapter:theirs.jar devinadapter.EnvLauncher LOCALE TZ MAIN-CLASS [their arguments...]
 *
 * The port's main class is called unmodified, with the remaining arguments exactly as given.
 */
public final class EnvLauncher {
    private EnvLauncher() {
    }

    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.forLanguageTag(args[0]));
        TimeZone.setDefault(TimeZone.getTimeZone(args[1]));
        Method main = Class.forName(args[2]).getMethod("main", String[].class);
        main.invoke(null, (Object) Arrays.copyOfRange(args, 3, args.length));
    }
}
