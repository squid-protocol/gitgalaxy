"""
Cryptography (#4108 slice 15): thin-signal probe, kept as a regression guard.

`cryptography` (`file_data.arch_crypto`) has a live import rule in four languages (python, embedded_python, javascript,
typescript) and fires on few golden files. This pins each import shape end to end through a real scan: one planted file
per shape must count exactly one, and look-alike imports (a project-local `crypto` path, a longer package name, a
comment, a string) must stay 0. Library names the rule's list does not carry are pinned as strict xfails (sibling gaps).
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="three real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

_PY_PAD = "".join(f"# filler line {i}\n" for i in range(40))
_JS_PAD = "".join(f"// filler line {i}\n" for i in range(40))

# name -> (extension, import line, language the scan must report)
FIRE = {
    "py_hashlib": ("py", "import hashlib", "python"),
    "py_from_cryptography": ("py", "from cryptography.hazmat.primitives import hashes", "python"),
    "py_second_in_list": ("py", "import os, hmac", "python"),
    "py_aliased": ("py", "import ssl as s", "python"),
    "py_openssl": ("py", "from OpenSSL import crypto", "python"),
    "js_require": ("js", "const c = require('crypto');", "javascript"),
    "js_node_prefix": ("js", "import c from 'node:crypto';", "javascript"),
    "js_crypto_dash": ("js", "const c = require('crypto-js');", "javascript"),
    "js_dynamic_import": ("js", "const c = await import('crypto');", "javascript"),
    "js_subpath": ("js", "import c from 'crypto/promises';", "javascript"),
    "ts_namespace": ("ts", "import * as crypto from 'crypto';", "typescript"),
    "ts_node_named": ("ts", "import { createHash } from 'node:crypto';", "typescript"),
}
QUIET = {
    "py_local_crypto_pkg": ("py", "from myproj.crypto.utils import X", "python"),
    "py_relative": ("py", "from .ssl_helpers import y", "python"),
    "py_longer_name": ("py", "import hashlib_utils", "python"),
    "py_comment": ("py", "# import hashlib", "python"),
    "py_string": ("py", 's = "import hashlib"', "python"),
    "js_relative": ("js", "import x from './crypto/util';", "javascript"),
    "js_comment": ("js", "// const c = require('crypto');", "javascript"),
    "ts_relative": ("ts", "import x from '../crypto/util';", "typescript"),
}
# Well-known crypto libraries the name list does not carry: sibling gaps (a list extension plus a golden check).
GAPS = {
    "py_pycryptodome": ("py", "from Crypto.Cipher import AES", "python"),
    "py_nacl": ("py", "import nacl.secret", "python"),
    "py_jwt": ("py", "import jwt", "python"),
    "py_passlib": ("py", "from passlib.hash import bcrypt", "python"),
    "py_paramiko": ("py", "import paramiko", "python"),
    "py_gnupg": ("py", "import gnupg", "python"),
    "js_bcryptjs": ("js", "const c = require('bcryptjs');", "javascript"),
    "js_jose": ("js", "import * as j from 'jose';", "javascript"),
    "js_tweetnacl": ("js", "const n = require('tweetnacl');", "javascript"),
    "js_node_forge": ("js", "const f = require('node-forge');", "javascript"),
    "ts_bcryptjs": ("ts", "import bcrypt from 'bcryptjs';", "typescript"),
}


def _write(src, table) -> None:
    for name, (ext, line, _) in table.items():
        (src / f"{name}.{ext}").write_text(line + "\n" + (_PY_PAD if ext == "py" else _JS_PAD), encoding="utf-8")


def _scan(tmp_path, table) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    _write(src, table)
    return _scan_dir(src, tmp_path / "out")


def _scan_dir(src, out) -> dict:
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        env=env,
        check=True,
        capture_output=True,
        timeout=180,
    )
    (db,) = out.glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    try:
        return {p: (lang, n) for p, lang, n in con.execute("select file_path, language, arch_crypto from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    return tuple(_scan(tmp_path_factory.mktemp(k), t) for k, t in (("fire", FIRE), ("quiet", QUIET), ("gaps", GAPS)))


def _row(scan, name, table):
    return scan[f"{name}.{table[name][0]}"]


@pytest.mark.parametrize("name", sorted(FIRE))
def test_import_shape_counts_once_through_a_real_scan(scans, name):
    assert _row(scans[0], name, FIRE) == (FIRE[name][2], 1)


@pytest.mark.parametrize("name", sorted(QUIET))
def test_lookalike_import_does_not_fire(scans, name):
    assert _row(scans[1], name, QUIET) == (QUIET[name][2], 0)


@pytest.mark.xfail(strict=True, reason="sibling gap: the library is not in the rule's name list")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unlisted_crypto_library_import_fires(scans, name):
    assert _row(scans[2], name, GAPS)[1] >= 1


def test_embedded_python_uses_the_same_import_pack(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "boot.py").write_text("import hashlib\nimport machine\n" + _PY_PAD, encoding="utf-8")
    rows = [v for v in _scan_dir(src, tmp_path / "out").values()]
    assert rows == [("embedded_python", 1)]
