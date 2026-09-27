"""#3869: the ground-truth readers' own lossless decoder (tests/tools/key_text.py).

It must stay independent of the engine (it imports no gitgalaxy module), and on every encoding the
engine handles it must reach the same text by its own route -- so a disagreement between the answer
key and the engine is a real finding, never a decoding artefact shared by both sides.
"""

import codecs
import random
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from key_text import decode_key_bytes, read_key_text  # noqa: E402

from gitgalaxy.core.source_text import decode_source, read_source  # noqa: E402

SOURCE = "       01 BELØP-顧客 PIC X(8).\n       MOVE 'Größe' TO WS-X.\n"


@pytest.mark.parametrize(
    "data",
    [
        SOURCE.encode("utf-8"),
        codecs.BOM_UTF8 + SOURCE.encode("utf-8"),
        SOURCE.encode("utf-16"),  # with a BOM
        SOURCE.encode("utf-16-le"),
        SOURCE.encode("utf-16-be"),
        SOURCE.encode("utf-32"),
        "PROGRAM-ID. GRÖßE.\n       01 CAMPO-AÑO.\n".encode("cp1252"),
        b"\x81\x8d\x8f\x90\x9d",  # the five bytes cp1252 leaves unmapped: Latin-1
        b"",
    ],
)
def test_agrees_with_the_engine_decoder(data):
    assert decode_key_bytes(data) == decode_source(data).text


def test_random_bytes_agree_and_lose_nothing():
    rng = random.Random(3869)
    for _ in range(500):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(400)))
        assert decode_key_bytes(data) == decode_source(data).text


def test_read_key_text_matches_read_source_including_line_endings(tmp_path):
    p = tmp_path / "PROG.cbl"
    for text, codec in ((SOURCE.replace("\n", "\r\n"), "utf-16"), ("A\rB\r\nC\n", "utf-8")):
        p.write_bytes(text.encode(codec))
        assert read_key_text(p) == read_source(p).text


def test_it_imports_no_engine_code():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import key_text\n"
        "print(sorted(m for m in sys.modules if m == 'gitgalaxy' or m.startswith('gitgalaxy.')))\n"
    )
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, str(TOOLS)], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "[]"
