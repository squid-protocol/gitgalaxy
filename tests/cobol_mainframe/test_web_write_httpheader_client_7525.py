"""#7525: WEB WRITE HTTPHEADER SESSTOKEN (the client form) is refused by name, with IBM's silence as the reason, and the
spec entry is what both translators read. The server form (no SESSTOKEN) still translates."""

from __future__ import annotations

import pytest

from gitgalaxy.standards.cics.commands.web import WEB_WRITE_HTTPHEADER

CLIENT = "WEB WRITE HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) SESSTOKEN(WS-TOK)"


def test_the_spec_names_why_the_client_form_is_refused():
    r = WEB_WRITE_HTTPHEADER.refused["SESSTOKEN"]
    for words in ("client form", "which request", "persists", "INVREQ RESP2 19"):
        assert words in r.why


def test_equivalence_translator_refuses_the_client_form_by_name():
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    with pytest.raises(ec.Unsupported, match="which request the header goes on"):
        ec.translate_command(CLIENT)
