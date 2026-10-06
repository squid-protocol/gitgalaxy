"""#4427: a CICS facade carries the COMMAREA a pseudo-conversation passes across programs.

`RETURN TRANSID(t) COMMAREA(ws)` starts the next task in whichever program owns `t`, and that program reads the bytes
through its own record. The facades (#4343) typed the COMMAREA as the program's own DTO both ways, so the crucible's
java-facade side found:

  * pc-wizard: PCWIZ `RETURN TRANSID('PC03') COMMAREA(WS-STATE)` starts PCCONF with a PcwizWsState, which PCCONF's
    handleTransaction(String, PcconfWsState) cannot take; and PCCONF XCTLs to PCWIZ, so its task can end in PCWIZ's
    RETURN -- task.returned(PcconfWsState.class) threw on the PcwizWsState;
  * pc-aid-menu: PCMENU's option 2 RETURNs TRANSID('PC12') with the record PCDETL reads, and PCMENU's facade threw
    in task.returned(PcmenuWsCa.class).

The facade's request is the program's own DTO only when every RETURN TRANSID into its transactions presents no other
class; its response only when every RETURN TRANSID its task can end in (its own, and an XCTL chain's) does the same.
Otherwise that side is Object. A program that converses only with itself keeps its typed facade, text unchanged.
"""

from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CicsForge
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict

SEC = {"field_testing": "open", "tested_on_public": 1, "tested_on_private": 0}


def _program(file, transids, record_file=None, record="WS-CA", returns=(), xctls=(), cut=None):
    """A CICS program with entry transactions `transids`, a COMMAREA record `record` declared in `record_file`, its
    RETURN TRANSID sites `returns` ((line, transid, callee file) -- the record it passes is its own) and XCTLs
    `xctls` ((line, target file)). The record is one PIC X(4), or the 4 bytes cut as `cut` ((name, pic, class,
    offset, bytes) items) -- #4449: records cut differently do not convert by layout."""
    fields = [{"name": n, "pic": pic, "class": c, "offset": o, "bytes": b, "file": record_file or file}
              for n, pic, c, o, b in (cut or [("CA-X", "X(4)", "X", 0, 4)])]  # fmt: skip
    commarea = {"record": record, "file": record_file or file, "basis": "caller_record", "alternatives": [],
                "sources": [], "bytes": 4, "variable": False, "extended": False, "unexpanded": [], "copybooks": [],
                "fields": fields}  # fmt: skip
    return {
        "program": {"file": file, "program_ids": [file[:-4]]},
        "sections": {
            "interface": {**SEC, "facts": {"commarea": commarea, "commarea_gap": None, "containers": []}},
            "entry_transactions": {
                **SEC,
                "facts": [
                    {"transid": t, "program": file[:-4], "resolves_to": file, "defined_in": "x.csd", "line": 1}
                    for t in transids
                ],
            },  # fmt: skip
            "commarea_contracts": {
                **SEC,
                "facts": [
                    {
                        "caller": file,
                        "line": line,
                        "verb": "RETURN TRANSID",
                        "target": t,
                        "callee": callee,
                        "commarea": record,
                        "caller_record": {"name": record, "file": record_file or file, "bytes": 4},
                    }
                    for line, t, callee in returns
                ],
            },  # fmt: skip
            "navigation": {
                **SEC,
                "facts": [
                    {"from": file, "line": line, "verb": "XCTL", "to": to, "via": "static"} for line, to in xctls
                ],
            },
        },
    }


# #4449: the same 4 bytes cut as two numbers: a PcwizWsState's text would be decoded as digits -- no conversion
CUT_OTHERWISE = [("CA-N1", "9(2)", "9", 0, 2), ("CA-N2", "9(2)", "9", 2, 2)]


def _forge(skeletons):
    forge = CicsForge(skeletons, "com.acme", target_from_dict({}))
    services = {k: "\n".join(forge.service_extras(p)["methods"]) for k, p in forge.programs.items()}
    controllers = {k: forge.controller(p) for k, p in forge.programs.items()}
    return forge, services, controllers


def test_pc_wizard_a_return_transid_to_another_program_and_an_xctl_back():
    forge, svc, ctrl = _forge({
        "PCWIZ": _program("PCWIZ.cbl", ["PC01", "PC02"], record="WS-STATE",
                          returns=[(65, "PC02", "PCWIZ.cbl"), (78, "PC03", "PCCONF.cbl")]),
        "PCCONF": _program("PCCONF.cbl", ["PC03"], record="WS-STATE", returns=[(84, "PC03", "PCCONF.cbl")],
                           xctls=[(50, "PCWIZ.cbl")], cut=CUT_OTHERWISE),
    })  # fmt: skip
    wiz, conf = forge.programs["PCWIZ"], forge.programs["PCCONF"]
    assert (wiz.commarea_dto, conf.commarea_dto) == ("PcwizWsState", "PcconfWsState")
    # PCWIZ is entered only by its own RETURN (PC02), and RETURNs to PCCONF's PC03: typed in, Object out
    assert (wiz.txn_request, wiz.txn_response) == ("PcwizWsState", "Object")
    assert "public Object handleTransaction(String transid, PcwizWsState request) {" in svc["PCWIZ"]
    assert "return task.returned(Object.class);" in svc["PCWIZ"]
    # PCCONF is entered by PCWIZ's RETURN, and its task ends in PCWIZ's RETURNs after the XCTL: Object both ways
    assert (conf.txn_request, conf.txn_response) == ("Object", "Object")
    assert "public Object handleTransaction(String transid, Object request) {" in svc["PCCONF"]
    assert ("in: RETURN TRANSID(PC03) COMMAREA(WS-STATE) at PCWIZ.cbl:78 -> PCCONF.cbl (PcwizWsState besides "
            "PcconfWsState).") in svc["PCCONF"]  # fmt: skip
    assert ("out: RETURN TRANSID(PC02) COMMAREA(WS-STATE) at PCWIZ.cbl:65 -> PCWIZ.cbl, after an XCTL from "
            "PCCONF.cbl (PcwizWsState besides PcconfWsState).") in svc["PCCONF"]  # fmt: skip
    # the REST endpoint's body stays the program's own record (JSON needs a concrete class); it answers Object
    assert "public ResponseEntity<Object> transactionPC03(@RequestBody PcconfWsState request) {" in ctrl["PCCONF"]


def test_pc_aid_menu_a_return_transid_to_the_program_an_xctl_also_reaches():
    forge, svc, _ = _forge({
        "PCMENU": _program("PCMENU.cbl", ["PC11"], returns=[(56, "PC12", "PCDETL.cbl"), (74, "PC11", "PCMENU.cbl")],
                           xctls=[(49, "PCDETL.cbl")]),
        "PCDETL": _program("PCDETL.cbl", ["PC12"], cut=CUT_OTHERWISE),  # RETURNs TRANSID(PC11), no COMMAREA: no row
    })  # fmt: skip
    menu, detl = forge.programs["PCMENU"], forge.programs["PCDETL"]
    assert (menu.txn_request, menu.txn_response) == ("PcmenuWsCa", "Object")
    assert "public Object handleTransaction(String transid, PcmenuWsCa request) {" in svc["PCMENU"]
    assert (detl.txn_request, detl.txn_response) == ("Object", "PcdetlWsCa")
    assert "public PcdetlWsCa handleTransaction(String transid, Object request) {" in svc["PCDETL"]
    assert "return task.returned(PcdetlWsCa.class);" in svc["PCDETL"]


def test_a_program_conversing_with_itself_keeps_its_typed_facade_verbatim():
    forge, svc, ctrl = _forge({"HXATTR": _program("HXATTR.cbl", ["HX01"], returns=[(90, "HX01", "HXATTR.cbl")])})
    assert forge.programs["HXATTR"].crossings == []
    facade = svc["HXATTR"]
    assert ("     *  ENTER pressed -- `request` its COMMAREA, null when started from a cleared screen -- run through "
            "runTask. Returns the COMMAREA its RETURN passes on (null: none). */\n"
            "    public HxattrWsCa handleTransaction(String transid, HxattrWsCa request) {") in facade  # fmt: skip
    assert "return task.returned(HxattrWsCa.class);" in facade and "crosses programs" not in facade
    assert "public ResponseEntity<HxattrWsCa> transactionHX01(@RequestBody HxattrWsCa request) {" in ctrl["HXATTR"]


def test_programs_passing_one_shared_copybook_record_stay_typed():
    # CardDemo's COCOM01Y: one DTO for every program passing the copybook record, so no flow presents another class
    shared = {"record": "CARDDEMO-COMMAREA", "record_file": "COCOM01Y.cpy"}
    forge, svc, _ = _forge({
        "MENU": _program("MENU.cbl", ["CM00"], returns=[(10, "CA00", "ADMIN.cbl")], xctls=[(5, "ADMIN.cbl")],
                         **shared),
        "ADMIN": _program("ADMIN.cbl", ["CA00"], returns=[(20, "CA00", "ADMIN.cbl")], **shared),
    })  # fmt: skip
    for key in ("MENU", "ADMIN"):
        p = forge.programs[key]
        assert (p.commarea_dto, p.txn_request, p.txn_response, p.crossings) == (
            "CarddemoCommarea", "CarddemoCommarea", "CarddemoCommarea", [])  # fmt: skip
    assert "public CarddemoCommarea handleTransaction(String transid, CarddemoCommarea request) {" in svc["MENU"]
