"""
Auth Middleware (#4108 slice 14): thin-signal probe, kept as a regression guard.

`auth_middleware` fires on fewer than 0.5% of the golden fixture's files, so a live rule that silently stopped matching
would pass the golden check. This pins each live language end to end: a real scan of a planted file must put a count in
`file_data.def_auth`, and a file with only look-alike text (a definition, a read-only query, the name in a comment)
must put none.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="two real scans of 55 planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

# language -> (file name, text that must fire, minimum count, text that must not fire)
LIVE = {
    "c": (
        "a.c",
        "int f(void) {\n    setuid(0);\n    pam_authenticate(h, 0);\n    return 0;\n}\n",
        2,
        "/* setuid(0) */\nint f(void) { return getuid(); }\n",
    ),
    "cpp": (
        "a.cpp",
        "void f() {\n    pam_authenticate(h, 0);\n    auto v = jwt::verify();\n    bcrypt::verify(a, b);\n}\n",
        3,
        "void f() { auto v = getuid(); }\n",
    ),
    "csharp": (
        "a.cs",
        'class A {\n    [Authorize]\n    void F() { app.UseAuthentication(); user.IsInRole("x"); }\n}\n',
        3,
        "class A {\n    void F() { var n = 1; }\n}\n",
    ),
    "crystal": ("a.cr", "require_sign_in\nauthenticate!\nJWT.decode(t)\n", 3, "def f\n  1\nend\n"),
    "dart": (
        "a.dart",
        "void f() {\n  FirebaseAuth.instance.signIn();\n  GoogleSignIn();\n  JWT.verify(t);\n}\n",
        3,
        "void f() {\n  var a = 1;\n}\n",
    ),
    "fsharp": (
        "a.fs",
        "open System\nlet f () =\n    requiresAuthentication ()\n    BCrypt.Verify(a, b)\n",
        2,
        "open System\nlet f () = 1\n",
    ),
    "go": (
        "a.go",
        "package main\nfunc f() {\n\tbcrypt.CompareHashAndPassword(a, b)\n\tjwt.Parse(t)\n}\n",
        2,
        "package main\nfunc f() {\n\ta := 1\n\t_ = a\n}\n",
    ),
    "haskell": (
        "a.hs",
        "module A where\nf = do\n  uid <- requireAuthId\n  verifyPassword a b\n",
        2,
        "module A where\nf = 1\n",
    ),
    "java": (
        "a.java",
        'class A {\n    @PreAuthorize("x")\n    void f() { new LoginContext("n"); }\n}\n',
        2,
        "class A {\n    void f() { int a = 1; }\n}\n",
    ),
    "javascript": (
        "a.js",
        "passport.authenticate('x');\njwt.verify(t, k);\nbcrypt.compare(a, b);\n",
        3,
        "const a = 1;\nfunction authenticate() {}\n",
    ),
    "kotlin": (
        "a.kt",
        "fun f() {\n    install(Authentication)\n    authenticate {\n    }\n}\n",
        2,
        "fun f() {\n    val a = 1\n}\n",
    ),
    "objective-c": (
        "a.m",
        "@implementation A\n- (void)f {\n    [ctx evaluatePolicy:p];\n    AuthorizationCreate(0, 0, 0, &r);\n}\n@end\n",
        2,
        "@implementation A\n- (void)f {\n    int a = 1;\n}\n@end\n",
    ),
    "perl": (
        "a.pl",
        "use strict;\n$a->check_password($p);\nAuthen::PAM->new();\n",
        2,
        "use strict;\nsub check_password { 1 }\n",
    ),
    "php": ("a.php", "<?php\nAuth::check();\nGate::allows('x');\npassword_verify($a, $b);\n", 3, "<?php\n$a = 1;\n"),
    "powershell": ("a.ps1", "$c = Get-Credential\nStart-Process x -Verb RunAs\n", 2, "$a = 1\nWrite-Output $a\n"),
    "python": (
        "a.py",
        "@login_required\ndef f(u):\n    check_password(u)\n    return 1\n",
        2,
        "def f(u):\n    return 1\n",
    ),
    "ruby": (
        "a.rb",
        "class A\n  before_action :authenticate_user!\n  def f\n    authorize @x\n  end\nend\n",
        2,
        "class A\n  def f\n    1\n  end\nend\n",
    ),
    "rust": (
        "a.rs",
        "fn f() {\n    bcrypt::verify(a, b);\n    jsonwebtoken::decode(t);\n}\n",
        2,
        "fn f() {\n    let a = 1;\n}\n",
    ),
    "scala": (
        "a.scala",
        "object A {\n  def f() = SecuredAction { 1 }\n  checkPassword(a)\n}\n",
        2,
        "object A {\n  def f() = 1\n}\n",
    ),
    "shell": ("a.sh", "#!/bin/sh\nkinit user\nchpasswd < f\n", 2, "#!/bin/sh\necho kinit\n"),
    "solidity": (
        "a.sol",
        "contract A {\n    function f() public {\n        hasRole(r, a);\n        _checkRole(r);\n    }\n}\n",
        2,
        "contract A {\n    function f() public {}\n}\n",
    ),
    "swift": (
        "a.swift",
        "func f() {\n    let c = LAContext()\n    c.evaluatePolicy(p)\n}\n",
        2,
        "func f() {\n    let a = 1\n}\n",
    ),
    "typescript": ("a.ts", "@UseGuards(G)\nclass A {}\njwt.verify(t, k);\n", 2, "const a: number = 1;\n"),
    "zig": ("a.zig", "pub fn f() void {\n    _ = std.posix.setuid(0);\n}\n", 1, "pub fn f() void {\n    _ = 1;\n}\n"),
    "cobol": (
        "a.cbl",
        "       PROCEDURE DIVISION.\n           EXEC CICS SIGNON USERID(U) END-EXEC.\n           EXEC SQL GRANT SELECT ON T TO P END-EXEC.\n           STOP RUN.\n",
        2,
        "       PROCEDURE DIVISION.\n           EXEC CICS RETURN END-EXEC.\n           STOP RUN.\n",
    ),
    "pli": (
        "a.pli",
        "A: PROC OPTIONS(MAIN);\n EXEC CICS SIGNOFF;\n EXEC SQL GRANT SELECT ON T TO P;\nEND A;\n",
        2,
        "A: PROC OPTIONS(MAIN);\n DCL X FIXED;\nEND A;\n",
    ),
    "postgresql": (
        "a.psql",
        "GRANT SELECT ON t TO bob;\nCREATE POLICY p ON t USING (true);\nALTER TABLE t ENABLE ROW LEVEL SECURITY;\n",
        3,
        "SELECT 1;\n",
    ),
}


# Tiny files are dropped by the aperture before the detector runs: pad the look-alike files with inert lines in the
# file's own comment syntax so they are scanned and the zero is a real zero.
_COMMENT = {
    **dict.fromkeys(("cr", "pl", "rb", "py", "sh", "ps1", "hs"), "#"),
    **dict.fromkeys(
        (
            "c",
            "cpp",
            "cs",
            "dart",
            "fs",
            "go",
            "java",
            "js",
            "kt",
            "m",
            "php",
            "rs",
            "scala",
            "sol",
            "swift",
            "ts",
            "zig",
        ),
        "//",
    ),
    "psql": "--",
    "hs": "--",
    "cbl": "      *",
    "pli": "/*",
}
_PAD = {
    ext: "\n".join(f"{c} filler line {i}" + (" */" if c == "/*" else "") for i in range(40)) + "\n"
    for ext, c in _COMMENT.items()
}


def _scan(tmp_path, files: dict) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, text in files.items():
        (src / name).write_text(text, encoding="utf-8")
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
        return {p: (lang, n) for p, lang, n in con.execute("select file_path, language, def_auth from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scan(tmp_path_factory):
    """(planted scan, look-alike scan): one directory each, since a single mixed directory drops some files."""
    fire = {name: text for name, text, _, _ in LIVE.values()}
    quiet = {"quiet_" + name: text + _PAD.get(name.rsplit(".", 1)[1], "") for name, _, _, text in LIVE.values()}
    quiet["d.py"] = "def check_password(u):\n    return 1\n"
    return _scan(tmp_path_factory.mktemp("fire"), fire), _scan(tmp_path_factory.mktemp("quiet"), quiet)


@pytest.mark.parametrize("language", sorted(LIVE))
def test_planted_auth_site_fires_through_a_real_scan(scan, language):
    name, _, minimum, _ = LIVE[language]
    lang, count = scan[0][name]
    assert lang == language
    assert count >= minimum


@pytest.mark.parametrize("language", sorted(LIVE))
def test_lookalike_text_does_not_fire(scan, language):
    name = "quiet_" + LIVE[language][0]
    lang, count = scan[1][name]
    assert lang == language
    assert count == 0


@pytest.mark.xfail(
    strict=True,
    reason="sibling gap: python's `check_password(` alternative has no `(?<!def )` guard, so a definition counts as an auth site",
)
def test_a_check_password_definition_does_not_fire(scan):
    assert scan[1]["d.py"] == ("python", 0)
