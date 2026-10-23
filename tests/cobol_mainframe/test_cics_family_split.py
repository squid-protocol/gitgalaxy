"""#5274: a CICS command family split out of the four hot files (the forge's CicsTask, the stub ggcics.c, the harness's
stub translator equivalence_cics.py, the det translator det/cics.py) still runs where it always did: each family module
is spliced, included or dispatched to exactly once, and each command the spec names is implemented in its family's
module, not left behind in the host file. Containers / channels (#4270, #4951, #5005) is the first family moved; file control is the second (stub and
forge so far: the harness and det halves are still in their host files); task / interval control is the third (stub,
det and forge; the harness half is still in its host file)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_containers as ecc  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_containers as tc  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_filecontrol as tf  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_taskcontrol as tt  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_containers as CC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as CF  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_taskcontrol as CT  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
STUB = ROOT / "tests" / "equivalence" / "cics"
FAMILY = {k: c.impl for k, c in COMMANDS.items() if c.impl and c.impl.translator.split(".")[1] in
          ("container", "container_browse", "channel_command")}  # fmt: skip


def test_the_family_is_every_container_and_channel_command():
    assert sorted(FAMILY) == sorted(k for k in COMMANDS if k.endswith((" CONTAINER", " CHANNEL"))
                                    and COMMANDS[k].impl is not None)  # fmt: skip
    assert {"PUT CONTAINER", "GET CONTAINER", "MOVE CONTAINER", "GETNEXT CONTAINER", "QUERY CHANNEL"} <= set(FAMILY)


def test_cicstask_holds_the_containers_java_once_where_it_sat():
    java = forge.CICS_TASK_JAVA
    assert java.count(tc.CONTAINERS_JAVA) == 1
    at = java.index(tc.CONTAINERS_JAVA)
    assert java[:at].endswith("        return link(program, null, 0);\n    }\n\n")  # LINK with no COMMAREA, before it
    assert java[at + len(tc.CONTAINERS_JAVA) :].startswith("    /** The bytes of the COMMAREA")
    for impl in FAMILY.values():
        assert re.search(rf"public \S+ {impl.java}\(", tc.CONTAINERS_JAVA), impl.java


def test_ggcics_includes_its_families_once():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_containers.c").read_text(encoding="utf-8")
    assert re.findall(r'^#include "(ggcics_\w+\.c)"', host, re.M) == [
        "ggcics_filecontrol.c",
        "ggcics_containers.c",
        "ggcics_taskcontrol.c",
    ]
    assert "#include" not in family  # one translation unit: the family sees everything ggcics.c declared before it
    for impl in FAMILY.values():
        assert re.search(rf"^int {impl.c}\(", family, re.M), impl.c
        assert not re.search(rf"^int {impl.c}\(", host, re.M), impl.c


def test_the_det_translator_dispatches_the_family_to_its_mixin():
    assert issubclass(C.Cics, CC.ContainerCommands)
    for key, impl in FAMILY.items():
        method = impl.translator.split(".")[1]
        assert method in vars(CC.ContainerCommands) and method not in vars(C.Cics), key
        assert C.command_key(key.split(), {key.split()[1]: "X"}) == key


def test_the_harness_dispatches_the_family_to_its_module():
    for key, impl in FAMILY.items():
        assert callable(getattr(ecc, impl.harness)) and not hasattr(ec, impl.harness), key
    # what the dispatch calls: a PUT CONTAINER through the stub translator reaches GGCPUTC
    lines = ec.translate_command("PUT CONTAINER('C1') CHANNEL('CH') FROM(WS-REC)")
    assert any("GGCPUTC" in ln for ln in lines), lines


# ---- file control (#5274, second family): READ, the browse, WRITE, REWRITE, DELETE, UNLOCK, keyed and by RBA ------------
FILE_VERBS = ("READ", "READNEXT", "READPREV", "STARTBR", "RESETBR", "ENDBR", "WRITE", "REWRITE", "DELETE", "UNLOCK")


def test_cicstask_holds_the_file_control_java_once_where_it_sat():
    java = forge.CICS_TASK_JAVA
    assert java.count(tf.FILECONTROL_JAVA) == 1
    at = java.index(tf.FILECONTROL_JAVA)
    assert java[:at].rstrip().endswith("this.faultLog = log;\n        return this;\n    }")  # withFaults, before it
    assert java[at + len(tf.FILECONTROL_JAVA) :].startswith("    /** #4437: the task runs a program LINKed")
    for method in ("read", "readForUpdate", "readSearch", "write", "rewrite", "delete", "unlockHeld", "readnext",
                   "readprev", "startbrRba", "readnextRba", "readprevRba", "endbr"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tf.FILECONTROL_JAVA), method


def test_ggcics_holds_the_file_control_stubs_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_filecontrol.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in ("GGCREAD", "GGCSTBR", "GGCRDNX", "GGCRDPV", "GGCENBR", "GGCDELT", "GGCUNLK"):
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    # WRITE / REWRITE are not moved: they sit before the unit-of-work code that browses_end / uow_end share
    assert re.search(r"^int GGCWRIT\(", host, re.M) and re.search(r"^int GGCREWR\(", host, re.M)
    # the include sits where the block did: after GGCSYNC, before the SEND MAP / RECEIVE MAP code
    assert host.index("int GGCSYNC(") < host.index('#include "ggcics_filecontrol.c"') < host.index("int GGCRECV(")


def test_the_file_verbs_still_translate_to_their_stubs():
    for verb, stub in (("READ FILE('F') INTO(WS) RIDFLD(K)", "GGCREAD"), ("STARTBR FILE('F') RIDFLD(K)", "GGCSTBR"),
                       ("ENDBR FILE('F')", "GGCENBR"), ("UNLOCK FILE('F')", "GGCUNLK")):  # fmt: skip
        assert any(stub in ln for ln in ec.translate_command(verb)), verb


def test_the_det_translator_holds_the_file_control_methods_in_its_mixin():
    assert issubclass(C.Cics, CF.FileControlCommands)
    for method in ("_rba", "rba_browse", "_keylength", "_search", "_read_length", "read", "read_set", "token_out",
                   "read_length", "record_from", "_runtime_keylength", "delete_generic", "token_update",
                   "file_update"):  # fmt: skip
        assert method in vars(CF.FileControlCommands) and method not in vars(C.Cics), method
    assert "constant_int" in vars(C.Cics)  # shared with LINK / RETURN / CONVERSE: it stays the translator's own
    for verb in FILE_VERBS:
        assert C.command_key([verb], {"FILE": "'F'"}).startswith(verb), verb


# ---- task / interval control (#5274, third family; the det half and the forge's CicsTask): START, RETRIEVE, the child tasks, DELAY ... ---
TASK_METHODS = ("_number", "start", "retrieve", "run_transid", "fetch", "free_child", "delay", "post", "wait_event",
                "converse", "cancel", "send_control")  # fmt: skip


def test_the_det_translator_holds_the_task_control_methods_in_its_mixin():
    assert issubclass(C.Cics, CT.TaskControlCommands)
    for method in TASK_METHODS:
        assert method in vars(CT.TaskControlCommands) and method not in vars(C.Cics), method
    # every spec command that dispatches to one of the moved methods still reaches it through `Cics`
    for key, cmd in COMMANDS.items():
        if cmd.impl and cmd.impl.translator.split(".")[1] in TASK_METHODS:
            assert callable(getattr(C.Cics, cmd.impl.translator.split(".")[1])), key
    assert "pointer" in vars(C.Cics)  # shared with the other families: it stays the translator's own


def test_cicstask_holds_the_task_control_java_once_where_it_sat():
    java = forge.CICS_TASK_JAVA
    assert java.count(tt.TASKCONTROL_JAVA) == 1
    at = java.index(tt.TASKCONTROL_JAVA)
    assert java[:at].endswith("    public long taskNumber() {\n        return root().taskNumber;\n    }\n")  # before it
    assert java[at + len(tt.TASKCONTROL_JAVA) :].startswith("    /** ENQ RESOURCE(resource)")
    for method in ("withStartData", "start", "startAt", "startRequest", "runTransid", "delay", "fetch", "freeChild",
                   "retrieve", "cancel", "post", "waitEvent"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tt.TASKCONTROL_JAVA), method


TASK_ENTRIES = ("GGCSTRT", "GGCRTRV", "GGCRUNT", "GGCCHLD", "GGCDLAY", "GGCPOST", "GGCWEVT", "GGCFETCH", "GGCFREE",
                "GGCCNCL")  # fmt: skip


def test_ggcics_holds_the_task_control_stubs_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_taskcontrol.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in TASK_ENTRIES:
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    # every spec command that dispatches to a task-control method has its stub in the family file (CONVERSE and SEND
    # CONTROL are terminal I/O in the stub: only their det methods sit in the task-control mixin)
    for key, cmd in COMMANDS.items():
        if (
            cmd.impl
            and cmd.impl.translator.split(".")[1] in set(TASK_METHODS) - {"converse", "send_control"}
            and cmd.impl.c
        ):
            assert re.search(rf"^int {cmd.impl.c}\(", family, re.M), key
    # the include sits where the block did: after DELETEQ TS, before ENQ
    assert host.index("int GGCDELQ(") < host.index('#include "ggcics_taskcontrol.c"') < host.index("int GGCENQ(")
