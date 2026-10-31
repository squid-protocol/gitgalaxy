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
    "os.urandom",
    "secrets.token_bytes",
    "secrets.token_hex",
    "random.randbytes",
    "random.getrandbits",
    "random.uniform",
    "time.perf_counter",
    "time.time_ns",
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


def _is_unsafe(call: ast.Call) -> str:
    name = _dotted(call.func)
    stamped = name in _NEEDS_MTIME and not any(k.arg == "mtime" for k in call.keywords)
    unseeded = name in {"random.Random", "Random"} and not call.args and not call.keywords
    return name if name in _NON_DETERMINISTIC or stamped or unseeded else ""


def _module_defs(tree: ast.AST) -> dict[str, ast.AST]:
    """Module-level functions and constants by name, so a parametrize argument can be followed into them."""
    defs: dict[str, ast.AST] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.FunctionDef):
            defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = node
    return defs


def _offenders(tree: ast.AST, label: str) -> list[str]:
    defs = _module_defs(tree)
    found = []
    for call in _parametrize_calls(tree):
        seen: set[str] = set()
        todo: list[ast.AST] = [call]
        while todo:
            for sub in ast.walk(todo.pop()):
                if isinstance(sub, ast.Call) and (name := _is_unsafe(sub)):
                    found.append(f"{label}:{sub.lineno} {name}")
                elif isinstance(sub, ast.Name) and sub.id in defs and sub.id not in seen:
                    seen.add(sub.id)
                    todo.append(defs[sub.id])
    return sorted(set(found))


def test_gzip_bytes_do_not_depend_on_the_clock(monkeypatch):
    first = gzip.compress(b"payload", mtime=0)
    monkeypatch.setattr(time, "time", lambda: 1_900_000_000.0)
    assert gzip.compress(b"payload", mtime=0) == first


def test_the_guard_flags_a_stamped_gzip_and_accepts_a_fixed_one():
    src = "@pytest.mark.parametrize('d', [gzip.compress(b'x')])\ndef test_a(d): pass\n"
    assert _offenders(ast.parse(src), "t")
    assert not _offenders(ast.parse(src.replace("b'x')", "b'x', mtime=0)")), "t")


def test_the_guard_follows_helpers_and_constants_and_flags_entropy():
    helper = (
        "def _blob():\n    return gzip.compress(b'x')\n@pytest.mark.parametrize('d', [_blob()])\ndef test_a(d): pass\n"
    )
    assert _offenders(ast.parse(helper), "t")
    assert not _offenders(ast.parse(helper.replace("b'x')", "b'x', mtime=0)")), "t")
    const = "DATA = os.urandom(8)\n@pytest.mark.parametrize('d', [DATA])\ndef test_a(d): pass\n"
    assert _offenders(ast.parse(const), "t")
    seeded = const.replace("os.urandom(8)", "random.Random(7).randbytes(8)")
    assert not _offenders(ast.parse(seeded), "t")
    assert _offenders(ast.parse(seeded.replace("Random(7)", "Random()")), "t")


def test_no_parametrize_argument_calls_a_non_deterministic_api():
    offenders = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(_offenders(tree, str(path.relative_to(TESTS))))
    assert not offenders, "parametrize ids must be identical on every xdist worker: " + ", ".join(offenders)
