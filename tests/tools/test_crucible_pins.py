"""tests/crucible_pins.toml, its thin Python wrappers and tests/tools/crucible_pins.py (get / check / sync / bump)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cics_crucible_pin
import _crucible_manifest as manifest
import _crucible_pin
import _estate_crucible_pin
import crucible_pins as cp

ENV_VARS = ("LANGUAGE_CRUCIBLE_PATH", "ESTATE_CRUCIBLE_PATH", "CICS_CRUCIBLE_PATH")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


def commit(repo, msg):
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A manifest plus, per crucible, an upstream repo (tags v1.0.0, v2.0.0) and a shared clone at v1.0.0."""
    lines = []
    for name, env in zip(manifest.NAMES, ENV_VARS):
        upstream = tmp_path / f"{name}-upstream"
        upstream.mkdir()
        git(upstream, "init", "-q", "-b", "main")
        commit(upstream, "one")
        git(upstream, "tag", "v1.0.0")
        commit(upstream, "two")
        git(upstream, "tag", "v2.0.0")
        clone = tmp_path / f"{name}-shared"
        subprocess.run(["git", "clone", "-q", str(upstream), str(clone)], check=True, capture_output=True)
        git(clone, "checkout", "-q", "--detach", "v1.0.0")
        monkeypatch.setenv(env, str(clone))
        lines += [
            f"[{name}]", f'repo = "{upstream}"', 'ref = "v2.0.0"', f'path_env = "{env}"',
            f'allow_unpinned_env = "{name.upper()}_ALLOW"', f'default_dir = "{name}-crucible"', "",
        ]  # fmt: skip
    path = tmp_path / "crucible_pins.toml"
    path.write_text("\n".join(lines))
    return path


def run(world, *args):
    return cp.main(["--manifest", str(world), *args])


def test_manifest_has_every_crucible_and_a_ref():
    pins = manifest.load()
    assert set(pins) == set(manifest.NAMES)
    for entry in pins.values():
        assert cp.REF_RE.fullmatch(entry["ref"])
        assert entry["repo"].startswith("https://github.com/squid-protocol/")
        assert not entry["default_dir"].startswith("/")  # no machine path is committed


def test_fallback_parser_agrees_with_tomllib():
    tomllib = pytest.importorskip("tomllib")
    text = manifest.MANIFEST.read_text(encoding="utf-8")
    assert manifest.parse_subset(text) == tomllib.loads(text)


def test_fallback_parser_rejects_what_it_cannot_read():
    with pytest.raises(ValueError):
        manifest.parse_subset('[a]\nref = ["x"]\n')
    with pytest.raises(ValueError):
        manifest.parse_subset('ref = "x"\n')


def test_wrappers_equal_the_manifest():
    pins = manifest.load()
    assert _crucible_pin.PINNED_TAG == pins["language"]["ref"]
    assert _estate_crucible_pin.PINNED_REF == pins["estate"]["ref"]
    assert _cics_crucible_pin.PINNED_REF == pins["cics"]["ref"]
    for module, name in ((_crucible_pin, "language"), (_estate_crucible_pin, "estate"), (_cics_crucible_pin, "cics")):
        assert module.ALLOW_UNPINNED_ENV == pins[name]["allow_unpinned_env"]
    assert _estate_crucible_pin.PATH_ENV == "ESTATE_CRUCIBLE_PATH"
    assert _cics_crucible_pin.PATH_ENV == "CICS_CRUCIBLE_PATH"
    assert _crucible_pin.PATH_ENV == "LANGUAGE_CRUCIBLE_PATH"


def test_get(world, capsys):
    assert run(world, "get", "cics") == 0
    assert run(world, "get", "estate-crucible") == 0
    assert capsys.readouterr().out.split() == ["v2.0.0", "v2.0.0"]
    with pytest.raises(SystemExit):
        run(world, "get", "nope")


def test_check_reports_off_pin_then_on_pin(world, capsys):
    assert run(world, "check", "--no-gh") == 1
    out = capsys.readouterr().out
    assert out.count("OFF") == 3 and "crucible_pins.py sync language" in out
    assert run(world, "sync", "--no-lock") == 0
    capsys.readouterr()
    assert run(world, "check", "--no-gh") == 0
    assert capsys.readouterr().out.count("on pin v2.0.0, clean") == 3


def test_check_flags_dirty_and_skips_absent(world, tmp_path, monkeypatch, capsys):
    run(world, "sync", "--no-lock")
    clone = Path(cp.os.environ["CICS_CRUCIBLE_PATH"])
    (clone / "tracked.txt").write_text("a")
    git(clone, "add", "tracked.txt")
    monkeypatch.setenv("ESTATE_CRUCIBLE_PATH", str(tmp_path / "absent"))
    capsys.readouterr()
    assert run(world, "check", "--no-gh") == 0
    out = capsys.readouterr().out
    assert "DIRTY" in out and "skip  estate" in out


def test_sync_prints_before_and_after(world, capsys):
    assert run(world, "sync", "language", "--no-lock") == 0
    out = capsys.readouterr().out
    assert "SYNCED language: v1.0.0 -> v2.0.0" in out
    clone = Path(cp.os.environ["LANGUAGE_CRUCIBLE_PATH"])
    assert git(clone, "rev-parse", "HEAD") == git(clone, "rev-parse", "v2.0.0^{commit}")
    assert git(Path(cp.os.environ["CICS_CRUCIBLE_PATH"]), "describe", "--tags") == "v1.0.0"  # untouched


def test_sync_refuses_a_dirty_checkout_and_touches_nothing(world, capsys):
    clone = Path(cp.os.environ["ESTATE_CRUCIBLE_PATH"])
    (clone / "f.txt").write_text("a")
    git(clone, "add", "f.txt")
    assert run(world, "sync", "--no-lock") == 1
    assert "REFUSE estate" in capsys.readouterr().err
    assert git(Path(cp.os.environ["LANGUAGE_CRUCIBLE_PATH"]), "describe", "--tags") == "v1.0.0"


def test_sync_refuses_unpushed_commits(world, capsys):
    clone = Path(cp.os.environ["LANGUAGE_CRUCIBLE_PATH"])
    git(clone, "checkout", "-q", "-b", "wip")
    commit(clone, "local only")
    assert run(world, "sync", "language", "--no-lock") == 1
    assert "no remote has" in capsys.readouterr().err
    assert git(clone, "rev-parse", "--abbrev-ref", "HEAD") == "wip"
    git(clone, "push", "-q", "origin", "wip")  # pushed commits are safe to leave behind
    assert run(world, "sync", "language", "--no-lock") == 0


def test_bump_edits_one_line_and_lists_followups(world, capsys):
    assert run(world, "bump", "cics", "v3.1.0") == 0
    pins = manifest.load(world)
    assert pins["cics"]["ref"] == "v3.1.0" and pins["language"]["ref"] == "v2.0.0" and pins["estate"]["ref"] == "v2.0.0"
    out = capsys.readouterr().out
    assert "--update-baseline" in out and "reprove" in out and "sync cics" in out
    with pytest.raises(SystemExit):
        run(world, "bump", "cics", "main")


def test_check_var(world, capsys):
    assert run(world, "check-var", "v2.0.0") == 0
    assert run(world, "check-var", "") == 0  # fork run: variable withheld
    assert run(world, "check-var", "v1.0.0") == 0  # warns only
    assert "WARN" in capsys.readouterr().out
    assert run(world, "check-var", "v1.0.0", "--strict") == 1
