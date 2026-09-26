"""#3826: the zoned-decimal sign table follows the data's code page.

Under a national EBCDIC code page the overpunch bytes 0xC0-0xC9 / 0xD0-0xD9 are that page's own
letters (cp273 German: `ä` is +0), not the US `{ABCDEFGHI` / `}JKLMNOPQR`. The generated
CobolRecords, the harness's decoder and its input generator all take the table from `data.code_page`;
cp037 (the default) stays exactly as before.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from equivalence_common import decode_field  # noqa: E402
from equivalence_inputs import encode_field  # noqa: E402

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.java_target import ConfigError, target_from_dict, zoned_sign_characters  # noqa: E402

ESTATE = {"sections": {"vsam_stores": {"facts": [{
    "name": "A", "dataset": "A", "users": [{"program": "A.cbl"}], "length": 100,
    "keys": [{"name": "K", "offset": 0, "length": 10, "bytes": 10}],
    "records": [{"name": "REC", "bytes": 100, "fields": [{"name": "F", "bytes": 10, "offset": 0, "pic": "X"}]}],
}]}}}  # fmt: skip


def _records_java(code_page: str) -> str:
    target = target_from_dict({"data": {"code_page": code_page}})
    forge = RepositoryForge(ESTATE, {"A": {"program": {"file": "A.cbl"}}}, "com.test", target=target)
    forge.stores = ["store"]  # records_source only asks whether any store exists
    return forge.records_source()


@pytest.mark.parametrize("cp, zeros", [("cp037", "{}"), ("cp500", "{}"), ("cp1047", "{}"), ("cp273", "äü"),
                                        ("cp277", "æå"), ("cp278", "äå"), ("cp280", "àè"), ("cp284", "{}"),
                                        ("cp285", "{}"), ("cp297", "éè")])  # fmt: skip
def test_each_code_page_has_twenty_distinct_sign_characters(cp, zeros):
    """Including the Nordic, Italian and French pages Python ships no codec for (#3826)."""
    pos, neg = zoned_sign_characters(cp)
    assert len(pos) == len(neg) == 10 and len(set(pos + neg)) == 20
    assert (pos[0], neg[0]) == tuple(zeros) and pos[1:] == "ABCDEFGHI" and neg[1:] == "JKLMNOPQR"


def test_cp273_plus_100_decodes_and_encodes_back():
    pos, neg = zoned_sign_characters("cp273")
    assert (pos[0], neg[0]) == ("ä", "ü")
    stored = b"001000" + "ä".encode("latin-1")  # +100.00 in PIC S9(5)V99, the last digit overpunched
    assert decode_field(stored, "S9(5)V99", None, "cp273") == Decimal("100.00")
    assert encode_field(Decimal("100.00"), "S9(5)V99", None, 7, "cp273") == stored
    assert decode_field(stored, "S9(5)V99", None) != Decimal("100.00")  # the US table misreads it


def test_generated_cobol_records_carries_the_code_page_signs():
    java = _records_java("cp273")
    assert 'POSITIVE = "\\u00e4ABCDEFGHI"' in java  # non-ASCII is escaped: the source stays ASCII
    assert 'NEGATIVE = "\\u00fcJKLMNOPQR"' in java


def test_cp037_is_unchanged():
    assert zoned_sign_characters("cp037") == ("{ABCDEFGHI", "}JKLMNOPQR")
    java = _records_java("cp037")
    assert 'POSITIVE = "{ABCDEFGHI"' in java and 'NEGATIVE = "}JKLMNOPQR"' in java


def test_an_unknown_code_page_fails_when_the_config_loads():
    with pytest.raises(ConfigError, match="cp9999"):
        target_from_dict({"data": {"code_page": "cp9999"}})
