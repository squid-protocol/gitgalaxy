"""#5076: SEND MAP / RECEIVE MAP over a map whose DFHMDF repeats (OCCURS=n).

The screen forge writes a repeated field's value as `values.put("NAME" + "." + (i + 1), ...)`, which the translator's
reader of the screen class did not match: SEND MAP left every occurrence out of the port's screen, silently. Whole
operand class: no OCCURS, OCCURS=n, an OCCURS beside a JUSTIFY field, and an OCCURS=1 (not a repeat).
"""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

_SCREEN = """class LstScreen {
    public static final List<ScreenField> LAYOUT = List.of(
            new ScreenField(null, 1, 1, 6, false, false, false, false, false, "Rows", null, 1, null),
            new ScreenField("HEAD", 2, 1, 8, true, true, false, false, true, null, null, 1, "RIGHT,ZERO"),
            new ScreenField("ROW", 3, 1, 79, false, false, false, false, false, null, "NEUTRAL", 10, null),
            new ScreenField("PAIR", 14, 1, 5, false, false, false, false, false, null, null, 2, "LEFT"),
            new ScreenField("ONE", 20, 1, 5, false, false, false, false, false, null, null, 1, null),
            new ScreenField("MSG", 23, 1, 79, false, false, true, false, false, null, "YELLOW", 1, null));
    public Map<String, String> screenValues() {
        values.put("HEAD", head);
        if (row != null) {
            for (int i = 0; i < row.size(); i++) {
                values.put("ROW" + "." + (i + 1), row.get(i));
            }
        }
        if (pair != null) {
            for (int i = 0; i < pair.size(); i++) {
                values.put("PAIR" + "." + (i + 1), pair.get(i));
            }
        }
        values.put("ONE", one);
        values.put("MSG", msg);
    }
}
"""


def _gp(tmp_path):
    d = tmp_path / "src/main/java/x/dto/screen"
    d.mkdir(parents=True)
    (d / "LstScreen.java").write_text(_SCREEN, encoding="utf-8")
    return C.Generated(tmp_path, "")


def test_every_field_is_listed_a_repeated_one_too(tmp_path):
    assert _gp(tmp_path).screen_fields("LstScreen") == ["HEAD", "ROW", "PAIR", "ONE", "MSG"]


def test_the_repeats_are_read_off_the_layout(tmp_path):
    assert _gp(tmp_path).screen_occurs("LstScreen") == {"ROW": 10, "PAIR": 2}  # OCCURS=1 and no OCCURS: absent


def test_a_screen_without_repeats_has_none(tmp_path):
    d = tmp_path / "src/main/java/x/dto/screen"
    d.mkdir(parents=True)
    (d / "OldScreen.java").write_text(
        'new ScreenField("AMT", 2, 10, 8, true, true, false, false, true, null, null, 1, null));\n values.put("AMT", a);\n',
        encoding="utf-8",
    )
    gp = C.Generated(tmp_path, "")
    assert gp.screen_occurs("OldScreen") == {} and gp.screen_fields("OldScreen") == ["AMT"]


def test_a_slot_per_occurrence(tmp_path):
    c = C.Cics.__new__(C.Cics)
    c.gp = _gp(tmp_path)
    slots = c.screen_slots("LstScreen")
    assert slots[0] == ("HEAD", None) and slots[1] == ("ROW", 1) and slots[10] == ("ROW", 10)
    assert slots[11:13] == [("PAIR", 1), ("PAIR", 2)] and slots[-2:] == [("ONE", None), ("MSG", None)]
    assert len(slots) == 1 + 10 + 2 + 2
