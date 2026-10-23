"""#5142: `relation_facts._data_items` is memoised and `_entries` is regex-driven; neither changes a result.

The Java matrix's unchanged-check generated every program's porting ticket once per config, and the data-item parse
was most of that time. The memo returns each caller its own copy, and the entry splitter must agree with the
character loop it replaced on every quote / period / end-of-text shape.
"""

import random

from gitgalaxy.core import relation_facts as rf

DATA = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. T.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-REC.
          05 WS-A PIC X(5) VALUE 'A.B. C'.
          05 WS-N PIC 9(3).
             88 WS-SMALL VALUE 1 THRU 9.
       PROCEDURE DIVISION.
           IF WS-A = 'X' DISPLAY 'Y'.
"""


def _entries_reference(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    start, quote, n = 0, "", len(text)
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "." and (i + 1 == n or text[i + 1] in " \t\r\n"):
            out.append((text[start:i], start))
            start = i + 1
        if len(out) > rf._ITEM_LIMIT:
            break
    return out


def test_entries_match_the_character_loop_on_every_quote_and_period_shape():
    rng = random.Random(5142)
    alphabet = ["'", '"', ".", " ", "\n", "\t", "\r", "A", "9", "-", ".."]
    for _ in range(3000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        assert rf._entries(text) == _entries_reference(text), repr(text)
    for text in ("", ".", "A.", "A. ", "'A. ", "'A.'. B.", 'X "it\'s." Y.\n'):
        assert rf._entries(text) == _entries_reference(text), repr(text)


def test_entries_stop_at_the_item_limit(monkeypatch):
    monkeypatch.setattr(rf, "_ITEM_LIMIT", 3)
    text = "A. B. C. D. E. F. "
    assert rf._entries(text) == _entries_reference(text)
    assert len(rf._entries(text)) == 4


def test_data_items_are_memoised_and_each_caller_owns_its_copy():
    rf._ITEM_CACHE.clear()
    first = rf._data_items([DATA])
    assert first == rf._parse_data_items([DATA])
    first[0]["name"] = "MUTATED"
    first[-1]["values"].append({"lo": "9", "hi": None})
    again = rf._data_items([DATA])
    assert again == rf._parse_data_items([DATA])
    assert len(rf._ITEM_CACHE) == 1


def test_the_memo_key_tells_text_boundaries_apart_and_is_bounded(monkeypatch):
    rf._ITEM_CACHE.clear()
    rf._data_items(["01 A PIC X.", "01 B PIC X."])
    rf._data_items(["01 A PIC X.01 B PIC X.", ""])
    assert len(rf._ITEM_CACHE) == 2
    monkeypatch.setattr(rf, "_ITEM_CACHE_MAX", 2)
    rf._data_items(["01 C PIC X."])
    assert len(rf._ITEM_CACHE) == 1
