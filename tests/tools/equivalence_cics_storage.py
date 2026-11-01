"""#5274: the storage family of the CICS harness's stub translator (equivalence_cics.translate), split out of
equivalence_cics.py: GETMAIN / FREEMAIN (#4771, #6876), LOAD / RELEASE (#6876) and ADDRESS (#5079). The family registry in
equivalence_cics calls `command`; it reaches the shared helpers through the module at call time, so the import works
either way round."""

from __future__ import annotations

import re

import equivalence_cics as ec


def _getmain(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4771 (register X47): GETMAIN SET(ptr) FLENGTH / LENGTH [INITIMG(area)] -> GGCGETM (length in GG-NUM, GG-FLAGS SHORT for the
    LENGTH form; the stub sets the pointer, to zero under LENGERR). The option rules as the det translator's."""
    key = "GETMAIN"
    ec._check_spec(key, opts, ("GETMAIN",), lambda bad: [f"{key} {o}" for o in bad])
    if not opts.get("SET"):
        raise ec.Unsupported(ec._rule(key, "required", "SET"), [key])
    if ("FLENGTH" in opts) == ("LENGTH" in opts):
        raise ec.Unsupported(ec._rule(key, "one_of", "FLENGTH"), [key])
    if "USERDATAKEY" in opts and "CICSDATAKEY" in opts:
        raise ec.Unsupported(ec._rule(key, "at_most_one", "USERDATAKEY"), [key])
    form = "FLENGTH" if "FLENGTH" in opts else "LENGTH"
    if not opts.get(form):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    img = opts.get("INITIMG")
    if img is not None and (ec._literal(img) is not None or re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", img) is None):
        raise ec.Unsupported("GETMAIN INITIMG as a literal: a data area is the COBOL form", [key])
    lines = [
        f"MOVE {opts[form]} TO GG-NUM",
        "MOVE 'SHORT' TO GG-FLAGS" if form == "LENGTH" else "MOVE SPACES TO GG-FLAGS",
    ]
    # #6876: no INITIMG: IBM gives the storage no contents; the stub answers LENGERR or refuses (image length 0)
    if img is None:
        args = [f"BY REFERENCE {ec._pointer(key, opts['SET'])}", "BY REFERENCE GG-FLAGS", "BY VALUE 0"]
    else:
        img = img.strip()
        args = [f"BY REFERENCE {ec._pointer(key, opts['SET'])}", f"BY REFERENCE {img}", f"BY VALUE LENGTH OF {img}"]
    return lines + ec._call("GGCGETM", args) + ec._resp(opts, True, labels)


def _load(opts: dict[str, str | None], program: list[str]) -> list[str]:
    """#6876 (register X65): LOAD PROGRAM(name) [SET(ptr)] [LENGTH(halfword)] -> GGCLDPG (GG-FLAGS names the options given; the stub
    sets the pointer to a non-null image and LENGTH to its length, PGMIDERR for a program the CSD does not define). HOLD, ENTRY and
    FLENGTH are not modelled by the stub."""
    key = "LOAD"
    ec._check_spec(key, opts, ("LOAD",), lambda bad: [f"{key} {o}" for o in bad])
    for o in ("HOLD", "ENTRY", "FLENGTH"):
        if o in opts:
            raise ec._stub_only(f"LOAD {o}")
    if not opts.get("PROGRAM"):
        raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    flags = [o for o in ("SET", "LENGTH") if o in opts]
    for o in flags:
        if not opts[o]:
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, [key])
    ptr = f"BY REFERENCE {ec._pointer(key, opts['SET'])}" if "SET" in opts else "BY REFERENCE GG-FLAGS"
    length = f"BY REFERENCE {opts['LENGTH']}" if "LENGTH" in opts else "BY REFERENCE GG-FLAGS"
    mark = f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS"
    return [*program, mark, *ec._call("GGCLDPG", [ptr, length])]


def _address(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#5079 (register X59): ADDRESS EIB(ptr) / COMMAREA(ptr) / CWA(ptr) / TWA(ptr) / TCTUA(ptr) -> GGCADDR, which sets the pointer to the address of the EIB /
    the program's DFHCOMMAREA (NORMAL: the command has no condition). A task with no COMMAREA (EIBCALEN 0) is refused by the
    stub: IBM's X'FF000000' is no COBOL NULL, and a LINKAGE item that was not passed is no area to name, so the area given
    then is the pointer itself. The option rules as the det translator's."""
    key = "ADDRESS"
    ec._check_spec(key, opts, ("ADDRESS",), lambda bad: [f"{key} {o}" for o in bad])
    if not any(opts.get(o) for o in ("EIB", "COMMAREA", "CWA", "TWA", "TCTUA")):
        raise ec.Unsupported("ADDRESS without EIB, COMMAREA, CWA, TWA or TCTUA: the pointer to set", [key])
    lines: list[str] = []
    if opts.get("EIB"):
        lines += ["MOVE SPACES TO GG-FLAGS"]
        lines += ec._call("GGCADDR", [f"BY REFERENCE {ec._pointer(key, opts['EIB'])}", "BY REFERENCE DFHEIBLK"])
    if opts.get("COMMAREA"):
        ptr = ec._pointer(key, opts["COMMAREA"])
        lines += ["MOVE EIBCALEN TO GG-NUM", "MOVE 'COMMAREA' TO GG-FLAGS", "IF EIBCALEN = 0"]
        lines += [f"    {ln}" for ln in ec._call("GGCADDR", [f"BY REFERENCE {ptr}", f"BY REFERENCE {ptr}"])]
        lines += ["ELSE"]
        lines += [f"    {ln}" for ln in ec._call("GGCADDR", [f"BY REFERENCE {ptr}", "BY REFERENCE DFHCOMMAREA"])]
        lines += ["END-IF"]
    # #5079 slice 2b: GGCADDR names the system area in GG-FLAGS (the port's addressCwa / addressTwa / addressTctua)
    for area in ("CWA", "TWA", "TCTUA"):
        if opts.get(area):
            lines += [f"MOVE '{area}' TO GG-FLAGS"]
            lines += ec._call(
                "GGCADDR",
                [f"BY REFERENCE {ec._pointer(key, opts[area])}", f"BY REFERENCE {ec._pointer(key, opts[area])}"],
            )
    return lines + ec._resp(opts, False, labels)


def _freemain(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4771 (register X47): FREEMAIN DATAPOINTER(ptr) -> GGCFREM, DATA(record) -> GGCFRED (#6876); INVREQ RESP2 1 for an address GETMAIN did not return."""
    key = "FREEMAIN"
    ec._check_spec(key, opts, ("FREEMAIN",), lambda bad: [f"{key} {o}" for o in bad])
    if opts.get("DATA") and opts.get("DATAPOINTER"):
        raise ec.Unsupported(ec._rule(key, "at_most_one", "DATAPOINTER"), [key])
    if opts.get("DATA"):  # #6876: the 01 LINKAGE record's address is the storage; GnuCOBOL passes it BY REFERENCE
        if re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", opts["DATA"]) is None:
            raise ec.Unsupported("FREEMAIN DATA: a data area is the COBOL form", [key])
        return ec._call("GGCFRED", [f"BY REFERENCE {opts['DATA'].strip()}"]) + ec._resp(opts, True, labels)
    if not opts.get("DATAPOINTER"):
        raise ec.Unsupported(ec._rule(key, "one_of", "DATAPOINTER"), [key])
    return ec._call("GGCFREM", [f"BY REFERENCE {ec._pointer(key, opts['DATAPOINTER'])}"]) + ec._resp(opts, True, labels)


def command(
    verb: str,
    opts: dict[str, str | None],
    pairs: list[tuple[str, str | None]],
    labels: list[str],
    handle_aid: bool,
) -> list[str] | None:
    """The storage commands, or None for a command of another family."""
    if verb == "GETMAIN":  # #4771 (X47): task storage addressed by a pointer
        return _getmain(opts, labels)
    if verb == "FREEMAIN":
        return _freemain(opts, labels)
    if verb == "LOAD":  # #6876 (X65): a program loaded by this task, addressed by a pointer
        return _load(opts, [ec._name(opts.get("PROGRAM"), "GG-NAME1")]) + ec._resp(opts, True, labels)
    if verb == "RELEASE":
        ec._check_spec("RELEASE", opts, (verb,), lambda bad: [f"RELEASE {o}" for o in bad])
        if not opts.get("PROGRAM"):
            raise ec.Unsupported(ec.NEEDS_ARGUMENT, ["RELEASE"])
        return [ec._name(opts["PROGRAM"], "GG-NAME1")] + ec._call("GGCRLPG", []) + ec._resp(opts, True, labels)
    if verb == "ADDRESS":  # #5079 (X59): a pointer to the EIB / the COMMAREA
        return _address(opts, labels)
    return None
