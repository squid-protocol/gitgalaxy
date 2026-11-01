"""#5274: a case the split test_equivalence_cics_*.py files share."""

from __future__ import annotations


def facade_case():
    return {"name": "x", "program": "PROG", "transid": "T001", "scenarios": [{"name": "a"}, {"name": "b"}],
            "datasets": {}}  # fmt: skip
