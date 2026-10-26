"""
Every gate a GitGalaxy PR meets in CI, run locally in one command -- so a PR does not learn about a
lint rule, a secret-scanner hit or a golden-master drift from CI, one push at a time.

    python tests/tools/pr_gates.py                  # all gates (~15 min)
    python tests/tools/pr_gates.py --fast           # skip the golden masters and the full suite
                                                    # (gen-docs: the uncommitted aggregate pages render, #5057;
                                                    # workflows: actionlint over .github/workflows;
                                                    # derived: evidence / det-ledger records and the docs-readers list
                                                    # the branch stales, #6731)
    python tests/tools/pr_gates.py --only affected      # the tests this branch can break (its importers too), #6733
    python tests/tools/pr_gates.py --only lint audits gauntlet
    python tests/tools/pr_gates.py --lower-baseline # also rewrite the gauntlet baseline when cells now pass
    python tests/tools/pr_gates.py --e2e            # add the equivalence proofs (Docker GnuCOBOL + JDK 17)
    python tests/tools/pr_gates.py --vs-main        # re-run each failing gate on a fresh origin/main worktree and
                                                    # label it "caused by branch" or "pre-existing on main@<sha>"
    python tests/tools/pr_gates.py --ratchets       # every ratchet a fix may move, in order: the CICS spec's generated
                                                    # files, ports compile, estate-crucible gate, fact cross-check,
                                                    # corpus completeness pins, ground-truth ledger;
                                                    # prints pass/fail and the exact update command per failure
                                                    # (--only-ratchets ports estate ... to pick; skips say "not available: why")

The environment the gates need is set up here, not remembered: the corpora beside the main checkout
(KEYWORD_ROSETTA_PATH, LANGUAGE_CRUCIBLE_PATH, GITGALAXY_MAINFRAME_CORPORA), the interpreter's bin on
PATH (the audits call `ruff` / `mypy` by name), the community licence key (no 5 s delay), and a JDK 17
for --e2e. Run it from the worktree to check, with the project's venv python.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
MYPY_REQUIREMENTS = "tests/requirements-mypy.txt"
MYPY_CACHE = Path(os.environ.get("GITGALAXY_MYPY_CACHE", Path.home() / ".cache" / "gitgalaxy"))
# actionlint (MIT, rhysd/actionlint) via its PyPI wrapper, which fetches the release binary at install. 2026-10-20: #5766
# merged `${{ (matrix.timeout || 30) - 3 }}` (expressions have no arithmetic), main started no Full Suite Gate job until
# #5768; actionlint names that line. shellcheck / pyflakes integrations off: the gate checks the workflow files only.
ACTIONLINT_PIN = "1.7.12.25"


def _main_checkout() -> Path:
    """The main checkout (a worktree's corpora sit beside it, not beside the worktree)."""
    common = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--git-common-dir"],  # noqa: S603, S607
                            capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    path = Path(common) if common else REPO / ".git"
    return (path if path.is_absolute() else REPO / path).resolve().parent


def environment(e2e: bool) -> dict[str, str]:
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env["PATH"] = str(Path(PY).parent) + os.pathsep + env.get("PATH", "")
    main = _main_checkout()
    for var, path in (("KEYWORD_ROSETTA_PATH", main.parent / "keyword-rosetta"),
                      ("LANGUAGE_CRUCIBLE_PATH", main.parent / "language-crucible"),
                      ("GITGALAXY_MAINFRAME_CORPORA", main / ".mainframe_corpora")):  # fmt: skip
        if var not in env and path.is_dir():
            env[var] = str(path)
    if e2e:
        env["EQUIVALENCE_E2E"] = "1"
        if "JAVA_HOME" not in env:  # Maven needs a JDK that compiles release 17
            jdks = sorted(Path("/usr/lib/jvm").glob("java-17-openjdk*")) if Path("/usr/lib/jvm").is_dir() else []
            if jdks:
                env["JAVA_HOME"] = str(jdks[0])
    return env


def ci_pins(repo: Path = REPO) -> dict[str, str | None]:
    """What CI installs, read from the workflows: {'python','ruff','mypy'} -> version, or None if unpinned."""
    wf = repo / ".github" / "workflows"

    def read(name: str) -> str:
        try:
            return (wf / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    ruff_yml, mypy_yml = read("ruff-audit.yml"), read("mypy-audit.yml")
    py = re.search(r"python-version:\s*[\"']?([\d.]+)", ruff_yml or mypy_yml)
    try:  # ruff is pinned in the shared hashed lockfile the workflow installs (#4918), not inline
        lint = (repo / "ci" / "requirements" / "lint.in").read_text(encoding="utf-8")
    except OSError:
        lint = ""
    ruff = re.search(r"^\s*ruff==([\w.]+)", lint, re.M) or re.search(r"\bruff==([\w.]+)", ruff_yml)
    try:  # mypy is pinned in ONE file that the workflow installs from
        reqs = (repo / MYPY_REQUIREMENTS).read_text(encoding="utf-8")
    except OSError:
        reqs = ""
    mypy = re.search(r"^\s*mypy==([\w.]+)", reqs, re.M) or re.search(r"\bmypy==([\w.]+)", mypy_yml)
    return {"python": py and py.group(1), "ruff": ruff and ruff.group(1), "mypy": mypy and mypy.group(1)}


def local_versions(env: dict[str, str] | None = None) -> dict[str, str | None]:
    """Versions of the interpreter, ruff and mypy the gates will actually use (None if not installed)."""
    out: dict[str, str | None] = {"python": ".".join(map(str, sys.version_info[:3]))}
    for tool in ("ruff", "mypy"):
        try:
            txt = subprocess.run([tool, "--version"], capture_output=True, text=True, check=False, env=env).stdout  # noqa: S603
        except OSError:
            txt = ""
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", txt)
        out[tool] = m.group(1) if m else None
    return out


def version_warnings(pins: dict[str, str | None], local: dict[str, str | None]) -> list[str]:
    """Loud warnings (never a failure) where local tooling differs from what CI pins. python compares major.minor."""
    msgs = []
    for tool in ("python", "ruff", "mypy"):
        want, have = pins.get(tool), local.get(tool)
        if want is None:
            continue
        if tool == "python":
            same = bool(have) and have.split(".")[:2] == want.split(".")[:2]
        else:
            same = have == want
        if not same:
            msgs.append(f"{tool}: local {have or 'MISSING'} != CI {want}")
    if any("!=" in m for m in msgs):
        pkgs = " ".join(f"{t}=={v}" if v else t for t, v in (("ruff", pins.get("ruff")), ("mypy", pins.get("mypy"))))
        py = pins.get("python") or "3.12"
        msgs.append(
            f"fix in a PRIVATE venv, never the shared one: python{py} -m venv /tmp/gitgalaxy-scratch/claude/ci-venv && "
            f"/tmp/gitgalaxy-scratch/claude/ci-venv/bin/pip install {pkgs} PyYAML && "
            f"PATH=/tmp/gitgalaxy-scratch/claude/ci-venv/bin:$PATH python tests/tools/pr_gates.py ..."
        )
    return msgs


class Ratchet:
    """One ratchet: its check command, the command that moves it, and what it needs (None = available)."""

    def __init__(self, name: str, cmd: list[str], update: str, needs: Callable[[dict[str, str]], str | None]):
        self.name, self.cmd, self.update, self.needs = name, cmd, update, needs


def _corpora_root(env: dict[str, str]) -> Path:
    return Path(env.get("GITGALAXY_MAINFRAME_CORPORA") or REPO / ".mainframe_corpora")


def _need_corpora(env: dict[str, str]) -> str | None:
    root = _corpora_root(env)
    if not any(root.glob("*/.git")):
        return f"no mainframe corpus fetched under {root} (python tests/tools/mainframe_corpus.py fetch, or set GITGALAXY_MAINFRAME_CORPORA)"
    return None


def _need_corpora_and_pytest(env: dict[str, str]) -> str | None:
    if importlib.util.find_spec("pytest") is None:
        return f"pytest is not installed for {PY} (pip install -e .[full,translator] plus pytest)"
    return _need_corpora(env)


def _need_crucible(var: str, name: str, marker: str) -> Callable[[dict[str, str]], str | None]:
    def check(env: dict[str, str]) -> str | None:
        path = Path(env.get(var) or _main_checkout().parent / name)
        if not (path / marker).exists():
            return f"no {name} checkout at {path} (set {var}; tests/tools/box/sync-pins.sh aligns it with the pin)"
        return None

    return check


def _need_ports(env: dict[str, str]) -> str | None:
    if not shutil.which("mvn", path=env.get("PATH")):
        return "mvn (Maven + JDK 17) is not on PATH"
    return _need_crucible("CICS_CRUCIBLE_PATH", "cics-crucible", ".git")(env)


def ratchets() -> list[Ratchet]:
    """The ratchets a fix may move, in the order to run them. Each reuses its tool's own entry point."""
    t = "tests/tools/"
    return [
        Ratchet(
            "cics-spec",
            [PY, "-m", "gitgalaxy.standards.cics", "regen", "--check"],
            "python -m gitgalaxy.standards.cics regen   (commit CicsSpec.java / ggcics_spec.h; #4270 spec PR 4)",
            lambda env: None,
        ),  # fmt: skip
        Ratchet(
            "ports",
            [PY, t + "ports_compile_check.py"],
            "fix the generator or the port overlays; re-check one case: python tests/tools/ports_compile_check.py --cases <case>",
            _need_ports,
        ),  # fmt: skip
        Ratchet(
            "port-surface",
            [
                PY,
                t + "port_surface.py",
                "equivalence",
                "--work",
                str(Path(tempfile.gettempdir()) / "gitgalaxy-port-surface"),
                "--check",
            ],
            "python tests/tools/port_surface.py equivalence --work DIR   (then re-prove: python tests/tools/evidence.py prove CASE ...)",
            _need_corpora,
        ),  # fmt: skip
        Ratchet(
            "estate",
            [PY, t + "estate_crucible_gate.py"],
            "python tests/tools/estate_crucible_gate.py --update-baseline   (commit tests/estate_crucible/baseline.json)",
            _need_crucible("ESTATE_CRUCIBLE_PATH", "estate-crucible", "key/manifest.json"),
        ),  # fmt: skip
        Ratchet(
            "fact-crosscheck",
            [PY, t + "fact_crosscheck.py", "check"],
            "python tests/tools/fact_crosscheck.py update   (two-way: also drops fixed entries; run unscoped, see #4472 re --corpus)",
            _need_corpora,
        ),  # fmt: skip
        Ratchet(
            "completeness",
            [
                PY,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "tests/cobol_mainframe/test_completeness.py",
                "-k",
                "pinned_corpus_completeness",
            ],
            "edit PINNED in tests/cobol_mainframe/test_completeness.py to the new (resolved, total); some corpora only run in CI",
            _need_corpora_and_pytest,
        ),  # fmt: skip
        Ratchet(
            "ground-truth",
            [PY, t + "ground_truth_ledger.py", "check"],
            "python tests/tools/ground_truth_ledger.py update   (then `assign` a cause to each UNTRIAGED entry)",
            _need_corpora,
        ),  # fmt: skip
        Ratchet(
            "det-mutation",
            [PY, t + "det_mutation.py", "stale-check", "--vs", "origin/main"],
            "python tests/tools/det_mutation.py refresh CASE --work DIR   (commit tests/equivalence/det_mutation/CASE.json; a moved det port needs `run`; #5862)",
            _need_corpora,
        ),  # fmt: skip
        Ratchet(
            "time",
            [PY, t + "time_ratchet.py", "check"],
            "make the test faster (over 15 s), or mark it @pytest.mark.slow(reason=...); shrink the baseline: python tests/tools/time_ratchet.py update --times .test_durations (never raises; #5166)",
            lambda env: None,
        ),  # fmt: skip
    ]


def run_ratchets(chosen: list[str] | None, env: dict[str, str]) -> int:
    """Runs the ratchets in order; prints a PASS / FAIL / SKIP table and the update command per failure."""
    plan = ratchets()
    unknown = sorted(set(chosen or []) - {r.name for r in plan})
    if unknown:
        print(f"unknown ratchet(s) {unknown}; ratchets are {[r.name for r in plan]}", file=sys.stderr)
        return 2
    rows: list[tuple[str, str, str]] = []  # (name, status, detail)
    for r in plan:
        if chosen and r.name not in chosen:
            continue
        why = r.needs(env)
        if why:
            rows.append((r.name, "SKIP", f"not available: {why}"))
            print(f"SKIP  {r.name:<16} not available: {why}", flush=True)
            continue
        t0 = time.time()
        ok, tail = run_gate([r.cmd], REPO, env)
        rows.append((r.name, "PASS" if ok else "FAIL", r.update if not ok else ""))
        print(f"{'PASS' if ok else 'FAIL'}  {r.name:<16} {time.time() - t0:6.0f}s", flush=True)
        if not ok:
            print("      " + tail.replace("\n", "\n      "), flush=True)
    failed = [n for n, st, _ in rows if st == "FAIL"]
    skipped = [n for n, st, _ in rows if st == "SKIP"]
    print("\nratchet           status")
    for name, st, detail in rows:
        print(f"{name:<17} {st}")
        if st == "FAIL":
            print(f"    update: {detail}")
    print(f"\n{len(rows) - len(failed) - len(skipped)} pass, {len(failed)} fail, {len(skipped)} skipped (not checked)")
    return 1 if failed else 0


def run_gate(cmds: list[list[str]], root: Path, env: dict[str, str]) -> tuple[bool, str]:
    """Runs one gate's commands in `root`; returns (ok, output tail of the first failure)."""
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if proc.returncode != 0:
            return False, "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
    return True, ""


def clean_prefix(bin_dir: Path, root: Path) -> list[str]:
    """`env -i` plus only what the audits need: no FORCE_COLOR / TERM / caller state can reach mypy or ruff (#4551)."""
    return [
        "env",
        "-i",
        f"HOME={Path.home()}",
        f"PATH={bin_dir}:/usr/bin:/bin",
        f"PYTHONPATH={root}",
        "GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER",
        "NO_COLOR=1",
    ]


def _announce(tool: str, exe: Path, bin_dir: Path) -> None:
    """Prints `<tool> used: <version> (<path>)`, resolved under the same clean PATH the gate runs with."""
    clean_path = f"{bin_dir}:/usr/bin:/bin"
    found = shutil.which(exe.name, path=clean_path) if not exe.is_absolute() else str(exe)
    if not found:
        print(f"NOTE  {tool} used: NOT FOUND on {clean_path}", flush=True)
        return
    ver = subprocess.run(  # noqa: S603
        [found, "--version"], capture_output=True, text=True, check=False, env={"PATH": clean_path}
    ).stdout.strip()
    print(f"NOTE  {tool} used: {ver} ({found})", flush=True)


def _tool_bin_dir(tool: str, env: dict[str, str]) -> Path:
    """Where the caller's `tool` lives (the one local_versions just matched against CI's pin), so the `env -i` PATH
    reaches it. Not always the interpreter's bin dir: churn's precheck runs pr_gates under /usr/bin/python3 with ruff
    on ~/.local/bin, and `PATH=/usr/bin:...` then found no ruff and failed lint in 0 s."""
    found = shutil.which(tool, path=env.get("PATH", os.environ.get("PATH")))
    return Path(found).resolve().parent if found else Path(PY).parent


def pinned_mypy_audit(root: Path, env: dict[str, str]) -> list[list[str]]:
    """The mypy gate command, run with exactly CI's mypy (#4537) and ALWAYS in a clean environment (#4551).

    When the local mypy already matches tests/requirements-mypy.txt it runs under this interpreter's bin dir;
    otherwise it builds (once) or reuses a private venv `~/.cache/gitgalaxy/mypy-<version>` holding only the
    pinned packages plus `-e <root>`. Either way `env -i` is used (a caller's FORCE_COLOR once made the audit
    parse zero findings and pass) and "mypy used: <version> (<path>)" is printed. Never touches a shared venv.
    """
    want = ci_pins(root).get("mypy")
    if not want or local_versions(env).get("mypy") == want:
        bin_dir = _tool_bin_dir("mypy", env)
        _announce("mypy", Path("mypy"), bin_dir)
        return [[*clean_prefix(bin_dir, root), PY, "tests/mypy_audit.py", "--ci"]]
    venv = MYPY_CACHE / f"mypy-{want}"
    vpy, marker = venv / "bin" / "python", venv / ".editable-root"
    if not (vpy.exists() and (venv / ".ready").exists()):
        shutil.rmtree(venv, ignore_errors=True)
        venv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([PY, "-m", "venv", str(venv)], check=True)  # noqa: S603
        subprocess.run([str(vpy), "-m", "pip", "install", "-q", "-r", str(root / MYPY_REQUIREMENTS)], check=True)  # noqa: S603
        (venv / ".ready").write_text(want)
    if not marker.exists() or marker.read_text() != str(root):
        subprocess.run([str(vpy), "-m", "pip", "install", "-q", "-e", str(root)], check=True)  # noqa: S603
        marker.write_text(str(root))
    _announce("mypy", venv / "bin" / "mypy", venv / "bin")
    return [[*clean_prefix(venv / "bin", root), str(vpy), "tests/mypy_audit.py", "--ci"]]


def pinned_ruff_lint(env: dict[str, str]) -> tuple[list[list[str]], dict[str, str]]:
    """The lint gate command + env, ALWAYS under `env -i` (#4551); ruff at CI's pin (private venv if local differs)."""
    want = ci_pins().get("ruff")
    if not want or local_versions(env).get("ruff") == want:
        bin_dir = _tool_bin_dir("ruff", env)
        _announce("ruff", Path("ruff"), bin_dir)
        return [[*clean_prefix(bin_dir, REPO), PY, "tests/ruff_audit.py", "--ci"]], env
    venv = MYPY_CACHE / f"ruff-{want}"
    if not (venv / ".ready").exists():
        shutil.rmtree(venv, ignore_errors=True)
        venv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([PY, "-m", "venv", str(venv)], check=True)  # noqa: S603
        subprocess.run([str(venv / "bin" / "python"), "-m", "pip", "install", "-q", f"ruff=={want}"], check=True)  # noqa: S603
        (venv / ".ready").write_text(want)
    _announce("ruff", venv / "bin" / "ruff", venv / "bin")
    # the audit imports gitgalaxy (lint_baseline), so it runs under this interpreter with the pinned ruff first on PATH
    return [[*clean_prefix(venv / "bin", REPO), PY, "tests/ruff_audit.py", "--ci"]], env


def actionlint_gate(root: Path = Path(".")) -> int:
    """actionlint at ACTIONLINT_PIN over root/.github/workflows (private venv, built once). Exit 0 when clean.

    A venv that cannot be built (offline, PyPI down) prints a NOTE and passes: churn's precheck runs --fast, and a
    network blip must not send a worker back. A real finding fails, one line per finding."""
    files = sorted(str(f) for f in (root / ".github" / "workflows").glob("*.y*ml"))
    if not files:
        return 0
    venv = MYPY_CACHE / f"actionlint-{ACTIONLINT_PIN}"
    bin_dir, ext = (venv / "Scripts", ".exe") if os.name == "nt" else (venv / "bin", "")
    exe = bin_dir / f"actionlint{ext}"
    if not (venv / ".ready").exists():
        shutil.rmtree(venv, ignore_errors=True)
        venv.parent.mkdir(parents=True, exist_ok=True)
        try:
            built = subprocess.run([PY, "-m", "venv", str(venv)], capture_output=True, check=False).returncode == 0  # noqa: S603
            built = built and subprocess.run(  # noqa: S603
                [str(bin_dir / f"python{ext}"), "-m", "pip", "install", "-q", f"actionlint-py=={ACTIONLINT_PIN}"],
                capture_output=True, check=False,
            ).returncode == 0  # fmt: skip
        except OSError:
            built = False
        if not (built and exe.exists()):
            shutil.rmtree(venv, ignore_errors=True)
            print(f"NOTE  actionlint-py=={ACTIONLINT_PIN} could not be installed: workflows not linted", flush=True)
            return 0
        (venv / ".ready").write_text(ACTIONLINT_PIN)
    _announce("actionlint", exe, bin_dir)
    # the files by name: actionlint's own discovery needs a git project root (a bare tree exits 3)
    return subprocess.run(
        [str(exe), "-shellcheck=", "-pyflakes=", "-oneline", *files], cwd=root, check=False
    ).returncode  # noqa: S603


def attribute_failures(
    failed: list[str], plan_for: Callable[[Path], dict[str, list[list[str]]]], env: dict[str, str]
) -> dict[str, str]:
    """For each failing gate, re-run it on a fresh detached origin/main worktree: {gate: label}.

    `plan_for(root)` returns the gate plan with its cwd/paths for that root. Fetches first so "main" is
    current, not 10 minutes stale (#4220 round); the worktree is removed afterwards.
    """
    subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "main"], check=False)  # noqa: S603, S607
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "origin/main"],  # noqa: S603, S607
                         capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    tmp = Path(tempfile.mkdtemp(prefix="gg-vs-main-"))
    wt = tmp / "main"
    labels: dict[str, str] = {}
    try:
        subprocess.run(
            ["git", "-C", str(REPO), "worktree", "add", "-q", "--detach", str(wt), "origin/main"], check=True
        )  # noqa: S603, S607
        menv = dict(env, PYTHONPATH=str(wt))
        plan = plan_for(wt)
        for name in failed:
            ok, _ = run_gate(pinned_mypy_audit(wt, menv) if name == "audits" else plan[name], wt, menv)
            labels[name] = f"pre-existing on main@{sha}" if not ok else "caused by branch"
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)], check=False)  # noqa: S603, S607
        shutil.rmtree(tmp, ignore_errors=True)
    return labels


def _tool(module: str) -> list[str]:
    return [PY, "-c", f"import sys; sys.argv = ['gate', '.']; from {module} import main; sys.exit(main())"]


def gates(args: argparse.Namespace, env: dict[str, str]) -> dict[str, list[list[str]]]:
    corpus = env.get("KEYWORD_ROSETTA_PATH")
    # heavy-run.sh's fair share of the cores (#4882), else every core
    gauntlet = [
        PY,
        "tests/tools/unicode_gauntlet.py",
        "--ci",
        "--jobs",
        os.environ.get("GG_JOB_CORES") or str(os.cpu_count() or 4),
    ]
    gauntlet += ["--corpus", corpus] if corpus else []
    suite = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    return {
        "lint": [[PY, "tests/ruff_audit.py", "--ci"]],
        "audits": [[PY, "tests/mypy_audit.py", "--ci"]],
        "secrets": [_tool("gitgalaxy.tools.supply_chain_security.vault_sentinel")],
        "xray": [_tool("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector")],
        # #5057: the aggregate pages are not committed; they must render, deterministically (generated-docs.yml)
        "gen-docs": [[PY, "tests/tools/generated_docs.py", "check"]],
        # #6731: derived records the branch stales, which CI fails a push later: evidence records / det-sweep ledger
        # entries (~5 s) and the docs-readers list (~15 s)
        "derived": [[PY, "tests/tools/derived_check.py"], [PY, "tests/tools/change_classifier.py", "--check"]],
        # a workflow file GitHub cannot load starts no job at all (#5768); cwd-relative, like every gate here
        "workflows": [
            [
                PY,
                "-c",
                "import sys; sys.path.insert(0, 'tests/tools'); from pr_gates import actionlint_gate; "
                "sys.exit(actionlint_gate())",
            ]
        ],
        "gauntlet": [gauntlet] + ([[*gauntlet[:2], "--update-baseline", *gauntlet[3:]]] if args.lower_baseline else []),
        # #6733: the test files whose imports (or names) reach what the branch changed, nearest first, ~5 min budget
        "affected": [[PY, "tests/tools/affected_tests.py"]],
        "golden": [[PY, "tests/tools/crucible_check.py"]],
        "suite": [suite],
    }


def gates_at(root: Path, args: argparse.Namespace, env: dict[str, str]) -> dict[str, list[list[str]]]:
    """The gate plan is cwd-relative, so a plan for another checkout is the same plan run with cwd=root."""
    return gates(args, env)


def det_mutation_hint() -> None:
    """A non-failing hint when this branch changes a case that has a det_mutation ledger: strengthening a case stales
    its ledger and drops the program from L5, so the PR re-runs it (the `det-mutation` ratchet; #5862)."""
    try:
        sys.path.insert(0, str(REPO / "tests" / "tools"))
        import det_mutation

        cases = det_mutation.cases_to_rerun("origin/main")
    except Exception:  # a hint must never fail the gates (no origin/main, no git, no ledger)
        return
    if cases:
        print(
            f"HINT  det-mutation: this branch changes case(s) with a det_mutation ledger ({', '.join(cases)}): "
            "python tests/tools/pr_gates.py --only-ratchets det-mutation, then "
            "python tests/tools/det_mutation.py refresh CASE --work DIR and commit the ledger (#5862)",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", help="run only these gates")
    ap.add_argument("--fast", action="store_true", help="skip the golden masters and the full suite")
    ap.add_argument("--lower-baseline", action="store_true", help="rewrite the gauntlet baseline after the check")
    ap.add_argument(
        "--vs-main",
        action="store_true",
        help="label each failing gate caused-by-branch / pre-existing on a fresh origin/main",
    )
    ap.add_argument("--ratchets", action="store_true", help="run every ratchet a fix may move, then exit")
    ap.add_argument("--only-ratchets", nargs="+", metavar="NAME", help="with --ratchets: only these")
    ap.add_argument("--e2e", action="store_true", help="the full suite also runs the equivalence proofs")
    args = ap.parse_args(argv)
    env = environment(args.e2e)
    if args.ratchets or args.only_ratchets:
        return run_ratchets(args.only_ratchets, env)
    det_mutation_hint()
    plan = gates(args, env)
    chosen = args.only or [g for g in plan if not (args.fast and g in ("golden", "suite"))]
    unknown = sorted(set(chosen) - set(plan))
    if unknown:
        ap.error(f"unknown gate(s) {unknown}; gates are {list(plan)}")
    for msg in version_warnings(ci_pins(), local_versions(env)):
        print(f"WARNING  {msg}", flush=True)
    results: list[tuple[str, bool, float]] = []
    for name in chosen:
        t0, ok, tail = time.time(), True, ""
        cmds, genv = plan[name], env
        if name == "audits":
            cmds = pinned_mypy_audit(REPO, env)
        elif name == "lint":
            cmds, genv = pinned_ruff_lint(env)
        ok, tail = run_gate(cmds, REPO, genv)
        results.append((name, ok, time.time() - t0))
        print(f"{'PASS' if ok else 'FAIL'}  {name:<9} {time.time() - t0:6.0f}s", flush=True)
        if not ok:
            print("      " + tail.replace("\n", "\n      "), flush=True)
    failed = [n for n, ok, _ in results if not ok]
    print(
        f"\n{len(results) - len(failed)}/{len(results)} gates pass"
        + (f"; failing: {', '.join(failed)}" if failed else "")
    )
    if failed and args.vs_main:
        print("\n--vs-main: re-running failing gates on a fresh origin/main worktree ...", flush=True)
        for name, label in attribute_failures(failed, lambda root: gates_at(root, args, env), env).items():
            print(f"  {name:<9} {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
