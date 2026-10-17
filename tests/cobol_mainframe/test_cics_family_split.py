"""#5274: a CICS command family split out of the four hot files (the forge's CicsTask, the stub ggcics.c, the harness's
stub translator equivalence_cics.py, the det translator det/cics.py) still runs where it always did: each family module
is spliced, included or dispatched to exactly once, and each command the spec names is implemented in its family's
module, not left behind in the host file. Containers / channels (#4270, #4951, #5005) is the first family moved."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_containers as ecc  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cics_task_containers as tc  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics_containers as CC  # noqa: E402

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


def test_ggcics_includes_its_containers_family_once():
    host = (STUB / "ggcics.c").read_text(encoding="utf-8")
    family = (STUB / "ggcics_containers.c").read_text(encoding="utf-8")
    assert re.findall(r'^#include "(ggcics_\w+\.c)"', host, re.M) == ["ggcics_containers.c"]
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
