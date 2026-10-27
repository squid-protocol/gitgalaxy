"""A javac that stays up: the JDK's own compiler (javax.tools, what the javac launcher runs) in one JVM per process,
so a test that compiles a small program pays ~0.05 s, not a JVM start (~0.6 s; ~1.7 s on a CI runner).

    from javac_server import javac
    javac([str(jdk / "javac"), "-encoding", "UTF-8", "-d", str(out), str(src)], check=True)

`javac(argv, **kw)` answers as `subprocess.run(argv, **kw)` does for a javac: the return code, the diagnostics on
stderr (printed, as the launcher's would be, unless captured), CalledProcessError with `check`, TimeoutExpired with
`timeout`. The class files are the launcher's, byte for byte (same compiler, same arguments). Anything it cannot answer
the same way runs the launcher instead: no `-encoding` (the launcher reads sources in the locale's charset), a relative path (the server's directory is the one it started in), another
working directory (`cwd`, or os.chdir since), its own `env`, `-J` options, `@argfiles`, a server that died twice.
The program a test then runs stays a `java` of its own. GITGALAXY_JAVAC_SERVER=0: always the launcher.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

SERVER_JAVA = r"""import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class JavacServer {
    public static void main(String[] a) throws Exception {
        JavaCompiler c = ToolProvider.getSystemJavaCompiler();
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        OutputStream out = new BufferedOutputStream(new FileOutputStream(FileDescriptor.out));
        String line;
        while ((line = in.readLine()) != null) {
            String[] args = line.isEmpty() ? new String[0] : line.split("\t", -1);
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            int rc;
            try { rc = c.run(null, buf, buf, args); } catch (Throwable t) { t.printStackTrace(new PrintStream(buf)); rc = 4; }
            byte[] msg = buf.toByteArray();
            out.write((rc + " " + msg.length + "\n").getBytes(StandardCharsets.US_ASCII));
            out.write(msg);
            out.flush();
        }
    }
}
"""
ENV = "GITGALAXY_JAVAC_SERVER"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gitgalaxy-javac-server"


class _Server:
    def __init__(self, bin_dir: Path) -> None:
        self.cwd = os.getcwd()
        classes = _server_classes(bin_dir)
        # (UTF-8 is the server's default charset; a request names its sources' encoding itself, see _servable)
        self.proc = subprocess.Popen([str(bin_dir / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",  # noqa: S603
                                      "-XX:+UseSerialGC", "-cp", str(classes), "JavacServer"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.cwd)  # fmt: skip

    def compile(self, args: list[str], timeout: float | None) -> tuple[int, bytes]:
        """(return code, diagnostics); TimeoutExpired (the server killed) past `timeout`; OSError / ValueError when the
        server is gone."""
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(("\t".join(args) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        got: list[Any] = []

        def read() -> None:
            head = self.proc.stdout.readline().split()  # type: ignore[union-attr]
            got.append((int(head[0]), self.proc.stdout.read(int(head[1]))) if len(head) == 2 else None)  # type: ignore[union-attr]

        t = threading.Thread(target=read, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            self.proc.kill()
            raise subprocess.TimeoutExpired(args, timeout or 0)
        if not got or got[0] is None:
            raise OSError("javac server ended")
        return got[0]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()  # type: ignore[union-attr]
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


_SERVERS: dict[Path, _Server] = {}
_FAILED: dict[Path, int] = {}
_LOCK = threading.Lock()


def _server_classes(bin_dir: Path) -> Path:
    """JavacServer.class for this JDK, compiled once (a directory per source and JDK, renamed into place whole)."""
    key = hashlib.sha256(SERVER_JAVA.encode() + str(bin_dir.resolve()).encode()).hexdigest()[:16]
    done = CACHE / key
    if (done / "JavacServer.class").is_file():
        return done
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=CACHE, prefix=".build-"))
    (tmp / "JavacServer.java").write_text(SERVER_JAVA, encoding="utf-8")
    subprocess.run([str(bin_dir / "javac"), "-encoding", "UTF-8", "-d", str(tmp), str(tmp / "JavacServer.java")],  # noqa: S603
                   check=True, capture_output=True)  # fmt: skip
    try:
        tmp.rename(done)
    except OSError:  # another process won the race: its copy is the same
        pass
    return done


def _close_all() -> None:
    for s in _SERVERS.values():
        s.close()


atexit.register(_close_all)


def _servable(argv: list[str], kw: dict[str, Any]) -> bool:
    """The server answers exactly as the launcher would: absolute paths, no own env or cwd, no launcher options."""
    if os.environ.get(ENV, "1") == "0" or kw.get("cwd") is not None or kw.get("env") is not None:
        return False
    if any(kw.get(k) is not None for k in ("input", "stdin", "stdout", "stderr")) or kw.get("shell"):
        return False  # (own streams: the launcher wires them)
    if "-encoding" not in argv:
        return False  # (the launcher reads the sources in the locale's charset, the server in UTF-8)
    for a in argv[1:]:
        if a in ("-version", "--version", "-help", "--help", "-X", "--help-extra"):
            return False  # (the launcher prints these on stdout)
        if a.startswith(("-J", "@")) or "\t" in a or "\n" in a:
            return False
        if not a.startswith("-") and ("/" in a or os.sep in a or a.endswith(".java")):
            if any(e and not os.path.isabs(e) for e in a.split(os.pathsep)):
                return False
    return True


def javac(argv: list[str], **kw: Any) -> subprocess.CompletedProcess:
    """`subprocess.run(argv, **kw)` for a javac launcher `argv[0]` (its JDK's bin/javac), through that JDK's server."""
    bin_dir = Path(argv[0]).resolve().parent  # (/usr/bin/javac -> its JDK's bin: the server runs THAT JDK's java)
    if (Path(argv[0]).name not in ("javac", "javac.exe") or not os.path.isabs(argv[0])  # (a bare javac: PATH's)
            or not _servable(argv, kw) or _FAILED.get(bin_dir, 0) >= 2):  # fmt: skip
        return subprocess.run(argv, **kw)  # noqa: S603
    with _LOCK:
        s = _SERVERS.get(bin_dir)
        if s is None or s.proc.poll() is not None or s.cwd != os.getcwd():
            if s is not None:
                s.close()
            try:
                s = _SERVERS[bin_dir] = _Server(bin_dir)
            except (OSError, subprocess.CalledProcessError):
                _FAILED[bin_dir] = 2
                return subprocess.run(argv, **kw)  # noqa: S603
        try:
            rc, msg = s.compile(argv[1:], kw.get("timeout"))
        except subprocess.TimeoutExpired:
            _SERVERS.pop(bin_dir, None)
            raise subprocess.TimeoutExpired(argv, kw.get("timeout") or 0) from None
        except (OSError, ValueError):
            _SERVERS.pop(bin_dir, None)
            _FAILED[bin_dir] = _FAILED.get(bin_dir, 0) + 1
            return subprocess.run(argv, **kw)  # noqa: S603
    text = bool(kw.get("text") or kw.get("universal_newlines") or kw.get("encoding") or kw.get("errors"))
    err: str | bytes = msg.decode(kw.get("encoding") or "utf-8", kw.get("errors") or "replace") if text else msg
    out: str | bytes = "" if text else b""
    captured = bool(kw.get("capture_output"))
    if not captured and msg:  # the launcher would have written them to the inherited stderr
        sys.stderr.write(msg.decode("utf-8", "replace"))
        sys.stderr.flush()
    proc = subprocess.CompletedProcess(argv, rc, out if captured else None, err if captured else None)
    if kw.get("check") and rc != 0:
        raise subprocess.CalledProcessError(rc, argv, proc.stdout, proc.stderr)
    return proc


def jdk_bin() -> Path | None:
    """bin/ of the JDK a test would use (JDK_17, else JAVA_HOME), or None when it has no javac."""
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


def warm() -> bool:
    """Start the server and run one compile and one `java` before any test does (#5606).

    The first compile and first run in a pytest-xdist worker pay a JVM start, the JDK's pages and the compiler's cold
    JIT: on a loaded CI runner that landed on whichever test the worker drew first (0.8 s locally, 15-20 s on CI) and
    tripped the per-test time ratchet at random. Called from a conftest hook, outside every test's timing. True when
    warmed; False (nothing started) with no JDK or GITGALAXY_JAVAC_SERVER=0.
    """
    bin_dir = jdk_bin()
    if bin_dir is None or os.environ.get(ENV, "1") == "0":
        return False
    with tempfile.TemporaryDirectory(prefix="javac-warm-") as tmp:
        src = Path(tmp) / "Warm.java"
        src.write_text("public class Warm { public static void main(String[] a) { System.out.print(a.length); } }\n",
                       encoding="utf-8")  # fmt: skip
        out = Path(tmp) / "classes"
        try:
            javac([str(bin_dir / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(out), str(src)],
                  check=True, capture_output=True, timeout=120)  # fmt: skip
            subprocess.run([str(bin_dir / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(out), "Warm"],  # noqa: S603
                           check=True, capture_output=True, encoding="utf-8", timeout=120)  # fmt: skip
        except (OSError, subprocess.SubprocessError):
            return False  # a warm-up never fails a run: the tests find out for themselves
    return True
