"""#4464: a program with an opaque DFHCOMMAREA still receives the COMMAREA its flows pass.

CardDemo's COSGN00C declares `01 DFHCOMMAREA. 05 LK-COMMAREA PIC X(01) OCCURS 1 TO 32767 DEPENDING ON EIBCALEN` -- no
record of its own -- and continues its pseudo-conversation with `RETURN TRANSID(CC00) COMMAREA(CARDDEMO-COMMAREA)`, CC00
being its own transaction. The engine pairs no COMMAREA with it (every XCTL to it is data-driven, and the RETURN's callee
is unresolved because the CSD also pairs CC00 with COCRDLIC through a DEFINE PROGRAM ... TRANSID), so its generated
facade took none: handleTransaction(String) / handleLink(), and every re-entry the equivalence harness drives was
refused. The generator now takes the record those flows pass, as the estate's DTO for it, and refuses by name where
it cannot.
"""

from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CicsForge
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict

SEC = {"field_testing": "open", "tested_on_public": 1, "tested_on_private": 0}
SHARED = ("CARDDEMO-COMMAREA", "COCOM01Y.cpy")
FIELDS = [{"name": "CDEMO-FROM-TRANID", "pic": "X(4)", "class": "X", "offset": 0, "bytes": 4, "file": "COCOM01Y.cpy"},
          {"name": "CDEMO-USER-ID", "pic": "X(8)", "class": "X", "offset": 4, "bytes": 8, "file": "COCOM01Y.cpy"}]  # fmt: skip
OPAQUE = {"level": 1, "name": "DFHCOMMAREA", "section": "LINKAGE", "pic": None, "line": 65, "children": [
    {"level": 5, "name": "LK-COMMAREA", "section": "LINKAGE", "pic": "X(01)", "occurs_min": 1, "occurs_max": 32767,
     "occurs_depending_on": "EIBCALEN", "line": 66, "children": []}]}  # fmt: skip


def _row(caller, line, verb, target, callee, record=SHARED, fields=2, width=12):
    return {"caller": caller, "line": line, "verb": verb, "target": target, "callee": callee, "commarea": record[0],
            "caller_record": {"name": record[0], "file": record[1], "bytes": width, "fields": fields}}  # fmt: skip


def _menu():
    """A program that declares the shared record as its COMMAREA: the estate's DTO for it."""
    commarea = {"record": SHARED[0], "file": SHARED[1], "basis": "caller_record", "alternatives": [], "sources": [],
                "bytes": 12, "variable": False, "extended": False, "unexpanded": [], "copybooks": [], "fields": FIELDS}  # fmt: skip
    return {
        "program": {"file": "MENU.cbl", "program_ids": ["MENU"]},
        "sections": {
            "interface": {**SEC, "facts": {"commarea": commarea, "commarea_gap": None, "containers": []}},
            "entry_transactions": {**SEC, "facts": [{"transid": "CM00", "program": "MENU", "resolves_to": "MENU.cbl"}]},
            "commarea_contracts": {**SEC, "facts": [_row("MENU.cbl", 10, "RETURN TRANSID", "CM00", "MENU.cbl")]},
        },
    }


def _signon(rows, area=OPAQUE, inbound=()):
    """COSGN00C's shape: an opaque DFHCOMMAREA, transaction CC00, and the given commarea_contracts rows."""
    gap = "DFHCOMMAREA is variable-length or of unknown width, and no resolved LINK / XCTL / RETURN TRANSID passes"
    return {
        "program": {"file": "SIGNON.cbl", "program_ids": ["SIGNON"]},
        "sections": {
            "interface": {
                **SEC,
                "facts": {"commarea": None, "commarea_gap": gap, "containers": [], "inbound": list(inbound)},
            },
            "entry_transactions": {
                **SEC,
                "facts": [{"transid": "CC00", "program": "SIGNON", "resolves_to": "SIGNON.cbl"}],
            },
            "records": {**SEC, "facts": [area]},
            "commarea_contracts": {**SEC, "facts": list(rows)},
            "navigation": {
                **SEC,
                "facts": [
                    {"from": "SIGNON.cbl", "line": 236, "verb": "XCTL", "to": "MENU.cbl", "via": "static"},
                    {"from": "MENU.cbl", "line": 201, "verb": "XCTL", "to": "SIGNON.cbl", "via": "moves"},
                ],
            },
        },
    }


def _forge(skeletons):
    forge = CicsForge(skeletons, "com.acme", target_from_dict({}))
    return forge, {k: "\n".join(forge.service_extras(p)["methods"]) for k, p in forge.programs.items()}


SELF_RETURN = _row("SIGNON.cbl", 98, "RETURN TRANSID", "CC00", None)  # callee unresolved: CC00 is ambiguous


def test_an_opaque_dfhcommarea_takes_the_record_its_own_return_transid_passes():
    forge, svc = _forge({"SIGNON": _signon([SELF_RETURN, _row("SIGNON.cbl", 236, "XCTL", "MENU", "MENU.cbl")]),
                         "MENU": _menu()})  # fmt: skip
    signon = forge.programs["SIGNON"]
    assert (signon.commarea_dto, signon.commarea_gap) == ("CarddemoCommarea", None)
    assert signon.commarea["basis"] == "flow_record"
    # its own RETURN re-enters it with the same DTO: typed in; its task ends in MENU's RETURN, the same DTO: typed out
    assert (signon.txn_request, signon.txn_response, signon.crossings) == ("CarddemoCommarea",) * 2 + ([],)
    assert "public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {" in svc["SIGNON"]
    assert "region.transaction(transid, request);" in svc["SIGNON"]
    assert "public CarddemoCommarea handleLink(CarddemoCommarea request) {" in svc["SIGNON"]
    assert any("Signon receives through its opaque DFHCOMMAREA (line 65), as passed by RETURN TRANSID at "
               "SIGNON.cbl:98" in u for u in forge.dtos["CarddemoCommarea"].uses)  # fmt: skip


def test_a_fixed_or_absent_dfhcommarea_is_not_opaque():
    fixed = {**OPAQUE, "children": [{"level": 5, "name": "CA-A", "pic": "X(4)", "children": []},
                                    {"level": 5, "name": "CA-B", "pic": "9(4)", "children": []}]}  # fmt: skip
    for area in (fixed, {**OPAQUE, "section": "WORKING-STORAGE"}):
        forge, svc = _forge({"SIGNON": _signon([SELF_RETURN], area=area), "MENU": _menu()})
        assert forge.programs["SIGNON"].commarea_dto is None
        assert "public void handleTransaction(String transid) {" in svc["SIGNON"]


def test_refused_by_name_when_no_single_dto_carries_the_record():
    forge, _ = _forge({"SIGNON": _signon([SELF_RETURN])})  # nobody declares the record: no layout to build from
    signon = forge.programs["SIGNON"]
    assert signon.commarea_dto is None
    assert signon.commarea_gap == ("DFHCOMMAREA is opaque; RETURN TRANSID at SIGNON.cbl:98 passes CARDDEMO-COMMAREA "
                                   "(COCOM01Y.cpy, 12 bytes), but no program's COMMAREA DTO carries it")  # fmt: skip
    # the record's width or field count differs from the DTO's (an extended copy): not the same record
    forge, _ = _forge({"SIGNON": _signon([_row("SIGNON.cbl", 98, "RETURN TRANSID", "CC00", None, width=70)]),
                       "MENU": _menu()})  # fmt: skip
    assert forge.programs["SIGNON"].commarea_dto is None


def test_refused_by_name_when_the_flows_disagree():
    other = _row("SIGNON.cbl", 120, "RETURN TRANSID", "CC00", "SIGNON.cbl", record=("WS-OTHER", "SIGNON.cbl"))
    forge, _ = _forge({"SIGNON": _signon([SELF_RETURN, other]), "MENU": _menu()})
    signon = forge.programs["SIGNON"]
    assert signon.commarea_dto is None
    assert signon.commarea_gap.startswith("DFHCOMMAREA is opaque and the flows into this program pass different "
                                          "records: CARDDEMO-COMMAREA (COCOM01Y.cpy, 12 bytes) by RETURN TRANSID at "
                                          "SIGNON.cbl:98; WS-OTHER (SIGNON.cbl, 12 bytes) by RETURN TRANSID at "
                                          "SIGNON.cbl:120")  # fmt: skip
    # a data-driven XCTL into it naming another record: a conflict, not a guess
    inbound = [{"caller": "X.cbl", "line": 5, "verb": "XCTL", "via": "moves", "passes": "WS-ELSE", "bytes": None}]
    forge, _ = _forge({"SIGNON": _signon([SELF_RETURN], inbound=inbound), "MENU": _menu()})
    assert forge.programs["SIGNON"].commarea_gap.endswith("but data-driven sites into it pass WS-ELSE")


def test_a_return_to_another_programs_transaction_is_not_its_own():
    forge, svc = _forge({"SIGNON": _signon([_row("SIGNON.cbl", 98, "RETURN TRANSID", "CM00", None)]),
                         "MENU": _menu()})  # fmt: skip
    assert forge.programs["SIGNON"].commarea_dto is None
    assert "public void handleLink() {" in svc["SIGNON"]
