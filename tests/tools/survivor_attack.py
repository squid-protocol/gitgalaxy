#!/usr/bin/env python3
"""Attack a surviving det-port mutant before excusing it (#4628).

A survivor means no test tells the mutant from the port. That is a claim about the TESTS until shown otherwise, so the
first move is an input that kills it, not a verdict. This tool makes the attack one command and leaves the record
`det_mutation.py state` asks for.

    python tests/tools/survivor_attack.py next [CASE ...] [--limit 20]        # the likeliest wrong verdicts first
    python tests/tools/survivor_attack.py facts CASE --work DIR               # what the port and the COBOL settle
    python tests/tools/survivor_attack.py packet CASE ID --work DIR           # everything needed to attack one mutant
    python tests/tools/survivor_attack.py try CASE ID[,ID...] --inputs F.json --work DIR   # run the attack
        [--as SIBLING]                                                        # ... entering it as a sibling case does
    python tests/tools/survivor_attack.py lint [CASE ...]                     # stated reasons that are not reasons

`facts` and `try` write DIR/attempts.json; `det_mutation.py state CASE TRIAGE.json --attempts DIR/attempts.json` refuses
an `equivalent` / `unreachable` verdict with no attempt behind it. The model proposes inputs and never an expected
result: the COBOL oracle decides, as in tests/tools/strengthen.py.

A CALL or CICS case's inputs are CALLs or scenarios, and the trial case holds only the new ones. A batch case is one
job step, so its inputs change that step (BATCH_FORMAT): a new record of an input dataset, new values for a `@generate`
dataset's fields, another SYSIN or PARM, or a fault run. The trial is the committed step with those changes; a mutant
it kills is told apart by them, since the committed step already ran it and saw nothing.

`try` proves the case's det port on the new inputs alone, then each mutant on the same inputs:
  killed      the port is equal and the mutant differs: the input belongs in case.json;
  survived    both are equal: this input did not separate them;
  port-differs the port itself differs from the COBOL on the input: a real translator or harness finding, stop and report;
  refused     the oracle refused the input: no information, try another;
  stillborn   the mutant does not compile.

Runs on the box, never in CI: a proof is one Docker oracle and one JVM. Reading a stated verdict needs nothing else.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shlex
import sys
import time
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import det_mutation as dm  # noqa: E402

CONTEXT = 15  # lines of Java each side of the mutant
ENTRY_POINTS = ("runTask", "runProgram", "runBatch", "handleTransaction", "handleLink", "handleCall", "main")
# what each shape of Java line usually needs: the first thing to try
HINTS = (
    (re.compile(r"eibresp|respond|\bresp\b", re.I),
     "A response store: plan a `faults` entry so a command answers a condition, then look for a later IF on the value."),
    (re.compile(r"linkArea|caBack|\braw\b|commarea", re.I),
     ("COMMAREA bytes: the program can be entered by XCTL or LINK from another program. Try a `{\"hex\": ...}` field "
      "value and a longer or shorter area than the layout.")),
    (re.compile(r'"[^"]*"\.|\.contains|indexOf|tally|inspect', re.I),
     "A text scan: try a value that holds the searched text. Install values such as URIMAP paths are inputs too."),
    (re.compile(r"\bif\b|\bwhile\b"),
     "A condition: find the boundary value that makes the original and the mutant take different branches."),
    (re.compile(r"length|\blen\b|maxlength", re.I),
     "A length: try exactly the limit, one over it, and empty."),
)  # fmt: skip
_METHOD = re.compile(r"(?m)^    (?:public|private|protected)[^;{=\n]*?\b(\w+)\(")
_CALL = re.compile(r"(?:\b(\w+)\.)?\b(\w+)\s*\(")  # (receiver, name)
_CONSTANT = re.compile(r"\bstatic final [\w<>\[\], ]+\s+(\w+)\s*=")


# ---- what the port itself settles -------------------------------------------------------------------------------
def methods(text: str) -> dict[str, list[tuple[int, int]]]:
    """{method name: [(first line, last line), ...]}: every overload, from each signature to its closing brace."""
    import mutation as mu

    mask, _ = mu.code_mask(text)
    out: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    for m in _METHOD.finditer(text):
        at = next((k for k in range(m.end(), len(text)) if mask[k] and text[k] == "{"), None)
        if at is None or text.find(";", m.end(), at) != -1:
            continue
        depth, end = 0, at
        for k in range(at, len(text)):
            if mask[k] and text[k] == "{":
                depth += 1
            elif mask[k] and text[k] == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        out[m.group(1)].append((text.count("\n", 0, m.start()) + 1, text.count("\n", 0, end) + 1))
    return dict(out)


def enclosing(spans: dict[str, list[tuple[int, int]]], line: int) -> str | None:
    return next((n for n, ss in spans.items() for a, b in ss if a <= line <= b), None)


def live_methods(text: str) -> set[str]:
    """The methods any entry point of the program reaches, following calls by name (an overload counts as its name,
    so this errs toward live). The roots are the program's entry points, every public method included: code a test
    never calls is not dead code. That is the difference between `unreachable` and a case gap."""
    spans = methods(text)
    lines = text.splitlines()
    body = {n: "\n".join("\n".join(lines[a - 1 : b]) for a, b in ss) for n, ss in spans.items()}
    public = {m.group(1) for m in _METHOD.finditer(text) if m.group(0).lstrip().startswith("public")}
    live = {n for n in spans if n in ENTRY_POINTS or n in public}
    todo = list(live)
    while todo:
        for receiver, name in _CALL.findall(body.get(todo.pop(), "")):
            # `Cobol.store(` is the runtime's method, not the port's private store(): a capitalised receiver is a
            # class. Any other receiver counts, so an unsure call keeps a method live
            if name in spans and name not in live and not receiver[:1].isupper():
                live.add(name)
                todo.append(name)
    return live


def port_fact(text: str, mutant: dict[str, Any]) -> dict[str, str] | None:
    """What the port's text alone settles about a mutant, or None. `result` is one of `dm.ATTACK_SETTLED`."""
    spans = methods(text)
    owner = enclosing(spans, int(mutant["line"]))
    if owner and owner not in live_methods(text):
        return {"result": "no-entry-path", "fact": f"{owner}() is reached from no entry point of the program"}
    constant = _CONSTANT.search(mutant.get("before") or "")
    if constant and len(re.findall(rf"\b{re.escape(constant.group(1))}\b", text)) == 1:
        return {"result": "constant-unused", "fact": f"{constant.group(1)} is declared and never read"}
    for infra in (local_unread, never_populated, store_dominates_read, subfield_unset):
        fact = infra(text, spans, mutant)
        if fact:
            return fact
    return None


# ---- generated infrastructure the port's text settles (#7955): four shapes, each conservative (any doubt -> None) ----
_PUT = re.compile(r'^\s*(\w+)\.put\("[^"]*", Cobol\.text\(\w+, CS\)\);\s*$')
_CLEAR = re.compile(r"^\s*(\w+)\.clear\(\);\s*$")
_STORE = re.compile(r"^\s*(f\d+_\w+) = -?\w+L?;\s*$")
_SUBFIELDS = re.compile(r'DetCics\.subfields\((\w+), "(\w+)", (\w+), (\w+), (\w+), (\w+), CS\);')
_FIELD_LINE = re.compile(r"^\s*private final Field (\w+) = Field\.(\w+)\((\w+), (\d+), (\d+)")
_LITERAL = re.compile(r'"[^"]*"')
_MAP_USES = r"\.(?:get|clear|containsKey|isEmpty|size)\("


def _comment_or(pattern: re.Pattern[str] | None, after: str) -> bool:
    """The mutant's line is deleted (commented out) or still has the shape `pattern` recognises."""
    a = after.strip()
    return a.startswith("/*") or (pattern is not None and pattern.match(after) is not None)


def _span(spans: dict[str, list[tuple[int, int]]], line: int) -> tuple[int, int] | None:
    return next(((a, b) for ss in spans.values() for a, b in ss if a <= line <= b), None)


def _word(name: str, line: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", line) is not None


def local_unread(text: str, spans: dict[str, list[tuple[int, int]]], mutant: dict[str, Any]) -> dict[str, str] | None:
    """`valuesN.put("X", Cobol.text(f, CS));` into a local map the rest of its method never reads or passes on (the
    MAPONLY send ignores its field values): the line changes nothing any input sees."""
    m = _PUT.match(mutant.get("before") or "")
    where = _span(spans, int(mutant["line"]))
    if not m or not where or not _comment_or(_PUT, mutant.get("after") or ""):
        return None
    var = m.group(1)
    body = text.splitlines()[where[0] - 1 : where[1]]
    decl = re.compile(rf"java\.util\.Map<[^>]*>\s+{var}\s*=")
    if not any(decl.search(ln) for ln in body):
        return None
    if any(_word(var, ln) and not decl.search(ln) and not (_PUT.match(ln) and _PUT.match(ln).group(1) == var) for ln in body):  # type: ignore[union-attr]  # fmt: skip
        return None
    return {"result": "local-unread", "fact": f"{var} is a local map only ever put into: nothing reads it or passes it on"}


def never_populated(text: str, spans: dict[str, list[tuple[int, int]]], mutant: dict[str, Any]) -> dict[str, str] | None:
    """`X.clear();` or `X.get("lit")` on a map field nothing ever puts into (no HANDLE CONDITION / READ UPDATE in the
    program): an empty map clears to empty and answers null for any key."""
    before, after = mutant.get("before") or "", mutant.get("after") or ""
    clear = _CLEAR.match(before)
    if clear:
        var, shape = clear.group(1), None
    else:
        got = re.search(r'\b(\w+)\.get\("[^"]*"\)', before)
        if not got or _LITERAL.sub('""', before) != _LITERAL.sub('""', after):
            return None  # only the key literal may differ
        var, shape = got.group(1), True
    if shape is None and not _comment_or(None, after):
        return None
    decl = re.compile(rf"^\s*private final java\.util\.Map<[^>]*>\s+{var}\s*=\s*new java\.util\.\w+<>\(\);")
    lines = text.splitlines()
    if sum(1 for ln in lines if decl.match(ln)) != 1:
        return None
    for ln in lines:
        if decl.match(ln):
            continue
        for hit in re.finditer(rf"\b{var}\b", ln):
            if not re.match(_MAP_USES, ln[hit.end() :]):
                return None
    return {"result": "never-populated", "fact": f"{var} is a map nothing puts into: clear() and get() see it empty"}


def _depth_starts(text: str) -> list[int]:
    """The brace depth at the start of each line (code only: strings and comments do not count)."""
    import mutation as mu  # noqa: PLC0415

    mask, _ = mu.code_mask(text)
    out, depth = [], 0
    for ln_start, ln in zip(_line_starts(text), text.splitlines(), strict=False):
        out.append(depth)
        for k, ch in enumerate(ln):
            if mask[ln_start + k] and ch == "{":
                depth += 1
            elif mask[ln_start + k] and ch == "}":
                depth -= 1
    return out


def _line_starts(text: str) -> list[int]:
    starts, at = [], 0
    for ln in text.splitlines(keepends=True):
        starts.append(at)
        at += len(ln)
    return starts


def store_dominates_read(text: str, spans: dict[str, list[tuple[int, int]]], mutant: dict[str, Any]) -> dict[str, str] | None:
    """`NAME = literal;` (an initialiser) of a primitive scalar field whose every read sits in a method that stores NAME
    first, at the top level of its body, in a line the mutant does not touch: the initial value is never read."""
    m = _STORE.match(mutant.get("before") or "")
    if not m or not _comment_or(_STORE, mutant.get("after") or ""):
        return None
    name, at = m.group(1), int(mutant["line"])
    lines = text.splitlines()
    decl = re.compile(rf"^\s*private (?:long|int|short|byte|double|boolean) {name};")
    if sum(1 for ln in lines if decl.match(ln)) != 1:
        return None
    depth = _depth_starts(text)
    stores, reads = [], []
    for i, ln in enumerate(lines, 1):
        if not _word(name, ln) or decl.match(ln):
            continue
        store = re.match(rf"^\s*{name} = ", ln)
        (stores if store else reads).append(i)
        if store and len(re.findall(rf"\b{name}\b", ln)) > 1:
            reads.append(i)  # the right-hand side reads it too
    for r in reads:
        where = _span(spans, r)
        if not where or "->" in lines[r - 1]:
            return None
        if not any(where[0] < s < r and s != at and depth[s - 1] == 2 and "->" not in lines[s - 1] for s in stores):
            return None
    return {"result": "store-dominates-read", "fact": f"every read of {name} follows a top-level store of it in its own method; the initial value is never read"}  # fmt: skip


def _field_bytes(kind: str, size: int) -> int | None:
    """Bytes a Field declaration covers: `size` is the length (alphanumeric / group) or the digits (binary)."""
    if kind in ("alphanumeric", "group"):
        return size
    if kind == "binary":
        return 2 if size <= 4 else 4 if size <= 9 else 8
    return None


def _image(text: str, storage: str) -> bytes | None:
    import base64  # noqa: PLC0415

    m = re.search(rf'IMAGE_{storage} = Base64\.getDecoder\(\)\.decode\((?:String\.join\(""\s*,)?((?:\s*"[A-Za-z0-9+/=]*",?)+)\s*\)', text)
    if not m:
        return None
    return base64.b64decode("".join(re.findall(r'"([A-Za-z0-9+/=]*)"', m.group(1))))


def subfield_unset(text: str, spans: dict[str, list[tuple[int, int]]], mutant: dict[str, Any]) -> dict[str, str] | None:
    """A mutant of the item-name literal of `DetCics.subfields(sub, "NAME", L, A, C, H, CS)`: the call registers a cursor
    (L = -1) or an attribute / colour / highlight byte (not 0x00 or a space) under NAME. It changes nothing when no L
    or A can hold those: the only writers of the items (and of every field overlapping them) are typed / place (which
    store a length of 0 or more), and the zero fills of the record, and the record's initial image holds neither."""
    before, after = mutant.get("before") or "", mutant.get("after") or ""
    call = _SUBFIELDS.search(before)
    if not call or not (_comment_or(None, after) or _LITERAL.sub('""', before) == _LITERAL.sub('""', after)):
        return None
    items = [v for v in call.groups()[2:] if v != "null"]
    lines = text.splitlines()
    decls: dict[str, tuple[str, str, int, int]] = {}
    for ln in lines:
        d = _FIELD_LINE.match(ln)
        if d:
            decls[d.group(1)] = (d.group(3), d.group(2), int(d.group(4)), int(d.group(5)))
    if any(i not in decls for i in items) or len({decls[i][0] for i in items}) != 1:
        return None
    storage = decls[items[0]][0]
    for s, kind, off, size in decls.values():
        if s == storage and _field_bytes(kind, size) is None:
            return None  # a kind on this storage this does not read: say nothing
    decls = {n: (s, k, off, _field_bytes(k, size) or 0) for n, (s, k, off, size) in decls.items()}
    length_item = items[0] if call.group(3) != "null" else None
    ranges = {i: (decls[i][2], decls[i][2] + decls[i][3]) for i in items}
    for n, (s, _, off, size) in decls.items():
        if s != storage:
            continue
        overlap = any(off < hi and lo < off + size for lo, hi in ranges.values())
        if not overlap:
            continue
        for ln in lines:
            if not _word(n, ln) or ln.lstrip().startswith(f"private final Field {n} = "):
                continue
            zero = re.escape(n)
            ok = (
                re.search(rf"Cobol\.moveFigurative\(Figurative\.LOW_VALUES, {zero}, CS\);", ln)
                or re.search(rf"Arrays\.fill\({zero}\.storage\(\)\.bytes, {zero}\.offset\(\), {zero}\.offset\(\) \+ {zero}\.length\(\), \(byte\) 0\);", ln)  # fmt: skip
                or _SUBFIELDS.search(ln)
                or (n == length_item and re.search(rf"(?:DetCics\.typed|DetJustify\.place)\(\w+, {zero},", ln))
            )
            if not ok:
                return None
    # the storage itself: only the field declarations and the initial image copy touch it
    arraycopy = re.compile(rf"System\.arraycopy\(IMAGE_{storage}, 0, {storage}\.bytes, 0, IMAGE_{storage}\.length\);")
    for ln in lines:
        if _word(storage, ln) and not _FIELD_LINE.match(ln) and not arraycopy.search(ln) and f"new Storage(IMAGE_{storage}.length)" not in ln:  # fmt: skip
            return None
    img = _image(text, storage)
    if img is None:
        return None
    fill = collections.Counter(img).most_common(1)[0][0]
    if fill not in (0x20, 0x40):
        return None  # the image's own space is not one this reads
    for i in items:
        lo, hi = ranges[i]
        cell = img[lo:hi]
        if i == length_item and cell == b"\xff" * len(cell):
            return None
        if i != length_item and any(b not in (0, fill) for b in cell):
            return None
    return {"result": "subfield-unset", "fact": f"{', '.join(items)}: never holds a cursor (-1) or an attribute byte on any path; the name registers nothing"}  # fmt: skip


# ---- the likeliest wrong verdicts -------------------------------------------------------------------------------
def suspicion(entry: dict[str, Any], shared: int) -> tuple[int, list[str]]:
    """(score, why) for a stated verdict: how much it deserves an attack first. `shared`: entries with this reason."""
    score, why = 0, []
    reason = str(entry.get("reason") or "")
    if entry.get("verdict") not in dm.ACCOUNTED:
        return 0, []
    for problem in dm.reason_problems(entry["verdict"], reason):
        score, why = score + 3, [*why, problem]
    if dm.VAGUE_REASON.search(reason):
        score, why = score + 2, [*why, "the reason could be said of any line"]
    if entry.get("op") == "DEL" and re.search(r"eibresp|respond|\bresp", str(entry.get("before")), re.I):
        score, why = score + 2, [*why, "deletes a response store: a later IF may read the stale value"]
    if re.search(r"linkArea|caBack|\braw\b", str(entry.get("before"))):
        score, why = score + 2, [*why, "touches the COMMAREA bytes: another program can enter here"]
    if shared >= 20:
        score, why = score + 1, [*why, f"one reason shared by {shared} survivors"]
    if not entry.get("tried"):
        score, why = score + 1, [*why, "no attack on record"]
    return score, why


def ranked(survivors: dict[str, list[dict[str, Any]]], cases: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    for case, entries in sorted(survivors.items()):
        if cases and case not in cases:
            continue
        counts = collections.Counter(str(e.get("reason"))[:60] for e in entries)
        for e in entries:
            score, why = suspicion(e, counts[str(e.get("reason"))[:60]])
            if score:
                out.append({"case": case, "id": e["id"], "score": score, "verdict": e["verdict"], "why": why})
    return sorted(out, key=lambda r: (-r["score"], r["case"], r["id"]))


# ---- the attack ---------------------------------------------------------------------------------------------------
_NO_BUILD = re.compile(r"maven-compiler-plugin|COMPILATION ERROR|release version \d+ not supported|BUILD FAILURE")


def judge(base: dict[str, Any], mutant: dict[str, Any]) -> str:
    """The attack's result from the proof of the port and the proof of the mutant on the same inputs."""
    report = base.get("report") or {}
    if base["verdict"] in ("error", "timeout") or report.get("refused"):
        return "refused"
    if report.get("java_failed") and _NO_BUILD.search(str(report.get("feedback") or "")):
        return "refused"  # the committed port did not compile here (a JDK, a Maven): the box, not the input
    if base["verdict"] != "proven":
        return "port-differs"
    return {"proven": "survived", "refuted": "killed", "timeout": "killed"}.get(mutant["verdict"], "refused")


def attack_case(case: dict[str, Any], proposals: list[dict[str, Any]], ca_names: set[str] | None) -> dict[str, Any]:
    """The case with only `proposals` as its inputs. Their extra keys pass through: the harness knows more scenario
    fields than the model's format (a WEB body, a clock); `targets` is the model's note and goes."""
    import strengthen as st

    taken = {e["name"] for e in st.entries(case)}
    kept = []
    for p in proposals:
        bad = st.validate(case, p, taken, ca_names)
        if bad:
            raise SystemExit(f"{p.get('name')}: {bad}")
        taken.add(p["name"])
        kept.append({k: v for k, v in p.items() if k != "targets"})
    out = json.loads(json.dumps(case))
    out[st.KINDS[case["kind"]]] = kept
    return out


BATCH_FORMAT = (
    'A batch case is one job step, and each input changes it. Every input has a "name" (kebab-case), a "why" (one '
    'sentence) and optional "targets" (mutant ids), plus exactly one of:\n'
    '- a new record: "dataset": DD, "based_on": the number of an existing record of that dataset to copy, "set": '
    "{FIELD: value} (DISPLAY fields only; a keyed dataset needs a key no record has). Every new record goes into the "
    "same run.\n"
    '- generated data: "generate": {DD: {"fields": {FIELD: {"values": [...]}}, "records": N}} for a dataset whose '
    'input is `@generate`: the named fields\' generator specs are replaced, "records" is optional.\n'
    '- "sysin": the SYSIN text, or "parm": the PARM text, replacing the case\'s (one of each per try).\n'
    '- a fault run: "fault": {"plan": [{"dd": DD, "op": "OPEN" | "READ" | "WRITE" | ..., "nth": 1, "status": '
    '"NN"}]}, the same shape as the case\'s `faults`: run as its own run beside the main one.'
)
_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
_BATCH_KINDS = ("dataset", "generate", "sysin", "parm", "fault")


def batch_trial(case: dict[str, Any], corpus: Path, proposals: list[dict[str, Any]], work: Path) -> dict[str, Any]:
    """The batch case `case` changed by `proposals` (BATCH_FORMAT): records appended, generator specs, SYSIN, PARM,
    and only the proposed fault runs. SystemExit names the first malformed input."""
    import strengthen as st

    if not isinstance(proposals, list) or not proposals:
        raise SystemExit("INPUTS.json: a JSON array of at least one input")
    out = json.loads(json.dumps(case))
    taken: set[str] = set()
    added: dict[str, list[bytes]] = {}
    faults: list[dict[str, Any]] = []
    inputs: dict[str, Any] | None = None
    for p in proposals:
        name = p.get("name") if isinstance(p, dict) else None
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise SystemExit(f"{name!r}: every input needs a kebab-case `name`")
        if name in taken:
            raise SystemExit(f"{name}: named twice")
        taken.add(name)
        kinds = [k for k in _BATCH_KINDS if k in p]
        if len(kinds) != 1:
            raise SystemExit(f"{name}: give exactly one of {', '.join(_BATCH_KINDS)} (has {kinds or 'none'})")
        kind = kinds[0]
        if kind == "dataset":
            inputs = st.batch_inputs(case, corpus) if inputs is None else inputs
            rec, bad = st.build_record(case, inputs, p)
            if bad or rec is None:
                raise SystemExit(f"{name}: {bad}")
            for k in inputs[p["dataset"]]["spec"].get("keys") or []:
                key = rec[k["offset"] : k["offset"] + k["length"]]
                if any(r[k["offset"] : k["offset"] + k["length"]] == key for r in added.get(p["dataset"], [])):
                    raise SystemExit(f"{name}: another new record of {p['dataset']} has the same key")
            added.setdefault(p["dataset"], []).append(rec)
        elif kind == "generate":
            if not isinstance(p["generate"], dict) or not p["generate"]:
                raise SystemExit(f'{name}: `generate` is {{DD: {{"fields": {{...}}}}}}')
            for dd, over in p["generate"].items():
                spec = out["datasets"].get(dd) or {}
                if spec.get("input") != "@generate":
                    raise SystemExit(f"{name}: {dd} is not a `@generate` dataset of the case")
                if not isinstance(over, dict) or set(over) - {"fields", "records"}:
                    raise SystemExit(f"{name}: {dd}: only `fields` and `records` can change")
                gen = spec["generate"]
                gen.setdefault("fields", {}).update(over.get("fields") or {})
                if "records" in over:
                    if not isinstance(over["records"], int) or over["records"] < 1:
                        raise SystemExit(f"{name}: {dd}: `records` is a count of at least 1")
                    gen["records"] = over["records"]
        elif kind in ("sysin", "parm"):
            if f"_{kind}" in taken:
                raise SystemExit(f"{name}: one `{kind}` per try: a step reads one")
            taken.add(f"_{kind}")
            if not isinstance(p[kind], str):
                raise SystemExit(f"{name}: `{kind}` is a string")
            out[kind] = p[kind]
        else:
            plan = p["fault"].get("plan") if isinstance(p["fault"], dict) else None
            if not isinstance(plan, list) or not plan or not all(isinstance(x, dict) and x.get("dd") for x in plan):
                raise SystemExit(f'{name}: `fault` is {{"plan": [{{"dd": DD, "op": ..., "nth": 1, ...}}]}}')
            faults.append({"name": name, "plan": plan, "why": str(p.get("why") or "survivor_attack.py try")})
    if added:
        out = st.with_records(out, corpus, added, work)
    out["faults"] = faults
    return out


def batch_context(case: dict[str, Any]) -> str:
    """What a batch input can change: the datasets with a layout and their first records, the generated datasets'
    fields, SYSIN / PARM, and one committed fault plan as the shape to copy."""
    import equivalence_cics as ec
    import equivalence_common as common
    import mainframe_corpus as mc
    import strengthen as st

    out = []
    try:
        (entry,) = mc.select([case["corpus"]])
        corpus = mc.require_clone(entry)
        enc = common.data_encoding(case)
        for dd, inp in st.batch_inputs(case, corpus).items():
            layout = ", ".join(f"{f['name']} {f.get('pic') or 'X'}@{f['offset']}" for f in inp["fields"])
            out += [f"### {dd} ({len(inp['records'])} records; keyed: {bool(inp['spec'].get('keys'))})",
                    f"Fields: {layout}",
                    *[f"{i + 1}. {json.dumps(ec.decode_record(r, inp['fields'], enc))}"
                      for i, r in enumerate(inp["records"][:3])], ""]  # fmt: skip
    except (SystemExit, OSError, ValueError, KeyError) as e:  # no corpus clone here: the packet still helps
        out.append(f"(the input datasets could not be read: {e})"[:300])
    for dd, spec in (case.get("datasets") or {}).items():
        if spec.get("input") == "@generate":
            fields = (spec.get("generate") or {}).get("fields") or {}
            out.append(f"### {dd} (`@generate`, {spec['generate'].get('records')} records): fields with a spec: "
                       f"{sorted(fields) or 'none'}")  # fmt: skip
    out.append(f"SYSIN: {case.get('sysin')!r}; PARM: {case.get('parm')!r}")
    if case.get("faults"):
        out.append(f"A committed fault plan, to copy the shape: {json.dumps(case['faults'][0]['plan'])}")
    return "\n".join(out)


def load_attempts(work: Path) -> dict[str, list[dict[str, Any]]]:
    f = work / "attempts.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def add_attempts(work: Path, new: dict[str, dict[str, Any]]) -> None:
    all_ = load_attempts(work)
    for mid, attempt in new.items():
        all_.setdefault(mid, []).append(attempt)
    (work / "attempts.json").write_text(json.dumps(all_, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def det_port(case: str, work: Path) -> Path:
    """The case's det port under `work`, translated once."""
    port = work / "det" / case / "port"
    if not port.is_dir():
        work.mkdir(parents=True, exist_ok=True)
        dm.translate([case], work)
    if not port.is_dir():
        raise SystemExit(f"{case}: no det port (see {work / 'det' / 'summary.json'})")
    return port


def port_text(port: Path, file: str = dm.FILES) -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(port.glob(file)))


def find_mutants(case: str, port: Path, ids: list[str]) -> dict[str, Any]:
    """{id: mutation.Mutant}; an id the port no longer has is found by its stated Java line before / after."""
    import mutation as mu

    every = mu.all_mutants(port, set(mu.OPERATORS), dm.FILES)
    by_id = {m.id: m for m in every}
    by_text = {(m.before.strip(), m.after.strip()): m for m in every}
    stated = dm.stated(case)
    out = {}
    for i in ids:
        s = stated.get(i, {})
        m = by_id.get(i) or by_text.get((str(s.get("before")).strip(), str(s.get("after")).strip()))
        if m is None:
            raise SystemExit(f"{case}: {i} is not a mutant of this port (the port moved? `det_mutation.py refresh`)")
        out[i] = m
    return out


def attack(
    case_name: str, ids: list[str], inputs: Path, work: Path, timeout: float, jobs: int = 1, base: str | None = None
) -> dict[str, dict[str, Any]]:
    import equivalence as eq
    import mainframe_corpus as mc
    import mutation as mu
    import strengthen as st

    # `base`: a sibling case of the same program (#6166: carddemo-userlist-linked enters COUSR00C by LINK, `linked` being
    # a case-level flag): its case.json carries the entry mode, the inputs go on it, the mutants are the case's own.
    case = eq.load_case(base or case_name)
    if base and base != case_name and case.get("corpus") != eq.load_case(case_name).get("corpus"):
        raise SystemExit(f"{base}: not a sibling of {case_name} (another corpus entry)")
    kind = case.get("kind", "batch")
    if kind != "batch" and kind not in st.KINDS:
        raise SystemExit(f"{case_name}: kind {kind}: `try` handles batch, {', '.join(sorted(st.KINDS))}")
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    proposals = json.loads(inputs.read_text(encoding="utf-8"))
    stamp = time.strftime("%Y%m%dT%H%M%S")
    here = work / "attacks" / stamp
    if kind == "batch":
        trial = batch_trial(case, corpus, proposals, here)
        faults = "all" if trial["faults"] else "none"  # the trial's faults are the proposed ones only
    else:
        trial, faults = attack_case(case, proposals, st.commarea_names(case, corpus)), "none"
    port = det_port(case_name, work)
    mutants = find_mutants(case_name, port, ids)
    here.mkdir(parents=True, exist_ok=True)
    cf = here / "case.json"
    cf.write_text(json.dumps({k: v for k, v in trial.items() if k != "name"}, indent=1) + "\n", encoding="utf-8")
    flags = ("--case-file", str(cf), "--no-facades", "--faults", faults)
    print(f"{case_name}: proving the port on {len(proposals)} new input(s); the trial case: {cf}", flush=True)
    base = mu.prove(case_name, port, here / "baseline", 3600, flags)
    names = [p["name"] for p in proposals]
    results: dict[str, dict[str, Any]] = {}
    classpath = mu.baseline_classpath(here / "baseline", here) if base["verdict"] == "proven" else ""

    def evaluate_one(item: tuple[str, Any]) -> tuple[str, Any, dict[str, Any]]:
        i, m = item
        record: dict[str, Any] = {"inputs": names, "date": time.strftime("%Y-%m-%d")}
        mdir = here / i
        if base["verdict"] != "proven":
            record["result"] = judge(base, {"verdict": "error"})
            record["detail"] = (base.get("why") or str((base.get("report") or {}).get("feedback") or ""))[:400]
        else:
            ok, why = mu.compiles(mu.write_mutant(port, m, mdir / "port"), classpath, mdir / "classes")
            if not ok:
                record.update(result="stillborn", detail=why[:400])
            else:
                res = mu.prove(case_name, mdir / "port", mdir / "proof", timeout,
                               (*flags, "--reuse", str(here / "baseline"), "--first-difference"))  # fmt: skip
                record.update(result=judge(base, res), killed_by=res.get("killed_by", []))
        return i, m, record

    if jobs > 1 and base["verdict"] == "proven":
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            for i, m, record in pool.map(evaluate_one, mutants.items()):
                results[i] = record
                print(f"  {i} {m.op} {m.file}:{m.line}: {record['result']}", flush=True)
    else:
        for i, m in mutants.items():
            _, _, record = evaluate_one((i, m))
            results[i] = record
            print(f"  {i} {m.op} {m.file}:{m.line}: {record['result']}", flush=True)
    add_attempts(work, results)
    return results


# ---- the commands ---------------------------------------------------------------------------------------------------
def cmd_next(cases: list[str], limit: int) -> int:
    rows = ranked(dm.load_survivors(), cases or None)
    for r in rows[:limit]:
        print(f"{r['score']:>2} {r['case']} {r['id']} {r['verdict']}: {'; '.join(r['why'])}")
    print(f"{len(rows)} verdicts worth an attack; {min(limit, len(rows))} shown")
    return 0


# ---- what the COBOL settles (tests/tools/branch_solver.py, #4175) ---------------------------------------------------
def solver_paragraphs(case: str, work: Path) -> dict[str, str] | None:
    """Paragraph name -> branch_solver verdict (confirmed: no input enters it; witness: some input does), or None when
    z3 (the `solver` extra) is missing or the program cannot be walked."""
    try:
        import z3  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: F401, PLC0415
    except ImportError:
        return None
    import branch_solver as bs  # noqa: PLC0415

    try:
        res = bs.paragraphs(case, work / "branch-solver")
    except Exception as e:  # noqa: BLE001 -- a program the walk cannot read: no solver facts, never a failure
        print(f"branch_solver: {case}: {type(e).__name__}: {e}"[:300])
        return None
    return {str(r["paragraph"]).upper(): str(r["verdict"]) for r in res["paragraphs"]}


_CLAUSE = re.compile(r"[.;:,]|->|\bso\b|\bwhich\b|\bwhose\b|\bbut\b", re.I)
_NEGATION = re.compile(r"\b(never|not|no|nothing|none|cannot|unreachable)\b", re.I)


def named_paragraphs(reason: str, names: Any) -> list[str]:
    """The program's paragraphs a stated reason says are not reached: named (whole word, four characters or more) in
    a clause before its negation ("POPULATE-TIME-DATE is never PERFORMed"). A paragraph named as context ("the program
    runs P010 -> GET-ME-OUT-OF-HERE", "which no paragraph PERFORMs from P010") is no claim."""
    out: set[str] = set()
    for clause in _CLAUSE.split(reason.upper()):
        neg = _NEGATION.search(clause)
        if not neg:
            continue
        for n in names:  # the paragraph is the clause's subject: named before its negation
            m = re.search(rf"(?<![A-Z0-9-]){re.escape(n)}(?![A-Z0-9-])", clause)
            if len(n) >= 4 and m and m.start() < neg.start():
                out.add(n)
    return sorted(out)


def solver_fact(stated: dict[str, Any], verdicts: dict[str, str]) -> dict[str, str] | None:
    """For an `unreachable` verdict whose reason says paragraphs are not reached: `solver-unreachable` (an attack that
    held, for `det_mutation.py state`) when the solver finds no input that enters any of them; `solver-entered` (advice
    only, never recorded: the reason's prose is read by a pattern) when it finds an input that enters one."""
    if stated.get("verdict") != "unreachable":
        return None
    named = named_paragraphs(str(stated.get("reason") or ""), verdicts)
    if not named:
        return None
    entered = [n for n in named if verdicts[n] == "witness"]
    if entered:
        return {"result": "solver-entered", "fact": f"branch_solver finds an input that enters {', '.join(entered)}"}
    if all(verdicts[n] == "confirmed" for n in named):
        return {
            "result": "solver-unreachable",
            "fact": f"branch_solver: no input of the program enters {', '.join(named)}",
        }
    return None


_FIELD_DECL = re.compile(r"\bf\d+_(\w+)\s*=\s*Field\.\w+\(\s*s_(\w+)")


def field_of(before: str) -> tuple[str, str] | None:
    """(COBOL item, COBOL record) a det-port Field declaration names (`f12_WS_X = Field.alphanumeric(s_REC, ...)`)."""
    m = _FIELD_DECL.search(before)
    return (m.group(1).replace("_", "-"), m.group(2).replace("_", "-")) if m else None


def solver_unread(case: str, work: Path) -> set[tuple[str, str]] | None:
    """(record, item) of the WORKING-STORAGE items no reachable statement uses (branch_solver.py fields), or None."""
    try:
        import z3  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: F401, PLC0415
    except ImportError:
        return None
    import branch_solver as bs  # noqa: PLC0415

    try:
        res = bs.fields_used(case, work / "branch-solver")
    except Exception as e:  # noqa: BLE001 -- a program the walk cannot read: no solver facts, never a failure
        print(f"branch_solver: {case}: {type(e).__name__}: {e}"[:300])
        return None
    return {(str(x["record"]).upper(), str(x["item"]).upper()) for x in res["unread"]}


def solver_observability(case: str, work: Path) -> Any:
    """field_observability.Observability for a case (its `judge(before, after)`), or None without z3 / a walk."""
    try:
        import z3  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: F401, PLC0415
    except ImportError:
        return None
    import branch_solver as bs  # noqa: PLC0415
    import field_observability as fo  # noqa: PLC0415

    try:
        spec = json.loads((dm.CASES / case / "case.json").read_text(encoding="utf-8"))
        return fo.Observability(bs.case_program(case, work / "branch-solver"), spec, bs.corpus_root(spec["corpus"]))
    except Exception as e:  # noqa: BLE001 -- a program the walk cannot read: no facts, never a failure
        print(f"field_observability: {case}: {type(e).__name__}: {e}"[:300])
        return None


def unread_fact(mutant: dict[str, Any], unread: set[tuple[str, str]]) -> dict[str, str] | None:
    """A mutant of the Field declaration of an item no reachable statement uses: nothing any input sees changes."""
    f = field_of(str(mutant.get("before") or ""))
    if f is None:
        return None
    item, record = f
    if (record, item) in unread or (item == record and (record, item) in unread):
        return {"result": "solver-unread", "fact": f"branch_solver: no reachable statement uses {item} ({record})"}
    return None


def cmd_facts(case: str, work: Path) -> int:
    port = det_port(case, work)
    entry = dm.load().get(case) or {}
    settled: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    for s in entry.get("survived", []):
        text = texts.setdefault(s["file"], (port / s["file"]).read_text(encoding="utf-8"))
        fact = port_fact(text, s)
        if fact:
            settled[s["id"]] = {**fact, "date": time.strftime("%Y-%m-%d")}
    fields = [s for s in entry.get("survived", []) if field_of(s.get("before") or "")]
    unread = solver_unread(case, work) if fields else None
    obs = solver_observability(case, work) if fields else None
    for s in fields:
        if s["id"] in settled:
            continue
        fact = unread_fact(s, unread) if unread else None
        why = obs.judge(s["before"], s["after"]) if obs is not None and not fact else None
        if why:
            fact = {"result": "solver-unobservable", "fact": f"field_observability: {why}"}
        if fact:
            settled[s["id"]] = {**fact, "date": time.strftime("%Y-%m-%d")}
    stated = dm.stated(case)
    pending = [s for s in entry.get("survived", []) if s["id"] not in settled and s["id"] in stated]
    verdicts = solver_paragraphs(case, work) if pending else None
    questioned = 0
    for s in pending if verdicts else []:
        fact = solver_fact(stated[s["id"]], verdicts or {})
        if fact and fact["result"] == "solver-entered":
            questioned += 1
            print(f"  {s['id']}: stated unreachable, but {fact['fact']}: read the reason, then attack it")
        elif fact:
            settled[s["id"]] = {**fact, "date": time.strftime("%Y-%m-%d")}
    add_attempts(work, settled)
    total = len(entry.get("survived", []))
    print(f"{case}: the port and the COBOL settle {len(settled)} of {total} survivors ({questioned} stated reasons the "
          f"solver questions); the other {total - len(settled)} need `try`" + ("" if verdicts is not None else
          " (no branch_solver: install the `solver` extra for the COBOL facts)"))  # fmt: skip
    return 0


def cmd_packet(case: str, mid: str, work: Path) -> int:
    import strengthen as st

    port = det_port(case, work)
    m = find_mutants(case, port, [mid])[mid]
    text = (port / m.file).read_text(encoding="utf-8")
    lines = text.splitlines()
    spec = json.loads((dm.CASES / case / "case.json").read_text(encoding="utf-8"))
    stated = dm.stated(case).get(mid, {})
    span = range(max(0, m.line - CONTEXT - 1), min(len(lines), m.line + CONTEXT))
    print(f"# Attack {mid}: {case} ({spec.get('program')}), {m.op} at {m.file}:{m.line}\n")
    print(f"Before: `{m.before.strip()}`\nAfter:  `{m.after.strip()}`\n")
    print(f"In method: {enclosing(methods(text), m.line) or '(class level)'}")
    print(f"The port settles it: {port_fact(text, {'line': m.line, 'before': m.before}) or 'no: it needs an attack'}")
    if stated:
        print(f"Stated: {stated.get('verdict')}: {stated.get('reason')}")
        verdicts = solver_paragraphs(case, work) if stated.get("reason") else None
        for name in named_paragraphs(str(stated.get("reason")), verdicts or {}):
            what = {"confirmed": "no input of the program enters it", "witness": "an input enters it (branch_solver.py "
                    "reach gives one)"}.get((verdicts or {})[name], "undecided")  # fmt: skip
            print(f"branch_solver, {name}: {what}")
        for problem in dm.reason_problems(str(stated.get("verdict")), str(stated.get("reason"))):
            print(f"Refused as written: {problem}")
    print("\n## The Java\n```java")
    print("\n".join(f"{'>' if i + 1 == m.line else ' '}{i + 1:5} {lines[i]}" for i in span))
    print(
        f"```\n\nThe COBOL: {spec.get('program_source')} in corpus {spec.get('corpus')}. Read it: the Java is one reading."
    )
    hints = [h for rx, h in HINTS if rx.search(m.before)]
    print("\n## Where to start\n" + ("\n".join(f"- {h}" for h in hints) or "- Read how this value reaches an output."))
    kind = spec.get("kind", "batch")
    if kind in st.INPUT_FORMAT:
        names = [e.get("name") for e in spec.get(st.KINDS[kind], [])]
        print(f"\n## The input format\n{st.INPUT_FORMAT[kind]}\n\nInputs the case has: {names}")
    elif kind == "batch":
        print(f"\n## The input format\n{BATCH_FORMAT}\n\n" + batch_context({**spec, "name": case}))
    print("\n## The command\n```bash")
    print(
        f"python tests/tools/survivor_attack.py try {case} {mid} --inputs INPUTS.json --work {shlex.quote(str(work))}"
    )
    print("```\nINPUTS.json is a JSON array of inputs. Never state an expected result: the COBOL decides.")
    return 0


def cmd_lint(cases: list[str]) -> int:
    bad = 0
    ledger = dm.load()
    for case, entries in sorted(dm.load_survivors().items()):
        if cases and case not in cases:
            continue
        coverage = (ledger.get(case) or {}).get("coverage")
        for e in entries:
            for problem in dm.reason_problems(str(e.get("verdict")), str(e.get("reason")), coverage):
                print(f"{case} {e['id']} {e['verdict']}: {problem}")
                bad += 1
        for problem in dm.template_problems(case, entries):
            print(problem)
            bad += 1
    print(f"{bad} stated reasons `det_mutation.py state` would refuse today")
    return 0  # a report: committed verdicts are re-attacked, not failed in bulk


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("cases", nargs="*")
    n.add_argument("--limit", type=int, default=20)
    f = sub.add_parser("facts")
    f.add_argument("case")
    f.add_argument("--work", type=Path, required=True)
    p = sub.add_parser("packet")
    p.add_argument("case")
    p.add_argument("id")
    p.add_argument("--work", type=Path, required=True)
    t = sub.add_parser("try")
    t.add_argument("case")
    t.add_argument("ids", help="mutant ids, comma separated: one input can be aimed at several")
    t.add_argument("--inputs", type=Path, required=True, help="a JSON array of inputs in the case's format")
    t.add_argument("--work", type=Path, required=True)
    t.add_argument("--timeout", type=float, default=600, help="seconds per mutant")
    t.add_argument("--jobs", type=int, default=1, help="parallel mutants to prove")
    t.add_argument("--as", dest="base", metavar="SIBLING", help="enter it the way this sibling case does (e.g. LINK)")
    li = sub.add_parser("lint")
    li.add_argument("cases", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "next":
        return cmd_next(args.cases, args.limit)
    if args.cmd == "facts":
        return cmd_facts(args.case, args.work.resolve())
    if args.cmd == "packet":
        return cmd_packet(args.case, args.id, args.work.resolve())
    if args.cmd == "lint":
        return cmd_lint(args.cases)
    results = attack(
        args.case, args.ids.split(","), args.inputs, args.work.resolve(), args.timeout, args.jobs, args.base
    )
    wins = [i for i, r in results.items() if r["result"] == "killed"]
    if wins:
        print(
            f"killed {', '.join(wins)}: add the input to tests/equivalence/{args.base or args.case}/case.json and re-run the ledger"
        )
    if any(r["result"] == "port-differs" for r in results.values()):
        print(
            "port-differs: the port is not equal to the COBOL on this input. Stop and report it: that is a real finding"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
