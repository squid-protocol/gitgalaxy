r"""estate-crucible's generated key (format `estate-crucible-key/1`, #4317) in the answer-key shape the
referee adapters read (tests/cobol_mainframe/answer_key/*.json: `programs`, `cics_resources`,
`sql_access`), so that the same adapters and score.py run on the synthetic estate unchanged.

    python tests/tools/referees/estate_key.py --crucible ../estate-crucible \
        --out <dir>/estate-crucible.answer_key.json [--facts <facts dir>/estate-crucible/key.json]

Only COBOL members with a PROGRAM-ID are carried. The estate key's layouts are per program record
(COPY-expanded), not per copybook, so they are not mapped onto the copybook `layouts` channel.
A `mainline` unit and the main-line edges (`from: null`) become the `(procedure division)`
pseudo-unit, as in the answer keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

_EDGE_VERB = {"perform": "PERFORM", "perform_thru": "PERFORM_THRU", "goto": "GO_TO", "go_to": "GO_TO"}
_PROGRAM_CALLS = ("CALL", "LINK", "XCTL")


def _occurs(raw: Any) -> tuple[Any, Any, Any]:
    if raw is None:
        return None, None, None
    if isinstance(raw, int):
        return raw, raw, None
    if isinstance(raw, dict):
        hi = raw.get("max", raw.get("times"))
        return raw.get("min", hi), hi, raw.get("depending_on")
    return None, None, None


def convert(crucible: Path) -> dict[str, Any]:
    manifest = json.loads((crucible / "key" / "manifest.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {"corpus": "estate-crucible", "ref": manifest.get("generator", {}).get("version", "")
                           if isinstance(manifest.get("generator"), dict) else str(manifest.get("generator", "")),
                           "programs": {}, "cics_resources": {}, "sql_access": {}}  # fmt: skip
    for app in sorted((crucible / "key" / "apps").glob("*.json")):
        for rel, m in json.loads(app.read_text(encoding="utf-8"))["members"].items():
            if m.get("language") != "cobol" or not m.get("programs"):
                continue
            units = []
            main_edges = []
            by_unit: dict[str, list[dict[str, Any]]] = {}
            for e in m.get("edges", []):
                if e.get("kind") not in _EDGE_VERB:
                    continue
                edge = {"verb": _EDGE_VERB[e["kind"]], "target": e["target"], "line": e.get("line")}
                (main_edges if not e.get("from") else by_unit.setdefault(e["from"], [])).append(edge)
            main_span: dict[str, Any] = {"line": None, "end": None}
            for u in m.get("units", []):
                if u.get("kind") == "mainline" or not u.get("name"):
                    main_span = {"line": u["start_line"], "end": u["end_line"]}
                    continue
                units.append({"name": u["name"], "kind": u.get("kind", "paragraph"), "line": u["start_line"],
                              "end": u["end_line"], "edges": by_unit.get(u["name"], [])})  # fmt: skip
            progs = sorted(m["programs"], key=lambda p: p.get("line") or 0)
            starts = [p.get("line") or 0 for p in progs]
            ends = [nxt - 1 for nxt in starts[1:]] + [10**9]
            sibling_units: dict[str, list[dict[str, Any]]] = {p["program_id"]: [] for p in progs[1:]}
            first_units = []
            for u in units:  # a second program's units go to its own block (#4206 naming)
                owner = next(
                    (
                        p["program_id"]
                        for p, s, e in zip(progs[1:], starts[1:], ends[1:], strict=False)
                        if s <= u["line"] <= e
                    ),
                    None,
                )  # reason: length may differ
                (sibling_units[owner] if owner else first_units).append(u)
            units = first_units
            records = []
            for d in m.get("data_items", []):
                lo, hi, dep = _occurs(d.get("occurs"))
                records.append({"line": d["line"], "level": d["level"], "name": d.get("name") or "FILLER",
                                "pic": d.get("pic"), "usage": d.get("usage"), "occurs_min": lo, "occurs_max": hi,
                                "occurs_depending_on": dep, "redefines": d.get("redefines"), "value": d.get("value")})  # fmt: skip
            out["programs"][rel] = {
                "program_id": progs[0]["program_id"],
                "siblings": {
                    p["program_id"]: {
                        "program_id": p["program_id"],
                        "units": sibling_units[p["program_id"]],
                        "line": st,
                        "end_line": en,
                    }
                    for p, st, en in zip(progs[1:], starts[1:], ends[1:], strict=False)
                },  # fmt: skip  # reason: length may differ
                "units": units,
                "main_line": {**main_span, "edges": main_edges} if main_edges or main_span["line"] else None,
                "calls": [
                    {
                        "verb": c["verb"],
                        "form": c.get("form", "literal"),
                        "operand": c.get("operand"),
                        "target": c.get("target"),
                        "line": c.get("line"),
                    }
                    for c in m.get("call_sites", [])
                    if c.get("verb") in _PROGRAM_CALLS
                ],  # fmt: skip
                "copybooks": [{"name": c["member"]} for c in m.get("copies", [])],
                "records": records,
            }
            if m.get("cics_resources"):
                out["cics_resources"][rel] = {"operations": m["cics_resources"]}
            acc = sorted(
                {
                    f"{s['access']} {s['table']}"
                    for s in m.get("sql_statements", [])
                    if s.get("table") and s.get("access")
                }
            )
            if acc:
                out["sql_access"][rel] = {"accesses": acc}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crucible", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--facts", type=Path, help="also write the converted key as a referee-facts/1 `key` document")
    args = ap.parse_args()
    key = convert(args.crucible)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(key, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.facts:
        F.dump(F.key_doc(key), args.facts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
