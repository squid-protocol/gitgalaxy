"""#4610: one SQL statement splitter for a Db2 case's seed -- the COBOL side (ggsqlrun -f) and the Java side
(EquivalenceRunTest.db2Reset) both split only at ';' outside quotes, so a comment is stripped for them first."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_db2 as db2

SEED = """-- GenApp's own endowment INSERTs (it's a comment; a ; here too)
INSERT INTO T VALUES (1, 'a--b');   -- trailing it's note
/* a block, with an apostrophe ' and a ; inside */
INSERT INTO T VALUES (2, 'it''s; fine'); INSERT INTO T VALUES (3, '/* not a comment */');
INSERT INTO "T-Q" VALUES (4, 'x');
"""
WANT = [
    "INSERT INTO T VALUES (1, 'a--b')",
    "/* gone */INSERT INTO T VALUES (2, 'it''s; fine')",
    "INSERT INTO T VALUES (3, '/* not a comment */')",
    "INSERT INTO \"T-Q\" VALUES (4, 'x')",
]
WANT[1] = WANT[1].replace("/* gone */", "")


def _loader(script: str) -> list[str]:
    """What ggsqlrun.c and db2Reset both do: ';' ends a statement outside single quotes, nothing else is known."""
    out, quote, cur = [], False, []
    for ch in script + ";":
        if ch == "'":
            quote = not quote
        if ch == ";" and not quote:
            if "".join(cur).strip():
                out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    return out


def test_splitter_strips_comments_outside_literals():
    assert db2.split_sql(SEED) == WANT


def test_both_loaders_get_the_same_statements_from_a_commented_seed():
    script = db2.normalise_sql(SEED)
    assert _loader(script) == WANT
    assert _loader(SEED) != WANT  # the bug: the raw seed is mis-split by the loaders' quote toggle


@pytest.mark.parametrize(
    "bad", ["INSERT INTO T VALUES ('open);", "SELECT 1; /* never closed", 'INSERT INTO "T VALUES (1);']
)
def test_unterminated_text_is_refused_by_name(bad):
    with pytest.raises(ValueError, match="unterminated"):
        db2.split_sql(bad, name="seed.sql")
