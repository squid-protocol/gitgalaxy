#!/usr/bin/env python3
"""#5054 done-when 4: feed each BURNED estate's survey through the customer blocker pipeline and check what comes out.

    python tests/tools/blocker_estate_feed.py DIR [--label before ...] [--out OUT] [--corpora DIR] [--extra-root DIR ...]

DIR is a `cics_census.py survey` directory (DIR/<label>-*/survey.json). For every burned estate in it (estate4_draw
BURNED_NAMES, plus the cics-crucible cells) the rows are split by corpus, ranked by proof_blockers.proof_blockers,
written as the full + anonymized report (blocker_report.write_reports, a fixed CI salt) and ingested into a scratch
ledger (blocker_ingest.ingest), the way a customer's report would be. Then it checks:

  * rows: one ledger row per distinct classified blocker, each with the full report's counts (programs only blocked
    by it, programs one gap away), under the same category;
  * links: a signature the catalogue knows links to its issue, whatever the salt;
  * hashes: the same salt gives the same ids, another salt gives other ones;
  * leak: no identifier of the estate's own sources (program, copybook, field names, file stems) is a word of the
    anonymized output.

Writes OUT/<estate>/ (the four report files, ledger.json) and OUT/feed.json + OUT/feed.md. feed.json holds, per
estate, the rows that match no issue yet: the feed for the tick (and for `cics_census.py blockers`) to turn into issues.
`blocker_estate_feed.py queue --feed FILE | --generated` turns those rows into the churn queue (drafted issue bodies).
--require-sources makes a missing estate checkout a failure (CI uses it). Exit 1 on any failed check. Only burned estates are read; a census corpus is skipped by name.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))
import blocker_ingest as bi  # noqa: E402
import blocker_report as br  # noqa: E402
import cics_census as cc  # noqa: E402
import estate4_draw  # noqa: E402
import proof_blockers as pb  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402

CI_SALT = bytes.fromhex("5054" * 16)
OTHER_SALT = bytes.fromhex("4505" * 16)
_NAME = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b|\b[A-Z]{3,8}\d{2,}[A-Z0-9]*\b")
_WORD = re.compile(r"[A-Za-z0-9_-]+")
_SOURCE_SUFFIXES = {".cbl", ".cob", ".cpy"}
# COBOL words the synthetic repro snippets are written in: language, not the estate's
RESERVED = frozenset({"PROGRAM-ID", "WORKING-STORAGE", "END-EXEC", "LOCAL-STORAGE", "LINKAGE-SECTION", "FILE-SECTION", "END-IF", "END-PERFORM"})  # fmt: skip


def is_burned(corpus: str) -> bool:
    low = corpus.lower()
    return low in estate4_draw.BURNED_NAMES or "cics-crucible" in low


def split_by_estate(rows: dict[tuple[str, str], dict[str, Any]]) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    out: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for (corpus, prog), r in rows.items():
        if is_burned(corpus):
            out.setdefault(corpus, {})[(corpus, prog)] = r
    return out


def source_names(root: Path, limit: int = 4000) -> set[str]:
    """Identifiers the estate's own sources hold that a report must not carry (public CICS vocabulary excluded)."""
    names: set[str] = set()
    for f in sorted(root.rglob("*"))[:limit]:
        if f.suffix.lower() in _SOURCE_SUFFIXES and f.is_file() and f.stat().st_size < 400_000:
            names.update(_NAME.findall(read_source(f).text))
            names.add(f.stem.upper())
    # the manifest's field descriptions are fixed text, the same for every customer: a source named CUSTOMER (CBSA) is
    # not a leak because the prose says "customer salt"
    prose = {
        w.upper() for d in (*br.ANON_BLOCKER_FIELDS.values(), *br.ANON_REPORT_FIELDS.values()) for w in _WORD.findall(d)
    }
    vocab = br.vocabulary() | prose
    return {n for n in names if len(n) >= 4 and n not in vocab and n not in RESERVED and not bi._public_word(n)}


def find_sources(roots: list[Path], estate: str) -> Path | None:
    """The estate's checkout: `root/<estate>`, or a root that is itself the estate (the cics-crucible checkout is passed
    as --extra-root, so `root/cics-crucible` does not exist and the leak scan was silently skipped)."""
    for r in roots:
        if (r / estate).is_dir():
            return r / estate
        if r.name.lower() == estate.lower() and r.is_dir():
            return r
    return None


def leaked(names: set[str], text: str) -> list[str]:
    words = {w.upper() for w in _WORD.findall(text)}
    return sorted(names & words)


def check_estate(estate: str, res: dict[str, Any], out: Path, src: Path | None, catalogue: list[dict[str, Any]]):
    """Run one estate through report + ingest; return (problems, summary, rows that match no issue)."""
    problems: list[str] = []
    paths = br.write_reports(res, out, CI_SALT, estate)
    anon = json.loads(paths["anon_json"].read_text(encoding="utf-8"))
    ledger: dict[str, Any] = {}
    fresh = bi.ingest(anon, ledger, catalogue)
    (out / "ledger.json").write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")
    rows = {r["id"]: r for r in ledger["rows"]}

    # every blocker of the full report appears, under the same category, with the same counts
    expect: dict[str, dict[str, Any]] = {}
    for g in res.get("gaps", []):
        cat, _sub, sig = br.classify(g["gap"], CI_SALT)
        e = expect.setdefault(
            bi.row_id(anon["estate"], br.hashed(CI_SALT, "BLK", sig)), {"category": cat, "only": 0, "one": 0}
        )
        e["only"] += g.get("only", 0)
        e["one"] += g.get("one_away", 0)
    if set(rows) != set(expect):
        problems.append(f"{estate}: {len(rows)} ledger rows for {len(expect)} blockers in the full report")
    for rid, e in expect.items():
        r = rows.get(rid)
        if r and (r["category"], r["programs_only_gap"], r["programs_one_away"]) != (
            e["category"],
            e["only"],
            e["one"],
        ):
            problems.append(f"{estate}: {rid} is {r['category']}/{r['programs_only_gap']}/{r['programs_one_away']}, "
                            f"full report says {e['category']}/{e['only']}/{e['one']}")  # fmt: skip
    for r in rows.values():
        want = bi.match_issue(r["category"], r["signature"], catalogue)
        if want is not None and r["issue"] != want:
            problems.append(f"{estate}: {r['id']} should link to #{want}, links to {r['issue']}")

    # hashes: stable per salt, different with another salt
    again = br.anon_report(res, CI_SALT, estate)
    other = br.anon_report(res, OTHER_SALT, estate)
    ids = [b["id"] for b in anon["blockers"]]
    if ids != [b["id"] for b in again["blockers"]]:
        problems.append(f"{estate}: blocker ids changed between runs with the same salt")
    if ids and set(ids) & {b["id"] for b in other["blockers"]}:
        problems.append(f"{estate}: a blocker id is the same under another salt")
    if anon["estate"] == other["estate"]:
        problems.append(f"{estate}: the estate hash is the same under another salt")

    # leak: nothing of the estate's sources, nor its name, in the anonymized output
    checked_sources = bool(src and src.is_dir())
    if src is not None and checked_sources:
        text = paths["anon_json"].read_text(encoding="utf-8") + paths["anon_md"].read_text(encoding="utf-8")
        hit = leaked(source_names(src), text)
        if hit:
            problems.append(f"{estate}: the anonymized report carries source names: {', '.join(hit[:10])}")
        if estate.lower() in text.lower():
            problems.append(f"{estate}: the anonymized report carries the estate name")
    summary = {"estate": estate, "programs": len(res.get("programs", [])), "blockers": len(rows),
               "linked": sum(1 for r in rows.values() if r["issue"]), "unmatched": len(fresh),
               "leak_checked": checked_sources}  # fmt: skip
    return problems, summary, fresh


def run(rows: dict[tuple[str, str], dict[str, Any]], roots: list[Path], out: Path, *, compute=None, catalogue=None,
        require_sources: bool = False):  # fmt: skip
    """Every burned estate in `rows`. `compute(rows, roots)` is the proof_blockers ranking (injected by tests).
    `require_sources` fails an estate whose sources were not found, so CI never passes without the leak scan (done-when 2)."""
    catalogue = bi.load_catalogue() if catalogue is None else catalogue
    compute = compute or (lambda r, rt: pb.proof_blockers(r, rt, only_cics=True))
    problems: list[str] = []
    summaries: list[dict[str, Any]] = []
    feed: dict[str, list[dict[str, Any]]] = {}
    for estate, est_rows in sorted(split_by_estate(rows).items()):
        src = find_sources(roots, estate)
        p, s, fresh = check_estate(estate, compute(est_rows, roots), out / estate, src, catalogue)
        if require_sources and not s["leak_checked"]:
            p.append(f"{estate}: the leak scan did not run (sources not found under the given roots)")
        problems += p
        summaries.append(s)
        feed[estate] = [{**r, "issue_body": bi.draft_issue(r)} for r in fresh]
    if not summaries:
        problems.append("no burned estate in the survey")
    (out / "feed.json").write_text(
        json.dumps({"schema": 1, "estates": summaries, "unmatched": feed}, indent=1) + "\n", encoding="utf-8"
    )
    (out / "feed.md").write_text(markdown(summaries, problems), encoding="utf-8")
    return problems, summaries


FEED_PATH = "docs/language_status/blockers/blocker_feed.json"


def queue(feed: dict[str, Any], filed: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """The churn queue from a feed.json: one item per distinct construct (category + salt-free signature), however many
    estates or customers report it; `ids` lists its rows. A construct already in `filed` has its issue and is not queued."""
    seen: dict[str, dict[str, Any]] = {}
    for rows in feed.get("unmatched", {}).values():
        for r in sorted(rows, key=lambda x: x["id"]):
            key = bi.signature_key(r["category"], r["signature"])
            if filed and key in filed:
                continue
            item = seen.setdefault(key, {"id": r["id"], "ids": [], "key": key, "category": r["category"],
                                         "class": r["class"], "side": r["side"], "signature": r["signature"],
                                         "body": r.get("issue_body") or bi.draft_issue(r)})  # fmt: skip
            if r["id"] not in item["ids"]:
                item["ids"].append(r["id"])
    return sorted(seen.values(), key=lambda i: i["id"])


def _read_feed(args: argparse.Namespace) -> dict[str, Any]:
    if args.generated:
        import generated_branch

        data = generated_branch.read_published(FEED_PATH, REPO)
        if data is None:
            raise SystemExit(f"{FEED_PATH} is not published on the generated branch yet")
        return json.loads(data.decode("utf-8"))
    return json.loads(args.feed.read_text(encoding="utf-8"))


def gh_create_issue(title: str, body: str) -> int:
    """Open an issue on the repo through the REST API (gh 2.45 fails on the GraphQL path) and return its number."""
    import subprocess

    out = subprocess.run(
        ["gh", "api", "repos/squid-protocol/gitgalaxy/issues", "-f", f"title={title}", "-f", f"body={body}", "-q", ".number"],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    return int(out.stdout.strip())


def file_issues(items: list[dict[str, Any]], filed_path: Path, create: Any = None) -> list[tuple[dict[str, Any], int]]:
    """Open one issue per queue item (`create` makes the issue; the CLI passes gh_create_issue only with --open-issues) and record each under its signature key in
    `filed_path`, so the next ingest links to it and the next queue skips it."""
    done: list[tuple[dict[str, Any], int]] = []
    data = json.loads(filed_path.read_text(encoding="utf-8")) if filed_path.is_file() else {"schema": 1, "filed": {}}
    for it in items:
        if it["key"] in data["filed"]:
            continue
        n = create(f"Customer blocker: {it['signature']} ({it['category']})", it["body"])
        data["filed"][it["key"]] = n
        done.append((it, n))
        filed_path.parent.mkdir(parents=True, exist_ok=True)
        filed_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")  # after each: a crash loses none
    return done


def queue_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="blocker_estate_feed.py queue", description="Turn unmatched feed rows into the churn queue."
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--feed", type=Path, help="a feed.json")
    src.add_argument("--generated", action="store_true", help=f"read {FEED_PATH} from the generated branch")
    ap.add_argument("--out", type=Path, help="write the queue as JSON here")
    ap.add_argument("--filed", type=Path, help="signatures already opened as issues: left out of the queue")
    ap.add_argument("--open-issues", action="store_true", help="open one issue per queued construct (needs --filed)")
    args = ap.parse_args(argv)
    if args.open_issues and not args.filed:
        raise SystemExit("--open-issues needs --filed (where the opened issue numbers are recorded)")
    items = queue(_read_feed(args), bi.load_filed(args.filed))
    if args.out:
        args.out.write_text(json.dumps(items, indent=1) + "\n", encoding="utf-8")
    print(f"{len(items)} unmatched blocker constructs for the queue")
    for it in items:
        print(it["body"])
    if args.open_issues:
        for it, n in file_issues(items, args.filed, gh_create_issue):
            print(f"opened #{n} for {it['key']}")
    return 0


def markdown(summaries: list[dict[str, Any]], problems: list[str]) -> str:
    lines = [
        "| estate | programs | blockers | linked to an issue | unmatched | leak scan |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {s['estate']} | {s['programs']} | {s['blockers']} | {s['linked']} | {s['unmatched']} | "
        f"{'ran' if s['leak_checked'] else 'sources not checked out'} |"
        for s in summaries
    )
    lines += ["", *(f"- FAIL {p}" for p in problems)] if problems else ["", "All checks passed."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["queue"]:
        return queue_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="a cics_census.py survey directory")
    ap.add_argument("--label", nargs="+", default=["before"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--corpora", type=Path, help="the burned corpora root (as cics_census.py)")
    ap.add_argument("--extra-root", type=Path, nargs="*", default=[])
    ap.add_argument("--require-sources", action="store_true", help="fail when an estate's leak scan could not run")
    args = ap.parse_args(argv)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for label in args.label:
        rows.update(cc.load_surveys(args.dir, label))
    if not rows:
        raise SystemExit(f"no {'/'.join(args.label)}-*/survey.json under {args.dir}")
    args.out.mkdir(parents=True, exist_ok=True)
    problems, _summaries = run(rows, [cc.mainframe_root(args.corpora), *args.extra_root], args.out,
                           require_sources=args.require_sources)  # fmt: skip
    print((args.out / "feed.md").read_text(encoding="utf-8"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
