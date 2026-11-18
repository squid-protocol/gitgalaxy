# ruff: noqa: S101, S603
"""`gitgalaxy libsurface`: library definitions (shipped table, TOML overrides, validation), discovery per language, coupling from imports and
external calls, the surface change between two scans, and the command end to end.

Builds tiny scan databases with the real `file_data` / `fcall_external` columns the command reads."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.sensors import libsurface as LS

REPO = Path(__file__).resolve().parents[2]
ENV = {"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "XDG_CONFIG_HOME": "/nonexistent"}


def _db(
    tmp: Path,
    files: list[tuple[str, int, list[str]]],
    external: dict[str, dict[str, int]] | None = None,
    name: str = "s.db",
) -> Path:
    db = tmp / name
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT, total_loc INTEGER, raw_imports TEXT, repo_name TEXT);
        CREATE TABLE fcall_external(id INTEGER PRIMARY KEY, src_file_id INTEGER, callee TEXT, callers INTEGER);
        """
    )
    ids = {}
    for i, (path, loc, imports) in enumerate(files, start=1):
        ids[path] = i
        con.execute("INSERT INTO file_data VALUES (?, ?, ?, ?, 'r')", (i, path, loc, json.dumps(imports)))
    for path, names in (external or {}).items():
        for callee, callers in names.items():
            con.execute(
                "INSERT INTO fcall_external(src_file_id, callee, callers) VALUES (?, ?, ?)",
                (ids[path], callee, callers),
            )
    con.commit()
    con.close()
    return db


C_FILES = [
    ("src/tls.c", 100, ["openssl/ssl.h", "stdio.h", "tls.h"]),
    ("src/wrap.c", 50, ["wrap.h"]),  # calls the API without including the header
    ("src/tls.h", 10, []),
    ("src/wrap.h", 10, []),
    ("src/main.c", 200, ["zlib.h", "sys/types.h", "vendor/thing.h"]),
]
C_EXTERNAL = {"src/tls.c": {"SSL_new": 3, "SSL_free": 1, "memcpy": 9}, "src/wrap.c": {"SSL_read": 2}}


def test_the_shipped_table_loads_and_has_no_pattern_that_is_empty():
    libs = LS.load_libraries([])
    assert {"openssl", "zlib", "glib", "freetype"} <= set(libs)
    assert all(lib.include or lib.calls for lib in libs.values())


def test_table_libraries_count_includes_and_calls(tmp_path):
    surface = LS.build(_db(tmp_path, C_FILES, C_EXTERNAL), LS.load_libraries([]))
    ssl = surface.libraries["openssl"]
    assert set(ssl) == {"src/tls.c", "src/wrap.c"}  # wrap.c is found by its calls alone: the wrapper-header case
    assert ssl["src/tls.c"].sites == 1 + 3 + 1 and ssl["src/tls.c"].names == {
        "SSL_new": 3,
        "SSL_free": 1,
    }  # memcpy is not the library's
    assert ssl["src/wrap.c"].includes == [] and ssl["src/wrap.c"].density == 2 / 50
    assert set(surface.libraries["zlib"]) == {"src/main.c"}


def test_discovery_finds_unlisted_libraries_and_skips_system_and_own_headers(tmp_path):
    surface = LS.build(_db(tmp_path, C_FILES, C_EXTERNAL), LS.load_libraries([]))
    assert "vendor" in surface.libraries  # an external header directory nobody listed
    assert "stdio" not in surface.libraries and "sys" not in surface.libraries  # system headers
    assert "tls" not in surface.libraries and "wrap" not in surface.libraries  # headers the repository holds
    assert "vendor" not in surface.table_libraries and "openssl" in surface.table_libraries


@pytest.mark.parametrize(
    ("ext", "token", "expected"),
    [
        (".py", "docutils.nodes", "docutils"),
        (".py", "os.path", None),  # standard library
        (".py", "mypkg.util", None),  # the repository's own package (a directory named mypkg)
        (".py", ".sibling", None),  # relative
        (".go", "github.com/stretchr/testify/require", "github.com/stretchr/testify"),
        (".go", "golang.org/x/net/http2", "golang.org/x/net"),
        (".go", "k8s.io/client-go/tools/cache", "k8s.io/client-go"),
        (".go", "fmt", None),
        (
            ".go",
            "github.com/o/r/util/testutil",
            None,
        ),  # the repository's own module, found by a `util/testutil` directory
        (".java", "org.junit.jupiter.api.Test", "org.junit"),
        (".java", "org.apache.commons.text.StringSubstitutor", "org.apache.commons.text"),
        (".java", "java.util.List", None),
        (".java", "org.xml.sax.Parser", None),
        (".rs", "serde::Serialize", "serde"),
        (".rs", "std::fs", None),
        (".rs", "crate::util", None),
        (".js", "@scope/pkg/sub", "@scope/pkg"),
        (".ts", "react", "react"),
        (".ts", "fs", None),
        (".ts", "./local", None),
    ],
)
def test_discovery_root_per_language(ext, token, expected):
    paths = ["src/mypkg/a.py", "util/testutil/x.go", "src/main/java/org/apache/commons/lang3/A.java"]
    own = LS.go_own_roots(["github.com/o/r/util/testutil"], frozenset({"util/testutil", "util"}))
    segments = LS._segments(paths)
    root = LS.discover_root(token, ext, own, segments, "\n".join(paths), frozenset())
    assert root == expected


def test_discovery_alone_gives_import_coupling_with_no_names(tmp_path):
    files = [("a.py", 40, ["docutils.nodes", "os"]), ("b.py", 60, ["docutils", "jinja2.sandbox"]), ("c.py", 10, ["os"])]
    surface = LS.build(_db(tmp_path, files), LS.load_libraries([]))
    assert set(surface.libraries) == {"docutils", "jinja2"}
    assert set(surface.libraries["docutils"]) == {"a.py", "b.py"}
    assert all(not c.names for c in surface.libraries["docutils"].values())


def test_user_toml_adds_replaces_and_disables_by_name(tmp_path):
    cfg = tmp_path / "libs.toml"
    cfg.write_text(
        """
[[library]]
name = "acme"
include = ["acme/*"]
calls = ["acme_*"]

[[library]]
name = "zlib"          # replaces the shipped entry
languages = ["c"]
include = ["zlib.h"]

[[library]]
name = "openssl"
disable = true
""",
        "utf8",
    )
    libs = LS.load_libraries([cfg])
    assert "acme" in libs and "openssl" not in libs
    assert libs["zlib"].calls == ()  # replaced, not merged
    files = [("a.c", 10, ["acme/x.h", "openssl/ssl.h"])]
    surface = LS.build(_db(tmp_path, files, {"a.c": {"acme_run": 2, "SSL_new": 5}}), libs)
    assert surface.libraries["acme"]["a.c"].sites == 1 + 2
    assert (
        "openssl" in surface.libraries
    )  # disabled in the table, so discovery lists it again, as a plain library with no names
    assert surface.libraries["openssl"]["a.c"].names == {}


@pytest.mark.parametrize(
    "body",
    [
        '[[library]]\ninclude = ["x/*"]\n',  # no name
        '[[library]]\nname = "x"\n',  # no patterns
        '[[library]]\nname = "x"\ninclude = "x/*"\n',  # not a list
        '[[library]]\nname = "x"\ninclude = [""]\n',  # empty pattern
        '[[library]]\nname = "x"\ninclude = ["' + "a" * 300 + '"]\n',  # too long
        '[[library]]\nname = "x"\nlanguages = ["cobol"]\ninclude = ["x"]\n',  # unknown language
        "this is not toml [[[",
    ],
)
def test_a_malformed_definition_is_refused_with_a_message(tmp_path, body):
    cfg = tmp_path / "bad.toml"
    cfg.write_text(body, "utf8")
    with pytest.raises(LS.LibraryConfigError):
        LS.load_libraries([cfg])


def test_a_missing_explicit_file_is_an_error_and_xdg_and_src_files_are_found(tmp_path, monkeypatch):
    with pytest.raises(LS.LibraryConfigError):
        LS.load_libraries([tmp_path / "nope.toml"])
    xdg = tmp_path / "xdg" / "gitgalaxy"
    xdg.mkdir(parents=True)
    (xdg / "libraries.toml").write_text('[[library]]\nname = "a"\ninclude = ["a/*"]\n')
    src = tmp_path / "repo" / ".gitgalaxy"
    src.mkdir(parents=True)
    (src / "libraries.toml").write_text('[[library]]\nname = "b"\ninclude = ["b/*"]\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    found = LS.config_files(tmp_path / "repo", None)
    assert [p.parent.parent.name for p in found] == ["xdg", "repo"]  # user config first, the repository's after it


def test_a_scan_without_external_calls_still_reports_imports_and_says_so(tmp_path):
    db = _db(tmp_path, C_FILES, C_EXTERNAL)
    con = sqlite3.connect(db)
    con.execute("DROP TABLE fcall_external")
    con.commit()
    con.close()
    surface = LS.build(db, LS.load_libraries([]))
    assert not surface.external_recorded and set(surface.libraries["openssl"]) == {"src/tls.c"}
    assert "did not record external calls" in LS.report_libraries(surface, 5)


def test_the_surface_change_between_two_scans(tmp_path):
    before = _db(
        tmp_path,
        [("a.c", 100, ["openssl/ssl.h"]), ("old.c", 50, ["openssl/ssl.h"])],
        {"a.c": {"SSL_old": 1, "SSL_keep": 2}},
        "b.db",
    )
    after = _db(
        tmp_path,
        [("a.c", 100, ["openssl/ssl.h"]), ("new.c", 50, ["openssl/ssl.h"])],
        {"a.c": {"SSL_keep": 2, "SSL_new": 1}},
        "a.db",
    )
    libs = LS.load_libraries([])
    ch = LS.change(LS.build(before, libs).libraries["openssl"], LS.build(after, libs).libraries["openssl"])
    assert ch.names_added == ["SSL_new"] and ch.names_dropped == ["SSL_old"]
    assert ch.files_newly_coupled == ["new.c"] and ch.files_no_longer_coupled == ["old.c"]
    assert (ch.files_before, ch.files_after) == (2, 2)
    assert "SSL_new" in LS.report_change("openssl", ch, 5)


def test_databases_are_opened_read_only(tmp_path):
    db = _db(tmp_path, C_FILES, C_EXTERNAL)
    before = db.read_bytes()
    LS.build(db, LS.load_libraries([]))
    assert db.read_bytes() == before


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "libsurface", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=ENV,
        check=False,
    )


def test_command_views_and_errors(tmp_path):
    db = _db(tmp_path, C_FILES, C_EXTERNAL)
    listing = _run(str(db))
    assert (
        listing.returncode == 0
        and "LIBRARIES" in listing.stdout
        and "openssl" in listing.stdout
        and "[table]" in listing.stdout
    )
    out_json = tmp_path / "o.json"
    one = _run(str(db), "--lib", "openssl", "--json", str(out_json))
    assert (
        one.returncode == 0 and "src/tls.c" in one.stdout and json.loads(out_json.read_text())["library"] == "openssl"
    )
    two = _run(str(db), str(db), "--lib", "openssl")
    assert two.returncode == 0 and "SURFACE CHANGE" in two.stdout
    assert _run(str(db), "--lib", "nope").returncode == 1  # unknown library: a message naming the ones in use
    assert _run(str(db), str(db)).returncode == 2  # two scans need --lib
    assert _run(str(tmp_path / "missing.db")).returncode == 2
    bad = tmp_path / "bad.toml"
    bad.write_text('[[library]]\nname = "x"\n')
    assert _run(str(db), "--libs", str(bad)).returncode == 2


def test_reading_a_wal_database_leaves_no_files_behind(tmp_path):
    db = _db(tmp_path, C_FILES, C_EXTERNAL)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()  # the last close removes the -wal file, as a finished scan leaves it
    LS.build(db, LS.load_libraries([]))
    assert sorted(p.name for p in tmp_path.glob("s.db*")) == ["s.db"]  # no -wal, no -shm
