"""
Blind cross-verification of a COBOL answer key by a second reviewer model.

An answer key (tests/cobol_mainframe/answer_key/) starts `llm_verified`: the model
that drafted it checked it against the source. That model also wrote the draft
reader, so its blind spots and the key's are correlated. This tool gets a SECOND
reviewer to answer the same questions without seeing the key's answers, then
lists every place the two disagree, so each can be settled against the source.

    python tests/tools/cross_verify.py brief --corpus NAME [--live 35] [--programs 10] [--seed S] --out DIR [--stage DIR]
    python tests/tools/cross_verify.py grade --corpus NAME --dir DIR [--answers DIR/answers.json]
    python tests/tools/cross_verify.py sign  --corpus NAME --dir DIR --by "REVIEWER MODEL"
    python tests/tools/cross_verify.py census --corpus NAME --out DIR [--max-units 150] [--stage DIR]
    python tests/tools/cross_verify.py coverage --corpus NAME

CENSUS. For a corpus small enough to review in full, `census` packs EVERY program
(whole, never split) into batches of about --max-units units and writes a blind
brief per batch (DIR/batch_NN/brief.md + truth.json) that asks every question for
its programs: all units, dead and live, in source order, plus the full PROGRAM-ID,
copybook, call and file lists. Each batch goes to its own fresh reviewer and is
graded and signed like a sample. Signing a census batch marks only its programs
(`verification.census`), and `coverage` reports how much of the key a clean census
has covered. At 100% the key's validated fields have been read twice,
independently, with every disagreement settled against the source. Use sampling
for corpora too large for that.

`brief` writes DIR/brief.md (the reviewer's whole task: source paths, the fixed-
format rules, the questions, the JSON reply shape) and DIR/truth.json (the key's
answers to exactly those questions -- never shown to the reviewer). The brief is
BLIND: the key's dead units are shuffled among an equal share of seeded live
controls and asked "reachable or not?", and PROGRAM-ID / copybooks / calls / files
are asked open-ended for a seeded program sample, so agreeing costs the reviewer
the same reading as disagreeing.

The reviewer is any model that can read files: a fresh-context agent given only
brief.md, or a different model family (e.g. Gemini through `agy -p`). It replies
with one JSON object, saved as DIR/answers.json.

`grade` writes DIR/grade.md and DIR/grade.json: per-task agreement, and every
disagreement with the key's value, the reviewer's value and its cited evidence.
Settle each against the source. Where the key is wrong, fix the key (and the
draft reader, with a test). Then record the ruling in DIR/rulings.json:
    {"<disagreement id>": {"verdict": "key_correct" | "key_fixed", "why": "..."}}

`sign` refuses unless every disagreement has a ruling and every `key_fixed` one
no longer disagrees when re-graded against the current key. It then sets each
program's `verification.tier` to `cross_verified` with `cross_by`, and records
the sample and its agreement in the key's top-level `cross_verification` list,
so the evidence behind the tier stays in the key.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mainframe_corpus as mc  # noqa: E402

REPO_ROOT = mc.REPO_ROOT

FIXED_FORMAT_RULES = """COBOL fixed-format rules to apply: columns 1-6 are a sequence area (ignore any digits there), column 7 is
the indicator ('*' or '/' = comment line, ignore the whole line), Area A is columns 8-11 (paragraph and section
headers start there), columns 73-80 are an identification area (ignore). A paragraph header's separator period may
appear on a following line. The same paragraph name may be declared twice while nothing references it."""

REACH_RULES = """Decide from control STRUCTURE only: treat every IF / EVALUATE / PERFORM UNTIL condition as able to
be true or false, and do not reason about what values data items can hold. Count as reaching a unit: PERFORM X; PERFORM A THRU B (every unit from A to B inclusive, but only as far as
control actually flows -- if A ends in a statement that never returns, units after it in the range are not reached
through that PERFORM); GO TO; falling through from the previous unit when that unit's execution can finish without
an unconditional transfer; EXEC CICS HANDLE ABEND/CONDITION/AID LABEL(x). Unconditional transfers that never fall
through: GOBACK, STOP RUN, EXIT PROGRAM, GO TO, EXEC CICS RETURN / XCTL / ABEND, and a PERFORM of a unit that itself
never returns. A unit reached only from unreachable code is unreachable. When a PERFORM range ends (its last unit
finishes), control returns to the PERFORM statement rather than falling into the next unit."""


def load_key(corpus: dict[str, Any]) -> dict[str, Any]:
    if not corpus.get("answer_key"):
        sys.exit(f"{corpus['name']} has no answer key")
    return json.loads((REPO_ROOT / corpus["answer_key"]).read_text(encoding="utf-8"))


def _norm_operand(op: str) -> str:
    """Quotes, case and blank padding dropped: CICS pads program names to 8, so
    `'INQCUST '` and `INQCUST` name the same program. A subscript on an identifier
    is dropped too: `CDEMO-MENU-OPT-PGMNAME(WS-OPTION)` is the table
    CDEMO-MENU-OPT-PGMNAME, which is what the key records."""
    op = op.strip()
    if not op.startswith(("'", '"')):
        op = re.sub(r"\s*\(.*\)\s*$", "", op)
    return op.strip("'\"").strip().upper()


def key_answers(
    key: dict[str, Any], units: list[tuple[str, str]], sample: list[str], b_programs: Optional[list[str]] = None
) -> dict[str, Any]:
    """The key's answers to a fixed question set: `units` for task A (in order),
    `b_programs` (default: every program) for B, and `sample` for C/D/E."""
    progs = key["programs"]
    b_set = set(progs) if b_programs is None else set(b_programs)
    return {
        "A": [
            {"n": i + 1, "program": p, "unit": n, "reachable": n not in progs[p]["dead"]}
            for i, (p, n) in enumerate(units)
        ],
        "B": {p: v["program_id"] for p, v in sorted(progs.items()) if p in b_set},
        "C": {
            p: sorted({(c["name"], c["resolves_to"]) for c in progs[p]["copybooks"]}, key=lambda t: (t[0], t[1] or ""))
            for p in sample
        },
        "D": {p: sorted({(c["verb"], _norm_operand(c["operand"])) for c in progs[p]["calls"]}) for p in sample},
        "E": {p: sorted({(f["dd"], tuple(f["modes"])) for f in progs[p]["files"]}) for p in sample},
    }


def _tup(x: Any) -> Any:
    return tuple(_tup(i) for i in x) if isinstance(x, (list, tuple)) else x


def build(key: dict[str, Any], repo: Path, live: int, programs: int, seed: int) -> tuple[str, dict[str, Any]]:
    """(brief markdown, truth). Deterministic for a given key and seed."""
    rng = random.Random(seed)
    progs = key["programs"]
    dead = sorted((p, n) for p, v in progs.items() for n in v["dead"])
    live_pool = sorted({(p, u["name"]) for p, v in progs.items() for u in v["units"] if u["name"] not in v["dead"]})
    units = dead + rng.sample(live_pool, min(max(live, len(dead)), len(live_pool)))
    rng.shuffle(units)
    sample = sorted(rng.sample(sorted(progs), min(programs, len(progs))))
    # Programs whose verification notes record a finding are the likeliest to be
    # wrong; always include them, so a finding is re-checked blind.
    sample = sorted(set(sample) | {p for p, v in progs.items() if v["verification"].get("notes")})
    return render(key, repo, units, sample, None, {"seed": seed, "mode": "sample"})


def census_batches(key: dict[str, Any], max_units: int) -> list[list[str]]:
    """Every program, packed whole into batches of about `max_units` units
    (a program larger than that gets a batch of its own), largest first."""
    progs = sorted(key["programs"], key=lambda p: (-len(key["programs"][p]["units"]), p))
    batches: list[list[str]] = []
    sizes: list[int] = []
    for p in progs:
        n = len({u["name"] for u in key["programs"][p]["units"]})
        for i, size in enumerate(sizes):
            if size + n <= max_units:
                batches[i].append(p)
                sizes[i] += n
                break
        else:
            batches.append([p])
            sizes.append(n)
    return [sorted(b) for b in batches]


def build_census(key: dict[str, Any], repo: Path, batch: list[str], index: int, of: int) -> tuple[str, dict[str, Any]]:
    """A blind brief asking EVERY question for the programs in `batch`: every unit's
    reachability (dead and live together, in source order, so position gives
    nothing away), the PROGRAM-ID, and the full copybook / call / file lists."""
    units: list[tuple[str, str]] = []
    for p in batch:
        seen: set[str] = set()
        for u in key["programs"][p]["units"]:
            if u["name"] not in seen:
                seen.add(u["name"])
                units.append((p, u["name"]))
    return render(key, repo, units, batch, batch, {"mode": "census", "batch": index, "of": of})


def render(
    key: dict[str, Any],
    repo: Path,
    units: list[tuple[str, str]],
    sample: list[str],
    b_programs: Optional[list[str]],
    meta: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    truth = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "seed": meta.get("seed"),
        "root": str(repo),
        **meta,
        **key_answers(key, units, sample, b_programs),
    }
    ul = "\n".join(f"{t['n']}. {repo / t['program']} :: {t['unit']}" for t in truth["A"])
    listing = "\n".join(str(repo / p) for p in sample)
    all_progs = "\n".join(str(repo / p) for p in truth["B"])
    brief = f"""You are independently verifying facts about real IBM mainframe COBOL source code, as a second reviewer.
Read the source files yourself. They are all under the repository root {repo} (absolute paths below);
read only inside that directory. Do NOT edit or create any files except your answers file, and do not look for any
existing answer key or analysis of this code: the point is an independent reading. Read the COBOL source directly
(grep/sed/cat or a file reader).

{FIXED_FORMAT_RULES}

TASK A -- reachability. For each numbered PROCEDURE DIVISION unit (paragraph or section), decide whether control can
EVER reach it when the program runs from its entry point (the start of the PROCEDURE DIVISION). {REACH_RULES}
{ul}

TASK B -- PROGRAM-ID. For each file, the program name its PROGRAM-ID paragraph declares:
{all_progs}

TASK C -- copybooks. For each file below, every COPY member and every EXEC SQL INCLUDE member that is not commented
out, and the repository file it resolves to: a file in the repository whose base name equals the member (any of the
extensions .cpy .CPY .copy .dcl), repo-relative, or null when no such file exists in the repository (CICS-, DB2-,
MQ- or LE-supplied members, BMS-generated maps). If several repository files match, give the one nearest the program.

TASK D -- program calls. For each file below, every executable (not commented-out) CALL statement and every EXEC
CICS LINK / XCTL PROGRAM(...), with its operand exactly as written (a quoted literal, or an identifier). Not
RETURN TRANSID, not END-CALL.

TASK E -- files. For each file below, every non-commented SELECT ... ASSIGN TO <name>, reported as the DD name (the
ASSIGN name with any UT-S- or UR-S- prefix removed), and the OPEN modes (INPUT / OUTPUT / I-O / EXTEND) that
non-commented OPEN statements actually use on it.

Files for tasks C, D and E:
{listing}

OUTPUT: reply with ONLY one JSON object, no prose before or after, of this shape (paths repo-relative):
{{"A": [{{"n": 1, "reachable": true, "evidence": "line numbers and the statement that reaches it, or why nothing does"}}, ...all {len(units)} items...],
 "B": {{"<path>": "PROGNAME", ...}},
 "C": {{"<path>": [{{"member": "X", "resolves_to": "relative/path or null", "line": 123}}, ...]}},
 "D": {{"<path>": [{{"verb": "CALL"|"LINK"|"XCTL", "operand": "'LIT' or IDENT", "line": 123}}, ...]}},
 "E": {{"<path>": [{{"dd": "DDNAME", "modes": ["INPUT"]}}, ...]}}}}
"""
    return brief, truth


def _rel(path: str, repo: Path) -> str:
    # Compared with `/` on every OS: on Windows `str(Path("/repo"))` has
    # backslashes, and so do the answer paths, so a `/`-only root never matched.
    p = str(path).replace("\\", "/")
    root = str(repo).replace("\\", "/").rstrip("/") + "/"
    return p[len(root) :] if p.startswith(root) else p


def grade(truth: dict[str, Any], answers: dict[str, Any], repo: Path) -> dict[str, Any]:
    """Every disagreement between the reviewer and the key, with a stable id."""
    out: dict[str, Any] = {"tasks": {}, "disagreements": []}

    def add(task: str, ident: str, key_value: Any, reviewer: Any, evidence: str = "") -> None:
        out["disagreements"].append(
            {"id": f"{task}:{ident}", "task": task, "key": key_value, "reviewer": reviewer, "evidence": evidence}
        )

    got_a = {int(a["n"]): a for a in answers.get("A", []) if isinstance(a, dict) and "n" in a}
    agree = 0
    for t in truth["A"]:
        a = got_a.get(t["n"])
        if a is not None and bool(a.get("reachable")) == t["reachable"]:
            agree += 1
            continue
        add(
            "A",
            f"{t['program']}::{t['unit']}",
            "reachable" if t["reachable"] else "unreachable",
            None if a is None else ("reachable" if a.get("reachable") else "unreachable"),
            "" if a is None else str(a.get("evidence", "")),
        )
    out["tasks"]["A"] = {"agree": agree, "asked": len(truth["A"])}

    got_b = {_rel(k, repo): v for k, v in (answers.get("B") or {}).items()}
    agree = 0
    for p, pid in truth["B"].items():
        if str(got_b.get(p, "")).strip().upper() == pid.upper():
            agree += 1
        else:
            add("B", p, pid, got_b.get(p))
    out["tasks"]["B"] = {"agree": agree, "asked": len(truth["B"])}

    def keyed(task: str, norm) -> None:
        got = {_rel(k, repo): v for k, v in (answers.get(task) or {}).items()}
        agree = asked = 0
        for p, want in truth[task].items():
            want_set = {_tup(w) for w in want}
            have = {norm(r, repo) for r in got.get(p, []) if isinstance(r, dict)}
            for item in sorted(want_set | have, key=str):
                asked += 1
                if item in want_set and item in have:
                    agree += 1
                else:
                    add(
                        task,
                        f"{p}::{item}",
                        "present" if item in want_set else "absent",
                        "present" if item in have else "absent",
                    )
        out["tasks"][task] = {"agree": agree, "asked": asked}

    keyed(
        "C",
        lambda r, repo: (
            str(r.get("member", "")).upper(),
            _rel(r["resolves_to"], repo) if r.get("resolves_to") else None,
        ),
    )
    keyed("D", lambda r, repo: (str(r.get("verb", "")).upper(), _norm_operand(str(r.get("operand", "")))))
    keyed(
        "E", lambda r, repo: (str(r.get("dd", "")).upper(), tuple(sorted(str(m).upper() for m in r.get("modes", []))))
    )
    return out


def _md(g: dict[str, Any], corpus: str) -> str:
    lines = [f"# Cross-verification: {corpus}", "", "| task | agree | asked |", "|---|---|---|"]
    lines += [f"| {t} | {v['agree']} | {v['asked']} |" for t, v in g["tasks"].items()]
    lines += ["", f"**{len(g['disagreements'])} disagreement(s)** to settle against the source:", ""]
    lines += [
        f"- `{d['id']}` -- key: {d['key']}, reviewer: {d['reviewer']}"
        + (f" -- {d['evidence']}" if d["evidence"] else "")
        for d in g["disagreements"]
    ]
    return "\n".join(lines) + "\n"


def parse_answers(text: str) -> dict[str, Any]:
    """The reviewer's JSON object, tolerating prose or a ``` fence around it."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the reviewer's answers")
    return json.loads(m.group(0))


def sign(
    key: dict[str, Any],
    truth: dict[str, Any],
    g: dict[str, Any],
    rulings: dict[str, Any],
    by: str,
    at: Optional[str] = None,
) -> dict[str, Any]:
    """The key, re-tiered `cross_verified` -- or SystemExit naming what is unsettled."""
    unruled = [d["id"] for d in g["disagreements"] if d["id"] not in rulings]
    if unruled:
        sys.exit(f"{len(unruled)} disagreement(s) have no ruling in rulings.json: {unruled[:5]}")
    fixed_still = [d["id"] for d in g["disagreements"] if rulings[d["id"]].get("verdict") == "key_fixed"]
    if fixed_still:
        sys.exit(
            f"ruled key_fixed but the current key still disagrees (re-run brief/grade after the fix): {fixed_still[:5]}"
        )
    bad = [i for i, r in rulings.items() if r.get("verdict") not in ("key_correct", "key_fixed") or not r.get("why")]
    if bad:
        sys.exit(f"rulings need verdict key_correct|key_fixed and a why: {bad[:5]}")
    at = at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    census = truth.get("mode") == "census"
    # A sample vouches for the key as a whole; a census batch only for the
    # programs it asked every question about.
    covered = sorted(truth["B"]) if census else sorted(key["programs"])
    for rel in covered:
        v = key["programs"][rel]["verification"]
        v["tier"] = "cross_verified"
        v["cross_by"] = v.get("cross_by") or by
        v["cross_at"] = v.get("cross_at") or at
        if census:
            v["census"] = {"by": by, "at": at}
    record: dict[str, Any] = {
        "by": by,
        "at": at,
        "mode": truth.get("mode", "sample"),
        "tasks": g["tasks"],
        "rulings": {i: rulings[i] for i in sorted(rulings)},
    }
    if census:
        record["programs"] = covered
    else:
        record["seed"] = truth["seed"]
    key.setdefault("cross_verification", []).append(record)
    return key


def coverage(key: dict[str, Any]) -> dict[str, Any]:
    """How much of the key a clean blind census has covered: programs and units."""
    progs = key["programs"]
    done = [p for p, v in progs.items() if v["verification"].get("census")]
    units = sum(len({u["name"] for u in v["units"]}) for v in progs.values())
    units_done = sum(len({u["name"] for u in progs[p]["units"]}) for p in done)
    return {
        "programs": [len(done), len(progs)],
        "units": [units_done, units],
        "missing": sorted(set(progs) - set(done)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief")
    b.add_argument("--corpus", required=True)
    b.add_argument("--live", type=int, default=35)
    b.add_argument("--programs", type=int, default=10)
    b.add_argument("--seed", type=int, default=3210)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument(
        "--stage",
        type=Path,
        help="copy the corpus (source only, no .git) here and point the brief at the copy, so the reviewer "
        "works in a directory with no engine, key or tooling anywhere above it",
    )
    c = sub.add_parser("census")
    c.add_argument("--corpus", required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--max-units", type=int, default=150)
    c.add_argument("--stage", type=Path, help="as for brief")
    cov = sub.add_parser("coverage")
    cov.add_argument("--corpus", required=True)
    for name in ("grade", "sign"):
        s = sub.add_parser(name)
        s.add_argument("--corpus", required=True)
        s.add_argument("--dir", type=Path, required=True)
        s.add_argument("--answers", type=Path)
        if name == "sign":
            s.add_argument("--by", required=True)
    args = ap.parse_args()

    (corpus,) = mc.select([args.corpus])
    key = load_key(corpus)
    repo = mc.require_clone(corpus)
    if args.cmd == "coverage":
        c = coverage(key)
        print(
            f"{corpus['name']}: census covers {c['programs'][0]}/{c['programs'][1]} programs, "
            f"{c['units'][0]}/{c['units'][1]} units"
        )
        for p in c["missing"]:
            print(f"  not yet: {p}")
        return 0 if not c["missing"] else 1
    if args.cmd in ("brief", "census") and args.stage:
        import shutil

        staged = args.stage.resolve() / corpus["name"]
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(repo, staged, ignore=shutil.ignore_patterns(".git"))
        repo = staged
    if args.cmd == "census":
        batches = census_batches(key, args.max_units)
        for i, batch in enumerate(batches, 1):
            d = args.out / f"batch_{i:02d}"
            d.mkdir(parents=True, exist_ok=True)
            brief, truth = build_census(key, repo, batch, i, len(batches))
            (d / "brief.md").write_text(brief, encoding="utf-8")
            (d / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
            print(f"{d}: {len(batch)} programs, {len(truth['A'])} units")
        return 0
    if args.cmd == "brief":
        brief, truth = build(key, repo, args.live, args.programs, args.seed)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "brief.md").write_text(brief, encoding="utf-8")
        (args.out / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        print(
            f"{args.out / 'brief.md'}: {len(truth['A'])} units, {len(truth['B'])} PROGRAM-IDs, {len(truth['C'])} programs for C/D/E"
        )
        return 0

    truth = json.loads((args.dir / "truth.json").read_text(encoding="utf-8"))
    repo = Path(truth.get("root") or repo)  # the tree the reviewer was pointed at
    answers = parse_answers((args.answers or args.dir / "answers.json").read_text(encoding="utf-8"))
    g = grade(truth, answers, repo)
    if args.cmd == "grade":
        (args.dir / "grade.json").write_text(json.dumps(g, indent=2) + "\n", encoding="utf-8")
        md = _md(g, corpus["name"])
        (args.dir / "grade.md").write_text(md, encoding="utf-8")
        print(md)
        return 0 if not g["disagreements"] else 1

    # sign: re-grade the SAME questions against the CURRENT key, so a key_fixed
    # ruling is only accepted once the fix is actually in the key.
    current = dict(
        truth,
        **key_answers(key, [(t["program"], t["unit"]) for t in truth["A"]], sorted(truth["C"]), sorted(truth["B"])),
    )
    g = grade(current, answers, repo)
    rulings_path = args.dir / "rulings.json"
    rulings = json.loads(rulings_path.read_text(encoding="utf-8")) if rulings_path.is_file() else {}
    signed = sign(key, truth, g, rulings, args.by)
    (REPO_ROOT / corpus["answer_key"]).write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    covered = signed["cross_verification"][-1].get("programs") or signed["programs"]
    print(f"{corpus['answer_key']}: {len(covered)} program(s) signed by {args.by} ({truth.get('mode', 'sample')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
