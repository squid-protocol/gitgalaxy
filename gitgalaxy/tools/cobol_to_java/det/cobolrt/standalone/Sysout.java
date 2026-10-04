package __PACKAGE__.cobolrt.standalone;

/** DISPLAY for a project the generator gave no batch package (a CICS-only estate): the operands' texts, one line. */
public final class Sysout {
    private Sysout() {
    }

    public static void display(Object... operands) {
        System.out.println(join(operands));
    }

    public static void displayNoAdvancing(Object... operands) {
        System.out.print(join(operands));
    }

    private static String join(Object... operands) {
        StringBuilder b = new StringBuilder();
        for (Object o : operands) {
            b.append(o);
        }
        return b.toString();
    }
}
