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
  call_sites      call_site_data (CALL, LINK, XCTL, RETURN TRANSID, EXEC PGM; a runner step's RUN PROGRAM row is read as the key's `RUN PROGRAM`)
  copies          file_data.raw_imports + edge_data import edges
  data_items      record_data entries
  layouts         GalaxyIR.record_layout of every 01 a program writes: bytes and every
                  elementary field's offset / length (REDEFINES overlays: unscored, the
                  layout reader skips them by design)
  dli_calls       CALL 'CBLTDLI' rows (dli_call_data) by line: pcb, io_area and ssas as written; the function code is the
                  RESOLVED one (GalaxyIR.ims_calls: the first operand's VALUE), since the table keeps only the operand
  ims_gen         DBD and SEGM macro rows (ims_gen_data) by (kind, name): parent and bytes; every other kind is
                  unkeyed until a later estate-crucible slice
  jcl_utility_cards  the control statements of an in-stream DD (job_flow_data INSTREAM rows); a DD outside
                  SYSIN / SYMNAMES / SORTCNTL / DFSPARM / TOOLIN / xxxxCNTL / SYSTSIN / STDPARM / STDIN / STDENV (SYSUT1, SORTIN) is unscored: the engine keeps no body
  jcl_steps       STEP rows (+ job: the nearest preceding JOB row, none inside a PROC); JOB RESTART= (+ checkid), RD=, PARM.procstep=, COND.procstep= are unscored (no engine field)
  jcl_dds         DD rows (an override DD `//PROCSTEP.DD` matches the row named after its proc step);
                  SYSOUT (+ class) and DUMMY DDs are their own row kinds (#7065); a sysout DD's output_refs (OUTPUT=)
                  are scored from the SYSOUT row's output_refs column
                  (+ symbolic: a single leading `&`; job; `added` against the proc definition's DD rows, unscored when the proc is not in the scan)
  jcl_outputs     OUTPUT JCL statements (name, step, line, keyword names) against job_flow's OUTPUT rows (#7065)
  sql_statements  (access: the engine's insert / delete / merge score as the key's `update`), sql_tables, jcl_steps, jcl_dds, screen_fields, csd_resources, transactions
  cics_resources  cics_resource_data (MAP / FILE / QUEUE commands; + ridfld, addressing RBA / RRN / XRBA when the key states them)
  jcl_datasets    a JCL member's DSN references in file_data.raw_imports (a GDG reference as
                  its base or with its relative generation)
  file_control    file_control_data SELECTs (+ relative_key, alternate_keys with the DUPLICATES flag, when the key states them);  entry_points  entry_point_data
  file_edges      edge_data kinds 'call' (CALL / LINK / XCTL) and 'exec' (EXEC PGM; a key RUN PROGRAM call site implies its exec edge)
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
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / "tests"
for p in (str(REPO_ROOT), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _estate_crucible_pin import PATH_ENV, PINNED_REF, pin_mismatch  # noqa: E402

from gitgalaxy.core.job_flow import is_control_dd  # noqa: E402

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
    "jcl_outputs",
    "jcl_utility_cards",
    "dli_calls",
    "ims_gen",
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
RESOLVED_VERBS = ("CALL", "LINK", "XCTL", "EXEC PGM", "RUN PROGRAM")
# The engine records a program a runner step runs as an `EXEC PGM` row of form `runner` whose operand is
# "<RUNNER> <VIA>" and whose target is the program (#3710). The key (SPEC.md `call_sites`) keys the RUN PROGRAM
# subcommand as verb `RUN PROGRAM`, operand the program: the same fact, so it is read in the key's shape.
_KEYED_RUNNER_VIAS = ("RUN PROGRAM",)


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
            # #7170: a program's main line is a function_data row with def_shape 'main_line'
            shape_col = (
                "def_shape"
                if any(r[1] == "def_shape" for r in conn.execute("PRAGMA table_info(function_data)"))
                else "NULL"
            )
            for fid, name, start, loc, calls, transfers, usage, shape in conn.execute(
                "SELECT file_id, func_name, start_line, loc, calls_out_to, transfers_to, usage_status, "  # noqa: S608
                f"{shape_col} FROM function_data"
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
                            "main_line": shape == "main_line",
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
            # job_flow_data's SYSOUT class (#7065): EngineJobFlow carries no such field, so (path, line) -> class here
            self.sysout: dict[tuple[str, int], str] = {}
            if any(r[1] == "sysout" for r in conn.execute("PRAGMA table_info(job_flow_data)")):
                for fid, line, cls in conn.execute(
                    "SELECT file_id, line_number, sysout FROM job_flow_data WHERE sysout IS NOT NULL"
                ):
                    if fid in ids:
                        self.sysout[(ids[fid], int(line or 0))] = cls
            # job_flow_data's restart / rd / PARM.step / COND.step columns (#7065): (path, line) -> {field: value}
            self.jcl_extra: dict[tuple[str, int], dict[str, Any]] = {}
            have = {r[1] for r in conn.execute("PRAGMA table_info(job_flow_data)")}
            cols = [c for c in _JCL_EXTRA_FIELDS if c in have]
            if cols:
                for fid, line, *vals in conn.execute(
                    f"SELECT file_id, line_number, {', '.join(cols)} FROM job_flow_data"  # noqa: S608 -- cols are literals
                ):
                    got = {
                        c: (json.loads(v) if c in _JCL_JSON_FIELDS else v) for c, v in zip(cols, vals, strict=True) if v
                    }
                    if got and fid in ids:
                        self.jcl_extra[(ids[fid], int(line or 0))] = got
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
    a function_data main-line unit (#7170) or synthetic_unit_data row, or a unit at its first line."""
    if unit is not None:
        hits = [u for u in eng.units.get(path, []) if u["name"].upper() == unit.upper() and not u.get("main_line")]
        if start is not None and hits:
            return min(hits, key=lambda u: abs(u["start"] - start))
        return hits[0] if hits else None
    cands = eng.synthetic.get(path, []) + eng.units.get(path, [])
    if start is None:
        mains = [u for u in eng.units.get(path, []) if u.get("main_line")] + eng.synthetic.get(path, [])
        return mains[0] if mains else None
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
        # #7170: a main line the key does not list is not a phantom paragraph (keys list paragraphs/sections)
        if id(u) not in keyed and not u.get("main_line"):
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


def _as_keyed_call(c: Any) -> Any:
    """A runner row ("IKJEFT01 RUN PROGRAM" -> BDLDDB2) as the key's `RUN PROGRAM BDLDDB2` call site."""
    if _u(c.verb) != "EXEC PGM" or _u(getattr(c, "form", None)) != "RUNNER" or not c.target:
        return c
    via = next((v for v in _KEYED_RUNNER_VIAS if _u(c.operand).endswith(" " + v)), None)
    if via is None:
        return c
    return SimpleNamespace(
        verb=via, form="literal", operand=c.target, target=c.target, resolves_to=c.resolves_to, line=c.line
    )


def score_call_sites(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    calls = [_as_keyed_call(c) for c in ef.calls] if ef else []
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


# The key states a statement's access as read / update; the engine keeps the verb's own word. INSERT, DELETE and MERGE
# change data like UPDATE does (IBM Db2 SQL Reference), so they score as the key's `update`; LOCK and the rest stay.
_SQL_ACCESS_KEY_WORD = {"insert": "update", "delete": "update", "merge": "update"}


def _sql_access(access: Any) -> Any:
    return _SQL_ACCESS_KEY_WORD.get(str(access).lower(), access) if access else access


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
                ("access", f.get("access"), _sql_access(s.access)),
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


# job_flow_data columns EngineJobFlow carries no field for (#7065): read by (path, line) from the DB.
_JCL_EXTRA_FIELDS = (
    "restart",
    "restart_checkid",
    "rd",
    "parm_overrides",
    "cond_overrides",
    "output_params",
    "output_refs",
)
_JCL_JSON_FIELDS = ("parm_overrides", "cond_overrides", "output_params", "output_refs")


# Optional key fields on a jcl_steps entry that job_flow_data has no field for (the key states them, the DB cannot
# answer): each is reported `unscored` with its reason, never silently dropped (gitgalaxy#7065, H-0073, H-0075).
_STEP_FIELDS_WITHOUT_ENGINE_ROW = ()


# The in-stream DDs job_flow_data keeps an INSTREAM row for (core/job_flow.py `_CONTROL_DDS`). Any other `DD *` has no
# row: SYSUT1 / SORTIN data bodies are not kept (#7065).


def _instream_not_kept(dd: Any) -> str | None:
    """Why job_flow_data has no INSTREAM row for an in-stream DD named `dd`, or None when it keeps one."""
    name = _u(dd)
    if is_control_dd(name):
        return None
    return f"{name}: job_flow_data keeps an in-stream body only for SYSIN, SYMNAMES, SORTCNTL, DFSPARM, TOOLIN, xxxxCNTL, SYSTSIN, STDPARM, STDIN and STDENV (core/job_flow.py)"


# Key fields the scorer has no check for yet (gitgalaxy#7065, found by tests/estate_crucible/test_estate_crucible_fields_accounted.py):
# the key states them, the scorecard neither passes nor fails them and does not list them as `unscored`. Naming them here
# keeps the gap visible; a field leaves this table when a scorer compares it or reports it `unscored` with a reason.
KEY_FIELDS_NOT_COMPARED: tuple[tuple[str, str], ...] = (
    ("member", "compile"),
    ("member", "numbered"),
    ("member", "lines"),
    ("data_moves", "target_refmod_text"),
    ("units", "span_end"),
    ("edges", "thru"),
    ("layouts", "unresolved"),
    ("gaps", "lookalikes"),
    ("csd_resources", "trigger_level"),
    ("data_items", "implicit_filler"),
    ("screen_fields", "map"),
    ("screen_fields", "mapset"),
    ("copies", "replacing"),
    ("copy_libraries", "path"),
    ("copy_libraries", "encoding"),
    ("copy_libraries", "storage"),
    ("member", "file"),
)


def _compact(v: Any) -> str:
    """A key value as one short token for a check label (a list of override dicts becomes `RPT020:QUARTERLY`)."""
    if isinstance(v, list):
        return ",".join(
            f"{o['name']}={o['value']}"
            if "name" in o
            else f"{o.get('step')}:{o.get('parm', o.get('cond'))}"
            if isinstance(o, dict)
            else str(o)
            for o in v
        )
    return str(v)


def _jobs(flow: list[Any]) -> dict[int, str | None]:
    """id(row) -> the JOB statement a row belongs to: the last JOB row before it, None inside a PROC (the key's `job`)."""
    out: dict[int, str | None] = {}
    job: str | None = None
    for r in flow:
        if _u(r.kind) == "JOB":
            job = _u(r.name)
        out[id(r)] = None if r.in_proc else job
    return out


def _is_symbolic(dsn: str | None) -> bool:
    """A DSN that begins with a single `&` is a symbolic parameter; `&&` is a temporary dataset."""
    return bool(dsn) and dsn.startswith("&") and not dsn.startswith("&&")  # type: ignore[union-attr]


def _score_added(sc: Score, path: str, label: str, f: dict[str, Any], row: Any, steps: list[Any], eng: Engine) -> None:
    """The key's `added` (a DD on a proc step the procedure does not define) against the proc definition's DD rows.

    An override names a DD the proc step already has: a DD row with that step and DD name inside the procedure. The proc
    may sit in another member, so every scanned file is searched; when no scanned file holds the procedure the engine
    cannot tell, and the field stays `unscored` (gitgalaxy#7065).
    """
    exec_step = next((x for x in steps if _u(x.step_name) == _u(f["step"])), None)
    proc = _u(exec_step.proc) if exec_step is not None else ""
    rows = [r for file in eng.files.values() for r in (getattr(file, "job_flow", None) or [])]
    if not proc or not any(_u(r.kind) == "STEP" and _u(r.in_proc) == proc for r in rows):
        why = f"procedure {proc or '?'} is not in the scan, so job_flow_data cannot tell an added DD from an override"
        sc.add("jcl_dds", path, f"{label} added", "unscored", f.get("horror"), why)
        return
    owner, dd = _u(f.get("override_of")), _u(f.get("dd"))
    defined = any(
        _u(r.kind) in ("DD", "SYSOUT", "DUMMY")
        and r is not row
        and _u(r.in_proc) == proc
        and _u(r.step_name) == owner
        and _u(r.dd_name) == dd
        for r in rows
    )
    d = _diff([("added", bool(f["added"]), not defined)])
    sc.add("jcl_dds", path, f"{label} added", "fail" if d else "pass", f.get("horror"), d)


def score_jcl(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    ef = eng.files.get(path)
    flow = list(ef.job_flow) if ef else []
    steps = [r for r in flow if _u(r.kind) == "STEP"]
    dds = [r for r in flow if _u(r.kind) == "DD"]
    used: set = set()
    jobs = _jobs(flow)
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
        opt = [("parm", f["parm"], s.parm)] if "parm" in f else []
        if "job" in f:
            opt.append(("job", _u(f["job"]), jobs[id(s)]))
        if "if_cond" in f:
            cond, branch = _if_branch(s.if_cond)
            opt += [("if_cond", f["if_cond"], cond), ("branch", f.get("branch"), branch)]
        # #7065: restart / checkid are the JOB statement's (the key repeats them on every step of the job); rd and the
        # PARM.step / COND.step overrides are the EXEC's.
        extra = getattr(eng, "jcl_extra", {})
        mine = extra.get((path, s.line), {})
        job_row = next((r for r in flow if _u(r.kind) == "JOB" and _u(r.name) == jobs[id(s)]), None)
        theirs = extra.get((path, job_row.line), {}) if job_row is not None else {}
        for k in ("restart", "restart_checkid"):
            if f.get(k):
                opt.append((k, _u(f[k]), _u(theirs.get(k))))
        if f.get("rd"):
            opt.append(("rd", _u(f["rd"]), _u(mine.get("rd"))))
        for k, sub in (("parm_overrides", "parm"), ("cond_overrides", "cond")):
            if f.get(k):
                opt.append(
                    (k, [(o["step"].upper(), o[sub]) for o in f[k]], [(o["step"], o[sub]) for o in mine.get(k, [])])
                )
        # #7065: the SET statements between the previous EXEC (or the JOB) and this one, the INCLUDEs between this EXEC and
        # the next; job_flow keeps both as their own rows, in coded order.
        at = next(i for i, r in enumerate(flow) if r is s)
        before = next((i for i in range(at - 1, -1, -1) if _u(flow[i].kind) in ("STEP", "JOB")), -1)
        after = next((i for i in range(at + 1, len(flow)) if _u(flow[i].kind) in ("STEP", "JOB")), len(flow))
        if f.get("set_symbols"):
            got = [(_u(r.name), r.parm) for r in flow[before + 1 : at] if _u(r.kind) == "SET"]
            opt.append(("set_symbols", [(_u(x["name"]), x["value"]) for x in f["set_symbols"]], got))
        if f.get("includes"):
            got = [_u(r.name) for r in flow[at + 1 : after] if _u(r.kind) == "INCLUDE"]
            opt.append(("includes", [_u(x) for x in f["includes"]], got))
        d = "; ".join(x for x in (d, _diff(opt)) if x)
        sc.add("jcl_steps", path, label, "fail" if d else "pass", f.get("horror"), d)
        for key, why in _STEP_FIELDS_WITHOUT_ENGINE_ROW:
            if f.get(key):
                sc.add("jcl_steps", path, f"{label} {key}={_compact(f[key])}", "unscored", f.get("horror"), why)
    for s in steps:
        if id(s) not in used:
            sc.add("jcl_steps", path, f"{s.step_name} @{s.line}", "phantom", None, "not in the key")
    ins = [r for r in flow if _u(r.kind) == "INSTREAM"]
    for f in entry.get("jcl_dds", []):
        dd = f.get("dd") or f.get("concat_of")
        label = f"{f['step']}.{f.get('dd') or '+' + str(f.get('concat_of'))} @{f['line']}"
        if f.get("include"):
            # a DD of an INCLUDE group has no job, proc or step of its own (SPEC.md section 3). The member lives in its
            # own file and INCLUDE is not expanded, so its DDs stay unscored (the INCLUDE statement is scored on the step).
            sc.add(
                "jcl_dds",
                path,
                f"INCLUDE {f['include']}: {f.get('dd')} @{f['line']}",
                "unscored",
                f.get("horror"),
                "a member of an INCLUDE group: job_flow_data does not expand INCLUDE (core/job_flow.py)",
            )
            continue
        added = (
            f"; added to {f.get('override_of')}: job_flow_data keeps only DDs that name a DSN, so it cannot tell an added DD from an override"
            if f.get("added")
            else ""
        )
        if f.get("sysout") or f.get("dummy"):
            # #7065: a SYSOUT / DUMMY DD is its own job_flow row kind, matched on (step, ddname) like a DSN DD
            kind = "SYSOUT" if f.get("sysout") else "DUMMY"
            owner = f.get("override_of") or f["step"]
            cands = [
                x
                for x in flow
                if _u(x.kind) == kind and _u(x.step_name) == _u(owner) and _u(x.dd_name) == dd and id(x) not in used
            ]
            r = next((x for x in cands if not (f.get("override_of") and x.in_proc)), cands[0] if cands else None)
            if r is None:
                sc.add("jcl_dds", path, label, "missing", f.get("horror"), f"no {kind} row for this DD")
                continue
            used.add(id(r))
            pairs = [("line", f["line"], r.line)]
            if kind == "SYSOUT":
                # the key states SYSOUT as written, `(class,writer,form)` or `class`; the engine keeps the class
                key_cls = str(f["sysout"]).strip().lstrip("(").split(",")[0].rstrip(")").strip()
                pairs.append(("sysout", key_cls, getattr(eng, "sysout", {}).get((path, r.line))))
            d = _diff(pairs)
            sc.add("jcl_dds", path, label, "fail" if d else "pass", f.get("horror"), d)
            if f.get("output_refs"):
                # #7065: OUTPUT= references, as coded (`*.NAME`), in coded order
                got = getattr(eng, "jcl_extra", {}).get((path, r.line), {}).get("output_refs", [])
                want = [_u(x) for x in f["output_refs"]]
                d = _diff([("output_refs", want, got)])
                sc.add(
                    "jcl_dds",
                    path,
                    f"{label} OUTPUT={_compact(f['output_refs'])}",
                    "fail" if d else "pass",
                    f.get("horror"),
                    d,
                )
            if f.get("added"):
                _score_added(sc, path, label, f, r, steps, eng)
            continue
        if "inline_lines" in f:
            why = _instream_not_kept(f["dd"])
            if why:
                sc.add("jcl_dds", path, label, "unscored", f.get("horror"), why)
                continue
            r = next((x for x in ins if _u(x.step_name) == f["step"] and _u(x.dd_name) == f["dd"]), None)
            if r is None:
                sc.add("jcl_dds", path, label, "missing", f.get("horror"), "no INSTREAM row for this DD")
                continue
            body = r.instream or ""
            n = len(body.split("\n")) if body else 0
            d = _diff([("line", f["line"], r.line), ("inline_lines", f["inline_lines"], n)])
            sc.add("jcl_dds", path, label, "fail" if d else "pass", f.get("horror"), d)
            continue
        # `//PROCSTEP.DD` on an EXEC of a procedure: job_flow names the row after the proc step (header of job_flow.py)
        owner = f.get("override_of") or f["step"]
        cands = [x for x in dds if _u(x.step_name) == _u(owner) and _u(x.dd_name) == dd and id(x) not in used]
        # an override sits in the job, so it wins over the procedure's own DD of the same name (#7065)
        r = next((x for x in cands if not (f.get("override_of") and x.in_proc)), cands[0] if cands else None)
        if r is None:
            sc.add("jcl_dds", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        pairs = [
            ("line", f["line"], r.line),
            ("dsn", _u(f.get("dsn")), _u(r.dsn)),
            ("generation", f.get("generation"), r.generation),
            ("disp", f.get("disp"), r.disp),
            ("disp_normal", f.get("disp_normal"), r.disp_normal),
        ]
        if "temp" in f:
            pairs.append(("temp", f["temp"], (r.dsn or "").startswith("&&")))
        if "symbolic" in f:
            pairs.append(("symbolic", f["symbolic"], _is_symbolic(r.dsn)))
        if "job" in f:
            pairs.append(("job", _u(f["job"]), jobs[id(r)]))
        d = _diff(pairs)
        sc.add("jcl_dds", path, label, "fail" if d else "pass", f.get("horror"), d)
        if "added" in f:
            _score_added(sc, path, label, f, r, steps, eng)
    for r in [x for x in flow if _u(x.kind) in ("DD", "SYSOUT", "DUMMY")]:
        if id(r) not in used:
            sc.add("jcl_dds", path, f"{r.step_name}.{r.dd_name} @{r.line}", "phantom", None, "not in the key")


def _if_branch(text: str | None) -> tuple[str | None, str | None]:
    """job_flow's `if_cond` ("(A.RC = 0)", "NOT (A.RC = 0)" after ELSE) as the key's (condition, branch)."""
    if not text:
        return None, None
    t = text.strip()
    branch = "then"
    if t.upper().startswith("NOT "):
        t, branch = t[4:].strip(), "else"
    if t.upper().endswith(" THEN"):
        t = t[:-5].strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    return t, branch


def _cards(body: str) -> list[tuple[int, str, str]]:
    """The control statements of an in-stream body as (index of its first line, verb, operands).

    A line ending in `-` (IDCAMS) or `,` (DFSORT / ICETOOL) continues on the next; the hyphen is dropped and
    the pieces joined with one blank. This is the scorer's own reading of the text the engine kept."""
    out: list[tuple[int, str, str]] = []
    pending: list[str] = []
    start = 0
    for i, raw in enumerate(body.split("\n")):
        line = raw.strip()
        if not pending:
            if not line or line.startswith(("*", "--")):  # `--` is a DB2 utility (DSNUTILB SYSIN) comment
                continue
            start = i
        cont = line.endswith(("-", ","))
        pending.append(line[:-1].rstrip() if line.endswith("-") else line)
        if cont:
            continue
        text = " ".join(" ".join(pending).split())
        verb, _, operands = text.partition(" ")
        out.append((start, verb.upper(), operands.strip()))
        pending = []
    return out


def score_jcl_utility_cards(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """Each keyed control statement against the INSTREAM row of its (step, DD): the engine keeps the body, not
    the statements, so a card passes when it is in the body at its line with the keyed operands."""
    ef = eng.files.get(path)
    ins = [r for r in (ef.job_flow if ef else []) if _u(r.kind) == "INSTREAM"]
    steps = [r for r in (ef.job_flow if ef else []) if _u(r.kind) == "STEP"]
    parsed: dict[int, list[tuple[int, str, str]]] = {}
    for f in entry.get("jcl_utility_cards", []):
        label = f"{f['step']}.{f['dd']} {f['verb']} @{f['line']}"
        why = _instream_not_kept(f["dd"])
        if why:
            sc.add("jcl_utility_cards", path, label, "unscored", f.get("horror"), why)
            continue
        r = next((x for x in ins if _u(x.step_name) == f["step"] and _u(x.dd_name) == f["dd"]), None)
        if r is None:
            sc.add("jcl_utility_cards", path, label, "missing", f.get("horror"), "no INSTREAM row for this DD")
            continue
        cards = parsed.setdefault(id(r), _cards(r.instream or ""))
        c = next((x for x in cards if r.line + 1 + x[0] == f["line"] and x[1] == f["verb"]), None)
        if c is None:
            sc.add("jcl_utility_cards", path, label, "missing", f.get("horror"), "no such statement at that line")
            continue
        owner = next((x for x in steps if _u(x.step_name) == f["step"] and _u(x.in_proc) == _u(f.get("proc"))), None)
        pairs = [("operands", f["operands"], c[2])]
        if owner is not None:  # no STEP row: the jcl_steps channel reports it, the card is scored on what it has
            pairs.append(("utility", _u(f.get("utility")), _u(owner.program)))
        d = _diff(pairs)
        sc.add("jcl_utility_cards", path, label, "fail" if d else "pass", f.get("horror"), d)


def _resolved_ims_calls(eng: Engine) -> dict[tuple[str, int], dict[str, Any]]:
    """GalaxyIR.ims_calls() by (file, line), computed once per engine: the CBLTDLI function code is the
    first operand's VALUE, which only the reader resolves."""
    cached = getattr(eng, "_resolved_ims_calls", None)
    if cached is None:
        cached = {(str(c["file"]).replace("\\", "/"), c["line"]): c for c in eng.ir.ims_calls()}
        eng._resolved_ims_calls = cached  # type: ignore[attr-defined]
    return cached


def score_dli_calls(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    keyed = entry.get("dli_calls", [])
    if not keyed:
        return
    ef = eng.files.get(path)
    rows = {r.line: r for r in (ef.dli_calls if ef else [])}
    resolved = _resolved_ims_calls(eng)
    for f in keyed:
        label = f"CBLTDLI {f['function']} @{f['line']}"
        r = rows.get(f["line"])
        if r is None:
            sc.add("dli_calls", path, label, "missing", f.get("horror"))
            continue
        got = resolved.get((path, f["line"]), {})
        d = _diff(
            [
                ("function", _u(f["function"]), _u(got.get("function"))),
                ("pcb", _u(f["pcb"]), _u(r.pcb)),
                ("io_area", _u(f["io_area"]), _u(r.io_area)),
                ("ssas", ",".join(_u(x) for x in f["ssas"]) or None, _u(r.ssas)),
            ]
        )
        sc.add("dli_calls", path, label, "fail" if d else "pass", f.get("horror"), d)


def score_ims_gen(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    keyed = entry.get("ims_gen", [])
    if not keyed:
        return
    ef = eng.files.get(path)
    rows = list(ef.ims_gen) if ef else []
    used: set = set()
    for f in keyed:
        label = f"{f['kind']} {f['name']} @{f['line']}"
        r = next((x for x in rows if x.kind == f["kind"] and _u(x.name) == _u(f["name"]) and id(x) not in used), None)
        if r is None:
            sc.add("ims_gen", path, label, "missing", f.get("horror"))
            continue
        used.add(id(r))
        pairs = [("line", f["line"], r.line)]
        if f["kind"] == "SEGM":
            pairs += [
                ("parent", _u(f.get("parent") or None), _u(r.parent or None)),
                ("bytes", f.get("bytes"), r.bytes),
            ]
        d = _diff(pairs)
        sc.add("ims_gen", path, label, "fail" if d else "pass", f.get("horror"), d)


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
        pairs = [("group", f["group"], _u(r.group) or _u(getattr(r, "macro_table", None))), ("line", f["line"], r.line)]
        if f.get("program"):
            pairs.append(("program", f["program"], _u(r.program)))
        if f.get("dsname"):
            pairs.append(("dsname", f["dsname"], _u(r.dsname)))
        if f.get("ddname"):
            pairs.append(("ddname", f["ddname"], _u(r.ddname)))
        if f.get("record_format"):
            pairs.append(("record_format", f["record_format"], _u(r.record_format)))
        if f.get("plan"):
            pairs.append(("plan", f["plan"], _u(r.plan)))
        if f.get("transid"):
            pairs.append(("transid", f["transid"], _u(r.transid)))
        d = _diff(pairs)
        sc.add("csd_resources", path, label, "fail" if d else "pass", f.get("horror"), d)
    explicit_res = {(_u(p["type"]), _u(p["name"])): p for p in _phantoms(entry, "csd_resources")}
    seen_res: set = set()
    for r in res:
        if id(r) not in used:
            key = (_u(r.resource_type), _u(r.name))
            p = explicit_res.get(key)
            if p:
                seen_res.add(key)
            sc.add(
                "csd_resources",
                path,
                f"{r.resource_type} {r.name}",
                "phantom",
                p.get("horror") if p else None,
                p["why"] if p else "not in the key",
            )
    for (rtype, rname), p in explicit_res.items():
        if (rtype, rname) not in seen_res:
            sc.add("csd_resources", path, f"not {rtype} {rname}", "pass", p.get("horror"))
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
    explicit_tx = {_u(p["transid"]): p for p in _phantoms(entry, "transactions")}
    seen_tx: set = set()
    for t in txs:
        if id(t) not in used:
            p = explicit_tx.get(_u(t.transid))
            if p:
                seen_tx.add(_u(t.transid))
            sc.add(
                "transactions",
                path,
                t.transid,
                "phantom",
                p.get("horror") if p else None,
                p["why"] if p else "not in the key",
            )
    for txid, p in explicit_tx.items():
        if txid not in seen_tx:
            sc.add("transactions", path, f"not {txid}", "pass", p.get("horror"))


def _ridfld_and_addressing(attributes: str | None) -> tuple[str | None, str | None]:
    """The RIDFLD operand and the RBA / RRN / XRBA flag the engine keeps in a FILE row's `attributes`."""
    text = (attributes or "").upper()
    m = re.search(r"RIDFLD\(([^)]*)\)", text)
    flags = [w for w in re.findall(r"[A-Z]+", re.sub(r"[A-Z]+\([^)]*\)", " ", text)) if w in ("RBA", "RRN", "XRBA")]
    return (m.group(1).strip() if m else None), (flags[0] if flags else None)


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
        ridfld, addressing = _ridfld_and_addressing(r.attributes)
        stated = []
        if "ridfld" in f:  # #7065: how the record is addressed, when the key states it
            stated.append(("ridfld", _u(f["ridfld"]), _u(ridfld)))
        if "addressing" in f:
            stated.append(("addressing", _u(f["addressing"]), _u(addressing)))
        d = _diff(
            stated
            + [
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
    explicit = {_u(p["dsn"]): p for p in _phantoms(entry, "jcl_datasets")}
    for dsn, p in explicit.items():
        if dsn not in raw:
            sc.add("jcl_datasets", path, f"not {p['dsn']}", "pass", p.get("horror"))
    for r in sorted(raw - accepted):
        if r in explicit:
            sc.add("jcl_datasets", path, f"raw import {r}", "phantom", explicit[r].get("horror"), explicit[r]["why"])
            continue
        h = next((f.get("horror") for f in entry.get("jcl_datasets", []) if r.startswith(f["dsn"].upper())), None)
        sc.add(
            "jcl_datasets",
            path,
            f"raw import {r}",
            "phantom",
            h or (horrors[0] if horrors and "(" in r else None),
            "not a dataset reference the member makes",
        )


def score_jcl_outputs(sc: Score, path: str, entry: dict[str, Any], eng: Engine) -> None:
    """Each OUTPUT JCL statement against job_flow's OUTPUT rows: name, step (none at job level), line and the keyword
    names it codes (gitgalaxy#7065, H-0094)."""
    ef = eng.files.get(path)
    rows = [r for r in (ef.job_flow if ef else []) if _u(r.kind) == "OUTPUT"]
    extra = getattr(eng, "jcl_extra", {})
    used: set = set()
    for f in entry.get("jcl_outputs", []):
        where = f["step"] if f.get("step") else "job level"
        label = f"{f['name']} OUTPUT ({where}) @{f['line']}"
        r = next((x for x in rows if _u(x.name) == _u(f["name"]) and id(x) not in used), None)
        if r is None:
            sc.add("jcl_outputs", path, label, "missing", f.get("horror"), "no OUTPUT row for this statement")
            continue
        used.add(id(r))
        got = extra.get((path, r.line), {}).get("output_params", [])
        d = _diff(
            [
                ("line", f["line"], r.line),
                ("step", _u(f.get("step")), _u(r.step_name)),
                ("params", [_u(x) for x in f.get("params", [])], got),
            ]
        )
        sc.add("jcl_outputs", path, label, "fail" if d else "pass", f.get("horror"), d)


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
        extra = []
        if "relative_key" in f:
            extra.append(("relative_key", _u(f["relative_key"]), _u(r.relative_key)))
        if "alternate_keys" in f:
            want = sorted((_u(a["name"]), bool(a["duplicates"])) for a in f["alternate_keys"])
            got = sorted((_u(n), bool(dup)) for n, dup in (r.alternate_keys or []))
            extra.append(("alternate_keys", want, got))
        d = _diff(
            extra
            + [
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
        if f.get("rerun"):
            sc.add(
                "file_control",
                path,
                f"{label} RERUN {f['rerun'].get('assign')}",
                "unscored",
                f.get("horror"),
                "file_control_data keeps no RERUN clause of I-O-CONTROL, neither its checkpoint data set nor EVERY "
                f"{f['rerun'].get('every')} records (the checkpoint data set is not a SELECT)",
            )
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
    stated = list(entry.get("file_edges", []))
    # a RUN PROGRAM call site (IKJEFT01 / IKJEFT1B running a program) is an EXEC PGM edge to that program's member,
    # which the key does not repeat as a file edge (#7065)
    for cs in entry.get("call_sites", []):
        if cs.get("verb") != "RUN PROGRAM":
            continue
        member = next(
            (p for p, ef in eng.files.items() if _u(cs.get("operand")) in {_u(i) for i in (ef.program_ids or [])}), None
        )
        if member and not any(f["kind"] == "exec" and f["target"] == member for f in stated):
            stated.append({"kind": "exec", "target": member, "horror": cs.get("horror")})
    for f in stated:
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
            u = next(
                (x for x in eng.units.get(path, []) if _u(x["name"]) == _u(f["name"]) and not x.get("main_line")), None
            )
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
    score_jcl_outputs,
    score_jcl_utility_cards,
    score_dli_calls,
    score_ims_gen,
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
