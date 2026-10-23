"""
#4108 slice 4: thin-signal probes. Each rule below missed a construct inside its own contract
(Safety & Constraint Bypasses = disabling TLS verification, Worm Pattern = a script copying
itself, Local Inference = model checkpoints); every case has near-miss controls that stay silent.
"""

import io
import zipfile

import pytest

from gitgalaxy.core.model_magic import sniff_model_format
from gitgalaxy.security.security_lens import SecurityLens

_LENS = SecurityLens()


def _count(key: str, text: str) -> int:
    return _LENS.scan_content(text)["counts"].get(key, 0)


_BYPASS_FIRES = [
    "ctx.check_hostname = False",
    "ctx.verify_mode = ssl.CERT_NONE",
    "ssl._create_unverified_context()",
    "&tls.Config{InsecureSkipVerify: true}",
    "curl -k https://example.test",
    "curl -sSLk https://example.test",
    "curl --insecure https://example.test",
    "export NODE_TLS_REJECT_UNAUTHORIZED=0",
    'process.env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"',
    "git config http.sslVerify false",
    "PYTHONHTTPSVERIFY=0",
    "verify_ssl = false",
    "curl_easy_setopt(c, CURLOPT_SSL_VERIFYPEER, 0L);",
    "curl_setopt($c, CURLOPT_SSL_VERIFYHOST, 0)",
]

_BYPASS_SILENT = [
    "ctx.verify_mode = ssl.CERT_REQUIRED",
    "requests.get(u, verify=True)",
    "InsecureSkipVerify: false",
    "curl -K cfg https://example.test",
    "curl --key k.pem https://example.test",
    "curl -sS https://example.test",
    'curl -H "X-a: b" -o out https://example.test',
    "verify_ssl = true",
    "check_hostname = True",
    "NODE_TLS_REJECT_UNAUTHORIZED=1",
    "git config http.sslVerify true",
    'echo "use -k with grep"',
    "CERT_NONE_FOUND",
    "from tls import SSLContext, CERT_NONE",
]

_WORM_FIRES = [
    "shutil.copy(sys.argv[0], d)",
    'cp "${BASH_SOURCE[0]}" /tmp/x',
    "cp $BASH_SOURCE x",
    'cp "${0}" x',
    "fs.copyFile(__filename, d, cb)",
    "fs.cpSync(__filename, d)",
    "FileUtils.cp __FILE__, d",
    "File.copy_stream(__FILE__, d)",
    'copy($_SERVER["SCRIPT_FILENAME"], $d)',
]

_WORM_SILENT = [
    "shutil.copy(sys.argv[1], d)",
    "cp other.sh x",
    "fs.copyFile(src, d, cb)",
    "FileUtils.cp src, d",
    "cp $BASH_SOURCE_DIR x",
    "print(sys.argv[0])",
    'copy($_SERVER["HTTP_HOST"], $d)',
]


@pytest.mark.parametrize("text", _BYPASS_FIRES)
def test_safety_bypass_fires(text):
    assert _count("safety_bypasses", text) >= 1


@pytest.mark.parametrize("text", _BYPASS_SILENT)
def test_safety_bypass_near_miss_is_silent(text):
    assert _count("safety_bypasses", text) == 0


@pytest.mark.parametrize("text", _WORM_FIRES)
def test_self_propagation_fires(text):
    assert _count("self_propagation", text) >= 1


@pytest.mark.parametrize("text", _WORM_SILENT)
def test_self_propagation_near_miss_is_silent(text):
    assert _count("self_propagation", text) == 0


def _zip(first_entry: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        # a fixed timestamp: writestr(name) stamps "now", which put different bytes in the parametrize id per xdist worker
        z.writestr(zipfile.ZipInfo(first_entry, date_time=(1980, 1, 1, 0, 0, 0)), b"x")
    return buf.getvalue()


_HDF5 = b"\x89HDF\r\n\x1a\n"


@pytest.mark.parametrize(
    "name,payload,expected",
    [
        ("last.ckpt", _zip("archive/data.pkl"), "pytorch"),
        ("model.hdf5", _HDF5 + b"\0" * 8 + b"keras_version", "keras_h5"),
        ("notes.ckpt", _zip("readme.txt"), None),
        ("notes.ckpt", b"plain text checkpoint file\n", None),
        ("data.hdf5", _HDF5 + b"\0" * 8 + b"temperature_readings", None),
        ("model.keras", _zip("archive/data.pkl"), None),
    ],
)
def test_checkpoint_extensions_need_a_model_header(tmp_path, name, payload, expected):
    path = tmp_path / name
    path.write_bytes(payload)
    assert sniff_model_format(path) == expected
