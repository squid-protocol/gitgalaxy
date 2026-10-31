"""#6876: a keyed CICS file whose generated entity states no key is refused with the reason, not a bare "no key"
(cics-crucible hc-file-unlock / HCUNLK: READ UPDATE ... RIDFLD(WS-KEY) with WS-KEY outside the record)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gitgalaxy.tools.cobol_to_java.det import cics  # noqa: E402

_HEADS = {
    "stated": " * Key: ACCT-ID (offset 0, 4 bytes)\n",
    "todo": " * Key: TODO: no key is known (no IDCAMS DEFINE, RIDFLD or RECORD KEY): carried as the String vsamKey.\n",
    "absent": " * CICS files: HCUF.\n",
}


def _generated(tmp_path, head):
    d = tmp_path / "entity" / "vsam"
    d.mkdir(parents=True)
    (d / "WsRec.java").write_text(f"/**\n{head} */\npublic class WsRec {{}}\n", encoding="utf-8")
    g = object.__new__(cics.Generated)
    g.java = tmp_path
    return g


def test_a_stated_key_is_read(tmp_path):
    assert _generated(tmp_path, _HEADS["stated"]).entity_key("WsRec", None) == (0, 4)


@pytest.mark.parametrize("head", ["todo", "absent"])
def test_an_entity_with_no_stated_key_is_refused_with_the_reason(tmp_path, head):
    with pytest.raises(cics.CicsError) as e:
        _generated(tmp_path, _HEADS[head]).entity_key("WsRec", None)
    msg = str(e.value)
    assert msg.startswith("WsRec: no key") and "IDCAMS DEFINE" in msg and "not guessed" in msg
