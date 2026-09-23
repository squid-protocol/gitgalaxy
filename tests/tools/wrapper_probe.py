#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Wrapper probe: which project-local THIN WRAPPERS hide a literal-vocabulary rule's
real use, and how many call sites go through them? (#3315, step 1 of epic #3313)

A literal rule (`debug_prints`, `panics_and_aborts`, `memory_alloc`, ...) counts
calls to a primitive by name. A project that wraps the primitive in its own
helper -- fortran/wrf's `wrf_error_fatal` is `print *,string` then `stop`, with
166 call sites -- makes every one of those call sites invisible to the rule.
`docs/known_blind_spots.md` records the limitation; this probe measures it, so
the detection heuristic the epic builds is chosen from data, not guessed.

MEASUREMENT ONLY. Nothing here changes what the engine records.

USAGE
    # the step-1 run: both rules, every crucible language, the LOC sweep
    python tests/tools/wrapper_probe.py --json /tmp/wrappers.json

    # one language, with every candidate's body (what the label pass reads)
    python tests/tools/wrapper_probe.py --langs fortran --detail

    # a full checkout instead of the crucible sample (#3324, epic step 2)
    python tests/tools/wrapper_probe.py --repo ../cpython --lang c --rules memory_alloc --max-loc 8

    # precision against the committed hand labels
    python tests/tools/wrapper_probe.py --json /tmp/wrappers.json --score tests/tools/wrapper_labels.json

DEFINITIONS (each is a decision #3315 measures, not a given)
    candidate   A non-synthetic extracted function of <= --max-loc LOC whose body
                hits the rule anywhere other than on its own name.
    call site   An UNQUALIFIED `name(` occurrence inside another function's body,
                after the engine's literal shield. The engine's own `calls_out_to`
                gates it (the language's call-form rule saw a call), so a
                same-spelled word that is not a call is never credited. `x.f(`,
                `x::f(` and `x->f(` are method or namespace calls on something
                else and are never credited.
    resolution  A call site credits a candidate only when the callee resolves to
                it: a definition of that name in the CALLER'S OWN FILE first, else
                exactly one definition in the repo group. Zero definitions (the
                callee lives outside the corpus sample) or several (a name
                collision) credit nothing -- that is the census's go/core `lock`
                false attribution, made impossible by construction.
    macro alias (#3324) A function-like `#define NAME(params) BODY` in a C-preprocessor
                language whose body hits the rule, or calls a function candidate or
                another macro alias (a bounded closure). curl 8.18's allocator layer
                is exactly this: `#define curlx_malloc(size) malloc(size)`. Several
                `#ifdef` definitions of one name are normal for a macro, so a name
                is an alias when ANY of its definitions is one. Call sites are
                unqualified `NAME(` occurrences outside `#define` lines.
    method      A candidate defined as a method (Go receiver, Python `self`/`cls`
                first parameter, a qualified header such as Lua `function M.f` or
                C++ `X::f`) is only reachable through a qualifier, so it receives
                no unqualified call sites at all.

The crucible samples files per repository, so a wrapper defined outside the
sample (CPython's obmalloc.c, curl's curlx) is invisible here. Counts are a
floor for those, not an estimate.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

import rule_probe  # noqa: E402  (corpus discovery, shared deliberately)

from gitgalaxy.core.detector import StructuralExtractor  # noqa: E402
from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

DEFAULT_RULES = ("debug_prints", "panics_and_aborts")
LOC_SWEEP = (3, 5, 8, 12)
LABELS = ("wrapper", "conditional", "incidental", "test_helper")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
# Languages whose source runs through the C preprocessor, so a function-like
# `#define` is a callable alias.
PREPROCESSOR_LANGS = frozenset({"c", "cpp", "objective-c"})
# A function-like macro definition, continuation lines included. Every repeat is
# bounded (a name, <= 200 chars of params, <= 400 chars of body) so one
# pathological line cannot scan the file.
_DEFINE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)\(([^)\n]{0,200})\)[ \t]*((?:[^\n\\]|\\\n){0,400})", re.M
)
_CALLED = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_ALIAS_CLOSURE_DEPTH = 6


def candidate_key(group: str, file: str, name: str, rule: str) -> str:
    """The stable identity of one candidate across runs (and in the label file)."""
    return f"{group}::{file}::{name}::{rule}"


def is_method_definition(lang: str, header: str, name: str) -> bool:
    """Whether the definition header makes `name` reachable only through a qualifier.

    `header` is the code from the function's start to the end of its first line.
    Conservative: an unrecognised shape is NOT a method, so the rule can only
    remove credit that a real qualifier would have removed anyway.
    """
    before = header.split(name, 1)[0]
    if re.search(r"(?:\.|::|->|:)\s*$", before):  # Lua `M.f`/`M:f`, C++ `X::f`, Ruby `self.f`
        return True
    if lang == "go" and re.match(r"\s*func\s*\(", header):  # receiver
        return True
    if lang == "python":
        m = re.search(re.escape(name) + r"\s*\(\s*(\w+)", header)
        return bool(m and m.group(1) in ("self", "cls"))
    return False


def _unqualified_sites(body: str, name: str) -> int:
    """Unqualified `name(` occurrences in an already literal-shielded body."""
    return sum(1 for _ in re.finditer(r"(?<![\w$.:>])" + re.escape(name) + r"\s*\(", body))


def probe_group(
    lang: str, group_dir: Path, rules: tuple[str, ...], max_loc: int, prism: Prism, crucible: Path
) -> dict[str, Any]:
    """Candidates and their resolved call sites for one crucible repo group."""
    registry = LANGUAGE_DEFINITIONS[lang]["rules"]
    patterns = {r: registry.get(r) for r in rules}
    patterns = {r: p for r, p in patterns.items() if hasattr(p, "finditer")}
    group = str(group_dir.relative_to(crucible))
    extractor = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
    exts = rule_probe._extensions(lang)

    literal: collections.Counter[str] = collections.Counter()
    definitions: dict[str, list[str]] = collections.defaultdict(list)  # name -> files
    candidates: dict[str, dict[str, Any]] = {}
    callers: list[tuple[str, str, list[str]]] = []  # (file, shielded body, calls_out_to)

    for path in sorted(group_dir.rglob("*"), key=lambda p: p.parts):
        if not path.is_file() or (exts and path.suffix.lower() not in exts and path.name.lower() not in exts):
            continue
        if path.stat().st_size > rule_probe.MAX_FILE_BYTES:
            continue
        rel = str(path.relative_to(group_dir))
        try:
            code = prism.split_streams(path.read_text(encoding="utf-8", errors="ignore"), lang)["code_stream"]
            functions = extractor.splice(code, "")["functions"]
        except Exception:  # a probe reports what it can read; one bad file is not a finding
            continue
        for rule, pattern in patterns.items():
            literal[rule] += sum(1 for _ in pattern.finditer(code))
        for func in functions:
            name = func.get("name") or ""
            if func.get("is_synthetic_slice") or not _IDENT.fullmatch(name):
                continue
            definitions[name].append(rel)
            body = code[func["start_idx"] : func["end_idx"]]
            callers.append((rel, extractor._apply_literal_shield(body, lang), list(func.get("calls_out_to") or [])))
            if (func.get("loc") or 0) > max_loc:
                continue
            own = [m.span() for m in re.finditer(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", body)]
            header = body.split("\n", 1)[0]
            # The span's opening lines: C writes the return type on its own line
            # (`Py_hash_t` then `PyObject_HashNotImplemented(PyObject *v)`), so the
            # name is on line 2 of a correctly aligned span.
            opening = "\n".join(body.split("\n", 3)[:3])
            for rule, pattern in patterns.items():
                hits = [m for m in pattern.finditer(body) if not any(a <= m.start() < b for a, b in own)]
                if not hits:
                    continue
                candidates[candidate_key(group, rel, name, rule)] = {
                    "group": group,
                    "file": rel,
                    "name": name,
                    "rule": rule,
                    "loc": func.get("loc"),
                    "hit": hits[0].group(0)[:60],
                    "method": is_method_definition(lang, header, name),
                    # #3315 features the label pass tests as filters:
                    # branches -- the engine's own branch count; a real wrapper
                    #   performs the behaviour unconditionally.
                    # header_has_name -- the slice's opening lines name the
                    #   function; when it does not, the engine's span is not
                    #   the function's and the hit belongs to other code.
                    "branches": func.get("branch_count", 0) or 0,
                    "header_has_name": bool(re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", opening)),
                    "body": body[:600],
                    "sites": 0,
                    "calling_functions": 0,
                }

    by_name: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for cand in candidates.values():
        by_name[cand["name"]].append(cand)

    unattributed: collections.Counter[str] = collections.Counter()
    for caller_file, shielded, calls_out in callers:
        for callee in set(calls_out) & set(by_name):
            sites = _unqualified_sites(shielded, callee)
            if not sites:
                continue  # every call here is qualified: a method on something else
            same_file = [c for c in by_name[callee] if c["file"] == caller_file]
            if same_file:
                targets = same_file
            elif len(definitions[callee]) == 1:
                targets = by_name[callee]
            else:
                # Once per rule, not once per same-named candidate: the call
                # site is one site whichever definition it would have reached.
                for rule in {c["rule"] for c in by_name[callee]}:
                    unattributed[rule] += sites
                continue
            for cand in targets:
                if cand["method"]:
                    continue  # reachable only through a qualifier
                cand["sites"] += sites
                cand["calling_functions"] += 1

    result = {
        "group": group,
        "lang": lang,
        "literal": {r: literal[r] for r in patterns},
        "unattributed_sites": dict(unattributed),
        "candidates": candidates,
    }
    if lang in PREPROCESSOR_LANGS:
        result["macro_aliases"] = macro_aliases(group_dir, exts, patterns, candidates)
    return result


def macro_aliases(
    group_dir: Path, exts: Any, patterns: dict[str, Any], candidates: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Function-like `#define` aliases per rule, with their call sites (#3324).

    Read from the RAW file, not PRISM's code stream: the macro body is exactly
    what the preprocessor pastes in. An alias is rule-bearing when its body hits
    the rule, or calls a live function candidate of that rule or another alias
    (a closure bounded at `_ALIAS_CLOSURE_DEPTH` rounds).
    """
    texts: dict[str, str] = {}
    for path in sorted(group_dir.rglob("*"), key=lambda p: p.parts):
        if not path.is_file() or (exts and path.suffix.lower() not in exts and path.name.lower() not in exts):
            continue
        if path.stat().st_size > rule_probe.MAX_FILE_BYTES:
            continue
        texts[str(path.relative_to(group_dir))] = path.read_text(encoding="utf-8", errors="ignore")
    definitions: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for rel, text in texts.items():
        for m in _DEFINE.finditer(text):
            definitions[m.group(1)].append((rel, m.group(3).replace("\\\n", " ").strip()))
    out: dict[str, dict[str, Any]] = {}
    for rule, pattern in patterns.items():
        wrappers = {c["name"] for c in candidates.values() if c["rule"] == rule and c["sites"]}
        bearing: dict[str, dict[str, Any]] = {}
        for _ in range(_ALIAS_CLOSURE_DEPTH):
            grew = False
            for name, defs in definitions.items():
                if name in bearing:
                    continue
                for rel, body in defs:
                    via = None
                    if pattern.search(body):
                        via = "primitive"
                    else:
                        via = next((f"via {c}" for c in _CALLED.findall(body) if c in wrappers or c in bearing), None)
                    if via:
                        bearing[name] = {"file": rel, "via": via, "body": body[:120], "sites": 0}
                        grew = True
                        break
            if not grew:
                break
        if bearing:
            rx = re.compile(
                r"(?<![\w$.>])(" + "|".join(map(re.escape, sorted(bearing, key=len, reverse=True))) + r")\s*\("
            )
            for text in texts.values():
                for m in rx.finditer(_DEFINE.sub("", text)):
                    bearing[m.group(1)]["sites"] += 1
        out[rule] = bearing
    return out


def run(langs: Optional[list[str]], rules: tuple[str, ...], max_loc: int) -> dict[str, Any]:
    crucible = rule_probe.CRUCIBLE
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    groups = []
    for lang_dir in sorted(p for p in crucible.iterdir() if p.is_dir()):
        lang = lang_dir.name
        if langs and lang not in langs:
            continue
        definition = LANGUAGE_DEFINITIONS.get(lang)
        if not definition or definition.get("invocation_model") == "positional":
            continue  # no invoke-by-name form, so no wrapper can be called by name
        if not any(hasattr(definition["rules"].get(r), "finditer") for r in rules):
            continue
        for group_dir in sorted((p for p in lang_dir.iterdir() if p.is_dir()), key=lambda p: p.name):
            result = probe_group(lang, group_dir, rules, max_loc, prism, crucible)
            if result["candidates"]:
                groups.append(result)
    return {"crucible": str(crucible), "rules": list(rules), "max_loc": max_loc, "groups": groups}


def all_candidates(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: c for g in data["groups"] for k, c in g["candidates"].items()}


# Candidate filters the label pass scores, each a predicate over one candidate.
FILTERS = {
    "all": lambda c: True,
    "aligned": lambda c: c.get("header_has_name", True),
    "aligned+no_branches": lambda c: c.get("header_has_name", True) and c.get("branches", 0) == 0,
}


def score_filters(data: dict[str, Any], labels: dict[str, Any], max_loc: int) -> None:
    """Labelled precision of each filter at `max_loc`: per candidate and site-weighted,
    strict (`wrapper` only) and lenient (`wrapper` + `conditional`)."""
    cands = all_candidates(data)
    judged = {k: c for k, c in cands.items() if k in labels and c["sites"] and c["loc"] <= max_loc}
    print(f"\nlabelled candidates at max_loc={max_loc}: {len(judged)}")
    print(
        f"{'filter':22} {'kept':>4} {'strict':>7} {'lenient':>8} {'sites kept':>10} {'strict/site':>11} {'recall(site)':>12}"
    )
    wrapper_sites = sum(c["sites"] for k, c in judged.items() if labels[k]["label"] == "wrapper")
    for fname, pred in FILTERS.items():
        kept = {k: c for k, c in judged.items() if pred(c)}
        if not kept:
            continue
        lbl = [labels[k]["label"] for k in kept]
        sites = sum(c["sites"] for c in kept.values())
        w_sites = sum(c["sites"] for k, c in kept.items() if labels[k]["label"] == "wrapper")
        print(
            f"{fname:22} {len(kept):4} {lbl.count('wrapper') / len(kept):7.0%} "
            f"{(lbl.count('wrapper') + lbl.count('conditional')) / len(kept):8.0%} {sites:10} "
            f"{w_sites / max(1, sites):11.0%} {w_sites / max(1, wrapper_sites):12.0%}"
        )


def summarize(data: dict[str, Any], labels: Optional[dict[str, Any]] = None) -> None:
    cands = all_candidates(data)
    print(f"{'rule':20} {'max_loc':>7} {'literal':>8} {'wrappers':>8} {'sites':>6}  labelled precision")
    for rule in data["rules"]:
        lit = sum(g["literal"].get(rule, 0) for g in data["groups"])
        for n in LOC_SWEEP:
            if n > data["max_loc"]:
                continue
            live = [c for c in cands.values() if c["rule"] == rule and c["loc"] <= n and c["sites"]]
            sites = sum(c["sites"] for c in live)
            prec = ""
            if labels:
                judged = [(labels[k]["label"], c["sites"]) for k, c in cands.items() if k in labels and c in live]
                if judged:
                    strict = sum(1 for lbl, _ in judged if lbl == "wrapper") / len(judged)
                    site_w = sum(s for lbl, s in judged if lbl == "wrapper") / max(1, sum(s for _, s in judged))
                    prec = f"strict {strict:.0%} of {len(judged)} labelled, {site_w:.0%} site-weighted"
            print(f"{rule:20} {n:7} {lit:8} {len(live):8} {sites:6}  {prec}")
        aliases = [a for g in data["groups"] for a in g.get("macro_aliases", {}).get(rule, {}).values() if a["sites"]]
        if aliases:
            print(
                f"{rule:20} {'macro':>7} {lit:8} {len(aliases):8} {sum(a['sites'] for a in aliases):6}  (#define aliases)"
            )


def sample_for_labelling(data: dict[str, Any], seed: int, size: int, floor: int) -> list[str]:
    """Every candidate with >= `floor` call sites, plus a seeded random sample of the rest."""
    live = {k: c for k, c in all_candidates(data).items() if c["sites"]}
    heavy = sorted(k for k, c in live.items() if c["sites"] >= floor)
    rest = sorted(k for k in live if k not in heavy)
    random.Random(seed).shuffle(rest)
    return heavy + rest[:size]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", help="comma-separated crucible languages (default: all)")
    ap.add_argument("--repo", type=Path, help="probe one full checkout instead of the crucible (needs --lang)")
    ap.add_argument("--lang", help="the language to probe --repo as")
    ap.add_argument("--rules", default=",".join(DEFAULT_RULES))
    ap.add_argument("--max-loc", type=int, default=max(LOC_SWEEP))
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("--load", type=Path, help="read a previous --json result instead of scanning")
    ap.add_argument("--score", type=Path, help="report labelled precision from this label file")
    ap.add_argument("--sample", type=int, metavar="N", help="print the label-pass sample (N random + every heavy)")
    ap.add_argument("--detail", action="store_true", help="print every live candidate's body")
    args = ap.parse_args()

    if args.load:
        data = json.loads(args.load.read_text(encoding="utf-8"))
    elif args.repo:
        if not args.lang:
            ap.error("--repo needs --lang")
        repo = args.repo.resolve()
        prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
        result = probe_group(args.lang, repo, tuple(args.rules.split(",")), args.max_loc, prism, repo.parent)
        data = {
            "crucible": str(repo.parent),
            "rules": args.rules.split(","),
            "max_loc": args.max_loc,
            "groups": [result],
        }
    else:
        langs = args.langs.split(",") if args.langs else None
        data = run(langs, tuple(args.rules.split(",")), args.max_loc)
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    labels = json.loads(args.score.read_text(encoding="utf-8"))["labels"] if args.score else None
    summarize(data, labels)
    if labels:
        for n in LOC_SWEEP:
            if n <= data["max_loc"]:
                score_filters(data, labels, n)
    if args.sample is not None:
        cands = all_candidates(data)
        for key in sample_for_labelling(data, seed=3313, size=args.sample, floor=20):
            c = cands[key]
            print(f"\n=== {key}  loc={c['loc']} sites={c['sites']} method={c['method']} hit={c['hit']!r}\n{c['body']}")
    elif args.detail:
        for key, c in sorted(all_candidates(data).items()):
            if c["sites"]:
                print(f"\n=== {key}  loc={c['loc']} sites={c['sites']} hit={c['hit']!r}\n{c['body']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
