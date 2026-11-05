# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 16: Embedded Credentials & Keys (`hardcoded_secrets`) probed through a real scan.

Slice 6 probed the security lens on single strings. This plants one file per form in eleven languages and reads
`file_data.has_credentials`, so a language the scan routes around the lens would show. Fixed here: a camelCase name
(`dbPassword`) and a typed declaration (`authToken: string = "..."`). Forms the rule still does not read are strict
xfails (sibling gaps). Fake values are assembled from parts so this file is not itself a credential.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="three real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

A = "abcdefghijklmnopqrstuvwxyz0123456789"
V = A[2:24] + "Q7"
_PAD = {"py": "#", "rb": "#", "sh": "#", "yaml": "#"}

# name -> (extension, line)
FIRE = {
    "go_camel": ("go", f'const dbPassword = "{V}"'),
    "kotlin_camel": ("kt", f'val dbPassword = "{V}"'),
    "swift_camel": ("swift", f'let apiSecret = "{V}"'),
    "ts_typed": ("ts", f"const authToken: string = '{V}';"),
    "rust_typed": ("rs", f'const API_KEY: &str = "{V}";'),
    "csharp_typed": ("cs", f'private const string Password = "{V}";'),
    "java_const": ("java", f'private static final String PASSWORD = "{V}";'),
    "js_camel": ("js", f"const apiKey = '{V}';"),
    "py_dict": ("py", f"cfg = {{'api_key': '{V}'}}"),
    "json_key": ("json", f'{{"client_secret": "{V}"}}'),
}
QUIET = {
    "go_camel_hash": ("go", f'const dbPasswordHash = "{V}"'),
    "go_suffix_word": ("go", f'const monkey = "{V}"'),
    "go_tokenizer": ("go", f'var tokenizer string = "{V}"'),
    "ts_typed_short": ("ts", "const authToken: string = 'hunter2';"),
    "ts_typed_non_string": ("ts", "const authToken: string = fetchToken();"),
    "kotlin_camel_short": ("kt", 'val dbPassword = "hunter2"'),
    "py_dict_ident": ("py", "cfg = {'password': other_name, 'k': 'v'}"),
}
# Forms the rule does not read: sibling gaps, each a different mechanism.
GAPS = {
    "c_define": ("c", f'#define API_KEY "{V}"'),
    "php_define": ("php", f"define('DB_PASSWORD', '{V}');"),
    "ruby_secret_key_base": ("rb", f"SECRET_KEY_BASE = '{V}'"),
    "shell_export_unquoted": ("sh", f"export AWS_SECRET_ACCESS_KEY={V}"),
    "yaml_unquoted": ("yaml", f"password: {V}"),
    "url_userinfo": ("py", f"u = 'postgres://admin:{V}@db.example.com/x'"),
    "bearer_header": ("py", f"h = 'Authorization: Bearer {A}'"),
    "sendgrid": ("py", f"k = 'SG.{A[:22]}.{A[:43]}'"),
}


def _scan(tmp_path, table) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, (ext, line) in table.items():
        pad = _PAD.get(ext, "//")
        (src / f"{name}.{ext}").write_text(line + "\n" + "".join(f"{pad} filler {i}\n" for i in range(30)), "utf-8")
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
        return {p: n for p, n in con.execute("select file_path, has_credentials from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    return tuple(_scan(tmp_path_factory.mktemp(k), t) for k, t in (("fire", FIRE), ("quiet", QUIET), ("gaps", GAPS)))


@pytest.mark.parametrize("name", sorted(FIRE))
def test_form_is_flagged_through_a_real_scan(scans, name):
    assert scans[0][f"{name}.{FIRE[name][0]}"] == 1


@pytest.mark.parametrize("name", sorted(QUIET))
def test_near_miss_is_not_flagged(scans, name):
    assert scans[1][f"{name}.{QUIET[name][0]}"] == 0


@pytest.mark.xfail(strict=True, reason="sibling gap: a different mechanism than the quoted-assignment rule")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unread_form_is_flagged(scans, name):
    assert scans[2][f"{name}.{GAPS[name][0]}"] == 1
