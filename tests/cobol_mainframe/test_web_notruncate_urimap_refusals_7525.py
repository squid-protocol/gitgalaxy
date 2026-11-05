"""#7525: WEB CONVERSE URIMAP / NOTRUNCATE and WEB RECEIVE NOTRUNCATE stay refused by name, each with IBM's wording or
silence as the reason; both translators read the spec entry."""

from __future__ import annotations

import pytest

from gitgalaxy.standards.cics.commands.web import WEB_CONVERSE, WEB_RECEIVE

CONVERSE = "WEB CONVERSE SESSTOKEN(KEY) METHOD(R) INTO(AREA) "


def test_the_spec_names_why_each_form_is_refused():
    cases = (
        (WEB_CONVERSE.refused["URIMAP"], ("this request only", "forbids PATH")),
        (WEB_CONVERSE.refused["NOTRUNCATE"], ("RESP2 36", "later WEB CONVERSE")),
        (WEB_RECEIVE.refused["NOTRUNCATE"], ("RESP2 36", "repeat", "partial")),
    )
    for r, words in cases:
        for w in words:
            assert w in r.why


@pytest.mark.parametrize("opt,match", [("NOTRUNCATE", "RESP2 36"), ("URIMAP(UM)", "this request only")])
def test_det_translator_refuses_the_converse_option_by_name(opt, match):
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    with pytest.raises(ec.Unsupported, match=match):
        ec.translate_command(CONVERSE + opt)
