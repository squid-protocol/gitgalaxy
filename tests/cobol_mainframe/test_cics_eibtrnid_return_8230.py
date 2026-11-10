"""#8230: `RETURN TRANSID(EIBTRNID) COMMAREA(ws)` names the task's own transaction (EIBTRNID holds it), so it re-enters
the program: the service keeps its typed COMMAREA DTO. Any other variable TRANSID stays unresolved (Object)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_cics_opaque_commarea_4464 import _forge, _menu, _row  # noqa: E402


def _with_return(target, callee=None):
    sk = _menu()
    sk["sections"]["commarea_contracts"]["facts"] = [_row("MENU.cbl", 10, "RETURN TRANSID", target, callee)]
    return {"MENU": sk}


@pytest.mark.parametrize("target", ["EIBTRNID", "eibtrnid", "CM00"])
@pytest.mark.parametrize("callee", [None, "MENU.cbl"])
def test_a_return_to_the_tasks_own_transaction_keeps_the_typed_service(target, callee):
    forge, svc = _forge(_with_return(target, callee))
    menu = forge.programs["MENU"]
    assert (menu.txn_request, menu.txn_response, menu.crossings) == ("CarddemoCommarea", "CarddemoCommarea", [])
    assert "handleTransaction(String transid, CarddemoCommarea request)" in svc["MENU"]


@pytest.mark.parametrize("target", ["WS-NEXT-TRANID", "OTHR"])
def test_another_variable_or_unresolved_transid_stays_object(target):
    forge, svc = _forge(_with_return(target))
    menu = forge.programs["MENU"]
    assert menu.txn_response == "Object"  # its task may end in a RETURN to a program the flow cannot name
    assert any(f"RETURN TRANSID({target})" in c for c in menu.crossings)

