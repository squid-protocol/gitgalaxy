"""
Extract the test programs of a GNU Autotest suite (`.at` files) and their expected output (#3806).

A compiler's own test suite is a ready-made fresh estate for the first-try trials of #3803: every
test case is a small COBOL program plus the output its maintainers pinned. This tool turns an
Autotest suite into one directory per test case:

    <out>/<suite>/<NNN-slug>/<file>        the AT_DATA files, RAW BYTES (never decoded and re-encoded)
    <out>/<suite>/<NNN-slug>/expected.json  name, encoding, the ordered steps: each AT_DATA file and each
                                            AT_CHECK command with its expected exit status, stdout, stderr
    <out>/<suite>/suite.json                the suite: source .at, encoding, extractor version, the cases

    python tests/tools/at_extract.py --suite i18n_sjis --at tests/i18n_sjis.at -I tests/i18n_sjis.src \\
        --encoding shift_jis --out /data/fresh-estates/oc4j [--source-repo URL --commit SHA]

The `.at` is read the way m4 reads it -- byte by byte, so a Shift-JIS file is never decoded to be parsed:
- `[` `]` quote; a macro argument loses its outer quotes when collected, and AT_DATA / AT_CHECK
  rescan it, which strips one more level -- so `[[x]]` in a file's text is `x` in the file;
- unquoted `#` starts a comment (to the end of the line) that is copied, never expanded; `dnl` drops it;
- trailing blanks (space / tab) at a line end are dropped, as autom4te drops them from the testsuite it
  writes -- the file a test writes and the output it expects never have them -- and only THEN are the
  quadrigraphs (`@<:@` `[`, `@:>@` `]`, `@S|@` `$`, `@%:@` `#`, `@{:@` `(`, `@:}@` `)`, `@&t@` nothing)
  replaced, so `  @&t@` keeps a line's trailing blanks;
- `m4_include([f])` is followed through the `-I` directories; AT_SETUP starts a case and AT_CLEANUP
  ends it; AT_SKIP_IF / AT_XFAIL_IF / AT_KEYWORDS are recorded; a case may write several files and
  write the same file twice (each later version goes to `vN/<file>`).

AT_CHECK's expected output: an omitted stdout / stderr must be empty and an omitted status is 0, as
Autotest checks them; `ignore`, `stdout`, `expout` ... are recorded as modes, not text.

The encoding is VERIFIED, not assumed: every file and expected string of a case must decode strictly
in the suite's declared encoding (through gitgalaxy.core.source_text's lossless ladder); a case where
one does not is marked `encoding_error`, and nothing is replaced.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gitgalaxy.core.source_text import decode_source

EXTRACTOR_VERSION = "1"

_QUADRIGRAPHS = ((b"@<:@", b"["), (b"@:>@", b"]"), (b"@S|@", b"$"), (b"@%:@", b"#"),
                 (b"@{:@", b"("), (b"@:}@", b")"), (b"@&t@", b""))  # fmt: skip
_WORD_START = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_WORD = _WORD_START | frozenset(b"0123456789")
_BLANKS = frozenset(b" \t\n\r")
# AT_CHECK's stdout / stderr arguments that are directives, not the expected text
_OUTPUT_MODES = frozenset({b"ignore", b"ignore-no-log", b"stdout", b"stderr", b"stdout-nolog", b"stderr-nolog",
                           b"expout", b"experr"})  # fmt: skip
_MACROS = frozenset({b"AT_SETUP", b"AT_CLEANUP", b"AT_DATA", b"AT_CHECK", b"AT_SKIP_IF", b"AT_XFAIL_IF",
                     b"AT_KEYWORDS", b"m4_include", b"dnl", b"m4_dnl"})  # fmt: skip


_TRAILING_BLANKS = re.compile(rb"[ \t]{1,4096}(?=\n)")


def _final(text: bytes) -> bytes:
    """autom4te's output pass: every line's trailing blanks are dropped (so the file a test writes and the
    output it expects have none), THEN the quadrigraphs become their characters -- which is why a test
    ends a line with `@&t@` to keep its trailing blanks."""
    text = _TRAILING_BLANKS.sub(b"", text)
    for quad, char in _QUADRIGRAPHS:
        text = text.replace(quad, char)
    return text


def _command(arg: bytes | None) -> bytes:
    """An AT_CHECK command: its last line ends the script line too, so its trailing blanks go as well."""
    return _final(_rescan(arg or b"").rstrip(b" \t"))


class AtSyntaxError(ValueError):
    """The .at text is not balanced where m4 needs it to be (an unclosed quote or argument list)."""


@dataclass
class Case:
    name: bytes
    at_file: str
    line: int
    keywords: list[bytes] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


def _line_of(data: bytes, pos: int) -> int:
    return data.count(b"\n", 0, pos) + 1


def _quoted(data: bytes, i: int) -> tuple[bytes, int]:
    """The text inside the quote opening at data[i] ('['), nested quotes kept; and the index past it."""
    depth, j = 1, i + 1
    while j < len(data):
        c = data[j]
        if c == 0x5B:
            depth += 1
        elif c == 0x5D:
            depth -= 1
            if depth == 0:
                return data[i + 1 : j], j + 1
        j += 1
    raise AtSyntaxError(f"unclosed quote opened at line {_line_of(data, i)}")


def _collect_args(data: bytes, i: int) -> tuple[list[bytes], int]:
    """m4's argument collection from data[i] (just past the '('): leading blanks dropped, one quote
    level removed, commas split only outside quotes and nested parentheses, comments kept verbatim."""
    args: list[bytes] = []
    cur = bytearray()
    depth, at_start = 0, True
    n = len(data)
    while i < n:
        c = data[i]
        if at_start and c in _BLANKS:
            i += 1
            continue
        at_start = False
        if c == 0x5B:
            inner, i = _quoted(data, i)
            cur += inner
            continue
        if c == 0x23:  # '#': a comment, copied through to the end of its line
            end = data.find(b"\n", i)
            end = n if end < 0 else end + 1
            cur += data[i:end]
            i = end
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            if depth == 0:
                args.append(bytes(cur))
                return args, i + 1
            depth -= 1
        elif c == 0x2C and depth == 0:
            args.append(bytes(cur))
            cur = bytearray()
            at_start = True
            i += 1
            continue
        cur.append(c)
        i += 1
    raise AtSyntaxError("unclosed macro argument list")


def expand(arg: bytes) -> bytes:
    """What AT_DATA / AT_CHECK make of a collected argument: m4's rescan, then autom4te's output pass."""
    return _final(_rescan(arg))


def _rescan(arg: bytes) -> bytes:
    """The rescan of an expanded argument strips one more quote level; comments are copied as they are."""
    out = bytearray()
    i, n = 0, len(arg)
    while i < n:
        c = arg[i]
        if c == 0x5B:
            inner, i = _quoted(arg, i)
            out += inner
        elif c == 0x23:
            end = arg.find(b"\n", i)
            end = n if end < 0 else end + 1
            out += arg[i:end]
            i = end
        else:
            out.append(c)
            i += 1
    return bytes(out)


def _output(arg: bytes | None) -> dict[str, Any]:
    """AT_CHECK's stdout / stderr expectation: omitted means empty; a directive is a mode."""
    if arg is None:
        return {"mode": "exact", "bytes": b""}
    text = expand(arg)
    if text in _OUTPUT_MODES:
        return {"mode": text.decode("ascii")}
    return {"mode": "exact", "bytes": text}


def _status(arg: bytes | None) -> int | str:
    text = expand(arg).strip() if arg is not None else b""
    if not text:
        return 0
    return int(text) if text.isdigit() else text.decode("ascii")


class _Parser:
    """Walks .at texts in m4's order; an m4_include is parsed in place, so a case may span files."""

    def __init__(self, include_dirs: list[Path]) -> None:
        self.include_dirs = include_dirs
        self.cases: list[Case] = []
        self.current: Case | None = None

    def parse(self, data: bytes, at_file: str) -> None:
        i, n = 0, len(data)
        while i < n:
            c = data[i]
            if c == 0x5B:  # top-level quoted text is output, never a macro call
                _, i = _quoted(data, i)
                continue
            if c == 0x23:
                end = data.find(b"\n", i)
                i = n if end < 0 else end + 1
                continue
            if c not in _WORD_START:
                i += 1
                continue
            j = i
            while j < n and data[j] in _WORD:
                j += 1
            word = data[i:j]
            if word not in _MACROS:
                i = j
                continue
            if word in (b"dnl", b"m4_dnl"):
                end = data.find(b"\n", j)
                i = n if end < 0 else end + 1
                continue
            args: list[bytes] = []
            if j < n and data[j] == 0x28:
                args, j = _collect_args(data, j + 1)
            self._macro(word, args, at_file, _line_of(data, i))
            i = j

    def _macro(self, word: bytes, args: list[bytes], at_file: str, line: int) -> None:
        if word == b"m4_include":
            name = expand(args[0]).decode("utf-8")
            self.parse(self._find(name, at_file), name)
            return
        if word == b"AT_SETUP":
            self.current = Case(expand(args[0]) if args else b"", at_file, line)
            self.cases.append(self.current)
            return
        if word == b"AT_CLEANUP":
            self.current = None
            return
        case = self.current
        if case is None:
            return  # AT_INIT-level text (AT_BANNER, AT_COLOR_TESTS ...) outside any case
        if word == b"AT_KEYWORDS":
            case.keywords += expand(args[0]).split() if args else []
        elif word in (b"AT_SKIP_IF", b"AT_XFAIL_IF"):
            kind = "skip_if" if word == b"AT_SKIP_IF" else "xfail_if"
            case.steps.append({"kind": kind, "line": line, "condition": expand(args[0]) if args else b""})
        elif word == b"AT_DATA":
            case.steps.append({"kind": "data", "line": line, "file": expand(args[0]).strip(),
                               "content": expand(args[1]) if len(args) > 1 else b""})  # fmt: skip
        elif word == b"AT_CHECK":
            full: list[bytes | None] = [*args, None, None, None, None, None, None][:6]
            case.steps.append({
                "kind": "check", "line": line, "command": _command(full[0]), "status": _status(full[1]),
                "stdout": _output(full[2]), "stderr": _output(full[3]),
                "run_if_fail": expand(full[4] or b""), "run_if_pass": expand(full[5] or b""),
            })  # fmt: skip

    def _find(self, name: str, at_file: str) -> bytes:
        for d in self.include_dirs:
            p = d / name
            if p.is_file():
                return p.read_bytes()
        raise FileNotFoundError(f"m4_include([{name}]) from {at_file}: not in {[str(d) for d in self.include_dirs]}")


def parse(data: bytes, at_file: str, include_dirs: list[Path] | None = None) -> list[Case]:
    """The cases in an .at text, in order, following m4_include through `include_dirs`."""
    parser = _Parser(include_dirs or [])
    parser.parse(data, at_file)
    return parser.cases


# ---- verifying the encoding ---------------------------------------------------------------------------
def verify_encoding(chunks: list[bytes], declared: str) -> tuple[str, list[str]]:
    """('ascii' | the declared codec, problems): every chunk must decode strictly as declared. The
    lossless ladder of source_text is used; a chunk it could only read as a guess is a problem."""
    if all(b.isascii() for b in chunks):
        return "ascii", []
    problems = []
    for b in chunks:
        if b.isascii():
            continue
        got = decode_source(b, declared=declared)
        utf8 = declared.replace("-", "_").lower() in ("utf_8", "utf8")
        if got.how != ("utf-8" if utf8 else "declared"):
            problems.append(f"{len(b)} bytes read as {got.encoding} ({got.how}), not {declared}")
    return declared, problems


def _text(b: bytes, encoding: str) -> str | None:
    """Text for JSON when the bytes decode strictly in the case's encoding, else None (the base64 stays)."""
    codec = "ascii" if encoding == "ascii" else encoding
    try:
        return b.decode(codec)
    except UnicodeDecodeError:
        return None


def _slug(name: bytes, index: int) -> str:
    ascii_words = re.sub(rb"[^A-Za-z0-9]+", b"-", name).strip(b"-").lower()[:48].decode("ascii")
    return f"{index:03d}-{ascii_words or 'case'}"


def _json_output(spec: dict[str, Any], encoding: str) -> dict[str, Any]:
    if spec["mode"] != "exact":
        return {"mode": spec["mode"]}
    raw = spec["bytes"]
    out: dict[str, Any] = {"mode": "exact", "text": _text(raw, encoding)}
    if not raw.isascii():
        out["b64"] = base64.b64encode(raw).decode("ascii")
    return out


def write_case(case: Case, index: int, suite: str, root: Path, encoding: str) -> dict[str, Any]:
    """Write one case's files and expected.json under root; its manifest entry."""
    slug = _slug(case.name, index)
    cdir = root / slug
    cdir.mkdir(parents=True, exist_ok=True)
    chunks: list[bytes] = [case.name]
    versions: dict[bytes, int] = {}
    steps: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for step in case.steps:
        if step["kind"] == "data":
            name = step["file"]
            versions[name] = versions.get(name, 0) + 1
            rel = name.decode("utf-8") if versions[name] == 1 else f"v{versions[name]}/{name.decode('utf-8')}"
            dest = cdir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(step["content"])
            chunks.append(step["content"])
            entry = {"path": rel, "file": name.decode("utf-8"), "line": step["line"], "bytes": len(step["content"]),
                     "sha256": hashlib.sha256(step["content"]).hexdigest()}  # fmt: skip
            files.append(entry)
            steps.append({"kind": "data", **entry})
        elif step["kind"] == "check":
            chunks += [step[k]["bytes"] for k in ("stdout", "stderr") if step[k]["mode"] == "exact"]
            chunks.append(step["command"])
            steps.append({"kind": "check", "line": step["line"], "command": step["command"], "status": step["status"],
                          "stdout": step["stdout"], "stderr": step["stderr"], "run_if_fail": step["run_if_fail"],
                          "run_if_pass": step["run_if_pass"]})  # fmt: skip
        else:
            chunks.append(step["condition"])
            steps.append({"kind": step["kind"], "line": step["line"], "condition": step["condition"]})
    enc, problems = verify_encoding(chunks, encoding)
    for s in steps:  # bytes -> JSON text in the verified encoding; bytes it does not decode stay base64, never lost
        for key in ("command", "condition", "run_if_fail", "run_if_pass"):
            if key in s:
                text = _text(s[key], enc)
                s[key] = text if text is not None else {"b64": base64.b64encode(s[key]).decode("ascii")}
        for key in ("stdout", "stderr"):
            if key in s:
                s[key] = _json_output(s[key], enc)
    record = {
        "suite": suite, "case": slug, "index": index, "name": _text(case.name, enc),
        "name_b64": base64.b64encode(case.name).decode("ascii"), "at_file": case.at_file,
        "line": case.line, "keywords": [k.decode("utf-8", "strict") for k in case.keywords], "encoding": enc,
        "encoding_error": problems, "files": files, "steps": steps, "extractor_version": EXTRACTOR_VERSION,
    }  # fmt: skip
    (cdir / "expected.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return record


def extract(suite: str, at: Path, include_dirs: list[Path], encoding: str, out: Path,
            provenance: dict[str, str] | None = None) -> dict[str, Any]:  # fmt: skip
    """Extract one suite into out/<suite>/; the suite manifest (also written as suite.json)."""
    cases = parse(at.read_bytes(), at.name, [at.parent, *include_dirs])
    root = out / suite
    root.mkdir(parents=True, exist_ok=True)
    records = [write_case(c, k, suite, root, encoding) for k, c in enumerate(cases, 1)]
    manifest = {"suite": suite, "at": at.name, "include_dirs": [d.name for d in include_dirs],
                "declared_encoding": encoding, "extractor_version": EXTRACTOR_VERSION, **(provenance or {}),
                "cases": [{"case": r["case"], "name": r["name"], "at_file": r["at_file"], "line": r["line"],
                           "encoding": r["encoding"], "encoding_error": r["encoding_error"]} for r in records]}  # fmt: skip
    (root / "suite.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", required=True, help="the suite's name (its directory under --out)")
    ap.add_argument("--at", required=True, type=Path, help="the suite's top .at file")
    ap.add_argument("-I", dest="include", action="append", type=Path, default=[], help="m4_include search dir")
    ap.add_argument("--encoding", default="utf-8", help="the suite's declared encoding (verified per case)")
    ap.add_argument("--out", required=True, type=Path, help="the estate root")
    ap.add_argument("--source-repo", default="", help="provenance: the repository the suite came from")
    ap.add_argument("--commit", default="", help="provenance: its commit")
    args = ap.parse_args(argv)
    prov = {k: v for k, v in (("source_repo", args.source_repo), ("commit", args.commit)) if v}
    manifest = extract(args.suite, args.at, args.include, args.encoding, args.out, prov)
    bad = [c["case"] for c in manifest["cases"] if c["encoding_error"]]
    print(f"{args.suite}: {len(manifest['cases'])} cases -> {args.out / args.suite}"
          + (f"; encoding errors in {len(bad)}: {', '.join(bad)}" if bad else ""))  # fmt: skip
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
