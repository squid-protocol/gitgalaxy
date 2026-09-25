#!/usr/bin/env python3
"""
The blast radius of an engine-reader change (#3653): every argument-free GalaxyIR
join, base ref vs working tree, on the pinned mainframe corpora.

    python tests/tools/ir_join_diff.py --base origin/main [--corpus NAME ...] [--rescan]
                                       [--expect-none] [--json OUT]

Each corpus is scanned once with the working tree's scanner into
.ir_join_diff_cache/<corpus>/ (reused until --rescan) and read by both versions of
gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py: the base's from `git show`, the working
tree's by import. Lists are compared as multisets of rows, dicts per key. This
compares the READER on one DB; a scanner change needs --rescan and a scan per side.
"""

import argparse
import contextlib
import dataclasses
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.tools.cobol_to_cobol import galaxy_ir

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mainframe_corpus


class DataclassEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return str(obj)


def serialize_row(row: Any) -> str:
    return json.dumps(row, cls=DataclassEncoder, sort_keys=True)


def compare_rows(
    old: Union[List[Any], Dict[Any, Any]], new: Union[List[Any], Dict[Any, Any]]
) -> Tuple[List[str], List[str]]:
    """Compare old and new rows, returning (removed, added).
    Supports lists (multiset semantics, duplicates count, order-insensitive)
    and dicts (compare per key).
    """
    removed: List[str] = []
    added: List[str] = []

    if isinstance(old, dict) and isinstance(new, dict):
        old_keys = set(old.keys())
        new_keys = set(new.keys())

        for k in old_keys - new_keys:
            removed.append(serialize_row({k: old[k]}))

        for k in new_keys - old_keys:
            added.append(serialize_row({k: new[k]}))

        for k in old_keys & new_keys:
            old_val = serialize_row(old[k])
            new_val = serialize_row(new[k])
            if old_val != new_val:
                removed.append(serialize_row({k: old[k]}))
                added.append(serialize_row({k: new[k]}))
    else:
        old_counts: Dict[str, int] = {}
        if isinstance(old, dict):
            # If old is a dict but new is not, this handles gracefully or crashes depending.
            # We assume both are lists if we reach here, or both are iterables.
            old_iter = old.values()
        else:
            old_iter = old

        for item in old_iter:
            s = serialize_row(item)
            old_counts[s] = old_counts.get(s, 0) + 1

        new_counts: Dict[str, int] = {}
        if isinstance(new, dict):
            new_iter = new.values()
        else:
            new_iter = new

        for item in new_iter:
            s = serialize_row(item)
            new_counts[s] = new_counts.get(s, 0) + 1

        for s, count in old_counts.items():
            diff = count - new_counts.get(s, 0)
            if diff > 0:
                removed.extend([s] * diff)

        for s, count in new_counts.items():
            diff = count - old_counts.get(s, 0)
            if diff > 0:
                added.extend([s] * diff)

    removed.sort()
    added.sort()
    return removed, added


def joins(cls: type) -> List[str]:
    """Returns a list of public method names of cls that can be called with no arguments."""
    valid_methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        try:
            sig = inspect.signature(method)
        except ValueError:
            continue

        params = list(sig.parameters.values())
        if not params or params[0].name != "self":
            continue

        can_call_no_args = True
        for p in params[1:]:
            if p.default == inspect.Parameter.empty and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                can_call_no_args = False
                break

        if can_call_no_args:
            valid_methods.append(name)

    return sorted(valid_methods)


@contextlib.contextmanager
def _quiet_stdout():
    """Silence file descriptor 1 -- a subprocess inherits it, so redirect_stdout is not enough."""
    sys.stdout.flush()
    saved, devnull = os.dup(1), os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    try:
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)
        os.close(devnull)


def load_base_galaxy_ir(base_ref: str) -> Any:
    """Loads galaxy_ir.py from the given git ref as a new module 'galaxy_ir_base'."""
    cmd = ["git", "show", f"{base_ref}:gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py"]
    try:
        content = subprocess.check_output(cmd, cwd=REPO_ROOT, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        sys.exit(f"Failed to get galaxy_ir.py from {base_ref}: {e}")

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(content.encode("utf-8"))
        temp_path = f.name

    try:
        spec = importlib.util.spec_from_file_location("galaxy_ir_base", temp_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load spec for base galaxy_ir")
        module = importlib.util.module_from_spec(spec)
        sys.modules["galaxy_ir_base"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        os.remove(temp_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="""
Compare GalaxyIR joins between a base git ref and the working tree.
Note: this compares the READER (galaxy_ir.py) on the same DB; scanner changes are out of scope.
"""
    )
    parser.add_argument("--base", required=True, help="Base git ref to compare against (e.g. origin/main)")
    parser.add_argument("--corpus", nargs="+", dest="corpora", help="Corpus names to scan and compare")
    parser.add_argument("--rescan", action="store_true", help="Force rescan of corpora")
    parser.add_argument("--expect-none", action="store_true", help="Exit 1 if any join changed")
    parser.add_argument("--json", dest="json_out", help="Output full results to JSON file")

    args = parser.parse_args()

    corpora_names = args.corpora
    if not corpora_names:
        corpora_names = [c["name"] for c in mainframe_corpus.load_manifest()]

    base_module = load_base_galaxy_ir(args.base)
    head_module = galaxy_ir

    base_joins = set(joins(base_module.GalaxyIR))
    head_joins = set(joins(head_module.GalaxyIR))

    common_joins = sorted(list(base_joins & head_joins))

    full_results: Dict[str, Any] = {}
    any_changed = False

    for corpus_name in corpora_names:
        corpus = mainframe_corpus.select([corpus_name])[0]
        repo_path = mainframe_corpus.require_clone(corpus)

        cache_dir = REPO_ROOT / ".ir_join_diff_cache" / corpus_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        db_path = cache_dir / f"{corpus_name}_galaxy_master.db"

        if args.rescan or not db_path.exists():
            with _quiet_stdout():  # the scanner subprocess's banners
                head_module.scan_to_db(repo_path, cache_dir)

        if not db_path.exists():
            print(f"Error: DB not found at {db_path} after scan.", file=sys.stderr)
            continue

        base_ir = base_module.load_galaxy_ir(db_path)
        head_ir = head_module.load_galaxy_ir(db_path)

        corpus_results: Dict[str, Any] = {}

        for j in base_joins - head_joins:
            corpus_results[j] = {"status": "removed"}
        for j in head_joins - base_joins:
            corpus_results[j] = {"status": "added"}

        changed_joins = []

        for j in common_joins:
            base_method = getattr(base_ir, j)
            head_method = getattr(head_ir, j)

            base_val = None
            head_val = None
            base_error = None
            head_error = None

            try:
                base_val = base_method()
            except Exception:
                base_error = traceback.format_exc()

            try:
                head_val = head_method()
            except Exception:
                head_error = traceback.format_exc()

            if base_error or head_error:
                corpus_results[j] = {
                    "status": "error",
                    "base_error": base_error,
                    "head_error": head_error,
                }
                changed_joins.append(j)
                continue

            # Ensure both returned value exist, they could be None?
            if base_val is None:
                base_val = []
            if head_val is None:
                head_val = []

            removed, added = compare_rows(base_val, head_val)
            if removed or added:
                corpus_results[j] = {
                    "status": "changed",
                    "removed": removed,
                    "added": added,
                }
                changed_joins.append(j)
            else:
                corpus_results[j] = {"status": "unchanged"}

        full_results[corpus_name] = corpus_results

        print(f"== {corpus_name}: {len(common_joins)} joins compared, {len(changed_joins)} changed")
        for j in changed_joins:
            any_changed = True
            res = corpus_results[j]
            if res["status"] == "error":
                print(f"  {j}: error")
                if res.get("base_error"):
                    print(f"    base: {res['base_error'].strip().splitlines()[-1]}")
                if res.get("head_error"):
                    print(f"    head: {res['head_error'].strip().splitlines()[-1]}")
            else:
                removed = res["removed"]
                added = res["added"]
                print(f"  {j}: -{len(removed)} +{len(added)}")
                for r in removed[:2]:
                    r_str = str(r)
                    if len(r_str) > 300:
                        r_str = r_str[:297] + "..."
                    print(f"    - {r_str}")
                for a in added[:2]:
                    a_str = str(a)
                    if len(a_str) > 300:
                        a_str = a_str[:297] + "..."
                    print(f"    + {a_str}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(full_results, f, indent=2)

    if args.expect_none and any_changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
