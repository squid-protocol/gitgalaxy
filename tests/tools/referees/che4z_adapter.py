r"""Eclipse Che4z COBOL Language Support referee (#4377, #4438): the language server (EPL-2.0; run as an
external, unmodified tool, never vendored), as a referee-facts/1 document. Two modes:

* `--mode lsp` (default): one server per corpus, driven over LSP (`java -jar server.jar pipeEnabled`):
  `didOpen`, the server's `publishDiagnostics`, then `textDocument/documentSymbol`. It yields PROGRAM-IDs,
  paragraphs / sections with extents, COPY members and the DATA DIVISION items' level and name. The symbols
  carry no PERFORM / GO TO edges and no PIC / USAGE / OCCURS / REDEFINES / VALUE clauses, so those channels
  are not produced in this mode (they are not scored as misses). The server asks the client to resolve
  copybooks (`copybook/resolve`, `file/content`); the adapter answers from the corpus's copybook dirs.
  Unlike the CLI it does not stop on a program with a CALL or overflow on a large tree.
* `--mode cli`: the headless `analysis` command with `--ast` (the #4377 first pass; every channel, but it
  fails on any program with a CALL and overflows on large ASTs).

    python tests/tools/referees/che4z_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/che4z.json

Needs the environment variable CHE4Z_SERVER_JAR: server/jar/server.jar unpacked from the
cobol-language-support VSIX release (README.md). Each member runs as
`java -jar server.jar analysis -s <member> -cf=<every copybook dir> --ast`; the AST's first stage
(`START`) is read. Che4z's lines are 0-based. A member whose AST cannot be serialised (the server's
JSON writer overflows its stack on some trees) falls back to a run without `--ast`: it then counts
as `fail` for facts but its diagnostics still say whether it parsed. Per-member time is the
server's own `timings.total` (JVM start-up excluded; it is reported separately as wall time).
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F
from gitgalaxy.core.source_text import read_source

JAR_ENV = "CHE4Z_SERVER_JAR"
COPY_EXTS = (".cpy", ".CPY", ".cbl", ".CBL", ".dcl", ".DCL", ".copy", ".cob")
CHANNELS = ["program_ids", "units", "unit_extents", "edges", "copybooks",
            "data_items", "pic", "usage", "occurs", "redefines", "value"]  # fmt: skip
UNIT_TYPES = ("PARAGRAPH", "PROCEDURE_SECTION")
LSP_CHANNELS = ["program_ids", "units", "unit_extents", "copybooks", "data_items"]
SYMBOL_VARIABLE, SYMBOL_STRUCT = 13, 23  # LSP SymbolKind.Variable / Struct: a DATA DIVISION item
SYMBOL_FILE_KINDS = (1,)  # SymbolKind.File: a `COPY name` node
LSP_TIMEOUT_S = 120.0
_LEVEL = re.compile(r"^\s*(\d{1,2})\s")


def che4z_version(jar: Path) -> str:
    out = subprocess.run(["unzip", "-p", str(jar), "META-INF/MANIFEST.MF"], capture_output=True, text=True)
    for ln in out.stdout.splitlines():
        if ln.startswith("Version:"):
            return ln.split(":", 1)[1].strip()
    return jar.name


def _line(loc: dict[str, Any], end: bool = False) -> int:
    return int(loc["range"]["end" if end else "start"]["line"]) + 1


def _in_file(node: dict[str, Any], uri: str) -> bool:
    return node.get("locality", {}).get("uri", "").rstrip("/") == uri


def _name(node: dict[str, Any]) -> str | None:
    if node.get("name"):
        return str(node["name"]).upper()
    for c in node.get("children", []):
        if c.get("nodeType") in ("PARAGRAPH_NAME_NODE", "SECTION_NAME_NODE") and c.get("name"):
            return str(c["name"]).upper()
    return None


def _first(clauses: list[Any]) -> str | None:
    if not clauses:
        return None
    c = clauses[0]
    if isinstance(c, dict):
        for k in ("name", "value", "usage", "format"):
            if c.get(k):
                return str(c[k])
        return None
    return str(c)


def _usage(clauses: list[Any]) -> str | None:
    u = _first(clauses)
    return u.replace("_", "-") if u else None  # Che4z writes the enum name, COMP_3


def _occurs(clauses: list[Any]) -> tuple[int | None, int | None, str | None]:
    if not clauses or not isinstance(clauses[0], dict):
        return None, None, None
    c = clauses[0]
    lo, hi = c.get("from"), c.get("to")
    if hi is None:
        hi = lo
    # The serialised clause carries no DEPENDING ON object (2.5.1): an ODO table scores as a miss.
    dep = c.get("dependingOn")
    if isinstance(dep, dict):
        dep = dep.get("name")
    return lo, hi, (str(dep) if dep else None)


def _value(clauses: list[Any]) -> str | None:
    if not clauses or not isinstance(clauses[0], dict):
        return None
    iv = clauses[0].get("valueIntervals") or []
    return str(iv[0].get("from")) if iv and iv[0].get("from") is not None else None


def ast_facts(doc: dict[str, Any], path: Path) -> dict[str, set[str]]:
    uri = path.resolve().as_uri().replace("file:///", "file:/")
    root = doc["asts"]["START"]
    f: dict[str, set[str]] = {ch: set() for ch in CHANNELS}
    programs: list[str] = []
    spans: dict[str, list[int]] = {}

    def visit(n: dict[str, Any], unit: str | None, in_proc: bool, prog: int) -> None:
        t = n.get("nodeType")
        if t == "PROGRAM_ID" and n.get("programId"):
            programs.append(str(n["programId"]).upper())
            f["program_ids"].add(programs[-1])
        if t == "PROGRAM" and programs:
            prog = len(programs)
        if t == "COPY" and n.get("name"):
            f["copybooks"].add(str(n["name"]).upper())
        if t == "VARIABLE_DEFINITION" and _in_file(n, uri):
            name = (n.get("variableName") or {}).get("name") or "FILLER"
            ln = _line(n.get("levelLocality") or n["locality"])
            lo, hi, dep = _occurs(n.get("occursClauses") or [])
            F.merge_item(f, F.item_values(ln, int(n.get("level") or 0), str(name), _first(n.get("picClauses") or []),
                                          _usage(n.get("usageClauses") or []), lo, hi, dep,
                                          _first(n.get("redefinesClauses") or []), _value(n.get("valueClauses") or [])))  # fmt: skip
        if t == "DIVISION" and n.get("divisionType") == "PROCEDURE_DIVISION" and _in_file(n, uri):
            in_proc = True
            spans.setdefault(F.MAIN_LINE, [_line(n["locality"]), 0])
            unit = F.MAIN_LINE
        if t in UNIT_TYPES and _in_file(n, uri):
            name = _name(n)
            if name:
                pid = programs[-1] if programs else None
                unit = F.unit_name(max(len(programs) - 1, 0), pid, name)
                f["units"].add(unit)
                start = _line(n["locality"])
                spans[unit] = [start, start]  # the header; its own sentences extend it below
        if t == "SENTENCE" and unit in spans and _in_file(n, uri):
            # a unit ends at its last sentence: trailing comments and the sentences of a
            # section's paragraphs are not its own (the answer keys' extent contract)
            spans[unit][1] = max(spans[unit][1], _line(n["locality"], end=True))
        if unit is not None and _in_file(n, uri):
            if t == "PERFORM" and (n.get("target") or {}).get("name"):
                f["edges"].add(F.edge_value(unit, "PERFORM", str(n["target"]["name"])))
            if t == "GO_TO":
                for tgt in n.get("targets") or []:
                    f["edges"].add(F.edge_value(unit, "GO_TO", str(tgt)))
        for c in n.get("children", []):
            visit(c, unit, in_proc, prog)

    visit(root, None, False, 0)
    for name, (s, e) in spans.items():
        if e and e >= s:
            f["unit_extents"].add(f"{name} L{s}-{e}")
    return f


def copy_dirs(root: Path) -> list[str]:
    return sorted(
        {str(p.parent) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix in COPY_EXTS}
    )


def run_member(jar: Path, path: Path, dirs: list[str], work: Path, ast: bool) -> tuple[dict[str, Any] | None, str]:
    cmd = ["java", "-Xss64m", "-jar", str(jar), "analysis", "-s", str(path)]
    cmd += [f"-cf={d}" for d in dirs] + [f"-ce={e.lstrip('.')}" for e in COPY_EXTS] + (["--ast"] if ast else [])
    out = work / "out.json"
    with out.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=600)
    try:
        return json.loads(out.read_text(encoding="utf-8")), ""
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, (proc.stderr.decode("utf-8", "backslashreplace").splitlines() or ["no output"])[0][:200]
    finally:
        out.unlink(missing_ok=True)


# ------------------------------------------------------------------------------
# LSP mode (#4438)
# ------------------------------------------------------------------------------
def write_message(stream: IO[bytes], msg: dict[str, Any]) -> None:
    body = json.dumps(msg).encode("utf-8")
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    stream.flush()


def read_message(stream: IO[bytes]) -> dict[str, Any] | None:
    """One Content-Length framed JSON-RPC message, or None at end of stream."""
    length = 0
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    body = stream.read(length)
    return json.loads(body) if len(body) == length and length else None


class LspSession:
    """A minimal LSP client: a reader thread, the server's own requests answered, one request at a time."""

    def __init__(self, rx: IO[bytes], tx: IO[bytes], resolve: Callable[[str], str | None]) -> None:
        self.tx, self.resolve, self.next_id = tx, resolve, 0
        self.inbox: queue.Queue[dict[str, Any] | None] = queue.Queue()
        threading.Thread(target=self._read, args=(rx,), daemon=True).start()

    def _read(self, rx: IO[bytes]) -> None:
        try:
            while (msg := read_message(rx)) is not None:
                self.inbox.put(msg)
        except (ValueError, OSError):
            pass
        self.inbox.put(None)

    def notify(self, method: str, params: dict[str, Any]) -> None:
        write_message(self.tx, {"jsonrpc": "2.0", "method": method, "params": params})

    def _answer(self, msg: dict[str, Any]) -> None:
        method, params = msg["method"], msg.get("params") or {}
        result: Any = None
        if method == "workspace/configuration":
            result = [None] * len(params.get("items", []))
        elif method == "copybook/resolve":  # params: [cobol file uri, copybook name, dialect]
            result = self.resolve(str(params[1]))
        elif method == "file/content":
            uri = params if isinstance(params, str) else (params[0] if isinstance(params, list) else "")
            result = _read_uri(str(uri))
        write_message(self.tx, {"jsonrpc": "2.0", "id": msg["id"], "result": result})

    def wait(self, accept: Callable[[dict[str, Any]], bool], timeout: float = LSP_TIMEOUT_S) -> dict[str, Any]:
        """Answer the server's requests until a message `accept` takes arrives; TimeoutError / EOFError otherwise."""
        end = time.monotonic() + timeout
        while True:
            try:
                msg = self.inbox.get(timeout=max(end - time.monotonic(), 0.01))
            except queue.Empty:
                raise TimeoutError("no matching LSP message") from None
            if msg is None:
                raise EOFError("language server closed the pipe")
            if "method" in msg and "id" in msg:
                self._answer(msg)
            elif accept(msg):
                return msg

    def request(self, method: str, params: dict[str, Any], timeout: float = LSP_TIMEOUT_S) -> Any:
        self.next_id += 1
        rid = self.next_id
        write_message(self.tx, {"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        msg = self.wait(lambda m: m.get("id") == rid and "method" not in m, timeout)
        if "error" in msg:
            raise RuntimeError(str(msg["error"].get("message", msg["error"]))[:160])
        return msg.get("result")

    def open_and_analyse(self, path: Path, text: str, timeout: float = LSP_TIMEOUT_S) -> tuple[list[Any], list[Any]]:
        """didOpen, wait for the server's diagnostics for the file (analysis done), then its document symbols."""
        uri = path.resolve().as_uri()
        self.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "cobol", "version": 1, "text": text}})  # fmt: skip
        diag = self.wait(lambda m: m.get("method") == "textDocument/publishDiagnostics" and m["params"].get("uri") == uri, timeout)  # fmt: skip
        symbols = self.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, timeout)
        self.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
        return symbols or [], diag["params"].get("diagnostics", [])

    def start(self) -> None:
        caps = {"textDocument": {"documentSymbol": {"hierarchicalDocumentSymbolSupport": True}}}
        self.request("initialize", {"processId": None, "rootUri": None, "capabilities": caps})
        self.notify("initialized", {})

    def stop(self) -> None:
        try:
            self.request("shutdown", {}, 10.0)
            self.notify("exit", {})
        except (TimeoutError, EOFError, RuntimeError, OSError):
            pass


def _read_uri(uri: str) -> str | None:
    if not uri.startswith("file:"):
        return None
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    try:
        return read_source(Path(url2pathname(urlparse(uri).path))).text
    except OSError:
        return None


def copybook_resolver(root: Path) -> Callable[[str], str | None]:
    """name -> file uri over every copybook-extension file under the corpus (first in sorted path order wins)."""
    index: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts and p.suffix in COPY_EXTS:
            index.setdefault(p.stem.upper(), p.resolve().as_uri())
    return lambda name: index.get(name.upper())


def _is_comment(line: str) -> bool:
    return not line.strip() or line[6:7] in ("*", "/") or line.lstrip().startswith("*>")


def _symbol_level(lines: list[str], ln: int) -> int | None:
    """The level number of the data description entry starting at 0-based line `ln` (symbols carry none)."""
    if not 0 <= ln < len(lines):
        return None
    for text in (lines[ln][6:72], lines[ln]):
        m = _LEVEL.match(text)
        if m:
            return int(m.group(1))
    return None


def symbol_facts(symbols: list[dict[str, Any]], lines: list[str]) -> dict[str, set[str]]:
    """Facts of one file from its hierarchical documentSymbol tree. Lines are 1-based like the other adapters."""
    f: dict[str, set[str]] = {ch: set() for ch in LSP_CHANNELS}
    programs: list[str] = []

    def span(sym: dict[str, Any], own_end: int | None = None) -> tuple[int, int]:
        s = int(sym["range"]["start"]["line"]) + 1
        e = own_end if own_end is not None else int(sym["range"]["end"]["line"]) + 1
        while e > s and 0 < e <= len(lines) and _is_comment(lines[e - 1]):  # trailing blanks / comments are no unit's
            e -= 1
        return s, e

    def unit(sym: dict[str, Any], name: str) -> str:
        children = sym.get("children") or []
        # a section's own extent stops where its first paragraph starts
        own_end = int(children[0]["range"]["start"]["line"]) if children else None
        label = name if name == F.MAIN_LINE else F.unit_name(max(len(programs) - 1, 0), programs[-1] if programs else None, name)  # fmt: skip
        s, e = span(sym, own_end)
        if name == F.MAIN_LINE:
            if e > s:
                f["unit_extents"].add(f"{label} L{s}-{e}")
        else:
            f["units"].add(label)
            f["unit_extents"].add(f"{label} L{s}-{max(e, s)}")
        return label

    def visit(sym: dict[str, Any], in_proc: bool) -> None:
        name, kind = str(sym.get("name", "")), sym.get("kind")
        if name.startswith("PROGRAM: "):
            programs.append(name[9:].strip().upper())
        elif name.startswith("PROGRAM-ID ") and len(name.split()) > 1:
            f["program_ids"].add(name.split()[1].strip(".").upper())
        elif name == "PROCEDURE DIVISION" or name.startswith("PROCEDURE DIVISION "):
            unit(sym, F.MAIN_LINE)
            in_proc = True
        elif kind in SYMBOL_FILE_KINDS and name.startswith("COPY "):
            f["copybooks"].add(name[5:].strip().upper())
        elif in_proc and kind == 6 and " DIVISION" not in name:
            unit(sym, name.upper())
        elif kind in (SYMBOL_VARIABLE, SYMBOL_STRUCT) and not in_proc:
            ln = int(sym["range"]["start"]["line"])
            level = _symbol_level(lines, ln)
            if level is not None:
                F.merge_item(f, {"data_items": F.item_values(ln + 1, level, name)["data_items"]})
        for c in sym.get("children") or []:
            visit(c, in_proc)

    for top in symbols:
        visit(top, False)
    return f


def lsp_doc(corpus: str, root: Path, key: dict[str, Any], jar: Path) -> dict[str, Any]:
    doc = F.new_doc("che4z", che4z_version(jar), corpus, LSP_CHANNELS)
    proc = subprocess.Popen(["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Xss64m", "-jar", str(jar), "pipeEnabled"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # fmt: skip
    assert proc.stdin is not None and proc.stdout is not None
    session = LspSession(proc.stdout, proc.stdin, copybook_resolver(root))
    wall = 0.0
    try:
        session.start()
        for rel in sorted(key.get("programs", {})):
            path = root / rel
            t0 = time.perf_counter()
            try:
                text = read_source(path).text
                symbols, diags = session.open_and_analyse(path, text)
                facts = symbol_facts(symbols, text.splitlines())
            except (TimeoutError, EOFError, RuntimeError, KeyError, TypeError, ValueError, OSError) as e:
                F.add_file(doc, rel, {}, status="fail", error=f"LSP: {type(e).__name__}: {e}"[:200])
                if isinstance(e, (EOFError, OSError)) or proc.poll() is not None:
                    break  # the server is gone: later members would only repeat this
                continue
            finally:
                wall += time.perf_counter() - t0
            syntax = [d for d in diags if d.get("severity") == 1 and "Copybook not found" not in str(d.get("message"))]
            F.add_file(doc, rel, facts, status="partial" if syntax else "ok", seconds=time.perf_counter() - t0,
                       error=str(syntax[0].get("message", ""))[:160] if syntax else None)  # fmt: skip
    finally:
        session.stop()
        proc.kill()
        proc.wait()
    doc["wall_seconds"] = wall
    return doc


def che4z_doc(corpus: str, root: Path, key: dict[str, Any], mode: str = "lsp") -> dict[str, Any]:
    jar = Path(os.environ.get(JAR_ENV) or "")
    if not jar.is_file():
        raise SystemExit(f"{JAR_ENV} does not name the Che4z server.jar (see tests/tools/referees/README.md)")
    if mode == "lsp":
        return lsp_doc(corpus, root, key, jar)
    doc = F.new_doc("che4z", che4z_version(jar), corpus, CHANNELS)
    dirs = copy_dirs(root)
    scratch = os.environ.get("REFEREES_CACHE")
    if scratch:
        Path(scratch).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="che4z-", dir=scratch))
    wall = 0.0
    for rel in sorted(key.get("programs", {})):
        path = root / rel
        t0 = time.perf_counter()
        out, err = run_member(jar, path, dirs, work, ast=True)
        if out is None:
            diag, err2 = run_member(jar, path, dirs, work, ast=False)
            wall += time.perf_counter() - t0
            syntax = [d for d in (diag or {}).get("diagnostics", []) if d.get("severity") == "ERROR" and d.get("code") != "missing copybook"]  # fmt: skip
            note = "parsed clean" if diag is not None and not syntax else f"{len(syntax)} error diagnostic(s)"
            F.add_file(doc, rel, {}, status="fail", seconds=(diag or {}).get("timings", {}).get("total"),
                       error=f"AST not serialisable ({err}); without --ast: {note if diag else err2}")  # fmt: skip
            continue
        wall += time.perf_counter() - t0
        if "asts" not in out:
            # 2.5.1's CLI prints only {uri, language} and exits 1 on a program with a CALL statement
            F.add_file(doc, rel, {}, status="fail", error="analysis returned no AST and no diagnostics (CLI crash)")
            continue
        syntax = [d for d in out.get("diagnostics", []) if d.get("severity") == "ERROR" and d.get("code") != "missing copybook"]  # fmt: skip
        try:
            facts = ast_facts(out, path)
        except (KeyError, TypeError, ValueError) as e:
            F.add_file(doc, rel, {}, status="fail", error=f"AST walk: {type(e).__name__}: {e}")
            continue
        F.add_file(doc, rel, facts, status="partial" if syntax else "ok", seconds=out.get("timings", {}).get("total"),
                   error=(syntax[0].get("suggestion") or syntax[0].get("message") or "")[:160] if syntax else None)  # fmt: skip
    work.rmdir()
    doc["wall_seconds"] = wall
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mode", choices=("lsp", "cli"), default="lsp")
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(che4z_doc(args.corpus, args.root, key, args.mode), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
