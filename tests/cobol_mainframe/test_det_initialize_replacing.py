"""#4892 (CardDemo CODATE01): INITIALIZE ... REPLACING category [DATA] BY value in the det translator. Only the
elementary items of a named category are set, each as by MOVE of the value; the others are left as they are (IBM
Enterprise COBOL, INITIALIZE statement). What the translator does not model stays a named hole: WITH FILLER, ALL,
TO VALUE, DEFAULT, a NATIONAL / DBCS category, an item as the value, an ALL literal -- and a table holding an item of a
category REPLACING does not name, which GnuCOBOL sets from the table's first occurrence (register C17). Both ways on
real programs: test_det_programs.py INITREPL (GnuCOBOL against the port)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402


def test_replacing_names_each_category_and_its_value():
    s = S._statement("INITIALIZE A B REPLACING NUMERIC DATA BY ZEROES ALPHANUMERIC BY 'X' NUMERIC-EDITED BY 7", 1)
    assert s.kind == "INITIALIZE" and s.data["refs"] == [E.Ref("A"), E.Ref("B")]
    r = s.data["replacing"]
    assert list(r) == ["NUMERIC", "ALPHANUMERIC", "NUMERIC-EDITED"]
    assert (
        isinstance(r["NUMERIC"], E.Fig) and r["ALPHANUMERIC"] == E.Lit("X") and r["NUMERIC-EDITED"].value == Decimal(7)
    )


def test_plain_initialize_has_no_replacing():
    s = S._statement("INITIALIZE A", 1)
    assert s.kind == "INITIALIZE" and "replacing" not in s.data


@pytest.mark.parametrize("text", [
    "INITIALIZE A WITH FILLER",
    "INITIALIZE A ALL TO VALUE",
    "INITIALIZE A TO VALUE",
    "INITIALIZE A REPLACING NATIONAL BY N'X'",
    "INITIALIZE A REPLACING NUMERIC BY B",  # an item as the value
    "INITIALIZE A REPLACING ALPHANUMERIC BY ALL 'AB'",
    "INITIALIZE A REPLACING NUMERIC BY 1 NUMERIC BY 2",  # a category named twice
    "INITIALIZE A REPLACING NUMERIC 0",  # no BY
    "INITIALIZE A REPLACING",
    "INITIALIZE A REPLACING NUMERIC BY 0 DEFAULT",
])  # fmt: skip
def test_what_is_not_modelled_is_a_named_hole(text):
    s = S._statement(text, 1)
    assert s.kind == "HOLE" and s.data["why"].startswith("INITIALIZE REPLACING")


def _translate(tmp_path, data: list[str], proc: list[str]):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. INITR.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *data,
             "PROCEDURE DIVISION.", *[f"    {x}" for x in proc], "    GOBACK."]  # fmt: skip
    (tmp_path / "INITR.cbl").write_text("".join(f"       {x}\n" for x in lines))
    (tmp_path / "project").mkdir()
    return P.translate(tmp_path / "INITR.cbl", [], "public class InitrService {\n}\n", "p", None, tmp_path / "project")


TABLE = ["01 T.", "   05 E OCCURS 3.", "      10 N PIC 9(2).", "      10 X PIC X(2)."]


def test_a_table_holding_an_item_replacing_does_not_name_is_checked_at_run_time(tmp_path):
    r = _translate(tmp_path, TABLE, ["INITIALIZE T REPLACING ALPHANUMERIC BY 'Q'"])
    assert not r.stats["holes"], r.stats["holes"]
    assert r.java.count("Cobol.sameBytes(") == 2  # occurrences 2 and 3 of N against the first
    assert r.java.count("register C17") == 2 and r.java.count('Cobol.move("Q"') == 3


def test_every_unnamed_category_of_a_table_is_checked(tmp_path):
    table = ["01 T.", "   05 E OCCURS 2.", "      10 N PIC 9(2).", "      10 P PIC S9(3) COMP-3.",
             "      10 X PIC X(2).", "      10 FILLER PIC X."]  # fmt: skip
    r = _translate(tmp_path, table, ["INITIALIZE T REPLACING ALPHANUMERIC BY 'Q'"])
    assert not r.stats["holes"], r.stats["holes"]
    assert r.java.count("Cobol.sameBytes(") == 2  # N and P, not FILLER and not the named X
    (tmp_path / "again").mkdir()
    r = _translate(tmp_path / "again", table, ["INITIALIZE T REPLACING NUMERIC BY 5"])
    assert not r.stats["holes"] and r.java.count("Cobol.sameBytes(") == 1  # X


def test_a_nested_table_with_unnamed_items_stays_a_hole(tmp_path):
    nested = ["01 T.", "   05 E OCCURS 2.", "      10 N PIC 9(2).", "      10 I OCCURS 2 PIC X."]
    r = _translate(tmp_path, nested, ["INITIALIZE T REPLACING NUMERIC BY 5"])
    assert any("register C17" in h for h in r.stats["holes"]), r.stats["holes"]


def test_a_table_whose_every_item_is_named_translates(tmp_path):
    r = _translate(tmp_path, TABLE, ["INITIALIZE T REPLACING NUMERIC BY 5 ALPHANUMERIC BY 'Q'"])
    assert not r.stats["holes"], r.stats["holes"]
    assert r.java.count('Cobol.move("Q"') == 3  # every occurrence's own item: none copied from the first


def test_only_the_named_category_is_set(tmp_path):
    r = _translate(tmp_path, ["01 G.", "   05 A PIC X(3).", "   05 N PIC 9(3).", "   05 P PIC S9(3) COMP-3."],
                   ["INITIALIZE G REPLACING NUMERIC BY ZEROES"])  # fmt: skip
    assert not r.stats["holes"]
    body = r.java.split("INITIALIZE G REPLACING NUMERIC BY ZEROES", 1)[1].split("//", 1)[0]
    assert body.count("Figurative.ZEROS") == 2 and "SPACES" not in body  # N and P; A left as it is
