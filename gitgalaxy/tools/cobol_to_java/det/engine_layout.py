"""#5649: the record layouts the translator takes from the engine (GalaxyIR.record_layout), at its own POINTER width.

The engine computes every record's storage once (offsets, lengths, OCCURS widths, REDEFINES overlays, the stand-in
copybooks of core/copy_libraries); the translator lays the record out at its storage's POINTER width
(det.cics.POINTER_BYTES: GnuCOBOL x86-64, oracle_assumptions.md C9) and takes the engine's numbers for every record the
engine reads at the same file / line / level. A record outside the estate (a system member such as DFHAID, a BMS
symbolic map the translator generates, a stand-in rooted record, the special registers it adds) keeps the
translator's own layout: the engine has no entry for it.

Modes (`EngineLayouts.mode`):
- "engine": the elementary items take the engine's offsets and widths; each group, REDEFINES overlay and the record
  follow from them.
- "check": as "engine", and the translator's own computation is kept beside it: any difference refuses the program
  by name (LayoutDisagrees). For one release (#5649), until the translator's copy is deleted.
SYNCHRONIZED (#5694): the translator's own layout models no SYNC slack; the engine does (#4266). "engine" mode takes the
engine's slack offsets, a POINTER SYNC at the width in use; "check" mode refuses a record whose slack the translator
lacks. A level-01 SYNC item starts its record and has no slack (every burned one).
A record whose items do not pair one to one with the engine's fields (a name or count that differs), or whose width
the engine does not know (an unexpanded COPY), refuses in both modes: there is nothing to consume."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gitgalaxy.tools.cobol_to_java.det.layout import Item, LayoutError

MODES = ("engine", "check")
_IRS: dict[Path, Any] = {}  # one load of each scan DB per process
_IRS_LOCK = threading.Lock()


class LayoutDisagrees(LayoutError):
    """The engine's layout of a record differs from the translator's own (check mode), or cannot be consumed."""


def elementary(rec: Item) -> list[Item]:
    """The elementary storage items of a record in storage order, REDEFINES subtrees (below the root) left out: the
    items GalaxyIR.record_layout lists as its `fields`."""
    out: list[Item] = []

    def walk(it: Item) -> None:
        if it.level in (66, 88) or (it is not rec and it.redefines):
            return
        if it.children and it.pic is None:
            for c in it.children:
                walk(c)
            return
        if it.pic is None and it.usage == "DISPLAY":
            return  # an empty group: no storage of its own
        out.append(it)

    walk(rec)
    return out


def _closure(ir: Any, ef: Any) -> list[Any]:
    """Every copybook file the program's COPYs reach, transitively."""
    seen: dict[str, Any] = {}
    todo = [ef]
    while todo:
        f = todo.pop()
        for c in ir._copy_files(f):
            if c.file_path not in seen:
                seen[c.file_path] = c
                todo.append(c)
    return list(seen.values())


@dataclass
class EngineRecords:
    """The engine's records of one program, found by where the translator read them: (file, line, level), or by
    (name, level) for a record a section-level COPY ... REPLACING built (#4472: GalaxyIR places those at the COPY
    statement's line, under their replaced names)."""

    ir: Any
    ef: Any
    by_loc: dict[tuple[str, int, int], tuple[Any, Any]] = field(default_factory=dict)
    replaced_roots: dict[tuple[str, int], Any] = field(default_factory=dict)

    @classmethod
    def of(cls, ir: Any, ef: Any) -> EngineRecords:
        out = cls(ir, ef)
        for f in [ef, *_closure(ir, ef)]:
            for it in f.data_items:
                out.by_loc.setdefault((f.file_path, it.line, it.level), (f, it))
        copied = {id(it) for it in ef.copied_items}
        for r in ef.records:
            if id(r) in copied:
                out.replaced_roots.setdefault(((r.name or "").upper(), r.level), r)
        return out

    def find(self, name: str | None, file: str, line: int, level: int) -> tuple[Any, Any, list | None] | None:
        """(owner file, engine item, the copy extension) of the record the translator read at `file` (repo-relative)
        / `line`, or None when the engine reads none there."""
        hit = self.by_loc.get((file, line, level))
        root = self.replaced_roots.get(((name or "").upper(), level))
        if root is not None:
            hit = (self.ef, root)
        if hit is None:
            return None
        owner, item = hit
        ext = None
        if owner is not self.ef:  # a copied record continued in the program (GalaxyIR._copy_extension)
            roots = [r for r in owner.records if r.level not in (66, 88)]
            if roots and roots[-1] is item:
                ext = self.ir._copy_extension(self.ef, owner) or None
        return owner, item, ext

    def layout(self, name: str | None, file: str, line: int, level: int, pointer_bytes: int) -> dict | None:
        """GalaxyIR.record_layout of the record at `file` / `line` / `level` at `pointer_bytes`; None: not read."""
        hit = self.find(name, file, line, level)
        if hit is None:
            return None
        owner, item, ext = hit
        return self.ir.record_layout(owner, item, ext, pointer_bytes=pointer_bytes)


def _shift(it: Item, by: int) -> None:
    for x in it.walk():
        x.offset += by


def adopt(rec: Item, lay: dict, where: str) -> None:
    """`rec` laid out by the engine's `lay` (GalaxyIR.record_layout): each elementary item takes the engine's offset
    and width, a REDEFINES overlay moves with its target, and each group spans its children. LayoutDisagrees where
    the two cannot be paired."""
    if lay.get("bytes") is None:
        raise LayoutDisagrees(f"{where}: the engine does not know the record's width "
                              f"(unexpanded: {', '.join(map(str, lay.get('unexpanded') or [])) or '?'})")  # fmt: skip
    mine, theirs = elementary(rec), lay["fields"]
    if len(mine) != len(theirs) or any((it.name or "FILLER").upper() != (f.get("name") or "FILLER").upper()
                                       for it, f in zip(mine, theirs, strict=True)):  # fmt: skip
        raise LayoutDisagrees(f"{where}: the engine's fields ({len(theirs)}) do not pair with the record's "
                              f"elementary items ({len(mine)})")  # fmt: skip
    before = {id(x): x.offset for x in rec.walk()}
    for it, f in zip(mine, theirs, strict=True):
        it.offset = f["offset"]
        it.size = f["bytes"] // max(it.occurs, 1)

    def span(it: Item) -> None:
        """Each group's offset and width from its children; a REDEFINES overlay keeps its place on its target."""
        if not it.children or it.pic is not None:
            return
        by_name: dict[str, Item] = {}
        ends: list[tuple[int, int]] = []
        for c in it.children:
            if c.level in (66, 88):
                continue
            if not c.children and c.pic is None and c.usage == "DISPLAY":
                c.offset = ends[-1][1] if ends else it.offset  # an empty group sits where the storage before it ends
            elif c.redefines and c.redefines in by_name:
                target = by_name[c.redefines]
                _shift(c, target.offset - before[id(target)] - (c.offset - before[id(c)]))
            span(c)
            by_name[c.name] = c
            ends.append((c.offset, c.offset + c.size * c.occurs))
        if ends:
            it.offset = min(s for s, _ in ends)
            it.size = max(e for _, e in ends) - it.offset

    span(rec)
    rec.offset = 0
    rec.size = lay["bytes"] // max(rec.occurs, 1)


def differences(rec: Item, own: dict[int, tuple[int, int]]) -> list[str]:
    """Where the engine's layout (now in `rec`) differs from the translator's own (`own`: id -> (offset, size))."""
    out = []
    for x in rec.walk():
        o = own.get(id(x))
        if o is not None and o != (x.offset, x.size):
            out.append(f"{x.name} engine @{x.offset}+{x.size}, translator @{o[0]}+{o[1]}")
    return out


@dataclass
class EngineLayouts:
    """The engine's layouts for one program's records (GalaxyIR, program `rel` of the estate at `root`), at the
    translator's POINTER width. `consumed` / `own`: the records laid out by the engine / by the translator alone."""

    records: EngineRecords
    root: Path
    mode: str = "check"
    pointer_bytes: int = 8
    consumed: list[str] = field(default_factory=list)
    own: list[str] = field(default_factory=list)

    @classmethod
    def from_ir(cls, ir: Any, rel: str, root: Path, mode: str = "check", pointer_bytes: int | None = None):
        """None when the engine holds no file `rel`."""
        if mode not in MODES:
            raise ValueError(f"layout mode {mode!r}: one of {', '.join(MODES)}")
        ef = ir.files.get(rel)
        if ef is None:
            return None
        if pointer_bytes is None:
            from gitgalaxy.tools.cobol_to_java.det.cics import POINTER_BYTES

            pointer_bytes = POINTER_BYTES
        return cls(EngineRecords.of(ir, ef), root, mode, pointer_bytes)

    @classmethod
    def for_project(cls, project: Path, corpus: Path, rel: str, mode: str = "check"):
        """The layouts of program `rel` (relative to the scanned `corpus`) from the estate scan beside the generated
        `project` (the clean room's galaxy DB); None without a scan or a file the scan does not hold."""
        from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

        db = next(iter(sorted(project.parent.glob("*_gitgalaxy_clean_*/04_ir_state_dumps/*_galaxy_master.db"))), None)
        if db is None:
            return None
        with _IRS_LOCK:
            if db not in _IRS:
                _IRS[db] = load_galaxy_ir(db)
            ir = _IRS[db]
        return cls.from_ir(ir, rel, corpus, mode)

    def rel(self, file: str) -> str | None:
        try:
            return Path(file).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return None

    def apply(self, records: list[Item], lines: list) -> list[Item]:
        """`records` (layout.parse of `lines`) with the engine's layouts taken; LayoutDisagrees in check mode where
        the translator's own differs. `consumed` / `own` are this call's."""
        self.consumed, self.own = [], []
        for rec in records:
            src = lines[rec.line - 1] if 0 < rec.line <= len(lines) else None
            rel = self.rel(src.file) if src is not None else None
            lay = None
            if src is not None and rel is not None:
                lay = self.records.layout(rec.name, rel, src.line, rec.level, self.pointer_bytes)
            if src is None or lay is None:
                self.own.append(rec.name)
                continue
            where = f"{rel}:{src.line}: {rec.level:02d} {rec.name}"
            own = {id(x): (x.offset, x.size) for x in rec.walk()}
            adopt(rec, lay, where)
            if self.mode == "check":
                diff = differences(rec, own)
                if diff:
                    raise LayoutDisagrees(f"{where}: the engine's layout differs from the translator's: "
                                          + "; ".join(diff[:5]) + (f" (+{len(diff) - 5} more)" if len(diff) > 5 else ""))  # fmt: skip
            self.consumed.append(rec.name)
        return records
