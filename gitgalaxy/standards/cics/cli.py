# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The cics_spec CLI (#4270, cics_command_spec.md section 7, PR 1): `python -m gitgalaxy.standards.cics ...`

    emit [--json] [KEY ...]   the entries (all, or the commands named), as a summary or as JSON (never committed)
    check                     the spec's own consistency (beyond what each dataclass checks when it is built)
    regen [--check | --out DIR]  rewrite the committed generated runtime tables (gitgalaxy/tools/cobol_to_java/
                              CicsSpec.java, tests/equivalence/cics/ggcics_spec.h); --check: exit 1 when one is
                              stale (the cics-spec ratchet, pr_gates.py --ratchets); --out: render them into DIR

Spec PR 4 committed them: DetCics.condition / resp, CicsTask.respName / abcodeFor and ggcics.c's condition enums /
condition_abcode delegate to them. Only tables are generated; every runtime's behaviour stays hand-written."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BANNER = "generated from gitgalaxy/standards/cics by `python -m gitgalaxy.standards.cics regen`; do not edit"


def _commands() -> Mapping[str, Any]:
    from gitgalaxy.standards.cics.commands import COMMANDS

    return COMMANDS


def as_json(keys: Sequence[str] = ()) -> dict[str, Any]:
    """The spec as plain data: the commands (all, or `keys`), DFHRESP and the abend codes."""
    from gitgalaxy.standards.cics import resp

    commands = _commands()
    unknown = [k for k in keys if k not in commands]
    if unknown:
        raise KeyError(f"no spec entry for {unknown}")
    return {
        "commands": {k: dataclasses.asdict(c) for k, c in commands.items() if not keys or k in keys},
        "dfhresp": dict(resp.DFHRESP),
        "aliases": dict(resp.ALIASES),
        "condition_abend": dict(resp.CONDITION_ABEND),
    }


def problems() -> list[str]:
    """What `check` reports: [] when the spec is consistent."""
    out = []
    for key, c in _commands().items():
        for name, r in [*c.refused.items(), ("(default)", c.default_refusal)]:
            if r is not None and r.register not in (None, c.register):
                out.append(f"{key} {name}: refused under {r.register}, the command is {c.register}")
        out.extend(
            f"{key}: a {g.kind} group of one option ({g.options})"
            for g in c.groups
            if g.kind != "required" and len(g.options) < 2 and not g.any_of
        )
        seen = set()
        for o in c.outcomes:
            if (o.condition, o.resp2) in seen:
                out.append(f"{key}: {o.condition} RESP2 {o.resp2} twice")
            seen.add((o.condition, o.resp2))
        if c.status == "modelled" and not any(o.condition == "NORMAL" for o in c.outcomes):
            out.append(f"{key}: modelled, but no NORMAL outcome")
    return out


# The committed generated files (spec PR 4), relative to the repository root. CicsSpec.java sits beside the
# transaction forge, which emits it next to CicsTask (package <pkg>.cics: a forge-only project has no cobolrt), and
# DetCics imports it from there; ggcics_spec.h sits beside ggcics.c, which includes it.
ROOT = Path(__file__).resolve().parents[3]
JAVA_FILE = Path("gitgalaxy/tools/cobol_to_java/CicsSpec.java")
C_FILE = Path("tests/equivalence/cics/ggcics_spec.h")
JAVA_PACKAGE = "__PACKAGE__.cics"  # the forge fills __PACKAGE__ in, as it does in CicsTask


# Each generated file is a list of sections, one per spec table. A later table (the stated facts of PR 5, the EIB
# facts) is one more renderer appended to JAVA_SECTIONS / C_SECTIONS: the file around it does not change.
def _java_resp() -> str:
    from gitgalaxy.standards.cics import resp

    names = "\n".join(f'            case {n} -> "{c}";' for n, c in sorted(resp.RESP_NAME.items()))
    numbers = "\n".join(f'            case "{c}" -> {n};' for c, n in resp.DFHRESP.items())
    return f"""    /** The condition name of a RESP value (IBM CICS TS, RESP values: DFHRESP; never an alias), null for a number
     *  DFHRESP has no name for. */
    public static String name(int resp) {{
        return switch (resp) {{
{names}
            default -> null;
        }};
    }}

    /** The condition a RESP value names; "RESP" + the number for one DFHRESP has no name for. */
    public static String condition(int resp) {{
        String name = name(resp);
        return name != null ? name : "RESP" + resp;
    }}

    /** The RESP value of a condition (an alias too: DSIDERR is FILENOTFOUND's number). */
    public static int resp(String condition) {{
        return switch (condition) {{
{numbers}
            default -> throw new IllegalArgumentException("no RESP value known for condition " + condition);
        }};
    }}
"""


def _java_abend() -> str:
    from gitgalaxy.standards.cics import resp

    abends = "\n".join(f'            case "{c}" -> "{a}";' for c, a in resp.CONDITION_ABEND.items())
    return f"""    /** The abend code of an unhandled condition (IBM's AEIx / AEYx / AEZx abend codes, the AEIA topic). */
    public static String abcodeFor(String condition) {{
        return switch (condition) {{
{abends}
            default -> throw new IllegalArgumentException("no abend code known for condition " + condition);
        }};
    }}
"""


def _c_resp() -> str:
    from gitgalaxy.standards.cics import resp

    enum = ",\n".join(f"    DFHRESP_{c} = {n}" for c, n in resp.DFHRESP.items())
    return f"""/* IBM CICS TS, RESP values (DFHRESP): the condition name -> its RESP number */
enum {{
{enum}
}};
"""


def _c_abend() -> str:
    from gitgalaxy.standards.cics import resp

    cases = "\n".join(f'    case DFHRESP_{c}: return "{a}";' for c, a in resp.CONDITION_ABEND.items())
    return f"""/* The abend code of an unhandled condition (IBM's AEIx / AEYx / AEZx abend codes, the AEIA topic); "????" for
   one the spec has none for. */
static const char *condition_abcode(int resp) {{
    switch (resp) {{
{cases}
    default: return "????";
    }}
}}
"""


JAVA_SECTIONS = [_java_resp, _java_abend]
C_SECTIONS = [_c_resp, _c_abend]


def render_java(package: str = JAVA_PACKAGE) -> str:
    """CicsSpec.java: the tables DetCics.condition / resp and CicsTask.respName / abcodeFor delegate to."""
    body = "\n".join(section() for section in JAVA_SECTIONS)
    return f"""// {BANNER}
package {package};

/** The CICS command spec's tables (gitgalaxy/standards/cics): RESP values and the default abend codes. */
public final class CicsSpec {{
    private CicsSpec() {{
    }}

{body}}}
"""


def render_c() -> str:
    """ggcics_spec.h: the DFHRESP enum (DFHRESP_<condition>) and condition_abcode, which ggcics.c includes."""
    body = "\n".join(section() for section in C_SECTIONS)
    return f"""/* {BANNER} */
#ifndef GGCICS_SPEC_H
#define GGCICS_SPEC_H

{body}
#endif
"""


def generated() -> dict[Path, str]:
    """The committed generated files (relative to the repository root) and the text the spec renders for each."""
    return {JAVA_FILE: render_java(), C_FILE: render_c()}


def stale(root: Path = ROOT) -> list[Path]:
    """The committed generated files that differ from what the spec renders: [] when none is stale."""
    return [rel for rel, text in generated().items()
            if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != text]  # fmt: skip


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gitgalaxy.standards.cics", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit", help="print the entries")
    e.add_argument("keys", nargs="*", help="command keys (default: all), e.g. 'GET CONTAINER'")
    e.add_argument("--json", action="store_true", help="the full entries as JSON")
    sub.add_parser("check", help="the spec's own consistency")
    r = sub.add_parser("regen", help="rewrite the committed generated runtime tables (or check / render them)")
    how = r.add_mutually_exclusive_group()
    how.add_argument("--check", action="store_true", help="exit 1, listing them, when a committed file is stale")
    how.add_argument("--out", type=Path, help="render CicsSpec.java and ggcics_spec.h into this directory instead")
    r.add_argument("--java-package", default=JAVA_PACKAGE, help="with --out: the generated Java class's package")
    args = ap.parse_args(argv)

    if args.cmd == "emit":
        try:
            data = as_json(args.keys)
        except KeyError as exc:
            print(exc.args[0], file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(data, indent=2, sort_keys=True))
            return 0
        for key, c in _commands().items():  # (the entries themselves: same order as data["commands"])
            if key in data["commands"]:
                print(f"{key:<18} {c.status:<9} {c.register or '-':<4} options {len(c.options):>3}  "
                      f"refused {len(c.refused):>3}  outcomes {len(c.outcomes):>2}  {c.ibm.url}")  # fmt: skip
        print(f"DFHRESP {len(data['dfhresp'])} names, {len(data['condition_abend'])} default abend codes")
        return 0
    if args.cmd == "check":
        found = problems()
        for p in found:
            print(p)
        n = len(_commands())
        print(f"cics spec: {n} commands, {'ok' if not found else f'{len(found)} problem(s)'}")
        return 1 if found else 0
    if args.check:
        found = stale()
        for rel in found:
            print(f"stale: {rel}")
        print(f"cics spec generated files: {'up to date' if not found else f'{len(found)} stale'}"
              + ("; run `python -m gitgalaxy.standards.cics regen` and commit them" if found else ""))  # fmt: skip
        return 1 if found else 0
    if args.out is None:
        for rel, text in generated().items():
            (ROOT / rel).write_text(text, encoding="utf-8")
            print(f"wrote {rel}")
        return 0
    if not re.fullmatch(r"(__PACKAGE__|[a-z_][a-z0-9_]*)(\.[a-z_][a-z0-9_]*)*", args.java_package):
        print(f"not a Java package name: {args.java_package}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "CicsSpec.java").write_text(render_java(args.java_package), encoding="utf-8")
    (args.out / "ggcics_spec.h").write_text(render_c(), encoding="utf-8")
    print(f"wrote {args.out / 'CicsSpec.java'} and {args.out / 'ggcics_spec.h'}")
    return 0
