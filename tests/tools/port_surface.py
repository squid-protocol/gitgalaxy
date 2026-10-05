#!/usr/bin/env python3
r"""
#4343: bring a committed port's deployed entry points (its facades) to what the generator writes now.

A port is a service class the porting loop wrote over a generated one: the model ported the PROCEDURE DIVISION into
runTask (and its helpers), and kept, changed or wrote the generated entry points around it. When the generator's
entry points change (#4342 / #4349: no executeX for a CICS program, render / submit only behind a screen
controller, handleTransaction / handleLink run the program in the region), the committed ports keep the old ones:
methods no proof can run, and facades that differ from the path the proof drives (#4343: HXEXT's handleTransaction
never ran the program; render / submit rebuilt screens outside runTask).

This rewrites ONLY that surface, from a fresh generation of the same program, and leaves the ported logic alone:

  * each facade the generator writes (handleTransaction, handleLink, executeX, renderX, submitX) replaces the port's
    method of that name, Javadoc and all -- the generated text, verbatim;
  * a facade the port has and the generator no longer writes is removed, unless the ported logic itself calls it
    (runTask may build its screen through renderX: that is ported behaviour the proof runs, and stays);
  * a facade the generator writes and the port lacks is added before runTask;
  * a private helper only the removed or replaced code called is removed with it (seed / bridgeHcsub of HCMAIN's
    old executeHcmain);
  * the generated file's imports the port lacks are added.

    python tests/tools/port_surface.py apply  --port PORT.java --generated GENERATED.java [--check]
    python tests/tools/port_surface.py crucible --work DIR [--cases CASE ...] [--check]

`crucible` runs the CICS crucible's java-ported side once (cics_crucible.py --keep DIR) to get each case's fresh
generation (generated_before_overlay/), then applies this to every committed port under tests/cics_crucible/ports
and appends a `resurfaced` event to its provenance.json (the methods replaced, removed, added). The port must then be
re-proven: `crucible_port_provenance.py reprove` and `evidence.py prove`. `--check` changes nothing and exits 1 when
a port's surface differs from the generator's.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS = REPO_ROOT / "tests" / "cics_crucible" / "ports"
sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.tools.cobol_to_java import proof_reach  # noqa: E402

# The entry points the generator writes around runTask / handleCall / runBatch (cobol_to_java_*_forge.py).
FACADE = re.compile(r"handleTransaction|handleLink|execute[A-Z]\w*|render[A-Z]\w*|submit[A-Z]\w*")
_LEAD_MARKS = ("/**", "*", "*/", "//", "@")  # a Javadoc / comment / annotation line starts so
_IMPORT = re.compile(r"^import\s+[\w.*]+\s*;\s*$", re.M)


@dataclass
class Span:
    name: str
    start: int  # first line (0-based) of its Javadoc / annotations
    end: int  # one past its closing brace's line
    visibility: str


@dataclass
class Change:
    replaced: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    helpers_removed: list[str] = field(default_factory=list)
    imports_added: list[str] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.replaced or self.removed or self.added or self.helpers_removed or self.imports_added)

    def as_dict(self) -> dict[str, list[str]]:
        return {k: v for k, v in self.__dict__.items() if v}


def spans(path: Path, text: str) -> list[Span]:
    """The top-level class's methods, each with the comment / annotation lines right above it."""
    unit = proof_reach.parse_java(path, text)
    lines = text.split("\n")
    out = []
    for m in unit.methods:
        if m.constructor:
            continue
        start = m.line - 1
        while start > 0 and lines[start - 1].strip().startswith(_LEAD_MARKS):
            start -= 1
        out.append(Span(m.name, start, m.end, m.visibility))
    return out


def _reached(path: Path, text: str, roots: set[str]) -> set[str]:
    """The method names reached from `roots` (and every non-private method) by proof_reach's call following."""
    unit = proof_reach.parse_java(path, text)
    entry = roots | {m.name for m in unit.methods if m.visibility != "private"}
    report = proof_reach.reach([unit], roots=tuple(entry))
    if not report:
        return {m.name for m in unit.methods}
    unproven = {m["method"] for r in report.values() for m in r["unproven"]}
    return {m.name for m in unit.methods} - unproven


def _cut(lines: list[str], span: Span) -> None:
    """Remove a span and one blank line around it."""
    end = span.end
    if end < len(lines) and not lines[end].strip() and span.start > 0 and not lines[span.start - 1].strip():
        end += 1
    del lines[span.start : end]


def resurface(port: Path, generated: Path, text: Optional[str] = None) -> tuple[str, Change]:
    """The port's text with its facades brought to the generated file's, and what changed."""
    src = port.read_text(encoding="utf-8") if text is None else text
    gen = generated.read_text(encoding="utf-8")
    ch = Change()
    gen_lines = gen.split("\n")
    gen_facades = {
        s.name: "\n".join(gen_lines[s.start : s.end]) for s in spans(generated, gen) if FACADE.fullmatch(s.name)
    }
    before_reach = _reached(port, src, set())
    # what the ported logic (everything but the facades) calls: a facade it calls is ported behaviour, kept
    lines = src.split("\n")
    port_spans = spans(port, src)
    facade_names = {s.name for s in port_spans if FACADE.fullmatch(s.name)}
    logic = "\n".join(ln for i, ln in enumerate(lines)
                      if not any(s.start <= i < s.end for s in port_spans if s.name in facade_names))  # fmt: skip
    called = {c.group("name") for c in proof_reach._CALL.finditer(proof_reach.strip_java(logic)) if c.group("name")}
    for s in sorted(port_spans, key=lambda s: s.start, reverse=True):
        if not FACADE.fullmatch(s.name):
            continue
        new = gen_facades.get(s.name)
        if new is not None:
            if "\n".join(lines[s.start : s.end]).strip() != new.strip():
                lines[s.start : s.end] = new.split("\n")
                ch.replaced.append(s.name)
        elif s.name not in called:
            _cut(lines, s)
            ch.removed.append(s.name)
    missing = [n for n in gen_facades if n not in facade_names]
    if missing:
        text_now = "\n".join(lines)
        at = next((s.start for s in spans(port, text_now) if s.name == "runTask"), None)
        if at is not None:
            block: list[str] = []
            for n in missing:
                block += [*gen_facades[n].split("\n"), ""]
                ch.added.append(n)
            lines[at:at] = block
    # helpers only the old facades reached
    while True:
        text_now = "\n".join(lines)
        now = _reached(port, text_now, set())
        gone = [s for s in spans(port, text_now)
                if s.visibility == "private" and s.name in before_reach and s.name not in now]  # fmt: skip
        if not gone:
            break
        for s in sorted(gone, key=lambda s: s.start, reverse=True):
            _cut(lines, s)
            ch.helpers_removed.append(s.name)
    text_now = "\n".join(lines)
    have = set(_IMPORT.findall(text_now))
    need = [i for i in _IMPORT.findall(gen) if i not in have]
    if need:
        last = list(_IMPORT.finditer(text_now))[-1]
        text_now = text_now[: last.end()] + "\n" + "\n".join(need) + text_now[last.end() :]
        ch.imports_added = [i.split()[1].rstrip(";") for i in need]
    ch.replaced.reverse()
    ch.removed.reverse()
    return text_now, ch


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def record(prov_path: Path, ch: Change, generated_from: str) -> None:
    """Append the `resurfaced` event to the port's provenance.json, and say the port is no longer the model's
    answer alone (edited_after)."""
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    head = (subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,  # noqa: S603, S607
                           text=True, check=False).stdout.strip())  # fmt: skip
    prov.setdefault("history", []).append({"at": _now(), "event": "resurfaced", "by": "tests/tools/port_surface.py",
                                           "generator_commit": head, "generated_from": generated_from,
                                           **ch.as_dict()})  # fmt: skip
    prov["edited_after"] = ("the deployed entry points (facades) were brought to the generator's by "
                            "tests/tools/port_surface.py (#4343; see history 'resurfaced'); runTask and the logic it "
                            "runs are the model's answer")  # fmt: skip
    prov_path.write_text(json.dumps(prov, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def crucible(work: Path, cases: Optional[list[str]], check: bool, offline: bool) -> int:
    argv = [sys.executable, str(REPO_ROOT / "tests" / "tools" / "cics_crucible.py"), "--sides", "java-ported",
            "--keep", str(work)] + (["--cases", *cases] if cases else []) + (["--offline"] if offline else [])  # fmt: skip
    if not all((work / c).is_dir() for c in (cases or [p.name for p in PORTS.iterdir() if p.is_dir()])):
        subprocess.run(argv, check=False)  # noqa: S603
    differs = 0
    for prov_path in sorted(PORTS.glob("*/*/provenance.json")):
        case, prog_dir = prov_path.parent.parent.name, prov_path.parent
        if cases and case not in cases:
            continue
        for port in sorted((prog_dir / "overlay").rglob("*.java")):
            rel = port.relative_to(prog_dir / "overlay")
            gen = work / case / "forge-ported" / "generated_before_overlay" / rel
            if not gen.is_file():
                print(f"{case}/{prog_dir.name}: no fresh generation of {rel} under {gen.parent}", file=sys.stderr)
                return 2
            text, ch = resurface(port, gen)
            if ch.empty():
                print(f"{case}/{prog_dir.name}: {rel}: surface is the generator's")
                continue
            differs += 1
            print(f"{case}/{prog_dir.name}: {rel}: {json.dumps(ch.as_dict())}")
            if not check:
                port.write_text(text, encoding="utf-8")
                record(prov_path, ch, rel.as_posix())
    return 1 if check and differs else 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--port", type=Path, required=True)
    a.add_argument("--generated", type=Path, required=True)
    a.add_argument("--check", action="store_true")
    c = sub.add_parser("crucible")
    c.add_argument("--work", type=Path, required=True)
    c.add_argument("--cases", nargs="+")
    c.add_argument("--check", action="store_true")
    c.add_argument("--offline", action="store_true")
    opts = ap.parse_args(argv)
    if opts.cmd == "apply":
        text, ch = resurface(opts.port, opts.generated)
        print(json.dumps(ch.as_dict()))
        if not opts.check and not ch.empty():
            opts.port.write_text(text, encoding="utf-8")
        return 1 if opts.check and not ch.empty() else 0
    return crucible(opts.work.resolve(), opts.cases, opts.check, opts.offline)


if __name__ == "__main__":
    sys.exit(main())
