"""Mainframe credential shapes (#8625, security epic #8427): what the hardcoded-secrets signature cannot see.

`SecurityLens`'s `hardcoded_secrets` wants a 16+ character quoted value; a JCL `PASSWORD=` is at most 8 characters and
unquoted, so a leak in a JCL member, PROC, REXX exec, CLIST or Db2 connect step passes it. These patterns feed Vault
Sentinel only (like `EXTRA_SECRETS`): the engine's signature feeds scoring and the golden masters, this does not.

Shapes (the syntax each reads; IBM manual titles, page numbers not checked from this environment):
  * `PASSWORD=` on a JOB, EXEC or DD statement. z/OS MVS JCL Reference, "JOB statement", PASSWORD parameter.
  * `PARM='... PASSWORD=x ...'` on EXEC. z/OS MVS JCL Reference, "EXEC statement", PARM parameter.
  * In-stream (`DD *` / `DD DATA`) FTP login lines, `USER id pw` or `PASS pw`. z/OS Communications Server: IP User's
    Guide and Commands, "FTP" login and subcommands.
  * Db2 CONNECT with a USER clause and a literal USING password. Db2 for z/OS SQL Reference, CONNECT statement: the
    safe form takes host variables (`USING :PW`), so a literal is the leak. The command-line form is in the Db2 Command
    Reference (CONNECT).
  * REXX `pw = 'literal'` / CLIST `SET &PW = literal` next to a user ID. z/OS TSO/E REXX Reference (assignments) and
    z/OS TSO/E CLISTs (SET statement).

Near-misses that stay quiet: a symbolic (`&PW`), a host variable (`:PW`), an empty or computed value, a comment, a
documentation member that only names the RACF `PASSWORD` operand.

Every pattern opens on a literal or runs over bounded classes, so none can backtrack badly.
"""

import re

_SYM = r"[A-Za-z0-9@#$]"  # JCL / FTP password characters (national characters included)
_PW_WORD = r"(?:PASSWORD|PASSWD|PWD|PSWD)"

_JCL_STATEMENT = re.compile(r"^//(?!\*)")
_JCL_PASSWORD = re.compile(r"\bPASSWORD=\(?(?![&,)])(" + _SYM + r"{1,8})\b")
_JCL_PARM_PASSWORD = re.compile(
    r"\bPARM=\(?['\"][^'\"\n]{0,100}?\b" + _PW_WORD + r"[=/ ][ ]?(?![&:])" + _SYM + r"{3,32}", re.I
)
_INSTREAM_START = re.compile(r"^//[A-Z0-9@#$]{0,8}[ \t]+DD[ \t]+(?:\*|DATA)(?![A-Za-z0-9])")
_FTP_USER_PW = re.compile(r"^[ \t]*USER[ \t]+[^\s&]+[ \t]+(?![&:])\S{1,32}[ \t]*$", re.I)
_FTP_PASS = re.compile(r"^[ \t]*PASS[ \t]+(?![&:])\S{1,32}[ \t]*$", re.I)
_DB2_CONNECT = re.compile(
    r"\bCONNECT\b(?:[ \t]+TO[ \t]+[\w.:$#@-]{1,64})?[ \t]+USER[ \t]+[^\s]{1,64}[ \t]+USING[ \t]+(?![:&?])['\"]?[^\s'\";:]{1,64}",
    re.I,
)
_REXX_PW = re.compile(
    r"\b(?:PW|PWD|PASS|PASSWD|PASSWORD|PSW|PSWD)[A-Z0-9_.]{0,12}[ \t]*=[ \t]*(['\"])[^'\"\s&]{1,32}\1", re.I
)
_REXX_USER = re.compile(r"\b(?:USER|USERID|UID|LOGON)[A-Z0-9_.]{0,12}[ \t]*=[ \t]*(['\"])[^'\"\s]{1,32}\1", re.I)
_CLIST_PW = re.compile(
    r"\bSET[ \t]+&(?:[A-Z0-9_]{0,12})(?:PW|PWD|PASSWORD|PASSWD)[A-Z0-9_]{0,12}[ \t]*=[ \t]*['\"]?[A-Za-z0-9@#$]{1,32}",
    re.I,
)
_CLIST_USER = re.compile(r"\bSET[ \t]+&[A-Z0-9_]{0,12}(?:USER|USERID|UID)[A-Z0-9_]{0,12}[ \t]*=[ \t]*(?![&\s])", re.I)
_USER_WINDOW = 5  # lines either side: "next to a user ID"


def _code_lines(text: str) -> list[str]:
    """The lines with comments blanked: JCL `//*`, COBOL fixed-format `*` / `/` in column 7 and `*>`, REXX/CLIST `/* */`."""
    lines = text.splitlines()
    is_jcl = any(_JCL_STATEMENT.match(ln) for ln in lines)
    out: list[str] = []
    in_block = False
    for ln in lines:
        if ln.startswith("//*") or re.match(r"^[ 0-9]{6}[*/]", ln) or ln.lstrip().startswith("*>"):
            out.append("")
            continue
        if is_jcl:
            out.append(ln)  # a `/*` at column 1 is the JCL delimiter statement, not a comment
            continue
        kept = []
        pos = 0
        while pos < len(ln):
            if in_block:
                end = ln.find("*/", pos)
                if end < 0:
                    pos = len(ln)
                else:
                    in_block, pos = False, end + 2
            else:
                start = ln.find("/*", pos)
                if start < 0:
                    kept.append(ln[pos:])
                    pos = len(ln)
                else:
                    kept.append(ln[pos:start])
                    in_block, pos = True, start + 2
        out.append("".join(kept))
    return out


# Languages whose files `SecurityLens` reads these shapes in: the JCL / PROC and REXX profiles, and COBOL for an
# embedded Db2 CONNECT. The snippet never holds the value: it names the shape.
MAINFRAME_SECRET_LANGUAGES = frozenset({"jcl", "rexx", "cobol"})


def mainframe_secret_sites(text: str) -> list[tuple[int, int, str]]:
    """Each mainframe credential shape in `text` as (1-indexed line, 1-indexed column, redacted label); [] when clean."""
    lines = _code_lines(text)
    sites: list[tuple[int, int, str]] = []
    in_stream = False
    user_lines = [i for i, ln in enumerate(lines) if _REXX_USER.search(ln) or _CLIST_USER.search(ln)]

    def add(i: int, m: "re.Match[str] | None", label: str) -> None:
        if m:
            sites.append((i + 1, m.start() + 1, f"{label} [REDACTED]"))

    for i, ln in enumerate(lines):
        if _JCL_STATEMENT.match(ln):
            in_stream = bool(_INSTREAM_START.match(ln))
            add(i, _JCL_PASSWORD.search(ln), "JCL PASSWORD=")
            add(i, _JCL_PARM_PASSWORD.search(ln), "JCL PARM= password")
            continue
        if ln.startswith("/*"):
            in_stream = False
        elif in_stream and (m := _FTP_USER_PW.match(ln) or _FTP_PASS.match(ln)):
            add(i, m, "in-stream FTP login")
            continue
        m = _DB2_CONNECT.search(ln)
        if m:
            add(i, m, "Db2 CONNECT ... USING")
            continue
        m = _REXX_PW.search(ln) or _CLIST_PW.search(ln)
        if m and any(abs(u - i) <= _USER_WINDOW for u in user_lines):
            add(i, m, "literal password next to a user ID")
    return sites


def mainframe_secret_hits(text: str) -> int:
    """How many mainframe credential shapes `text` holds (0 for a clean or non-mainframe file)."""
    return len(mainframe_secret_sites(text))
