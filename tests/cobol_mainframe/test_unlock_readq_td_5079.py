"""#5079 (registers X52, X57): the options of UNLOCK and the TD queue commands, each class member on both translators.

IBM (EXEC CICS UNLOCK, READQ TD, WRITEQ TD, DELETEQ TD): SYSID names a remote system, which the region does not model, so
it is refused by name with that reason; the options a command models translate. The det port (check_options) and the
stub's harness (equivalence_cics.translate_command) must answer alike."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

_MODELLED = (
    "UNLOCK FILE('F')",
    "UNLOCK FILE('F') TOKEN(T)",
    "READQ TD QUEUE('CSSL') INTO(REC) LENGTH(LEN)",
    "WRITEQ TD QUEUE('CSSL') FROM(REC) LENGTH(LEN)",
    "DELETEQ TD QUEUE('CSSL')",
)


@pytest.mark.parametrize("cmd", _MODELLED)
def test_the_modelled_forms_translate_on_the_stub(cmd):
    assert ec.translate_command(cmd)


@pytest.mark.parametrize("cmd", _MODELLED)
def test_sysid_is_refused_by_name_on_both_translators(cmd):
    remote = cmd + " SYSID('RMT1')"
    with pytest.raises(ec.Unsupported, match=r"SYSID: option not modelled .*remote system"):
        ec.translate_command(remote)
    words = cmd.split("(")[0].split()
    words = words[: 2 if words[0] in ("READQ", "WRITEQ", "DELETEQ") else 1]
    with pytest.raises(C.CicsError, match=r"SYSID: option not modelled .*remote system"):
        C.check_options(words, {"SYSID": "'RMT1'"})
