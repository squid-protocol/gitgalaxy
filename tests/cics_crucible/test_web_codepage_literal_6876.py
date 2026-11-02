"""#6876 (X37 / X38): WEB SEND / WEB RECEIVE take CHARACTERSET + HOSTCODEPAGE only as the one literal pair the burned
programs state (GTHECHO, GTWRECV, GTWSEND: CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037')), and WEB READ / WRITE HTTPHEADER
take a literal header name (WRITE: a literal value too). Every other pair is refused by name on BOTH translators, so the
pair is checked, not dropped. The oracle is GnuCOBOL plus our stub, not z/OS (register X37, ASSUMED)."""

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

from gitgalaxy.tools.cobol_to_java.det.cics_web import code_page_pair_refusal  # noqa: E402
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
    """The stub translator's lines for `text` (a verb word, then the options)."""
    first, _, rest = text.partition(" ")
    opts = {first: None}
    for m in re.finditer(r"([A-Z]+)(?:\((.*?)\))?(?=\s+[A-Z]+(?:\(|\s|$)|$)", rest):
        opts[m.group(1)] = m.group(2)
    return stub.command("WEB", opts, [], [], False)


GOOD = "CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037')"
BAD = {
    "other charset": "CHARACTERSET('utf-8') HOSTCODEPAGE('037')",
    "other host page": "CHARACTERSET('iso-8859-1') HOSTCODEPAGE('1047')",
    "data area": "CHARACTERSET(X8) HOSTCODEPAGE('037')",
    "data area page": "CHARACTERSET('iso-8859-1') HOSTCODEPAGE(X8)",
    "charset alone": "CHARACTERSET('iso-8859-1')",
    "page alone": "HOSTCODEPAGE('037')",
    "client page": "CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037') CLNTCODEPAGE('037')",
}
SEND = "SEND FROM(X8) FROMLENGTH(N) MEDIATYPE(X8) SRVCONVERT {} RESP(R)"
RECV = "RECEIVE INTO(X8) MAXLENGTH(N) LENGTH(N) MEDIATYPE(X8) SRVCONVERT {} RESP(R)"


@pytest.mark.parametrize("cmd", [SEND, RECV], ids=["send", "receive"])
def test_the_identity_pair_is_accepted_on_both_translators(cmd):
    assert "task.web" in _det(f"WEB {cmd.format(GOOD)}")
    assert _stub(cmd.format(GOOD))


@pytest.mark.parametrize("cmd", [SEND, RECV], ids=["send", "receive"])
@pytest.mark.parametrize("why", sorted(BAD))
def test_every_other_pair_is_refused_by_name_on_both_translators(cmd, why):
    text = cmd.format(BAD[why])
    with pytest.raises(CicsError, match="CODEPAGE|CHARACTERSET"):
        _det(f"WEB {text}")
    with pytest.raises(ec.Unsupported, match="CODEPAGE|CHARACTERSET"):
        _stub(text)


def test_the_pair_check_is_case_blind_on_the_values_only():
    assert code_page_pair_refusal({"CHARACTERSET": "'ISO-8859-1'", "HOSTCODEPAGE": "'037'"}, "WEB SEND") is None
    assert code_page_pair_refusal({}, "WEB SEND") is None
    assert code_page_pair_refusal({"CHARACTERSET": None, "HOSTCODEPAGE": "'037'"}, "WEB SEND")


@pytest.mark.parametrize("quote", ["'", '"'])
def test_a_literal_header_name_and_value_are_lowered(quote):
    q = quote
    read = _det(f"WEB READ HTTPHEADER({q}X-Tag{q}) NAMELENGTH(N) VALUE(X8) VALUELENGTH(N) RESP(R)")
    assert 'webReadHeader("X-Tag", ' in read
    write = _det(f"WEB WRITE HTTPHEADER({q}X-Reply{q}) NAMELENGTH(N) VALUE({q}ok{q}) VALUELENGTH(N) RESP(R)")
    assert 'webWriteHeader("X-Reply", ' in write and '"ok"' in write
    assert _stub(f"READ HTTPHEADER({q}X-Tag{q}) NAMELENGTH(N) VALUE(X8) VALUELENGTH(N) RESP(R)")
    assert _stub(f"WRITE HTTPHEADER({q}X-Reply{q}) NAMELENGTH(N) VALUE({q}ok{q}) VALUELENGTH(N) RESP(R)")


def test_a_data_area_header_still_lowers_and_a_literal_read_value_is_refused():
    assert "Cobol.text(" in _det("WEB WRITE HTTPHEADER(X8) NAMELENGTH(N) VALUE(X8) VALUELENGTH(N) RESP(R)")
    with pytest.raises(Exception, match="written to"):
        _det("WEB READ HTTPHEADER('X') NAMELENGTH(N) VALUE('v') VALUELENGTH(N) RESP(R)")
    with pytest.raises(ec.Unsupported, match="written to"):
        _stub("READ HTTPHEADER('X') NAMELENGTH(N) VALUE('v') VALUELENGTH(N) RESP(R)")


def test_a_literal_media_type_and_a_literal_header_value_length_are_input_only():
    send = "SEND FROM(X8) FROMLENGTH(N) MEDIATYPE('text/plain') SRVCONVERT " + GOOD + " RESP(R)"
    assert '"text/plain"' in _det("WEB " + send)
    assert _stub(send)
    read = "READ HTTPHEADER('X-Tag') NAMELENGTH(6) VALUE(X8) VALUELENGTH(3) RESP(R)"
    assert "webReadHeader" in _det("WEB " + read)
    assert _stub(read)


def test_the_http_peer_body_ignores_trailing_blanks_and_nothing_else():
    """SPEC 6.1: trailing blanks are optional in a stated text (GTWRECV sends a 107-byte line, the peer states it trimmed)."""
    import test_cics_http_driver_4767 as drv

    case = drv._case("RCV=00 V=alpha")
    sc = {"requests": [drv._req(0)]}
    assert drv.runner.http_peer_log(case, sc, [drv._task(0, "RCV=00 V=alpha     ")]) == {}
    assert "the peer states" in drv.runner.http_peer_log(case, sc, [drv._task(0, "RCV=00  V=alpha")])["http_peer"]
    assert "the peer states" in drv.runner.http_peer_log(case, sc, [drv._task(0, " RCV=00 V=alpha")])["http_peer"]
