"""#5882: tests/tools/db2_snapshot.py keys a snapshot by the pinned image and equivalence_db2.py, and restores only
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
