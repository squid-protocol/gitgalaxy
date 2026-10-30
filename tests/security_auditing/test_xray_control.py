"""#7155: X-Ray's real detector over planted inert content, nothing mocked.

test_binary_anomaly_detector.py mocks SecurityLens and ApertureFilter, so it proves the exit code, not that anything is
ever found. Nothing here runs: the payloads are random bytes, and the "executable" is a header on noise.
"""

import base64
import gzip
import random
import struct
import sys
import zlib

import pytest

import gitgalaxy.tools.supply_chain_security.binary_anomaly_detector as xray
from gitgalaxy.standards.config_resolver import resolve_config

NOISE = random.Random(7).randbytes(6000)
_ENCODED = base64.b64encode(NOISE).decode().replace("MZ", "Mz")  # "MZ" anywhere reads as an executable header
DENSE = f'PAYLOAD = "{_ENCODED[:200]}"\n'.encode()  # SecurityLens empties lines of 250+ characters before it scans
LARGE = f'PAYLOAD = "{_ENCODED}"\n'.encode()
ELF = b"\x7fELF\x02\x01\x01\x00" + NOISE
XOR_LOOP = b"def d(b, k):\n    out = bytearray()\n    for i, c in enumerate(b):\n        out.append(c ^ k[i % len(k)])\n    return bytes(out)\n"


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\0"))
        + chunk(b"IEND", b"")
    )


def _scan(tmp_path, monkeypatch, files: dict[str, bytes]) -> int:
    """The real scanner over a planted tree, with the default config. The exit code it would give CI."""
    root = tmp_path / "planted"
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    monkeypatch.setattr(sys, "argv", ["binary_anomaly_detector.py", str(root)])
    try:
        xray.main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


@pytest.mark.parametrize("name", ["a.py", "a.js", "a.txt", "a.toml", "a.sh", "run"])
def test_the_real_detector_fails_ci_on_a_dense_payload(name, tmp_path, monkeypatch, capsys):
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": DENSE}) == 1
    assert "ANOMALY DETECTED" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["a.txt", "a.bin", "tool", "lib.so", "a.exe"])
def test_a_bare_executable_fails(name, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": ELF}) == 1


@pytest.mark.parametrize("name", ["logo.png", "photo.jpg", "bundle.zip", "data.gz"])
def test_an_executable_behind_a_bypassed_extension_fails(name, tmp_path, monkeypatch, capsys):
    """The banner's own example: the extension bypass is for dense data, and a header mismatch is never that."""
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": ELF}) == 1
    assert "ANOMALY DETECTED" in capsys.readouterr().out


def test_the_headless_audit_agrees_on_a_disguised_executable(tmp_path):
    root = tmp_path / "planted"
    root.mkdir()
    (root / "logo.png").write_bytes(ELF)
    assert xray.run_xray_audit(root, resolve_config())["anomalies_found"] == 1


@pytest.mark.parametrize(
    "name, data",
    [
        ("src/a.py", b"def add(a, b):\n    return a + b\n"),
        ("src/logo.png", _png()),
        ("src/data.gz", gzip.compress(NOISE)),
        ("src/a.json", b'{"a": 1}\n'),
    ],
)
def test_real_clean_files_pass(name, data, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {name: data}) == 0


@pytest.mark.parametrize("rel", ["src/latests/a.py", "contests/a.py", "src/phpunit_helper.py"])
def test_a_name_that_only_looks_like_a_test_folder_is_not_exempt(rel, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {rel: DENSE}) == 1


@pytest.mark.parametrize("rel", ["tests/a.py", "src/tests/a.py", "src/test/a.py", "vendor/phpunit/a.py"])
def test_a_real_test_folder_stays_exempt(rel, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {rel: DENSE}) == 0


@pytest.mark.xfail(strict=True, reason="#7187: printed as a detection, but this loop isn't flagged")
def test_known_miss_xor_loop(tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"src/a.py": XOR_LOOP}) == 1


@pytest.mark.xfail(strict=True, reason="#7187: only the first 8 KB is read")
def test_known_miss_a_payload_after_the_first_8_kb(tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"src/a.py": b"# padding\n" * 1000 + DENSE}) == 1


@pytest.mark.xfail(strict=True, reason="#7187: .json and .yml skip the entropy check by design")
@pytest.mark.parametrize("name", ["a.json", "a.yml"])
def test_known_miss_dense_data_in_a_bypassed_text_type(name, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": DENSE}) == 1


@pytest.mark.xfail(strict=True, reason="#7187: SecurityLens has no required header for these bypassed types")
@pytest.mark.parametrize("name", ["icon.ico", "bundle.tar"])
def test_known_miss_an_executable_behind_a_type_with_no_known_header(name, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": ELF}) == 1


@pytest.mark.xfail(
    strict=True, reason="#7187: SecurityLens empties lines of 250+ characters, so a long payload is never measured"
)
def test_known_miss_a_large_encoded_payload(tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"src/a.py": LARGE}) == 1
