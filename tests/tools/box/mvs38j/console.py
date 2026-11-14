"""A minimal telnet client for Hercules' 3215 console (device 001F, port 3270): JCL oracle tier 2 (#8414).

Internal use only until counsel answers Q16. Stdlib only. The SMP stages of Jay Moseley's sysgen (smp1.cnf, smp2.cnf)
run on the telnet 3215 at 001F, not on the integrated 1052-C `/` console `sysgen.py` uses for the stand-alone programs.
The client answers option negotiation by refusing everything except suppress-go-ahead, binary and echo, strips IAC
sequences from the received stream, and collects text on a thread so `wait` can match console messages.
"""

import re
import socket
import threading
import time

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
ACCEPT = {0, 1, 3}  # binary, echo, suppress-go-ahead


class ConsoleError(RuntimeError):
    pass


def strip_telnet(data, state):
    """Split `data` into (text bytes, replies); `state` is a dict carrying a partial sequence between calls."""
    buf = state.pop("pending", b"") + data
    out, replies, i = bytearray(), bytearray(), 0
    while i < len(buf):
        b = buf[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= len(buf):
            break
        cmd = buf[i + 1]
        if cmd == IAC:
            out.append(IAC)
            i += 2
        elif cmd in (DO, DONT, WILL, WONT):
            if i + 2 >= len(buf):
                break
            opt = buf[i + 2]
            if cmd == DO:
                replies += bytes([IAC, WILL if opt in ACCEPT else WONT, opt])
            elif cmd == WILL:
                replies += bytes([IAC, DO if opt in ACCEPT else DONT, opt])
            i += 3
        elif cmd == SB:
            end = buf.find(bytes([IAC, SE]), i + 2)
            if end < 0:
                break
            i = end + 2
        else:
            i += 2
    if i < len(buf):
        state["pending"] = bytes(buf[i:])
    return bytes(out), bytes(replies)


class Console:
    """One telnet session on the 3215 console; lines are collected as they arrive."""

    def __init__(self, host="127.0.0.1", port=3270, connect_timeout=60):
        self.host, self.port, self.connect_timeout = host, port, connect_timeout
        self.lines, self._partial, self._tel = [], "", {}
        self._cv = threading.Condition()
        self.sock = None

    def connect(self):
        end = time.monotonic() + self.connect_timeout
        while True:  # Hercules binds the console port a moment after it starts
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=5)
                break
            except OSError as e:
                if time.monotonic() > end:
                    raise ConsoleError(f"no console on {self.host}:{self.port}: {e}") from e
                time.sleep(0.5)
        self.sock.settimeout(None)
        threading.Thread(target=self._pump, daemon=True).start()
        return self

    def _pump(self):
        while True:
            try:
                data = self.sock.recv(4096)
            except OSError:
                data = b""
            with self._cv:
                if not data:
                    self.closed = True
                    self._cv.notify_all()
                    return
                self._feed(data)

    def _feed(self, data):
        text, replies = strip_telnet(data, self._tel)
        if replies:
            self.sock.sendall(replies)
        self._partial += text.decode("ascii", errors="backslashreplace").replace("\r", "")
        *done, self._partial = self._partial.split("\n")
        self.lines.extend(done)
        self._cv.notify_all()

    closed = False

    def send(self, line):
        self.sock.sendall(line.encode("ascii") + b"\r\n")

    def mark(self):
        with self._cv:
            return len(self.lines)

    def wait(self, pattern, timeout, since=0):
        """The first line at or after `since` matching `pattern` (a prompt without a newline counts too)."""
        rx, end, i = re.compile(pattern), time.monotonic() + timeout, since
        with self._cv:
            while True:
                while i < len(self.lines):
                    if rx.search(self.lines[i]):
                        return self.lines[i]
                    i += 1
                if self._partial and rx.search(self._partial):
                    return self._partial
                if self.closed:
                    raise ConsoleError(f"console closed while waiting for /{pattern}/")
                left = end - time.monotonic()
                if left <= 0:
                    raise ConsoleError(f"timed out after {timeout}s waiting for /{pattern}/")
                self._cv.wait(min(left, 1.0))

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
