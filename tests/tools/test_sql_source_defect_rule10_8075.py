"""#8075 -- an EXEC SQL census key is a named source defect only under rule 10 (an IBM citation and a review).

No EXEC SQL form is one today: every key of the class (kept keyword, `other (<VERB>)`, `other (<class>)`, bare `other`)
is owned by the det Db2 standing owner and stays unaccounted. Any owner row that does name one must carry both.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))

import gap_prevalence as gp  # noqa: E402


def _keys():
    keys = [f"EXEC SQL: {w}" for w in sorted(gp._SQL_WORDS)]
    keys += [f"EXEC SQL: other ({v})" for v in sorted(gp._SQL_OTHER_VERBS)]
    keys += [f"EXEC SQL: other ({label})" for _, label in gp._SQL_OTHER_CLASSES]
    keys += ["EXEC SQL: other", "EXEC SQL: DECLARE CURSOR WITH HOLD"]
    return keys


@pytest.mark.parametrize("key", _keys())
def test_no_sql_form_is_accounted_as_a_source_defect(key):
    assert gp.owner_of(key).startswith("#8060")
    assert not gp.is_named_defect(key)
    assert gp.status_of(key) == "not modelled"


def test_an_sql_owner_row_naming_a_defect_carries_ibm_citation_and_review():
    for pat, owner in gp.OWNERS:
        if re.search(pat, "EXEC SQL: other") or "EXEC SQL" in pat:
            if "source defect" in owner:
                assert "https://www.ibm.com" in owner and "Rule-10 review" in owner, pat
