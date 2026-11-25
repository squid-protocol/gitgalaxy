"""#8059 (X38, extends #6876): WEB READ / STARTBROWSE of FORMFIELD take CHARACTERSET('iso-8859-1') + HOSTCODEPAGE('037') and of
QUERYPARM HOSTCODEPAGE('037') only as literals, as a no-op; every other form is refused by name on BOTH translators."""

import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cobol_mainframe"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_web as stub  # noqa: E402
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det.cics_common import CicsError  # noqa: E402


class _Item:
    category = "ALPHANUMERIC"


class _Cics(_LenCics):
    def __init__(self):
        super().__init__()
        self.g.resolve = lambda ref: _Item()
        self.g.field_expr = lambda ref: f"f_{ref.name}"
        self.SIZES = {**self.SIZES, "X8": "8"}


def _det(text):
    return "\n".join(_Cics().command(text, ""))


def _stub(text):
    first, _, rest = text.partition(" ")
    opts = {first: None}
    for m in re.finditer(r"([A-Z]+)(?:\((.*?)\))?(?=\s+[A-Z]+(?:\(|\s|$)|$)", rest):
        opts[m.group(1)] = m.group(2)
    return stub.command("WEB", opts, [], [], False)


FORM = "'iso-8859-1'"
READ_FORM = "READ FORMFIELD(X8) NAMELENGTH(N) VALUE(X8) VALUELENGTH(N) {} RESP(R)"
READ_QP = "READ QUERYPARM(X8) NAMELENGTH(N) VALUE(X8) VALUELENGTH(N) {} RESP(R)"
GOOD = {
    "form": (READ_FORM, f"CHARACTERSET({FORM}) HOSTCODEPAGE('037')"),
    "form none": (READ_FORM, ""),
    "qp": (READ_QP, "HOSTCODEPAGE('037')"),
    "qp none": (READ_QP, ""),
}
BAD = {
    "form other charset": (READ_FORM, "CHARACTERSET('utf-8') HOSTCODEPAGE('037')"),
    "form other page": (READ_FORM, f"CHARACTERSET({FORM}) HOSTCODEPAGE('1047')"),
    "form half pair": (READ_FORM, f"CHARACTERSET({FORM})"),
    "form data area": (READ_FORM, "CHARACTERSET(X8) HOSTCODEPAGE('037')"),
    "form client page": (READ_FORM, f"CHARACTERSET({FORM}) HOSTCODEPAGE('037') CLNTCODEPAGE('037')"),
    "qp other page": (READ_QP, "HOSTCODEPAGE('1047')"),
    "qp data area": (READ_QP, "HOSTCODEPAGE(X8)"),
}


@pytest.mark.parametrize("name", sorted(GOOD))
def test_the_identity_literals_are_accepted_on_both_translators(name):
    cmd, opts = GOOD[name]
    text = cmd.format(opts)
    assert "task.web" in _det(f"WEB {text}")
    assert _stub(text)


@pytest.mark.parametrize("name", sorted(BAD))
def test_every_other_form_is_refused_by_name_on_both_translators(name):
    cmd, opts = BAD[name]
    text = cmd.format(opts)
    with pytest.raises(CicsError, match="CODEPAGE|CHARACTERSET|code-page"):
        _det(f"WEB {text}")
    with pytest.raises(ec.Unsupported, match="CODEPAGE|CHARACTERSET|code-page"):
        _stub(text)
