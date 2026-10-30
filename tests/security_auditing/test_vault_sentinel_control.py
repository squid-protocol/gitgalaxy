"""#7155: Vault Sentinel's real detector and file filter over planted fakes, nothing mocked.

test_vault_sentinel.py mocks SecurityLens and ApertureFilter, so it proves the exit code, not that a secret is ever
found. Every value here is invented or a published documentation example, split so no scanner reads this file as a leak.
"""

import sys

import pytest

import gitgalaxy.tools.supply_chain_security.vault_sentinel as sentinel
from gitgalaxy.standards.config_resolver import path_allowlisted

CAUGHT = {
    "aws key id": 'KEY = "AKIA' + 'IOSFODNN7EXAMPLE"\n',
    "github token": 'TOKEN = "ghp_' + "a1B2c3D4e5F6g7H8i9J0" * 2 + '"\n',
    "slack token": 'HOOK = "xoxb-' + '123456789012-1234567890123-abcdefghijklmnopqrstuvwx"\n',
    "stripe key": 'S = "sk_live_' + 'a1B2c3D4e5F6g7H8i9J0k1L2"\n',
    "private key": "-----BEGIN RSA "
    + "PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4\n-----END RSA PRIVATE KEY-----\n",
    "assigned password": 'password = "' + 'hunter2hunter2hunter2"\n',
}
MISSED = {  # #7179: found by this control. strict: fixing one fails the test until it moves to CAUGHT
    "aws secret key": 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCY' + 'EXAMPLEKEY"\n',
    "google api key": 'K = "AIza' + 'SyA1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7"\n',
    "json web token": 'T = "eyJhbGciOiJIUzI1NiJ9.' + 'eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnopqrstuvwxyz012345"\n',
}
UNREAD_TYPES = ["main.tf", "app.ini", "app.toml", "app.conf", "app.cfg", "prod.env", "old.bak", "notes.ipynb"]


def _scan(tmp_path, monkeypatch, files: dict[str, str]) -> int:
    """The real scanner over a planted tree, with the default config. The exit code it would give CI."""
    root = tmp_path / "planted"
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["vault_sentinel.py", str(root)])
    try:
        sentinel.main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


@pytest.mark.parametrize("kind", CAUGHT)
def test_the_real_detector_fails_ci_on_a_planted_secret(kind, tmp_path, monkeypatch, capsys):
    assert _scan(tmp_path, monkeypatch, {"src/app.py": CAUGHT[kind]}) == 1
    out = capsys.readouterr().out
    assert "CONTENT BREACH" in out and "src/app.py" in out
    assert CAUGHT[kind].strip() not in out, "a detected secret must never be logged"


def test_a_clean_tree_passes(tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"src/app.py": "def add(a, b):\n    return a + b\n"}) == 0


@pytest.mark.parametrize("name", [".env", "src/.env.local", "deploy/id_rsa"])
def test_a_secret_file_fails_by_its_name_alone(name, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {name: "anything\n"}) == 1


@pytest.mark.xfail(strict=True, reason="#7179: the detector has no signature for this")
@pytest.mark.parametrize("kind", MISSED)
def test_known_miss_secret_kinds(kind, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {"src/app.py": MISSED[kind]}) == 1


@pytest.mark.xfail(strict=True, reason="#7179: ApertureFilter drops these file types, so they are never read")
@pytest.mark.parametrize("name", UNREAD_TYPES)
def test_known_miss_file_types(name, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {f"src/{name}": CAUGHT["aws key id"]}) == 1


@pytest.mark.parametrize("rel", ["src/latests/app.py", "contests/app.py", "mytests/app.py"])
def test_a_folder_that_only_ends_in_tests_is_not_allowlisted(rel, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {rel: CAUGHT["aws key id"]}) == 1


@pytest.mark.parametrize("rel", ["tests/app.py", "src/tests/app.py"])
def test_a_real_tests_folder_stays_allowlisted(rel, tmp_path, monkeypatch):
    assert _scan(tmp_path, monkeypatch, {rel: CAUGHT["aws key id"]}) == 0


def test_path_allowlisted():
    assert path_allowlisted("tests/a.py", ["tests/"]) and path_allowlisted("x/tests/a.py", ["tests/"])
    assert not path_allowlisted("latests/a.py", ["tests/"]) and not path_allowlisted("x/contests/a.py", ["tests/"])
    assert path_allowlisted("a/key1.pem", ["key1.pem"])  # an entry that isn't a folder stays a partial match
    assert not path_allowlisted("a.py", [])
