"""#3829: the input generator makes dates whatever language a field is named in, in the shape it needs.

Only a ten-byte field with DATE in its name used to get a date; DATUM / FECHA / DATO fields and eight-byte
DDMMYYYY / YYYYMMDD fields got random letters, so a program took only its invalid-date path.
"""

import random
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_inputs as ei  # noqa: E402


def _field(name, nbytes, pic=None, offset=0):
    return {"name": name, "offset": offset, "bytes": nbytes, "pic": pic or f"X({nbytes:02d})", "usage": None}


def _values(field, rows=12, rule=None):
    spec = {"reclen": field["bytes"], "organization": "sequential",
            "generate": {"records": rows, "seed": 3, "fields": {field["name"]: rule} if rule else {}}}  # fmt: skip
    data, _ = ei.generate_dataset("DD", spec, [field], {})
    n = field["bytes"]
    return [data[i : i + n].decode("latin-1") for i in range(0, len(data), n)]


@pytest.mark.parametrize("name, nbytes, fmt", [
    ("WS-FECHA-ALTA", 10, "%Y-%m-%d"), ("DATUM-VON", 10, "%Y-%m-%d"), ("KTO-DATO", 8, "%Y%m%d"),
    ("DATA-NASC", 6, "%y%m%d"), ("BIRTH-DATE", 8, "%Y%m%d"), ("TARIKH", 8, "%Y%m%d"),
])  # fmt: skip
def test_a_date_word_in_any_language_makes_valid_dates(name, nbytes, fmt):
    for v in _values(_field(name, nbytes)):
        datetime.strptime(v, fmt)  # raises on a non-date


@pytest.mark.parametrize("name", ["CANDIDATE", "UPDATE-FLAG", "KDATO-X", "WS-VALIDATED"])
def test_a_date_word_inside_another_word_is_not_a_date(name):
    values = _values(_field(name, 8))
    assert not all(v.isdigit() for v in values)


def test_a_declared_shape_wins_over_the_name():
    for v in _values(_field("KTO-DATUM", 10), rule={"date": "DD.MM.YYYY"}):
        datetime.strptime(v, "%d.%m.%Y")
    for v in _values(_field("ANY-NAME", 8), rule={"date": "DDMMYYYY"}):
        datetime.strptime(v, "%d%m%Y")


def test_a_numeric_date_field_holds_the_date_as_its_number():
    f = _field("WS-DATUM", 8, pic="9(08)")
    spec = {"reclen": 8, "organization": "sequential",
            "generate": {"records": 10, "seed": 3, "fields": {"WS-DATUM": {"date": "YYYYMMDD"}}}}  # fmt: skip
    data, values = ei.generate_dataset("DD", spec, [f], {})
    for raw, v in zip((data[i : i + 8] for i in range(0, len(data), 8)), values["DD.WS-DATUM"]):
        datetime.strptime(raw.decode("latin-1"), "%Y%m%d")
        assert eq.decode_field(raw, "9(08)", None) == v


def test_a_shape_that_does_not_fit_the_field_is_an_error():
    with pytest.raises(ValueError, match="10 characters, the field 8 bytes"):
        _values(_field("KTO-DATUM", 8), rule={"date": "DD.MM.YYYY"})
    with pytest.raises(ValueError, match="digits only"):
        _values(_field("KTO-DATUM", 10, pic="9(10)"), rule={"date": "DD.MM.YYYY"})


def test_the_english_rule_of_old_is_unchanged():
    """A ten-byte *DATE* field draws the same dates from the same seed as before #3829."""
    rng_old, rng_new = random.Random(9), random.Random(9)
    for row in range(20):
        old = f"{rng_old.randint(1990, 2030):04d}-{rng_old.randint(1, 12):02d}-{rng_old.randint(1, 28):02d}"
        assert ei._text_value(rng_new, "ACCT-OPEN-DATE", 10, row) == old
    rng_old, rng_new = random.Random(9), random.Random(9)
    for row in range(20):  # a non-date text field: the same letters as before
        assert ei._text_value(rng_new, "ACCT-GROUP", 10, row) == _old_text(rng_old, 10, row)


def _old_text(rng, nbytes, row):
    if row % 7 == 3:
        return ""
    width = nbytes if row % 3 else max(1, nbytes // 2)
    return "".join(rng.choice(ei._TEXT) for _ in range(width))
