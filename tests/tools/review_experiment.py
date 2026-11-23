#!/usr/bin/env python3
"""Measure how often a model review catches the hidden review-layer defects, and how often it cries wolf (#7155, part 3).

`review_controls.py` authors three realistic diffs, each hiding one defect, plus a clean twin of each. This tool is the
measuring half: it turns a packet into a blind reviewer prompt, scores a reviewer's JSON answer against the answer key
with no model in the loop, and compares models (Sonnet vs Opus) on the same set.

    python tests/tools/review_experiment.py prompt KEY                 # the blind prompt a reviewer gets
    python tests/tools/review_experiment.py run --models sonnet,opus   # DRY RUN: prints the size and stops
    python tests/tools/review_experiment.py run --models sonnet,opus --owner-ok --out DIR/results.json
    python tests/tools/review_experiment.py report DIR/results.json    # catch rate, false alarms, model delta
    python tests/tools/review_experiment.py report DIR/results.json --markdown   # the same as a table for a page

`run` calls a model, so it is the experiment lane's (Opus design, owner OK, cost-vs-reward gate): it makes no call
without `--owner-ok`. The set is three defects and three twins, so every rate is printed with its n and no verdict is
drawn from it. Stdlib only; `subprocess` is used only by the owner-gated `run`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import review_controls as rc  # noqa: E402

PROMPT = """You are reviewing a pull request before it merges. Read the title, description and diff, then decide
whether to approve it. Report only problems you would block or question in a real review; do not praise or summarize.

Answer with one JSON object and nothing else:
{{"verdict": "approve" or "request_changes",
 "findings": [{{"file": "path in the diff", "line_text": "the changed line you mean, copied exactly", "summary": "the problem"}}]}}
Use an empty findings list when you have none.

Title: {title}

Description:
{body}

Diff:
{diff}
"""

# Headless Claude Code as a text-only reviewer: no tools, no MCP, nothing persisted, prompt on stdin.
CLAUDE_ARGS = (
    "-p",
    "--tools",
    "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
    "--output-format",
    "text",
)
RUN_TIMEOUT_S = 600
CHARS_PER_TOKEN = 4  # a rough size, for the dry run only


def prompt_for(c: rc.Control) -> str:
    """The blind prompt: a packet and a fixed answer format, nothing that names a key, class or experiment."""
    text = PROMPT.format(**rc.reviewer_packet(c))
    if rc.LEAKY.search(text):
        raise ValueError(f"{c.key}: the prompt names the experiment")
    return text


def parse_review(raw: str) -> dict | None:
    """The reviewer's JSON object (fences and chatter tolerated), or None when there is no usable one."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict) or obj.get("verdict") not in ("approve", "request_changes"):
        return None
    findings = obj.get("findings", [])
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        return None
    return {"verdict": obj["verdict"], "findings": findings}


def _norm(path: object) -> str:
    return str(path).replace("\\", "/").strip().removeprefix("b/")


def _hits(c: rc.Control, finding: dict) -> bool:
    """A finding catches the defect when it names the defect's file and quotes the defect's line."""
    key = rc.answer_key(c)
    quote = " ".join(str(finding.get("line_text", "")).split())
    if _norm(finding.get("file", "")) != key["file"] or not quote:
        return False
    where = " ".join(key["where"].split())
    changed = [" ".join(ln.split()) for ln in c.files[key["file"]].splitlines()]
    return where in quote or any(quote == ln for ln in changed if where in ln)


def score_review(c: rc.Control, raw: str) -> dict:
    """Score one review of one diff. `caught` is None on a clean twin; `false_alarm` is a blocked twin or a stray finding."""
    review = parse_review(raw)
    if review is None:
        return {"key": c.key, "defective": bool(c.cls), "malformed": True, "caught": False if c.cls else None,
                "false_alarm": False, "blocked": False, "stray": 0}  # fmt: skip
    findings = review["findings"]
    hit = any(_hits(c, f) for f in findings) if c.cls else None
    stray = len(findings) - sum(1 for f in findings if c.cls and _hits(c, f))
    blocked = review["verdict"] == "request_changes"
    return {
        "key": c.key,
        "defective": bool(c.cls),
        "malformed": False,
        "caught": hit,
        "false_alarm": stray > 0 or (not c.cls and blocked),
        "blocked": blocked,
        "stray": stray,
    }


def is_errored(row: dict) -> bool:
    """A call that produced no review (nonzero exit, timeout, empty output) says nothing about the reviewer."""
    return bool(row.get("exit", 0) != 0 or row.get("error") or not str(row.get("raw", "")).strip())


def score_results(results: list[dict]) -> list[dict]:
    """`results` rows are {model, key, raw[, run, exit, error]}; each gains its score, or `errored` and no score."""
    return [
        {**r, "defective": bool(rc.BY_KEY[r["key"]].cls), "errored": True}
        if is_errored(r)
        else {**r, **score_review(rc.BY_KEY[r["key"]], r["raw"]), "errored": False}
        for r in results
    ]


def report(results: list[dict]) -> dict:
    """Per model: catch rate by defect class and false-alarm rate on clean twins, with n. Then the first-two-model delta."""
    scored = score_results(results)
    models: dict[str, dict] = {}
    for row in scored:
        m = models.setdefault(row["model"], {"catch": {}, "twin_false_alarms": [0, 0], "stray_on_defective": 0,
                                             "malformed": 0, "errored": 0})  # fmt: skip
        if row["errored"]:
            m["errored"] += 1
            continue
        m["malformed"] += int(row["malformed"])
        if row["defective"]:
            cell = m["catch"].setdefault(rc.BY_KEY[row["key"]].cls, [0, 0])
            cell[0] += int(bool(row["caught"]))
            cell[1] += 1
            m["stray_on_defective"] += row["stray"]
        else:
            m["twin_false_alarms"][0] += int(row["false_alarm"])
            m["twin_false_alarms"][1] += 1
    for m in models.values():
        caught, n = (sum(v[i] for v in m["catch"].values()) for i in (0, 1))
        m["catch_rate"] = [caught, n]
    out: dict = {
        "models": models,
        "note": f"n is {sum(v['catch_rate'][1] for v in models.values())} completed defective reviews over "
        f"{len(rc.CONTROLS) // 2} defects (errored calls are counted apart and left out of every rate): "
        "read counts, not percentages; no verdict is drawn from a set this small",
    }
    names = list(models)
    if len(names) >= 2:
        a, b = names[0], names[1]
        out["delta"] = {
            "a": a,
            "b": b,
            "catch_rate": [models[a]["catch_rate"], models[b]["catch_rate"]],
            "twin_false_alarms": [models[a]["twin_false_alarms"], models[b]["twin_false_alarms"]],
        }
    return out


def render_markdown(rep: dict) -> str:
    """The report as a table for a committed page: counts with n per model, errored calls apart, then the delta."""
    lines = ["| model | caught | false alarms on twins | stray findings on defects | errored | malformed |",
             "|---|---|---|---|---|---|"]  # fmt: skip
    for name, m in rep["models"].items():
        by_cls = ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(m["catch"].items()))
        caught = f"{m['catch_rate'][0]}/{m['catch_rate'][1]}" + (f" ({by_cls})" if by_cls else "")
        fa = m["twin_false_alarms"]
        lines.append(
            f"| {name} | {caught} | {fa[0]}/{fa[1]} | {m['stray_on_defective']} | {m['errored']} | {m['malformed']} |"
        )
    if "delta" in rep:
        d = rep["delta"]
        ca, cb = d["catch_rate"]
        fa, fb = d["twin_false_alarms"]
        lines.append("")
        lines.append(f"Delta {d['a']} vs {d['b']}: caught {ca[0]}/{ca[1]} vs {cb[0]}/{cb[1]}; "
                     f"false alarms {fa[0]}/{fa[1]} vs {fb[0]}/{fb[1]}.")  # fmt: skip
    lines += ["", rep["note"]]
    return "\n".join(lines)


def estimate(models: list[str], repeats: int) -> dict:
    """The size of a run, for the dry run: reviews and rough input tokens (output is a short JSON object)."""
    chars = sum(len(prompt_for(c)) for c in rc.CONTROLS)
    return {
        "reviews": len(rc.CONTROLS) * len(models) * repeats,
        "input_tokens": chars // CHARS_PER_TOKEN * len(models) * repeats,
    }


def run(models: list[str], repeats: int) -> list[dict]:
    """Ask each model to review each diff. Calls a model: only reached with --owner-ok."""
    rows = []
    for model in models:
        for c in rc.CONTROLS:
            for i in range(repeats):
                row = {"model": model, "key": c.key, "run": i}
                try:
                    p = subprocess.run(  # noqa: S603
                        ["claude", *CLAUDE_ARGS[:1], "--model", model, *CLAUDE_ARGS[1:]],  # noqa: S607
                        input=prompt_for(c), capture_output=True, text=True, timeout=RUN_TIMEOUT_S, check=False,
                        encoding="utf-8",
                    )  # fmt: skip
                except subprocess.TimeoutExpired:
                    rows.append({**row, "raw": "", "exit": None, "error": f"timeout after {RUN_TIMEOUT_S}s"})
                    continue
                err = (p.stderr or "")[-300:].strip() if p.returncode != 0 else ""
                rows.append({**row, "raw": p.stdout, "exit": p.returncode, "error": err})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt").add_argument("key", choices=sorted(rc.BY_KEY))
    r = sub.add_parser("run")
    r.add_argument("--models", default="sonnet,opus")
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--max-reviews", type=int, help="refuse a run larger than this many reviews")
    r.add_argument("--owner-ok", action="store_true", help="the experiment lane's OK: without it nothing is called")
    r.add_argument("--out", help="where to write the raw reviews (outside the repo)")
    rp = sub.add_parser("report")
    rp.add_argument("results")
    rp.add_argument("--markdown", action="store_true", help="print a table instead of JSON")
    args = ap.parse_args(argv)
    bad = rc.problems()
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    if args.cmd == "prompt":
        print(prompt_for(rc.BY_KEY[args.key]))
    elif args.cmd == "report":
        rep = report(json.loads(Path(args.results).read_text(encoding="utf-8")))
        print(render_markdown(rep) if args.markdown else json.dumps(rep, indent=2))
    else:
        models = [m for m in re.split(r"[,\s]+", args.models) if m]
        size = estimate(models, args.repeats)
        print(json.dumps({"dry_run": not args.owner_ok, **size}))
        if args.max_reviews is not None and size["reviews"] > args.max_reviews:
            print(f"refused: {size['reviews']} reviews exceeds --max-reviews {args.max_reviews}", file=sys.stderr)
            return 2
        if not args.owner_ok:
            print("dry run: pass --owner-ok (experiment lane) to call the models", file=sys.stderr)
            return 0
        rows = run(models, args.repeats)
        text = json.dumps(rows, indent=2)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
