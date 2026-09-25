# ==============================================================================
# GitGalaxy Tool: units of work and handlers -> @Transactional + exception mapping (#3621)
#
# PURPOSE:
# A CICS task is one unit of work: CICS commits at task end and backs out on an
# abend -- the semantics of a @Transactional method boundary. From the verified
# skeleton (06_skeleton, #3614; the `units of work and handlers` channel is
# field-tested), each program's @Service gains:
#   - @Transactional, for a CICS program or one with explicit COMMIT / ROLLBACK;
#   - commitPointL<line>(): an explicit SYNCPOINT / SQL COMMIT, documented as a
#     transaction split point (never a faked commit);
#   - rollbackL<line>(): SYNCPOINT ROLLBACK, throwing UnitOfWorkRollbackException;
#   - abend<CODE>L<line>(): an explicit ABEND, throwing CicsAbendException;
#   - onAbendL<line>() / onCondition<C>L<line>(): HANDLE ABEND / CONDITION routes;
#   - a class note listing the RESP checks and every response never tested.
# The exception classes (package exception) and, with REST controllers, a
# CicsExceptionAdvice mapping conditions to HTTP statuses are generated once,
# only when a service uses them. Every item cites file:line and field testing.
# ==============================================================================
from __future__ import annotations

import re

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import ClassNames, status_text
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget


class UowForge:
    def __init__(self, skeletons: dict[str, dict], package: str, target: JavaTarget, names: ClassNames) -> None:
        self.skeletons = skeletons
        self.package = package
        self.target = target
        self.names = names
        self.counts = {"services": 0, "commits": 0, "rollbacks": 0, "abends": 0, "handlers": 0, "unchecked": 0}
        # Planned once, like the other forges: service_extras only looks the result up.
        self.planned = {key: self._plan(key) for key in sorted(skeletons)}
        self.needs_exceptions = any(
            ex and any("Exception" in m for m in ex.get("methods", [])) for ex in self.planned.values()
        )
        if self.needs_exceptions:
            names.claim("CicsAbendException")
            names.claim("CicsConditionException")
            names.claim("UnitOfWorkRollbackException")
            if self.target.features.rest_controllers:
                names.claim("CicsExceptionAdvice")

    def _generate_exceptions(self) -> dict[str, str]:
        if not self.needs_exceptions:
            return {}

        exceptions = {}
        pkg = self.package

        # CicsAbendException
        code = [
            f"package {pkg}.exception;",
            "",
            "public class CicsAbendException extends RuntimeException {",
            "    private final String abcode;",
            "    private final String program;",
            "    private final String site;",
            "",
            "    public CicsAbendException(String abcode, String program, String site) {",
            '        super("CICS Abend " + abcode + " at " + site);',
            "        this.abcode = abcode;",
            "        this.program = program;",
            "        this.site = site;",
            "    }",
            "",
            "    public String getAbcode() { return abcode; }",
            "    public String getProgram() { return program; }",
            "    public String getSite() { return site; }",
            "}",
        ]
        exceptions["CicsAbendException"] = "\n".join(code) + "\n"

        # CicsConditionException
        code = [
            f"package {pkg}.exception;",
            "",
            "public class CicsConditionException extends RuntimeException {",
            "    private final String condition;",
            "    private final String program;",
            "    private final String site;",
            "",
            "    public CicsConditionException(String condition, String program, String site) {",
            '        super("CICS Condition " + condition + " at " + site);',
            "        this.condition = condition;",
            "        this.program = program;",
            "        this.site = site;",
            "    }",
            "",
            "    public String getCondition() { return condition; }",
            "    public String getProgram() { return program; }",
            "    public String getSite() { return site; }",
            "}",
        ]
        exceptions["CicsConditionException"] = "\n".join(code) + "\n"

        # UnitOfWorkRollbackException
        code = [
            f"package {pkg}.exception;",
            "",
            "public class UnitOfWorkRollbackException extends RuntimeException {",
            "    private final String program;",
            "    private final String site;",
            "",
            "    public UnitOfWorkRollbackException(String program, String site) {",
            '        super("Rollback requested at " + site);',
            "        this.program = program;",
            "        this.site = site;",
            "    }",
            "",
            "    public String getProgram() { return program; }",
            "    public String getSite() { return site; }",
            "}",
        ]
        exceptions["UnitOfWorkRollbackException"] = "\n".join(code) + "\n"

        return exceptions

    def _generate_advice(self) -> dict[str, str]:
        if not self.needs_exceptions or not self.target.features.rest_controllers:
            return {}

        pkg = self.package
        code = [
            f"package {pkg}.web;",
            "",
            "import org.springframework.http.HttpStatus;",
            "import org.springframework.http.ResponseEntity;",
            "import org.springframework.web.bind.annotation.ExceptionHandler;",
            "import org.springframework.web.bind.annotation.RestControllerAdvice;",
            "import java.util.HashMap;",
            "import java.util.Map;",
            f"import {pkg}.exception.CicsAbendException;",
            f"import {pkg}.exception.CicsConditionException;",
            f"import {pkg}.exception.UnitOfWorkRollbackException;",
            "",
            "@RestControllerAdvice",
            "public class CicsExceptionAdvice {",
            "",
            "    @ExceptionHandler(CicsConditionException.class)",
            "    public ResponseEntity<Map<String, String>> handleCondition(CicsConditionException e) {",
            "        Map<String, String> body = new HashMap<>();",
            '        body.put("condition", e.getCondition());',
            '        body.put("program", e.getProgram());',
            '        body.put("site", e.getSite());',
            "        HttpStatus status = HttpStatus.INTERNAL_SERVER_ERROR;",
            '        if (e.getCondition().equals("NOTFND")) {',
            "            status = HttpStatus.NOT_FOUND;",
            '        } else if (e.getCondition().equals("DUPREC") || e.getCondition().equals("DUPKEY")) {',
            "            status = HttpStatus.CONFLICT;",
            '        } else if (e.getCondition().equals("NOTAUTH")) {',
            "            status = HttpStatus.FORBIDDEN;",
            '        } else if (e.getCondition().equals("INVREQ") || e.getCondition().equals("LENGERR")) {',
            "            status = HttpStatus.BAD_REQUEST;",
            "        }",
            "        return new ResponseEntity<>(body, status);",
            "    }",
            "",
            "    @ExceptionHandler(CicsAbendException.class)",
            "    public ResponseEntity<Map<String, String>> handleAbend(CicsAbendException e) {",
            "        Map<String, String> body = new HashMap<>();",
            '        body.put("abcode", e.getAbcode());',
            '        body.put("program", e.getProgram());',
            '        body.put("site", e.getSite());',
            "        return new ResponseEntity<>(body, HttpStatus.INTERNAL_SERVER_ERROR);",
            "    }",
            "",
            "    @ExceptionHandler(UnitOfWorkRollbackException.class)",
            "    public ResponseEntity<Map<String, String>> handleRollback(UnitOfWorkRollbackException e) {",
            "        Map<String, String> body = new HashMap<>();",
            '        body.put("program", e.getProgram());',
            '        body.put("site", e.getSite());',
            "        return new ResponseEntity<>(body, HttpStatus.CONFLICT);",
            "    }",
            "}",
        ]
        return {"CicsExceptionAdvice": "\n".join(code) + "\n"}

    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        srcs: dict[tuple[str, ...], dict[str, str]] = {}
        if self.needs_exceptions:
            srcs[("base_pkg", "exception")] = self._generate_exceptions()
            if self.target.features.rest_controllers:
                srcs[("base_pkg", "web")] = self._generate_advice()
        return srcs

    def service_extras(self, key: str) -> dict | None:
        return self.planned.get(key)

    def _plan(self, key: str) -> dict | None:
        prog_sk = self.skeletons.get(key)
        if not prog_sk:
            return None

        sections = prog_sk.get("sections", {})
        uow_sec = sections.get("uow_handlers")
        handlers = uow_sec.get("facts", []) if uow_sec else []

        has_commit = False
        has_rollback = False

        is_cics = False
        if (
            sections.get("entry_transactions", {}).get("facts")
            or sections.get("cics_resources", {}).get("facts")
            or sections.get("commarea_contracts", {}).get("facts")
        ):
            is_cics = True

        for h in handlers:
            kind = h.get("kind")
            if kind == "COMMIT":
                has_commit = True
            elif kind == "ROLLBACK":
                has_rollback = True

        if not (is_cics or has_commit or has_rollback):
            return None

        self.counts["services"] += 1
        extras = {
            "imports": ["import org.springframework.transaction.annotation.Transactional;"],
            "annotations": ["@Transactional"],
            "methods": [],
            "class_doc": [],
        }

        program = key.upper()
        path = prog_sk["program"]["file"]

        # We need to get the units_of_work, error_handlers, unchecked_responses and uow_handlers
        uows = sections.get("units_of_work", {}).get("facts", [])
        uow_sec_info = sections.get("units_of_work", {})

        error_handlers = sections.get("error_handlers", {}).get("facts", [])
        #

        unchecked = sections.get("unchecked_responses", {}).get("facts", [])
        unchecked_sec_info = sections.get("unchecked_responses", {})

        uow_handlers = sections.get("uow_handlers", {}).get("facts", [])
        uow_handlers_sec = sections.get("uow_handlers", {})

        # Also need RESP_CHECKS
        # "RESP checks and unchecked responses: no methods. Add a class-level documentation block"

        # Let's process explicit commits and rollbacks
        for h in uows:
            kind = h.get("kind")
            line = h.get("line")
            verb = h.get("verb", "VERB")
            source = h.get("source", "CICS")
            unit = h.get("unit", "paragraph")
            file_name = h.get("file") or path

            if kind == "COMMIT":
                self.counts["commits"] += 1
                stmt = f"EXEC {source} {verb}".strip()
                method_code = [
                    "    /**",
                    f"     * {stmt} at {file_name}:{line} (paragraph {unit}).",
                    f"     * Units of work and handlers field testing: {status_text(uow_sec_info)}.",
                    "     * commits the work so far and starts a new unit of work; in Spring, split the work at this point into separate @Transactional calls (TransactionTemplate).",
                    "     */",
                    f"    public void commitPointL{line}() {{",
                    f'        log.info("{stmt} at line {line}");',
                    "        // TODO: [AI AGENT] split the transaction here",
                    "    }",
                ]
                extras["methods"].append("\n".join(method_code) + "\n")

            elif kind == "ROLLBACK":
                self.counts["rollbacks"] += 1
                method_code = [
                    "    /**",
                    f"     * EXEC {source} {verb} at {file_name}:{line} (paragraph {unit}): rolls the unit of work back.",
                    f"     * Units of work and handlers field testing: {status_text(uow_sec_info)}.",
                    "     */",
                    f"    public void rollbackL{line}() {{",
                    f'        throw new UnitOfWorkRollbackException("{program}", "{file_name}:{line}");',
                    "    }",
                ]
                extras["methods"].append("\n".join(method_code) + "\n")

        # Now process ABENDs, HANDLE ABEND, HANDLE CONDITION, HANDLE AID from uow_handlers or error_handlers
        for h in uow_handlers:
            kind = h.get("kind")
            if kind not in ("ABEND", "HANDLE_ABEND", "HANDLE_CONDITION"):
                continue

            line = h.get("line")
            condition = h.get("condition")
            target = h.get("target", "x")
            file_name = path

            # Note: error_handlers has unit. uow_handlers doesn't.
            # Let's see if we can find it in error_handlers
            unit = "paragraph"
            for eh in error_handlers:
                if eh.get("line") == line and eh.get("kind") == kind:
                    unit = eh.get("unit", "paragraph")
                    break

            if kind == "ABEND":
                self.counts["abends"] += 1
                # explicit ABEND with an ABCODE
                if not condition:
                    # no ABCODE?
                    continue
                abcode = condition
                # ABCODE may be an identifier (e.g., WS-ABCODE)
                # But it says "sanitise conditions/abcodes: java_class_base / strip non-alnum"
                sanitized_abcode = java_class_base(re.sub(r"[^A-Za-z0-9]", "", abcode))
                method_code = [
                    "    /**",
                    f"     * EXEC CICS ABEND ABCODE({abcode}) at {file_name}:{line} (paragraph {unit}).",
                    f"     * Units of work and handlers field testing: {status_text(uow_handlers_sec)}.",
                    "     * Note: resolved at run time if an identifier.",
                    "     */",
                    f"    public void abend{sanitized_abcode}L{line}() {{",
                    f'        throw new CicsAbendException("{abcode}", "{program}", "{file_name}:{line}");',
                    "    }",
                ]
                extras["methods"].append("\n".join(method_code) + "\n")

            elif kind == "HANDLE_ABEND":
                self.counts["handlers"] += 1
                method_code = [
                    "    /**",
                    f"     * EXEC CICS HANDLE ABEND at {file_name}:{line} (paragraph {unit}) routes abends to {target}.",
                    f"     * Units of work and handlers field testing: {status_text(uow_handlers_sec)}.",
                    "     */",
                    f"    public void onAbendL{line}(CicsAbendException e) {{",
                    f'        log.info("HANDLE ABEND LABEL {target} at line {line}", e);',
                    f"        // TODO: port paragraph {target}'s logic",
                    "    }",
                ]
                extras["methods"].append("\n".join(method_code) + "\n")

            elif kind == "HANDLE_CONDITION":
                self.counts["handlers"] += 1
                if not condition:
                    continue
                sanitized_cond = java_class_base(re.sub(r"[^A-Za-z0-9]", "", condition))
                method_code = [
                    "    /**",
                    f"     * EXEC CICS HANDLE CONDITION at {file_name}:{line} (paragraph {unit}) routes {condition} to {target}.",
                    f"     * Units of work and handlers field testing: {status_text(uow_handlers_sec)}.",
                    "     */",
                    f"    public void onCondition{sanitized_cond}L{line}(CicsConditionException e) {{",
                    f'        log.info("HANDLE CONDITION {condition} LABEL {target} at line {line}", e);',
                    f"        // TODO: port paragraph {target}'s logic",
                    "    }",
                ]
                extras["methods"].append("\n".join(method_code) + "\n")

        class_doc_lines = []
        resp_checks = [h for h in uow_handlers if h.get("kind") == "RESP_CHECK"]

        handle_aids = [h for h in uow_handlers if h.get("kind") == "HANDLE_AID"]
        if handle_aids:
            class_doc_lines.append(f"HANDLE AID mapping (field testing: {status_text(uow_handlers_sec)}):")
            class_doc_lines.extend(
                f"  HANDLE AID at line {h.get('line')}: {h.get('condition')} -> {h.get('target')}"
                for h in handle_aids[:30]
            )
            if len(handle_aids) > 30:
                class_doc_lines.append(f"  ... and {len(handle_aids) - 30} more")
            class_doc_lines.append("")

        if resp_checks or unchecked:
            status = status_text(uow_handlers_sec)
            if not resp_checks and unchecked:
                status = status_text(unchecked_sec_info)
            class_doc_lines.append(f"Response handling (field testing: {status}):")

            entries = []
            for h in resp_checks:
                conditions = h.get("condition")
                if not conditions:
                    continue
                verb = h.get("verb", "VERB")
                line = h.get("line")
                entries.append(f"{verb} at line {line} tests {conditions}")

            for h in unchecked:
                verb = h.get("verb", "VERB")
                line = h.get("line")
                unit = h.get("unit", "paragraph")
                entries.append(f"TODO: the RESP of {verb} at line {line} (paragraph {unit}) is never tested")
                self.counts["unchecked"] += 1

            for i, entry in enumerate(entries):
                if i < 30:
                    class_doc_lines.append(entry)
                else:
                    class_doc_lines.append(f"... and {len(entries) - 30} more")
                    break

        if class_doc_lines:
            extras["class_doc"] = class_doc_lines

        if any("Exception" in m for m in extras["methods"]):
            extras["imports"].append(f"import {self.package}.exception.*;")
        if not extras["methods"]:
            del extras["methods"]
        if not extras["class_doc"]:
            del extras["class_doc"]

        return extras
