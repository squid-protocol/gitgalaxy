"""
#3214: a ReDoS scaling sweep over every regex in the refraction tools
(gitgalaxy/tools/cobol_to_cobol/, gitgalaxy/tools/cobol_to_java/ and both
controllers). The engine's language rules get tests/extraction/tools/
sweep_redos_scaling.py and the strict suites; these tools got neither, which is
how #3205's `EXEC\\s+CICS.*?END-EXEC\\.` over a whole file shipped.

    python tests/tools/tool_regex_redos.py            # report
    python tests/tools/tool_regex_redos.py --ci       # exit 1 on an offender not in the baseline
    python tests/tools/tool_regex_redos.py --update-baseline

COLLECTION. Every `re.<fn>(pattern, ...)` call in the suites' source, with the
pattern and flags evaluated in the module's namespace (so f-strings built from
module constants resolve), plus every compiled `re.Pattern` reachable from a
module's globals. A pattern built from a function's local variables cannot be
evaluated statically; it is reported as `skipped`, never silently dropped.

MEASUREMENT. Each pattern runs through the method its code actually calls
(`findall`/`sub`/`split` scan every start position; `search`; `match` only
position 0) over payload families derived from the pattern: generic fillers
plus runs of the pattern's own keywords, including every prefix of its keyword
sequence (the #3205 shape: `EXEC CICS ` repeated, with no `END-EXEC`). A family
is an offender when

  - one call over PROBE_CHARS or SMALL_CHARS characters takes over SLOW_S, or
  - it costs at least BUDGET_S at LARGE_CHARS (4x SMALL_CHARS) AND that 4x
    input took at least QUADRATIC (8x) the time, confirmed on best-of-3 timings.
    Linear grows ~4x, quadratic ~16x.

An absolute budget alone cannot separate a mild quadratic from a bounded but
heavy linear pattern (the `.{0,600}?` CICS HANDLE scan costs 0.13s at 160k
chars and grows 4x); the growth test on samples of 0.1s and up can, and the
best-of-3 confirmation keeps a noisy runner from failing CI on a linear pattern
(#2901: never trust a ratio between small single samples). Calibration
(2026-09-19): #3205's pattern takes ~1s at 40k chars; a family under FLOOR_S at
40k is not scaled up. Each pattern runs in a worker process with a hard
timeout, so an exponential pattern is an offender instead of a hung sweep.

BASELINE. tests/cobol_mainframe/tool_regex_redos_baseline.json lists known
offenders by (module, pattern, flags). `--ci` fails on any offender outside it
and reports baseline entries that no longer reproduce, so they can be removed.
"""

import argparse
import ast
import importlib
import json
import multiprocessing
import queue
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SUITES = (
    "gitgalaxy/tools/cobol_to_cobol",
    "gitgalaxy/tools/cobol_to_java",
    "gitgalaxy/cobol_refractor_controller.py",
    "gitgalaxy/cobol_to_java_controller.py",
)
BASELINE = REPO_ROOT / "tests" / "cobol_mainframe" / "tool_regex_redos_baseline.json"

PROBE_CHARS = 4_000
SMALL_CHARS = 40_000
LARGE_CHARS = 160_000
FLOOR_S = 0.002
SLOW_S = 0.25
BUDGET_S = 0.1
QUADRATIC = 8.0
JOB_TIMEOUT_S = 30.0

# Positional index of `flags` in each module-level re function.
_FLAGS_ARG = {"compile": 1, "search": 2, "match": 2, "fullmatch": 2, "findall": 2, "finditer": 2, "split": 3}
_FLAGS_ARG.update({"sub": 4, "subn": 4})
_METHODS = set(_FLAGS_ARG) - {"compile"}
# Cost order: every start position > leftmost match > position 0 only.
_METHOD_RANK = {"findall": 3, "finditer": 3, "sub": 3, "subn": 3, "split": 3, "search": 2, "match": 1, "fullmatch": 1}

_GENERIC_UNITS = (
    " ",
    "A",
    "9",
    "A ",
    "A-",
    "-",
    ".",
    ". ",
    "'",
    '"',
    "(",
    ")",
    "*",
    ",",
    "=",
    "\n",
    "A\n",
    " \n",
    "X(9)",
)
# Escapes, character classes, group names and inline flags carry no keywords.
_ESCAPE = re.compile(r"\\[A-Za-z]|\[(?:\\.|[^\]])*\]|\(\?P?<[^>]*>|\(\?[a-zA-Z]+\)")
_KEYWORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9]")


@dataclass
class Site:
    module: str
    pattern: str
    flags: int
    lines: list[int] = field(default_factory=list)
    methods: set[str] = field(default_factory=set)

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.module, self.pattern, self.flags)

    @property
    def method(self) -> str:
        # Unknown usage (a compiled global passed elsewhere) is measured at its worst.
        return max(self.methods, key=_METHOD_RANK.__getitem__) if self.methods else "findall"


def _suite_files() -> list[Path]:
    files = []
    for entry in SUITES:
        path = REPO_ROOT / entry
        files.extend(sorted(path.glob("*.py")) if path.is_dir() else [path])
    return files


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)


def _is_re_call(node: ast.AST) -> Optional[str]:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
        and node.func.attr in _FLAGS_ARG
    ):
        return node.func.attr
    return None


def _call_arg(node: ast.Call, index: int, name: str) -> Optional[ast.expr]:
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return node.args[index] if len(node.args) > index else None


def _eval(node: ast.expr, namespace: dict[str, Any]) -> Any:
    code = compile(ast.Expression(body=node), "<pattern>", "eval")
    return eval(code, dict(namespace))  # noqa: S307 -- an expression from this repo's own tool source, evaluated in its module's namespace


def _pattern_globals(namespace: dict[str, Any]) -> dict[str, re.Pattern]:
    """Compiled patterns reachable from a module's globals, by global name."""
    found: dict[str, re.Pattern] = {}

    def walk(name: str, obj: Any, depth: int) -> None:
        if isinstance(obj, re.Pattern) and isinstance(obj.pattern, str):
            found.setdefault(name, obj)
        elif depth < 3 and isinstance(obj, dict):
            for k, v in obj.items():
                walk(f"{name}[{k!r}]", v, depth + 1)
        elif depth < 3 and isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                walk(f"{name}[{i}]", v, depth + 1)

    for name, obj in namespace.items():
        if not name.startswith("__"):
            walk(name, obj, 0)
    return found


def collect() -> tuple[list[Site], list[dict[str, Any]]]:
    """(sites, skipped): every evaluable pattern in the suites, merged per (module,
    pattern, flags), and every re call whose pattern could not be evaluated."""
    sites: dict[tuple[str, str, int], Site] = {}
    skipped: list[dict[str, Any]] = []
    trees = {}
    for path in _suite_files():
        trees[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    # Which methods each compiled global is called with, across every suite module.
    used_by_name: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _METHODS:
                target = node.func.value
                name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
                if name and name != "re":
                    used_by_name.setdefault(name, set()).add(node.func.attr)

    def add(module: str, pattern: str, flags: int, line: Optional[int], method: Optional[str]) -> None:
        site = sites.setdefault((module, pattern, flags), Site(module, pattern, flags))
        if line is not None and line not in site.lines:
            site.lines.append(line)
        if method:
            site.methods.add(method)

    for path, tree in trees.items():
        module = _module_name(path)
        namespace = vars(importlib.import_module(module))
        rel = path.relative_to(REPO_ROOT).as_posix()
        assigned: dict[int, str] = {}  # id(call node) -> the global it is assigned to
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                assigned[id(node.value)] = node.targets[0].id
        for node in ast.walk(tree):
            fn = _is_re_call(node)
            if fn is None:
                continue
            assert isinstance(node, ast.Call)
            pat_node = _call_arg(node, 0, "pattern")
            flag_node = _call_arg(node, _FLAGS_ARG[fn], "flags")
            try:
                pattern = _eval(pat_node, namespace) if pat_node is not None else None
                flags = int(_eval(flag_node, namespace)) if flag_node is not None else 0
            except Exception as exc:  # noqa: BLE001 -- any evaluation failure means "not statically known"
                skipped.append({"module": rel, "line": node.lineno, "call": f"re.{fn}", "why": type(exc).__name__})
                continue
            if isinstance(pattern, re.Pattern):
                pattern, flags = pattern.pattern, pattern.flags & ~re.UNICODE
            if not isinstance(pattern, str):
                skipped.append({"module": rel, "line": node.lineno, "call": f"re.{fn}", "why": "non-str pattern"})
                continue
            if fn == "compile":
                name = assigned.get(id(node))
                methods = used_by_name.get(name, set()) if name else set()
                for m in methods or {None}:
                    add(rel, pattern, flags, node.lineno, m)
            else:
                add(rel, pattern, flags, node.lineno, fn)
        imported = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        for name, compiled in _pattern_globals(namespace).items():
            flags = compiled.flags & ~re.UNICODE
            root = name.split("[")[0]
            # Already collected from its re call, or imported (the defining module owns it).
            if (rel, compiled.pattern, flags) in sites or root in imported:
                continue
            for m in used_by_name.get(root, set()) or {None}:
                add(rel, compiled.pattern, flags, None, m)
    for site in sites.values():
        site.lines.sort()
    return sorted(sites.values(), key=lambda s: (s.module, s.lines[:1], s.pattern)), skipped


# ==============================================================================
# Payloads and measurement
# ==============================================================================
def payload_units(pattern: str, flags: int) -> list[str]:
    """Repeating units that stress `pattern`: generic fillers, then its keywords
    alone and as every prefix of their sequence."""
    words: list[str] = []
    for w in _KEYWORD.findall(_ESCAPE.sub(" ", pattern)):
        if w not in words:
            words.append(w)
    words = words[:6]
    units = list(_GENERIC_UNITS)
    for w in words:
        units += [f"{w} ", f"{w}\n", w]
    # Every prefix of the keyword sequence, bare and with a name after each keyword
    # (`SELECT X ASSIGN X `): the statement opens but never reaches its terminator.
    for i in range(1, len(words) + 1):
        units.append(" ".join(words[:i]) + " ")
        units.append(" X ".join(words[:i]) + " X ")
    if flags & re.IGNORECASE:
        units += [u.lower() for u in units if u.lower() != u]
    return list(dict.fromkeys(units))


def _fill(unit: str, n: int) -> str:
    return (unit * (n // len(unit) + 1))[:n]


def _time_once(compiled: re.Pattern, method: str, text: str) -> float:
    call = {
        "sub": lambda: compiled.sub("", text),
        "subn": lambda: compiled.subn("", text),
        "finditer": lambda: list(compiled.finditer(text)),
    }.get(method) or (lambda: getattr(compiled, method)(text))
    start = time.perf_counter()
    call()
    return time.perf_counter() - start


def _best_of(compiled: re.Pattern, method: str, text: str, first: float, runs: int = 2) -> float:
    return min([first] + [_time_once(compiled, method, text) for _ in range(runs)])


def measure(pattern: str, flags: int, method: str) -> dict[str, Any]:
    """The verdict for one pattern: the first offending payload family (see
    MEASUREMENT in the module docstring), else the costliest clean one."""
    compiled = re.compile(pattern, flags)
    worst: dict[str, Any] = {"offender": False, "reason": None, "seconds": 0.0, "unit": None, "chars": None}
    for unit in payload_units(pattern, flags):
        small = _fill(unit, SMALL_CHARS)
        for chars, text in ((PROBE_CHARS, _fill(unit, PROBE_CHARS)), (SMALL_CHARS, small)):
            seconds = _time_once(compiled, method, text)
            if seconds > SLOW_S:
                return {"offender": True, "reason": "slow", "seconds": round(seconds, 4), "unit": unit, "chars": chars}
        if seconds < FLOOR_S:
            continue
        large = _fill(unit, LARGE_CHARS)
        t_large = _time_once(compiled, method, large)
        if t_large > worst["seconds"]:
            worst.update(seconds=round(t_large, 4), unit=unit, chars=LARGE_CHARS)
        if t_large < BUDGET_S or t_large / seconds < QUADRATIC:
            continue
        t_small, t_large = _best_of(compiled, method, small, seconds), _best_of(compiled, method, large, t_large)
        growth = t_large / t_small
        if t_large >= BUDGET_S and growth >= QUADRATIC:
            return {
                "offender": True,
                "reason": f"quadratic ({growth:.1f}x for 4x the input)",
                "seconds": round(t_large, 4),
                "unit": unit,
                "chars": LARGE_CHARS,
            }
    return worst


def _worker(jobs: "multiprocessing.Queue", results: "multiprocessing.Queue") -> None:
    while True:
        job = jobs.get()
        if job is None:
            return
        results.put(measure(*job))


def sweep(sites: list[Site], timeout: float = JOB_TIMEOUT_S) -> list[dict[str, Any]]:
    """Measures every site in a worker process, restarting the worker after a timeout."""
    ctx = multiprocessing.get_context("spawn")
    rows = []
    proc = jobs = results = None
    try:
        for site in sites:
            if proc is None:
                jobs, results = ctx.Queue(), ctx.Queue()
                proc = ctx.Process(target=_worker, args=(jobs, results), daemon=True)
                proc.start()
            jobs.put((site.pattern, site.flags, site.method))
            try:
                result = results.get(timeout=timeout)
            except queue.Empty:
                proc.terminate()
                proc.join()
                proc = None
                result = {
                    "offender": True,
                    "reason": f"timeout ({timeout}s)",
                    "seconds": None,
                    "unit": None,
                    "chars": None,
                }
            rows.append(
                {
                    "module": site.module,
                    "lines": site.lines,
                    "method": site.method,
                    "pattern": site.pattern,
                    "flags": site.flags,
                    **result,
                }
            )
    finally:
        if proc is not None:
            jobs.put(None)
            proc.join(timeout=5)
            if proc.is_alive():
                proc.terminate()
    return rows


def load_baseline(path: Path = BASELINE) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["offenders"] if path.is_file() else []


def _bkey(row: dict[str, Any]) -> tuple[str, str, int]:
    return (row["module"], row["pattern"], row["flags"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ci", action="store_true", help="exit 1 on an offender not in the baseline")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--json", type=Path, help="write every measured row here")
    args = ap.parse_args()

    sites, skipped = collect()
    started = time.perf_counter()
    rows = sweep(sites)
    offenders = [r for r in rows if r["offender"]]
    print(
        f"{len(rows)} patterns measured in {time.perf_counter() - started:.1f}s, {len(skipped)} skipped, {len(offenders)} offenders"
    )
    for s in skipped:
        print(f"  skipped {s['module']}:{s['line']} {s['call']} ({s['why']})")
    for r in offenders:
        cost = (
            r["reason"]
            if r["seconds"] is None
            else f"{r['reason']}: {r['seconds']}s at {r['chars']} chars of {r['unit']!r}"
        )
        print(f"  OFFENDER {r['module']}:{r['lines']} .{r['method']} {r['pattern']!r} -- {cost}")
    if args.json:
        args.json.write_text(json.dumps({"rows": rows, "skipped": skipped}, indent=2) + "\n", encoding="utf-8")

    if args.update_baseline:
        notes = {_bkey(b): b["note"] for b in load_baseline() if b.get("note")}
        entries = []
        for r in offenders:
            entry = {k: r[k] for k in ("module", "pattern", "flags", "method", "reason", "unit", "seconds", "chars")}
            if _bkey(r) in notes:
                entry["note"] = notes[_bkey(r)]
            entries.append(entry)
        BASELINE.write_text(json.dumps({"offenders": entries}, indent=2) + "\n", encoding="utf-8")
        print(f"baseline: {len(entries)} offenders -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    baseline = {_bkey(b) for b in load_baseline()}
    new = [r for r in offenders if _bkey(r) not in baseline]
    gone = baseline - {_bkey(r) for r in offenders}
    for b in sorted(gone):
        print(f"  no longer reproduces (remove from the baseline): {b[0]} {b[1]!r}")
    if new:
        print(f"{len(new)} new offender(s) outside {BASELINE.name}")
    return 1 if args.ci and new else 0


if __name__ == "__main__":
    sys.exit(main())
