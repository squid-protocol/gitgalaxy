"""#4270 spec PRs 1-4: gitgalaxy/standards/cics on its own -- the model's checks, the rendered refusal messages, the
entries (45 full, the name-only API commands), the cics_spec CLI, and the package's cost: stdlib only, lazily
loaded, imported only by its listed consumers (spec PR 2: the det translator; PR 3: the equivalence harness),
none of them the engine. Spec PR 4: the committed generated runtime tables (CicsSpec.java, ggcics_spec.h) are
never stale, and the runtimes keep no hand copy of them.

(The proofs that the spec equals today's hand copies are transitional and live in
tests/cobol_mainframe/test_cics_spec_equality.py.)"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.cics import cli
from gitgalaxy.standards.cics.commands import COMMANDS
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    Doc,
    Fact,
    Group,
    Outcome,
    Refusal,
    RuntimeRefusal,
    one_of,
)
from gitgalaxy.standards.cics.resp import CONDITION_ABEND, DFHRESP, RESP_NAME

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "gitgalaxy" / "standards" / "cics"
_DOC = Doc("EXEC CICS X", "https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-x")


# ---- cost: stdlib only, lazy, no engine importer -----------------------------------------------------------------
def _run(code: str) -> str:
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True)
    return out.stdout.strip()


def test_importing_the_package_loads_no_entry_until_one_is_used():
    loaded = _run(
        "import sys, gitgalaxy.standards.cics as s\n"
        "print(sorted(m for m in sys.modules if m.startswith('gitgalaxy.standards.cics.')))\n"
        "s.COMMANDS\n"
        "print('gitgalaxy.standards.cics.commands' in sys.modules)"
    ).splitlines()
    assert loaded == ["[]", "True"]


def test_the_spec_imports_only_the_stdlib():
    """The engine is "0 dependencies" (pyproject.toml): loading every entry imports nothing outside the standard
    library and the package itself."""
    extra = _run(
        "import sys\n"
        "before = set(sys.modules)\n"
        "import gitgalaxy.standards.cics as s\n"
        "s.COMMANDS, s.DFHRESP\n"
        "import gitgalaxy.standards.cics.cli\n"
        "std = set(sys.stdlib_module_names)\n"
        "print(sorted(m for m in set(sys.modules) - before if m.split('.')[0] not in std\n"
        "             and m not in ('gitgalaxy', 'gitgalaxy.standards')\n"
        "             and not m.startswith('gitgalaxy.standards.cics')))"
    )
    assert extra == "[]"
    for py in PACKAGE.rglob("*.py"):
        for mod in re.findall(r"^\s*(?:from|import)\s+([\w.]+)", py.read_text(encoding="utf-8"), re.M):
            top = mod.split(".")[0]
            assert (
                top in sys.stdlib_module_names or top == "__future__" or mod.startswith("gitgalaxy.standards.cics")
            ), f"{py.name}: imports {mod}"


# Who may import the spec. Each spec PR adds its consumer here: PR 2 the det translator, PR 3 the equivalence
# harness's stub translator, PR 8a the engine walkers (lazily, inside the CICS walkers only). The status page
# tool (tests/tools/cics_spec_status.py, #4270) only reports on the spec: docs/language_status/cics_spec_status.md.
# The proof-level ranking (tests/tools/proof_blockers.py) reads the EIB facts a harness states (eib.EIB_FACTS).
# The det expression translator (det/expr.py) resolves DFHRESP(name) conditions from the RESP table directly
# (gitgalaxy.standards.cics.resp, not via det/cics.py: that import closed a cycle CodeQL flagged).
IMPORTERS: set[str] = {
    "gitgalaxy/tools/cobol_to_java/det/cics.py",
    "gitgalaxy/tools/cobol_to_java/det/cics_common.py",  # #7153: the helpers cics.py and its mixins share
    "gitgalaxy/tools/cobol_to_java/det/expr.py",
    "tests/tools/equivalence_cics.py",
    "tests/tools/equivalence_cics_conditions.py",  # #5274: the conditions family split out of equivalence_cics.py
    "tests/tools/cics_spec_status.py",
    "tests/tools/proof_blockers.py",
    "tests/tools/blocker_report.py",  # #5054: the blocker signatures' vocabulary is the spec's command and option words
    "gitgalaxy/tools/readiness/schema.py",  # #4726: the spec's command and option words are assess's CICS vocabulary
}
_IMPORTS_SPEC = re.compile(
    r"^\s*(?:from\s+gitgalaxy\.standards(?:\.cics\b|\s+import\s+cics\b)|import\s+gitgalaxy\.standards\.cics\b)", re.M
)


def test_only_the_listed_consumers_import_the_spec():
    """The package's importers in gitgalaxy/ and the harness tools (tests/tools/): an import statement, not a
    mention (crucible_case.py names the package to deny it to the crucible's log scripts)."""
    found = set()
    for py in [*(ROOT / "gitgalaxy").rglob("*.py"), *(ROOT / "tests" / "tools").glob("*.py")]:
        if PACKAGE in py.parents:
            continue
        if _IMPORTS_SPEC.search(py.read_text(encoding="utf-8")):
            found.add(py.relative_to(ROOT).as_posix())  # #4836: "/" on Windows too
    assert found == IMPORTERS


# ---- the model's own checks ----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("build", "why"),
    [
        (lambda: Arg("blob"), "unknown argument kind"),  # type: ignore[arg-type]
        (lambda: Arg("name", hosts=("rexx",)), "hosts"),
        (lambda: Refusal(" padded"), "refusal reason"),
        (lambda: Refusal("why", register="17"), "register"),
        (lambda: RuntimeRefusal("nobody"), "refused by no runtime"),
        (lambda: Outcome("notfnd", 0, ""), "not an upper-case CICS name"),
        (lambda: Group("requires", ("A",), "m"), "group requires"),
        (lambda: Fact("x", java=None, env="X", region_default=None, options=()), "env"),
        (lambda: Doc("t", "https://example.com/x"), "not an IBM documentation URL"),
        (lambda: Command("X", _DOC, "modelled", options={"A": Arg("flag")}, refused={"A": Refusal("r")}),
         "both honoured and refused"),
        (lambda: Command("X", _DOC, "modelled", options={"A": Arg("flag")}, groups=(one_of("A", "B", msg="m"),)),
         "not options of the command"),
        (lambda: Command("X", _DOC, "modelled", outcomes=(Outcome("NORMAL", 0, "", writes=("INTO",)),)),
         "is not an option it honours"),
        (lambda: Command("X", _DOC, "modelled", state=("browse",)), "unknown state"),
        (lambda: Command("X", _DOC, "refused"), "whole-command reason"),
        (lambda: Command("X", _DOC, "modelled", why="w"), "whole-command reason"),
        (lambda: Command("X", _DOC, "refused", why="w", options={"A": Arg("flag")}), "name-only entry"),
    ],
)  # fmt: skip
def test_the_model_refuses_a_wrong_entry_when_built(build, why):
    with pytest.raises(ValueError, match=why):
        build()


def test_refusal_messages_render_as_the_translator_words_them():
    c = Command(
        "X Y", _DOC, "modelled",
        refused={"A": Refusal("a's reason"), "B": Refusal("b's reason"), "W": Refusal("X Y W: alone", whole=True)},
    )  # fmt: skip
    assert c.refusal_message(["A"]) == "X Y A: option not modelled (A: a's reason)"
    assert c.refusal_message(["A", "B"]) == "X Y A B: option not modelled (A: a's reason; B: b's reason)"
    assert c.refusal_message(["Z"]) == "X Y Z: option not modelled"  # no default: no reason
    assert c.refusal_message(["A", "W"]) == "X Y A W: option not modelled (X Y W: alone)"


def test_every_entry_is_consistent():
    assert cli.problems() == []
    for c in COMMANDS.values():
        assert re.fullmatch(r"https://www\.ibm\.com/docs/en/cics-ts/6\.x\?topic=(summary|commands)-[a-z0-9-]+",
                            c.ibm.url), c.key  # fmt: skip
        assert all(o.condition in DFHRESP for o in c.outcomes)


def test_resp_tables():
    assert (
        len(DFHRESP) == 106
        and DFHRESP["CONTAINERERR"] == 110
        and DFHRESP["CHANNELERR"] == 122
        and DFHRESP["TOKENERR"] == 112
    )
    assert RESP_NAME[12] == "FILENOTFOUND"  # (DSIDERR, its older name, is an alias)
    assert set(CONDITION_ABEND) <= set(DFHRESP)
    assert CONDITION_ABEND["IOERR"] == "AEIQ"  # #6166: IBM abend AEIQ, "IOERR condition not handled"


# ---- the CLI -------------------------------------------------------------------------------------------------------
def test_cli_check_and_emit(capsys):
    assert cli.main(["check"]) == 0
    assert "257 commands, ok" in capsys.readouterr().out
    assert cli.main(["emit", "--json", "SEND MAP"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert list(data["commands"]) == ["SEND MAP"]
    assert data["commands"]["SEND MAP"]["refused"]["SET"]["why"].startswith("the address of CICS's copy")
    assert cli.main(["emit"]) == 0 and "SEND TEXT" in capsys.readouterr().out
    assert cli.main(["emit", "NO SUCH"]) == 2


def test_cli_regen_writes_the_runtime_tables(tmp_path):
    assert cli.main(["regen", "--out", str(tmp_path)]) == 0
    java = (tmp_path / "CicsSpec.java").read_text()
    c = (tmp_path / "ggcics_spec.h").read_text()
    assert cli.BANNER in java and cli.BANNER in c
    assert 'case 110 -> "CONTAINERERR";' in java and 'case "CHANNELERR" -> "AEZV";' in java
    assert "DFHRESP_CHANNELERR = 122," in c and 'case DFHRESP_CONTAINERERR: return "AEZJ";' in c
    assert cli.main(["regen", "--out", str(tmp_path), "--java-package", "Not A Package"]) == 2
    assert java.splitlines()[1] == "package __PACKAGE__.cics;"  # (the forge fills the package in, as in CicsTask)


# ---- spec PR 4: the committed generated runtime tables -------------------------------------------------------------
def test_the_committed_generated_files_are_not_stale():
    """The drift test (cics_command_spec.md section 7, PR 4; also the cics-spec ratchet, pr_gates.py --ratchets):
    regenerating from the spec changes neither committed file. On a failure: `python -m gitgalaxy.standards.cics
    regen`, review the Java / C diff, commit it."""
    assert cli.stale() == []
    for rel in cli.generated():
        assert (ROOT / rel).read_text(encoding="utf-8").startswith(("// " + cli.BANNER, "/* " + cli.BANNER)), rel


def test_regen_check_reports_a_stale_file(tmp_path, capsys):
    for rel, text in cli.generated().items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    assert cli.stale(tmp_path) == []
    (tmp_path / cli.C_FILE).write_text(cli.render_c().replace("AEZV", "AEZX"), encoding="utf-8")
    assert cli.stale(tmp_path) == [cli.C_FILE]
    assert cli.main(["regen", "--check"]) == 0 and "up to date" in capsys.readouterr().out


def _java_cases(src: str) -> list[str]:
    """The `case <RESP> -> "<NAME>";` / `case "<NAME>" -> <RESP or code>;` arms of a Java source."""
    return re.findall(r'case (?:\d+ -> "[A-Z0-9]+"|"[A-Z0-9]+" -> (?:\d+|"[A-Z0-9]{4}"));', src)


def test_the_runtimes_keep_no_hand_copy_of_the_generated_tables():
    """DetCics.condition / resp, CicsTask.respName / abcodeFor delegate to CicsSpec; ggcics.c includes ggcics_spec.h
    and names its conditions by the spec's numbers (no literal RESP), with no condition_abcode of its own."""
    from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge

    detcics = (ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    assert "return CicsSpec.condition(resp);" in detcics and "return CicsSpec.resp(condition);" in detcics
    assert (
        "CicsSpec.name(resp)" in forge.CICS_TASK_JAVA
        and "return CicsSpec.abcodeFor(condition);" in forge.CICS_TASK_JAVA
    )
    assert _java_cases(detcics) == [] and _java_cases(forge.CICS_TASK_JAVA) == []
    assert len(_java_cases(forge.CICS_SPEC_JAVA)) == len(RESP_NAME) + len(DFHRESP) + len(CONDITION_ABEND)
    stub = ROOT / "tests/equivalence/cics"
    ggcics = (stub / "ggcics.c").read_text(encoding="utf-8")
    assert '#include "ggcics_spec.h"' in ggcics and "condition_abcode(int" not in ggcics
    for family in sorted(stub.glob("ggcics_*.c")):  # #5274: a family file is part of the stub's one translation unit
        ggcics += family.read_text(encoding="utf-8")
    for body in re.findall(r"enum\s*\{([^}]*)\}", ggcics):
        for name, value in re.findall(r"(\w+)\s*=\s*(\w+)", body):
            if name in DFHRESP:
                assert value == f"DFHRESP_{name}", name
    assert re.search(r"\bERRCOND = DFHRESP_ERROR\b", ggcics)


def test_python_m_runs_the_cli():
    assert "cics spec: 257 commands, ok" in _run("import runpy, sys; sys.argv = ['x', 'check']\n"
                                               "try:\n    runpy.run_module('gitgalaxy.standards.cics', run_name='__main__')\n"
                                               "except SystemExit as e:\n    assert e.code == 0")  # fmt: skip


# ---- spec PR 2: the coverage (cics_command_spec.md section 9, decision 4) ------------------------------------------
def test_coverage_45_full_entries_and_the_name_only_api_commands():
    by_status: dict[str, list[str]] = {}
    for c in COMMANDS.values():
        by_status.setdefault(c.status, []).append(c.key)
    assert len(by_status["modelled"]) == 103 and sorted(by_status["engine-only"]) == ["LOAD", "RELEASE"]
    # IBM's CICS TS 6.x command summary: 259 API command names, 57 with full entries (+ INQUIRE PROGRAM, SPI; #4767: WEB
    # OPEN / CONVERSE / CLOSE / PARSE URL / SEND / EXTRACT / RECEIVE / READ + WRITE HTTPHEADER; #4940: READ FORMFIELD / QUERYPARM and the nine WEB browse forms; #4941: RETRIEVE; #4951: MOVE CONTAINER, STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER; #4950: FREE CHILD; #4972: EXTRACT WEB, EXTRACT TCPIP; #5005: DELETE CHANNEL, QUERY CHANNEL, GET64 / PUT64 CONTAINER; #4771: GETMAIN / FREEMAIN; #5078: UNLOCK; #5079: READQ TD, DELETEQ TD, ADDRESS, POST, WAIT EVENT, CONVERSE; #5039: REWIND COUNTER, UPDATE COUNTER; #5859: VERIFY PASSWORD, no longer name-only), 9 forms of a modelled command (api.py's docstring), the other 152 name-only
    assert len(by_status["refused"]) == 152
    for key in by_status["refused"]:
        c = COMMANDS[key]
        assert c.why and not c.options and not c.outcomes, key
        # #5235: a name-only entry may name its refused options (SOAPFAULT CREATE), nothing else may
        assert not c.refused or key == "SOAPFAULT CREATE", key


def test_a_whole_command_refusal_names_its_reason():
    from gitgalaxy.standards.cics.commands import whole_refusal

    getmain = whole_refusal("GETMAIN64", "GETMAIN64", "SET")
    assert getmain is not None and getmain.whole_message("GETMAIN64") == (
        "EXEC CICS GETMAIN64 not modelled (storage CICS acquires for the task, addressed by a pointer, is not modelled)"
    )
    # a verb and its first option: IBM's WAIT JOURNALNAME, ADDRESS SET (the most specific form wins)
    assert whole_refusal("WAIT", "WAIT", "JOURNALNAME").key == "WAIT JOURNALNAME"  # type: ignore[union-attr]
    assert whole_refusal("ADDRESS", "ADDRESS", "SET").key == "ADDRESS SET"  # type: ignore[union-attr]
    assert whole_refusal("ADDRESS", "ADDRESS", "EIB") is None  # #5079 (X59): ADDRESS EIB / COMMAREA are modelled
    assert whole_refusal("LOAD", "LOAD", "PROGRAM").status == "engine-only"  # type: ignore[union-attr]
    # a modelled command, or a name that is no API command (an SPI one): no whole-command entry
    assert whole_refusal("READ", "READ", "FILE") is None
    assert whole_refusal("INQUIRE", "INQUIRE FILE", None) is None


def test_inquire_container_is_refused_whole_in_every_form():
    """#5005 / X44: IBM documents INQUIRE CONTAINER only for a BTS data-container (ACTIVITYID / PROCESS / PROCESSTYPE /
    DATALENGTH / SET), with no CHANNEL, BROWSETOKEN or START / NEXT / END form, so every option set is refused by name
    and the reason says why (the channel browse is STARTBROWSE CONTAINER, X42; a length is GET CONTAINER NODATA)."""
    from gitgalaxy.standards.cics.commands import whole_refusal

    c = COMMANDS["INQUIRE CONTAINER"]
    assert c.status == "refused" and not c.options and not c.outcomes
    for first in (
        None,
        "CONTAINER",
        "CHANNEL",
        "BROWSETOKEN",
        "START",
        "NEXT",
        "END",
        "DATALENGTH",
        "SET",
        "ACTIVITYID",
        "PROCESS",
        "PROCESSTYPE",
        "NODATA",
        "FLENGTH",
    ):
        r = whole_refusal("INQUIRE", "INQUIRE CONTAINER", first)
        assert r is not None and r.key == "INQUIRE CONTAINER", first
        msg = r.whole_message("INQUIRE CONTAINER")
        assert "only for a BTS data-container" in msg and "no channel form" in msg, first
        assert "STARTBROWSE CONTAINER" in msg and "NODATA FLENGTH" in msg, first
    # the neighbours are untouched: the browse is modelled, and the other INQUIREs keep their own entries
    for key in ("STARTBROWSE CONTAINER", "GETNEXT CONTAINER", "ENDBROWSE CONTAINER", "QUERY CHANNEL"):
        assert COMMANDS[key].status == "modelled", key


def test_the_64_bit_container_commands_keep_their_refusals_by_name():
    """#5005 / X17: GET64 / PUT64 CONTAINER are modelled as the base commands with an ordinary item as the data area;
    GET64 SET (a 64-bit pointer above the bar) and the IANA code-page names stay refused by name, with the reason, and
    no burned program reads any of them."""
    for base in ("GET", "PUT"):
        wide = COMMANDS[base + "64 CONTAINER"]
        assert wide.status == "modelled", base
        assert set(wide.options) <= set(COMMANDS[base + " CONTAINER"].options), base
    get64 = COMMANDS["GET64 CONTAINER"]
    assert "SET" not in get64.options and "SET" in get64.refused
    msg = get64.refusal_message(["SET"])
    assert msg.startswith("GET64 CONTAINER SET: option not modelled") and "64-bit pointer" in msg and "use INTO" in msg
    assert COMMANDS["GET CONTAINER"].options["SET"].kind == "pointer"
    for key, option in (
        ("GET CONTAINER", "INTOCODEPAGE"),
        ("GET64 CONTAINER", "INTOCODEPAGE"),
        ("PUT CONTAINER", "FROMCODEPAGE"),
        ("PUT64 CONTAINER", "FROMCODEPAGE"),
    ):
        assert option in COMMANDS[key].refused and option not in COMMANDS[key].options, (key, option)
        assert COMMANDS[key].refusal_message([option]).startswith(f"{key} {option}: option not modelled"), (key, option)
    # X65 lists only what is still refused whole: the 64-bit storage commands, not the modelled container twins.
    for key in ("GETMAIN64", "FREEMAIN64"):
        assert COMMANDS[key].status != "modelled", key
    x65 = (Path(__file__).resolve().parents[2] / "docs/language_status/register/X65.md").read_text(encoding="utf-8")
    assert "64-bit GETMAIN64 / FREEMAIN64 (2;" in x65 and "64-bit GET64 / PUT64 CONTAINER and" not in x65


def test_group_lookup():
    assert COMMANDS["START"].group("required", "TRANSID").msg == "START without TRANSID"
    with pytest.raises(KeyError):
        COMMANDS["START"].group("one_of", "TRANSID")


def test_each_command_keeps_its_own_refusal_reasons():
    """Owner decision (spec PR 2, disagreement 2): no global table -- GET CONTAINER WAIT shows no RETRIEVE reason;
    a SEND MAP's SET and a file command's SYSID keep the reason that is true for them (#5042: a read's SET is modelled)."""
    assert COMMANDS["GET CONTAINER"].refusal_message(["WAIT"]) == "GET CONTAINER WAIT: option not modelled"
    assert COMMANDS["SEND MAP"].refusal_message(["SET"]) == (
        "SEND MAP SET: option not modelled (SET: the address of CICS's copy of the data (a pointer) is not modelled)"
    )
    assert (
        COMMANDS["LINK"].refusal_message(["SYSID"])
        == "LINK SYSID: option not modelled (SYSID: a remote system is not modelled)"
    )


@pytest.mark.parametrize("name", ["cics_common", "cics_taskcontrol"])
def test_a_leaf_det_module_imports_nothing_back_from_cics_or_gen(name):
    """#7153: CodeQL py/cyclic-import counts an import inside a function too, so no import statement anywhere in these
    modules may name det.cics or det.gen (a mixin takes the shared helpers from det.cics_common)."""
    import ast

    path = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / f"{name}.py"
    banned = {"cics", "gen"}
    pkg = "gitgalaxy.tools.cobol_to_java.det"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = {f"{node.module}.{a.name}" for a in node.names}
            hit = {node.module, *names} & {f"{pkg}.{b}" for b in banned}
            assert not hit, f"{name}.py:{node.lineno} imports {sorted(hit)}"
        elif isinstance(node, ast.Import):
            assert not {a.name for a in node.names} & {f"{pkg}.{b}" for b in banned}, f"{name}.py:{node.lineno}"
