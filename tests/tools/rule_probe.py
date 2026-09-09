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
Rule probe: what does one rule match, per language, on the code streams the
engine actually scans?

Every rule-contract session (api #2730, args #2773, state_mutation #2765) and every
single-language rule fix before them (#2654, #2660, #2673, #2674) hand-rolled this
same script: run `LANGUAGE_DEFINITIONS[lang]["rules"][rule]` over the Prism
code stream of every file in a corpus, count the hits, show the matched lines.
This is that script, committed, with the two things the audit table needs on
top: a saved JSON snapshot and a before/after comparison of two snapshots.

USAGE
    # incidence + top matched lines, one language or all of them
    python tests/tools/rule_probe.py state_mutation haskell
    python tests/tools/rule_probe.py state_mutation all --samples 5

    # snapshot before the rule edit, snapshot after, then the audit-table rows
    python tests/tools/rule_probe.py state_mutation all --json /tmp/before.json
    ...edit the rules...
    python tests/tools/rule_probe.py state_mutation all --json /tmp/after.json
    python tests/tools/rule_probe.py state_mutation all --compare /tmp/before.json /tmp/after.json

    # try a candidate regex without editing the registry
    python tests/tools/rule_probe.py state_mutation c --override '(?:^|[;{])[ \\t]*\\w+ *=' --flags M

CORPORA
    Both are scanned by default: the language-crucible real-world corpus
    (LANGUAGE_CRUCIBLE_PATH, default ../language-crucible -- scan a clean
    worktree of the pinned tag, never a checkout with scan residue in it) and the
    keyword-rosetta control corpus (KEYWORD_ROSETTA_PATH, default
    ../keyword-rosetta). --corpus crucible|rosetta picks one.

WHAT IT MEASURES
    Raw rule hits over `Prism.split_streams(...)["code_stream"]` -- comments
    stripped, string literals kept, exactly the text detector.py hands the rule.
    The six comment-stream rules (`dead_code`, `doc`, `ownership`, `planned_debt`,
    `fragile_debt`, `spec_exposure`; detector.comment_analysis) are run over the
    code stream AND the comment stream, because that is what the detector does:
    coding_analysis applies every non-underscore rule to the code stream, then
    comment_analysis adds a second pass over the comments (#2882). `--stream`
    picks one stream explicitly; the default is `auto` (both for those six, code
    for everything else). The per-stream split is in the JSON and the samples.
    NOT the recorded count: scope filters (`_scope_filters`, e.g. matlab's return
    channel) and the per-function slicer run after the regex, so a language with a
    filter reads higher here than in a manifest. That is the right thing for a
    rule audit (it isolates the regex) and the wrong thing for a corpus bless
    (use tests/tools/rosetta_audit.py for that).

Run it from a worktree with PYTHONPATH pointing at that worktree, so the registry
you probe is the one you are editing (the sibling .venv is an editable install of
whatever the primary checkout has checked out).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def _sibling(env: str, name: str) -> Path:
    """The corpus checkout: $env, else ../<name> from the checkout, else ../../<name> from a worktree."""
    if os.environ.get(env):
        return Path(os.environ[env])
    for base in (REPO_ROOT.parent, REPO_ROOT.parent.parent):
        if (base / name / "data").is_dir():
            return base / name
    return REPO_ROOT.parent / name


CRUCIBLE = _sibling("LANGUAGE_CRUCIBLE_PATH", "language-crucible") / "data"
ROSETTA = _sibling("KEYWORD_ROSETTA_PATH", "keyword-rosetta") / "data"
# registry key -> corpus directory name, where they differ
CORPUS_DIR = {"objectivec": "objective-c"}
MAX_FILE_BYTES = 2_000_000
# detector.comment_analysis's list: these rules read the comment surface too.
COMMENT_STREAM_RULES = frozenset({"dead_code", "doc", "ownership", "planned_debt", "fragile_debt", "spec_exposure"})


def streams_for(rule_name: str, stream: str) -> tuple[str, ...]:
    if stream == "auto":
        stream = "both" if rule_name in COMMENT_STREAM_RULES else "code"
    return ("code_stream", "comment_stream") if stream == "both" else (f"{stream}_stream",)


def _extensions(lang: str) -> set[str]:
    """The suffixes AND the exact file names a language claims (lower-cased).

    #2851: `makefile` reaches its corpus files by exact name (`Makefile`, `Kbuild`),
    not by suffix -- filtering on `extensions` alone skipped every one of them and
    reported the crucible as `--` for a language the golden master does scan.
    """
    defn = LANGUAGE_DEFINITIONS[lang]
    exts = defn.get("extensions") or defn.get("file_extensions") or []
    names = defn.get("exact_matches") or []
    return {e.lower() for e in exts} | {n.lower() for n in names}


def corpus_files(lang: str, corpus: str):
    exts = _extensions(lang)
    d = CORPUS_DIR.get(lang, lang)
    roots = []
    if corpus in ("crucible", "both"):
        roots.append(("crucible", CRUCIBLE / d))
    if corpus in ("rosetta", "both"):
        roots.append(("rosetta", ROSETTA / d))
    for name, root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or ".git" in p.parts or p.stat().st_size > MAX_FILE_BYTES:
                continue
            if exts and p.suffix.lower() not in exts and p.name.lower() not in exts:
                continue
            yield name, root, p


def compile_override(pattern: str, flags: str) -> re.Pattern:
    fl = 0
    for ch in flags.upper():
        fl |= {"I": re.I, "M": re.M, "S": re.S, "X": re.X}[ch]
    return re.compile(pattern, fl)


def probe(
    rule_name: str,
    lang: str,
    corpus: str,
    samples: int,
    override: re.Pattern | None,
    prism: Prism,
    stream: str = "auto",
):
    rule = override or LANGUAGE_DEFINITIONS[lang]["rules"].get(rule_name)
    if rule is None or not hasattr(rule, "finditer"):
        return None
    streams = streams_for(rule_name, stream)
    per: dict[str, dict] = {}
    for name, root, path in corpus_files(lang, corpus):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        split = prism.split_streams(src, lang)
        c = per.setdefault(
            name,
            {
                "files": 0,
                "hits": 0,
                "by_stream": dict.fromkeys(streams, 0),
                "by_file": {},
                "samples": collections.Counter(),
            },
        )
        c["files"] += 1
        rel = str(path.relative_to(root))
        for sname in streams:
            text = split[sname]
            hits = list(rule.finditer(text))
            c["hits"] += len(hits)
            c["by_stream"][sname] += len(hits)
            if hits:
                c["by_file"][rel] = c["by_file"].get(rel, 0) + len(hits)
            for m in hits:
                ls = text.rfind("\n", 0, m.start()) + 1
                le = text.find("\n", m.end())
                line = text[ls : len(text) if le < 0 else le].strip()
                tag = "" if len(streams) == 1 else f"{sname[:4]} "
                c["samples"][(tag + m.group(0).strip()[:40], line[:120])] += 1
                # --diff-lines (#2916) reads these: every matched span with its
                # 1-based line number, so two snapshots of the SAME corpus under
                # different rule candidates can be diffed line-by-line. Line
                # numbers are stable across snapshots because the corpus doesn't
                # change between them -- only the rule does.
                c.setdefault("lines", {}).setdefault(rel, []).append(
                    [text.count("\n", 0, m.start()) + 1, m.group(0)[:200]]
                )
    for c in per.values():
        c["samples"] = [(tok, line, n) for (tok, line), n in c["samples"].most_common(samples)]
    return per


def print_probe(lang: str, per: dict | None, samples: int) -> None:
    if per is None:
        print(f"{lang:16s} rule is None")
        return

    def _cell(v: dict) -> str:
        by = v.get("by_stream") or {}
        split = f" ({', '.join(f'{k[:4]} {n}' for k, n in by.items())})" if len(by) > 1 else ""
        return f"{v['hits']}/{v['files']}f{split}"

    summary = "  ".join(f"{k}:{_cell(v)}" for k, v in per.items())
    print(f"{lang:16s} {summary}")
    for k, v in per.items():
        for tok, line, n in v["samples"][:samples]:
            print(f"      [{k}] x{n:<4d} {tok!r:24s} | {line}")


def compare(before: dict, after: dict, langs: list[str]) -> None:
    print("| language | crucible | keyword-rosetta |")
    print("|---|---|---|")
    for lang in langs:
        b, a = before.get(lang), after.get(lang)
        if a is None and b is None:
            print(f"| `{lang}` | rule is `None` | n/a |")
            continue

        def cell(corpus: str, b=b, a=a) -> str:
            hb = (b or {}).get(corpus, {}).get("hits")
            ha = (a or {}).get(corpus, {}).get("hits")
            if hb is None and ha is None:
                return "--"
            return f"{hb} -> {ha}" if hb != ha else f"{ha}"

        print(f"| `{lang}` | {cell('crucible')} | {cell('rosetta')} |")


def _context_lines(lang: str, rel: str, lineno: int, n: int) -> list[str]:
    """±n source lines around lineno, re-read from whichever corpus holds rel (best effort)."""
    d = CORPUS_DIR.get(lang, lang)
    for root in (CRUCIBLE / d, ROSETTA / d):
        p = root / rel
        if p.is_file():
            try:
                src = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return []
            lo, hi = max(0, lineno - 1 - n), min(len(src), lineno + n)
            return [f"{'>' if i == lineno - 1 else ' '} {i + 1:5d} {src[i]}" for i in range(lo, hi)]
    return []


def diff_lines(before: dict, after: dict, langs: list[str], context: int) -> int:
    """#2916: list lost and gained matched lines per corpus, with counts.

    The #2907 session wrote this twice by hand; its first rule candidate lost 21
    Doom K&R definitions that only this listing showed. Keyed on
    (file, lineno, matched text) as a multiset -- a line matching twice under one
    rule and once under the other shows up. Multi-line matches print in full
    (their span IS the context); --context N adds N surrounding source lines
    re-read from the corpus when it is checked out.
    """
    total_lost = total_gained = 0
    for lang in langs:
        for corpus in ("crucible", "rosetta"):
            b = ((before.get(lang) or {}).get(corpus) or {}).get("lines", {})
            a = ((after.get(lang) or {}).get(corpus) or {}).get("lines", {})
            bc: collections.Counter = collections.Counter(
                (rel, ln, txt) for rel, ms in b.items() for ln, txt in ms
            )
            ac: collections.Counter = collections.Counter(
                (rel, ln, txt) for rel, ms in a.items() for ln, txt in ms
            )
            lost, gained = bc - ac, ac - bc
            if not lost and not gained:
                continue
            total_lost += sum(lost.values())
            total_gained += sum(gained.values())
            print(f"\n{lang} / {corpus}: -{sum(lost.values())} lost, +{sum(gained.values())} gained")
            for label, bag in (("LOST", lost), ("GAINED", gained)):
                for (rel, ln, txt) in sorted(bag):
                    n = bag[(rel, ln, txt)]
                    mark = f" x{n}" if n > 1 else ""
                    if "\n" in txt:
                        print(f"  {label}{mark} {rel}:{ln} (multi-line match)")
                        for tl in txt.splitlines():
                            print(f"      | {tl}")
                    else:
                        print(f"  {label}{mark} {rel}:{ln}: {txt.strip()[:160]}")
                    if context:
                        for cl in _context_lines(lang, rel, ln, context):
                            print(f"      {cl}")
    if total_lost == 0 and total_gained == 0:
        print("no matched-line movement between the snapshots")
    else:
        print(f"\ntotal: -{total_lost} lost, +{total_gained} gained")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rule")
    ap.add_argument("lang", help="a registry key, or `all`")
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument(
        "--stream",
        choices=("auto", "code", "comment", "both"),
        default="auto",
        help="which Prism stream(s) to run the rule over; auto = both for the comment-stream rules, code otherwise",
    )
    ap.add_argument("--samples", type=int, default=6, help="matched lines to show per corpus (most frequent first)")
    ap.add_argument("--override", help="probe this regex instead of the registry's rule")
    ap.add_argument("--flags", default="", help="flags for --override, e.g. IM")
    ap.add_argument("--json", help="write the per-language snapshot here")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="print audit-table rows from two snapshots")
    ap.add_argument(
        "--diff-lines",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="list lost and gained matched LINES between two --json snapshots (#2916)",
    )
    ap.add_argument("--context", type=int, default=0, help="source lines of context around each --diff-lines entry")
    args = ap.parse_args(argv)

    langs = sorted(LANGUAGE_DEFINITIONS) if args.lang == "all" else [args.lang]
    if args.compare:
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        compare(before, after, langs)
        return 0
    if args.diff_lines:
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.diff_lines)
        return diff_lines(before, after, langs, args.context)

    override = compile_override(args.override, args.flags) if args.override else None
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    out: dict[str, dict | None] = {}
    for lang in langs:
        per = probe(args.rule, lang, args.corpus, args.samples, override, prism, args.stream)
        out[lang] = per
        print_probe(lang, per, args.samples)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"snapshot written: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
