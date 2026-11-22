"""#8486: guard against per-service duplicated runtime shims in generated and committed *Service.java ports.

Two checks preempt future translators or ports from emitting boilerplate helpers into every *Service.java
instead of hoisting them into cobolrt (DetCics.java / Cobol.java / etc.):
1. Live `det` translator output across 3 distinct CICS programs must not emit any new shared helper method
   (>= 3 lines) identically across all 3 services.
2. Committed `*Service.java` ports (cics_crucible/det-ports and carddemo-*/port/service) have a shrink-only
   allowlist of existing >= 3-line duplicated method bodies; any new duplicate >= 3 services fails.
"""

from __future__ import annotations

import collections
import hashlib
import tempfile
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import program as det_prog
from tree_sitter_language_pack import get_parser

REPO = Path(__file__).resolve().parents[2]
PARSER = get_parser("java")

# Structural entrypoints / dispatchers that are inherently per-service in live det output.
DET_STRUCTURAL_METHODS: frozenset[str] = frozenset({
    "dd",
    "handleLink",
    "handleTransaction",
    "perform",
    "run",
    "runBatch",
    "runProgram",
})

# Existing >= 3-line duplicated methods across committed det-ports and CardDemo services. Shrink-only (#8486).
ALLOWED_COMMITTED_DUPLICATES: frozenset[tuple[str, str]] = frozenset({
    ("lastAnswerBytes", "291bad6b159e"),
    ("abended", "9833d8ca150a"),
    ("condition", "826e1b3c89b8"),
    ("cx", "efa45148d25b"),
    ("paragraph", "5ffea72b1434"),
    ("lastLinkBytes", "3e85001ff4b4"),
    ("store", "4e8376bfdc43"),
    ("caWhole", "61b6bf813053"),
    ("dd", "e672f3b81654"),
    ("store", "af604c4d3140"),
    ("perform", "67e0e367a682"),
    ("run", "cdd22096c86b"),
    ("spaces", "224d208f7ef3"),
    ("store", "1727782403ca"),
    ("p10", "1cc06dbd9698"),
    ("perform", "c2030b3f21e2"),
    ("perform", "c3262a62be95"),
    ("perform", "ef5e18d425d9"),
    ("run", "83409b52c6d3"),
    ("run", "c4c7550dff89"),
    ("run", "ca85a8776928"),
    ("browseBackTransact", "fffaf505ddb0"),
    ("browseTransact", "c9a6c21629f5"),
    ("id_AccountRecord", "05603d535870"),
    ("id_CustomerRecord", "4393bdc17343"),
    ("low", "1e42d296e7ed"),
    ("p12", "9284293c782b"),
    ("p4", "4d109ae17764"),
    ("readCxacaix", "2346fd398675"),
    ("readUsrsec", "0f454e8a5a5c"),
})

_SAMPLE_STUB = """package com.example.service;
import com.example.cics.CicsTask;
public class {cls} {{
    public void runTask(CicsTask task) {{}}
    public void handleTransaction(String transid) {{}}
    public byte[] lastAnswerBytes() {{ return null; }}
    public byte[] lastLinkBytes() {{ return null; }}
}}
"""

_SAMPLE_PROGRAMS: dict[str, str] = {
    "P1": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC X(4) VALUE "ABCD".
       01 WS-R PIC S9(8) COMP.
       PROCEDURE DIVISION.
       MAIN-1.
           EXEC CICS ASSIGN USERID(WS-A) RESP(WS-R) END-EXEC.
           EXEC CICS RETURN END-EXEC.
""",
    "P2": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-B PIC X(8) VALUE "EFGH".
       01 WS-N PIC S9(4) COMP VALUE 1.
       01 WS-R PIC S9(8) COMP.
       PROCEDURE DIVISION.
       MAIN-2.
           ADD 1 TO WS-N.
           EXEC CICS ASSIGN SYSID(WS-B) RESP(WS-R) END-EXEC.
           EXEC CICS RETURN END-EXEC.
""",
    "P3": """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P3.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-C PIC X(4) VALUE "IJKL".
       01 WS-D PIC X(4) VALUE SPACES.
       01 WS-R PIC S9(8) COMP.
       PROCEDURE DIVISION.
       MAIN-3.
           MOVE WS-C TO WS-D.
           EXEC CICS ASSIGN APPLID(WS-D) RESP(WS-R) END-EXEC.
           EXEC CICS RETURN END-EXEC.
""",
}


def _translate(td: Path, name: str):
    """The live det output for one sample, through the full task path (a project dir, a stub with runTask)."""
    p = td / f"{name}.cbl"
    p.write_text(_SAMPLE_PROGRAMS[name], encoding="utf-8")
    (td / "proj/src/main/java/com/example").mkdir(parents=True, exist_ok=True)
    stub = _SAMPLE_STUB.format(cls=f"{name}Service")
    return det_prog.translate(p, [], stub, "com.example", {}, td / "proj")


def _collect_methods(java_sources: list[tuple[str, bytes]]) -> dict[tuple[str, str], set[str]]:
    methods: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for label, src in java_sources:
        tree = PARSER.parse(src)
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "method_declaration":
                nn = node.child_by_field_name("name")
                bn = node.child_by_field_name("body")
                if nn and bn:
                    name = src[nn.start_byte:nn.end_byte].decode()
                    body = src[bn.start_byte:bn.end_byte].decode()
                    lines = [
                        line.strip()
                        for line in body.splitlines()
                        if line.strip() and not line.strip().startswith("//")
                    ]
                    if len(lines) >= 3:
                        norm = "\n".join(lines)
                        digest = hashlib.sha256(norm.encode()).hexdigest()[:12]
                        methods[(name, digest)].add(label)
            stack.extend(node.children)
    return methods


def test_det_translator_emits_no_new_duplicated_shims():
    sources: list[tuple[str, bytes]] = []
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        for name in _SAMPLE_PROGRAMS:
            res = _translate(td, name)
            sources.append((name, res.java.encode("utf-8")))
    methods = _collect_methods(sources)
    dups = sorted(
        name
        for (name, _), owners in methods.items()
        if len(owners) >= len(_SAMPLE_PROGRAMS) and name not in DET_STRUCTURAL_METHODS
    )
    if dups:
        raise AssertionError(
            "det translator emitted identical >=3-line helper(s) across all sample services; "
            "hoist them into cobolrt (DetCics.java / Cobol.java) instead (#8486): "
            + ", ".join(dups)
        )


def test_det_service_delegates_the_cobolrt_invariant_shims():
    """#8486: abended / lastAnswerBytes / lastLinkBytes are one-line delegates to DetCics, not per-service bodies."""
    with tempfile.TemporaryDirectory() as d:
        java = _translate(Path(d), "P1").java
    assert "private Goback abended() { return DetCics.abended(task, caBack, Goback::new); }" in java
    assert "return DetCics.copyBytes(lastAnswerBytes);" in java
    assert "return DetCics.copyBytes(lastLinkBytes);" in java
    assert "java.util.Arrays.copyOf(lastAnswerBytes" not in java


def test_committed_ports_no_new_duplicated_shims():
    port_paths = sorted(
        list((REPO / "tests/cics_crucible/det-ports").rglob("*Service.java"))
        + list((REPO / "tests/equivalence").glob("carddemo-*/port/service/*Service.java"))
    )
    sources = [(p.relative_to(REPO).as_posix(), p.read_bytes()) for p in port_paths]
    methods = _collect_methods(sources)
    actual = {key for key, owners in methods.items() if len(owners) >= 3}

    unexpected = sorted(actual - ALLOWED_COMMITTED_DUPLICATES)
    if unexpected:
        raise AssertionError(
            "New >=3-line duplicated helper method(s) found in >=3 committed *Service.java ports; "
            "hoist them into cobolrt instead (#8486):\n"
            + "\n".join(f"  - {name} ({digest})" for name, digest in unexpected)
        )

    stale = sorted(ALLOWED_COMMITTED_DUPLICATES - actual)
    if stale:
        raise AssertionError(
            "Fixed/removed duplicated shim(s) still in ALLOWED_COMMITTED_DUPLICATES (shrink the list, #8486):\n"
            + "\n".join(f"  - {name} ({digest})" for name, digest in stale)
        )
