"""#4265: COPY library resolution -- the estate's own library concatenation, when it is declared.

On z/OS a `COPY member` is found by searching the program's SYSLIB concatenation (its copy
libraries, in order): the FIRST library holding the member wins. `COPY member IN|OF library`
searches that library only. Without a declaration the scan cannot know either -- the import
resolver then narrows same-named members by language, program-ness and proximity (#3199), as
it always has. With one (`galaxyscope --copy-libraries FILE`), a COPY resolves the way the
compiler resolves it, and a member that sits in more than one library of a program's search
order is REPORTED as a collision (the first one still wins, as on z/OS).

The declaration is a JSON (or YAML, with PyYAML) file::

    {
      "libraries": {"PAYRCPY": ["apps/PAYR/copybook"], "SHRCPY": ["shared/copylib"]},
      "syslib": [
        {"programs": "apps/PAYR/*", "order": ["PAYRCPY", "PAYRDCL", "SHRCPY"]},
        {"programs": "*", "order": ["SHRCPY"]}
      ]
    }

`libraries` maps a library-name (as `COPY ... IN` writes it) to the scan-relative directories
that hold its members (a PDS is flat: a member is a file directly in one of them, any
extension). `syslib` lists search orders; a program takes the FIRST entry whose `programs`
glob (fnmatch, `*` crosses `/`) matches its scan-relative path. A program no entry matches and
a library-name the declaration does not know fall back to the default resolver. A program WITH
a declared search order is held to it (#4420): a member found in none of its libraries -- or not
in the library `IN` names -- gets no edge, as the compiler would not find it either (nothing
falls back to a program source of the same name), and is reported as a gap
(`copy_member_gaps`).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CopyLibraryError(ValueError):
    """A --copy-libraries declaration that cannot be read."""


@dataclass
class CopyLibraries:
    libraries: dict[str, list[str]] = field(default_factory=dict)  # NAME -> directories
    syslib: list[tuple[str, list[str]]] = field(default_factory=list)  # (programs glob, [NAME, ...])

    def order_for(self, importer: str) -> list[str] | None:
        """The library search order of the program at scan-relative `importer`, or None."""
        path = importer.replace("\\", "/")
        for glob, order in self.syslib:
            if fnmatch.fnmatchcase(path, glob):
                return order
        return None

    def knows(self, library: str) -> bool:
        return library.upper() in self.libraries


def _norm_dir(d: str) -> str:
    return d.replace("\\", "/").strip("/").upper()


def parse_copy_libraries(spec: Any) -> CopyLibraries:
    """A CopyLibraries from a parsed declaration (dict), raising CopyLibraryError on a bad shape."""
    if not isinstance(spec, dict):
        raise CopyLibraryError("a copy-library declaration is an object with `libraries` and `syslib`")
    libs: dict[str, list[str]] = {}
    for name, dirs in (spec.get("libraries") or {}).items():
        if isinstance(dirs, str):
            dirs = [dirs]
        if not isinstance(dirs, list) or not all(isinstance(d, str) and d.strip() for d in dirs):
            raise CopyLibraryError(f"library {name!r}: a directory or a list of directories")
        libs[str(name).upper()] = [_norm_dir(d) for d in dirs]
    order: list[tuple[str, list[str]]] = []
    for i, entry in enumerate(spec.get("syslib") or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("programs"), str):
            raise CopyLibraryError(f"syslib[{i}]: needs `programs` (a glob) and `order` (library-names)")
        names = [str(n).upper() for n in entry.get("order") or []]
        unknown = [n for n in names if n not in libs]
        if unknown:
            raise CopyLibraryError(f"syslib[{i}]: unknown library-name(s) {', '.join(unknown)}")
        order.append((entry["programs"].replace("\\", "/"), names))
    return CopyLibraries(libs, order)


def load_copy_libraries(path: str | None) -> CopyLibraries | None:
    """The declaration in the JSON / YAML file at `path`, or None when no path is given."""
    if not path:
        return None
    text = Path(path).read_text(encoding="utf-8")
    try:
        if Path(path).suffix.lower() in (".yaml", ".yml"):
            import yaml  # optional dependency; JSON needs nothing

            spec = yaml.safe_load(text)
        else:
            spec = json.loads(text)
    except Exception as exc:  # a malformed file is the user's to fix, reported with its name
        raise CopyLibraryError(f"{path}: {exc}") from exc
    return parse_copy_libraries(spec)


class MemberIndex:
    """(library directory, MEMBER) -> the scanned files that are that member."""

    def __init__(self, paths: list[str]):
        self._index: dict[tuple[str, str], list[str]] = {}
        for p in paths:
            norm = p.replace("\\", "/")
            directory, _, name = norm.rpartition("/")
            stem = name.rsplit(".", 1)[0] if "." in name.lstrip(".") else name
            self._index.setdefault((directory.upper(), stem.upper()), []).append(p)

    def members(self, libs: CopyLibraries, library: str, member: str) -> list[str]:
        out: list[str] = []
        for d in libs.libraries.get(library.upper(), []):
            out += self._index.get((d, member.upper()), [])
        return out


# #5649: the stand-in copybooks GitGalaxy writes for system members the estates COPY but never ship (never
# IBM's text, owner 2026-10-11): one shared directory the translator falls back on (det/source._SHIPPED_COPY)
# and the engine lays records out from, so both read the same bytes. Member -> its oracle-register entry.
STAND_IN_DIR = Path(__file__).resolve().parent.parent / "tools" / "cobol_to_java" / "det" / "copy"


def stand_in_registers() -> dict[str, str]:
    """Each stand-in member and the register entry that records it as an assumption (W1: MQ, L4: LE)."""
    from gitgalaxy.standards.mq import STAND_INS

    return {**dict.fromkeys(STAND_INS, "W1"), "CEEIGZCT": "L4"}


def stand_in_text(member: str) -> str | None:
    """A stand-in member's source with its comment lines (indicator `*` or `/`) and sequence area blanked,
    or None when `member` is no registered stand-in. Line numbers are kept."""
    member = member.upper()
    if member not in stand_in_registers():
        return None
    path = STAND_IN_DIR / f"{member}.cpy"
    if not path.is_file():
        return None
    from gitgalaxy.core.source_text import read_source

    lines = read_source(path).text.splitlines()
    return "\n".join("" if line[6:7] in ("*", "/") else line[:72] for line in lines) + "\n"


# #5649: the system members the translator also ships (det/copy), laid out by the engine from the same bytes. They are
# not register stand-ins (stand_in_registers: W1 / L4), so the readiness inventory and the register pins skip them.
SYSTEM_MEMBERS = ("DFHAID", "DFHBMSCA", "DFHEIBLK", "SQLCA", "SQLDA")


def system_member_text(member: str) -> str | None:
    """A shipped system member's source, comments and sequence area blanked as in `stand_in_text`, or None."""
    member = member.upper()
    if member not in SYSTEM_MEMBERS:
        return None
    from gitgalaxy.core.source_text import read_source

    lines = read_source(STAND_IN_DIR / f"{member}.cpy").text.splitlines()
    return "\n".join("" if line[6:7] in ("*", "/") else line[:72] for line in lines) + "\n"


class DirectoryIndex:
    """#8111 slice 6: with no `--copy-libraries`, a library is the directory it is named after. Maps (directory
    name or scan-relative directory, MEMBER) -> the scanned files that are that member (any case, any extension or none)."""

    def __init__(self, paths: list[str]):
        self._by_name: dict[tuple[str, str], list[str]] = {}
        self._by_dir: dict[tuple[str, str], list[str]] = {}
        for p in paths:
            directory, _, name = p.replace("\\", "/").rpartition("/")
            stem = (name.rsplit(".", 1)[0] if "." in name.lstrip(".") else name).upper()
            self._by_name.setdefault((directory.rpartition("/")[2].upper(), stem), []).append(p)
            self._by_dir.setdefault((directory.upper(), stem), []).append(p)

    def named(self, library: str, member: str) -> list[str]:
        """Files `member` in any directory whose own name is `library`."""
        return self._by_name.get((library.upper(), member.upper()), [])

    def in_dir(self, directory: str, member: str) -> list[str]:
        return self._by_dir.get((directory.upper(), member.upper()), [])


_JCL_EXTS = (".jcl", ".prc", ".proc")
_JCL_FILE_CAP = 5000  # JCL files read for one scan; a bigger estate declares nothing past it
_JCL_PRUNE = {".git", "node_modules"}
_COMPILER_PGM = "IGYCRCTL"  # Enterprise COBOL; the IGYW* cataloged procs run it under a qualified step name
_SYSIN_MEMBER = re.compile(r"\(([A-Z0-9@#$]{1,8})\)$", re.I)


def _compile_steps(text: str, procs: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """#8412: each compile step of one JCL file as {step, proc, sysin, libs}: `sysin` the literal SYSIN member (or
    None), `libs` the SYSLIB DD concatenation (the DD and its unnamed continuation DDs) read as library names, a
    dataset's last qualifier (a library is the directory it is named after, as `COPY ... IN` reads it). A step whose
    SYSLIB holds a symbolic or member-qualified dataset has `libs` None: the order is unknown, never half an order.
    A compile step is `EXEC PGM=IGYCRCTL`, an `IGYW*` proc, or a call of a name in `procs` (`proc` holds that name)."""
    from gitgalaxy.core.jcl_proc import _dd_keys
    from gitgalaxy.core.job_flow import _statements

    out: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    in_syslib = False
    for _no, name, op, operands in _statements(text):
        if op == "EXEC":
            up = operands.upper().replace("PROC=", "").replace("PGM=", "")
            called = re.split(r"[,\s]", up, maxsplit=1)[0]
            ok = up.startswith(_COMPILER_PGM) or up.startswith("IGYW") or called in procs
            cur = {"step": name, "proc": called if called in procs else "", "sysin": None, "libs": []} if ok else None
            if cur is not None:
                out.append(cur)
            in_syslib = False
        elif op == "DD" and cur is not None:
            dd = name.rpartition(".")[2]
            if not name and in_syslib:
                pass
            elif dd == "SYSLIB":
                in_syslib = True
            else:
                in_syslib = False
            keys = _dd_keys(operands)
            dsn = (keys.get("DSN") or keys.get("DSNAME") or "").upper()
            if dd == "SYSIN":
                m = _SYSIN_MEMBER.search(dsn)
                cur["sysin"] = m.group(1) if m else None
            elif in_syslib and dsn and cur["libs"] is not None:
                last = dsn.split("(")[0].rpartition(".")[2]
                if "&" in dsn or "(" in dsn or not last:
                    cur["libs"] = None
                elif last not in cur["libs"]:
                    cur["libs"].append(last)
    return out


def _jcl_compiles(text: str) -> list[tuple[str, list[str]]]:
    """#8412: each compile step of one JCL file as (program, [library name, ...]). A step whose SYSIN member is not
    literal (`&MEMBER`, in-stream), or whose SYSLIB is unreadable or absent, declares nothing."""
    return [(s["sysin"], s["libs"]) for s in _compile_steps(text) if s["sysin"] and s["libs"]]


def _jcllib_order(text: str) -> list[str]:
    """#8412: the libraries a job's `JCLLIB ORDER=(a.b.PROCLIB,...)` names, as last qualifiers, in order."""
    from gitgalaxy.core.job_flow import _statements

    for _no, _name, op, operands in _statements(text):
        if op == "JCLLIB":
            m = re.search(r"ORDER=\(?([^)]*)\)?", operands, re.I)
            raw = m.group(1) if m else ""
            return [x.strip().upper().rpartition(".")[2] for x in raw.split(",") if x.strip()]
    return []


def jcl_syslib_orders(root: str) -> dict[str, list[str]]:
    """#8412: PROGRAM -> the library names its compile JCL's SYSLIB concatenation lists, in order, over every
    `.jcl` / `.prc` / `.proc` under `root`. A compile step may call a cataloged proc (`EXEC MYCOB`): the job's
    `JCLLIB ORDER=` names the PROCLIB libraries (directories named after each dataset's last qualifier) searched
    for the member, first hit wins; the proc's compile step supplies the SYSLIB unless the call overrides it
    (`//STEP.SYSLIB DD`, which replaces the whole concatenation). A program two JCL files compile with different
    orders is ambiguous and declares nothing, never a guess. Reads nothing past `_JCL_FILE_CAP` files."""
    from gitgalaxy.core.source_text import read_source

    found: dict[str, list[str] | None] = {}
    texts: list[tuple[str, str, str]] = []  # (directory name, member stem, text)
    seen = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _JCL_PRUNE)
        for fname in sorted(files):
            if not fname.lower().endswith(_JCL_EXTS):
                continue
            seen += 1
            if seen > _JCL_FILE_CAP:
                break
            try:
                text = read_source(os.path.join(base, fname)).text
            except (OSError, ValueError):
                continue
            texts.append((os.path.basename(base).upper(), fname.rpartition(".")[0].upper(), text))

    def declare(program: str, libs: list[str]) -> None:
        key = program.upper()
        found[key] = libs if found.get(key, libs) == libs else None

    members = {(lib, stem): text for lib, stem, text in texts}
    for _lib, _stem, text in texts:
        order = _jcllib_order(text)
        # a name resolves along the JCLLIB order to the first library holding it, and only to a proc with a compile step
        resolved: dict[str, list[dict[str, Any]]] = {}
        for stem in {stem for (_d, stem) in members if any((lib, stem) in members for lib in order)}:
            first = next(lib for lib in order if (lib, stem) in members)
            steps = [x for x in _compile_steps(members[(first, stem)]) if not x["proc"]]
            if steps:
                resolved[stem] = steps
        for call in _compile_steps(text, frozenset(resolved)):
            if not call["proc"]:
                if call["sysin"] and call["libs"]:
                    declare(call["sysin"], call["libs"])
                continue
            proc_steps = resolved[call["proc"]]
            if len(proc_steps) != 1:
                continue  # which compile step a call's overrides address is not guessed
            libs = call["libs"] or proc_steps[0]["libs"]
            sysin = call["sysin"] or proc_steps[0]["sysin"]
            if call["libs"] is None or not (sysin and libs):
                continue
            declare(sysin, libs)
    return {k: v for k, v in found.items() if v}


def declared_library_dirs(root: str, importer: str, cache: dict[str, list[str]]) -> list[str]:
    """#8111 slice 6: the scan-relative copy-library directories the workspace declares for `importer`
    (`.cobolplugin/proc_grps.json` libs, `.vscode/settings.json` cpy-manager paths), nearest declaration folder
    first, in declaration order. `cache` is per folder. Unreadable declarations declare nothing."""
    from gitgalaxy.standards.language_lens import declared_dirs_in_folder

    root_abs = os.path.abspath(root)
    folder = os.path.abspath(os.path.join(root_abs, os.path.dirname(importer.replace("\\", "/"))))
    out: list[str] = []
    for _ in range(12):
        if folder not in cache:
            cache[folder] = declared_dirs_in_folder(folder)
        for d in cache[folder]:
            rel = os.path.relpath(d, root_abs).replace(os.sep, "/")
            if not rel.startswith("..") and rel not in out:
                out.append(rel)
        # #8412: a zapp.yaml is its workspace's whole declaration: an ancestor's never applies beneath it (a
        # multi-root sample names workspace folders, not directories, and would otherwise read the root's libraries)
        if os.path.isfile(os.path.join(folder, "zapp.yaml")):
            break
        parent = os.path.dirname(folder)
        if parent == folder or folder == root_abs:
            break
        folder = parent
    return out
