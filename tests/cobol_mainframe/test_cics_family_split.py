"""#5274: a CICS command family split out of the four hot files (the forge's CicsTask, the stub ggcics.c, the harness's
stub translator equivalence_cics.py, the det translator det/cics.py) still runs where it always did: each family module
is spliced, included or dispatched to exactly once, and each command the spec names is implemented in its family's
module, not left behind in the host file. Containers / channels (#4270, #4951, #5005) is the first family moved; file control is the second (stub and
forge so far: the harness and det halves are still in their host files); task / interval control is the third (stub,
det, forge and harness)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_containers as ecc  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_conditions as tcn  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_containers as tc  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_faults as tfl  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_filecontrol as tf  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_taskcontrol as tt  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_tdqueues as tq  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_time as tim  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_tsqueues as tsq  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_web as tw  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_conditions as CN  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_containers as CC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_faults as CFL  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as CF  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_program as CP  # noqa: E402
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
        "ggcics_faults.c",
        "ggcics_filecontrol.c",
        "ggcics_tempstorage.c",
        "ggcics_conditions.c",
        "ggcics_transientdata.c",
        "ggcics_containers.c",
        "ggcics_tempstorage.c",  # the second part: DELETEQ TS, where it sat
        "ggcics_taskcontrol.c",
        "ggcics_enq.c",
        "ggcics_web.c",  # the web family, part 1
        "ggcics_web.c",  # part 2: WEB RECEIVE SET, after the storage block
        "ggcics_web.c",  # part 3: WEB RETRIEVE and the form / browse reads
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
    assert (
        java[:at].rstrip().endswith("public record Received(String resp, int length, String data) {\n    }")
    )  # before it
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


def test_cicstask_holds_the_ts_queue_java_once_where_it_sat():
    """#5274: the TS queue family is spliced between the faults family and sendMap."""
    java = forge.CICS_TASK_JAVA
    assert java.count(tsq.TSQUEUES_JAVA) == 1
    a = java.index(tsq.TSQUEUES_JAVA)
    assert java[:a].endswith(tfl.FAULTS_JAVA)
    assert java[a + len(tsq.TSQUEUES_JAVA) :].startswith("    public void sendMap(String map, Object screen) {")
    for method in ("withTempStorage", "writeqTs", "rewriteqTs", "readqTs", "readqTsNext"):
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tsq.TSQUEUES_JAVA), method
    assert "public record TsResult(" in tsq.TSQUEUES_JAVA
    assert "public static final class TempStorage" in tsq.TSQUEUES_JAVA


def test_cicstask_holds_the_task_control_java_once_where_it_sat():
    java = forge.CICS_TASK_JAVA
    assert java.count(tt.TASKCONTROL_JAVA) == 1
    at = java.index(tt.TASKCONTROL_JAVA)
    assert java[:at].endswith("    public long taskNumber() {\n        return root().taskNumber;\n    }\n")  # before it
    assert java[at + len(tt.TASKCONTROL_JAVA) :].startswith("    /** ENQ RESOURCE(resource)")
    for method in ("withStartData", "start", "startAt", "startRequest", "runTransid", "delay", "fetch", "freeChild",
                   "retrieve", "cancel", "post", "waitEvent"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tt.TASKCONTROL_JAVA), method


def test_cicstask_holds_the_td_queue_java_once_where_it_sat():
    """#5274: the transient-data queue family is spliced between the web request part and the FORMATTIME code."""
    java = forge.CICS_TASK_JAVA
    assert java.count(tq.TDQUEUES_JAVA) == 1
    a = java.index(tq.TDQUEUES_JAVA)
    assert java[:a].endswith(tw.WEB_REQUEST_JAVA)
    assert java[a + len(tq.TDQUEUES_JAVA) :].startswith(tim.TIME_JAVA)
    for method in ("withTdQueues", "withTdQueueTypes", "withTdQueueAttributes", "setTdQueueOpenStatus", "inquireTdQueue",
                   "setTdQueueTriggerLevel", "setTdQueueEnableStatus", "writeqTd", "readqTd", "deleteqTd"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tq.TDQUEUES_JAVA), method
    assert "public record TdResult(" in tq.TDQUEUES_JAVA


def test_cicstask_holds_the_time_java_once_where_it_sat():
    """#5274: the ASKTIME / FORMATTIME code is spliced between the TD queue family and withTermid."""
    java = forge.CICS_TASK_JAVA
    assert java.count(tim.TIME_JAVA) == 1
    a = java.index(tim.TIME_JAVA)
    assert java[:a].endswith(tq.TDQUEUES_JAVA)
    assert java[a + len(tim.TIME_JAVA) :].startswith("    /** The terminal the task is attached to (#3989)")
    for method in ("formattimeCheck", "asktime", "formatDate", "formatNumber", "formatTime"):
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tim.TIME_JAVA), method
    assert "private static void refuseNegativeAbstime(" in tim.TIME_JAVA
    assert "ABSTIME_EPOCH = " in tim.TIME_JAVA


def test_cicstask_holds_the_web_java_once_per_part_where_it_sat():
    """#5274: the web family is two parts, either side of the task-storage block, each spliced where it sat."""
    java = forge.CICS_TASK_JAVA
    for part in (tw.WEB_SESSION_JAVA, tw.WEB_REQUEST_JAVA):
        assert java.count(part) == 1
    a = java.index(tw.WEB_SESSION_JAVA)
    b = java.index(tw.WEB_REQUEST_JAVA)
    assert a + len(tw.WEB_SESSION_JAVA) < b
    assert java[:a].endswith(
        "        return new DocumentData(0, 0, doc.length, doc.clone());\n    }\n\n"
    )  # DOCUMENT RETRIEVE
    mid = java[a + len(tw.WEB_SESSION_JAVA) : b]
    assert mid.startswith("    // ---- #4771 (register X47): storage CICS acquires") and "acquireReceived" in mid
    assert "public WebOpened" not in mid and "public WebHeader" not in mid  # the storage block holds no web command
    assert java[b + len(tw.WEB_REQUEST_JAVA) :].startswith("    /** The transient-data queues the CSD defines")
    for method in ("webOpenHost", "webOpenUrimap", "webConverse", "webClose", "webSend", "webSendContainer",
                   "webSendDocument", "webExtract", "extractTcpip", "webReceive"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tw.WEB_SESSION_JAVA), method
    for method in ("webReadHeader", "webWriteHeader", "webRetrieve", "webReadParam", "webStartBrowse", "webReadNext",
                   "webEndBrowse", "webParse"):  # fmt: skip
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tw.WEB_REQUEST_JAVA), method


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
    # the include sits where the block did: after DELETEQ TS, before the ENQ include
    assert (
        host.index("#define GGCICS_TS_DELETEQ")
        < host.index('#include "ggcics_taskcontrol.c"')
        < host.index('#include "ggcics_enq.c"')
    )


# ---- ENQ / DEQ (#5274, fourth stub family): one stub function; DEQ is translated inline, with no stub ---------------
def test_ggcics_holds_the_enq_stub_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_enq.c").read_text(encoding="utf-8")
    assert "#include" not in family
    assert re.search(r"^int GGCENQ\(", family, re.M) and not re.search(r"^int GGCENQ\(", host, re.M)
    assert (
        COMMANDS["ENQ"].impl is None and COMMANDS["DEQ"].impl is None
    )  # no spec impl: the harness calls GGCENQ itself
    # the include sits where the block did: after the task-control include, before GGCAOUT
    assert (
        host.index('#include "ggcics_taskcontrol.c"')
        < host.index('#include "ggcics_enq.c"')
        < host.index("int GGCAOUT(")
    )


def test_enq_still_translates_to_its_stub_and_deq_to_none():
    assert any("GGCENQ" in ln for ln in ec.translate_command("ENQ RESOURCE(WS-RES)"))
    assert not any("GGC" in ln and "CALL" in ln for ln in ec.translate_command("DEQ RESOURCE(WS-RES)"))


# ---- transient data (#5274, fifth stub family): READQ / WRITEQ / DELETEQ TD, SET / INQUIRE TDQUEUE -------------------
def test_ggcics_holds_the_transient_data_stubs_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_transientdata.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in ("GGCWRTD", "GGCRDTD", "GGCDLTD", "GGCRDTS", "GGCSTDQ", "GGCSTDE", "GGCSTDT", "GGCITDQ"):
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    for helper in ("td_dir", "td_kind", "td_uow_end"):
        assert re.search(rf"^static \w+ {helper}\(", family, re.M), helper
    # the uow code in the host calls td_uow_end, so its forward declaration stays there, before the include
    assert host.index("static void td_uow_end(int rollback);") < host.index('#include "ggcics_transientdata.c"')
    # the include sits where the block did: after the file-control include, before the containers include
    assert (
        host.index('#include "ggcics_filecontrol.c"')
        < host.index('#include "ggcics_transientdata.c"')
        < host.index('#include "ggcics_containers.c"')
    )


def test_the_td_verbs_still_translate_to_their_stubs():
    for verb, stub in (("READQ TD QUEUE('Q') INTO(WS-REC)", "GGCRDTD"), ("DELETEQ TD QUEUE('Q')", "GGCDLTD"),
                       ("WRITEQ TD QUEUE('Q') FROM(WS-REC)", "GGCWRTD")):  # fmt: skip
        assert any(stub in ln for ln in ec.translate_command(verb)), verb


# ---- temporary storage and conditions / abends (#5274, sixth and seventh stub families) ---------------------------------
def test_ggcics_holds_the_temporary_storage_stubs_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_tempstorage.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in ("GGCREADQ", "GGCWRTQ", "GGCDELQ"):
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    for helper in ("ts_dir", "ts_count", "ts_next", "ts_set_next"):
        assert re.search(rf"^static \w+ {helper}\(", family, re.M), helper
        assert not re.search(rf"^static \w+ {helper}\(", host, re.M), helper


def test_ggcics_holds_the_condition_and_abend_handlers_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_conditions.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in ("GGCPENT", "GGCHCND", "GGCHABN", "GGCPUSH", "GGCPOP", "GGCHAID", "GGCAID", "GGCABND", "GGCCOND",
                  "GGCASGN"):  # fmt: skip
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    # the include sits where the blocks did: file control, temporary storage, conditions, then transient data
    assert (
        host.index('#include "ggcics_filecontrol.c"')
        < host.index('#include "ggcics_tempstorage.c"')
        < host.index('#include "ggcics_conditions.c"')
        < host.index('#include "ggcics_transientdata.c"')
    )


def test_ggcics_holds_the_fault_injection_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_faults.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in ("GGCSQLAB",):
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    for helper in ("injected_at", "dupkey_apply", "map_not_found"):
        assert re.search(rf"^static \w+ {helper}\(", family, re.M), helper
        assert not re.search(rf"^static \w+ {helper}\(", host, re.M), helper
    for state in ("fault_counts", "fault_keys", "dupkey"):
        assert state in family and not re.search(rf"^static .*\b{state}\b", host, re.M), state
    # the include sits where the state did: after the spec header, before the file-control family that calls injected()
    assert (
        host.index('#include "ggcics_spec.h"')
        < host.index('#include "ggcics_faults.c"')
        < host.index('#include "ggcics_filecontrol.c"')
    )


def test_deleteq_ts_is_the_second_include_of_the_temporary_storage_family():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_tempstorage.c").read_text(encoding="utf-8")
    assert host.count('#include "ggcics_tempstorage.c"') == 2
    assert (
        host.index("int GGCINQA(")
        < host.index("#define GGCICS_TS_DELETEQ")
        < host.index('#include "ggcics_taskcontrol.c"')
    )
    assert family.index("#ifndef GGCICS_TS_DELETEQ") < family.index("int GGCREADQ(") < family.index("int GGCDELQ(")


def test_the_ts_verbs_still_translate_to_their_stubs():
    for verb, stub in (
        ("DELETEQ TS QUEUE('Q')", "GGCDELQ"),
        ("READQ TS QUEUE('Q') INTO(WS-REC)", "GGCREADQ"),
        ("WRITEQ TS QUEUE('Q') FROM(WS-REC)", "GGCWRTQ"),
    ):
        assert any(stub in ln for ln in ec.translate_command(verb)), verb


# ---- temporary storage (#5274, harness half): READQ / WRITEQ / DELETEQ TS and how a TS event is read back --------------
def test_the_harness_dispatches_temporary_storage_to_its_module():
    import equivalence_cics_tempstorage as ect  # noqa: E402

    for name in ("ts_command", "delete_queue", "ts_seed", "cobol_ts", "java_ts_as_compared"):
        assert callable(getattr(ect, name)), name
    for old in ("_ts_command", "_cobol_ts"):
        assert not hasattr(ec, old), old
    assert ec.ts_seed is ect.ts_seed and ec.java_ts_as_compared is ect.java_ts_as_compared
    for body, stub in (("WRITEQ TS QUEUE('Q') FROM(WS-REC)", "GGCWRTQ"), ("READQ TS QUEUE('Q') INTO(WS-REC)", "GGCREADQ"),
                       ("DELETEQ TS QUEUE('Q')", "GGCDELQ")):  # fmt: skip
        assert any(stub in ln for ln in ec.translate_command(body)), body


# ---- task / interval control (#5274, harness half): START / RETRIEVE / CANCEL, RUN, FETCH, FREE, DELAY, POST, WAIT, CONVERSE --
def test_the_harness_dispatches_task_control_to_its_module():
    import equivalence_cics_taskcontrol as ectc  # noqa: E402

    names = ("_interval_command", "_run_transid", "_fetch_child", "_free_child", "_delay", "_post", "_wait_event",
             "_converse", "_cobol_start", "_cobol_retrieve", "java_start_as_compared", "java_retrieve_as_compared")  # fmt: skip
    for name in names:
        assert callable(getattr(ectc, name)), name
    for old in names[:-4] + ("_cobol_start",):
        assert not hasattr(ec, old), old
    assert ec.java_start_as_compared is ectc.java_start_as_compared
    assert ec.java_retrieve_as_compared is ectc.java_retrieve_as_compared and ec._cobol_retrieve is ectc._cobol_retrieve
    for body, stub in (("START TRANSID('ABCD') INTERVAL(10)", "GGCSTRT"), ("RETRIEVE INTO(WS-REC)", "GGCRTRV"),
                       ("CANCEL REQID('R1')", "GGCCNCL"), ("RUN TRANSID('ABCD') CHILD(WS-TOK)", "GGCRUNT"),
                       ("FETCH CHILD(WS-TOK)", "GGCFETCH"), ("FETCH ANY(WS-TOK)", "GGCFETCH"),
                       ("FREE CHILD(WS-TOK)", "GGCFREE"), ("DELAY INTERVAL(5)", "GGCDLAY"),
                       ("POST INTERVAL(5)", "GGCPOST"), ("WAIT EVENT ECADDR(WS-PTR)", "GGCWEVT"),
                       ("CONVERSE FROM(WS-OUT) INTO(WS-IN)", "GGCCONV")):  # fmt: skip
        assert any(stub in ln for ln in ec.translate_command(body)), body


# ---- conditions (#5274, harness half): HANDLE CONDITION / AID / ABEND, PUSH / POP HANDLE, ASSIGN, AID after input -----
def test_the_harness_dispatches_conditions_to_its_module():
    import equivalence_cics_conditions as ecc  # noqa: E402

    for name in ("aid", "input_resp", "handle", "handler_labels"):
        assert callable(getattr(ecc, name)), name
    for old in ("_aid", "_input_resp", "_handle", "AID_KEYS", "_HANDLE_KINDS"):
        assert not hasattr(ec, old), old
    assert ec.handler_labels is ecc.handler_labels
    assert ecc.handler_labels(["HANDLE CONDITION ERROR(E1)", "HANDLE AID PF3(P3)"]) == ["E1", "P3"]
    for body, stub in (("HANDLE CONDITION ERROR(ANY-ERROR)", "GGCHCND"), ("HANDLE AID PF3(DONE)", "GGCHAID"),
                       ("HANDLE ABEND CANCEL", "GGCHABN"), ("PUSH HANDLE", "GGCPUSH"), ("POP HANDLE", "GGCPOP"),
                       ("ASSIGN ABCODE(WS-AB)", "GGCASGN")):  # fmt: skip
        assert any(stub in ln for ln in ec.translate_command(body, ["ANY-ERROR", "DONE"])), body


# ---- conditions (#5274, det half): ASSIGN, the conditions a HANDLE / IGNORE names, HANDLE AID, PUSH / POP HANDLE ---------
CONDITION_METHODS = ("assign", "conditions", "handle_aid_", "push_pop", "input_outcome")


def test_the_det_translator_holds_the_condition_methods_in_its_mixin():
    assert issubclass(C.Cics, CN.ConditionCommands)
    for method in CONDITION_METHODS:
        assert method in vars(CN.ConditionCommands) and method not in vars(C.Cics), method
        assert callable(getattr(C.Cics, method)), method
    for key, cmd in COMMANDS.items():  # every spec command that dispatches to a moved method still reaches it
        if cmd.impl and cmd.impl.translator.split(".")[1] in CONDITION_METHODS:
            assert callable(getattr(C.Cics, cmd.impl.translator.split(".")[1])), key
    assert "outcome" in vars(C.Cics)  # shared with every family: it stays the translator's own


# ---- conditions (#5274, forge half): ASSIGN, HANDLE ABEND, PUSH / POP HANDLE, ABEND, RESP / abend-code names --------
CONDITION_JAVA_METHODS = ("assignApplid", "assignSysid", "assignStartcode", "assignUserid", "assignTerminalResp",
                          "statedTerminal", "assignFacility", "assignScreen", "invokingProgram", "handleAbend",
                          "handleAbendCancel", "handleAbendReset", "pushHandle", "popHandle", "abend", "abendCancel",
                          "abendOnCondition", "abendMapNotFound", "abendToExit", "abendExit", "abcode", "respName",
                          "abcodeFor", "record")  # fmt: skip


def _java_methods(java: str) -> list[str]:
    return re.findall(r"^    (?:public |private |static )+(?:<\w+> )?[\w<>\[\], ]+? (\w+)\(.*\{$", java, re.M)


def test_cicstask_holds_the_conditions_java_once_as_one_span():
    java = forge.CICS_TASK_JAVA
    assert java.count(tcn.CONDITIONS_JAVA) == 1
    assert java[java.index(tcn.CONDITIONS_JAVA) + len(tcn.CONDITIONS_JAVA) :].startswith(
        "    private CicsTask root() {"
    )
    in_family = _java_methods(tcn.CONDITIONS_JAVA)
    for method in CONDITION_JAVA_METHODS:
        assert method in in_family, method
    host = java.replace(tcn.CONDITIONS_JAVA, "")
    for method in CONDITION_JAVA_METHODS:
        assert method not in _java_methods(host), method  # none left behind, scattered, in the host
    assert "root" in _java_methods(host)  # shared with every family: it stays the class's own


def test_every_condition_method_the_forge_emitted_before_the_split_is_still_emitted():
    # the 24 moved methods, not their order: the generated class is the same bar the order
    assert (
        len(_java_methods(tcn.CONDITIONS_JAVA)) == 25
    )  # abend is overloaded: public abend(abcode) and private abend(...)
    assert "ASSIGN ABCODE" in tcn.CONDITIONS_JAVA and "HANDLE ABEND LABEL" in tcn.CONDITIONS_JAVA


# ---- faults (#5274, forge half): withFaults, injected, fileFault and undefinableFile (#6839), logFault, logAbend, planned, the deferred DUPKEY ---------------
FAULT_JAVA_METHODS = (
    "withFaults",
    "dupkeyOr",
    "logFault",
    "logAbend",
    "injected",
    "fileFault",
    "undefinableFile",
    "planned",
    "rcode",
    "rcodeOf",
)


def test_cicstask_holds_the_faults_java_once_as_one_span():
    java = forge.CICS_TASK_JAVA
    assert java.count(tfl.FAULTS_JAVA) == 1
    in_family = _java_methods(tfl.FAULTS_JAVA)
    assert sorted(in_family) == sorted(FAULT_JAVA_METHODS)
    host = java.replace(tfl.FAULTS_JAVA, "")
    for method in FAULT_JAVA_METHODS:
        assert method not in _java_methods(host), method  # none left behind, scattered, in the host
    for field in ("deferredDupkey", "deferredWhat"):
        assert f" {field}" in tfl.FAULTS_JAVA and f" {field};" not in host, field
    for shared in ("root", "abend", "respName"):  # the other families' and the class's own
        assert shared in _java_methods(host), shared


def test_every_fault_member_the_forge_emitted_before_the_split_is_still_emitted():
    assert "faults.cfg: `CMD FILE NTH RESP [RESP2]`" in tfl.FAULTS_JAVA
    assert "`CMD FILE NTH -1 0 ABCODE` abends the task" in tfl.FAULTS_JAVA  # #6271 (X70)
    assert "private List<String[]> faultPlan" in forge.CICS_TASK_JAVA  # the state stays in the class header


# ---- faults (#5274, det half): HANDLE ABEND, ABEND, the ABM0 abend, the abend-exit check ------------------------------
FAULT_METHODS = ("abend_exit", "handle_abend_", "abend", "map_not_found")


class _FaultCics(CFL.FaultCommands):
    """Just the members the faults mixin reads: a Gen with a paragraph index, a temp-name counter and a jump."""

    def __init__(self, mapsets=None):
        class G:
            para_index = {"EXIT-PARA": 3}
            n = 0

            def tmpname(self, base):
                self.n += 1
                return f"{base}{self.n}"

            def jump(self, target):
                return f"jump {target};"

        class GP:
            pass

        self.g = G()
        self.gp = GP()
        self.gp.mapsets = mapsets or {}

    def name(self, text):
        return text

    def file_name(self, text):
        return text


def test_the_det_translator_holds_the_fault_methods_in_its_mixin():
    assert issubclass(C.Cics, CFL.FaultCommands)
    for method in FAULT_METHODS:
        assert method in vars(CFL.FaultCommands) and method not in vars(C.Cics), method
    assert "outcome" in vars(C.Cics) and "handle_abend" not in vars(CFL.FaultCommands)  # shared: stays the host's
    assert issubclass(C.Cics, CN.ConditionCommands)  # PUSH / POP HANDLE stay with the conditions family


def test_handle_abend_and_abend_emit_what_they_did_in_the_host():
    f = _FaultCics()
    assert f.handle_abend_({"LABEL": "exit-para"}, "  ") == ['  task.handleAbend("EXIT-PARA");']
    assert f.handle_abend_({"CANCEL": None}, "") == ["task.handleAbendCancel();"]
    assert f.handle_abend_({"RESET": None}, "") == ["task.handleAbendReset();"]
    for opts, why in (({}, "without LABEL"), ({"LABEL": "NOPE"}, "no such paragraph")):
        with pytest.raises(C.CicsError, match=why):
            f.handle_abend_(opts, "")
    assert _FaultCics().abend({"ABCODE": "'ABC1'"}, "") == [
        "String exit1 = task.abend('ABC1');",
        "if (exit1 == null) throw abended();",
        "if (true) jump paragraph(exit1);",
    ]
    assert _FaultCics().abend({"CANCEL": None}, "")[0] == 'String exit1 = task.abendCancel("");'


def test_map_not_found_is_the_abm0_abend_only_for_a_map_its_mapset_lacks():
    mapsets = {"MS1": ["MAP1"]}
    assert _FaultCics(mapsets).map_not_found("MAP1", "MS1", "") is None  # the mapset holds it
    assert _FaultCics(mapsets).map_not_found("X", "NOT-A-MAPSET", "") is None  # not a mapset of the estate
    lines = _FaultCics(mapsets).map_not_found("MAP2", "MS1", "")
    assert lines[0] == 'String exit1 = task.abendMapNotFound("MAP2", "MS1");' and len(lines) == 3


def test_the_abend_exit_check_is_one_shape_after_a_link_and_after_an_injected_file_abend():
    lines = _FaultCics().abend_exit("    ")
    assert lines == [
        "    String exit1 = task.abendExit();",
        "    if (exit1 != null) jump paragraph(exit1);",
        "    if (task.ended()) throw abended();",
    ]
    src = "".join(Path(m.__file__).read_text(encoding="utf-8") for m in (C, CP))
    assert src.count("self.abend_exit(ind)") == 2 and "task.abendExit()" not in src  # LINK and the file command


# ---- faults (#5274, harness half): the scenario fault-injection planner, IBM's conditions and RESP2 per command -------
def test_the_harness_dispatches_faults_to_its_module():
    import equivalence_cics_faults as ecf  # noqa: E402

    for name in ("fault_lines", "dli_fault_lines", "enq_fault_key", "FAULT_COMMANDS", "UI_FAULT_CONDITIONS",
                 "FILE_FAULT_CONDITIONS", "LINK_REFUSED_CONDITIONS", "_file_fault_resp2", "_ui_fault_resp2",
                 "_abend_fault_line"):  # fmt: skip
        assert hasattr(ecf, name), name
    for old in ("_file_fault_resp2", "_ui_fault_resp2", "_abend_fault_line", "_FAULT_NAME", "FILE_FAULT_REFUSED"):
        assert not hasattr(ec, old), old
    for name in ("fault_lines", "dli_fault_lines", "enq_fault_key", "FAULT_COMMANDS", "UI_FAULT_CONDITIONS",
                 "FILE_FAULT_CONDITIONS", "LINK_REFUSED_CONDITIONS"):  # fmt: skip
        assert getattr(ec, name) is getattr(ecf, name), name
    assert "CICS_RESP" in vars(ec) and "CICS_RESP" not in vars(ecf)  # built from the host's DFHRESP: stays there


def test_fault_lines_cover_each_planning_family():
    plans = (
        ({"cmd": "READ", "file": "F", "resp": "NOTFND"}, "READ F 1 13 80"),  # file control, IBM's RESP2
        ({"cmd": "ROLLBACK", "resp": "INVREQ"}, "ROLLBACK - 1 16 200"),  # terminal / unit of work
        ({"cmd": "ENQ", "resource": "ws-res ", "resp": "ENQBUSY"}, "ENQ WS-RES 1 55 0"),
        ({"cmd": "READQ-TD", "queue": "Q", "resp": "IOERR"}, f"READQ-TD Q 1 {ec.CICS_RESP['IOERR']} 0"),
        ({"cmd": "XCTL", "program": "P", "resp": "PGMIDERR", "resp2": 3}, "XCTL P 1 27 3"),
        ({"cmd": "READ", "file": "F", "resp": "ABEND", "abcode": "AFCR"}, "READ F 1 -1 0 AFCR"),
    )
    for plan, line in plans:
        assert ec.fault_lines({"name": "s", "faults": [plan]}) == [line], plan
    assert ec.fault_lines({"name": "s", "sql_abend_plan": ["SQL P:1 1 -1 0 AD2Z"]}) == ["SQL P:1 1 -1 0 AD2Z"]
    with pytest.raises(ec.Unsupported):
        ec.fault_lines({"name": "s", "faults": [{"cmd": "DELETE", "file": "F", "resp": "DUPKEY"}]})  # register X48
    assert ec.dli_fault_lines({"ims": {}}, {"name": "s"}) == []
    assert any("GGCENQ" in ln for ln in ec.translate_command("ENQ RESOURCE(WS-RES)"))


# ---- web (#5274, harness half): the HTTP scenario inputs, the WEB / EXTRACT TCPIP translators, the web event readers ----
def test_the_harness_dispatches_web_to_its_module():
    import equivalence_cics_web as ecw  # noqa: E402

    moved = ("_web_requires", "_web_parse", "_web_send", "_web_extract", "_extract_tcpip", "_web_receive", "_web_retrieve",
             "_web_header", "_web_forms", "_web", "_WEB_KIND", "_cobol_web", "_cobol_web_open", "_cobol_web_send",
             "_cobol_web_header", "_cobol_web_receive", "http_peers", "http_peers_cfg", "http_request",
             "http_request_cfg", "tcpip", "tcpip_cfg")  # fmt: skip
    for name in moved:
        assert hasattr(ecw, name), name
    for old in moved[:11]:  # the translators left the host (the event readers stay reachable as aliases)
        assert not hasattr(ec, old), old
    for name in ("http_peers", "http_peers_cfg", "http_request", "http_request_cfg", "tcpip", "tcpip_cfg",
                 "_cobol_web", "_cobol_web_open", "_cobol_web_send", "_cobol_web_header"):  # fmt: skip
        assert getattr(ec, name) is getattr(ecw, name), name
    for shared in ("_pointer", "_getmain", "_freemain", "_address", "mapsets_env", "doctemplates"):
        assert hasattr(ec, shared) and not hasattr(ecw, shared), shared  # not web: they stay in the host


def test_the_web_translators_reach_the_hosts_helpers_and_refuse_by_name():
    lines = ec.translate_command(
        "WEB CONVERSE SESSTOKEN(WS-TOK) PATH(WS-PATH) PATHLENGTH(WS-PL) METHOD(WS-M) INTO(WS-IN)"
    )
    assert any("GGCWCNV" in ln for ln in lines)  # the host's _call / _resp, reached through `ec.`
    with pytest.raises(ec.Unsupported, match="WEB CONVERSE without METHOD"):
        ec.translate_command("WEB CONVERSE SESSTOKEN(WS-TOK) INTO(WS-IN)")


# ---- web (#5274, slice 2 of the stub): WEB *, EXTRACT TCPIP -- three guarded parts around the storage block ------------
WEB_ENTRIES = ("GGCWOPN", "GGCWCNV", "GGCWCLS", "GGCWPRS", "GGCWSND", "GGCWSDC", "GGCWSCT", "GGCWEXT", "GGCTCPX",
               "GGCTCPN", "GGCWRCV", "GGCWRDH", "GGCWWRH", "GGCWRCS", "GGCWRTV", "GGCWRDP", "GGCWSBR", "GGCWRNX",
               "GGCWEBR")  # fmt: skip


def test_ggcics_holds_the_web_stubs_in_its_family_file():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_web.c").read_text(encoding="utf-8")
    assert "#include" not in family
    for entry in WEB_ENTRIES:
        assert re.search(rf"^int {entry}\(", family, re.M), entry
        assert not re.search(rf"^int {entry}\(", host, re.M), entry
    # the document and file-control WRITE stubs are not web: they stay in the host
    assert re.search(r"^int GGCWTO\(", host, re.M) and re.search(r"^int GGCWRIT\(", host, re.M)
    # every spec command that dispatches to a web or TCPIP stub has it in the family file
    for key, cmd in COMMANDS.items():
        if (
            cmd.impl
            and cmd.impl.c
            and re.match(r"GGC(W|TCP)", cmd.impl.c)
            and cmd.impl.c not in ("GGCWTO", "GGCWRIT", "GGCWEVT")
        ):
            assert re.search(rf"^int {cmd.impl.c}\(", family, re.M), key


def test_the_web_parts_are_included_around_the_storage_block():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    at = [m.start() for m in re.finditer(r'^#include "ggcics_web\.c"', host, re.M)]
    assert len(at) == 3
    assert host.index("int GGCEND(") < at[0] < host.index("enum { BLK_GETMAIN") < at[1] < host.index("int GGCRECP(")
    assert host.index("int GGCGETS(") < at[2]
    assert host.index("#define GGCICS_WEB_PART2") < at[1] < host.index("#undef GGCICS_WEB_PART2")
    assert host.index("#define GGCICS_WEB_PART3") < at[2] < host.index("#undef GGCICS_WEB_PART3")
    assert host.index("int GGCADDR(") < at[1]  # WEB RECEIVE SET needs blk_set_new, defined before it


def test_an_undefinable_file_name_answers_filenotfound_with_resp2_1():
    # #6839 row I, register X75: IBM's "not defined to CICS" is RESP2 1, as the stub answers it
    assert "return new int[] {12, 1};" in tfl.FAULTS_JAVA
    assert "{12, 0}" not in tfl.FAULTS_JAVA


# ---- #7153: equivalence_cics re-exports its families' names lazily, so import order does not matter ------------------
_TOOLS = Path(__file__).resolve().parents[1] / "tools"
_FAMILY_MODULES = ("conditions", "containers", "faults", "filecontrol", "taskcontrol", "tempstorage", "web")


def test_equivalence_cics_holds_no_import_time_copy_of_a_family_name():
    import ast

    tree = ast.parse((_TOOLS / "equivalence_cics.py").read_text(encoding="utf-8"))
    copies = [
        n.targets[0].id
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and isinstance(n.value, ast.Attribute)
        and isinstance(n.value.value, ast.Name)
        and n.value.value.id.startswith("cics_")
    ]
    assert copies == []


@pytest.mark.parametrize("first", ("cics", *("cics_" + f for f in _FAMILY_MODULES)))
def test_every_reexported_name_resolves_whichever_module_is_imported_first(first):
    import subprocess

    code = (
        f"import sys; sys.path[:0] = [{str(_TOOLS)!r}, {str(ROOT)!r}]\n"
        f"import equivalence_{first}\n"
        "import equivalence_cics as ec\n"
        "for name, fam in ec._FAMILY_NAMES.items():\n"
        "    assert getattr(ec, name) is getattr(fam, name), name\n"
        "assert len(ec._FAMILY_NAMES) == 24\n"
        "try:\n    ec.no_such_name\nexcept AttributeError:\n    pass\n"
        "else:\n    raise SystemExit('no AttributeError')\n"
    )
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
