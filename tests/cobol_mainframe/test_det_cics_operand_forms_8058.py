"""#8058: audit drift guard for the EXEC CICS operand paths in det/cics*.py.

Every call of `ref` / `field` / `read_field` (the data-area path: a COBOL data name only, #7959) and `value_text` (the
data-value path: a data name or a constant, #8057, #8066) was checked against IBM's CICS TS 6.x syntax diagrams (the
audit table is in PR #8066). This pins how many of each sit in each function, so a new or moved call site fails here
until its option is checked against IBM's type: a sender IBM declares a data-value takes `value_text`; a receiver or a
data-area sender takes the strict path. Update `AUDITED` only after reading the option's syntax page.
"""

import ast
import collections
from pathlib import Path

DET = Path(__file__).resolve().parents[2] / "gitgalaxy" / "tools" / "cobol_to_java" / "det"
STRICT = {"ref", "field", "read_field"}

# (file, function, "area" | "value") -> call sites
AUDITED = {
    ("cics.py", "_value_name", "area"): 1,
    ("cics.py", "commarea_bytes", "area"): 1,
    ("cics.py", "commarea_out", "area"): 1,
    ("cics.py", "constant", "area"): 1,
    ("cics.py", "constant_int", "area"): 1,
    ("cics.py", "field", "area"): 1,
    ("cics.py", "in_dfhcommarea", "area"): 1,
    ("cics.py", "linkage_record", "area"): 1,
    ("cics.py", "outcome", "area"): 2,
    ("cics.py", "pointer", "area"): 1,
    ("cics.py", "read_field", "area"): 1,
    ("cics.py", "size", "area"): 1,
    ("cics.py", "value_text", "area"): 1,
    ("cics_conditions.py", "assign", "area"): 2,
    ("cics_containers.py", "channel_command", "area"): 1,
    ("cics_containers.py", "container", "area"): 4,
    ("cics_containers.py", "container_browse", "area"): 2,
    ("cics_counters.py", "_cint", "area"): 1,
    ("cics_counters.py", "_clong", "area"): 1,
    ("cics_counters.py", "_cstore", "area"): 2,
    ("cics_filecontrol.py", "delete_generic", "area"): 1,
    ("cics_filecontrol.py", "file_update", "area"): 3,
    ("cics_filecontrol.py", "rba_browse", "area"): 2,
    ("cics_filecontrol.py", "read", "area"): 2,
    ("cics_filecontrol.py", "read_length", "area"): 1,
    ("cics_filecontrol.py", "read_set", "area"): 2,
    ("cics_filecontrol.py", "record_from", "area"): 1,
    ("cics_filecontrol.py", "token_out", "area"): 1,
    ("cics_program.py", "dispatch_program", "area"): 1,
    ("cics_queues.py", "dispatch_queues", "area"): 3,
    ("cics_queues.py", "readq_td", "area"): 2,
    ("cics_queues.py", "ts_queue", "area"): 6,
    ("cics_storage.py", "load_release", "area"): 1,
    ("cics_storage.py", "storage", "area"): 1,
    ("cics_system.py", "dispatch_system", "area"): 8,
    ("cics_system.py", "dispatch_system", "value"): 3,
    ("cics_system.py", "inquire_association", "area"): 2,
    ("cics_system.py", "inquire_urimap", "area"): 1,
    ("cics_taskcontrol.py", "converse", "area"): 4,
    ("cics_taskcontrol.py", "fetch", "area"): 4,
    ("cics_taskcontrol.py", "post", "area"): 1,
    ("cics_taskcontrol.py", "retrieve", "area"): 4,
    ("cics_taskcontrol.py", "run_transid", "area"): 1,
    ("cics_taskcontrol.py", "start", "area"): 1,
    ("cics_terminal.py", "dispatch_terminal", "area"): 3,
    ("cics_terminal.py", "map_names", "area"): 1,
    ("cics_terminal.py", "receive", "area"): 3,
    ("cics_terminal.py", "receive_map", "area"): 1,
    ("cics_terminal.py", "send_map", "area"): 1,
    ("cics_web.py", "document", "area"): 5,
    ("cics_web.py", "extract_tcpip", "area"): 1,
    ("cics_web.py", "put", "area"): 1,
    ("cics_web.py", "received", "area"): 1,
    ("cics_web.py", "store", "area"): 2,
    ("cics_web.py", "text", "area"): 3,
    ("cics_web.py", "text", "value"): 1,
    ("cics_web.py", "value", "value"): 1,
    ("cics_web.py", "web", "area"): 4,
    ("cics_web.py", "web", "value"): 2,
    ("cics_web.py", "web_forms", "value"): 1,
    ("cics_web.py", "web_parse", "area"): 4,
    ("cics_web.py", "web_parse", "value"): 1,
    ("cics_web.py", "web_request", "area"): 2,
    ("cics_web.py", "web_request", "value"): 1,
    ("cics_web.py", "web_send", "area"): 1,
}


def _sites() -> dict:
    found: collections.Counter = collections.Counter()
    for path in sorted(DET.glob("cics*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def visit(node: ast.AST, fn: str | None, name: str = path.name) -> None:
            for child in ast.iter_child_nodes(node):
                inner = child.name if isinstance(child, ast.FunctionDef) else fn
                f = child.func if isinstance(child, ast.Call) else None
                if isinstance(f, ast.Attribute) and (f.attr in STRICT or f.attr == "value_text"):
                    found[(name, fn, "value" if f.attr == "value_text" else "area")] += 1
                visit(child, inner)

        visit(tree, None)
    return dict(found)


def test_every_operand_call_site_is_audited_against_ibm():
    now = _sites()
    added = {k: v for k, v in now.items() if AUDITED.get(k) != v}
    gone = {k: v for k, v in AUDITED.items() if k not in now}
    assert not added and not gone, (
        "an EXEC CICS operand call site changed: check the option's IBM type (data-value -> Cics.value_text, "
        f"data-area or receiver -> ref/field/read_field, #8058), then update AUDITED. changed={added} gone={gone}"
    )


def test_data_value_sites_exist_in_the_commands_8066_fixed():
    values = {(f, fn) for (f, fn, kind) in AUDITED if kind == "value"}
    assert {"cics_web.py", "cics_system.py"} <= {f for f, _ in values}


def test_the_audit_page_lists_every_pinned_call_site():
    """#8058: docs/language_status/cics_operand_types.md carries the option-by-option audit and every pinned site."""
    page = DET.parents[3] / "docs" / "language_status" / "cics_operand_types.md"
    lines = page.read_text(encoding="utf-8").splitlines()
    by_file = {ln.split("`")[1]: ln for ln in lines if ln.startswith("- `cics") and ln.count("`") > 2}
    missing = [k for k, n in AUDITED.items() if f"`{k[1]}` ({k[2]} {n})" not in by_file.get(k[0], "")]
    assert not missing, f"add these call sites to {page.name}: {missing}"
