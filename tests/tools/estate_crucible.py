"""
#4317: score the engine against estate-crucible, a synthetic z/OS estate whose answer key is
generated with its code (squid-protocol/estate-crucible, format `estate-crucible-key/1`).

    python tests/tools/estate_crucible.py [--crucible PATH] [--db DB] [--scan-dir DIR]
                                          [--json out.json] [--md out.md]

Scans `<crucible>/estate` with galaxyscope (or reads --db), loads the master DB through
GalaxyIR, and diffs every fact channel of the key against it:

  programs        class_data PROGRAM-IDs
  units           function_data name + extent (start_line, start_line + loc - 1); the
                  main line (code before the first paragraph) as a unit or a
                  synthetic_unit_data row
  edges           PERFORM / CALL -> function_data.calls_out_to, GO TO -> transfers_to,
                  per owning unit (the main line's from synthetic_unit_data)
  call_sites      call_site_data (CALL, LINK, XCTL, RETURN TRANSID, EXEC PGM)
  copies          file_data.raw_imports + edge_data import edges
  data_items      record_data entries
  layouts         GalaxyIR.record_layout of every 01 a program writes: bytes and every
                  elementary field's offset / length (REDEFINES overlays: unscored, the
                  layout reader skips them by design)
  sql_statements, sql_tables, jcl_steps, jcl_dds, screen_fields, csd_resources, transactions
  cics_resources  cics_resource_data (MAP / FILE / QUEUE commands)
  jcl_datasets    a JCL member's DSN references in file_data.raw_imports (a GDG reference as
                  its base or with its relative generation)
  file_control    file_control_data SELECTs;  entry_points  entry_point_data
  file_edges      edge_data kinds 'call' (CALL / LINK / XCTL) and 'exec' (EXEC PGM)
  copy_collisions the scan's `copy_member_collisions` report (#4265), read from the master DB
                  (repo_data, #4421)
  gaps            a reference the estate cannot answer: no edge_data edge from the member to
                  a member of that name
  dead            a paragraph: function_data.usage_status 1 (unused); a program or copybook:
                  no edge_data edge of any kind into its member

The scan is told the estate's code pages (`code_pages`) and copy libraries (`copy_libraries`,
v0.4.0+; derived from the library naming rule for older keys).

Units, edges, copies, data items and layouts are scored for COBOL and PL/I members; the
engine's own unit model of JCL / BMS / CSD is outside these channels. A key fact marked
`depends_on` (it can only pass once that horror is fixed) is reported as the horror's cascade.

Each check is pass / fail (found, an attribute differs) / missing / phantom (recorded but not
in the key, or a fact the key says must NOT be recorded) / unscored (the key states it, the DB
has no column for it). A horror passes when every check tagged with it passes.

A CI gate since #4317 phase 5: tests/tools/estate_crucible_gate.py ratchets this score against tests/estate_crucible/baseline.json. A failing check is a finding against the engine OR the key:
the key comes from a generator that can share the engine's blind spots, so read both.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / "tests"
for p in (str(REPO_ROOT), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _estate_crucible_pin import PATH_ENV, PINNED_REF, pin_mismatch  # noqa: E402

KEY_FORMAT = "estate-crucible-key/1"
STATUSES = ("pass", "fail", "missing", "phantom", "unscored")
CHANNELS = (
    "programs",
    "units",
    "edges",
    "call_sites",
    "copies",
    "data_items",
    "layouts",
    "sql_statements",
    "sql_tables",
    "jcl_steps",
    "jcl_dds",
    "screen_fields",
    "csd_resources",
    "transactions",
    "cics_resources",
    "jcl_datasets",
    "file_control",
    "entry_points",
    "file_edges",
    "data_moves",
    # phase 3 (estate realism)
    "copy_collisions",
    "gaps",
    "dead",
)
RESOLVED_VERBS = ("CALL", "LINK", "XCTL", "EXEC PGM")


@dataclass
class Check:
    channel: str
    member: str
    fact: str
    status: str
    horror: str | None = None
    detail: str = ""
    # horrors this fact can only pass after (a call to a program whose PROGRAM-ID is a horror)
    depends_on: list = field(default_factory=list)


@dataclass
class Score:
    checks: list = field(default_factory=list)  # Check
    engine_commit: str = ""
    key_generator: dict = field(default_factory=dict)

    def add(
        self,
        channel: str,
        member: str,
        fact: str,
        status: str,
        horror: str | None = None,
        detail: str = "",
        depends_on: list | None = None,
    ) -> None:
        self.checks.append(Check(channel, member, fact, status, horror, detail, list(depends_on or [])))


# ----------------------------------------------------------------------------- inputs


def crucible_path(arg: Path | None) -> Path:
    """--crucible, else $ESTATE_CRUCIBLE_PATH, else ../estate-crucible beside the main checkout."""
    if arg:
        return arg
    if os.environ.get(PATH_ENV):
        return Path(os.environ[PATH_ENV])
    common = subprocess.run(  # noqa: S603 -- fixed argv
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    main = (
        (Path(common) if Path(common).is_absolute() else REPO_ROOT / common).resolve().parent if common else REPO_ROOT
    )
    return main.parent / "estate-crucible"


def load_key(crucible: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """(manifest, {member path: key entry})."""
    manifest = json.loads((crucible / "key" / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != KEY_FORMAT:
        raise ValueError(f"{crucible}/key/manifest.json is {manifest.get('format')}; this scorer reads {KEY_FORMAT}")
    members: dict[str, dict[str, Any]] = {}
    for key_file in sorted({m["key"] for m in manifest["members"].values()}):
        members.update(json.loads((crucible / key_file).read_text(encoding="utf-8"))["members"])
    return manifest, members


def source_encoding_arg(manifest: dict[str, Any]) -> list[str]:
    """`--source-encoding PATH=CODEC,...` for every member the key says is not UTF-8: nothing in
    a raw EBCDIC member's bytes names its code page, so the scan is told, as an estate would be."""
    pages = manifest.get("code_pages") or {}
    if not pages:
        return []
    return ["--source-encoding", ",".join(f"{path}={codec}" for path, codec in sorted(pages.items()))]


# #4265: the estate's copy libraries, by its own naming rule (README "Copy libraries"): `<APP>CPY` is an
# app's copybook/ directory, `<APP>DCL` its dclgen/, `SHRCPY` shared/copylib/; a program's SYSLIB is its
# app's two libraries, then SHRCPY.
_LIBRARY_DIRS = (("copybook", "CPY"), ("dclgen", "DCL"))


def copy_library_declaration(manifest: dict[str, Any]) -> dict[str, Any]:
    """The `galaxyscope --copy-libraries` declaration of the estate the manifest describes: the key's
    own (`copy_libraries`, v0.4.0+: per-program SYSLIB orders, retired OLD libraries), else derived
    from the naming rule."""
    if manifest.get("copy_libraries"):
        return dict(manifest["copy_libraries"])
    libraries: dict[str, list[str]] = {}
    apps: dict[str, list[str]] = {}
    for path, member in sorted(manifest["members"].items()):
        directory = path.rsplit("/", 1)[0]
        if member.get("library") == "copylib":
            libraries.setdefault("SHRCPY", [])
            if directory not in libraries["SHRCPY"]:
                libraries["SHRCPY"].append(directory)
        for kind, suffix in _LIBRARY_DIRS:
            if member.get("library") == kind and member.get("app"):
                name = f"{member['app']}{suffix}"
                libraries.setdefault(name, [directory])
                apps.setdefault(member["app"], [])
                if name not in apps[member["app"]]:
                    apps[member["app"]].append(name)
        if member.get("app"):
            apps.setdefault(member["app"], [])
    shared = ["SHRCPY"] if "SHRCPY" in libraries else []
    syslib = [
        {"programs": f"apps/{app}/*", "order": sorted(names, key=lambda n: n.endswith("DCL")) + shared}
        for app, names in sorted(apps.items())
    ]
    return {"libraries": libraries, "syslib": syslib}


def scan(crucible: Path, scan_dir: Path) -> Path:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    manifest = json.loads((crucible / "key" / "manifest.json").read_text(encoding="utf-8"))
    scan_dir.mkdir(parents=True, exist_ok=True)
    declaration = scan_dir / "copy_libraries.json"
    declaration.write_text(json.dumps(copy_library_declaration(manifest), indent=1) + "\n", encoding="utf-8")
    extra = [*source_encoding_arg(manifest), "--copy-libraries", str(declaration)]

    saved = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (str(REPO_ROOT), saved) if p)
    try:
        return scan_to_db(crucible / "estate", scan_dir, extra_args=extra)
    finally:
        if saved is None:
            os.environ.pop("PYTHONPATH")
        else:
            os.environ["PYTHONPATH"] = saved


class Engine:
    """The master DB, through GalaxyIR plus the few columns GalaxyIR does not carry
    (calls_out_to / transfers_to, synthetic units, raw_imports)."""

    def __init__(self, db: Path) -> None:
        from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

        self.ir = load_galaxy_ir(db)
        self.files = self.ir.files
        # the scan's COPY collision report (#4421: persisted in repo_data); None: no copy libraries declared
        self.collisions: list[dict[str, Any]] | None = self.ir.copy_member_collisions
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            ids = {
                fid: path.replace("\\", "/")
                for fid, path in conn.execute(
                    "SELECT id, file_path FROM file_data WHERE repo_name = ? AND commit_hash = ?",
                    (self.ir.repo_name, self.ir.commit_hash),
                )
            }
            self.raw_imports: dict[str, list[str]] = {}
            for fid, raw in conn.execute("SELECT id, raw_imports FROM file_data"):
                if fid in ids:
                    try:
                        self.raw_imports[ids[fid]] = [str(x) for x in json.loads(raw or "[]")]
                    except ValueError:
                        self.raw_imports[ids[fid]] = []
            # (path, unit) -> {"start", "end", "calls", "transfers", "usage"}
            self.units: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for fid, name, start, loc, calls, transfers, usage in conn.execute(
                "SELECT file_id, func_name, start_line, loc, calls_out_to, transfers_to, usage_status FROM function_data"
            ):
                if fid in ids:
                    self.units[ids[fid]].append(
                        {
                            "name": name or "",
                            "start": int(start or 0),
                            "end": int(start or 0) + int(loc or 0) - 1,
                            "calls": _json_list(calls),
                            "transfers": _json_list(transfers),
                            "synthetic": False,
                            # detector: 0 normal, 1 orphan / unused, 2 duplicate
                            "usage": usage,
                        }
                    )
            self.synthetic: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for fid, name, start, calls, transfers in conn.execute(
                "SELECT file_id, unit_name, start_line, calls_out_to, transfers_to FROM synthetic_unit_data"
            ):
                if fid in ids:
                    self.synthetic[ids[fid]].append(
                        {
                            "name": name or "",
                            "start": int(start or 0),
                            "end": None,
                            "calls": _json_list(calls),
                            "transfers": _json_list(transfers),
                            "synthetic": True,
                        }
                    )
            # #3200 / #3237: resolved invocation edges between files, by kind
            self.file_edges: dict[str, set] = defaultdict(set)
            # every resolved edge (import, call, exec, ...) by source and by target (gaps, dead)
            self.out_edges: dict[str, set] = defaultdict(set)
            self.in_edges: dict[str, set] = defaultdict(set)
            for src, dst, kind in conn.execute("SELECT src_file_id, dst_file_id, edge_kind FROM edge_data"):
                if src in ids and dst in ids:
                    if kind in ("call", "exec"):
                        self.file_edges[ids[src]].add((ids[dst], kind))
                    self.out_edges[ids[src]].add((ids[dst], kind or "import"))
                    self.in_edges[ids[dst]].add((ids[src], kind or "import"))
            self.excluded: dict[str, str] = {}
            for path, reason in conn.execute("SELECT file_path, exclusion_reason FROM excluded_artifacts"):
                self.excluded[str(path).replace("\\", "/")] = reason or ""
        finally:
            conn.close()


def _json_list(raw: str | None) -> list[str]:
    try:
        v = json.loads(raw) if raw else []
    except ValueError:
        return []
    return [str(x) for x in v] if isinstance(v, list) else []


def _u(v: Any) -> Any:
    return v.upper() if isinstance(v, str) else v


def _val(v: str | None) -> str | None:
    """A VALUE as its content: quotes dropped, blanks inside a literal kept."""
    if v is None:
        return None
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v


def _phantoms(entry: dict[str, Any], channel: str) -> list[dict[str, Any]]:
    return [p for p in entry.get("phantoms", []) if p["channel"] == channel]


def _diff(pairs: list[tuple[str, Any, Any]]) -> str:
    return "; ".join(f"{name}: key {k!r} engine {e!r}" for name, k, e in pairs if k != e)


# ----------------------------------------------------------------------------- channels


def score_programs(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    got = {p.upper() for p in (ef.program_ids if ef else [])}
    want = set()
    for f in entry.get("programs", []):
        want.add(f["program_id"].upper())
        status = "pass" if f["program_id"].upper() in got else "missing"
        sc.add("programs", path, f["program_id"], status, f.get("horror"))
    for extra in sorted(got - want):
        sc.add("programs", path, extra, "phantom")


def _owner(eng: Engine, path: str, unit: str | None, start: int | None) -> dict[str, Any] | None:
    """The engine unit that holds a key unit: by name (the one nearest `start` when a member
    holds several programs with the same paragraph names), or, for the main line (no name),
    a synthetic_unit_data row or a function_data unit at its first line."""
    if unit is not None:
        hits = [u for u in eng.units.get(path, []) if u["name"].upper() == unit.upper()]
        if start is not None and hits:
            return min(hits, key=lambda u: abs(u["start"] - start))
        return hits[0] if hits else None
    cands = eng.synthetic.get(path, []) + eng.units.get(path, [])
    if start is None:
        return eng.synthetic[path][0] if eng.synthetic.get(path) else None
    near = [u for u in cands if start - 2 <= u["start"] <= start]
    return max(near, key=lambda u: u["start"]) if near else None


def score_units(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    keyed: set[int] = set()
    for f in entry.get("units", []):
        label = f["name"] or "(main line)"
        h = f.get("horror")
        u = _owner(eng, path, f["name"], f["start_line"])
        if f["name"] is None:
            if u is None:
                sc.add("units", path, label, "missing", h, f"lines {f['start_line']}-{f['end_line']}: no unit")
                continue
            keyed.add(id(u))
            sc.add("units", path, label, "pass", h, "synthetic unit" if u["synthetic"] else f"unit {u['name']}")
            continue
        if u is None or id(u) in keyed:
            sc.add("units", path, label, "missing", h)
            continue
        keyed.add(id(u))
        d = _diff([("start_line", f["start_line"], u["start"]), ("end_line", f["end_line"], u["end"])])
        sc.add("units", path, label, "fail" if d else "pass", h, d)
    explicit = {p["name"].upper(): p for p in _phantoms(entry, "units")}
    for p in explicit.values():
        if not any(u["name"].upper() == p["name"].upper() for u in eng.units.get(path, [])):
            sc.add("units", path, f"not {p['name']}", "pass", p.get("horror"))
    for u in eng.units.get(path, []):
        if id(u) not in keyed:
            p = explicit.get(u["name"].upper())
            sc.add(
                "units",
                path,
                u["name"],
                "phantom",
                p.get("horror") if p else None,
                p["why"] if p else f"unkeyed unit at line {u['start']}",
            )


def score_edges(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    unit_starts = {(f.get("program"), f["name"]): f["start_line"] for f in entry.get("units", [])}
    claimed: dict[int, set] = defaultdict(set)  # id(owner) -> {(list, TARGET)}
    for f in entry.get("edges", []):
        lst = "transfers" if f["kind"] == "goto" else "calls"
        label = f"{f['from'] or '(main line)'} -{f['kind']}-> {f['target']} @{f['line']}"
        u = _owner(eng, path, f["from"], unit_starts.get((f.get("program"), f["from"])))
        if u is None:
            sc.add("edges", path, label, "missing", f.get("horror"), "the owning unit is not recorded")
            continue
        claimed[id(u)].add((lst, f["target"].upper()))
        ok = f["target"].upper() in {t.upper() for t in u[lst]}
        sc.add(
            "edges",
            path,
            label,
            "pass" if ok else "missing",
            f.get("horror"),
            ""
            if ok
            else f"not in {u['name'] or 'synthetic unit'}.{'transfers_to' if lst == 'transfers' else 'calls_out_to'}",
        )
    explicit = {(p["from"], p["target"].upper()): p for p in _phantoms(entry, "edges")}
    seen = set()
    for u in eng.units.get(path, []) + eng.synthetic.get(path, []):
        for lst in ("calls", "transfers"):
            for t in sorted(set(x.upper() for x in u[lst])):
                if (lst, t) in claimed.get(id(u), set()):
                    continue
                p = next((ph for (frm, tgt), ph in explicit.items() if tgt == t), None)
                if p:
                    seen.add((p["from"], t))
                kind = "transfers_to" if lst == "transfers" else "calls_out_to"
                sc.add(
                    "edges",
                    path,
                    f"{u['name'] or '(synthetic)'}.{kind} {t}",
                    "phantom",
                    p.get("horror") if p else None,
                    p["why"] if p else "not in the key",
                )
    for (frm, t), p in explicit.items():
        if (frm, t) not in seen:
            sc.add("edges", path, f"not {frm or '(main line)'} -> {t}", "pass", p.get("horror"))


def score_call_sites(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    calls = list(ef.calls) if ef else []
    used: set = set()
    for f in entry.get("call_sites", []):
        label = f"{f['verb']} {f['operand']} @{f['line']}"
        cands = [
            c for c in calls if _u(c.verb) == f["verb"] and _u(c.operand) == _u(f["operand"]) and id(c) not in used
        ]
        exact = [c for c in cands if c.line == f["line"]]
        c = (exact or cands or [None])[0]
        if c is None:
            sc.add("call_sites", path, label, "missing", f.get("horror"), "", f.get("depends_on"))
            continue
        used.add(id(c))
        pairs = [
            ("line", f["line"], c.line),
            ("form", f["form"], c.form),
            ("target", _u(f.get("target")), _u(c.target)),
        ]
        if f["verb"] in RESOLVED_VERBS:
            pairs.append(("resolves_to", f.get("resolves_to"), c.resolves_to))
        d = _diff(pairs)
        sc.add("call_sites", path, label, "fail" if d else "pass", f.get("horror"), d, f.get("depends_on"))
    explicit = _phantoms(entry, "call_sites")
    for c in calls:
        if id(c) in used:
            continue
        p = next((ph for ph in explicit if _u(ph["operand"]) == _u(c.operand) and ph["verb"] == _u(c.verb)), None)
        sc.add(
            "call_sites",
            path,
            f"{c.verb} {c.operand} @{c.line}",
            "phantom",
            p.get("horror") if p else None,
            p["why"] if p else "not in the key",
        )
    for p in explicit:
        if not any(_u(c.operand) == _u(p["operand"]) and _u(c.verb) == p["verb"] for c in calls):
            sc.add("call_sites", path, f"not {p['verb']} {p['operand']}", "pass", p.get("horror"))


def score_copies(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    raw = {r.upper() for r in eng.raw_imports.get(path, [])}
    deps = set(ef.copy_deps) if ef else set()
    want_raw, want_dep = set(), set()
    for f in entry.get("copies", []):
        label = f"{f['member']} @{f['line']}"
        want_raw.add(f["member"].upper())
        has_raw = f["member"].upper() in raw
        targets = ([f["resolves_to"]] if f["resolves_to"] else []) + f.get("alternatives", [])
        has_dep = not targets or any(t in deps for t in targets)
        want_dep.update(targets)
        if has_raw and has_dep:
            status, detail = "pass", ""
        elif not has_raw and (f["resolves_to"] is None or not has_dep):
            status, detail = "missing", "no raw import" + ("" if f["resolves_to"] is None else ", no import edge")
        else:
            status = "fail"
            detail = "no import edge to " + str(f["resolves_to"]) if has_raw else "import edge, but no raw import"
        sc.add("copies", path, label, status, f.get("horror"), detail, f.get("depends_on"))
    explicit = {p["member"].upper(): p for p in _phantoms(entry, "copies")}
    for r in sorted(raw - want_raw):
        p = explicit.get(r)
        sc.add(
            "copies",
            path,
            f"raw import {r}",
            "phantom",
            p.get("horror") if p else None,
            p["why"] if p else "not in the key",
        )
    for m, p in explicit.items():
        if m not in raw:
            sc.add("copies", path, f"not {m}", "pass", p.get("horror"))
    for d in sorted(deps - want_dep):
        # an edge to the wrong same-named member is that COPY's failure, attributed like it
        stem = d.rsplit("/", 1)[-1].rsplit(".", 1)[0].upper()
        f = next((x for x in entry.get("copies", []) if x["member"].upper() == stem), {})
        sc.add(
            "copies",
            path,
            f"import edge -> {d}",
            "phantom",
            f.get("horror"),
            "not in the key" + (f" (COPY {stem} resolves elsewhere)" if f else ""),
            f.get("depends_on"),
        )


def score_data_items(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    items = list(ef.data_items) if ef else []
    used: set = set()
    is_program = bool(entry.get("programs"))
    for f in entry.get("data_items", []):
        label = f"{f['level']:02d} {f['name']} @{f['line']}"
        cands = [i for i in items if _u(i.name) == _u(f["name"]) and id(i) not in used]
        exact = [i for i in cands if i.line == f["line"]]
        it = (exact or [i for i in cands if i.level == f["level"]] or [None])[0]
        if it is None:
            sc.add("data_items", path, label, "missing", f.get("horror"), "", f.get("depends_on"))
            continue
        used.add(id(it))
        pairs = [
            ("line", f["line"], it.line),
            ("level", f["level"], it.level),
            ("pic", _u(f.get("pic")), _u(it.pic)),
            ("usage", _u(f.get("usage")), _u(it.usage)),
            ("occurs", f.get("occurs"), it.occurs_max),
            ("redefines", _u(f.get("redefines")), _u(it.redefines)),
            ("value", _val(f.get("value")), _val(it.value)),
            (
                "copy_members",
                sorted(_u(c) for c in f.get("copy_members", [])),
                sorted(_u(c.strip()) for c in (it.copy_members or "").split(",") if c.strip()),
            ),
        ]
        if is_program:
            pairs.append(("section", f.get("section"), it.section))
        if "sign_separate" in f:
            pairs += [
                ("sign_separate", f["sign_separate"], bool(it.sign_separate)),
                ("sign_leading", f["sign_leading"], bool(it.sign_leading)),
            ]
        d = _diff(pairs)
        sc.add("data_items", path, label, "fail" if d else "pass", f.get("horror"), d, f.get("depends_on"))
    for it in items:
        if id(it) not in used:
            sc.add("data_items", path, f"{it.level:02d} {it.name} @{it.line}", "phantom", None, "not in the key")


def score_layouts(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    for f in entry.get("layouts", []):
        label = f"{f['record']} @{f['line']}"
        root = next(
            (r for r in (ef.records if ef else []) if _u(r.name) == _u(f["record"]) and r.line == f["line"]), None
        )
        if root is None or ef is None:
            sc.add("layouts", path, label, "missing", f.get("horror"), "no 01 entry recorded", f.get("depends_on"))
            continue
        lay = eng.ir.record_layout(ef, root)
        want = [x for x in f["fields"] if not x.get("overlay")]
        got = lay["fields"]
        problems = []
        if lay["bytes"] != f["bytes"]:
            problems.append(f"bytes: key {f['bytes']} engine {lay['bytes']}")
        for i, w in enumerate(want):
            g = got[i] if i < len(got) else None
            if g is None:
                problems.append(f"field {w['name']}: not in the engine layout")
                break
            d = _diff(
                [
                    ("name", _u(w["name"]), _u(g["name"])),
                    ("offset", w["offset"], g["offset"]),
                    ("bytes", w["bytes"], g["bytes"]),
                ]
            )
            if d:
                problems.append(f"field {i + 1} ({w['name']}): {d}")
                break
        if len(got) > len(want) and not problems:
            problems.append(f"engine has {len(got) - len(want)} extra field(s), first {got[len(want)]['name']}")
        sc.add(
            "layouts",
            path,
            label,
            "fail" if problems else "pass",
            f.get("horror"),
            "; ".join(problems),
            f.get("depends_on"),
        )
        overlays = [x for x in f["fields"] if x.get("overlay")]
        if overlays:
            sc.add(
                "layouts",
                path,
                f"{label} overlays",
                "unscored",
                f.get("horror"),
                f"{len(overlays)} REDEFINES field(s); record_layout skips overlays by design",
            )


def score_sql(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    stmts = list(ef.sql_statements) if ef else []
    used: set = set()
    for f in entry.get("sql_statements", []):
        label = f"{f['verb']} @{f['line']}"
        s = next((x for x in stmts if _u(x.verb) == f["verb"] and x.line == f["line"] and id(x) not in used), None)
        if s is None:
            s = next((x for x in stmts if _u(x.verb) == f["verb"] and id(x) not in used), None)
        if s is None:
            sc.add("sql_statements", path, label, "missing", f.get("horror"))
            continue
        used.add(id(s))
        d = _diff(
            [
                ("line", f["line"], s.line),
                ("table", _u(f.get("table")), _u(s.table)),
                ("access", f.get("access"), s.access),
            ]
        )
        sc.add("sql_statements", path, label, "fail" if d else "pass", f.get("horror"), d)
        if f.get("procedure"):
            sc.add(
                "sql_statements",
                path,
                f"{label} procedure {f['procedure']}",
                "unscored",
                f.get("horror"),
                "sql_statement_data has no procedure-name column (#4304 optional criterion)",
            )
    for s in stmts:
        if id(s) not in used:
            sc.add("sql_statements", path, f"{s.verb} @{s.line}", "phantom", None, "not in the key")
    tables = list(ef.sql_tables) if ef else []
    for f in entry.get("sql_tables", []):
        t = next((x for x in tables if _u(x.name) == _u(f["table"])), None)
        if t is None:
            sc.add("sql_tables", path, f["table"], "missing", f.get("horror"))
            continue
        problems = [_diff([("line", f["line"], t.line), ("columns", len(f["columns"]), len(t.columns))])]
        for kc, ec in zip(f["columns"], t.columns, strict=False):  # reason: length may differ
            problems.append(
                _diff(
                    [
                        (f"{kc['name']}.name", kc["name"], ec.name),
                        (f"{kc['name']}.type", kc["type"], ec.sql_type),
                        (f"{kc['name']}.length", kc["length"], ec.length),
                        (f"{kc['name']}.scale", kc["scale"], ec.scale),
                        (f"{kc['name']}.nullable", kc["nullable"], bool(ec.nullable)),
                        (f"{kc['name']}.line", kc["line"], ec.line),
                    ]
                )
            )
        d = "; ".join(p for p in problems if p)
        sc.add("sql_tables", path, f["table"], "fail" if d else "pass", f.get("horror"), d)


def score_jcl(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    flow = list(ef.job_flow) if ef else []
    steps = [r for r in flow if _u(r.kind) == "STEP"]
    dds = [r for r in flow if _u(r.kind) == "DD"]
    used: set = set()
    for f in entry.get("jcl_steps", []):
        label = f"{f['step']} @{f['line']}"
        s = next((r for r in steps if _u(r.step_name) == f["step"] and id(r) not in used), None)
        if s is None:
            sc.add("jcl_steps", path, label, "missing", f.get("horror"))
            continue
        used.add(id(s))
        d = _diff(
            [
                ("line", f["line"], s.line),
                ("ordinal", f["ordinal"], s.step_ordinal),
                ("program", _u(f.get("program")), _u(s.program)),
                ("proc", _u(f.get("exec_proc")), _u(s.proc)),
                ("cond", f.get("cond"), s.cond),
                ("in_proc", _u(f.get("proc")), _u(s.in_proc)),
            ]
        )
        sc.add("jcl_steps", path, label, "fail" if d else "pass", f.get("horror"), d)
    for s in steps:
        if id(s) not in used:
            sc.add("jcl_steps", path, f"{s.step_name} @{s.line}", "phantom", None, "not in the key")
    for f in entry.get("jcl_dds", []):
        label = f"{f['step']}.{f['dd']} @{f['line']}"
        if f.get("sysout"):
            sc.add(
                "jcl_dds",
                path,
                label,
                "unscored",
                f.get("horror"),
                f"SYSOUT={f['sysout']}: job_flow_data records only DDs that name a DSN (core/job_flow.py)",
            )
            continue
        r = next(
            (x for x in dds if _u(x.step_name) == f["step"] and _u(x.dd_name) == f["dd"] and id(x) not in used), None
        )
        if r is None:
            sc.add(
                "jcl_dds", path, label, "missing", f.get("horror"), f"SYSOUT={f['sysout']}" if f.get("sysout") else ""
            )
            continue
        used.add(id(r))
        d = _diff(
            [
                ("line", f["line"], r.line),
                ("dsn", _u(f.get("dsn")), _u(r.dsn)),
                ("generation", f.get("generation"), r.generation),
                ("disp", f.get("disp"), r.disp),
                ("disp_normal", f.get("disp_normal"), r.disp_normal),
            ]
        )
        sc.add("jcl_dds", path, label, "fail" if d else "pass", f.get("horror"), d)
    for r in dds:
        if id(r) not in used:
            sc.add("jcl_dds", path, f"{r.step_name}.{r.dd_name} @{r.line}", "phantom", None, "not in the key")


def score_cics(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    fields = list(ef.screen_fields) if ef else []
    used: set = set()
    for f in entry.get("screen_fields", []):
        label = f"{f['kind']} {f.get('name') or '(unnamed)'} @{f['line']}"
        s = next((x for x in fields if _u(x.kind) == _u(f["kind"]) and x.line == f["line"]), None)
        if s is None:
            sc.add("screen_fields", path, label, "missing", f.get("horror"))
            continue
        used.add(id(s))
        pairs = [("name", _u(f.get("name")), _u(s.name))]
        if f["kind"] == "field":
            pairs += [
                ("pos_line", f["pos_line"], s.pos_line),
                ("pos_column", f["pos_column"], s.pos_column),
                ("length", f["length"], s.length),
                ("attrb", _u(f["attrb"]), _u(s.attrb)),
                ("picin", f.get("picin"), s.picin),
                ("initial", f.get("initial"), _val(s.initial)),
            ]
        d = _diff(pairs)
        sc.add("screen_fields", path, label, "fail" if d else "pass", f.get("horror"), d)
    for s in fields:
        if id(s) not in used:
            sc.add("screen_fields", path, f"{s.kind} {s.name} @{s.line}", "phantom", None, "not in the key")
    res = list(ef.csd_resources) if ef else []
    for f in entry.get("csd_resources", []):
        label = f"{f['type']} {f['name']}"
        r = next((x for x in res if _u(x.resource_type) == f["type"] and _u(x.name) == f["name"]), None)
        if r is None:
            sc.add("csd_resources", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        pairs = [("group", f["group"], _u(r.group)), ("line", f["line"], r.line)]
        if f.get("program"):
            pairs.append(("program", f["program"], _u(r.program)))
        if f.get("dsname"):
            pairs.append(("dsname", f["dsname"], _u(r.dsname)))
        d = _diff(pairs)
        sc.add("csd_resources", path, label, "fail" if d else "pass", f.get("horror"), d)
    for r in res:
        if id(r) not in used:
            sc.add("csd_resources", path, f"{r.resource_type} {r.name}", "phantom", None, "not in the key")
    txs = list(ef.transactions) if ef else []
    for f in entry.get("transactions", []):
        t = next((x for x in txs if _u(x.transid) == f["transid"]), None)
        if t is None:
            sc.add("transactions", path, f["transid"], "missing", f.get("horror"))
            continue
        used.add(id(t))
        d = _diff(
            [
                ("program", f["program"], _u(t.program)),
                ("line", f["line"], t.line),
                ("resolves_to", f.get("resolves_to"), t.resolves_to),
            ]
        )
        sc.add("transactions", path, f["transid"], "fail" if d else "pass", f.get("horror"), d)
    for t in txs:
        if id(t) not in used:
            sc.add("transactions", path, t.transid, "phantom", None, "not in the key")


def score_cics_resources(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    rows = list(ef.cics_resources) if ef else []
    used: set = set()
    for f in entry.get("cics_resources", []):
        label = f"{f['verb']} {f['kind']} {f['name']} @{f['line']}"
        r = next(
            (
                x
                for x in rows
                if _u(x.verb) == f["verb"] and _u(x.kind) == f["kind"] and x.line == f["line"] and id(x) not in used
            ),
            None,
        )
        if r is None:
            sc.add("cics_resources", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        d = _diff(
            [
                ("name", _u(f["name"]), _u(r.name)),
                ("qualifier", _u(f.get("qualifier")), _u(r.qualifier)),
                ("record", _u(f.get("record")), _u(r.record)),
                ("access", f["access"], r.access),
            ]
        )
        sc.add("cics_resources", path, label, "fail" if d else "pass", f.get("horror"), d)
    for r in rows:
        if id(r) not in used:
            sc.add("cics_resources", path, f"{r.verb} {r.kind} {r.name} @{r.line}", "phantom", None, "not in the key")


def score_jcl_datasets(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """A JCL member's dataset references, against file_data.raw_imports: a GDG reference may
    be recorded as its base or with its relative generation, never anything else."""
    if entry["language"] != "jcl":
        return
    raw = {r.upper() for r in eng.raw_imports.get(path, [])}
    accepted: set = set()
    for f in entry.get("jcl_datasets", []):
        forms = {f["dsn"].upper()} | ({f"{f['dsn']}({f['generation']})".upper()} if f.get("generation") else set())
        accepted |= forms
        label = f"{f['step']}.{f['dd']} {f['dsn']}" + (f"({f['generation']})" if f.get("generation") else "")
        ok = bool(forms & raw)
        sc.add(
            "jcl_datasets",
            path,
            label,
            "pass" if ok else "missing",
            f.get("horror"),
            "" if ok else f"none of {sorted(forms)} in raw_imports",
            f.get("depends_on"),
        )
    horrors = sorted({f["horror"] for f in entry.get("jcl_datasets", []) if f.get("horror")})
    for r in sorted(raw - accepted):
        h = next((f.get("horror") for f in entry.get("jcl_datasets", []) if r.startswith(f["dsn"].upper())), None)
        sc.add(
            "jcl_datasets",
            path,
            f"raw import {r}",
            "phantom",
            h or (horrors[0] if horrors and "(" in r else None),
            "not a dataset reference the member makes",
        )


def score_file_control(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    rows = list(ef.file_control) if ef else []
    used: set = set()
    for f in entry.get("file_control", []):
        label = f"SELECT {f['select']} @{f['line']}"
        r = next((x for x in rows if _u(x.select_name) == f["select"] and id(x) not in used), None)
        if r is None:
            sc.add("file_control", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        d = _diff(
            [
                ("assign", _u(f["assign"]), _u(r.assign)),
                ("organization", _u(f["organization"]), _u(r.organization)),
                ("access_mode", _u(f.get("access_mode")), _u(r.access_mode)),
                ("record_key", _u(f.get("record_key")), _u(r.record_key)),
                ("file_status", _u(f["file_status"]), _u(r.file_status)),
                ("fd_copies", sorted(_u(c) for c in f["fd_copies"]), sorted(_u(c) for c in (r.fd_copies or []))),
                ("line", f["line"], r.line),
            ]
        )
        sc.add("file_control", path, label, "fail" if d else "pass", f.get("horror"), d)
    for r in rows:
        if id(r) not in used:
            sc.add("file_control", path, f"SELECT {r.select_name} @{r.line}", "phantom", None, "not in the key")


def score_entry_points(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    rows = list(ef.entry_points) if ef else []
    used: set = set()
    for f in entry.get("entry_points", []):
        label = f"{f['kind']} {f['program']} @{f['line']}"
        r = next((x for x in rows if _u(x.kind) == f["kind"] and x.line == f["line"] and id(x) not in used), None)
        if r is None:
            sc.add("entry_points", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        d = _diff([("params", [_u(p) for p in f["params"]], [_u(p) for p in r.parameters])])
        sc.add("entry_points", path, label, "fail" if d else "pass", f.get("horror"), d)
    for r in rows:
        if id(r) not in used:
            sc.add("entry_points", path, f"{r.kind} {r.entry_name} @{r.line}", "phantom", None, "not in the key")


def _norm(v: Any) -> Any:
    return " ".join(v.split()).upper() if isinstance(v, str) else v


def score_data_moves(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """data_move_data: one row per source -> target pair of a data-moving statement."""
    ef = eng.files.get(path)
    rows = list(ef.data_moves) if ef else []
    used: set = set()
    for f in entry.get("data_moves", []):
        label = f"{f['verb']} {f['source']} -> {f['target']} @{f['line']}"
        r = next(
            (
                x
                for x in rows
                if id(x) not in used
                and _u(x.verb) == f["verb"]
                and x.line == f["line"]
                and _norm(x.target) == _norm(f["target"])
                and _norm(x.source) == _norm(f["source"])
            ),
            None,
        )
        if r is None:
            sc.add("data_moves", path, label, "missing", f.get("horror"), "", f.get("depends_on"))
            continue
        used.add(id(r))
        d = _diff(
            [
                ("source_kind", f["source_kind"], r.source_kind),
                ("corresponding", f["corresponding"], bool(r.corresponding)),
                ("source_refmod", f["source_refmod"], bool(r.source_refmod)),
                ("target_refmod", f["target_refmod"], bool(r.target_refmod)),
                ("source_refmod_text", f["source_refmod_text"], r.source_refmod_text),
            ]
        )
        sc.add("data_moves", path, label, "fail" if d else "pass", f.get("horror"), d, f.get("depends_on"))
    explicit = {_norm(p["target"]): p for p in _phantoms(entry, "data_moves")}
    seen = set()
    for r in rows:
        if id(r) not in used:
            p = explicit.get(_norm(r.target))
            if p:
                seen.add(_norm(r.target))
            sc.add(
                "data_moves",
                path,
                f"{r.verb} {r.source} -> {r.target} @{r.line}",
                "phantom",
                p.get("horror") if p else None,
                p["why"] if p else "not in the key",
            )
    for t, p in explicit.items():
        if t not in seen:
            sc.add("data_moves", path, f"not -> {p['target']}", "pass", p.get("horror"))


def score_file_edges(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    got = set(eng.file_edges.get(path, set()))
    for f in entry.get("file_edges", []):
        label = f"{f['kind']} -> {f['target']}"
        ok = (f["target"], f["kind"]) in got
        got.discard((f["target"], f["kind"]))
        sc.add("file_edges", path, label, "pass" if ok else "missing", f.get("horror"), "", f.get("depends_on"))
    explicit = {(p["target"], p["kind"]): p for p in _phantoms(entry, "file_edges")}
    for dst, kind in sorted(got):
        p = explicit.get((dst, kind))
        sc.add(
            "file_edges",
            path,
            f"{kind} -> {dst}",
            "phantom",
            p.get("horror") if p else None,
            p["why"] if p else "not in the key",
        )


def score_copy_collisions(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """#4265: the key's collisions against the scan's `copy_member_collisions` report."""
    if eng.collisions is None:
        for f in entry.get("copy_collisions", []):
            sc.add(
                "copy_collisions",
                path,
                f"{f['member']} @{f['line']}",
                "unscored",
                f.get("horror"),
                "no collision report beside the DB",
                f.get("depends_on"),
            )
        return
    reported: dict[str, dict[str, Any]] = {}
    for r in eng.collisions:
        if str(r.get("importer", "")).replace("\\", "/") == path:
            reported.setdefault(str(r.get("member", "")).upper(), r)
    for f in entry.get("copy_collisions", []):
        label = f"{f['member']} @{f['line']}"
        r = reported.pop(f["member"].upper(), None)
        if r is None:
            sc.add("copy_collisions", path, label, "missing", f.get("horror"), "not reported", f.get("depends_on"))
            continue
        shadowed = sorted(str(x.get("library", "")).upper() for x in r.get("shadowed") or [])
        d = _diff(
            [
                ("resolved", f["resolves_to"], r.get("resolved")),
                ("library", f["library"].upper(), str(r.get("library", "")).upper()),
                ("shadowed", sorted(x["library"].upper() for x in f["shadowed"]), shadowed),
            ]
        )
        sc.add("copy_collisions", path, label, "fail" if d else "pass", f.get("horror"), d, f.get("depends_on"))
    for member in sorted(reported):
        sc.add("copy_collisions", path, f"{member} (reported)", "phantom", None, "not a collision in the key")


def _stem(p: str) -> str:
    return p.rsplit("/", 1)[-1].rsplit(".", 1)[0].upper()


def score_gaps(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """A gap: a reference the estate cannot answer. It passes when the scan resolves it to nothing:
    no edge from this member to a member of that name (for a COPY, an import edge; a program found for a missing copybook, a
    stale copy for a missing program)."""
    for f in entry.get("gaps", []):
        # a COPY gap is about the COPY: the member's own CALL of a program of that name is a call edge, not a hit
        kinds = ("import",) if f["kind"] == "copy" else None
        hits = sorted(
            {
                dst
                for dst, kind in eng.out_edges.get(path, set())
                if _stem(dst) == f["name"].upper() and (kinds is None or kind in kinds)
            }
        )
        sc.add(
            "gaps",
            path,
            f"{f['kind']} {f['name']} @{f['line']}",
            "fail" if hits else "pass",
            f.get("horror"),
            f"resolved to {', '.join(hits)}" if hits else "",
            f.get("depends_on"),
        )


def score_dead(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """Dead code: a paragraph passes when the engine marks its unit unused (usage_status 1); a program
    or copybook passes when no edge of any kind points at its member."""
    for f in entry.get("dead", []):
        label = f"{f['kind']} {f['name']} @{f['line']}"
        if f["kind"] == "paragraph":
            u = next((x for x in eng.units.get(path, []) if _u(x["name"]) == _u(f["name"])), None)
            if u is None:
                sc.add("dead", path, label, "missing", f.get("horror"), "no such unit", f.get("depends_on"))
                continue
            ok = u.get("usage") == 1
            sc.add(
                "dead",
                path,
                label,
                "pass" if ok else "fail",
                f.get("horror"),
                "" if ok else f"usage_status {u.get('usage')}",
                f.get("depends_on"),
            )
            continue
        callers = sorted(f"{src} ({kind})" for src, kind in eng.in_edges.get(path, set()))
        sc.add(
            "dead",
            path,
            label,
            "fail" if callers else "pass",
            f.get("horror"),
            f"reached from {', '.join(callers)}" if callers else "",
            f.get("depends_on"),
        )


SOURCE_LANGUAGES = ("cobol", "pli")
COBOL_ONLY = (score_programs, score_units, score_edges, score_copies, score_data_items, score_layouts, score_data_moves)
SCORERS = (
    score_programs,
    score_units,
    score_edges,
    score_call_sites,
    score_copies,
    score_data_items,
    score_layouts,
    score_sql,
    score_jcl,
    score_cics,
    score_cics_resources,
    score_jcl_datasets,
    score_file_control,
    score_entry_points,
    score_file_edges,
    score_data_moves,
    score_copy_collisions,
    score_gaps,
    score_dead,
)


def engine_commit() -> str:
    """This checkout's HEAD (the scan sets no commit of its own), `+dirty` with engine edits."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],  # noqa: S603, S607 -- fixed argv
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

    head = git("rev-parse", "--short=12", "HEAD") or "unknown"
    return head + ("+dirty" if git("status", "--porcelain", "--", "gitgalaxy") else "")


def score(crucible: Path, db: Path) -> Score:
    manifest, key = load_key(crucible)
    eng = Engine(db)
    sc = Score(engine_commit=engine_commit(), key_generator=manifest["generator"])
    if not eng.files:
        raise ValueError(
            f"{db} records no files: was the estate scanned (an untracked tree in a git checkout scans as empty)?"
        )
    for path in sorted(key):
        entry = key[path]
        if path in eng.excluded:
            reason = eng.excluded[path]
            status = "unscored" if entry.get("generated_from") else "missing"
            for ch in CHANNELS:
                for f in entry.get(ch, []):
                    sc.add(
                        ch,
                        path,
                        json.dumps({k: v for k, v in f.items() if k in ("name", "member", "line")}),
                        status,
                        f.get("horror"),
                        f"excluded by the scan: {reason}",
                    )
            continue
        for fn in SCORERS:
            if entry["language"] not in SOURCE_LANGUAGES and fn in COBOL_ONLY:
                continue  # the engine's own model of JCL / BMS / CSD units is not what these channels key
            fn(sc, path, entry, eng)
    for path in sorted(set(eng.files) - set(key)):
        sc.add("programs", path, path, "phantom", None, "a file the estate does not have")
    return sc


# ----------------------------------------------------------------------------- reports


def horror_verdicts(sc: Score, crucible: Path) -> list[dict[str, Any]]:
    catalog = sorted((crucible / "horrors").glob("H-*.json"))
    out = []
    for p in catalog:
        h = json.loads(p.read_text(encoding="utf-8"))
        checks = [c for c in sc.checks if c.horror == h["id"]]
        counts = Counter(c.status for c in checks)
        # a failing check that depends on another horror is that horror's cascade, not this one's failure
        bad = [c for c in checks if c.status in ("fail", "missing", "phantom") and not c.depends_on]
        cascade = [c for c in sc.checks if h["id"] in c.depends_on and c.status in ("fail", "missing", "phantom")]
        out.append(
            {
                "id": h["id"],
                "issue": h.get("issue"),
                # a phase-3 realism horror imitates real estates rather than a filed defect
                "source": "realism" if h.get("realism") else (f"#{h['issue']}" if h.get("issue") else ""),
                "title": h["title"],
                "verdict": "FAIL" if bad else "PASS",
                "counts": dict(counts),
                "failing": [c.__dict__ for c in bad],
                "cascade": [c.__dict__ for c in cascade],
            }
        )
    return out


def channel_table(sc: Score) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {ch: dict.fromkeys(STATUSES, 0) for ch in CHANNELS}
    for c in sc.checks:
        table[c.channel][c.status] += 1
    return table


def markdown(sc: Score, crucible: Path) -> str:
    rows = ["| channel | pass | fail | missing | phantom | unscored |", "|---|--:|--:|--:|--:|--:|"]
    tot = dict.fromkeys(STATUSES, 0)
    for ch, cnt in channel_table(sc).items():
        rows.append(f"| {ch} | " + " | ".join(str(cnt[s]) for s in STATUSES) + " |")
        for s in STATUSES:
            tot[s] += cnt[s]
    rows.append("| **total** | " + " | ".join(f"**{tot[s]}**" for s in STATUSES) + " |")
    out = [
        f"Engine `{sc.engine_commit}` vs estate-crucible key (generator {sc.key_generator}).",
        "",
        "**Per channel**",
        "",
        *rows,
        "",
        "**Per horror**",
        "",
        "| horror | issue | verdict | checks | not passing |",
        "|---|---|---|---|---|",
    ]
    for h in horror_verdicts(sc, crucible):
        n = sum(h["counts"].values())
        why = "; ".join(f"{c['status']} {c['channel']} `{c['fact']}`" for c in h["failing"][:4])
        more = f" (+{len(h['failing']) - 4} more)" if len(h["failing"]) > 4 else ""
        casc = f"; cascade: {len(h['cascade'])} check(s) elsewhere" if h["cascade"] else ""
        out.append(f"| {h['id']} | {h['source']} | {h['verdict']} | {n} | {why}{more}{casc} |")
    untagged = [
        c for c in sc.checks if c.horror is None and not c.depends_on and c.status in ("fail", "missing", "phantom")
    ]
    out += ["", f"**Outside the horrors** ({len(untagged)} not passing)", ""]
    for c in untagged:
        out.append(f"- {c.status} {c.channel} `{c.member}` `{c.fact}`" + (f": {c.detail}" if c.detail else ""))
    return "\n".join(out) + "\n"


def text(sc: Score, crucible: Path) -> str:
    lines = [
        f"estate-crucible scorecard: engine {sc.engine_commit}, key {sc.key_generator}",
        "",
        f"{'channel':<16}" + "".join(f"{s:>10}" for s in STATUSES),
    ]
    for ch, cnt in channel_table(sc).items():
        lines.append(f"{ch:<16}" + "".join(f"{cnt[s]:>10}" for s in STATUSES))
    lines.append("")
    for h in horror_verdicts(sc, crucible):
        lines.append(f"{h['id']} {h['source'] or '-'} {h['verdict']:<4} {h['title']}")
        for c in h["failing"]:
            lines.append(
                f"    {c['status']:<8} {c['channel']:<12} {c['member']} {c['fact']}"
                + (f"  [{c['detail']}]" if c["detail"] else "")
            )
        for c in h["cascade"]:
            lines.append(
                f"    cascade  {c['status']:<8} {c['channel']:<12} {c['member']} {c['fact']}"
                + (f"  [{c['detail']}]" if c["detail"] else "")
            )
    lines.append("")
    lines.append("outside the horrors:")
    for c in sc.checks:
        if c.horror is None and not c.depends_on and c.status in ("fail", "missing", "phantom"):
            lines.append(
                f"    {c.status:<8} {c.channel:<12} {c.member} {c.fact}" + (f"  [{c.detail}]" if c.detail else "")
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--crucible", type=Path, help=f"estate-crucible checkout (default ${PATH_ENV} or ../estate-crucible)"
    )
    ap.add_argument("--db", type=Path, help="score this master DB instead of scanning")
    ap.add_argument("--scan-dir", type=Path, help="where to write the scan (default: a temporary directory)")
    ap.add_argument("--json", type=Path, help="write every check here")
    ap.add_argument("--md", type=Path, help="write the markdown scorecard here")
    args = ap.parse_args(argv)
    crucible = crucible_path(args.crucible)
    if not (crucible / "key" / "manifest.json").is_file():
        print(f"no estate-crucible checkout at {crucible} (set {PATH_ENV} or pass --crucible)", file=sys.stderr)
        return 2
    msg = pin_mismatch(crucible)
    if msg:
        print(msg, file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="estate-scan-") as tmp:
        db = args.db or scan(crucible, args.scan_dir or Path(tmp))
        sc = score(crucible, db)
    print(text(sc, crucible), end="")
    if args.md:
        args.md.write_text(markdown(sc, crucible), encoding="utf-8")
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "engine_commit": sc.engine_commit,
                    "pinned_ref": PINNED_REF,
                    "key_generator": sc.key_generator,
                    "channels": channel_table(sc),
                    "horrors": horror_verdicts(sc, crucible),
                    "checks": [c.__dict__ for c in sc.checks],
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
