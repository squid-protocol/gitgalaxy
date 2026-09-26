# ==============================================================================
# GitGalaxy Tool: the AI-agent guardrail (#3652)
#
# PURPOSE:
# The agent tickets carry the verified skeleton and tell the agent not to invent
# calls or resources. This checks that it didn't. At generation the controller
# writes guardrail_baseline.json, an inventory of the generated project -- every
# class with its fields, methods and endpoints, the services / repositories /
# clients each one calls, and the SQL tables the project's own SQL names. After
# an agent (or a person) edits the project, or returns a ticket's `java_code`,
# the check compares the changed code against that inventory and reports:
#
#   unknown-call     a changed class calls a service, repository or client its
#                    generated code never called (the COBOL program does not), or
#                    one that does not exist in the project at all;
#   new-component    a new service / repository / controller / client / DTO /
#                    entity class: a program, file or transaction the skeleton
#                    does not contain;
#   layout-changed   a field added to or dropped from a generated DTO, entity or
#                    row class: a COMMAREA / container / record field outside the
#                    verified layout;
#   unknown-table    SQL naming a table the project's own SQL never uses;
#   new-endpoint     a controller entry point the skeleton does not define.
#
# Violations exit 1. Notices (a new helper class, a deleted file) do not. The
# report goes to agent_guardrail.json / .md, into the audit as section [4], and,
# for a ticket result, into that result's JSON as `guardrail`.
#
#   python -m gitgalaxy.tools.cobol_to_java.cobol_to_java_guardrail <java project>
#          [--result TICKET.json RESULT.json ...]
#
# Java is read with a small scanner (comments and string literals set aside,
# braces counted), not a parser: it sees what generated and agent code declare
# at class level, which is what the rules need.
# ==============================================================================
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

BASELINE_FILE = "guardrail_baseline.json"
BASELINE_VERSION = 1
AUDIT_HEAD = "[4] AI AGENT GUARDRAIL"

_CALL_SUFFIXES = ("Service", "Repository", "Client")
_COMPONENT_SUFFIXES = (*_CALL_SUFFIXES, "Controller", "Commarea", "Row", "Entity", "Dto")
_KINDS = (("/dto/", "data"), ("/entity/", "data"), ("/controller/", "controller"), ("/service/", "service"),
          ("/repository/", "repository"), ("/client/", "client"))  # fmt: skip
_REF = re.compile(r"(?<![@\w.])([A-Z][A-Za-z0-9]*(?:Service|Repository|Client))\b")
_TYPE_DECL = re.compile(r"\b(?:class|interface|record|enum)\s+([A-Z]\w*)")
_RECORD = re.compile(r"\brecord\s+([A-Z]\w*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)")
_IMPORT = re.compile(r"^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+)[ \t]*;", re.M)
_PACKAGE = re.compile(r"^[ \t]*package[ \t]+([\w.]+)[ \t]*;", re.M)
_ANNOTATION = re.compile(r"@[\w.]+(?:\s*\((?:[^()]|\([^()]*\))*\))?")
_MAPPING = re.compile(r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping\b")
_SQL_START = re.compile(r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)\b", re.I)
_SQL_TABLE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([A-Za-z_][\w.$#@]*)", re.I)


# ---- reading Java ------------------------------------------------------------
def split_java(src: str) -> tuple[str, list[str]]:
    """(code with comments and literals blanked, the string literals' contents)."""
    out, strings, i, n = [], [], 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * src.count("\n", i, j))
            i = j
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            j = n if j < 0 else j
            strings.append(src[i + 3 : j])
            out.append('""' + "\n" * src.count("\n", i, j))
            i = j + 3
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            if c == '"':
                strings.append(src[i + 1 : j])
            out.append(c + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out), strings


def _class_level(code: str) -> list[tuple[str, str]]:
    """The statements at class level (brace depth 1): (text, how it ended: ';' or '{')."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(code):
        if c == "{":
            if depth == 1:
                parts.append((code[start:i], "{"))
            depth += 1
            if depth == 1:
                start = i + 1
        elif c == "}":
            depth -= 1
            if depth == 1:
                start = i + 1
        elif c == ";" and depth == 1:
            parts.append((code[start:i], ";"))
            start = i + 1
    return parts


def _last_ident(text: str) -> str | None:
    found = re.findall(r"[A-Za-z_]\w*", text)
    return found[-1] if found else None


def read_java(src: str) -> dict:
    """What a Java file declares at class level, and what it calls and queries."""
    code, strings = split_java(src)
    fields, methods, endpoints = [], [], []
    for raw, end in _class_level(code):
        text = _ANNOTATION.sub(" ", raw)  # `@Column(name = "X") private String x;` is a field
        head = text.split("=", 1)[0]
        if end == ";" and "(" not in head and not re.search(r"\bstatic\b", head):
            name = _last_ident(head)
            if name:
                fields.append(name)
        elif end == "{" and "(" in text and not _TYPE_DECL.search(text):
            name = _last_ident(text.split("(", 1)[0])
            if name and name not in ("if", "for", "while", "switch", "catch", "synchronized"):
                methods.append(name)
                if _MAPPING.search(raw):
                    endpoints.append(name)
    for m in _RECORD.finditer(code):  # a record's components are its fields
        depth, part, comps = 0, "", []
        for ch in m.group(2) + ",":
            depth += ch == "<"
            depth -= ch == ">"
            if ch == "," and depth == 0:
                comps.append(part)
                part = ""
            else:
                part += ch
        fields += [n for n in (_last_ident(p) for p in comps if p.strip()) if n]
    tables = sorted(
        {t.upper() for s in strings if _SQL_START.match(s) for t in _SQL_TABLE.findall(s) if not t.startswith(":")}
    )
    pkg = _PACKAGE.search(code)
    return {
        "package": pkg.group(1) if pkg else "",
        "classes": _TYPE_DECL.findall(code),
        "fields": sorted(set(fields)),
        "methods": sorted(set(methods)),
        "endpoints": sorted(set(endpoints)),
        "refs": sorted(set(_REF.findall(code)) - set(_TYPE_DECL.findall(code))),  # not its own `X.class`
        "imports": sorted({i.rsplit(".", 1)[-1] for i in _IMPORT.findall(code)}),
        "tables": tables,
    }


def _kind(rel: str) -> str:
    return next((k for marker, k in _KINDS if marker in f"/{rel}"), "other")


def _project_java(java_dir: Path) -> dict[str, str]:
    src = java_dir / "src"
    return {p.relative_to(java_dir).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(src.rglob("*.java"))} if src.is_dir() else {}  # fmt: skip


# ---- the baseline ------------------------------------------------------------
def build_baseline(
    java_dir: Path,
    generated_from: dict | None = None,
    extra_calls: dict[str, set[str]] | None = None,
    owners: dict[str, str] | None = None,
) -> dict:
    """The inventory an agent's changes are checked against. `extra_calls` adds call targets a
    class may use although its generated code does not yet (a program's mock services)."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_worklist import _owner

    files, tables = {}, set()
    for rel, src in _project_java(java_dir).items():
        info = read_java(src)
        own = set(info["classes"])
        calls = {r for r in info["refs"] if r not in own}
        for cls in own:
            calls |= (extra_calls or {}).get(cls, set())
        tables |= set(info["tables"])
        files[rel] = {
            "sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
            "kind": _kind(rel),
            "program": _owner(rel, owners or {}),
            "classes": info["classes"],
            "fields": info["fields"],
            "methods": info["methods"],
            "endpoints": info["endpoints"],
            "calls": sorted(calls),
        }
    return {"version": BASELINE_VERSION, "generated_from": generated_from or {}, "files": files,
            "tables": sorted(tables)}  # fmt: skip


def write_baseline(java_dir: Path, generated_from: dict | None = None,
                   extra_calls: dict[str, set[str]] | None = None, owners: dict[str, str] | None = None) -> dict:  # fmt: skip
    baseline = build_baseline(java_dir, generated_from, extra_calls, owners)
    (java_dir / BASELINE_FILE).write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return baseline


# ---- the check ---------------------------------------------------------------
def _line_of(src: str, word: str) -> int | None:
    m = re.search(rf"\b{re.escape(word)}\b", src)
    return src.count("\n", 0, m.start()) + 1 if m else None


def check(baseline: dict, current: dict[str, str]) -> dict:
    """Every violation and notice in `current` (project-relative path -> Java source) against `baseline`."""
    base = baseline["files"]
    known = {c for f in base.values() for c in f["classes"]}
    tables = set(baseline["tables"])
    violations: list[dict] = []
    notices: list[dict] = []

    def flag(rule: str, rel: str, detail: str, word: str | None = None, violation: bool = True) -> None:
        src = current.get(rel, "")
        (violations if violation else notices).append({
            "rule": rule, "file": rel, "line": _line_of(src, word) if word else None,
            "program": (base.get(rel) or {}).get("program"), "detail": detail,
        })  # fmt: skip

    changed = sorted(rel for rel, src in current.items()
                     if rel not in base or base[rel]["sha256"] != hashlib.sha256(src.encode("utf-8")).hexdigest())  # fmt: skip
    for rel in changed:
        info, was = read_java(current[rel]), base.get(rel)
        own = set(info["classes"])
        if was is None:
            for cls in info["classes"]:
                if cls in known:
                    continue
                if cls.endswith(_COMPONENT_SUFFIXES) or _kind(rel) != "other":
                    flag("new-component", rel, f"new class {cls}: the skeleton has no such program, "
                         "file, table or transaction", cls)  # fmt: skip
                else:
                    flag("new-component", rel, f"new helper class {cls}", cls, violation=False)
        allowed = set(was["calls"]) if was else set()
        for ref in info["refs"]:
            if ref in own or ref in allowed:
                continue
            if ref in known:
                flag("unknown-call", rel, f"calls {ref}, which this program's generated code never calls: "
                     "the COBOL program does not", ref)  # fmt: skip
            elif ref not in info["imports"]:  # an imported library type (ExecutorService) is not a program
                flag("unknown-call", rel, f"calls {ref}, which does not exist in the generated project", ref)
        if was is not None and was["kind"] == "data":
            for name in sorted(set(info["fields"]) - set(was["fields"])):
                flag("layout-changed", rel, f"adds field {name}, outside the verified layout", name)
            for name in sorted(set(was["fields"]) - set(info["fields"])):
                flag("layout-changed", rel, f"drops field {name} of the verified layout")
        if _kind(rel) == "controller":
            for name in sorted(set(info["endpoints"]) - set((was or {}).get("endpoints", []))):
                flag("new-endpoint", rel, f"new entry point {name}: the skeleton defines no such transaction", name)
        for t in info["tables"]:
            if t not in tables:
                flag("unknown-table", rel, f"SQL names table {t}, which the project's SQL never uses", t)
    for rel in sorted(set(base) - set(current)):
        flag("deleted", rel, "a generated file was deleted", violation=False)

    rules = sorted({v["rule"] for v in violations})
    return {
        "version": 1,
        "baseline": baseline.get("generated_from", {}),
        "changed_files": changed,
        "summary": {
            "changed_files": len(changed),
            "violations": len(violations),
            "notices": len(notices),
            "by_rule": {r: sum(1 for v in violations if v["rule"] == r) for r in rules},
        },
        "violations": violations,
        "notices": notices,
    }


def render_markdown(report: dict) -> str:
    s = report["summary"]
    md = ["# AI agent guardrail", "",
          f"{s['changed_files']} changed file(s) checked against the verified skeleton's inventory: "
          f"**{s['violations']} violation(s)**, {s['notices']} notice(s).", ""]  # fmt: skip
    for title, rows in (("Violations", report["violations"]), ("Notices", report["notices"])):
        if rows:
            md += [f"## {title}", "", "| rule | where | program | detail |", "|---|---|---|---|"]
            for v in rows:
                where = f"{v['file']}:{v['line']}" if v["line"] else v["file"]
                md.append(f"| {v['rule']} | `{where}` | {v['program'] or ''} | {v['detail']} |")
            md.append("")
    return "\n".join(md) + "\n"


def audit_section(report: dict | None, baseline: dict) -> str:
    lines = [AUDIT_HEAD, "-" * 58]
    n_classes = sum(len(f["classes"]) for f in baseline["files"].values())
    lines.append(f"  • Baseline : {len(baseline['files'])} files, {n_classes} classes, "
                 f"{len(baseline['tables'])} SQL tables -> {BASELINE_FILE}")  # fmt: skip
    if report is None:
        lines.append("  • Not run  : after agent edits, python -m gitgalaxy.tools.cobol_to_java.cobol_to_java_guardrail "
                     "<this project>")  # fmt: skip
    else:
        s = report["summary"]
        lines.append(f"  • Checked  : {s['changed_files']} changed files: {s['violations']} violations, "
                     f"{s['notices']} notices -> agent_guardrail.md")  # fmt: skip
        lines += [f"    {rule:<18} {n:>5}" for rule, n in s["by_rule"].items()]
    return "\n".join(lines) + "\n\n"


def _replace_audit_section(audit: Path, section: str) -> None:
    if not audit.is_file():
        return
    text = audit.read_text(encoding="utf-8")
    start = text.find(AUDIT_HEAD)
    if start < 0:
        end_rule = text.rfind("=" * 58)
        text = text[:end_rule] + section + text[end_rule:] if end_rule > 0 else text + section
    else:
        end = text.find("\n\n", start)
        text = text[:start] + section + text[end + 2 :]
    audit.write_text(text, encoding="utf-8")


def run(java_dir: Path, results: list[tuple[Path, Path]] | None = None) -> dict:
    """Check a project (and any ticket results) and write the report; returns it."""
    baseline = json.loads((java_dir / BASELINE_FILE).read_text(encoding="utf-8"))
    current = _project_java(java_dir)
    result_files: dict[str, Path] = {}
    for ticket_path, result_path in results or []:
        ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        cls = f"{java_class_base(ticket['target_program'])}Service"
        rel = next((r for r, f in baseline["files"].items() if cls in f["classes"]), None)
        rel = rel or next((r for r in current if r.endswith(f"/service/{cls}.java")), f"src/{cls}.java")
        current[rel] = result.get("java_code", "")
        result_files[rel] = result_path
    report = check(baseline, current)
    (java_dir / "agent_guardrail.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (java_dir / "agent_guardrail.md").write_text(render_markdown(report), encoding="utf-8")
    _replace_audit_section(java_dir / "java_migration_audit.txt", audit_section(report, baseline))
    for rel, path in result_files.items():  # the ticket result carries its own verdict
        result = json.loads(path.read_text(encoding="utf-8"))
        mine = [v for v in report["violations"] if v["file"] == rel]
        result["guardrail"] = {"status": "rejected" if mine else "passed", "violations": mine}
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check AI-agent changes to a generated project against its "
                                             "verified skeleton (#3652).")  # fmt: skip
    ap.add_argument("project", type=Path, help="the generated Java project (holds guardrail_baseline.json)")
    ap.add_argument("--result", nargs=2, action="append", type=Path, metavar=("TICKET", "RESULT"),
                    help="an agent ticket and the JSON result it returned (its java_code is checked)")  # fmt: skip
    args = ap.parse_args(argv)
    if not (args.project / BASELINE_FILE).is_file():
        print(f"[!] {args.project / BASELINE_FILE} not found: regenerate the project with cobol-to-java")
        return 2
    report = run(args.project, [tuple(r) for r in args.result or []])
    s = report["summary"]
    print(f"[guardrail] {s['changed_files']} changed files: {s['violations']} violations, {s['notices']} notices "
          f"-> {args.project / 'agent_guardrail.md'}")  # fmt: skip
    return 1 if s["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
