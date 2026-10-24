"""#5082 (register X54): RECEIVE MAP into a DFHMDF field coded JUSTIFY=([LEFT|RIGHT][,BLANK|ZERO]) (IBM CICS TS 6.x, DFHMDF:
"the type of justification (RIGHT or LEFT) and the fill character (BLANK or ZERO) for input data"; LEFT and BLANK the defaults).

Three layers, each over the whole operand class: the forge writes the operand into `ScreenField.justify`; `Cics.receive_map`
reads it back off the screen and calls `DetJustify.place` only for a field that has one (every other field keeps
`DetCics.typed`, so no existing port moves); and the runtime (DetCics, compiled and run) places the text.
"""

from __future__ import annotations

import itertools
import os
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java import cobol_to_java_screen_forge as F  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

_OPERANDS = [  # (the DFHMDF `attributes` text the BMS channel keeps, ScreenField.justify)
    (None, None),
    ("COLOR=BLUE", None),
    ("JUSTIFY=RIGHT", "RIGHT"),
    ("JUSTIFY=LEFT", "LEFT"),
    ("JUSTIFY=(RIGHT,ZERO)", "RIGHT,ZERO"),
    ("JUSTIFY=(RIGHT,BLANK)", "RIGHT,BLANK"),
    ("JUSTIFY=(LEFT,ZERO)", "LEFT,ZERO"),
    ("JUSTIFY=(LEFT,BLANK)", "LEFT,BLANK"),
    ("JUSTIFY=(RIGHT)", "RIGHT"),
    ("JUSTIFY=(,ZERO)", ",ZERO"),
    ("JUSTIFY=( RIGHT , ZERO )", "RIGHT,ZERO"),
    ("justify=(right,zero)", "RIGHT,ZERO"),
    ("COLOR=RED,JUSTIFY=(RIGHT,ZERO),HILIGHT=UNDERLINE", "RIGHT,ZERO"),
    ("GRPNAME=G1,JUSTIFY=RIGHT", "RIGHT"),
    ("HILIGHT=REVERSE,JUSTIFY=LEFT", "LEFT"),
    ("XJUSTIFY=RIGHT", None),  # another operand whose name ends in JUSTIFY
]


@pytest.mark.parametrize(("attributes", "want"), _OPERANDS)
def test_the_forge_reads_the_operand_in_every_form(attributes, want):
    assert F._justify({"attributes": attributes}) == want


def test_the_screen_record_carries_justify_last():
    src = Path(F.__file__).read_text(encoding="utf-8")
    assert "int occurs,\n                          String justify)" in src


_SCREEN = """class PcScreen {
    public static final List<ScreenField> LAYOUT = List.of(
            new ScreenField(null, 1, 1, 6, false, false, false, false, false, "Amt :", null, 1, null),
            new ScreenField("AMT", 2, 10, 8, true, true, false, false, true, null, null, 1, "RIGHT,ZERO"),
            new ScreenField("NAME", 3, 10, 8, true, false, false, false, false, null, "BLUE", 1, null),
            new ScreenField("CODE", 4, 10, 4, true, false, false, false, false, null, null, 1, "LEFT,ZERO"));
    public static PcScreen fromValues(Map<String, String> values) {
        values.put("AMT", x); values.put("NAME", x); values.put("CODE", x);
    }
}
"""


def _cics(tmp_path):
    d = tmp_path / "src/main/java/x/dto/screen"
    d.mkdir(parents=True)
    (d / "PcScreen.java").write_text(
        'class PcScreen { public static final String MAP = "PCM";\n  public static final String MAPSET = "PCMS"; }\n'
        + _SCREEN.replace("class PcScreen {", "// layout\nclass PcLayout {"),
        encoding="utf-8",
    )
    c = C.Cics.__new__(C.Cics)
    c.gp = C.Generated(tmp_path, "")
    return c


def test_translator_reads_justify_off_the_layout_by_field_name(tmp_path):
    c = _cics(tmp_path)
    assert c.gp.screen_justify("PcScreen") == {"AMT": "RIGHT,ZERO", "CODE": "LEFT,ZERO"}


def test_an_old_screen_without_the_component_has_no_justify(tmp_path):
    d = tmp_path / "src/main/java/x/dto/screen"
    d.mkdir(parents=True)
    (d / "OldScreen.java").write_text(
        'new ScreenField("AMT", 2, 10, 8, true, true, false, false, true, null, null, 1),\n', encoding="utf-8"
    )
    gp = C.Generated(tmp_path, "")
    assert gp.screen_justify("OldScreen") == {}


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _expected(text: str, width: int, justify: str) -> tuple[str, int]:
    """IBM's rule as modelled in X54, written independently of the Java: (the field's bytes, <f>L)."""
    typed = text.rstrip(" ")
    fill = "0" if "ZERO" in justify else " "
    kept = typed[-width:] if "RIGHT" in justify else typed[:width]
    body = kept.rjust(width, fill) if "RIGHT" in justify else kept.ljust(width, fill)
    return body, len(typed)


_JUSTIFIES = ["RIGHT", "RIGHT,ZERO", "RIGHT,BLANK", "LEFT", "LEFT,ZERO", "LEFT,BLANK", ",ZERO", ",BLANK"]
_TEXTS = ["", "7", "42", "1234", "12345", "123456789", "ab  ", "  ab", "0", "00"]
_WIDTHS = [1, 4, 8]


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_places_the_text_for_the_whole_operand_class(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    cases = list(itertools.product(_JUSTIFIES, _WIDTHS, _TEXTS))
    rows = ",\n".join(f'        {{"{j}", "{w}", "{t}"}}' for j, w, t in cases)
    files["Main.java"] = (
        """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.Storage;
import t.cobolrt.cics.DetJustify;
public class Main {
    static Field rec(int n) { return Field.alphanumeric(new Storage(n), 0, n, false); }
    public static void main(String[] a) {
        Charset cs = Charset.forName("ISO-8859-1");
        String[][] cases = {
"""
        + rows
        + """
        };
        for (String[] c : cases) {
            int w = Integer.parseInt(c[1]);
            Field in = rec(w), len = Field.zoned(new Storage(3), 0, 3, 0, false, false, false);
            DetJustify.place(in, len, c[2], cs, c[0]);
            System.out.println("[" + new String(in.storage().bytes, cs) + "] " + Cobol_num(len, cs));
        }
    }
    static String Cobol_num(Field f, Charset cs) { return t.cobolrt.Cobol.num(f, cs).toBigInteger().toString(); }
}
"""
    )
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"], capture_output=True,  # noqa: S603
                         text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    want = []
    for j, w, t in cases:
        body, n = _expected(t, w, j)
        want.append(f"[{body}] {n}")
    assert out == want


# ---- #5116 (X54): the NUM default, and the three implementations agreeing -----------------------------------------
_NUM_FIELDS = [  # (the BMS row's attrb, its `attributes`, the effective justify)
    ("UNPROT,NUM", None, "RIGHT,ZERO"),
    ("UNPROT,NUM,IC", "COLOR=RED", "RIGHT,ZERO"),
    ("NUM", "XJUSTIFY=RIGHT", "RIGHT,ZERO"),
    ("UNPROT,NUM", "JUSTIFY=(LEFT)", "LEFT"),  # coded: LEFT / BLANK for what it leaves out, NUM or not
    ("UNPROT,NUM", "JUSTIFY=(BLANK)", "BLANK"),
    ("UNPROT,NUM", "JUSTIFY=(LEFT,BLANK)", "LEFT,BLANK"),
    ("UNPROT,NUM", "JUSTIFY=(RIGHT,BLANK)", "RIGHT,BLANK"),
    ("UNPROT", None, None),
    (None, None, None),  # no ATTRB: ASKIP,NORM
    ("UNPROT,NORM", "COLOR=BLUE", None),
    ("UNPROT,NUMX", None, None),  # a different attribute word
]


@pytest.mark.parametrize(("attrb", "attributes", "want"), _NUM_FIELDS)
def test_a_num_field_with_no_justify_is_right_zero_5116(attrb, attributes, want):
    assert F._justify({"attrb": attrb, "attributes": attributes}) == want


@pytest.mark.parametrize(("attrb", "attributes", "_want"), _NUM_FIELDS)
@pytest.mark.parametrize("text", ["", "7", "42", "12345", "123456789", "ab  "])
def test_forge_oracle_and_crucible_runner_place_alike_5116(attrb, attributes, _want, text):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import cics_bms
    import equivalence_cics as ec

    width = 6
    row = {"attrb": attrb, "attributes": attributes}
    jf = F._justify(row)
    j = (attributes or "").upper()
    coded = []
    if "JUSTIFY=" in j and "XJUSTIFY" not in j:
        coded = [w for w in j.split("JUSTIFY=")[1].strip("()").replace(")", "").split(",") if w]
    field = cics_bms.BmsField(name="F", length=width, attrb=attrb.split(",") if attrb else None, initial=None,
                              color=None, hilight=None, justify=coded, ic=False)  # fmt: skip
    oracle = ec.justified(text, width, jf) if jf else text.rstrip(" ").ljust(width)[:width]
    assert cics_bms.received_value(field, text.rstrip(" ")) == oracle


# #5116 (c:5781930a): JUSTIFY is an input-only DFHMDF operand, so the SEND MAP path must not apply it.
_IBM_JUSTIFY_SENTENCE = "specifies the field justifications for input operations."
_X54 = Path(__file__).resolve().parents[2] / "docs/language_status/register/X54.md"


def test_det_send_map_never_justifies_5116():
    import inspect

    src = inspect.getsource(C.Cics.send_map).lower()
    assert "justify" not in src
    assert "detjustify" not in src


def test_the_oracle_output_side_never_justifies_5116():
    import inspect

    import equivalence_cics as E

    assert "justify" in inspect.signature(E.map_input).parameters
    assert "justif" not in inspect.getsource(E.compare_events).lower()


def test_x54_records_send_map_justify_not_applicable_5116():
    text = " ".join(_X54.read_text(encoding="utf-8").split())
    assert _IBM_JUSTIFY_SENTENCE in text
    assert "JUSTIFY on SEND MAP: not applicable" in text
    assert "test_det_send_map_never_justifies_5116" in text


# #5116: PICIN / PICOUT are compile-time pictures on the symbolic map; IBM gives BMS no run-time conversion.
_IBM_PICIN_SENTENCE = (
    "the validity of the input data is not checked by BMS or the high-level language when the map is used"
)
_IBM_PICOUT_SENTENCE = (
    "is like PICIN, except that a picture to be applied to an output field in the OUT or INOUT map is generated."
)


def test_det_receive_and_send_map_never_read_a_picture_5116():
    import inspect

    for fn in (C.Cics.receive_map, C.Cics.send_map):
        src = inspect.getsource(fn).lower()
        assert "picin" not in src
        assert "picout" not in src


def test_x54_records_picin_picout_no_runtime_conversion_5116():
    text = " ".join(_X54.read_text(encoding="utf-8").split())
    assert _IBM_PICIN_SENTENCE in text
    assert _IBM_PICOUT_SENTENCE in text
    assert "PICIN / PICOUT: out of scope, by name" in text
    assert "test_det_receive_and_send_map_never_read_a_picture_5116" in text


# #5116 (c:9d9ee016): the register's citations were re-read against the live DFHMDF page and the result recorded.
def test_x54_records_the_live_page_reread_5116():
    text = " ".join(_X54.read_text(encoding="utf-8").split())
    assert "Re-read 2026-10-23 (#5116, c:9d9ee016" in text
    assert "If JUSTIFY is omitted, but the NUM attribute is specified, RIGHT and ZERO are assumed." in text
    assert "If JUSTIFY is omitted, but attributes other than NUM are specified, LEFT and BLANK are assumed." in text
    assert (
        "The ATTRB operand specified on the first field of the group applies to all of the fields within the group."
        in text
    )
    assert "per-occurrence JUSTIFY stays frontier" in text


def test_x54_does_not_attribute_per_occurrence_justify_to_ibm_5116():
    text = " ".join(_X54.read_text(encoding="utf-8").split())
    assert "IBM gives every occurrence" not in text
    assert "no sentence joins JUSTIFY with OCCURS, GRPNAME" in text
    assert "test_bms_occurs_grpname_census_5116.py" in text
