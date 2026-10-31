"""#5079 (register X58): READ / READNEXT / READPREV SET(ADDRESS OF record) on the cobol-stub translator.

SET(pointer) hands the stub the pointer itself; SET(ADDRESS OF rec) hands it GG-PTR and lays the LINKAGE record over the
block only when a record came (READ: NORMAL or DUPKEY, browse: NORMAL), so NOTFND and ENDFILE leave the address as it was.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

_STUB = {"READ": "GGCRDST", "READNEXT": "GGCRDNS", "READPREV": "GGCRDPS"}
_GUARD = {"READ": "IF GG-RESP = 0 OR GG-RESP = 15", "READNEXT": "IF GG-RESP = 0", "READPREV": "IF GG-RESP = 0"}
_LENGTH = {"READ": " LENGTH(L)", "READNEXT": "", "READPREV": ""}


@pytest.mark.parametrize("verb", sorted(_STUB))
def test_address_of_is_set_only_on_a_delivered_record(verb):
    out = ec.translate_command(f"{verb} FILE('F') SET(ADDRESS OF LS-REC) RIDFLD(K){_LENGTH[verb]} RESP(R)")
    text = "\n".join(out)
    assert f"CALL '{_STUB[verb]}' USING GG-CICS" in text
    assert "BY REFERENCE GG-PTR" in text
    i = out.index(_GUARD[verb])
    assert out[i + 1] == "    SET ADDRESS OF LS-REC TO GG-PTR"
    assert out[out.index("END-IF", i) + 1].startswith(
        "MOVE GG-RESP TO EIBRESP"
    )  # (the response is read after the guard)
    assert text.count("SET ADDRESS OF") == 1


@pytest.mark.parametrize("verb", sorted(_STUB))
def test_a_plain_pointer_is_passed_as_it_was(verb):
    text = "\n".join(ec.translate_command(f"{verb} FILE('F') SET(PTR) RIDFLD(K) RESP(R)"))
    assert "BY REFERENCE PTR" in text
    assert "GG-PTR" not in text
    assert "SET ADDRESS OF" not in text


@pytest.mark.parametrize("verb", sorted(_STUB))
def test_what_neither_form_names_is_still_refused(verb):
    for bad in ("SET(A OF B)", "SET(ADDRESS OF A OF B)", "SET(TBL(1))"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(f"{verb} FILE('F') {bad} RIDFLD(K)")
