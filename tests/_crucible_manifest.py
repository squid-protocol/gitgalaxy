"""Reader for tests/crucible_pins.toml, the one manifest of crucible pins (stdlib only).

TOML, because it is commented, diffable and a one-line `ref = "..."` edit. tomllib is 3.11+ and
3.10 is supported, so on older interpreters a ~15-line parser reads the subset the manifest uses
(`[table]` headers and `key = "string"` lines); tests/tools/test_crucible_pins.py proves the two
agree on the real file. Used by the three tests/_*crucible_pin.py wrappers and
tests/tools/crucible_pins.py.
"""

import re
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent / "crucible_pins.toml"
NAMES = ("language", "estate", "cics")


def parse_subset(text):
    """The manifest's TOML subset: `[table]` headers, `key = "string"`, `#` comments, blank lines."""
    data, table = {}, None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[([A-Za-z0-9_-]+)\]", line)
        if header:
            table = data.setdefault(header.group(1), {})
            continue
        pair = re.fullmatch(r'([A-Za-z0-9_-]+)\s*=\s*"([^"\\]*)"\s*(?:#.*)?', line)
        if not pair or table is None:
            raise ValueError(f"crucible_pins.toml line {number}: unsupported syntax: {raw!r}")
        table[pair.group(1)] = pair.group(2)
    return data


def load(path=MANIFEST):
    text = Path(path).read_text(encoding="utf-8")
    try:
        import tomllib  # noqa: PLC0415 -- 3.11+; the fallback below keeps 3.10 working
    except ImportError:
        return parse_subset(text)
    return tomllib.loads(text)


def entry(name, path=MANIFEST):
    pins = load(path)
    if name not in pins:
        raise KeyError(f"no crucible named {name!r} in {path} (have: {', '.join(pins)})")
    return pins[name]
