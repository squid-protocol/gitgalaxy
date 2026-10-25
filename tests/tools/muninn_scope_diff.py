"""#5499: compare two Muninn SARIF files from one SHA (full tree vs the PR's sparse paths).

    muninn_scope_diff.py FULL.sarif PR.sarif [--scope /gitgalaxy/ ...]

Both sides are cut to the paths the PR checkout keeps (default: the `sparse-checkout` list of the PR step in
`muninn.yml`); exit 0 only when the cut sets are equal. Findings that exist only on the full scan and lie outside the
scope are summarised by top-level directory, which answers "which directories dominate" without failing the run.
Stdlib only apart from the lazy `yaml` import used to read the default scope.
"""

import argparse
import fnmatch
import json
import sys
from collections import Counter
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "muninn.yml"


def default_scope(workflow=None):
    """The sparse-checkout entries of the PR checkout step in the workflow."""
    import yaml

    doc = yaml.safe_load(Path(workflow or WORKFLOW).read_text(encoding="utf-8"))
    for step in doc["jobs"]["muninn"]["steps"]:
        if "sparse-checkout" in step.get("with", {}):
            return step["with"]["sparse-checkout"].split()
    raise SystemExit("no sparse-checkout step in the workflow")


def in_scope(path, scope):
    path = "/" + path.lstrip("/")
    return any(path.startswith(e) if e.endswith("/") else fnmatch.fnmatch(path, e) for e in scope)


def load(sarif):
    """The set of (rule, path, line, message) tuples of a SARIF file."""
    data = json.loads(Path(sarif).read_text(encoding="utf-8"))
    found = set()
    for run in data.get("runs", []):
        for res in run.get("results") or []:
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            uri = loc.get("artifactLocation", {}).get("uri", "")
            found.add(
                (
                    res.get("ruleId", ""),
                    uri,
                    loc.get("region", {}).get("startLine", 0),
                    res.get("message", {}).get("text", ""),
                )
            )
    return found


def compare(full, pr, scope):
    """(only_full_in_scope, only_pr_in_scope, outside_scope_dirs) for two result sets."""
    cut = lambda s: {r for r in s if in_scope(r[1], scope)}  # noqa: E731
    f_in, p_in = cut(full), cut(pr)
    outside = Counter(r[1].lstrip("/").split("/")[0] or "(root)" for r in full - f_in)
    return f_in - p_in, p_in - f_in, outside


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("full")
    ap.add_argument("pr")
    ap.add_argument("--scope", nargs="*", help="sparse-checkout style entries (default: read muninn.yml)")
    args = ap.parse_args(argv)
    scope = args.scope or default_scope()
    only_full, only_pr, outside = compare(load(args.full), load(args.pr), scope)
    for label, rows in (("only on the full scan, inside the scope", only_full), ("only on the PR scan", only_pr)):
        print(f"{label}: {len(rows)}")
        for row in sorted(rows):
            print("  ", *row)
    print("full-scan findings outside the scope, by top-level directory:", dict(outside.most_common()))
    return 1 if only_full or only_pr else 0


if __name__ == "__main__":
    sys.exit(main())
