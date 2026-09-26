"""
Call-graph triage: every missed and every wrong call link, bucketed and ranked
(#3774, epic #3772).

`call_graph_resolution.py` says HOW WELL the engine's call graph matches a
compiler reference. This says WHERE it doesn't, in buckets a fix can target,
biggest first, with a few source lines each -- so choosing the next fix is one
command, not an afternoon of throwaway scripts and reading samples by eye.

RECALL -- every reference edge (caller -> callee) the engine did not link
confidently gets exactly one bucket:
  caller_unmapped            the reference's caller is not an engine function at all
  not_extracted/*            the callee's name is not in the caller's calls_out_to:
    same_name                  it is also the caller's own name (a different function of that name)
    in_string                  the call sits inside a string / template literal
    after_nested_def           the call is past the engine's end of the caller (a nested
                               function cut the caller's span short)
    other
  ambiguous/<step>           named, but only an ambiguous row (receiver/nearest/tie/unseen/overload) --
                             never an edge
  resolved_outside           named, and the engine found no definition in the repo (`none`)
  confident_other_target     named and linked confidently, but to a different definition
  confident_unmapped_target  linked confidently to something the reference has no function for
The buckets add up to (reference edges - edges linked), the gate's recall gap.

PRECISION -- every confident engine call link gets the gate's verdict:
  agree | wrong | external (the reference resolved it only outside the repo) |
  unconfirmed | unmapped_src | unmapped_dst

    python tests/tools/callgraph_triage.py typescript [--samples 3] [--json out.json] [--no-cache]
    python tests/tools/callgraph_triage.py typescript --split resolved_outside   # one bucket, by call shape

A reference is a reference, not ground truth: a bucket is a lead to check against
source before anything is claimed (CLAUDE.md, "Comparative-correctness claims").
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import call_graph_resolution as cgr  # noqa: E402
from callgraph_refs import REFERENCES, corpus_repos, reference_graph  # noqa: E402

# What a bucket usually means, and the issue that fixed or tracks that pattern.
HINTS = {
    "caller_unmapped": "the caller is not extracted as a unit (string-keyed methods, anonymous callbacks, naming)",
    "not_extracted/same_name": "a call to a DIFFERENT function of the caller's own name, dropped like recursion",
    "not_extracted/in_string": "calls inside template-literal interpolation are blanked with the string",
    "not_extracted/after_nested_def": "the caller's span ends where a nested function starts",
    "not_extracted/other": "calls_out_to missed the name: check the detector's call extraction for the site",
    "ambiguous/receiver": "x.m() with an untyped receiver: needs receiver typing (#3693 for python)",
    "ambiguous/nearest": "several definitions, the nearest by path was only a guess",
    "ambiguous/tie": "several definitions, equally near",
    "ambiguous/overload": "several overloads take this many arguments (or none does): the overload is not chosen (#3835)",
    "ambiguous/unseen": "the only definition, but the caller cannot see it (no import) -- often an import gap",
    "resolved_outside": "the engine found no definition: an import it did not follow, or a name it keys differently",
    "confident_other_target": "a confident link to the wrong definition (see the precision table's `wrong`)",
    "confident_unmapped_target": "linked to something with no body or no reference counterpart (#3757's pattern)",
    "wrong": "the reference links this caller to a different function of the same name",
    "external": "the call is a built-in/library method shadowed by a repo method (#3756)",
    "unconfirmed": "the reference has no edge from the caller to that name (often its own blind spot)",
    "unmapped_src": "the engine's caller has no reference counterpart",
    "unmapped_dst": "the engine's target has no reference counterpart (a bodyless signature, #3757)",
}

_FUNCS_SQL = """
SELECT fd.file_path, fn.func_name, fn.start_line, fn.loc, fn.calls_out_to
FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id
"""
# every row, ambiguous ones included (the gate's _LINKS_SQL keeps function targets only)
_ROWS_SQL = """
SELECT sfd.file_path, sfn.func_name, sfn.start_line, c.callee, c.step, c.kind,
       dfd.file_path, dfn.func_name, dfn.start_line
FROM fcall_data c
JOIN function_data sfn ON sfn.id = c.src_func_id
JOIN file_data sfd ON sfd.id = sfn.file_id
LEFT JOIN function_data dfn ON dfn.id = c.dst_func_id
LEFT JOIN file_data dfd ON dfd.id = dfn.file_id
"""


def _in_string(text: str, name: str) -> bool:
    """`name(` occurs on the line only inside a quoted or template literal."""
    hits = [m.start() for m in re.finditer(rf"(?<![\w$]){re.escape(name)}\s*[(<]", text)]
    if not hits:
        return False
    for pos in hits:
        quote = None
        for ch in text[:pos]:
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"`":
                quote = ch
        if quote is None:
            return False  # at least one plain-code occurrence
    return True


class _Source:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, list[str]] = {}

    def line(self, path: str, line: int) -> str:
        if path not in self._cache:
            try:
                self._cache[path] = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                self._cache[path] = []
        lines = self._cache[path]
        return lines[line - 1].strip() if 0 < line <= len(lines) else ""

    def find_call(self, path: str, start: int, end: int, name: str) -> int | None:
        """The first line in [start, end] that calls `name`."""
        pat = re.compile(rf"(?<![\w$]){re.escape(name)}\s*[(<]")
        for ln in range(start, end + 1):
            if pat.search(self.line(path, ln)):
                return ln
        return None


def triage_repo(lang: str, name: str, repo: Path, use_cache: bool = True) -> dict[str, Any]:
    graph, version = reference_graph(lang, repo, use_cache)
    db = cgr._scan(repo)
    conn = sqlite3.connect(db)
    try:
        funcs = conn.execute(_FUNCS_SQL).fetchall()
        rows = conn.execute(_ROWS_SQL).fetchall()
    finally:
        conn.close()
    src = _Source(repo)
    to_ref = lambda p, n, line: cgr._to_pyan(graph.defs, p, n, int(line or 0))  # noqa: E731

    # the engine's functions under the reference's keys
    engine: dict[tuple, tuple[str, int, int, set[str]]] = {}
    for p, n, line, loc, calls in funcs:
        k = to_ref(p, n, line)
        if k is not None and k not in engine:
            start = int(line or 0)
            engine[k] = (p, start, start + max(int(loc or 1), 1) - 1, set(json.loads(calls or "[]")))

    # engine rows per (caller key, callee name); confident mapped call links
    by_pair: dict[tuple, list[tuple]] = collections.defaultdict(list)
    confident: set[tuple] = set()
    precision: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for sp, sn, sl, callee, step, kind, dp, dn, dl in rows:
        if kind not in (None, "call"):
            continue
        ks = to_ref(sp, sn, sl)
        kd = to_ref(dp, dn, dl) if dp else None
        if ks is not None:
            by_pair[(ks, callee)].append((step, kd, dp, dn, dl))
        if step not in cgr.CONFIDENT or not dp:
            continue
        if ks is not None and kd is not None:
            confident.add((ks, kd))
            verdict = cgr._verdict(graph, ks, kd)
        else:
            verdict = "unmapped_src" if ks is None else "unmapped_dst"
        site = src.find_call(sp, int(sl or 0), int(sl or 0) + 400, str(callee)) if verdict != "agree" else None
        precision[verdict].append(
            {"repo": name, "caller": f"{sp}:{sn}", "target": f"{dp}:{dn}@{dl}", "step": step, "site": site}
        )

    recall: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    linked = 0
    for ks, kd in sorted(graph.edges):
        if not kd[1]:
            continue
        if (ks, kd) in confident:
            linked += 1
            continue
        site = (graph.sites.get((ks, kd)) or [None])[0]
        where = {"repo": name, "caller": f"{ks[0]}:{ks[1]}", "callee": f"{kd[0]}:{kd[1]}@{kd[2]}", "site": site}
        fn = engine.get(ks)
        if fn is None:
            bucket = "caller_unmapped"
        elif kd[1] not in fn[3]:
            if kd[1] == ks[1]:
                bucket = "not_extracted/same_name"
            elif site and _in_string(src.line(ks[0], site), kd[1]):
                bucket = "not_extracted/in_string"
            elif site and site > fn[2]:
                bucket = "not_extracted/after_nested_def"
            else:
                bucket = "not_extracted/other"
        else:
            options = by_pair.get((ks, kd[1]), [])
            conf = [o for o in options if o[0] in cgr.CONFIDENT and o[2]]
            if conf:
                bucket = "confident_other_target" if any(o[1] for o in conf) else "confident_unmapped_target"
            elif options and options[0][0] in (*cgr.AMBIGUOUS, "tie"):
                bucket = f"ambiguous/{options[0][0]}"
            else:
                bucket = "resolved_outside"
        recall[bucket].append(where)
    return {
        "repo": name,
        "version": version,
        "reference_edges": sum(1 for e in graph.edges if e[1][1]),
        "linked": linked,
        "recall": recall,
        "precision": precision,
        "sources": src,
    }


def triage(lang: str, use_cache: bool = True) -> dict[str, Any]:
    parts = [triage_repo(lang, name, path, use_cache) for name, path in corpus_repos(lang)]
    out: dict[str, Any] = {
        "lang": lang,
        "reference": REFERENCES[lang].tool,
        "version": ", ".join(sorted({p["version"] for p in parts})),
        "repos": [p["repo"] for p in parts],
        "reference_edges": sum(p["reference_edges"] for p in parts),
        "linked": sum(p["linked"] for p in parts),
        "recall": collections.defaultdict(list),
        "precision": collections.defaultdict(list),
        "_sources": {p["repo"]: p["sources"] for p in parts},
    }
    for p in parts:
        for side in ("recall", "precision"):
            for bucket, items in p[side].items():
                out[side][bucket].extend(items)
    return out


def _excerpt(result: dict[str, Any], item: dict[str, Any]) -> str:
    src: _Source = result["_sources"][item["repo"]]
    path = item["caller"].rsplit(":", 1)[0]
    if item.get("site"):
        return f"`{path}:{item['site']}` `{src.line(path, item['site'])[:110]}`"
    return f"`{item['caller']}`"


def render(result: dict[str, Any], samples: int = 3) -> str:
    total, linked = result["reference_edges"], result["linked"]
    gap = total - linked
    lines = [
        f"## {result['lang']} call-graph triage vs {result['reference']} {result['version']} "
        f"({', '.join(result['repos'])})",
        "",
        f"**Recall:** {total} reference edges, {linked} linked confidently "
        f"({100.0 * linked / total if total else 0:.1f}%). The {gap} not linked, by bucket:",
        "",
        "| bucket | edges | % of reference | usually means |",
        "|---|---|---|---|",
    ]
    ranked = sorted(result["recall"].items(), key=lambda kv: -len(kv[1]))
    for bucket, items in ranked:
        pct = 100.0 * len(items) / total if total else 0
        lines.append(f"| `{bucket}` | {len(items)} | {pct:.1f}% | {HINTS.get(bucket, '')} |")
    judged = sum(len(v) for v in result["precision"].values())
    lines += [
        "",
        f"**Precision:** {judged} confident engine call links, by verdict:",
        "",
        "| verdict | links | usually means |",
        "|---|---|---|",
    ]
    for verdict, items in sorted(result["precision"].items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| `{verdict}` | {len(items)} | {HINTS.get(verdict, '') if verdict != 'agree' else ''} |")
    if samples:
        lines += ["", "### Samples"]
        for bucket, items in ranked:
            lines.append(f"\n**recall `{bucket}`** ({len(items)})")
            for it in items[:samples]:
                lines.append(f"- {it['caller']} -> {it['callee']}: {_excerpt(result, it)}")
        for verdict, items in sorted(result["precision"].items(), key=lambda kv: -len(kv[1])):
            if verdict == "agree":
                continue
            lines.append(f"\n**precision `{verdict}`** ({len(items)})")
            for it in items[:samples]:
                lines.append(f"- {it['caller']} -> {it['target']} ({it['step']}): {_excerpt(result, it)}")
    return "\n".join(lines)


def to_json(result: dict[str, Any], samples: int = 3) -> dict[str, Any]:
    def with_excerpt(item: dict[str, Any]) -> dict[str, Any]:
        # the call site's own source line, so a reader (or the callgraph-triage-scout
        # agent) can classify a sample's shape without opening the corpus
        src: _Source = result["_sources"][item["repo"]]
        path = item["caller"].rsplit(":", 1)[0]
        return {**item, "excerpt": src.line(path, item["site"]) if item.get("site") else ""}

    def side(d):
        return {
            b: {"count": len(v), "hint": HINTS.get(b, ""), "samples": [with_excerpt(i) for i in v[:samples]]}
            for b, v in sorted(d.items(), key=lambda kv: -len(kv[1]))
        }

    return {
        **{k: v for k, v in result.items() if k not in ("recall", "precision", "_sources")},
        "recall": side(result["recall"]),
        "precision": side(result["precision"]),
    }


def call_shape(line: str, name: str) -> tuple[str, str]:
    """(shape, receiver) of the call to `name` on a source line, keyed on the CALLEE --
    `requestedCases.push(...parseCaseValue(v))` is a spread call of parseCaseValue, not a
    call qualified by requestedCases. Shapes: template, spread, constructor, qualified
    (receiver = the chain's head identifier), chained (`).name(`), bare, other."""
    n = re.escape(name)
    m = re.search(rf"(\.\.\.\s*)?(new\s+)?((?:[\w$]+\s*\.\s*)*)(\)\s*\.\s*)?(?<![\w$]){n}\s*[(<`]", line)
    if not m:
        return "other", ""
    spread, new, chain, chained = m.group(1), m.group(2), m.group(3), m.group(4)
    head = chain.split(".")[0].strip() if chain else ""
    before = line[: m.start()]
    if "${" in before and before.rfind("${") > before.rfind("}"):
        return "template", head
    if spread:
        return ("spread-qualified" if head else "spread"), head
    if new:
        return "constructor", head
    if chained:
        return "chained", ""
    if head:
        return "qualified", head
    return "bare", ""


def split(result: dict[str, Any], bucket: str, samples: int = 2) -> str:
    """Every item of one bucket grouped by call_shape, receivers counted -- the
    deterministic version of reading a bucket's samples by eye."""
    items = result["recall"].get(bucket) or result["precision"].get(bucket)
    if not items:
        return f"callgraph_triage: no bucket {bucket!r} (buckets: {sorted({*result['recall'], *result['precision']})})"
    shapes: dict[str, list[tuple[str, dict[str, Any]]]] = collections.defaultdict(list)
    receivers: collections.Counter[str] = collections.Counter()
    for it in items:
        src: _Source = result["_sources"][it["repo"]]
        path = it["caller"].rsplit(":", 1)[0]
        callee = (it.get("callee") or it.get("target") or "").rsplit(":", 1)[-1].split("@")[0]
        line = src.line(path, it["site"]) if it.get("site") else ""
        shape, head = call_shape(line, callee) if line else ("no_site", "")
        shapes[shape].append((line, it))
        if head:
            receivers[f"{shape}:{head}"] += 1
    out = [f"### `{bucket}` by call shape ({len(items)} items)", "", "| shape | items |", "|---|---|"]
    out += [f"| `{k}` | {len(v)} |" for k, v in sorted(shapes.items(), key=lambda kv: -len(kv[1]))]
    out += ["", "| shape:receiver | items |", "|---|---|"]
    out += [f"| `{k}` | {c} |" for k, c in receivers.most_common(15)]
    for k, v in sorted(shapes.items(), key=lambda kv: -len(kv[1])):
        out.append(f"\n**{k}**")
        out += [
            f"- `{it['caller']}` -> `{it.get('callee') or it.get('target')}`: `{line[:110]}`"
            for line, it in v[:samples]
        ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lang", choices=sorted(REFERENCES))
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--split", metavar="BUCKET", help="group one bucket's items by call shape and receiver")
    a = ap.parse_args(argv)
    result = triage(a.lang, use_cache=not a.no_cache)
    # the buckets must account for exactly the recall gap
    unlinked = sum(len(v) for v in result["recall"].values())
    if unlinked != result["reference_edges"] - result["linked"]:
        print(
            f"callgraph_triage: internal error -- buckets hold {unlinked} edges, the gap is "
            f"{result['reference_edges'] - result['linked']}"
        )
        return 1
    print(split(result, a.split, a.samples) if a.split else render(result, a.samples))
    if a.json:
        Path(a.json).write_text(json.dumps(to_json(result, a.samples), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
