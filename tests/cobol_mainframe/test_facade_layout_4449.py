"""#4449: a facade answers the program's own COMMAREA DTO where the records its task can RETURN convert by layout.

#4427 made a facade's answer Object wherever a RETURN TRANSID its task can end in presents another class: COBOL
passes bytes, and each program reads them through its own record. Where those records cut the bytes exactly as the
program's own does -- the same width, each item at the same offset, width, PICTURE and USAGE: the same COMMAREA under
another program's names (pc-wizard's PCWIZ and PCCONF both COPY PCSTATE into their own WS-STATE) -- the generator
types the answer as the program's own DTO, writes toCommarea / fromCommarea into the DTOs involved, and
CicsTask.returned converts by layout. Any other record (wider, narrower, cut otherwise, or not laid out exactly)
keeps Object: a typed answer would truncate it, pad it, or decode bytes that are not a number as one.
"""

import re
import shutil
import subprocess

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import (
    CICS_TASK_JAVA,
    CicsForge,
    commarea_codec,
    layout_partition,
)
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict

SEC = {"field_testing": "open", "tested_on_public": 1, "tested_on_private": 0}

# PCSTATE, as pc-wizard's copybook lays it out (30 bytes)
PCSTATE = [
    ("PC-STEP", "9", "9", None, 0, 1, None),
    ("PC-NAME", "X(15)", "X", None, 1, 15, None),
    ("PC-AMOUNT", "S9(5)V99", "9", "COMP-3", 16, 4, None),
    ("PC-ERRORS", "S9(4)", "9", "COMP", 20, 2, None),
    ("PC-BACK", "X", "X", None, 22, 1, None),
    ("PC-SPARE", "X(7)", "X", None, 23, 7, None),
]


def _layout(file, items, width=30):
    fields = [{"name": n, "pic": pic, "class": c, "usage": u, "offset": o, "bytes": b, "occurs": occ, "file": file}
              for n, pic, c, u, o, b, occ in items]  # fmt: skip
    return {"bytes": width, "fields": fields}


def _program(file, transid, returns=(), xctls=(), items=PCSTATE, width=30):
    layout = _layout(file, items, width)
    commarea = {"record": "WS-STATE", "file": file, "basis": "caller_record", "alternatives": [], "sources": [],
                "variable": False, "extended": False, "unexpanded": [], "copybooks": [], **layout}  # fmt: skip
    return {
        "program": {"file": file, "program_ids": [file[:-4]]},
        "sections": {
            "interface": {**SEC, "facts": {"commarea": commarea, "commarea_gap": None, "containers": []}},
            "entry_transactions": {
                **SEC,
                "facts": [
                    {"transid": transid, "program": file[:-4], "resolves_to": file, "defined_in": "x.csd", "line": 1}
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
                        "commarea": "WS-STATE",
                        "caller_record": {"name": "WS-STATE", "file": file, "bytes": width},
                    }
                    for line, t, callee in returns
                ],
            },  # fmt: skip
            "navigation": {
                **SEC,
                "facts": [
                    {"from": file, "line": line, "verb": "XCTL", "to": to, "via": "static"} for line, to in xctls
                ],
            },  # fmt: skip
        },
    }


def _wizard(**conf):
    """pc-wizard: PCWIZ RETURNs TRANSID(PC03) into PCCONF with its WS-STATE; PCCONF XCTLs back to PCWIZ."""
    forge = CicsForge({
        "PCWIZ": _program("PCWIZ.cbl", "PC02", returns=[(65, "PC02", "PCWIZ.cbl"), (78, "PC03", "PCCONF.cbl")]),
        "PCCONF": _program("PCCONF.cbl", "PC03", returns=[(84, "PC03", "PCCONF.cbl")], xctls=[(50, "PCWIZ.cbl")],
                           **conf),
    }, "com.acme", target_from_dict({}))  # fmt: skip
    services = {k: "\n".join(forge.service_extras(p)["methods"]) for k, p in forge.programs.items()}
    return forge, services


def test_records_cut_the_same_way_convert_and_the_facade_answers_its_own_dto():
    forge, svc = _wizard()
    wiz, conf = forge.programs["PCWIZ"], forge.programs["PCCONF"]
    assert (wiz.txn_request, wiz.txn_response, wiz.txn_converts) == ("PcwizWsState", "PcwizWsState", ["PcconfWsState"])
    assert (conf.txn_request, conf.txn_response, conf.txn_converts) == ("Object", "PcconfWsState", ["PcwizWsState"])
    assert "public PcwizWsState handleTransaction(String transid, PcwizWsState request) {" in svc["PCWIZ"]
    assert "return task.returned(PcwizWsState.class);" in svc["PCWIZ"]
    assert "public PcconfWsState handleTransaction(String transid, Object request) {" in svc["PCCONF"]
    assert "(PcconfWsState) cut their bytes as PcwizWsState does, so task.returned converts" in svc["PCWIZ"]
    dtos = forge.dto_sources()
    for name in ("PcwizWsState", "PcconfWsState"):  # both ends of the conversion are laid out as bytes
        assert "public byte[] toCommarea() {" in dtos[name]
        assert f"public static {name} fromCommarea(byte[] rec) {{" in dtos[name]


@pytest.mark.parametrize(
    "conf, why",
    [
        ({"items": [*PCSTATE[:-1], ("PC-SPARE", "X(9)", "X", None, 23, 9, None)], "width": 32}, "wider"),
        ({"items": PCSTATE[:-1], "width": 23}, "narrower"),
        ({"items": [*PCSTATE[:-1], ("PC-SPARE", "9(7)", "9", None, 23, 7, None)]}, "cut otherwise"),
        ({"items": [*PCSTATE[:-1], ("PC-SPARE", "X(1)", "X", None, 23, 7, 7)]}, "an OCCURS table"),
    ],
)
def test_any_other_record_keeps_object(conf, why):
    forge, svc = _wizard(**conf)
    wiz = forge.programs["PCWIZ"]
    assert (wiz.txn_response, wiz.txn_converts) == ("Object", []), why
    assert "return task.returned(Object.class);" in svc["PCWIZ"]
    assert "toCommarea" not in forge.dto_sources()["PcwizWsState"]  # no codec is written where none converts


def test_the_partition_ignores_names_and_picture_spelling():
    a = _layout("A.cbl", PCSTATE)
    b = _layout("B.cbl", [(n.replace("PC-", "XY-"), pic.replace("X(15)", "XXXXXXXXXXXXXXX"), *rest)
                          for n, pic, *rest in PCSTATE])  # fmt: skip
    assert layout_partition(a) == layout_partition(b)
    assert layout_partition(a) != layout_partition(_layout("A.cbl", PCSTATE, width=31))


def test_no_codec_for_a_layout_it_cannot_lay_out_exactly():
    rec = "p.CobolRecords"
    assert commarea_codec("X", _layout("A.cbl", PCSTATE), rec) is not None
    assert commarea_codec("X", _layout("A.cbl", PCSTATE, width=None), rec) is None  # width unknown
    redefines = [*PCSTATE, ("PC-ALT", "X(4)", "X", None, 16, 4, None)]  # overlaps PC-AMOUNT
    assert commarea_codec("X", _layout("A.cbl", redefines), rec) is None
    assert commarea_codec("X", _layout("A.cbl", [("F", None, "F", "COMP-2", 0, 8, None)], width=8), rec) is None


MAIN = """package com.acme.cics;

import com.acme.dto.contract.PcconfWsState;
import com.acme.dto.contract.PcwizWsState;

public class Main {
    static CicsTask ended(Object area, Integer length) {
        CicsTask t = new CicsTask("PC03", "ENTER", null, null);
        t.returnTransid("PC03", area, length);
        return t;
    }

    public static void main(String[] a) {
        PcwizWsState wiz = __NEW_WIZ__;
        PcconfWsState conf = ended(wiz, null).returned(PcconfWsState.class);
        System.out.println(conf.__GET__(PcStep) + "|" + conf.__GET__(PcName) + "|" + conf.__GET__(PcAmount) + "|"
                + conf.__GET__(PcErrors) + "|" + conf.__GET__(PcBack) + "|" + conf.__GET__(PcSpare) + "|");
        System.out.println(ended(wiz, null).returned(PcwizWsState.class) == wiz);
        System.out.println(ended(null, null).returned(PcconfWsState.class));
        for (CicsTask t : new CicsTask[] {ended(new StringBuilder("X"), null), ended(wiz, 20)}) {
            try {
                t.returned(PcconfWsState.class);
            } catch (IllegalStateException e) {
                System.out.println("refused: " + e.getMessage());
            }
        }
    }
}
"""
NEW_WIZ = {
    "class": """new PcwizWsState();
        wiz.setPcStep(2);
        wiz.setPcName("ADA");
        wiz.setPcAmount(new java.math.BigDecimal("-123.45"));
        wiz.setPcBack("Y")""",
    "record": 'new PcwizWsState(2, "ADA", new java.math.BigDecimal("-123.45"), null, "Y", null)',
}


@pytest.mark.skipif(shutil.which("javac") is None, reason="needs a JDK (javac)")
@pytest.mark.parametrize("style", ["class", "record"])
def test_returned_converts_by_layout_and_refuses_what_it_cannot(tmp_path, style):
    """The generated runtime and DTOs, compiled (plain classes, and Java records): a PCCONF task RETURNing a
    PcwizWsState is answered as PcconfWsState with every field (an unset number stays unset); the same object when the
    class matches; a class with no layout, or a LENGTH short of the record, is refused by name."""
    target = target_from_dict({"java": {"data_classes": "plain", "dto_style": style}})
    forge = CicsForge(forge_skeletons(), "com.acme", target)
    get = (lambda m: re.sub(r"__GET__\((\w)(\w*)\)", lambda g: g.group(1).lower() + g.group(2) + "()", m)) if (
        style == "record") else (lambda m: re.sub(r"__GET__\((\w+)\)", r"get\1()", m))  # fmt: skip
    root = tmp_path / "src" / "com" / "acme"
    files = {
        "cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "com.acme").replace("__ZONE__", "UTC"),
        "entity/vsam/CobolRecords.java": RepositoryForge({}, {}, "com.acme", target).records_source(needed=True),
        **{f"dto/contract/{n}.java": src for n, src in forge.dto_sources().items()},
        "cics/Main.java": get(MAIN.replace("__NEW_WIZ__", NEW_WIZ[style])),
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text or "", encoding="utf-8")
    classes = tmp_path / "classes"
    built = subprocess.run(["javac", "-d", str(classes), *map(str, root.rglob("*.java"))],  # noqa: S603, S607
                           capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run(["java", "-cp", str(classes), "com.acme.cics.Main"], capture_output=True, text=True,  # noqa: S603, S607
                         check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "2|ADA            |-123.45|null|Y|       |",  # PC-ERRORS unset stays unset; text is its 15 / 7 bytes
        "true",
        "null",
        "refused: the task RETURNed a java.lang.StringBuilder, not a com.acme.dto.contract.PcconfWsState "
        "(no layout converts one into the other)",
        "refused: the task RETURNed a com.acme.dto.contract.PcwizWsState, not a com.acme.dto.contract.PcconfWsState: "
        "20 bytes do not fill PcconfWsState's 30-byte record",
    ]


def forge_skeletons():
    return {
        "PCWIZ": _program("PCWIZ.cbl", "PC02", returns=[(65, "PC02", "PCWIZ.cbl"), (78, "PC03", "PCCONF.cbl")]),
        "PCCONF": _program("PCCONF.cbl", "PC03", returns=[(84, "PC03", "PCCONF.cbl")], xctls=[(50, "PCWIZ.cbl")]),
    }
