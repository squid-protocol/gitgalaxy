"""#5882: tests/tools/db2_snapshot.py keys a snapshot by the pinned image and the parts of equivalence_db2.py that make the container and databases, and restores only
its own key (anything else: Db2 starts from scratch, as before). The save/restore round trip needs Docker and Db2:
it was run by hand (all pool databases used ~38 s after a restore)."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db2_snapshot as s  # noqa: E402
import equivalence_db2 as d  # noqa: E402


def test_the_key_names_the_pin_and_the_harness_source():
    assert re.fullmatch(r"db2-snapshot-[0-9a-f]{16}-[0-9a-f]{16}-pool4", s.key())
    assert s.key().split("-")[2] == d.IMAGE.rsplit(":", 1)[1][:16]


def test_the_key_ignores_harness_edits_outside_the_start_and_follows_the_ones_inside():
    text = s.SOURCE.read_text(encoding="utf-8")
    assert s.keyed_source(text + "\n\ndef _readiness_wait():\n    return 1\n") == s.keyed_source(text)
    assert s.keyed_source(text.replace("def _await_ready", "def _await_ready_x")) == s.keyed_source(text)
    for edit, other in (
        ("BLU=false", "BLU=true"),
        ("PORT = 50000", "PORT = 50001"),
        ("pagesize {ref", "pagesize 8 {ref"),
    ):
        assert edit in text  # a container option, a constant, the create
        assert s.keyed_source(text.replace(edit, other)) != s.keyed_source(text)


def test_a_keyed_definition_that_disappears_fails_loudly():
    text = s.SOURCE.read_text(encoding="utf-8")
    for name in (
        *s.KEYED_FUNCTIONS,
        *(n for n in s.KEYED_ASSIGNS if n not in ("USER", "PASSWORD")),
    ):  # (those two: one tuple)
        broken = text.replace(f"def {name}(", f"def {name}_x(")
        broken = re.sub(rf"^{name}\b", f"{name}_x", broken, flags=re.M)
        try:
            s.keyed_source(broken)
        except ValueError as e:
            assert name in str(e)
        else:
            raise AssertionError(name)


def test_no_snapshot_or_another_key_is_not_restored(tmp_path, capsys):
    assert s.restore(tmp_path) is False
    (tmp_path / s.META).write_text(json.dumps({"key": "db2-snapshot-old"}), encoding="utf-8")
    (tmp_path / s.DELTA).write_bytes(b"")
    (tmp_path / s.DATA).write_bytes(b"")
    assert s.restore(tmp_path) is False
    assert "is not" in capsys.readouterr().out


def test_the_restored_container_is_the_started_one_plus_its_volume():
    assert d.run_args("vol") == [*d.run_args()[:7], "-v", "vol:/database", *d.run_args()[7:]]
    assert d.run_args()[:2] == ["--name", d.CONTAINER] and "-v" not in d.run_args()
