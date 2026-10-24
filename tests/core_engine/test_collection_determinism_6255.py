"""
#6255: pytest-xdist collects every worker independently and errors ("Different tests were collected") when
a parametrize id differs between them. The windows 3.11 part died that way when a zip built with
``writestr(name)`` (stamped "now") put its raw bytes in the id.
"""

import ast
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


def test_no_parametrize_argument_calls_a_non_deterministic_api():
    offenders = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _parametrize_calls(tree):
            offenders.extend(
                f"{path.relative_to(TESTS)}:{sub.lineno} {_dotted(sub.func)}"
                for sub in ast.walk(call)
                if isinstance(sub, ast.Call) and _dotted(sub.func) in _NON_DETERMINISTIC
            )
    assert not offenders, "parametrize ids must be identical on every xdist worker: " + ", ".join(offenders)
