"""Regression test: ctags output that is not valid UTF-8 must not crash the tri-comparison run.

ctags can cut a field (the signature, the verbatim pattern) in the middle of a multi-byte UTF-8 character, so its
stdout is not always valid UTF-8 even when the source file is. The crucible v1.9.0 candidate (new Kotlin sources) made
`tri_comparison_chart.py --all --write` die with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xbb` from
`subprocess.run(..., text=True)`. `read_ctags_symbols` now decodes through `gitgalaxy.core.source_text.decode_bytes` (#3813: no lossy errors= handler).

Not an integration test: the real `subprocess.run` is kept (so the decoding settings are what is under test) but the
command it runs is replaced by a python one-liner that prints a lone continuation byte, so no ctags binary is needed.

Per this repo's testing conventions (tests/ has no __init__.py anywhere): the sibling tool directory is put on sys.path
and the module is imported as a bare top-level name.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ctags_reader  # noqa: E402


def test_invalid_utf8_from_ctags_is_replaced_not_raised(monkeypatch, tmp_path):
    real_run = subprocess.run
    emit = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xbb\\n')"]

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "ctags"
        return real_run(emit, **kwargs)

    monkeypatch.setattr(ctags_reader, "has_ctags", lambda: True)
    monkeypatch.setattr(ctags_reader.subprocess, "run", fake_run)
    source = tmp_path / "A.kt"
    source.write_text("fun a() {}\n", encoding="utf-8")

    # The lone 0xbb byte is not a tag line, so there are no symbols; the point is that no UnicodeDecodeError escapes.
    assert ctags_reader.read_ctags_symbols(source, "kotlin") == []
