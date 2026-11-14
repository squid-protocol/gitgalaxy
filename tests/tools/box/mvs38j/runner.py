#!/usr/bin/env python3
"""MVS 3.8J job runner (JCL oracle tier 2, #8414): submit a deck, parse the JES2 job log to JSON.

Internal use only until counsel answers Q16: no MVS 3.8J result is published. Stdlib only; runs on the host against a
started box (`mvs38j.sh start`, card reader socket on 127.0.0.1:3505, printer file under the work dir).

    runner.py submit DECK [--printer FILE] [--host H] [--port P] [--timeout S]   # submit, wait for the job, print JSON
    runner.py parse PRINTER_FILE [JOB]                                           # parse a captured printer file

The JSON carries provenance `mvs38j-run` and, per job: the steps (IEF142I executed with its completion code, IEF272I /
IEF202I not executed), dataset dispositions (IEF285I), abends (IEF450I), a JCL-error flag (IEF452I) and the SYSOUT line
count. It reads only the messages MVS 3.8J writes; a message it does not know is counted in `unparsed_ief`, never guessed.
"""

import argparse
import json
import re
import socket
import sys
import time
from pathlib import Path

PROVENANCE = "mvs38j-run"
# IEF142I JOB STEP [PROCSTEP] - STEP WAS EXECUTED - COND CODE 0004 ; IEF272I / IEF202I: not executed / not run.
_STEP = re.compile(
    r"(IEF142I|IEF272I|IEF202I)\s+(\S+)\s+(\S+)\s+(?:(\S+)\s+)?-\s+STEP WAS (NOT )?(?:EXECUTED|RUN)"
    r"(?:.*?COND CODE (\d{4}))?"
)
_DISP = re.compile(r"IEF285I\s+(\S.*?)\s+(KEPT|DELETED|PASSED|CATALOGED|UNCATALOGED|SYSOUT)\s*$")
_ABEND = re.compile(r"IEF450I\s+(\S+)\s+(\S+)\s+(?:(\S+)\s+)?-\s+ABEND\s+(S[0-9A-F]{3})\s+(U\d{4})")
_JCLERR = re.compile(r"IEF452I\s+(\S+)\s+-\s+JOB NOT RUN - JCL ERROR")
_ANY_IEF = re.compile(r"\bIEF\d{3}[A-Z]\b")
_KNOWN_IEF = {"IEF142I", "IEF272I", "IEF202I", "IEF285I", "IEF450I", "IEF452I", "IEF403I", "IEF404I"}
_STARTED = re.compile(r"IEF403I\s+(\S+)\s+-\s+STARTED")
_JOBEND = re.compile(r"\$HASP395\s+(\S+)\s+ENDED")


def parse_log(text, job=None):
    """Parse a printer file's text into {provenance, jobs: [{job, steps, dispositions, abends, jcl_error, ...}]}."""
    jobs = {}

    def rec(name):
        return jobs.setdefault(
            name,
            {"job": name, "steps": [], "dispositions": [], "abends": [], "jcl_error": False, "ended": False},
        )

    unparsed = 0
    current = None  # IEF285I names no job: it belongs to the job last seen starting or reporting a step
    for line in text.splitlines():
        if m := _STARTED.search(line):
            current = rec(m.group(1))
        elif m := _STEP.search(line):
            current = rec(m.group(2))
            executed = m.group(5) is None
            current["steps"].append(
                {
                    "step": m.group(3),
                    "procstep": m.group(4),
                    "executed": executed,
                    "cond_code": int(m.group(6)) if executed and m.group(6) else None,
                    "message": m.group(1),
                }
            )
        elif m := _ABEND.search(line):
            rec(m.group(1))["abends"].append({"step": m.group(2), "system": m.group(4), "user": m.group(5)})
        elif m := _JCLERR.search(line):
            rec(m.group(1))["jcl_error"] = True
        elif m := _JOBEND.search(line):
            rec(m.group(1))["ended"] = True
        elif m := _DISP.search(line):
            if current:
                current["dispositions"].append({"dsn": m.group(1), "disposition": m.group(2)})
        else:
            ief = _ANY_IEF.search(line)
            if ief and ief.group(0) not in _KNOWN_IEF:
                unparsed += 1
    chosen = [j for j in jobs.values() if job is None or j["job"] == job.upper()]
    return {"provenance": PROVENANCE, "jobs": chosen, "unparsed_ief": unparsed, "sysout_lines": len(text.splitlines())}


def submit(deck, host="127.0.0.1", port=3505):
    """Send the deck's card images to the socket card reader; the connection closing ends the deck."""
    cards = [ln.rstrip("\r\n").ljust(80)[:80] for ln in Path(deck).read_text().splitlines()]
    if not cards or not cards[0].startswith("//"):
        raise ValueError(f"{deck} does not start with a JCL card")
    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(("\n".join(cards) + "\n").encode("ascii", "replace"))


def wait_for_job(printer, job, timeout, since=0, interval=1.0):
    """Block until `printer`, past byte `since`, shows `$HASP395 job ENDED` (or a JCL error); False on timeout."""
    end = time.monotonic() + timeout
    p = Path(printer)
    while time.monotonic() < end:
        if p.is_file():
            got = parse_log(p.read_bytes()[since:].decode("utf-8", "backslashreplace"), job)["jobs"]
            if got and (got[0]["ended"] or got[0]["jcl_error"]):
                return True
        time.sleep(interval)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("submit")
    sp.add_argument("deck")
    sp.add_argument("--printer", required=True, help="the printer file Hercules writes (3.8J's 00E)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=3505)
    sp.add_argument("--timeout", type=float, default=120)
    pp = sub.add_parser("parse")
    pp.add_argument("printer_file")
    pp.add_argument("job", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd == "parse":
        print(json.dumps(parse_log(Path(args.printer_file).read_text(errors="backslashreplace"), args.job), indent=1))
        return 0
    first = Path(args.deck).read_text().splitlines()[:1]
    m = re.match(r"//(\S+)\s+JOB\b", first[0] if first else "")
    if not m:
        print("runner: the first card must be '//NAME JOB ...'", file=sys.stderr)
        return 1
    name = m.group(1)
    before = Path(args.printer).stat().st_size if Path(args.printer).is_file() else 0
    submit(args.deck, args.host, args.port)
    if not wait_for_job(args.printer, name, args.timeout, before):
        print(f"runner: {name} did not end within {args.timeout:.0f} s", file=sys.stderr)
        return 1
    text = Path(args.printer).read_bytes()[before:].decode("utf-8", "backslashreplace")
    print(json.dumps(parse_log(text, name), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
