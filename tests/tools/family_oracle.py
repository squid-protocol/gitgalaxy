#!/usr/bin/env python3
"""Keyword-family validity test (#8863): does each per-function signal count what its name says?

    python tests/tools/family_oracle.py SCAN_DB --src ROOT              # report, every family, Python
    python tests/tools/family_oracle.py SCAN_DB --src ROOT --lang go    # another language (go rust javascript typescript java c)
    python tests/tools/family_oracle.py SCAN_DB --src ROOT --json OUT   # the same, machine readable
    python tests/tools/family_oracle.py SCAN_DB --src ROOT --gate FLOORS.json   # exit 1 when a family falls below its floor
    python tests/tools/family_oracle.py --list-families                 # each family and the sentence it is scored against

GitGalaxy's per-function signals (`function_data.arch_io`, `arch_regex`, `bitwise_ops`, ...) are regex families, written per language in
`gitgalaxy/standards/language_standards/languages/`. A name such as "File & Network I/O" is a promise; this tool checks it. For every
function in a finished scan it asks a real parser what the function does (the oracle), joins the answer to the family column on the same
function (file and start line), and reports per family:

  recall      of the functions where the oracle sees the construct, the share where the family fired
  precision   of the functions where the family fired, the share where the oracle sees the construct
  rho         Spearman rank correlation of the family count with the oracle count
  missed      the tokens most common in the functions the family missed: the candidates for missing keywords

and a status: ok, misses (recall under the bar), over-counts (precision under the bar), both, dead (never fires although the oracle sees the
construct) or no-instances (the oracle never sees it, so nothing can be said).

What the numbers mean, and do not. The oracle is a reading of the family NAME written in `FAMILIES` below, one sentence each. Where a family is
narrow on purpose (`arch_serialization` is unsafe deserialization only), the sentence says so, and the score is against that sentence. A low
recall against a sentence nobody agreed to is a definition question, not a bug: the sentences are provisional until the owner answers #8862.
Python's oracle is `ast`; Go, Rust, JavaScript, TypeScript, Java and C use tree-sitter (`family_oracle_ts.py`, the `translator` extra); any other language raises a clear error rather than scoring against nothing. Report only: nothing here
runs in CI, and `--gate` is the hook for a ratchet once the floors are agreed.

SCAN_DB is a finished `*_master.db`; `--src` is the directory that was scanned (the database's file paths are looked up under it, then with
leading path parts dropped, so a scan of a copy still resolves). A function the oracle cannot find (a file that no longer parses, a start line
that moved) is counted as unmatched and left out of every ratio.
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gitgalaxy.core.source_text import read_source  # noqa: E402

RECALL_BAR = 0.8
PRECISION_BAR = 0.8

# Names the oracle reads. Kept apart from the rules in standards/ on purpose: the oracle is the independent reading.
_FILE_METHODS = frozenset(
    {
        "read",
        "write",
        "readline",
        "readlines",
        "writelines",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "listdir",
        "glob",
        "rglob",
        "iterdir",
        "mkdir",
        "makedirs",
        "unlink",
        "copyfile",
        "rmtree",
    }
)
_REGEX_METHODS = frozenset({"search", "match", "fullmatch", "finditer", "findall", "sub", "subn"})
_CLOCKS = frozenset(
    {
        "time",
        "perf_counter",
        "perf_counter_ns",
        "monotonic",
        "process_time",
        "time_ns",
        "now",
        "utcnow",
        "strftime",
        "strptime",
        "timedelta",
    }
)
_DANGER_CALLS = frozenset({"eval", "exec", "system", "popen", "Popen", "unsafe_load", "_exit", "abort", "exit"})
_SUBPROCESS_CALLS = frozenset({"call", "run", "Popen", "check_output", "check_call"})
_LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
_LOG_OBJECTS = frozenset({"logger", "logging", "log", "_log", "_logger", "LOG"})
_THREAD_NAMES = frozenset(
    {"Thread", "Pool", "Process", "ThreadPoolExecutor", "ProcessPoolExecutor", "Queue", "submit", "imap", "apply_async"}
)
_LOCK_NAMES = frozenset({"Lock", "RLock", "Semaphore", "BoundedSemaphore", "acquire", "release"})
_CASTS = frozenset({"int", "str", "float", "bool", "bytes", "list", "dict", "set", "tuple", "cast", "bytearray"})
_BITWISE_OPS = (ast.LShift, ast.RShift, ast.BitXor)


@dataclass(frozen=True)
class Family:
    column: str  # function_data column
    oracle: str  # key in the oracle's counts
    sentence: str  # the one sentence the family is scored against


FAMILIES: tuple[Family, ...] = (
    Family(
        "complexity",
        "branch",
        "decision points: if, loops, conditional expressions, except handlers, asserts, boolean operators, comprehension filters",
    ),
    Family("struct_branch", "branch", "same count as complexity"),
    Family("struct_closures", "closures", "functions and lambdas defined inside the function"),
    Family("struct_comprehensions", "comprehensions", "list, set, dict comprehensions and generator expressions"),
    Family("struct_decorators", "decorators", "decorators on the function itself"),
    Family(
        "arch_io",
        "io",
        "opens or reads/writes a file, lists or globs a directory (not path string work, not process exit)",
    ),
    Family(
        "arch_regex",
        "regex",
        "executes a regular expression: re.* module calls or a match/search/fullmatch/finditer/findall/sub/subn call",
    ),
    Family("arch_time", "time", "reads a clock or formats/parses a time"),
    Family(
        "arch_serialization",
        "unsafe_deserialize",
        "unsafe deserialization only: pickle/marshal load(s), ast.literal_eval, yaml unsafe load (json is outside)",
    ),
    Family("state_danger", "danger", "high-risk execution: eval, exec, subprocess calls, os.system, process exit"),
    Family("state_halt_hits", "sleep", "sleeps and timed waits: sleep calls"),
    Family("state_bailout_hits", "bailout", "raise statements and process-exit calls"),
    Family("state_print_hits", "print", "print calls"),
    Family("state_cast_hits", "cast", "builtin type casts: int, str, float, bool, bytes, list, dict, set, tuple"),
    Family(
        "bitwise_ops",
        "bitwise",
        "bitwise operators in operator position: << >> ^ ~ (& and | are set operators too, so left out)",
    ),
    Family("lazy_evaluation", "lazy", "yield / yield from (generator expressions are a #8862 decision, left out)"),
    Family("def_telemetry", "telemetry", "logger calls"),
    Family("arch_concurrency", "threads", "threads, pools, processes, queues, executor submits"),
    Family("def_sync_locks", "locks", "locks, semaphores, acquire and release"),
    Family("arch_globals", "globals", "global / nonlocal statements and reads of os.environ, sys.argv, sys.path"),
    Family("arch_import", "imports", "import statements inside the function"),
    Family("def_cleanup", "cleanup", "with blocks and try/finally"),
    Family("is_documented", "doc", "has a docstring"),
)


class _Counts:
    """Per-function oracle counts and, for each, the tokens that triggered it (for the missed-token list)."""

    def __init__(self) -> None:
        self.n: collections.Counter[str] = collections.Counter()
        self.tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

    def add(self, key: str, token: str | None = None) -> None:
        self.n[key] += 1
        if token:
            self.tokens[key][token] += 1


def _call_names(call: ast.Call) -> tuple[str | None, str | None]:
    """(method or function name, base name) of a call: `re.search(..)` -> ("search", "re"); `f(..)` -> ("f", None)."""
    func = call.func
    if isinstance(func, ast.Attribute):
        base = func.value
        return func.attr, base.id if isinstance(base, ast.Name) else None
    if isinstance(func, ast.Name):
        return func.id, None
    return None, None


def _count_call(call: ast.Call, c: _Counts) -> None:
    name, base = _call_names(call)
    if name is None:
        return
    if name == "print":
        c.add("print", name)
    if name == "open" or name in _FILE_METHODS:
        c.add("io", name)
    if base == "re" or name in _REGEX_METHODS:
        c.add("regex", name)
    if name in _CLOCKS or base in ("time", "datetime"):
        c.add("time", name)
    if (base in ("pickle", "marshal") and name in ("load", "loads", "Unpickler")) or name in (
        "literal_eval",
        "unsafe_load",
    ):
        c.add("unsafe_deserialize", name)
    if (
        name in _DANGER_CALLS
        or (base == "subprocess" and name in _SUBPROCESS_CALLS)
        or (base == "os" and name.startswith(("exec", "spawn")))
    ):
        c.add("danger", name)
    if name == "sleep":
        c.add("sleep", name)
    if name in ("exit", "_exit", "abort", "quit"):
        c.add("bailout", name)
    if name in _LOG_METHODS and base in _LOG_OBJECTS:
        c.add("telemetry", name)
    if name in _THREAD_NAMES or base in ("threading", "multiprocessing"):
        c.add("threads", name)
    if name in _LOCK_NAMES:
        c.add("locks", name)
    if isinstance(call.func, ast.Name) and name in _CASTS:
        c.add("cast", name)


def python_oracle(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> _Counts:
    """What `fn` (its whole span, nested definitions included) does, counted from its syntax tree."""
    c = _Counts()
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.IfExp, ast.ExceptHandler, ast.Assert)):
            c.add("branch")
        elif isinstance(node, ast.BoolOp):
            c.n["branch"] += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            c.n["branch"] += len(node.ifs)
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            c.add("closures")
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            c.add("comprehensions")
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            c.add("lazy", "yield")
        if isinstance(node, ast.Raise):
            c.add("bailout", "raise")
        if isinstance(node, (ast.With, ast.AsyncWith)):
            c.add("cleanup", "with")
        if isinstance(node, ast.Try) and node.finalbody:
            c.add("cleanup", "finally")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            c.add("globals", "global")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and (node.value.id, node.attr)
            in {
                ("os", "environ"),
                ("sys", "argv"),
                ("sys", "path"),
            }
        ):
            c.add("globals", f"{node.value.id}.{node.attr}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            c.add("imports")
        if (isinstance(node, ast.BinOp) and isinstance(node.op, _BITWISE_OPS)) or (
            isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert)
        ):
            c.add("bitwise", type(node.op).__name__)
        if isinstance(node, ast.Call):
            _count_call(node, c)
    for dec in fn.decorator_list:
        c.add("decorators", ast.unparse(dec).split("(")[0])
    c.n["doc"] = 1 if ast.get_docstring(fn) else 0
    return c


class _PythonOracle:
    """The interface every language oracle has: `exts`, `families`, `index(text)` -> {(name, line): node}, `count(node)` -> (counts, tokens)."""

    exts = (".py", ".pyi", ".pyw")
    families = FAMILIES

    @staticmethod
    def index(text: str) -> dict:
        return _index_functions(ast.parse(text))

    @staticmethod
    def count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[collections.Counter, dict]:
        c = python_oracle(node)
        return c.n, c.tokens


def get_oracle(lang: str):
    """The oracle for `lang`: Python's `ast`, or a tree-sitter one from family_oracle_ts (languages listed there)."""
    if lang == "python":
        return _PythonOracle
    import family_oracle_ts

    oracle = family_oracle_ts.get_oracle(lang)
    if oracle is None:
        raise SystemExit(
            f"no oracle for language {lang!r} yet (available: python, {', '.join(family_oracle_ts.languages())}); see #8863"
        )
    return oracle


def _index_functions(tree: ast.AST) -> dict[tuple[str, int], ast.FunctionDef | ast.AsyncFunctionDef]:
    """(name, line) -> function node; a decorated function is reachable by its `def` line and by its first decorator's line."""
    index: dict[tuple[str, int], ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            index[(node.name, node.lineno)] = node
            if node.decorator_list:
                index[(node.name, node.decorator_list[0].lineno)] = node
    return index


def resolve_source(rel_path: str, src: Path) -> Path | None:
    """The file a scan row names, looked up under `src`, then with leading path parts dropped (a scan of a copy)."""
    parts = Path(rel_path.replace("\\", "/")).parts
    for start in range(len(parts)):
        cand = src.joinpath(*parts[start:])
        if cand.is_file():
            return cand
    return None


def spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rank correlation (average ranks for ties); None when either side is constant."""

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=v.__getitem__)
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out

    if len(a) < 2:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return None if va == 0 or vb == 0 else cov / (va * vb) ** 0.5


def status(
    n_oracle: int,
    n_family: int,
    recall: float | None,
    precision: float | None,
    *,
    recall_bar: float,
    precision_bar: float,
) -> str:
    if n_oracle == 0:
        return "no-instances" if n_family == 0 else "over-counts"
    if n_family == 0:
        return "dead"
    low_r = recall is not None and recall < recall_bar
    low_p = precision is not None and precision < precision_bar
    return "both" if low_r and low_p else "misses" if low_r else "over-counts" if low_p else "ok"


def score(
    db: Path,
    src: Path,
    lang: str = "python",
    *,
    top: int = 5,
    recall_bar: float = RECALL_BAR,
    precision_bar: float = PRECISION_BAR,
) -> dict:
    """Score every family of the language's oracle found in the scan; returns {"matched", "unmatched", "families": [...]}."""
    oracle = get_oracle(lang)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    have = {r[1] for r in con.execute("PRAGMA table_info(function_data)")}
    fams = [f for f in oracle.families if f.column in have]
    cols = ",".join(f"u.{f.column}" for f in fams)
    rows = con.execute(
        f"SELECT f.file_path, u.func_name, u.start_line, {cols} FROM function_data u JOIN file_data f ON f.id = u.file_id"  # noqa: S608
    )
    trees: dict[str, dict | None] = {}
    fam_vals: dict[str, list[float]] = {f.column: [] for f in fams}
    orc_vals: dict[str, list[float]] = {f.column: [] for f in fams}
    missed: dict[str, collections.Counter[str]] = {f.column: collections.Counter() for f in fams}
    matched = unmatched = 0
    exts = oracle.exts
    for row in rows:
        rel, name, line = row[0], row[1], row[2]
        if not str(rel).lower().endswith(exts):
            continue
        if rel not in trees:
            path = resolve_source(str(rel), src)
            try:
                trees[rel] = oracle.index(read_source(path).text) if path else None
            except (SyntaxError, ValueError):
                trees[rel] = None
        funcs = trees[rel] or {}
        node = funcs.get((name, line)) or funcs.get((str(name).replace("::", ".").split(".")[-1], line))
        if node is None:
            unmatched += 1
            continue
        matched += 1
        counts, tokens = oracle.count(node)
        for fam, value in zip(fams, row[3:], strict=True):
            o = counts.get(fam.oracle, 0)
            v = value or 0
            fam_vals[fam.column].append(float(v))
            orc_vals[fam.column].append(float(o))
            if o > 0 and not v > 0:
                missed[fam.column].update(tokens.get(fam.oracle, {}))
    out = []
    for fam in fams:
        fv, ov = fam_vals[fam.column], orc_vals[fam.column]
        n_o = sum(1 for x in ov if x > 0)
        n_f = sum(1 for x in fv if x > 0)
        both = sum(1 for x, y in zip(fv, ov, strict=True) if x > 0 and y > 0)
        recall = both / n_o if n_o else None
        precision = both / n_f if n_f else None
        out.append(
            {
                "family": fam.column,
                "definition": fam.sentence,
                "oracle_functions": n_o,
                "family_functions": n_f,
                "recall": None if recall is None else round(recall, 3),
                "precision": None if precision is None else round(precision, 3),
                "rho": None if (r := spearman(fv, ov)) is None else round(r, 3),
                "status": status(n_o, n_f, recall, precision, recall_bar=recall_bar, precision_bar=precision_bar),
                "missed_tokens": missed[fam.column].most_common(top),
            }
        )
    return {"language": lang, "matched": matched, "unmatched": unmatched, "families": out}


def _fmt(x: float | None) -> str:
    return "  -  " if x is None else f"{x:5.2f}"


def render(result: dict) -> str:
    lines = [
        f"language {result['language']}: {result['matched']} functions matched to the oracle, {result['unmatched']} unmatched (left out)",
        "",
        f"{'family':22s}{'oracle':>8s}{'family':>8s}{'recall':>8s}{'prec':>7s}{'rho':>7s}  {'status':13s} missed tokens",
    ]
    for f in result["families"]:
        miss = ", ".join(f"{t}:{n}" for t, n in f["missed_tokens"])
        lines.append(
            f"{f['family']:22s}{f['oracle_functions']:8d}{f['family_functions']:8d}{_fmt(f['recall']):>8s}{_fmt(f['precision']):>7s}"
            f"{_fmt(f['rho']):>7s}  {f['status']:13s} {miss}"
        )
    return "\n".join(lines)


def check_gate(result: dict, floors: dict) -> list[str]:
    """Failures of {family: {"recall": x, "precision": y}} floors; a family named in the floors but absent from the scan fails."""
    by = {f["family"]: f for f in result["families"]}
    bad = []
    for name, want in sorted(floors.items()):
        got = by.get(name)
        if got is None:
            bad.append(f"{name}: not in this scan")
            continue
        bad.extend(
            f"{name}: {metric} {got[metric]} below floor {want[metric]}"
            for metric in ("recall", "precision")
            if metric in want and (got[metric] is None or got[metric] < want[metric])
        )
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Score each keyword family against a real parser's reading of the same function (#8863)."
    )
    ap.add_argument("db", nargs="?", help="a finished *_master.db")
    ap.add_argument("--src", help="the directory that was scanned")
    ap.add_argument("--lang", default="python", help="oracle language (python; others from family_oracle_ts)")
    ap.add_argument("--json", dest="json_out", help="also write the result here")
    ap.add_argument("--gate", help="JSON {family: {recall, precision}} floors; exit 1 when one is not met")
    ap.add_argument("--top", type=int, default=5, help="missed tokens listed per family")
    ap.add_argument(
        "--list-families", action="store_true", help="print each family and its scoring sentence, then exit"
    )
    args = ap.parse_args(argv)
    if args.list_families:
        for f in get_oracle(args.lang).families:
            print(f"{f.column:22s} {f.sentence}")
        return 0
    if not args.db or not args.src:
        ap.error("SCAN_DB and --src are required")
    result = score(Path(args.db), Path(args.src), args.lang, top=args.top)
    print(render(result))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    if args.gate:
        bad = check_gate(result, json.loads(Path(args.gate).read_text(encoding="utf-8")))
        for line in bad:
            print("GATE:", line, file=sys.stderr)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
