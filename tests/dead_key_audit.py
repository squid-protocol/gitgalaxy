#!/usr/bin/env python3
"""
Dead Key Auditor (#325)

Finds dict keys that a consumer reads (.get("key"), ["key"], .pop("key"))
somewhere in gitgalaxy/, but that no producer anywhere in gitgalaxy/ ever
writes (["key"] = ..., a {"key": ...} literal/comprehension, .setdefault(
"key", ...), or a dict(key=...)/​.update(key=...) keyword). That failure
shape -- a read against a producer that was never built, or was renamed
later without updating the consumer -- was found six independent times by
hand (see #325); this is the "automate the manual diff" half of that issue.

USAGE
    python tests/dead_key_audit.py          # full report, exits 1 if anything
                                             # un-allowlisted is found -- use
                                             # this to re-tune ALLOWLIST or to
                                             # refresh the baseline below.
    python tests/dead_key_audit.py --ci      # baseline-gated regression check
                                             # (see BASELINE below) -- this is
                                             # what CI runs.

BASELINE (#325 sub-task 3)
This repo had 15 confirmed-real, not-yet-fixed instances of this pattern the
day this check was wired into CI (see dead_key_audit_baseline.json). Hard
failing on those immediately would block every unrelated PR until all 15
were fixed first, so `--ci` mode is a REGRESSION gate, not a zero-tolerance
one: it fails only on keys not already in the baseline. Fixing a baselined
key doesn't fail the build either -- shrinking the baseline is a deliberate,
reviewable edit you make yourself (matching #330's "deliberate, reviewable
updates instead of silent overwrite" philosophy for golden_master.json),
not something this script does automatically. `--ci` prints anything it
notices has already been fixed as an FYI, so the baseline doesn't silently
go stale, but it does not fail the build over it.

SCOPE & LIMITATIONS (read before treating a hit as a confirmed bug)
This is a purely syntactic, whole-repo string-literal cross-reference. It
has no type information, so "key" is one flat global namespace regardless
of which dict it actually belongs to -- a real false negative is a key
that's read from an unrelated producer of the same name elsewhere in the
repo, and a real false positive is a key that IS produced, but only via
a runtime-computed key the walker can't resolve to a literal (a variable,
a function return value, etc). The PREFIX_WRITES handling below recovers
the single largest source of that -- f-string-templated keys like
f"sec_{sec_key}" -- but arbitrary indirection (e.g. CORE_MAPPING-style
rule-name remapping through a dict lookup) is still invisible to it.
Treat every hit as a lead to grep-confirm by hand, not a proven bug.

External-schema keys (parsed YAML/JSON config, third-party API responses,
lockfile fields, etc.) are real reads with no producer *in this repo* by
design -- those go in ALLOWLIST below, with a comment saying why.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Set, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = [REPO_ROOT / "gitgalaxy"]
BASELINE_PATH = Path(__file__).resolve().parent / "dead_key_audit_baseline.json"

# ==============================================================================
# ALLOWLIST -- tuned from a real run against this repo, not guessed in
# advance (#325's sub-task 2). Each entry is a key this script currently
# flags that is NOT an instance of the #325 pattern. Keep the reason with
# the entry: it's the only thing that lets a future run tell "still valid"
# apart from "the code changed, re-check this."
# ==============================================================================
ALLOWLIST = {
    # --- External package manifests (package.json / composer.json / lockfiles) ---
    # manifest_parser.py and guidestar_lens.py json.load() a THIRD-PARTY file;
    # these keys are that file format's schema, not a dict this repo produces.
    "dependencies": "package.json/composer.json field (manifest_parser.py)",
    "devDependencies": "package.json field (manifest_parser.py)",
    "require": "composer.json field (manifest_parser.py)",
    "require-dev": "composer.json field (manifest_parser.py)",
    "packages": "composer.lock field (manifest_parser.py)",
    "resolved": "composer.lock field (manifest_parser.py)",
    "bin": "package.json field (guidestar_lens.py)",
    "main": "package.json field (guidestar_lens.py)",
    "scripts": "package.json field (guidestar_lens.py)",
    # --- External model/tensor files ---
    # tensor_scanner.py json.loads()'s a .safetensors file's own header; these
    # are that format's reserved/per-tensor keys, not ours.
    "__metadata__": "safetensors header reserved key (tensor_scanner.py)",
    "format": "safetensors per-tensor header field (tensor_scanner.py)",
    "shape": "safetensors per-tensor header field (tensor_scanner.py)",
    # func_ml_brain/repo_model are loaded ML archetype-clustering artifacts;
    # the .get(..., [...]) fallback is explicitly "Bulletproof fallback names
    # if the model dictionary forgets them" per signal_processor.py's own
    # comment -- absence is the designed case, not a bug.
    "cluster_names": "optional ML archetype-model field, has an explicit fallback (signal_processor.py)",
    # --- External YAML/env config ---
    "galaxyscope": "top-level section name in a user's .galaxyscope.yml project config file",
    "GITGALAXY_LICENSE_KEY": "environment variable (os.environ.get), not a repo-produced dict",
    "vulnerability_density_min": "optional risk_tuning YAML key (signal_processor.py._calc_injection_surface-style tuning)",
    "asymptotic_dampener": "optional risk_tuning YAML key (signal_processor.py)",
    "quarantine": "STATIC_ARCHETYPES app-config constant, read with a graceful string fallback",
    # --- Explicit dual/legacy-schema compatibility shims ---
    # spatial_mapper.py's own docstring: "Safely extracts structural magnitude
    # regardless of which JSON version the pipeline is using."
    "forensics": "legacy-schema compatibility branch (spatial_mapper.py, self-documented)",
    # Defensive SECONDARY key in a.get("primary", a.get("filename", default))
    # fallback chain -- "path"/"name" is the real, always-written key.
    "filename": "defensive fallback alt-key, not the primary key (spatial_mapper.py)",
    # --- SQLite Row column access ---
    # state_rehydrator.py reads sqlite3.Row objects like dicts; these column
    # names live in record_keeper.py's CREATE TABLE schema (confirmed present
    # there), not in a Python dict literal this walker can see.
    "author": "SQLite column, schema confirmed in record_keeper.py (state_rehydrator.py)",
    "file_path": "SQLite column, schema confirmed in record_keeper.py (state_rehydrator.py)",
    "src/hacked.py": "test fixture value inside state_rehydrator.py's own embedded test, not a real key",
    # --- Dynamically-keyed dicts (walker can't trace the indirection) ---
    # audit_recorder.py builds a dict keyed by each entry's own "label" value
    # (e.g. {"secrets_risk": {"label": "Secrets Risk Exposure", ...}}), so
    # "Hidden Malware Risk Exposure"/"Secrets Risk Exposure" ARE real keys of
    # the resulting dict -- just not literal at the read site.
    "Hidden Malware Risk Exposure": "dynamically keyed by a config table's 'label' field (audit_recorder.py)",
    "Secrets Risk Exposure": "dynamically keyed by a config table's 'label' field (audit_recorder.py)",
    # signal_processor.py._get_locational_multipliers() writes
    # active_multipliers[signal_key] = multiplier, where signal_key comes from
    # a "Friendly Name" -> short-name `bridge` dict lookup -- confirmed real
    # writes, just one level of variable indirection away from the literal.
    "cog": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "debt": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "async": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "dead": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "obscured": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "secrets": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    "spec": "written via the bridge/signal_key indirection in _get_locational_multipliers (signal_processor.py)",
    # --- External user-provided data ---
    "known_programs": "user-provided IR JSON field, documented as external input (terabyte_log_scanner.py)",
}


class KeyUsage(NamedTuple):
    file: str
    line: int


def _string_const(node: Optional[ast.expr]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _fstring_prefix(node: Optional[ast.expr]) -> Optional[str]:
    """
    For an f-string key like f"sec_{sec_key}", returns the leading literal
    text ("sec_") a write to that templated key would always start with.
    Returns None for anything that isn't a JoinedStr with a leading literal
    ast.Constant segment (e.g. f"{x}_suffix" has no usable prefix).
    """
    if not isinstance(node, ast.JoinedStr) or not node.values:
        return None
    first = node.values[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value:
        return first.value
    return None


class KeyVisitor(ast.NodeVisitor):
    """
    Walks one module's AST, recording every string-literal dict key read or
    written in it. Deliberately conservative: only exact string constants
    (plus the f-string PREFIX_WRITES special case below) are recorded --
    anything keyed by a variable or function call is invisible to this pass
    rather than guessed at.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.reads: Dict[str, List[KeyUsage]] = {}
        self.writes: Set[str] = set()
        self.prefix_writes: Set[str] = set()

    def _record_read(self, key: str, node: ast.AST) -> None:
        self.reads.setdefault(key, []).append(KeyUsage(self.filename, node.lineno))

    def visit_Subscript(self, node: ast.Subscript) -> None:
        key = _string_const(node.slice)
        if key is not None:
            if isinstance(node.ctx, ast.Load):
                self._record_read(key, node)
            elif isinstance(node.ctx, ast.Store):
                self.writes.add(key)
        elif isinstance(node.ctx, ast.Store):
            prefix = _fstring_prefix(node.slice)
            if prefix:
                self.prefix_writes.add(prefix)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for k in node.keys:
            key = _string_const(k)
            if key is not None:
                self.writes.add(key)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        prefix = _fstring_prefix(node.key)
        if prefix:
            self.prefix_writes.add(prefix)
        key = _string_const(node.key)
        if key is not None:
            self.writes.add(key)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in ("get", "pop") and node.args:
                key = _string_const(node.args[0])
                if key is not None:
                    self._record_read(key, node)
            elif func.attr == "setdefault" and node.args:
                key = _string_const(node.args[0])
                if key is not None:
                    self.writes.add(key)
                else:
                    prefix = _fstring_prefix(node.args[0])
                    if prefix:
                        self.prefix_writes.add(prefix)
            elif func.attr == "update":
                for kw in node.keywords:
                    if kw.arg:
                        self.writes.add(kw.arg)
        elif isinstance(func, ast.Name) and func.id == "dict":
            for kw in node.keywords:
                if kw.arg:
                    self.writes.add(kw.arg)
        self.generic_visit(node)


def iter_python_files(roots: List[Path]):
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def scan() -> tuple:
    all_reads: Dict[str, List[KeyUsage]] = {}
    all_writes: Set[str] = set()
    all_prefix_writes: Set[str] = set()

    for path in iter_python_files(SCAN_ROOTS):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        try:
            rel = str(path.relative_to(REPO_ROOT))
        except ValueError:
            # Only reachable when SCAN_ROOTS points outside REPO_ROOT, e.g.
            # this module's own tests pointing it at a tmp_path fixture.
            rel = str(path)
        visitor = KeyVisitor(rel)
        visitor.visit(tree)

        for key, usages in visitor.reads.items():
            all_reads.setdefault(key, []).extend(usages)
        all_writes.update(visitor.writes)
        all_prefix_writes.update(visitor.prefix_writes)

    return all_reads, all_writes, all_prefix_writes


def find_dead_keys() -> Dict[str, List[KeyUsage]]:
    reads, writes, prefix_writes = scan()
    dead = {}
    for key, usages in reads.items():
        if key in writes:
            continue
        if any(key.startswith(prefix) for prefix in prefix_writes):
            continue
        if key in ALLOWLIST:
            continue
        dead[key] = usages
    return dead


def load_baseline() -> Dict[str, str]:
    """Returns {key: reason} for every already-known, not-yet-fixed lead."""
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_dead_keys(dead: Dict[str, List[KeyUsage]]) -> None:
    for key in sorted(dead, key=lambda k: (-len(dead[k]), k)):
        usages = dead[key]
        print(f'  "{key}"  ({len(usages)} read site(s))')
        for usage in usages[:5]:
            print(f"      {usage.file}:{usage.line}")
        if len(usages) > 5:
            print(f"      ... and {len(usages) - 5} more")
        print()


def run_full_report() -> int:
    dead = find_dead_keys()
    if not dead:
        print("Dead Key Auditor: no un-allowlisted read-without-write keys found.")
        return 0

    print(f"Dead Key Auditor: {len(dead)} key(s) read but never written anywhere in gitgalaxy/:\n")
    _print_dead_keys(dead)
    print(
        "Each hit above is a LEAD, not a confirmed bug -- see the module docstring's "
        '"SCOPE & LIMITATIONS" section before filing an issue.'
    )
    return 1


def run_ci_check() -> int:
    """
    Baseline-gated regression check (#325 sub-task 3): fails only on keys
    NOT already in dead_key_audit_baseline.json. See the module docstring's
    BASELINE section for why this isn't a zero-tolerance check.
    """
    dead = find_dead_keys()
    baseline = load_baseline()

    new_keys = {key: usages for key, usages in dead.items() if key not in baseline}
    resolved_keys = sorted(set(baseline) - set(dead))

    if resolved_keys:
        print("Dead Key Auditor: FYI -- these baselined keys are no longer flagged (fixed, or now allowlisted).")
        print("Consider removing them from dead_key_audit_baseline.json in this PR:\n")
        for key in resolved_keys:
            print(f'  "{key}"  -- {baseline[key]}')
        print()

    if not new_keys:
        print(f"Dead Key Auditor: no NEW read-without-write keys beyond the {len(baseline)}-key baseline.")
        return 0

    print(f"Dead Key Auditor: {len(new_keys)} NEW key(s) read but never written anywhere in gitgalaxy/:\n")
    _print_dead_keys(new_keys)
    print(
        "Each hit above is a LEAD, not a confirmed bug -- see the module docstring's "
        '"SCOPE & LIMITATIONS" section. From here:\n'
        "  - Confirmed false positive (walker limitation)? Add it to ALLOWLIST with a reason.\n"
        "  - Confirmed real instance of #325's pattern, not fixing it in this PR? Add it to\n"
        "    dead_key_audit_baseline.json with a reason, and consider filing an issue.\n"
        "  - Otherwise, fix the actual read/write mismatch."
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Baseline-gated regression check (what CI runs) instead of the full report.",
    )
    args = parser.parse_args()
    return run_ci_check() if args.ci else run_full_report()


if __name__ == "__main__":
    sys.exit(main())
