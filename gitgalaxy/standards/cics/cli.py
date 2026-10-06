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
    regen --out DIR           render the generated runtime tables (CicsSpec.java, ggcics_spec.h) into DIR

PR 1 commits no generated file: PR 4 commits them beside the runtimes, delegates the hand-written switches to
them and adds the drift test."""

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


def render_java(package: str) -> str:
    """CicsSpec.java: the RESP / abend switches DetCics.condition / resp, CicsTask.respName / abcodeFor delegate to
    (from PR 4)."""
    from gitgalaxy.standards.cics import resp

    def cases(pairs: list[tuple[str, str]]) -> str:
        return "\n".join(f"            case {k} -> {v};" for k, v in pairs)

    names = cases([(str(n), f'"{c}"') for n, c in sorted(resp.RESP_NAME.items())])
    numbers = cases([(f'"{c}"', str(n)) for c, n in resp.DFHRESP.items()])
    abends = cases([(f'"{c}"', f'"{a}"') for c, a in resp.CONDITION_ABEND.items()])
    return f"""// {BANNER}
package {package};

/** The CICS command spec's tables (IBM CICS TS, RESP values; the AEIx / AEYx / AEZx abend codes). */
public final class CicsSpec {{
    private CicsSpec() {{
    }}

    /** The condition a RESP value names; "RESP" + the number for one DFHRESP has no name for. */
    public static String condition(int resp) {{
        return switch (resp) {{
{names}
            default -> "RESP" + resp;
        }};
    }}

    /** The RESP value of a condition. */
    public static int resp(String condition) {{
        return switch (condition) {{
{numbers}
            default -> throw new IllegalArgumentException("no RESP value known for condition " + condition);
        }};
    }}

    /** The abend code of an unhandled condition. */
    public static String abcodeFor(String condition) {{
        return switch (condition) {{
{abends}
            default -> throw new IllegalArgumentException("no abend code known for condition " + condition);
        }};
    }}
}}
"""


def render_c() -> str:
    """ggcics_spec.h: the DFHRESP enum and condition_abcode for the stub (from PR 4)."""
    from gitgalaxy.standards.cics import resp

    enum = ",\n".join(f"    DFHRESP_{c} = {n}" for c, n in resp.DFHRESP.items())
    cases = "\n".join(f'    case DFHRESP_{c}: return "{a}";' for c, a in resp.CONDITION_ABEND.items())
    return f"""/* {BANNER} */
#ifndef GGCICS_SPEC_H
#define GGCICS_SPEC_H

enum {{
{enum}
}};

/* The abend code of an unhandled condition; "????" for one the spec has none for. */
static const char *condition_abcode(int resp) {{
    switch (resp) {{
{cases}
    default: return "????";
    }}
}}

#endif
"""


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gitgalaxy.standards.cics", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit", help="print the entries")
    e.add_argument("keys", nargs="*", help="command keys (default: all), e.g. 'GET CONTAINER'")
    e.add_argument("--json", action="store_true", help="the full entries as JSON")
    sub.add_parser("check", help="the spec's own consistency")
    r = sub.add_parser("regen", help="render the generated runtime tables into a directory")
    r.add_argument("--out", type=Path, required=True, help="where to write CicsSpec.java and ggcics_spec.h")
    r.add_argument("--java-package", default="cobolrt.cics", help="the generated Java class's package")
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
        for key, c in data["commands"].items():
            print(f"{key:<18} {c['status']:<9} {c['register'] or '-':<4} options {len(c['options']):>3}  "
                  f"refused {len(c['refused']):>3}  outcomes {len(c['outcomes']):>2}  {c['ibm']['url']}")  # fmt: skip
        print(f"DFHRESP {len(data['dfhresp'])} names, {len(data['condition_abend'])} default abend codes")
        return 0
    if args.cmd == "check":
        found = problems()
        for p in found:
            print(p)
        n = len(_commands())
        print(f"cics spec: {n} commands, {'ok' if not found else f'{len(found)} problem(s)'}")
        return 1 if found else 0
    if not re.fullmatch(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*", args.java_package):
        print(f"not a Java package name: {args.java_package}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "CicsSpec.java").write_text(render_java(args.java_package), encoding="utf-8")
    (args.out / "ggcics_spec.h").write_text(render_c(), encoding="utf-8")
    print(f"wrote {args.out / 'CicsSpec.java'} and {args.out / 'ggcics_spec.h'}")
    return 0
