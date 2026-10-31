"""The GalaxyScope CLI contract: docs/wiki/01-02-galaxyscope-cli-reference.md must match the code.

That page once documented `--airgap`, `--legacy`, exit codes 3 and 4 and three environment variables that never
existed, and its GitHub Actions example failed with a usage error. These tests fail when the page and the parser
disagree in either direction, when a `galaxyscope` command elsewhere in the docs names a flag the parser lacks, when
the code can set an exit code the page does not list, or when the page's own example stops running.

The parser is built inside `main()` with no way to reach it from outside. Rather than change the engine, the test runs
`main()` with `parse_args` patched to capture the parser and stop, so nothing past argument parsing runs.
"""

import argparse
import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy
from gitgalaxy.galaxyscope import main

PACKAGE = Path(gitgalaxy.__file__).resolve().parent
REPO_ROOT = PACKAGE.parent
PAGE = REPO_ROOT / "docs" / "wiki" / "01-02-galaxyscope-cli-reference.md"

# Hand-written docs that show `galaxyscope` commands. docs/self_scan/ is generated; site/ is not checked yet.
DOC_GLOBS = (
    "README.md",
    "CONTRIBUTING.md",
    "github-action-readme.md",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    "gitgalaxy/README.md",
    "gitgalaxy/core/*.md",
    "docs/*.md",
    "docs/wiki/*.md",
    "docs/wiki/cookbook/*.md",
    "templates/**/*.yml",
)
# The two modules that hold a network client on purpose; neither is on the `galaxyscope` scan path.
NETWORK_ALLOWED = {"tools/cobol_to_java/port_runner.py", "tools/readiness/offline.py"}
NETWORK_MODULES = ("aiohttp", "ftplib", "http.client", "httpx", "requests", "smtplib", "socket", "urllib.request")
# Engine code a scan runs. Controllers and forges under gitgalaxy/ are their own commands with their own exit codes.
SCAN_MODULES = ("galaxyscope.py", "licensing.py", "core", "metrics", "recorders", "security")
ENV_NAME = re.compile(r"(?:GITGALAXY|GALAXYSCOPE|GG)_[A-Z0-9_]+")
SECRET_FILE = 'password = "correct-horse-battery-staple-0123456789"\n'


class _ParserCaptured(Exception):
    pass


@pytest.fixture(scope="module")
def parser() -> argparse.ArgumentParser:
    seen: list[argparse.ArgumentParser] = []

    def capture(self, *_args, **_kwargs):
        seen.append(self)
        raise _ParserCaptured

    with (
        patch("gitgalaxy.licensing.enforce_licensing_guard"),
        patch.object(argparse.ArgumentParser, "parse_args", capture),
    ):
        with pytest.raises(_ParserCaptured):
            main()
    return seen[0]


def _section(heading: str, next_heading: str) -> str:
    text = PAGE.read_text(encoding="utf-8")
    return text[text.index(f"\n## {heading}\n") : text.index(f"\n## {next_heading}\n")]


def _rows(section: str) -> list[list[str]]:
    """The body rows of the section's tables, as stripped cells (header and rule rows dropped)."""
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not line.startswith("| :---"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return [row for row in rows if row[0] not in ("Flag", "File", "Variable", "Code")]


def _documented_flags() -> dict[str, str | None]:
    """Each option string in a flag table's first column -> the value it is shown taking, or None."""
    flags: dict[str, str | None] = {}
    for row in _rows(_section("Flags", "Environment Variables")):
        for token in re.findall(r"`(-[^`]*)`", row[0]):
            name, _, value = token.partition(" ")
            flags[name] = value or None
    return flags


def _parser_flags(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    return {name: action for action in parser._actions for name in action.option_strings}


def test_every_parser_flag_is_documented_and_every_documented_flag_exists(parser):
    documented, real = set(_documented_flags()), set(_parser_flags(parser))
    assert not documented - real, "documented, but the parser has no such flag"
    assert not real - documented, "the parser has it, but the contract page omits it"


def test_a_flag_is_shown_with_a_value_exactly_when_it_takes_one(parser):
    documented = _documented_flags()
    wrong = [name for name, action in _parser_flags(parser).items() if bool(documented[name]) != (action.nargs != 0)]
    assert not wrong


def test_the_target_is_the_only_positional_and_is_documented_as_required(parser):
    assert [a.dest for a in parser._actions if not a.option_strings] == ["target"]
    assert "galaxyscope <target> [options]" in PAGE.read_text(encoding="utf-8")


def test_every_flag_named_anywhere_on_the_page_exists(parser):
    named = set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", PAGE.read_text(encoding="utf-8")))
    allowed = set(_parser_flags(parser))
    # `--out` is named once, as the example of an abbreviation that is NOT promised.
    assert named - allowed == {"--out"}


def _doc_files() -> list[Path]:
    files = {path for pattern in DOC_GLOBS for path in REPO_ROOT.glob(pattern)}
    assert PAGE in files and len(files) > 20
    return sorted(files)


def test_every_galaxyscope_command_in_the_docs_uses_real_flags(parser):
    allowed = set(_parser_flags(parser))
    command = re.compile(r"(?<![\w./-])(?:galaxyscope|GG_ARGS\b)[^\n`|]*")
    wrong = []
    for path in _doc_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in command.finditer(line):
                unknown = set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", match.group())) - allowed
                wrong += [f"{path.relative_to(REPO_ROOT)}:{number}: {flag}" for flag in sorted(unknown)]
    assert not wrong


def test_no_doc_names_a_report_the_engine_does_not_write():
    wrong = [
        str(path.relative_to(REPO_ROOT))
        for path in _doc_files()
        if re.search(r"(?<![\w])_galaxy\.json", path.read_text(encoding="utf-8"))
    ]
    assert not wrong, "a scan writes <stem>_gpu.json and friends, never a bare <stem>.json"


def _modules(*roots: str) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        path = PACKAGE / root
        paths += sorted(path.rglob("*.py")) if path.is_dir() else [path]
    return paths


def test_every_environment_variable_the_engine_reads_is_documented_and_vice_versa():
    read = set()
    for path in _modules(*SCAN_MODULES):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and ENV_NAME.fullmatch(node.value):
                read.add(node.value)
    documented = {row[0].strip("`") for row in _rows(_section("Environment Variables", "Exit Codes"))}
    assert read == documented


def test_no_stale_environment_variable_is_named_anywhere_in_the_docs():
    # None of these was ever read by the engine.
    gone = ("GITGALAXY_LLM_KEY", "GITGALAXY_WORKERS", "GITGALAXY_RAM_LIMIT_MB")
    assert not [p.name for p in _doc_files() if any(name in p.read_text(encoding="utf-8") for name in gone)]


def test_the_engine_has_no_network_client():
    wrong = []
    for path in PACKAGE.rglob("*.py"):
        rel = path.relative_to(PACKAGE).as_posix()
        if rel in NETWORK_ALLOWED or rel.startswith("data/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            wrong += [f"{rel}: {n}" for n in names if n in NETWORK_MODULES or n.startswith(("requests.", "httpx."))]
    assert not wrong


# --- exit codes ---


def _documented_exit_codes() -> set[int]:
    return {
        int(row[0].strip("`")) for row in _rows(_section("Exit Codes", "Pipeline Integration Example (GitHub Actions)"))
    }


def test_the_documented_exit_codes_are_exactly_0_1_2():
    assert _documented_exit_codes() == {0, 1, 2}


def test_the_scan_code_sets_no_exit_code_the_page_omits():
    """sys.exit / exit / SystemExit with anything but a listed constant is a contract change."""
    documented = _documented_exit_codes()
    wrong = []
    for path in _modules(*SCAN_MODULES):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name not in ("exit", "_exit", "SystemExit") or not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Constant) and arg.value in documented):
                wrong.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not wrong


def _galaxyscope(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """The real command, in a subprocess: `main()` reconfigures logging for the whole process."""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONUTF8": "1",
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
    }
    return subprocess.run(  # noqa: S603 -- our own interpreter and module, fixed args
        [sys.executable, "-m", "gitgalaxy.galaxyscope", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return repo


@pytest.fixture
def secret_repo(clean_repo: Path) -> Path:
    (clean_repo / "settings.py").write_text(SECRET_FILE, encoding="utf-8")
    return clean_repo


@pytest.mark.parametrize(
    "args",
    [["--airgap"], ["--legacy"], ["--no-such-flag"], ["--max-risk-exposure", "lots"]],
    ids=["airgap", "legacy", "unknown", "bad-value"],
)
def test_a_bad_command_line_exits_2(clean_repo, args):
    assert _galaxyscope(str(clean_repo), *args, cwd=clean_repo.parent).returncode == 2


def test_a_missing_target_argument_exits_2(tmp_path):
    assert _galaxyscope(cwd=tmp_path).returncode == 2


def test_help_exits_0(tmp_path):
    assert _galaxyscope("--help", cwd=tmp_path).returncode == 0


@pytest.mark.parametrize(
    "args",
    [["--source-encoding", "no_such_codec"], ["--copy-libraries", "no_such_file.json"]],
    ids=["codec", "copy-libraries"],
)
def test_a_rejected_input_exits_1_before_any_report(clean_repo, args):
    out = clean_repo.parent / "out"
    result = _galaxyscope(str(clean_repo), "--output", str(out), *args, cwd=clean_repo.parent)
    assert result.returncode == 1
    assert "Critical failure during execution" in result.stderr
    assert not out.exists()


def test_a_missing_target_path_exits_1(tmp_path):
    result = _galaxyscope(str(tmp_path / "no_such_repo"), cwd=tmp_path)
    assert result.returncode == 1
    assert "Critical failure during execution" in result.stderr


def test_a_clean_scan_exits_0_and_writes_the_documented_reports(clean_repo):
    out = clean_repo.parent / "out"
    assert _galaxyscope(str(clean_repo), "--output", str(out), cwd=clean_repo.parent).returncode == 0
    assert {path.name for path in out.iterdir()} == {
        f"repo_galaxy_{suffix}"
        for suffix in ("audit.json", "gpu.json", "graph.sqlite", "llm.md", "master.db", "sarif.json", "sbom.json")
    }


def test_output_defaults_to_the_working_directory_not_the_target(clean_repo, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert _galaxyscope(str(clean_repo), "--db-only", cwd=work).returncode == 0
    assert (work / "repo_galaxy_master.db").exists()
    assert not (clean_repo / "repo_galaxy_master.db").exists()


def test_output_with_an_extension_sets_the_stem_except_for_the_llm_files(clean_repo):
    out = clean_repo.parent / "out"
    assert _galaxyscope(str(clean_repo), "--output", str(out / "scan.json"), cwd=clean_repo.parent).returncode == 0
    names = {path.name for path in out.iterdir()}
    assert {"scan_sarif.json", "scan_gpu.json", "repo_galaxy_llm.md"} <= names
    assert "scan.json" not in names


def test_findings_without_a_gate_exit_0(secret_repo):
    out = secret_repo.parent / "out"
    assert _galaxyscope(str(secret_repo), "--output", str(out), cwd=secret_repo.parent).returncode == 0


@pytest.mark.parametrize(
    "gate",
    [["--fail-on-secrets"], ["--max-risk-exposure", "0.001"]],
    ids=["secrets", "risk"],
)
def test_a_tripped_gate_exits_1_with_every_report_written(secret_repo, gate):
    out = secret_repo.parent / "out"
    result = _galaxyscope(str(secret_repo), "--output", str(out), *gate, cwd=secret_repo.parent)
    assert result.returncode == 1
    assert "BUILD FAILED:" in result.stderr
    assert "Critical failure during execution" not in result.stderr
    assert (out / "repo_galaxy_gpu.json").exists() and (out / "repo_galaxy_sarif.json").exists()


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("no_such.yaml", None),
        ("broken.yaml", "galaxyscope: [unclosed"),
        ("a_list.yaml", "- fail-on-secrets\n"),
        ("bad_section.yaml", "galaxyscope: true\n"),
    ],
)
def test_a_config_that_cannot_be_applied_stops_the_run(secret_repo, name, text):
    """It may hold the gates: a scan that drops them must not pass."""
    if text is not None:
        (secret_repo.parent / name).write_text(text, encoding="utf-8")
    out = secret_repo.parent / "out"
    result = _galaxyscope(str(secret_repo), "--config", name, "--output", str(out), cwd=secret_repo.parent)
    assert result.returncode == 1
    assert "Failed to load config file" in result.stderr
    assert not out.exists()


def test_config_without_pyyaml_stops_the_run(secret_repo, monkeypatch, caplog):
    monkeypatch.setattr("gitgalaxy.galaxyscope.HAS_PYYAML", False)
    monkeypatch.setattr(sys, "argv", ["galaxyscope", str(secret_repo), "--config", "any.yaml"])
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 1
    assert "PyYAML is not installed" in caplog.text


def _delta(repo, change, *flags):
    """A baseline of `repo`, `change` applied and staged, then an --incremental scan with `flags`."""
    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "baseline"]):
        subprocess.run([*git, *args], cwd=repo, check=True)  # noqa: S603 -- fixed args
    out = repo.parent / "out"
    assert _galaxyscope(str(repo), "--db-only", "--output", str(out), cwd=repo.parent).returncode == 0
    change()
    subprocess.run([*git, "add", "."], cwd=repo, check=True)  # noqa: S603 -- fixed args
    baseline = str(out / "repo_galaxy_master.db")
    result = _galaxyscope(str(repo), "--incremental", baseline, *flags, "--output", str(out), cwd=repo.parent)
    assert "DELTA_SUCCESS" in result.stderr
    return result


def test_gates_run_on_an_incremental_scan_and_catch_an_added_secret(clean_repo):
    delta = _delta(
        clean_repo, lambda: (clean_repo / "added.py").write_text(SECRET_FILE, encoding="utf-8"), "--fail-on-secrets"
    )
    assert delta.returncode == 1
    assert "BUILD FAILED:" in delta.stderr and "added.py" in delta.stderr


def test_an_incremental_scan_judges_the_unchanged_files_too(secret_repo):
    """It fails on what a full scan fails on: a secret already in the baseline is still in the repository."""
    delta = _delta(
        secret_repo, lambda: (secret_repo / "other.py").write_text("x = 1\n", encoding="utf-8"), "--fail-on-secrets"
    )
    assert delta.returncode == 1
    assert "BUILD FAILED:" in delta.stderr and "settings.py" in delta.stderr


def test_an_incremental_scan_with_no_finding_passes(clean_repo):
    delta = _delta(
        clean_repo, lambda: (clean_repo / "other.py").write_text("x = 1\n", encoding="utf-8"), "--fail-on-secrets"
    )
    assert delta.returncode == 0
    assert "BUILD FAILED:" not in delta.stderr


def test_an_incremental_scan_with_no_gate_set_passes_on_a_secret(clean_repo):
    delta = _delta(clean_repo, lambda: (clean_repo / "added.py").write_text(SECRET_FILE, encoding="utf-8"))
    assert delta.returncode == 0


@pytest.mark.parametrize("rule", ["secrets_risk", "sec_hardcoded_secrets"])
def test_a_suppressed_secret_passes_a_full_and_an_incremental_scan_alike(clean_repo, rule):
    """Both spellings of the suppression survive the baseline, where the file is rehydrated, not rescanned."""
    (clean_repo / "kept.py").write_text(f"# galaxyscope:ignore {rule}\n{SECRET_FILE}", encoding="utf-8")
    out = clean_repo.parent / "full"
    full = _galaxyscope(str(clean_repo), "--fail-on-secrets", "--output", str(out), cwd=clean_repo.parent)
    assert full.returncode == 0, full.stderr[-1500:]
    delta = _delta(
        clean_repo, lambda: (clean_repo / "other.py").write_text("x = 1\n", encoding="utf-8"), "--fail-on-secrets"
    )
    assert delta.returncode == 0, delta.stderr[-1500:]


def test_the_pages_github_actions_example_runs(secret_repo):
    """The example has to work as printed. Run from the repo root, it trips its own gate on this fixture."""
    line = next(row for row in PAGE.read_text(encoding="utf-8").splitlines() if "run: galaxyscope" in row)
    command = shlex.split(line.split("run: ", 1)[1])
    assert command[0] == "galaxyscope"
    upload = re.search(r"path: (\S+)", PAGE.read_text(encoding="utf-8")).group(1)

    result = _galaxyscope(*command[1:], cwd=secret_repo)
    assert result.returncode == 1 and "BUILD FAILED:" in result.stderr
    reports = secret_repo / upload
    assert (reports / "repo_galaxy_gpu.json").exists()

    (secret_repo / "settings.py").unlink()
    shutil.rmtree(reports)  # a CI checkout starts clean; these hold the finding
    assert _galaxyscope(*command[1:], cwd=secret_repo).returncode == 0
