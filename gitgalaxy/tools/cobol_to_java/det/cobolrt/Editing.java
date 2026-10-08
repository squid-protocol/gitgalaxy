package __PACKAGE__.cobolrt;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** #3827: a number rendered through a numeric-edited PICTURE as COBOL renders it -- Z / * zero suppression,
 *  9, the `.` and `,` insertion characters (which one is the decimal point follows DECIMAL-POINT IS COMMA),
 *  a trailing or leading fixed - / +, CR / DB, the currency sign, B, 0 and /. #3933: floating insertion
 *  strings (`$$$,$$9.99`, `+++9`, `---9`, `III,II9.99`) float the sign or currency string to just left of
 *  the first significant digit. `currency` is the program's CURRENCY SIGN string ('EUR ', 'INR ', 'Rs'):
 *  it replaces `$` or the declared PICTURE SYMBOL (any character that is no editing symbol: U, I, K, or a
 *  one-character sign); null keeps the PICTURE's own character. Porting rules require it for edited fields. */
final class Editing {
    private Editing() {}

    /** The PICTURE's editing symbols; any other character is its currency symbol (#3933). */
    private static final String EDITING = "9Z*.,+-CRDBV0/$";

    static String format(String pic, BigDecimal value, boolean decimalComma, String currency) {
        pic = expand(pic);
        if (value == null) return pic.replaceAll("[9Z*]", "0");
        // #3933: the currency symbol -- `$`, or the declared sign / PICTURE SYMBOL -- stands for the whole
        // currency string; it is read as `$` below
        char symbol = '$';
        for (int i = 0; i < pic.length(); i++) {
            if (EDITING.indexOf(pic.charAt(i)) == -1) {
                symbol = pic.charAt(i);
                break;
            }
        }
        String cur = currency != null ? currency : String.valueOf(symbol);
        pic = pic.replace(symbol, '$');
        boolean neg = value.compareTo(BigDecimal.ZERO) < 0;
        BigDecimal abs = value.abs();

        int digits = 0;
        int scale = 0;
        char decChar = decimalComma ? ',' : '.';

        int decIdx = pic.indexOf('V');
        if (decIdx == -1) decIdx = pic.indexOf(decChar);
        if (decIdx == -1) decIdx = pic.length();

        // #3933: a floating insertion string -- two or more of `$`, `+` or `-`, with only the insertion
        // characters , . B 0 / between them (IBM Enterprise COBOL Language Reference, PICTURE clause,
        // "Floating insertion editing"). Its first symbol is the sign / currency position only; each other
        // one is a digit position.
        char floating = 0;
        int floatStart = -1;
        int floatEnd = -1;
        for (char f : new char[] {'$', '+', '-'}) {
            int a = pic.indexOf(f);
            if (a == -1) continue;
            int b = a;
            int n = 1;
            for (int i = a + 1; i < pic.length(); i++) {
                char c = pic.charAt(i);
                if (c == f) {
                    b = i;
                    n++;
                } else if (",.B0/".indexOf(c) == -1) {
                    break;
                }
            }
            if (n >= 2) {
                floating = f;
                floatStart = a;
                floatEnd = b;
                break;
            }
        }

        boolean allFloating = floating != 0;
        for (int i = 0; i < pic.length(); i++) {
            char c = pic.charAt(i);
            boolean floatDigit = floating != 0 && c == floating && i > floatStart && i <= floatEnd;
            if (c == '9' || c == 'Z' || c == '*' || floatDigit) {
                digits++;
                if (i > decIdx) scale++;
                if (!floatDigit) allFloating = false;
            }
        }

        String raw = abs.setScale(scale, RoundingMode.HALF_UP).toPlainString().replace(".", "");
        while (raw.length() < digits) raw = "0" + raw;
        if (raw.length() > digits) raw = raw.substring(raw.length() - digits);

        // one output string per PICTURE position: a floating symbol is placed after the positions it passes
        String[] cells = new String[pic.length()];
        String floatText = floating == '$' ? cur : floating == '+' ? (neg ? "-" : "+") : (neg ? "-" : " ");
        boolean floatSuppression = floating != 0;
        int floatAt = -1;  // the last position blanked in the floating string: where the symbol goes
        int rawIdx = 0;
        boolean zeroSuppression = true;

        for (int i = 0; i < pic.length(); i++) {
            char c = pic.charAt(i);
            if (floatSuppression && i > floatEnd) {
                // every digit of the floating string was a leading zero: the symbol takes its last position
                cells[floatAt] = floatText;
                floatSuppression = false;
            }
            if (floating != 0 && i >= floatStart && i <= floatEnd) {
                if (i == floatStart) {
                    cells[i] = " ";
                    floatAt = i;
                } else if (c == floating) {
                    char d = raw.charAt(rawIdx++);
                    if (floatSuppression && d == '0' && i < decIdx) {
                        cells[i] = " ";
                        floatAt = i;
                    } else {
                        if (floatSuppression) cells[floatAt] = floatText;
                        floatSuppression = false;
                        zeroSuppression = false;
                        cells[i] = String.valueOf(d);
                    }
                } else if (c == decChar && i == decIdx) {
                    // the decimal point ends the suppression: the symbol goes just left of it (`$.05`)
                    if (floatSuppression) cells[floatAt] = floatText;
                    floatSuppression = false;
                    zeroSuppression = false;
                    cells[i] = String.valueOf(c);
                } else if (floatSuppression) {
                    // an insertion character before the first significant digit is blanked, and floated over
                    cells[i] = " ";
                    floatAt = i;
                } else {
                    cells[i] = c == 'B' ? " " : String.valueOf(c);
                }
                continue;
            }
            if (c == '9' || c == 'Z' || c == '*') {
                char d = raw.charAt(rawIdx++);
                if (c == 'Z') {
                    if (d == '0' && zeroSuppression) cells[i] = " ";
                    else { cells[i] = String.valueOf(d); zeroSuppression = false; }
                } else if (c == '*') {
                    if (d == '0' && zeroSuppression) cells[i] = "*";
                    else { cells[i] = String.valueOf(d); zeroSuppression = false; }
                } else {
                    cells[i] = String.valueOf(d);
                    zeroSuppression = false;
                }
            } else if (c == '.' || c == ',') {
                if (zeroSuppression && (pic.indexOf('Z') != -1 || pic.indexOf('*') != -1)) {
                    if (c == decChar) {
                        cells[i] = String.valueOf(c);
                        zeroSuppression = false; // Decimal point cancels zero suppression
                    } else {
                        cells[i] = pic.indexOf('*') != -1 ? "*" : " ";
                    }
                } else {
                    cells[i] = String.valueOf(c);
                }
            } else if (c == '-') {
                cells[i] = neg ? "-" : " ";
            } else if (c == '+') {
                cells[i] = neg ? "-" : "+";
            } else if (c == 'C' && i + 1 < pic.length() && pic.charAt(i + 1) == 'R') {
                cells[i] = neg ? "CR" : "  ";
                cells[++i] = "";
            } else if (c == 'D' && i + 1 < pic.length() && pic.charAt(i + 1) == 'B') {
                cells[i] = neg ? "DB" : "  ";
                cells[++i] = "";
            } else if (c == '$') {
                cells[i] = cur;
            } else if (c == 'B') {
                cells[i] = " ";
            } else if (c == '0' || c == '/') {
                if (zeroSuppression) cells[i] = pic.indexOf('*') != -1 ? "*" : " ";
                else cells[i] = String.valueOf(c);
            } else if (c == 'V') {
                cells[i] = ""; // Implicit, do nothing
            } else {
                cells[i] = String.valueOf(c);
            }
        }
        if (floatSuppression) cells[floatAt] = floatText;
        String out = String.join("", cells);
        // IBM: when every digit position is in the floating string, a zero value edits to all spaces
        if (allFloating && raw.chars().allMatch(ch -> ch == '0')) return " ".repeat(out.length());
        return out;
    }

    /** {integer digit positions, decimal digit positions} of an edit PICTURE (floating insertion included). */
    static int[] shape(String pic) {
        return shape(pic, false);
    }

    /** As shape(pic); `decimalComma` (#4462: DECIMAL-POINT IS COMMA): `,` is the PICTURE's decimal point. */
    static int[] shape(String pic, boolean decimalComma) {
        pic = expand(pic);
        char symbol = '$';
        for (int i = 0; i < pic.length(); i++) {
            if (EDITING.indexOf(pic.charAt(i)) == -1) { symbol = pic.charAt(i); break; }
        }
        pic = pic.replace(symbol, '$');
        int decIdx = pic.indexOf('V');
        if (decIdx == -1) decIdx = pic.indexOf(decimalComma ? ',' : '.');
        if (decIdx == -1) decIdx = pic.length();
        char floating = 0;
        int floatStart = -1, floatEnd = -1;
        for (char f : new char[] {'$', '+', '-'}) {
            int a = pic.indexOf(f);
            if (a == -1) continue;
            int b = a, n = 1;
            for (int i = a + 1; i < pic.length(); i++) {
                char c = pic.charAt(i);
                if (c == f) { b = i; n++; } else if (",.B0/".indexOf(c) == -1) break;
            }
            if (n >= 2) { floating = f; floatStart = a; floatEnd = b; break; }
        }
        int ints = 0, decs = 0;
        for (int i = 0; i < pic.length(); i++) {
            char c = pic.charAt(i);
            boolean floatDigit = floating != 0 && c == floating && i > floatStart && i <= floatEnd;
            if (c == '9' || c == 'Z' || c == '*' || floatDigit) {
                if (i > decIdx) decs++; else ints++;
            }
        }
        return new int[] {ints, decs};
    }

    /** The edited text of a PICTURE (`ZZ9`, `X(3)B99`) with repetition expanded, upper case, S and P kept out. */
    static String expandPic(String pic) { return expand(pic); }

    /** `Z(3)9(2)` -> `ZZZ99`, upper case, without S and P (a sign and scaling have no display position). */
    private static String expand(String pic) {
        StringBuilder ex = new StringBuilder();
        for (int i = 0; i < pic.length(); i++) {
            char c = Character.toUpperCase(pic.charAt(i));
            if (c == '(' && ex.length() > 0) {
                int j = pic.indexOf(')', i);
                int n = Integer.parseInt(pic.substring(i + 1, j).trim());
                char r = ex.charAt(ex.length() - 1);
                for (int k = 1; k < n; k++) ex.append(r);
                i = j;
            } else if (c != 'S' && c != 'P') {
                ex.append(c);
            }
        }
        return ex.toString();
    }
}
