# ==============================================================================
# GitGalaxy Tool: the skeleton-driven forges as one pipeline (#3657)
#
# PURPOSE:
# The forges that build from the refractor's verified skeleton (06_skeleton,
# #3614) -- CICS endpoints and contract DTOs (#3615), service-to-service calls
# (#3616), VSAM repositories (#3617), and the ones to come (#3618-#3622) -- are
# planned together, over one shared registry of class names, and hand the
# cobol-to-java controller three things: the files to write, each program's
# service extras (merged), and the audit lines. The controller wires this one
# object instead of every forge.
# ==============================================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from gitgalaxy.tools.cobol_to_cobol.skeleton_export import (
    ESTATE_JOINS,
    FILE_CHANNELS,
    INTERFACE_FIELD,
    PROGRAM_JOINS,
    load_confidence,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_call_forge import CallForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import ClassNames, TraceLog, merge_extras
from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import Db2Forge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_messaging_forge import MessagingForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_screen_forge import ScreenForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CicsForge, CicsProgram, load_skeletons
from gitgalaxy.tools.cobol_to_java.cobol_to_java_uow_forge import UowForge
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


class SkeletonForges:
    """Every skeleton-driven forge, planned over the same skeletons and class-name registry."""

    def __init__(self, skeleton_dir: Path, package: str, target: JavaTarget) -> None:
        self.skeletons = load_skeletons(skeleton_dir)
        estate_file = skeleton_dir / "estate.json"
        self.estate = json.loads(estate_file.read_text(encoding="utf-8")) if estate_file.is_file() else {}
        self.names = ClassNames()
        # #3650: every fact cites its skeleton section's ledger field and field-testing status
        ledger_of = {name: fld for name, (_, fld) in {**FILE_CHANNELS, **PROGRAM_JOINS}.items()}
        ledger_of.update(ESTATE_JOINS)
        ledger_of["interface"] = INTERFACE_FIELD
        self.trace = TraceLog(ledger_of, load_confidence())
        self.cics = CicsForge(self.skeletons, package, target, self.names, trace=self.trace)
        self.calls = CallForge(self.skeletons, self.cics, package, target, trace=self.trace)
        self.repos = RepositoryForge(self.estate, self.skeletons, package, target, self.names, trace=self.trace)
        self.uow = UowForge(self.skeletons, package, target, self.names, trace=self.trace)
        self.db2 = Db2Forge(self.estate, self.skeletons, package, target, self.names, trace=self.trace)  # #3618
        self.screens = ScreenForge(self.skeletons, package, target, self.names, trace=self.trace)  # #3619
        self.messaging = MessagingForge(self.skeletons, self.estate, package, target, trace=self.trace)  # #3620

    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        """(java_dirs key, sub-directory) -> {class name: Java source}, every generated file."""
        repos = self.repos
        entities = {st.entity: repos.entity_source(st) for st in repos.stores}
        entities.update({st.key_type: repos.key_source(st) or "" for st in repos.stores if st.composite})
        out: dict[tuple[str, ...], dict[str, str]] = {
            ("entity", "vsam"): entities,
            ("repository", "vsam"): {st.repository: repos.repository_source(st) for st in repos.stores},
            ("dto", "contract"): self.cics.dto_sources(),
            ("base_pkg", "client"): self.calls.client_sources(),
            **self.db2.sources(),
        }
        for where, files in self.uow.sources().items():  # #3621: exception + web packages
            out.setdefault(where, {}).update(files)
        for where, files in self.screens.sources().items():  # #3619: view models + screen controllers
            out.setdefault(where, {}).update(files)
        for where, files in self.messaging.sources().items():  # #3620: ports, adapter, MQ listeners
            out.setdefault(where, {}).update(files)
        return out

    def write(self, java_dirs: dict[str, Path], header: str) -> dict[str, int]:
        """Writes every generated file under the Spring Boot tree; returns what the stats count."""
        (java_dirs["dto"] / "contract").mkdir(parents=True, exist_ok=True)  # present even when empty, as before
        for (base, sub), files in self.sources().items():
            out_dir = java_dirs[base] / sub
            for name, code in files.items():
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"{name}.java").write_text(header + code, encoding="utf-8")
        for rel, text in self.screens.resources().items():  # #3619: templates/screen.html
            path = java_dirs["resources"] / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return {"entities": len(self.repos.stores), "dtos": len(self.cics.dtos)}

    def summary(self) -> str:
        return (
            f"Generated {len(self.cics.dtos)} program-contract DTOs for {len(self.cics.programs)} CICS programs and "
            f"{len(self.calls.clients)} remote-region clients"
        )

    def class_base(self, key: str) -> str | None:
        """The class base a program's service is generated under, or None when it has no skeleton."""
        return self.calls.cls_of.get(key)

    def cics_program(self, key: str) -> CicsProgram | None:
        return self.cics.programs.get(key)

    def service_extras(self, key: str) -> dict | None:
        """What every forge adds to the program's @Service, merged."""
        prog = self.cics.programs.get(key)
        return merge_extras(
            self.cics.service_extras(prog) if prog is not None else None,
            self.calls.service_extras(key),
            self.repos.service_extras(key),
            self.uow.service_extras(key),
            self.db2.service_extras(key),
            self.screens.service_extras(key),
            self.messaging.service_extras(key),
        )

    def write_audit(self, f: TextIO) -> None:
        """The audit lines for what the forges generated (#3615-#3617)."""
        cics, calls, repos = self.cics, self.calls, self.repos
        with_commarea = sum(1 for p in cics.programs.values() if p.commarea_dto)
        f.write(
            f"  • CICS programs (#3615)    : {len(cics.programs)} -- {with_commarea} with a COMMAREA DTO, "
            f"{sum(len(p.transactions) for p in cics.programs.values())} transaction endpoints, "
            f"{len(cics.dtos)} COMMAREA / channel DTOs\n"
        )
        n = calls.counts
        f.write(
            f"  • Service calls (#3616)    : {n['link']} LINK, {n['xctl']} XCTL, {n['call']} CALL, "
            f"{n['dispatch']} data-driven dispatch, {n['remote']} remote; {len(calls.clients)} remote-region clients\n"
        )
        f.write(
            f"  • VSAM stores (#3617)      : {len(repos.stores)} entities + repositories "
            f"({sum(1 for st in repos.stores if st.key is not None)} keyed by one field); "
            f"{len(repos.unmapped)} not generated\n"
        )
        for label, why in repos.unmapped:
            f.write(f"      - {label}: {why}\n")
        d = self.db2.counts
        f.write(
            f"  • DB2 tables (#3618)       : {d['tables']} repositories ({d['rows']} with DECLAREd row classes), "
            f"{d['statements']} statements as written; {d['positioned']} positioned (TODO)\n"
        )
        if self.screens.screens or self.screens.unresolved:
            f.write(self.screens.audit_line())
        if self.messaging.plan.ts or self.messaging.plan.td or self.messaging.plan.mq:
            f.write(self.messaging.audit_line())
        u = self.uow.counts
        f.write(
            f"  • Units of work (#3621)   : {u['services']} @Transactional services, {u['commits']} commit points, "
            f"{u['rollbacks']} rollback points, {u['abends']} abends, {u['handlers']} handlers; "
            f"{u['unchecked']} unchecked responses\n"
        )

        n_artifacts = len(self.trace.entries)
        n_facts = sum(len(e.facts) for e in self.trace.entries)
        n_todos = sum(len(e.todos) for e in self.trace.entries)
        f.write(
            f"  • Traceability (#3650)    : {n_artifacts} artifacts, {n_facts} facts, {n_todos} TODOs -> traceability.json\n"
        )
