"""The decoding lint gate (#3813, #3869): no read in `gitgalaxy/` or `tests/` may lose a byte of source.

Every source read used to be `encoding="utf-8", errors="ignore"`: a cp1252 / Latin-1 / Shift-JIS
file silently lost its national characters (names came out truncated), and a UTF-16 file decoded
full of NULs and was dropped whole as binary. `gitgalaxy/core/source_text.py` now decodes every
read without losing a byte; this gate keeps it that way. It is AST-based, so a comment or a string
that merely mentions `errors="ignore"` is not a finding.

Two rules:

1. Nowhere in `gitgalaxy/` or `tests/` may a call pass `errors="ignore"` or `errors="replace"` --
   both lose bytes silently. (A lossless handler such as `surrogatepass` is fine.) `tests/` counts
   because its tools are the ruler: an answer key or accuracy audit that drops the same national
   character the engine drops agrees with it, and reports a false pass (#3869).
2. In the modules that read the SCANNED ESTATE (the engine, recorders, security, metrics and the
   language lens), a text-mode `open()` / `Path.open()` / `read_text()` is a finding: estate files
   go through `read_source` / `open_source`, so a BOM, UTF-16 or a legacy code page decodes the
   same way everywhere. Tools that read only their own JSON artifacts are out of rule 2's scope.

Each allowlist entry is (repo-relative path, enclosing function, rule) with the reason beside it --
keyed by function, not line number, so an unrelated edit does not move it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "gitgalaxy"
TESTS = REPO / "tests"  # rule 1 only: rule 2's scope is gitgalaxy/ paths

LOSSY_HANDLERS = frozenset({"ignore", "replace"})

# Rule 2's scope: the modules that read files from the scanned repository.
ESTATE_READERS = (
    "gitgalaxy/galaxyscope.py",
    "gitgalaxy/core/",
    "gitgalaxy/recorders/",
    "gitgalaxy/security/",
    "gitgalaxy/metrics/",
    "gitgalaxy/standards/language_lens.py",
)

ALLOWED: dict[tuple[str, str, str], str] = {
    # The payload is a binary (that is what the detector is for); decoding its head is an entropy
    # sniff, not a source read, and a lossless Latin-1 decode would change what the sniff measures.
    (
        "gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py",
        "main",
        "lossy-errors",
    ): "binary entropy sniff",
    (
        "gitgalaxy/tools/supply_chain_security/binary_anomaly_detector.py",
        "run_xray_audit",
        "lossy-errors",
    ): "binary entropy sniff",
    # `--config`: the scan's own YAML configuration, not a file of the estate being scanned.
    ("gitgalaxy/galaxyscope.py", "main", "text-read"): "the scan's own --config YAML",
}


def _text_mode(call: ast.Call, mode_index: int) -> bool:
    """True unless the call's mode is a constant containing 'b' (or a write/append mode)."""
    mode = call.args[mode_index] if len(call.args) > mode_index else None
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return True
    if not isinstance(mode, ast.Constant) or not isinstance(mode.value, str):
        return False  # a computed mode: not decidable here, not flagged
    return "b" not in mode.value and "r" in mode.value and "+" not in mode.value


def _is_text_read(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "open":
        return _text_mode(call, 1)
    if isinstance(func, ast.Attribute) and func.attr == "read_text":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "open":
        # Path.open(mode=...) -- mode is the first positional. `urllib` openers and
        # `webbrowser.open(url)` pass a non-mode first argument; only a str constant counts.
        first = call.args[0] if call.args else None
        if first is not None and not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            return False
        return _text_mode(call, 0)
    return False


def _lossy_errors(call: ast.Call) -> bool:
    return any(
        kw.arg == "errors" and isinstance(kw.value, ast.Constant) and kw.value.value in LOSSY_HANDLERS
        for kw in call.keywords
    )


def findings(
    root: Path = PACKAGE, allowed: dict[tuple[str, str, str], str] = ALLOWED
) -> list[tuple[str, str, str, int]]:
    """(path, enclosing function, rule, line) for every read the gate forbids, allowlist applied."""
    out = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root.parent).as_posix()
        estate = rel.startswith(ESTATE_READERS)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        stack: list[tuple[ast.AST, str]] = [(tree, "<module>")]
        while stack:
            node, func_name = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
            if isinstance(node, ast.Call):
                rules = []
                if _lossy_errors(node):
                    rules.append("lossy-errors")
                if estate and _is_text_read(node):
                    rules.append("text-read")
                out.extend(
                    (rel, func_name, rule, node.lineno) for rule in rules if (rel, func_name, rule) not in allowed
                )
            stack.extend((child, func_name) for child in ast.iter_child_nodes(node))
    return sorted(out)


def test_no_source_read_loses_a_byte():
    found = findings() + findings(TESTS)
    assert not found, (
        "#3813: decode through gitgalaxy.core.source_text (read_source / open_source / decode_bytes) "
        "instead of a lossy errors= handler or a text-mode read of an estate file:\n"
        + "\n".join(f"  {path}:{line} in {func}() [{rule}]" for path, func, rule, line in found)
    )


def test_every_allowlist_entry_is_still_needed():
    """A stale entry would silently license a future lossy read in that function."""
    unfiltered = {(path, func, rule) for path, func, rule, _ in findings(allowed={}) + findings(TESTS, allowed={})}
    stale = sorted(set(ALLOWED) - unfiltered)
    assert not stale, f"allowlist entries that no longer match a read: {stale}"


def test_the_gate_catches_what_it_is_for(tmp_path):
    """Self-test on a synthetic package: each forbidden shape is caught, each lossless one is not."""
    pkg = tmp_path / "gitgalaxy" / "core"
    pkg.mkdir(parents=True)
    (pkg / "reader.py").write_text(
        "from pathlib import Path\n"
        "def lossy(p):\n"
        "    return Path(p).read_text(encoding='utf-8', errors='ignore')\n"
        "def replaced(b):\n"
        "    return b.decode('utf-8', errors='replace')\n"
        "def text_open(p):\n"
        "    with open(p, encoding='utf-8') as f:\n"
        "        return f.read()\n"
        "def binary_open(p):\n"
        "    with open(p, 'rb') as f:\n"
        "        return f.read()\n"
        "def write(p):\n"
        "    with open(p, 'w', encoding='utf-8') as f:\n"
        "        f.write('errors=\"ignore\" in a string is not a call')\n"
        "def lossless(s):\n"
        "    return s.encode('utf-8', errors='surrogatepass')\n",
        encoding="utf-8",
    )
    got = {(func, rule) for _, func, rule, _ in findings(tmp_path / "gitgalaxy")}
    assert got == {
        ("lossy", "lossy-errors"),
        ("lossy", "text-read"),
        ("replaced", "lossy-errors"),
        ("text_open", "text-read"),
    }
