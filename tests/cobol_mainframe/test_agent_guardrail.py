"""#3652: the AI-agent guardrail -- agent changes checked against the verified skeleton.

Pins the Java reader (annotations, records, text blocks, comments), each rule on a
small baseline -- a legitimate edit passes, each kind of hallucination is caught -- the
ticket-result mode, and a real run: generation writes the baseline, an untouched project
is clean, and a planted invented call is rejected.
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_guardrail import build_baseline, check, main, read_java

PKG = "src/main/java/p"

SERVICE = """package p.service;

import java.util.concurrent.ExecutorService;
import p.repository.AccountRepository;

/** Calls OtherService in a comment only. */
@Service
public class MenuService {
    private static final Logger log = LoggerFactory.getLogger(MenuService.class);
    private final AccountRepository accountRepository;
    private final ObjectProvider<AcctService> acctService;

    public void run() {
        String sql = \"\"\"
            SELECT BAL FROM ACCOUNT WHERE ID = :id
            \"\"\";
        String note = "FakeService in a string";
    }
}
"""

DTO = """package p.dto;

@Data
public class MenuCommarea {
    @Column(name = "WS_ID", length = 5)
    private String wsId;
    private BigDecimal wsAmount = BigDecimal.ZERO;
}
"""

RECORD = "package p.dto;\n\npublic record AcctRow(String acctId, Map<String, Integer> totals) {}\n"

CONTROLLER = """package p.controller;

@RestController
public class MenuController {
    @PostMapping("/transaction/MENU")
    public MenuCommarea transactionMENU(@RequestBody MenuCommarea req) { return req; }
}
"""


def _project(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


BASE = {f"{PKG}/service/MenuService.java": SERVICE, f"{PKG}/dto/MenuCommarea.java": DTO,
        f"{PKG}/dto/AcctRow.java": RECORD, f"{PKG}/controller/MenuController.java": CONTROLLER,
        f"{PKG}/service/AcctService.java": "package p.service;\npublic class AcctService {}\n",
        f"{PKG}/service/BatchService.java": "package p.service;\npublic class BatchService {}\n",
        f"{PKG}/repository/AccountRepository.java": "package p.repository;\npublic interface AccountRepository {}\n"}  # fmt: skip


def test_the_java_reader():
    svc = read_java(SERVICE)
    assert svc["classes"] == ["MenuService"]
    assert svc["fields"] == ["accountRepository", "acctService"]  # the static logger is not state
    assert svc["refs"] == ["AccountRepository", "AcctService"]  # not the comment's, the string's or the library's
    assert svc["tables"] == ["ACCOUNT"]  # from the text block
    assert read_java(DTO)["fields"] == ["wsAmount", "wsId"]  # an annotated field is a field
    assert read_java(RECORD)["fields"] == ["acctId", "totals"]  # a record's components
    assert read_java(CONTROLLER)["endpoints"] == ["transactionMENU"]


def test_a_legitimate_edit_passes_and_each_hallucination_is_caught(tmp_path):
    _project(tmp_path, BASE)
    baseline = build_baseline(tmp_path, extra_calls={"MenuService": {"LegacyService"}})
    current = dict(BASE)
    current[f"{PKG}/service/MenuService.java"] = SERVICE.replace(
        'String note = "FakeService in a string";',
        "accountRepository.findAll(); acctService.getObject(); ExecutorService pool = null;\n"
        "        LegacyService mock = null;",  # the program's mock of an unresolved CALL: allowed
    )
    assert check(baseline, current)["violations"] == []

    current[f"{PKG}/service/MenuService.java"] = SERVICE.replace(
        'String note = "FakeService in a string";',
        'BatchService b = null; PaymentService p = null; String q = "UPDATE LOYALTY SET X = 1";',
    )
    current[f"{PKG}/dto/MenuCommarea.java"] = DTO.replace("    private String wsId;", "    private String wsTier;")
    current[f"{PKG}/controller/MenuController.java"] = CONTROLLER.replace(
        "}\n}", '}\n    @GetMapping("/refund")\n    public String refund() { return ""; }\n}'
    )
    current[f"{PKG}/service/RefundService.java"] = "package p.service;\npublic class RefundService {}\n"
    current[f"{PKG}/util/Dates.java"] = "package p.util;\npublic class Dates {}\n"
    del current[f"{PKG}/dto/AcctRow.java"]
    report = check(baseline, current)
    got = [(v["rule"], v["file"].rsplit("/", 1)[-1], v["detail"].split(",")[0]) for v in report["violations"]]
    assert got == [
        ("new-endpoint", "MenuController.java", "new entry point refund: the skeleton defines no such transaction"),
        ("layout-changed", "MenuCommarea.java", "adds field wsTier"),
        ("layout-changed", "MenuCommarea.java", "drops field wsId of the verified layout"),
        ("unknown-call", "MenuService.java", "calls BatchService"),  # exists; MENU never calls it
        ("unknown-call", "MenuService.java", "calls PaymentService"),  # exists nowhere
        ("unknown-table", "MenuService.java", "SQL names table LOYALTY"),
        ("new-component", "RefundService.java", "new class RefundService: the skeleton has no such program"),
    ]
    assert [(n["rule"], n["file"].rsplit("/", 1)[-1]) for n in report["notices"]] == [
        ("new-component", "Dates.java"),
        ("deleted", "AcctRow.java"),
    ]
    assert report["summary"]["by_rule"] == {"layout-changed": 2, "new-component": 1, "new-endpoint": 1,
                                            "unknown-call": 2, "unknown-table": 1}  # fmt: skip


def test_a_ticket_result_is_checked_and_carries_its_verdict(tmp_path):
    _project(tmp_path, BASE)
    (tmp_path / "guardrail_baseline.json").write_text(json.dumps(build_baseline(tmp_path)), encoding="utf-8")
    ticket = tmp_path / "MENU_java_service_job.json"
    ticket.write_text(json.dumps({"target_program": "MENU"}), encoding="utf-8")
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps({"diagnosis": "ok", "java_code": SERVICE}), encoding="utf-8")
    bad.write_text(json.dumps({"java_code": SERVICE.replace("AcctService>", "FraudService>")}), encoding="utf-8")

    assert main([str(tmp_path), "--result", str(ticket), str(good)]) == 0
    assert json.loads(good.read_text(encoding="utf-8"))["guardrail"] == {"status": "passed", "violations": []}
    assert main([str(tmp_path), "--result", str(ticket), str(bad)]) == 1
    verdict = json.loads(bad.read_text(encoding="utf-8"))["guardrail"]
    assert verdict["status"] == "rejected" and "FraudService" in verdict["violations"][0]["detail"]
    assert (tmp_path / "agent_guardrail.md").read_text(encoding="utf-8").startswith("# AI agent guardrail")


def test_without_a_baseline_it_says_how_to_get_one(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    assert "regenerate the project with cobol-to-java" in capsys.readouterr().out


MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('ACCTINQ') END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

ACCTINQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""

LONER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LONER.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""


def test_a_real_run_writes_the_baseline_and_rejects_an_invented_call(tmp_path):
    repo = tmp_path / "estate"
    _project(repo, {"cbl/MENU.cbl": MENU, "cbl/ACCTINQ.cbl": ACCTINQ, "cbl/LONER.cbl": LONER,
                    "csd/APP.csd": " DEFINE TRANSACTION(MENU) GROUP(APP)\n        PROGRAM(MENU)\n"})  # fmt: skip
    db = scan_to_db(repo, tmp_path / "scan")
    work = tmp_path / "work" / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = (tmp_path / "work").glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = (tmp_path / "work").glob("estate_gitgalaxy_java_spring_*")
    baseline = json.loads((java / "guardrail_baseline.json").read_text(encoding="utf-8"))
    menu = next(f for r, f in baseline["files"].items() if r.endswith("/service/MenuService.java"))
    assert menu["program"] == "cbl/MENU.cbl" and "AcctinqService" in menu["calls"]
    assert "[4] AI AGENT GUARDRAIL" in (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert main([str(java)]) == 0  # untouched: clean

    svc = next(java.rglob("MenuService.java"))
    svc.write_text(svc.read_text(encoding="utf-8").replace(
        "public class MenuService {", "public class MenuService {\n    private LonerService loner;"
    ), encoding="utf-8")  # fmt: skip
    assert main([str(java)]) == 1  # LONER exists, but MENU never calls it
    report = json.loads((java / "agent_guardrail.json").read_text(encoding="utf-8"))
    assert [(v["rule"], v["program"]) for v in report["violations"]] == [("unknown-call", "cbl/MENU.cbl")]
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "  • Checked  : 1 changed files: 1 violations, 0 notices -> agent_guardrail.md" in audit
    assert audit.count("[4] AI AGENT GUARDRAIL") == 1  # the section is replaced, not appended
