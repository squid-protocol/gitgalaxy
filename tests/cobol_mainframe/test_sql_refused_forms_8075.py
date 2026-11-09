"""#8075 -- every EXEC SQL statement keyword IBM documents is modelled or refused by name, never silently dropped.

The blind trial's "EXEC SQL: other" was a census artefact (compile-listing copies, #8081), not an unmodelled verb. This pins
the class it stood for: each keyword of the census vocabulary (`gap_prevalence._SQL_OTHER_VERBS`, Db2 for z/OS SQL
Reference statements) raises a `SqlError` from the det Db2 path when no generated repository method exists for it, and
each verb of `det.sql._REFUSED_VERBS` is refused with its register Q4 reason. No burned estate reads any of them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))


class _Gen:
    cics = None

    def field_expr(self, ref):
        return "ca"


def _command(sql):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    return Sql(_Gen(), "P", None).command(f"EXEC SQL {sql} END-EXEC", 7, "")


def _other_verbs():
    import gap_prevalence as gp

    return sorted(gp._SQL_OTHER_VERBS)


@pytest.mark.parametrize("verb", _other_verbs())
def test_each_census_keyword_is_refused_not_dropped(verb):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError):
        _command(f"{verb} X")


def test_each_refused_verb_names_register_q4():
    from gitgalaxy.tools.cobol_to_java.det.sql import _REFUSED_VERBS, SqlError

    for verb in _REFUSED_VERBS:
        sql = "SET CURRENT SQLID = 'X'" if verb == "SET" else f"{verb} X"
        if verb == "EXECUTE":
            sql = "EXECUTE X USING DESCRIPTOR :D"
        with pytest.raises(SqlError, match=r"EXEC SQL " + verb):
            _command(sql)


def test_the_census_vocabulary_overlaps_no_modelled_verb():
    import gap_prevalence as gp

    assert not gp._SQL_OTHER_VERBS & gp._SQL_WORDS
