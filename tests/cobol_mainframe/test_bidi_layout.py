"""#3987: Arabic and Hebrew records hold their text in visual order; the generated Java hands out logical text.

A 3270 had no BiDi engine, so the host stored right-to-left characters left to right as the screen showed
them: `שלום` (logical, reading order) is the bytes of `םולש`. A browser takes a String as logical and lays it
out itself, so a field decoded as-is came out backwards. Under a visual page (cp420 / cp424 / cp864 / cp862,
or data.bidi_layout: visual) CobolRecords.text now returns logical order and putText stores visual order back;
a record read and re-written is byte-exact. Single-byte Latin pages are untouched.

The Java is compiled and run with the local JDK (IBM420 / IBM424 ship with it); without one it is skipped.
"""

import codecs
import re
import shutil
import subprocess

import pytest

from gitgalaxy.core.ebcdic_codecs import EBCDIC_CODE_PAGES, register
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, bidi_rules
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import COBOL_RECORDS_JAVA
from gitgalaxy.tools.cobol_to_java.java_target import (
    VISUAL_BIDI_PAGES,
    ConfigError,
    JavaTarget,
    target_from_dict,
    visual_bidi,
)

# (expression, expected output); H = IBM424 (EBCDIC Hebrew), A = IBM420 (EBCDIC Arabic), E = IBM037
AUTO = [
    # a visual record reads as logical text: the screen showed `םולש`, the word is `שלום`
    ('CobolRecords.text(bytesOf("םולש  ", H), 0, 6, H)', "שלום  "),
    # and logical text is stored visual, space-padded on the right as before (final mem, vav, lamed, shin)
    ('hex(put(6, "שלום", H))', "554654694040"),
    # a number keeps its digits left to right inside the Arabic run: `رصيد 125 دينار` shows as `رانيد 125 ديصر`
    ('hex(put(14, "رصيد 125 دينار", A))', "7556BDDC7340F1F2F54073DC8B75"),
    ('CobolRecords.text(fromHex("7556BDDC7340F1F2F54073DC8B75"), 0, 14, A)', "رصيد 125 دينار"),
    # a number at the left edge of a left-to-right screen reads first: the screen is the same either way
    ('CobolRecords.text(fromHex("F1F2F54073DC8B75"), 0, 8, A)', "125 رصيد"),
    ('hex(put(8, "رصيد 125", A))', "F1F2F54073DC8B75"),
    # Latin beside Hebrew stays where it is; the Hebrew run turns: NAME: <first> <last>
    ('CobolRecords.text(bytesOf("NAME: ןהכ דוד", H), 0, 13, H)', "NAME: דוד כהן"),
    # a bracket in a right-to-left run is mirrored, as the screen drew it
    ('hex(put(6, "(שלום)", H))', "4D55465469" + "5D"),
    # read and re-written, a visual record is byte-exact -- shaped Arabic forms included (0x59 is ﺑ, initial beh)
    ('hex(put(13, CobolRecords.text(bytesOf("NAME: ןהכ דוד", H), 0, 13, H), H))', "D5C1D4C57A40" + "57455340444644"),
    ('hex(put(8, CobolRecords.text(fromHex("F1F2F540BB5958BB"), 0, 8, A), A))', "F1F2F540BB5958BB"),
    # no right-to-left character: the bytes and the String are as before
    ('hex(put(6, "ABC 12", H))', "C1C2C340F1F2"),
    ('hex(put(6, "ABC 12", E))', "C1C2C340F1F2"),
    # which pages are visual (auto)
    (
        'CobolRecords.visualOrder(H) + " " + CobolRecords.visualOrder(A) + " " '
        '+ CobolRecords.visualOrder(Charset.forName("IBM864")) + " " + CobolRecords.visualOrder(Charset.forName("IBM862"))',
        "true true true true",
    ),
    (
        'CobolRecords.visualOrder(E) + " " + CobolRecords.visualOrder(Charset.forName("windows-1255")) + " " '
        '+ CobolRecords.visualOrder(Charset.forName("ISO-8859-1")) + " " + CobolRecords.visualOrder(null)',
        "false false false false",
    ),
    # a VSAM key sorts by the bytes the mainframe holds -- the visual ones
    ('CobolRecords.sortKey("שלום", "IBM424")', "55465469"),
    ('String.valueOf(CobolRecords.logical(null)) + " " + CobolRecords.visual("")', "null "),
]
# data.bidi_layout overrides the page: logical keeps visual pages' bytes as they are, visual_ltr turns any page
LOGICAL = [
    ('CobolRecords.text(bytesOf("םולש", H), 0, 4, H)', "םולש"),
    ("String.valueOf(CobolRecords.visualOrder(H))", "false"),
]
VISUAL = [
    ('CobolRecords.text(bytesOf("םולש", W), 0, 4, W)', "שלום"),
    ("String.valueOf(CobolRecords.visualOrder(E))", "true"),
]
# a screen-reverse terminal (visual_rtl): the first byte is the screen's rightmost character, so Hebrew is
# stored in reading order and a number reversed -- `רחוב הרצל 12` is the bytes of `רחוב הרצל 21`
VISUAL_RTL = [
    ('hex(put(14, "רחוב הרצל 12", H))', "68484642404568665440F2F14040"),
    ('CobolRecords.text(fromHex("68484642404568665440F2F14040"), 0, 14, H)', "רחוב הרצל 12  "),
    # a Latin label is reversed too, and keeps its place at the screen's left
    ('CobolRecords.logical(CobolRecords.visual("NAME: דוד"))', "NAME: דוד"),
    ('CobolRecords.visual("ABC")', "ABC"),  # nothing right-to-left: untouched
]

PROBE = """package t;
import java.nio.charset.Charset;
public class Probe {
    static final Charset H = Charset.forName("IBM424");
    static final Charset A = Charset.forName("IBM420");
    static final Charset E = Charset.forName("IBM037");
    static final Charset W = Charset.forName("windows-1255");
    static byte[] bytesOf(String s, Charset cs) { return s.getBytes(cs); }
    static byte[] fromHex(String h) {
        byte[] b = new byte[h.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        return b;
    }
    static byte[] put(int width, String value, Charset cs) {
        byte[] rec = CobolRecords.blank(width, cs);
        CobolRecords.putText(rec, 0, width, value, cs);
        return rec;
    }
    static String hex(byte[] b) {
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format("%02X", x));
        return s.toString();
    }
    public static void main(String[] a) throws Exception {
        java.io.PrintStream out = new java.io.PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, "UTF-8");
__LINES__
    }
}
"""


def _run(tmp_path, layout, cases):
    pkg = tmp_path / layout / "t"
    pkg.mkdir(parents=True)
    source = COBOL_RECORDS_JAVA.replace("__PACKAGE__", "t").replace("__BIDI_LAYOUT__", layout)
    source = source.replace("__POSITIVE__", "{ABCDEFGHI").replace("__NEGATIVE__", "}JKLMNOPQR")
    (pkg / "CobolRecords.java").write_text(source, encoding="utf-8")
    lines = "\n".join(f"        out.println({expr});" for expr, _ in cases)
    (pkg / "Probe.java").write_text(PROBE.replace("__LINES__", lines), encoding="utf-8")
    out = tmp_path / layout / "out"
    subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(out), str(pkg / "CobolRecords.java"),
                    str(pkg / "Probe.java")], check=True)  # fmt: skip
    run = subprocess.run(["java", "-Dstdout.encoding=UTF-8", "-cp", str(out), "t.Probe"],
                         capture_output=True, encoding="utf-8", check=True)  # fmt: skip
    got = run.stdout.splitlines()
    assert [(expr, g) for (expr, _), g in zip(cases, got, strict=False)] == [
        (expr, want) for expr, want in cases
    ]  # reason: length may differ


@pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")
@pytest.mark.parametrize("layout, cases", [("auto", AUTO), ("logical", LOGICAL), ("visual_ltr", VISUAL),
                                           ("visual_rtl", VISUAL_RTL)])  # fmt: skip
def test_visual_records_read_as_logical_text(tmp_path, layout, cases):
    _run(tmp_path, layout, cases)


def test_the_java_runtime_and_the_config_name_the_same_visual_pages():
    (pages,) = re.findall(r"VISUAL_BIDI_PAGES = Set\.of\(([^)]*)\)", COBOL_RECORDS_JAVA)
    assert tuple(p.strip(' "') for p in pages.split(",")) == VISUAL_BIDI_PAGES


def test_records_source_bakes_in_the_declared_layout():
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

    for layout in ("auto", "logical", "visual_ltr", "visual_rtl"):
        target = target_from_dict({"data": {"record_charset": "cp420", "bidi_layout": layout}})
        src = RepositoryForge({}, {}, "com.x", target).records_source(needed=True)
        assert f'BIDI_LAYOUT = "{layout}";' in src and '"IBM420";' in src


def test_bidi_layout_is_checked():
    assert JavaTarget().data.bidi_layout == "auto"
    with pytest.raises(ConfigError, match=r"data\.bidi_layout 'rtl' is not supported"):
        target_from_dict({"data": {"bidi_layout": "rtl"}})
    with pytest.raises(ConfigError, match=r"data\.bidi_layout 'visual' is not supported"):
        target_from_dict({"data": {"bidi_layout": "visual"}})  # which side of the screen is the first byte?


@pytest.mark.parametrize("data, visual", [
    (None, False), ({}, False), ({"record_charset": "cp037"}, False), ({"record_charset": "cp1256"}, False),
    ({"record_charset": "cp420"}, True), ({"record_charset": "cp424"}, True), ({"record_charset": "cp864"}, True),
    ({"record_charset": "cp862"}, True), ({"record_charset": "cp420", "bidi_layout": "logical"}, False),
    ({"record_charset": "latin-1", "bidi_layout": "visual_ltr"}, True),
    ({"record_charset": "cp037", "bidi_layout": "visual_rtl"}, True),
])  # fmt: skip
def test_which_estates_are_visual_and_get_the_porting_rule(data, visual):
    assert visual_bidi(data) is visual
    rules = bidi_rules(data)
    assert bool(rules) is visual
    if visual:
        (rule,) = rules
        assert "VISUAL order" in rule and "CobolRecords.visual" in rule and "CobolRecords.logical" in rule
        assert "#3987" in rule
    assert not any("#3987" in r for r in PORTING_RULES)  # only where it applies


def test_cp420_is_a_known_ebcdic_page():
    """`record_charset: cp420` (and `code_page: cp420`) validated: Python ships cp424 but not cp420."""
    register()
    assert codecs.lookup("cp420").name == "cp420" and {"cp420", "cp424"} <= EBCDIC_CODE_PAGES
    assert "رصيد 125".encode("cp420").hex().upper() == "758BDC7340F1F2F5"
    assert bytes.fromhex("BB5958").decode("cp420") == "مﺑب"  # base and shaped forms, as IBM420
    with pytest.raises(UnicodeDecodeError):
        b"\x53".decode("cp420")  # a byte the JDK leaves unmapped is not guessed
    target = target_from_dict({"data": {"code_page": "cp420", "record_charset": "cp420"}})
    assert target.data.record_charset == "cp420"
