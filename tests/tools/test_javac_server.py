"""tests/tools/javac_server.py answers as the javac launcher does, and leaves to it whatever it cannot answer the same."""

from __future__ import annotations

import filecmp
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import javac_server as js  # noqa: E402

HOME = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME") or ""
JAVAC = Path(HOME) / "bin" / "javac"
pytestmark = pytest.mark.skipif(not JAVAC.is_file(), reason="needs a JDK (JDK_17 / JAVA_HOME)")


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(js, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(js, "_SERVERS", {})
    monkeypatch.setattr(js, "_FAILED", {})
    monkeypatch.delenv(js.ENV, raising=False)
    yield
    js._close_all()


def _src(tmp: Path, body: str = "static int one() { return 1; }") -> Path:
    f = tmp / "src" / "A.java"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"public class A {{ {body} public static void main(String[] a) {{ System.out.println(\"é\" + one()); }} }}\n",
                 encoding="utf-8")  # fmt: skip
    return f


def _calls(monkeypatch):
    seen = []
    real = subprocess.run
    monkeypatch.setattr(js.subprocess, "run", lambda argv, **kw: seen.append(argv) or real(argv, **kw))
    return seen


def test_the_classes_are_the_launchers_byte_for_byte(tmp_path):
    src = _src(tmp_path)
    subprocess.run([str(JAVAC), "-encoding", "UTF-8", "-d", str(tmp_path / "cli"), str(src)], check=True)
    r = js.javac([str(JAVAC), "-encoding", "UTF-8", "-d", str(tmp_path / "srv"), str(src)], check=True,
                 capture_output=True)  # fmt: skip
    assert r.returncode == 0 and r.stderr == b""
    cmp = filecmp.dircmp(tmp_path / "cli", tmp_path / "srv")
    assert cmp.common_files == ["A.class"] and not cmp.diff_files and not cmp.left_only and not cmp.right_only
    assert bin_dir_has_server()


def bin_dir_has_server() -> bool:
    return any(s.proc.poll() is None for s in js._SERVERS.values())


def test_a_compile_error_is_the_launchers_return_code_and_diagnostics(tmp_path):
    src = _src(tmp_path, body="static int one() { return nope; }")
    argv = [str(JAVAC), "-encoding", "UTF-8", "-d", str(tmp_path / "o"), str(src)]
    cli = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    srv = js.javac(argv, capture_output=True, text=True, encoding="utf-8")
    assert srv.returncode == cli.returncode == 1
    assert "cannot find symbol" in srv.stderr and srv.stderr == cli.stderr
    with pytest.raises(subprocess.CalledProcessError) as e:
        js.javac(argv, check=True, capture_output=True)
    assert e.value.returncode == 1


def test_what_it_cannot_answer_the_same_goes_to_the_launcher(tmp_path, monkeypatch):
    src = _src(tmp_path)
    seen = _calls(monkeypatch)
    out = str(tmp_path / "o")
    js.javac([str(JAVAC), "-encoding", "UTF-8", "-d", out, "src/A.java"], cwd=tmp_path, check=True)  # relative + cwd
    js.javac([str(JAVAC), "-version"], capture_output=True)  # prints on stdout
    js.javac([str(JAVAC), "-J-Xmx64m", "-encoding", "UTF-8", "-d", out, str(src)], check=True)  # launcher option
    js.javac([str(JAVAC), "-d", out, str(src)], check=True)  # no -encoding: the locale's charset, the launcher's
    monkeypatch.setenv(js.ENV, "0")
    js.javac([str(JAVAC), "-encoding", "UTF-8", "-d", out, str(src)], check=True)  # switched off
    assert len([a for a in seen if a[0] == str(JAVAC)]) == 5 and not js._SERVERS


def test_a_server_that_died_is_replaced(tmp_path):
    src = _src(tmp_path)
    argv = [str(JAVAC), "-encoding", "UTF-8", "-d", str(tmp_path / "o"), str(src)]
    js.javac(argv, check=True)
    (first,) = js._SERVERS.values()
    first.proc.kill()
    first.proc.wait()
    js.javac(argv, check=True)
    (second,) = js._SERVERS.values()
    assert second is not first and second.proc.poll() is None


def test_a_linked_launcher_is_served_by_its_own_jdk(tmp_path):
    """/usr/bin/javac and /usr/bin/java can be two JDKs (Debian alternatives: 17 and 21 on the box this was found on):
    the server runs the java of the JDK the javac link resolves to, never the java beside the link."""
    links = tmp_path / "bin"
    links.mkdir()
    (links / "javac").symlink_to(JAVAC.resolve())
    (links / "java").symlink_to("/bin/false")  # the other JDK's java, here one that cannot serve at all
    src = _src(tmp_path)
    r = js.javac([str(links / "javac"), "-encoding", "UTF-8", "-d", str(tmp_path / "o"), str(src)], check=True,
                 capture_output=True)  # fmt: skip
    assert r.returncode == 0 and (tmp_path / "o" / "A.class").is_file()
    assert [b.name for b in js._SERVERS] == ["bin"] and list(js._SERVERS)[0] == JAVAC.resolve().parent


def test_warm_starts_one_server_and_a_later_compile_reuses_it(tmp_path):
    assert js.warm() is True
    (first,) = js._SERVERS.values()
    assert js.warm() is True  # idempotent: the same server answers again
    src = _src(tmp_path)
    js.javac([str(JAVAC), "-encoding", "UTF-8", "-d", str(tmp_path / "o"), str(src)], check=True)
    (again,) = js._SERVERS.values()
    assert again is first and (tmp_path / "o" / "A.class").is_file()


def test_warm_starts_nothing_when_switched_off_or_without_a_jdk(monkeypatch, tmp_path):
    monkeypatch.setenv(js.ENV, "0")
    assert js.warm() is False and not js._SERVERS
    monkeypatch.delenv(js.ENV)
    for var in ("JDK_17", "JAVA_HOME"):
        monkeypatch.setenv(var, str(tmp_path / "no-jdk"))
    assert js.jdk_bin() is None and js.warm() is False and not js._SERVERS


def test_warm_never_fails_a_run_when_the_toolchain_is_broken(monkeypatch, tmp_path):
    bin_dir = tmp_path / "jdk" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "javac").symlink_to("/bin/false")
    monkeypatch.setenv("JDK_17", str(tmp_path / "jdk"))
    assert js.warm() is False
