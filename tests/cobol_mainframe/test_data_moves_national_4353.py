"""#4353: data_moves' word class lacked the national, CJK and full-width characters the record
reader takes (#3955 / #3991), and a name had to contain an ASCII letter. `MOVE '000001' TO
社員コード` and `MOVE 'Z' TO Ｆ０２` drew no row, and `MOVE SPACE TO X項目` was recorded into `X`
(estate-crucible H-0040, H-0041, H-0046, part of H-0042)."""

from gitgalaxy.core.data_moves import data_moves

SRC = """\
       PROCEDURE DIVISION.
           MOVE '000001' TO 社員コード
           MOVE 'Z' TO Ｆ０２
           MOVE SPACE TO X項目
           MOVE SPACES TO ＴＥＳＴ－ＤＡＴＡ１
           MOVE 見出し TO 社員番号
           ADD 1000 TO 賞与額
           MOVE 1 TO WS-COUNT
           MOVE 'A' TO WS-X.
"""


def _moves() -> list:
    return [(m["verb"], m["source"], m["target"]) for m in data_moves(SRC)]


def test_japanese_full_width_and_mixed_names_are_whole_operands():
    assert _moves() == [
        ("MOVE", "'000001'", "社員コード"),
        ("MOVE", "'Z'", "Ｆ０２"),
        ("MOVE", "SPACE", "X項目"),
        ("MOVE", "SPACES", "ＴＥＳＴ－ＤＡＴＡ１"),
        ("MOVE", "見出し", "社員番号"),
        ("ADD", "1000", "賞与額"),
        ("MOVE", "1", "WS-COUNT"),
        ("MOVE", "'A'", "WS-X"),
    ]


def test_a_full_width_digit_run_is_not_a_name():
    # a name still needs a letter: a bare full-width number is not a data name
    assert [m["target"] for m in data_moves("       PROCEDURE DIVISION.\n           MOVE 1 TO １２.\n")] == []
