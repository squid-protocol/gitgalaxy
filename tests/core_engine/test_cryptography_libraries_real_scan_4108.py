# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108: Cryptography Libraries (`arch_crypto`) probed through a real scan.

The rule (`PY_CRYPTOGRAPHY` / `JS_CRYPTOGRAPHY`) lives in python, javascript and typescript only. This plants one
file per import shape, scans them end to end and reads `file_data.arch_crypto`. Names the lists do not carry, and
every other language, are strict xfails (sibling gaps, each needs a name-list or stated-absence decision).
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="four real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

# name -> (extension, body); one comment style per extension
FIRE = {
    "py_hashlib": ("py", "import hashlib\n"),
    "py_from_cryptography": ("py", "from cryptography.hazmat.primitives import hashes\n"),
    "py_openssl": ("py", "from OpenSSL import crypto\n"),
    "py_hmac_in_list": ("py", "import os, hmac\n"),
    "py_ssl": ("py", "import ssl\n"),
    "js_require_crypto": ("js", "const c = require('crypto');\n"),
    "js_node_prefix": ("js", "import crypto from 'node:crypto';\n"),
    "js_crypto_js": ("js", "import CryptoJS from 'crypto-js';\n"),
    "ts_tls": ("ts", "import tls from 'tls';\n"),
}
QUIET = {
    "py_crypto_prefix_name": ("py", "import crypto_utils\n"),
    "py_commented": ("py", "# import hashlib\n"),
    "js_relative_path": ("js", "import c from './crypto';\n"),
    "js_webcrypto_global": ("js", "const k = await crypto.subtle.digest('SHA-256', d);\n"),
}
# Cryptographic libraries the name lists do not carry, and languages with no rule at all (stated absence).
GAPS = {
    "py_pycryptodome": ("py", "from Crypto.Cipher import AES\n"),
    "py_pynacl": ("py", "import nacl.secret\n"),
    "py_pyjwt": ("py", "import jwt\n"),
    "py_passlib": ("py", "from passlib.hash import pbkdf2_sha256\n"),
    "js_bcryptjs": ("js", "const b = require('bcryptjs');\n"),
    "js_jose": ("js", "import { SignJWT } from 'jose';\n"),
    "js_node_forge": ("js", "const forge = require('node-forge');\n"),
    "go_crypto_sha256": ("go", 'import "crypto/sha256"\n'),
    "java_javax_crypto": ("java", "import javax.crypto.Mac;\n"),
    "rust_ring": ("rs", "use ring::digest;\n"),
    "ruby_openssl": ("rb", "require 'openssl'\n"),
    "csharp_cryptography": ("cs", "using System.Security.Cryptography;\n"),
}
_PAD = {"py": "#", "rb": "#"}


def _scan(tmp_path, table) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, (ext, body) in table.items():
        pad = _PAD.get(ext, "//")
        (src / f"{name}.{ext}").write_text(body + "".join(f"{pad} filler {i}\n" for i in range(30)), "utf-8")
    out = tmp_path / "out"
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
        return {p: n for p, n in con.execute("select file_path, arch_crypto from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    return tuple(_scan(tmp_path_factory.mktemp(k), t) for k, t in (("fire", FIRE), ("quiet", QUIET), ("gaps", GAPS)))


@pytest.mark.parametrize("name", sorted(FIRE))
def test_crypto_import_fires_through_a_real_scan(scans, name):
    assert scans[0][f"{name}.{FIRE[name][0]}"] >= 1


@pytest.mark.parametrize("name", sorted(QUIET))
def test_near_miss_stays_zero(scans, name):
    assert scans[1][f"{name}.{QUIET[name][0]}"] == 0


@pytest.mark.xfail(strict=True, reason="sibling gap: library not in the name list, or language has no rule")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unread_import_fires(scans, name):
    assert scans[2][f"{name}.{GAPS[name][0]}"] >= 1
