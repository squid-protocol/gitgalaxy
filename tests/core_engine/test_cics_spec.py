"""#4270 spec PRs 1-2: gitgalaxy/standards/cics on its own -- the model's checks, the rendered refusal messages, the
entries (45 full, the name-only API commands), the cics_spec CLI, and the package's cost: stdlib only, lazily
loaded, imported only by its listed consumers (spec PR 2: the det translator; PR 3: the equivalence harness),
none of them the engine.

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
IMPORTERS: set[str] = {
    "gitgalaxy/tools/cobol_to_java/det/cics.py",
    "tests/tools/equivalence_cics.py",
    "tests/tools/cics_spec_status.py",
    "tests/tools/proof_blockers.py",
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
            found.add(str(py.relative_to(ROOT)))
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
    assert len(DFHRESP) == 104 and DFHRESP["CONTAINERERR"] == 110 and DFHRESP["CHANNELERR"] == 122
    assert RESP_NAME[12] == "FILENOTFOUND"  # (DSIDERR, its older name, is an alias)
    assert set(CONDITION_ABEND) <= set(DFHRESP)


# ---- the CLI -------------------------------------------------------------------------------------------------------
def test_cli_check_and_emit(capsys):
    assert cli.main(["check"]) == 0
    assert "251 commands, ok" in capsys.readouterr().out
    assert cli.main(["emit", "--json", "GET CONTAINER"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert list(data["commands"]) == ["GET CONTAINER"]
    assert data["commands"]["GET CONTAINER"]["refused"]["SET"]["why"].startswith("the address of CICS's copy")
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


def test_python_m_runs_the_cli():
    assert "cics spec: 251 commands, ok" in _run("import runpy, sys; sys.argv = ['x', 'check']\n"
                                               "try:\n    runpy.run_module('gitgalaxy.standards.cics', run_name='__main__')\n"
                                               "except SystemExit as e:\n    assert e.code == 0")  # fmt: skip


# ---- spec PR 2: the coverage (cics_command_spec.md section 9, decision 4) ------------------------------------------
def test_coverage_45_full_entries_and_the_name_only_api_commands():
    by_status: dict[str, list[str]] = {}
    for c in COMMANDS.values():
        by_status.setdefault(c.status, []).append(c.key)
    assert len(by_status["modelled"]) == 43 and sorted(by_status["engine-only"]) == ["LOAD", "RELEASE"]
    # IBM's CICS TS 6.x command summary: 259 API command names, 44 with full entries (+ INQUIRE PROGRAM, SPI), 9
    # forms of a modelled command (api.py's docstring), the other 206 name-only
    assert len(by_status["refused"]) == 206
    for key in by_status["refused"]:
        c = COMMANDS[key]
        assert c.why and not c.options and not c.refused and not c.outcomes, key


def test_a_whole_command_refusal_names_its_reason():
    from gitgalaxy.standards.cics.commands import whole_refusal

    getmain = whole_refusal("GETMAIN", "GETMAIN", "SET")
    assert getmain is not None and getmain.whole_message("GETMAIN") == (
        "EXEC CICS GETMAIN not modelled (storage CICS acquires for the task, addressed by a pointer, is not modelled)"
    )
    # a verb and its first option: IBM's WAIT JOURNALNAME, ADDRESS SET (the most specific form wins)
    assert whole_refusal("WAIT", "WAIT", "JOURNALNAME").key == "WAIT JOURNALNAME"  # type: ignore[union-attr]
    assert whole_refusal("ADDRESS", "ADDRESS", "SET").key == "ADDRESS SET"  # type: ignore[union-attr]
    assert whole_refusal("ADDRESS", "ADDRESS", "EIB").key == "ADDRESS"  # type: ignore[union-attr]
    assert whole_refusal("LOAD", "LOAD", "PROGRAM").status == "engine-only"  # type: ignore[union-attr]
    # a modelled command, or a name that is no API command (an SPI one): no whole-command entry
    assert whole_refusal("READ", "READ", "FILE") is None
    assert whole_refusal("INQUIRE", "INQUIRE FILE", None) is None


def test_group_lookup():
    assert COMMANDS["START"].group("required", "TRANSID").msg == "START without TRANSID"
    with pytest.raises(KeyError):
        COMMANDS["START"].group("one_of", "TRANSID")


def test_each_command_keeps_its_own_refusal_reasons():
    """Owner decision (spec PR 2, disagreement 2): no global table -- GET CONTAINER WAIT shows no RETRIEVE reason;
    a read's SET and a file command's SYSID keep the reason that is true for them."""
    assert COMMANDS["GET CONTAINER"].refusal_message(["WAIT"]) == "GET CONTAINER WAIT: option not modelled"
    assert COMMANDS["READ"].refusal_message(["SET"]) == (
        "READ SET: option not modelled (SET: the address of CICS's copy of the data (a pointer) is not modelled)"
    )
    assert (
        COMMANDS["LINK"].refusal_message(["SYSID"])
        == "LINK SYSID: option not modelled (SYSID: a remote system is not modelled)"
    )
