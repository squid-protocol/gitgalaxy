"""
#6255: pytest-xdist collects every worker independently and errors ("Different tests were collected") when
a parametrize id differs between them. The windows 3.11 part died that way when a zip built with
``writestr(name)`` (stamped "now") put its raw bytes in the id.
"""

import ast
import gzip
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TESTS / "security_auditing"))

import test_signal_probes_4108_slice4 as slice4  # noqa: E402

_NON_DETERMINISTIC = {
    "time.time",
    "time.localtime",
    "time.gmtime",
    "time.monotonic",
    "datetime.now",
    "datetime.utcnow",
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "uuid.uuid1",
    "uuid.uuid4",
    "random.random",
    "random.randint",
    "random.choice",
    "tempfile.mkdtemp",
    "tempfile.gettempdir",
    "os.getpid",
}


# Calls that stamp the clock into their bytes unless told otherwise (gzip's header mtime).
_NEEDS_MTIME = {"gzip.compress", "gzip.GzipFile"}


def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _parametrize_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _dotted(node.func).endswith("mark.parametrize"):
            yield node


def test_zip_probe_bytes_do_not_depend_on_the_clock(monkeypatch):
    first = slice4._zip("archive/data.pkl")
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 86400 * 400)
    monkeypatch.setattr(time, "localtime", lambda *_: time.gmtime(real + 86400 * 400))
    assert slice4._zip("archive/data.pkl") == first


def _offenders(tree: ast.AST, label: str) -> list[str]:
    found = []
    for call in _parametrize_calls(tree):
        for sub in ast.walk(call):
            if not isinstance(sub, ast.Call):
                continue
            name = _dotted(sub.func)
            stamped = name in _NEEDS_MTIME and not any(k.arg == "mtime" for k in sub.keywords)
            if name in _NON_DETERMINISTIC or stamped:
                found.append(f"{label}:{sub.lineno} {name}")
    return found


def test_gzip_bytes_do_not_depend_on_the_clock(monkeypatch):
    first = gzip.compress(b"payload", mtime=0)
    monkeypatch.setattr(time, "time", lambda: 1_900_000_000.0)
    assert gzip.compress(b"payload", mtime=0) == first


def test_the_guard_flags_a_stamped_gzip_and_accepts_a_fixed_one():
    src = "@pytest.mark.parametrize('d', [gzip.compress(b'x')])\ndef test_a(d): pass\n"
    assert _offenders(ast.parse(src), "t")
    assert not _offenders(ast.parse(src.replace("b'x')", "b'x', mtime=0)")), "t")


def test_no_parametrize_argument_calls_a_non_deterministic_api():
    offenders = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(_offenders(tree, str(path.relative_to(TESTS))))
    assert not offenders, "parametrize ids must be identical on every xdist worker: " + ", ".join(offenders)
