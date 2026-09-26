# ==============================================================================
# GitGalaxy Tool: the migration worklist (#3651)
#
# PURPOSE:
# The generators refuse to guess: where a fact is missing or two facts disagree
# they leave a TODO in the Java. This rolls every TODO of a generated project
# into one plan -- migration_worklist.json + .md -- by category and by COBOL
# source, each item with where it sits (file:line, symbol), the fact it rests on
# (from traceability.json, #3650) and a suggested resolution.
#
# Two sources, joined per Java file:
#   - the project itself: every `TODO` comment in the Java, resources and build
#     files (a javadoc TODO keeps its wrapped
#     continuation lines) -- the ground truth of what is open, with its line;
#   - the manifest: the TODOs the skeleton forges recorded, with their symbol
#     and facts. A manifest TODO claims the first Java TODO in its file with the
#     same text; one with no Java twin (a per-statement note, or one past a class
#     comment's cut-off) is kept with its symbol. Every unclaimed Java TODO is an
#     item too, except a category's declared class summary (the DB2 repository's
#     one "this SQL is DB2's" line) in a file whose manifest items itemise it.
#
# Each category has a NATURE, the effort class a pilot plans with:
#   conflict  two facts disagree: a person decides which one the Java follows;
#   fact-gap  a fact is missing: supply it (a copybook, a key, a JCL step);
#   review    the Java runs as generated: check it on the target;
#   port      business logic to write (the paragraphs the skeleton cites).
# No hours are invented; the counts per nature are the estimate's inputs.
# ==============================================================================
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

WORKLIST_VERSION = 1
NATURES = ("conflict", "fact-gap", "review", "port")


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    nature: str
    phrases: tuple[str, ...]  # a TODO whose text contains any of these is in this category
    resolution: str
    # a once-per-class Java TODO restating the category's per-item manifest TODOs (not counted again)
    class_summary: tuple[str, ...] = ()


CATEGORIES = (
    Category("commarea-mismatch", "COMMAREA layout mismatches", "conflict",
             ("this site passes", "callers also pass", "disagrees with this program's declared"),
             "For each caller, confirm which layout the callee reads (the COBOL MOVEs into DFHCOMMAREA say); "
             "map that caller's record onto the DTO, or give the callee one DTO per entry."),
    Category("record-variant", "Programs reading another record layout", "conflict",
             ("this program uses",),
             "Map the program's record onto the entity's fields (or split the entity); "
             "the two layouts' sizes are in the TODO."),
    Category("missing-layout", "Unresolved layouts", "fact-gap",
             ("no COMMAREA layout", "the layout of", "COPY members not found", "was not found in the DATA DIVISION",
              "has no known width", "no single BMS source defines"),
             "Add the missing copybook or record to the repository and re-run; the DTO then gets its real fields."),
    Category("vsam-key", "Keys that are not one field", "fact-gap",
             ("the key (offset", "no key is known", "STARTBR / READNEXT", "alternate index", "start from a key",
              "reads through path"),
             "Name the key: split the record so the key is one field, or keep the String vsamKey in step with "
             "the record; for a browse, add a range query over the key."),
    Category("queue-name", "Data-driven queue names", "fact-gap",
             ("the queue name is data-driven", "is an installation symbol"),
             "Resolve the name (the MOVEs into the operand, or the installation's symbol table) and pass it: "
             "the port takes any queue name."),
    Category("batch-utility", "Utility job steps to port", "port",
             ("a utility step to port",),
             "Replace the utility with its Spring Batch equivalent (SORT -> a sorting step, IDCAMS REPRO -> a copy, "
             "a TSO / IMS runner -> the program's runBatch), reading its control statements in SYSIN."),
    Category("open-mode", "DDs without an OPEN mode", "fact-gap",
             ("no OPEN mode",),
             "Add the JCL step that runs the program (or state the mode); the access methods are generated from it."),
    Category("unchecked-resp", "CICS responses the COBOL never tests", "review",
             ("the RESP of",),
             "Decide what a failed call does: the COBOL ignores it, so the Java throws; catch it where the old "
             "behaviour (carry on) is really wanted."),
    Category("db2-positioned", "Positioned SQL (WHERE CURRENT OF)", "review",
             ("a positioned statement",),
             "Rewrite the UPDATE / DELETE to the row's key: JDBC keeps no cursor position here."),
    Category("db2-dialect", "DB2 SQL on another database", "review",
             ("this SQL is DB2's", "DB2 SQL on"),
             "Run each statement on the target database; DB2-only syntax (FETCH FIRST, WITH UR, special "
             "registers) needs its equivalent.", class_summary=("this SQL is DB2's",)),
    Category("transaction-split", "Unit-of-work boundaries to split", "port",
             ("split the transaction here",),
             "End the transaction at the SYNCPOINT the comment cites: a nested REQUIRES_NEW call, or two service "
             "methods."),
    Category("interface-call", "Calls to other services", "port",
             ("Implement or mock interface call", "submits a job through the internal reader", "submits job"),
             "Wire the called service (or a mock) in place of the placeholder."),
    Category("business-logic", "Business logic to port", "port",
             ("implement from the program's business rules", "Implement extracted business rules", "port paragraph",
              "port the logic that fills", "port the logic that reads", "port the logic that handles the MQ request",
              "port the PROCEDURE DIVISION main line",
              "build the response"),
             "Port the cited paragraphs; the skeleton names the COBOL lines and the facts they touch."),
    Category("configuration", "Target configuration", "review",
             ("Update these credentials",),
             "Point the datasource at the target database; the password comes from SPRING_DATASOURCE_PASSWORD "
             "at run time, never from a file."),
)  # fmt: skip
UNCATEGORISED = Category("uncategorised", "Other TODOs", "review", (), "Read the TODO; it has no category yet.")

_TODO = re.compile(r"\bTODO\b:?\s*(.*)")
_AI_TAG = re.compile(r"^(?:\[AI AGENT\]|AI AGENT\s*-)\s*")
_PROGRAM_ROLES = ("Service", "Controller")
_PROGRAM_SUFFIXES = (".cbl", ".cob", ".cobol", ".ccp", ".sqb", ".pco", ".pli", ".pl1", ".asm", ".hlasm")


def classify(text: str) -> Category:
    return next((c for c in CATEGORIES if any(p in text for p in c.phrases)), UNCATEGORISED)


def normalize(text: str) -> str:
    """A TODO's text without its `TODO:` / agent tag, comment closers and extra spaces."""
    m = _TODO.search(text)
    text = m.group(1) if m else text
    text = _AI_TAG.sub("", text.strip())
    text = re.sub(r"\*/\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip().rstrip(".")


def _same(a: str, b: str) -> bool:
    n = min(len(a), len(b), 60)
    return n >= 12 and a[:n] == b[:n]


_SCANNED = (".java", ".yml", ".yaml", ".properties", ".xml", ".gradle", ".kts")


def _project_files(java_dir: Path) -> list[Path]:
    """The generated sources, resources and build files (not the reports or the agent tickets)."""
    top = [p for p in java_dir.iterdir() if p.is_file() and p.suffix in _SCANNED]
    return sorted(top + [p for p in (java_dir / "src").rglob("*") if p.is_file() and p.suffix in _SCANNED])


def java_todos(java_dir: Path) -> list[dict]:
    """Every TODO comment in the generated project: file (project-relative), line, text."""
    out = []
    for path in _project_files(java_dir) if (java_dir / "src").is_dir() else []:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rel = path.relative_to(java_dir).as_posix()
        for i, line in enumerate(lines):
            if "TODO" not in line or not _TODO.search(line):
                continue
            text = _TODO.search(line).group(1)  # type: ignore[union-attr]
            if line.lstrip().startswith(("*", "/**")) and "*/" not in line:  # a javadoc TODO: its wrapped rest
                for nxt in lines[i + 1 : i + 6]:
                    body = nxt.strip()
                    if not body.startswith("*") or body in ("*", "*/") or "TODO" in body:
                        break
                    text += " " + body.lstrip("*").strip()
                    if "*/" in body:
                        break
            out.append({"file": rel, "line": i + 1, "text": normalize(text)})
    return out


def _program(facts: list[dict]) -> str | None:
    sources = [f.get("source", "").split(":")[0] for f in facts if f.get("source")]
    programs = [s for s in sources if s.lower().endswith(_PROGRAM_SUFFIXES)]
    ranked = Counter(programs or sources).most_common(1)
    return ranked[0][0] if ranked else None


def _owner(file: str, owners: dict[str, str]) -> str | None:
    """The COBOL file a program's Service or Controller was generated from."""
    cls = file.rsplit("/", 1)[-1].removesuffix(".java")
    base = next((cls[: -len(r)] for r in _PROGRAM_ROLES if cls.endswith(r)), None)
    return owners.get(base) if base else None


def build_worklist(
    java_dir: Path, manifest: dict | None, generated_from: dict | None = None, owners: dict[str, str] | None = None
) -> dict:
    """The worklist of a generated project: every open TODO, categorised, with its fact.

    `owners` maps a program's Java class base to its COBOL file; an item in that program's
    Service or Controller belongs to it, whatever other programs its facts cite (a COMMAREA
    mismatch cites the callers)."""
    in_java = java_todos(java_dir)
    by_file: dict[str, list[dict]] = {}
    for t in in_java:
        by_file.setdefault(t["file"], []).append(t)
    claimed: set[int] = set()
    items: list[dict] = []
    file_facts: dict[str, list[dict]] = {}
    for art in (manifest or {}).get("artifacts", []):
        file_facts.setdefault(art["file"], []).extend(art.get("facts", []))
        for raw in art.get("todos", []):
            text = normalize(raw)
            twin = next(
                (t for t in by_file.get(art["file"], []) if id(t) not in claimed and _same(t["text"], text)), None
            )
            if twin is not None:
                claimed.add(id(twin))
            items.append({"file": art["file"], "line": twin["line"] if twin else None, "symbol": art["symbol"],
                          "text": text, "facts": art.get("facts", [])})  # fmt: skip
    itemised = {(i["file"], classify(i["text"]).id) for i in items}
    for t in in_java:
        cat = classify(t["text"])
        summary = any(p in t["text"] for p in cat.class_summary) and (t["file"], cat.id) in itemised
        if id(t) in claimed or summary:
            continue
        items.append({"file": t["file"], "line": t["line"], "symbol": None, "text": t["text"], "facts": []})

    # a manifest TODO with no Java line of its own, whose text a claimed Java TODO in its file already
    # says (a controller's one COMMAREA note, recorded on each endpoint), is that item for one more symbol
    for it in items:
        it["symbols"] = [it.pop("symbol")] if it["symbol"] else []
    lined = {(i["file"], i["text"]): i for i in items if i["line"] is not None}
    kept = []
    for it in items:
        twin = lined.get((it["file"], it["text"])) if it["line"] is None else None
        if twin is None:
            kept.append(it)
            continue
        twin["symbols"] += [s for s in it["symbols"] if s not in twin["symbols"]]
        twin["facts"] = twin["facts"] + [f for f in it["facts"] if f not in twin["facts"]]
    items = kept

    order = {c.id: n for n, c in enumerate((*CATEGORIES, UNCATEGORISED))}
    for it in items:
        cat = classify(it["text"])
        it["category"], it["nature"] = cat.id, cat.nature
        it["program"] = (
            _owner(it["file"], owners or {})
            or _program(it["facts"])
            or _program(file_facts.get(it["file"], []))
            or ("(no program source cited)" if it["file"].endswith(".java") else "(project configuration)")
        )
    items.sort(
        key=lambda i: (
            order[i["category"]],
            i["program"],
            i["file"],
            i["line"] is None,
            i["line"] or 0,
            i["symbols"],
            i["text"],
        )
    )
    for n, it in enumerate(items, 1):
        it["id"] = f"WL-{n:04d}"
    items = [{k: it[k] for k in ("id", "category", "nature", "program", "file", "line", "symbols", "text", "facts")}
             for it in items]  # fmt: skip

    categories = Counter(i["category"] for i in items)
    return {
        "version": WORKLIST_VERSION,
        "generated_from": generated_from or {},
        "summary": {
            "items": len(items),
            "by_nature": {n: sum(1 for i in items if i["nature"] == n) for n in NATURES},
            "by_category": {c.id: categories[c.id] for c in (*CATEGORIES, UNCATEGORISED) if categories[c.id]},
            "programs": len({i["program"] for i in items if not i["program"].startswith("(")}),
        },
        "categories": {
            c.id: {"title": c.title, "nature": c.nature, "resolution": c.resolution}
            for c in (*CATEGORIES, UNCATEGORISED)
            if categories[c.id]
        },
        "items": items,
    }


def _where(it: dict) -> str:
    loc = f"{it['file']}:{it['line']}" if it["line"] else it["file"]
    return f"`{loc}`" + (" (" + ", ".join(f"`{s}`" for s in it["symbols"]) + ")" if it["symbols"] else "")


def render_markdown(wl: dict) -> str:
    s = wl["summary"]
    md = ["# Migration worklist", "",
          ("Every TODO the generators left in this project: where a fact was missing or two facts disagreed, "
           "the Java says so instead of guessing. Each item names the fact it rests on (from "
           "`traceability.json`) and a suggested resolution."), "",
          f"**{s['items']} items** across {s['programs']} program sources (COBOL, PL/I).", "",
          "| nature | items | what it takes |", "|---|---:|---|"]  # fmt: skip
    what = {"conflict": "two facts disagree: a person decides which one the Java follows",
            "fact-gap": "a fact is missing: supply it and re-run",
            "review": "the Java runs as generated: check it on the target",
            "port": "business logic to write"}  # fmt: skip
    md += [f"| {n} | {s['by_nature'][n]} | {what[n]} |" for n in NATURES]
    md += ["", "## By category", "", "| category | nature | items | suggested resolution |", "|---|---|---:|---|"]
    md += [f"| [{c['title']}](#{cid}) | {c['nature']} | {s['by_category'][cid]} | {c['resolution']} |"
           for cid, c in wl["categories"].items()]  # fmt: skip

    programs: dict[str, Counter] = {}
    for it in wl["items"]:
        programs.setdefault(it["program"], Counter())[it["nature"]] += 1
    md += ["", "## By program source", "", "| source | " + " | ".join(NATURES) + " | total |",
           "|---|" + "---:|" * (len(NATURES) + 1)]  # fmt: skip
    for prog, cnt in sorted(programs.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        md.append(f"| `{prog}` | " + " | ".join(str(cnt[n] or "") for n in NATURES) + f" | {sum(cnt.values())} |")

    for cid, c in wl["categories"].items():
        md += ["", f'<a id="{cid}"></a>', f"## {c['title']} ({c['nature']})", "", f"_Resolution:_ {c['resolution']}"]
        current: str | None = None
        for it in (i for i in wl["items"] if i["category"] == cid):
            if it["program"] != current:
                current = it["program"]
                md += ["", f"**`{current}`**", ""]
            md.append(f"- [ ] **{it['id']}** {_where(it)}: {it['text']}")
            for f in it["facts"][:3]:
                status = f" ({f['field_testing']})" if f.get("field_testing") else ""
                md.append(f"  - fact: `{f.get('source') or '?'}`, {f.get('ledger_field') or 'no ledger field'}{status}")
    return "\n".join(md) + "\n"


def write_worklist(
    java_dir: Path, manifest: dict | None, generated_from: dict | None = None, owners: dict[str, str] | None = None
) -> dict:
    wl = build_worklist(java_dir, manifest, generated_from, owners)
    (java_dir / "migration_worklist.json").write_text(json.dumps(wl, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (java_dir / "migration_worklist.md").write_text(render_markdown(wl), encoding="utf-8")
    return wl
